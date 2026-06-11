#!/usr/bin/env bash
# ngrok-update.sh — starts ngrok, gets the public URL, updates Twilio TwiML App
# and rewrites TWILIO_PUBLIC_URL in .env so the backend picks it up on next start.
#
# Uses only curl + python3 — no Twilio CLI or npm required.
#
# Designed to run as a systemd service after docker.service and network-online.target.
# See install instructions at the bottom of this file.

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
ENV_FILE="${ENV_FILE:-/home/operator/talkbox/pointer-fork/.env}"
BACKEND_PORT="${BACKEND_PORT:-8085}"
TWIML_ROUTE="${TWIML_ROUTE:-/api/kiosk/call/twiml}"
COMPOSE_DIR="${COMPOSE_DIR:-/home/operator/talkbox/pointer-fork}"
LOG_FILE="/tmp/ngrok-update.log"
# ──────────────────────────────────────────────────────────────────────────────

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

# Read Twilio credentials + TwiML App SID from .env
_env_val() { grep -E "^$1=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'"; }

TWILIO_ACCOUNT_SID="${TWILIO_ACCOUNT_SID:-$(_env_val TWILIO_ACCOUNT_SID)}"
TWILIO_AUTH_TOKEN="${TWILIO_AUTH_TOKEN:-$(_env_val TWILIO_AUTH_TOKEN)}"
TWIML_APP_SID="${TWIML_APP_SID:-$(_env_val TWILIO_TWIML_APP_SID)}"

if [ -z "$TWILIO_ACCOUNT_SID" ] || [ -z "$TWILIO_AUTH_TOKEN" ]; then
    log "ERROR: TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN not set in $ENV_FILE"
    exit 1
fi
if [ -z "$TWIML_APP_SID" ]; then
    log "ERROR: TWILIO_TWIML_APP_SID not set in $ENV_FILE"
    exit 1
fi

# ── 1. Kill any existing ngrok ────────────────────────────────────────────────
log "Stopping any existing ngrok..."
pkill -f "ngrok http" 2>/dev/null || true
sleep 1

# ── 2. Start ngrok in background ──────────────────────────────────────────────
log "Starting ngrok on port $BACKEND_PORT..."
nohup ngrok http "$BACKEND_PORT" >> "$LOG_FILE" 2>&1 &
log "ngrok PID: $!"

# ── 3. Wait for ngrok API to be ready ─────────────────────────────────────────
NGROK_URL=""
for i in $(seq 1 15); do
    sleep 2
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['tunnels'][0]['public_url'])" 2>/dev/null || true)
    if [ -n "$NGROK_URL" ]; then
        log "ngrok URL: $NGROK_URL"
        break
    fi
    log "waiting for ngrok... ($i/15)"
done

if [ -z "$NGROK_URL" ]; then
    log "ERROR: ngrok did not start in time. Check $LOG_FILE"
    exit 1
fi

TWIML_WEBHOOK="${NGROK_URL}${TWIML_ROUTE}"
log "TwiML webhook URL: $TWIML_WEBHOOK"

# ── 4. Update Twilio TwiML App via REST API ───────────────────────────────────
log "Updating Twilio TwiML App $TWIML_APP_SID..."
HTTP_STATUS=$(curl -s -o /tmp/twilio_response.json -w "%{http_code}" \
    -X POST "https://api.twilio.com/2010-04-01/Accounts/${TWILIO_ACCOUNT_SID}/Applications/${TWIML_APP_SID}.json" \
    -u "${TWILIO_ACCOUNT_SID}:${TWILIO_AUTH_TOKEN}" \
    --data-urlencode "VoiceUrl=${TWIML_WEBHOOK}" \
    --data-urlencode "VoiceMethod=POST")

if [ "$HTTP_STATUS" = "200" ]; then
    log "Twilio TwiML App updated successfully (HTTP 200)."
