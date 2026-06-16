# Deploy a new Databricks workspace (hackathon free tier)

Step-by-step guide for bootstrapping CareLenseAI on a **new** workspace — e.g. the hackathon free-tier URL `https://dbc-d7535c0c-012b.cloud.databricks.com` (AWS) vs the premium Azure workspace `https://adb-3141834805281315.15.azuredatabricks.net`. Each workspace needs its own config; paths and warehouse IDs are not portable.

## 1. Clone the repo

```bash
git clone https://github.com/rkaushik2007/CareLenseAI.git
cd CareLenseAI
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

## 2. Create deploy config

```bash
copy deploy.config.example.yaml deploy.config.yaml   # Windows
# cp deploy.config.example.yaml deploy.config.yaml   # macOS/Linux
```

Edit `deploy.config.yaml`:

| Field | Example (hackathon free) |
|-------|--------------------------|
| `databricks_host` | `https://dbc-d7535c0c-012b.cloud.databricks.com` |
| `databricks_token` | `${DATABRICKS_TOKEN}` (set token in shell, not in file) |
| `warehouse_id` | Your SQL warehouse ID from **Compute → SQL Warehouses** |
| `catalog` | `main` |
| `gold_schema` | `carelense_gold` |
| `workspace_base` | `/Workspace/Users/you@email.com/apps/carelenseai` |
| `app_name` | `carelenseai` |

Set your token in the shell (never commit it):

```bash
# Windows PowerShell
$env:DATABRICKS_TOKEN = "dapi..."

# macOS/Linux
export DATABRICKS_TOKEN="dapi..."
```

`deploy.config.yaml` is gitignored — do not add it to git.

## 3. Prerequisites in the workspace

### SQL warehouse

Create or start a **SQL warehouse** (Serverless or Pro). Copy its ID into `warehouse_id`.

### Unity Catalog

Ensure catalog **`main`** exists (default on hackathon workspaces). The app reads gold tables from `main.carelense_gold`.

### Hackathon facility dataset

From **Marketplace**, add the Virtue Foundation / DAIS facility dataset. Update `FACILITY_CATALOG`, `FACILITY_SCHEMA`, and `FACILITY_TABLE` in `app.yaml` if your catalog names differ.

### DLT pipeline and gold jobs

Full data setup is defined in `databricks.yml`:

- **DLT pipeline** `carelense_medallion_pipeline` — bronze/silver from facility source
- **Job** `[CareLenseAI] Gold Materialization` — runs `notebooks/jobs/01_materialize_gold.py` then `03_grant_permissions.py`
- **Job** `[CareLenseAI] Data Readiness Report` — optional validation

**Option A — infrastructure script (recommended first time):**

```bash
export DATABRICKS_HOST=https://dbc-d7535c0c-012b.cloud.databricks.com
export DATABRICKS_TOKEN=dapi...
export DATABRICKS_WAREHOUSE_ID=your-warehouse-id
export DATABRICKS_APP_PATH=/Workspace/Users/you@email.com/apps/carelenseai
export GOLD_CATALOG=main
python scripts/deploy_infrastructure.py
```

This creates schemas, uploads notebooks, runs the DLT pipeline, and triggers gold materialization.

**Option B — Databricks Asset Bundles:**

```bash
databricks bundle deploy -t default
databricks bundle run carelense_gold_job
```

**Option C — manual:** Run `notebooks/jobs/01_materialize_gold.py` in the workspace after the DLT pipeline completes.

Confirm gold data exists:

```sql
SELECT COUNT(*) FROM main.carelense_gold.gold_geo_capability;
```

## 4. Deploy the app

From the repo root with `deploy.config.yaml` filled in:

```bash
python scripts/deploy_from_config.py
```

Fast backend-only redeploy:

```bash
python scripts/deploy_from_config.py --hotfix
```

Custom config path:

```bash
python scripts/deploy_from_config.py --config path/to/my.config.yaml
```

The script uploads source to `workspace_base`, attaches the SQL warehouse, and deploys the Databricks App.

## 5. Set app secrets (Databricks UI)

In **Compute → Apps → carelenseai → Environment**:

| Secret name | Purpose |
|-------------|---------|
| `openai-api-key` | OpenAI API key for agent / Genie features |
| `genie-space-id` | Optional — if using a Genie space (or set `GENIE_SPACE_ID` in `app.yaml`) |

Wire secrets in `app.yaml` with `valueFrom` entries (see commented examples). Update `GENIE_SPACE_ID` in `app.yaml` to match your workspace Genie space, then redeploy.

## 6. Verify deployment

1. Open the app URL printed by the deploy script (or **Compute → Apps → carelenseai**).
2. Check health endpoints:
   - `https://<app-url>/healthz` → `{"status":"ok"}`
   - `https://<app-url>/api/health/data` → shows `gold_catalog`, `warehouse_id`, and `icu_state_rows` > 0 when gold data is loaded

Example:

```bash
curl -s https://<your-app-url>/api/health/data | python -m json.tool
```

Expected: `"status": "ok"`, `"gold_catalog": "main"`, `"icu_state_rows"` with a positive count.

## Workspace comparison

| | Hackathon (free) | Premium (Azure) |
|---|------------------|-----------------|
| Host | `dbc-d7535c0c-012b.cloud.databricks.com` | `adb-3141834805281315.15.azuredatabricks.net` |
| Catalog | `main` | `main` |
| Config | Separate `deploy.config.yaml` per machine | Same pattern, different host/warehouse/path |

## Troubleshooting

- **401 / auth errors** — Regenerate PAT; confirm `DATABRICKS_TOKEN` is exported before running deploy.
- **Empty map / zero rows** — Run gold materialization job; confirm `GOLD_CATALOG=main` in deployed `app.yaml`.
- **Wrong workspace** — Each host has its own warehouse ID and workspace path; never reuse IDs across workspaces.
- **App FAILED** — Check **Apps → carelenseai → Logs**; ensure `app/frontend/out` exists (run `npm run build` in `app/frontend` if missing).
