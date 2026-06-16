#!/usr/bin/env python3
"""Run all CareLenseAI deployment steps via REST API + SQL (no CLI profile)."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Required env
os.environ.setdefault("DATABRICKS_HOST", "https://adb-3141834805281315.15.azuredatabricks.net")
os.environ.setdefault("DATABRICKS_WAREHOUSE_ID", "c0c32c95246fd6a9")
os.environ.setdefault("GOLD_CATALOG", "main")

import requests

HOST = os.environ["DATABRICKS_HOST"].rstrip("/")
TOKEN = os.environ.get("DATABRICKS_TOKEN", "")
HDRS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def sql_query(query: str):
    from databricks import sql

    conn = sql.connect(
        server_hostname=HOST.replace("https://", "").replace("http://", ""),
        http_path=f"/sql/1.0/warehouses/{os.environ['DATABRICKS_WAREHOUSE_ID']}",
        access_token=TOKEN,
    )
    with conn.cursor() as cur:
        cur.execute(query)
        if cur.description:
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            conn.close()
            return cols, rows
    conn.close()
    return [], []


def step1_materialize():
    print("\n=== STEP 1: Materialize Gold ===")
    from scripts.materialize_gold import main as mat_main
    mat_main()
    cols, rows = sql_query(
        f"SELECT COUNT(*) AS n FROM {os.environ['GOLD_CATALOG']}.carelense_gold.gold_geo_capability"
    )
    n = rows[0][0] if rows else 0
    print(f"  Verified gold_geo_capability rows: {n}")
    cols2, rows2 = sql_query(
        f"SELECT COUNT(*) AS n FROM {os.environ['GOLD_CATALOG']}.carelense_gold.gold_evidence_citations"
    )
    c = rows2[0][0] if rows2 else 0
    print(f"  Verified gold_evidence_citations rows: {c}")
    cols3, rows3 = sql_query(f"""
        SELECT capability, verdict, COUNT(*) AS n
        FROM {os.environ['GOLD_CATALOG']}.carelense_gold.gold_geo_capability
        WHERE grain = 'state'
        GROUP BY capability, verdict ORDER BY 1, 2 LIMIT 20
    """)
    for r in rows3:
        print(f"    {r}")
    return n, c


def step2_upload():
    print("\n=== STEP 2: Upload code ===")
    from scripts.deploy_infrastructure import upload_tree
    return upload_tree()


def step3_grants():
    print("\n=== STEP 3: Grant permissions ===")
    from scripts.deploy_infrastructure import grant_permissions_sql
    grant_permissions_sql()


def step4_deploy():
    print("\n=== STEP 4: Deploy app ===")
    from scripts.deploy_infrastructure import deploy_app
    return deploy_app()


def step5_verify():
    print("\n=== STEP 5: Verify app ===")
    r = requests.get(f"{HOST}/api/2.0/apps/carelenseai", headers=HDRS, timeout=30)
    if r.status_code != 200:
        print(f"  App get failed: {r.status_code}")
        return None, False
    data = r.json()
    url = data.get("url", "")
    state = data.get("app_status", {}).get("state", "")
    print(f"  App state: {state}")
    print(f"  App URL: {url}")
    health_ok = False
    if url:
        try:
            hr = requests.get(f"{url}/healthz", timeout=30)
            print(f"  /healthz: {hr.status_code} {hr.text[:100]}")
            health_ok = hr.status_code == 200
        except Exception as e:
            print(f"  /healthz error: {e}")
    return url, health_ok


def main():
    if not TOKEN:
        print("ERROR: Set DATABRICKS_TOKEN")
        sys.exit(1)

    # Auth check
    r = requests.get(f"{HOST}/api/2.0/sql/warehouses", headers=HDRS, timeout=30)
    print(f"Auth check: {r.status_code}")
    if r.status_code != 200:
        print(r.text[:300])
        sys.exit(1)

    gold_n, cite_n = step1_materialize()
    uploaded = step2_upload()
    step3_grants()
    deployed = step4_deploy()
    url, health = step5_verify()

    print("\n========== DEPLOYMENT COMPLETE ==========")
    print(f"  Gold rows: {gold_n}")
    print(f"  Citation rows: {cite_n}")
    print(f"  Files uploaded: {uploaded}")
    print(f"  App deployed: {deployed}")
    print(f"  App URL: {url}")
    print(f"  Health OK: {health}")


if __name__ == "__main__":
    main()
