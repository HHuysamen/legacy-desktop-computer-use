from pathlib import Path
import sqlite3

import pytest

from ledgerdesk.reports import build_report
from ledgerdesk.seed_data import reset_database
from ledgerdesk.tasks import task_instruction


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "ledgerdesk.db"
    reset_database(path)
    return path


def test_monthly_revenue_uses_invoice_date_excludes_voids_and_sorts_ties(db):
    headers, rows = build_report(db, "monthly-revenue")
    assert headers == ["customer", "revenue"]
    assert rows == [
        {"customer": "Alder Robotics", "revenue": "2400.00"},
        {"customer": "Beacon Paperworks", "revenue": "2400.00"},
        {"customer": "Cedar Trail Foods", "revenue": "2000.00"},
        {"customer": "Delta Quay Services", "revenue": "1800.00"},
        {"customer": "Ember Loom Textiles", "revenue": "1500.00"},
        {"customer": "Fernlight Design", "revenue": "1500.00"},
    ]


def test_overdue_includes_partial_payments_excludes_due_today_void_and_paid(db):
    _, rows = build_report(db, "overdue-invoices", as_of="2026-10-15")
    assert [row["invoice_number"] for row in rows] == [
        "INV-260801", "INV-260831", "INV-260820", "INV-260903",
        "INV-260916", "INV-260918", "INV-261014",
    ]
    partial = next(row for row in rows if row["invoice_number"] == "INV-260916")
    assert partial == {
        "customer": "Beacon Paperworks", "invoice_number": "INV-260916",
        "balance": "400.00", "due_date": "2026-10-10", "days_overdue": "5",
    }
    assert rows[-1]["days_overdue"] == "1"


def test_reconciliation_strict_threshold_and_signed_difference(db):
    _, rows = build_report(db, "reconciliation-exceptions")
    assert [row["transaction_id"] for row in rows] == ["TXN-004", "TXN-005", "TXN-006", "TXN-007"]
    assert [row["difference"] for row in rows] == ["0.02", "-0.02", "5.00", "-10.00"]
    _, at_two_cents = build_report(db, "reconciliation-exceptions", tolerance="0.02")
    assert [row["transaction_id"] for row in at_two_cents] == ["TXN-006", "TXN-007"]


@pytest.mark.parametrize("tolerance", ["-1", "NaN", "Infinity", "oops"])
def test_reconciliation_rejects_invalid_tolerance(db, tolerance):
    with pytest.raises(ValueError):
        build_report(db, "reconciliation-exceptions", tolerance=tolerance)


@pytest.mark.parametrize("report_id,kwargs", [
    ("unknown", {}),
    ("monthly-revenue", {"month": "2026-13"}),
    ("monthly-revenue", {"month": "2026-9"}),
    ("overdue-invoices", {"as_of": "2026-02-30"}),
    ("overdue-invoices", {"as_of": "20261015"}),
])
def test_invalid_report_parameters(db, report_id, kwargs):
    with pytest.raises(ValueError):
        build_report(db, report_id, **kwargs)


def test_fixture_reset_restores_exact_records(db):
    before = {report: build_report(db, report) for report in (
        "monthly-revenue", "overdue-invoices", "reconciliation-exceptions"
    )}
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE invoices SET net_cents = net_cents + 100000")
        connection.execute("DELETE FROM transactions")
    reset_database(db)
    assert before == {report: build_report(db, report) for report in before}
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM invoices").fetchone()[0] == 25


def test_missing_database_is_not_created(tmp_path):
    missing = tmp_path / "absent.db"
    with pytest.raises(sqlite3.OperationalError):
        build_report(missing, "monthly-revenue")
    assert not missing.exists()


def test_task_dates_and_unknown_report():
    assert "2026-12-01" in task_instruction("overdue-invoices", "2026-12-01")
    with pytest.raises(ValueError):
        task_instruction("overdue-invoices", "bad-date")
    with pytest.raises(ValueError):
        task_instruction("not-a-report")
