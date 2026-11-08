import base64
import json
import struct
from types import SimpleNamespace

import pytest
import httpx2
from openai import APIStatusError, RateLimitError
from openai.types.responses import ResponseComputerToolCall, ResponseOutputMessage

from ledgerdesk import computer_agent


PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" + struct.pack(">II", 1100, 760)).decode()


class Driver:
    def __init__(self):
        self.actions = []

    def screenshot(self):
        return {"type": "computer_screenshot", "image_url": "data:image/png;base64," + PNG}

    def action(self, action):
        self.actions.append(action.type)

    click = double_click = drag = keypress = move = scroll = type = wait = action


def call(number=1, *, actions=None, checks=None):
    return ResponseComputerToolCall.model_validate({
        "id": f"computer-{number}", "call_id": f"call-{number}", "status": "completed", "type": "computer_call",
        "pending_safety_checks": checks or [], "actions": actions or [{"type": "click", "button": "left", "x": 10, "y": 10}],
    })


def reply(*items, usage=True, status="completed", text=""):
    return SimpleNamespace(status=status, output=list(items), output_text=text, usage=SimpleNamespace(input_tokens=200, output_tokens=30, total_tokens=230) if usage else None)


def final(number=1, **kwargs):
    message = ResponseOutputMessage.model_validate({"id": f"message-{number}", "role": "assistant", "status": "completed", "type": "message", "content": [{"type": "output_text", "text": "Export finished.", "annotations": []}]})
    return reply(message, text="Export finished.", **kwargs)


def fake_client(monkeypatch, responses):
    class Client:
        def __init__(self, **kwargs):
            self.settings = kwargs
            self.responses = self
            self.requests = []
            self.closed = False

        def create(self, **kwargs):
            self.requests.append(kwargs)
            value = responses.pop(0)
            if isinstance(value, Exception):
                raise value
            return value

        def close(self):
            self.closed = True

    client = Client()

    def factory(**kwargs):
        client.settings = kwargs
        return client

    monkeypatch.setattr(computer_agent, "OpenAI", factory)
    return client


def test_real_sdk_executes_computer_calls_and_collects_all_usage(monkeypatch, tmp_path):
    client = fake_client(monkeypatch, [reply(call()), final()])
    driver = Driver()
    result = computer_agent.run_agent(driver, "Export monthly revenue.", tmp_path)
    assert result["status"] == "completed"
    assert driver.actions == ["click"]
    assert result["action_count"] == 1
    assert result["request_count"] == 2
    assert result["usage"] == {"input_tokens": 400, "output_tokens": 60, "total_tokens": 460, "complete": True}
    assert result["estimated_cost_usd"] == pytest.approx(0.0007)
    assert result["model_text"] == "Export finished."
    assert client.settings["max_retries"] == 0 and client.closed
    assert client.requests[0]["tools"] == [{"type": "computer"}]
    assert client.requests[0]["store"] is False
    assert client.requests[0]["truncation"] == "disabled"
    assert client.requests[0]["max_output_tokens"] == 4096
    assert "computer_call_output" in json.dumps(client.requests[1]["input"])
    assert "image_url" not in (tmp_path / "events.jsonl").read_text()


def test_budget_is_checked_before_the_first_request(monkeypatch, tmp_path):
    client = fake_client(monkeypatch, [])
    result = computer_agent.run_agent(Driver(), "Export.", tmp_path, budget_usd=0.001)
    assert result["status"] == "blocked"
    assert "budget" in result["error"]
    assert client.requests == []


def test_pending_safety_check_stops_before_any_actions(monkeypatch, tmp_path):
    client = fake_client(monkeypatch, [reply(call(checks=[{"id": "check", "code": "sensitive_domain", "message": "Confirm action"}]))])
    driver = Driver()
    result = computer_agent.run_agent(driver, "Export.", tmp_path)
    assert result["status"] == "blocked"
    assert "human review" in result["error"]
    assert driver.actions == []
    assert len(client.requests) == 1


def test_later_safety_check_blocks_the_whole_response(monkeypatch, tmp_path):
    fake_client(monkeypatch, [reply(call(1), call(2, checks=[{"id": "check", "code": "sensitive_domain", "message": "Confirm action"}]))])
    driver = Driver()
    result = computer_agent.run_agent(driver, "Export.", tmp_path)
    assert result["status"] == "blocked"
    assert driver.actions == []


