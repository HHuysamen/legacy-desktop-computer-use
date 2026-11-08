"""Synthetic desktop workflow operations and a separate state/CSV verifier."""

from __future__ import annotations

from contextlib import closing
import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
import re
import sqlite3


WORKFLOWS = {
    "invoice-lookup": "Invoice lookup",
    "customer-update": "Update customer contact",
    "invoice-entry": "Enter draft invoice",
    "payment-entry": "Record demo payment",
    "csv-import": "Import draft invoices",
}

FIELDS = {
    "invoice-lookup": [("invoice_number", "Invoice number")],
    "customer-update": [("customer_id", "Customer ID"), ("email", "Email"), ("phone", "Phone")],
    "invoice-entry": [
        ("reference", "Draft reference"), ("customer_id", "Customer ID"),
        ("invoice_date", "Invoice date (YYYY-MM-DD)"), ("due_date", "Due date (YYYY-MM-DD)"),
        ("amount", "Amount (USD)"),
    ],
    "payment-entry": [("reference", "Receipt reference"), ("invoice_number", "Invoice number"), ("amount", "Payment (USD)")],
    "csv-import": [("file_name", "Import file")],
}

IMPORT_PATH = Path("/tmp/ledgerdesk/imports/invoices.csv")
IMPORT_HEADERS = ["reference", "customer_id", "invoice_date", "due_date", "amount"]
IMPORT_ROWS = [
    {"reference": "000101", "customer_id": "1", "invoice_date": "2026-11-02", "due_date": "2026-12-02", "amount": "210.10"},
    {"reference": "000102", "customer_id": "2", "invoice_date": "2026-11-03", "due_date": "2026-12-03", "amount": "325.00"},
    {"reference": "000103", "customer_id": "6", "invoice_date": "2026-11-04", "due_date": "2026-12-04", "amount": "99.95"},
]


def workflow_instruction(workflow_id: str) -> str:
    instructions = {
        "invoice-lookup": (
            "In LedgerDesk, look up invoice INV-260916 by its exact invoice number. "
            "Do not modify any records. Export the lookup result as CSV."
        ),
        "customer-update": (
            "In LedgerDesk, update only customer ID 2 (Beacon Paperworks): set the email to "
            "billing@beacon.example and the phone to +1-555-0142. Confirm the change and "
            "export its audit result as CSV. Leave all other records unchanged."
        ),
        "invoice-entry": (
            "In LedgerDesk, create one draft invoice with reference DRAFT-261101 for customer ID 3 "
            "(Cedar Trail Foods), invoice date 2026-11-01, due date 2026-12-01, and amount 1250.50 USD. "
            "Confirm creation and export the audit result as CSV. Do not post or send an invoice."
        ),
        "payment-entry": (
            "In LedgerDesk, record a synthetic payment receipt RCPT-1001 for invoice INV-260916 "
            "with amount 125.25 USD. This only updates the included demo records; it must not "
            "transfer funds. Confirm the demo receipt and export its audit result as CSV."
        ),
        "csv-import": (
            "In LedgerDesk, import the configured file invoices.csv into draft invoices. "
            "It contains three new drafts with references 000101, 000102 and 000103; preserve "
            "the leading zeros. Confirm the import and export its audit result as CSV. "
            "Do not post or send invoices."
        ),
    }
    try:
        return instructions[workflow_id]
    except KeyError:
        raise ValueError(f"Unknown workflow: {workflow_id}") from None


