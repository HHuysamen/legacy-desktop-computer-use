"""Trusted startup for one isolated application; never exposed to the model."""
import os
import json
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
    study = json.loads(os.environ.get("LEDGERDESK_STUDY_SPEC") or "null")
    real_app = task.startswith("gnucash-")
    if real_app:
        from .gnucash_tasks import prepare_gnucash
        command = prepare_gnucash(task, index=(study or {}).get("fixture_index", 0))
    elif office and study:
        from .robustness_fixtures import prepare_variant
        command = prepare_variant(task, study["split"], study["fixture_index"])
    else:
        command = prepare_office(task) if office else [
        "python", "-m", "ledgerdesk.desktop_app", "--db", "/tmp/ledgerdesk/ledgerdesk.db",
        "--export-dir", "/tmp/ledgerdesk/exports",
        ]
    if study and study.get("control") == "missing-source":
        Path(command[-1]).unlink()
    if (office or real_app) and not Path(command[-1]).is_file():
        if study and study.get("control") == "missing-source":
            Path("/tmp/ledgerdesk/setup-blocked.json").write_text(json.dumps({"reason": "missing_source", "source": command[-1], "exists": False}))
            # Keep the refused startup available for evidence collection.
            while True:
                time.sleep(1)
        raise RuntimeError("Required source document is missing")
    process = subprocess.Popen(command)
    for _ in range(300):
        windows = subprocess.run(["wmctrl", "-lp"], capture_output=True, text=True)
        if windows.returncode:
            time.sleep(0.1)
            continue
        rows = windows.stdout.splitlines()
        title = "GnuCash" if real_app else (f"LibreOffice {OFFICE_TASKS[task]['application'].title()}" if office else "LedgerDesk")
        candidates = [r.split(None, 4) for r in rows if title in r]
        if real_app:
            candidates = [row for row in candidates if Path(command[-1]).name in row[-1]]
        if candidates:
            row = candidates[0]
            window = row[0]
            pid = int(row[2]) if office or real_app else process.pid
            if pid <= 1 or ((office or real_app) and not owned_process(pid, process.pid)):
                time.sleep(0.1)
                continue
            if not office and not real_app:
                subprocess.run(["xprop", "-id", window, "-f", "_NET_WM_PID", "32c", "-set", "_NET_WM_PID", str(pid)], check=True)
            Path("/tmp/ledgerdesk/app.pid").write_text(str(pid))
            if office or real_app:
                if study and study.get("geometry") == "changed":
                    subprocess.run(["wmctrl", "-ir", window, "-b", "remove,maximized_vert,maximized_horz"], check=True)
                    subprocess.run(["wmctrl", "-ir", window, "-e", "0,120,80,920,660"], check=True)
                else:
                    subprocess.run(["wmctrl", "-ir", window, "-b", "add,maximized_vert,maximized_horz"], check=True)
            subprocess.run(["xdotool", "windowactivate", "--sync", window], check=True)
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("Target application did not open")
    process.wait()


if __name__ == "__main__":
    main()
