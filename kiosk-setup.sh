#!/usr/bin/env bash
# kiosk-setup.sh — Configure the Pi as a captive kiosk display
# Launches Chromium fullscreen on the TalkBox kiosk entrypoint after Docker stack is healthy.
#
# Run once on the Pi:
#   bash ~/talkbox/kiosk-setup.sh
#
# Assumptions:
#   - Raspberry Pi OS (Bookworm) with desktop or lite + X11/Wayland
#   - Docker stack already installed via install.sh
#   - A display is connected (HDMI)

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info() { echo -e "${GREEN}[kiosk]${NC} $*"; }
warn() { echo -e "${YELLOW}[kiosk]${NC} $*"; }

KIOSK_URL="${KIOSK_URL:-http://localhost:8084/}"
KIOSK_USER="${SUDO_USER:-${USER}}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

info "Setting up Talk Box kiosk display for user: $KIOSK_USER"

# ── 1. Install display dependencies ─────────────────────────────────────────
info "Installing display packages..."
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    chromium-browser \
    xserver-xorg \
    xinit \
    openbox \
    x11-xserver-utils \
    unclutter \
    network-manager \
    2>/dev/null || true

# ── 2. Auto-login on tty1 (text console → startx) ───────────────────────────
# Only when no display manager owns the screen (Pi OS Lite). On full desktop
# images (lightdm) the session autostart entry from §2b launches the kiosk —
# configuring BOTH would race two X servers for the display.
DISPLAY_MANAGER=""
for dm in lightdm gdm3 sddm; do
    if systemctl is-enabled "$dm" >/dev/null 2>&1; then DISPLAY_MANAGER="$dm"; break; fi
done

if [ -z "$DISPLAY_MANAGER" ]; then
    info "Configuring auto-login for $KIOSK_USER on tty1..."
    sudo mkdir -p /etc/systemd/system/getty@tty1.service.d
    sudo tee /etc/systemd/system/getty@tty1.service.d/autologin.conf >/dev/null <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin ${KIOSK_USER} --noclear %I \$TERM
EOF
    sudo systemctl daemon-reload
else
    warn "Display manager '$DISPLAY_MANAGER' detected — kiosk will launch via the"
    warn "desktop session autostart entry; skipping tty1 autologin/startx setup."
    warn "Ensure auto-login is enabled: raspi-config → System → Boot / Auto Login."
    sudo rm -f /etc/systemd/system/getty@tty1.service.d/autologin.conf
fi

# ── 2b. Shared kiosk browser launcher ───────────────────────────────────────
# Single source of truth for launching the kiosk browser. Used by BOTH boot
# paths: console autologin → startx → .xinitrc (Pi OS Lite) AND a desktop
# session's XDG autostart (lightdm / LXDE on full Pi OS images). Whichever
# path owns the display gets the same flags, health wait and restart loop.
info "Installing talkbox-kiosk-browser launcher..."
sudo tee /usr/local/bin/talkbox-kiosk-browser >/dev/null <<EOF
#!/bin/sh
# talkbox-kiosk-browser — launch (and keep relaunching) the kiosk browser.
KIOSK_URL="\${KIOSK_URL:-${KIOSK_URL}}"
REPO_DIR="\${TALKBOX_REPO_DIR:-${REPO_DIR}}"
MAINTENANCE_FLAG="/tmp/talkbox-kiosk-maintenance.flag"

# Only one launcher loop may run per boot (autostart + manual refresh races).
exec 9>/tmp/talkbox-kiosk-browser.lock
flock -n 9 || exit 0

BROWSER="\$(command -v chromium-browser || command -v chromium)"
[ -n "\$BROWSER" ] || { echo "no chromium binary found" >&2; exit 1; }

# Deterministic audio: pin TONOR mic + P10S speaker by name before the
# browser opens any audio streams (sudoers grants this single script).
sudo -n /usr/local/bin/talkbox-audio-init \
    || echo "talkbox-audio-init failed — keeping previous audio config"

