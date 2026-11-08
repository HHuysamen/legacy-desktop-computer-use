"""Synthetic native GnuCash books and independent saved-book verification.

Only instructions and screenshots reach the model. XML creation and inspection
are trusted controller operations; neither is an agent tool.
"""

from __future__ import annotations

from datetime import datetime
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import re
from uuid import NAMESPACE_URL, uuid5
from xml.etree import ElementTree as ET
import zlib


GNUTASKS = {
    "gnucash-expense": {"name": "GnuCash: enter an expense", "application": "gnucash"},
    "gnucash-split": {"name": "GnuCash: enter a split expense", "application": "gnucash"},
    "gnucash-transfer": {"name": "GnuCash: record an account transfer", "application": "gnucash"},
}
for _task_id, _task in GNUTASKS.items():
    _task.update(input_name="gnucash-source.gnucash", output_name=f"{_task_id}.gnucash")

NS = {name: f"http://www.gnucash.org/XML/{name}" for name in (
    "gnc", "book", "cd", "act", "cmdty", "trn", "split", "ts",
)}
for _prefix, _namespace in NS.items():
    ET.register_namespace(_prefix, _namespace)

ACCOUNTS = {
    "Root Account": "ROOT", "Checking": "BANK", "Savings": "BANK",
    "ExpenseTravel": "EXPENSE", "ExpenseMeals": "EXPENSE",
    "ExpenseSupplies": "EXPENSE", "EquityOpening": "EQUITY",
}
MAX_BOOK_BYTES = 2_000_000


def _q(name: str) -> str:
    prefix, local = name.split(":", 1)
    return f"{{{NS[prefix]}}}{local}"


def _node(parent, tag: str, text: str | None = None, **attributes):
    node = ET.SubElement(parent, _q(tag), attributes)
    node.text = text
    return node


def _guid(label: str) -> str:
    return uuid5(NAMESPACE_URL, "ledgerdesk-gnucash:" + label).hex


def _validate(task_id: str, index: int) -> None:
    if task_id not in GNUTASKS:
        raise ValueError(f"Unknown GnuCash task: {task_id}")
    if type(index) is not int or index not in range(3):
        raise ValueError("GnuCash variant index must be 0, 1 or 2.")


def _expected(task_id: str, index: int) -> dict:
    _validate(task_id, index)
    if task_id == "gnucash-expense":
        amount = (12550, 8735, 21980)[index]
        description = ("EXP-01 Printer supplies", "EXP-02 Packing materials", "EXP-03 Stationery")[index]
        splits = {"Checking": -amount, "ExpenseSupplies": amount}
    elif task_id == "gnucash-split":
        travel, meals = ((18000, 6000), (9750, 4225), (22110, 7890))[index]
        description = ("SPL-01 Client visit", "SPL-02 Regional meeting", "SPL-03 Supplier visit")[index]
        splits = {"Checking": -travel - meals, "ExpenseTravel": travel, "ExpenseMeals": meals}
    else:
        amount = (50000, 72525, 31000)[index]
        description = ("TRF-01 Reserve transfer", "TRF-02 Savings allocation", "TRF-03 Cash reserve")[index]
        splits = {"Checking": -amount, "Savings": amount}
    return {"date": f"2026-11-{10 + index:02d}", "description": description, "splits": splits}


def _currency(parent, tag: str):
    node = _node(parent, tag)
    _node(node, "cmdty:space", "CURRENCY")
    _node(node, "cmdty:id", "USD")
    return node


def _transaction(book, label: str, date: str, description: str, splits: dict[str, int]):
    transaction = _node(book, "gnc:transaction", version="2.0.0")
    _node(transaction, "trn:id", _guid(label), type="guid")
    _currency(transaction, "trn:currency")
    _node(transaction, "trn:num", "")
    for field in ("trn:date-posted", "trn:date-entered"):
        _node(_node(transaction, field), "ts:date", date + " 12:00:00 +0000")
    _node(transaction, "trn:description", description)
    children = _node(transaction, "trn:splits")
    for name, cents in splits.items():
        split = _node(children, "trn:split")
        _node(split, "split:id", _guid(label + ":" + name), type="guid")
        _node(split, "split:reconciled-state", "n")
        _node(split, "split:value", f"{cents}/100")
        _node(split, "split:quantity", f"{cents}/100")
        _node(split, "split:account", _guid("account:" + name), type="guid")
    return transaction


