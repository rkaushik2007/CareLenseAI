"""Geo crosswalk — PIN directory ↔ NFHS district matching."""

from pyspark.sql import functions as F
from pyspark.sql.types import StringType


def normalize_geo_key(col):
    """Strip 'district' and non-alpha chars for fuzzy join keys."""
    return F.regexp_replace(
        F.regexp_replace(F.lower(F.trim(col)), "district", ""),
        "[^a-z]",
        "",
    )


def build_silver_geo_dim(bronze_pincodes, bronze_nfhs):
    """Build canonical district dimension with NFHS match flag."""
    pins = (
        bronze_pincodes.select(
            F.col("pincode").cast("string").alias("pincode"),
            F.col("district"),
            F.col("statename"),
            F.col("latitude"),
            F.col("longitude"),
        )
        .distinct()
        .withColumn("pin3", F.lpad(F.substring(F.col("pincode"), 1, 3), 3, "0"))
        .withColumn("pin_district_key", normalize_geo_key(F.col("district")))
        .withColumn("pin_state_key", normalize_geo_key(F.col("statename")))
    )

    nfhs = (
        bronze_nfhs.select(
            F.col("district_name"),
            F.col("state_ut"),
            F.col("households_surveyed").cast("double"),
        )
        .distinct()
        .withColumn("nfhs_district_key", normalize_geo_key(F.col("district_name")))
        .withColumn("nfhs_state_key", normalize_geo_key(F.col("state_ut")))
    )

    # Exact normalized key join first
    joined = pins.join(
        nfhs,
        (pins.pin_district_key == nfhs.nfhs_district_key)
        & (pins.pin_state_key == nfhs.nfhs_state_key),
        "left",
    )

    geo = joined.groupBy(
        F.col("district").alias("district_canonical"),
        F.col("statename").alias("state_canonical"),
    ).agg(
        F.first("pincode").alias("sample_pincode"),
        F.first("pin3").alias("pin3"),
        F.first("latitude").alias("latitude"),
        F.first("longitude").alias("longitude"),
        F.max(F.when(F.col("district_name").isNotNull(), F.lit(1)).otherwise(F.lit(0))).alias("nfhs_matched"),
        F.max("households_surveyed").alias("households_surveyed"),
    )

    return geo.withColumn("nfhs_matched", F.col("nfhs_matched") == 1)