# Wait for the Docker backend, self-healing the stack if it never comes up.
echo "Waiting for backend..."
waited=0
until curl -fsS http://localhost:8085/api/health >/dev/null 2>&1; do
    sleep 3
    waited=\$((waited + 3))
    if [ "\$waited" -ge 180 ]; then
        echo "Backend still down after \${waited}s — running docker compose up -d"
        (cd "\$REPO_DIR" && docker compose up -d) || true
        waited=0
    fi
done

# Relaunch the browser unless maintenance mode is active — a crashed browser
# must never leave a dead public phone.
while true; do
    if [ -f "\$MAINTENANCE_FLAG" ]; then
        sleep 1
        continue
    fi

    "\$BROWSER" \
        --kiosk \
        --noerrdialogs \
        --disable-infobars \
        --disable-session-crashed-bubble \
        --disable-restore-session-state \
        --no-first-run \
        --disable-translate \
        --disable-features=TranslateUI \
        --check-for-update-interval=31536000 \
        --disable-pinch \
        --overscroll-history-navigation=0 \
        --autoplay-policy=no-user-gesture-required \
        "\$KIOSK_URL"

    sleep 1
done
EOF
sudo chmod +x /usr/local/bin/talkbox-kiosk-browser

# Desktop-session boot path: point the XDG autostart entry at the launcher.
mkdir -p "/home/${KIOSK_USER}/.config/autostart"
cat > "/home/${KIOSK_USER}/.config/autostart/kiosk.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Talk Box Kiosk
Comment=Launch the Talk Box kiosk browser (with restart loop + audio pinning)
Exec=/usr/local/bin/talkbox-kiosk-browser
X-GNOME-Autostart-enabled=true
EOF

# ── 3. .xinitrc — minimal X session: openbox + chromium kiosk ───────────────
info "Writing ~/.xinitrc..."
cat > "/home/${KIOSK_USER}/.xinitrc" <<EOF
#!/bin/sh
# Disable screen blanking and power saving (the kiosk dims itself in software
# after 30 minutes idle — see useScreenDim in the frontend).
xset s off
xset s noblank
xset -dpms

# Hide the mouse cursor after 0.5s of inactivity
unclutter -idle 0.5 -root &

# Minimal window manager (no decorations, no taskbar)
openbox &

# Shared launcher: audio pinning, backend health wait (self-healing), and the
# browser restart loop all live in one place for both boot paths.
exec /usr/local/bin/talkbox-kiosk-browser
EOF
chmod +x "/home/${KIOSK_USER}/.xinitrc"

# ── 4. Auto-start X on login to tty1 ────────────────────────────────────────
BASH_PROFILE="/home/${KIOSK_USER}/.bash_profile"

touch "$BASH_PROFILE"

# Remove legacy block from older kiosk installers.
sed -i '/^# Auto-start X kiosk on tty1$/,/^fi$/d' "$BASH_PROFILE" || true

# Remove previously managed block so re-runs always refresh behavior.
sed -i '/^# >>> TALKBOX_KIOSK_AUTOSTART >>>$/,/^# <<< TALKBOX_KIOSK_AUTOSTART <<<$/d' "$BASH_PROFILE" || true

if [ -z "$DISPLAY_MANAGER" ]; then
info "Configuring .bash_profile to startx on tty1..."
cat >> "$BASH_PROFILE" <<'EOF'

# >>> TALKBOX_KIOSK_AUTOSTART >>>

# Auto-start X kiosk on tty1
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
    # Escape hatch flag drops into a plain tty shell instead of relaunching X.
    if [ -f "/tmp/talkbox-kiosk-tty.flag" ]; then
        rm -f /tmp/talkbox-kiosk-tty.flag
      rm -f /tmp/talkbox-kiosk-maintenance.flag
        printf "\nTalk Box maintenance shell on tty1. Type 'exit' to relaunch kiosk.\n\n"
        exec /bin/bash
    fi
    exec startx -- -nocursor 2>/dev/null
