from collections import Counter, defaultdict
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZIP_STORED, ZipFile

import pytest

from ledgerdesk import office_tasks as office
from ledgerdesk import robustness_fixtures as fixtures


CASES = [(task, split, index) for task in fixtures.TASK_IDS for split in fixtures.SPLITS for index in fixtures.INDICES]


def source_calc_rows(path):
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("content.xml"))
    table = root.find("office:body/office:spreadsheet/table:table", office.NS)
    return [
        [office._odf_text(cell.find("text:p", office.NS)) for cell in row.findall("table:table-cell", office.NS)]
        for row in table.findall("table:table-row", office.NS)
    ]


def export_sorted_calc(source, output):
    header, *rows = source_calc_rows(source)
    rows.sort(key=lambda row: (-Decimal(row[2]), row[0]))
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)


def export_replaced_writer(source, output, old, new, *, first_only=False, extra_edit=False):
    replacements = 0
    with ZipFile(source) as original, ZipFile(output, "w") as edited:
        for info in original.infolist():
            content = original.read(info)
            if info.filename == "content.xml":
                root = ET.fromstring(content)
                for element in root.iter():
                    if element.tag not in {office._q("text:p"), office._q("text:h")}:
                        continue
                    text = office._odf_text(element)
                    if not first_only or replacements == 0:
                        replacements += text.count(old)
                        text = text.replace(old, new, 1 if first_only else -1)
                    if extra_edit:
                        text = text.replace("Review due: 30 November", "Review due: 29 November")
                    for child in list(element):
                        element.remove(child)
                    element.text = text
                content = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            edited.writestr(info, content)


def writer_names(task, split, index):
    match = re.search(r"occurrence of '([^']+)' with '([^']+)'", fixtures.variant_instruction(task, split, index))
    return match.groups()


def test_manifest_freezes_twelve_distinct_inputs_and_twenty_four_geometry_pairs():
    first = fixtures.variant_manifest()
    assert first == fixtures.variant_manifest()
    assert first["fixture_count"] == len(first["fixtures"]) == 12
    assert first["measurement_count"] == len(first["cases"]) == 24
    assert len({row["input_sha256"] for row in first["fixtures"]}) == 12
    assert Counter((row["task_id"], row["split"]) for row in first["fixtures"]) == {
        (task, split): 3 for task in fixtures.TASK_IDS for split in fixtures.SPLITS
    }
    pairs = defaultdict(list)
    for case in first["cases"]:
        pairs[case["fixture_id"]].append(case)
    for pair in pairs.values():
        assert {case["geometry"] for case in pair} == {"normal", "changed"}
        assert len({case["input_sha256"] for case in pair}) == 1
        assert len({case["instruction_sha256"] for case in pair}) == 1
        assert all(case["control"] is None for case in pair)
    assert "heldout" in json.dumps(first)


@pytest.mark.parametrize("task,split,index", CASES)
def test_prepare_matches_frozen_manifest_and_is_geometry_independent(tmp_path, task, split, index):
    fixture_id = fixtures.variant_id(task, split, index)
    frozen = next(row for row in fixtures.variant_manifest()["fixtures"] if row["fixture_id"] == fixture_id)
    data = []
    for geometry in fixtures.GEOMETRIES:
        base = tmp_path / geometry
        command = fixtures.prepare_variant(task, split, index, base)
        source = Path(command[-1])
        assert source.name == office.OFFICE_TASKS[task]["input_name"]
        assert command[-2] == "--" + office.OFFICE_TASKS[task]["application"]
        content = source.read_bytes()
        assert hashlib.sha256(content).hexdigest() == frozen["input_sha256"]
        with ZipFile(source) as archive:
            assert archive.infolist()[0].filename == "mimetype"
            assert all(info.compress_type == ZIP_STORED for info in archive.infolist())
            assert archive.read("content.xml").isascii()
        data.append(content)
    assert data[0] == data[1]


@pytest.mark.parametrize("split,index", [(split, index) for split in fixtures.SPLITS for index in fixtures.INDICES])
def test_calc_variants_have_matched_structure_ties_and_correct_oracle(tmp_path, split, index):
    task = "calc-sort-export"
    source = Path(fixtures.prepare_variant(task, split, index, tmp_path)[-1])
    header, *rows = source_calc_rows(source)
    assert header == office.CALC_HEADERS
    assert len(rows) == 8
    assert len({row[0] for row in rows}) == 8
    counts = sorted(Counter(row[2] for row in rows).values())
    assert counts == [1, 1, 1, 1, 1, 1, 2]
    assert sum(Decimal(row[2]) == 0 for row in rows) == 1
    assert max(Decimal(row[2]) for row in rows) >= 10000
    assert rows != sorted(rows, key=lambda row: (-Decimal(row[2]), row[0]))
    assert all(value.isascii() and len(value) < 100 for row in rows for value in row)
    output = tmp_path / "export.csv"
    export_sorted_calc(source, output)
    assert fixtures.verify_variant(output, task, split, index)["passed"]
    # The correct result is not interchangeable with another fixed input.
    assert not fixtures.verify_variant(output, task, split, (index + 1) % 3)["passed"]


