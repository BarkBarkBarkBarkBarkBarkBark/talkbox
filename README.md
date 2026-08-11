# Talk Box

**A payphone for the 21st century.** Talk Box is a Raspberry-Pi kiosk that
connects homeless and phoneless individuals directly to **211** and local
services — shelter, food, medical care, mental health — with one big green
button. No phone, no account, no login. Walk up, press Call, talk to a human
who can help.

Under the hood it's a keypad-first React kiosk, a FastAPI backend with
pgvector semantic search over a seeded agency database, and real two-way
phone calls placed straight from the browser via the Twilio Voice SDK.
Outbound dialing is **allowlisted server-side** — the kiosk can only call
known service agencies, the 211 help lines, and configured test numbers.

## Canonical resource architecture

The FSC Resource Platform is the source of truth for community organizations,
services, approved contacts, announcements, and kiosk content. FSC staff manage
those records in the Replit-hosted Staff CMS backed by production Neon
PostgreSQL. TalkBox does not integrate with that database schema directly:

```text
FSC Staff CMS -> Replit Neon -> authenticated /api/v1/talkbox/*
              -> TalkBox FastAPI on Fly.io -> TalkBox kiosks
```

FastAPI checks the upstream `content_version` every 60 seconds by default and
downloads a complete typed snapshot only when it changes. A snapshot is
installed atomically after validation; a timeout, unauthorized response, or
malformed update leaves the last-known-good data untouched. `/healthz` remains
healthy during an FSC outage, while `/api/kiosk/sync-status` reports cache and
sync state.

The source currently supports multiple frontend/backend topologies. A local
client appliance serves React through nginx and proxies `/api/*` to its own
backend container. The Vercel frontend rewrites `/api/*` to Fly, while CI-built
frontend images may bake another backend into `VITE_API_URL`. Keep these roles
separate when configuring credentials: only Fly receives the FSC service key;
client appliances receive a distinct read-only snapshot key.

Validated snapshots persist at `/data/resource-snapshot.sqlite3`. Configure a
Docker-based client appliance, whether Raspberry Pi, Linux, or macOS, with:

```bash
./scripts/configure-client-snapshot.sh https://talkbox.fly.dev
```

The helper requires `python3`, updates ignored `app/.env` without printing the
key, recreates only the backend, and reports non-secret synchronization status.
For a local virtual environment, use `python3 -m venv .venv`.

Synchronization is strictly limited to public resource and kiosk configuration
data. Client, participant, user, submission, authentication, case, audit, and
interaction-event records are excluded. Kiosk calling remains server-controlled:
only active contacts explicitly marked `allow_talkbox_call=true` are callable.
See [`docs/adr/0001-fsc-resource-platform-source-of-truth.md`](docs/adr/0001-fsc-resource-platform-source-of-truth.md).

**Entrypoint rule:** TalkBox is kiosk-first on appliances and marketing-first on
the public web. On **localhost**, `/` is the production kiosk; on **public hosts**
(Vercel), `/` is the marketing site (About, Demo, Donate). **`/kiosk` is the
hardware-stable production kiosk** (Pi Chromium default via `kiosk-setup.sh`).
`/demo` is the simulated product demo; `/donate` uses `VITE_DONATE_URL`; `/site`
always shows marketing for local preview. `/chat` is only a secondary
admin/partner console. Pointer/Health Scout are supporting routing and dataset
assets, not the app identity or appliance entrypoint.

```
┌─────────────────────────────────────────────┐
│   📞  Call 211 — Get Help Now               │   ← the main feature
├─────────────────────────────────────────────┤
│   Ask: "I need shelter tonight"  → search   │   ← semantic agency lookup
│   Browse: 1 Shelter  2 Food  3 Medical …    │   ← numbered keypad menu
│   Dial: 211 or any allowlisted number       │   ← ATM-style dial pad
└─────────────────────────────────────────────┘
```

211 is dialable everywhere through its national access numbers:
dialing `2-1-1` on the kiosk routes to `+1 (916) 498-1000`
(toll-free `+1 (844) 546-1464` is also allowlisted).

## Repository layout

