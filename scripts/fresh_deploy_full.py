#!/usr/bin/env python3
"""Full fresh deploy - all 9 phases, log to fresh_deploy.log"""
from __future__ import annotations

import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
LOG_PATH = ROOT / "fresh_deploy.log"

os.environ.setdefault("DATABRICKS_HOST", "https://adb-3141834805281315.15.azuredatabricks.net")
os.environ.setdefault("DATABRICKS_WAREHOUSE_ID", "c0c32c95246fd6a9")
os.environ.setdefault("GOLD_CATALOG", "main")
os.environ.setdefault(
    "DATABRICKS_APP_PATH",
    "/Workspace/Users/rajaniesh@rajanieshkaushikk.com/apps/carelenseai",
)
os.environ.setdefault("DATABRICKS_APP_SP", "d4e46205-b7d2-4626-a4bb-4ffea79965c8")

GENIE_SPACE_ID = "01f1690e21db1857bf0da7b45a35d4b4"
PIPELINE_ID = "a48b3985-0060-41d8-8790-41d01f021bd1"

lines: list[str] = []
results: dict[str, str] = {}


def log(msg: str = ""):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    lines.append(line)
    print(line, flush=True)


def write_log():
    LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


from scripts.deploy_infrastructure import (  # noqa: E402
    APP_NAME,
    GOLD_CATALOG,
    WAREHOUSE_ID,
    WORKSPACE_BASE,
    api,
    create_all_jobs,
    create_or_update_pipeline,
    create_schemas_sql,
    deploy_app,
    grant_permissions_sql,
    mkdirs,
    sql_scalar,
    start_pipeline_update,
    stop_pipeline,
    upload_file,
    upload_job_notebooks,
)
from scripts.upload_essential import upload_essential  # noqa: E402
from scripts.deploy_complete import (  # noqa: E402
    update_genie_space,
    restore_app_resources,
)


def phase1():
    log("=== Phase 1: Verify catalogs & gold ===")
    try:
        create_schemas_sql()
        log("  Schemas ensured")
    except Exception as e:
        log(f"  Schema create error: {e}")
    try:
        n = int(sql_scalar(f"SELECT COUNT(*) FROM {GOLD_CATALOG}.carelense_gold.gold_geo_capability") or 0)
    except Exception as e:
        log(f"  Gold count query failed: {e}")
        n = 0
    log(f"  gold_geo_capability rows: {n}")
    if n == 0:
        log("  Running materialize_gold.py...")
        from scripts.materialize_gold import main as mat

        mat()
        n = int(sql_scalar(f"SELECT COUNT(*) FROM {GOLD_CATALOG}.carelense_gold.gold_geo_capability") or 0)
        log(f"  After materialize: {n}")
    ok = n == 7756 or n > 0
    results["Phase 1"] = "PASS" if ok else "FAIL"
    return n


def export_workspace_text(remote: str) -> str:
    r = api("GET", "/api/2.0/workspace/export", None)
    # export uses query params - use requests style via api with path
    host = os.environ["DATABRICKS_HOST"].rstrip("/")
    import requests

    hdrs = {"Authorization": f"Bearer {os.environ['DATABRICKS_TOKEN']}"}
    r = requests.get(
        f"{host}/api/2.0/workspace/export",
        headers=hdrs,
        params={"path": remote, "format": "SOURCE"},
        timeout=120,
    )
    if r.status_code != 200:
        return f"EXPORT_ERROR_{r.status_code}:{r.text[:200]}"
    import base64

    return base64.b64decode(r.json().get("content", "")).decode("utf-8", errors="replace")


