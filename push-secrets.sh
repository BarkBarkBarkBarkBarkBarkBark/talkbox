#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-.env}"
VERCEL_ENV="${VERCEL_ENV:-production}"
FLY_APP="${FLY_APP:-}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE"
  exit 1
fi

echo "Installing CLIs..."
command -v npm >/dev/null || { echo "Install node/npm first"; exit 1; }
npm i -g vercel

if ! command -v fly >/dev/null; then
  curl -L https://fly.io/install.sh | sh
  export FLYCTL_INSTALL="${HOME}/.fly"
  export PATH="$FLYCTL_INSTALL/bin:$PATH"
fi

echo "Login if needed..."
vercel whoami >/dev/null 2>&1 || vercel login
fly auth whoami >/dev/null 2>&1 || fly auth login

echo "Linking Vercel project..."
vercel link

echo "Pushing secrets to Vercel: $VERCEL_ENV"
while IFS='=' read -r key value; do
  [[ -z "${key}" || "${key}" =~ ^# ]] && continue
  key="$(echo "$key" | xargs)"
  value="${value%$'\r'}"
  value="${value%\"}"
  value="${value#\"}"

  tmp="$(mktemp)"
  printf "%s" "$value" > "$tmp"

  vercel env rm "$key" "$VERCEL_ENV" -y >/dev/null 2>&1 || true
  vercel env add "$key" "$VERCEL_ENV" < "$tmp"

  rm -f "$tmp"
done < "$ENV_FILE"

if [[ -z "$FLY_APP" ]]; then
  echo "Skipping Fly: set FLY_APP first, e.g."
  echo "  FLY_APP=talkbox ./scripts/push-secrets.sh .env"
else
  echo "Pushing secrets to Fly app: $FLY_APP"
  fly secrets import -a "$FLY_APP" < "$ENV_FILE"
fi

echo "Done."
echo "Check:"
echo "  vercel env ls $VERCEL_ENV"
echo "  fly secrets list -a $FLY_APP"
