#!/usr/bin/env python3
"""
Full CareLenseAI deployment to premium workspace:
  upload all files, DLT pipeline, jobs, Genie space, app redeploy, grants.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.deploy_infrastructure import (  # noqa: E402
    APP_NAME,
    GOLD_CATALOG,
    WAREHOUSE_ID,
    WORKSPACE_BASE,
    api,
    create_job,
    create_or_update_pipeline,
    create_schemas_sql,
    deploy_app,
    grant_permissions_sql,
    resolve_app_sp,
    run_job,
    start_pipeline,
    upload_file,
    upload_job_notebooks,
    upload_tree,
)

GENIE_TITLE = "CareLenseAI Medical Desert Planner"
GENIE_INSTRUCTIONS = """You are the CareLenseAI Genie assistant for healthcare planners in India.

Tables:
- gold_geo_capability: one row per (grain, unit_key, capability). Columns include risk (6-97), confidence (8-96), verdict (desert|blind|served|unknown), strong_count, partial_count, weak_count, need_index, nfhs_matched.
- gold_evidence_citations: facility quotes supporting capability claims. tier is strong|partial|weak. rec_id is the facility unique_id.

Verdict rules (threshold 58):
- desert = risk>=58 AND confidence>=58 (confirmed care gap)
- blind = risk>=58 AND confidence<58 (high risk, thin data — investigate)
- served = risk<58 AND confidence>=58
- unknown = otherwise

