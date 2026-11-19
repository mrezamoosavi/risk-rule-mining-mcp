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


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
