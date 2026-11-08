from collections import Counter, defaultdict
from contextlib import contextmanager, nullcontext
import hashlib
import json
from pathlib import Path
import sys

import pytest

from scripts import run_robustness_study as study


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def manifest():
    fixtures, cases = [], []
    for task in study.OFFICE_TASKS:
        for split in ("development", "heldout"):
            for index in range(3):
                identifier = f"{task}-{split}-{index:02d}"
                item = {"fixture_id": identifier, "task_id": task, "split": split,
                        "fixture_index": index, "input_sha256": digest(identifier),
                        "instruction_sha256": digest(identifier + "instruction"),
                        "expected_sha256": digest(identifier + "expected")}
                fixtures.append(item)
                for geometry in ("normal", "changed"):
                    cases.append({**item, "case_id": f"{identifier}-{geometry}", "geometry": geometry, "control": None})
    return {"schema_version": 1, "fixtures": fixtures, "cases": cases}


@pytest.fixture
def context(tmp_path, monkeypatch):
    monkeypatch.setattr(study, "ROOT", tmp_path)
    source = tmp_path / "ledgerdesk/source.py"
    source.parent.mkdir()
    source.write_text("# frozen source\n")
    return {"source_revision": "a" * 40, "image_id": "sha256:" + "b" * 64,
            "environment": {"display": "1200x900", "platform": "test"},
            "code_files": {"ledgerdesk/source.py": hashlib.sha256(source.read_bytes()).hexdigest()},
            "fixtures": manifest()}


def runner(tmp_path, calls, *, cost=0.1, complete=True, control_proof=True, wrong_image=False):
    def invoke(case, limits):
        calls.append(case)
        assert limits == study.LIMITS
        directory = tmp_path / "output/runs" / case["case_id"]
        directory.mkdir(parents=True)
        (directory / "verification.json").write_text('{"passed":true}')
        metadata = {"status": "passed" if case["kind"] == "positive" else "blocked",
                    "request_count": 1, "estimated_cost_usd": cost, "usage": {"complete": complete},
                    "image_id": "c" * 64 if wrong_image else case["expected_image_id"],
                    "source_revision": case["expected_source_revision"], "input_sha256": case.get("input_sha256")}
        if control_proof:
            metadata["control_verification"] = {"passed": True, "errors": []}
        return directory, metadata
    return invoke


def test_plan_is_paired_distinct_balanced_and_deterministically_randomized():
    first = study.make_plan(manifest())
    assert first == study.make_plan(manifest())
    assert first != study.make_plan(manifest(), seed=99)
    assert len(first) == len({item["case_id"] for item in first}) == 30
    positive = [item for item in first if item["kind"] == "positive"]
    controls = [item for item in first if item["kind"] == "negative_control"]
    assert len(positive) == 24 and len(controls) == 6
    assert Counter(item["control"] for item in controls) == {"foreign-focus": 2, "missing-source": 2, "duplicate-receipt": 2}
    pairs = defaultdict(list)
    for item in positive:
        pairs[item["fixture_id"]].append(item)
    assert len(pairs) == 12
    for items in pairs.values():
        assert {item["geometry"] for item in items} == {"normal", "changed"}
        assert len({item["input_sha256"] for item in items}) == 1


