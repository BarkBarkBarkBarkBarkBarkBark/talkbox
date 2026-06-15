#!/usr/bin/env bash
# kiosk-setup.sh — Configure the Pi as a captive kiosk display
# Launches Chromium fullscreen on :8084/kiosk after Docker stack is healthy.
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

KIOSK_URL="${KIOSK_URL:-http://localhost:8084/kiosk}"
KIOSK_USER="${SUDO_USER:-${USER}}"

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
info "Configuring auto-login for $KIOSK_USER on tty1..."
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d
sudo tee /etc/systemd/system/getty@tty1.service.d/autologin.conf >/dev/null <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin ${KIOSK_USER} --noclear %I \$TERM
EOF
sudo systemctl daemon-reload

# ── 3. .xinitrc — minimal X session: openbox + chromium kiosk ───────────────
info "Writing ~/.xinitrc..."
cat > "/home/${KIOSK_USER}/.xinitrc" <<EOF
#!/bin/sh
KIOSK_URL="${KIOSK_URL}"
MAINTENANCE_FLAG="/tmp/talkbox-kiosk-maintenance.flag"

# Disable screen blanking and power saving
xset s off
xset s noblank
xset -dpms

# Hide the mouse cursor after 0.5s of inactivity
unclutter -idle 0.5 -root &

# Minimal window manager (no decorations, no taskbar)
openbox &

# Wait for Docker backend to be healthy before opening browser
echo "Waiting for backend..."
until curl -fsS http://localhost:8085/api/health >/dev/null 2>&1; do
    sleep 3
done

# Relaunch Chromium unless maintenance mode is active. This avoids blank
# screens if the browser exits unexpectedly.
while true; do
  if [ -f "$MAINTENANCE_FLAG" ]; then
    sleep 1
    continue
  fi

  chromium-browser \
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
    "$KIOSK_URL"

  sleep 1
done
EOF
chmod +x "/home/${KIOSK_USER}/.xinitrc"

# ── 4. Auto-start X on login to tty1 ────────────────────────────────────────
info "Configuring .bash_profile to startx on tty1..."
BASH_PROFILE="/home/${KIOSK_USER}/.bash_profile"

touch "$BASH_PROFILE"

# Remove legacy block from older kiosk installers.
sed -i '/^# Auto-start X kiosk on tty1$/,/^fi$/d' "$BASH_PROFILE" || true

# Remove previously managed block so re-runs always refresh behavior.
sed -i '/^# >>> TALKBOX_KIOSK_AUTOSTART >>>$/,/^# <<< TALKBOX_KIOSK_AUTOSTART <<<$/d' "$BASH_PROFILE" || true

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

# Close kiosk session and return to Linux console.
pkill -TERM -f "chromium-browser.*--kiosk" >/dev/null 2>&1 || true
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

# ── 7. USB audio — route default ALSA device + persist volume ───────────────
info "Configuring USB audio (P10S)..."

# Pin the USB audio device as the ALSA default for both playback and capture.
# Without this, ALSA may fall back to the HDMI audio devices.
cat > "/home/${KIOSK_USER}/.asoundrc" <<'EOF'
# Route all ALSA default audio to the USB P10S (card 0).
pcm.!default {
    type plug
    slave.pcm "hw:0,0"
}

ctl.!default {
    type hw
    card 0
}
EOF

# Set USB PCM playback volume to 100% immediately (idempotent).
amixer -c 0 set 'PCM' 100% unmute 2>/dev/null || true

# Restore 100% PCM volume at every desktop session start.
# ALSA does not persist mixer state automatically on this device, so we use
# an LXDE/openbox autostart entry that runs after the USB device initialises.
mkdir -p "/home/${KIOSK_USER}/.config/autostart"
cat > "/home/${KIOSK_USER}/.config/autostart/usb-audio-volume.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=USB Audio Volume
Exec=/bin/bash -c 'sleep 3 && amixer -c 0 set PCM 100% unmute'
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Comment=Restore USB P10S PCM playback volume to 100% on session start
EOF

# ── 8. Optional: splash screen while Docker starts ──────────────────────────
info "Writing loading page..."
sudo mkdir -p /var/www/loading
sudo tee /var/www/loading/index.html >/dev/null <<'EOF'
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Starting...</title>
<style>
  body { background:#111; color:#eee; font-family:sans-serif;
         display:flex; flex-direction:column; align-items:center;
         justify-content:center; height:100vh; margin:0; }
  .spinner { width:60px; height:60px; border:6px solid #333;
             border-top-color:#4f9; border-radius:50%;
             animation:spin 1s linear infinite; margin-bottom:24px; }
  @keyframes spin { to { transform:rotate(360deg); } }
</style>
</head>
<body>
  <div class="spinner"></div>
  <p>Starting Talk Box Kiosk...</p>
  <script>
    // Poll until the backend is up, then redirect
    (function poll() {
      fetch('/api/health').then(r => { if(r.ok) location.href='/kiosk'; else setTimeout(poll,3000); })
                          .catch(() => setTimeout(poll,3000));
    })();
  </script>
</body>
</html>
EOF

# ── 8. Done ──────────────────────────────────────────────────────────────────
echo ""
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║  Kiosk display configured!                               ║"
echo "  ╠══════════════════════════════════════════════════════════╣"
echo "  ║  The Pi will now:                                        ║"
echo "  ║    1. Boot → auto-login as ${KIOSK_USER}                       ║"
echo "  ║    2. Start X + openbox (no desktop, no taskbar)         ║"
echo "  ║    3. Wait for Docker backend to be healthy              ║"
echo "  ║    4. Open Chromium fullscreen on ${KIOSK_URL}  ║"
echo "  ║    5. USB audio routed + PCM volume locked at 100%       ║"
echo "  ║    6. Ctrl+Alt+T or Ctrl+Alt+F4 opens tty shell          ║"
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
