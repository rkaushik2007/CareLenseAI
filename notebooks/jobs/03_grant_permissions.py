# Databricks notebook source
# MAGIC %md
# MAGIC # CareLenseAI — Grant Permissions
# MAGIC Grants the app service principal access to Gold/Silver schemas and hackathon dataset.

# COMMAND ----------

APP_SP = "d4e46205-b7d2-4626-a4bb-4ffea79965c8"  # carelenseai premium workspace SP
CATALOG = "main"

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Grant app service principal SELECT on Gold tables
# MAGIC GRANT USE SCHEMA ON SCHEMA main.carelense_gold TO `d4e46205-b7d2-4626-a4bb-4ffea79965c8`;
# MAGIC GRANT SELECT ON SCHEMA main.carelense_gold TO `d4e46205-b7d2-4626-a4bb-4ffea79965c8`;

# COMMAND ----------

# MAGIC %sql
# MAGIC GRANT USE SCHEMA ON SCHEMA main.carelense_silver TO `d4e46205-b7d2-4626-a4bb-4ffea79965c8`;
# MAGIC GRANT SELECT ON SCHEMA main.carelense_silver TO `d4e46205-b7d2-4626-a4bb-4ffea79965c8`;

# COMMAND ----------

# MAGIC %sql
# MAGIC GRANT USE CATALOG ON CATALOG databricks_virtue_foundation_dataset_dais_2026 TO `d4e46205-b7d2-4626-a4bb-4ffea79965c8`;
# MAGIC GRANT USE SCHEMA ON SCHEMA databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset TO `d4e46205-b7d2-4626-a4bb-4ffea79965c8`;
# MAGIC GRANT SELECT ON SCHEMA databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset TO `d4e46205-b7d2-4626-a4bb-4ffea79965c8`;

# COMMAND ----------

print("Permissions granted on main.carelense_gold / main.carelense_silver.")
