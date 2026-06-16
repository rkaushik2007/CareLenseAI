"""Pipeline configuration — NFHS need mapping and UC paths."""

import os

CATALOG = "databricks_virtue_foundation_dataset_dais_2026"
SCHEMA = "virtue_foundation_dataset"
GOLD_CATALOG = os.getenv("GOLD_CATALOG", "main")
GOLD_SCHEMA = "carelense_gold"

FACILITIES = f"{CATALOG}.{SCHEMA}.facilities"
PINCODES = f"{CATALOG}.{SCHEMA}.india_post_pincode_directory"
NFHS = f"{CATALOG}.{SCHEMA}.nfhs_5_district_health_indicators"

# NFHS column → direction. lower_is_worse: low % = more need; higher_is_worse: high % = more need
NEED_MAP = {
    "maternity": {
        "signal_strength": "strong",
        "indicators": [
            ("institutional_birth_5y_pct", "lower_is_worse"),
            ("institutional_birth_in_public_facility_5y_pct", "lower_is_worse"),
            ("mothers_who_had_at_least_4_anc_visits_lb5y_pct", "lower_is_worse"),
            ("births_attended_by_skilled_hp_5y_10_pct", "lower_is_worse"),
            ("average_out_of_pocket_expenditure_per_delivery_in_a_public_fac", "higher_is_worse"),
        ],
    },
    "nicu": {
        "signal_strength": "strong",
        "indicators": [
            ("institutional_birth_in_public_facility_5y_pct", "lower_is_worse"),
            ("mothers_whose_last_birth_was_protected_against_neo_tetanus_pct", "lower_is_worse"),
            ("children_who_received_pnc_from_a_doctor_nurse_lhv_anm_midwi_pct", "lower_is_worse"),
        ],
    },
    "oncology": {
        "signal_strength": "moderate",
        "indicators": [
            ("women_age_30_49_years_ever_undergone_a_cervical_screen_pct", "lower_is_worse"),
            ("women_age_30_49_years_ever_undergone_a_breast_exam_pct", "lower_is_worse"),
            ("women_age_30_49_years_ever_undergone_an_oral_cancer_exam_pct", "lower_is_worse"),
            ("w15_plus_who_use_any_kind_of_tobacco_pct", "higher_is_worse"),
            ("m15_plus_who_use_any_kind_of_tobacco_pct", "higher_is_worse"),
            ("w15_plus_who_consume_alcohol_pct", "higher_is_worse"),
            ("m15_plus_who_consume_alcohol_pct", "higher_is_worse"),
        ],
    },
    "dialysis": {
        "signal_strength": "moderate",
        "indicators": [
            ("w15_plus_with_high_or_very_high_gt_140_mg_dl_blood_sugar_or_pct", "higher_is_worse"),
            ("m15_plus_with_high_or_very_high_gt_140_mg_dl_blood_sugar_or_pct", "higher_is_worse"),
            ("w15_plus_with_high_bp_sys_gte_140_mmhg_and_or_dia_gte_90_mm_pct", "higher_is_worse"),
            ("m15_plus_with_high_bp_sys_gte_140_mmhg_and_or_dia_gte_90_mm_pct", "higher_is_worse"),
        ],
    },
    "emergency": {
        "signal_strength": "weak",
        "indicators": [
            ("children_with_fever_or_symptoms_of_ari_2wk_taken_to_a_healt_pct", "lower_is_worse"),
            ("children_with_diarrhoea_2wk_taken_to_a_health_facility_or_h_pct", "lower_is_worse"),
        ],
    },
    "icu": {
        "signal_strength": "weak",
        "indicators": [
            ("w15_plus_with_high_or_very_high_gt_140_mg_dl_blood_sugar_or_pct", "higher_is_worse"),
            ("m15_plus_with_high_or_very_high_gt_140_mg_dl_blood_sugar_or_pct", "higher_is_worse"),
            ("w15_plus_with_high_bp_sys_gte_140_mmhg_and_or_dia_gte_90_mm_pct", "higher_is_worse"),
            ("m15_plus_with_high_bp_sys_gte_140_mmhg_and_or_dia_gte_90_mm_pct", "higher_is_worse"),
        ],
    },
    "trauma": {
        "signal_strength": "none",
        "indicators": [],
    },
}

STRUCTURED_FIELDS = ["capability", "procedure", "equipment", "specialties"]
ALL_EVIDENCE_FIELDS = ["capability", "procedure", "equipment", "specialties", "description"]
FIELD_PRIORITY = ["capability", "procedure", "equipment", "specialties", "description"]

TIER_WEIGHTS = {"strong": 1.0, "partial": 0.5, "weak": 0.15}

CONFIDENCE_WEIGHTS = {
    "evidence_strength": 0.35,
    "meta_credibility": 0.25,
    "need_data_density": 0.20,
    "n_facilities": 0.10,
    "capability_signal": 0.10,
}

SIGNAL_STRENGTH_SCORES = {"strong": 100, "moderate": 70, "weak": 40, "none": 15}
