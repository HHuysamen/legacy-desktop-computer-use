import hashlib
import json
from pathlib import Path

import pytest

from scripts.package_evidence import package_evidence, TASKS


def evaluation_fixture(tmp_path):
    output = tmp_path / "output"
    entries = []
    for index in range(9):
        run_dir = output / "runs" / f"run-{index}"
        (run_dir / "screenshots").mkdir(parents=True)
        passed = index != 8
        metadata = {"id": f"run-{index}", "task_id": TASKS[index % 3], "status": "passed" if passed else "failed", "finished_at": "2026-11-08T00:00:00Z", "elapsed_seconds": index + 10, "action_count": index + 1, "request_count": index + 2, "estimated_cost_usd": 0.01 if passed else None, "usage": {"complete": passed}}
        (run_dir / "run.json").write_text(json.dumps(metadata))
        (run_dir / "events.jsonl").write_text('{"type":"response","text":"<script>synthetic</script>"}\n')
        (run_dir / "report.html").write_text(f"<!doctype html>Run {index}")
        (run_dir / "verification.json").write_text(json.dumps({"passed": passed}))
        (run_dir / "screenshots" / "001.png").write_bytes(b"example screenshot")
        (run_dir / "screenshots" / "002.png").write_bytes(b"final screenshot")
        (run_dir / "recording.mp4").write_bytes(b"example recording")
        (run_dir / "excluded-secret.env").write_text("MUST NOT BE PACKAGED")
        if passed:
            (run_dir / "export.csv").write_text("customer,revenue\nSynthetic,1.00\n")
        entries.append({"run_dir": str(run_dir.relative_to(tmp_path)), **metadata})
    path = output / "evaluation.json"
    path.write_text(json.dumps({"planned_attempts": 9, "completed_attempts": 9, "runs": entries}))
    return path


def test_packages_all_outcomes_and_exact_hashes(tmp_path):
    source = evaluation_fixture(tmp_path)
    destination = package_evidence(source, tmp_path / "examples")
    summary = json.loads((destination / "summary.json").read_text())
    assert summary["overall"]["attempts"] == 9
    assert summary["overall"]["verified"] == 8
    assert summary["overall"]["failed"] == 1
    assert summary["overall"]["usage_complete"] is False
    assert summary["overall"]["estimated_cost_usd_known"] == 0.08
    assert summary["tasks"][TASKS[0]]["median_elapsed_seconds"] == 13
    assert summary["tasks"][TASKS[2]]["action_range"] == [3, 9]
    assert (destination / "runs" / "run-8" / "run.json").is_file()
    assert not list(destination.rglob("*.env"))
    assert len(list(destination.rglob("*.mp4"))) == 1
    assert (destination / "demo.mp4").read_bytes() == b"example recording"
    assert (destination / "poster.png").read_bytes() == b"final screenshot"
    assert 'poster="poster.png"' in (destination / "index.html").read_text()
    manifest = json.loads((destination / "manifest.json").read_text())
    assert not any(item["path"] == "manifest.json" for item in manifest["files"])
    for item in manifest["files"]:
        assert hashlib.sha256((destination / item["path"]).read_bytes()).hexdigest() == item["sha256"]
    assert "Incomplete / unavailable" in (destination / "index.html").read_text()


def test_rejects_unfinished_or_external_run_without_output(tmp_path):
    source = evaluation_fixture(tmp_path)
    evaluation = json.loads(source.read_text())
    evaluation["completed_attempts"] = 8
    source.write_text(json.dumps(evaluation))
    with pytest.raises(ValueError, match="completed nine-attempt"):
        package_evidence(source, tmp_path / "examples")
    evaluation["completed_attempts"] = 9
    evaluation["runs"][0]["run_dir"] = "../outside"
    source.write_text(json.dumps(evaluation))
    with pytest.raises(ValueError, match="inside output/runs"):
        package_evidence(source, tmp_path / "examples")
    assert not (tmp_path / "examples").exists()


def test_optional_pilot_is_separate_from_denominator(tmp_path):
    source = evaluation_fixture(tmp_path)
    original = tmp_path / "output" / "runs" / "run-0"
    pilot = original.parent / "pilot-only"
    import shutil
    shutil.copytree(original, pilot)
    metadata = json.loads((pilot / "run.json").read_text())
    metadata["id"] = "pilot-only"
    (pilot / "run.json").write_text(json.dumps(metadata))
    destination = package_evidence(source, tmp_path / "examples", pilot=pilot)
    summary = json.loads((destination / "summary.json").read_text())
    assert summary["pilot"]["id"] == "pilot-only"
    assert summary["overall"]["attempts"] == 9
    assert summary["overall"]["verified"] == 8
    assert (destination / "pilot" / "pilot-only" / "report.html").is_file()
    assert "excluded from every count" in (destination / "index.html").read_text()


def test_file_symlink_cannot_read_outside_run_directory(tmp_path):
    source = evaluation_fixture(tmp_path)
    run_file = tmp_path / "output" / "runs" / "run-0" / "run.json"
    outside = tmp_path / "outside.json"
    outside.write_text(run_file.read_text())
    run_file.unlink()
    run_file.symlink_to(outside)
    with pytest.raises(ValueError, match="outside its run directory"):
        package_evidence(source, tmp_path / "examples")
    assert not (tmp_path / "examples").exists()
