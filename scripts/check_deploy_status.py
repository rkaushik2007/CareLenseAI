#!/usr/bin/env python3
"""Quick status check for CareLenseAI Databricks resources."""
import os
import sys

import requests

host = os.environ["DATABRICKS_HOST"].rstrip("/")
h = {
    "Authorization": f"Bearer {os.environ['DATABRICKS_TOKEN']}",
    "Content-Type": "application/json",
}

r = requests.get(f"{host}/api/2.0/pipelines?max_results=100", headers=h, timeout=60)
print("Pipelines:", r.status_code)
if r.ok:
    for p in r.json().get("statuses", []):
        print(f"  {p.get('name')} id={p.get('pipeline_id')} state={p.get('state')}")

r = requests.get(f"{host}/api/2.1/jobs/list?limit=100", headers=h, timeout=60)
print("Jobs:", r.status_code)
if r.ok:
    for j in r.json().get("jobs", []):
        print(f"  {j.get('settings', {}).get('name')} id={j.get('job_id')}")

r = requests.get(f"{host}/api/2.0/apps/carelenseai", headers=h, timeout=60)
print("App:", r.status_code)
if r.ok:
    d = r.json()
    print(f"  state={d.get('app_status', {}).get('state')} url={d.get('url')}")

from databricks import sql

wh = os.environ.get("DATABRICKS_WAREHOUSE_ID", "c0c32c95246fd6a9")
GOLD_CATALOG = os.environ.get("GOLD_CATALOG", "main")
conn = sql.connect(
    server_hostname=host.replace("https://", ""),
    http_path=f"/sql/1.0/warehouses/{wh}",
    access_token=os.environ["DATABRICKS_TOKEN"],
)
with conn.cursor() as cur:
    for schema in (f"{GOLD_CATALOG}.carelense_gold", f"{GOLD_CATALOG}.carelense_silver"):
        try:
            cur.execute(f"SHOW TABLES IN {schema}")
            rows = cur.fetchall()
            print(f"Tables in {schema}: {len(rows)}")
            for row in rows[:10]:
                print(f"  {row}")
        except Exception as e:
            print(f"Schema {schema}: {e}")
conn.close()
