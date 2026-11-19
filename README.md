# Risk Rule Mining MCP

> Mine interpretable risk rules from relational financial data, with Claude as the interface.

[![CI](https://github.com/mrezamoosavi/risk-rule-mining-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/mrezamoosavi/risk-rule-mining-mcp/actions/workflows/ci.yml)
![status](https://img.shields.io/badge/status-early%20development-orange)
![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.11%2B-blue)

An open-source [Model Context Protocol](https://modelcontextprotocol.io) server that searches relational data for simple, explainable rules (alpha-mining style), scores them honestly, and reports what they are worth. One shared rule engine, four risk domains.

**Status:** early development. The data layer for credit works today; rule mining tools land use case by use case. Sections marked _TODO_ fill in as the [roadmap](#roadmap) progresses.

---

## Why

Risk teams live on rules: they are auditable, explainable to regulators, and cheap to run. Finding good ones is still mostly manual. This project automates the search, then holds every rule to the same bar: out-of-time validation, minimum support, stability over time, and a dollar estimate of impact.

## Design principles

- **Runs fully local.** No hosting, no cloud services, no custom UI. Claude (or any MCP client) is the interface.
- **Relational first.** Sits on a real relational database with primary and foreign keys. DuckDB by default, so no Docker is needed; Postgres optional.
- **Interpretable by construction.** Output is rules a person can read, not a black-box score.
- **Honest scoring.** Capture rate, false positive rate, lift and precision, always on out-of-time data.
- **Every module earns its keep.** Each use case ships an insights dashboard and an ROI estimate.
- **Clean-room, public data only.** See [Data](#data).

## Domains and use cases

| # | Domain | Use case | Public data | ROI type |
|---|---|---|---|---|
| 1 | Credit | Four use cases, below | Home Credit Default Risk (7 relational tables) | Loss reduction, revenue, capital |
| 2 | Treasury | Reverse stress testing: find the combinations of rate moves, deposit outflow and funding spread that breach liquidity or NII limits | Synthetic balance sheet + Bank of Canada yield curves | Profit and capital efficiency |
| 3 | AML | Transaction-monitoring scenario tuning: typology rules (fan-in, fan-out, gather-scatter, layering) with thresholds tuned to cut false alerts | IBM AMLworld | Fewer false alerts, analyst hours saved |
| 4 | Derivatives | Futures positioning early warning: positioning patterns that come before large moves in CAD, crude and Canadian rates | CFTC Commitments of Traders + Bank of Canada | Risk avoided, hedging cost |

### Credit use cases

1. **Thin-file underwriting.** Rules from alternative data for applicants that bureau scores serve poorly: newcomers, young borrowers, the self-employed.
2. **Credit limit management.** Rules for line increases and decreases, with simulated revenue and loss impact.
3. **IFRS 9 staging and overlays.** Explain what drives significant-increase-in-credit-risk staging and tie management overlays to scenarios.
4. **Vendor data profiling and signal requirements.** Profile a new vendor data feed and manage the signals required from it.

_TODO: detail and tools for each as it is built._

## Architecture

```
┌──────────────┐     MCP      ┌──────────────────────────────────────────┐
│   Claude /   │ ◄──────────► │  MCP server                              │
│  MCP client  │              │  shared tools + use-case tools           │
└──────────────┘              ├──────────────────────────────────────────┤
                              │  Use-case modules                        │
                              │  labels · features · ROI logic           │
                              ├──────────────────────────────────────────┤
                              │  Shared rule engine                      │
                              │  single conditions → combinations →      │
                              │  expression search                       │
                              │  scoring · out-of-time · stability       │
                              ├──────────────────────────────────────────┤
                              │  Data layer                              │
                              │  download scripts · loaders with PK/FK   │
                              │  DuckDB (default) | Postgres (optional)  │
                              └──────────────────────────────────────────┘
```

## MCP tools

| Tool | Status | What it does |
|---|---|---|
| `list_tables` | available | Loaded tables with row and column counts |
| `describe_table` | available | Columns, types, primary and foreign keys |
| `profile_table` | planned | Nulls, distributions and join coverage |
| `mine_rules` | planned | Search for candidate rules against a target |
| `backtest_rule` | planned | Score a rule out of time |
| `explain_rule` | planned | Plain-language explanation of a rule |
| `estimate_roi` | planned | Dollar impact of a rule or rule set |
| `build_dashboard` | planned | Self-contained HTML insights dashboard |

Use-case tools are added as each use case is built.

## Quickstart

Needs [uv](https://docs.astral.sh/uv/). No Docker, no database server.

```bash
git clone https://github.com/mrezamoosavi/risk-rule-mining-mcp.git
cd risk-rule-mining-mcp
uv sync

# Try it in seconds on synthetic sample data (no account, no download)
uv run rrm demo
uv run rrm status

# Real data: needs a Kaggle account, see Data below
uv run rrm setup credit            # full data, about 2.5 GB
uv run rrm setup credit --quick    # about 1 applicant in 20, faster
```

Data and the database live in `./data` (ignored by git). Set `RRM_DATA_DIR` to put them elsewhere.

### Connect to Claude Desktop

Add this to `claude_desktop_config.json` (Claude Desktop → Settings → Developer → Edit Config), using absolute paths. Use the full path to `uv` (`which uv`), since Claude Desktop may not see your shell's PATH.

```json
{
  "mcpServers": {
    "risk-rule-mining": {
      "command": "/full/path/to/uv",
      "args": ["--directory", "/full/path/to/risk-rule-mining-mcp", "run", "rrm-server"],
      "env": { "RRM_DATA_DIR": "/full/path/to/risk-rule-mining-mcp/data" }
    }
  }
}
```

Restart Claude Desktop, then ask: _"What tables are loaded, and how are they related?"_

## Data

No data is committed to this repository. Each domain has one command that downloads it from the original source, loads it with keys, and reports what it loaded.

| Domain | Dataset | Source | License | Size | Command |
|---|---|---|---|---|---|
| Credit | Home Credit Default Risk | [Kaggle competition](https://www.kaggle.com/competitions/home-credit-default-risk) | Kaggle competition rules: use for research and modelling, no redistribution | ~2.5 GB unzipped | `rrm setup credit` |
| Treasury | Synthetic balance sheet + yield curves | Generated by this repo + [Bank of Canada](https://www.bankofcanada.ca/rates/interest-rates/) | MIT (generated) / Bank of Canada terms | small | _TODO_ |
| AML | IBM AMLworld | [Kaggle dataset](https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml) | CDLA-Sharing-1.0 | small variants: hundreds of MB | _TODO_ |
| Derivatives | Commitments of Traders | [CFTC](https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm) + Bank of Canada | US government public data / Bank of Canada terms | small | _TODO_ |

**Kaggle setup (credit and AML), once:**

1. Create a free account and an API token at [kaggle.com/settings](https://www.kaggle.com/settings). Save it as `~/.kaggle/kaggle.json`, or set `KAGGLE_USERNAME` and `KAGGLE_KEY`.
2. For credit, accept the [competition rules](https://www.kaggle.com/competitions/home-credit-default-risk/rules) with the same account.

If something is missing, `rrm setup` says exactly which step to do. You can also download the zip by hand and drop it in `data/raw/credit/`.

**How credit loads.** `application_train` and `application_test` become one `application` table with a `split` column (TARGET is empty for test). Primary keys: `application`, `bureau`, `previous_application`. Every child table has foreign keys to its parents. Child rows whose parent doesn't exist are skipped and counted in the load report, never silently dropped.

**Caveats shown on every dashboard.** Home Credit has no calendar dates (days relative to the application) and is not Canadian, so ROI is calibrated to Canadian aggregates (Equifax, TransUnion, OSB). The treasury balance sheet is synthetic. CFTC data is weekly.

**Clean-room build.** All code, rules, features and assumptions come from public sources only. Nothing comes from any employer's code, rules, models or data.

## Development

```bash
uv sync
uv run pytest            # runs on synthetic data generated at test time
uv run ruff check .
```

CI runs lint, tests and a CLI smoke test on Linux and macOS for every push.

## Roadmap

- [ ] **0. Foundation:** repo, uv project, MCP skeleton, CI, DuckDB, credit download and load _(in progress)_
- [ ] **1. Credit:** thin-file underwriting, limit management, IFRS 9 staging, vendor data profiling
- [ ] **2. Treasury:** synthetic balance sheet, yield curves, reverse stress testing
- [ ] **3. AML:** AMLworld load, network features, scenario tuning, alert reduction ROI
- [ ] **4. Derivatives:** CFTC positioning, Bank of Canada context, early-warning rules

## Results

_TODO: headline findings and dashboards per use case._

## Contributing

Issues and suggestions are welcome. This is a personal portfolio project, so larger pull requests are best discussed in an issue first.

## License

[MIT](LICENSE) © 2026 Mohamad Reza Moosavi
