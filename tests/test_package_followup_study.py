import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from ledgerdesk import gnucash_tasks as gnc, office_tasks as office, robustness_fixtures as variants, workflows
from ledgerdesk.seed_data import reset_database
from scripts import package_followup_study as package
from scripts import run_robustness_study as study


def write_json(path, value):
    path.write_text(json.dumps(value) + "\n")


def office_output(case, directory):
    prepared = directory / "preparation"
    command = variants.prepare_variant(case["task_id"], case["split"], case["fixture_index"], prepared)
    source = Path(command[-1])
    shutil.copyfile(source, directory / source.name)
    if case["task_id"] == "calc-sort-export":
        with ZipFile(source) as archive:
            root = ET.fromstring(archive.read("content.xml"))
        rows = [[office._odf_text(cell.find("text:p", office.NS)) for cell in row.findall("table:table-cell", office.NS)]
                for row in root.findall("office:body/office:spreadsheet/table:table/table:table-row", office.NS)]
        header, *rows = rows
        rows.sort(key=lambda row: (-float(row[2]), row[0]))
        with (directory / "export.csv").open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerows([header, *rows])
    else:
        old, new = re.search(r"occurrence of '([^']+)' with '([^']+)'", variants.variant_instruction(case["task_id"], case["split"], case["fixture_index"])).groups()
        with ZipFile(source) as original, ZipFile(directory / "export.odt", "w") as output:
            for info in original.infolist():
                data = original.read(info)
                if info.filename == "content.xml":
                    root = ET.fromstring(data)
                    for element in root.iter():
                        if element.tag in {office._q("text:p"), office._q("text:h")}:
                            text = office._odf_text(element).replace(old, new)
                            for child in list(element):
                                element.remove(child)
                            element.text = text
                    data = ET.tostring(root, encoding="utf-8")
                output.writestr(info, data)


def gnc_output(case, directory):
    task, index = case["task_id"], case["fixture_index"]
    data = gnc._fixture_bytes(task, index)
    (directory / "gnucash-source.gnucash").write_bytes(data)
    root = ET.fromstring(data)
    wanted = gnc._expected(task, index)
    gnc._transaction(root.find("gnc:book", gnc.NS), "test-result", wanted["date"], wanted["description"], wanted["splits"])
    (directory / "export.gnucash").write_bytes(ET.tostring(root, encoding="utf-8"))


