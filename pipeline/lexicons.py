"""Capability lexicons — word-boundary matching against facility text fields."""

LEXICONS = {
    "icu": [
        "icu", "intensive care", "ventilator", "critical care",
        "multipara monitor", "hdu", "high dependency",
    ],
    "maternity": [
        "maternity", "labour room", "labor room", "c-section", "caesarean",
        "cesarean", "obstetric", "antenatal", "delivery", "ob/gyn",
        "gynaec", "lscs",
    ],
    "emergency": [
        "emergency", "casualty", "trauma triage", "ambulance", "24x7", "24/7",
        "round-the-clock", "accident & emergency", "a&e",
    ],
    "oncology": [
        "oncology", "cancer", "chemotherapy", "chemo", "radiotherapy",
        "palliative", "tumor", "tumour", "oncologist",
    ],
    "trauma": [
        "trauma", "orthopaedic", "orthopedic", "fracture", "accident wing",
        "ortho", "trauma centre", "trauma center",
    ],
    "nicu": [
        "nicu", "neonatal", "newborn care", "sncu", "phototherapy",
        "warmer", "neonatal ventilation",
    ],
    "dialysis": [
        "dialysis", "haemodialysis", "hemodialysis", "nephrology", "renal",
        "pmndp", "kidney",
    ],
}

CAPABILITIES = [
    {"id": "icu", "label": "ICU", "dot": "#d23f2d"},
    {"id": "maternity", "label": "Maternity", "dot": "#7c4dd6"},
    {"id": "emergency", "label": "Emergency", "dot": "#e0732b"},
    {"id": "oncology", "label": "Oncology", "dot": "#2f9e6b"},
    {"id": "trauma", "label": "Trauma", "dot": "#d6452f"},
    {"id": "nicu", "label": "NICU", "dot": "#3d8bd6"},
    {"id": "dialysis", "label": "Dialysis", "dot": "#1f9e9e"},
]

VERDICT_THRESHOLD = 58

PRIORITY_WEIGHTS = {
    "desert": 2.1,
    "blind": 1.5,
    "served": 0.7,
    "unknown": 1.0,
}
