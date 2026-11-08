import csv
from decimal import Decimal
import hashlib
from xml.etree import ElementTree as ET
from zipfile import ZIP_STORED, ZipFile

import pytest

from ledgerdesk import office_tasks as office


def calc_export(path, rows=None, headers=None):
    if rows is None:
        rows = sorted(office.CALC_ROWS, key=lambda row: (-Decimal(row[2]), row[0]))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers or office.CALC_HEADERS)
        writer.writerows(rows)


def edit_writer(source, destination, transform):
    with ZipFile(source) as original, ZipFile(destination, "w") as edited:
        for info in original.infolist():
            data = original.read(info)
            if info.filename == "content.xml":
                root = ET.fromstring(data)
                for element in root.iter():
                    if element.tag in {office._q("text:p"), office._q("text:h")}:
                        text = office._odf_text(element)
                        for child in list(element):
                            element.remove(child)
                        element.text = transform(text)
                data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            edited.writestr(info, data)


@pytest.mark.parametrize("task_id", list(office.OFFICE_TASKS))
def test_prepare_creates_valid_deterministic_odf_and_real_app_command(tmp_path, task_id):
    first = office.prepare_office(task_id, tmp_path)
    assert first[:4] == ["libreoffice", "--norestore", "--nodefault", "--nofirststartwizard"]
    assert first[-2] == "--" + office.OFFICE_TASKS[task_id]["application"]
    source = tmp_path / "inputs" / office.OFFICE_TASKS[task_id]["input_name"]
    assert first[-1] == str(source)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    with ZipFile(source) as archive:
        assert archive.infolist()[0].filename == "mimetype"
        assert archive.infolist()[0].compress_type == ZIP_STORED
        for name in ("content.xml", "styles.xml", "META-INF/manifest.xml"):
            ET.fromstring(archive.read(name))
    export = tmp_path / "exports" / office.OFFICE_TASKS[task_id]["output_name"]
    export.write_text("stale result")
    other = tmp_path / "exports" / "other.csv"
    other.write_text("retain me")
    assert office.prepare_office(task_id, tmp_path) == first
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    assert not export.exists()
    assert other.read_text() == "retain me"


def test_prepare_rejects_unknown_task_before_creating_files(tmp_path):
    base = tmp_path / "not-created"
    with pytest.raises(ValueError, match="Unknown office task"):
        office.prepare_office("../outside", base)
    assert not base.exists()


def test_calc_numeric_sort_and_preserved_rows_pass(tmp_path):
    output = tmp_path / "sorted.csv"
    calc_export(output)
    result = office.verify_office("calc-sort-export", output)
    assert result["passed"]
    assert result["row_count"] == 8
    assert [row["invoice_id"] for row in result["rows"]] == [
        "INV-003", "INV-001", "INV-005", "INV-006", "INV-008", "INV-002", "INV-007", "INV-004",
    ]


def test_calc_accepts_same_numeric_value_with_calc_display_precision(tmp_path):
    output = tmp_path / "sorted.csv"
    rows = sorted(office.CALC_ROWS, key=lambda row: (-Decimal(row[2]), row[0]))
    rows = [(*row[:2], str(Decimal(row[2]).normalize()), *row[3:]) for row in rows]
    # Calc can omit trailing zeros; plain decimal CSV forms are equivalent.
    rows = [(*row[:2], format(Decimal(row[2]), "f"), *row[3:]) for row in rows]
    calc_export(output, rows)
    assert office.verify_office("calc-sort-export", output)["passed"]


