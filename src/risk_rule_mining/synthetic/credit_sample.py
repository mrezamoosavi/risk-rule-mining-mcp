"""Tiny synthetic data in the shape of Home Credit's files.

Used by the tests and CI so nobody needs a Kaggle account to run them. It is generated
at run time, never committed, and carries no real records. It mirrors file names, key
columns and a handful of real column names, not the full 122-column application table.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path


def _write(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def generate(out: Path, n_applicants: int = 200, seed: int = 7, orphans: int = 3) -> Path:
    """Write the nine CSVs into `out`. `orphans` child rows point at parents that don't exist."""
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)

    app_cols = [
        "SK_ID_CURR",
        "NAME_CONTRACT_TYPE",
        "CODE_GENDER",
        "AMT_INCOME_TOTAL",
        "AMT_CREDIT",
        "DAYS_BIRTH",
        "DAYS_EMPLOYED",
        "EXT_SOURCE_1",
    ]
    ids = list(range(100001, 100001 + n_applicants))
    n_train = int(n_applicants * 0.8)

    def app_row(i: int) -> list:
        return [
            i,
            rng.choice(["Cash loans", "Revolving loans"]),
            rng.choice(["F", "M"]),
            round(rng.uniform(30000, 300000), 1),
            round(rng.uniform(50000, 1000000), 1),
            -rng.randint(7000, 25000),
            -rng.randint(0, 15000),
            "" if rng.random() < 0.3 else round(rng.random(), 4),
        ]

    train = [[*app_row(i), int(rng.random() < 0.08)] for i in ids[:n_train]]
    _write(
        out / "application_train.csv",
        app_cols[:1] + ["TARGET"] + app_cols[1:],
        [[r[0], r[-1], *r[1:-1]] for r in train],
    )
    _write(out / "application_test.csv", app_cols, [app_row(i) for i in ids[n_train:]])

    bureau, bureau_balance = [], []
    bureau_id = 5000000
    for cur in ids:
        for _ in range(rng.randint(0, 3)):
            bureau_id += 1
            bureau.append(
                [
                    cur,
                    bureau_id,
                    rng.choice(["Active", "Closed"]),
                    -rng.randint(1, 2900),
                    round(rng.uniform(0, 500000), 1),
                ]
            )
            for m in range(rng.randint(1, 6)):
                bureau_balance.append([bureau_id, -m, rng.choice(["0", "C", "X", "1"])])
    bureau += [[999, 9000000 + k, "Active", -10, 1000.0] for k in range(orphans)]
    bureau_balance += [[8000000 + k, 0, "0"] for k in range(orphans)]
    _write(
        out / "bureau.csv",
        ["SK_ID_CURR", "SK_ID_BUREAU", "CREDIT_ACTIVE", "DAYS_CREDIT", "AMT_CREDIT_SUM"],
        bureau,
    )
    _write(out / "bureau_balance.csv", ["SK_ID_BUREAU", "MONTHS_BALANCE", "STATUS"], bureau_balance)

    prev, pos, card, inst = [], [], [], []
    prev_id = 2000000
    for cur in ids:
        for _ in range(rng.randint(0, 2)):
            prev_id += 1
            kind = rng.choice(["Consumer loans", "Cash loans", "Revolving loans"])
            prev.append(
                [
                    prev_id,
                    cur,
                    kind,
                    round(rng.uniform(5000, 400000), 1),
                    rng.choice(["Approved", "Refused"]),
                ]
            )
            for m in range(1, rng.randint(2, 6)):
                pos.append([prev_id, cur, -m, rng.randint(6, 24), rng.choice([0, 0, 0, 5])])
                due = round(rng.uniform(1000, 20000), 1)
                late = rng.random() < 0.1
                inst.append(
                    [
                        prev_id,
                        cur,
                        1,
                        m,
                        -30 * m,
                        -30 * m + (rng.randint(1, 40) if late else 0),
                        due,
                        due if not late else round(due * 0.5, 1),
                    ]
                )
            if kind == "Revolving loans":
                for m in range(1, 4):
                    card.append([prev_id, cur, -m, round(rng.uniform(0, 90000), 1), 90000])
    prev += [[7000000 + k, 999, "Cash loans", 1000.0, "Approved"] for k in range(orphans)]
    _write(
        out / "previous_application.csv",
        ["SK_ID_PREV", "SK_ID_CURR", "NAME_CONTRACT_TYPE", "AMT_CREDIT", "NAME_CONTRACT_STATUS"],
        prev,
    )
    _write(
        out / "POS_CASH_balance.csv",
        ["SK_ID_PREV", "SK_ID_CURR", "MONTHS_BALANCE", "CNT_INSTALMENT", "SK_DPD"],
        pos,
    )
    _write(
        out / "credit_card_balance.csv",
        ["SK_ID_PREV", "SK_ID_CURR", "MONTHS_BALANCE", "AMT_BALANCE", "AMT_CREDIT_LIMIT_ACTUAL"],
        card,
    )
    _write(
        out / "installments_payments.csv",
        [
            "SK_ID_PREV",
            "SK_ID_CURR",
            "NUM_INSTALMENT_VERSION",
            "NUM_INSTALMENT_NUMBER",
            "DAYS_INSTALMENT",
            "DAYS_ENTRY_PAYMENT",
            "AMT_INSTALMENT",
            "AMT_PAYMENT",
        ],
        inst,
    )

    with (out / "HomeCredit_columns_description.csv").open("w", encoding="latin-1") as f:
        f.write(
            ",Table,Row,Description,Special\n1,application_{train|test}.csv,SK_ID_CURR,"
            "ID of loan in our sample,\n2,application_{train|test}.csv,TARGET,"
            '"Target variable (1 - client with payment difficulties)",\n'
        )
    return out
