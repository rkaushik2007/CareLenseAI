"""Deterministic scoring core — shared by pipeline materialization and validation."""

from __future__ import annotations

import math
import re
from typing import Any

from pipeline.config import (
    CONFIDENCE_WEIGHTS,
    NEED_MAP,
    SIGNAL_STRENGTH_SCORES,
    STRUCTURED_FIELDS,
    TIER_WEIGHTS,
)
from pipeline.lexicons import LEXICONS, PRIORITY_WEIGHTS, VERDICT_THRESHOLD

THRESHOLD = VERDICT_THRESHOLD


def word_match(text: str, term: str) -> bool:
    if not text:
        return False
    pattern = rf"\b{re.escape(term)}\b"
    return bool(re.search(pattern, text, re.IGNORECASE))


def parse_number(val: Any) -> float | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    m = re.search(r"[\d.]+", s)
    return float(m.group()) if m else None


def assess_tier(row: dict[str, Any], cap_id: str) -> tuple[str, list[str], str, str]:
    """Return tier, matched_fields, matched_span, source_field."""
    terms = LEXICONS.get(cap_id, [])
    matched_fields: list[str] = []
    span = ""
    source_field = ""

    for field in ["capability", "procedure", "equipment", "specialties", "description"]:
        text = str(row.get(field) or "")
        if any(word_match(text, t) for t in terms):
            matched_fields.append(field)

    if not matched_fields:
        return "none", [], "", ""

    structured_hits = [f for f in matched_fields if f in STRUCTURED_FIELDS]
    has_quant = (
        (parse_number(row.get("capacity")) or 0) > 0
        or (parse_number(row.get("numberDoctors")) or 0) > 0
    )

    if len(structured_hits) >= 2 or (len(structured_hits) >= 1 and has_quant):
        tier = "strong"
    elif len(structured_hits) == 1:
        tier = "partial"
    else:
        tier = "weak"

    priority = ["capability", "procedure", "equipment", "specialties", "description"]
    for field in priority:
        if field in matched_fields:
            source_field = field
            text = str(row.get(field) or "")
            for term in terms:
                if word_match(text, term):
                    idx = text.lower().find(term.lower())
                    start = max(0, idx - 60)
                    end = min(len(text), idx + len(term) + 60)
                    span = text[start:end].strip()
                    if start > 0:
                        span = "..." + span
                    if end < len(text):
                        span = span + "..."
                    break
            break

    return tier, matched_fields, span[:160], source_field


def winsor_minmax(values: list[float | None], lo_p: float = 5, hi_p: float = 95) -> list[float | None]:
    """Clip to percentile band then min-max to 0-100."""
    clean = sorted(v for v in values if v is not None)
    if not clean:
        return [None] * len(values)
    lo_idx = max(0, int(len(clean) * lo_p / 100))
    hi_idx = min(len(clean) - 1, int(len(clean) * hi_p / 100))
    lo, hi = clean[lo_idx], clean[hi_idx]
    if hi <= lo:
        return [50.0 if v is not None else None for v in values]
    out = []
    for v in values:
        if v is None:
            out.append(None)
        else:
            clipped = max(lo, min(hi, v))
            out.append(100.0 * (clipped - lo) / (hi - lo))
    return out


def compute_need_index(nfhs_row: dict | None, cap_id: str) -> tuple[float | None, str, list[dict]]:
    """Compute need index and drivers from NFHS row."""
    cfg = NEED_MAP.get(cap_id, {"signal_strength": "none", "indicators": []})
    signal = cfg["signal_strength"]
    if not nfhs_row or not cfg["indicators"]:
        return None, signal, []

    raw_scores: list[float] = []
    drivers: list[dict] = []
    for col, direction in cfg["indicators"]:
        val = parse_number(nfhs_row.get(col))
        if val is None:
            continue
        drivers.append({"label": col, "value": val, "direction": direction})
        raw_scores.append(val)

    if not raw_scores:
        return None, signal, drivers

    # Normalize within indicator set for this row (simple 0-100 mapping)
    need_scores = []
    for col, direction in cfg["indicators"]:
        val = parse_number(nfhs_row.get(col))
        if val is None:
            continue
        # Use raw value scaled heuristically for single-row; batch winsor applied at unit level
        if direction == "lower_is_worse":
            need_scores.append(max(0, min(100, 100 - val)))
        else:
            need_scores.append(max(0, min(100, val)))

    need_index = sum(need_scores) / len(need_scores) if need_scores else None
    return need_index, signal, drivers


def compute_verdict(risk: int, conf: int) -> str:
    if risk >= THRESHOLD and conf >= THRESHOLD:
        return "desert"
    if risk >= THRESHOLD and conf < THRESHOLD:
        return "blind"
    if risk < THRESHOLD and conf >= THRESHOLD:
        return "served"
    return "unknown"


