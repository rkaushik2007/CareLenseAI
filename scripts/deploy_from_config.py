#!/usr/bin/env python3
"""Deploy CareLenseAI using deploy.config.yaml (or env-var fallback)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.deploy_config import ROOT as CONFIG_ROOT
from scripts.deploy_config import load_deploy_config


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deploy CareLenseAI to a Databricks workspace from deploy.config.yaml"
    )
    parser.add_argument(
        "--config",
        default=str(CONFIG_ROOT / "deploy.config.yaml"),
        help="Path to deploy config YAML (default: deploy.config.yaml at repo root)",
    )
    parser.add_argument(
        "--hotfix",
        action="store_true",
        help="Upload only hotfix backend files and redeploy (fast path)",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_file():
        example = CONFIG_ROOT / "deploy.config.example.yaml"
        print(f"Config not found: {config_path}")
        print(f"Copy {example.name} to {config_path.name} and fill in your workspace values.")
        return 1

    cfg = load_deploy_config(config_path)
    cfg.apply_to_env()

    print(f"Workspace : {cfg.databricks_host}")
    print(f"App path  : {cfg.workspace_base}")
    print(f"App name  : {cfg.app_name}")
    print(f"Catalog   : {cfg.catalog}.{cfg.gold_schema}")
    print(f"Warehouse : {cfg.warehouse_id}")
    print(f"Mode      : {'hotfix' if args.hotfix else 'full'}")
    print()

    if args.hotfix:
        from scripts.deploy_hotfix import main as hotfix_main

        return hotfix_main(cfg)
    from scripts.deploy_databricks import main as deploy_main

    return deploy_main(cfg)


if __name__ == "__main__":
    sys.exit(main())
