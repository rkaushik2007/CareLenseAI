#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from databricks import sql

host = os.environ["DATABRICKS_HOST"].replace("https://", "").rstrip("/")
conn = sql.connect(
    server_hostname=host,
    http_path=f"/sql/1.0/warehouses/{os.environ['DATABRICKS_WAREHOUSE_ID']}",
    access_token=os.environ["DATABRICKS_TOKEN"],
)
cur = conn.cursor()
catalog = os.environ.get("GOLD_CATALOG", "main")
cur.execute(f"SELECT COUNT(*) FROM {catalog}.carelense_gold.gold_geo_capability")
print("gold_geo_capability:", cur.fetchone()[0])
cur.execute(f"SELECT COUNT(*) FROM {catalog}.carelense_gold.gold_evidence_citations")
print("gold_evidence_citations:", cur.fetchone()[0])
cur.execute("""
    SELECT capability, verdict, COUNT(*) AS n
    FROM workspace.carelense_gold.gold_geo_capability
    WHERE grain = 'state'
    GROUP BY capability, verdict ORDER BY 1, 2
""")
for r in cur.fetchall():
    print(" ", r)
conn.close()
