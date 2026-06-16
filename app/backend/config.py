"""Backend configuration from environment."""

from __future__ import annotations

import os
def settings():
    # No cross-workspace default: wrong warehouse ID breaks SQL on other workspaces.
    warehouse_id = (
        os.getenv("DATABRICKS_WAREHOUSE_ID")
        or os.getenv("WAREHOUSE_ID")
        or ""
    )
    return {
        "warehouse_id": warehouse_id,
        "gold_catalog": os.getenv("GOLD_CATALOG", "main"),
        "gold_schema": os.getenv("GOLD_SCHEMA", "carelense_gold"),
        "source_catalog": os.getenv(
            "FACILITY_CATALOG", "databricks_virtue_foundation_dataset_dais_2026"
        ),
        "source_schema": os.getenv("FACILITY_SCHEMA", "virtue_foundation_dataset"),
        "source_table": os.getenv("FACILITY_TABLE", "facilities"),
        "genie_space_id": os.getenv("GENIE_SPACE_ID", ""),
        "agent_endpoint": os.getenv("AGENT_ENDPOINT", ""),
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "openai_base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "cache_ttl": int(os.getenv("GOLD_CACHE_TTL", "300")),
        "frontend_dir": os.getenv(
            "FRONTEND_DIR",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "out"),
        ),
    }