def write_import_fixture(path: Path = IMPORT_PATH) -> None:
    """Guest setup only: create the one fixed, synthetic import file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=IMPORT_HEADERS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(IMPORT_ROWS)


def initialize_workflow_data(db_path: Path) -> None:
    """Add workflow tables without changing the original seed or existing rows."""
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("""CREATE TABLE IF NOT EXISTS contacts (
            customer_id INTEGER PRIMARY KEY REFERENCES customers(id),
            email TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '')""")
        db.execute("""CREATE TABLE IF NOT EXISTS drafts (
            reference TEXT PRIMARY KEY,
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            invoice_date TEXT NOT NULL, due_date TEXT NOT NULL,
            amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
            source TEXT NOT NULL CHECK(source IN ('manual', 'csv')))""")
        db.execute("""CREATE TABLE IF NOT EXISTS receipts (
            reference TEXT PRIMARY KEY,
            invoice_number TEXT NOT NULL REFERENCES invoices(invoice_number),
            amount_cents INTEGER NOT NULL CHECK(amount_cents > 0))""")
        db.execute("INSERT OR IGNORE INTO contacts (customer_id) SELECT id FROM customers")


def _money(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"


def _amount(value: str) -> int:
    if len(value) > 20 or not re.fullmatch(r"(?:0|[1-9]\d*)(?:\.\d{1,2})?", value):
        raise ValueError("Amount must be a positive decimal with at most two decimal places.")
    cents = int(Decimal(value) * 100)
    if not 0 < cents <= 2**63 - 1:
        raise ValueError("Amount is outside the supported range.")
    return cents


def _reference(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,39}", value):
        raise ValueError("Reference must contain 1–40 letters, digits, hyphens or underscores.")
    return value


def _customer(db: sqlite3.Connection, value: str) -> tuple[int, str]:
    if not re.fullmatch(r"[0-9]{1,10}", value):
        raise ValueError("Customer ID must be a positive integer.")
    row = db.execute("SELECT id, name FROM customers WHERE id = ?", (int(value),)).fetchone()
    if row is None:
        raise ValueError("Customer ID was not found.")
    return row


def _draft_values(db: sqlite3.Connection, fields: dict[str, str]) -> tuple:
    reference = _reference(fields["reference"])
    customer_id, customer = _customer(db, fields["customer_id"])
    issued, due = date.fromisoformat(fields["invoice_date"]), date.fromisoformat(fields["due_date"])
    if issued.isoformat() != fields["invoice_date"] or due.isoformat() != fields["due_date"] or due < issued:
        raise ValueError("Use YYYY-MM-DD dates with due date on or after the invoice date.")
    return reference, customer_id, issued.isoformat(), due.isoformat(), _amount(fields["amount"]), customer


def _draft_result(values: list[tuple]) -> tuple[list[str], list[dict[str, str]]]:
    headers = ["reference", "customer_id", "customer", "invoice_date", "due_date", "amount", "status"]
    return headers, [dict(zip(headers, [reference, str(customer_id), customer, issued, due, _money(cents), "draft"]))
                     for reference, customer_id, issued, due, cents, customer in values]


def execute_workflow(db_path: Path, workflow_id: str, fields: dict[str, str]) -> tuple[list[str], list[dict[str, str]]]:
    """Called by the fixture's Confirm button; mutations commit atomically."""
    if workflow_id not in WORKFLOWS:
        raise ValueError(f"Unknown workflow: {workflow_id}")
    if set(fields) != {key for key, _ in FIELDS[workflow_id]} or not all(isinstance(value, str) for value in fields.values()):
        raise ValueError("Workflow fields are missing, unexpected or invalid.")
    fields = {key: value.strip() for key, value in fields.items()}
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute("PRAGMA foreign_keys = ON")
        if workflow_id == "invoice-lookup":
            row = db.execute(
                """SELECT i.invoice_number, c.name, i.invoice_date, i.due_date,
                          i.net_cents, i.paid_cents, i.status
                   FROM invoices i JOIN customers c ON c.id=i.customer_id
                   WHERE i.invoice_number=?""", (fields["invoice_number"],)
            ).fetchone()
            if row is None:
                raise ValueError("Invoice number was not found.")
            number, customer, issued, due, total, paid, status = row
            headers = ["invoice_number", "customer", "invoice_date", "due_date", "amount", "paid", "balance", "status"]
            return headers, [dict(zip(headers, [number, customer, issued, due, _money(total), _money(paid), _money(total-paid), status]))]
        if workflow_id == "customer-update":
            customer_id, customer = _customer(db, fields["customer_id"])
            email, phone = fields["email"], fields["phone"]
            if len(email) > 100 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                raise ValueError("Enter a valid contact email.")
            if not re.fullmatch(r"\+?[0-9 ()-]{5,30}", phone):
                raise ValueError("Enter a valid contact phone.")
            changed = db.execute("UPDATE contacts SET email=?, phone=? WHERE customer_id=?", (email, phone, customer_id))
            if changed.rowcount != 1:
                raise ValueError("Contact was not initialized.")
            headers = ["customer_id", "customer", "email", "phone"]
            return headers, [dict(zip(headers, [str(customer_id), customer, email, phone]))]
        if workflow_id == "invoice-entry":
            values = _draft_values(db, fields)
            db.execute("INSERT INTO drafts VALUES (?, ?, ?, ?, ?, 'manual')", values[:5])
            return _draft_result([values])
        if workflow_id == "payment-entry":
            reference = _reference(fields["reference"])
            amount = _amount(fields["amount"])
            row = db.execute(
                """SELECT i.net_cents, i.paid_cents, i.status, c.name
                   FROM invoices i JOIN customers c ON c.id=i.customer_id
                   WHERE i.invoice_number=?""", (fields["invoice_number"],)
            ).fetchone()
            if row is None:
                raise ValueError("Invoice number was not found.")
            total, paid, status, customer = row
            if status != "issued" or amount > total-paid:
                raise ValueError("Payment requires an issued invoice and cannot exceed its balance.")
            db.execute("INSERT INTO receipts VALUES (?, ?, ?)", (reference, fields["invoice_number"], amount))
            changed = db.execute(
                "UPDATE invoices SET paid_cents=paid_cents+? WHERE invoice_number=? AND paid_cents=?",
                (amount, fields["invoice_number"], paid),
            )
            if changed.rowcount != 1:
                raise ValueError("Invoice changed while recording payment; retry after reviewing it.")
            headers = ["reference", "invoice_number", "customer", "payment", "paid_total", "balance"]
            return headers, [dict(zip(headers, [reference, fields["invoice_number"], customer,
                                               _money(amount), _money(paid+amount), _money(total-paid-amount)]))]
        if fields["file_name"] != "invoices.csv":
            raise ValueError("Only the configured invoices.csv import is allowed.")
        if not IMPORT_PATH.is_file() or IMPORT_PATH.is_symlink() or IMPORT_PATH.stat().st_size > 65536:
            raise ValueError("Import file must be a regular CSV no larger than 64 KiB.")
        try:
            with IMPORT_PATH.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream, strict=True)
                if reader.fieldnames != IMPORT_HEADERS:
                    raise ValueError("Import CSV columns do not match the configured format.")
                records = list(reader)
        except (csv.Error, UnicodeError) as error:
            raise ValueError("Import file is not valid UTF-8 CSV.") from error
        if len(records) != 3 or any(set(row) != set(IMPORT_HEADERS) or None in row.values() for row in records):
            raise ValueError("Import must contain exactly three complete draft rows.")
        values = [_draft_values(db, row) for row in records]
        if len({row[0] for row in values}) != len(values):
            raise ValueError("Import contains duplicate references.")
        db.executemany("INSERT INTO drafts VALUES (?, ?, ?, ?, ?, 'csv')", [row[:5] for row in values])
        return _draft_result(values)


