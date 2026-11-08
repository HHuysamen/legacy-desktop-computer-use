"""Run the fixed 76-attempt extension, retaining every outcome and original24."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from ledgerdesk.__main__ import ROOT, TASKS, REPORTS, compose, load_env, run_task, save_json, session_lock


def plan():
    return ([{"task": task, "repetition": repetition} for repetition in (9, 10) for task in REPORTS]
            + [{"task": task, "repetition": repetition} for repetition in range(1, 11) for task in TASKS if task not in REPORTS])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="Stop after this many cumulative extension attempts; later invocations resume")
    args = parser.parse_args()
    load_env()
    original_path = ROOT / "output/evaluation-24.json"
    original_bytes = original_path.read_bytes()
    original = json.loads(original_bytes)
    assert len(original["runs"]) == 24
    assert Counter(r["task_id"] for r in original["runs"]) == Counter({task: 8 for task in REPORTS})
    output = ROOT / "output/evaluation-extension-76.json"
    queue = plan()
    study = json.loads(output.read_text()) if output.exists() else {
        "protocol": "expanded-100-v1", "created_at": datetime.now(timezone.utc).isoformat(),
        "planned_attempts": 76, "plan": queue, "budget_usd": 20.0,
        "original_evaluation_sha256": hashlib.sha256(original_bytes).hexdigest(), "runs": [],
    }
    assert study["plan"] == queue
    assert study["original_evaluation_sha256"] == hashlib.sha256(original_bytes).hexdigest()
    assert all(r["task_id"] == queue[i]["task"] and r["repetition"] == queue[i]["repetition"] for i, r in enumerate(study["runs"]))
    def persist():
        study["completed_attempts"] = len(study["runs"])
        study["estimated_cost_usd_known"] = round(sum(r.get("estimated_cost_usd") or 0 for r in study["runs"]), 6)
        study["cost_complete"] = all(r.get("estimated_cost_usd") is not None for r in study["runs"])
        save_json(output, study)
        combined = original["runs"] + study["runs"]
        save_json(ROOT / "output/evaluation-100.json", {
            "protocol": study["protocol"], "planned_attempts": 100, "completed_attempts": len(combined),
            "task_ids": list(TASKS), "historical_attempts": 24, "new_attempts": len(study["runs"]),
            "estimated_cost_usd_known": round(sum(r.get("estimated_cost_usd") or 0 for r in combined), 6),
            "cost_complete": all(r.get("estimated_cost_usd") is not None for r in combined),
            "evaluation_parts": ["output/evaluation-24.json", "output/evaluation-extension-76.json"], "runs": combined,
        })
    with session_lock():
        try:
            persist()
            for index in range(len(study["runs"]), min(args.limit or 76, 76)):
                item = queue[index]
                spent_guard = sum(r.get("estimated_cost_usd") if r.get("estimated_cost_usd") is not None else 1.0 for r in study["runs"])
                if spent_guard + 1.0 > study["budget_usd"]:
                    raise RuntimeError("Study budget reserve exhausted")
                report = item["task"] in REPORTS
                attempt = argparse.Namespace(task=item["task"], as_of="2026-10-15", model="gpt-6.1-terra", max_requests=20 if report else 30, max_actions=40 if report else 80, timeout=300 if report else 420, budget_usd=1.0)
                print(f"START {index+1}/76 {item}", flush=True)
                directory, metadata = run_task(attempt)
                study["runs"].append({**metadata, "repetition": item["repetition"], "task": item["task"], "run_dir": str(directory.relative_to(ROOT))})
                persist()
                print(f"DONE {index+1}/76 {metadata['status']} cost={metadata.get('estimated_cost_usd')} elapsed={metadata['elapsed_seconds']}", flush=True)
                if metadata.get("api_error", {}).get("status_code") in {401, 403, 429}:
                    raise RuntimeError("Provider access failure retained; stopped further requests")
                if metadata.get("request_count", 0) == 0:
                    raise RuntimeError("Infrastructure failure retained; inspect before continuing")
            assert original_path.read_bytes() == original_bytes
        finally:
            compose("down", timeout=60)


if __name__ == "__main__":
    main()
