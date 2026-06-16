"""Lakebase Postgres persistence for planner actions."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Any

from app.backend.config import settings


def _planner_id(request_headers: dict | None = None) -> str:
    if request_headers:
        for key in ("X-Forwarded-Email", "X-Forwarded-Preferred-Username", "X-Forwarded-User"):
            if request_headers.get(key):
                return str(request_headers[key])
    return os.getenv("PLANNER_ID", "demo-planner")


@contextmanager
def get_conn():
    import psycopg2

    conn = psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        dbname=os.getenv("PGDATABASE", "postgres"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", ""),
        port=os.getenv("PGPORT", "5432"),
        sslmode=os.getenv("PGSSLMODE", "require"),
    )
    try:
        _ensure_schema(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_schema(conn) -> None:
    schema_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "lakebase",
        "schema.sql",
    )
    if not os.path.exists(schema_path):
        return
    with open(schema_path, encoding="utf-8") as f:
        sql = f.read()
    with conn.cursor() as cur:
        cur.execute(sql)




def _sqlite_db_path():
    from pathlib import Path
    import tempfile

    override = os.getenv("PLANNER_SQLITE_PATH")
    if override:
        return Path(override)
    if os.getenv("DATABRICKS_SERVER_HOST") or os.getenv("DATABRICKS_APP_NAME"):
        return Path(tempfile.gettempdir()) / "carelense_planner_state.db"
    return Path(__file__).parent.parent.parent / "data" / "planner_state.db"


def _sqlite_fallback():
    import sqlite3
    from pathlib import Path

    db = _sqlite_db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS planner_watch (
            planner_id TEXT, unit_key TEXT, capability TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (planner_id, unit_key, capability));
        CREATE TABLE IF NOT EXISTS planner_notes (
            planner_id TEXT, unit_key TEXT, capability TEXT, note TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (planner_id, unit_key, capability));
        CREATE TABLE IF NOT EXISTS planner_overrides (
            planner_id TEXT, unit_key TEXT, capability TEXT, verdict TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (planner_id, unit_key, capability));
        CREATE TABLE IF NOT EXISTS planner_scenarios (
            planner_id TEXT, name TEXT, cap TEXT, grain TEXT,
            overlay INTEGER, sort TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (planner_id, name));
    """)
    return conn


def _use_lakebase() -> bool:
    return bool(
        os.getenv("PGHOST")
        or os.getenv("DATABRICKS_DATABASE_HOST")
        or os.getenv("DATABASE_HOST")
    )


def planner_backend() -> str:
    return "lakebase" if _use_lakebase() else "sqlite"


