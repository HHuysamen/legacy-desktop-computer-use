import pytest

from ledgerdesk.guest_control import validate_action

BOUNDS = (35, 60, 1100, 760)


@pytest.mark.parametrize("action", [
    {"type": "click", "x": 0, "y": 0},
    {"type": "click", "x": 100, "y": 200, "button": "right"},
    {"type": "click", "x": 100, "y": 200, "keys": ["CTRL"]},
    {"type": "click", "x": True, "y": 200},
    {"type": "keypress", "keys": ["ALT", "F4"]},
    {"type": "keypress", "keys": ["CTRL", "ESC"]},
    {"type": "type", "text": "2026\nrm -rf /"},
    {"type": "type", "text": "x" * 101},
    {"type": "scroll", "x": 100, "y": 200, "scroll_y": 1501},
    {"type": "drag", "path": []},
])
def test_unsafe_actions_refused(action):
    with pytest.raises(ValueError):
        validate_action(action, BOUNDS)


@pytest.mark.parametrize("action", [
    {"type": "click", "x": 35, "y": 60, "button": "left"},
    {"type": "keypress", "keys": ["CTRL", "A"]},
    {"type": "keypress", "keys": ["SHIFT", "TAB"]},
    {"type": "type", "text": "2026-10-15"},
    {"type": "screenshot"},
])
def test_task_actions_allowed(action):
    validate_action(action, BOUNDS)


def test_office_shortcuts_are_scoped_to_office(monkeypatch):
    monkeypatch.delenv("LEDGERDESK_TASK", raising=False)
    with pytest.raises(ValueError):
        validate_action({"type": "keypress", "keys": ["CTRL", "SHIFT", "S"]}, BOUNDS)
    monkeypatch.setenv("LEDGERDESK_TASK", "writer-find-replace")
    validate_action({"type": "keypress", "keys": ["CTRL", "SHIFT", "S"]}, BOUNDS)
    validate_action({"type": "keypress", "keys": ["CTRL", "H"]}, BOUNDS)
    with pytest.raises(ValueError):
        validate_action({"type": "keypress", "keys": ["CTRL", "ESC"]}, BOUNDS)
