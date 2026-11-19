# Risk Rule Mining MCP

> Mine interpretable risk rules from relational financial data, with Claude as the interface.

![status](https://img.shields.io/badge/status-early%20development-orange)
![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.11%2B-blue)

An open-source [Model Context Protocol](https://modelcontextprotocol.io) server that searches relational data for simple, explainable rules (alpha-mining style), scores them honestly, and reports what they are worth. One shared rule engine, four risk domains.

**Status:** early development. Nothing below is runnable yet; sections marked _TODO_ fill in as the roadmap progresses.

---

## Why

Risk teams live on rules: they are auditable, explainable to regulators, and cheap to run. Finding good ones is still mostly manual. This project automates the search, then holds every rule to the same bar: out-of-time validation, minimum support, stability over time, and a dollar estimate of impact.

## Design principles

- **Runs fully local.** No hosting, no cloud services, no custom UI. Claude (or any MCP client) is the interface.
- **Relational first.** Sits on a real relational database (Postgres, with a DuckDB fallback for laptops without Docker).
- **Interpretable by construction.** Output is rules a person can read, not a black-box score.
- **Honest scoring.** Capture rate, false positive rate, lift and precision, always on out-of-time data.
- **Every module earns its keep.** Each domain ships an insights dashboard and an ROI estimate.
- **Clean-room, public data only.** See [Data policy](#data-policy).

## Domains

| # | Domain | Public data | Core problem | ROI type |
|---|---|---|---|---|
| 1 | Credit early warning | Home Credit Default Risk (7 relational tables) | Flag existing borrowers heading into trouble from repayment behaviour | Loss reduction |
| 2 | Treasury stress testing | Synthetic bank balance sheet + Canadian yield curves | Rate and liquidity stress, including non-maturity deposit behaviour | Profit and capital efficiency |
| 3 | AML | IBM AMLworld | Multi-account laundering patterns (fan-in, fan-out, gather-scatter, layering) | Fewer false alerts, analyst hours saved |
| 4 | Derivatives | DTCC Canada public OTC trade data | Off-market pricing and unusual size without counterparty identity | Surveillance cost, mispricing losses |

Built in that order. Credit comes first because it has the richest public relational data.

## Architecture

```
┌──────────────┐     MCP      ┌──────────────────────────────────────────┐
│   Claude /   │ ◄──────────► │  MCP server                              │
│  MCP client  │              │  profile_table · mine_rules ·            │
└──────────────┘              │  backtest_rule · explain_rule ·          │
                              │  estimate_roi · run_stress_test ·        │
                              │  build_dashboard                         │
                              ├──────────────────────────────────────────┤
                              │  Domain modules                          │
                              │  labels · features · ROI logic           │
                              ├──────────────────────────────────────────┤
                              │  Shared rule engine                      │
                              │  single conditions → combinations →      │
                              │  expression search                       │
                              │  scoring · out-of-time · stability       │
                              ├──────────────────────────────────────────┤
                              │  Data layer                              │
                              │  download scripts · loaders with PK/FK   │
                              │  Postgres  |  DuckDB fallback            │
                              └──────────────────────────────────────────┘
```

## MCP tools

| Tool | What it does |
|---|---|
| `profile_table` | Nulls, distributions and join coverage for a table |
| `mine_rules` | Search for candidate rules against a target |
| `backtest_rule` | Score a rule out of time |
| `explain_rule` | Plain-language explanation of a rule and its drivers |
| `estimate_roi` | Dollar impact of a rule or rule set |
| `run_stress_test` | Scenario analysis (treasury) |
| `build_dashboard` | Generate the insights dashboard for a module |

_TODO: signatures and examples as each tool lands._

## Quickstart

_TODO (tasks 0.4 to 0.6)._ The intended flow:

```bash
git clone https://github.com/mrezamoosavi/risk-rule-mining-mcp.git
cd risk-rule-mining-mcp
uv sync
docker compose up -d          # or skip Docker and use DuckDB
uv run scripts/download.py credit
uv run scripts/load.py credit
```

Then register the server with your MCP client. _TODO: client config snippet._

## Data policy

- **No data is committed to this repository.** Download scripts fetch each dataset from its original source.
- **You accept each dataset's license** when you download it. Links and license notes live with each script.
- **Clean-room build.** All code, rules, features and assumptions are developed from public sources only. Nothing comes from any employer's code, rules, models or data.

## Roadmap

- [ ] **0. Foundation:** repo, uv project, MCP skeleton, CI, local Postgres and DuckDB, download scripts
- [ ] **1. Credit early warning:** data load, label and out-of-time split, rule engine v1, scoring and guards, expression search, ROI, MCP tools, dashboard
- [ ] **2. Treasury stress testing:** synthetic balance sheet, Canadian yield curves, rate and liquidity shocks, deposit behaviour, triggers
- [ ] **3. AML:** AMLworld load, network features, network-aware rules, alert reduction ROI
- [ ] **4. Derivatives:** DTCC Canada ingest, fair-value reference, off-market and unusual size rules

## Results

_TODO: headline findings and dashboards per domain._

## Contributing

Issues and suggestions are welcome. This is a personal portfolio project, so larger pull requests are best discussed in an issue first.

## License

[MIT](LICENSE) © 2026 Mohamad Reza Moosavi
