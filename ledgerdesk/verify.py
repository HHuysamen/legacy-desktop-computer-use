"""Trusted CSV oracle: independent SQL and formatting, no app report functions."""

from __future__ import annotations

import csv
from contextlib import closing
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from pathlib import Path
import re
import sqlite3


def _expected(db_path: Path, report_id: str, as_of: str, month: str, tolerance: str):
    def money(cents):
        return format(Decimal(cents) / Decimal(100), ".2f")

    with closing(sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)) as db:
        if report_id == "monthly-revenue":
            if not re.fullmatch(r"\d{4}-\d{2}", month):
                raise ValueError("Month must use YYYY-MM.")
            first = date.fromisoformat(month + "-01")
            next_month = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
            records = db.execute(
                """SELECT customers.name, SUM(net_cents) AS total
                   FROM customers JOIN invoices ON customer_id = customers.id
                   WHERE status = 'issued' AND invoice_date >= ? AND invoice_date < ?
                   GROUP BY customers.name ORDER BY total DESC, customers.name""",
                (first.isoformat(), next_month.isoformat()),
            ).fetchall()
            headers = ["customer", "revenue"]
            values = [(name, money(total)) for name, total in records]
        elif report_id == "overdue-invoices":
            cutoff = date.fromisoformat(as_of)
            if cutoff.isoformat() != as_of:
                raise ValueError("As-of date must use YYYY-MM-DD.")
            records = db.execute(
                """SELECT name, invoice_number, net_cents, paid_cents, due_date
                   FROM customers JOIN invoices ON customer_id = customers.id
                   WHERE status = 'issued' AND net_cents - paid_cents > 0 AND due_date < ?
                   ORDER BY due_date, invoice_number""",
                (as_of,),
            ).fetchall()
            headers = ["customer", "invoice_number", "balance", "due_date", "days_overdue"]
            values = [
                (name, number, money(net - paid), due, str(cutoff.toordinal() - date.fromisoformat(due).toordinal()))
                for name, number, net, paid, due in records
            ]
        elif report_id == "reconciliation-exceptions":
            try:
                threshold = Decimal(tolerance)
            except InvalidOperation as error:
                raise ValueError("Invalid tolerance.") from error
            if not threshold.is_finite() or threshold < 0:
                raise ValueError("Invalid tolerance.")
            if threshold >= Decimal(2**63 - 1) / 100:
                records = []
            else:
                minimum_cents = int((threshold * 100).to_integral_value(rounding=ROUND_FLOOR)) + 1
                records = db.execute(
                    """SELECT transaction_id, recorded_cents, expected_cents
                       FROM transactions WHERE ABS(recorded_cents - expected_cents) >= ?
                       ORDER BY transaction_id""",
                    (minimum_cents,),
                ).fetchall()
            headers = ["transaction_id", "recorded_amount", "expected_amount", "difference"]
            values = [(identifier, money(actual), money(expected), money(actual - expected))
                      for identifier, actual, expected in records]
        else:
            raise ValueError(f"Unknown report: {report_id}")
    return headers, [dict(zip(headers, row)) for row in values]


def verify_csv(
    csv_path: Path,
    db_path: Path,
    report_id: str,
    *,
    as_of: str = "2026-10-15",
    month: str = "2026-09",
    tolerance: str = "0.01",
) -> dict:
    """Compare schema, values, row count, uniqueness and ordering exactly."""
    expected_headers, expected_rows = _expected(db_path, report_id, as_of, month, tolerance)
    errors = []
    headers = []
    rows = []
    try:
        with Path(csv_path).open(newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file, strict=True)
            headers = reader.fieldnames or []
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as error:
        errors.append(f"Unable to read exported CSV: {error}")
    if headers != expected_headers:
        errors.append(f"Columns differ: expected {expected_headers!r}, received {headers!r}.")
    if len(rows) != len(expected_rows):
        errors.append(f"Row count differs: expected {len(expected_rows)}, received {len(rows)}.")
    key = "customer" if report_id == "monthly-revenue" else (
        "invoice_number" if report_id == "overdue-invoices" else "transaction_id"
    )
    identifiers = [row.get(key) for row in rows]
    if len(set(identifiers)) != len(identifiers):
        errors.append(f"Duplicate values in {key}.")
    for index, (actual, expected) in enumerate(zip(rows, expected_rows), start=1):
        if actual != expected:
            errors.append(f"Row {index} differs: expected {expected!r}, received {actual!r}.")
    return {
        "passed": not errors,
        "errors": errors,
        "row_count": len(rows),
        "headers": headers,
        "rows": rows,
    }
