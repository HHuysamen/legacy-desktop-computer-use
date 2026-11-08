from types import SimpleNamespace

import pytest

from ledgerdesk import desktop_app, workflows


class Widget:
    def __init__(self, value="", state="disabled"):
        self.value = value
        self.state = state

    def get(self):
        return self.value

    def set(self, value):
        self.value = value

    def configure(self, **kwargs):
        self.state = kwargs.get("state", self.state)


class Table:
    def __init__(self):
        self.rows = []

    def get_children(self):
        return tuple(range(len(self.rows)))

    def delete(self, *rows):
        self.rows = []

    def configure(self, **kwargs):
        pass

    def heading(self, *args, **kwargs):
        pass

    def column(self, *args, **kwargs):
        pass

    def insert(self, *args, **kwargs):
        self.rows.append(kwargs["values"])


def form(tmp_path):
    view = SimpleNamespace(
        db_path=tmp_path / "fixture.db", export_dir=tmp_path / "exports",
        entries={"invoice_number": Widget("INV-260916")}, _pending=None, _result=None,
        confirm_button=Widget(), export_button=Widget(), status=Widget(), table=Table(),
        operation="invoice-lookup",
    )
    view._operation_id = lambda: view.operation
    return view


def test_review_does_not_execute_or_export(tmp_path, monkeypatch):
    view = form(tmp_path)
    monkeypatch.setattr(workflows, "execute_workflow", lambda *args: pytest.fail("Review must not mutate data"))
    desktop_app.WorkflowDesk._review(view)
    assert view._pending == ("invoice-lookup", {"invoice_number": "INV-260916"})
    assert view.confirm_button.state == "normal"
    assert view.export_button.state == "disabled"


@pytest.mark.parametrize("change", ["field", "operation"])
def test_changing_reviewed_details_blocks_confirmation(tmp_path, monkeypatch, change):
    view = form(tmp_path)
    desktop_app.WorkflowDesk._review(view)
    if change == "field":
        view.entries["invoice_number"].value = "INV-260915"
    else:
        view.operation = "payment-entry"
    monkeypatch.setattr(workflows, "execute_workflow", lambda *args: pytest.fail("Stale review was executed"))
    desktop_app.WorkflowDesk._confirm(view)
    assert view.confirm_button.state == "disabled"
    assert view.export_button.state == "disabled"
    assert "Review" in view.status.value


def test_confirmation_consumed_once_and_export_enabled_only_after_success(tmp_path, monkeypatch):
    view = form(tmp_path)
    calls = []

    def execute(*args):
        calls.append(args)
        return ["invoice_number"], [{"invoice_number": "INV-260916"}]

    monkeypatch.setattr(workflows, "execute_workflow", execute)
    desktop_app.WorkflowDesk._review(view)
    desktop_app.WorkflowDesk._confirm(view)
    desktop_app.WorkflowDesk._confirm(view)
    assert len(calls) == 1
    assert view._pending is None
    assert view.confirm_button.state == "disabled"
    assert view.export_button.state == "normal"
    assert view.table.rows == [["INV-260916"]]


def test_failed_confirmation_cannot_export(tmp_path, monkeypatch):
    view = form(tmp_path)
    desktop_app.WorkflowDesk._review(view)

    def fail(*args):
        raise ValueError("Invalid payment")

    monkeypatch.setattr(workflows, "execute_workflow", fail)
    desktop_app.WorkflowDesk._confirm(view)
    assert view._pending is None
    assert view.export_button.state == "disabled"
    assert "Action failed" in view.status.value


def test_workflow_export_reports_write_failure_in_ui(tmp_path, monkeypatch):
    view = form(tmp_path)
    view._result = ("invoice-lookup", ["invoice_number"], [{"invoice_number": "INV-260916"}])

    def fail(*args):
        raise OSError("Output is unavailable")

    monkeypatch.setattr(desktop_app, "write_csv_export", fail)
    desktop_app.WorkflowDesk._export_workflow(view)
    assert "Export failed" in view.status.value

