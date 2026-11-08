#!/bin/sh
set -eu
mkdir -p /tmp/ledgerdesk/exports
touch /home/demo/.Xauthority
Xvfb :99 -screen 0 1200x900x24 -nolisten tcp -ac &
until xdpyinfo >/dev/null 2>&1; do sleep 0.1; done
openbox >/tmp/openbox.log 2>&1 &
x11vnc -display :99 -forever -shared -nopw -rfbport 5900 -quiet >/tmp/vnc.log 2>&1 &
exec python -m ledgerdesk.launch
