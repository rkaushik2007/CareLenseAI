"""Load workspace deployment settings from deploy.config.yaml with env-var fallback."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "deploy.config.yaml"

_ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _resolve_env_refs(value: str) -> str:
    if not isinstance(value, str):
        return value

    def repl(match: re.Match[str]) -> str:
        return os.environ.get(match.group(1), "")

    return _ENV_REF.sub(repl, value)


def _cfg_value(data: dict, key: str, env_key: str, default: str = "") -> str:
    raw = data.get(key)
    if raw is None or raw == "":
        return os.environ.get(env_key, default)
    return _resolve_env_refs(str(raw))


@dataclass
class DeployConfig:
    databricks_host: str
    databricks_token: str
    warehouse_id: str
    catalog: str
    gold_schema: str
    workspace_base: str
    app_name: str
    genie_space_id: str = ""
    openai_api_key: str = ""

    def apply_to_env(self) -> None:
        """Export config to os.environ for scripts that read env vars directly."""
        os.environ["DATABRICKS_HOST"] = self.databricks_host
        os.environ["DATABRICKS_TOKEN"] = self.databricks_token
        os.environ["DATABRICKS_WAREHOUSE_ID"] = self.warehouse_id
        os.environ["GOLD_CATALOG"] = self.catalog
        os.environ["GOLD_SCHEMA"] = self.gold_schema
        os.environ["DATABRICKS_APP_PATH"] = self.workspace_base
        if self.genie_space_id:
            os.environ["GENIE_SPACE_ID"] = self.genie_space_id
        if self.openai_api_key:
            os.environ["OPENAI_API_KEY"] = self.openai_api_key


def load_deploy_config(config_path: Path | str | None = None) -> DeployConfig:
    """Load deploy config from YAML file, falling back to environment variables."""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    data: dict = {}

    if path.is_file():
        with path.open(encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"{path} must contain a YAML mapping at the top level")
        data = loaded

    cfg = DeployConfig(
        databricks_host=_cfg_value(data, "databricks_host", "DATABRICKS_HOST"),
        databricks_token=_cfg_value(data, "databricks_token", "DATABRICKS_TOKEN"),
        warehouse_id=_cfg_value(data, "warehouse_id", "DATABRICKS_WAREHOUSE_ID"),
        catalog=_cfg_value(data, "catalog", "GOLD_CATALOG", "main"),
        gold_schema=_cfg_value(data, "gold_schema", "GOLD_SCHEMA", "carelense_gold"),
        workspace_base=_cfg_value(data, "workspace_base", "DATABRICKS_APP_PATH"),
        app_name=_cfg_value(data, "app_name", "DATABRICKS_APP_NAME", "carelenseai"),
        genie_space_id=_cfg_value(data, "genie_space_id", "GENIE_SPACE_ID"),
        openai_api_key=_cfg_value(data, "openai_api_key", "OPENAI_API_KEY"),
    )

    missing = []
    if not cfg.databricks_host:
        missing.append("databricks_host (or DATABRICKS_HOST)")
    if not cfg.databricks_token:
        missing.append("databricks_token (or DATABRICKS_TOKEN)")
    if not cfg.warehouse_id:
        missing.append("warehouse_id (or DATABRICKS_WAREHOUSE_ID)")
    if not cfg.workspace_base:
        missing.append("workspace_base (or DATABRICKS_APP_PATH)")
    if missing:
        raise ValueError(
            "Missing required deploy settings: "
            + ", ".join(missing)
            + f". Copy deploy.config.example.yaml to {path.name} and fill in values."
        )

    return cfg