fi
# <<< TALKBOX_KIOSK_AUTOSTART <<<
EOF
fi  # end of no-display-manager (tty1/startx) boot path

# ── 5. Plain TTY escape hatch script ────────────────────────────────────────
info "Installing kiosk TTY escape hatch..."
sudo tee /usr/local/bin/talkbox-kiosk-tty >/dev/null <<'EOF'
#!/bin/sh
set -eu

MAINTENANCE_FLAG="/tmp/talkbox-kiosk-maintenance.flag"
TTY_FLAG="/tmp/talkbox-kiosk-tty.flag"

# Pause Chromium relaunch and request tty shell on next autologin.
touch "$MAINTENANCE_FLAG"
touch "$TTY_FLAG"

# Close kiosk session and return to Linux console. (The launcher loop stays
# paused via the maintenance flag; match both chromium and chromium-browser.)
pkill -TERM -f "chromium.*--kiosk" >/dev/null 2>&1 || true
pkill -TERM -f "/home/.*/.xinitrc" >/dev/null 2>&1 || true
pkill -TERM -f "^openbox$" >/dev/null 2>&1 || true
pkill -TERM -f "Xorg|X$" >/dev/null 2>&1 || true

exit 0
EOF
sudo chmod +x /usr/local/bin/talkbox-kiosk-tty

# ── 6. Openbox config: lock down desktop + add maintenance hotkey ──────────
info "Locking down openbox..."
OPENBOX_DIR="/home/${KIOSK_USER}/.config/openbox"
mkdir -p "$OPENBOX_DIR"
cat > "$OPENBOX_DIR/rc.xml" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
  <keyboard>
    <!-- Dedicated plain tty escape hatch -->
    <keybind key="C-A-t">
      <action name="Execute">
        <command>/usr/local/bin/talkbox-kiosk-tty</command>
      </action>
    </keybind>
    <keybind key="C-A-F4">
      <action name="Execute">
        <command>/usr/local/bin/talkbox-kiosk-tty</command>
      </action>
    </keybind>
  </keyboard>
  <mouse>
    <context name="Desktop">
      <!-- Remove right-click menu -->
    </context>
  </mouse>
  <applications>
    <application class="*">
      <decor>no</decor>
      <maximized>true</maximized>
    </application>
  </applications>
</openbox_config>
EOF

sudo chown -R "${KIOSK_USER}:${KIOSK_USER}" "/home/${KIOSK_USER}/.config"

# ── 7. Deterministic USB audio — TONOR mic in, P10S speaker out ─────────────
info "Installing talkbox-audio-init (mic=TONOR, speaker=P10S, pinned by NAME)..."

# USB enumeration order is not stable across boots, so pinning "card 0" is a
# coin flip once two USB audio devices are attached. talkbox-audio-init
# interrogates the connected cards at every boot / hot-plug and writes
# /etc/asound.conf routed by card NAME instead.
sudo tee /usr/local/bin/talkbox-audio-init >/dev/null <<'EOF'
#!/usr/bin/env bash
# talkbox-audio-init — make the kiosk's audio deterministic at every boot.
#
# Interrogates the connected ALSA sound cards and pins:
#   capture  → the TONOR USB microphone        (TALKBOX_MIC_MATCH)
#   playback → the MV-SILICON P10S speakerphone (TALKBOX_SPEAKER_MATCH)
# by card NAME (never card index — USB enumeration order is not stable).
#
# Fallback order if expected hardware is missing:
#   mic:     TONOR → P10S built-in mic (onboard AEC) → any capture device
#   speaker: P10S  → any USB playback device (never HDMI: no speakers there)
#
# Writes /etc/asound.conf, normalises mixer levels, and records the outcome
# in /run/talkbox-audio.state for `talkbox audio` / `talkbox doctor`.
# Exit codes: 0 = ok (possibly degraded), 1 = no usable speaker found.
set -u