def test_plan_rejects_unpaired_or_duplicate_input_fixtures():
    data = manifest()
    data["cases"][0]["input_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="Paired"):
        study.make_plan(data)
    data = manifest()
    data["fixtures"][1]["input_sha256"] = data["fixtures"][0]["input_sha256"]
    with pytest.raises(ValueError, match="distinct"):
        study.make_plan(data)


def test_plan_only_freezes_without_invoking_runner(context, tmp_path):
    directory = tmp_path / "study"
    result = study.run_study(context, directory, lambda *args: pytest.fail("No runner in plan-only mode"), plan_only=True)
    protocol = json.loads((directory / "protocol.json").read_text())
    assert result["completed"] == 0
    assert protocol["total_budget_usd"] == 20
    assert protocol["limits"] == study.LIMITS
    for field in ("code_sha256", "environment_sha256", "fixtures_sha256"):
        assert len(protocol[field]) == 64
    assert not (directory / "events.jsonl").exists()


def test_resume_appends_only_and_never_repeats_slots(context, tmp_path):
    calls = []
    directory = tmp_path / "study"
    invoke = runner(tmp_path, calls)
    first = study.run_study(context, directory, invoke, limit=5)
    protocol = (directory / "protocol.json").read_bytes()
    prefix = (directory / "events.jsonl").read_bytes()
    second = study.run_study(context, directory, invoke, limit=8)
    assert first["completed"] == 5 and second["completed"] == 8
    assert len(calls) == 8 and len({item["case_id"] for item in calls}) == 8
    assert (directory / "protocol.json").read_bytes() == protocol
    assert (directory / "events.jsonl").read_bytes().startswith(prefix)


def test_positive_and_control_grades_are_separate(context, tmp_path):
    calls = []
    result = study.run_study(context, tmp_path / "study", runner(tmp_path, calls))
    assert result["completed"] == 30
    assert result["grades"]["positive"] == {"completed": 24, "passed": 24, "failed": 0, "unverified": 0}
    assert result["grades"]["negative_control"] == {"completed": 6, "passed": 6, "failed": 0, "unverified": 0}
    assert result["estimated_cost_usd"] == pytest.approx(3.0)


def test_blocked_status_alone_does_not_pass_a_control(context, tmp_path):
    result = study.run_study(context, tmp_path / "study", runner(tmp_path, [], control_proof=False))
    assert result["grades"]["negative_control"]["unverified"] == 6
    assert result["grades"]["negative_control"]["passed"] == 0


def test_changed_code_or_context_is_rejected_before_calls(context, tmp_path):
    directory = tmp_path / "study"
    study.run_study(context, directory, plan_only=True)
    modified = {**context, "environment": {"display": "different"}}
    with pytest.raises(ValueError, match="changed"):
        study.run_study(modified, directory, lambda *args: pytest.fail("Changed context ran"))
    (tmp_path / "ledgerdesk/source.py").write_text("# source was changed\n")
    with pytest.raises(ValueError, match="code hash"):
        study.run_study(context, directory, lambda *args: pytest.fail("Changed code ran"))


def test_pending_start_is_retained_as_unknown_without_reexecution(context, tmp_path):
    directory = tmp_path / "study"
    study.run_study(context, directory, plan_only=True)
    protocol = json.loads((directory / "protocol.json").read_text())
    case = protocol["plan"][0]
    study._append(directory / "events.jsonl", {"event": "started", "protocol_sha256": hashlib.sha256((directory / "protocol.json").read_bytes()).hexdigest(), "case_id": case["case_id"], "kind": case["kind"]})
    result = study.run_study(context, directory, lambda *args: pytest.fail("Unknown slot repeated"))
    assert result["completed"] == 1 and result["remaining"] == 29
    assert result["estimated_cost_usd"] is None
    assert result["budget_reserved_usd"] == 1.0
    assert "Interrupted" in result["stop_reason"]


def test_runner_exception_is_sanitized_and_does_not_continue(context, tmp_path):
    def fail(*args):
        raise RuntimeError("Authorization secret-MUST-NOT-APPEAR")
    directory = tmp_path / "study"
    result = study.run_study(context, directory, fail)
    assert result["completed"] == 1
    assert result["cost_complete"] is False
    assert "secret-MUST-NOT-APPEAR" not in (directory / "events.jsonl").read_text()


@pytest.mark.parametrize("complete,cost", [(True, 1.0), (False, None)])
def test_budget_reserves_unknown_attempts_and_stops_before_overspend(context, tmp_path, complete, cost):
    calls = []
    result = study.run_study(context, tmp_path / "study", runner(tmp_path, calls, cost=cost, complete=complete))
    assert len(calls) == result["completed"] == 20
    assert result["remaining"] == 10
    assert result["budget_reserved_usd"] == 20.0
    assert "budget" in result["stop_reason"]
    if not complete:
        assert result["estimated_cost_usd"] is None


def test_environment_drift_is_retained_and_stops_further_calls(context, tmp_path):
    result = study.run_study(context, tmp_path / "study", runner(tmp_path, [], wrong_image=True))
    assert result["completed"] == 1
    assert result["stop_reason"]
    assert sum(group["failed"] for group in result["grades"].values()) == 1


def test_corrupt_or_reordered_ledger_is_rejected(context, tmp_path):
    directory = tmp_path / "study"
    study.run_study(context, directory, runner(tmp_path, []), limit=1)
    ledger = directory / "events.jsonl"
    lines = ledger.read_text().splitlines()
    ledger.write_text(lines[1] + "\n" + lines[0] + "\n")
    with pytest.raises(ValueError, match="duplicate or out-of-order"):
        study.run_study(context, directory, lambda *args: pytest.fail("Corrupt ledger ran"))


def test_cli_returns_failure_for_complete_study_with_failed_grade(context, tmp_path, monkeypatch):
    from ledgerdesk import __main__ as cli
    monkeypatch.setattr(cli, "session_lock", nullcontext)
    context_path = tmp_path / "context.json"
    context_path.write_text(json.dumps(context))
    monkeypatch.setattr(sys, "argv", ["study", "--context", str(context_path)])
    monkeypatch.setattr(study, "run_study", lambda *args, **kwargs: {
        "completed": 30, "planned": 30, "stop_reason": None,
        "grades": {"positive": {"failed": 1, "unverified": 0}, "negative_control": {"failed": 0, "unverified": 0}},
    })
    assert study.main() == 1


def test_cli_holds_shared_desktop_lock_around_actual_run(context, tmp_path, monkeypatch):
    from ledgerdesk import __main__ as cli
    context_path = tmp_path / "context.json"
    context_path.write_text(json.dumps(context))
    monkeypatch.setattr(sys, "argv", ["study", "--context", str(context_path)])
    state = {"held": False}

    @contextmanager
    def lock():
        state["held"] = True
        try:
            yield
        finally:
            state["held"] = False

    def run(*args, **kwargs):
        assert state["held"]
        return {"planned": 30, "completed": 30, "stop_reason": None,
                "grades": {"positive": {"failed": 0, "unverified": 0}}}

    monkeypatch.setattr(cli, "session_lock", lock)
    monkeypatch.setattr(study, "run_study", run)
    assert study.main() == 0
    assert state["held"] is False


def test_plan_only_bypasses_shared_desktop_lock(context, tmp_path, monkeypatch):
    from ledgerdesk import __main__ as cli
    context_path = tmp_path / "context.json"
    context_path.write_text(json.dumps(context))
    monkeypatch.setattr(sys, "argv", ["study", "--context", str(context_path), "--plan-only"])
    monkeypatch.setattr(cli, "session_lock", lambda: pytest.fail("Plan-only must not claim a desktop"))
    monkeypatch.setattr(study, "run_study", lambda *args, **kwargs: {
        "planned": 30, "completed": 0, "stop_reason": "Plan only",
        "grades": {"positive": {"failed": 0, "unverified": 0}},
    })
    assert study.main() == 0


def test_busy_shared_desktop_lock_prevents_runner_call(context, tmp_path, monkeypatch):
    from ledgerdesk import __main__ as cli
    context_path = tmp_path / "context.json"
    context_path.write_text(json.dumps(context))
    monkeypatch.setattr(sys, "argv", ["study", "--context", str(context_path)])

    @contextmanager
    def busy():
        raise RuntimeError("Desktop already owned")
        yield

    monkeypatch.setattr(cli, "session_lock", busy)
    monkeypatch.setattr(study, "run_study", lambda *args, **kwargs: pytest.fail("Must not run without ownership"))
    with pytest.raises(RuntimeError, match="already owned"):
        study.main()


def gnucash_manifest():
    fixtures, cases = [], []
    for task in study.GNUCASH_TASKS:
        for index in range(3):
            identifier = f"{task}-{index:02d}"
            item = {"fixture_id": identifier, "task_id": task, "fixture_index": index,
                    "input_sha256": digest(f"book-{index}"),
                    "instruction_sha256": digest(identifier + "instruction"),
                    "expected_sha256": digest(identifier + "expected")}
            fixtures.append(item)
            cases.append({**item, "case_id": identifier, "geometry": "normal", "control": None})
    return {"protocol": "gnucash-native-v1", "fixtures": fixtures, "cases": cases}


def test_explicit_gnucash_plan_contains_nine_cases_and_no_controls():
    first = study.make_plan(gnucash_manifest())
    assert first == study.make_plan(gnucash_manifest())
    assert len(first) == len({case["case_id"] for case in first}) == 9
    assert Counter(case["task_id"] for case in first) == {task: 3 for task in study.GNUCASH_TASKS}
    assert all(case["kind"] == "positive" and case["control"] is None for case in first)


def test_gnucash_campaign_uses_ten_dollar_budget_and_caps_at_nine_cases(context, tmp_path):
    context = {**context, "campaign": "gnucash", "fixtures": gnucash_manifest()}
    calls = []
    directory = tmp_path / "gnu-study"
    result = study.run_study(context, directory, runner(tmp_path, calls, cost=1.0))
    protocol = json.loads((directory / "protocol.json").read_text())
    assert result["planned"] == result["completed"] == len(calls) == 9
    assert result["protocol"] == "gnucash-native-9-v1"
    assert result["total_budget_usd"] == 10
    assert result["estimated_cost_usd"] == 9
    assert protocol["planned_positive_cases"] == 9
    assert protocol["planned_negative_controls"] == 0
    assert result["grades"]["negative_control"]["completed"] == 0


def test_gnucash_manifest_requires_explicit_matching_campaign(context, tmp_path):
    with pytest.raises(ValueError, match="do not agree"):
        study.run_study({**context, "campaign": "gnucash"}, tmp_path / "wrong", plan_only=True)
    context = {**context, "campaign": "gnucash", "fixtures": gnucash_manifest()}
    context["fixtures"]["cases"][0]["geometry"] = "changed"
    with pytest.raises(ValueError, match="normal-geometry"):
        study.run_study(context, tmp_path / "wrong", plan_only=True)
