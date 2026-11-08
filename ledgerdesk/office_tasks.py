"""Trusted fixtures and output checks for unmodified LibreOffice applications.

Only the task instructions reach the model. Preparing files and reading the
exports are controller operations, never agent tools.
"""

from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo


OFFICE_TASKS = {
    "calc-sort-export": {
        "name": "LibreOffice Calc: sort and export receivables",
        "application": "calc",
        "input_name": "calc-source.ods",
        "output_name": "calc-sort-export.csv",
    },
    "writer-find-replace": {
        "name": "LibreOffice Writer: replace a supplier name",
        "application": "writer",
        "input_name": "writer-source.odt",
        "output_name": "writer-find-replace.odt",
    },
}

CALC_HEADERS = ["invoice_id", "customer", "outstanding_balance", "due_date", "status"]
CALC_ROWS = (
    ("INV-001", "Northstar Manufacturing", "1234.50", "2026-10-01", "open"),
    ("INV-002", "Cedar Services", "50.00", "2026-10-02", "partial"),
    ("INV-003", "Northstar Manufacturing", "10000.00", "2026-10-03", "open"),
    ("INV-004", "Harbor Supply", "0.00", "2026-10-04", "settled"),
    ("INV-005", "Amber Research", "1234.50", "2026-09-29", "open"),
    ("INV-006", "Cedar Services", "999.99", "2026-10-12", "partial"),
    ("INV-007", "Beacon Tools", "9.50", "2026-10-15", "open"),
    ("INV-008", "Beacon Tools", "100.00", "2026-10-15", "open"),
)
OLD_COMPANY = "Harbor Systems"
NEW_COMPANY = "Northstar Devices"
WRITER_BLOCKS = (
    ("heading:1", "Supplier handover memo"),
    ("paragraph", "Prepared on 8 November 2026. All figures below are synthetic."),
    ("heading:2", "Supplier overview"),
    ("paragraph", "Harbor Systems is the primary supplier. Harbor Systems owns the quarterly delivery plan."),
    ("paragraph", "Harbour Systems and Harbor System are different suppliers; leave those names unchanged."),
    ("paragraph", "Recorded balance: USD 12,500.50. Review due: 30 November 2026."),
    ("table", (
        ("Supplier", "Owner", "Action"),
        ("Harbor Systems", "Mina Patel", "Confirm 18 components"),
        ("Harbor Systems", "Jonas Lind", "Keep existing due date"),
    )),
    ("paragraph", "Escalations for Harbor Systems go to Mina Patel. Reference: HS-2026-11."),
)

NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "number": "urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "manifest": "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0",
}
for _prefix, _namespace in NS.items():
    ET.register_namespace(_prefix, _namespace)


def _q(name: str) -> str:
    prefix, local = name.split(":", 1)
    return f"{{{NS[prefix]}}}{local}"


def _node(parent, tag: str, attributes: dict | None = None, text: str | None = None):
    element = ET.SubElement(parent, _q(tag), {_q(k): v for k, v in (attributes or {}).items()})
    element.text = text
    return element


def _xml(element) -> bytes:
    return ET.tostring(element, encoding="utf-8", xml_declaration=True)


def _document_root(tag: str):
    return ET.Element(_q(tag), {_q("office:version"): "1.3"})


def _styles() -> bytes:
    root = _document_root("office:document-styles")
    styles = _node(root, "office:styles")
    for name, size in (("Body", "11pt"), ("Title", "18pt"), ("Heading", "14pt")):
        style = _node(styles, "style:style", {"style:name": name, "style:family": "paragraph"})
        _node(style, "style:paragraph-properties", {"fo:margin-bottom": "0.2cm"})
        _node(style, "style:text-properties", {
            "fo:font-family": "Liberation Sans", "fo:font-size": size,
            "fo:font-weight": "normal" if name == "Body" else "bold",
        })
    return _xml(root)


