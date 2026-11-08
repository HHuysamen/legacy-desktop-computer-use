"""Plain-language tasks supplied to the screenshot-only agent."""

from datetime import date

DEFAULT_AS_OF = "2026-10-15"
DEFAULT_MONTH = "2026-09"
DEFAULT_TOLERANCE = "0.01"


def task_instruction(report_id: str, as_of: str = DEFAULT_AS_OF) -> str:
    if report_id == "monthly-revenue":
        return (
            "In LedgerDesk, generate Monthly revenue for September 2026, grouped by customer "
            "and sorted by revenue descending (customer name ascending for ties). "
            "Use invoice-date net amounts, excluding voided invoices. Export the result as CSV."
        )
    if report_id == "overdue-invoices":
        if date.fromisoformat(as_of).isoformat() != as_of:
            raise ValueError("As-of date must use YYYY-MM-DD.")
        return (
            f"In LedgerDesk, generate Overdue invoices as of {as_of}. Include issued invoices "
            "with an outstanding balance and a due date strictly before that date, including "
            "partially paid invoices. Include customer, invoice number, balance, due date and "
            "days overdue. Sort by due date, then invoice number, ascending. Export as CSV."
        )
    if report_id == "reconciliation-exceptions":
        return (
            "In LedgerDesk, generate Reconciliation exceptions with a tolerance of 0.01. "
            "Include transactions whose absolute difference is strictly greater than the "
            "tolerance. Show transaction ID, recorded amount, expected amount and signed "
            "difference (recorded minus expected), sorted by transaction ID ascending. Export as CSV."
        )
    raise ValueError(f"Unknown report: {report_id}")