MIC_MATCH="${TALKBOX_MIC_MATCH:-TONOR}"
SPEAKER_MATCH="${TALKBOX_SPEAKER_MATCH:-P10S|MV-SILICON}"
CONF="/etc/asound.conf"
STATE="/run/talkbox-audio.state"
LOG="/var/log/talkbox-audio.log"

log() { printf '%s %s\n' "$(date '+%F %T')" "$*" >>"$LOG"; }

# Keep the log from growing forever.
if [ -f "$LOG" ] && [ "$(wc -l <"$LOG")" -gt 1000 ]; then
    tail -n 500 "$LOG" >"$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi

# A per-user ~/.asoundrc OVERRIDES /etc/asound.conf — remove the legacy
# index-pinned file written by older installers wherever it survives,
# otherwise all of this is silently ignored.
for rc in /home/*/.asoundrc /root/.asoundrc; do
    if [ -f "$rc" ] && grep -q 'Route all ALSA default audio' "$rc" 2>/dev/null; then
        rm -f "$rc"
        log "removed legacy index-pinned $rc"
    fi
done

# find_card <regex> <aplay|arecord> — print the ALSA card ID (name) of the
# first card matching regex that supports the tool's direction. The regex is
# tested against the full device line (card id, card name, device name) so
# both "TONOR" and generic "USB" style matches work.
find_card() {
    "$2" -l 2>/dev/null \
        | grep '^card ' \
        | grep -iE "$1" \
        | head -n 1 \
        | sed 's/^card [0-9][0-9]*: \([^ ,]*\).*/\1/'
}

MIC="$(find_card "$MIC_MATCH" arecord)"
SPEAKER="$(find_card "$SPEAKER_MATCH" aplay)"
DEGRADED="no"

if [ -z "$MIC" ]; then
    # The P10S is a conference speakerphone — its built-in mic (with onboard
    # echo cancellation) is the designed fallback when the TONOR is missing.
    MIC="$(find_card "$SPEAKER_MATCH" arecord)"
    [ -n "$MIC" ] && DEGRADED="mic-fallback-speakerphone"
fi
if [ -z "$MIC" ]; then
    MIC="$(find_card '.' arecord)"   # last resort: any capture device
    [ -n "$MIC" ] && DEGRADED="mic-fallback-any"
fi
if [ -z "$SPEAKER" ]; then
    SPEAKER="$(find_card 'USB' aplay)"
    [ -n "$SPEAKER" ] && DEGRADED="speaker-fallback-usb"
fi

if [ -z "$SPEAKER" ]; then
    log "ERROR: no usable playback device (looked for: $SPEAKER_MATCH, then USB)"
    printf 'MIC=%s\nSPEAKER=\nDEGRADED=no-speaker\nCHANGED=no\n' "${MIC:-}" >"$STATE" 2>/dev/null || true
    exit 1
fi
if [ -z "$MIC" ]; then
    log "WARNING: no capture device at all — calls will be one-way"
    DEGRADED="no-mic"
fi

# dmix/dsnoop let key tones, TTS and the Twilio call share the devices.
TMP="$(mktemp)"
{
    echo "# Managed by talkbox-audio-init — do not edit (regenerated at boot/hot-plug)."
    echo "# mic=${MIC:-none} speaker=${SPEAKER} degraded=${DEGRADED}"
    echo "pcm.!default {"
    echo "    type asym"
    echo "    playback.pcm \"talkbox_out\""
    [ -n "$MIC" ] && echo "    capture.pcm \"talkbox_in\""
    echo "}"
    echo "pcm.talkbox_out {"
    echo "    type plug"
    echo "    slave.pcm \"dmix:CARD=${SPEAKER},DEV=0\""
    echo "}"
    if [ -n "$MIC" ]; then
        echo "pcm.talkbox_in {"
        echo "    type plug"
        echo "    slave.pcm \"dsnoop:CARD=${MIC},DEV=0\""
        echo "}"
    fi
    echo "ctl.!default {"
    echo "    type hw"
    echo "    card ${SPEAKER}"
    echo "}"
} >"$TMP"

