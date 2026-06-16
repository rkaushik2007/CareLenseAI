#!/usr/bin/env python3
import os
import requests

host = os.environ["DATABRICKS_HOST"].rstrip("/")
h = {"Authorization": f"Bearer {os.environ['DATABRICKS_TOKEN']}", "Content-Type": "application/json"}
pid = "36457d6a-007c-45fa-a2bd-8a3b261ece34"
uid = "4c0f3470-f8d2-4142-b908-b354b5fd411f"

r = requests.get(f"{host}/api/2.0/pipelines/{pid}/updates/{uid}", headers=h, timeout=60)
print("Update detail:", r.status_code)
if r.ok:
    import json
    print(json.dumps(r.json(), indent=2)[:8000])

r = requests.get(f"{host}/api/2.1/jobs/runs/get?run_id=659432463782771", headers=h, timeout=60)
print("\nJob run detail:", r.status_code)
if r.ok:
    import json
    d = r.json()
    print("state:", d.get("state"))
    for t in d.get("tasks", []):
        print("task:", t.get("task_key"), t.get("state"))
        print("  msg:", (t.get("state", {}).get("state_message") or "")[:2000])
