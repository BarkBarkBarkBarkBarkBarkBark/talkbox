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

The FSC Resource Platform is the source of truth for TalkBox resource and
directory data. Its Replit-hosted Neon database is maintained through the FSC
Staff CMS, and TalkBox consumes public TalkBox data through the authenticated
versioned API via the Fly FastAPI backend. Do not reintroduce hard-coded
canonical resource lists or connect kiosks directly to Neon.

Resource synchronization is public-data-only. Never synchronize users,
participants, clients, submissions, authentication data, audit records, case
data, or kiosk interaction events. Phone numbers are callable only when an
active upstream contact explicitly has `allow_talkbox_call=true`.

Key files:
- `app/frontend/src/main.jsx` defines the route map.
- `app/frontend/src/pages/RootPage.jsx` chooses marketing vs kiosk on `/`.
- `app/frontend/src/pages/KioskPage.jsx` is the production kiosk page.
- `app/frontend/src/components/kiosk/KioskShell.jsx` owns the kiosk screen flow.
- `app/frontend/src/components/marketing/` is the public advertising shell.
- `kiosk-setup.sh` launches Chromium against `/kiosk` on the Pi.
