"""Shared Gold table computation — used by CLI script and Databricks notebook."""

from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd

from pipeline.config import CONFIDENCE_WEIGHTS
from pipeline.lexicons import LEXICONS
from pipeline.scoring_core import aggregate_unit, finalize_unit_scores
from pipeline.source_urls import first_source_url

SOURCE_CAT = "databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset"


def _clean_state(s: str) -> str | None:
    if not s or len(str(s)) > 60 or str(s).startswith(("{", "[")):
        return None
    return str(s).strip()


def _clean_pin(s: str) -> str | None:
    if not s:
        return None
    digits = re.sub(r"\D", "", str(s))[:6]
    return digits if len(digits) == 6 else None


def _norm_key(s: Any) -> str:
    return re.sub(r"[^a-z]", "", str(s or "").lower().replace("district", ""))


def compute_gold_tables(
    facilities: pd.DataFrame,
    pincodes: pd.DataFrame,
    nfhs: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (gold_geo_capability, gold_evidence_citations) DataFrames."""
    pin_map: dict[str, dict] = {}
    for _, r in pincodes.iterrows():
        try:
            pin = str(int(r["pincode"]))
        except (TypeError, ValueError):
            continue
        pin_map[pin] = {
            "district": r["district"],
            "state": r["statename"],
            "pin3": pin[:3].zfill(3),
        }

    nfhs_map: dict[tuple[str, str], dict] = {}
    for _, r in nfhs.iterrows():
        nfhs_map[(_norm_key(r["district_name"]), _norm_key(r["state_ut"]))] = r.to_dict()

    fac_rows = []
    for _, f in facilities.iterrows():
        row = f.to_dict()
        pin = _clean_pin(row.get("address_zipOrPostcode"))
        geo = pin_map.get(pin, {})
        row["district_resolved"] = geo.get("district")
        row["state_resolved"] = geo.get("state") or _clean_state(row.get("address_stateOrRegion"))
        row["pin3"] = geo.get("pin3") or (pin[:3] if pin else None)
        row["geo_resolved"] = bool(geo.get("district"))
        fac_rows.append(row)

    fac_df = pd.DataFrame(fac_rows)
    gold_rows: list[dict] = []
    citation_rows: list[dict] = []

    for cap_id in LEXICONS:
        for grain in ("state", "district", "pin"):
            groups: dict[str, list] = {}
            meta: dict[str, dict] = {}

            for _, fac in fac_df.iterrows():
                state = fac.get("state_resolved")
                if not state:
                    continue
                if grain == "state":
                    key, name, sub = f"state:{state}", state, "State"
                elif grain == "district":
                    dist = fac.get("district_resolved")
                    if not dist:
                        continue
                    key = f"district:{dist}|{state}"
                    name, sub = dist, f"{dist} District · {state}"
                else:
                    pin3 = fac.get("pin3")
                    if not pin3:
                        continue
                    key = f"pin:{pin3}xxx|{state}"
                    name, sub = f"{pin3}xxx · {state}", f"PIN {pin3}xxx · {state}"

                groups.setdefault(key, []).append(fac.to_dict())
                meta[key] = {"name": name, "sub": sub, "state": state}

            units: list[dict] = []
            for key, facs in groups.items():
                m = meta[key]
                dist = m["name"] if grain == "district" else facs[0].get("district_resolved")
                state = m["state"]
                nfhs_key = (_norm_key(dist), _norm_key(state)) if dist else (None, None)
                nfhs_row = nfhs_map.get(nfhs_key) if nfhs_key[0] else None
                nfhs_matched = nfhs_row is not None
                hh = float(nfhs_row["households_surveyed"]) if nfhs_row else None

                agg = aggregate_unit(facs, nfhs_row, cap_id, nfhs_matched, hh)
                conf_parts = agg.pop("confidence_parts")
                evidence = agg.pop("evidence_rows")

                conf = round(max(8, min(96,
                    CONFIDENCE_WEIGHTS["evidence_strength"] * conf_parts["evidence_strength"]
                    + CONFIDENCE_WEIGHTS["meta_credibility"] * conf_parts["meta_credibility"]
                    + CONFIDENCE_WEIGHTS["need_data_density"] * conf_parts["need_data_density"]
                    + CONFIDENCE_WEIGHTS["n_facilities"] * conf_parts["n_facilities"]
                    + CONFIDENCE_WEIGHTS["capability_signal"] * conf_parts["capability_signal"]
                )))

                units.append({
                    "grain": grain,
                    "unit_key": key,
                    "unit_name": m["name"],
                    "sub": m["sub"],
                    "capability": cap_id,
                    "confidence": conf,
                    **agg,
                })

                for ev in evidence:
                    citation_rows.append({
                        "grain": grain,
                        "unit_key": key,
                        "capability": cap_id,
                        **ev,
                    })

            gold_rows.extend(finalize_unit_scores(units, cap_id))

    gold_df = pd.DataFrame(gold_rows)
    cite_df = pd.DataFrame(citation_rows)

    if not gold_df.empty:
        gold_df["need_drivers"] = gold_df["need_drivers"].apply(
            lambda x: json.dumps(x) if isinstance(x, (list, dict)) else (x or "[]")
        )
        gold_df["nfhs_matched"] = gold_df["nfhs_matched"].astype(bool)

    return gold_df, cite_df


GOLD_COLUMNS = [
    "grain", "unit_key", "unit_name", "sub", "capability",
    "risk", "confidence", "verdict", "n_facilities",
    "strong_count", "partial_count", "weak_count",
    "supply_index", "need_index", "need_signal_strength",
    "nfhs_matched", "need_drivers", "priority", "supply_raw",
]

CITE_COLUMNS = [
    "grain", "unit_key", "capability", "facility_name",
    "matched_span", "tier", "source_field", "rec_id", "source_url",
]
