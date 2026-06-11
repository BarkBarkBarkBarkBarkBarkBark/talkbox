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

# Launch Chromium in kiosk mode
exec chromium-browser \
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
    "${KIOSK_URL}"
EOF
chmod +x "/home/${KIOSK_USER}/.xinitrc"

# ── 4. Auto-start X on login to tty1 ────────────────────────────────────────
info "Configuring .bash_profile to startx on tty1..."
BASH_PROFILE="/home/${KIOSK_USER}/.bash_profile"
# Only add if not already there
if ! grep -q "startx" "$BASH_PROFILE" 2>/dev/null; then
    cat >> "$BASH_PROFILE" <<'EOF'

# Auto-start X kiosk on tty1
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
    exec startx -- -nocursor 2>/dev/null
fi
EOF
fi

# ── 5. Openbox config: prevent Alt+F4 / right-click menu ────────────────────
info "Locking down openbox..."
OPENBOX_DIR="/home/${KIOSK_USER}/.config/openbox"
mkdir -p "$OPENBOX_DIR"
cat > "$OPENBOX_DIR/rc.xml" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
  <keyboard>
    <!-- Unbind all default keyboard shortcuts -->
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

# ── 6. Optional: splash screen while Docker starts ──────────────────────────
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

# ── 7. Done ──────────────────────────────────────────────────────────────────
echo ""
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║  Kiosk display configured!                               ║"
echo "  ╠══════════════════════════════════════════════════════════╣"
echo "  ║  The Pi will now:                                        ║"
echo "  ║    1. Boot → auto-login as ${KIOSK_USER}                       ║"
echo "  ║    2. Start X + openbox (no desktop, no taskbar)         ║"
echo "  ║    3. Wait for Docker backend to be healthy              ║"
echo "  ║    4. Open Chromium fullscreen on ${KIOSK_URL}  ║"
echo "  ╠══════════════════════════════════════════════════════════╣"
echo "  ║  To exit kiosk manually (SSH in and):                    ║"
echo "  ║    sudo pkill chromium                                   ║"
echo "  ║    sudo pkill xinit                                      ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo ""
warn "Reboot now to activate: sudo reboot"
