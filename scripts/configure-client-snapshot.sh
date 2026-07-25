#!/usr/bin/env bash
# Configure a TalkBox client appliance to download public snapshots from Fly.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/app/.env"
CENTRAL_URL="${1:-https://talkbox.fly.dev}"

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required" >&2
    exit 1
fi
if ! command -v docker >/dev/null 2>&1; then
    echo "docker is required" >&2
    exit 1
fi
if [[ ! -f "$ENV_FILE" ]]; then
    echo "Missing $ENV_FILE; copy app/.env.example first" >&2
    exit 1
fi

python3 - "$ENV_FILE" "$CENTRAL_URL" <<'PY'
from __future__ import annotations

import getpass
import sys
from pathlib import Path

path = Path(sys.argv[1])
central_url = sys.argv[2].rstrip("/")
key = getpass.getpass("TalkBox client snapshot key: ").strip()
if not key:
    raise SystemExit("Snapshot key cannot be empty")

updates = {
    "FSC_RESOURCE_API_BASE_URL": "",
    "FSC_RESOURCE_API_KEY": "",
    "FSC_RESOURCE_CACHE_PATH": "/data/resource-snapshot.sqlite3",
    "TALKBOX_CENTRAL_API_BASE_URL": central_url,
    "TALKBOX_CLIENT_SNAPSHOT_KEY": key,
    "TALKBOX_KIOSK_SNAPSHOT_KEY": "",
}
lines = path.read_text().splitlines()
seen: set[str] = set()
output: list[str] = []
for line in lines:
    stripped = line.lstrip()
    if not stripped or stripped.startswith("#") or "=" not in line:
        output.append(line)
        continue
    name = line.split("=", 1)[0].strip()
    if name in updates:
        output.append(f"{name}={updates[name]}")
        seen.add(name)
    else:
        output.append(line)
for name, value in updates.items():
    if name not in seen:
        output.append(f"{name}={value}")
path.write_text("\n".join(output) + "\n")
PY

cd "$ROOT_DIR/app"
docker compose up -d --force-recreate --wait talkbox-backend

echo "Client snapshot synchronization configured. Current non-secret status:"
backend_host_port="$(python3 - "$ENV_FILE" <<'PY'
from pathlib import Path
import sys

value = "8085"
for line in Path(sys.argv[1]).read_text().splitlines():
    if line.startswith("BACKEND_HOST_PORT="):
        value = line.split("=", 1)[1].strip() or value
        break
print(value)
PY
)"
curl -fsS "http://127.0.0.1:${backend_host_port}/api/kiosk/sync-status" | python3 -m json.tool