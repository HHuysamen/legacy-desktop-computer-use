"""Frozen Office input variants and trusted oracles for the paired study.

Geometry is intentionally absent from fixture generation. Every normal/changed
pair receives identical input bytes, instructions and expected output.
"""

from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZIP_STORED, ZipFile, ZipInfo

from . import office_tasks as office


PROTOCOL = "office-robustness-v1"
SPLITS = ("development", "heldout")
INDICES = (0, 1, 2)
GEOMETRIES = ("normal", "changed")
TASK_IDS = tuple(office.OFFICE_TASKS)

# One tie pair, one zero, fractional cents, and a five-digit maximum per file.
# Row order, tie positions and the numerical values vary without changing size.
_AMOUNTS = (
    (235075, 5000, 1250000, 0, 235075, 99999, 950, 10000),
    (0, 1499999, 80505, 750000, 1200, 750000, 6800, 99999),
    (4500, 149999, 275050, 275050, 1000000, 0, 999, 89000),
    (0, 1350000, 345075, 990, 6000, 345075, 89999, 20000),
    (850000, 1300, 0, 1599999, 850000, 70606, 7800, 99998),
    (1001, 375050, 0, 1199999, 189999, 5500, 375050, 99000),
)
_CUSTOMERS = {
    "development": (
        "Aster Components", "Maple Distribution", "Summit Workshop", "Amber Fabrication",
        "Cobalt Supply", "Juniper Research", "Willow Devices", "Cedar Instruments",
    ),
    "heldout": (
        "Elm Components", "Birch Distribution", "Orion Workshop", "Topaz Fabrication",
        "Indigo Supply", "Aspen Research", "Hazel Devices", "Larch Instruments",
    ),
}
_WRITER_NAMES = (
    ("Aster Systems", "Summit Devices", "Aster System", "Astor Systems"),
    ("Cobalt Works", "Maple Devices", "Cobalt Work", "Cobolt Works"),
    ("Juniper Labs", "Atlas Devices", "Juniper Lab", "Juniper Labx"),
    ("Willow Systems", "Beacon Devices", "Willow System", "Wallow Systems"),
    ("Harbor Tools", "Acorn Devices", "Harbour Tools", "Harbor Tool"),
    ("Cedar Works", "Orbit Devices", "Cedars Works", "Cedar Work"),
)
_OWNERS = (
    ("Mara Chen", "Elias Vale"), ("Nina Cole", "Tomas Reed"), ("Ava Stone", "Leo Finch"),
    ("Mila Hart", "Owen Lake"), ("Lina West", "Adam Grove"), ("Eva Marsh", "Noah Brook"),
)


def _number(task_id: str, split: str, index: int) -> int:
    if task_id not in TASK_IDS:
        raise ValueError(f"Unknown robustness task: {task_id}")
    if split not in SPLITS:
        raise ValueError("Split must be development or heldout.")
    if type(index) is not int or index not in INDICES:
        raise ValueError("Fixture index must be 0, 1 or 2.")
    return index + (3 if split == "heldout" else 0)


def variant_id(task_id: str, split: str, index: int) -> str:
    _number(task_id, split, index)
    return f"{task_id}-{split}-{index:02d}"


def _calc_rows(split: str, index: int) -> tuple[tuple[str, ...], ...]:
    number = _number("calc-sort-export", split, index)
    prefix = f"{'DV' if split == 'development' else 'HO'}{index + 1}"
    identifiers = (8, 2, 7, 4, 3, 6, 1, 5)
    return tuple(
        (
            f"{prefix}-{identifier:03d}",
            _CUSTOMERS[split][(row + number) % len(_CUSTOMERS[split])],
            f"{cents // 100}.{cents % 100:02d}",
            f"2026-11-{(1, 2, 3, 4, 5, 12, 15, 16)[row]:02d}",
            "settled" if cents == 0 else ("partial" if row % 3 == 1 else "open"),
        )
        for row, (identifier, cents) in enumerate(zip(identifiers, _AMOUNTS[number]))
    )


def _writer_blocks(split: str, index: int) -> tuple:
    number = _number("writer-find-replace", split, index)
    old, _new, near_one, near_two = _WRITER_NAMES[number]
    owner, reviewer = _OWNERS[number]
    reference = f"{'DEV' if split == 'development' else 'HLD'}-{index + 1:03d}-2026"
    return (
        ("heading:1", "Supplier handover memo"),
        ("paragraph", f"Prepared on 8 November 2026. Case {reference}. All figures below are synthetic."),
        ("heading:2", "Supplier overview"),
        ("paragraph", f"{old} is the primary supplier. {old} owns the quarterly delivery plan."),
        ("paragraph", f"{near_one} and {near_two} are different suppliers; leave those names unchanged."),
        ("paragraph", f"Recorded balance: USD {12500 + number * 137:,}.50. Review due: 30 November 2026."),
        ("table", (
            ("Supplier", "Owner", "Action"),
            (old, owner, f"Confirm {18 + number} components"),
            (old, reviewer, "Keep existing due date"),
        )),
        ("paragraph", f"Escalations for {old} go to {owner}. Reference: {reference}."),
    )


