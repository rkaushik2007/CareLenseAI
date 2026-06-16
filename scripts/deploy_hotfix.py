#!/usr/bin/env python3
"""Upload only changed backend files and redeploy (fast hotfix)."""

from __future__ import annotations

import base64
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent

HOTFIX_FILES = (
    "app/backend/genie.py",
    "app/backend/gold_reads.py",
    "app/backend/main.py",
)

_cfg = None


def _settings():
    global _cfg
    if _cfg is not None:
        return _cfg
    from scripts.deploy_config import load_deploy_config

    _cfg = load_deploy_config()
    _cfg.apply_to_env()
    return _cfg


def workspace_base() -> str:
    return _settings().workspace_base


def app_name() -> str:
    return _settings().app_name


def warehouse_id() -> str:
    return _settings().warehouse_id


def headers():
    cfg = _settings()
    host = cfg.databricks_host.rstrip("/")
    return host, {"Authorization": f"Bearer {cfg.databricks_token}"}


def upload_file(host, hdrs, local: Path, remote: str) -> bool:
    body = {
        "path": remote,
        "format": "AUTO",
        "language": "PYTHON",
        "content": base64.b64encode(local.read_bytes()).decode(),
        "overwrite": True,
    }
    r = requests.post(
        f"{host}/api/2.0/workspace/import",
        headers=hdrs,
        json=body,
        timeout=60,
    )
    print(f"  {remote}: {r.status_code}")
    return r.status_code == 200


def deploy_app(host, hdrs) -> bool:
    r = requests.post(
        f"{host}/api/2.0/apps/{app_name()}/deployments",
        headers=hdrs,
        json={"source_code_path": workspace_base(), "mode": "SNAPSHOT"},
        timeout=60,
    )
    print(f"Deploy: {r.status_code} {r.text[:200]}")
    if r.status_code not in (200, 201):
        return False
    for _ in range(30):
        time.sleep(8)
        g = requests.get(f"{host}/api/2.0/apps/{app_name()}", headers=hdrs, timeout=30)
        data = g.json()
        state = data.get("app_status", {}).get("state", "")
        print(f"  state: {state}")
        if state == "RUNNING":
            print(f"Live: {data.get('url')}")
            return True
        if state in ("FAILED", "ERROR"):
            return False
    return False


def main(cfg=None) -> int:
    global _cfg
    if cfg is not None:
        _cfg = cfg
        cfg.apply_to_env()
    else:
        try:
            _settings()
        except ValueError as exc:
            print(exc)
            return 1

    host, hdrs = headers()
    base = workspace_base()
    print(f"Hotfix upload ({len(HOTFIX_FILES)} files)...")
    for rel in HOTFIX_FILES:
        local = ROOT / rel
        remote = f"{base}/{rel}".replace("\\", "/")
        if not upload_file(host, hdrs, local, remote):
            return 1

    requests.post(
        f"{host}/api/2.0/apps/{app_name()}/create-update",
        headers=hdrs,
        json={
            "update_mask": "resources",
            "resources": [
                {
                    "name": "sql-warehouse",
                    "sql_warehouse": {"id": warehouse_id(), "permission": "CAN_USE"},
                }
            ],
        },
        timeout=30,
    )

    return 0 if deploy_app(host, hdrs) else 1


if __name__ == "__main__":
    sys.exit(main())