Always cite unit_key and rec_id when answering. Never invent risk or confidence numbers."""


def _uid() -> str:
    return uuid.uuid4().hex[:32]


def build_genie_serialized_space() -> str:
    gold = f"{GOLD_CATALOG}.carelense_gold"
    space = {
        "version": 2,
        "config": {
            "sample_questions": [
                {"id": _uid(), "question": ["What are the worst ICU gaps in Bihar?"]},
                {"id": _uid(), "question": ["Show blind spots for maternity in Rajasthan"]},
                {"id": _uid(), "question": ["Which states have the most confirmed deserts for emergency care?"]},
            ]
        },
        "data_sources": {
            "tables": sorted(
                [
                    {"identifier": f"{gold}.gold_evidence_citations"},
                    {"identifier": f"{gold}.gold_geo_capability"},
                ],
                key=lambda t: t["identifier"],
            )
        },
        "instructions": {
            "text_instructions": [
                {"id": _uid(), "content": [GENIE_INSTRUCTIONS + "\n"]},
            ],
            "example_question_sqls": [
                {
                    "id": _uid(),
                    "question": ["What are the worst ICU gaps in Bihar?"],
                    "sql": [
                        "SELECT unit_name, risk, confidence, verdict, strong_count\n",
                        f"FROM {gold}.gold_geo_capability\n",
                        "WHERE capability = 'icu' AND grain = 'state' AND unit_name LIKE '%Bihar%'\n",
                        "ORDER BY risk DESC\n",
                    ],
                },
                {
                    "id": _uid(),
                    "question": ["Show blind spots for maternity in Rajasthan"],
                    "sql": [
                        "SELECT unit_name, risk, confidence, verdict\n",
                        f"FROM {gold}.gold_geo_capability\n",
                        "WHERE capability = 'maternity' AND grain = 'state' AND verdict = 'blind'\n",
                        "  AND unit_name LIKE '%Rajasthan%'\n",
                        "ORDER BY risk DESC\n",
                    ],
                },
            ],
        },
    }
    return json.dumps(space)


def update_genie_space(space_id: str) -> bool:
    """Refresh data sources and example SQL to current GOLD_CATALOG."""
    body = {
        "warehouse_id": WAREHOUSE_ID,
        "serialized_space": build_genie_serialized_space(),
    }
    r = api("PATCH", f"/api/2.0/genie/spaces/{space_id}", body)
    if r.status_code in (200, 204):
        print(f"  Genie space updated: {space_id}")
        return True
    print(f"  Genie PATCH failed: {r.status_code} {r.text[:400]}")
    return False


def find_or_create_genie_space() -> str | None:
    r = api("GET", "/api/2.0/genie/spaces")
    if r.status_code == 200:
        for s in r.json().get("spaces", []):
            if s.get("title") == GENIE_TITLE:
                sid = s["space_id"]
                print(f"  Genie space exists: {sid}")
                update_genie_space(sid)
                return sid

    body = {
        "title": GENIE_TITLE,
        "description": "Natural language Q&A over CareLenseAI Gold tables for India medical deserts.",
        "warehouse_id": WAREHOUSE_ID,
        "parent_path": "/Users/rajaniesh@rajanieshkaushikk.com",
        "serialized_space": build_genie_serialized_space(),
    }
    r = api("POST", "/api/2.0/genie/spaces", body)
    if r.status_code not in (200, 201):
        print(f"  Genie create failed: {r.status_code} {r.text[:400]}")
        return None
    sid = r.json().get("space_id")
    print(f"  Genie space created: {sid}")
    return sid


def patch_app_yaml_genie(space_id: str):
    """Write GENIE_SPACE_ID into app.yaml and upload."""
    app_yaml = ROOT / "app.yaml"
    text = app_yaml.read_text(encoding="utf-8")
    line = f'  - name: GENIE_SPACE_ID\n    value: "{space_id}"\n'
    if "GENIE_SPACE_ID" in text:
        import re
        text = re.sub(
            r"  - name: GENIE_SPACE_ID\n    value:.*\n",
            line,
            text,
        )
    else:
        text = text.rstrip() + "\n" + line
    app_yaml.write_text(text, encoding="utf-8")
    upload_file(app_yaml, f"{WORKSPACE_BASE}/app.yaml")
    print(f"  app.yaml updated with GENIE_SPACE_ID={space_id}")


def restore_app_resources():
    body = {
        "description": "CareLenseAI Medical Desert Planner — Track 2",
        "resources": [{
            "name": "sql-warehouse",
            "sql_warehouse": {"id": WAREHOUSE_ID, "permission": "CAN_USE"},
        }],
    }
    r = api("PATCH", f"/api/2.0/apps/{APP_NAME}", body)
    print(f"  App PATCH resources: {r.status_code}")


def upload_notebooks():
    from scripts.deploy_infrastructure import upload_job_notebooks
    return upload_job_notebooks()


def create_all_jobs():
    jobs = [
        ("[CareLenseAI] Gold Materialization", f"{WORKSPACE_BASE}/notebooks/jobs/01_materialize_gold.py"),
        ("[CareLenseAI] Grant Permissions", f"{WORKSPACE_BASE}/notebooks/jobs/03_grant_permissions.py"),
        ("[CareLenseAI] Data Readiness Report", f"{WORKSPACE_BASE}/notebooks/jobs/04_data_readiness.py"),
        ("[CareLenseAI] Lakebase Setup", f"{WORKSPACE_BASE}/notebooks/jobs/02_setup_lakebase.py"),
    ]
    ids = {}
    for name, path in jobs:
        jid = create_job(name, path)
        if jid:
            ids[name] = jid
    return ids


def try_lakebase_catalog():
    from databricks import sql

    host = os.environ["DATABRICKS_HOST"].replace("https://", "").rstrip("/")
    conn = sql.connect(
        server_hostname=host,
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        access_token=os.environ["DATABRICKS_TOKEN"],
    )
    with conn.cursor() as cur:
        try:
            cur.execute("SHOW SCHEMAS IN lakebase")
            schemas = [r[0] for r in cur.fetchall()]
            print(f"  Lakebase catalog schemas: {schemas[:10]}")
        except Exception as e:
            print(f"  Lakebase catalog: {e}")
    conn.close()

    r = api("GET", "/api/2.0/database/instances")
    if r.status_code == 200:
        inst = r.json()
        if not inst:
            print("  No Lakebase Postgres instances — attach manually in Apps UI when available")
        else:
            print(f"  Lakebase instances: {inst}")


def main():
    if not os.environ.get("DATABRICKS_TOKEN"):
        print("Set DATABRICKS_HOST and DATABRICKS_TOKEN")
        sys.exit(1)

    print("=== 1. Upload all source files ===")
    try:
        upload_tree()
    except Exception as exc:
        print(f"  Upload tree error (continuing): {exc}")
    upload_job_notebooks()

    print("\n=== 2. Unity Catalog schemas ===")
    create_schemas_sql()

    print("\n=== 3. DLT pipeline ===")
    pid = create_or_update_pipeline()
    pipeline_ok = bool(pid and start_pipeline(pid))

    print("\n=== 4. Gold materialization ===")
    try:
        from scripts.materialize_gold import main as mat_gold
        mat_gold()
        print("  Gold materialized via SQL warehouse")
    except Exception as exc:
        print(f"  Gold materialize error: {exc}")

    print("\n=== 5. Jobs ===")
    job_ids = create_all_jobs()

    print("\n=== 6. Genie space ===")
    genie_id = find_or_create_genie_space()
    if genie_id:
        patch_app_yaml_genie(genie_id)

    print("\n=== 7. App resources + redeploy ===")
    restore_app_resources()
    deploy_app()

    print("\n=== 8. Permissions ===")
    grant_permissions_sql()

    print("\n=== 9. Lakebase check ===")
    try_lakebase_catalog()

    app_url = ""
    g = api("GET", f"/api/2.0/apps/{APP_NAME}")
    if g.status_code == 200:
        app_url = g.json().get("url", "")

    print("\n=== DEPLOYMENT COMPLETE ===")
    print(f"  Workspace: {os.environ.get('DATABRICKS_HOST', '')}")
    print(f"  Pipeline: {'OK' if pipeline_ok else 'SKIPPED/FAILED'}")
    print(f"  Gold: {GOLD_CATALOG}.carelense_gold.*")
    print(f"  Silver: {GOLD_CATALOG}.carelense_silver.*")
    if genie_id:
        print(f"  Genie space: {genie_id}")
    if app_url:
        print(f"  App: {app_url}")
    print(f"  Jobs: {', '.join(job_ids.keys())}")
    sp = resolve_app_sp()
    if sp:
        print(f"  App SP: {sp}")
    print("  Agent Bricks: set OPENAI_API_KEY + AGENT_ENDPOINT in app env when ready")
    print("  Lakebase: attach postgres resource in Apps UI, then run [CareLenseAI] Lakebase Setup job")


if __name__ == "__main__":
    main()
