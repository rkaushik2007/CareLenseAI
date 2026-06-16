#!/usr/bin/env python3
"""Re-run pipeline + jobs after fixes (skip full upload)."""
from __future__ import annotations

import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.deploy_infrastructure import (  # noqa: E402
    api,
    create_job,
    create_or_update_pipeline,
    deploy_app,
    grant_permissions_sql,
    run_job,
    start_pipeline,
    upload_file,
    WORKSPACE_BASE,
)

PIPELINE_ID = "36457d6a-007c-45fa-a2bd-8a3b261ece34"


def main():
    from pathlib import Path

    print("Upload fixed silver.py...")
    upload_file(Path(ROOT) / "pipeline" / "silver.py", f"{WORKSPACE_BASE}/pipeline/silver.py")

    print("Update pipeline...")
    pid = create_or_update_pipeline() or PIPELINE_ID

    print("Start pipeline...")
    ok = start_pipeline(pid)
    print(f"Pipeline: {'OK' if ok else 'FAILED'}")

    gold_nb = f"{WORKSPACE_BASE}/notebooks/jobs/01_materialize_gold"
    gold_job = create_job("[CareLenseAI] Gold Materialization", gold_nb)
    if gold_job and ok:
        print("Run gold job...")
        run_job(gold_job)

    readiness_nb = f"{WORKSPACE_BASE}/notebooks/jobs/04_data_readiness"
    create_job("[CareLenseAI] Data Readiness Report", readiness_nb)

    print("Grants...")
    grant_permissions_sql()

    print("Redeploy app...")
    deploy_app()
    print("Done.")


if __name__ == "__main__":
    main()