def _fixture_bytes(task_id: str, index: int) -> bytes:
    _validate(task_id, index)
    root = ET.Element("gnc-v2")
    _node(root, "gnc:count-data", "1", **{_q("cd:type"): "book"})
    book = _node(root, "gnc:book", version="2.0.0")
    _node(book, "book:id", _guid(f"book:{task_id}:{index}"), type="guid")
    for kind, count in (("commodity", 1), ("account", len(ACCOUNTS)), ("transaction", 1)):
        _node(book, "gnc:count-data", str(count), **{_q("cd:type"): kind})
    _currency(book, "gnc:commodity").set("version", "2.0.0")
    for name, account_type in ACCOUNTS.items():
        account = _node(book, "gnc:account", version="2.0.0")
        _node(account, "act:name", name)
        _node(account, "act:id", _guid("account:" + name), type="guid")
        _node(account, "act:type", account_type)
        if account_type != "ROOT":
            _currency(account, "act:commodity")
            _node(account, "act:commodity-scu", "100")
            _node(account, "act:parent", _guid("account:Root Account"), type="guid")
    _transaction(book, "opening", "2026-10-01", "Synthetic opening balance", {
        "Checking": 1_000_000, "EquityOpening": -1_000_000,
    })
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def prepare_gnucash(task_id: str, index: int = 0, base_dir: Path = Path("/tmp/ledgerdesk")) -> list[str]:
    """Restore one deterministic native book, clearing only its expected export."""
    data = _fixture_bytes(task_id, index)
    inputs, exports = Path(base_dir) / "inputs", Path(base_dir) / "exports"
    inputs.mkdir(parents=True, exist_ok=True)
    exports.mkdir(parents=True, exist_ok=True)
    (exports / GNUTASKS[task_id]["output_name"]).unlink(missing_ok=True)
    source = inputs / GNUTASKS[task_id]["input_name"]
    source.write_bytes(data)
    return ["gnucash", str(source)]


def gnucash_instruction(task_id: str, index: int = 0) -> str:
    wanted = _expected(task_id, index)
    if task_id == "gnucash-expense":
        operation = f"Record a supplies expense of USD {wanted['splits']['ExpenseSupplies'] / 100:.2f}, paid from Checking to ExpenseSupplies."
    elif task_id == "gnucash-split":
        operation = (
            f"Record one split expense paid from Checking: USD {wanted['splits']['ExpenseTravel'] / 100:.2f} "
            f"to ExpenseTravel and USD {wanted['splits']['ExpenseMeals'] / 100:.2f} to ExpenseMeals. "
            "Use one transaction with three splits, not two separate transactions."
        )
    else:
        operation = f"Record a transfer of USD {wanted['splits']['Savings'] / 100:.2f} from Checking to Savings."
    return (
        "A synthetic USD book is open in GnuCash. " + operation + " "
        f"Use date {wanted['date']} ({datetime.fromisoformat(wanted['date']).strftime('%m/%d/%y')} in the displayed MM/DD/YY field) "
        f"and exact Description '{wanted['description']}'. Leave Num and split memos blank. "
        "Add exactly one transaction and leave it unreconciled. Preserve all existing accounts and transactions. "
        f"Use Save As to save the XML GnuCash book to /tmp/ledgerdesk/exports/{GNUTASKS[task_id]['output_name']}. "
        "Do not overwrite the source book. Use only the application's normal controls."
    )


def gnucash_manifest() -> dict:
    fixtures, cases = [], []
    for task_id, config in GNUTASKS.items():
        for index in range(3):
            item = {"fixture_id": f"{task_id}-{index:02d}", "task_id": task_id,
                    "fixture_index": index, "input_name": config["input_name"], "output_name": config["output_name"],
                    "input_sha256": hashlib.sha256(_fixture_bytes(task_id, index)).hexdigest(),
                    "instruction_sha256": hashlib.sha256(gnucash_instruction(task_id, index).encode()).hexdigest(),
                    "expected_sha256": hashlib.sha256(json.dumps(_expected(task_id, index), sort_keys=True).encode()).hexdigest()}
            fixtures.append(item)
            cases.append({**item, "case_id": item["fixture_id"], "geometry": "normal", "control": None})
    return {"schema_version": 1, "protocol": "gnucash-native-v1", "fixtures": fixtures, "cases": cases}


def _text(element, path: str, default: str = "") -> str:
    nodes = element.findall(path, NS)
    if len(nodes) > 1:
        raise ValueError("Duplicate book field.")
    return (nodes[0].text or "") if nodes else default


def _identifier(element, path: str) -> str:
    value = _text(element, path)
    if not re.fullmatch(r"[0-9a-f]{32}", value):
        raise ValueError("Invalid book identifier.")
    return value


def _money(element, path: str) -> Fraction:
    value = _text(element, path)
    if not re.fullmatch(r"-?\d{1,16}/[1-9]\d{0,15}", value):
        raise ValueError("Invalid rational amount.")
    return Fraction(value)


