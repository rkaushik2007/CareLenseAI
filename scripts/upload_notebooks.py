#!/usr/bin/env python3
"""Upload Databricks notebooks (delete + re-import as SOURCE)."""
import base64
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_BASE = "/Workspace/Users/rajaniesh@rajanieshkaushikk.com/apps/carelenseai"
host = os.environ["DATABRICKS_HOST"].rstrip("/")
hdrs = {"Authorization": f"Bearer {os.environ['DATABRICKS_TOKEN']}", "Content-Type": "application/json"}


def upload_notebook(local: Path, remote: str) -> bool:
    requests.post(f"{host}/api/2.0/workspace/delete", headers=hdrs, json={"path": remote, "recursive": False})
    content = base64.b64encode(local.read_text(encoding="utf-8").encode()).decode()
    body = {
        "path": remote,
        "format": "SOURCE",
        "language": "PYTHON",
        "content": content,
        "overwrite": True,
    }
    r = requests.post(f"{host}/api/2.0/workspace/import", headers=hdrs, json=body, timeout=120)
    ok = r.status_code == 200
    print(f"{'OK' if ok else 'FAIL'} {remote}: {r.status_code} {r.text[:120]}")
    return ok


def main():
    nb_dir = ROOT / "notebooks" / "jobs"
    for nb in sorted(nb_dir.glob("*.py")):
        remote = f"{WORKSPACE_BASE}/notebooks/jobs/{nb.stem}"
        upload_notebook(nb, remote)


if __name__ == "__main__":
    main()
