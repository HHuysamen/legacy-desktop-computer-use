"""Fixed screenshot/input transport inside the isolated guest; not an agent tool."""
from __future__ import annotations

import base64
from contextlib import redirect_stdout
import io
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time

TITLE = "LedgerDesk — Demo Finance"
WIDTH, HEIGHT = 1200, 900
KEYS = {
    "ENTER": "enter", "RETURN": "enter", "TAB": "tab", "ESC": "esc", "ESCAPE": "esc",
    "BACKSPACE": "backspace", "DELETE": "delete", "SPACE": "space",
    "UP": "up", "DOWN": "down", "LEFT": "left", "RIGHT": "right",
    "ARROWUP": "up", "ARROWDOWN": "down", "ARROWLEFT": "left", "ARROWRIGHT": "right",
    "HOME": "home", "END": "end", "PAGEUP": "pageup", "PAGEDOWN": "pagedown",
    "CTRL": "ctrl", "CONTROL": "ctrl", "SHIFT": "shift", "A": "a",
    "S": "s", "H": "h",
}


def is_office() -> bool:
    return os.environ.get("LEDGERDESK_TASK") in {"calc-sort-export", "writer-find-replace"}


def uses_process_windows() -> bool:
    return is_office() or os.environ.get("LEDGERDESK_TASK") in {"gnucash-expense", "gnucash-split", "gnucash-transfer"}


def command(*args: str) -> str:
    return subprocess.check_output(args, text=True, timeout=2).strip()


def window_bounds() -> tuple[int, int, int, int]:
    """Read window-manager metadata only; never inspect widgets or app data."""
    expected_pid = int(Path("/tmp/ledgerdesk/app.pid").read_text().strip())
    if expected_pid <= 1:
        raise RuntimeError("Invalid target process identity")
    windows = command("wmctrl", "-lpG").splitlines()
    matches = [line.split(None, 8) for line in windows if uses_process_windows() or line.endswith(TITLE)]
    matches = [parts for parts in matches if len(parts) == 9 and int(parts[2]) == expected_pid]
    active = int(command("xdotool", "getactivewindow"))
    if uses_process_windows():
        # Native application dialogs are allowed only within the same process.
        if not any(int(parts[0], 16) == active for parts in matches):
            raise RuntimeError("Target application lost focus")
        office_windows = matches[:]
        matches = [parts for parts in matches if int(parts[0], 16) == active]
    if len(matches) != 1:
        raise RuntimeError("LedgerDesk window missing or ambiguous")
    parts = matches[0]
    if active != int(parts[0], 16):
        raise RuntimeError("LedgerDesk lost focus")
    bounds = tuple(map(int, parts[3:7]))
    if uses_process_windows():
        # wmctrl can double-count decorations on maximized LibreOffice windows.
        # Read X11's absolute client geometry, not application content.
        labels = ("Absolute upper-left X", "Absolute upper-left Y", "Width", "Height")
        rectangles = []
        for window in office_windows:
            geometry = command("xwininfo", "-id", window[0])
            values = [re.search(rf"^\s*{label}:\s*(-?\d+)", geometry, re.MULTILINE) for label in labels]
            if any(value is None for value in values):
                raise RuntimeError("Target client geometry is unavailable")
            rectangles.append(tuple(int(value.group(1)) for value in values))
        # A combo-box popup can extend outside its dialog onto the owned main window.
        left = min(r[0] for r in rectangles)
        top = min(r[1] for r in rectangles)
        right = max(r[0] + r[2] for r in rectangles)
        bottom = max(r[1] + r[3] for r in rectangles)
        bounds = (left, top, right - left, bottom - top)
    x, y, width, height = bounds
    if width <= 0 or height <= 0 or x < 0 or y < 0 or x + width > WIDTH or y + height > HEIGHT:
        raise RuntimeError("LedgerDesk client area is outside the captured display")
    return bounds


