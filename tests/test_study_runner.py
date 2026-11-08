from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
from types import SimpleNamespace

import pytest

from ledgerdesk import robustness_fixtures, study_runner, workflows
from ledgerdesk.seed_data import reset_database


def case(*, control=None, geometry="normal"):
    item = next(item for item in robustness_fixtures.variant_manifest()["cases"]
                if item["task_id"] == "writer-find-replace" and item["split"] == "development"
                and item["fixture_index"] == 0 and item["geometry"] == geometry)
    return {**item, "control": control, "expected_image_id": "sha256:" + "b" * 64,
            "expected_source_revision": "a" * 40}


@pytest.fixture
def transport(tmp_path, monkeypatch):
    monkeypatch.setattr(study_runner, "ROOT", tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "unused-test-value")
    monkeypatch.setenv("LEDGERDESK_STUDY_SPEC", "previous-value")
    monkeypatch.setattr(study_runner, "_revision", lambda: "a" * 40)
    monkeypatch.setattr(study_runner, "_image_id", lambda: "sha256:" + "b" * 64)
    prepared = tmp_path / "prepared"
    robustness_fixtures.prepare_variant("writer-find-replace", "development", 0, prepared)
    source = (prepared / "inputs/writer-source.odt").read_bytes()
    state = {"calls": [], "agent_calls": [], "bounds": [0, 19, 1200, 881],
             "source": source, "source_after": source, "source_reads": 0,
             "marker": {"reason": "missing_source", "source": "/tmp/ledgerdesk/inputs/writer-source.odt", "exists": False},
             "agent_status": "completed", "cleanup_fails": False, "audit": "", "foreign_events": ""}

    def compose(*args, **kwargs):
        state["calls"].append(args)
        if args == ("down",):
            if state["cleanup_fails"]:
                raise subprocess.CalledProcessError(1, "docker compose down")
            return SimpleNamespace(stdout="", returncode=0)
        if args[-1] == "--version":
            return SimpleNamespace(stdout="LibreOffice test-version")
        if "window_bounds" in str(args[-1]):
            return SimpleNamespace(stdout=json.dumps(state["bounds"]))
        if "wmctrl" in args:
            return SimpleNamespace(stdout="0x1234 0 test Foreign focus control")
        return SimpleNamespace(stdout="", returncode=0)

    def read(path):
        if path.endswith("setup-blocked.json"):
            return json.dumps(state["marker"]).encode()
        if path.endswith("writer-source.odt"):
            state["source_reads"] += 1
            return state["source"] if state["source_reads"] == 1 else state["source_after"]
        if path.endswith("writer-find-replace.odt"):
            return b"output checked by independent mocked verifier"
        if path.endswith("ledgerdesk.db"):
            return state["db"] if state.get("db_reads", 0) == 0 else state.get("final_db", state["db"])
        if path.endswith("application-audit.jsonl"):
            return state["audit"].encode()
        if path.endswith("foreign-value.txt"):
            return b"UNCHANGED"
        if path.endswith("foreign-events.jsonl"):
            return state["foreign_events"].encode()
        raise AssertionError(path)

    def agent(*args, **kwargs):
        state["agent_calls"].append((args, kwargs))
        # The duplicate test can substitute a changed final snapshot after the baseline was captured.
        if "db" in state:
            state["db_reads"] = 1
        return {"status": state["agent_status"], "request_count": 1, "action_count": 1,
                "estimated_cost_usd": 0.1, "usage": {"complete": True}}

    monkeypatch.setattr(study_runner, "compose", compose)
    monkeypatch.setattr(study_runner, "_bytes", read)
    monkeypatch.setattr(study_runner, "start_desktop", lambda **kwargs: state["calls"].append(("start", kwargs)))
    monkeypatch.setattr(study_runner, "record_start", lambda: False)
    monkeypatch.setattr(study_runner, "run_agent", agent)
    monkeypatch.setattr(study_runner, "verify_variant", lambda *args: {"passed": True, "errors": [], "headers": [], "rows": []})
    monkeypatch.setattr(study_runner, "write_report", lambda *args: None)
    monkeypatch.setattr(study_runner, "_capture_uncontrolled_display", lambda *args: None)

    class Driver:
        def __init__(self, run_dir):
            self.run_dir = run_dir

        def screenshot(self):
            (self.run_dir / "events.jsonl").write_text('{"type":"screenshot"}\n')

        def click(self, action):
            raise RuntimeError("Target application lost focus")

    monkeypatch.setattr(study_runner, "DesktopDriver", Driver)
    return state


LIMITS = {"max_requests": 30, "max_actions": 80, "timeout": 420, "budget_usd": 1.0}


def test_wrong_frozen_revision_or_image_stops_before_launch(transport):
    spec = case()
    spec["expected_image_id"] = "sha256:" + "c" * 64
    with pytest.raises(RuntimeError, match="frozen"):
        study_runner.run_study_case(spec, LIMITS)
    assert not transport["calls"] and not transport["agent_calls"]


def test_wrong_frozen_input_stops_before_model(transport):
    spec = {**case(), "input_sha256": "0" * 64}
    directory, result = study_runner.run_study_case(spec, LIMITS)
    assert result["status"] == "blocked"
    assert "frozen fixture" in result["error"]
    assert not transport["agent_calls"]
    assert (directory / "run.json").exists()


def test_wrong_frozen_instruction_stops_before_model(transport):
    spec = {**case(), "instruction_sha256": "0" * 64}
    with pytest.raises(RuntimeError, match="instruction"):
        study_runner.run_study_case(spec, LIMITS)
    assert not transport["calls"]
    assert not transport["agent_calls"]