def _parse(data: bytes) -> dict:
    if len(data) > MAX_BOOK_BYTES or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("Unsafe or oversized book XML.")
    root = ET.fromstring(data)
    books = root.findall("gnc:book", NS)
    if root.tag != "gnc-v2" or len(books) != 1:
        raise ValueError("Expected one native GnuCash book.")
    book = books[0]
    allowed = {_q(name) for name in ("book:id", "book:slots", "gnc:count-data", "gnc:commodity", "gnc:pricedb", "gnc:account", "gnc:transaction")}
    if any(child.tag not in allowed for child in book) or book.findall("gnc:pricedb/*", NS):
        raise ValueError("Unexpected financial objects in book.")
    accounts = {}
    all_ids = {_identifier(book, "book:id")}
    for account in book.findall("gnc:account", NS):
        identifier = _identifier(account, "act:id")
        if identifier in all_ids:
            raise ValueError("Duplicate book identifier.")
        all_ids.add(identifier)
        accounts[identifier] = tuple(_text(account, field) for field in (
            "act:name", "act:type", "act:commodity/cmdty:id", "act:commodity-scu", "act:parent", "act:code", "act:description",
        ))
        if accounts[identifier][1] != "ROOT" and _text(account, "act:commodity/cmdty:space") not in {"CURRENCY", "ISO4217"}:
            raise ValueError("Unexpected account commodity.")
    transactions = {}
    for transaction in book.findall("gnc:transaction", NS):
        identifier = _identifier(transaction, "trn:id")
        if identifier in all_ids:
            raise ValueError("Duplicate book identifier.")
        all_ids.add(identifier)
        if (_text(transaction, "trn:currency/cmdty:space") not in {"CURRENCY", "ISO4217"}
                or _text(transaction, "trn:currency/cmdty:id") != "USD"):
            raise ValueError("Unexpected transaction currency.")
        posted = _text(transaction, "trn:date-posted/ts:date")
        datetime.strptime(posted, "%Y-%m-%d %H:%M:%S %z")
        splits = []
        for split in transaction.findall("trn:splits/trn:split", NS):
            split_id = _identifier(split, "split:id")
            if split_id in all_ids:
                raise ValueError("Duplicate book identifier.")
            all_ids.add(split_id)
            account_id = _identifier(split, "split:account")
            value, quantity = _money(split, "split:value"), _money(split, "split:quantity")
            if account_id not in accounts or value != quantity:
                raise ValueError("Unknown account or mismatched USD split quantity.")
            splits.append((account_id, value, _text(split, "split:reconciled-state"),
                           _text(split, "split:memo"), _text(split, "split:action")))
        if len(splits) < 2 or sum((split[1] for split in splits), Fraction()) != 0:
            raise ValueError("Transaction splits do not balance.")
        transactions[identifier] = {
            "date": posted[:10], "description": _text(transaction, "trn:description"),
            "num": _text(transaction, "trn:num"), "splits": sorted(splits),
        }
    return {"id": _identifier(book, "book:id"), "accounts": accounts, "transactions": transactions}


def _read_book(path: Path) -> bytes:
    with Path(path).open("rb") as stream:
        compressed = stream.read(2) == b"\x1f\x8b"
        stream.seek(0)
        if compressed:
            with gzip.GzipFile(fileobj=stream) as archive:
                data = archive.read(MAX_BOOK_BYTES + 1)
        else:
            data = stream.read(MAX_BOOK_BYTES + 1)
    if len(data) > MAX_BOOK_BYTES:
        raise ValueError("Book exceeds the fixture size limit.")
    return data


def verify_gnucash(task_id: str, output: Path, index: int = 0, *, source_path: Path | None = None) -> dict:
    """Verify financial state; the controller must also check the source byte hash."""
    wanted = _expected(task_id, index)
    baseline_bytes = _fixture_bytes(task_id, index)
    baseline = _parse(baseline_bytes)
    rows, errors, source_unchanged = [], [], None
    try:
        actual = _parse(_read_book(output))
        if actual["id"] != baseline["id"] or actual["accounts"] != baseline["accounts"]:
            errors.append("Starting book identity or accounts changed.")
        opening_id = _guid("opening")
        if actual["transactions"].get(opening_id) != baseline["transactions"][opening_id]:
            errors.append("Starting transaction changed or is missing.")
        added = {key: value for key, value in actual["transactions"].items() if key != opening_id}
        expected_splits = sorted((_guid("account:" + name), Fraction(cents, 100), "n", "", "")
                                 for name, cents in wanted["splits"].items())
        expected_transaction = {"date": wanted["date"], "description": wanted["description"], "num": "", "splits": expected_splits}
        if list(added.values()) != [expected_transaction]:
            errors.append("Expected exactly one new transaction with the requested date, description and splits.")
        for transaction in actual["transactions"].values():
            for account_id, amount, state, memo, action in transaction["splits"]:
                rows.append({"date": transaction["date"], "description": transaction["description"],
                             "account": actual["accounts"][account_id][0], "amount": f"{float(amount):.2f}"})
        if source_path is not None:
            source_unchanged = hashlib.sha256(Path(source_path).read_bytes()).digest() == hashlib.sha256(baseline_bytes).digest()
            if not source_unchanged:
                errors.append("The original input file was modified.")
    except (OSError, EOFError, ET.ParseError, ValueError, OverflowError, zlib.error) as error:
        errors.append(f"Cannot verify GnuCash output: {error}")
    return {"passed": not errors, "errors": errors, "headers": ["date", "description", "account", "amount"],
            "rows": rows, "row_count": len(rows), "source_unchanged": source_unchanged,
            "expected_input_sha256": hashlib.sha256(baseline_bytes).hexdigest()}