| Path | What it is |
| --- | --- |
| [`talkbox`](talkbox) | The CLI. `talkbox update` = git pull → rebuild → relaunch → Twilio publish → health check. |
| [`app/`](app/) | The app: FastAPI backend, React kiosk frontend, nginx, pgvector Postgres, Docker Compose. |
| [`app/backend/`](app/backend/) | Python 3.13 / FastAPI / SQLAlchemy / LangChain. Seeds the agency DB + embeddings on first boot. |
| [`app/frontend/`](app/frontend/) | React 19 + Vite + Tailwind. Routes: public `/` marketing (Vercel); localhost `/` + `/kiosk` production kiosk; `/demo`, `/donate`, `/site`, `/chat`. |
| [`Datasets/`](Datasets/) | Reference datasets and data-source documentation. |
| [`install.sh`](install.sh) | One-shot Pi installer (Docker, repo, `.env`, build, health). |
| [`kiosk-setup.sh`](kiosk-setup.sh) | Turns the Pi into a fullscreen Chromium kiosk on boot. |
| [`twilio-sync.sh`](twilio-sync.sh) | Thin systemd wrapper around `talkbox twilio-sync` (re-syncs webhook config at boot). |
| [`agent-context.yaml`](agent-context.yaml), [`kiosk-roadmap.yaml`](kiosk-roadmap.yaml) | Machine-readable project context and roadmap for AI agents (historical, pre-rename). |

## Agent crib sheet (key files)

| Concern | File |
| --- | --- |
| Kiosk state machine (screens, keypad vocabulary, DTMF) | `app/frontend/src/hooks/useKioskStateMachine.js` |
| Kiosk voice search (`*` on Ask screen) | `app/frontend/src/hooks/useVoiceSearch.js`, `app/backend/src/application/services/kiosk_stt_service.py` |
| Twilio Voice SDK hook (token → connect → sendDigits) | `app/frontend/src/hooks/useKioskVoiceCall.js` |
| Screen router / shell | `app/frontend/src/components/kiosk/KioskShell.jsx` |
| Kiosk HTTP API (`/api/kiosk/*`: query, token, TwiML webhook) | `app/backend/src/presentation/kiosk_routes.py` |
| Call allowlist + 211 short-code mapping | `app/backend/src/application/services/kiosk_call_service.py` |
| Twilio access tokens + TwiML generation | `app/backend/src/infrastructure/voice/twilio_voice_service.py` |
| Semantic search / results / 211 fallback | `app/backend/src/application/services/kiosk_query_service.py` |
| nginx (API proxy, mic Permissions-Policy) | `app/nginx/default.conf` |
| All settings | `app/.env.example` (copy to `app/.env`) |

### How a call works

```mermaid
flowchart LR
  Button["Kiosk: green Call button"] --> Token["POST /api/kiosk/call/token (allowlist check, JWT)"]
  Token --> Connect["Browser: Twilio Device.connect"]
  Connect --> Twilio[Twilio Cloud]
  Twilio -->|"via public HTTPS webhook"| Webhook["POST /api/kiosk/call/twiml"]
  Webhook --> DialOut["TwiML Dial to agency / 211"]
  Connect -. "keypad → DTMF during call" .-> Twilio
```

The keypad vocabulary is `1-9`, `0`, `*`, `#`, plus two dedicated buttons:
**`CALL`** (green) and **`HANGUP`** (red), always visible in the footer —
touch targets today, mappable to physical GPIO/HID buttons later (keyboard
aliases: `C` / `H`). Outside a call: `0` = back, `*` = repeat aloud,
`#` = select, `CALL` = context-aware (confirm call / dial / Call 211 from
home). On the Ask screen, `*` starts one-shot voice search: record a short
request, transcribe it, and run the normal semantic search. **During a live call
every keypad key is sent as a DTMF tone** (so
"press 0 for an operator" works); only `HANGUP` ends the call.

### Arcade buttons (physical kiosk)

The physical kiosk has seven arcade buttons. A small host-side bridge
(`~/.local/bin/talkbox-button-bridge`, started at login) reads the USB encoder
and re-emits keystrokes the kiosk already understands, so the buttons and the
keyboard/keypad stay in sync.

