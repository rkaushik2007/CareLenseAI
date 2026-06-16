# Databricks notebook source
# MAGIC %md
# MAGIC # CareLenseAI — Lakebase Schema Setup
# MAGIC Creates planner state tables in Lakebase Postgres for watchlist, notes, overrides, scenarios.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Instructions
# MAGIC 1. Attach a **Lakebase** database resource to the `carelenseai` app (key: `postgres`)
# MAGIC 2. Run this notebook connected to Lakebase, OR execute the SQL below in Lakebase SQL editor
# MAGIC 3. Set `PGHOST` env on the app via Lakebase resource binding

# COMMAND ----------

schema_sql = """
CREATE TABLE IF NOT EXISTS planner_watch (
  planner_id TEXT NOT NULL,
  unit_key   TEXT NOT NULL,
  capability TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (planner_id, unit_key, capability)
);

CREATE TABLE IF NOT EXISTS planner_notes (
  planner_id TEXT NOT NULL,
  unit_key   TEXT NOT NULL,
  capability TEXT NOT NULL,
  note       TEXT,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (planner_id, unit_key, capability)
);

CREATE TABLE IF NOT EXISTS planner_overrides (
  planner_id TEXT NOT NULL,
  unit_key   TEXT NOT NULL,
  capability TEXT NOT NULL,
  verdict    TEXT CHECK (verdict IN ('desert','blind','served','unknown')),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (planner_id, unit_key, capability)
);

CREATE TABLE IF NOT EXISTS planner_scenarios (
  planner_id TEXT NOT NULL,
  name       TEXT NOT NULL,
  cap        TEXT NOT NULL,
  grain      TEXT NOT NULL,
  overlay    BOOLEAN DEFAULT FALSE,
  sort       TEXT DEFAULT 'priority',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (planner_id, name)
);
"""

print(schema_sql)

# COMMAND ----------

# If running with Lakebase connection via %sql magic or psycopg2:
try:
    import os
    import psycopg2
    conn = psycopg2.connect(
        host=os.environ["PGHOST"],
        dbname=os.environ.get("PGDATABASE", "postgres"),
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        port=os.environ.get("PGPORT", "5432"),
        sslmode=os.environ.get("PGSSLMODE", "require"),
    )
    with conn.cursor() as cur:
        cur.execute(schema_sql)
    conn.commit()
    conn.close()
    print("Lakebase schema created successfully.")
except Exception as e:
    print(f"Lakebase not connected in this notebook context: {e}")
    print("Run the SQL above manually in Lakebase, or attach Lakebase to the app.")