def build_study(tmp_path, monkeypatch, campaign="office", failed_correct=False, unknown_cost=False):
    monkeypatch.setattr(package, "ROOT", tmp_path)
    monkeypatch.setattr(study, "ROOT", tmp_path)
    source = tmp_path / "ledgerdesk/source.py"
    source.parent.mkdir(parents=True)
    source.write_text("# frozen test runtime\n")
    manifest = variants.variant_manifest() if campaign == "office" else gnc.gnucash_manifest()
    context = {"campaign": campaign, "source_revision": "a" * 40, "image_id": "sha256:" + "b" * 64,
               "environment": {"display": "1200x900", "platform": "test"}, "fixtures": manifest,
               "code_files": {"ledgerdesk/source.py": hashlib.sha256(source.read_bytes()).hexdigest()}}
    positive_count = 0

    def runner(case, limits):
        nonlocal positive_count
        directory = tmp_path / "output" / "runs" / case["case_id"]
        (directory / "screenshots").mkdir(parents=True)
        (directory / "screenshots/001.png").write_bytes(b"test screenshot")
        (directory / "recording.mp4").write_bytes(b"test recording")
        (directory / "report.html").write_text("<html><body>Saved run evidence</body></html>")
        (directory / "private.env").write_text("NOT COPIED")
        (directory / "unapproved.json").write_text('{"secret":"NOT COPIED"}')
        metadata = {"id": case["case_id"], "case_id": case["case_id"], "task_id": case["task_id"], "spec": case,
                    "source_revision": context["source_revision"], "image_id": context["image_id"], "operator_interventions": 0,
                    "input_sha256": case.get("input_sha256"), "status": "passed", "agent_status": "completed",
                    "request_count": 1, "action_count": 1, "executed_actions": 1,
                    "elapsed_seconds": 12.0 if case["geometry"] == "changed" else 10.0,
                    "estimated_cost_usd": 0.01, "usage": {"complete": True, "input_tokens": 100, "output_tokens": 20, "total_tokens": 120}}
        if case["task_id"] in office.OFFICE_TASKS:
            metadata["instruction"] = variants.variant_instruction(case["task_id"], case["split"], case["fixture_index"])
        elif case["task_id"] in gnc.GNUTASKS:
            metadata["instruction"] = gnc.gnucash_instruction(case["task_id"], case["fixture_index"])
        control = case.get("control")
        if case["kind"] == "positive":
            metadata["window_bounds"] = [0, 19, 1200, 881] if case["geometry"] == "normal" else [120, 90, 920, 660]
            (gnc_output if campaign == "gnucash" else office_output)(case, directory)
            check = {"passed": True, "source_unchanged": True, "source_sha256_after": case["input_sha256"]}
            write_json(directory / "verification.json", check)
            positive_count += 1
            if failed_correct and positive_count == 1:
                metadata.update(status="failed", agent_status="failed")
            if unknown_cost and positive_count == 1:
                metadata["estimated_cost_usd"] = None
                metadata["usage"]["complete"] = False
        else:
            metadata["status"] = "blocked"
            if control == "duplicate-receipt":
                reset_database(directory / "baseline.db")
                workflows.initialize_workflow_data(directory / "baseline.db")
                workflows.execute_workflow(directory / "baseline.db", "payment-entry", {"reference": "RCPT-1001", "invoice_number": "INV-260916", "amount": "125.25"})
                shutil.copyfile(directory / "baseline.db", directory / "final.db")
                audit = {"operation": "payment-entry", "status": "rejected", "fields": {"reference": "RCPT-1001"}, "reason": "UNIQUE constraint failed"}
                (directory / "application-audit.jsonl").write_text(json.dumps(audit) + "\n")
                proof = {"passed": True, "model_attempted": True, "duplicate_rejected": True, "state_unchanged": True}
            else:
                metadata.update(request_count=0, action_count=0, executed_actions=0, estimated_cost_usd=0.0)
                if control == "foreign-focus":
                    (directory / "foreign-value.txt").write_text("UNCHANGED")
                    (directory / "foreign-events.jsonl").write_text("")
                    proof = {"passed": True, "model_attempted": False, "refusal": "Target lost focus", "executed_inputs": 0}
                else:
                    write_json(directory / "setup-blocked.json", {"reason": "missing_source", "exists": False, "source": "/tmp/ledgerdesk/inputs/" + office.OFFICE_TASKS[case["task_id"]]["input_name"]})
                    proof = {"passed": True, "model_attempted": False}
            metadata["control_verification"] = proof
            write_json(directory / "control-verification.json", proof)
        events = '{"type":"action_result"}\n' if metadata["executed_actions"] else ''
        (directory / "events.jsonl").write_text(events)
        write_json(directory / "run.json", metadata)
        return directory, metadata

    directory = tmp_path / "output" / f"{campaign}-study"
    result = study.run_study(context, directory, runner)
    assert result["completed"] == (30 if campaign == "office" else 9)
    return directory


def test_office_package_rechecks_all_pairs_controls_and_hashes(tmp_path, monkeypatch):
    source = build_study(tmp_path, monkeypatch)
    before = {p: p.read_bytes() for p in source.rglob("*") if p.is_file()}
    destination = package.package_followup_study(source, tmp_path / "examples/office")
    summary = json.loads((destination / "summary.json").read_text())
    assert summary["positive"]["passed"] == summary["positive"]["attempts"] == 24
    assert summary["negative_controls"]["passed"] == summary["negative_controls"]["attempts"] == 6
    assert len(summary["pairs"]) == 12
    assert all(p["outcome"] == "both_passed" and p["input_hashes_match"] and p["changed_minus_normal_seconds"] == 2 for p in summary["pairs"])
    assert len(summary["positive_by_application"]) == 2
    assert summary["positive_by_split"]["heldout"]["attempts"] == 12
    assert summary["positive_by_geometry"]["changed"]["attempts"] == 12
    assert summary["all_cases"]["estimated_cost_usd"] == pytest.approx(0.26)
    assert summary["positive"]["cost_per_verified_success"] == pytest.approx(0.01)
    assert summary["positive_by_application"]["LibreOffice Calc"]["cost_per_verified_success"] == pytest.approx(0.01)
    assert summary["positive_by_split"]["heldout"]["cost_per_verified_success"] == pytest.approx(0.01)
    assert summary["positive_by_geometry"]["changed"]["cost_per_verified_success"] == pytest.approx(0.01)
    assert summary["negative_controls"]["cost_per_verified_success"] is None
    assert summary["all_cases"]["cost_per_verified_success"] is None
    assert summary["all_cases"]["operator_interventions"]["total"] == 0
    assert summary["all_cases"]["operator_interventions"]["available"] == 30
    assert all(pair["changed_minus_normal_executed_actions"] == pair["changed_minus_normal_request_count"] == pair["changed_minus_normal_cost_usd"] == 0 for pair in summary["pairs"])
    assert len(list(destination.rglob("recording.mp4"))) == 30
    assert not list(destination.rglob("*.env"))
    assert not list(destination.rglob("unapproved.json"))
    manifest = json.loads((destination / "manifest.json").read_text())
    for item in manifest["files"]:
        assert hashlib.sha256((destination / item["path"]).read_bytes()).hexdigest() == item["sha256"]
    assert {p: p.read_bytes() for p in source.rglob("*") if p.is_file()} == before


