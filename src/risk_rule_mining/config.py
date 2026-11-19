"""Paths and settings. Everything can be overridden with environment variables."""

from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    """Root folder for downloaded data and the local database. Never committed."""
    return Path(os.environ.get("RRM_DATA_DIR", "data")).expanduser().resolve()


def raw_dir(domain: str) -> Path:
    return data_dir() / "raw" / domain


def db_path() -> Path:
    """DuckDB file used by the loaders and the MCP server."""
    default = data_dir() / "rrm.duckdb"
    return Path(os.environ.get("RRM_DB", default)).expanduser().resolve()
