"""Care-Gap Analyst agent — verification plans and export narratives."""

from __future__ import annotations

import json
import os
from typing import Any

from app.backend import gold_reads


def generate_verification_plan(unit_keys: list[str], cap: str) -> dict[str, Any]:
    """Draft field verification plan citing rec_ids and NFHS indicators."""
    units = []
    for key in unit_keys:
        detail = gold_reads.get_unit_detail(cap, key)
        if detail:
            units.append(detail)

    if not units:
        return {"plan": "No units selected.", "sections": []}

    endpoint = os.getenv("AGENT_ENDPOINT", "").strip()
    if endpoint:
        try:
            return _agent_bricks_plan(units, cap, endpoint)
        except Exception:
            pass

    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key:
        try:
            return _openai_plan(units, cap, api_key)
        except Exception:
            pass

    return _deterministic_plan(units, cap)


def _deterministic_plan(units: list[dict], cap: str) -> dict[str, Any]:
    sections = []
    for u in units:
        citations = u.get("citations", [])
        drivers = u.get("need_drivers_parsed", [])
        rec_ids = [c.get("rec_id") for c in citations if c.get("rec_id")]
        actions = []

        if u.get("verdict") == "blind" or u.get("confidence", 0) < 58:
            actions.append(
                "Commission field verification — risk is elevated but evidence is thin."
            )
        elif u.get("verdict") == "desert":
            actions.append(
                "Prioritise capacity build-out; pipeline shows strong evidence of gap."
            )
        else:
            actions.append("Maintain monitoring; re-verify if new facilities register.")

        if not u.get("nfhs_matched"):
            actions.append("Need signal unavailable — do not infer demand from NFHS.")

        if rec_ids:
            actions.append(f"Verify claims at facilities: {', '.join(rec_ids[:5])}.")
        else:
            actions.append("Insufficient facility citations — site visit required.")

        if drivers:
            driver_labels = [d.get("label", "") for d in drivers[:3]]
            actions.append(f"Cross-check NFHS indicators: {', '.join(driver_labels)}.")

        sections.append({
            "unit_key": u.get("unit_key"),
            "name": u.get("unit_name"),
            "verdict": u.get("verdict"),
            "risk": u.get("risk"),
            "confidence": u.get("confidence"),
            "actions": actions,
            "citations": rec_ids,
        })

    narrative = "\n\n".join(
        f"**{s['name']}** (RISK {s['risk']}, CONF {s['confidence']})\n"
        + "\n".join(f"- {a}" for a in s["actions"])
        for s in sections
    )
    return {"plan": narrative, "sections": sections}


def _openai_plan(units: list[dict], cap: str, api_key: str) -> dict[str, Any]:
    import urllib.request

    context = []
    for u in units:
        rec_ids = [c.get("rec_id") for c in u.get("citations", []) if c.get("rec_id")]
        context.append({
            "unit": u.get("unit_name"),
            "verdict": u.get("verdict"),
            "risk": u.get("risk"),
            "confidence": u.get("confidence"),
            "rec_ids": rec_ids,
            "nfhs_matched": u.get("nfhs_matched"),
            "need_drivers": u.get("need_drivers_parsed", []),
        })

    prompt = (
        "You are Care-Gap Analyst. Draft a concise field verification plan for NGO coordinators. "
        "RULES: Cite rec_ids and NFHS indicator names from the data, or say 'insufficient evidence'. "
        "NEVER invent risk, confidence, or verdict numbers — use only those provided.\n\n"
        f"Capability: {cap}\nData: {json.dumps(context, indent=2)}"
    )

    body = json.dumps({
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "Care-Gap Analyst for Indian healthcare planning."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }).encode()

    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())

    plan = data["choices"][0]["message"]["content"]
    return {"plan": plan, "sections": context}


def _agent_bricks_plan(units: list[dict], cap: str, endpoint: str) -> dict[str, Any]:
    """Call deployed Agent Bricks / model-serving endpoint."""
    import urllib.request

    context = []
    for u in units:
        rec_ids = [c.get("rec_id") for c in u.get("citations", []) if c.get("rec_id")]
        context.append({
            "unit": u.get("unit_name"),
            "unit_key": u.get("unit_key"),
            "verdict": u.get("verdict"),
            "risk": u.get("risk"),
            "confidence": u.get("confidence"),
            "rec_ids": rec_ids,
            "nfhs_matched": u.get("nfhs_matched"),
            "need_drivers": u.get("need_drivers_parsed", []),
        })

    body = json.dumps({
        "capability": cap,
        "units": context,
        "instructions": (
            "Draft a field verification plan. Cite rec_ids and NFHS indicators; "
            "never invent risk, confidence, or verdict numbers."
        ),
    }).encode()

    headers = {"Content-Type": "application/json"}
    token = os.getenv("DATABRICKS_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read())

    if isinstance(data, dict):
        if "plan" in data:
            return {"plan": data["plan"], "sections": data.get("sections", context)}
        for key in ("output", "text", "response", "message"):
            if data.get(key):
                return {"plan": str(data[key]), "sections": context}
        if "choices" in data:
            plan = data["choices"][0]["message"]["content"]
            return {"plan": plan, "sections": context}

    return {"plan": json.dumps(data), "sections": context}


def build_export_payload(watched_units: list[dict], cap: str) -> dict[str, Any]:
    regions = []
    for u in watched_units:
        detail = gold_reads.get_unit_detail(cap, u["unit_key"])
        verdict = u.get("verdict", "unknown")
        action = {
            "desert": "Prioritise capacity build-out; evidence is strong and risk is high.",
            "blind": "Commission field verification — risk is high but evidence is thin.",
            "served": "Maintain; monitor for regression in coverage.",
            "unknown": "Improve data capture before drawing any planning conclusion.",
        }.get(verdict, "Review manually.")
        regions.append({
            "name": u.get("name"),
            "sub": u.get("sub"),
            "risk": u.get("risk"),
            "conf": u.get("conf"),
            "verdict": verdict,
            "action": action,
            "note": u.get("note", ""),
            "citations": [
                {
                    "facility": c.get("facility_name"),
                    "quote": c.get("matched_span"),
                    "rec_id": c.get("rec_id"),
                    "source": f"{c.get('rec_id')} · {cap}/{c.get('source_field')}",
                }
                for c in (detail or {}).get("citations", [])[:3]
            ],
        })
    return {"capability": cap, "regions": regions}