def test_gnucash_package_rechecks_nine_saved_books(tmp_path, monkeypatch):
    source = build_study(tmp_path, monkeypatch, "gnucash")
    destination = package.package_followup_study(source, tmp_path / "examples/gnucash")
    summary = json.loads((destination / "summary.json").read_text())
    assert summary["positive"]["passed"] == 9
    assert summary["negative_controls"]["attempts"] == 0
    assert summary["pairs"] == []
    assert summary["positive_by_application"]["GnuCash"]["attempts"] == 9
    assert len(list(destination.rglob("export.gnucash"))) == 9
    assert len(list(destination.rglob("gnucash-source.gnucash"))) == 9


def test_artifact_pass_does_not_upgrade_failed_execution_and_unknown_cost_is_retained(tmp_path, monkeypatch):
    source = build_study(tmp_path, monkeypatch, "gnucash", failed_correct=True, unknown_cost=True)
    destination = package.package_followup_study(source, tmp_path / "examples")
    summary = json.loads((destination / "summary.json").read_text())
    assert summary["positive"]["passed"] == 8
    assert summary["positive"]["failed"] == 1
    assert summary["positive"]["estimated_cost_usd"] is None
    assert summary["positive"]["estimated_cost_usd_known"] == pytest.approx(0.08)
    assert summary["positive"]["cost_per_verified_success"] is None
    assert summary["positive"]["input_tokens"]["total"] is None
    assert summary["positive"]["input_tokens"]["available"] == 8
    failed = next(row for row in summary["cases"] if row["metadata"]["status"] == "failed")
    assert failed["recheck"]["artifact_passed"] is True
    assert failed["recheck"]["passed"] is False


def test_cost_per_verified_success_includes_failed_attempt_cost(tmp_path, monkeypatch):
    source = build_study(tmp_path, monkeypatch, "gnucash", failed_correct=True)
    destination = package.package_followup_study(source, tmp_path / "examples")
    summary = json.loads((destination / "summary.json").read_text())
    assert summary["positive"]["passed"] == 8
    assert summary["positive"]["failed"] == 1
    assert summary["positive"]["estimated_cost_usd"] == pytest.approx(0.09)
    assert summary["positive"]["cost_per_verified_success"] == pytest.approx(0.09 / 8)


@pytest.mark.parametrize("grades", [[], [False], [True, None]])
def test_cost_per_verified_success_requires_known_outcomes_and_a_pass(grades):
    rows = [{"metadata": {"estimated_cost_usd": 0.01, "usage": {"complete": True}},
             "recheck": {"passed": grade}} for grade in grades]
    assert package._metrics(rows, positive=True)["cost_per_verified_success"] is None


@pytest.mark.parametrize("corruption", ["output", "extra-cell", "source-after", "duplicate-state", "foreign-events", "missing-marker"])
def test_rechecks_detect_incorrect_artifacts_and_control_evidence(tmp_path, monkeypatch, corruption):
    source = build_study(tmp_path, monkeypatch)
    protocol = json.loads((source / "protocol.json").read_text())
    target = next(case for case in protocol["plan"] if (
        case["kind"] == "positive" and case["task_id"] == "calc-sort-export" if corruption in {"output", "extra-cell", "source-after"}
        else case.get("control") == {"duplicate-state": "duplicate-receipt", "foreign-events": "foreign-focus", "missing-marker": "missing-source"}[corruption]))
    directory = tmp_path / "output/runs" / target["case_id"]
    if corruption == "output":
        (directory / "export.csv").write_text("wrong,output\n")
    elif corruption == "extra-cell":
        path = directory / "export.csv"
        lines = path.read_text().splitlines()
        lines[1] += ",extra"
        path.write_text("\n".join(lines) + "\n")
    elif corruption == "source-after":
        check = json.loads((directory / "verification.json").read_text())
        check["source_sha256_after"] = "0" * 64
        write_json(directory / "verification.json", check)
    elif corruption == "duplicate-state":
        with sqlite3.connect(directory / "final.db") as db:
            db.execute("UPDATE contacts SET phone='changed' WHERE customer_id=1")
    elif corruption == "foreign-events":
        (directory / "foreign-events.jsonl").write_text('{"event":"keypress"}\n')
    else:
        marker = json.loads((directory / "setup-blocked.json").read_text())
        marker["source"] = "/tmp/ledgerdesk/inputs/other.odt"
        write_json(directory / "setup-blocked.json", marker)
    destination = package.package_followup_study(source, tmp_path / "examples")
    summary = json.loads((destination / "summary.json").read_text())
    result = next(row for row in summary["cases"] if row["case"]["case_id"] == target["case_id"])
    assert result["recheck"]["passed"] is False