def validate_action(action: dict, bounds: tuple[int, int, int, int]) -> None:
    kind = action.get("type")
    if kind not in {"click", "double_click", "move", "scroll", "type", "keypress", "wait", "screenshot"}:
        raise ValueError("Unsupported desktop action")
    if kind in {"click", "double_click", "move", "scroll"}:
        x, y = action.get("x"), action.get("y")
        bx, by, bw, bh = bounds
        if type(x) is not int or type(y) is not int or not (bx <= x < bx + bw and by <= y < by + bh):
            raise ValueError("Coordinates outside LedgerDesk client area")
    if kind in {"click", "double_click", "move", "scroll"} and action.get("keys"):
        raise ValueError("Pointer modifiers are disabled")
    if kind == "click" and action.get("button", "left") != "left":
        raise ValueError("Only left clicks are allowed")
    if kind == "scroll":
        for axis in ("scroll_x", "scroll_y"):
            value = action.get(axis, 0)
            if type(value) is not int or abs(value) > 1500:
                raise ValueError("Scroll distance exceeds limit")
    if kind == "type":
        value = action.get("text", "")
        if not isinstance(value, str) or len(value) > 100 or any(ord(c) < 32 or ord(c) > 126 for c in value):
            raise ValueError("Only short printable ASCII parameter values are allowed")
    if kind == "keypress":
        keys = action.get("keys", [])
        if not isinstance(keys, list) or not keys or len(keys) > 3 or any(k not in KEYS for k in keys):
            raise ValueError("Unsupported keys")
        combinations = [["CTRL", "A"], ["CONTROL", "A"], ["SHIFT", "TAB"]]
        if is_office():
            combinations += [[modifier, key] for modifier in ("CTRL", "CONTROL") for key in ("S", "H", "HOME", "END")]
            combinations += [[modifier, "SHIFT", "S"] for modifier in ("CTRL", "CONTROL")]
        elif uses_process_windows():
            combinations += [[modifier, "S"] for modifier in ("CTRL", "CONTROL")]
            combinations += [[modifier, "SHIFT", "S"] for modifier in ("CTRL", "CONTROL")]
        if len(keys) > 1 and keys not in combinations:
            raise ValueError("Unsupported key combination")
        if len(keys) == 1 and keys[0] in {"CTRL", "CONTROL", "SHIFT", "A", "S", "H"}:
            raise ValueError("Standalone modifier or letter is disabled")


def execute(action: dict) -> dict:
    import pyautogui
    import mss
    from PIL import Image
    bounds = window_bounds()
    validate_action(action, bounds)
    kind = action["type"]
    pyautogui.PAUSE = 0.08
    pyautogui.FAILSAFE = True
    if kind == "click":
        pyautogui.click(action["x"], action["y"])
    elif kind == "double_click":
        pyautogui.doubleClick(action["x"], action["y"], interval=0.12)
    elif kind == "move":
        pyautogui.moveTo(action["x"], action["y"])
    elif kind == "scroll":
        pyautogui.moveTo(action["x"], action["y"])
        pyautogui.scroll(-round(action.get("scroll_y", 0) / 100))
        pyautogui.hscroll(round(action.get("scroll_x", 0) / 100))
    elif kind == "type":
        pyautogui.write(action["text"], interval=0.025)
    elif kind == "keypress":
        pyautogui.hotkey(*(KEYS[k] for k in action["keys"]))
    elif kind == "wait":
        time.sleep(0.5)
    time.sleep(0.12)
    # A lost focus after input stops the next action and this observation.
    window_bounds()
    if kind == "screenshot":
        with mss.mss() as capture:
            shot = capture.grab({"left": 0, "top": 0, "width": WIDTH, "height": HEIGHT})
        image = Image.frombytes("RGB", shot.size, shot.rgb)
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        return {"png": base64.b64encode(stream.getvalue()).decode()}
    return {"ok": True}


def main() -> None:
    try:
        if sys.argv[1:] == ["check"]:
            window_bounds()
            print("ready")
            return
        action = json.loads(sys.stdin.read(16384))
        # Xlib can print startup warnings; stdout is reserved for transport JSON.
        with redirect_stdout(sys.stderr):
            result = execute(action)
        print(json.dumps(result))
    except Exception as error:
        print(json.dumps({"error": f"{type(error).__name__}: {error}"}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