def _write_package(path: Path, media_type: str, content: bytes) -> None:
    manifest = ET.Element(_q("manifest:manifest"), {_q("manifest:version"): "1.3"})
    for name, kind in (("/", media_type), ("content.xml", "text/xml"), ("styles.xml", "text/xml")):
        _node(manifest, "manifest:file-entry", {"manifest:full-path": name, "manifest:media-type": kind})
    files = (("mimetype", media_type.encode()), ("content.xml", content),
             ("styles.xml", _styles()), ("META-INF/manifest.xml", _xml(manifest)))
    with ZipFile(path, "w") as archive:
        for name, data in files:
            info = ZipInfo(name, date_time=(2026, 11, 8, 0, 0, 0))
            archive.writestr(info, data, compress_type=ZIP_STORED if name == "mimetype" else ZIP_DEFLATED)


def _calc_content() -> bytes:
    root = _document_root("office:document-content")
    styles = _node(root, "office:automatic-styles")
    money = _node(styles, "number:number-style", {"style:name": "Money"})
    _node(money, "number:number", {"number:decimal-places": "2", "number:min-integer-digits": "1", "number:grouping": "false"})
    amount = _node(styles, "style:style", {"style:name": "Amount", "style:family": "table-cell", "style:data-style-name": "Money"})
    _node(amount, "style:paragraph-properties", {"fo:text-align": "end"})
    heading = _node(styles, "style:style", {"style:name": "Header", "style:family": "table-cell"})
    _node(heading, "style:text-properties", {"fo:font-weight": "bold"})
    _node(heading, "style:table-cell-properties", {"fo:background-color": "#dce6f1"})
    for index, width in enumerate(("2.8cm", "5.6cm", "4cm", "3cm", "3cm")):
        style = _node(styles, "style:style", {"style:name": f"Column{index}", "style:family": "table-column"})
        _node(style, "style:table-column-properties", {"style:column-width": width})
    sheet = _node(_node(_node(root, "office:body"), "office:spreadsheet"), "table:table", {"table:name": "Receivables"})
    for index in range(len(CALC_HEADERS)):
        _node(sheet, "table:table-column", {"table:style-name": f"Column{index}"})
    for row_index, row in enumerate((CALC_HEADERS, *CALC_ROWS)):
        line = _node(sheet, "table:table-row")
        for column, value in enumerate(row):
            attributes = {"office:value-type": "string"}
            if row_index == 0:
                attributes["table:style-name"] = "Header"
            elif column == 2:
                attributes.update({"office:value-type": "float", "office:value": value, "table:style-name": "Amount"})
            cell = _node(line, "table:table-cell", attributes)
            _node(cell, "text:p", text=value)
    return _xml(root)


def _writer_content() -> bytes:
    root = _document_root("office:document-content")
    body = _node(_node(root, "office:body"), "office:text")
    for kind, value in WRITER_BLOCKS:
        if kind == "table":
            table = _node(body, "table:table", {"table:name": "Action register"})
            _node(table, "table:table-column", {"table:number-columns-repeated": "3"})
            for row in value:
                line = _node(table, "table:table-row")
                for text in row:
                    _node(_node(line, "table:table-cell", {"office:value-type": "string"}), "text:p", text=text)
        elif kind.startswith("heading:"):
            level = kind.split(":")[1]
            _node(body, "text:h", {"text:outline-level": level, "text:style-name": "Title" if level == "1" else "Heading"}, value)
        else:
            paragraph = _node(body, "text:p", {"text:style-name": "Body"}, value)
            if value.startswith(OLD_COMPANY):
                # A real phrase may cross XML spans even though it is contiguous on screen.
                paragraph.text = "Harbor "
                span = _node(paragraph, "text:span", text="Systems")
                span.tail = value[len(OLD_COMPANY):]
    return _xml(root)


