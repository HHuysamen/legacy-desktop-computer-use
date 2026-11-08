"""Package the finished nine-attempt evaluation without altering its evidence."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from html import escape
import json
import math
from pathlib import Path
import re
import shutil
from statistics import median
import tempfile


ROOT = Path(__file__).resolve().parents[1]
TASKS = ("monthly-revenue", "overdue-invoices", "reconciliation-exceptions")
FILES = ("report.html", "run.json", "events.jsonl", "verification.json", "export.csv")


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _source(path: Path, runs_root: Path) -> Path:
    source = path.resolve()
    if source == runs_root or not source.is_relative_to(runs_root) or not source.is_dir():
        raise ValueError("Evidence run must be an existing directory inside output/runs.")
    return source


def _read_run(source: Path) -> dict:
    for name in FILES:
        path = source / name
        if path.exists() and not path.resolve().is_relative_to(source):
            raise ValueError("Evidence file points outside its run directory.")
    run = _json(source / "run.json")
    identifier = run.get("id", "")
    if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", identifier):
        raise ValueError("Run ID is not a safe evidence directory name.")
    if run.get("status") not in {"passed", "failed", "blocked"} or not run.get("finished_at"):
        raise ValueError(f"Run {identifier} is not finished.")
    verification = _json(source / "verification.json") if (source / "verification.json").exists() else None
    if run["status"] == "passed" and (verification is None or verification.get("passed") is not True):
        raise ValueError(f"Run {identifier} claims success without a passing verifier.")
    if run["status"] == "passed" and not (source / "export.csv").is_file():
        raise ValueError(f"Verified run {identifier} is missing its exported CSV.")
    return run


def _copy_run(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True)
    paths = [source / name for name in FILES]
    paths += sorted((source / "screenshots").glob("*")) if (source / "screenshots").exists() else []
    for name in ("report.html", "run.json", "events.jsonl"):
        if not (source / name).is_file():
            raise ValueError(f"Required evidence file is missing: {name}")
    for path in paths:
        if not path.exists():
            continue
        if not path.resolve().is_relative_to(source) or not path.is_file():
            raise ValueError("Evidence contains a file or screenshot outside its run directory.")
        if path.parent.name == "screenshots" and path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


def _stats(runs: list[dict]) -> dict:
    times = [run["elapsed_seconds"] for run in runs if _number(run.get("elapsed_seconds"))]
    costs = [run["estimated_cost_usd"] for run in runs if _number(run.get("estimated_cost_usd"))]

    def bounds(field):
        values = [run[field] for run in runs if _number(run.get(field))]
        return [min(values), max(values)] if values else None

    return {
        "attempts": len(runs), "verified": sum(run["status"] == "passed" for run in runs),
        "failed": sum(run["status"] == "failed" for run in runs),
        "blocked": sum(run["status"] == "blocked" for run in runs),
        "median_elapsed_seconds": median(times) if times else None,
        "elapsed_values_available": len(times), "action_range": bounds("action_count"),
        "request_range": bounds("request_count"),
        "estimated_cost_usd_known": round(sum(costs), 6) if costs else None,
        "cost_values_available": len(costs),
        "usage_complete": all(run.get("usage", {}).get("complete") is True for run in runs),
    }


def _display(value, suffix="") -> str:
    return "Unavailable" if value is None else f"{value:g}{suffix}"


def _scorecard(summary: dict) -> str:
    def text(value):
        return escape(str(value), quote=True)

    cards = []
    for task, stats in summary["tasks"].items():
        action_range = stats["action_range"]
        request_range = stats["request_range"]
        ranges = lambda values: "Unavailable" if values is None else f"{values[0]}–{values[1]}"
        cards.append(f'''<article><h2>{text(task.replace('-', ' ').title())}</h2><strong>{stats['verified']} / {stats['attempts']}</strong><p>Independently verified</p><dl><dt>Median elapsed</dt><dd>{_display(stats['median_elapsed_seconds'], 's')}</dd><dt>Actions</dt><dd>{ranges(action_range)}</dd><dt>Requests</dt><dd>{ranges(request_range)}</dd><dt>Known estimated cost</dt><dd>{_display(stats['estimated_cost_usd_known'], ' USD')}</dd></dl></article>''')
    rows = []
    for run in summary["runs"]:
        identifier = run["id"]
        rows.append(f'''<tr><td><a href="runs/{identifier}/report.html">{text(run['task_id'])}</a><small>{text(identifier)}</small></td><td class="{run['status']}">{text(run['status'])}</td><td>{_display(run.get('elapsed_seconds'), 's')}</td><td>{text(run.get('action_count', 'Unavailable'))}</td><td>{text(run.get('request_count', 'Unavailable'))}</td><td>{_display(run.get('estimated_cost_usd'), ' USD')}</td><td>{'Complete' if run.get('usage', {}).get('complete') is True else 'Incomplete / unavailable'}</td></tr>''')
    pilot = summary.get("pilot")
    pilot_html = f'<p>Separate pilot: <a href="pilot/{pilot["id"]}/report.html">{text(pilot["id"])}</a>. The pilot is excluded from every count and statistic above.</p>' if pilot else ""
    complete = summary["overall"]["usage_complete"] and summary["overall"]["cost_values_available"] == 9
    usage_note = "Usage and cost estimates are available for all nine attempts." if complete else "Usage or cost is incomplete for at least one attempt. Known costs are partial totals, not a full bill."
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; media-src 'self'; img-src 'self'; base-uri 'none'"><title>LedgerDesk — Nine-attempt scorecard</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#edf2f5;color:#1b3041;font:15px/1.55 system-ui,sans-serif}}header{{background:#153245;color:white;padding:45px max(24px,calc((100vw - 1150px)/2));border-bottom:5px solid #49b8b7}}header p{{color:#c4dce6;max-width:780px}}.eyebrow{{text-transform:uppercase;letter-spacing:.12em;font-size:12px}}h1{{font-size:34px;line-height:1.2;margin:10px 0}}main{{max-width:1198px;margin:auto;padding:28px 24px 50px}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}}article,section{{background:white;border:1px solid #d5e0e7;border-radius:8px;padding:23px;margin-bottom:23px}}article h2{{font-size:17px;margin-top:0}}article strong{{font-size:37px;color:#126d65}}article p{{margin-top:0;color:#516d7c}}dl{{display:grid;grid-template-columns:1fr 1fr;font-size:12px;gap:7px}}dt{{color:#647884}}dd{{margin:0;text-align:right;font-weight:650}}h2{{font-size:20px}}.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:12px}}td,th{{text-align:left;padding:12px;border-bottom:1px solid #e1e7eb;white-space:nowrap}}th{{background:#edf4f6}}small{{display:block;color:#667e8d;font-size:10px}}a{{color:#076778}}.passed{{color:#137653;font-weight:700}}.failed,.blocked{{color:#963e35;font-weight:700}}video{{max-width:100%;width:900px;background:#122c3c}}.note{{font-size:13px;color:#526c7c}}@media(max-width:800px){{.cards{{grid-template-columns:1fr}}h1{{font-size:27px}}}}footer{{font-size:12px;color:#6a7d89}}
</style></head><body><header><p class="eyebrow">LedgerDesk / Recorded evaluation</p><h1>{summary['overall']['verified']} of 9 attempts independently verified</h1><p>Three reporting tasks. Three attempts each. Every evaluated outcome is retained, including failures and blocked attempts.</p></header><main><div class="cards">{''.join(cards)}</div><section><h2>All nine attempts</h2><div class="scroll"><table><thead><tr><th>Task / evidence</th><th>Outcome</th><th>Elapsed</th><th>Actions</th><th>Requests</th><th>Estimated cost</th><th>API usage</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div><p class="note">{usage_note} Costs use published standard token rates and exclude cache discounts; provider billing remains authoritative.</p></section><section><h2>Watch a verified attempt</h2><video controls preload="metadata" src="demo.mp4" poster="poster.png">Download demo.mp4 to watch this recorded native desktop session.</video><p><a href="sample-report.html">Open its self-contained evidence report</a> · <a href="summary.json">Machine-readable summary</a> · <a href="manifest.json">SHA-256 manifest</a></p>{pilot_html}</section><section><h2>What these results establish</h2><p>The model operated the fictional native application through screenshots and mouse or keyboard actions. A separate verifier checked each exported CSV against the fixture. The model's completion text alone cannot pass a run.</p><p class="note">This is a small, fixed-fixture demonstration on one recorded desktop configuration. It does not establish general reliability across applications, layouts or operating systems.</p></section><footer>Packaged {text(summary['packaged_at'])}. Files retain their original run identifiers.</footer></main></body></html>'''


def package_evidence(evaluation_path: Path, destination: Path, *, pilot: Path | None = None) -> Path:
    evaluation_path = Path(evaluation_path).resolve()
    workspace = evaluation_path.parent.parent
    runs_root = (workspace / "output" / "runs").resolve()
    evaluation = _json(evaluation_path)
    entries = evaluation.get("runs", [])
    if evaluation.get("planned_attempts") != 9 or evaluation.get("completed_attempts") != 9 or len(entries) != 9:
        raise ValueError("Packaging requires the completed nine-attempt evaluation.")
    sources = [_source(workspace / entry["run_dir"], runs_root) for entry in entries]
    if len(set(sources)) != 9:
        raise ValueError("Evaluation contains duplicate run directories.")
    runs = [_read_run(source) for source in sources]
    if Counter(run.get("task_id") for run in runs) != Counter({task: 3 for task in TASKS}):
        raise ValueError("Evaluation must contain exactly three attempts for each reporting task.")
    if len({run["id"] for run in runs}) != 9:
        raise ValueError("Evaluation contains duplicate run IDs.")
    for entry, run in zip(entries, runs):
        if any(key in entry and entry[key] != run[key] for key in ("id", "task_id", "status")):
            raise ValueError("Evaluation metadata disagrees with the recorded run.")
    selected = next(((source, run) for source, run in zip(sources, runs) if run["status"] == "passed" and (source / "recording.mp4").is_file()), None)
    if selected is None:
        raise ValueError("A verified evaluated run with a recording is required for demo.mp4.")
    pilot_source = _source(Path(pilot) if Path(pilot).is_absolute() else workspace / pilot, runs_root) if pilot is not None else None
    pilot_run = _read_run(pilot_source) if pilot_source is not None else None
    if pilot_source in sources:
        raise ValueError("The optional pilot must be separate from the nine evaluated runs.")
    destination = Path(destination).resolve()
    if destination.is_relative_to(runs_root) or (destination.exists() and any(destination.iterdir())):
        raise ValueError("Choose an empty destination outside output/runs.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "schema_version": 1, "packaged_at": datetime.now(timezone.utc).isoformat(),
        "planned_attempts": 9, "completed_attempts": 9, "pilot_excluded_from_statistics": True,
        "overall": _stats(runs), "tasks": {task: _stats([run for run in runs if run["task_id"] == task]) for task in TASKS},
        "runs": runs, "pilot": pilot_run, "demo_run_id": selected[1]["id"],
    }
    with tempfile.TemporaryDirectory(prefix=".ledgerdesk-evidence-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "package"
        stage.mkdir()
        for source, run in zip(sources, runs):
            _copy_run(source, stage / "runs" / run["id"])
        if pilot_source is not None:
            _copy_run(pilot_source, stage / "pilot" / pilot_run["id"])
        recording = selected[0] / "recording.mp4"
        if not recording.resolve().is_relative_to(selected[0]):
            raise ValueError("Recording must remain within its run directory.")
        shutil.copyfile(recording, stage / "demo.mp4")
        screenshots = sorted((selected[0] / "screenshots").glob("*.png"))
        if not screenshots or not screenshots[-1].resolve().is_relative_to(selected[0]):
            raise ValueError("A final PNG screenshot within the selected run is required.")
        shutil.copyfile(screenshots[-1], stage / "poster.png")
        shutil.copyfile(selected[0] / "report.html", stage / "sample-report.html")
        _write_json(stage / "summary.json", summary)
        (stage / "index.html").write_text(_scorecard(summary), encoding="utf-8")
        manifest = {
            "schema_version": 1, "generator": "ledgerdesk.package_evidence",
            "evaluation_sha256": hashlib.sha256(evaluation_path.read_bytes()).hexdigest(),
            "files": [{"path": str(path.relative_to(stage)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size} for path in sorted(stage.rglob("*")) if path.is_file()],
        }
        _write_json(stage / "manifest.json", manifest)
        if destination.exists():
            destination.rmdir()
        stage.rename(destination)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation", type=Path, default=ROOT / "output" / "evaluation.json")
    parser.add_argument("--destination", type=Path, default=ROOT / "examples" / "evaluation")
    parser.add_argument("--pilot", type=Path, help="Optional separate pilot run inside output/runs; excluded from statistics")
    args = parser.parse_args()
    try:
        print(package_evidence(args.evaluation, args.destination, pilot=args.pilot))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f"Cannot package evidence: {error}\n")


if __name__ == "__main__":
    main()
