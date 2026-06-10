# Pointer Kiosk

Keypad-first, voice-assisted kiosk UX for the Pointer resource-routing app,
designed for a 6-inch screen driven by an ATM-style 12-key keypad. This is an
**additive** layer: the existing web app (`/`), the `/api/query` endpoint, and
the Twilio SMS webhook are unchanged.

## What's implemented (this milestone set: M0–M3, M8)

- **`/kiosk`** — production kiosk surface. Full-screen, no login wall, no desktop
  header. Driven entirely by number keys (`1`–`9`, `0`, `*`, `#`).
- **`/demo`** — same UX plus an on-screen simulated keypad and a DEMO badge, for
  showing partners from any browser. Calling is always simulated here.
- **Chat-first home** — the main surface is an open-ended "What do you need?"
  input (original Pointer style). Single turn: ask → numbered results → press a
  number → call. A **Browse services** tab lists the numbered category menu,
  and numbered quick chips under the input give keypad-only users a shortcut
  while the input is empty.
- **Keypad state machine** — deterministic navigation across screens:
  `ASK_HOME (ask | browse tabs) → RESULTS_LIST → RESOURCE_DETAIL →
  CALL_CONFIRM → CALL_ACTIVE`, plus `EMPTY` / `ERROR`. Inactivity auto-resets
  to the ask screen.
- **Numbered, structured results** — `POST /api/kiosk/query` routes the query
  with embedding similarity (pgvector) and a plain SQL lookup, then returns
  compact, numbered (1–9), display-safe resources with truncated descriptions
  and a 211 fallback. **No LLM-generated text is ever shown on the kiosk** —
  the Healthscout LLM-extraction branch of the web pipeline is bypassed here
  on purpose, since kiosk users may be in crisis and false information must be
  minimized.
- **Mock mode** — `KIOSK_MOCK_QUERY=true` serves a snapshot of **real
  Sacramento agencies** (generated from the original Health Scout DBs) so the
  kiosk runs with **no OpenAI key and no seeded database** (ideal for a laptop
  or Raspberry Pi demo).
- **Seed rebuild** — `python scripts/build_agencies_csv.py` regenerates
  `backend/src/infrastructure/seeds/agencies_master.csv` and the kiosk mock
  catalog (`kiosk_mock_catalog.json`) from the original
  `PointerST/Health Scout DBs/*.csv` exports.

Real outbound calling (Twilio Voice + an allowlist) and the admin portal are
later milestones (M6/M7); the kiosk **cannot dial a real number** today.

## Key bindings

| Key   | Meaning                                  |
| ----- | ---------------------------------------- |
| `1`–`9` | Select the visible menu item / resource (on the ask screen, digits act as category shortcuts while the input is empty) |
| `0`   | Back / home (clears the input on the ask screen) |
| `*`   | Repeat / help (reads the screen aloud)   |
| `#`   | Search / select / confirm call           |

Keyboard aliases for laptop testing: `Enter` = `#`, `Escape`/`Backspace` = `0`,
`/` = `*`. The number row works directly.

## Run locally (Docker Compose)

The repo ships with a multi-arch (alpine) Compose stack that builds on Apple
Silicon and on a Raspberry Pi (arm64) unchanged.

```sh
cd pointer-fork
cp .env.example .env   # the committed local .env already defaults to mock mode
docker compose up --build
```

Then open:

- Kiosk: <http://localhost:8084/kiosk>
- Demo:  <http://localhost:8084/demo>
- Web app (unchanged): <http://localhost:8084/>
- API health: <http://127.0.0.1:8085/api/health>

The bundled `.env` defaults to a **zero-dependency demo**:
`KIOSK_MOCK_QUERY=true`, `POINTER_SKIP_BOOTSTRAP=1` (no migrations/seeds),
`DISABLE_AUTH=true`, `COOKIE_SECURE=0`.

### Frontend-only dev (hot reload)

```sh
cd frontend
npm install
npm run dev   # http://localhost:5173/kiosk  (proxies /api to the compose backend on 127.0.0.1:8085)
```

## Switching to the real query pipeline

1. Set `OPENAI_API_KEY` in `.env`.
2. Set `KIOSK_MOCK_QUERY=false`.
3. Remove the `POINTER_SKIP_BOOTSTRAP=1` line so migrations + vector/agency
   seeds run on boot.
4. `docker compose up --build` again.

## Raspberry Pi notes (later: M9)

- Same Compose stack runs on Pi OS / Debian (arm64). Build on the Pi or push
  multi-arch images.
- The Pi is a thin terminal: a Chromium kiosk pointed at `/kiosk` on the cloud
  (or a local) backend. Autostart, health page, and heartbeat land in M9.
- Keep `KIOSK_MOCK_QUERY` off in the field; point the device at the real backend.

## Baseline reference (verified)

- Backend: FastAPI (`backend/main.py` → `src.presentation.api:app`). Public:
  `GET /api/health`, `POST /api/query`, `POST /api/sms-query`, auth routers.
  Kiosk adds: `GET /api/kiosk/config`, `POST /api/kiosk/query`,
  `POST /api/kiosk/events`.
- Query response shape: `{ markdown, results: { type: "agencies"|"doctors",
  category, items_agencies[], items_doctors[] } }`.
- Frontend: React 19 + Vite 6 + Tailwind 4. Router in `frontend/src/main.jsx`.
- Data store: Postgres + pgvector (`pgvector/pgvector:pg18`).
- Compose ports: frontend `127.0.0.1:8084→80`, backend `127.0.0.1:8085→8000`.
  nginx proxies `/api/` → backend, so kiosk endpoints flow through automatically.
