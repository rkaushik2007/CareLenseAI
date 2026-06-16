#!/usr/bin/env python3
"""Upload project to Databricks workspace and deploy the carelenseai app."""

from __future__ import annotations

import base64
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", ".next", "__pycache__", ".idea", "data", "src"}
SKIP_FILES = {".env", ".env.example", "cursor_prompt_medical_desert_planner_2.md", "deploy.config.yaml"}

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


def mkdirs(host, hdrs, path: str):
    requests.post(f"{host}/api/2.0/workspace/mkdirs", headers=hdrs, json={"path": path})


def upload_file(host, hdrs, local: Path, remote: str):
    content = local.read_bytes()
    b64 = base64.b64encode(content).decode()
    fmt = "AUTO"
    language = None
    if local.suffix == ".py":
        language = "PYTHON"
    elif local.suffix in (".yaml", ".yml", ".txt", ".sql", ".md", ".json", ".html", ".css", ".js"):
        fmt = "RAW"
    elif local.suffix in (".png", ".jpg", ".svg", ".ico", ".woff", ".woff2"):
        fmt = "RAW"

    body = {"path": remote, "format": fmt, "content": b64, "overwrite": True}
    if language:
        body["language"] = language

    r = requests.post(f"{host}/api/2.0/workspace/import", headers=hdrs, json=body, timeout=120)
    if r.status_code != 200:
        print(f"  FAIL {remote}: {r.status_code} {r.text[:200]}")
        return False
    return True


def collect_files() -> list[tuple[Path, str]]:
    base = workspace_base()
    files: list[tuple[Path, str]] = []

    def add(local: Path, remote_rel: str):
        files.append((local, f"{base}/{remote_rel}".replace("\\", "/")))

    for name in ("app.yaml", "requirements.txt", "databricks.yml"):
        p = ROOT / name
        if p.exists():
            add(p, name)

    for p in (ROOT / "app").rglob("*"):
        if p.is_file() and "node_modules" not in p.parts and ".next" not in p.parts:
            if p.suffix in (".ts", ".tsx") and "frontend/src" in str(p):
                continue
            rel = p.relative_to(ROOT).as_posix()
            add(p, rel)

    for p in (ROOT / "pipeline").rglob("*"):
        if p.is_file() and p.suffix == ".py":
            add(p, p.relative_to(ROOT).as_posix())

    schema = ROOT / "lakebase" / "schema.sql"
    if schema.exists():
        add(schema, "lakebase/schema.sql")

    return files


def upload_all():
    base = workspace_base()
    host, hdrs = headers()
    mkdirs(host, hdrs, base)
    mkdirs(host, hdrs, f"{base}/app/backend")
    mkdirs(host, hdrs, f"{base}/app/frontend/out")
    mkdirs(host, hdrs, f"{base}/pipeline")

    files = collect_files()
    print(f"Uploading {len(files)} files...")
    ok = 0
    for local, remote in files:
        remote_dir = "/".join(remote.split("/")[:-1])
        mkdirs(host, hdrs, remote_dir)
        if upload_file(host, hdrs, local, remote):
            ok += 1
        if ok % 50 == 0 and ok > 0:
            print(f"  ... {ok}/{len(files)}")
    print(f"Uploaded {ok}/{len(files)} files")
    return ok == len(files)


def attach_sql_warehouse():
    host, hdrs = headers()
    body = {
        "update_mask": "resources",
        "resources": [
            {
                "name": "sql-warehouse",
                "sql_warehouse": {"id": warehouse_id(), "permission": "CAN_USE"},
            }
        ],
    }
    r = requests.post(
        f"{host}/api/2.0/apps/{app_name()}/create-update",
        headers=hdrs,
        json=body,
        timeout=60,
    )
    print(f"Attach warehouse: {r.status_code} {r.text[:300]}")
    return r.status_code in (200, 201)


def deploy_app():
    host, hdrs = headers()
    body = {
        "source_code_path": workspace_base(),
        "mode": "SNAPSHOT",
    }
    r = requests.post(
        f"{host}/api/2.0/apps/{app_name()}/deployments",
        headers=hdrs,
        json=body,
        timeout=60,
    )
    print(f"Deploy started: {r.status_code} {r.text[:400]}")
    if r.status_code not in (200, 201):
        return False

    for _ in range(60):
        time.sleep(10)
        g = requests.get(f"{host}/api/2.0/apps/{app_name()}", headers=hdrs)
        data = g.json()
        status = data.get("app_status", {})
        state = status.get("state", "")
        msg = status.get("message", "")
        print(f"  App state: {state} — {msg[:120]}")
        if state == "RUNNING":
            print(f"\nLive URL: {data.get('url')}")
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

    if not upload_all():
        print("Upload had failures — continuing anyway")

    attach_sql_warehouse()
    time.sleep(5)

    if not deploy_app():
        print("Deploy may still be in progress — check Databricks UI")
        return 1

    print("Deployment complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
