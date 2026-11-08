import csv
from contextlib import closing
from pathlib import Path
import shutil
import sqlite3

import pytest

from ledgerdesk.seed_data import reset_database
from ledgerdesk import workflows


REQUESTS = {
    "invoice-lookup": {"invoice_number": "INV-260916"},
    "customer-update": {"customer_id": "2", "email": "billing@beacon.example", "phone": "+1-555-0142"},
    "invoice-entry": {"reference": "DRAFT-261101", "customer_id": "3", "invoice_date": "2026-11-01", "due_date": "2026-12-01", "amount": "1250.50"},
    "payment-entry": {"reference": "RCPT-1001", "invoice_number": "INV-260916", "amount": "125.25"},
    "csv-import": {"file_name": "invoices.csv"},
}


@pytest.fixture
def case(tmp_path, monkeypatch):
    baseline = tmp_path / "baseline.db"
    reset_database(baseline)
    workflows.initialize_workflow_data(baseline)
    final = tmp_path / "final.db"
    shutil.copyfile(baseline, final)
    import_file = tmp_path / "imports" / "invoices.csv"
    workflows.write_import_fixture(import_file)
    monkeypatch.setattr(workflows, "IMPORT_PATH", import_file)
    return baseline, final, tmp_path / "export.csv", import_file


def export(path, result):
    headers, rows = result
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def table(db_path, name):
    with closing(sqlite3.connect(db_path)) as db:
        return db.execute(f'SELECT * FROM "{name}" ORDER BY 1').fetchall()


@pytest.mark.parametrize("workflow_id", REQUESTS)
def test_each_workflow_passes_independent_output_and_state_oracle(case, workflow_id):
    baseline, final, output, _ = case
    result = workflows.execute_workflow(final, workflow_id, REQUESTS[workflow_id])
    export(output, result)
    verified = workflows.verify_workflow(output, final, baseline, workflow_id)
    assert verified["passed"], verified["errors"]
    assert verified["row_count"] == (3 if workflow_id == "csv-import" else 1)
    assert all(isinstance(value, str) for row in result[1] for value in row.values())


def test_lookup_is_exact_and_changes_no_database_tables(case):
    baseline, final, _, _ = case
    before = workflows._snapshot(final)
    _, rows = workflows.execute_workflow(final, "invoice-lookup", REQUESTS["invoice-lookup"])
    assert rows == [{"invoice_number": "INV-260916", "customer": "Beacon Paperworks", "invoice_date": "2026-09-16", "due_date": "2026-10-10", "amount": "1000.00", "paid": "600.00", "balance": "400.00", "status": "issued"}]
    assert before == workflows._snapshot(final) == workflows._snapshot(baseline)
    with pytest.raises(ValueError, match="not found"):
        workflows.execute_workflow(final, "invoice-lookup", {"invoice_number": "INV-26091"})


def test_contact_update_preserves_other_contacts_and_reinitialization(case):
    _, final, _, _ = case
    workflows.execute_workflow(final, "customer-update", REQUESTS["customer-update"])
    workflows.initialize_workflow_data(final)
    contacts = table(final, "contacts")
    assert contacts == [(1, "", ""), (2, "billing@beacon.example", "+1-555-0142"), (3, "", ""), (4, "", ""), (5, "", ""), (6, "", "")]


def test_payment_uses_integer_cents_and_duplicate_receipt_does_not_repeat_payment(case):
    _, final, _, _ = case
    _, rows = workflows.execute_workflow(final, "payment-entry", REQUESTS["payment-entry"])
    assert rows[0]["paid_total"] == "725.25"
    assert rows[0]["balance"] == "274.75"
    before = workflows._snapshot(final)
    with pytest.raises(sqlite3.IntegrityError):
        workflows.execute_workflow(final, "payment-entry", REQUESTS["payment-entry"])
    assert workflows._snapshot(final) == before


def test_duplicate_draft_is_rejected_without_changing_other_state(case):
    _, final, _, _ = case
    workflows.execute_workflow(final, "invoice-entry", REQUESTS["invoice-entry"])
    before = workflows._snapshot(final)
    with pytest.raises(sqlite3.IntegrityError):
        workflows.execute_workflow(final, "invoice-entry", REQUESTS["invoice-entry"])
    assert workflows._snapshot(final) == before