def prepare_office(task_id: str, base_dir: Path = Path("/tmp/ledgerdesk")) -> list[str]:
    """Restore a deterministic input and clear this task's previous export."""
    if task_id not in OFFICE_TASKS:
        raise ValueError(f"Unknown office task: {task_id}")
    task = OFFICE_TASKS[task_id]
    base_dir = Path(base_dir)
    inputs, exports = base_dir / "inputs", base_dir / "exports"
    inputs.mkdir(parents=True, exist_ok=True)
    exports.mkdir(parents=True, exist_ok=True)
    output = exports / task["output_name"]
    output.unlink(missing_ok=True)
    source = inputs / task["input_name"]
    is_calc = task["application"] == "calc"
    _write_package(source, "application/vnd.oasis.opendocument.spreadsheet" if is_calc else "application/vnd.oasis.opendocument.text", _calc_content() if is_calc else _writer_content())
    return ["libreoffice", "--norestore", "--nodefault", "--nofirststartwizard", f"--{task['application']}", str(source)]


def office_instruction(task_id: str) -> str:
    if task_id == "calc-sort-export":
        return (
            "The supplied receivables spreadsheet is open in LibreOffice Calc. Sort the entire table "
            "by outstanding_balance numerically descending, then invoice_id ascending for ties. "
            "Keep the header first and preserve every row and every other cell value. Export the sorted "
            "sheet as a UTF-8, comma-separated CSV to /tmp/ledgerdesk/exports/calc-sort-export.csv. "
            "Use the application's normal controls and confirm the CSV format if asked. Do not overwrite the source ODS."
        )
    if task_id == "writer-find-replace":
        return (
            f"The supplied supplier handover memo is open in LibreOffice Writer. Replace every exact "
            f"occurrence of '{OLD_COMPANY}' with '{NEW_COMPANY}', including occurrences in the table. "
            "Do not change the similar names 'Harbour Systems' or 'Harbor System', or any other text, "
            "numbers, paragraph order or table content. Save the edited document as OpenDocument Text "
            "to /tmp/ledgerdesk/exports/writer-find-replace.odt, leaving the source ODT unchanged."
        )
    raise ValueError(f"Unknown office task: {task_id}")


def _verify_calc(output: Path) -> tuple[list[str], list[dict], list[str]]:
    errors, headers, rows = [], [], []
    with output.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream, strict=True)
        headers, rows = reader.fieldnames or [], list(reader)
    if headers != CALC_HEADERS:
        errors.append("CSV columns or column order differ from the original spreadsheet.")
    expected = sorted(CALC_ROWS, key=lambda row: (-Decimal(row[2]), row[0]))
    if len(rows) != len(expected):
        errors.append(f"Expected {len(expected)} rows, received {len(rows)}.")
    if len({row.get("invoice_id") for row in rows}) != len(rows):
        errors.append("Duplicate invoice identifiers.")
    for number, (actual, source) in enumerate(zip(rows, expected), 1):
        wanted = dict(zip(CALC_HEADERS, source))
        balance = actual.get("outstanding_balance", "")
        try:
            if not isinstance(balance, str) or not re.fullmatch(r"-?\d+(?:\.\d{1,2})?", balance):
                raise InvalidOperation
            normalized = dict(actual, outstanding_balance=format(Decimal(balance), ".2f"))
        except InvalidOperation:
            normalized = actual
        if normalized != wanted:
            errors.append(f"Row {number} changed content or is out of the required sort order.")
    return headers, rows, errors


def _odf_text(element) -> str:
    parts = [element.text or ""]
    for child in element:
        if child.tag == _q("text:s"):
            count = int(child.get(_q("text:c"), "1"))
            if not 1 <= count <= 1000:
                raise ValueError("Invalid ODT space count.")
            parts.append(" " * count)
        elif child.tag == _q("text:tab"):
            parts.append("\t")
        elif child.tag == _q("text:line-break"):
            parts.append("\n")
        else:
            parts.append(_odf_text(child))
        parts.append(child.tail or "")
    return "".join(parts)


