"""Recheck a completed 100-run study and summarize costs without API or Docker calls."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import mean, median
import tempfile

from ledgerdesk.office_tasks import OFFICE_TASKS, verify_office
from ledgerdesk.reports import REPORTS
from ledgerdesk.seed_data import reset_database
from ledgerdesk.verify import verify_csv
from ledgerdesk.workflows import WORKFLOWS, initialize_workflow_data, verify_workflow


ROOT = Path(__file__).resolve().parents[1]
TASK_IDS = (*REPORTS, *WORKFLOWS, *OFFICE_TASKS)
SOURCE_PRESERVATION_NOTE = (
    "Office source preservation is checked against the saved input file and the "
    "controller's recorded before/after hashes. This is not a new observation of "
    "the original live desktop filesystem."
)


def _number(value) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def statistics(runs: list[dict]) -> dict:
    """Unknown or partial usage never becomes a zero-cost completed estimate."""
    statuses = Counter(run["status"] for run in runs)
    elapsed = [run["elapsed_seconds"] for run in runs if _number(run.get("elapsed_seconds"))]
    costs = [Decimal(str(run["estimated_cost_usd"])) for run in runs if _number(run.get("estimated_cost_usd"))]
    unknown = [run["id"] for run in runs if not _number(run.get("estimated_cost_usd"))
               or not isinstance(run.get("usage"), dict) or run["usage"].get("complete") is not True]
    cost_complete = bool(runs) and not unknown
    total = sum(costs, Decimal(0)) if cost_complete else None
    average = total / len(runs) if total is not None else None

    def numeric(value):
        return float(value) if value is not None else None

    def bounds(field):
        values = [run[field] for run in runs if type(run.get(field)) is int and run[field] >= 0]
        return {"range": [min(values), max(values)] if values else None, "values_available": len(values)}

    return {
        "attempts": len(runs), "passed": statuses["passed"], "failed": statuses["failed"], "blocked": statuses["blocked"],
        "mean_elapsed_seconds": mean(elapsed) if elapsed else None,
        "median_elapsed_seconds": median(elapsed) if elapsed else None,
        "elapsed_values_available": len(elapsed),
        "actions": bounds("action_count"), "requests": bounds("request_count"),
        "cost_complete": cost_complete, "cost_values_available": len(costs),
        "missing_or_incomplete_cost_run_ids": unknown,
        "estimated_cost_usd_known": numeric(sum(costs, Decimal(0))) if costs else None,
        "estimated_cost_usd": numeric(total), "mean_estimated_cost_usd_per_attempt": numeric(average),
        "estimated_cost_usd_per_verified_success": numeric(total / statuses["passed"]) if total is not None and statuses["passed"] else None,
        "projected_20_workday_cost_usd": numeric(average * 20) if average is not None else None,
    }


def _artifact(run_dir: Path, name: str) -> Path:
    candidate = (run_dir / name).resolve()
    if not candidate.is_relative_to(run_dir.resolve()):
        raise ValueError("Artifact points outside its run directory.")
    return candidate


def _recheck_run(run: dict, run_dir: Path) -> dict:
    task = run["task_id"]
    try:
        current_hash = hashlib.sha256((ROOT / "fixtures/seed.json").read_bytes()).hexdigest()
        if run.get("fixture_sha256") != current_hash:
            return {"passed": False, "errors": ["Fixture hash differs from the verifier's source fixture."]}
        if task in OFFICE_TASKS:
            suffix = ".odt" if task == "writer-find-replace" else ".csv"
            result = verify_office(task, _artifact(run_dir, "export" + suffix))
            source = _artifact(run_dir, OFFICE_TASKS[task]["input_name"])
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            recorded = json.loads(_artifact(run_dir, "verification.json").read_text())
            preserved = (
                recorded.get("source_unchanged") is True
                and source_hash == run.get("input_sha256")
                and source_hash == recorded.get("source_sha256_after")
            )
            result["source_preservation_consistent"] = preserved
            result["source_preservation_basis"] = SOURCE_PRESERVATION_NOTE
            if not preserved:
                result["passed"] = False
                result["errors"].append("Office source preservation records are missing or inconsistent.")
            return result
        with tempfile.TemporaryDirectory(prefix="ledgerdesk-recheck-") as directory:
            baseline = Path(directory) / "baseline.db"
            reset_database(baseline)
            if task in WORKFLOWS:
                initialize_workflow_data(baseline)
                return verify_workflow(_artifact(run_dir, "export.csv"), _artifact(run_dir, "final.db"), baseline, task)
            return verify_csv(_artifact(run_dir, "export.csv"), baseline, task, as_of=run.get("as_of", "2026-10-15"))
    except (OSError, ValueError, KeyError) as error:
        return {"passed": False, "errors": [f"Saved artifact recheck failed: {type(error).__name__}: {error}"]}


def _load_study(evaluation_path: Path) -> tuple[dict, list[tuple[dict, Path]], str]:
    raw = evaluation_path.read_bytes()
    evaluation = json.loads(raw)
    runs = evaluation.get("runs", [])
    if evaluation.get("planned_attempts") != 100 or evaluation.get("completed_attempts") != 100 or len(runs) != 100:
        raise ValueError("This summarizer requires all 100 planned attempts to be complete.")
    if evaluation.get("historical_attempts") != 24 or evaluation.get("new_attempts") != 76:
        raise ValueError("Expected 24 historical attempts and 76 new attempts.")
    if Counter(run.get("task_id") for run in runs) != Counter({task: 10 for task in TASK_IDS}):
        raise ValueError("Expected exactly ten attempts for each of the ten tasks.")
    if Counter(run.get("task_id") for run in runs[:24]) != Counter({task: 8 for task in REPORTS}):
        raise ValueError("The first 24 attempts must be the eight-per-report historical cohort.")
    identifiers = [run.get("id") for run in runs]
    if any(not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", identifier) for identifier in identifiers) or len(set(identifiers)) != 100:
        raise ValueError("The study must contain 100 distinct safe run identifiers.")
    project_root = evaluation_path.resolve().parent.parent
    runs_root = (project_root / "output/runs").resolve()
    loaded = []
    for entry in runs:
        run_dir = (project_root / entry["run_dir"]).resolve()
        if run_dir == runs_root or not run_dir.is_relative_to(runs_root) or run_dir.name != entry["id"]:
            raise ValueError("Run directories must match their IDs inside output/runs.")
        saved = json.loads(_artifact(run_dir, "run.json").read_text())
        if saved.get("status") not in {"passed", "failed", "blocked"} or not saved.get("finished_at"):
            raise ValueError(f"Run {entry['id']} has no terminal recorded outcome.")
        for field in ("id", "task_id", "status", "fixture_sha256", "model", "finished_at", "estimated_cost_usd", "usage", "elapsed_seconds", "action_count", "request_count", "source_revision", "source_tree_sha256", "image_id", "input_sha256"):
            if saved.get(field) != entry.get(field):
                raise ValueError(f"Run {entry['id']} differs from the evaluation at {field}.")
        loaded.append((saved, run_dir))
    return evaluation, loaded, hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    temporary.replace(path)


def summarize_evaluation(evaluation_path: Path, output_dir: Path | None = None) -> tuple[Path, Path]:
    """Write new summaries only; never change saved run files or verification records."""
    evaluation_path = Path(evaluation_path)
    evaluation, loaded, evaluation_hash = _load_study(evaluation_path)
    checked, scored, mismatches = [], [], []
    for index, (run, run_dir) in enumerate(loaded):
        result = _recheck_run(run, run_dir)
        artifact_passed = result.get("passed") is True
        consistent = run["status"] != "passed" or artifact_passed
        if not consistent:
            mismatches.append(run["id"])
        # An artifact alone cannot upgrade a failed or interrupted model run.
        effective_status = "failed" if run["status"] == "passed" and not artifact_passed else run["status"]
        cohort = "historical_24" if index < 24 else "new_76"
        scored.append({**run, "status": effective_status, "cohort": cohort})
        checked.append({
            "id": run["id"], "task_id": run["task_id"], "cohort": cohort,
            "recorded_status": run["status"], "effective_status": effective_status,
            "recorded_pass_reverified": consistent if run["status"] == "passed" else None,
            "artifact_verification": result,
        })
    common = {
        "schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_evaluation_sha256": evaluation_hash, "protocol": evaluation.get("protocol"),
        "historical_attempts": 24, "new_attempts": 76,
    }
    recheck = {**common, "all_recorded_passes_reverified": not mismatches,
               "recorded_pass_mismatches": mismatches, "source_preservation_note": SOURCE_PRESERVATION_NOTE, "runs": checked}
    costs = {
        **common,
        "cost_basis": "Recorded standard-rate model API estimates; no repricing, hosting or operating costs. Provider billing may differ.",
        "projection_basis": "Twenty workdays with one attempted task per day, using the observed mean per attempt; not a retry-until-success projection.",
        "success_cost_basis": "All attempt costs, including failed and blocked attempts, divided by independently reverified recorded successes.",
        "unknown_cost_policy": "Incomplete or unavailable costs make full totals, means, success costs and projections null; known subtotals are labelled separately.",
        "recorded_pass_mismatches": mismatches,
        "overall": statistics(scored),
        "tasks": {task: statistics([run for run in scored if run["task_id"] == task]) for task in TASK_IDS},
        "cohorts": {cohort: statistics([run for run in scored if run["cohort"] == cohort]) for cohort in ("historical_24", "new_76")},
        "new_source_revisions": {
            revision: statistics([run for run in scored if run.get("source_revision") == revision])
            for revision in sorted({run["source_revision"] for run in scored if run.get("source_revision")})
        },
    }
    output_dir = Path(output_dir) if output_dir is not None else evaluation_path.parent
    recheck_path = output_dir / "evaluation-100-recheck.json"
    cost_path = output_dir / "cost-analysis-100.json"
    _write_json(recheck_path, recheck)
    _write_json(cost_path, costs)
    return recheck_path, cost_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evaluation", nargs="?", type=Path, default=ROOT / "output/evaluation-100.json")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    recheck_path, cost_path = summarize_evaluation(args.evaluation, args.output_dir)
    print(f"Artifact recheck: {recheck_path}\nCost analysis: {cost_path}")
    recheck = json.loads(recheck_path.read_text())
    if not recheck["all_recorded_passes_reverified"]:
        print("ERROR: One or more recorded passes failed independent artifact recheck.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