def compute_priority(risk: int, verdict: str) -> float:
    return risk * PRIORITY_WEIGHTS.get(verdict, 1.0)


def meta_credibility(row: dict) -> float:
    score = 0.0
    recency = parse_number(row.get("recency_of_page_update"))
    if recency:
        score += min(40, recency / 3)
    facts = parse_number(row.get("number_of_facts_about_the_organization"))
    if facts:
        score += min(30, facts)
    if str(row.get("affiliated_staff_presence") or "").lower() in ("true", "1", "yes"):
        score += 10
    if str(row.get("source_urls") or "").strip():
        score += 10
    if str(row.get("officialWebsite") or "").strip():
        score += 10
    return min(100, score)


def aggregate_unit(
    facilities: list[dict],
    nfhs_row: dict | None,
    cap_id: str,
    nfhs_matched: bool,
    households_surveyed: float | None,
) -> dict[str, Any]:
    """Score one geographic unit for one capability."""
    tiers = {"strong": 0, "partial": 0, "weak": 0}
    supply_raw = 0.0
    evidence_rows = []

    for fac in facilities:
        tier, fields, span, src = assess_tier(fac, cap_id)
        if tier == "none":
            continue
        tiers[tier] += 1
        supply_raw += TIER_WEIGHTS[tier]
        evidence_rows.append({
            "facility_name": fac.get("name", ""),
            "matched_span": span,
            "tier": tier,
            "source_field": src,
            "rec_id": fac.get("unique_id", ""),
            "source_url": first_source_url(fac.get("source_urls")),
        })

    n_fac = len(facilities)
    n_evidence = tiers["strong"] + tiers["partial"] + tiers["weak"]
    evidence_strength = (
        100.0 * (tiers["strong"] + 0.5 * tiers["partial"]) / max(n_evidence, 1)
        if n_evidence else 0
    )

    meta_scores = [meta_credibility(f) for f in facilities]
    meta_cred = sum(meta_scores) / max(len(meta_scores), 1) if meta_scores else 0

    need_index, need_signal, need_drivers = compute_need_index(nfhs_row, cap_id)

    hh = households_surveyed or 0
    need_density = min(100, 100 * math.log10(1 + hh) / math.log10(1 + 50000)) if nfhs_matched and hh else 0
    n_fac_score = min(100, 100 * math.log10(1 + n_fac) / math.log10(1 + 25))
    cap_signal = SIGNAL_STRENGTH_SCORES.get(need_signal, 15)

    confidence = (
        CONFIDENCE_WEIGHTS["evidence_strength"] * evidence_strength
        + CONFIDENCE_WEIGHTS["meta_credibility"] * meta_cred
        + CONFIDENCE_WEIGHTS["need_data_density"] * need_density
        + CONFIDENCE_WEIGHTS["n_facilities"] * n_fac_score
        + CONFIDENCE_WEIGHTS["capability_signal"] * cap_signal
    )
    confidence = round(max(8, min(96, confidence)))

    return {
        "n_facilities": n_fac,
        "strong_count": tiers["strong"],
        "partial_count": tiers["partial"],
        "weak_count": tiers["weak"],
        "supply_raw": supply_raw,
        "need_index": need_index,
        "need_signal_strength": need_signal,
        "need_drivers": need_drivers,
        "nfhs_matched": nfhs_matched,
        "confidence_parts": {
            "evidence_strength": evidence_strength,
            "meta_credibility": meta_cred,
            "need_data_density": need_density,
            "n_facilities": n_fac_score,
            "capability_signal": cap_signal,
        },
        "evidence_rows": sorted(
            evidence_rows,
            key=lambda e: {"strong": 0, "partial": 1, "weak": 2}.get(e["tier"], 3),
        )[:6],
    }


def finalize_unit_scores(units: list[dict], cap_id: str) -> list[dict]:
    """Apply winsor_minmax for supply/need and compute risk + verdict."""
    supply_raws = [u.get("supply_raw") for u in units]
    supply_indices = winsor_minmax(supply_raws)

    need_raws = [u.get("need_index") for u in units]
    need_indices = winsor_minmax(need_raws)

    for u, supply_idx, need_idx in zip(units, supply_indices, need_indices):
        supply_idx = supply_idx if supply_idx is not None else 0
        supply_deficit = 100 - supply_idx
        u["supply_index"] = round(supply_idx, 1)

        raw_need = u.get("need_index")
        if raw_need is not None and need_idx is not None:
            risk = 0.6 * need_idx + 0.4 * supply_deficit
            u["need_index"] = round(need_idx, 1)
        else:
            risk = supply_deficit
            u["need_index"] = None

        u["risk"] = round(max(6, min(97, risk)))
        u["confidence"] = u.get("confidence", 8)
        u["verdict"] = compute_verdict(u["risk"], u["confidence"])
        u["priority"] = compute_priority(u["risk"], u["verdict"])

    return units