CHANGED="no"
if ! cmp -s "$TMP" "$CONF" 2>/dev/null; then
    CHANGED="yes"
    cat "$TMP" >"$CONF"
fi
rm -f "$TMP"

# Normalise mixer levels — ALSA does not persist them on these devices.
set_levels() {  # set_levels <card> <percent> <extra amixer args...>
    local card="$1" pct="$2" ctl
    shift 2
    amixer -c "$card" scontrols 2>/dev/null \
        | sed -n "s/^Simple mixer control '\(.*\)',[0-9]*$/\1/p" \
        | while IFS= read -r ctl; do
            amixer -c "$card" sset "$ctl" "$pct" "$@" >/dev/null 2>&1 || true
        done
}
set_levels "$SPEAKER" "100%" unmute
[ -n "$MIC" ] && set_levels "$MIC" "85%" cap

printf 'MIC=%s\nSPEAKER=%s\nDEGRADED=%s\nCHANGED=%s\n' \
    "${MIC:-}" "$SPEAKER" "$DEGRADED" "$CHANGED" >"$STATE" 2>/dev/null || true
log "mic=${MIC:-none} speaker=${SPEAKER} degraded=${DEGRADED} changed=${CHANGED}"

# If routing changed while the kiosk browser is running, its ALSA handles
# point at stale devices — restart it (the .xinitrc loop relaunches it).
if [ "$CHANGED" = "yes" ] && pgrep -f "chromium.*--kiosk" >/dev/null 2>&1; then
    log "audio routing changed while kiosk running — restarting browser"
    pkill -f "chromium.*--kiosk" 2>/dev/null || true
fi

exit 0
EOF
sudo chmod +x /usr/local/bin/talkbox-audio-init

# The kiosk session runs audio-init before launching the browser; allow that
# single script (and nothing else) without a password.
sudo tee /etc/sudoers.d/talkbox-audio >/dev/null <<EOF
${KIOSK_USER} ALL=(root) NOPASSWD: /usr/local/bin/talkbox-audio-init
EOF
sudo chmod 0440 /etc/sudoers.d/talkbox-audio
sudo visudo -c -f /etc/sudoers.d/talkbox-audio >/dev/null

# Re-pin audio on hot-plug: udev fires the oneshot unit whenever a sound card
# appears (mic or speaker replugged, hub reset), so a swapped USB port heals
# itself without a reboot.
sudo tee /etc/systemd/system/talkbox-audio-init.service >/dev/null <<'EOF'
[Unit]
Description=Talk Box — pin kiosk mic/speaker as ALSA defaults (by card name)

[Service]
Type=oneshot
# Give the USB device a moment to finish enumerating its PCM interfaces.
ExecStartPre=/bin/sleep 2
ExecStart=/usr/local/bin/talkbox-audio-init

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/udev/rules.d/99-talkbox-audio.rules >/dev/null <<'EOF'
# Re-run talkbox-audio-init whenever a sound card is added (USB hot-plug).
ACTION=="add", SUBSYSTEM=="sound", KERNEL=="card[0-9]*", TAG+="systemd", ENV{SYSTEMD_WANTS}+="talkbox-audio-init.service"
EOF
sudo udevadm control --reload-rules

# Run once now so the config is correct before the first reboot.
sudo /usr/local/bin/talkbox-audio-init || warn "audio-init: expected devices not found (will retry at boot/hot-plug)"

# Remove legacy artifacts from older installers: the index-pinned ~/.asoundrc
# and the XDG autostart volume hack (which never ran — bare openbox does not
# process XDG autostart entries).
rm -f "/home/${KIOSK_USER}/.asoundrc"
rm -f "/home/${KIOSK_USER}/.config/autostart/usb-audio-volume.desktop"
sudo rm -rf /var/www/loading

