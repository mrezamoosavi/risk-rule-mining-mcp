"""Database access. DuckDB by default; Postgres support comes later (task 0.5)."""

from __future__ import annotations

from pathlib import Path

import duckdb

from risk_rule_mining import config


def connect(path: Path | None = None, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    path = path or config.db_path()
    if not read_only:
        path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path), read_only=read_only)


def quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'
