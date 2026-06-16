# Databricks notebook source
# MAGIC %md
# MAGIC # CareLenseAI — Data Readiness Report
# MAGIC Surfaces pipeline quality metrics for judges (Track 4 bonus).

# COMMAND ----------

catalog = "main"

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   COUNT(*) AS total_facilities,
# MAGIC   SUM(CASE WHEN geo_resolved THEN 1 ELSE 0 END) / COUNT(*) AS pct_geo_resolved,
# MAGIC   SUM(CASE WHEN geo_source = 'state_only' THEN 1 ELSE 0 END) AS state_only_count
# MAGIC FROM main.carelense_silver.silver_facility

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   COUNT(DISTINCT district_canonical) AS districts,
# MAGIC   SUM(CASE WHEN nfhs_matched THEN 1 ELSE 0 END) / COUNT(*) AS pct_nfhs_matched
# MAGIC FROM main.carelense_silver.silver_geo_dim

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT capability, tier, COUNT(*) AS n
# MAGIC FROM main.carelense_silver.silver_facility_capability_evidence
# MAGIC GROUP BY capability, tier
# MAGIC ORDER BY capability, tier

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   SUM(CASE WHEN description IS NOT NULL AND description != '' THEN 1 ELSE 0 END) / COUNT(*) AS description_pct,
# MAGIC   SUM(CASE WHEN capability IS NOT NULL AND capability != '' THEN 1 ELSE 0 END) / COUNT(*) AS capability_pct,
# MAGIC   SUM(CASE WHEN equipment IS NOT NULL AND equipment != '' THEN 1 ELSE 0 END) / COUNT(*) AS equipment_pct,
# MAGIC   SUM(CASE WHEN numberDoctors IS NOT NULL AND numberDoctors != '' THEN 1 ELSE 0 END) / COUNT(*) AS doctors_pct
# MAGIC FROM databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.facilities
# MAGIC WHERE address_countryCode = 'IN' OR lower(countries) LIKE '%india%'

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT cluster_id, COUNT(*) AS dup_count
# MAGIC FROM databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.facilities
# MAGIC GROUP BY cluster_id
# MAGIC HAVING COUNT(*) > 1
# MAGIC ORDER BY dup_count DESC
# MAGIC LIMIT 10
