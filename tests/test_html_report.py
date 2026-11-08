import json
from pathlib import Path

import pytest

from ledgerdesk.html_report import write_report


def make_run(tmp_path: Path, *, status="passed", verification=True, **fields):
    run = {"id": "example-run", "task_id": "monthly-revenue", "instruction": "Export September revenue.", "status": status, "elapsed_seconds": 12.5, "action_count": 7, "request_count": 3, "model": "test-model", **fields}
    (tmp_path / "run.json").write_text(json.dumps(run))
    (tmp_path / "events.jsonl").write_text("")
    if verification is not None:
        (tmp_path / "verification.json").write_text(json.dumps({"passed": verification, "headers": ["customer", "revenue"], "rows": [{"customer": "Fjord Tools", "revenue": "42.00"}], "errors": [] if verification else ["Revenue differs"], "row_count": 1}))
    return tmp_path


def test_verified_result_and_preview_are_visible(tmp_path):
    path = write_report(make_run(tmp_path, usage={"total_tokens": 1234, "complete": True}, estimated_cost_usd=0.1234))
    html = path.read_text()
    assert "Verified pass" in html
    assert "Fjord Tools" in html and "42.00" in html
    assert "1234" in html and "$0.1234" in html
    assert "completion message is not evidence" in html


@pytest.mark.parametrize(("status", "verification", "verdict"), [("passed", None, "Unverified"), ("passed", False, "Failed"), ("blocked", None, "Blocked"), ("failed", None, "Failed")])
def test_model_or_runner_claim_cannot_replace_verification(tmp_path, status, verification, verdict):
    html = write_report(make_run(tmp_path, status=status, verification=verification)).read_text()
    assert f">{verdict}</div>" in html
    assert '>Verified pass</div>' not in html


def test_missing_usage_is_not_reported_as_zero(tmp_path):
    html = write_report(make_run(tmp_path)).read_text()
    assert "Not available" in html
    assert "Incomplete or unavailable API usage" in html
    assert "Complete API usage" not in html


def test_all_untrusted_text_is_escaped(tmp_path):
    injection = '<script>alert("x")</script>'
    make_run(tmp_path, instruction=injection, error=injection, model=injection)
    (tmp_path / "events.jsonl").write_text(json.dumps({"type": "response", "timestamp": injection, "text": injection}) + "\n")
    (tmp_path / "verification.json").write_text(json.dumps({"passed": False, "errors": [injection], "headers": [injection], "rows": [{injection: injection}]}))
    html = write_report(tmp_path).read_text()
    assert injection not in html
    assert "&lt;script&gt;" in html
    assert "default-src 'none'" in html


def test_screenshots_embedded_and_external_paths_rejected(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    make_run(run_dir)
    png = b"\x89PNG\r\n\x1a\nexample"
    (run_dir / "screen.png").write_bytes(png)
    (tmp_path / "outside.png").write_bytes(b"PRIVATE OUTSIDE IMAGE")
    (run_dir / "linked.png").symlink_to(tmp_path / "outside.png")
    events = [{"type": "screenshot", "path": path} for path in ("screen.png", "../outside.png", "linked.png", "missing.png")]
    (run_dir / "events.jsonl").write_text("\n".join(json.dumps(event) for event in events))
    html = write_report(run_dir).read_text()
    assert html.count('<img src="data:image/png;base64,') == 1
    assert "UFJJVkFURSBPVVRTSURFIElNQUdF" not in html
    assert html.count("Screenshot unavailable:") == 3


def test_partial_usage_label_stays_partial(tmp_path):
    html = write_report(make_run(tmp_path, usage={"total_tokens": 95, "complete": False})).read_text()
    assert "95" in html
    assert "Incomplete or unavailable API usage" in html


def test_model_text_metadata_is_available_when_response_events_are_missing(tmp_path):
    html = write_report(make_run(tmp_path, model_text='Exported <revenue.csv>.')).read_text()
    assert "Exported &lt;revenue.csv&gt;." in html
    assert "No model completion text was recorded." not in html


def test_document_output_has_correct_verification_label_and_download(tmp_path):
    make_run(tmp_path, task_id='writer-find-replace')
    (tmp_path / 'export.odt').write_bytes(b'demo document')
    html = write_report(tmp_path).read_text()
    assert 'Independent output verification' in html
    assert 'href="export.odt"' in html
    assert 'that the CSV is correct' not in html


def test_expected_control_refusal_is_not_labelled_business_success(tmp_path):
    make_run(tmp_path, status='blocked', verification=None, control_verification={'passed': True, 'errors': [], 'component': 'driver'})
    (tmp_path/'control-verification.json').write_text('{}')
    html = write_report(tmp_path).read_text()
    assert 'Expected refusal verified' in html
    assert '>Verified pass</div>' not in html
    assert 'graded separately from business-task completion' in html
    assert 'href="control-verification.json"' in html