def test_action_limit_blocks_remaining_batch(monkeypatch, tmp_path):
    fake_client(monkeypatch, [reply(call(actions=[{"type": "click", "button": "left", "x": 10, "y": 10}, {"type": "click", "button": "left", "x": 20, "y": 20}]))])
    driver = Driver()
    result = computer_agent.run_agent(driver, "Export.", tmp_path, max_actions=1)
    assert result["status"] == "blocked"
    assert "action limit" in result["error"]
    assert driver.actions == ["click"]
    assert result["action_count"] == 1


def test_last_request_does_not_start_more_actions(monkeypatch, tmp_path):
    fake_client(monkeypatch, [reply(call())])
    driver = Driver()
    result = computer_agent.run_agent(driver, "Export.", tmp_path, max_requests=1)
    assert result["status"] == "blocked"
    assert "request limit" in result["error"]
    assert driver.actions == []


def test_missing_usage_stops_before_actions_and_never_claims_zero_cost(monkeypatch, tmp_path):
    fake_client(monkeypatch, [reply(call(), usage=False)])
    driver = Driver()
    result = computer_agent.run_agent(driver, "Export.", tmp_path)
    assert result["status"] == "blocked"
    assert result["usage"]["complete"] is False
    assert result["estimated_cost_usd"] is None
    assert driver.actions == []


def test_unknown_model_is_not_spent_against_unverified_prices(monkeypatch, tmp_path):
    client = fake_client(monkeypatch, [])
    result = computer_agent.run_agent(Driver(), "Export.", tmp_path, model="unknown-model")
    assert result["status"] == "blocked"
    assert "price configuration" in result["error"]
    assert client.requests == []


def test_api_error_does_not_log_request_or_secret(monkeypatch, tmp_path):
    fake_client(monkeypatch, [RuntimeError("Authorization: Bearer SUPER-SECRET")])
    result = computer_agent.run_agent(Driver(), "Export.", tmp_path)
    assert result["status"] == "failed"
    assert result["usage"]["complete"] is False
    assert result["estimated_cost_usd"] is None
    assert "SUPER-SECRET" not in json.dumps(result)
    assert "SUPER-SECRET" not in (tmp_path / "events.jsonl").read_text()


def test_incomplete_response_never_executes_actions(monkeypatch, tmp_path):
    fake_client(monkeypatch, [reply(call(), status="incomplete")])
    driver = Driver()
    result = computer_agent.run_agent(driver, "Export.", tmp_path)
    assert result["status"] == "blocked"
    assert "did not complete" in result["error"]
    assert driver.actions == []


def test_screenshot_size_is_bounded_before_api(monkeypatch, tmp_path):
    client = fake_client(monkeypatch, [])
    driver = Driver()
    bad_png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" + struct.pack(">II", 4096, 2160)).decode()
    driver.screenshot = lambda: {"type": "computer_screenshot", "image_url": "data:image/png;base64," + bad_png}
    result = computer_agent.run_agent(driver, "Export.", tmp_path)
    assert result["status"] == "blocked"
    assert "pixel limit" in result["error"]
    assert client.requests == []


def test_deadline_rechecked_after_model_response(monkeypatch, tmp_path):
    clock = [0.0]
    monkeypatch.setattr(computer_agent.time, "monotonic", lambda: clock[0])
    client = fake_client(monkeypatch, [reply(call())])
    create = client.create

    def slow_response(**kwargs):
        response = create(**kwargs)
        clock[0] = 1.0
        return response

    client.create = slow_response
    driver = Driver()
    result = computer_agent.run_agent(driver, "Export.", tmp_path, timeout_seconds=0.5)
    assert result["status"] == "blocked"
    assert "time limit" in result["error"]
    assert driver.actions == []


def test_interrupted_request_has_unknown_final_cost(monkeypatch, tmp_path):
    client = fake_client(monkeypatch, [])

    def interrupted(**kwargs):
        raise KeyboardInterrupt

    client.create = interrupted
    result = computer_agent.run_agent(Driver(), "Export.", tmp_path)
    assert result["status"] == "blocked"
    assert result["usage"]["complete"] is False
    assert result["estimated_cost_usd"] is None


