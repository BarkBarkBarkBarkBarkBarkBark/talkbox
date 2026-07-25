#!/usr/bin/env bash
# install.sh — Talk Box Kiosk, Raspberry Pi setup (arm64 / amd64)
# Usage (on the Pi):
#   curl -fsSL https://raw.githubusercontent.com/BarkBarkBarkBarkBarkBarkBark/talkbox/main/install.sh | bash
# Or after cloning:
#   bash install.sh

set -euo pipefail

REPO_URL="https://github.com/BarkBarkBarkBarkBarkBarkBark/talkbox.git"
INSTALL_DIR="$HOME/talkbox"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[talkbox]${NC} $*"; }
warn()  { echo -e "${YELLOW}[talkbox]${NC} $*"; }
error() { echo -e "${RED}[talkbox]${NC} $*" >&2; exit 1; }

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║   Talk Box Kiosk — Pi Install Script      ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

# ── 1. Dependencies ──────────────────────────────────────────────────────────
info "Checking dependencies..."

if ! command -v git &>/dev/null || ! command -v curl &>/dev/null; then
    warn "Installing git and curl..."
    sudo apt-get update -qq
    sudo apt-get install -y git curl ca-certificates
fi

if ! command -v docker &>/dev/null; then
    warn "Docker not found — installing via get.docker.com..."
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$USER"
    sudo systemctl enable docker
    sudo systemctl start docker
    warn "Docker installed. Running this session with sudo docker."
    warn "After install, log out and back in so your user can run docker without sudo."
    DOCKER="sudo docker"
else
    DOCKER="docker"
fi

# Docker Compose v2 (plugin)
if ! $DOCKER compose version &>/dev/null 2>&1; then
    warn "Installing docker-compose-plugin..."
    sudo apt-get install -y docker-compose-plugin
fi

info "Docker: $($DOCKER --version)"
info "Compose: $($DOCKER compose version)"

# ── 2. Clone / update repo ───────────────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
    info "Repo found at $INSTALL_DIR — pulling latest..."
    git -C "$INSTALL_DIR" pull --ff-only
else
    info "Cloning repo to $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# ── 3. Install local speech model ────────────────────────────────────────────
WHISPER_MODEL_NAME="ggml-tiny.en-q5_1.bin"
WHISPER_MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/${WHISPER_MODEL_NAME}"
WHISPER_MODEL_SHA256="c77c5766f1cef09b6b7d47f21b546cbddd4157886b3b5d6d4f709e91e66c7c2b"
WHISPER_MODEL_DIR="$INSTALL_DIR/app/models"
WHISPER_MODEL_PATH="$WHISPER_MODEL_DIR/$WHISPER_MODEL_NAME"

mkdir -p "$WHISPER_MODEL_DIR"
if [ -f "$WHISPER_MODEL_PATH" ] \
    && echo "$WHISPER_MODEL_SHA256  $WHISPER_MODEL_PATH" | sha256sum --check --status; then
    info "whisper.cpp model already installed."
else
    info "Downloading whisper.cpp model (31 MB, one time)..."
    rm -f "$WHISPER_MODEL_PATH.tmp"
    curl --fail --location --retry 3 --output "$WHISPER_MODEL_PATH.tmp" "$WHISPER_MODEL_URL"
    echo "$WHISPER_MODEL_SHA256  $WHISPER_MODEL_PATH.tmp" | sha256sum --check --status \
        || error "whisper.cpp model checksum verification failed."
    mv "$WHISPER_MODEL_PATH.tmp" "$WHISPER_MODEL_PATH"
    info "whisper.cpp model installed."
fi

# ── 4. Configure .env ────────────────────────────────────────────────────────
ENV_FILE="$INSTALL_DIR/app/.env"

if [ -f "$ENV_FILE" ]; then
    warn ".env already exists — skipping configuration."
    warn "Edit $ENV_FILE manually if you need to change settings."
