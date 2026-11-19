"""Profiling and metadata: what each table and column is, how complete it is, how tables join.

`build_metadata` writes three tables into the database so Claude (and people) can query them:

- meta_tables:        one row per table: description, grain, rows, columns, primary key
- meta_columns:       one row per column: role, description, type, nulls, ranges, top values
- meta_relationships: one row per key: hard or soft, rows matched, parent coverage
"""

from __future__ import annotations

import json
import re

import duckdb

from risk_rule_mining.datasets import credit
from risk_rule_mining.db import quote

ROLE_RULES: tuple[tuple[str, str], ...] = (
    (r"^SK_ID_", "id"),
    (r"^TARGET$", "target"),
    (r"^split$", "split"),
    (r"^(DAYS|MONTHS)_", "time_offset"),
    (r"^(AMT|AMOUNT)_", "amount"),
    (r"^(FLAG|REG_|LIVE_)", "flag"),
    (r"^(CNT|NUM|OBS|DEF)_", "count"),
    (r"^(EXT_SOURCE|RATE)_", "score_or_rate"),
)


def column_role(name: str, dtype: str) -> str:
    for pattern, role in ROLE_RULES:
        if re.search(pattern, name):
            return role
    return "category" if dtype.upper().startswith("VARCHAR") else "numeric"


def _descriptions(con: duckdb.DuckDBPyConnection) -> dict[tuple[str, str], str]:
    """Kaggle's column descriptions keyed by (table, column), plus (None, column) fallbacks."""
    exists = con.execute(
        "SELECT count(*) FROM duckdb_tables() WHERE table_name = 'column_description'"
    ).fetchone()[0]
    if not exists:
        return {}
    out: dict[tuple[str | None, str], str] = {}
    for source, column, text in con.execute(
        'SELECT "Table", "Row", "Description" FROM column_description'
    ).fetchall():
        if not column or not text:
            continue
        table = credit.FILE_TO_TABLE.get((source or "").strip())
        out[(table, column.strip())] = text.strip()
        out.setdefault((None, column.strip()), text.strip())
    return out


def profile_table(con: duckdb.DuckDBPyConnection, table: str, top_n: int = 5) -> list[dict]:
    """Per-column profile using DuckDB's SUMMARIZE plus top values for text columns."""
    rows = con.execute(f"SUMMARIZE {quote(table)}").fetchall()
    cols = [d[0] for d in con.description]
    descriptions = _descriptions(con)
    profile = []
    for raw in rows:
        r = dict(zip(cols, raw, strict=True))
        name, dtype = r["column_name"], r["column_type"]
        entry = {
            "column": name,
            "type": dtype,
            "role": column_role(name, dtype),
            "description": descriptions.get((table, name)) or descriptions.get((None, name)),
            "rows": int(r["count"]),
            "null_pct": round(float(r["null_percentage"] or 0), 2),
            "approx_distinct": int(r["approx_unique"] or 0),
            "min": r["min"],
            "max": r["max"],
            "mean": None if r["avg"] is None else round(float(r["avg"]), 4),
            "p50": r["q50"],
            "top_values": None,
        }
        if entry["role"] == "category" or (0 < entry["approx_distinct"] <= 12):
            top = con.execute(
                f"SELECT {quote(name)}::VARCHAR, count(*) n FROM {quote(table)} "
                f"GROUP BY 1 ORDER BY n DESC LIMIT {top_n}"
            ).fetchall()
            entry["top_values"] = [{"value": v, "rows": n} for v, n in top]
        profile.append(entry)
    return profile


