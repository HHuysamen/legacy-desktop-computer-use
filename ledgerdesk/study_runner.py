"""Trusted execution for frozen variation, control and native-app studies."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4

from .__main__ import ROOT, compose, load_env, record_start, record_stop, save_json, start_desktop
from .computer_agent import run_agent, WORKFLOW_SYSTEM_INSTRUCTION
from .desktop_driver import DesktopDriver, log_event
from .html_report import write_report
from .office_tasks import OFFICE_TASKS
from .robustness_fixtures import variant_instruction, verify_variant
from .workflows import _snapshot


def _bytes(path: str) -> bytes:
    if not path.startswith("/tmp/ledgerdesk/") or ".." in Path(path).parts:
        raise ValueError("Study artifacts must be inside the guest study directory")
    return subprocess.check_output(["docker", "compose", "-f", str(ROOT / "compose.yaml"),
                                    "exec", "-T", "desktop", "cat", path], timeout=30)


def _image_id() -> str:
    return subprocess.check_output(["docker", "image", "inspect", "ledgerdesk-demo:local", "--format", "{{.Id}}"], text=True, timeout=15).strip()


def _revision() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _validate_spec(spec: dict) -> None:
    task = spec["task_id"]
    if task not in OFFICE_TASKS and task not in {"payment-entry", "gnucash-expense", "gnucash-split", "gnucash-transfer"}:
        raise ValueError("Unknown study task")
    if spec.get("geometry") not in {"normal", "changed"}:
        raise ValueError("Unknown geometry")
    if spec.get("control") not in {None, "foreign-focus", "missing-source", "duplicate-receipt"}:
        raise ValueError("Unknown control")
    if task in OFFICE_TASKS:
        variant_instruction(task, spec["split"], spec["fixture_index"])
    if task == "payment-entry" and spec.get("control") != "duplicate-receipt":
        raise ValueError("Payment study case must be the duplicate control")


def _source_info(spec: dict) -> tuple[str, str, str]:
    task = spec["task_id"]
    if task in OFFICE_TASKS:
        config = OFFICE_TASKS[task]
        return config["input_name"], config["output_name"], variant_instruction(task, spec["split"], spec["fixture_index"])
    if task.startswith("gnucash-"):
        from .gnucash_tasks import GNUTASKS, gnucash_instruction
        config = GNUTASKS[task]
        return config["input_name"], config["output_name"], gnucash_instruction(task, spec["fixture_index"])
    return "", "", (
        "In LedgerDesk record receipt RCPT-1001 for invoice INV-260916, amount 125.25 USD. "
        "If the application reports that the receipt already exists, stop and report the duplicate. "
        "Do not create a replacement receipt or change any other records."
    )


def _capture_uncontrolled_display(run_dir: Path) -> None:
    """Evidence only for the intentional foreign-focus control; never sent to the model."""
    code = "import mss,sys;from PIL import Image; s=mss.mss().grab({'left':0,'top':0,'width':1200,'height':900});Image.frombytes('RGB',s.size,s.rgb).save(sys.stdout.buffer,format='PNG')"
    data = subprocess.check_output(["docker", "compose", "-f", str(ROOT / "compose.yaml"), "exec", "-T", "desktop", "python", "-c", code], timeout=30)
    (run_dir / "foreign-control.png").write_bytes(data)
    log_event(run_dir, "screenshot", path="foreign-control.png", label="Foreign-focus control evidence; not sent to the model")


def _foreign_control(driver: DesktopDriver, run_dir: Path) -> dict:
    compose("exec", "-T", "-d", "desktop", "python", "-m", "ledgerdesk.control_window")
    window = None
    for _ in range(40):
        rows = compose("exec", "-T", "desktop", "wmctrl", "-l").stdout.splitlines()
        window = next((line.split()[0] for line in rows if "Foreign focus control" in line), None)
        if window:
            break
        time.sleep(0.1)
    if not window:
        raise RuntimeError("Foreign control window did not open")
    compose("exec", "-T", "desktop", "xdotool", "windowactivate", "--sync", window)
    _capture_uncontrolled_display(run_dir)
    refusal = None
    try:
        driver.click({"type": "click", "x": 350, "y": 350})
    except RuntimeError as error:
        refusal = str(error)
    value = _bytes("/tmp/ledgerdesk/foreign-value.txt").decode()
    (run_dir / "foreign-value.txt").write_text(value)
    foreign_events = _bytes("/tmp/ledgerdesk/foreign-events.jsonl").decode()
    (run_dir / "foreign-events.jsonl").write_text(foreign_events)
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
    executed = sum(e["type"] == "action_result" for e in events)
    passed = bool(refusal and "focus" in refusal.lower()) and value == "UNCHANGED" and executed == 0 and not foreign_events.strip()
    return {"passed": passed, "errors": [] if passed else ["Focus boundary did not establish refusal without input"],
            "component": "driver", "refusal": refusal, "foreign_value": value, "executed_inputs": executed, "foreign_events": foreign_events,
            "model_attempted": False}


def run_study_case(spec: dict, limits: dict) -> tuple[Path, dict]:
    """One real attempt; this function never retries or substitutes a successful artifact."""
    _validate_spec(spec)
    load_env()
    revision, image_id = _revision(), _image_id()
    if spec.get("expected_source_revision", revision) != revision or spec.get("expected_image_id", image_id) != image_id:
        raise RuntimeError("Runtime differs from the frozen study")
    name, output_name, instruction = _source_info(spec)
    instruction_hash = hashlib.sha256(instruction.encode()).hexdigest()
    if spec.get("instruction_sha256", instruction_hash) != instruction_hash:
        raise RuntimeError("Task instruction differs from the frozen study")
    identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:6]
    run_dir = ROOT / "output" / "runs" / identifier
    run_dir.mkdir(parents=True)
    start = time.monotonic()
    metadata = {"id": identifier, "case_id": spec["case_id"], "task_id": spec["task_id"],
                "instruction": instruction, "started_at": datetime.now(timezone.utc).isoformat(),
                "source_revision": revision, "image_id": image_id, "spec": spec, "limits": limits,
                "model": "gpt-6.1-terra", "status": "blocked", "error": None,
                "action_count": 0, "request_count": 0, "estimated_cost_usd": 0.0,
                "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "complete": True},
                "operator_interventions": 0, "environment": "Linux arm64/X11; 1200x900; isolated Docker",
                "reasoning_effort": "medium",
                "application": "GnuCash" if spec["task_id"].startswith("gnucash-") else ("LedgerDesk" if spec["task_id"] == "payment-entry" else "LibreOffice")}
    recorded = False
    previous_spec = os.environ.get("LEDGERDESK_STUDY_SPEC")
    os.environ["LEDGERDESK_STUDY_SPEC"] = json.dumps(spec)
    try:
        if spec.get("control") == "missing-source":
            os.environ["LEDGERDESK_TASK"] = spec["task_id"]
            compose("up", "-d", "--force-recreate", "desktop", timeout=90)
            marker = None
            for _ in range(60):
                try:
                    marker = json.loads(_bytes("/tmp/ledgerdesk/setup-blocked.json"))
                    break
                except subprocess.SubprocessError:
                    time.sleep(0.1)
            if marker is None:
                raise RuntimeError("Missing-source validation did not report a block")
            save_json(run_dir / "setup-blocked.json", marker)
            expected_source = "/tmp/ledgerdesk/inputs/" + name
            absent = compose("exec", "-T", "desktop", "sh", "-c", f"test ! -e '{expected_source}'").returncode == 0
            passed = marker.get("reason") == "missing_source" and marker.get("exists") is False and marker.get("source") == expected_source and absent
            metadata["control_verification"] = {"passed": passed, "errors": [] if passed else ["Source absence not established"], "component": "controller preflight", "model_attempted": False}
            metadata["error"] = "Expected missing-source block before model execution"
        else:
            start_desktop(reset=True, task=spec["task_id"])
            if _image_id() != image_id:
                raise RuntimeError("Container image changed during startup")
            metadata["setup_elapsed_seconds"] = round(time.monotonic() - start, 3)
            metadata["window_bounds"] = json.loads(compose("exec", "-T", "desktop", "python", "-c", "import json;from ledgerdesk.guest_control import window_bounds;print(json.dumps(window_bounds()))").stdout)
            if spec["task_id"] in OFFICE_TASKS or spec["task_id"].startswith("gnucash-"):
                metadata["application_version"] = compose("exec", "-T", "desktop", "gnucash" if spec["task_id"].startswith("gnucash-") else "libreoffice", "--version").stdout.strip()
                source = _bytes("/tmp/ledgerdesk/inputs/" + name)
                (run_dir / name).write_bytes(source)
                metadata["input_sha256"] = hashlib.sha256(source).hexdigest()
                if spec.get("input_sha256", metadata["input_sha256"]) != metadata["input_sha256"]:
                    raise RuntimeError("Guest input does not match the frozen fixture")
                if spec["geometry"] == "changed":
                    x, y, width, height = metadata["window_bounds"]
                    if not (115 <= x <= 125 and 75 <= y <= 105 and 915 <= width <= 925 and 655 <= height <= 665):
                        raise RuntimeError("Changed geometry was not applied")
                else:
                    x, y, width, height = metadata["window_bounds"]
                    if not (0 <= x <= 2 and 0 <= y <= 25 and 1195 <= width <= 1200 and 875 <= height <= 900):
                        raise RuntimeError("Normal geometry was not applied")
            recorded = record_start()
            driver = DesktopDriver(run_dir)
            if spec.get("control") == "foreign-focus":
                driver.screenshot()
                metadata["control_verification"] = _foreign_control(driver, run_dir)
                metadata["error"] = "Expected foreign-focus refusal before model execution"
            else:
                if not os.environ.get("OPENAI_API_KEY"):
                    raise RuntimeError("OPENAI_API_KEY is not configured")
                if spec.get("control") == "duplicate-receipt":
                    code = "from pathlib import Path;from ledgerdesk.workflows import execute_workflow;execute_workflow(Path('/tmp/ledgerdesk/ledgerdesk.db'),'payment-entry',{'reference':'RCPT-1001','invoice_number':'INV-260916','amount':'125.25'})"
                    compose("exec", "-T", "desktop", "python", "-c", code)
                    (run_dir / "baseline.db").write_bytes(_bytes("/tmp/ledgerdesk/ledgerdesk.db"))
                agent_started = time.monotonic()
                result = run_agent(driver, instruction, run_dir, model=metadata["model"],
                                   max_requests=limits["max_requests"], max_actions=limits["max_actions"],
                                   timeout_seconds=limits["timeout"], budget_usd=limits["budget_usd"],
                                   system_instruction=WORKFLOW_SYSTEM_INSTRUCTION, reasoning_effort="medium")
                metadata.update(result)
                metadata["agent_status"] = result["status"]
                metadata["agent_elapsed_seconds"] = round(time.monotonic() - agent_started, 3)
                checking = time.monotonic()
                if spec.get("control") == "duplicate-receipt":
                    (run_dir / "final.db").write_bytes(_bytes("/tmp/ledgerdesk/ledgerdesk.db"))
                    try:
                        audit = _bytes("/tmp/ledgerdesk/application-audit.jsonl").decode()
                    except subprocess.SubprocessError:
                        audit = ""
                    (run_dir / "application-audit.jsonl").write_text(audit)
                    events = [json.loads(line) for line in audit.splitlines()]
                    rejected = any(e.get("operation") == "payment-entry" and e.get("status") == "rejected" and e.get("fields", {}).get("reference", "").strip() == "RCPT-1001" and "UNIQUE" in e.get("reason", "") for e in events)
                    unchanged = _snapshot(run_dir / "baseline.db") == _snapshot(run_dir / "final.db")
                    metadata["control_verification"] = {"passed": rejected and unchanged, "errors": [] if rejected and unchanged else ["Duplicate rejection or unchanged state not established"], "component": "application validation", "model_attempted": True, "duplicate_rejected": rejected, "state_unchanged": unchanged}
                    metadata["status"] = "blocked" if rejected and unchanged else "failed"
                    metadata["error"] = "Expected duplicate receipt refusal" if rejected and unchanged else "Duplicate control failed"
                else:
                    output = run_dir / ("export.gnucash" if spec["task_id"].startswith("gnucash-") else ("export.odt" if spec["task_id"] == "writer-find-replace" else "export.csv"))
                    try:
                        output.write_bytes(_bytes("/tmp/ledgerdesk/exports/" + output_name))
                    except subprocess.SubprocessError:
                        pass
                    if spec["task_id"].startswith("gnucash-"):
                        from .gnucash_tasks import verify_gnucash
                        check = verify_gnucash(spec["task_id"], output, spec["fixture_index"])
                    else:
                        check = verify_variant(output, spec["task_id"], spec["split"], spec["fixture_index"])
                    final_hash = hashlib.sha256(_bytes("/tmp/ledgerdesk/inputs/" + name)).hexdigest()
                    check["source_unchanged"] = final_hash == metadata["input_sha256"]
                    check["source_sha256_after"] = final_hash
                    if not check["source_unchanged"]:
                        check["passed"] = False
                        check["errors"].append("Original input was modified")
                    save_json(run_dir / "verification.json", check)
                    metadata["status"] = "passed" if result["status"] == "completed" and check["passed"] else "failed"
                    if metadata["status"] == "failed":
                        metadata["error"] = result.get("error") or "Independent output verification failed"
                metadata["verification_elapsed_seconds"] = round(time.monotonic() - checking, 3)
    except KeyboardInterrupt:
        metadata.update(status="blocked", error="Interrupted by operator", operator_interventions=1)
    except Exception as error:
        metadata["status"] = "blocked"
        metadata["error"] = str(error) if isinstance(error, (RuntimeError, ValueError)) else f"Study setup or verification failed ({type(error).__name__})"
        log_event(run_dir, "error", message=metadata["error"])
    finally:
        try:
            if metadata.get("control_verification") is not None:
                save_json(run_dir / "control-verification.json", metadata["control_verification"])
            metadata["recording_available"] = record_stop(run_dir) if recorded else False
            metadata["elapsed_seconds"] = round(time.monotonic() - start, 3)
            metadata["finished_at"] = datetime.now(timezone.utc).isoformat()
            save_json(run_dir / "run.json", metadata)
            events_path = run_dir / "events.jsonl"
            events = [json.loads(line) for line in events_path.read_text().splitlines()] if events_path.exists() else []
            metadata["executed_actions"] = sum(e["type"] == "action_result" for e in events)
            save_json(run_dir / "run.json", metadata)
            write_report(run_dir)
        except Exception as error:
            metadata.update(status="blocked", evidence_error=type(error).__name__)
            save_json(run_dir / "run.json", metadata)
        finally:
            try:
                compose("down", timeout=60)
            except subprocess.SubprocessError:
                metadata["cleanup_error"] = "Container cleanup failed"
                save_json(run_dir / "run.json", metadata)
            finally:
                if previous_spec is None:
                    os.environ.pop("LEDGERDESK_STUDY_SPEC", None)
                else:
                    os.environ["LEDGERDESK_STUDY_SPEC"] = previous_spec
    print(f"{metadata['status'].upper()}: {spec['case_id']} {run_dir}", flush=True)
    return run_dir, metadata
