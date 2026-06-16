#!/usr/bin/env python3
"""
Deploy full CareLenseAI infrastructure to Databricks:
  - Unity Catalog schemas
  - Lakeflow DLT pipeline (bronze/silver)
  - Jobs (gold materialization, permissions, data readiness)
  - App redeploy with SQL warehouse
  - Pipeline run + gold job trigger
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path

import requests

_bprint = print


def print(*args, **kwargs):  # noqa: A001
    kwargs.setdefault("flush", True)
    _bprint(*args, **kwargs)

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_BASE = os.environ.get(
    "DATABRICKS_APP_PATH",
    "/Workspace/Users/rajaniesh@rajanieshkaushikk.com/apps/carelenseai",
)
APP_NAME = "carelenseai"
WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "c0c32c95246fd6a9")
GOLD_CATALOG = os.environ.get("GOLD_CATALOG", "main")
SOURCE_CATALOG = os.environ.get("FACILITY_CATALOG", "databricks_virtue_foundation_dataset_dais_2026")
SOURCE_SCHEMA = os.environ.get("FACILITY_SCHEMA", "virtue_foundation_dataset")
APP_SP = os.environ.get("DATABRICKS_APP_SP", "")


def host_hdrs():
    host = os.environ["DATABRICKS_HOST"].rstrip("/")
    return host, {"Authorization": f"Bearer {os.environ['DATABRICKS_TOKEN']}", "Content-Type": "application/json"}


def api(method: str, path: str, body=None, timeout=120, retries=4):
    host, hdrs = host_hdrs()
    url = f"{host}{path}"
    last_exc = None
    for attempt in range(retries):
        try:
            r = requests.request(method, url, headers=hdrs, json=body, timeout=timeout)
            if r.status_code in (429, 503):
                time.sleep(5 * (attempt + 1))
                continue
            return r
        except requests.RequestException as exc:
            last_exc = exc
            print(f"  API retry {attempt + 1}/{retries} {method} {path}: {exc}")
            time.sleep(5 * (attempt + 1))
    if last_exc:
        raise last_exc
    raise RuntimeError(f"API failed: {method} {path}")


def mkdirs(path: str):
    api("POST", "/api/2.0/workspace/mkdirs", {"path": path})


def delete_workspace_path(path: str, recursive: bool = True) -> bool:
    r = api("POST", "/api/2.0/workspace/delete", {"path": path, "recursive": recursive})
    if r.status_code in (200, 404):
        return True
    print(f"  delete fail {path}: {r.status_code} {r.text[:120]}")
    return False


def upload_file(local: Path, remote: str, retries: int = 4) -> bool:
    host, hdrs = host_hdrs()
    content = base64.b64encode(local.read_bytes()).decode()
    body = {"path": remote, "format": "RAW", "content": content, "overwrite": True}
    if local.suffix == ".py":
        body["format"] = "AUTO"
        body["language"] = "PYTHON"
    for attempt in range(retries):
        try:
            r = requests.post(
                f"{host}/api/2.0/workspace/import",
                headers=hdrs,
                json=body,
                timeout=180,
            )
            if r.status_code == 200:
                return True
            if "Cannot overwrite" in r.text and delete_workspace_path(remote):
                r = requests.post(
                    f"{host}/api/2.0/workspace/import",
                    headers=hdrs,
                    json=body,
                    timeout=180,
                )
                if r.status_code == 200:
                    return True
            print(f"  upload fail {remote}: {r.status_code} {r.text[:120]}")
        except requests.RequestException as exc:
            print(f"  upload retry {attempt + 1}/{retries} {remote}: {exc}")
            time.sleep(5 * (attempt + 1))
    return False


def upload_tree():
    """Upload all project files needed on Databricks."""
    skip = {".git", ".venv", "venv", "node_modules", ".next", "__pycache__", "data", ".idea", "src"}
    skip_files = {".env", ".env.example"}

    files = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(s in p.parts for s in skip):
            continue
        if p.name in skip_files:
            continue
        if p.suffix in (".ts", ".tsx") and "frontend/src" in str(p):
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith("notebooks/jobs/") and p.suffix == ".py":
            continue
        files.append((p, f"{WORKSPACE_BASE}/{rel}"))

    print(f"Uploading {len(files)} files...")
    ok = 0
    for local, remote in files:
        try:
            mkdirs("/".join(remote.split("/")[:-1]))
        except Exception as exc:
            print(f"  mkdir skip {remote}: {exc}")
        if upload_file(local, remote):
            ok += 1
        elif ok % 10 == 0:
            print(f"  progress {ok}/{len(files)}")
    print(f"  {ok}/{len(files)} uploaded")
    return ok


def upload_job_notebooks() -> dict[str, bool]:
    """Upload job notebooks as .py files (delete conflicting folder paths first)."""
    nb_root = ROOT / "notebooks" / "jobs"
    results: dict[str, bool] = {}
    if not nb_root.is_dir():
        return results
    mkdirs(f"{WORKSPACE_BASE}/notebooks/jobs")
    for nb in sorted(nb_root.glob("*.py")):
        remote = f"{WORKSPACE_BASE}/notebooks/jobs/{nb.name}"
        delete_workspace_path(f"{WORKSPACE_BASE}/notebooks/jobs/{nb.stem}")
        delete_workspace_path(remote)
        ok = upload_file(nb, remote)
        results[nb.name] = ok
        print(f"  notebook {'ok' if ok else 'FAIL'}: {nb.name} -> {remote}")
    return results


def create_schemas_sql():
    """Create UC schemas via SQL warehouse."""
    from databricks import sql

    host = os.environ["DATABRICKS_HOST"].replace("https://", "").rstrip("/")
    conn = sql.connect(
        server_hostname=host,
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        access_token=os.environ["DATABRICKS_TOKEN"],
    )
    stmts = [
        f"CREATE SCHEMA IF NOT EXISTS {GOLD_CATALOG}.carelense_gold COMMENT 'CareLenseAI Gold serving tables'",
        f"CREATE SCHEMA IF NOT EXISTS {GOLD_CATALOG}.carelense_silver COMMENT 'CareLenseAI Silver DLT pipeline output'",
    ]
    with conn.cursor() as cur:
        for s in stmts:
            cur.execute(s)
            print(f"  SQL OK: {s[:60]}...")
    conn.close()


def create_or_update_pipeline() -> str | None:
    """Create DLT medallion pipeline."""
    pipeline_path = ROOT / "pipeline" / "dlt_pipeline.json"
    body = json.loads(pipeline_path.read_text())
    body["catalog"] = GOLD_CATALOG
    body["target"] = "carelense_silver"
    for lib in body.get("libraries", []):
        fp = lib.get("file", {}).get("path", "")
        if fp.startswith("/Workspace/"):
            lib["file"]["path"] = fp.replace(
                "/Workspace/Users/rajaniesh@rajanieshkaushikk.com/apps/carelenseai",
                WORKSPACE_BASE,
            )

    # Check if pipeline exists
    r = api("GET", "/api/2.0/pipelines?max_results=100")
    existing_id = None
    if r.status_code == 200:
        for p in r.json().get("statuses", []):
            if p.get("name") == body["name"]:
                existing_id = p.get("pipeline_id")
                break

    if existing_id:
        print(f"Updating pipeline {existing_id}...")
        r = api("PUT", f"/api/2.0/pipelines/{existing_id}", body)
    else:
        print("Creating DLT pipeline...")
        r = api("POST", "/api/2.0/pipelines", body)

    if r.status_code not in (200, 201):
        print(f"  Pipeline error: {r.status_code} {r.text[:400]}")
        return existing_id

    pid = r.json().get("pipeline_id", existing_id)
    print(f"  Pipeline ID: {pid}")
    return pid


def stop_pipeline(pipeline_id: str) -> None:
    """Stop in-flight pipeline updates before starting a fresh run."""
    r = api("POST", f"/api/2.0/pipelines/{pipeline_id}/stop")
    if r.status_code in (200, 400):
        print(f"  Pipeline stop requested ({r.status_code})")
    else:
        print(f"  Pipeline stop: {r.status_code} {r.text[:120]}")
    time.sleep(5)


def start_pipeline_update(pipeline_id: str, full_refresh: bool = False) -> str | None:
    print(f"Starting pipeline update {pipeline_id}...")
    r = api("POST", f"/api/2.0/pipelines/{pipeline_id}/updates", {"full_refresh": full_refresh})
    if r.status_code not in (200, 201):
        print(f"  Start failed: {r.status_code} {r.text[:300]}")
        return None
    update_id = r.json().get("update_id")
    print(f"  Update ID: {update_id}")
    return update_id


def wait_pipeline(pipeline_id: str, update_id: str, timeout_polls: int = 90) -> bool:
    for _ in range(timeout_polls):
        time.sleep(20)
        g = api("GET", f"/api/2.0/pipelines/{pipeline_id}/updates/{update_id}")
        if g.status_code != 200:
            continue
        state = g.json().get("update", {}).get("state", "")
        print(f"  Pipeline: {state}")
        if state == "COMPLETED":
            return True
        if state in ("FAILED", "CANCELED"):
            print(f"  Pipeline failed: {g.text[:500]}")
            return False
    print("  Pipeline timed out")
    return False


def start_pipeline(pipeline_id: str) -> bool:
    stop_pipeline(pipeline_id)
    update_id = start_pipeline_update(pipeline_id)
    if not update_id:
        return False
    return wait_pipeline(pipeline_id, update_id)


def create_job(name: str, notebook_path: str) -> int | None:
    """Create or reset a Databricks job."""
    body = {
        "name": name,
        "tasks": [{
            "task_key": "main",
            "notebook_task": {"notebook_path": notebook_path, "source": "WORKSPACE"},
            "environment_key": "default",
        }],
        "environments": [{"environment_key": "default", "spec": {"environment_version": "2"}}],
    }

    r = api("GET", "/api/2.1/jobs/list?limit=100")
    job_id = None
    if r.status_code == 200:
        for j in r.json().get("jobs", []):
            if j.get("settings", {}).get("name") == name:
                job_id = j["job_id"]
                break

    if job_id:
        r = api("POST", "/api/2.1/jobs/reset", {"job_id": job_id, "new_settings": body})
    else:
        r = api("POST", "/api/2.1/jobs/create", body)

    if r.status_code not in (200, 201):
        print(f"  Job '{name}' error: {r.status_code} {r.text[:300]}")
        return job_id

    jid = r.json().get("job_id", job_id)
    print(f"  Job '{name}' ID: {jid}")
    return jid


def resolve_app_sp() -> str:
    global APP_SP
    if APP_SP:
        return APP_SP
    r = api("GET", f"/api/2.0/apps/{APP_NAME}")
    if r.status_code == 200:
        APP_SP = (
            r.json().get("service_principal_client_id")
            or r.json().get("service_principal_id")
            or r.json().get("identity", {}).get("service_principal_client_id", "")
        )
    return APP_SP


def deploy_app():
    resources_body = {
        "resources": [{
            "name": "sql-warehouse",
            "sql_warehouse": {"id": WAREHOUSE_ID, "permission": "CAN_USE"},
        }]
    }
    r = api("GET", f"/api/2.0/apps/{APP_NAME}")
    if r.status_code == 404:
        r = api("POST", "/api/2.0/apps", {"name": APP_NAME, **resources_body})
        print(f"  App create: {r.status_code}")
    else:
        r = api("PUT", f"/api/2.0/apps/{APP_NAME}", resources_body)
        if r.status_code not in (200, 204):
            r = api("PATCH", f"/api/2.0/apps/{APP_NAME}", resources_body)
        print(f"  App resources: {r.status_code} {r.text[:200] if not r.ok else ''}")

    r = api("POST", f"/api/2.0/apps/{APP_NAME}/deployments", {
        "source_code_path": WORKSPACE_BASE,
        "mode": "SNAPSHOT",
    })
    print(f"  App deploy: {r.status_code} {r.text[:300] if not r.ok else ''}")
    for _ in range(18):
        time.sleep(10)
        g = api("GET", f"/api/2.0/apps/{APP_NAME}")
        if g.status_code != 200:
            continue
        state = g.json().get("app_status", {}).get("state", "")
        if state == "RUNNING":
            print(f"  App URL: {g.json().get('url')}")
            return True
    return False


def run_job(job_id: int) -> bool:
    r = api("POST", "/api/2.1/jobs/run-now", {"job_id": job_id})
    if r.status_code != 200:
        print(f"  Run job failed: {r.text[:200]}")
        return False
    run_id = r.json()["run_id"]
    print(f"  Job run started: {run_id}")
    for _ in range(60):
        time.sleep(15)
        g = api("GET", f"/api/2.1/jobs/runs/get?run_id={run_id}")
        if g.status_code != 200:
            continue
        state = g.json().get("state", {}).get("life_cycle_state", "")
        result = g.json().get("state", {}).get("result_state", "")
        print(f"    Job state: {state} {result}")
        if state == "TERMINATED":
            return result == "SUCCESS"
    return False


def grant_permissions_sql():
    from databricks import sql

    sp = resolve_app_sp()
    if not sp:
        print("  Skip grants — app service principal not available yet")
        return

    host = os.environ["DATABRICKS_HOST"].replace("https://", "").rstrip("/")
    conn = sql.connect(
        server_hostname=host,
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        access_token=os.environ["DATABRICKS_TOKEN"],
    )
    grants = [
        f"GRANT USE CATALOG ON CATALOG {GOLD_CATALOG} TO `{sp}`",
        f"GRANT USE SCHEMA ON SCHEMA {GOLD_CATALOG}.carelense_gold TO `{sp}`",
        f"GRANT SELECT ON SCHEMA {GOLD_CATALOG}.carelense_gold TO `{sp}`",
        f"GRANT USE SCHEMA ON SCHEMA {GOLD_CATALOG}.carelense_silver TO `{sp}`",
        f"GRANT SELECT ON SCHEMA {GOLD_CATALOG}.carelense_silver TO `{sp}`",
        f"GRANT USE CATALOG ON CATALOG {SOURCE_CATALOG} TO `{sp}`",
        f"GRANT USE SCHEMA ON SCHEMA {SOURCE_CATALOG}.{SOURCE_SCHEMA} TO `{sp}`",
        f"GRANT SELECT ON SCHEMA {SOURCE_CATALOG}.{SOURCE_SCHEMA} TO `{sp}`",
    ]
    with conn.cursor() as cur:
        for g in grants:
            try:
                cur.execute(g)
                print(f"  Grant OK: {g[:70]}...")
            except Exception as e:
                print(f"  Grant skip: {e}")
    conn.close()


def sql_scalar(query: str):
    from databricks import sql

    host = os.environ["DATABRICKS_HOST"].replace("https://", "").rstrip("/")
    conn = sql.connect(
        server_hostname=host,
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        access_token=os.environ["DATABRICKS_TOKEN"],
    )
    with conn.cursor() as cur:
        cur.execute(query)
        row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def verify_deployment(app_url: str = "") -> dict:
    """Return status dict for final demo table."""
    status = {
        "gold_rows": None,
        "silver_tables": None,
        "pipeline_state": "UNKNOWN",
        "app_state": "UNKNOWN",
        "healthz": False,
        "summary_api": False,
    }
    try:
        status["gold_rows"] = sql_scalar(
            f"SELECT COUNT(*) FROM {GOLD_CATALOG}.carelense_gold.gold_geo_capability"
        )
    except Exception as exc:
        status["gold_rows"] = f"ERR: {exc}"

    try:
        status["silver_tables"] = sql_scalar(
            f"SELECT COUNT(*) FROM {GOLD_CATALOG}.information_schema.tables "
            f"WHERE table_schema = 'carelense_silver'"
        )
    except Exception as exc:
        status["silver_tables"] = f"ERR: {exc}"

    r = api("GET", "/api/2.0/pipelines?max_results=100")
    if r.status_code == 200:
        for p in r.json().get("statuses", []):
            if p.get("name") == "carelense_medallion_pipeline":
                status["pipeline_state"] = p.get("state", "UNKNOWN")
                for u in p.get("latest_updates") or []:
                    if u.get("state") in ("COMPLETED", "FAILED", "RUNNING"):
                        status["pipeline_state"] = u.get("state", status["pipeline_state"])
                        break
                break

    g = api("GET", f"/api/2.0/apps/{APP_NAME}")
    if g.status_code == 200:
        status["app_state"] = g.json().get("app_status", {}).get("state", "UNKNOWN")
        app_url = app_url or g.json().get("url", "")

    if app_url:
        try:
            hr = requests.get(f"{app_url}/healthz", timeout=30)
            status["healthz"] = hr.status_code == 200
        except Exception:
            pass
        try:
            sr = requests.get(f"{app_url}/api/summary", timeout=30)
            status["summary_api"] = sr.status_code == 200
        except Exception:
            pass

    return status


def create_all_jobs() -> dict[str, int | None]:
    jobs = [
        ("[CareLenseAI] Gold Materialization", f"{WORKSPACE_BASE}/notebooks/jobs/01_materialize_gold.py"),
        ("[CareLenseAI] Lakebase Setup", f"{WORKSPACE_BASE}/notebooks/jobs/02_setup_lakebase.py"),
        ("[CareLenseAI] Grant Permissions", f"{WORKSPACE_BASE}/notebooks/jobs/03_grant_permissions.py"),
        ("[CareLenseAI] Data Readiness Report", f"{WORKSPACE_BASE}/notebooks/jobs/04_data_readiness.py"),
    ]
    ids: dict[str, int | None] = {}
    for name, path in jobs:
        ids[name] = create_job(name, path)
    return ids


def main():
    if not os.environ.get("DATABRICKS_TOKEN"):
        print("Set DATABRICKS_HOST and DATABRICKS_TOKEN")
        sys.exit(1)

    import threading

    print("=== 1. Upload source ===")
    upload_tree()
    nb_results = upload_job_notebooks()
    if not all(nb_results.values()):
        print(f"  WARNING: notebook upload issues: {nb_results}")

    print("\n=== 2. Unity Catalog schemas ===")
    create_schemas_sql()

    print("\n=== 3. DLT Pipeline (bronze/silver) + parallel Gold ===")
    pid = create_or_update_pipeline()
    pipeline_ok = False
    gold_parallel_ok = False
    gold_err = None

    if pid:
        stop_pipeline(pid)
        update_id = start_pipeline_update(pid)
        if update_id:

            def _run_gold():
                nonlocal gold_parallel_ok, gold_err
                try:
                    from scripts.materialize_gold import main as mat_gold
                    mat_gold()
                    gold_parallel_ok = True
                except Exception as exc:
                    gold_err = str(exc)
                    print(f"  Gold materialize error: {exc}")

            gold_thread = threading.Thread(target=_run_gold, name="gold-materialize")
            gold_thread.start()
            pipeline_ok = wait_pipeline(pid, update_id)
            gold_thread.join()
            if gold_err:
                print(f"  Parallel gold failed: {gold_err}")
        else:
            print("  Pipeline start failed — running gold sequentially")
            try:
                from scripts.materialize_gold import main as mat_gold
                mat_gold()
                gold_parallel_ok = True
            except Exception as exc:
                print(f"  Gold materialize error: {exc}")
    else:
        print("  No pipeline ID — running gold only")
        try:
            from scripts.materialize_gold import main as mat_gold
            mat_gold()
            gold_parallel_ok = True
        except Exception as exc:
            print(f"  Gold materialize error: {exc}")

    print("\n=== 4. Jobs (create/update all) ===")
    job_ids = create_all_jobs()

    print("\n=== 5. Run grant permissions job ===")
    grant_job = job_ids.get("[CareLenseAI] Grant Permissions")
    grant_ok = run_job(grant_job) if grant_job else False
    if not grant_ok:
        grant_permissions_sql()

    try:
        gold_count = sql_scalar(f"SELECT COUNT(*) FROM {GOLD_CATALOG}.carelense_gold.gold_geo_capability")
        if not gold_count and job_ids.get("[CareLenseAI] Gold Materialization"):
            print("\n=== 5b. Gold empty — run materialize job ===")
            run_job(job_ids["[CareLenseAI] Gold Materialization"])
    except Exception as exc:
        print(f"  Gold count check skipped: {exc}")

    print("\n=== 6. Redeploy app ===")
    deploy_app()

    print("\n=== 7. Permissions (SQL fallback) ===")
    grant_permissions_sql()

    app_url = ""
    g = api("GET", f"/api/2.0/apps/{APP_NAME}")
    if g.status_code == 200:
        app_url = g.json().get("url", "")

    print("\n=== 8. Verify ===")
    verify = verify_deployment(app_url)

    print("\n=== DEPLOYMENT SUMMARY ===")
    print(f"  Workspace: {os.environ.get('DATABRICKS_HOST', '')}")
    print(f"  Pipeline: {'OK' if pipeline_ok else 'FAILED'}")
    print(f"  Gold (parallel): {'OK' if gold_parallel_ok else 'FAILED/SKIPPED'}")
    print(f"  Gold tables: {GOLD_CATALOG}.carelense_gold.*")
    print(f"  Silver tables: {GOLD_CATALOG}.carelense_silver.*")
    print(f"  Jobs: {', '.join(f'{k}={v}' for k, v in job_ids.items())}")
    if app_url:
        print(f"  App: {app_url}")
    print(f"  Genie: run scripts/deploy_complete.py for Genie space setup")

    print("\n=== STATUS TABLE ===")
    rows = [
        ("Gold rows", verify.get("gold_rows")),
        ("Silver tables", verify.get("silver_tables")),
        ("Pipeline", verify.get("pipeline_state")),
        ("App", verify.get("app_state")),
        ("/healthz", "OK" if verify.get("healthz") else "FAIL"),
        ("/api/summary", "OK" if verify.get("summary_api") else "FAIL"),
    ]
    w = max(len(r[0]) for r in rows) + 2
    for label, val in rows:
        print(f"  {label:<{w}} {val}")

    if not pipeline_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