def test_local_response_failure_preserves_received_usage(monkeypatch, tmp_path):
    malformed_call = SimpleNamespace(type="computer_call", id="x", call_id="x", status="completed", pending_safety_checks=[])

    def cannot_replay(**kwargs):
        raise ValueError("private response details")

    malformed_call.to_dict = cannot_replay
    fake_client(monkeypatch, [reply(malformed_call)])
    result = computer_agent.run_agent(Driver(), "Export.", tmp_path)
    assert result["status"] == "failed"
    assert "response validation" in result["error"]
    assert "private response details" not in result["error"]
    assert result["usage"]["complete"] is True
    assert result["usage"]["total_tokens"] == 230
    assert result["estimated_cost_usd"] == pytest.approx(0.00035)


def test_no_subsequent_effect_after_slow_driver_action(monkeypatch, tmp_path):
    clock = [0.0]
    monkeypatch.setattr(computer_agent.time, "monotonic", lambda: clock[0])
    fake_client(monkeypatch, [reply(call(actions=[{"type": "click", "button": "left", "x": 10, "y": 10}, {"type": "click", "button": "left", "x": 20, "y": 20}]))])
    driver = Driver()

    def slow_click(action):
        driver.actions.append(action.type)
        clock[0] = 2.0

    driver.click = slow_click
    result = computer_agent.run_agent(driver, "Export.", tmp_path, timeout_seconds=1.0)
    assert result["status"] == "blocked"
    assert "time limit" in result["error"]
    assert driver.actions == ["click"]
    assert result["action_count"] == 1


def test_credit_exhaustion_is_blocked_and_diagnostic_is_sanitized(monkeypatch, tmp_path):
    request = httpx2.Request("POST", "https://api.openai.com/v1/responses", headers={"Authorization": "Bearer SECRET-KEY"})
    error = RateLimitError("PRIVATE PROVIDER MESSAGE", response=httpx2.Response(429, request=request, headers={"x-request-id": "PRIVATE-REQUEST"}), body={"code": "credit_balance_exhausted", "type": "insufficient_quota", "message": "PRIVATE BODY"})
    fake_client(monkeypatch, [error])
    driver = Driver()
    result = computer_agent.run_agent(driver, "Export.", tmp_path)
    assert result["status"] == "blocked"
    assert "add credits" in result["error"]
    assert result["api_error"] == {"status_code": 429, "code": "credit_balance_exhausted", "type": "insufficient_quota"}
    assert result["usage"]["complete"] is False and result["estimated_cost_usd"] is None
    assert driver.actions == []
    serialized = json.dumps(result) + (tmp_path / "events.jsonl").read_text()
    assert "PRIVATE" not in serialized and "SECRET-KEY" not in serialized


@pytest.mark.parametrize(("status", "expected"), [(401, "blocked"), (403, "blocked"), (429, "blocked"), (400, "failed"), (500, "failed")])
def test_http_access_and_quota_errors_are_not_task_failures(monkeypatch, tmp_path, status, expected):
    error = APIStatusError("private", response=httpx2.Response(status, request=httpx2.Request("POST", "https://api.openai.com/v1/responses")), body={"code": "generic_error", "type": "api_error"})
    fake_client(monkeypatch, [error])
    result = computer_agent.run_agent(Driver(), "Export.", tmp_path)
    assert result["status"] == expected
    assert result["api_error"]["status_code"] == status
    assert result["estimated_cost_usd"] is None


def test_api_error_identifiers_reject_unsafe_or_oversized_values(monkeypatch, tmp_path):
    error = RateLimitError("private", response=httpx2.Response(429, request=httpx2.Request("POST", "https://api.openai.com/v1/responses")), body={"code": "<script>SECRET</script>", "type": "x" * 101})
    fake_client(monkeypatch, [error])
    result = computer_agent.run_agent(Driver(), "Export.", tmp_path)
    assert result["api_error"] == {"status_code": 429, "code": None, "type": None}
    assert "SECRET" not in json.dumps(result)
    assert "SECRET" not in (tmp_path / "events.jsonl").read_text()
