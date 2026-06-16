# Databricks notebook source
# MAGIC %md
# MAGIC # CareLenseAI — Setup & Trust Scoring Pipeline
# MAGIC
# MAGIC Run this notebook in your Databricks Free Edition workspace to:
# MAGIC 1. Locate the hackathon facility dataset
# MAGIC 2. Preview trust scoring on sample records
# MAGIC 3. Optionally sync data to Lakebase for fast app reads

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Find the hackathon dataset

# COMMAND ----------

# Find facility tables in Unity Catalog
display(spark.sql("""
    SELECT table_catalog, table_schema, table_name, comment
    FROM system.information_schema.tables
    WHERE LOWER(table_name) LIKE '%facilit%'
       OR LOWER(table_name) LIKE '%health%'
       OR LOWER(table_catalog) LIKE '%dais%'
       OR LOWER(table_catalog) LIKE '%hackathon%'
    ORDER BY table_catalog, table_schema, table_name
"""))

# COMMAND ----------

# Update these after finding your table
CATALOG = "dais_hackathon_2026"  # adjust to your catalog name
SCHEMA = "virtue_foundation"      # adjust to your schema
TABLE = "healthcare_facilities"   # adjust to your table

full_table = f"`{CATALOG}`.`{SCHEMA}`.`{TABLE}`"
print(f"Using table: {full_table}")

# COMMAND ----------

# Preview dataset
df = spark.sql(f"SELECT * FROM {full_table} LIMIT 10")
display(df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Dataset profile

# COMMAND ----------

profile = spark.sql(f"""
    SELECT
        COUNT(*) AS total_records,
        COUNT(DISTINCT state) AS states,
        COUNT(DISTINCT city) AS cities,
        SUM(CASE WHEN description IS NOT NULL AND description != '' THEN 1 ELSE 0 END) / COUNT(*) AS description_pct,
        SUM(CASE WHEN capability IS NOT NULL AND capability != '' THEN 1 ELSE 0 END) / COUNT(*) AS capability_pct,
        SUM(CASE WHEN procedure IS NOT NULL AND procedure != '' THEN 1 ELSE 0 END) / COUNT(*) AS procedure_pct,
        SUM(CASE WHEN equipment IS NOT NULL AND equipment != '' THEN 1 ELSE 0 END) / COUNT(*) AS equipment_pct,
        SUM(CASE WHEN postcode IS NOT NULL AND postcode != '' THEN 1 ELSE 0 END) / COUNT(*) AS postcode_pct
    FROM {full_table}
""")
display(profile)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Trust scoring preview (Emergency capability)

# COMMAND ----------

# Sample trust scoring logic — mirrors src/trust_engine.py
from pyspark.sql.functions import col, lower, when, lit

facilities = spark.table(full_table.replace("`", ""))

emergency_pattern = "emergency|casualty|24x7|24/7|trauma center|accident"

scored = facilities.withColumn(
    "has_emergency_evidence",
    when(
        lower(col("capability")).rlike(emergency_pattern) |
        lower(col("procedure")).rlike(emergency_pattern) |
        lower(col("equipment")).rlike(emergency_pattern) |
        lower(col("description")).rlike(emergency_pattern),
        lit(True)
    ).otherwise(lit(False))
)

display(scored.filter(col("has_emergency_evidence")).select(
    "name", "state", "city", "capability", "description"
).limit(20))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Regional gap analysis preview

# COMMAND ----------

regional = spark.sql(f"""
    SELECT
        state,
        COUNT(*) AS facility_count,
        SUM(CASE WHEN LOWER(capability) LIKE '%emergency%'
                  OR LOWER(description) LIKE '%emergency%'
                  OR LOWER(procedure) LIKE '%emergency%' THEN 1 ELSE 0 END) AS emergency_evidence_count
    FROM {full_table}
    GROUP BY state
    ORDER BY emergency_evidence_count / facility_count ASC
""")
display(regional)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Configure the CareLenseAI app
# MAGIC
# MAGIC Set these environment variables in your Databricks App (`app.yaml`):
# MAGIC
# MAGIC ```
# MAGIC FACILITY_CATALOG: <your catalog>
# MAGIC FACILITY_SCHEMA: <your schema>
# MAGIC FACILITY_TABLE: <your table>
# MAGIC USE_MOCK_DATA: false
# MAGIC ```
# MAGIC
# MAGIC Attach a SQL warehouse resource to the app for `DATABRICKS_WAREHOUSE_ID`.