else
    log "ERROR: Twilio API returned HTTP $HTTP_STATUS:"
    cat /tmp/twilio_response.json | tee -a "$LOG_FILE"
    exit 1
fi

# ── 5. Rewrite TWILIO_PUBLIC_URL in .env ──────────────────────────────────────
if [ -f "$ENV_FILE" ]; then
    if grep -q '^TWILIO_PUBLIC_URL=' "$ENV_FILE"; then
        sed -i "s|^TWILIO_PUBLIC_URL=.*|TWILIO_PUBLIC_URL=$NGROK_URL|" "$ENV_FILE"
    else
        echo "TWILIO_PUBLIC_URL=$NGROK_URL" >> "$ENV_FILE"
    fi
    log ".env updated: TWILIO_PUBLIC_URL=$NGROK_URL"
fi

# ── 6. Restart the backend container so it picks up the new URL ───────────────
log "Restarting backend container..."
docker compose -f "$COMPOSE_DIR/docker-compose.yml" restart pointer-backend 2>&1 | tee -a "$LOG_FILE"
log "Done. Talk Box is ready for calls."

# ════════════════════════════════════════════════════════════════════════════════
# INSTALL AS SYSTEMD SERVICE
# ════════════════════════════════════════════════════════════════════════════════
# 1. Pull the script and make it executable:
#    cd ~/talkbox && git pull
#    chmod +x ngrok-update.sh
#
# 2. Create the systemd service:
#    sudo tee /etc/systemd/system/ngrok-update.service > /dev/null << 'EOF'
#    [Unit]
#    Description=Start ngrok and update Twilio TwiML App URL
#    After=network-online.target docker.service
#    Wants=network-online.target
#
#    [Service]
#    Type=oneshot
#    User=operator
#    Environment="PATH=/usr/local/bin:/usr/bin:/bin"
#    ExecStart=/home/operator/talkbox/ngrok-update.sh
#    RemainAfterExit=yes
#    StandardOutput=journal
#    StandardError=journal
#
#    [Install]
#    WantedBy=multi-user.target
#    EOF
#
# 3. Enable and start:
#    sudo systemctl daemon-reload
#    sudo systemctl enable ngrok-update.service
#    sudo systemctl start ngrok-update.service
#
# 4. Check status:
#    sudo systemctl status ngrok-update.service
#    journalctl -u ngrok-update.service -f


set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
ENV_FILE="${ENV_FILE:-/home/operator/talkbox/pointer-fork/.env}"
BACKEND_PORT="${BACKEND_PORT:-8085}"
TWIML_APP_SID="${TWIML_APP_SID:-}"          # APxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWIML_ROUTE="${TWIML_ROUTE:-/api/kiosk/call/twiml}"
COMPOSE_DIR="${COMPOSE_DIR:-/home/operator/talkbox/pointer-fork}"
LOG_FILE="/tmp/ngrok-update.log"
# ──────────────────────────────────────────────────────────────────────────────

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

# Read TWIML_APP_SID from .env if not set in environment
if [ -z "$TWIML_APP_SID" ] && [ -f "$ENV_FILE" ]; then
    TWIML_APP_SID=$(grep -E '^TWILIO_TWIML_APP_SID=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'")
fi

if [ -z "$TWIML_APP_SID" ]; then
    log "ERROR: TWIML_APP_SID is not set. Add TWILIO_TWIML_APP_SID=AP... to $ENV_FILE"
    exit 1
fi

# ── 1. Kill any existing ngrok ────────────────────────────────────────────────
log "Stopping any existing ngrok..."
pkill -f "ngrok http" 2>/dev/null || true
sleep 1

# ── 2. Start ngrok in background ──────────────────────────────────────────────
log "Starting ngrok on port $BACKEND_PORT..."
nohup ngrok http "$BACKEND_PORT" >> "$LOG_FILE" 2>&1 &
NGROK_PID=$!
log "ngrok PID: $NGROK_PID"

# ── 3. Wait for ngrok API to be ready ─────────────────────────────────────────
NGROK_URL=""
for i in $(seq 1 15); do
    sleep 2
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['tunnels'][0]['public_url'])" 2>/dev/null || true)
    if [ -n "$NGROK_URL" ]; then
        log "ngrok URL: $NGROK_URL"
        break
    fi
    log "waiting for ngrok... ($i/15)"
