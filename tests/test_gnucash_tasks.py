import gzip
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from ledgerdesk import gnucash_tasks as gnc


def completed_book(task, index=0):
    root = ET.fromstring(gnc._fixture_bytes(task, index))
    book = root.find("gnc:book", gnc.NS)
    wanted = gnc._expected(task, index)
    transaction = ET.SubElement(book, gnc._q("gnc:transaction"), version="2.0.0")

    def child(parent, tag, text):
        node = ET.SubElement(parent, gnc._q(tag))
        node.text = text
        return node

    child(transaction, "trn:id", "a" * 32)
    currency = child(transaction, "trn:currency", None)
    child(currency, "cmdty:space", "CURRENCY")
    child(currency, "cmdty:id", "USD")
    child(child(transaction, "trn:date-posted", None), "ts:date", wanted["date"] + " 00:00:00 +0000")
    child(transaction, "trn:description", wanted["description"])
    splits = child(transaction, "trn:splits", None)
    for number, (name, cents) in enumerate(reversed(list(wanted["splits"].items())), 1):
        split = child(splits, "trn:split", None)
        child(split, "split:id", f"{number:032x}")
        child(split, "split:account", gnc._guid("account:" + name))
        child(split, "split:reconciled-state", "n")
        child(split, "split:value", f"{cents * 10}/1000")
        child(split, "split:quantity", f"{cents}/100")
    return root, transaction


def write_xml(path, root, compressed=False):
    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    path.write_bytes(gzip.compress(data) if compressed else data)


@pytest.mark.parametrize("task", list(gnc.GNUTASKS))
@pytest.mark.parametrize("index", range(3))
def test_native_fixture_is_deterministic_and_each_variant_verifies(tmp_path, task, index):
    command = gnc.prepare_gnucash(task, index, tmp_path)
    source = Path(command[-1])
    assert command == ["gnucash", str(tmp_path / "inputs" / "gnucash-source.gnucash")]
    original = source.read_bytes()
    parsed = gnc._parse(original)
    assert len(parsed["accounts"]) == 7
    assert len(parsed["transactions"]) == 1
    output = tmp_path / "exports" / gnc.GNUTASKS[task]["output_name"]
    output.write_text("stale")
    keep = output.with_name("keep.txt")
    keep.write_text("keep")
    gnc.prepare_gnucash(task, index, tmp_path)
    assert not output.exists()
    assert source.read_bytes() == original
    assert keep.read_text() == "keep"
    root, _ = completed_book(task, index)
    write_xml(output, root, compressed=index % 2 == 1)
    result = gnc.verify_gnucash(task, output, index, source_path=source)
    assert result["passed"], result["errors"]
    assert result["source_unchanged"] is True
    assert result["row_count"] == (5 if task == "gnucash-split" else 4)
    assert not gnc.verify_gnucash(task, source, index)["passed"]


