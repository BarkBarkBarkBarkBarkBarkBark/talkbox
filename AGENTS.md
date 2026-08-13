# TalkBox Agent Instructions

TalkBox is a kiosk-first product. The production kiosk is the main appliance
experience. The public web (Vercel) is a marketing surface for partners and donors.

Canonical routes:
- `/` on **localhost / appliance** renders the production kiosk.
- `/` on **public hosts** (e.g. Vercel) renders the marketing home (About).
- `/kiosk` is the hardware-stable production kiosk entrypoint (Pi Chromium default).
- `/demo` renders the simulated kiosk with browser keypad controls and a thin marketing strip.
- `/donate` is the public donation page (`VITE_DONATE_URL` powers the CTA).
- `/site` always shows marketing home (local preview when `/` is kiosk).
- `/chat` is a secondary admin/partner console, not the website or kiosk default.

When working on frontend routing, deployment, docs, or kiosk setup:
- Keep production kiosk at `/kiosk` (and localhost `/`).
- Do not point kiosk Chromium at public marketing routes.
- Do not move the desktop chat console back to `/` unless the user explicitly asks.

Pointer and Health Scout are supporting routing/data assets inherited from earlier project language. Treat them as assets that serve TalkBox, not as the product identity, deployment target, or primary entrypoint.

The existing standalone Neon project named `talkbox` is the source of truth for
TalkBox resources, directory data, users, and pgvector collections. FastAPI is
the only application layer that connects to Neon; browsers and kiosks consume
that data through the API and must never receive database credentials.

The former FSC Resource Platform synchronization code is dormant rollback
code, not an active or canonical data source. Do not enable it or reintroduce
hard-coded canonical resource lists without an explicit architecture change.
Database migrations, admin bootstrap, imports, and seed commands must remain
explicit operations and must never run automatically at application startup.

When catching a local appliance or this checkout up to the live catalog
(multi-category join table, Browse visibility, `/admin` bulk edit, Neon as
canonical), follow `docs/LOCAL_AGENT_HANDOFF_CANONICAL_NEON.md`. Do not follow
the archived Replit/SQLite handoff.

Key files:
- `docs/LOCAL_AGENT_HANDOFF_CANONICAL_NEON.md` is the current local-agent brief.
- `app/frontend/src/main.jsx` defines the route map.
- `app/frontend/src/pages/RootPage.jsx` chooses marketing vs kiosk on `/`.
- `app/frontend/src/pages/KioskPage.jsx` is the production kiosk page.
- `app/frontend/src/components/kiosk/KioskShell.jsx` owns the kiosk screen flow.
- `app/frontend/src/components/marketing/` is the public advertising shell.
- `kiosk-setup.sh` launches Chromium against `/kiosk` on the Pi.
