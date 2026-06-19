"""Programmatic Alembic runner (used on container start when RUN_MIGRATIONS_ON_START)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from captureos.config import get_settings

_API_ROOT = Path(__file__).resolve().parents[2]  # apps/api


def _alembic_config() -> Config:
    cfg = Config(str(_API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_API_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url_sync)
    return cfg


def apply_migrations() -> None:
    command.upgrade(_alembic_config(), "head")