def _calc_xml(split: str, index: int) -> bytes:
    # Reuse only the ODF template/styles, never its fixed expected report values.
    root = ET.fromstring(office._calc_content())
    sheet = root.find("office:body/office:spreadsheet/table:table", office.NS)
    for line, values in zip(sheet.findall("table:table-row", office.NS)[1:], _calc_rows(split, index)):
        for column, (cell, value) in enumerate(zip(line.findall("table:table-cell", office.NS), values)):
            cell.find("text:p", office.NS).text = value
            if column == 2:
                cell.set(office._q("office:value"), value)
    return office._xml(root)


def _writer_xml(split: str, index: int) -> bytes:
    number = _number("writer-find-replace", split, index)
    old = _WRITER_NAMES[number][0]
    root = office._document_root("office:document-content")
    body = office._node(office._node(root, "office:body"), "office:text")
    for kind, value in _writer_blocks(split, index):
        if kind == "table":
            table = office._node(body, "table:table", {"table:name": "Action register"})
            office._node(table, "table:table-column", {"table:number-columns-repeated": "3"})
            for row in value:
                line = office._node(table, "table:table-row")
                for text in row:
                    cell = office._node(line, "table:table-cell", {"office:value-type": "string"})
                    office._node(cell, "text:p", text=text)
        elif kind.startswith("heading:"):
            level = kind.split(":")[1]
            office._node(body, "text:h", {"text:outline-level": level, "text:style-name": "Title" if level == "1" else "Heading"}, value)
        else:
            paragraph = office._node(body, "text:p", {"text:style-name": "Body"}, value)
            if value.startswith(old):
                first, last = old.rsplit(" ", 1)
                paragraph.text = first + " "
                span = office._node(paragraph, "text:span", text=last)
                span.tail = value[len(old):]
    return office._xml(root)


