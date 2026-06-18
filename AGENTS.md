# TalkBox Agent Instructions

TalkBox is a kiosk-first product. The production kiosk is the main user experience and must remain the default entrypoint.

Canonical routes:
- `/` renders the production kiosk and is the public/default route.
- `/kiosk` is an alias to the same production kiosk, kept for hardware and older docs.
- `/demo` renders the simulated kiosk with browser keypad controls.
- `/chat` is a secondary admin/partner console, not the default experience.

When working on frontend routing, deployment, docs, or kiosk setup, preserve that ordering. Do not move the desktop chat console back to `/` unless the user explicitly asks.

Pointer and Health Scout are supporting routing/data assets inherited from earlier project language. Treat them as assets that serve TalkBox, not as the product identity, deployment target, or primary entrypoint.

Key files:
- `app/frontend/src/main.jsx` defines the route map.
- `app/frontend/src/pages/KioskPage.jsx` is the production kiosk page.
- `app/frontend/src/components/kiosk/KioskShell.jsx` owns the kiosk screen flow.
- `kiosk-setup.sh` launches Chromium against the kiosk entrypoint on the Pi.