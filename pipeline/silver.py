"""Silver layer — geo crosswalk, facility resolution, capability evidence."""

import dlt
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, ArrayType
from pyspark.sql.window import Window

LEXICONS = {
    "icu": ["icu", "intensive care", "ventilator", "critical care", "hdu"],
    "maternity": ["maternity", "labour room", "labor room", "obstetric", "c-section", "delivery"],
    "emergency": ["emergency", "casualty", "ambulance", "24x7", "24/7", "a&e"],
    "oncology": ["oncology", "cancer", "chemotherapy", "radiotherapy", "tumor"],
    "trauma": ["trauma", "orthopaedic", "orthopedic", "fracture", "ortho"],
    "nicu": ["nicu", "neonatal", "newborn care", "sncu", "phototherapy"],
    "dialysis": ["dialysis", "hemodialysis", "haemodialysis", "nephrology", "renal"],
}

CAP_IDS = list(LEXICONS.keys())


def _cap_pattern(cap_id: str) -> str:
    terms = LEXICONS.get(cap_id, [])
    return "|".join(f"\\b{F.lit(t)}" for t in terms) if False else (
        "(?i)(" + "|".join(t.replace(" ", r"\s+") for t in terms) + ")"
    )


@dlt.table(name="silver_geo_dim", comment="PIN ↔ district ↔ NFHS crosswalk")
def silver_geo_dim():
    pins = dlt.read("bronze_pincodes").select(
        F.col("pincode").cast("string").alias("pincode"),
        F.col("district"),
        F.col("statename").alias("state_canonical"),
        F.col("latitude"),
        F.col("longitude"),
    ).distinct().withColumn(
        "pin3", F.lpad(F.substring("pincode", 1, 3), 3, "0")
    ).withColumn(
        "pin_district_key",
        F.regexp_replace(F.regexp_replace(F.lower(F.trim("district")), "district", ""), "[^a-z]", ""),
    )

    nfhs = dlt.read("bronze_nfhs").select(
        F.col("district_name"),
        F.col("state_ut"),
        F.col("households_surveyed").cast("double"),
    ).distinct().withColumn(
        "nfhs_district_key",
        F.regexp_replace(F.regexp_replace(F.lower(F.trim("district_name")), "district", ""), "[^a-z]", ""),
    ).withColumn(
        "nfhs_state_key",
        F.regexp_replace(F.lower(F.trim("state_ut")), "[^a-z]", ""),
    )

    joined = pins.join(
        nfhs,
        (pins.pin_district_key == nfhs.nfhs_district_key)
        & (F.regexp_replace(F.lower(pins.state_canonical), "[^a-z]", "") == nfhs.nfhs_state_key),
        "left",
    )

    return joined.groupBy(
        F.col("district").alias("district_canonical"),
        F.col("state_canonical"),
    ).agg(
        F.first("pincode").alias("sample_pincode"),
        F.first("pin3").alias("pin3"),
        F.first("latitude").alias("latitude"),
        F.first("longitude").alias("longitude"),
        F.max(F.when(F.col("district_name").isNotNull(), F.lit(1)).otherwise(F.lit(0))).alias("nfhs_matched_int"),
        F.max("households_surveyed").alias("households_surveyed"),
    ).withColumn("nfhs_matched", F.col("nfhs_matched_int") == 1).drop("nfhs_matched_int")


@dlt.table(name="silver_facility", comment="Primary facilities with resolved geography")
def silver_facility():
    fac = dlt.read("bronze_facilities").filter(F.col("is_cluster_primary") == True)
    pins = dlt.read("bronze_pincodes").select(
        F.col("pincode").cast("string").alias("pincode"),
        F.col("district").alias("pin_district"),
        F.col("statename").alias("pin_state"),
    ).distinct()

    clean_pin = F.regexp_extract(F.col("address_zipOrPostcode").cast("string"), r"(\d{6})", 1)
    fac2 = fac.withColumn("pin_clean", clean_pin)
    resolved = fac2.join(pins, fac2["pin_clean"] == pins["pincode"], "left").select(
        fac["*"],
        F.col("pin_district").alias("district_resolved"),
        F.coalesce(F.col("pin_state"), F.col("address_stateOrRegion")).alias("state_resolved"),
        F.when(F.length(clean_pin) == 6, F.lpad(F.substring(clean_pin, 1, 3), 3, "0")).alias("pin3"),
        F.when(F.col("pin_district").isNotNull(), F.lit(True)).otherwise(F.lit(False)).alias("geo_resolved"),
        F.when(F.col("pin_district").isNotNull(), F.lit("pincode")).otherwise(F.lit("state_only")).alias("geo_source"),
    )
    return resolved


@dlt.table(name="silver_facility_capability_evidence", comment="Facility × capability evidence tiers")
@dlt.expect_or_drop("has_span", "matched_span IS NOT NULL AND matched_span != ''")
def silver_facility_capability_evidence():
    fac = dlt.read("silver_facility")
    parts = []

    for cap_id, terms in LEXICONS.items():
        pattern = "(?i)(" + "|".join(t.replace(" ", r"\\s+") for t in terms) + ")"
        hit_cap = F.when(F.col("capability").rlike(pattern), F.lit("capability"))
        hit_proc = F.when(F.col("procedure").rlike(pattern), F.lit("procedure"))
        hit_equip = F.when(F.col("equipment").rlike(pattern), F.lit("equipment"))
        hit_spec = F.when(F.col("specialties").rlike(pattern), F.lit("specialties"))
        hit_desc = F.when(F.col("description").rlike(pattern), F.lit("description"))

        structured_count = (
            F.when(hit_cap.isNotNull(), 1).otherwise(0)
            + F.when(hit_proc.isNotNull(), 1).otherwise(0)
            + F.when(hit_equip.isNotNull(), 1).otherwise(0)
            + F.when(hit_spec.isNotNull(), 1).otherwise(0)
        )
        has_desc_only = (
            hit_desc.isNotNull()
            & hit_cap.isNull()
            & hit_proc.isNull()
            & hit_equip.isNull()
            & hit_spec.isNull()
        )
        tier = (
            F.when(structured_count >= 2, F.lit("strong"))
            .when(structured_count == 1, F.lit("partial"))
            .when(has_desc_only, F.lit("weak"))
            .otherwise(F.lit("none"))
        )
        source_field = F.coalesce(hit_cap, hit_proc, hit_equip, hit_spec, hit_desc)
        matched_span = F.substring(
            F.coalesce(
                F.col("capability"),
                F.col("procedure"),
                F.col("equipment"),
                F.col("specialties"),
                F.col("description"),
            ),
            1,
            160,
        )

        parts.append(
            fac.withColumn("capability", F.lit(cap_id))
            .withColumn("tier", tier)
            .withColumn("source_field", source_field)
            .withColumn("matched_span", matched_span)
            .withColumn("rec_id", F.col("unique_id"))
            .filter(F.col("tier") != "none")
            .select(
                "rec_id", "name", "capability", "tier", "matched_span", "source_field",
                "district_resolved", "state_resolved", "pin3", "geo_resolved",
                "description", "source_urls",
            )
        )

    out = parts[0]
    for part in parts[1:]:
        out = out.unionByName(part)
    return out