| Button | Action | Kiosk key |
| --- | --- | --- |
| **K1** | Call 211 | `CALL_211` (≡ `9` on home) |
| **K2** | Talk — ask a question by voice | `*` |
| **K3** | Call / Enter (confirm + select) | `CALL` / `#` |
| **K4** | Hang up / Exit (back) | `HANGUP` / Back |
| **L1** | Move highlight up | `PREV` |
| **R1** | Move highlight down | `NEXT` |
| **L2** | Toggle screen (cycle Ask → Browse → Dial) | `CYCLE_TAB` |

## The `talkbox` CLI

```bash
./talkbox install   # once — puts `talkbox` on your PATH

talkbox update      # git pull → rebuild → relaunch → publish webhook to Twilio → health
talkbox twilio-sync # publish webhook to Twilio + sync backend env
talkbox status      # containers, health, public URL, Twilio sync check
talkbox restart     # restart containers without rebuilding
talkbox logs        # tail backend logs
```

`update` publishes `TWILIO_PUBLIC_URL + /api/kiosk/call/twiml` to the Twilio
TwiML App via the REST API and relaunches the stack.

## Quick start (Docker)

Requirements: Docker with Compose v2.20+ (root compose uses `include:`).

```bash
git clone https://github.com/BarkBarkBarkBarkBarkBarkBark/talkbox.git
cd talkbox

# 1. Configure
cp app/.env.example app/.env
#    Minimum: POSTGRES_PASSWORD, DB_URI (same password), OPENAI_API_KEY
#    For real calls: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER,
#                    TWILIO_TWIML_APP_SID, KIOSK_CALLING_ENABLED=true

# 2. Deploy everything
./talkbox update

# 3. Open it (loopback-only by default)
#    Production kiosk:    http://localhost:8084/kiosk  (also localhost /)
#    Marketing preview:   http://localhost:8084/site
#    Demo (simulated):    http://localhost:8084/demo
#    Donate:              http://localhost:8084/donate
#    Admin chat console:  http://localhost:8084/chat
#    API health:          http://127.0.0.1:8085/api/health
```

Local installs may bootstrap the legacy agency database for offline development.
That seed is a fallback and is not the canonical production resource source.

### Smoke test

```bash
curl -s 127.0.0.1:8085/api/health
curl -s 127.0.0.1:8085/api/kiosk/query -X POST \
  -H 'Content-Type: application/json' -d '{"query":"i need shelter tonight"}'
# 211 should always be allowlisted:
curl -s -X POST 127.0.0.1:8085/api/kiosk/call/token \
  -H 'Content-Type: application/json' -d '{"phone":"211"}'
```

## Phone calls (Twilio) — the safety model

Real two-way calls run through the Twilio Voice **browser SDK**: the kiosk
fetches a short-lived access token, `Device.connect()` opens the call, and
Twilio fetches dial instructions from `/api/kiosk/call/twiml` through your
public HTTPS URL (for example Tailscale Funnel). The backend refuses any
number that is not:

1. an active FSC API contact explicitly approved for TalkBox calling (with the
  legacy `agencies` table used only before the first canonical snapshot),
2. a built-in 211 help-line number, or
3. listed in `KIOSK_TEST_CALL_NUMBERS` (comma-separated, handy on trial
   accounts which can only call verified numbers).

`/demo` never places real calls. The microphone must be allowed —
nginx ships `Permissions-Policy: microphone=(self)` for this.

One-time Twilio setup: create a TwiML App (Console → Voice → TwiML Apps),
put its SID in `TWILIO_TWIML_APP_SID`, and set `TWILIO_PUBLIC_URL` in `.env`
to your stable public host URL.

## Voice search (`*` on Ask)

The kiosk can do local-first, push-button speech search. On the Ask tab, press
`*`, speak for up to `KIOSK_STT_MAX_SECONDS`, and the frontend posts microphone
audio to `POST /api/kiosk/speech/transcribe`. The backend converts the browser
audio with `ffmpeg`, runs `whisper.cpp`, inserts the transcript into the Ask
field, and then uses the existing `/api/kiosk/query` search path.

Configure it in `app/.env`:

```bash
KIOSK_STT_ENABLED=true
KIOSK_STT_PROVIDER=local        # local | openai | auto
KIOSK_STT_WHISPER_BIN=/usr/local/bin/whisper-cli
KIOSK_STT_MODEL_PATH=/models/ggml-tiny.en-q5_1.bin
KIOSK_STT_MAX_SECONDS=6
```

