from risk_rule_mining import db, profiling
from risk_rule_mining.datasets import credit
from risk_rule_mining.synthetic import credit_sample


def test_build_metadata_and_dictionary(tmp_path):
    raw = credit_sample.generate(tmp_path / "raw", orphans=3)
    with db.connect(tmp_path / "t.duckdb") as con:
        credit.load(con, raw)
        meta = profiling.build_metadata(con)
        assert con.execute("SELECT count(*) FROM meta_tables").fetchone()[0] == 7
        assert con.execute("SELECT count(*) FROM meta_columns").fetchone()[0] > 30
    rel = {(r["child_table"], r["child_column"]): r for r in meta["relationships"]}
    assert rel[("bureau_balance", "SK_ID_BUREAU")]["rows_unmatched"] == 3
    assert rel[("bureau", "SK_ID_CURR")]["row_match_pct"] == 100.0
    desc = {(c["table"], c["column"]): c["description"] for c in meta["columns"]}
    assert desc[("application", "TARGET")].startswith("Target variable")
    md = profiling.data_dictionary_markdown(meta)
    assert "## Relationships" in md and "`application`" in md


def test_roles():
    assert profiling.column_role("DAYS_BIRTH", "BIGINT") == "time_offset"
    assert profiling.column_role("AMT_CREDIT", "DOUBLE") == "amount"
    assert profiling.column_role("NAME_CONTRACT_TYPE", "VARCHAR") == "category"