done

if [ -z "$NGROK_URL" ]; then
    log "ERROR: ngrok did not start in time. Check $LOG_FILE"
    exit 1
fi

TWIML_WEBHOOK="${NGROK_URL}${TWIML_ROUTE}"
log "TwiML webhook URL: $TWIML_WEBHOOK"

# ── 4. Update Twilio TwiML App via CLI ────────────────────────────────────────
log "Updating Twilio TwiML App $TWIML_APP_SID..."
twilio api:core:applications:update \
    --sid "$TWIML_APP_SID" \
    --voice-url "$TWIML_WEBHOOK" \
    --voice-method POST \
    2>&1 | tee -a "$LOG_FILE"
log "Twilio TwiML App updated."

# ── 5. Rewrite TWILIO_PUBLIC_URL in .env ──────────────────────────────────────
if [ -f "$ENV_FILE" ]; then
    if grep -q '^TWILIO_PUBLIC_URL=' "$ENV_FILE"; then
        sed -i "s|^TWILIO_PUBLIC_URL=.*|TWILIO_PUBLIC_URL=$NGROK_URL|" "$ENV_FILE"
    else
        echo "TWILIO_PUBLIC_URL=$NGROK_URL" >> "$ENV_FILE"
    fi
    log ".env updated: TWILIO_PUBLIC_URL=$NGROK_URL"
fi

# ── 6. Restart the backend container so it picks up the new URL ───────────────
log "Restarting backend container..."
docker compose -f "$COMPOSE_DIR/docker-compose.yml" restart pointer-backend 2>&1 | tee -a "$LOG_FILE"
log "Done. Talk Box is ready for calls."

# ════════════════════════════════════════════════════════════════════════════════
# INSTALL AS SYSTEMD SERVICE
# ════════════════════════════════════════════════════════════════════════════════
# 1. Copy this script to the Pi:
#    scp ngrok-update.sh operator@hosaka:~/talkbox/ngrok-update.sh
#    ssh operator@hosaka "chmod +x ~/talkbox/ngrok-update.sh"
#
# 2. Install Twilio CLI on the Pi (pick one):
#    sudo npm install -g twilio-cli          # if Node is installed
#    # OR: download binary directly:
#    curl -L https://github.com/twilio/twilio-cli/releases/latest/download/twilio-linux-arm64.tar.gz | tar -xz
#    sudo mv twilio /usr/local/bin/
#
# 3. Authenticate Twilio CLI (one-time, stores creds in ~/.twilio-cli/config.json):
#    twilio login
#    # Enter your Account SID (from Twilio Console dashboard)
#    # Enter your Auth Token  (from Twilio Console dashboard)
#    # Profile name:      talkbox
#
# 4. Create the systemd service:
#    sudo tee /etc/systemd/system/ngrok-update.service > /dev/null << 'EOF'
#    [Unit]
#    Description=Start ngrok and update Twilio TwiML App URL
#    After=network-online.target docker.service
#    Wants=network-online.target
#
#    [Service]
#    Type=oneshot
#    User=operator
#    ExecStart=/home/operator/talkbox/ngrok-update.sh
#    RemainAfterExit=yes
#    StandardOutput=journal
#    StandardError=journal
#
#    [Install]
#    WantedBy=multi-user.target
#    EOF
#
# 5. Enable and start:
#    sudo systemctl daemon-reload
#    sudo systemctl enable ngrok-update.service
#    sudo systemctl start ngrok-update.service
#
# 6. Check status:
#    sudo systemctl status ngrok-update.service
#    journalctl -u ngrok-update.service -f
