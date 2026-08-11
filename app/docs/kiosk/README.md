# Talk Box Kiosk

Keypad-first, voice-assisted kiosk UX for the Talk Box resource-routing app,
designed for a 6-inch screen driven by an ATM-style 12-key keypad. This is the
**primary appliance surface**. Marketing lives on public web hosts; hardware
always loads `/kiosk`.

## What's implemented (this milestone set: M0–M3, M8)

- **`/` (localhost)** — production kiosk surface. Full-screen, no login wall, no
  desktop header. Driven entirely by number keys (`1`–`9`, `0`, `*`, `#`).
- **`/` (public host / Vercel)** — marketing About page (not the appliance).
- **`/kiosk`** — hardware-stable production kiosk (Pi Chromium default).
- **`/demo`** — same UX plus an on-screen simulated keypad, DEMO badge, and a thin
  marketing chrome strip. Calling is always simulated here.
- **`/donate`**, **`/site`** — public donation page and always-on marketing
  preview (for local review when `/` is the kiosk).
- **Chat-first home** — the main surface is an open-ended "What do you need?"
  input (original Talk Box style). Single turn: ask → numbered results → press a
  number → call. A **Browse services** tab lists the numbered category menu,
  and numbered quick chips under the input give keypad-only users a shortcut
  while the input is empty.
- **Keypad state machine** — deterministic navigation across screens:
  `ASK_HOME (ask | browse tabs) → RESULTS_LIST → RESOURCE_DETAIL →
  CALL_CONFIRM → CALL_ACTIVE`, plus `EMPTY` / `ERROR`. Inactivity auto-resets
  to the ask screen.
- **Push-button voice search** — on the Ask tab, `*` records a short request,
  posts it to `POST /api/kiosk/speech/transcribe`, inserts the transcript into
  the Ask field, and runs the existing kiosk search. Other screens keep
  `*` repeat/help behavior; live calls keep `*` as DTMF.
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
  legacy `Health Scout DBs/*.csv` exports (original Pointer project).

Real outbound calling runs through Twilio Voice with a server-side allowlist.
The admin/partner chat console is intentionally separate from the kiosk.

## Key bindings

| Key   | Meaning                                  |
| ----- | ---------------------------------------- |
| `1`–`9` | Select the visible menu item / resource (on the ask screen, digits act as category shortcuts while the input is empty) |
| `0`   | Back / home (clears the input on the ask screen) |
| `*`   | Speak on Ask; repeat / help elsewhere; DTMF during active calls |
| `#`   | Search / select / confirm call           |

Keyboard aliases for laptop testing: `Enter` = `#`, `Escape`/`Backspace` = `0`,
`/` = `*`. The number row works directly.

## Run locally (Docker Compose)

The repo ships with a multi-arch (alpine) Compose stack that builds on Apple
Silicon and on a Raspberry Pi (arm64) unchanged.

```sh
cd app
cp .env.example .env   # the committed local .env already defaults to mock mode
docker compose up --build
```

Then open:

- Production kiosk: <http://localhost:8084/kiosk> (also `/` on localhost)
- Marketing preview: <http://localhost:8084/site>
- Demo: <http://localhost:8084/demo>
- Donate: <http://localhost:8084/donate>
- Admin chat console: <http://localhost:8084/chat>
- API health: <http://127.0.0.1:8085/api/health>

Normal backend startup never migrates, imports, or seeds data. Initialize a
disposable local database with the explicit commands in the main README.

### Frontend-only dev (hot reload)

```sh
cd frontend
npm install
npm run dev   # http://localhost:5173/  (proxies /api to the compose backend on 127.0.0.1:8085)
```

## Switching to the real query pipeline

1. Set `OPENAI_API_KEY` in `.env`.
2. Set `KIOSK_MOCK_QUERY=false`.
3. Run `python main.py migrate`, then explicitly initialize the catalog and
  vector collections if the database is empty.
4. `docker compose up --build` again. Restarts will not mutate catalog data.

## Raspberry Pi notes (later: M9)

- Same Compose stack runs on Pi OS / Debian (arm64). Build on the Pi or push
  multi-arch images.
- The Pi is a thin terminal: a Chromium kiosk pointed at `/` on the cloud
  (or a local) backend. Autostart, health page, and heartbeat land in M9.
- Keep `KIOSK_MOCK_QUERY` off in the field; point the device at the real backend.
- The one-line installer builds `whisper.cpp` into the backend image and
  downloads `ggml-tiny.en-q5_1.bin` once into `app/models`. Compose mounts the
  model read-only at `/models`; normal updates reuse it.

## Baseline reference (verified)

- Backend: FastAPI (`backend/main.py` → `src.presentation.api:app`). Public:
  `GET /api/health`, `POST /api/query`, `POST /api/sms-query`, auth routers.
  Kiosk adds: `GET /api/kiosk/config`, `POST /api/kiosk/query`,
  `POST /api/kiosk/speech/transcribe`, `POST /api/kiosk/events`.
- Query response shape: `{ markdown, results: { type: "agencies"|"doctors",
  category, items_agencies[], items_doctors[] } }`.
- Frontend: React 19 + Vite 6 + Tailwind 4. Router in `frontend/src/main.jsx`.
- Data store: Postgres + pgvector (`pgvector/pgvector:pg18`).
- Compose ports: frontend `127.0.0.1:8084→80`, backend `127.0.0.1:8085→8000`.
  nginx proxies `/api/` → backend, so kiosk endpoints flow through automatically.
