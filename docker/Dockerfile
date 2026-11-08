FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-tk tk xvfb xauth openbox x11vnc novnc websockify \
    xdotool wmctrl x11-utils fonts-dejavu-core ffmpeg procps libreoffice-calc libreoffice-writer gnucash \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir PyAutoGUI==0.9.54 Pillow==12.0.0 mss==10.1.0
RUN useradd --create-home --uid 1000 demo
WORKDIR /opt/ledgerdesk
COPY ledgerdesk/ ledgerdesk/
COPY fixtures/ fixtures/
COPY docker/start-desktop.sh docker/start-desktop.sh
ENV DISPLAY=:99 HOME=/home/demo PYTHONUNBUFFERED=1
USER demo
CMD ["/bin/sh", "/opt/ledgerdesk/docker/start-desktop.sh"]
