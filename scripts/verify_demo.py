#!/usr/bin/env python3
"""Verify CareLenseAI demo readiness for a workspace."""
from __future__ import annotations

import json
import os
import sys

import requests


def verify(label: str) -> dict:
    host = os.environ["DATABRICKS_HOST"].rstrip("/")
    token = os.environ["DATABRICKS_TOKEN"]
    wh = os.environ.get("DATABRICKS_WAREHOUSE_ID", "")
    gold_catalog = os.environ.get("GOLD_CATALOG", "main")
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    result = {
        "label": label,
        "host": host,
        "warehouse_id": wh,
        "gold_catalog": gold_catalog,
        "api_ok": False,
        "sql_ok": False,
        "gold_geo_count": None,
        "gold_citations_count": None,
        "app_status": None,
        "app_url": None,
        "healthz": None,
        "summary": None,
        "errors": [],
    }

    # API connectivity
    try:
        r = requests.get(f"{host}/api/2.0/clusters/list", headers=hdrs, timeout=30)
        if r.status_code in (200, 403):
            result["api_ok"] = True
        else:
            result["errors"].append(f"API {r.status_code}: {r.text[:200]}")
    except Exception as exc:
        result["errors"].append(f"API connect: {exc}")

    # SQL / gold counts
    if result["api_ok"] and wh:
        try:
            from databricks import sql

            conn = sql.connect(
                server_hostname=host.replace("https://", "").replace("http://", ""),
                http_path=f"/sql/1.0/warehouses/{wh}",
                access_token=token,
            )
            with conn.cursor() as cur:
                for tbl, key in (
                    ("gold_geo_capability", "gold_geo_count"),
                    ("gold_evidence_citations", "gold_citations_count"),
                ):
                    try:
                        cur.execute(
                            f"SELECT COUNT(*) FROM {gold_catalog}.carelense_gold.{tbl}"
                        )
                        result[key] = cur.fetchone()[0]
                    except Exception as exc:
                        result[key] = f"ERROR: {exc}"
                        result["errors"].append(f"{tbl}: {exc}")
            conn.close()
            result["sql_ok"] = isinstance(result["gold_geo_count"], int)
        except Exception as exc:
            result["errors"].append(f"SQL connect: {exc}")

    # App status
    if result["api_ok"]:
        try:
            r = requests.get(f"{host}/api/2.0/apps/carelenseai", headers=hdrs, timeout=60)
            if r.ok:
                d = r.json()
                result["app_status"] = d.get("app_status", {}).get("state")
                result["app_url"] = d.get("url", "")
            else:
                result["errors"].append(f"App GET {r.status_code}: {r.text[:200]}")
        except Exception as exc:
            result["errors"].append(f"App: {exc}")

    # HTTP endpoints
    app_url = result.get("app_url") or ""
    if app_url:
        for path, key in (("/healthz", "healthz"), ("/api/summary?cap=icu&grain=state", "summary")):
            try:
                sr = requests.get(f"{app_url}{path}", timeout=90)
                result[key] = {"status": sr.status_code, "body": sr.text[:500]}
            except Exception as exc:
                result[key] = {"status": "ERROR", "body": str(exc)}

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: verify_demo.py <label>")
        sys.exit(1)
    r = verify(sys.argv[1])
    print(json.dumps(r, indent=2, default=str))


if __name__ == "__main__":
    main()
