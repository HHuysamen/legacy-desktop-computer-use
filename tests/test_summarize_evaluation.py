from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys

import pytest

from ledgerdesk import office_tasks, reports, workflows
from ledgerdesk.seed_data import reset_database
from scripts import summarize_evaluation as summary


def run(identifier, *, status="passed", cost=0.1, complete=True, seconds=20):
    return {"id": identifier, "status": status, "estimated_cost_usd": cost,
            "usage": {"complete": complete}, "elapsed_seconds": seconds,
            "action_count": 7, "request_count": 6}


def study(tmp_path):
    tasks = list(reports.REPORTS)
    new_tasks = [task for task in summary.TASK_IDS if task not in reports.REPORTS]
    order = tasks * 8 + tasks * 2 + new_tasks * 10
    entries = []
    for index, task in enumerate(order):
        identifier = f"run-{index:03d}"
        directory = tmp_path / "output/runs" / identifier
        directory.mkdir(parents=True)
        metadata = {**run(identifier, cost=0.01), "task_id": task, "model": "test-model",
                    "fixture_sha256": "fixture", "finished_at": "2026-11-08T12:00:00Z"}
        (directory / "run.json").write_text(json.dumps(metadata))
        entries.append({**metadata, "run_dir": str(directory.relative_to(tmp_path))})
    document = {"planned_attempts": 100, "completed_attempts": 100,
                "historical_attempts": 24, "new_attempts": 76,
                "protocol": "expanded-100-v1", "runs": entries}
    path = tmp_path / "output/evaluation-100.json"
    path.write_text(json.dumps(document))
    return path, document


def rewrite_run(path, document, index, **changes):
    entry = document["runs"][index]
    entry.update(changes)
    directory = path.parent.parent / entry["run_dir"]
    (directory / "run.json").write_text(json.dumps({key: value for key, value in entry.items() if key != "run_dir"}))
    path.write_text(json.dumps(document))


def test_cost_per_success_includes_unsuccessful_attempt_cost():
    stats = summary.statistics([run("a", cost=0.1, seconds=10), run("b", status="failed", cost=0.2, seconds=30)])
    assert stats["passed"] == stats["failed"] == 1
    assert stats["estimated_cost_usd"] == pytest.approx(0.3)
    assert stats["mean_estimated_cost_usd_per_attempt"] == pytest.approx(0.15)
    assert stats["estimated_cost_usd_per_verified_success"] == pytest.approx(0.3)
    assert stats["projected_20_workday_cost_usd"] == pytest.approx(3.0)
    assert stats["mean_elapsed_seconds"] == stats["median_elapsed_seconds"] == 20


@pytest.mark.parametrize("cost,complete", [(None, False), (0.2, False), (float("nan"), True), (-1, True), (True, True)])
def test_unknown_or_partial_cost_does_not_become_zero(cost, complete):
    stats = summary.statistics([run("a", cost=0.1), run("b", cost=cost, complete=complete)])
    assert stats["cost_complete"] is False
    assert stats["missing_or_incomplete_cost_run_ids"] == ["b"]
    for key in ("estimated_cost_usd", "mean_estimated_cost_usd_per_attempt",
                "estimated_cost_usd_per_verified_success", "projected_20_workday_cost_usd"):
        assert stats[key] is None
    assert stats["estimated_cost_usd_known"] >= 0.1


def test_legitimate_zero_cost_and_no_success_are_distinct():
    stats = summary.statistics([run("a", status="blocked", cost=0, complete=True)])
    assert stats["estimated_cost_usd"] == 0
    assert stats["projected_20_workday_cost_usd"] == 0
    assert stats["estimated_cost_usd_per_verified_success"] is None


def test_missing_usage_cannot_establish_complete_cost():
    entry = {**run("a", cost=0.1), "usage": None}
    stats = summary.statistics([entry])
    assert stats["cost_complete"] is False
    assert stats["estimated_cost_usd"] is None
    assert stats["estimated_cost_usd_known"] == 0.1


def test_complete_summary_preserves_inputs_and_failed_outcomes(tmp_path, monkeypatch):
    path, document = study(tmp_path)
    rewrite_run(path, document, 0, status="failed")
    rewrite_run(path, document, 1, status="blocked")
    original_bytes = {item: item.read_bytes() for item in tmp_path.rglob("*") if item.is_file()}
    monkeypatch.setattr(summary, "_recheck_run", lambda *args: {"passed": True, "errors": []})
    recheck_path, cost_path = summary.summarize_evaluation(path)
    recheck, costs = json.loads(recheck_path.read_text()), json.loads(cost_path.read_text())
    assert recheck["all_recorded_passes_reverified"] is True
    assert recheck["runs"][0]["effective_status"] == "failed"
    assert recheck["runs"][1]["effective_status"] == "blocked"
    assert costs["overall"]["passed"] == 98
    assert costs["overall"]["estimated_cost_usd"] == 1.0
    assert costs["overall"]["estimated_cost_usd_per_verified_success"] == pytest.approx(1 / 98)
    assert costs["overall"]["projected_20_workday_cost_usd"] == pytest.approx(0.2)
    assert costs["cohorts"]["historical_24"]["attempts"] == 24
    assert costs["cohorts"]["new_76"]["attempts"] == 76
    assert Counter({task: stat["attempts"] for task, stat in costs["tasks"].items()}) == Counter({task: 10 for task in summary.TASK_IDS})
    assert all(item.read_bytes() == before for item, before in original_bytes.items())


