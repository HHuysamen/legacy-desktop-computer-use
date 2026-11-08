import argparse
from contextlib import closing
import csv
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sqlite3

import pytest

from ledgerdesk import __main__ as cli, computer_agent, guest_control, launch, workflows
from ledgerdesk.seed_data import reset_database
from scripts import extend_evaluation
from collections import Counter


def test_expanded_registry_has_ten_distinct_tasks():
    assert len(cli.TASKS) == 10
    for task in cli.TASKS:
        assert cli.instruction_for(task, "2026-10-15").strip()


def test_extension_plan_adds_exactly_76_unique_attempts_for_100_total():
    queue = extend_evaluation.plan()
    original = list(cli.REPORTS)
    new_tasks = [task for task in cli.TASKS if task not in cli.REPORTS]
    assert len(original) == 3 and len(new_tasks) == 7
    assert queue == (
        [{"task": task, "repetition": repetition} for repetition in (9, 10) for task in original]
        + [{"task": task, "repetition": repetition} for repetition in range(1, 11) for task in new_tasks]
    )
    assert len(queue) == len({(item["task"], item["repetition"]) for item in queue}) == 76
    combined_counts = Counter({task: 8 for task in original})
    combined_counts.update(item["task"] for item in queue)
    assert combined_counts == Counter({task: 10 for task in cli.TASKS})
    assert sum(combined_counts.values()) == 100


@pytest.mark.parametrize("unintended_change", [False, True])
def test_run_task_dispatches_payment_to_state_verifier(tmp_path, monkeypatch, unintended_change):
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures/seed.json").write_bytes(b"synthetic fixture identity")
    fixture_hash = hashlib.sha256(b"synthetic fixture identity").hexdigest()
    final_db = tmp_path / "guest-final.db"
    reset_database(final_db)
    workflows.initialize_workflow_data(final_db)
    headers, rows = workflows.execute_workflow(final_db, "payment-entry", {
        "reference": "RCPT-1001", "invoice_number": "INV-260916", "amount": "125.25",
    })
    if unintended_change:
        with closing(sqlite3.connect(final_db)) as db, db:
            db.execute("UPDATE contacts SET email='unintended@example.test' WHERE customer_id=1")

    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "unused-local-test-value")
    monkeypatch.setattr(cli, "start_desktop", lambda **kwargs: None)
    monkeypatch.setattr(cli, "record_start", lambda: False)
    monkeypatch.setattr(cli, "DesktopDriver", lambda run_dir: object())

    def compose(*args, **kwargs):
        return SimpleNamespace(stdout=fixture_hash + "  seed.json" if "sha256sum" in args else "image-digest")

    monkeypatch.setattr(cli, "compose", compose)

    def process(arguments, **kwargs):
        if arguments[:2] == ["git", "rev-parse"]:
            return SimpleNamespace(stdout="test-commit")
        assert arguments[-1] == "/tmp/ledgerdesk/ledgerdesk.db"
        return SimpleNamespace(stdout=final_db.read_bytes())

    monkeypatch.setattr(cli.subprocess, "run", process)

    def collect(run_dir, task):
        assert task == "payment-entry"
        path = run_dir / "export.csv"
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
        return path

    monkeypatch.setattr(cli, "collect_export", collect)

    def agent(*args, **kwargs):
        assert kwargs["system_instruction"] == computer_agent.WORKFLOW_SYSTEM_INSTRUCTION
        return {"status": "completed", "action_count": 1, "request_count": 1}

    monkeypatch.setattr(computer_agent, "run_agent", agent)
    args = argparse.Namespace(task="payment-entry", as_of="2026-10-15", model="gpt-6.1-terra",
                              max_requests=20, max_actions=40, timeout=300, budget_usd=2)
    run_dir, result = cli.run_task(args)
    assert result["status"] == ("failed" if unintended_change else "passed")
    verification = json.loads((run_dir / "verification.json").read_text())
    assert verification["passed"] is not unintended_change
    assert (run_dir / "final.db").is_file()
    assert not (run_dir / "oracle.db").exists()


def test_office_reverification_rejects_inconsistent_source_preservation(tmp_path, monkeypatch):
    (tmp_path / "fixtures").mkdir()
    fixture = tmp_path / "fixtures/seed.json"
    fixture.write_bytes(b"fixture identity")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    source = b"saved original office input"
    (run_dir / "calc-source.ods").write_bytes(source)
    (run_dir / "export.csv").write_text("valid output represented by mocked verifier")
    metadata = {
        "task_id": "calc-sort-export", "status": "passed",
        "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
        "input_sha256": hashlib.sha256(source).hexdigest(),
    }
    (run_dir / "run.json").write_text(json.dumps(metadata))
    (run_dir / "verification.json").write_text(json.dumps({
        "passed": True, "source_unchanged": True, "source_sha256_after": "different-source-hash",
    }))
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "verify_office", lambda *args: {"passed": True, "errors": [], "headers": [], "rows": []})
    monkeypatch.setattr(cli, "write_report", lambda *args: None)
    code = cli.dispatch(argparse.Namespace(command="verify", run_dir=run_dir))
    assert code == 1
    assert not json.loads((run_dir / "verification.json").read_text())["passed"]


def test_office_dialogs_require_the_bound_process(monkeypatch):
    monkeypatch.setenv("LEDGERDESK_TASK", "writer-find-replace")
    monkeypatch.setattr(guest_control, "Path", lambda _path: SimpleNamespace(read_text=lambda: "222"))

    def command(*args):
        if args == ("wmctrl", "-lpG"):
            return "0x000001 0 222 0 0 1200 850 demo Writer — LibreOffice\n0x000002 0 222 200 100 700 500 demo Save As\n0x000003 0 999 100 100 700 500 demo Other app"
        if args[0] == "xwininfo":
            return "  Absolute upper-left X: 200\n  Absolute upper-left Y: 100\n  Width: 700\n  Height: 500"
        return "2"

    monkeypatch.setattr(guest_control, "command", command)
    assert guest_control.window_bounds() == (200, 100, 700, 500)


def test_office_zero_process_identity_is_rejected(monkeypatch):
    monkeypatch.setenv("LEDGERDESK_TASK", "writer-find-replace")
    monkeypatch.setattr(guest_control, "Path", lambda _path: SimpleNamespace(read_text=lambda: "0"))
    monkeypatch.setattr(guest_control, "command", lambda *args: "0x000001 0 0 0 0 1200 850 demo Unknown window" if args[0] == "wmctrl" else "1")
    with pytest.raises(RuntimeError):
        guest_control.window_bounds()


def test_office_startup_rejects_unknown_window_pid(monkeypatch):
    monkeypatch.setenv("LEDGERDESK_TASK", "writer-find-replace")
    monkeypatch.setattr(launch, "prepare_office", lambda task: ["libreoffice", "synthetic.odt"])
    monkeypatch.setattr(launch.subprocess, "Popen", lambda *args: SimpleNamespace(pid=222, wait=lambda: None))
    monkeypatch.setattr(launch.subprocess, "check_output", lambda *args, **kwargs: "0x000001 0 0 demo LibreOffice Writer")
    monkeypatch.setattr(launch.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="0x000001 0 0 demo LibreOffice Writer"))
    monkeypatch.setattr(launch.time, "sleep", lambda *args: None)
    monkeypatch.setattr(launch, "Path", lambda *args: SimpleNamespace(write_text=lambda value: None))
    with pytest.raises(RuntimeError):
        launch.main()
