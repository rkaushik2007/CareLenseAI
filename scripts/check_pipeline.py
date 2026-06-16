#!/usr/bin/env python3
import os
import requests

host = os.environ["DATABRICKS_HOST"].rstrip("/")
h = {"Authorization": f"Bearer {os.environ['DATABRICKS_TOKEN']}", "Content-Type": "application/json"}
pid = "36457d6a-007c-45fa-a2bd-8a3b261ece34"

r = requests.get(f"{host}/api/2.0/pipelines/{pid}/updates", headers=h, timeout=60)
print("Updates:", r.status_code)
if r.ok:
    for u in r.json().get("updates", [])[:5]:
        print(u.get("update_id"), u.get("state"), u.get("creation_time"))

r = requests.get(f"{host}/api/2.0/pipelines/{pid}", headers=h, timeout=60)
print("Pipeline detail:", r.status_code)
if r.ok:
    d = r.json()
    print("state:", d.get("state"))
    print("latest:", d.get("latest_updates"))

job_id = 291956500668661
r = requests.get(f"{host}/api/2.1/jobs/runs/list?job_id={job_id}&limit=3", headers=h, timeout=60)
print("Job runs:", r.status_code)
if r.ok:
    for run in r.json().get("runs", []):
        st = run.get("state", {})
        print(run.get("run_id"), st.get("life_cycle_state"), st.get("result_state"))
