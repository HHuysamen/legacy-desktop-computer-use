"""Business rules used by the fixture app, never exposed as agent tools."""

from __future__ import annotations

import calendar
from contextlib import closing
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import sqlite3

REPORTS = {
    "monthly-revenue": "Monthly revenue",
    "overdue-invoices": "Overdue invoices",
    "reconciliation-exceptions": "Reconciliation exceptions",
}


def _money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    whole, fraction = divmod(abs(cents), 100)
    return f"{sign}{whole}.{fraction:02d}"


def _date(value: str) -> date:
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("Dates must use YYYY-MM-DD.")
    return parsed


def build_report(
    db_path: Path,
    report_id: str,
    *,
    as_of: str = "2026-10-15",
    month: str = "2026-09",
    tolerance: str = "0.01",
) -> tuple[list[str], list[dict[str, str]]]:
    if report_id not in REPORTS:
        raise ValueError(f"Unknown report: {report_id}")
    with closing(sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)) as db:
        if report_id == "monthly-revenue":
            if not re.fullmatch(r"\d{4}-\d{2}", month):
                raise ValueError("Month must use YYYY-MM.")
            first = _date(month + "-01")
            last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
            records = db.execute(
                """SELECT c.name, SUM(i.net_cents) AS revenue
                   FROM invoices i JOIN customers c ON c.id = i.customer_id
                   WHERE i.status != 'void' AND i.invoice_date BETWEEN ? AND ?
                   GROUP BY c.id, c.name ORDER BY revenue DESC, c.name ASC""",
                (first.isoformat(), last.isoformat()),
            ).fetchall()
            return ["customer", "revenue"], [
                {"customer": customer, "revenue": _money(amount)}
                for customer, amount in records
            ]
        if report_id == "overdue-invoices":
            cutoff = _date(as_of)
            records = db.execute(
                """SELECT c.name, i.invoice_number, i.net_cents - i.paid_cents, i.due_date
                   FROM invoices i JOIN customers c ON c.id = i.customer_id
                   WHERE i.status != 'void' AND i.paid_cents < i.net_cents AND i.due_date < ?
                   ORDER BY i.due_date ASC, i.invoice_number ASC""",
                (cutoff.isoformat(),),
            ).fetchall()
            return ["customer", "invoice_number", "balance", "due_date", "days_overdue"], [
                {
                    "customer": customer,
                    "invoice_number": number,
                    "balance": _money(balance),
                    "due_date": due,
                    "days_overdue": str((cutoff - date.fromisoformat(due)).days),
                }
                for customer, number, balance, due in records
            ]
        try:
            threshold = Decimal(tolerance)
        except InvalidOperation as error:
            raise ValueError("Tolerance must be a non-negative finite amount.") from error
        if not threshold.is_finite() or threshold < 0:
            raise ValueError("Tolerance must be a non-negative finite amount.")
        records = db.execute(
            "SELECT transaction_id, recorded_cents, expected_cents FROM transactions ORDER BY transaction_id"
        ).fetchall()
        return ["transaction_id", "recorded_amount", "expected_amount", "difference"], [
            {
                "transaction_id": transaction_id,
                "recorded_amount": _money(recorded),
                "expected_amount": _money(expected),
                "difference": _money(recorded - expected),
            }
            for transaction_id, recorded, expected in records
            if Decimal(abs(recorded - expected)) / 100 > threshold
        ]
