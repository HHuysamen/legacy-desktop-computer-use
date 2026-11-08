"""Trusted startup for one isolated application; never exposed to the model."""
import os
from pathlib import Path
import subprocess
import time

from .office_tasks import OFFICE_TASKS, prepare_office


def owned_process(pid: int, ancestor: int) -> bool:
    for _ in range(30):
        if pid == ancestor:
            return True
        if pid <= 1:
            return False
        try:
            pid = int(Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            return False
    return False


def main():
    task = os.environ.get("LEDGERDESK_TASK", "monthly-revenue")
    office = task in OFFICE_TASKS
    command = prepare_office(task) if office else [
        "python", "-m", "ledgerdesk.desktop_app", "--db", "/tmp/ledgerdesk/ledgerdesk.db",
        "--export-dir", "/tmp/ledgerdesk/exports",
    ]
    process = subprocess.Popen(command)
    for _ in range(300):
        rows = subprocess.check_output(["wmctrl", "-lp"], text=True).splitlines()
        title = f"LibreOffice {OFFICE_TASKS[task]['application'].title()}" if office else "LedgerDesk"
        candidates = [r.split(None, 4) for r in rows if title in r]
        if candidates:
            row = candidates[0]
            window = row[0]
            pid = int(row[2]) if office else process.pid
            if pid <= 1 or (office and not owned_process(pid, process.pid)):
                time.sleep(0.1)
                continue
            if not office:
                subprocess.run(["xprop", "-id", window, "-f", "_NET_WM_PID", "32c", "-set", "_NET_WM_PID", str(pid)], check=True)
            Path("/tmp/ledgerdesk/app.pid").write_text(str(pid))
            if office:
                subprocess.run(["wmctrl", "-ir", window, "-b", "add,maximized_vert,maximized_horz"], check=True)
            subprocess.run(["xdotool", "windowactivate", "--sync", window], check=True)
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("Target application did not open")
    process.wait()


if __name__ == "__main__":
    main()
