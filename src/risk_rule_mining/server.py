"""MCP server. Skeleton: lets Claude see what data is loaded.

Rule mining tools land as each credit use case is built.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from risk_rule_mining import config, db

mcp = MCPServer("risk-rule-mining")


def _connect():
    path = config.db_path()
    if not path.exists():
        raise FileNotFoundError(
            f"No database at {path}. Run `rrm setup credit` (real data) or `rrm demo` (sample)."
        )
    return db.connect(read_only=True)


@mcp.tool()
def list_tables() -> list[dict]:
    """List loaded tables with row and column counts."""
    with _connect() as con:
        rows = con.execute(
            "SELECT table_name, estimated_size, column_count FROM duckdb_tables() "
            "ORDER BY table_name"
        ).fetchall()
    return [{"table": t, "rows": n, "columns": c} for t, n, c in rows]


@mcp.tool()
def describe_table(table: str) -> dict:
    """Columns, types, primary key and foreign keys of one table."""
    with _connect() as con:
        known = {r[0] for r in con.execute("SELECT table_name FROM duckdb_tables()").fetchall()}
        if table not in known:
            raise ValueError(f"Unknown table {table!r}. Known: {', '.join(sorted(known))}")
        columns = con.execute(
            "SELECT column_name, data_type FROM duckdb_columns() WHERE table_name = ? "
            "ORDER BY column_index",
            [table],
        ).fetchall()
        constraints = con.execute(
            "SELECT constraint_type, constraint_column_names, referenced_table "
            "FROM duckdb_constraints() WHERE table_name = ? "
            "AND constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')",
            [table],
        ).fetchall()
    return {
        "table": table,
        "columns": [{"name": n, "type": t} for n, t in columns],
        "keys": [{"type": k, "columns": cols, "references": ref} for k, cols, ref in constraints],
    }


@mcp.tool()
def profile_table(table: str) -> list[dict]:
    """Column-by-column profile: role, description, nulls, distinct values, ranges, top values.

    Reads saved metadata when `rrm profile` has been run, otherwise profiles on the fly.
    """
    from risk_rule_mining import profiling

    with _connect() as con:
        known = {r[0] for r in con.execute("SELECT table_name FROM duckdb_tables()").fetchall()}
        if table not in known:
            raise ValueError(f"Unknown table {table!r}. Known: {', '.join(sorted(known))}")
        if "meta_columns" in known:
            rows = con.execute(
                "SELECT * FROM meta_columns WHERE tbl = ? ORDER BY rowid", [table]
            ).fetchall()
            if rows:
                cols = [d[0] for d in con.description]
                return [dict(zip(cols, r, strict=True)) for r in rows]
        return profiling.profile_table(con, table)


@mcp.tool()
def get_metadata() -> dict:
    """What each table is (description, grain, size, key) and how tables relate, with coverage."""
    with _connect() as con:
        known = {r[0] for r in con.execute("SELECT table_name FROM duckdb_tables()").fetchall()}
        if "meta_tables" not in known:
            raise FileNotFoundError("No metadata yet. Run `rrm profile credit` first.")
        out = {}
        for name in ("meta_tables", "meta_relationships"):
            rows = con.execute(f"SELECT * FROM {name}").fetchall()
            cols = [d[0] for d in con.description]
            out[name.removeprefix("meta_")] = [dict(zip(cols, r, strict=True)) for r in rows]
        return out


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
