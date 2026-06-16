"""CareLenseAI FastAPI backend — serves /api and static Next.js export."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import FastAPI, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.backend import agent, genie, gold_reads
from app.backend.config import settings
from app.backend.lakebase import PlannerStore, _planner_id, planner_backend
from pipeline.source_urls import first_source_url
from app.backend.models import (
    AskRequest,
    NoteRequest,
    OverrideRequest,
    ScenarioIn,
    VerificationPlanRequest,
    WatchRequest,
)
from pipeline.lexicons import CAPABILITIES

app = FastAPI(title="CareLenseAI Medical Desert Planner", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            {"error": exc.detail, "path": request.url.path},
            status_code=exc.status_code,
        )
    raise exc


@app.exception_handler(Exception)
async def api_exception_handler(request: Request, exc: Exception):
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            {"error": str(exc), "type": type(exc).__name__, "path": request.url.path},
            status_code=500,
        )
    raise exc


def _store(request: Request) -> PlannerStore:
    headers = dict(request.headers)
    return PlannerStore(_planner_id(headers))


def _cap_label(cap_id: str) -> str:
    return next((c["label"] for c in CAPABILITIES if c["id"] == cap_id), cap_id)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/api/health/data")
def api_health_data():
    """Diagnostics: config + gold row probe (visible when SQL fails)."""
    s = settings()
    out = {
        "status": "ok",
        "sql_mode": "statement_execution",
        "warehouse_id": s["warehouse_id"] or None,
        "gold_catalog": s["gold_catalog"],
        "gold_schema": s["gold_schema"],
        "gold_table": f"{s['gold_catalog']}.{s['gold_schema']}.gold_geo_capability",
        "env": {
            "app_name": os.getenv("DATABRICKS_APP_NAME"),
            "server_host": bool(os.getenv("DATABRICKS_SERVER_HOST")),
            "client_id": bool(os.getenv("DATABRICKS_CLIENT_ID")),
        },
        "planner_backend": planner_backend(),
        "agent": {
            "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
            "agent_endpoint_configured": bool(os.getenv("AGENT_ENDPOINT")),
        },
    }
    try:
        rows = gold_reads.get_units("icu", "state")
        out["icu_state_rows"] = len(rows)
        out["summary"] = gold_reads.summarize(
            gold_reads.apply_overlay(rows, {}, set(), {})
        )
    except Exception as exc:
        out["status"] = "error"
        out["error"] = str(exc)
    return out


@app.get("/api/capabilities")
def api_capabilities():
    return gold_reads.get_capabilities()


@app.get("/api/summary")
def api_summary(request: Request, cap: str = "icu", grain: str = "state"):
    store = _store(request)
    units = gold_reads.get_units(cap, grain)
    merged = gold_reads.apply_overlay(
        units, store.get_overrides(cap), store.get_watch_set(cap), store.get_notes(cap)
    )
    return gold_reads.summarize(merged)


@app.get("/api/units")
def api_units(
    request: Request,
    cap: str = "icu",
    grain: str = "state",
    sort: str = "priority",
    q: str = "",
    state: str = "",
):
    store = _store(request)
    units = gold_reads.get_units(cap, grain)
    merged = gold_reads.apply_overlay(
        units, store.get_overrides(cap), store.get_watch_set(cap), store.get_notes(cap)
    )
    if state:
        merged = [u for u in merged if state.lower() in u.get("state", "").lower()]
    if q.strip():
        ql = q.lower()
        merged = [
            u for u in merged
            if ql in (u["name"] + u["sub"] + u.get("state", "")).lower()
        ]
    if sort == "az":
        merged.sort(key=lambda u: u["name"])
    elif sort == "risk":
        merged.sort(key=lambda u: -u["risk"])
    elif sort == "conf":
        merged.sort(key=lambda u: u["conf"])
    else:
        merged.sort(key=lambda u: -u["priority"])
    return merged


@app.get("/api/unit")
def api_unit(request: Request, cap: str = "icu", unit_key: str = ""):
    store = _store(request)
    detail = gold_reads.get_unit_detail(cap, unit_key)
    if not detail:
        return JSONResponse({"error": "Unit not found"}, status_code=404)

    overrides = store.get_overrides(cap)
    base = detail.get("verdict", "unknown")
    verdict = overrides.get(unit_key, base)

    evidence = []
    for c in detail.get("citations", []):
        tier = (c.get("tier") or "weak").upper()
        evidence.append({
            "facility": c.get("facility_name", ""),
            "quote": f'"{c.get("matched_span", "")}"',
            "tier": tier,
            "source_field": c.get("source_field", ""),
            "rec_id": c.get("rec_id", ""),
            "source_url": first_source_url(c.get("source_url")),
            "source": f"{c.get('rec_id')} · {cap}/{c.get('source_field')}",
        })

    need = {
        "index": detail.get("need_index"),
        "signal_strength": detail.get("need_signal_strength"),
        "drivers": detail.get("need_drivers_parsed", []),
        "nfhs_matched": bool(detail.get("nfhs_matched")),
    }
    if not need["nfhs_matched"]:
        need["index"] = None

    return {
        "unit_key": unit_key,
        "name": detail.get("unit_name"),
        "sub": detail.get("sub"),
        "risk": int(detail.get("risk", 0)),
        "conf": int(detail.get("confidence", 0)),
        "verdict": verdict,
        "base_verdict": base,
        "overridden": unit_key in overrides,
        "supply": {
            "strong": int(detail.get("strong_count", 0)),
            "partial": int(detail.get("partial_count", 0)),
            "weak": int(detail.get("weak_count", 0)),
            "n": int(detail.get("n_facilities", 0)),
        },
        "need": need,
        "evidence": evidence,
        "note": store.get_notes(cap).get(unit_key, ""),
        "watched": unit_key in store.get_watch_set(cap),
    }


@app.get("/api/geo")
def api_geo(request: Request, grain: str = "state", cap: str = "icu"):
    store = _store(request)
    units = gold_reads.get_units(cap, grain)
    merged = gold_reads.apply_overlay(
        units, store.get_overrides(cap), store.get_watch_set(cap), store.get_notes(cap)
    )
    out = []
    for u in merged:
        key = u["unit_key"]
        state = key.split("|")[-1] if "|" in key else u["name"]
        district = u["name"] if grain == "district" else None
        pin3 = None
        if grain == "pin" and key.startswith("pin:"):
            pin3 = key.split(":")[1].replace("xxx", "")
        out.append({
            "unit_key": key,
            "state": state,
            "district": district,
            "pin3": pin3,
            "risk": u["risk"],
            "conf": u["conf"],
            "verdict": u["verdict"],
            "name": u["name"],
        })
    return out


@app.post("/api/watch")
def api_watch(body: WatchRequest, request: Request):
    _store(request).set_watch(body.cap, body.unit_key, body.on)
    return {"ok": True}


@app.put("/api/note")
def api_note(body: NoteRequest, request: Request):
    _store(request).set_note(body.cap, body.unit_key, body.note)
    return {"ok": True}


@app.put("/api/override")
def api_override(body: OverrideRequest, request: Request):
    _store(request).set_override(body.cap, body.unit_key, body.verdict)
    return {"ok": True}


@app.get("/api/scenarios")
def api_scenarios(request: Request):
    return _store(request).list_scenarios()


@app.post("/api/scenario")
def api_save_scenario(body: ScenarioIn, request: Request):
    _store(request).save_scenario(body.model_dump())
    return {"ok": True}


@app.delete("/api/scenario/{name}")
def api_delete_scenario(name: str, request: Request):
    _store(request).delete_scenario(name)
    return {"ok": True}


@app.post("/api/ask")
def api_ask(body: AskRequest):
    return genie.ask_genie(body.question)


@app.post("/api/verification-plan")
def api_verification_plan(body: VerificationPlanRequest):
    return agent.generate_verification_plan(body.unit_keys, body.cap)


@app.get("/api/export")
def api_export(request: Request, cap: str = "icu"):
    store = _store(request)
    units = gold_reads.get_units(cap, "state")
    merged = gold_reads.apply_overlay(
        units, store.get_overrides(cap), store.get_watch_set(cap), store.get_notes(cap)
    )
    watch = store.get_watch_set(cap)
    notes = store.get_notes(cap)
    watched = [u for u in merged if u["unit_key"] in watch]
    for u in watched:
        u["note"] = notes.get(u["unit_key"], "")
    return agent.build_export_payload(watched, cap)


# Static frontend
_frontend = settings()["frontend_dir"]
if os.path.isdir(_frontend):
    app.mount("/_next", StaticFiles(directory=os.path.join(_frontend, "_next")), name="next")
    app.mount("/assets", StaticFiles(directory=_frontend), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        fp = os.path.join(_frontend, full_path)
        if full_path and os.path.isfile(fp):
            return FileResponse(fp)
        index = os.path.join(_frontend, "index.html")
        if os.path.isfile(index):
            return FileResponse(index)
        return JSONResponse({"error": "Frontend not built"}, status_code=503)