def test_recorded_pass_disagreement_is_reported_and_cli_fails(tmp_path, monkeypatch):
    path, _ = study(tmp_path)
    monkeypatch.setattr(summary, "_recheck_run", lambda entry, directory: {"passed": entry["id"] != "run-024", "errors": []})
    monkeypatch.setattr(sys, "argv", ["summarize", str(path)])
    assert summary.main() == 1
    recheck = json.loads((path.parent / "evaluation-100-recheck.json").read_text())
    costs = json.loads((path.parent / "cost-analysis-100.json").read_text())
    assert recheck["recorded_pass_mismatches"] == ["run-024"]
    assert costs["overall"]["passed"] == 99
    assert costs["overall"]["failed"] == 1


@pytest.mark.parametrize("problem", ["incomplete", "unbalanced", "duplicate", "outside", "metadata"])
def test_rejects_incomplete_or_inconsistent_study_before_recheck(tmp_path, monkeypatch, problem):
    path, document = study(tmp_path)
    if problem == "incomplete":
        document["completed_attempts"] = 99
    elif problem == "unbalanced":
        document["runs"][-1]["task_id"] = document["runs"][-2]["task_id"]
    elif problem == "duplicate":
        document["runs"][-1]["id"] = document["runs"][-2]["id"]
    elif problem == "outside":
        document["runs"][-1]["run_dir"] = "../outside"
    else:
        document["runs"][-1]["estimated_cost_usd"] = 10
    path.write_text(json.dumps(document))
    monkeypatch.setattr(summary, "_recheck_run", lambda *args: pytest.fail("Invalid study must not be rechecked"))
    with pytest.raises(ValueError):
        summary.summarize_evaluation(path)
    assert not (path.parent / "cost-analysis-100.json").exists()


def write_csv(path, headers, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def fixture_hash():
    return hashlib.sha256((summary.ROOT / "fixtures/seed.json").read_bytes()).hexdigest()


def test_report_artifact_recheck_uses_fresh_fixture(tmp_path):
    baseline = tmp_path / "baseline.db"
    reset_database(baseline)
    headers, rows = reports.build_report(baseline, "monthly-revenue")
    write_csv(tmp_path / "export.csv", headers, rows)
    result = summary._recheck_run({"task_id": "monthly-revenue", "fixture_sha256": fixture_hash()}, tmp_path)
    assert result["passed"]


def test_workflow_recheck_detects_unintended_state_changes(tmp_path):
    final = tmp_path / "final.db"
    reset_database(final)
    workflows.initialize_workflow_data(final)
    headers, rows = workflows.execute_workflow(final, "customer-update", {"customer_id": "2", "email": "billing@beacon.example", "phone": "+1-555-0142"})
    write_csv(tmp_path / "export.csv", headers, rows)
    metadata = {"task_id": "customer-update", "fixture_sha256": fixture_hash()}
    assert summary._recheck_run(metadata, tmp_path)["passed"]
    import sqlite3
    with sqlite3.connect(final) as db:
        db.execute("UPDATE contacts SET phone='extra-change' WHERE customer_id=1")
    assert not summary._recheck_run(metadata, tmp_path)["passed"]


def test_office_source_preservation_is_record_consistency_not_live_claim(tmp_path):
    prepared = tmp_path / "prepared"
    office_tasks.prepare_office("calc-sort-export", prepared)
    shutil.copyfile(prepared / "inputs/calc-source.ods", tmp_path / "calc-source.ods")
    rows = sorted(office_tasks.CALC_ROWS, key=lambda row: (-float(row[2]), row[0]))
    write_csv(tmp_path / "export.csv", office_tasks.CALC_HEADERS, [dict(zip(office_tasks.CALC_HEADERS, row)) for row in rows])
    source_hash = hashlib.sha256((tmp_path / "calc-source.ods").read_bytes()).hexdigest()
    metadata = {"task_id": "calc-sort-export", "fixture_sha256": fixture_hash(), "input_sha256": source_hash}
    record = {"source_unchanged": True, "source_sha256_after": source_hash}
    (tmp_path / "verification.json").write_text(json.dumps(record))
    result = summary._recheck_run(metadata, tmp_path)
    assert result["passed"]
    assert "not a new observation" in result["source_preservation_basis"]
    record["source_sha256_after"] = "different"
    (tmp_path / "verification.json").write_text(json.dumps(record))
    assert not summary._recheck_run(metadata, tmp_path)["passed"]


def test_artifact_symlink_cannot_read_outside_run(tmp_path):
    directory = tmp_path / "run"
    directory.mkdir()
    (directory / "export.csv").symlink_to(tmp_path / "outside.csv")
    with pytest.raises(ValueError, match="outside"):
        summary._artifact(directory, "export.csv")