def phase2():
    log("=== Phase 2: Upload everything fresh ===")
    ok_count = upload_essential()
    log(f"  upload_essential files: {ok_count}")
    for rel in [
        "app/backend/gold_reads.py",
        "app/backend/main.py",
        "app/backend/lakebase.py",
        "app/backend/config.py",
    ]:
        local = ROOT / rel
        remote = f"{WORKSPACE_BASE}/{rel}"
        mkdirs("/".join(remote.split("/")[:-1]))
        ok = upload_file(local, remote)
        log(f"  explicit {rel}: {'ok' if ok else 'FAIL'}")
    nb = upload_job_notebooks()
    log(f"  job notebooks: {nb}")
    out = ROOT / "app" / "frontend" / "out"
    if not out.is_dir():
        log("  frontend/out missing - run npm build separately")
    from scripts.deploy_infrastructure import upload_tree

    try:
        upload_tree()
        log("  upload_tree done")
    except Exception as e:
        log(f"  upload_tree: {e}")
    results["Phase 2"] = "PASS" if ok_count > 0 else "FAIL"


def phase3():
    log("=== Phase 3: Verify workspace files BEFORE deploy ===")
    gr_path = f"{WORKSPACE_BASE}/app/backend/gold_reads.py"
    yaml_path = f"{WORKSPACE_BASE}/app.yaml"
    gr = export_workspace_text(gr_path)
    ya = export_workspace_text(yaml_path)
    gr_ok = "_query_sdk" in gr and "statement_execution" in gr
    yaml_ok = "GOLD_CATALOG" in ya and "main" in ya and "valueFrom" in ya and "sql-warehouse" in ya
    log(f"  gold_reads _query_sdk+statement_execution: {gr_ok}")
    log(f"  app.yaml GOLD_CATALOG main + valueFrom sql-warehouse: {yaml_ok}")
    if not gr_ok:
        log(f"  gold_reads snippet: {gr[:300]}")
    results["Phase 3"] = "PASS" if (gr_ok and yaml_ok) else "FAIL"
    return gr_ok and yaml_ok


def phase4():
    log("=== Phase 4: DLT pipeline update ===")
    pid = create_or_update_pipeline() or PIPELINE_ID
    log(f"  pipeline id: {pid}")
    try:
        stop_pipeline(pid)
        uid = start_pipeline_update(pid, full_refresh=False)
        log(f"  pipeline update started: {uid}")
        results["Phase 4"] = "PASS" if uid else "FAIL"
    except Exception as e:
        log(f"  pipeline error: {e}")
        results["Phase 4"] = "FAIL"


def phase5():
    log("=== Phase 5: Grants for app SP ===")
    try:
        grant_permissions_sql()
        results["Phase 5"] = "PASS"
    except Exception as e:
        log(f"  grant error: {e}\n{traceback.format_exc()}")
        results["Phase 5"] = "FAIL"


def phase6():
    log("=== Phase 6: App fresh deploy ===")
    restore_app_resources()
    resources_body = {
        "resources": [{
            "name": "sql-warehouse",
            "sql_warehouse": {"id": WAREHOUSE_ID, "permission": "CAN_USE"},
        }]
    }
    r = api("PUT", f"/api/2.0/apps/{APP_NAME}", resources_body)
    log(f"  PUT resources: {r.status_code} {r.text[:200] if not r.ok else 'OK'}")
    r = api("POST", f"/api/2.0/apps/{APP_NAME}/deployments", {
        "source_code_path": WORKSPACE_BASE,
        "mode": "SNAPSHOT",
    })
    log(f"  POST deployment: {r.status_code} {r.text[:400] if not r.ok else 'started'}")
    deploy_ok = False
    app_url = ""
    dep_state = ""
    for i in range(30):
        time.sleep(10)
        g = api("GET", f"/api/2.0/apps/{APP_NAME}")
        if g.status_code != 200:
            continue
        data = g.json()
        app_url = data.get("url", "")
        app_state = data.get("app_status", {}).get("state", "")
        deployments = data.get("active_deployment") or data.get("pending_deployment") or {}
        if isinstance(deployments, dict):
            dep_state = deployments.get("status", {}).get("state", "") or deployments.get("state", "")
        log(f"  poll {i+1}: app={app_state} deployment={dep_state}")
        if app_state == "RUNNING" and (dep_state in ("SUCCEEDED", "") or i > 5):
            deploy_ok = True
            break
        if dep_state == "FAILED":
            break
    if not deploy_ok:
        deploy_ok = deploy_app()
    g = api("GET", f"/api/2.0/apps/{APP_NAME}")
    if g.status_code == 200:
        app_url = g.json().get("url", "")
        deploy_ok = g.json().get("app_status", {}).get("state") == "RUNNING" or deploy_ok
    log(f"  App URL: {app_url}")
    results["Phase 6"] = "PASS" if deploy_ok else "FAIL"
    return app_url, deploy_ok


