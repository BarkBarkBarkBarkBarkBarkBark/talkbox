# Talkbox

Monorepo for the **Pointer** community-resource kiosk and its supporting data
tooling. The flagship app is a chat-first, keypad-driven kiosk that helps
people in crisis find — and directly call — local services (shelter, food,
medical, mental health) with zero LLM-generated answers in the response path.

## Repository layout

| Directory | What it does |
| --- | --- |
| [`pointer-fork/`](pointer-fork/) | The main app: FastAPI backend + React kiosk frontend + pgvector Postgres. Embedding-based category search over the Health Scout agency database, structured (non-LLM) results, and allowlisted outbound calling via Twilio. |
| [`PointerST/`](PointerST/) | The original Pointer prototype — a Streamlit chat app with Weaviate integration. Kept for reference. |
| [`PDF_Analyzer/`](PDF_Analyzer/) | Scripts that convert resource-directory PDFs into structured JSON (`0-pdf2json.py`, `1-reanalyze-jpeg.py`). |
| [`Health Scout/`](Health%20Scout/) | Source datasets. `Datasets/` is committed; the multi-GB raw exports in `Pointer Databases/` stay local-only (gitignored). |

Root-level `docker-compose.yml` runs the whole kiosk stack; per-service
Dockerfiles live in `pointer-fork/backend/Dockerfile` and
`pointer-fork/frontend/Dockerfile`.

## Quick start (Docker)

Requirements: Docker with Compose v2.20+ (for `include:` support).

```bash
git clone https://github.com/<you>/talkbox.git
cd talkbox

# 1. Configure
cp pointer-fork/.env.example pointer-fork/.env
#    Edit pointer-fork/.env — at minimum set:
#      POSTGRES_PASSWORD, DB_URI (same password), OPENAI_API_KEY
#    For real phone calls also set:
#      TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER,
#      KIOSK_CALLING_ENABLED=true

# 2. Build and run
docker compose up -d --build

# 3. Open it
#    Kiosk (real calls):   http://localhost:8084/kiosk
#    Demo (simulated):     http://localhost:8084/demo
#    API health:           http://127.0.0.1:8085/api/health
```

On first boot the backend seeds Postgres with the agency database
(`pointer-fork/backend/src/infrastructure/seeds/agencies_master.csv`) and the
category embeddings. No login is required.

### Smoke test

```bash
curl -s 127.0.0.1:8085/api/health
curl -s 127.0.0.1:8085/api/kiosk/query -X POST \
  -H 'Content-Type: application/json' -d '{"query":"i need shelter tonight"}'
```

Logs roll to `pointer-fork/logs/` and `docker logs pointer-backend`.

## Deploying to a Raspberry Pi

Tested approach: build the images on the Pi itself (arm64). Use a Pi 4/5 with
64-bit Raspberry Pi OS and at least 4 GB RAM.

```bash
# On the Pi
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker

git clone https://github.com/<you>/talkbox.git
cd talkbox
cp pointer-fork/.env.example pointer-fork/.env   # then edit (see above)

docker compose up -d --build    # first build takes a while on a Pi
```

Notes for the Pi:

- All base images (`pgvector/pgvector:pg18`, `python`, `node`, `nginx`) ship
  arm64 variants, so `--build` just works.
- Ports bind to loopback by default. To expose the kiosk on your LAN, change
  `127.0.0.1:8084:80` to `8084:80` in `pointer-fork/docker-compose.yml`
  (and keep the backend on loopback — the frontend's nginx proxies `/api`).
- `restart: unless-stopped` is already set, so the stack survives reboots once
  Docker is enabled: `sudo systemctl enable docker`.
- For a true kiosk, autostart Chromium fullscreen:
  `chromium-browser --kiosk http://localhost:8084/kiosk`

## Phone calls (Twilio)

The kiosk's Dial tab and per-resource "Call" buttons place real outbound calls
through Twilio, restricted to an allowlist:

- numbers present in the seeded `agencies` table, or
- `KIOSK_TEST_CALL_NUMBER` from `.env` (handy for trial accounts, which can
  only call verified numbers).

Everything else is refused server-side (`POST /api/kiosk/call/start`).
The `/demo` route never places real calls.

## Development (without Docker)

```bash
# Backend (uses uv)
cd pointer-fork/backend
uv sync
uv run python main.py api

# Frontend
cd pointer-fork/frontend
npm install
npm run dev          # Vite proxies /api to 127.0.0.1:8085
```

## Data pipeline

`pointer-fork/scripts/build_agencies_csv.py` regenerates the seed CSV and the
mock catalog from the Health Scout source exports:

```bash
cd pointer-fork
python scripts/build_agencies_csv.py
```

The large raw exports (`Health Scout/Pointer Databases/`, ~1 GB) exceed
GitHub's file limits and are intentionally gitignored — keep them local or in
object storage.

## Repo history

`pointer-fork`, `PointerST`, and `PDF_Analyzer` were originally standalone
repos. Their full histories are preserved locally in `*/.git.bak` (gitignored);
this monorepo starts fresh from their combined working trees.
