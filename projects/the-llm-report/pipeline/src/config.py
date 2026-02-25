"""
The LLM Report — Pipeline Configuration
Loads and validates config files from the project config directory.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Optional

import yaml

CONFIG_DIR = Path(
    os.environ.get(
        "PIPELINE_CONFIG_DIR",
        str(Path(__file__).parent.parent.parent / "config"),
    )
)


def load_sources() -> dict:
    with open(CONFIG_DIR / "sources.yaml") as f:
        return yaml.safe_load(f)


def load_budget() -> dict:
    with open(CONFIG_DIR / "budget.yaml") as f:
        return yaml.safe_load(f)


def load_editorial() -> dict:
    with open(CONFIG_DIR / "editorial.yaml") as f:
        return yaml.safe_load(f)


def get_budget_caps() -> dict[str, float]:
    budget = load_budget()
    caps = budget.get("caps", {})
    return {
        "per_run": float(caps.get("per_run", 15.0)),
        "per_day": float(caps.get("per_day", 20.0)),
        "per_month": float(caps.get("per_month", 200.0)),
    }
