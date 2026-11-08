import json

import pytest

from ledgerdesk.desktop_driver import DesktopDriver
from ledgerdesk.guest_control import validate_action


BOUNDS = (0, 0, 1200, 900)


def driver(tmp_path, monkeypatch):
    instance = DesktopDriver(tmp_path)
    sent = []

    def send(action):
        sent.append(action)
        validate_action(action, BOUNDS)
        return {"ok": True}

    monkeypatch.setattr(instance, "_send", send)
    return instance, sent


def test_key_case_normalization_preserves_raw_request_and_original_object(tmp_path, monkeypatch):
    instance, sent = driver(tmp_path, monkeypatch)
    original = {"type": "keypress", "keys": ["Tab"]}
    instance.keypress(original)
    assert original == {"type": "keypress", "keys": ["Tab"]}
    assert sent == [{"type": "keypress", "keys": ["TAB"]}]
    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert events[0]["type"] == "action" and events[0]["action"] == original
    assert events[1]["type"] == "action_transport" and events[1]["action"] == sent[0]
    assert events[2]["type"] == "action_result"


def test_normalized_combination_retains_application_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGERDESK_TASK", "writer-find-replace")
    instance, sent = driver(tmp_path, monkeypatch)
    instance.keypress({"type": "keypress", "keys": ["Ctrl", "s"]})
    assert sent[-1]["keys"] == ["CTRL", "S"]
    monkeypatch.setenv("LEDGERDESK_TASK", "monthly-revenue")
    with pytest.raises(ValueError, match="combination"):
        instance.keypress({"type": "keypress", "keys": ["Ctrl", "s"]})


@pytest.mark.parametrize("keys", [["alt", "f4"], ["CTRL", "escape"], [" Tab"], ["ſ"], ["s"]])
def test_case_normalization_does_not_expand_guest_allowlist(tmp_path, monkeypatch, keys):
    monkeypatch.setenv("LEDGERDESK_TASK", "monthly-revenue")
    instance, sent = driver(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        instance.keypress({"type": "keypress", "keys": keys})
    if keys == ["ſ"]:
        assert sent[-1]["keys"] == keys
    assert not any(json.loads(line)["type"] == "action_result" for line in (tmp_path / "events.jsonl").read_text().splitlines())


def test_typing_text_is_not_case_normalized(tmp_path, monkeypatch):
    instance, sent = driver(tmp_path, monkeypatch)
    instance.type({"type": "type", "text": "Tab Ctrl InvoiceAbc"})
    assert sent == [{"type": "type", "text": "Tab Ctrl InvoiceAbc"}]


def test_transport_error_keeps_both_request_and_normalized_input(tmp_path, monkeypatch):
    instance = DesktopDriver(tmp_path)

    def fail(action):
        raise RuntimeError("Guest input failed")

    monkeypatch.setattr(instance, "_send", fail)
    with pytest.raises(RuntimeError):
        instance.keypress({"type": "keypress", "keys": ["Tab"]})
    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert [event["type"] for event in events] == ["action", "action_transport", "driver_error"]
    assert events[0]["action"]["keys"] == ["Tab"]
    assert events[1]["action"]["keys"] == ["TAB"]
