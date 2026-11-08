"""Run a frozen Office robustness study or the explicit nine-case GnuCash study."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "office-robustness-30-v1"
RANDOM_SEED = 20261108
TOTAL_BUDGET_USD = 20.0
LIMITS = {"budget_usd": 1.0, "max_requests": 30, "max_actions": 80, "timeout": 420}
OFFICE_TASKS = ("calc-sort-export", "writer-find-replace")
GNUCASH_TASKS = ("gnucash-expense", "gnucash-split", "gnucash-transfer")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def make_plan(manifest: dict, seed: int = RANDOM_SEED) -> list[dict]:
    """Validate and deterministically shuffle one of the two explicit study plans."""
    if manifest.get("protocol") == "gnucash-native-v1":
        fixtures, cases = manifest.get("fixtures", []), manifest.get("cases", [])
        expected = {(task, index) for task in GNUCASH_TASKS for index in range(3)}
        by_key = {(item["task_id"], item["fixture_index"]): item for item in fixtures}
        if len(fixtures) != 9 or len(cases) != 9 or set(by_key) != expected:
            raise ValueError("GnuCash manifest must contain three inputs for each of three tasks.")
        seen, plan = set(), []
        for case in cases:
            key = case["task_id"], case["fixture_index"]
            if key not in expected or key in seen or case.get("control") is not None or case.get("geometry") != "normal":
                raise ValueError("GnuCash cases must be nine unique normal-geometry positive cases.")
            fixture = by_key[key]
            if case["fixture_id"] != fixture["fixture_id"]:
                raise ValueError("GnuCash case references the wrong fixture.")
            for field in ("input_sha256", "instruction_sha256", "expected_sha256"):
                if not isinstance(fixture.get(field), str) or not re.fullmatch(r"[0-9a-f]{64}", fixture[field]):
                    raise ValueError("GnuCash fixtures require input, instruction and expected-output hashes.")
            if any(case.get(field) != fixture[field] for field in ("input_sha256", "instruction_sha256")):
                raise ValueError("GnuCash case hashes differ from the frozen fixture.")
            seen.add(key)
            plan.append({**case, "kind": "positive"})
        if len({case["case_id"] for case in plan}) != 9:
            raise ValueError("GnuCash case IDs must be unique.")
        random.Random(seed).shuffle(plan)
        return plan
    fixtures = manifest.get("fixtures", [])
    cases = manifest.get("cases", [])
    expected = {(task, split, index) for task in OFFICE_TASKS for split in ("development", "heldout") for index in range(3)}
    by_key = {(item["task_id"], item["split"], item["fixture_index"]): item for item in fixtures}
    if len(fixtures) != 12 or set(by_key) != expected or len(cases) != 24:
        raise ValueError("Fixture manifest must contain 12 inputs and 24 paired cases.")
    for fixture in fixtures:
        if any(not isinstance(fixture.get(field), str) or not re.fullmatch(r"[0-9a-f]{64}", fixture[field])
               for field in ("input_sha256", "instruction_sha256", "expected_sha256")):
            raise ValueError("Every fixture needs input, instruction and expected-output hashes.")
    if len({fixture["input_sha256"] for fixture in fixtures}) != 12:
        raise ValueError("The twelve input fixtures must be distinct.")
    seen = set()
    plan = []
    for case in cases:
        key = (case["task_id"], case["split"], case["fixture_index"])
        combination = (*key, case["geometry"])
        if key not in expected or case["geometry"] not in {"normal", "changed"} or combination in seen:
            raise ValueError("Fixture cases do not form the required paired design.")
        fixture = by_key[key]
        if case["fixture_id"] != fixture["fixture_id"] or any(case.get(field) != fixture.get(field) for field in ("input_sha256", "instruction_sha256")):
            raise ValueError("Paired cases must preserve their input and instruction hashes.")
        if case.get("control") is not None:
            raise ValueError("Positive cases cannot be controls.")
        seen.add(combination)
        plan.append({**case, "kind": "positive"})
    for control in ("foreign-focus", "missing-source", "duplicate-receipt"):
        for repeat in range(2):
            task = "payment-entry" if control == "duplicate-receipt" else OFFICE_TASKS[repeat]
            spec = {"case_id": f"control-{control}-{repeat:02d}", "task_id": task,
                    "kind": "negative_control", "control": control, "control_index": repeat,
                    "split": "development" if task in OFFICE_TASKS else None,
                    "fixture_index": 0 if task in OFFICE_TASKS else None, "geometry": "normal"}
            if task in OFFICE_TASKS:
                fixture = by_key[(task, "development", 0)]
                spec.update({field: fixture[field] for field in ("fixture_id", "input_sha256", "instruction_sha256")})
            plan.append(spec)
    if len({case["case_id"] for case in plan}) != 30:
        raise ValueError("Case IDs must be unique.")
    random.Random(seed).shuffle(plan)
    return plan


def _check_code_files(context: dict) -> None:
    files = context.get("code_files")
    if not isinstance(files, dict) or not files:
        raise ValueError("Freeze context requires a nonempty code_files hash map.")
    for name, expected_hash in files.items():
        path = (ROOT / name).resolve()
        relative = Path(name)
        if relative.is_absolute() or not path.is_relative_to(ROOT.resolve()) or any(part.startswith(".") or part == ".." for part in relative.parts):
            raise ValueError("Code files must be ordinary repository-relative paths.")
        if path.suffix not in {".py", ".json", ".toml", ".yaml", ".yml", ".sh"} and path.name != "Dockerfile":
            raise ValueError("Only source/configuration files may be included in code_files.")
        if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash) or _sha(path.read_bytes()) != expected_hash:
            raise ValueError(f"Frozen code hash does not match: {name}")


def _protocol_data(context: dict, seed: int) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", context.get("source_revision", "")):
        raise ValueError("Freeze context requires a full source commit ID.")
    if not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", context.get("image_id", "")):
        raise ValueError("Freeze context requires a full container image ID.")
    if not isinstance(context.get("environment"), dict) or not context["environment"]:
        raise ValueError("Freeze context requires recorded environment details.")
    campaign = context.get("campaign", "office")
    if campaign not in {"office", "gnucash"}:
        raise ValueError("Campaign must be office or gnucash.")
    is_gnucash = campaign == "gnucash"
    if is_gnucash != (context["fixtures"].get("protocol") == "gnucash-native-v1"):
        raise ValueError("Campaign and fixture manifest do not agree.")
    _check_code_files(context)
    plan = make_plan(context["fixtures"], seed)
    return {
        "schema_version": 1, "protocol": "gnucash-native-9-v1" if is_gnucash else PROTOCOL,
        "campaign": campaign, "random_seed": seed,
        "planned_positive_cases": 9 if is_gnucash else 24, "planned_negative_controls": 0 if is_gnucash else 6,
        "design": ("Three native GnuCash tasks with three distinct fixture indices each; normal geometry only."
                   if is_gnucash else "Two applications, two input splits, three distinct files per split, paired across two geometries; no same-state stochastic replicas."),
        "source_revision": context["source_revision"], "code_files": context["code_files"],
        "code_sha256": _sha(_canonical(context["code_files"])),
        "image_id": context["image_id"], "environment": context["environment"],
        "environment_sha256": _sha(_canonical(context["environment"])),
        "fixtures": context["fixtures"], "fixtures_sha256": _sha(_canonical(context["fixtures"])),
        "limits": dict(LIMITS), "total_budget_usd": 10.0 if is_gnucash else TOTAL_BUDGET_USD,
        "plan": plan,
    }


def _write_json(path: Path, value) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


@contextmanager
def _lock(study_dir: Path):
    study_dir.mkdir(parents=True, exist_ok=True)
    with (study_dir / ".lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another process owns this robustness study.") from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _freeze(study_dir: Path, context: dict, seed: int) -> tuple[dict, str]:
    expected = _protocol_data(context, seed)
    path = study_dir / "protocol.json"
    if path.exists():
        protocol = json.loads(path.read_text())
        if {key: value for key, value in protocol.items() if key != "frozen_at"} != expected:
            raise ValueError("Study context or plan changed after freezing; use a separate study directory.")
    else:
        protocol = {**expected, "frozen_at": _now()}
        _write_json(path, protocol)
    return protocol, _sha(path.read_bytes())


def _append(path: Path, event: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"timestamp": _now(), **event}, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _read_events(path: Path, protocol: dict, protocol_hash: str) -> tuple[list[dict], dict | None]:
    finished, pending = [], None
    if not path.exists():
        return finished, pending
    for line in path.read_text().splitlines():
        event = json.loads(line)
        index = len(finished)
        if index >= len(protocol["plan"]) or event.get("protocol_sha256") != protocol_hash or event.get("case_id") != protocol["plan"][index]["case_id"]:
            raise ValueError("Study event order or frozen protocol hash is inconsistent.")
        if event.get("event") == "started" and pending is None:
            pending = event
        elif event.get("event") == "finished" and pending is not None:
            finished.append(event)
            pending = None
        else:
            raise ValueError("Study ledger has a duplicate or out-of-order event.")
    return finished, pending


def _known_cost(metadata: dict):
    value = metadata.get("estimated_cost_usd")
    usage = metadata.get("usage")
    if type(value) in (int, float) and math.isfinite(value) and value >= 0 and isinstance(usage, dict) and usage.get("complete") is True:
        return Decimal(str(value))
    return None


def _grade(case: dict, run_dir: Path, metadata: dict) -> dict:
    if case["kind"] == "negative_control":
        check = metadata.get("control_verification")
        if not isinstance(check, dict) or type(check.get("passed")) is not bool:
            return {"passed": None, "errors": ["No deterministic control verification was returned."]}
        return {"passed": check["passed"], "errors": check.get("errors", [])}
    try:
        path = run_dir / "verification.json"
        if not path.resolve().is_relative_to(run_dir.resolve()):
            raise ValueError("Verification record is outside the run directory.")
        check = json.loads(path.read_text())
    except (OSError, ValueError):
        check = {"passed": False}
    passed = metadata.get("status") == "passed" and check.get("passed") is True
    return {"passed": passed, "errors": [] if passed else ["Task did not finish with an independently verified output."]}


def _status(protocol: dict, finished: list[dict], stop_reason: str | None) -> dict:
    known = [_known_cost(event["metadata"]) for event in finished]
    complete = all(cost is not None for cost in known)
    subtotal = sum((cost for cost in known if cost is not None), Decimal(0))
    groups = {}
    for kind in ("positive", "negative_control"):
        cases = [event for event in finished if event["kind"] == kind]
        grades = Counter("passed" if event["grade"]["passed"] is True else "failed" if event["grade"]["passed"] is False else "unverified" for event in cases)
        groups[kind] = {"completed": len(cases), **{key: grades[key] for key in ("passed", "failed", "unverified")}}
    return {
        "protocol": protocol["protocol"], "planned": len(protocol["plan"]), "completed": len(finished),
        "remaining": len(protocol["plan"]) - len(finished), "grades": groups,
        "estimated_cost_usd_known": float(subtotal),
        "estimated_cost_usd": float(subtotal) if complete else None, "cost_complete": complete,
        "budget_reserved_usd": float(subtotal + sum(Decimal(str(LIMITS["budget_usd"])) for cost in known if cost is None)),
        "total_budget_usd": protocol["total_budget_usd"], "stop_reason": stop_reason,
    }


def run_study(context: dict, study_dir: Path, runner=None, *, limit: int = 30,
              seed: int = RANDOM_SEED, plan_only: bool = False) -> dict:
    """Only explicit calls execute cases. A crash consumes an uncertain slot, never retries it."""
    if type(limit) is not int or not 0 <= limit <= 30:
        raise ValueError("limit must be an integer from 0 to 30.")
    study_dir = Path(study_dir)
    with _lock(study_dir):
        protocol, protocol_hash = _freeze(study_dir, context, seed)
        ledger = study_dir / "events.jsonl"
        finished, pending = _read_events(ledger, protocol, protocol_hash)
        stop_reason = "Plan frozen; no cases executed." if plan_only else None
        if not plan_only and pending is not None:
            case = protocol["plan"][len(finished)]
            event = {"event": "finished", "protocol_sha256": protocol_hash, "case_id": case["case_id"],
                     "kind": case["kind"], "completion": "interrupted_unknown", "run_dir": None,
                     "metadata": {"status": "blocked", "estimated_cost_usd": None, "usage": {"complete": False}},
                     "grade": {"passed": None, "errors": ["A previous process stopped after starting this slot; it will not be retried."]}}
            _append(ledger, event)
            finished.append(event)
            stop_reason = "Interrupted slot retained with unknown outcome/cost. Inspect before resuming remaining slots."
        if not plan_only and stop_reason is None:
            if runner is None:
                from ledgerdesk.study_runner import run_study_case
                runner = run_study_case
            while len(finished) < min(limit, len(protocol["plan"])):
                _check_code_files(context)
                state = _status(protocol, finished, None)
                if Decimal(str(state["budget_reserved_usd"])) + Decimal(str(LIMITS["budget_usd"])) > Decimal(str(protocol["total_budget_usd"])):
                    stop_reason = "Remaining study budget cannot cover the next attempt's reserve."
                    break
                case = protocol["plan"][len(finished)]
                common = {"protocol_sha256": protocol_hash, "case_id": case["case_id"], "kind": case["kind"]}
                _append(ledger, {"event": "started", **common})
                run_reference, stop_after = None, False
                try:
                    supplied = {**case, "expected_image_id": protocol["image_id"], "expected_source_revision": protocol["source_revision"]}
                    run_dir, metadata = runner(supplied, dict(protocol["limits"]))
                    run_dir = Path(run_dir).resolve()
                    if not run_dir.is_relative_to((ROOT / "output/runs").resolve()):
                        raise ValueError("Runner returned an unexpected evidence location.")
                    run_reference = str(run_dir.relative_to(ROOT.resolve()))
                    grade = _grade(case, run_dir, metadata)
                    image_matches = str(metadata.get("image_id", "")).removeprefix("sha256:") == protocol["image_id"].removeprefix("sha256:")
                    source_matches = metadata.get("source_revision") == protocol["source_revision"]
                    inputs_match = metadata.get("input_sha256") == case.get("input_sha256")
                    drift = (not image_matches or not source_matches or not inputs_match) if case["kind"] == "positive" else (
                        metadata.get("image_id") is not None and not image_matches
                        or metadata.get("source_revision") is not None and not source_matches
                    )
                    if drift:
                        grade = {"passed": False, "errors": ["Runner environment differs from the frozen study."]}
                        stop_after = True
                    if case["kind"] == "positive" and metadata.get("request_count") == 0:
                        stop_after = True
                    if metadata.get("api_error", {}).get("status_code") in {401, 403, 429}:
                        stop_after = True
                    completion = "returned"
                except (Exception, KeyboardInterrupt) as error:
                    metadata = {"status": "blocked", "estimated_cost_usd": None, "usage": {"complete": False},
                                "error": f"Runner stopped with {type(error).__name__}; outcome and cost are unknown."}
                    grade = {"passed": None, "errors": [metadata["error"]]}
                    completion, stop_after = "runner_interrupted", True
                event = {"event": "finished", **common, "completion": completion,
                         "run_dir": run_reference, "metadata": metadata, "grade": grade}
                _append(ledger, event)
                finished.append(event)
                if stop_after:
                    stop_reason = "Attempt retained; inspect the interruption or environment/provider error before resuming."
                    break
        status = _status(protocol, finished, stop_reason)
        _write_json(study_dir / "status.json", status)
        return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True, type=Path)
    parser.add_argument("--study-dir", type=Path, default=ROOT / "output/robustness-study")
    parser.add_argument("--limit", type=int, default=30, help="Cumulative attempt-slot limit, never a retry count")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    status = run_study(json.loads(args.context.read_text()), args.study_dir,
                       limit=args.limit, plan_only=args.plan_only)
    print(json.dumps(status, indent=2))
    grades_pass = all(group["failed"] == 0 and group["unverified"] == 0 for group in status["grades"].values())
    return 0 if args.plan_only or status["completed"] == status["planned"] and not status["stop_reason"] and grades_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
