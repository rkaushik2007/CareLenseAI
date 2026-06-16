#!/usr/bin/env python3
"""Upload only files required to run the app and DLT pipeline."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.deploy_infrastructure import APP_NAME, WAREHOUSE_ID, WORKSPACE_BASE, api, deploy_app, mkdirs, upload_file

ESSENTIAL = [
    "app.yaml",
    "requirements.txt",
    "app/backend/main.py",
    "app/backend/config.py",
    "app/backend/gold_reads.py",
    "app/backend/lakebase.py",
    "app/backend/genie.py",
    "app/backend/agent.py",
    "app/backend/models.py",
    "app/backend/__init__.py",
    "app/__init__.py",
    "pipeline/bronze.py",
    "pipeline/silver.py",
    "pipeline/config.py",
    "pipeline/lexicons.py",
    "pipeline/scoring_core.py",
    "pipeline/source_urls.py",
    "pipeline/geo_crosswalk.py",
    "pipeline/__init__.py",
]


def upload_essential() -> int:
    ok = 0
    for rel in ESSENTIAL:
        local = ROOT / rel
        if not local.exists():
            print(f"  skip missing {rel}")
            continue
        remote = f"{WORKSPACE_BASE}/{rel.replace(chr(92), '/')}"
        mkdirs("/".join(remote.split("/")[:-1]))
        if upload_file(local, remote):
            ok += 1
            print(f"  ok {rel}")
        else:
            print(f"  FAIL {rel}")
    # frontend build output
    out = ROOT / "app" / "frontend" / "out"
    if out.is_dir():
        for p in out.rglob("*"):
            if p.is_file():
                rel = p.relative_to(ROOT).as_posix()
                remote = f"{WORKSPACE_BASE}/{rel}"
                mkdirs("/".join(remote.split("/")[:-1]))
                if upload_file(p, remote):
                    ok += 1
    return ok


def create_app_if_needed():
    r = api("GET", f"/api/2.0/apps/{APP_NAME}")
    body = {
        "name": APP_NAME,
        "description": "CareLenseAI Medical Desert Planner",
        "resources": [{
            "name": "sql-warehouse",
            "sql_warehouse": {"id": WAREHOUSE_ID, "permission": "CAN_USE"},
        }],
    }
    if r.status_code == 404:
        r = api("POST", "/api/2.0/apps", body)
        print("create app", r.status_code, r.text[:200])
    else:
        r = api("PUT", f"/api/2.0/apps/{APP_NAME}", {"resources": body["resources"]})
        print("update app", r.status_code)


def main():
    print("Uploading essential files...")
    n = upload_essential()
    print(f"Uploaded {n} files")
    create_app_if_needed()
    print("Deploying app...")
    deploy_app()


if __name__ == "__main__":
    main()
