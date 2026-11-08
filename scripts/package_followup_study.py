"""Recheck and package a completed Office or GnuCash follow-up study offline."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
from html import escape
import json
import math
from pathlib import Path
import re
import shutil
import sqlite3
from statistics import mean, median
import tempfile

from ledgerdesk.gnucash_tasks import GNUTASKS, verify_gnucash
from ledgerdesk.office_tasks import OFFICE_TASKS
from ledgerdesk.robustness_fixtures import verify_variant
from ledgerdesk.workflows import _snapshot
from scripts.run_robustness_study import _canonical, _read_events, make_plan


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "run.json", "events.jsonl", "report.html", "verification.json", "control-verification.json",
    "setup-blocked.json", "application-audit.jsonl", "foreign-events.jsonl", "foreign-value.txt",
    "foreign-control.png", "baseline.db", "final.db", "export.csv", "export.odt", "export.gnucash",
    "calc-source.ods", "writer-source.odt", "gnucash-source.gnucash", "recording.mp4",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file(directory: Path, name: str, *, required: bool = False) -> Path:
    path = directory / name
    if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
        raise ValueError(f"Evidence file escapes its directory: {name}")
    if path.exists() and not path.is_file():
        raise ValueError(f"Evidence is not a regular file: {name}")
    if required and not path.is_file():
        raise ValueError(f"Required evidence file is missing: {name}")
    return path


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_directory(reference: str | None) -> Path | None:
    if reference is None:
        return None
    if not isinstance(reference, str) or Path(reference).is_absolute() or ".." in Path(reference).parts:
        raise ValueError("Run references must be repository-relative paths inside output/runs.")
    path = ROOT / reference
    root = (ROOT / "output" / "runs").resolve()
    if path.is_symlink() or path.resolve() == root or not path.resolve().is_relative_to(root) or not path.is_dir():
        raise ValueError("Run reference is outside output/runs or is unavailable.")
    return path.resolve()


def _read_study(study_dir: Path) -> tuple[dict, dict, list[dict]]:
    protocol_path = _file(study_dir, "protocol.json", required=True)
    events_path = _file(study_dir, "events.jsonl", required=True)
    status = _json(_file(study_dir, "status.json", required=True))
    protocol = _json(protocol_path)
    campaign = protocol.get("campaign")
    expected_protocol = {"office": "office-robustness-30-v1", "gnucash": "gnucash-native-9-v1"}.get(campaign)
    if expected_protocol is None or protocol.get("protocol") != expected_protocol:
        raise ValueError("Only the frozen Office-30 and GnuCash-9 studies are supported.")
    if (not re.fullmatch(r"[0-9a-f]{40}", protocol.get("source_revision", ""))
            or not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", protocol.get("image_id", ""))):
        raise ValueError("Frozen source and image identifiers are invalid.")
    if protocol.get("plan") != make_plan(protocol["fixtures"], protocol["random_seed"]):
        raise ValueError("Recorded plan differs from the frozen fixture design.")
    for value, fingerprint in (("fixtures", "fixtures_sha256"), ("environment", "environment_sha256"), ("code_files", "code_sha256")):
        if hashlib.sha256(_canonical(protocol[value])).hexdigest() != protocol.get(fingerprint):
            raise ValueError(f"Frozen {value} fingerprint differs.")
    plan = protocol["plan"]
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,159}", case.get("case_id", "")) for case in plan):
        raise ValueError("Unsafe case identifier.")
    finished, pending = _read_events(events_path, protocol, _sha(protocol_path))
    if (pending is not None or len(finished) != len(plan)
            or status.get("planned") != len(plan) or status.get("completed") != len(plan)
            or status.get("remaining") != 0 or status.get("protocol") != protocol["protocol"]):
        raise ValueError("Package only a completed study with every planned slot finished.")
    positives = sum(case["kind"] == "positive" for case in plan)
    if protocol.get("planned_positive_cases") != positives or protocol.get("planned_negative_controls") != len(plan) - positives:
        raise ValueError("Protocol denominators disagree with its plan.")
    for kind in ("positive", "negative_control"):
        events = [event for event in finished if event["kind"] == kind]
        recorded = status.get("grades", {}).get(kind, {})
        expected = {"completed": len(events),
                    "passed": sum(e["grade"]["passed"] is True for e in events),
                    "failed": sum(e["grade"]["passed"] is False for e in events),
                    "unverified": sum(e["grade"]["passed"] is None for e in events)}
        if recorded != expected:
            raise ValueError("Status grades disagree with the append-only event ledger.")
    return protocol, status, finished


def _evidence_files(directory: Path) -> list[Path]:
    paths = [_file(directory, name) for name in FILES]
    screenshots = directory / "screenshots"
    if screenshots.is_symlink():
        raise ValueError("Screenshot directory must not be a symlink.")
    if screenshots.exists():
        if not screenshots.is_dir():
            raise ValueError("Screenshot path must be a directory.")
        paths += [_file(directory, f"screenshots/{path.name}") for path in sorted(screenshots.glob("*.png"))]
    return [path for path in paths if path.is_file()]


def _read_optional(directory: Path, name: str) -> dict:
    path = _file(directory, name)
    return _json(path) if path.is_file() else {}


def _provenance_errors(case: dict, metadata: dict, protocol: dict) -> list[str]:
    errors = []
    if metadata.get("source_revision") != protocol["source_revision"]:
        errors.append("Recorded source revision differs from the frozen protocol.")
    if str(metadata.get("image_id", "")).removeprefix("sha256:") != protocol["image_id"].removeprefix("sha256:"):
        errors.append("Recorded container image differs from the frozen protocol.")
    if metadata.get("operator_interventions") != 0:
        errors.append("Zero operator interventions were not recorded.")
    if metadata.get("case_id") != case["case_id"] or metadata.get("task_id") != case["task_id"]:
        errors.append("Run identity differs from the planned case.")
    if case.get("instruction_sha256"):
        instruction = metadata.get("instruction")
        if not isinstance(instruction, str) or hashlib.sha256(instruction.encode()).hexdigest() != case["instruction_sha256"]:
            errors.append("Recorded instruction differs from the frozen task.")
    for key in ("task_id", "split", "fixture_index", "geometry", "control"):
        if metadata.get("spec", {}).get(key) != case.get(key):
            errors.append(f"Recorded case field differs: {key}.")
    if case["kind"] == "positive":
        bounds = metadata.get("window_bounds")
        ranges = ((0, 2), (0, 25), (1195, 1200), (875, 900)) if case["geometry"] == "normal" else ((115, 125), (75, 105), (915, 925), (655, 665))
        if (not isinstance(bounds, (list, tuple)) or len(bounds) != 4
                or any(type(value) is not int or not low <= value <= high for value, (low, high) in zip(bounds, ranges))):
            errors.append("Recorded window bounds do not match the frozen geometry condition.")
    return errors


def _public_errors(value, directory: Path | None, case_id: str, in_error: bool = False):
    """Redact host paths in derived error text; copied source files stay intact."""
    if isinstance(value, dict):
        return {key: _public_errors(item, directory, case_id, in_error or isinstance(key, str) and "error" in key.lower()) for key, item in value.items()}
    if isinstance(value, list):
        return [_public_errors(item, directory, case_id, in_error) for item in value]
    if isinstance(value, str) and in_error:
        if directory is not None:
            value = value.replace(str(directory), f"runs/{case_id}")
        value = value.replace(str(ROOT.resolve()), "[workspace]")
        value = re.sub(r"(?<![A-Za-z0-9:/])/(?!/)[^\s'\"<>]+", "[local path]", value)
        value = re.sub(r"[A-Za-z]:[\\/][^\s'\"<>]+", "[local path]", value)
    return value


def _positive(case: dict, metadata: dict, directory: Path, protocol: dict, recorded_grade) -> dict:
    task = case["task_id"]
    is_gnucash = task in GNUTASKS
    source_name = (GNUTASKS if is_gnucash else OFFICE_TASKS)[task]["input_name"]
    output_name = "export.gnucash" if is_gnucash else ("export.odt" if task == "writer-find-replace" else "export.csv")
    source = _file(directory, source_name)
    output = _file(directory, output_name)
    result = verify_gnucash(task, output, case["fixture_index"]) if is_gnucash else verify_variant(output, task, case["split"], case["fixture_index"])
    recorded = _read_optional(directory, "verification.json")
    source_hash = _sha(source) if source.is_file() else None
    expected_hash = case["input_sha256"]
    source_ok = (source_hash == expected_hash and metadata.get("input_sha256") == expected_hash
                 and recorded.get("source_sha256_after") == expected_hash and recorded.get("source_unchanged") is True)
    errors = _provenance_errors(case, metadata, protocol) + list(result["errors"])
    if not source_ok:
        errors.append("Saved input or recorded post-run source hash does not match the frozen input.")
    execution_ok = (metadata.get("status") == "passed" and metadata.get("agent_status") == "completed"
                    and recorded.get("passed") is True and recorded_grade is True)
    if not execution_ok:
        errors.append("Original execution was not a verified pass; rechecking cannot upgrade it.")
    return {"passed": not errors, "artifact_passed": result["passed"], "source_check_passed": source_ok,
            "saved_input_sha256": source_hash, "recorded_source_sha256_after": recorded.get("source_sha256_after"),
            "source_check_scope": "Saved initial input plus the controller's recorded post-run hash; no new live observation.",
            "errors": errors, "artifact_verification": result}


def _control(case: dict, metadata: dict, directory: Path, protocol: dict, recorded_grade) -> dict:
    proof = _read_optional(directory, "control-verification.json")
    errors = _provenance_errors(case, metadata, protocol)
    if proof != metadata.get("control_verification"):
        errors.append("Saved control proof differs from run metadata.")
    checks = {}
    control = case["control"]
    if control == "duplicate-receipt":
        try:
            baseline = _snapshot(_file(directory, "baseline.db", required=True))
            final = _snapshot(_file(directory, "final.db", required=True))
            audit = [json.loads(line) for line in _file(directory, "application-audit.jsonl", required=True).read_text().splitlines() if line.strip()]
            checks = {
                "duplicate_present_in_baseline": ("RCPT-1001", "INV-260916", 12525) in baseline[1].get("receipts", []),
                "state_unchanged": baseline == final,
                "duplicate_rejected": any(e.get("operation") == "payment-entry" and e.get("status") == "rejected"
                    and e.get("fields", {}).get("reference", "").strip() == "RCPT-1001" and "UNIQUE" in e.get("reason", "") for e in audit),
                "model_attempted": proof.get("model_attempted") is True and metadata.get("request_count", 0) > 0,
            }
        except (OSError, ValueError, KeyError, sqlite3.Error) as error:
            errors.append(f"Duplicate-control evidence cannot be rechecked: {error}")
        scope = "Canonical database snapshots and the recorded application rejection audit."
    elif control == "foreign-focus":
        events = [json.loads(line) for line in _file(directory, "events.jsonl", required=True).read_text().splitlines() if line.strip()]
        foreign = _file(directory, "foreign-events.jsonl")
        value = _file(directory, "foreign-value.txt")
        checks = {
            "no_foreign_events": foreign.is_file() and not foreign.read_text().strip(),
            "foreign_value_unchanged": value.is_file() and value.read_text() == "UNCHANGED",
            "focus_refusal_recorded": isinstance(proof.get("refusal"), str) and "focus" in proof["refusal"].lower(),
            "no_executed_inputs": not any(e.get("type") == "action_result" for e in events) and proof.get("executed_inputs") == 0,
            "model_not_attempted": proof.get("model_attempted") is False and metadata.get("request_count") == 0,
        }
        scope = "Recorded refusal, foreign-window event log and unchanged value; no new live action."
    else:
        marker = _read_optional(directory, "setup-blocked.json")
        expected_source = "/tmp/ledgerdesk/inputs/" + OFFICE_TASKS[case["task_id"]]["input_name"]
        checks = {
            "expected_missing_source_marker": marker.get("reason") == "missing_source" and marker.get("source") == expected_source and marker.get("exists") is False,
            "model_not_attempted": proof.get("model_attempted") is False and metadata.get("request_count") == 0,
        }
        scope = "Consistency of the recorded missing-source preflight marker; historical source absence is not newly observed."
    if not checks or not all(checks.values()):
        errors.append("The retained evidence does not establish the expected control behavior.")
    if proof.get("passed") is not True or recorded_grade is not True or metadata.get("status") != "blocked":
        errors.append("The original control was not graded as the expected block.")
    return {"passed": not errors, "checks": checks, "scope": scope, "errors": errors}


def _numeric(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _metrics(rows: list[dict], *, positive: bool = False) -> dict:
    def measurement(name: str, usage: bool = False):
        values = [(row["metadata"].get("usage", {}) if usage else row["metadata"]).get(name) for row in rows
                  if not usage or row["metadata"].get("usage", {}).get("complete") is True]
        values = [value for value in values if _numeric(value)]
        complete = len(values) == len(rows)
        return {"available": len(values), "complete": complete,
                "known_total": sum(values) if values else None, "total": sum(values) if complete else None,
                "mean": mean(values) if values else None, "median": median(values) if values else None,
                "min": min(values) if values else None, "max": max(values) if values else None}
    costs = [Decimal(str(row["metadata"]["estimated_cost_usd"])) for row in rows
             if _numeric(row["metadata"].get("estimated_cost_usd")) and row["metadata"].get("usage", {}).get("complete") is True]
    total_cost = sum(costs, Decimal(0))
    known = float(total_cost)
    complete = len(costs) == len(rows)
    passed = sum(row["recheck"]["passed"] is True for row in rows)
    unverified = sum(row["recheck"]["passed"] is None for row in rows)
    return {"attempts": len(rows), "passed": passed,
            "failed": sum(row["recheck"]["passed"] is False for row in rows),
            "unverified": unverified,
            "cost_values_available": len(costs), "estimated_cost_usd_known": known,
            "estimated_cost_usd": known if complete else None, "cost_complete": complete,
            "cost_per_verified_success": float(total_cost / passed) if positive and complete and not unverified and passed else None,
            **{name: measurement(name) for name in ("elapsed_seconds", "setup_elapsed_seconds", "agent_elapsed_seconds", "verification_elapsed_seconds", "action_count", "executed_actions", "request_count", "operator_interventions")},
            **{name: measurement(name, True) for name in ("input_tokens", "output_tokens", "total_tokens")}}


def _application(task: str) -> str:
    return "GnuCash" if task in GNUTASKS else ("LedgerDesk" if task == "payment-entry" else "LibreOffice " + OFFICE_TASKS[task]["application"].title())


def _groups(rows: list[dict], field: str, *, positive: bool = False) -> dict:
    grouped = defaultdict(list)
    for row in rows:
        value = row["application"] if field == "application" else row["case"].get(field)
        grouped[value if value is not None else "not-applicable"].append(row)
    return {key: _metrics(value, positive=positive) for key, value in sorted(grouped.items())}


def _pairs(rows: list[dict]) -> list[dict]:
    def difference(normal, changed, name, *, cost=False):
        values = [row["metadata"].get(name) for row in (normal, changed)]
        if not all(_numeric(value) for value in values):
            return None
        if cost:
            if not all(row["metadata"].get("usage", {}).get("complete") is True for row in (normal, changed)):
                return None
            return float(Decimal(str(values[1])) - Decimal(str(values[0])))
        return values[1] - values[0]

    groups = defaultdict(dict)
    for row in rows:
        if row["case"]["task_id"] in OFFICE_TASKS:
            groups[row["case"]["fixture_id"]][row["case"]["geometry"]] = row
    paired = []
    for fixture, pair in sorted(groups.items()):
        normal, changed = pair["normal"], pair["changed"]
        a, b = normal["recheck"]["passed"], changed["recheck"]["passed"]
        outcome = "unverified" if a is None or b is None else ("both_passed" if a and b else "normal_only" if a else "changed_only" if b else "neither_passed")
        original_hash = normal["recheck"].get("saved_input_sha256")
        paired.append({"fixture_id": fixture, "task_id": normal["case"]["task_id"], "split": normal["case"]["split"],
                       "normal_case_id": normal["case"]["case_id"], "changed_case_id": changed["case"]["case_id"],
                       "normal_passed": a, "changed_passed": b, "outcome": outcome,
                       "input_hashes_match": original_hash is not None and original_hash == changed["recheck"].get("saved_input_sha256") == normal["case"]["input_sha256"],
                       "changed_minus_normal_seconds": difference(normal, changed, "elapsed_seconds"),
                       "changed_minus_normal_executed_actions": difference(normal, changed, "executed_actions"),
                       "changed_minus_normal_request_count": difference(normal, changed, "request_count"),
                       "changed_minus_normal_cost_usd": difference(normal, changed, "estimated_cost_usd", cost=True)})
    return paired


def _html(summary: dict) -> str:
    def text(value):
        return escape("Unavailable" if value is None else str(value), quote=True)
    def display(value):
        return f"{value:.4f}" if type(value) in (int, float) and math.isfinite(value) else "Unavailable"
    title = "Office robustness follow-up" if summary["campaign"] == "office" else "GnuCash native-app study"
    body = []
    for row in summary["cases"]:
        case, metadata, check = row["case"], row["metadata"], row["recheck"]
        path = row["evidence_path"]
        link = f'<a href="{path}/report.html">{text(case["case_id"])}</a>' if row["has_report"] else text(case["case_id"])
        if row["has_recording"]:
            link += f' <a href="{path}/recording.mp4">Recording</a>'
        outcome = "passed" if check["passed"] is True else "failed" if check["passed"] is False else "unverified"
        cost = metadata.get("estimated_cost_usd") if metadata.get("usage", {}).get("complete") is True else None
        body.append(f'<tr><td>{link}</td><td>{text(case["kind"])}</td><td>{text(row["application"])}</td><td>{text(case.get("split"))}</td><td>{text(case["geometry"])}</td><td>{text(metadata.get("status"))}</td><td>{outcome}</td><td>{text(metadata.get("action_count"))}</td><td>{text(metadata.get("request_count"))}</td><td>{display(metadata.get("elapsed_seconds"))}</td><td>{display(cost)}</td></tr>')
    pairs = ''.join(f'<tr><td>{text(pair["fixture_id"])}</td><td>{text(pair["normal_passed"])}</td><td>{text(pair["changed_passed"])}</td><td>{text(pair["input_hashes_match"])}</td><td>{display(pair["changed_minus_normal_seconds"])}</td></tr>' for pair in summary["pairs"])
    positive, controls = summary["positive"], summary["negative_controls"]
    paired_html = f'<section><h2>Matched geometry cases</h2><p>The same input and instruction were used in each pair. These are descriptive comparisons, not a population reliability estimate.</p><div class="scroll"><table><thead><tr><th>Fixture</th><th>Normal pass</th><th>Changed pass</th><th>Input proof matches</th><th>Changed − normal seconds</th></tr></thead><tbody>{pairs}</tbody></table></div></section>' if pairs else ''
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; media-src 'self'; img-src 'self'; base-uri 'none'"><title>{title}</title><style>body{{margin:0;background:#edf2f5;color:#193346;font:15px/1.6 system-ui,sans-serif}}header{{background:#153245;color:white;padding:35px max(24px,calc((100vw - 1200px)/2))}}main{{max-width:1200px;margin:auto;padding:24px}}section{{background:white;border:1px solid #d3dfe6;border-radius:8px;padding:22px;margin-bottom:24px}}h1{{line-height:1.2}}a{{color:#087275}}.scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:12px}}th,td{{text-align:left;padding:10px;border-bottom:1px solid #dce4e9;vertical-align:top}}th{{white-space:nowrap}}td:first-child{{min-width:200px}}code{{overflow-wrap:anywhere}}.note{{color:#4c6677;font-size:13px}}</style></head><body><header><h1>{title}</h1><p>Protocol {text(summary['protocol'])} · {summary['completed']} of {summary['planned']} planned slots finished</p></header><main><section><h2>Positive tasks and controls are separate</h2><p><strong>{positive['passed']} / {positive['attempts']}</strong> positive tasks remain verified after recheck; {positive['failed']} failed and {positive['unverified']} unverified.</p><p><strong>{controls['passed']} / {controls['attempts']}</strong> negative controls show their expected behavior; {controls['failed']} failed and {controls['unverified']} unverified.</p><p>Known model cost across all slots: USD {display(summary['all_cases']['estimated_cost_usd_known'])}. Complete total: {display(summary['all_cases']['estimated_cost_usd'])}.</p><p class="note">Unknown usage is not zero. Costs include failed attempts with known usage and exclude hosting. An offline artifact pass cannot upgrade a failed original execution. The missing-source control is a check of the recorded preflight evidence, not a new live observation.</p><p><a href="summary.json">Summary and grouped metrics</a> · <a href="recheck.json">Detailed independent rechecks</a> · <a href="protocol.json">Frozen protocol</a> · <a href="events.jsonl">Study ledger</a> · <a href="status.json">Recorded status</a> · <a href="manifest.json">Artifact hashes</a></p></section><section><h2>Every planned case</h2><div class="scroll"><table><thead><tr><th>Case / evidence</th><th>Kind</th><th>Application</th><th>Split</th><th>Geometry</th><th>Original execution</th><th>Recheck grade</th><th>Inputs</th><th>Requests</th><th>Seconds</th><th>USD</th></tr></thead><tbody>{''.join(body)}</tbody></table></div></section>{paired_html}<section><h2>Scope</h2><p>These results apply to the frozen tasks, inputs, recorded application versions and desktop conditions. They do not establish general desktop reliability. Source preservation uses the saved initial input and the controller's recorded post-run hash. Full metrics are separated by application, split, geometry and control type in summary.json.</p><p class="note">Packaged {text(summary['packaged_at'])} without making model calls or changing the original evidence.</p></section></main></body></html>'''


def package_followup_study(study_dir: Path, destination: Path) -> Path:
    study_dir, destination = Path(study_dir), Path(destination)
    if study_dir.is_symlink() or not study_dir.is_dir():
        raise ValueError("Study directory must be an existing non-symlink directory.")
    study_dir = study_dir.resolve()
    if (destination.is_symlink() or destination.resolve().is_relative_to(study_dir)
            or destination.resolve().is_relative_to((ROOT / "output" / "runs").resolve())
            or destination.exists() and (not destination.is_dir() or any(destination.iterdir()))):
        raise ValueError("Choose an empty destination outside the study and run directories.")
    protocol, status, events = _read_study(study_dir)
    cases = []
    files_by_case = {}
    for case, event in zip(protocol["plan"], events):
        directory = _run_directory(event.get("run_dir"))
        metadata = event["metadata"]
        paths = []
        if directory is None:
            check = {"passed": None, "errors": ["No run directory survived this finished slot; its outcome remains unverified."]}
        else:
            paths = _evidence_files(directory)
            saved = _json(_file(directory, "run.json", required=True))
            if saved != metadata:
                if event.get("completion") == "runner_interrupted" and event["grade"]["passed"] is None:
                    check = {"passed": None, "errors": ["The runner interrupted after saving partial evidence; its ledger outcome remains unknown."]}
                else:
                    raise ValueError("Saved run metadata differs from the study ledger.")
            else:
                try:
                    check = (_positive if case["kind"] == "positive" else _control)(case, metadata, directory, protocol, event["grade"]["passed"])
                except (OSError, ValueError, KeyError, sqlite3.Error) as error:
                    check = {"passed": False, "errors": [f"Retained evidence could not be rechecked: {error}"]}
        evidence = f"runs/{case['case_id']}" if directory is not None else None
        cases.append({"case": case, "metadata": _public_errors(metadata, directory, case["case_id"]), "application": _application(case["task_id"]),
                      "recorded_grade": _public_errors(event["grade"], directory, case["case_id"]),
                      "recheck": _public_errors(check, directory, case["case_id"]), "evidence_path": evidence,
                      "has_report": any(path.name == "report.html" for path in paths),
                      "has_recording": any(path.name == "recording.mp4" for path in paths)})
        files_by_case[case["case_id"]] = (directory, paths)
    positive = [row for row in cases if row["case"]["kind"] == "positive"]
    controls = [row for row in cases if row["case"]["kind"] == "negative_control"]
    summary = {"schema_version": 1, "protocol": protocol["protocol"], "campaign": protocol["campaign"],
               "packaged_at": datetime.now(timezone.utc).isoformat(), "protocol_sha256": _sha(study_dir / "protocol.json"),
               "planned": len(protocol["plan"]), "completed": len(cases), "positive": _metrics(positive, positive=True),
               "negative_controls": _metrics(controls), "all_cases": _metrics(cases),
               "positive_by_application": _groups(positive, "application", positive=True), "positive_by_split": _groups(positive, "split", positive=True),
               "positive_by_geometry": _groups(positive, "geometry", positive=True), "controls_by_type": _groups(controls, "control"),
               "metric_definitions": {
                   "cost_per_verified_success": "Positive tasks only: total model cost in USD, including failed attempts, divided by rechecked passes. Null if any cost or outcome is unknown, or there are no passes.",
                   "operator_interventions": "Recorded operator intervention counts across all attempts in the group; missing values remain unknown.",
                   "paired_deltas": "Changed geometry minus normal geometry for the matched input, including failed attempts. Null if either measurement is unknown."},
               "pairs": _pairs(positive), "cases": cases}
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".followup-evidence-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "package"
        stage.mkdir()
        for name in ("protocol.json", "events.jsonl", "status.json"):
            shutil.copyfile(_file(study_dir, name, required=True), stage / name)
        for case_id, (directory, paths) in files_by_case.items():
            for path in paths:
                target = stage / "runs" / case_id / path.relative_to(directory)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
        (stage / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
        recheck = {"protocol_sha256": summary["protocol_sha256"], "rechecked_at": summary["packaged_at"],
                   "cases": [{"case_id": row["case"]["case_id"], "recorded_status": row["metadata"].get("status"), **row["recheck"]} for row in cases]}
        (stage / "recheck.json").write_text(json.dumps(recheck, indent=2, allow_nan=False) + "\n")
        (stage / "index.html").write_text(_html(summary))
        manifest = {"schema_version": 1, "generator": "package_followup_study", "protocol_sha256": summary["protocol_sha256"],
                    "files": [{"path": str(path.relative_to(stage)), "bytes": path.stat().st_size, "sha256": _sha(path)}
                              for path in sorted(stage.rglob("*")) if path.is_file()]}
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        if destination.exists():
            destination.rmdir()
        stage.rename(destination)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-dir", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(package_followup_study(args.study_dir, args.destination))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Cannot package follow-up study: {error}\n")


if __name__ == "__main__":
    main()