def test_changed_geometry_rejects_wrong_height_before_model(transport):
    transport["bounds"] = [120, 99, 920, 800]
    _, result = study_runner.run_study_case(case(geometry="changed"), LIMITS)
    assert result["status"] == "blocked"
    assert not transport["agent_calls"]


def test_changed_geometry_accepts_expected_client_area(transport):
    transport["bounds"] = [120, 99, 920, 660]
    _, result = study_runner.run_study_case(case(geometry="changed"), LIMITS)
    assert result["status"] == "passed"
    assert len(transport["agent_calls"]) == 1


def test_normal_geometry_cannot_silently_use_changed_window(transport):
    transport["bounds"] = [120, 99, 920, 660]
    _, result = study_runner.run_study_case(case(), LIMITS)
    assert result["status"] == "blocked"
    assert not transport["agent_calls"]


@pytest.mark.parametrize("agent_status,expected", [("completed", "passed"), ("failed", "failed")])
def test_artifact_pass_alone_does_not_upgrade_failed_agent(transport, agent_status, expected):
    transport["agent_status"] = agent_status
    directory, result = study_runner.run_study_case(case(), LIMITS)
    assert result["status"] == expected
    assert result["agent_status"] == agent_status
    assert result["estimated_cost_usd"] == 0.1
    assert (directory / "verification.json").exists()
    kwargs = transport["agent_calls"][0][1]
    assert (kwargs["max_requests"], kwargs["max_actions"], kwargs["timeout_seconds"], kwargs["budget_usd"]) == (30, 80, 420, 1.0)


def test_modified_source_fails_even_with_valid_output(transport):
    transport["source_after"] = b"source changed"
    directory, result = study_runner.run_study_case(case(), LIMITS)
    assert result["status"] == "failed"
    assert json.loads((directory / "verification.json").read_text())["source_unchanged"] is False


@pytest.mark.parametrize("wrong_source", [False, True])
def test_missing_source_control_checks_exact_target_and_makes_no_model_call(transport, wrong_source):
    if wrong_source:
        transport["marker"]["source"] = "/tmp/ledgerdesk/inputs/unrelated.odt"
    directory, result = study_runner.run_study_case(case(control="missing-source"), LIMITS)
    assert result["status"] == "blocked"
    assert result["control_verification"]["passed"] is not wrong_source
    assert not transport["agent_calls"]
    assert result["request_count"] == 0 and result["estimated_cost_usd"] == 0
    assert (directory / "setup-blocked.json").exists()


def test_foreign_focus_control_has_no_model_call(transport):
    directory, result = study_runner.run_study_case(case(control="foreign-focus"), LIMITS)
    assert result["control_verification"]["passed"] is True
    assert result["control_verification"]["component"] == "driver"
    assert not transport["agent_calls"]
    assert (directory / "control-verification.json").exists()


def test_foreign_control_rejects_click_that_happened_before_driver_error(transport):
    transport["foreign_events"] = '{"event":"button_press","x":350,"y":350}\n'
    _, result = study_runner.run_study_case(case(control="foreign-focus"), LIMITS)
    assert result["control_verification"]["passed"] is False
    assert not transport["agent_calls"]


@pytest.mark.parametrize("rejected,changed,expected", [(True, False, True), (False, False, False), (True, True, False)])
def test_duplicate_control_requires_rejection_and_unchanged_state(transport, tmp_path, rejected, changed, expected):
    database = tmp_path / "receipt.db"
    reset_database(database)
    workflows.initialize_workflow_data(database)
    workflows.execute_workflow(database, "payment-entry", {"reference": "RCPT-1001", "invoice_number": "INV-260916", "amount": "125.25"})
    transport["db"] = database.read_bytes()
    if changed:
        with closing(sqlite3.connect(database)) as db, db:
            db.execute("UPDATE contacts SET phone='unexpected' WHERE customer_id=1")
        transport["final_db"] = database.read_bytes()
    if rejected:
        transport["audit"] = json.dumps({"operation": "payment-entry", "status": "rejected",
                                          "fields": {"reference": "RCPT-1001"},
                                          "reason": "UNIQUE constraint failed: receipts.reference"}) + "\n"
    spec = {"case_id": "control-duplicate-receipt-00", "task_id": "payment-entry", "control": "duplicate-receipt",
            "geometry": "normal", "expected_image_id": "sha256:" + "b" * 64, "expected_source_revision": "a" * 40}
    _, result = study_runner.run_study_case(spec, LIMITS)
    assert result["control_verification"]["passed"] is expected
    assert len(transport["agent_calls"]) == 1


def test_cleanup_failure_preserves_known_result_and_restores_environment(transport, monkeypatch):
    transport["cleanup_fails"] = True
    _, result = study_runner.run_study_case(case(), LIMITS)
    assert result["status"] == "passed"
    assert result["estimated_cost_usd"] == 0.1
    import os
    assert os.environ["LEDGERDESK_STUDY_SPEC"] == "previous-value"


def test_report_failure_still_cleans_up_and_restores_environment(transport, monkeypatch):
    def fail(*args):
        raise OSError("Report could not be written")
    monkeypatch.setattr(study_runner, "write_report", fail)
    try:
        study_runner.run_study_case(case(), LIMITS)
    except OSError:
        pass
    import os
    assert ("down",) in transport["calls"]
    assert os.environ["LEDGERDESK_STUDY_SPEC"] == "previous-value"