# ── 8. Chromium managed policy — permanent mic grant for the kiosk origin ───
info "Granting microphone permission to ${KIOSK_URL%/kiosk} via Chromium policy..."
# Policy (not --use-fake-ui-for-media-stream): scoped to our origin only, and
# it also unlocks device labels for enumerateDevices() so the frontend can
# verify the TONOR/P10S are actually present.
for POLICY_DIR in /etc/chromium/policies/managed /etc/chromium-browser/policies/managed; do
    sudo mkdir -p "$POLICY_DIR"
    sudo tee "$POLICY_DIR/talkbox.json" >/dev/null <<'EOF'
{
    "AudioCaptureAllowed": true,
    "AudioCaptureAllowedUrls": ["http://localhost:8084", "http://localhost:8084/*"]
}
EOF
done

# ── 9. Docker stack systemd unit — stack always starts at boot ──────────────
info "Installing talkbox-stack.service..."
sudo tee /etc/systemd/system/talkbox-stack.service >/dev/null <<EOF
[Unit]
Description=Talk Box docker stack (postgres + backend + frontend)
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${REPO_DIR}
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose stop
TimeoutStartSec=900

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable docker.service talkbox-stack.service talkbox-audio-init.service >/dev/null 2>&1 || true

# ── 10. Hardware watchdog — recover from kernel/system hangs ────────────────
info "Enabling hardware watchdog..."
BOOT_CONFIG="/boot/firmware/config.txt"
[ -f "$BOOT_CONFIG" ] || BOOT_CONFIG="/boot/config.txt"
if [ -f "$BOOT_CONFIG" ] && ! grep -q '^dtparam=watchdog=on' "$BOOT_CONFIG"; then
    echo 'dtparam=watchdog=on' | sudo tee -a "$BOOT_CONFIG" >/dev/null
fi
sudo mkdir -p /etc/systemd/system.conf.d
sudo tee /etc/systemd/system.conf.d/10-talkbox-watchdog.conf >/dev/null <<'EOF'
# If systemd stops petting the hardware watchdog for 15s (kernel hang, hard
# lockup), the Pi resets itself — an unattended kiosk must never need a human
# to pull the plug.
[Manager]
RuntimeWatchdogSec=15
EOF

# ── 11. Done ─────────────────────────────────────────────────────────────────
echo ""
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║  Kiosk display configured!                               ║"
echo "  ╠══════════════════════════════════════════════════════════╣"
echo "  ║  The Pi will now:                                        ║"
echo "  ║    1. Boot → auto-login as ${KIOSK_USER}                       ║"
echo "  ║    2. Start Docker stack via talkbox-stack.service       ║"
echo "  ║    3. Pin audio: TONOR mic in, P10S speaker out (by name)║"
echo "  ║    4. Start X + openbox, wait for backend (self-healing) ║"
echo "  ║    5. Open Chromium fullscreen on ${KIOSK_URL}  ║"
echo "  ║    6. Mic permission pre-granted via Chromium policy     ║"
echo "  ║    7. Hardware watchdog resets the Pi if it ever hangs   ║"
echo "  ╠══════════════════════════════════════════════════════════╣"
echo "  ║  Audio hot-plug: replugging the mic or speaker re-pins   ║"
echo "  ║  routing automatically (udev → talkbox-audio-init).      ║"
echo "  ║  Diagnostics:  talkbox audio   /  talkbox doctor         ║"
echo "  ╠══════════════════════════════════════════════════════════╣"
echo "  ║  Escape hatch in kiosk session:                          ║"
echo "  ║    Press Ctrl+Alt+T (or Ctrl+Alt+F4)                    ║"
echo "  ║    Run nmtui, then type exit to resume kiosk            ║"
echo "  ╠══════════════════════════════════════════════════════════╣"
echo "  ║  Emergency from SSH:                                     ║"
echo "  ║    /usr/local/bin/talkbox-kiosk-tty                     ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo ""
warn "Reboot now to activate: sudo reboot"
