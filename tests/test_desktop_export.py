import csv
from types import SimpleNamespace

import pytest

from ledgerdesk.desktop_app import LedgerDesk, write_csv_export


def test_export_preserves_csv_quoting_and_uses_fixed_filename(tmp_path):
    rows = [{"customer": 'Fictional, "North" Ltd', "revenue": "12.34"}]
    result = write_csv_export(tmp_path / "exports", "monthly-revenue", ["customer", "revenue"], rows)
    assert result.name == "monthly-revenue.csv"
    with result.open(newline="", encoding="utf-8") as stream:
        assert list(csv.DictReader(stream)) == rows


def test_export_replaces_destination_symlink_without_writing_target(tmp_path):
    original = tmp_path / "untouched.txt"
    original.write_text("unchanged", encoding="utf-8")
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    destination = export_dir / "monthly-revenue.csv"
    destination.symlink_to(original)
    write_csv_export(export_dir, "monthly-revenue", ["customer", "revenue"], [])
    assert original.read_text(encoding="utf-8") == "unchanged"
    assert not destination.is_symlink()
    assert destination.read_text(encoding="utf-8") == "customer,revenue\n"


def test_export_rejects_arbitrary_paths(tmp_path):
    with pytest.raises(ValueError, match="Unknown report"):
        write_csv_export(tmp_path, "../outside", [], [])
    assert not (tmp_path.parent / "outside.csv").exists()


def test_export_confirmation_requires_a_current_preview():
    class Value:
        def __init__(self, value=""):
            self.value = value

        def set(self, value):
            self.value = value

    class Button:
        state = "disabled"

        def configure(self, *, state):
            self.state = state

    view = SimpleNamespace(
        _result=None,
        _parameter_signature="current",
        _signature=lambda: "current",
        export_filename=Value(),
        save_button=Button(),
        cancel_button=Button(),
        status=Value(),
    )
    LedgerDesk._show_export(view)
    assert view.save_button.state == "disabled"
    view._result = ("monthly-revenue", ["customer", "revenue"], [])
    LedgerDesk._show_export(view)
    assert view.save_button.state == "normal"
    assert "monthly-revenue.csv" in view.export_filename.value
    LedgerDesk._hide_export(view)
    assert view.save_button.state == view.cancel_button.state == "disabled"