def _input_bytes(task_id: str, split: str, index: int) -> bytes:
    _number(task_id, split, index)
    is_calc = task_id == "calc-sort-export"
    media_type = "application/vnd.oasis.opendocument.spreadsheet" if is_calc else "application/vnd.oasis.opendocument.text"
    content = _calc_xml(split, index) if is_calc else _writer_xml(split, index)
    manifest = ET.Element(office._q("manifest:manifest"), {office._q("manifest:version"): "1.3"})
    for name, kind in (("/", media_type), ("content.xml", "text/xml"), ("styles.xml", "text/xml")):
        office._node(manifest, "manifest:file-entry", {"manifest:full-path": name, "manifest:media-type": kind})
    files = (("mimetype", media_type.encode("ascii")), ("content.xml", content),
             ("styles.xml", office._styles()), ("META-INF/manifest.xml", office._xml(manifest)))
    output = io.BytesIO()
    # Stored entries avoid compression-library version differences in hashes.
    with ZipFile(output, "w") as archive:
        for name, data in files:
            info = ZipInfo(name, date_time=(2026, 11, 8, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=ZIP_STORED)
    return output.getvalue()


def prepare_variant(task_id: str, split: str, index: int, base_dir: Path = Path("/tmp/ledgerdesk")) -> list[str]:
    """Create one frozen input; geometry changes belong only to the controller."""
    content = _input_bytes(task_id, split, index)
    task = office.OFFICE_TASKS[task_id]
    base_dir = Path(base_dir)
    inputs, exports = base_dir / "inputs", base_dir / "exports"
    inputs.mkdir(parents=True, exist_ok=True)
    exports.mkdir(parents=True, exist_ok=True)
    source = inputs / task["input_name"]
    if source.is_symlink():
        raise ValueError("Fixture source must not be a symlink.")
    source.write_bytes(content)
    (exports / task["output_name"]).unlink(missing_ok=True)
    return ["libreoffice", "--norestore", "--nodefault", "--nofirststartwizard", f"--{task['application']}", str(source)]


def variant_instruction(task_id: str, split: str, index: int) -> str:
    number = _number(task_id, split, index)
    if task_id == "calc-sort-export":
        return (
            "The supplied receivables spreadsheet is open in LibreOffice Calc. Sort the entire table "
            "by outstanding_balance numerically descending, then invoice_id ascending for ties. "
            "Keep the header first and preserve every row and every other cell value. Export the sorted "
            "sheet as a UTF-8, comma-separated CSV to /tmp/ledgerdesk/exports/calc-sort-export.csv. "
            "Use the application's normal controls and confirm the CSV format if asked. Do not overwrite the source ODS."
        )
    old, new, near_one, near_two = _WRITER_NAMES[number]
    return (
        f"The supplied supplier handover memo is open in LibreOffice Writer. Replace every exact "
        f"occurrence of '{old}' with '{new}', including occurrences in the table. "
        f"Do not change the similar names '{near_one}' or '{near_two}', or any other text, "
        "numbers, paragraph order or table content. Save the edited document as OpenDocument Text "
        "to /tmp/ledgerdesk/exports/writer-find-replace.odt, leaving the source ODT unchanged."
    )


def _expected_rows(task_id: str, split: str, index: int) -> tuple[list[str], list[dict]]:
    number = _number(task_id, split, index)
    if task_id == "calc-sort-export":
        ordered = sorted(_calc_rows(split, index), key=lambda row: (-Decimal(row[2]), row[0]))
        return list(office.CALC_HEADERS), [dict(zip(office.CALC_HEADERS, row)) for row in ordered]
    old, new, _near_one, _near_two = _WRITER_NAMES[number]
    rows = []
    for block, (kind, value) in enumerate(_writer_blocks(split, index), 1):
        if kind == "table":
            for row, cells in enumerate(value, 1):
                for column, text in enumerate(cells, 1):
                    rows.append({"section": f"{block}:table:{row}:{column}", "text": text.replace(old, new)})
        else:
            rows.append({"section": f"{block}:{kind}", "text": value.replace(old, new)})
    return ["section", "text"], rows


def verify_variant(output: Path, task_id: str, split: str, index: int) -> dict:
    """Compare saved content to immutable fixture values, without Office tools."""
    expected_headers, expected = _expected_rows(task_id, split, index)
    headers, rows, errors = [], [], []
    try:
        output = Path(output)
        if output.stat().st_size > 10_000_000:
            raise ValueError("Output exceeds the fixture size limit.")
        if task_id == "calc-sort-export":
            with output.open(newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream, strict=True)
                headers, rows = reader.fieldnames or [], list(reader)
            normalized = []
            for row in rows:
                value = row.get("outstanding_balance", "")
                if not isinstance(value, str) or not re.fullmatch(r"-?\d+(?:\.\d{1,2})?", value):
                    raise ValueError("Invalid balance in CSV output.")
                normalized.append(dict(row, outstanding_balance=format(Decimal(value), ".2f")))
        else:
            with ZipFile(output) as archive:
                if archive.read("mimetype") != b"application/vnd.oasis.opendocument.text":
                    raise ValueError("Expected an OpenDocument Text output.")
                info = archive.getinfo("content.xml")
                if info.file_size > 1_000_000:
                    raise ValueError("ODT content exceeds the fixture size limit.")
                content = archive.read(info)
            if b"<!DOCTYPE" in content or b"<!ENTITY" in content:
                raise ValueError("ODT document declarations are not allowed.")
            headers = ["section", "text"]
            rows = normalized = office._writer_rows(ET.fromstring(content))
        if headers != expected_headers:
            errors.append("Output columns differ from the expected schema.")
        if normalized != expected:
            errors.append("Output values, row order or document structure differ from the required result.")
    except (OSError, UnicodeError, csv.Error, BadZipFile, ET.ParseError, KeyError, ValueError, OverflowError, InvalidOperation) as error:
        errors.append(f"Cannot verify variant output: {error}")
    return {"passed": not errors, "errors": errors, "headers": headers, "rows": rows, "row_count": len(rows)}


def variant_manifest() -> dict:
    """Return all twelve frozen inputs and their twenty-four matched cases."""
    fixtures, cases = [], []
    for task_id in TASK_IDS:
        task = office.OFFICE_TASKS[task_id]
        for split in SPLITS:
            for index in INDICES:
                identifier = variant_id(task_id, split, index)
                expected_headers, expected_rows = _expected_rows(task_id, split, index)
                expectation = json.dumps({"headers": expected_headers, "rows": expected_rows}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
                hashes = {
                    "input_sha256": hashlib.sha256(_input_bytes(task_id, split, index)).hexdigest(),
                    "instruction_sha256": hashlib.sha256(variant_instruction(task_id, split, index).encode("ascii")).hexdigest(),
                    "expected_sha256": hashlib.sha256(expectation.encode("ascii")).hexdigest(),
                }
                identity = {"fixture_id": identifier, "task_id": task_id, "split": split, "fixture_index": index}
                fixtures.append({**identity, "input_name": task["input_name"], "output_name": task["output_name"], **hashes})
                for geometry in GEOMETRIES:
                    cases.append({**identity, "case_id": f"{identifier}-{geometry}", "geometry": geometry, "control": None,
                                  "input_sha256": hashes["input_sha256"], "instruction_sha256": hashes["instruction_sha256"]})
    return {"schema_version": 1, "protocol": PROTOCOL, "fixture_count": len(fixtures), "measurement_count": len(cases), "fixtures": fixtures, "cases": cases}
