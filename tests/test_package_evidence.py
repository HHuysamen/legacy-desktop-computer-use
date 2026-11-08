import hashlib
import json
from pathlib import Path

import pytest

from scripts.package_evidence import package_evidence, TASKS


def evaluation_fixture(tmp_path, count=9, filename="evaluation.json"):
    output = tmp_path / "output"
    entries = []
    for index in range(count):
        run_dir = output / "runs" / f"run-{index}"
        (run_dir / "screenshots").mkdir(parents=True, exist_ok=True)
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
    path = output / filename
    path.write_text(json.dumps({"planned_attempts": count, "completed_attempts": count, "runs": entries}))
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


def test_packages_balanced_extension_without_altering_original_evidence(tmp_path):
    original = evaluation_fixture(tmp_path)
    original_bytes = original.read_bytes()
    original_package = package_evidence(original, tmp_path / "examples" / "evaluation")
    original_files = {path.relative_to(original_package): path.read_bytes() for path in original_package.rglob("*") if path.is_file()}
    extension = evaluation_fixture(tmp_path, count=24, filename="evaluation-24.json")
    destination = package_evidence(extension, tmp_path / "examples" / "evaluation-24")
    summary = json.loads((destination / "summary.json").read_text())
    assert summary["planned_attempts"] == summary["completed_attempts"] == 24
    assert summary["overall"]["verified"] == 23
    assert summary["overall"]["failed"] == 1
    assert summary["overall"]["estimated_cost_usd_known"] == 0.23
    assert all(stats["attempts"] == 8 for stats in summary["tasks"].values())
    html = (destination / "index.html").read_text()
    assert "23 of 24 attempts" in html
    assert "8 attempts each" in html
    assert "All 24 attempts" in html
    assert "nine" not in html.lower()
    assert original.read_bytes() == original_bytes
    assert {path.relative_to(original_package): path.read_bytes() for path in original_package.rglob("*") if path.is_file()} == original_files


@pytest.mark.parametrize("count", [0, 20])
def test_requires_a_positive_multiple_of_three(tmp_path, count):
    source = evaluation_fixture(tmp_path)
    data = json.loads(source.read_text())
    data["planned_attempts"] = count
    source.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="positive multiple of three"):
        package_evidence(source, tmp_path / "examples")


def test_rejects_unbalanced_extension(tmp_path):
    source = evaluation_fixture(tmp_path, count=24)
    data = json.loads(source.read_text())
    data["runs"][0]["task_id"] = TASKS[1]
    source.write_text(json.dumps(data))
    run_file = tmp_path / data["runs"][0]["run_dir"] / "run.json"
    metadata = json.loads(run_file.read_text())
    metadata["task_id"] = TASKS[1]
    run_file.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="exactly 8 attempts"):
        package_evidence(source, tmp_path / "examples")