class PlannerStore:
    def __init__(self, planner_id: str):
        self.planner_id = planner_id

    def get_overrides(self, cap: str) -> dict[str, str]:
        if _use_lakebase():
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT unit_key, verdict FROM planner_overrides "
                        "WHERE planner_id = %s AND capability = %s",
                        (self.planner_id, cap),
                    )
                    return {r[0]: r[1] for r in cur.fetchall()}
        conn = _sqlite_fallback()
        rows = conn.execute(
            "SELECT unit_key, verdict FROM planner_overrides WHERE planner_id=? AND capability=?",
            (self.planner_id, cap),
        ).fetchall()
        conn.close()
        return {r["unit_key"]: r["verdict"] for r in rows}

    def get_watch_set(self, cap: str) -> set[str]:
        if _use_lakebase():
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT unit_key FROM planner_watch WHERE planner_id=%s AND capability=%s",
                        (self.planner_id, cap),
                    )
                    return {r[0] for r in cur.fetchall()}
        conn = _sqlite_fallback()
        rows = conn.execute(
            "SELECT unit_key FROM planner_watch WHERE planner_id=? AND capability=?",
            (self.planner_id, cap),
        ).fetchall()
        conn.close()
        return {r["unit_key"] for r in rows}

    def get_notes(self, cap: str) -> dict[str, str]:
        if _use_lakebase():
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT unit_key, note FROM planner_notes WHERE planner_id=%s AND capability=%s",
                        (self.planner_id, cap),
                    )
                    return {r[0]: r[1] or "" for r in cur.fetchall()}
        conn = _sqlite_fallback()
        rows = conn.execute(
            "SELECT unit_key, note FROM planner_notes WHERE planner_id=? AND capability=?",
            (self.planner_id, cap),
        ).fetchall()
        conn.close()
        return {r["unit_key"]: r["note"] or "" for r in rows}

    def set_watch(self, cap: str, unit_key: str, on: bool) -> None:
        if _use_lakebase():
            with get_conn() as conn:
                with conn.cursor() as cur:
                    if on:
                        cur.execute(
                            "INSERT INTO planner_watch (planner_id, unit_key, capability) "
                            "VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                            (self.planner_id, unit_key, cap),
                        )
                    else:
                        cur.execute(
                            "DELETE FROM planner_watch WHERE planner_id=%s AND unit_key=%s AND capability=%s",
                            (self.planner_id, unit_key, cap),
                        )
            return
        conn = _sqlite_fallback()
        if on:
            conn.execute(
                "INSERT OR IGNORE INTO planner_watch (planner_id, unit_key, capability) VALUES (?,?,?)",
                (self.planner_id, unit_key, cap),
            )
        else:
            conn.execute(
                "DELETE FROM planner_watch WHERE planner_id=? AND unit_key=? AND capability=?",
                (self.planner_id, unit_key, cap),
            )
        conn.commit()
        conn.close()

    def set_note(self, cap: str, unit_key: str, note: str) -> None:
        if _use_lakebase():
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO planner_notes (planner_id, unit_key, capability, note) "
                        "VALUES (%s,%s,%s,%s) ON CONFLICT (planner_id, unit_key, capability) "
                        "DO UPDATE SET note=EXCLUDED.note, updated_at=NOW()",
                        (self.planner_id, unit_key, cap, note),
                    )
            return
        conn = _sqlite_fallback()
        conn.execute(
            "INSERT OR REPLACE INTO planner_notes (planner_id, unit_key, capability, note) VALUES (?,?,?,?)",
            (self.planner_id, unit_key, cap, note),
        )
        conn.commit()
        conn.close()

    def set_override(self, cap: str, unit_key: str, verdict: str | None) -> None:
        if _use_lakebase():
            with get_conn() as conn:
                with conn.cursor() as cur:
                    if verdict is None:
                        cur.execute(
                            "DELETE FROM planner_overrides WHERE planner_id=%s AND unit_key=%s AND capability=%s",
                            (self.planner_id, unit_key, cap),
                        )
                    else:
                        cur.execute(
                            "INSERT INTO planner_overrides (planner_id, unit_key, capability, verdict) "
                            "VALUES (%s,%s,%s,%s) ON CONFLICT (planner_id, unit_key, capability) "
                            "DO UPDATE SET verdict=EXCLUDED.verdict, updated_at=NOW()",
                            (self.planner_id, unit_key, cap, verdict),
                        )
            return
        conn = _sqlite_fallback()
        if verdict is None:
            conn.execute(
                "DELETE FROM planner_overrides WHERE planner_id=? AND unit_key=? AND capability=?",
                (self.planner_id, unit_key, cap),
            )
        else:
            conn.execute(
                "INSERT OR REPLACE INTO planner_overrides (planner_id, unit_key, capability, verdict) VALUES (?,?,?,?)",
                (self.planner_id, unit_key, cap, verdict),
            )
        conn.commit()
        conn.close()

    def list_scenarios(self) -> list[dict[str, Any]]:
        if _use_lakebase():
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT name, cap, grain, overlay, sort, created_at FROM planner_scenarios "
                        "WHERE planner_id=%s ORDER BY created_at DESC",
                        (self.planner_id,),
                    )
                    return [
                        {"name": r[0], "cap": r[1], "grain": r[2], "overlay": r[3], "sort": r[4]}
                        for r in cur.fetchall()
                    ]
        conn = _sqlite_fallback()
        rows = conn.execute(
            "SELECT name, cap, grain, overlay, sort FROM planner_scenarios WHERE planner_id=?",
            (self.planner_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def save_scenario(self, data: dict[str, Any]) -> None:
        if _use_lakebase():
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO planner_scenarios (planner_id, name, cap, grain, overlay, sort) "
                        "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (planner_id, name) "
                        "DO UPDATE SET cap=EXCLUDED.cap, grain=EXCLUDED.grain, "
                        "overlay=EXCLUDED.overlay, sort=EXCLUDED.sort",
                        (
                            self.planner_id, data["name"], data["cap"], data["grain"],
                            data["overlay"], data["sort"],
                        ),
                    )
            return
        conn = _sqlite_fallback()
        conn.execute(
            "INSERT OR REPLACE INTO planner_scenarios (planner_id, name, cap, grain, overlay, sort) VALUES (?,?,?,?,?,?)",
            (self.planner_id, data["name"], data["cap"], data["grain"], int(data["overlay"]), data["sort"]),
        )
        conn.commit()
        conn.close()

    def delete_scenario(self, name: str) -> None:
        if _use_lakebase():
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM planner_scenarios WHERE planner_id=%s AND name=%s",
                        (self.planner_id, name),
                    )
            return
        conn = _sqlite_fallback()
        conn.execute("DELETE FROM planner_scenarios WHERE planner_id=? AND name=?", (self.planner_id, name))
        conn.commit()
        conn.close()