def _snapshot(db_path: Path) -> tuple[list, dict[str, list[tuple]]]:
    with closing(sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)) as db:
        schema = db.execute("SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name").fetchall()
        tables = {}
        for kind, name, _ in schema:
            if kind == "table":
                quoted = '"' + name.replace('"', '""') + '"'
                tables[name] = sorted(db.execute(f"SELECT * FROM {quoted}").fetchall(), key=repr)
        return schema, tables


def _oracle(baseline_db: Path, workflow_id: str) -> tuple[list[str], list[dict[str, str]], list, dict]:
    """Expected changes from the original snapshot, independent of operation helpers."""
    schema, tables = _snapshot(baseline_db)
    customers = dict(tables["customers"])
    invoice = next(row for row in tables["invoices"] if row[0] == "INV-260916")
    fmt = lambda cents: format(Decimal(cents) / Decimal(100), ".2f")
    if workflow_id == "invoice-lookup":
        number, customer_id, issued, due, net, paid, status = invoice
        headers = ["invoice_number", "customer", "invoice_date", "due_date", "amount", "paid", "balance", "status"]
        values = [[number, customers[customer_id], issued, due, fmt(net), fmt(paid), fmt(net-paid), status]]
    elif workflow_id == "customer-update":
        tables["contacts"] = [(2, "billing@beacon.example", "+1-555-0142") if row[0] == 2 else row for row in tables["contacts"]]
        headers = ["customer_id", "customer", "email", "phone"]
        values = [["2", customers[2], "billing@beacon.example", "+1-555-0142"]]
    elif workflow_id == "invoice-entry":
        tables["drafts"].append(("DRAFT-261101", 3, "2026-11-01", "2026-12-01", 125050, "manual"))
        headers = ["reference", "customer_id", "customer", "invoice_date", "due_date", "amount", "status"]
        values = [["DRAFT-261101", "3", customers[3], "2026-11-01", "2026-12-01", "1250.50", "draft"]]
    elif workflow_id == "payment-entry":
        updated = (*invoice[:5], invoice[5] + 12525, invoice[6])
        tables["invoices"] = [updated if row[0] == invoice[0] else row for row in tables["invoices"]]
        tables["receipts"].append(("RCPT-1001", "INV-260916", 12525))
        headers = ["reference", "invoice_number", "customer", "payment", "paid_total", "balance"]
        values = [["RCPT-1001", "INV-260916", customers[invoice[1]], "125.25", fmt(invoice[5]+12525), fmt(invoice[4]-invoice[5]-12525)]]
    elif workflow_id == "csv-import":
        additions = [
            ("000101", 1, "2026-11-02", "2026-12-02", 21010, "csv"),
            ("000102", 2, "2026-11-03", "2026-12-03", 32500, "csv"),
            ("000103", 6, "2026-11-04", "2026-12-04", 9995, "csv"),
        ]
        tables["drafts"].extend(additions)
        headers = ["reference", "customer_id", "customer", "invoice_date", "due_date", "amount", "status"]
        values = [[ref, str(customer), customers[customer], issued, due, fmt(amount), "draft"]
                  for ref, customer, issued, due, amount, _ in additions]
    else:
        raise ValueError(f"Unknown workflow: {workflow_id}")
    return headers, [dict(zip(headers, row)) for row in values], schema, {name: sorted(rows, key=repr) for name, rows in tables.items()}