@pytest.mark.parametrize("mistake", ["wrong-date", "wrong-description", "wrong-amount", "wrong-account", "quantity", "opening", "account-name", "extra-account", "extra-transaction", "currency", "reconciled", "duplicate-id"])
def test_verifier_rejects_incorrect_or_unrelated_financial_changes(tmp_path, mistake):
    task = "gnucash-expense"
    root, transaction = completed_book(task)
    book = root.find("gnc:book", gnc.NS)
    splits = transaction.findall("trn:splits/trn:split", gnc.NS)
    if mistake == "wrong-date":
        transaction.find("trn:date-posted/ts:date", gnc.NS).text = "2026-11-11 00:00:00 +0000"
    elif mistake == "wrong-description":
        transaction.find("trn:description", gnc.NS).text = "different reference"
    elif mistake == "wrong-amount":
        for split, value in zip(splits, ("12600/100", "-12600/100")):
            split.find("split:value", gnc.NS).text = value
            split.find("split:quantity", gnc.NS).text = value
    elif mistake == "wrong-account":
        splits[0].find("split:account", gnc.NS).text = gnc._guid("account:ExpenseMeals")
    elif mistake == "quantity":
        splits[0].find("split:quantity", gnc.NS).text = "1/100"
    elif mistake == "opening":
        book.find("gnc:transaction/trn:description", gnc.NS).text = "changed opening"
    elif mistake == "account-name":
        book.findall("gnc:account", gnc.NS)[1].find("act:name", gnc.NS).text = "Renamed"
    elif mistake == "extra-account":
        account = ET.fromstring(ET.tostring(book.findall("gnc:account", gnc.NS)[1]))
        account.find("act:id", gnc.NS).text = "b" * 32
        book.append(account)
    elif mistake == "extra-transaction":
        extra = ET.fromstring(ET.tostring(transaction))
        extra.find("trn:id", gnc.NS).text = "b" * 32
        for number, split in enumerate(extra.findall("trn:splits/trn:split", gnc.NS), 10):
            split.find("split:id", gnc.NS).text = f"{number:032x}"
        book.append(extra)
    elif mistake == "currency":
        transaction.find("trn:currency/cmdty:id", gnc.NS).text = "EUR"
    elif mistake == "reconciled":
        splits[0].find("split:reconciled-state", gnc.NS).text = "y"
    else:
        splits[1].find("split:id", gnc.NS).text = splits[0].find("split:id", gnc.NS).text
    output = tmp_path / "result.gnucash"
    write_xml(output, root)
    assert not gnc.verify_gnucash(task, output)["passed"]


def test_source_hash_check_is_explicit_and_does_not_infer_success(tmp_path):
    task = "gnucash-transfer"
    source = Path(gnc.prepare_gnucash(task, 0, tmp_path)[-1])
    output = tmp_path / "result.gnucash"
    write_xml(output, completed_book(task)[0])
    assert gnc.verify_gnucash(task, output)["source_unchanged"] is None
    source.write_bytes(source.read_bytes() + b"\n")
    result = gnc.verify_gnucash(task, output, source_path=source)
    assert not result["passed"]
    assert result["source_unchanged"] is False


@pytest.mark.parametrize("data", [b"not xml", b"<!DOCTYPE x><gnc-v2/>", b"\x1f\x8btruncated", b"\x1f\x8b\x08\x00" + b"\x00" * 6 + b"\xff" * 20, gzip.compress(b"x" * (gnc.MAX_BOOK_BYTES + 1))])
def test_malformed_unsafe_and_oversized_books_fail_closed(tmp_path, data):
    output = tmp_path / "bad.gnucash"
    output.write_bytes(data)
    assert not gnc.verify_gnucash("gnucash-expense", output)["passed"]
    assert not gnc.verify_gnucash("gnucash-expense", tmp_path / "missing")["passed"]


def test_variants_and_instructions_are_distinct_and_validate_before_writing(tmp_path):
    for task, config in gnc.GNUTASKS.items():
        assert len({gnc.gnucash_instruction(task, index) for index in range(3)}) == 3
        assert len({gnc._fixture_bytes(task, index) for index in range(3)}) == 3
        assert "/tmp/ledgerdesk/exports/" + config["output_name"] in gnc.gnucash_instruction(task)
    for task, index in (("../escape", 0), ("gnucash-expense", -1), ("gnucash-expense", 3), ("gnucash-expense", True)):
        base = tmp_path / "should-not-exist"
        with pytest.raises(ValueError):
            gnc.prepare_gnucash(task, index, base)
        assert not base.exists()


def test_manifest_is_complete_and_matches_prepared_inputs(tmp_path):
    import hashlib
    from ledgerdesk.gnucash_tasks import gnucash_manifest, prepare_gnucash, gnucash_instruction
    manifest = gnucash_manifest()
    assert len(manifest['fixtures']) == len(manifest['cases']) == 9
    assert len({c['case_id'] for c in manifest['cases']}) == 9
    for item in manifest['fixtures']:
        command = prepare_gnucash(item['task_id'], item['fixture_index'], tmp_path)
        assert hashlib.sha256(Path(command[-1]).read_bytes()).hexdigest() == item['input_sha256']
        assert hashlib.sha256(gnucash_instruction(item['task_id'], item['fixture_index']).encode()).hexdigest() == item['instruction_sha256']
