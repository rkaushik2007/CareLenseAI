"""Read Gold tables from Unity Catalog via SQL warehouse."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from app.backend.config import settings
from pipeline.lexicons import CAPABILITIES, LEXICONS, PRIORITY_WEIGHTS

_cache: dict[str, tuple[float, Any]] = {}




def _on_databricks_app() -> bool:
    return bool(os.getenv("DATABRICKS_APP_NAME") or os.getenv("DATABRICKS_SERVER_HOST"))


def _warehouse_id() -> str:
    return (
        os.getenv("DATABRICKS_WAREHOUSE_ID")
        or os.getenv("WAREHOUSE_ID")
        or settings()["warehouse_id"]
        or ""
    )


def _conn():
    from databricks import sql

    wh = _warehouse_id()
    if not wh:
        raise RuntimeError(
            "DATABRICKS_WAREHOUSE_ID is not set. "
            "Attach a SQL warehouse resource and map it in app.yaml "
            "(valueFrom: sql-warehouse)."
        )

    host = (
        os.getenv("DATABRICKS_SERVER_HOST")
        or os.getenv("DATABRICKS_HOST")
        or ""
    )
    host = host.replace("https://", "").replace("http://", "").rstrip("/")
    http_path = os.getenv("DATABRICKS_HTTP_PATH", f"/sql/1.0/warehouses/{wh}")

    # On Databricks Apps always use OAuth (injected client credentials), never PAT.
    if _on_databricks_app() or not os.getenv("DATABRICKS_TOKEN"):
        from databricks.sdk.core import Config

        cfg = Config()
        if not host and cfg.host:
            host = cfg.host.replace("https://", "").replace("http://", "").rstrip("/")
        if not host:
            raise RuntimeError("DATABRICKS_HOST is not set and SDK host is unavailable")
        return sql.connect(
            server_hostname=host,
            http_path=http_path,
            credentials_provider=cfg.authenticate,
        )

    return sql.connect(
        server_hostname=host,
        http_path=http_path,
        access_token=os.getenv("DATABRICKS_TOKEN", ""),
    )


def _query_sdk(sql: str) -> list[dict[str, Any]]:
    """Statement Execution API — reliable auth inside Databricks Apps."""
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.sql import StatementState

    wh = _warehouse_id()
    if not wh:
        raise RuntimeError("DATABRICKS_WAREHOUSE_ID is not set")

    w = WorkspaceClient()
    resp = w.statement_execution.execute_statement(
        warehouse_id=wh,
        statement=sql,
        wait_timeout="50s",
    )
    sid = resp.statement_id
    while resp.status and resp.status.state in (
        StatementState.PENDING,
        StatementState.RUNNING,
    ):
        time.sleep(0.3)
        resp = w.statement_execution.get_statement(sid)

    st = resp.status
    if not st or st.state != StatementState.SUCCEEDED:
        err = st.error.message if st and st.error else "unknown"
        state = st.state.value if st and st.state else "?"
        raise RuntimeError(f"SQL statement failed ({state}): {err}")

    cols = [c.name for c in (resp.manifest.schema.columns or [])]
    data = list(resp.result.data_array or []) if resp.result else []
    if not data and resp.manifest and resp.manifest.total_chunk_count:
        for i in range(resp.manifest.total_chunk_count):
            chunk = w.statement_execution.get_statement_result_chunk_n(sid, i)
            data.extend(chunk.data_array or [])
    return [dict(zip(cols, row)) for row in data]


def _query(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    ttl = settings()["cache_ttl"]
    key = sql + str(params)
    now = time.time()
    if key in _cache and now - _cache[key][0] < ttl:
        return _cache[key][1]

    if params:
        # databricks-sql-connector param binding is flaky on Apps; inline safe literals.
        for p in params:
            lit = "'" + str(p).replace("'", "''") + "'"
            sql = sql.replace("?", lit, 1)

    try:
        # Statement Execution API works on Databricks Apps (OAuth) and locally (PAT).
        rows = _query_sdk(sql)
    except Exception as sdk_exc:
        if os.getenv("USE_SQL_CONNECTOR") == "1":
            conn = _conn()
            with conn.cursor() as cur:
                cur.execute(sql)
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            conn.close()
        else:
            s = settings()
            raise RuntimeError(
                f"Gold SQL failed (catalog={s['gold_catalog']}, "
                f"warehouse={s['warehouse_id'] or 'unset'}, mode=statement_execution): {sdk_exc}"
            ) from sdk_exc
    _cache[key] = (now, rows)
    return rows


def _gold_table(name: str) -> str:
    s = settings()
    return f"`{s['gold_catalog']}`.`{s['gold_schema']}`.`{name}`"


def _source_table() -> str:
    s = settings()
    return f"`{s['source_catalog']}`.`{s['source_schema']}`.`{s['source_table']}`"


def get_capabilities() -> list[dict[str, Any]]:
    """Coverage = share of India facilities with ≥1 matched claim."""
    from pipeline.scoring_core import assess_tier

    rows = _query(f"SELECT * FROM {_source_table()} LIMIT 12000")
    total = len(rows) or 1
    out = []
    for cap in CAPABILITIES:
        cap_id = cap["id"]
        matched = sum(1 for r in rows if assess_tier(r, cap_id)[0] != "none")
        out.append({**cap, "coverage": round(matched / total, 2)})
    return out


def get_units(cap: str, grain: str) -> list[dict[str, Any]]:
    rows = _query(
        f"SELECT * FROM {_gold_table('gold_geo_capability')} "
        f"WHERE capability = ? AND grain = ?",
        (cap, grain),
    )
    return rows


def get_citations(cap: str, unit_key: str) -> list[dict[str, Any]]:
    return _query(
        f"SELECT * FROM {_gold_table('gold_evidence_citations')} "
        f"WHERE capability = ? AND unit_key = ?",
        (cap, unit_key),
    )


def get_unit_detail(cap: str, unit_key: str) -> dict[str, Any] | None:
    rows = _query(
        f"SELECT * FROM {_gold_table('gold_geo_capability')} "
        f"WHERE capability = ? AND unit_key = ? LIMIT 1",
        (cap, unit_key),
    )
    if not rows:
        return None
    row = rows[0]
    citations = get_citations(cap, unit_key)
    drivers = row.get("need_drivers")
    if isinstance(drivers, str):
        try:
            drivers = json.loads(drivers)
        except json.JSONDecodeError:
            drivers = []
    row["need_drivers_parsed"] = drivers or []
    row["citations"] = citations
    return row


def apply_overlay(
    units: list[dict],
    overrides: dict[str, str],
    watch: set[str],
    notes: dict[str, str],
) -> list[dict[str, Any]]:
    out = []
    for u in units:
        base = u.get("verdict", "unknown")
        verdict = overrides.get(u["unit_key"], base)
        risk = int(u.get("risk", 0))
        priority = risk * PRIORITY_WEIGHTS.get(verdict, 1.0)
        out.append({
            "unit_key": u["unit_key"],
            "name": u.get("unit_name", u.get("name", "")),
            "sub": u.get("sub", ""),
            "risk": risk,
            "conf": int(u.get("confidence", u.get("conf", 0))),
            "verdict": verdict,
            "base_verdict": base,
            "overridden": u["unit_key"] in overrides,
            "watched": u["unit_key"] in watch,
            "hasNote": bool(notes.get(u["unit_key"], "").strip()),
            "n_facilities": int(u.get("n_facilities", 0)),
            "priority": priority,
            "strong_count": int(u.get("strong_count", 0)),
            "partial_count": int(u.get("partial_count", 0)),
            "weak_count": int(u.get("weak_count", 0)),
            "need_index": u.get("need_index"),
            "need_signal_strength": u.get("need_signal_strength"),
            "nfhs_matched": bool(u.get("nfhs_matched")),
            "state": u["unit_key"].split("|")[-1] if "|" in u["unit_key"] else u.get("unit_name", ""),
        })
    return out




def query_pin_gaps(
    pin: str,
    cap: str | None = None,
    limit: int = 25,
) -> tuple[list[dict[str, Any]], str]:
    """Care-gap rows for a 6-digit PIN (matched via pin3 zone grain)."""
    digits = re.sub(r"\D", "", str(pin))
    pin3 = (digits[:3] if digits else "000").zfill(3)
    safe_pin3 = pin3.replace("'", "")
    lim = max(1, min(int(limit), 50))
    sql = (
        f"SELECT capability, unit_name, unit_key, risk, confidence, verdict, n_facilities "
        f"FROM {_gold_table('gold_geo_capability')} "
        f"WHERE grain = 'pin' AND unit_key LIKE 'pin:{safe_pin3}xxx%' "
    )
    if cap:
        safe_cap = str(cap).replace("'", "")
        sql += f"AND capability = '{safe_cap}' "
    sql += f"ORDER BY risk DESC LIMIT {lim}"
    return _query(sql), sql


def query_state_gaps(
    cap: str,
    state_substr: str,
    limit: int = 5,
    worst: bool = True,
) -> tuple[list[dict[str, Any]], str]:
    """Top/bottom state units for a capability matching a state name substring."""
    order = "DESC" if worst else "ASC"
    safe_cap = str(cap).replace("'", "")
    safe_pat = str(state_substr).replace("'", "''")
    lim = max(1, min(int(limit), 25))
    sql = (
        f"SELECT unit_name, unit_key, risk, confidence, verdict, n_facilities "
        f"FROM {_gold_table('gold_geo_capability')} "
        f"WHERE capability = '{safe_cap}' AND grain = 'state' "
        f"AND LOWER(unit_name) LIKE LOWER('%{safe_pat}%') "
        f"ORDER BY risk {order} LIMIT {lim}"
    )
    return _query(sql), sql


def summarize(units: list[dict]) -> dict[str, int]:
    counts = {"desert": 0, "blind": 0, "served": 0, "unknown": 0}
    for u in units:
        v = u.get("verdict", "unknown")
        if v in counts:
            counts[v] += 1
    return counts
