# Databricks notebook source
# MAGIC %md
# MAGIC # CareLenseAI — Gold Materialization
# MAGIC Writes deterministic scores to **`main.carelense_gold`** (must match app `GOLD_CATALOG`).
# MAGIC
# MAGIC **Run this notebook** if you see:
# MAGIC `TABLE_OR_VIEW_NOT_FOUND main.carelense_gold.gold_geo_capability`

# COMMAND ----------

# MAGIC %pip install -q pandas

# COMMAND ----------

import os
import sys

# Repo path on workspace (adjust if you uploaded elsewhere)
for candidate in [
    "/Workspace/Users/rajaniesh@rajanieshkaushikk.com/apps/carelenseai",
    "/Workspace/Repos/carelenseai",
]:
    if os.path.isdir(candidate):
        sys.path.insert(0, candidate)
        break

# COMMAND ----------

# IMPORTANT: must match app.yaml GOLD_CATALOG
os.environ["GOLD_CATALOG"] = "main"

from pipeline.gold_compute import compute_gold_tables, GOLD_COLUMNS, CITE_COLUMNS, SOURCE_CAT
from scripts.materialize_gold import write_gold_spark

# COMMAND ----------

# Load source tables via Spark (fast, no token needed)
facilities = spark.table(f"{SOURCE_CAT}.facilities").filter(
    "address_countryCode = 'IN' OR lower(countries) LIKE '%india%'"
)
pincodes = spark.table(f"{SOURCE_CAT}.india_post_pincode_directory")
nfhs = spark.table(f"{SOURCE_CAT}.nfhs_5_district_health_indicators")

print(f"Facilities: {facilities.count()}, Pincodes: {pincodes.count()}, NFHS: {nfhs.count()}")

# COMMAND ----------

gold_df, cite_df = compute_gold_tables(
    facilities.toPandas(),
    pincodes.toPandas(),
    nfhs.toPandas(),
)
print(f"Gold rows: {len(gold_df)}, Citations: {len(cite_df)}")
display(gold_df.groupby(["capability", "verdict"]).size().reset_index(name="count").head(20))

# COMMAND ----------

catalog = os.environ["GOLD_CATALOG"]
write_gold_spark(spark, gold_df, cite_df, catalog)

# COMMAND ----------

# Verify tables exist
spark.sql(f"""
SELECT capability, verdict, COUNT(*) AS n
FROM {catalog}.carelense_gold.gold_geo_capability
WHERE grain = 'state'
GROUP BY capability, verdict
ORDER BY capability, verdict
""").display()

# COMMAND ----------

spark.sql(f"SELECT COUNT(*) AS citations FROM {catalog}.carelense_gold.gold_evidence_citations").display()
