#!/usr/bin/env python3
"""Probe Genie, Lakebase, and app update APIs on premium workspace."""
import os
import json
import requests

host = os.environ["DATABRICKS_HOST"].rstrip("/")
h = {"Authorization": f"Bearer {os.environ['DATABRICKS_TOKEN']}", "Content-Type": "application/json"}

probes = [
    ("GET", "/api/2.0/genie/spaces"),
    ("GET", "/api/2.0/lakeview/genie/spaces"),
    ("GET", "/api/2.0/database/instances"),
    ("GET", "/api/2.0/database/catalogs"),
    ("GET", "/api/2.0/serving-endpoints"),
    ("GET", "/api/2.0/apps/carelenseai"),
]

for method, path in probes:
    r = requests.request(method, host + path, headers=h, timeout=60)
    print(f"\n{method} {path} -> {r.status_code}")
    if r.ok:
        text = json.dumps(r.json(), indent=2)
        print(text[:1200])
    else:
        print(r.text[:300])
