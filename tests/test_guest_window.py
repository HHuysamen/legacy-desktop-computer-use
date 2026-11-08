from types import SimpleNamespace

import pytest

from ledgerdesk import guest_control


WINDOW_ID = "0x03e00003"


def configure_window(monkeypatch, *, pid=4242, bounds=(35, 62, 1100, 760), active=None, duplicate=False):
    monkeypatch.setattr(guest_control, "Path", lambda _path: SimpleNamespace(read_text=lambda: "4242"))
    x, y, width, height = bounds
    line = f"{WINDOW_ID} 0 {pid} {x} {y} {width} {height} demo {guest_control.TITLE}"
    windows = line + ("\n" + line if duplicate else "")

    def command(*arguments):
        if arguments == ("wmctrl", "-lpG"):
            return windows
        assert arguments == ("xdotool", "getactivewindow")
        return str(int(WINDOW_ID, 16) if active is None else active)

    monkeypatch.setattr(guest_control, "command", command)


def test_owned_focused_window_within_display_is_accepted(monkeypatch):
    configure_window(monkeypatch)
    assert guest_control.window_bounds() == (35, 62, 1100, 760)


def test_same_title_from_other_process_is_rejected(monkeypatch):
    configure_window(monkeypatch, pid=7777)
    with pytest.raises(RuntimeError, match="missing or ambiguous"):
        guest_control.window_bounds()


def test_ambiguous_owned_window_is_rejected(monkeypatch):
    configure_window(monkeypatch, duplicate=True)
    with pytest.raises(RuntimeError, match="missing or ambiguous"):
        guest_control.window_bounds()


def test_focus_loss_is_rejected(monkeypatch):
    configure_window(monkeypatch, active=1234)
    with pytest.raises(RuntimeError, match="lost focus"):
        guest_control.window_bounds()


@pytest.mark.parametrize("bounds", [
    (-1, 62, 1100, 760),
    (35, -1, 1100, 760),
    (101, 62, 1100, 760),
    (35, 141, 1100, 760),
    (35, 62, 0, 760),
    (35, 62, 1100, -1),
])
def test_offscreen_or_empty_client_area_is_rejected(monkeypatch, bounds):
    configure_window(monkeypatch, bounds=bounds)
    with pytest.raises(RuntimeError, match="outside the captured display"):
        guest_control.window_bounds()
