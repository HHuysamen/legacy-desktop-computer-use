import csv

import pytest

from ledgerdesk.reports import build_report
from ledgerdesk.seed_data import reset_database
from ledgerdesk.verify import verify_csv


@pytest.fixture
def export(tmp_path):
    db = tmp_path / "ledgerdesk.db"
    reset_database(db)
    path = tmp_path / "report.csv"
    return db, path


def write_csv(path, headers, rows):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


@pytest.mark.parametrize("report_id", ["monthly-revenue", "overdue-invoices", "reconciliation-exceptions"])
def test_correct_report_passes_independent_oracle(export, report_id):
    db, path = export
    headers, rows = build_report(db, report_id)
    write_csv(path, headers, rows)
    result = verify_csv(path, db, report_id)
    assert result == {"passed": True, "errors": [], "row_count": len(rows), "headers": headers, "rows": rows}


@pytest.mark.parametrize("mutation", ["amount", "order", "missing", "duplicate", "columns", "extra-cell"])
def test_verifier_rejects_wrong_content_not_only_missing_file(export, mutation):
    db, path = export
    headers, rows = build_report(db, "monthly-revenue")
    if mutation == "amount":
        rows[0]["revenue"] = "2400.01"
    elif mutation == "order":
        rows.reverse()
    elif mutation == "missing":
        rows.pop()
    elif mutation == "duplicate":
        rows[-1] = rows[0].copy()
    elif mutation == "columns":
        headers.reverse()
    write_csv(path, headers, rows)
    if mutation == "extra-cell":
        text = path.read_text()
        path.write_text(text.replace("2400.00", "2400.00,unexpected", 1))
    result = verify_csv(path, db, "monthly-revenue")
    assert not result["passed"]
    assert result["errors"]


def test_missing_export_is_a_failed_verification(export):
    db, path = export
    result = verify_csv(path, db, "monthly-revenue")
    assert not result["passed"]
    assert result["row_count"] == 0
    assert any("Unable to read" in error for error in result["errors"])


def test_oracle_does_not_depend_on_app_report_implementation(export, monkeypatch):
    db, path = export
    headers, rows = build_report(db, "reconciliation-exceptions")
    write_csv(path, headers, rows)
    monkeypatch.setattr("ledgerdesk.reports.build_report", lambda *args, **kwargs: ([], []))
    assert verify_csv(path, db, "reconciliation-exceptions")["passed"]


@pytest.mark.parametrize("tolerance", ["0.015", "1e999"])
def test_tolerance_is_exact_and_handles_large_values(export, tolerance):
    db, path = export
    headers, rows = build_report(db, "reconciliation-exceptions", tolerance=tolerance)
    write_csv(path, headers, rows)
    assert verify_csv(path, db, "reconciliation-exceptions", tolerance=tolerance)["passed"]
