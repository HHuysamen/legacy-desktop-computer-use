"""Reproducible desktop lifecycle, evaluation and trusted verification."""
from __future__ import annotations

import argparse
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

from .desktop_driver import ROOT, DesktopDriver, compose, log_event
from .html_report import write_report
from .reports import REPORTS
from .seed_data import reset_database
from .tasks import task_instruction
from .verify import verify_csv


def load_env(path: Path = ROOT / ".env") -> None:
    """Read only the two supported names, without executing shell syntax."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        name, separator, value = line.strip().partition("=")
        if separator and name in {"OPENAI_API_KEY", "OPENAI_MODEL"}:
            os.environ.setdefault(name, value.strip().strip("\"'"))


def save_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


@contextmanager
def session_lock():
    """One process owns the shared desktop, including all suite attempts."""
    directory = ROOT / "output"
    directory.mkdir(exist_ok=True)
    with (directory / ".session.lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another LedgerDesk command owns the desktop. Wait for it to finish.") from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def start_desktop(*, build: bool = False, reset: bool = False) -> None:
    if build:
        subprocess.run(["docker", "compose", "-f", str(ROOT / "compose.yaml"), "build"], check=True)
    args = ["up", "-d", "--wait", "--wait-timeout", "60"]
    if reset:
        args.append("--force-recreate")
    compose(*args, timeout=90)


def collect_export(run_dir: Path, report_id: str) -> Path:
    if report_id not in REPORTS:
        raise ValueError("Unknown report")
    target = run_dir / "export.csv"
    # Docker's archive endpoint cannot reliably copy tmpfs files. This trusted,
    # fixed-path read happens after the model loop; it is never an agent tool.
    exported = compose("exec", "-T", "desktop", "cat", f"/tmp/ledgerdesk/exports/{report_id}.csv").stdout
    target.write_text(exported, encoding="utf-8")
    return target


def record_start() -> bool:
    """Record only the fictional guest display, never the host screen."""
    try:
        compose("exec", "-T", "-d", "desktop", "ffmpeg", "-y", "-loglevel", "error",
                "-f", "x11grab", "-framerate", "8", "-video_size", "1200x900",
                "-i", ":99", "-an", "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p", "/tmp/ledgerdesk/recording.mp4")
        return True
    except subprocess.SubprocessError:
        return False


def record_stop(run_dir: Path) -> bool:
    try:
        compose("exec", "-T", "desktop", "pkill", "-INT", "-x", "ffmpeg")
        # Wait for the MP4 trailer before copying; no model action is retried.
        for _ in range(40):
            try:
                compose("exec", "-T", "desktop", "pgrep", "-x", "ffmpeg")
            except subprocess.CalledProcessError:
                break
            time.sleep(0.1)
        else:
            return False
        recording = subprocess.run(
            ["docker", "compose", "-f", str(ROOT / "compose.yaml"), "exec", "-T", "desktop",
             "cat", "/tmp/ledgerdesk/recording.mp4"], capture_output=True, check=True, timeout=30,
        )
        (run_dir / "recording.mp4").write_bytes(recording.stdout)
        return True
    except subprocess.SubprocessError:
        return False


def run_task(args) -> tuple[Path, dict]:
    from .computer_agent import run_agent
    identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:6]
    run_dir = ROOT / "output" / "runs" / identifier
    run_dir.mkdir(parents=True)
    started = time.monotonic()
    metadata = {
        "id": identifier, "task_id": args.task, "instruction": task_instruction(args.task, args.as_of),
        "started_at": datetime.now(timezone.utc).isoformat(), "as_of": args.as_of,
        "model": args.model, "status": "blocked", "error": None,
        "action_count": 0, "request_count": 0,
        "limits": {"actions": args.max_actions, "requests": args.max_requests, "seconds": args.timeout, "budget_usd": args.budget_usd},
        "fixture_sha256": hashlib.sha256((ROOT / "fixtures" / "seed.json").read_bytes()).hexdigest(),
        "environment": "Linux X11 in Docker; 1200x900; no host mounts; desktop network internal",
    }
    recording = False
    try:
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not configured; no API request made")
        start_desktop(reset=True)
        guest_hash = compose("exec", "-T", "desktop", "sha256sum", "/opt/ledgerdesk/fixtures/seed.json").stdout.split()[0]
        if guest_hash != metadata["fixture_sha256"]:
            raise RuntimeError("Desktop fixture differs from local verifier fixture; rebuild with the desktop command")
        metadata["image_id"] = compose("images", "-q", "desktop").stdout.strip()
        recording = record_start()
        driver = DesktopDriver(run_dir)
        result = run_agent(driver, metadata["instruction"], run_dir, model=args.model,
                           max_requests=args.max_requests, max_actions=args.max_actions,
                           timeout_seconds=args.timeout, budget_usd=args.budget_usd)
        metadata.update(result)
        if result["status"] == "completed":
            try:
                csv_path = collect_export(run_dir, args.task)
                # A fresh container had no export before this attempt. Use a new host
                # fixture for the trusted oracle; neither is an agent tool.
                oracle = run_dir / "oracle.db"
                reset_database(oracle)
                verification = verify_csv(csv_path, oracle, args.task, as_of=args.as_of)
                oracle.unlink()
            except subprocess.SubprocessError:
                verification = {"passed": False, "errors": ["The GUI did not create the expected CSV."], "rows": [], "headers": [], "row_count": 0}
            save_json(run_dir / "verification.json", verification)
            log_event(run_dir, "verification", passed=verification["passed"], errors=verification["errors"])
            metadata["status"] = "passed" if verification["passed"] else "failed"
            if not verification["passed"]:
                metadata["error"] = "Independent CSV verification failed"
    except KeyboardInterrupt:
        metadata["status"], metadata["error"] = "blocked", "Interrupted by the operator"
    except Exception as error:
        metadata["status"] = "blocked"
        metadata["error"] = str(error) if isinstance(error, RuntimeError) else f"Setup or verification failed ({type(error).__name__})"
        log_event(run_dir, "error", message=metadata["error"])
    finally:
        metadata["recording_available"] = record_stop(run_dir) if recording else False
        metadata["elapsed_seconds"] = round(time.monotonic() - started, 3)
        metadata["finished_at"] = datetime.now(timezone.utc).isoformat()
        save_json(run_dir / "run.json", metadata)
        write_report(run_dir)
    print(f"{metadata['status'].upper()}: {run_dir / 'report.html'}", flush=True)
    if metadata.get("error"):
        print(metadata["error"], flush=True)
    return run_dir, metadata


def evaluate(args) -> int:
    results = []
    cost = 0.0
    budget = args.budget_usd
    for repetition in range(1, args.repeats + 1):
        for task in REPORTS:
            remaining = budget - cost
            if remaining < 0.25:
                break
            attempt = argparse.Namespace(**vars(args))
            attempt.task = task
            attempt.budget_usd = min(2.0, remaining)
            run_dir, metadata = run_task(attempt)
            results.append({"repetition": repetition, "task": task, "run_dir": str(run_dir.relative_to(ROOT)), **metadata})
            estimate = metadata.get("estimated_cost_usd")
            cost += estimate if estimate is not None else attempt.budget_usd
            # Missing credentials/access is not evidence about task accuracy.
            if metadata["status"] == "blocked":
                break
        else:
            continue
        break
    path = ROOT / "output" / "evaluation.json"
    save_json(path, {"planned_attempts": args.repeats * len(REPORTS), "completed_attempts": len(results), "estimated_cost_usd": cost, "runs": results})
    print(f"Evaluation: {path}")
    return 0 if len(results) == args.repeats * len(REPORTS) and all(r["status"] == "passed" for r in results) else 1


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="LedgerDesk native desktop computer-use demo")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("desktop", help="Build and open the isolated desktop")
    commands.add_parser("stop", help="Stop and remove this demo's containers")
    commands.add_parser("fixture", help="Open native LedgerDesk locally for manual use")
    verify = commands.add_parser("verify", help="Independently recheck a saved run")
    verify.add_argument("--run-dir", type=Path, required=True)
    for name in ("run", "evaluate"):
        sub = commands.add_parser(name)
        if name == "run":
            sub.add_argument("--task", choices=REPORTS, required=True)
        else:
            sub.add_argument("--repeats", type=int, default=3)
        sub.add_argument("--as-of", default="2026-10-15")
        sub.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-6.1-terra"))
        sub.add_argument("--budget-usd", type=float, default=20.0 if name == "evaluate" else 2.0)
        sub.add_argument("--max-actions", type=int, default=40)
        sub.add_argument("--max-requests", type=int, default=20)
        sub.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    if args.command in {"run", "evaluate"}:
        try:
            task_instruction("overdue-invoices", args.as_of)
        except ValueError as error:
            parser.error(str(error))
        for field in ("budget_usd", "max_actions", "max_requests", "timeout"):
            if not 0 < getattr(args, field) < float("inf"):
                parser.error(f"{field} must be positive and finite")
        if args.command == "evaluate" and not 1 <= args.repeats <= 10:
            parser.error("repeats must be between 1 and 10")
    try:
        with session_lock() if args.command in {"desktop", "stop", "run", "evaluate"} else nullcontext():
            return dispatch(args)
    except (RuntimeError, subprocess.SubprocessError) as error:
        print(str(error) if isinstance(error, RuntimeError) else f"Desktop command failed ({type(error).__name__}).", file=sys.stderr)
        return 1


def dispatch(args) -> int:
    if args.command == "desktop":
        start_desktop(build=True)
        print("Watch and interact: http://127.0.0.1:6080/vnc.html?autoconnect=true&resize=scale")
    elif args.command == "stop":
        compose("down", timeout=60)
    elif args.command == "fixture":
        from .desktop_app import main as fixture_main
        target = ROOT / "output"
        target.mkdir(exist_ok=True)
        reset_database(target / "ledgerdesk.db")
        fixture_main(target / "ledgerdesk.db", target / "exports")
    elif args.command == "verify":
        metadata = json.loads((args.run_dir / "run.json").read_text())
        current_hash = hashlib.sha256((ROOT / "fixtures" / "seed.json").read_bytes()).hexdigest()
        if current_hash != metadata.get("fixture_sha256"):
            raise RuntimeError("Saved run uses a different fixture; restore its source revision before reverifying")
        oracle = args.run_dir / "oracle.db"
        reset_database(oracle)
        try:
            result = verify_csv(args.run_dir / "export.csv", oracle, metadata["task_id"], as_of=metadata.get("as_of", "2026-10-15"))
        finally:
            oracle.unlink(missing_ok=True)
        save_json(args.run_dir / "verification.json", result)
        # Reverification does not retroactively turn a blocked run into a success.
        if not result["passed"]:
            metadata["status"] = "failed"
            save_json(args.run_dir / "run.json", metadata)
        write_report(args.run_dir)
        print(json.dumps(result, indent=2))
        return 0 if result["passed"] else 1
    elif args.command == "run":
        return 0 if run_task(args)[1]["status"] == "passed" else 1
    elif args.command == "evaluate":
        return evaluate(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
