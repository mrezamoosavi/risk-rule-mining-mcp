from pathlib import Path

import duckdb
import pytest

from risk_rule_mining import db
from risk_rule_mining.datasets import credit
from risk_rule_mining.synthetic import credit_sample


@pytest.fixture()
def raw(tmp_path: Path) -> Path:
    return credit_sample.generate(tmp_path / "raw", n_applicants=300, orphans=3)


@pytest.fixture()
def con(tmp_path: Path):
    with db.connect(tmp_path / "test.duckdb") as connection:
        yield connection


def test_generator_writes_every_expected_file(raw: Path):
    assert credit.missing_files(raw) == []


def test_load_creates_all_tables_with_rows(con, raw):
    report = {r["table"]: r for r in credit.load(con, raw)}
    assert set(report) == {t.name for t in credit.TABLES}
    assert report["application"]["rows_loaded"] == 300
    assert all(r["rows_loaded"] > 0 for r in report.values())


def test_orphans_are_skipped_and_counted(con, raw):
    report = {r["table"]: r for r in credit.load(con, raw)}
    # Hard keys (to application) skip orphans
    assert report["bureau"]["rows_skipped"] == 3
    assert report["previous_application"]["rows_skipped"] == 3
    assert report["application"]["rows_skipped"] == 0
    # Soft keys keep every row
    assert report["bureau_balance"]["rows_skipped"] == 0


def test_soft_key_coverage_counts_unmatched(con, raw):
    credit.load(con, raw)
    cov = {(r["table"], r["column"]): r for r in credit.soft_key_coverage(con)}
    assert cov[("bureau_balance", "SK_ID_BUREAU")]["unmatched"] == 3
    assert cov[("installments_payments", "SK_ID_PREV")]["unmatched"] == 0


def test_description_file_in_windows_1252_loads(con, raw):
    path = raw / credit.DESCRIPTION_FILE
    path.write_bytes(
        path.read_bytes().replace(b"payment difficulties", b"payment difficulties\x85")
    )
    credit.load(con, raw)
    text = " ".join(
        r[0] for r in con.execute("SELECT Description FROM column_description").fetchall()
    )
    assert "\u2026" in text


def test_train_and_test_are_combined_with_split_flag(con, raw):
    credit.load(con, raw)
    splits = dict(con.execute("SELECT split, count(*) FROM application GROUP BY split").fetchall())
    assert splits == {"train": 240, "test": 60}
    assert (
        con.execute(
            "SELECT count(*) FROM application WHERE split = 'test' AND TARGET IS NOT NULL"
        ).fetchone()[0]
        == 0
    )


def test_keys_are_declared(con, raw):
    credit.load(con, raw)
    pks = {
        r[0]
        for r in con.execute(
            "SELECT table_name FROM duckdb_constraints() WHERE constraint_type = 'PRIMARY KEY'"
        ).fetchall()
    }
    assert pks == {"application", "bureau", "previous_application"}
    fk_count = con.execute(
        "SELECT count(*) FROM duckdb_constraints() WHERE constraint_type = 'FOREIGN KEY'"
    ).fetchone()[0]
    assert fk_count == sum(len(t.foreign_keys) for t in credit.TABLES)


def test_foreign_keys_reject_orphans_after_load(con, raw):
    credit.load(con, raw)
    with pytest.raises(duckdb.ConstraintException):
        con.execute("INSERT INTO bureau (SK_ID_CURR, SK_ID_BUREAU) VALUES (1, 1)")


def test_quick_mode_loads_a_subset(con, raw):
    report = {r["table"]: r for r in credit.load(con, raw, quick=True)}
    assert 0 < report["application"]["rows_loaded"] < 300


def test_reload_replaces_tables(con, raw):
    credit.load(con, raw)
    report = {r["table"]: r for r in credit.load(con, raw)}
    assert report["application"]["rows_loaded"] == 300


def test_missing_files_give_a_helpful_error(con, tmp_path):
    with pytest.raises(credit.SetupError, match="rrm download credit"):
        credit.load(con, tmp_path / "empty")


def test_download_without_credentials_explains_setup(tmp_path, monkeypatch):
    for var in ("KAGGLE_API_TOKEN", "KAGGLE_USERNAME", "KAGGLE_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("KAGGLE_CONFIG_DIR", str(tmp_path / "no-kaggle"))
    with pytest.raises(credit.SetupError, match="rules"):
        credit.download(tmp_path / "raw")


def test_download_skips_when_files_present(raw):
    assert "already present" in credit.download(raw)