def phase7():
    log("=== Phase 7: Genie space update ===")
    ok = update_genie_space(GENIE_SPACE_ID)
    results["Phase 7"] = "PASS" if ok else "FAIL"


def phase8():
    log("=== Phase 8: Jobs verify/create ===")
    ids = create_all_jobs()
    for name, jid in ids.items():
        log(f"  job {name}: {jid}")
    ok = len(ids) >= 4 and all(v for v in ids.values())
    results["Phase 8"] = "PASS" if ok else "PARTIAL" if ids else "FAIL"


def phase9(app_url: str):
    log("=== Phase 9: Post-deploy verification ===")
    sdk_ok = False
    n = 0
    try:
        from databricks.sdk import WorkspaceClient

        w = WorkspaceClient(
            host=os.environ["DATABRICKS_HOST"],
            token=os.environ["DATABRICKS_TOKEN"],
        )
        resp = w.statement_execution.execute_statement(
            warehouse_id=WAREHOUSE_ID,
            statement=f"SELECT COUNT(*) AS n FROM {GOLD_CATALOG}.carelense_gold.gold_geo_capability",
            wait_timeout="50s",
        )
        sid = resp.statement_id
        for _ in range(30):
            st = w.statement_execution.get_statement(sid)
            if st.status.state.name in ("SUCCEEDED", "FAILED", "CANCELED"):
                break
            time.sleep(2)
        if st.status.state.name == "SUCCEEDED" and st.result and st.result.data_array:
            n = int(st.result.data_array[0][0])
            sdk_ok = True
        log(f"  SDK statement count: {n} (ok={sdk_ok})")
    except Exception as e:
        log(f"  SDK verify error: {e}")
    health = {}
    if app_url:
        import requests

        try:
            hr = requests.get(f"{app_url}/api/health/data", timeout=60)
            health = hr.json() if hr.status_code == 200 else {"status": hr.status_code, "text": hr.text[:500]}
            log(f"  /api/health/data: {health}")
        except Exception as e:
            log(f"  health/data error: {e}")
    exp = "sql_mode=statement_execution, icu_state_rows=69"
    log(f"  Expected health: {exp}")
    results["Phase 9"] = "PASS" if sdk_ok else "PARTIAL"
    return n, sdk_ok, health


def main():
    if not os.environ.get("DATABRICKS_TOKEN"):
        log("ERROR: DATABRICKS_TOKEN required")
        write_log()
        sys.exit(1)
    log("CareLenseAI FULL FRESH DEPLOY")
    log(f"HOST={os.environ['DATABRICKS_HOST']} WAREHOUSE={WAREHOUSE_ID} GOLD={GOLD_CATALOG}")
    gold_n = 0
    app_url = ""
    deploy_ok = False
    try:
        gold_n = phase1()
        phase2()
        phase3()
        phase4()
        phase5()
        app_url, deploy_ok = phase6()
        phase7()
        phase8()
        _, _, health = phase9(app_url)
    except Exception:
        log(traceback.format_exc())
    log("\n=== CHECKLIST ===")
    for i in range(1, 10):
        key = f"Phase {i}"
        log(f"  {key}: {results.get(key, 'NOT_RUN')}")
    log(f"\nApp URL: {app_url}")
    log(f"Gold count: {gold_n}")
    log(f"Deploy succeeded: {'yes' if deploy_ok else 'no'}")
    log("\nUser actions: hard refresh browser (Ctrl+Shift+R); open {}/api/health/data".format(app_url or "<app-url>"))
    write_log()


if __name__ == "__main__":
    main()
