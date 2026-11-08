"""Host-side fixed transport; the model can submit only Computer actions."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def compose(*args: str, input_text: str | None = None, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-f", str(ROOT / "compose.yaml"), *args],
        cwd=ROOT, input=input_text, capture_output=True, text=True, timeout=timeout, check=True,
    )


def log_event(run_dir: Path, kind: str, **values) -> None:
    event = {"type": kind, "timestamp": datetime.now(timezone.utc).isoformat(), **values}
    with (run_dir / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event) + "\n")


class DesktopDriver:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.screenshot_count = 0

    def _send(self, action: dict) -> dict:
        try:
            result = compose("exec", "-T", "desktop", "python", "-m", "ledgerdesk.guest_control", input_text=json.dumps(action))
        except subprocess.CalledProcessError as error:
            # Only fixed guest code emits stdout; never relay Docker configuration.
            try:
                message = json.loads(error.stdout).get("error", "Desktop operation failed")
            except (ValueError, TypeError):
                message = "Desktop operation failed"
            raise RuntimeError(message) from None
        return json.loads(result.stdout)

    def _action(self, action) -> None:
        data = action.model_dump(exclude_none=True) if hasattr(action, "model_dump") else dict(action)
        log_event(self.run_dir, "action", action=data, phase="requested")
        self._send(data)
        log_event(self.run_dir, "action_result", action_type=data["type"], completed=True)

    click = _action
    double_click = _action
    move = _action
    scroll = _action
    type = _action
    keypress = _action
    wait = _action

    def drag(self, action) -> None:
        raise ValueError("Drag is not required by LedgerDesk and is disabled")

    def screenshot(self) -> dict:
        result = self._send({"type": "screenshot"})
        self.screenshot_count += 1
        relative = Path("screenshots") / f"{self.screenshot_count:03d}.png"
        destination = self.run_dir / relative
        destination.parent.mkdir(exist_ok=True)
        destination.write_bytes(base64.b64decode(result["png"], validate=True))
        log_event(self.run_dir, "screenshot", path=str(relative))
        return {"type": "computer_screenshot", "image_url": "data:image/png;base64," + result["png"]}