def verify_workflow(csv_path: Path, final_db: Path, baseline_db: Path, workflow_id: str) -> dict:
    """Check the exact output and all final database state, including non-target rows."""
    errors, headers, rows = [], [], []
    try:
        expected_headers, expected_rows, expected_schema, expected_tables = _oracle(baseline_db, workflow_id)
        final_schema, final_tables = _snapshot(final_db)
        if final_schema != expected_schema:
            errors.append("Database schema changed unexpectedly.")
        for name in sorted(set(expected_tables) | set(final_tables)):
            if final_tables.get(name) != expected_tables.get(name):
                errors.append(f"Database table {name} does not match the expected final state.")
    except (OSError, sqlite3.Error, KeyError, StopIteration) as error:
        errors.append(f"Unable to verify database state: {type(error).__name__}.")
        expected_headers, expected_rows = [], []
    try:
        with Path(csv_path).open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            headers = reader.fieldnames or []
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as error:
        errors.append(f"Unable to read exported CSV: {type(error).__name__}.")
    if headers != expected_headers:
        errors.append(f"Columns differ: expected {expected_headers!r}, received {headers!r}.")
    if rows != expected_rows:
        errors.append("Exported rows differ from the exact expected workflow result.")
    return {"passed": not errors, "errors": errors, "row_count": len(rows), "headers": headers, "rows": rows}