def _writer_rows(root) -> list[dict[str, str]]:
    body = root.find("office:body/office:text", NS)
    if body is None:
        raise ValueError("Output is not a Writer text document.")
    rows = []
    block_index = 0
    ignored = {_q(f"text:{name}") for name in ("sequence-decls", "user-field-decls", "variable-decls", "dde-connection-decls")}
    for child in body:
        if child.tag in ignored:
            continue
        block_index += 1
        if child.tag in {_q("text:p"), _q("text:h")}:
            kind = f"heading:{child.get(_q('text:outline-level'), '1')}" if child.tag == _q("text:h") else "paragraph"
            rows.append({"section": f"{block_index}:{kind}", "text": _odf_text(child)})
        elif child.tag == _q("table:table"):
            table_rows = child.findall(".//table:table-row", NS)
            if len(table_rows) > 20:
                raise ValueError("Unexpected table size.")
            for row_index, line in enumerate(table_rows, 1):
                if int(line.get(_q("table:number-rows-repeated"), "1")) != 1:
                    raise ValueError("Unexpected repeated table row.")
                cells = line.findall("table:table-cell", NS)
                if len(cells) > 12:
                    raise ValueError("Unexpected table width.")
                for column, cell in enumerate(cells, 1):
                    if int(cell.get(_q("table:number-columns-repeated"), "1")) != 1:
                        raise ValueError("Unexpected repeated table cell.")
                    paragraphs = cell.findall("text:p", NS)
                    rows.append({"section": f"{block_index}:table:{row_index}:{column}", "text": "\n".join(_odf_text(p) for p in paragraphs)})
        else:
            raise ValueError("Unexpected document structure.")
    return rows


def _expected_writer_rows() -> list[dict[str, str]]:
    rows = []
    for index, (kind, value) in enumerate(WRITER_BLOCKS, 1):
        if kind == "table":
            for row_index, line in enumerate(value, 1):
                for column, text in enumerate(line, 1):
                    rows.append({"section": f"{index}:table:{row_index}:{column}", "text": text.replace(OLD_COMPANY, NEW_COMPANY)})
        else:
            rows.append({"section": f"{index}:{kind}", "text": value.replace(OLD_COMPANY, NEW_COMPANY)})
    return rows


def _verify_writer(output: Path) -> tuple[list[str], list[dict], list[str]]:
    with ZipFile(output) as archive:
        if archive.read("mimetype") != b"application/vnd.oasis.opendocument.text":
            raise ValueError("Expected an OpenDocument Text file.")
        info = archive.getinfo("content.xml")
        if info.file_size > 1_000_000:
            raise ValueError("ODT content exceeds the fixture size limit.")
        content = archive.read(info)
    if b"<!DOCTYPE" in content or b"<!ENTITY" in content:
        raise ValueError("ODT document declarations are not allowed.")
    rows = _writer_rows(ET.fromstring(content))
    expected = _expected_writer_rows()
    errors = [] if rows == expected else ["Document text, headings, paragraph order or table cells differ from the required replacement."]
    return ["section", "text"], rows, errors


def verify_office(task_id: str, output: Path) -> dict:
    """Check the output's substance, independently of LibreOffice or its GUI."""
    if task_id not in OFFICE_TASKS:
        raise ValueError(f"Unknown office task: {task_id}")
    headers, rows = [], []
    try:
        output = Path(output)
        if output.stat().st_size > 10_000_000:
            raise ValueError("Output exceeds the fixture size limit.")
        headers, rows, errors = _verify_calc(output) if task_id == "calc-sort-export" else _verify_writer(output)
    except (OSError, UnicodeError, csv.Error, BadZipFile, ET.ParseError, KeyError, ValueError, OverflowError) as error:
        errors = [f"Cannot verify office output: {error}"]
    return {"passed": not errors, "errors": errors, "headers": headers, "rows": rows, "row_count": len(rows)}