def test_incomplete_study_is_not_packaged(tmp_path, monkeypatch):
    source = build_study(tmp_path, monkeypatch, "gnucash")
    status = json.loads((source / "status.json").read_text())
    status.update(completed=8, remaining=1)
    write_json(source / "status.json", status)
    with pytest.raises(ValueError, match="completed study"):
        package.package_followup_study(source, tmp_path / "examples")
    assert not (tmp_path / "examples").exists()


@pytest.mark.parametrize("name", ["export.gnucash", "gnucash-source.gnucash", "screenshots/001.png"])
def test_artifact_symlinks_cannot_escape_run_directory(tmp_path, monkeypatch, name):
    source = build_study(tmp_path, monkeypatch, "gnucash")
    case = json.loads((source / "protocol.json").read_text())["plan"][0]
    target = tmp_path / "output/runs" / case["case_id"] / name
    outside = tmp_path / "outside"
    outside.write_bytes(target.read_bytes())
    target.unlink()
    target.symlink_to(outside)
    with pytest.raises(ValueError, match="escapes"):
        package.package_followup_study(source, tmp_path / "examples")


def test_existing_archive_is_never_overwritten(tmp_path, monkeypatch):
    source = build_study(tmp_path, monkeypatch, "gnucash")
    destination = tmp_path / "existing"
    destination.mkdir()
    (destination / "retain.txt").write_text("original archive")
    with pytest.raises(ValueError, match="empty destination"):
        package.package_followup_study(source, destination)
    assert (destination / "retain.txt").read_text() == "original archive"


def test_interrupted_slot_keeps_partial_evidence_without_upgrading_its_unknown_outcome(tmp_path, monkeypatch):
    source = build_study(tmp_path, monkeypatch, "gnucash")
    ledger = source / "events.jsonl"
    events = [json.loads(line) for line in ledger.read_text().splitlines()]
    finished = next(event for event in events if event["event"] == "finished")
    finished.update(completion="runner_interrupted", metadata={"status": "blocked", "estimated_cost_usd": None, "usage": {"complete": False}},
                    grade={"passed": None, "errors": ["Interrupted"]})
    ledger.write_text("".join(json.dumps(event) + "\n" for event in events))
    protocol = json.loads((source / "protocol.json").read_text())
    write_json(source / "status.json", study._status(protocol, [event for event in events if event["event"] == "finished"], None))
    destination = package.package_followup_study(source, tmp_path / "examples")
    summary = json.loads((destination / "summary.json").read_text())
    assert summary["positive"]["passed"] == 8
    assert summary["positive"]["unverified"] == 1
    assert summary["positive"]["estimated_cost_usd"] is None
    assert (destination / "runs" / finished["case_id"] / "export.gnucash").is_file()


def update_run_metadata(study_dir, tmp_path, predicate, change):
    ledger = study_dir / "events.jsonl"
    events = [json.loads(line) for line in ledger.read_text().splitlines()]
    event = next(e for e in events if e["event"] == "finished" and predicate(e["metadata"]))
    change(event["metadata"])
    write_json(tmp_path / event["run_dir"] / "run.json", event["metadata"])
    ledger.write_text("".join(json.dumps(item) + "\n" for item in events))
    return event


def test_operator_interventions_preserve_nonzero_and_unknown_counts(tmp_path, monkeypatch):
    source = build_study(tmp_path, monkeypatch, "gnucash")
    update_run_metadata(source, tmp_path, lambda m: True, lambda m: m.update(operator_interventions=1))
    update_run_metadata(source, tmp_path, lambda m: m.get("operator_interventions") == 0, lambda m: m.pop("operator_interventions"))
    destination = package.package_followup_study(source, tmp_path / "examples")
    summary = json.loads((destination / "summary.json").read_text())
    measurement = summary["positive"]["operator_interventions"]
    assert measurement["available"] == 8
    assert measurement["complete"] is False
    assert measurement["known_total"] == 1
    assert measurement["total"] is None
    assert measurement["mean"] == pytest.approx(1 / 8)
    assert summary["positive"]["passed"] == 7
    assert summary["positive"]["failed"] == 2


