#!/usr/bin/env python3
import os
from databricks import sql

host = os.environ["DATABRICKS_HOST"].replace("https://", "").rstrip("/")
wh = os.environ.get("DATABRICKS_WAREHOUSE_ID", "c0c32c95246fd6a9")
conn = sql.connect(
    server_hostname=host,
    http_path=f"/sql/1.0/warehouses/{wh}",
    access_token=os.environ["DATABRICKS_TOKEN"],
)
with conn.cursor() as cur:
    cur.execute(
        """
        SELECT table_catalog, table_schema, table_name
        FROM system.information_schema.tables
        WHERE lower(table_name) LIKE '%facilit%'
           OR lower(table_name) LIKE '%nfhs%'
           OR lower(table_name) LIKE '%pincode%'
        LIMIT 50
        """
    )
    rows = cur.fetchall()
    print(f"Found {len(rows)} tables:")
    for row in rows:
        print(row)

    cur.execute("SHOW CATALOGS")
    print("\nAll catalogs:")
    for row in cur.fetchall():
        print(row[0])
conn.close()
