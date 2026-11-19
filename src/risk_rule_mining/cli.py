"""Command line: `rrm setup credit` downloads, loads and checks in one go."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from risk_rule_mining import config, db
from risk_rule_mining.datasets import credit

DOMAINS = {"credit": credit}


def _print_report(report: list[dict]) -> None:
    print(f"{'table':<24}{'read':>12}{'loaded':>12}{'skipped':>10}")
    for r in report:
        print(
            f"{r['table']:<24}{r['rows_read']:>12,}{r['rows_loaded']:>12,}{r['rows_skipped']:>10,}"
        )


def cmd_download(args: argparse.Namespace) -> None:
    print(DOMAINS[args.domain].download(config.raw_dir(args.domain)))


def cmd_load(args: argparse.Namespace) -> None:
    raw = Path(args.raw) if args.raw else config.raw_dir(args.domain)
    with db.connect() as con:
        report = DOMAINS[args.domain].load(con, raw, quick=args.quick)
    _print_report(report)
    if args.quick:
        print("Quick mode: about 1 applicant in 20, so child rows outside the sample are skipped.")
    print(f"Database: {config.db_path()}")


def cmd_setup(args: argparse.Namespace) -> None:
    cmd_download(args)
    cmd_load(args)


def cmd_demo(args: argparse.Namespace) -> None:
    """Load synthetic sample data: no download, no account. For a first look and for CI."""
    from risk_rule_mining.synthetic import credit_sample

    with tempfile.TemporaryDirectory() as tmp:
        raw = credit_sample.generate(Path(tmp))
        with db.connect() as con:
            report = credit.load(con, raw)
    _print_report(report)
    print(f"Synthetic sample loaded into {config.db_path()}")


def cmd_status(args: argparse.Namespace) -> None:
    path = config.db_path()
    if not path.exists():
        print(f"No database yet at {path}. Run `rrm setup credit` or `rrm demo`.")
        return
    with db.connect(read_only=True) as con:
        for row in credit.status(con):
            count = "not loaded" if row["rows"] is None else f"{row['rows']:,}"
            print(f"{row['table']:<24}{count:>14}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rrm", description="Risk Rule Mining data setup")
    sub = parser.add_subparsers(dest="command", required=True)

    for name, fn, help_text in [
        ("setup", cmd_setup, "download, load and check a domain"),
        ("download", cmd_download, "download a domain's raw files"),
        ("load", cmd_load, "load raw files into the database"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("domain", choices=sorted(DOMAINS))
        p.add_argument("--quick", action="store_true", help="load a ~5%% applicant subset")
        if name == "load":
            p.add_argument("--raw", help="folder holding the raw CSVs")
        p.set_defaults(func=fn)

    sub.add_parser("demo", help="load synthetic sample data (no download)").set_defaults(
        func=cmd_demo
    )
    sub.add_parser("status", help="show what is loaded").set_defaults(func=cmd_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except credit.SetupError as err:
        print(f"\n{err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