def test_heldout_calc_identifiers_and_customer_names_are_unseen_in_development(tmp_path):
    observed = {}
    for split in fixtures.SPLITS:
        identifiers, names = set(), set()
        for index in fixtures.INDICES:
            source = Path(fixtures.prepare_variant("calc-sort-export", split, index, tmp_path / split / str(index))[-1])
            for row in source_calc_rows(source)[1:]:
                identifiers.add(row[0])
                names.add(row[1])
        observed[split] = (identifiers, names)
    assert observed["development"][0].isdisjoint(observed["heldout"][0])
    assert observed["development"][1].isdisjoint(observed["heldout"][1])


@pytest.mark.parametrize("split,index", [(split, index) for split in fixtures.SPLITS for index in fixtures.INDICES])
def test_writer_variants_have_five_targets_near_matches_and_preserved_structure(tmp_path, split, index):
    task = "writer-find-replace"
    source = Path(fixtures.prepare_variant(task, split, index, tmp_path)[-1])
    original = source.read_bytes()
    old, new = writer_names(task, split, index)
    with ZipFile(source) as archive:
        document = ET.fromstring(archive.read("content.xml"))
    source_rows = office._writer_rows(document)
    assert len(source_rows) == 16
    assert sum(row["text"].count(old) for row in source_rows) == 5
    assert all(row["text"].isascii() for row in source_rows)
    assert len(old) < 100 and len(new) < 100
    assert not fixtures.verify_variant(source, task, split, index)["passed"]
    output = tmp_path / "edited.odt"
    export_replaced_writer(source, output, old, new)
    result = fixtures.verify_variant(output, task, split, index)
    assert result["passed"], result["errors"]
    assert [row["section"] for row in result["rows"]] == [row["section"] for row in source_rows]
    assert sum(row["text"].count(new) for row in result["rows"]) == 5
    assert source.read_bytes() == original
    assert not fixtures.verify_variant(output, task, split, (index + 1) % 3)["passed"]


@pytest.mark.parametrize("mistake", ["partial", "unrelated"])
def test_writer_oracle_rejects_partial_replacement_and_unrelated_changes(tmp_path, mistake):
    task, split, index = "writer-find-replace", "heldout", 0
    source = Path(fixtures.prepare_variant(task, split, index, tmp_path)[-1])
    old, new = writer_names(task, split, index)
    output = tmp_path / "bad.odt"
    export_replaced_writer(source, output, old, new, first_only=mistake == "partial", extra_edit=mistake == "unrelated")
    assert not fixtures.verify_variant(output, task, split, index)["passed"]


def test_calc_oracle_rejects_changed_row_values(tmp_path):
    task, split, index = "calc-sort-export", "development", 1
    source = Path(fixtures.prepare_variant(task, split, index, tmp_path)[-1])
    header, *rows = source_calc_rows(source)
    rows.sort(key=lambda row: (-Decimal(row[2]), row[0]))
    rows[0][1] = "Wrong Customer"
    output = tmp_path / "bad.csv"
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerows([header, *rows])
    assert not fixtures.verify_variant(output, task, split, index)["passed"]


@pytest.mark.parametrize("task,split,index", [
    ("unknown", "development", 0), ("calc-sort-export", "dev", 0),
    ("calc-sort-export", "heldout", -1), ("writer-find-replace", "heldout", 3),
    ("writer-find-replace", "heldout", True),
])
def test_invalid_variant_refused_before_files_are_created(tmp_path, task, split, index):
    base = tmp_path / "absent"
    with pytest.raises(ValueError):
        fixtures.prepare_variant(task, split, index, base)
    assert not base.exists()


def test_source_symlink_is_not_followed(tmp_path):
    outside = tmp_path / "retain.txt"
    outside.write_text("unchanged")
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "calc-source.ods").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        fixtures.prepare_variant("calc-sort-export", "development", 0, tmp_path)
    assert outside.read_text() == "unchanged"