def test_paired_deltas_include_failed_attempts_and_preserve_missing_measurements():
    rows = [{"case": {"task_id": "calc-sort-export", "fixture_id": "paired-input", "split": "heldout",
                      "geometry": geometry, "case_id": geometry, "input_sha256": "unchanged"},
             "metadata": {"elapsed_seconds": seconds, "executed_actions": actions, "request_count": requests,
                          "estimated_cost_usd": cost, "usage": {"complete": True}},
             "recheck": {"passed": passed, "saved_input_sha256": "unchanged"}}
            for geometry, seconds, actions, requests, cost, passed in
            [("normal", 10, 5, 3, 0.03, False), ("changed", 12, 3, 2, 0.08, True)]]
    pair = package._pairs(rows)[0]
    assert pair["outcome"] == "changed_only"
    assert pair["changed_minus_normal_seconds"] == 2
    assert pair["changed_minus_normal_executed_actions"] == -2
    assert pair["changed_minus_normal_request_count"] == -1
    assert pair["changed_minus_normal_cost_usd"] == 0.05
    rows[0]["metadata"]["usage"]["complete"] = False
    rows[1]["metadata"].pop("executed_actions")
    pair = package._pairs(rows)[0]
    assert pair["changed_minus_normal_executed_actions"] is None
    assert pair["changed_minus_normal_cost_usd"] is None
    assert pair["changed_minus_normal_request_count"] == -1


def test_duplicate_recheck_accepts_the_frozen_runners_reference_normalization(tmp_path, monkeypatch):
    source = build_study(tmp_path, monkeypatch)
    plan = json.loads((source / "protocol.json").read_text())["plan"]
    case = next(case for case in plan if case.get("control") == "duplicate-receipt")
    audit = tmp_path / "output/runs" / case["case_id"] / "application-audit.jsonl"
    row = json.loads(audit.read_text())
    row["fields"]["reference"] = " RCPT-1001 "
    audit.write_text(json.dumps(row) + "\n")
    destination = package.package_followup_study(source, tmp_path / "examples")
    summary = json.loads((destination / "summary.json").read_text())
    assert summary["negative_controls"]["passed"] == 6


@pytest.mark.parametrize("geometry,bounds", [("normal", [120, 90, 920, 660]), ("changed", [0, 19, 1200, 881])])
def test_positive_geometry_is_checked_against_captured_bounds(tmp_path, monkeypatch, geometry, bounds):
    source = build_study(tmp_path, monkeypatch)
    event = update_run_metadata(source, tmp_path, lambda m: m["spec"]["kind"] == "positive" and m["spec"]["geometry"] == geometry,
                                lambda m: m.update(window_bounds=bounds))
    destination = package.package_followup_study(source, tmp_path / "examples")
    summary = json.loads((destination / "summary.json").read_text())
    case = next(row for row in summary["cases"] if row["case"]["case_id"] == event["case_id"])
    assert case["recheck"]["passed"] is False
    assert case["recheck"]["artifact_passed"] is True
    assert any("window bounds" in error for error in case["recheck"]["errors"])


def test_gnucash_positive_requires_normal_geometry(tmp_path, monkeypatch):
    source = build_study(tmp_path, monkeypatch, "gnucash")
    update_run_metadata(source, tmp_path, lambda m: True, lambda m: m.pop("window_bounds"))
    destination = package.package_followup_study(source, tmp_path / "examples")
    summary = json.loads((destination / "summary.json").read_text())
    assert summary["positive"]["passed"] == 8
    assert summary["positive"]["failed"] == 1


def test_derived_error_messages_redact_host_paths_but_raw_records_are_unchanged(tmp_path, monkeypatch):
    source = build_study(tmp_path, monkeypatch, "gnucash", failed_correct=True)
    event = update_run_metadata(source, tmp_path, lambda m: m["status"] == "failed",
                                lambda m: m.update(error=f"Failed to read '{tmp_path}/private-file.csv'"))
    directory = tmp_path / event["run_dir"]
    (directory / "export.gnucash").unlink()
    original_run = (directory / "run.json").read_bytes()
    destination = package.package_followup_study(source, tmp_path / "examples")
    for name in ("summary.json", "recheck.json"):
        assert str(tmp_path) not in (destination / name).read_text()
    copied = destination / "runs" / event["case_id"] / "run.json"
    assert copied.read_bytes() == original_run
    assert str(tmp_path) in copied.read_text()