@pytest.mark.parametrize("mistake", ["unsorted", "lexical", "tie", "only-amounts", "missing", "duplicate", "extra-column", "amount", "customer"])
def test_calc_rejects_wrong_sort_or_changed_cells(tmp_path, mistake):
    rows = [list(row) for row in sorted(office.CALC_ROWS, key=lambda row: (-Decimal(row[2]), row[0]))]
    headers = list(office.CALC_HEADERS)
    if mistake == "unsorted":
        rows = list(office.CALC_ROWS)
    elif mistake == "lexical":
        rows.sort(key=lambda row: row[2], reverse=True)
    elif mistake == "tie":
        rows[1], rows[2] = rows[2], rows[1]
    elif mistake == "only-amounts":
        balances = [row[2] for row in rows]
        rows = [list(row) for row in office.CALC_ROWS]
        for row, balance in zip(rows, balances):
            row[2] = balance
    elif mistake == "missing":
        rows.pop()
    elif mistake == "duplicate":
        rows[-1] = rows[0]
    elif mistake == "extra-column":
        headers.append("extra")
    elif mistake == "amount":
        rows[0][2] = "10000.01"
    else:
        rows[0][1] = "Changed customer"
    output = tmp_path / "bad.csv"
    calc_export(output, rows, headers)
    result = office.verify_office("calc-sort-export", output)
    assert not result["passed"]
    assert result["errors"]


def test_writer_all_replacements_with_other_content_preserved_pass(tmp_path):
    command = office.prepare_office("writer-find-replace", tmp_path)
    source = tmp_path / "inputs" / "writer-source.odt"
    original = source.read_bytes()
    output = tmp_path / "edited.odt"
    edit_writer(source, output, lambda text: text.replace(office.OLD_COMPANY, office.NEW_COMPANY))
    result = office.verify_office("writer-find-replace", output)
    assert result["passed"], result["errors"]
    assert result["headers"] == ["section", "text"]
    assert sum(row["text"].count(office.NEW_COMPANY) for row in result["rows"]) == 5
    assert any("Harbour Systems and Harbor System" in row["text"] for row in result["rows"])
    assert source.read_bytes() == original
    assert command[-1] == str(source)


@pytest.mark.parametrize("mistake", ["none", "partial", "similar-name", "amount", "deleted-text"])
def test_writer_rejects_incomplete_or_excessive_edits(tmp_path, mistake):
    office.prepare_office("writer-find-replace", tmp_path)
    source = tmp_path / "inputs" / "writer-source.odt"
    output = tmp_path / "bad.odt"

    def transform(text):
        if mistake == "none":
            return text
        if mistake == "partial":
            return text.replace(office.OLD_COMPANY, office.NEW_COMPANY, 1)
        changed = text.replace(office.OLD_COMPANY, office.NEW_COMPANY)
        if mistake == "similar-name":
            return changed.replace("Harbour Systems", office.NEW_COMPANY)
        if mistake == "amount":
            return changed.replace("12,500.50", "12,500.51")
        return "" if text.startswith("Prepared on") else changed

    edit_writer(source, output, transform)
    assert not office.verify_office("writer-find-replace", output)["passed"]


@pytest.mark.parametrize("task_id", list(office.OFFICE_TASKS))
def test_missing_output_and_wrong_file_format_fail(tmp_path, task_id):
    output = tmp_path / "missing"
    assert not office.verify_office(task_id, output)["passed"]
    output.write_text("not the requested office output")
    assert not office.verify_office(task_id, output)["passed"]


def test_writer_span_boundaries_do_not_hide_the_old_name(tmp_path):
    office.prepare_office("writer-find-replace", tmp_path)
    source = tmp_path / "inputs" / "writer-source.odt"
    with ZipFile(source) as archive:
        root = ET.fromstring(archive.read("content.xml"))
    rows = office._writer_rows(root)
    assert sum(row["text"].count(office.OLD_COMPANY) for row in rows) == 5
    assert not office.verify_office("writer-find-replace", source)["passed"]


def test_instructions_name_the_real_apps_and_fixed_exports():
    for task_id, task in office.OFFICE_TASKS.items():
        instruction = office.office_instruction(task_id)
        assert "LibreOffice" in instruction
        assert f"/tmp/ledgerdesk/exports/{task['output_name']}" in instruction
    with pytest.raises(ValueError, match="Unknown office task"):
        office.office_instruction("unknown")
