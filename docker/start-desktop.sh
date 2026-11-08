#!/bin/sh
set -eu
mkdir -p /tmp/ledgerdesk/exports
touch /home/demo/.Xauthority
Xvfb :99 -screen 0 1200x900x24 -nolisten tcp -ac &
until xdpyinfo >/dev/null 2>&1; do sleep 0.1; done
openbox >/tmp/openbox.log 2>&1 &
x11vnc -display :99 -forever -shared -nopw -rfbport 5900 -quiet >/tmp/vnc.log 2>&1 &
python -m ledgerdesk.desktop_app --db /tmp/ledgerdesk/ledgerdesk.db --export-dir /tmp/ledgerdesk/exports &
app_pid=$!
echo "$app_pid" >/tmp/ledgerdesk/app.pid
# Tk on X11 does not set _NET_WM_PID. Bind the only fixture window to the
# trusted launch process once; subsequent actions only verify this identity.
attempt=0
while [ "$attempt" -lt 100 ]; do
    window_id=$(xdotool search --name '^LedgerDesk' 2>/dev/null | head -n 1 || true)
    if [ -n "$window_id" ]; then
        xprop -id "$window_id" -f _NET_WM_PID 32c -set _NET_WM_PID "$app_pid"
        xdotool windowactivate --sync "$window_id"
        break
    fi
    attempt=$((attempt + 1))
    sleep 0.1
done
wait "$app_pid"