def relationships(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Every declared key, hard or soft: row match rate and parent coverage."""
    out = []
    for table in credit.TABLES:
        keys = [(c, p, "hard") for c, p in table.foreign_keys.items()]
        keys += [(c, p, "soft") for c, p in table.soft_keys.items()]
        for col, (parent, pcol), kind in keys:
            rows, matched, parents_with_children = con.execute(
                f"""
                SELECT count(*), count(p.k),
                       (SELECT count(DISTINCT {quote(col)}) FROM {table.name}
                        WHERE {quote(col)} IN (SELECT {quote(pcol)} FROM {parent}))
                FROM {table.name} c
                LEFT JOIN (SELECT DISTINCT {quote(pcol)} AS k FROM {parent}) p
                  ON c.{quote(col)} = p.k
                """
            ).fetchone()
            parents = con.execute(f"SELECT count(*) FROM {parent}").fetchone()[0]
            out.append(
                {
                    "child_table": table.name,
                    "child_column": col,
                    "parent_table": parent,
                    "parent_column": pcol,
                    "kind": kind,
                    "child_rows": rows,
                    "rows_matched": matched,
                    "rows_unmatched": rows - matched,
                    "row_match_pct": round(100 * matched / rows, 2) if rows else None,
                    "parents_with_children_pct": (
                        round(100 * parents_with_children / parents, 2) if parents else None
                    ),
                }
            )
    return out


def build_metadata(con: duckdb.DuckDBPyConnection) -> dict:
    """Profile every credit table and write meta_tables, meta_columns, meta_relationships."""
    existing = {r[0] for r in con.execute("SELECT table_name FROM duckdb_tables()").fetchall()}
    tables, columns = [], []
    for t in credit.TABLES:
        if t.name not in existing:
            continue
        prof = profile_table(con, t.name)
        info = credit.TABLE_INFO[t.name]
        tables.append(
            {
                "table": t.name,
                "description": info["description"],
                "grain": info["grain"],
                "rows": prof[0]["rows"] if prof else 0,
                "columns": len(prof),
                "primary_key": t.primary_key,
            }
        )
        for c in prof:
            columns.append({"table": t.name, **c})
    rels = relationships(con)

    con.execute(
        "CREATE OR REPLACE TABLE meta_tables (tbl VARCHAR, description VARCHAR, grain VARCHAR, "
        "rows BIGINT, columns INTEGER, primary_key VARCHAR)"
    )
    con.executemany(
        "INSERT INTO meta_tables VALUES (?, ?, ?, ?, ?, ?)",
        [list(t.values()) for t in tables],
    )
    con.execute(
        "CREATE OR REPLACE TABLE meta_columns (tbl VARCHAR, col VARCHAR, type VARCHAR, "
        "role VARCHAR, description VARCHAR, rows BIGINT, null_pct DOUBLE, approx_distinct BIGINT, "
        "min VARCHAR, max VARCHAR, mean DOUBLE, p50 VARCHAR, top_values VARCHAR)"
    )
    con.executemany(
        "INSERT INTO meta_columns VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            [
                c["table"],
                c["column"],
                c["type"],
                c["role"],
                c["description"],
                c["rows"],
                c["null_pct"],
                c["approx_distinct"],
                None if c["min"] is None else str(c["min"]),
                None if c["max"] is None else str(c["max"]),
                c["mean"],
                None if c["p50"] is None else str(c["p50"]),
                None if c["top_values"] is None else json.dumps(c["top_values"]),
            ]
            for c in columns
        ],
    )
    con.execute(
        "CREATE OR REPLACE TABLE meta_relationships (child_table VARCHAR, child_column VARCHAR, "
        "parent_table VARCHAR, parent_column VARCHAR, kind VARCHAR, child_rows BIGINT, "
        "rows_matched BIGINT, rows_unmatched BIGINT, row_match_pct DOUBLE, "
        "parents_with_children_pct DOUBLE)"
    )
    con.executemany(
        "INSERT INTO meta_relationships VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [list(r.values()) for r in rels],
    )
    return {"tables": tables, "columns": columns, "relationships": rels}


def data_dictionary_markdown(meta: dict) -> str:
    """A readable data dictionary from build_metadata's output."""
    lines = [
        "# Home Credit data dictionary",
        "",
        "Generated by `rrm profile credit`. Figures come from the loaded database.",
        "",
        "## Tables",
        "",
        "| Table | Grain | Rows | Columns | Primary key | Description |",
        "|---|---|---:|---:|---|---|",
    ]
    for t in meta["tables"]:
        lines.append(
            f"| `{t['table']}` | {t['grain']} | {t['rows']:,} | {t['columns']} | "
            f"{t['primary_key'] or '-'} | {t['description']} |"
        )
    lines += [
        "",
        "## Relationships",
        "",
        "Hard keys are enforced (orphan rows skipped at load). Soft keys are kept and "
        "measured, because the source data does not fully honour them.",
        "",
        "| Child | Parent | Kind | Rows matched | Parents with children |",
        "|---|---|---|---:|---:|",
    ]
    for r in meta["relationships"]:
        lines.append(
            f"| `{r['child_table']}.{r['child_column']}` | `{r['parent_table']}."
            f"{r['parent_column']}` | {r['kind']} | {r['row_match_pct']}% "
            f"({r['rows_unmatched']:,} unmatched) | {r['parents_with_children_pct']}% |"
        )
    for t in meta["tables"]:
        lines += [
            "",
            f"## `{t['table']}`",
            "",
            t["description"],
            "",
            "| Column | Role | Type | Null % | Distinct | Min | Max | Description |",
            "|---|---|---|---:|---:|---|---|---|",
        ]
        for c in (c for c in meta["columns"] if c["table"] == t["table"]):
            desc = (c["description"] or "").replace("|", "/")
            lines.append(
                f"| `{c['column']}` | {c['role']} | {c['type']} | {c['null_pct']} | "
                f"{c['approx_distinct']:,} | {_short(c['min'])} | {_short(c['max'])} | {desc} |"
            )
    return "\n".join(lines) + "\n"


def _short(value, width: int = 24) -> str:
    if value is None:
        return ""
    text = str(value).replace("|", "/")
    return text if len(text) <= width else text[: width - 1] + "…"
