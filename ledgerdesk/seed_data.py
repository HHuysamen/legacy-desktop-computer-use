"""Create the deterministic, entirely fictional LedgerDesk database."""

from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path
import sqlite3


def default_data_path() -> Path:
    return Path("output") / "ledgerdesk.db"


def load_seed() -> dict:
    root = Path(__file__).resolve().parent
    source = root.parent / "fixtures" / "seed.json"
    if not source.is_file():
        source = root / "fixtures" / "seed.json"
    return json.loads(source.read_text(encoding="utf-8"))


def reset_database(db_path: Path) -> None:
    """Replace the demo tables with the bundled seed; money is integer cents."""
    seed = load_seed()
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as connection, connection:
        connection.execute("PRAGMA foreign_keys = ON")
        # Explicit transaction keeps a failed reset from leaving half-seeded data.
        connection.execute("BEGIN IMMEDIATE")
        for table in ("invoices", "transactions", "customers"):
            connection.execute(f"DROP TABLE IF EXISTS {table}")
        connection.execute(
            "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)"
        )
        connection.execute(
            """CREATE TABLE invoices (
                invoice_number TEXT PRIMARY KEY,
                customer_id INTEGER NOT NULL REFERENCES customers(id),
                invoice_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                net_cents INTEGER NOT NULL CHECK(net_cents >= 0),
                paid_cents INTEGER NOT NULL CHECK(paid_cents >= 0 AND paid_cents <= net_cents),
                status TEXT NOT NULL CHECK(status IN ('issued', 'void'))
            )"""
        )
        connection.execute(
            """CREATE TABLE transactions (
                transaction_id TEXT PRIMARY KEY,
                recorded_cents INTEGER NOT NULL,
                expected_cents INTEGER NOT NULL
            )"""
        )
        connection.executemany(
            "INSERT INTO customers VALUES (:id, :name)", seed["customers"]
        )
        connection.executemany(
            """INSERT INTO invoices VALUES (
                :invoice_number, :customer_id, :invoice_date, :due_date,
                :net_cents, :paid_cents, :status
            )""",
            seed["invoices"],
        )
        connection.executemany(
            "INSERT INTO transactions VALUES (:transaction_id, :recorded_cents, :expected_cents)",
            seed["transactions"],
        )
