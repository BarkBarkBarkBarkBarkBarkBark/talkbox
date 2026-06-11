#!/usr/bin/env bash
# ngrok-update.sh — thin wrapper kept for the systemd boot service.
# All logic now lives in the `talkbox` CLI (see ./talkbox).
#
# Starts/reuses ngrok, publishes the public URL to the Twilio TwiML App via
# the REST API, rewrites TWILIO_PUBLIC_URL in .env, and restarts the backend
# if the URL changed.
#
# ════════════════════════════════════════════════════════════════════════════
# INSTALL AS SYSTEMD SERVICE (runs at boot, after docker + network)
# ════════════════════════════════════════════════════════════════════════════
#   sudo tee /etc/systemd/system/ngrok-update.service > /dev/null << 'EOF'
#   [Unit]
#   Description=Start ngrok and update Twilio TwiML App URL
#   After=network-online.target docker.service
#   Wants=network-online.target
#
#   [Service]
#   Type=oneshot
#   User=operator
#   Environment="PATH=/usr/local/bin:/usr/bin:/bin"
#   ExecStart=/home/operator/talkbox/ngrok-update.sh
#   RemainAfterExit=yes
#   StandardOutput=journal
#   StandardError=journal
#
#   [Install]
#   WantedBy=multi-user.target
#   EOF
#
#   sudo systemctl daemon-reload
#   sudo systemctl enable --now ngrok-update.service
#   journalctl -u ngrok-update.service -f

set -euo pipefail
exec "$(dirname "$(realpath "$0")")/talkbox" ngrok
