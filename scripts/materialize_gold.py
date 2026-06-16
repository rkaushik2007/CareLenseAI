"""
Materialize Gold tables on Databricks.

Usage (local / notebook):
  export DATABRICKS_HOST=https://adb-3141834805281315.15.azuredatabricks.net
  export DATABRICKS_TOKEN=dapi...
  export DATABRICKS_WAREHOUSE_ID=...
  export GOLD_CATALOG=main
  python scripts/materialize_gold.py

Writes to: {GOLD_CATALOG}.carelense_gold.gold_geo_capability
           {GOLD_CATALOG}.carelense_gold.gold_evidence_citations
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.config import GOLD_CATALOG, GOLD_SCHEMA
from pipeline.gold_compute import (
    CITE_COLUMNS,
    GOLD_COLUMNS,
    SOURCE_CAT,
    compute_gold_tables,
)


def _sql_connect():
    from databricks import sql

    host = os.environ["DATABRICKS_HOST"].replace("https://", "").replace("http://", "").rstrip("/")
    wh = os.environ.get("DATABRICKS_WAREHOUSE_ID", "c0c32c95246fd6a9")
    return sql.connect(
        server_hostname=host,
        http_path=f"/sql/1.0/warehouses/{wh}",
        access_token=os.environ["DATABRICKS_TOKEN"],
    )


def _fetch_df(conn, query: str):
    import pandas as pd

    with conn.cursor() as cur:
        cur.execute(query)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    return __import__("pandas").DataFrame(rows, columns=cols)


def _sql_literal(val) -> str:
    import math
    import pandas as pd

    if val is None or (isinstance(val, float) and (math.isnan(val) or pd.isna(val))):
        return "NULL"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float)):
        return str(val)
    s = str(val).replace("'", "''")
    return f"'{s}'"


def write_gold_spark(spark, gold_df, cite_df, catalog: str | None = None) -> str:
    """Preferred write path when running inside Databricks (notebook/job)."""
    catalog = catalog or os.environ.get("GOLD_CATALOG", GOLD_CATALOG)
    fq = f"`{catalog}`.`{GOLD_SCHEMA}`"

    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {fq}")

    g = gold_df[GOLD_COLUMNS] if not gold_df.empty else gold_df
    c = cite_df[CITE_COLUMNS] if not cite_df.empty else cite_df

    (
        spark.createDataFrame(g)
        .write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(f"{catalog}.{GOLD_SCHEMA}.gold_geo_capability")
    )
    (
        spark.createDataFrame(c)
        .write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(f"{catalog}.{GOLD_SCHEMA}.gold_evidence_citations")
    )

    n = spark.table(f"{catalog}.{GOLD_SCHEMA}.gold_geo_capability").count()
    print(f"Spark write complete: {catalog}.{GOLD_SCHEMA}.gold_geo_capability ({n} rows)")
    return catalog


def write_gold_sql(conn, gold_df, cite_df, catalog: str | None = None) -> str:
    """Fallback write via SQL warehouse INSERT batches."""
    import pandas as pd

    catalog = catalog or os.environ.get("GOLD_CATALOG", GOLD_CATALOG)
    fq = f"`{catalog}`.`{GOLD_SCHEMA}`"

    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {fq}")

    def _write_table(df: pd.DataFrame, table: str, columns: list[str], ddl: str):
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {fq}.{table}")
            cur.execute(f"CREATE TABLE {fq}.{table} ({ddl}) USING DELTA")

        if df.empty:
            print(f"  Warning: {table} is empty — table created with 0 rows")
            return

        subset = df[columns]
        for i in range(0, len(subset), 200):
            batch = subset.iloc[i:i + 200]
            values_sql = []
            for _, row in batch.iterrows():
                vals = ", ".join(_sql_literal(row[c]) for c in columns)
                values_sql.append(f"({vals})")
            sql = f"INSERT INTO {fq}.{table} ({', '.join(columns)}) VALUES " + ", ".join(values_sql)
            with conn.cursor() as cur:
                cur.execute(sql)

    gold_ddl = """
        grain STRING, unit_key STRING, unit_name STRING, sub STRING, capability STRING,
        risk INT, confidence INT, verdict STRING, n_facilities INT,
        strong_count INT, partial_count INT, weak_count INT,
        supply_index DOUBLE, need_index DOUBLE, need_signal_strength STRING,
        nfhs_matched BOOLEAN, need_drivers STRING, priority DOUBLE, supply_raw DOUBLE
    """
    cite_ddl = """
        grain STRING, unit_key STRING, capability STRING, facility_name STRING,
        matched_span STRING, tier STRING, source_field STRING, rec_id STRING, source_url STRING
    """

    _write_table(gold_df, "gold_geo_capability", GOLD_COLUMNS, gold_ddl)
    _write_table(cite_df, "gold_evidence_citations", CITE_COLUMNS, cite_ddl)

    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {fq}.gold_geo_capability")
        n = cur.fetchone()[0]
    print(f"SQL write complete: {catalog}.{GOLD_SCHEMA}.gold_geo_capability ({n} rows)")
    return catalog


def load_source_data(conn):
    return (
        _fetch_df(conn, f"SELECT * FROM {SOURCE_CAT}.facilities "
                  "WHERE address_countryCode = 'IN' OR lower(countries) LIKE '%india%'"),
        _fetch_df(conn, f"SELECT * FROM {SOURCE_CAT}.india_post_pincode_directory"),
        _fetch_df(conn, f"SELECT * FROM {SOURCE_CAT}.nfhs_5_district_health_indicators"),
    )


def main(use_spark: bool = False, spark=None):
    catalog = os.environ.get("GOLD_CATALOG", GOLD_CATALOG)
    print(f"Target catalog: {catalog}.{GOLD_SCHEMA}")

    if use_spark and spark is not None:
        facilities = spark.table(f"{SOURCE_CAT}.facilities").filter(
            "address_countryCode = 'IN' OR lower(countries) LIKE '%india%'"
        ).toPandas()
        pincodes = spark.table(f"{SOURCE_CAT}.india_post_pincode_directory").toPandas()
        nfhs = spark.table(f"{SOURCE_CAT}.nfhs_5_district_health_indicators").toPandas()
    else:
        conn = _sql_connect()
        facilities, pincodes, nfhs = load_source_data(conn)

    print(f"Loaded {len(facilities)} facilities, {len(pincodes)} pincodes, {len(nfhs)} NFHS districts")
    gold_df, cite_df = compute_gold_tables(facilities, pincodes, nfhs)
    print(f"Computed {len(gold_df)} gold rows, {len(cite_df)} citations")

    if use_spark and spark is not None:
        write_gold_spark(spark, gold_df, cite_df, catalog)
    else:
        write_gold_sql(conn, gold_df, cite_df, catalog)
        conn.close()

    print(f"\nVerify with:")
    print(f"  SELECT COUNT(*) FROM {catalog}.{GOLD_SCHEMA}.gold_geo_capability;")


if __name__ == "__main__":
    main()