The one-line Pi installer builds a pinned `whisper.cpp` binary into the backend
image, downloads the quantized tiny English model once with checksum
verification, and mounts it read-only at the configured model path. Normal
`talkbox update` runs reuse the downloaded model.

## Deploying to a Raspberry Pi

Pi 4/5, 64-bit Raspberry Pi OS, 4 GB+ RAM. Build on the Pi itself (arm64):

```bash
curl -fsSL https://raw.githubusercontent.com/BarkBarkBarkBarkBarkBarkBark/talkbox/main/install.sh | bash
bash ~/talkbox/kiosk-setup.sh       # fullscreen Chromium kiosk on boot
# systemd service for boot-time Twilio sync: see header of twilio-sync.sh
```

After kiosk setup, use the maintenance escape hatch from the kiosk session:

- `Ctrl+Alt+T` (or `Ctrl+Alt+F4`) exits kiosk X and opens a plain tty shell.
- Run `nmtui` there for Wi-Fi configuration, or any Linux commands.
- Type `exit` to return to kiosk mode automatically.

Ports bind to loopback by default. To expose the kiosk on your LAN, change
`127.0.0.1:8084:80` to `8084:80` in `app/docker-compose.yml`
(keep the backend on loopback — nginx proxies `/api`).

## Development (without Docker)

```bash
# Backend (uses uv)
cd app/backend
uv sync && uv run python main.py api

# Frontend
cd app/frontend
npm install && npm run dev    # Vite proxies /api to 127.0.0.1:8085
```

## Resource synchronization configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `FSC_RESOURCE_API_BASE_URL` | Published HTTPS FSC Resource Platform origin | required |
| `FSC_RESOURCE_API_KEY` | Backend-only bearer credential | required secret |
| `FSC_RESOURCE_SYNC_ENABLED` | Enables startup and periodic synchronization | `true` |
| `FSC_RESOURCE_SYNC_INTERVAL_SECONDS` | Version polling interval | `60` |
| `FSC_RESOURCE_REQUEST_TIMEOUT_SECONDS` | Upstream request timeout | `10` |
| `FSC_RESOURCE_CACHE_MAX_AGE_SECONDS` | Stale-warning threshold | `86400` |

On Fly, set `FSC_RESOURCE_API_BASE_URL` to the real published HTTPS origin and
store `FSC_RESOURCE_API_KEY` with `fly secrets set`; never put the key in
`fly.toml` or on a Raspberry Pi. Troubleshoot with `/api/kiosk/sync-status` and
backend events `resource_sync_updated`, `resource_sync_unchanged`,
`resource_sync_failed`, and `upstream_auth_failed`. The cache is currently
in-memory on Fly and is repopulated automatically after process startup.

## Known sharp edges

- **Public URL drift**: if `TWILIO_PUBLIC_URL` in `.env`, the backend container,
  and Twilio VoiceUrl do not match, webhooks can fail. `talkbox status` detects
  drift and `talkbox twilio-sync` repairs it.
- **Pending calls are in-process memory** (`_pending_calls` in
  `kiosk_routes.py`): a backend restart between token issue and Twilio's
  webhook drops the call, and multiple uvicorn workers would break it. Fine
  at single-worker kiosk scale; move to Redis/Postgres if scaling out.
- **TwiML webhook auth depends on `TWILIO_PUBLIC_URL`**: X-Twilio-Signature
  is validated against that URL, so if `.env` is stale the webhook returns 403.
  `talkbox update` / `talkbox twilio-sync` keep it in sync.
- **`docker compose pull` is a trap**: images are tagged
  `ghcr.io/la-plas-growth/talkbox-*:latest` but built locally. Pulling could
  clobber local builds with stale registry images. Always use
  `talkbox update` (it builds, never pulls).
- **nginx `add_header` inheritance**: any `add_header` inside a `location`
  block silently drops all server-level headers — that's why the security
  headers are repeated inside `location /` in `nginx/default.conf`.
- **Physical buttons not wired yet**: the green/red footer buttons emit the
  `CALL` / `HANGUP` key vocabulary (keyboard `C` / `H`), so a GPIO or HID
  button pair just needs to emit those keys — no UI changes required.