@pytest.mark.parametrize("value", ["0", "-1", "1.001", "NaN", "Infinity", "1e3", "99999999999999999999"])
def test_invalid_amounts_do_not_mutate_database(case, value):
    _, final, _, _ = case
    before = workflows._snapshot(final)
    fields = {**REQUESTS["payment-entry"], "amount": value}
    with pytest.raises(ValueError):
        workflows.execute_workflow(final, "payment-entry", fields)
    assert workflows._snapshot(final) == before


@pytest.mark.parametrize("changes", [
    {"amount": "400.01"}, {"invoice_number": "missing"}, {"invoice_number": "INV-260912"},
])
def test_payment_rejects_overpayment_missing_and_voided_invoice(case, changes):
    _, final, _, _ = case
    before = workflows._snapshot(final)
    with pytest.raises(ValueError):
        workflows.execute_workflow(final, "payment-entry", {**REQUESTS["payment-entry"], **changes})
    assert workflows._snapshot(final) == before


@pytest.mark.parametrize("changes", [
    {"customer_id": "99"}, {"invoice_date": "2026-02-30"},
    {"due_date": "2026-10-31"}, {"reference": "../../escape"},
])
def test_invalid_draft_fields_do_not_mutate_database(case, changes):
    _, final, _, _ = case
    before = workflows._snapshot(final)
    with pytest.raises(ValueError):
        workflows.execute_workflow(final, "invoice-entry", {**REQUESTS["invoice-entry"], **changes})
    assert workflows._snapshot(final) == before


def test_import_preserves_leading_zeros_and_source_file(case):
    _, final, _, source = case
    source_bytes = source.read_bytes()
    _, rows = workflows.execute_workflow(final, "csv-import", REQUESTS["csv-import"])
    assert [row["reference"] for row in rows] == ["000101", "000102", "000103"]
    assert source.read_bytes() == source_bytes
    assert [row[0] for row in table(final, "drafts")] == ["000101", "000102", "000103"]


def test_import_is_atomic_when_last_row_duplicates_existing_draft(case):
    _, final, _, _ = case
    existing = {**REQUESTS["invoice-entry"], "reference": "000103"}
    workflows.execute_workflow(final, "invoice-entry", existing)
    before = workflows._snapshot(final)
    with pytest.raises(sqlite3.IntegrityError):
        workflows.execute_workflow(final, "csv-import", REQUESTS["csv-import"])
    assert workflows._snapshot(final) == before


@pytest.mark.parametrize("bad_kind", ["columns", "duplicate", "bad_amount", "missing", "oversized"])
def test_invalid_import_is_rejected_before_any_mutation(case, bad_kind):
    _, final, _, source = case
    text = source.read_text()
    if bad_kind == "columns":
        source.write_text(text.replace("reference,", "id,", 1))
    elif bad_kind == "duplicate":
        source.write_text(text.replace("000103", "000101"))
    elif bad_kind == "bad_amount":
        source.write_text(text.replace("99.95", "99.951"))
    elif bad_kind == "missing":
        source.write_text("\n".join(text.splitlines()[:-1]) + "\n")
    else:
        source.write_text("x" * 65537)
    before = workflows._snapshot(final)
    with pytest.raises(ValueError):
        workflows.execute_workflow(final, "csv-import", REQUESTS["csv-import"])
    assert workflows._snapshot(final) == before


def test_import_refuses_arbitrary_file_names(case):
    _, final, _, _ = case
    with pytest.raises(ValueError, match="configured"):
        workflows.execute_workflow(final, "csv-import", {"file_name": "../../other.csv"})


@pytest.mark.parametrize("invalid", ["malformed", "encoding", "symlink"])
def test_bad_import_file_does_not_escape_gui_error_handling(case, tmp_path, invalid):
    _, final, _, source = case
    before = workflows._snapshot(final)
    if invalid == "malformed":
        source.write_text('"unterminated')
    elif invalid == "encoding":
        source.write_bytes(b"\xff\xfeinvalid")
    else:
        target = tmp_path / "other.csv"
        source.rename(target)
        source.symlink_to(target)
    with pytest.raises(ValueError):
        workflows.execute_workflow(final, "csv-import", REQUESTS["csv-import"])
    assert workflows._snapshot(final) == before


