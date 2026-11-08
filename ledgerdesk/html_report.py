"""Render portable run evidence. Nothing in this module grants agent access to files."""

from __future__ import annotations

import base64
from html import escape
import json
from pathlib import Path


def _text(value: object) -> str:
    return escape(str(value), quote=True)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _screenshot_data(run_dir: Path, relative_path: object) -> str | None:
    """Only embed raster screenshots contained in this run, including through symlinks."""
    if not isinstance(relative_path, str) or not relative_path:
        return None
    candidate = (run_dir / relative_path).resolve()
    if not candidate.is_relative_to(run_dir.resolve()) or not candidate.is_file():
        return None
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(candidate.suffix.lower())
    if mime is None:
        return None
    return f"data:{mime};base64,{base64.b64encode(candidate.read_bytes()).decode('ascii')}"


def _metric(label: str, value: object, note: str = "") -> str:
    return f'<div class="metric"><span>{_text(label)}</span><strong>{_text(value)}</strong><small>{_text(note)}</small></div>'


def _preview(verification: dict | None) -> str:
    if verification is None:
        return '<p class="muted">No independent verification result was recorded.</p>'
    errors = verification.get("errors", [])
    error_html = "".join(f"<li>{_text(error)}</li>" for error in errors)
    note = f'<ul class="errors">{error_html}</ul>' if error_html else ""
    headers = verification.get("headers", [])
    rows = verification.get("rows", [])
    if not headers:
        return note + '<p class="muted">No output preview is available.</p>'
    head = "".join(f'<th scope="col">{_text(header)}</th>' for header in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{_text(row.get(header, ''))}</td>" for header in headers) + "</tr>"
        for row in rows
    )
    if not rows:
        body = f'<tr><td colspan="{len(headers)}">The output contains no data rows.</td></tr>'
    return note + f'<div class="table-scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def write_report(run_dir: Path) -> Path:
    """Read recorded evidence and write an HTML file with embedded screenshots.

    ``run.json`` and ``events.jsonl`` are produced by the trusted runner;
    ``verification.json`` is optional. A model completion is never a pass.
    """
    run_dir = Path(run_dir)
    run = _read_json(run_dir / "run.json")
    verification_path = run_dir / "verification.json"
    verification = _read_json(verification_path) if verification_path.exists() else None
    control = run.get("control_verification")
    events_path = run_dir / "events.jsonl"
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()] if events_path.exists() else []
    status = str(run.get("status", "unknown"))
    if control is not None:
        verification = control
        verdict, tone = ("Expected refusal verified", "pass") if control.get("passed") is True else ("Control failed", "fail")
    elif status == "passed" and verification is not None and verification.get("passed") is True:
        verdict, tone = "Verified pass", "pass"
    elif status == "blocked":
        verdict, tone = "Blocked", "blocked"
    elif status == "failed" or (verification is not None and verification.get("passed") is False):
        verdict, tone = "Failed", "fail"
    else:
        verdict, tone = "Unverified", "blocked"

    usage = run.get("usage") or {}
    token_count = usage.get("total_tokens")
    token_note = "Complete API usage" if usage.get("complete") is True else "Incomplete or unavailable API usage"
    cost = run.get("estimated_cost_usd")
    cost_text = f"${cost:.4f}" if isinstance(cost, (int, float)) and not isinstance(cost, bool) else "Not available"
    elapsed = run.get("elapsed_seconds")
    elapsed_text = f"{elapsed:.1f}s" if isinstance(elapsed, (int, float)) else "Not available"
    metrics = "".join([
        _metric("Elapsed", elapsed_text, "Wall-clock run time"),
        _metric("Actions", run.get("action_count", "Not recorded"), "Executed desktop inputs"),
        _metric("Requests", run.get("request_count", "Not recorded"), "Model requests"),
        _metric("Tokens", token_count if token_count is not None else "Not available", token_note),
        _metric("Estimated cost", cost_text, "Estimate; provider billing is authoritative"),
    ])

    screenshots = []
    traces = []
    model_messages = []
    for index, event in enumerate(events, 1):
        kind = str(event.get("type", "event"))
        if kind == "screenshot":
            uri = _screenshot_data(run_dir, event.get("path"))
            caption = event.get("label") or event.get("path") or "Screenshot"
            if uri:
                screenshots.append(f'<figure><img src="{uri}" alt="{_text(caption)}" loading="lazy"><figcaption>{_text(caption)}<span>{_text(event.get("timestamp", ""))}</span></figcaption></figure>')
            else:
                screenshots.append(f'<p class="muted">Screenshot unavailable: {_text(caption)}</p>')
        if kind == "response" and event.get("text"):
            model_messages.append(f'<blockquote>{_text(event["text"])}</blockquote>')
        payload = {key: value for key, value in event.items() if key not in {"type", "timestamp"}}
        traces.append(f'<details><summary><span class="step">{index:02}</span> {_text(kind)} <time>{_text(event.get("timestamp", ""))}</time></summary><pre>{_text(json.dumps(payload, indent=2, ensure_ascii=False))}</pre></details>')
    if not model_messages and run.get("model_text"):
        model_messages.append(f'<blockquote>{_text(run["model_text"])}</blockquote>')

    error_html = f'<p class="run-error">{_text(run["error"])}</p>' if run.get("error") else ""
    verification_explanation = (
        "This is an operational control, graded separately from business-task completion."
        if control is not None else
        "The saved output matches the independent verifier."
        if verdict == "Verified pass" else
        "This run did not establish a verified successful outcome. See the recorded outcome below."
    )
    companion_files = [name for name in ("export.csv", "export.odt", "export.gnucash", "final.db", "baseline.db", "calc-source.ods", "writer-source.odt", "gnucash-source.gnucash", "run.json", "events.jsonl", "verification.json", "control-verification.json", "setup-blocked.json", "foreign-events.jsonl", "foreign-value.txt") if (run_dir / name).is_file()]
    downloads = " · ".join(f'<a href="{name}">{name}</a>' for name in companion_files)
    limits = json.dumps(run.get("limits", {}), ensure_ascii=False, indent=2)
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>LedgerDesk — {_text(verdict)} — {_text(run.get('task_id', 'Run evidence'))}</title>
<style>
:root{{color-scheme:light;--ink:#172a3a;--muted:#5c6d7d;--line:#dce3e9;--paper:#fff;--accent:#0d6171}}
*{{box-sizing:border-box}}body{{margin:0;background:#edf1f4;color:var(--ink);font:15px/1.55 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
header{{background:#122b3d;color:white;padding:44px max(24px,calc((100vw - 1180px)/2)) 38px;border-bottom:5px solid #46b3b2}}
.eyebrow{{font-size:12px;font-weight:750;letter-spacing:.14em;text-transform:uppercase;color:#99d7d8;margin:0 0 12px}}
h1{{font-size:clamp(25px,4vw,38px);line-height:1.2;margin:0 0 16px;font-weight:650;letter-spacing:-.025em}}
.subtitle{{max-width:790px;color:#d0dde5;margin:0}}.badge{{display:inline-block;border:1px solid currentColor;border-radius:5px;padding:5px 11px;font-size:13px;font-weight:750;margin:0 0 18px}}
.pass{{color:#96e8bc}}.fail{{color:#ffb2ad}}.blocked{{color:#ffdb91}}main{{max-width:1228px;margin:auto;padding:28px 24px 54px}}
.metrics{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin-bottom:24px}}.metric{{background:var(--paper);border:1px solid var(--line);border-radius:8px;padding:17px 18px;display:flex;flex-direction:column;gap:4px}}
.metric span{{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.06em;font-weight:700}}.metric strong{{font-size:26px;font-weight:650;overflow-wrap:anywhere}}.metric small{{color:var(--muted);font-size:11px;line-height:1.4}}
section{{background:var(--paper);border:1px solid var(--line);border-radius:8px;padding:25px 28px;margin-bottom:22px}}h2{{font-size:19px;margin:0 0 12px;letter-spacing:-.015em}}p{{margin:0 0 12px}}p:last-child{{margin-bottom:0}}
.muted,.meta{{color:var(--muted)}}.meta{{font-size:12px;overflow-wrap:anywhere}}.instruction{{font-size:18px;border-left:3px solid #61aaae;padding-left:17px;white-space:pre-wrap}}
.table-scroll{{overflow:auto;margin-top:17px}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:11px 13px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}}th{{background:#edf4f5;color:#204c56;font-size:11px;text-transform:uppercase;letter-spacing:.035em}}tbody tr:nth-child(even){{background:#f8fafb}}
.errors,.run-error{{color:#963e35;background:#fff1ee;padding:13px 18px;border-radius:5px}}.errors{{padding-left:36px}}.gallery{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}}figure{{margin:0;border:1px solid var(--line);border-radius:5px;overflow:hidden;background:#f5f7f9}}figure img{{display:block;width:100%;height:auto}}figcaption{{padding:10px 13px;font-size:12px;overflow-wrap:anywhere}}figcaption span{{display:block;color:var(--muted);font-size:11px}}
details{{border-top:1px solid var(--line)}}summary{{padding:12px 0;cursor:pointer;font-weight:600;font-size:13px}}.step{{color:#7d909c;font-variant-numeric:tabular-nums;margin-right:8px}}time{{float:right;color:var(--muted);font-size:11px;font-weight:400}}pre{{overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;background:#f2f5f7;padding:14px 17px;border-radius:5px;font:12px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace}}blockquote{{margin:12px 0;padding:13px 17px;border-left:3px solid #c5cfd7;background:#f8fafb;white-space:pre-wrap;font-size:14px}}footer{{color:var(--muted);font-size:12px;text-align:center;padding:5px 16px}}a{{color:var(--accent)}}
@media(max-width:800px){{.metrics{{grid-template-columns:repeat(2,minmax(0,1fr))}}.gallery{{grid-template-columns:1fr}}section{{padding:20px}}time{{float:none;display:block;margin-left:27px}}}}@media print{{body{{background:white}}header{{padding:24px;color:black;background:white;border-color:#bbb}}.eyebrow,.subtitle,.badge{{color:black}}main{{padding:20px 0}}section,figure{{break-inside:avoid}}details{{display:block}}}}
</style></head><body>
<header><p class="eyebrow">LedgerDesk / Run evidence</p><div class="badge {tone}">{_text(verdict)}</div><h1>{_text(run.get('task_id', 'Desktop reporting task'))}</h1><p class="subtitle">A native desktop task, operated through screenshots and mouse or keyboard actions, checked against a separate trusted verifier.</p></header>
<main><div class="metrics">{metrics}</div>
<section><h2>The task</h2><p class="instruction">{_text(run.get('instruction', 'No task instruction recorded.'))}</p><p class="meta">Run {_text(run.get('id', run_dir.name))} · Model {_text(run.get('model', 'Not recorded'))}<br>Started {_text(run.get('started_at', 'Not recorded'))} · Finished {_text(run.get('finished_at', 'Not recorded'))}</p>{error_html}</section>
<section><h2>Independent output verification</h2><p>{_text(verification_explanation)}</p><p class="muted">The model cannot call the verifier or inspect its expected-state calculations. Its completion message is not evidence that the output is correct.</p>{_preview(verification)}</section>
<section><h2>Companion evidence files</h2><p>{downloads}</p><p class="muted">These relative links work in the complete evidence package.</p></section>
<section><h2>What the model reported</h2><p class="muted">These are recorded model statements, shown separately from the verifier's result.</p>{''.join(model_messages) or '<p class="muted">No model completion text was recorded.</p>'}</section>
<section><h2>Desktop screenshots</h2><div class="gallery">{''.join(screenshots) or '<p class="muted">No screenshots were recorded.</p>'}</div></section>
<section><h2>Action and event trace</h2><p class="muted">Events are listed in recorded order. Expand a row to inspect its payload.</p>{''.join(traces) or '<p class="muted">No events were recorded.</p>'}</section>
<section><h2>Operating limits</h2><pre>{_text(limits)}</pre><p class="muted">All accounting records are fictional. This evidence describes one recorded attempt; it is not a general reliability benchmark.</p></section>
<footer>LedgerDesk · Screenshot-driven computer use · Self-contained evidence file</footer></main></body></html>'''
    target = run_dir / "report.html"
    target.write_text(html, encoding="utf-8")
    return target
