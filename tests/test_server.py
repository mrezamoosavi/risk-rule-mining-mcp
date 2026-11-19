import pytest

from risk_rule_mining import db, server
from risk_rule_mining.datasets import credit
from risk_rule_mining.synthetic import credit_sample


@pytest.fixture()
def loaded_db(tmp_path, monkeypatch):
    path = tmp_path / "rrm.duckdb"
    raw = credit_sample.generate(tmp_path / "raw")
    with db.connect(path) as con:
        credit.load(con, raw)
    monkeypatch.setenv("RRM_DB", str(path))
    return path


def test_list_tables(loaded_db):
    tables = {t["table"] for t in server.list_tables()}
    assert {"application", "bureau", "installments_payments"} <= tables


def test_describe_table_shows_keys(loaded_db):
    info = server.describe_table("bureau")
    kinds = {k["type"] for k in info["keys"]}
    assert kinds == {"PRIMARY KEY", "FOREIGN KEY"}
    assert any(c["name"] == "SK_ID_CURR" for c in info["columns"])


def test_describe_unknown_table(loaded_db):
    with pytest.raises(ValueError, match="Unknown table"):
        server.describe_table("nope")


def test_missing_database_message(tmp_path, monkeypatch):
    monkeypatch.setenv("RRM_DB", str(tmp_path / "absent.duckdb"))
    with pytest.raises(FileNotFoundError, match="rrm demo"):
        server.list_tables()


def test_profile_table_on_the_fly(loaded_db):
    prof = {c["column"]: c for c in server.profile_table("application")}
    assert prof["SK_ID_CURR"]["role"] == "id"
    assert prof["TARGET"]["role"] == "target"
    assert prof["EXT_SOURCE_1"]["null_pct"] > 0


def test_get_metadata_after_profile(loaded_db):
    from risk_rule_mining import profiling

    with db.connect(loaded_db) as con:
        profiling.build_metadata(con)
    meta = server.get_metadata()
    assert {t["tbl"] for t in meta["tables"]} >= {"application", "bureau"}
    kinds = {r["kind"] for r in meta["relationships"]}
    assert kinds == {"hard", "soft"}
    saved = server.profile_table("bureau")
    assert any(c["col"] == "SK_ID_CURR" for c in saved)