else
    info "Configuring .env from template..."
    cp "$INSTALL_DIR/app/.env.example" "$ENV_FILE"

    echo ""
    echo "  ┌─ Required settings ─────────────────────────────────────────────"

    # OpenAI key
    read -rp "  │  OpenAI API key: " OPENAI_KEY </dev/tty
    while [ -z "$OPENAI_KEY" ]; do
        echo "  │  ↳ Cannot be empty"
        read -rp "  │  OpenAI API key: " OPENAI_KEY </dev/tty
    done

    # Postgres password
    read -rsp "  │  Choose a Postgres password: " PG_PASS </dev/tty; echo ""
    while [ ${#PG_PASS} -lt 8 ]; do
        echo "  │  ↳ Must be at least 8 characters"
        read -rsp "  │  Postgres password: " PG_PASS </dev/tty; echo ""
    done

    # Admin credentials
    read -rp "  │  Admin email (for the web UI): " ADMIN_EMAIL </dev/tty
    read -rsp "  │  Admin password: " ADMIN_PASS </dev/tty; echo ""

    echo "  └─────────────────────────────────────────────────────────────────"
    echo ""

    # Apply to .env (using | as sed delimiter to avoid / conflicts in URLs)
    sed -i "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=${OPENAI_KEY}|"        "$ENV_FILE"
    sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PG_PASS}|"     "$ENV_FILE"
    sed -i "s|^DB_URI=.*|DB_URI=postgresql+psycopg://talkbox:${PG_PASS}@talkbox-postgres:5432/talkbox|" "$ENV_FILE"
    sed -i "s|^COOKIE_SECURE=.*|COOKIE_SECURE=0|"                       "$ENV_FILE"
    sed -i "s|^ADMIN_EMAIL=.*|ADMIN_EMAIL=${ADMIN_EMAIL}|"             "$ENV_FILE"
    sed -i "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=${ADMIN_PASS}|"        "$ENV_FILE"
    # Pi is local-only HTTP
    sed -i "s|^FRONTEND_URL=.*|FRONTEND_URL=http://localhost:8084|"     "$ENV_FILE"

    info ".env written."
fi

# ── 5. Fix line endings on entrypoint (safe to re-run) ──────────────────────
info "Ensuring shell scripts have LF line endings..."
sed -i 's/\r//' "$INSTALL_DIR/app/backend/docker-entrypoint.sh"

# ── 6. Build + initialize ───────────────────────────────────────────────────
info "Building containers (first build takes ~5-10 min on Pi)..."
cd "$INSTALL_DIR/app"
$DOCKER compose build

info "Verifying local speech installation..."
$DOCKER compose run --rm --no-deps --entrypoint sh talkbox-backend -c \
    'command -v whisper-cli >/dev/null && test -s /models/ggml-tiny.en-q5_1.bin' \
    || error "whisper.cpp binary or model is unavailable inside the backend container."

$DOCKER compose up -d talkbox-postgres

info "Running schema migrations..."
$DOCKER compose run --rm --no-deps --entrypoint python3 talkbox-backend \
    main.py migrate

AGENCY_COUNT=$(
    $DOCKER compose exec -T talkbox-postgres \
        psql -U talkbox -d talkbox -Atc "SELECT COUNT(*) FROM agencies"
)
if [ "$AGENCY_COUNT" = "0" ]; then
    info "Initializing the empty local catalog..."
    $DOCKER compose run --rm --no-deps --entrypoint python3 talkbox-backend \
        main.py seed-agencies --confirm-replace
    $DOCKER compose run --rm --no-deps --entrypoint python3 talkbox-backend \
        main.py seed-category-vectors
    $DOCKER compose run --rm --no-deps --entrypoint python3 talkbox-backend \
        main.py seed-agency-vectors
else
    info "Existing catalog has $AGENCY_COUNT agencies; leaving it unchanged."
fi

info "Starting application services..."
$DOCKER compose up -d

# ── 7. Wait for health ───────────────────────────────────────────────────────
info "Waiting for backend health..."
ATTEMPTS=0
until $DOCKER compose exec talkbox-backend curl -fsS http://localhost:8000/api/health &>/dev/null; do
    ATTEMPTS=$((ATTEMPTS + 1))
    if [ $ATTEMPTS -ge 30 ]; then
        warn "Backend taking a while — check logs with: docker logs -f talkbox-backend"
        break
    fi
    echo -n "."
    sleep 5
done
echo ""

# ── 8. Run embedding benchmark ───────────────────────────────────────────────
if command -v python3 &>/dev/null && [ -f "$INSTALL_DIR/bench_embeddings.py" ]; then
    echo ""
    info "Running embedding latency benchmark on this hardware..."
    python3 - <<'HEREDOC'
import sys, subprocess
for pkg in ["sentence-transformers", "numpy"]:
    try: __import__(pkg.replace("-","_"))
    except ImportError: subprocess.check_call([sys.executable,"-m","pip","install",pkg,"-q"])
HEREDOC
    python3 "$INSTALL_DIR/bench_embeddings.py" 2>/dev/null || warn "Benchmark skipped (deps missing)"
fi

# ── 9. Done ──────────────────────────────────────────────────────────────────
LOCAL_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║  Talk Box Kiosk is running!                               ║"
echo "  ╠══════════════════════════════════════════════════════════╣"
printf "  ║  Kiosk UI  → http://%-35s║\n" "${LOCAL_IP}:8084/kiosk"
printf "  ║  Demo mode → http://%-35s║\n" "${LOCAL_IP}:8084/demo"
printf "  ║  API       → http://%-35s║\n" "${LOCAL_IP}:8085/api/health"
echo "  ╠══════════════════════════════════════════════════════════╣"
echo "  ║  Useful commands:                                        ║"
echo "  ║    docker logs -f talkbox-backend                        ║"
echo "  ║    docker compose -f ~/talkbox/app/docker-      ║"
echo "  ║      compose.yml restart                                 ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo ""
