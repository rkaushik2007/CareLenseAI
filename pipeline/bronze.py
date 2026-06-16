"""Bronze layer — typed snapshots from hackathon UC tables."""

import dlt
from pyspark.sql import functions as F


@dlt.table(
    name="bronze_facilities",
    comment="India healthcare facilities — raw snapshot with cluster primary flag",
)
@dlt.expect("has_id", "unique_id IS NOT NULL")
@dlt.expect("has_name", "name IS NOT NULL")
def bronze_facilities():
    df = (
        spark.table("databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.facilities")
        .filter(
            (F.col("address_countryCode") == "IN")
            | F.lower(F.col("countries")).contains("india")
        )
        .withColumn("ingest_ts", F.current_timestamp())
    )

    from pyspark.sql.window import Window

    w = Window.partitionBy("cluster_id").orderBy(
        F.col("recency_of_page_update").desc_nulls_last(),
        F.col("number_of_facts_about_the_organization").cast("int").desc_nulls_last(),
    )
    ranked = df.withColumn("_rn", F.row_number().over(w))
    return ranked.withColumn("is_cluster_primary", F.col("_rn") == 1).drop("_rn")


@dlt.table(name="bronze_pincodes", comment="India PIN directory with typed coordinates")
def bronze_pincodes():
    return (
        spark.table("databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.india_post_pincode_directory")
        .withColumn("latitude", F.col("latitude").cast("double"))
        .withColumn("longitude", F.col("longitude").cast("double"))
        .withColumn("ingest_ts", F.current_timestamp())
    )


@dlt.table(name="bronze_nfhs", comment="NFHS-5 district health indicators")
def bronze_nfhs():
    return (
        spark.table("databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset.nfhs_5_district_health_indicators")
        .withColumn("ingest_ts", F.current_timestamp())
    )
