"""Home Credit Default Risk: download and load into the local database.

Source: https://www.kaggle.com/competitions/home-credit-default-risk
License: Kaggle competition rules. You must accept them on Kaggle once. The data may be
used for research and model development but must not be redistributed, so this repo
ships this script, never the data.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from risk_rule_mining.db import quote

COMPETITION = "home-credit-default-risk"
COMPETITION_URL = f"https://www.kaggle.com/competitions/{COMPETITION}"
RULES_URL = f"{COMPETITION_URL}/rules"
TOKEN_URL = "https://www.kaggle.com/settings"

QUICK_MODULUS = 20  # quick mode keeps roughly 1 applicant in 20


@dataclass(frozen=True)
class Table:
    name: str
    files: tuple[str, ...]
    primary_key: str | None = None
    foreign_keys: dict[str, tuple[str, str]] = field(default_factory=dict)


APP = ("application", "SK_ID_CURR")
PREV = ("previous_application", "SK_ID_PREV")

# Parents before children: foreign keys are checked on insert.
TABLES: tuple[Table, ...] = (
    Table("application", ("application_train.csv", "application_test.csv"), "SK_ID_CURR"),
    Table("bureau", ("bureau.csv",), "SK_ID_BUREAU", {"SK_ID_CURR": APP}),
    Table(
        "bureau_balance",
        ("bureau_balance.csv",),
        None,
        {"SK_ID_BUREAU": ("bureau", "SK_ID_BUREAU")},
    ),
    Table("previous_application", ("previous_application.csv",), "SK_ID_PREV", {"SK_ID_CURR": APP}),
    Table(
        "pos_cash_balance", ("POS_CASH_balance.csv",), None, {"SK_ID_PREV": PREV, "SK_ID_CURR": APP}
    ),
    Table(
        "credit_card_balance",
        ("credit_card_balance.csv",),
        None,
        {"SK_ID_PREV": PREV, "SK_ID_CURR": APP},
    ),
    Table(
        "installments_payments",
        ("installments_payments.csv",),
        None,
        {"SK_ID_PREV": PREV, "SK_ID_CURR": APP},
    ),
)
DESCRIPTION_FILE = "HomeCredit_columns_description.csv"
EXPECTED_FILES = tuple(f for t in TABLES for f in t.files) + (DESCRIPTION_FILE,)


class SetupError(RuntimeError):
    """A problem the user can fix. The message says how."""


# ---------------------------------------------------------------- download


def _has_kaggle_credentials() -> bool:
    if os.environ.get("KAGGLE_API_TOKEN"):
        return True
    if os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        return True
    config_dir = Path(os.environ.get("KAGGLE_CONFIG_DIR", Path.home() / ".kaggle"))
    return (config_dir / "kaggle.json").exists() or (config_dir / "access_token").exists()


def _kaggle_command() -> list[str]:
    beside_python = Path(sys.executable).parent / "kaggle"
    if beside_python.exists():
        return [str(beside_python)]
    found = shutil.which("kaggle")
    if found:
        return [found]
    raise SetupError("The kaggle command was not found. Run `uv sync` first.")


def missing_files(raw: Path) -> list[str]:
    return [f for f in EXPECTED_FILES if not (raw / f).exists()]


def download(raw: Path) -> str:
    """Make sure the CSVs are in `raw`. Returns a one-line summary."""
    raw.mkdir(parents=True, exist_ok=True)
    if not missing_files(raw):
        return f"Home Credit files already present in {raw}"

    archive = raw / f"{COMPETITION}.zip"
    if not archive.exists():
        if not _has_kaggle_credentials():
            raise SetupError(
                "No Kaggle API credentials found.\n"
                f"  1. Sign in at {TOKEN_URL} and create an API token.\n"
                "  2. Save it as ~/.kaggle/kaggle.json (or set KAGGLE_USERNAME and KAGGLE_KEY).\n"
                f"  3. Accept the competition rules once: {RULES_URL}\n"
                f"Or download the zip by hand from {COMPETITION_URL} and put it in {raw}"
            )
        cmd = _kaggle_command() + ["competitions", "download", "-c", COMPETITION, "-p", str(raw)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = f"{result.stdout}\n{result.stderr}"
        if result.returncode != 0 or not archive.exists():
            if "403" in output or "rules" in output.lower():
                raise SetupError(
                    "Kaggle refused the download. Accept the competition rules once at "
                    f"{RULES_URL} (signed in as the same account), then run this again."
                )
            if "401" in output:
                raise SetupError(
                    f"Kaggle rejected your API token. Create a new one at {TOKEN_URL}."
                )
            raise SetupError(f"Kaggle download failed:\n{output.strip()}")

    with zipfile.ZipFile(archive) as zf:
        zf.extractall(raw)
    still_missing = missing_files(raw)
    if still_missing:
        raise SetupError(f"Archive extracted but files are missing: {', '.join(still_missing)}")
    return f"Downloaded and extracted Home Credit into {raw}"


# ---------------------------------------------------------------- load


def _csv(path: Path, **options: str) -> str:
    extra = "".join(f", {k}={v}" for k, v in options.items())
    literal = str(path).replace("'", "''")
    return f"read_csv('{literal}', header=true, sample_size=-1{extra})"


def _source_sql(table: Table, raw: Path, quick: bool) -> str:
    if table.name == "application":
        train, test = (raw / f for f in table.files)
        sql = (
            f"SELECT *, 'train' AS split FROM {_csv(train)} "
            f"UNION ALL BY NAME SELECT *, 'test' AS split FROM {_csv(test)}"
        )
        if quick:
            sql = f"SELECT * FROM ({sql}) WHERE hash(SK_ID_CURR) % {QUICK_MODULUS} = 0"
        return sql
    return f"SELECT * FROM {_csv(raw / table.files[0])}"


def _create_sql(table: Table, columns: list[tuple[str, str]]) -> str:
    parts = [f"{quote(name)} {dtype}" for name, dtype in columns]
    if table.primary_key:
        parts.append(f"PRIMARY KEY ({quote(table.primary_key)})")
    for col, (parent, parent_col) in table.foreign_keys.items():
        parts.append(f"FOREIGN KEY ({quote(col)}) REFERENCES {parent} ({quote(parent_col)})")
    return f"CREATE TABLE {table.name} (\n  " + ",\n  ".join(parts) + "\n)"


def load(con: duckdb.DuckDBPyConnection, raw: Path, quick: bool = False) -> list[dict]:
    """Load all tables with keys. Child rows whose parent is missing are skipped and counted.

    Returns one report dict per table: rows read, rows loaded, rows skipped.
    """
    missing = missing_files(raw)
    if missing:
        raise SetupError(
            f"Missing files in {raw}: {', '.join(missing)}. Run `rrm download credit` first."
        )

    for table in reversed(TABLES):
        con.execute(f"DROP TABLE IF EXISTS {table.name}")
    con.execute("DROP TABLE IF EXISTS column_description")

    report = []
    for table in TABLES:
        con.execute(f"CREATE OR REPLACE TEMP TABLE _stage AS {_source_sql(table, raw, quick)}")
        columns = [(r[0], r[1]) for r in con.execute("DESCRIBE _stage").fetchall()]
        con.execute(_create_sql(table, columns))

        conditions = [
            f"(s.{quote(col)} IS NULL OR s.{quote(col)} IN (SELECT {quote(pcol)} FROM {parent}))"
            for col, (parent, pcol) in table.foreign_keys.items()
        ]
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        con.execute(f"INSERT INTO {table.name} SELECT s.* FROM _stage s{where}")

        read = con.execute("SELECT count(*) FROM _stage").fetchone()[0]
        loaded = con.execute(f"SELECT count(*) FROM {table.name}").fetchone()[0]
        report.append(
            {
                "table": table.name,
                "rows_read": read,
                "rows_loaded": loaded,
                "rows_skipped": read - loaded,
            }
        )
    con.execute("DROP TABLE IF EXISTS _stage")

    con.execute(
        "CREATE TABLE column_description AS SELECT * FROM "
        + _csv(raw / DESCRIPTION_FILE, encoding="'latin-1'", all_varchar="true")
    )
    return report


def status(con: duckdb.DuckDBPyConnection) -> list[dict]:
    existing = {r[0] for r in con.execute("SELECT table_name FROM duckdb_tables()").fetchall()}
    rows = []
    for table in TABLES:
        count = (
            con.execute(f"SELECT count(*) FROM {table.name}").fetchone()[0]
            if table.name in existing
            else None
        )
        rows.append({"table": table.name, "rows": count})
    return rows