@pytest.mark.parametrize("mutation", ["unrelated_contact", "invoice", "new_table", "extra_draft"])
def test_verifier_rejects_unintended_database_changes(case, mutation):
    baseline, final, output, _ = case
    export(output, workflows.execute_workflow(final, "customer-update", REQUESTS["customer-update"]))
    with closing(sqlite3.connect(final)) as db, db:
        if mutation == "unrelated_contact":
            db.execute("UPDATE contacts SET phone='unintended' WHERE customer_id=1")
        elif mutation == "invoice":
            db.execute("UPDATE invoices SET paid_cents=1 WHERE invoice_number='INV-260903'")
        elif mutation == "new_table":
            db.execute("CREATE TABLE unexpected (value TEXT)")
        else:
            db.execute("INSERT INTO drafts VALUES ('EXTRA', 1, '2026-11-01', '2026-12-01', 100, 'manual')")
    assert not workflows.verify_workflow(output, final, baseline, "customer-update")["passed"]


@pytest.mark.parametrize("mutation", ["amount", "duplicate", "missing", "reorder", "extra_column"])
def test_verifier_rejects_incorrect_csv_even_when_state_is_correct(case, mutation):
    baseline, final, output, _ = case
    headers, rows = workflows.execute_workflow(final, "csv-import", REQUESTS["csv-import"])
    if mutation == "amount":
        rows[0]["amount"] = "210.11"
    elif mutation == "duplicate":
        rows[-1] = rows[0].copy()
    elif mutation == "missing":
        rows.pop()
    elif mutation == "reorder":
        rows.reverse()
    else:
        headers.append("extra")
    export(output, (headers, rows))
    assert not workflows.verify_workflow(output, final, baseline, "csv-import")["passed"]


def test_verifier_rejects_correct_looking_csv_without_payment_mutation(case):
    baseline, final, output, _ = case
    result = workflows.execute_workflow(final, "payment-entry", REQUESTS["payment-entry"])
    export(output, result)
    shutil.copyfile(baseline, final)
    assert not workflows.verify_workflow(output, final, baseline, "payment-entry")["passed"]


def test_verifier_is_independent_of_operation_and_formatter(case, monkeypatch):
    baseline, final, output, _ = case
    export(output, workflows.execute_workflow(final, "payment-entry", REQUESTS["payment-entry"]))
    monkeypatch.setattr(workflows, "execute_workflow", lambda *args: ([], []))
    monkeypatch.setattr(workflows, "_money", lambda cents: "wrong")
    assert workflows.verify_workflow(output, final, baseline, "payment-entry")["passed"]


def test_missing_csv_and_database_fail_verification(case, tmp_path):
    baseline, final, output, _ = case
    assert not workflows.verify_workflow(output, final, baseline, "invoice-lookup")["passed"]
    assert not workflows.verify_workflow(output, tmp_path / "missing.db", baseline, "invoice-lookup")["passed"]


def test_unknown_or_unexpected_fields_are_rejected(case):
    _, final, _, _ = case
    with pytest.raises(ValueError, match="Unknown"):
        workflows.execute_workflow(final, "unknown", {})
    with pytest.raises(ValueError, match="fields"):
        workflows.execute_workflow(final, "invoice-lookup", {"invoice_number": "INV-260916", "extra": "no"})
    with pytest.raises(ValueError, match="Unknown"):
        workflows.workflow_instruction("unknown")


def test_workflow_instructions_include_exact_target_and_no_transfer():
    assert "INV-260916" in workflows.workflow_instruction("invoice-lookup")
    assert "billing@beacon.example" in workflows.workflow_instruction("customer-update")
    assert "DRAFT-261101" in workflows.workflow_instruction("invoice-entry")
    assert "must not transfer funds" in workflows.workflow_instruction("payment-entry")
    assert "leading zeros" in workflows.workflow_instruction("csv-import")


def test_initialization_leaves_original_seed_tables_unchanged(tmp_path):
    db = tmp_path / "fixture.db"
    reset_database(db)
    _, original_tables = workflows._snapshot(db)
    workflows.initialize_workflow_data(db)
    _, initialized_tables = workflows._snapshot(db)
    for name, rows in original_tables.items():
        assert initialized_tables[name] == rows
