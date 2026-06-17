#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="app/.env"
VERCEL_ENV="production"
FLY_APP="talkbox"

echo "Checking CLIs..."

if ! command -v vercel >/dev/null; then
    echo "Installing Vercel CLI..."
    sudo npm install -g vercel
fi

if ! command -v fly >/dev/null; then
    echo "Installing Fly CLI..."
    curl -L https://fly.io/install.sh | sh
    export PATH="$HOME/.fly/bin:$PATH"
fi

echo "Authenticating..."
vercel whoami >/dev/null 2>&1 || vercel login
fly auth whoami >/dev/null 2>&1 || fly auth login

echo "Linking Vercel project..."
vercel link

echo "Uploading Fly secrets..."
fly secrets import -a "$FLY_APP" < "$ENV_FILE"

echo "Uploading Vercel secrets..."
while IFS='=' read -r key value; do
    [[ -z "$key" || "$key" =~ ^# ]] && continue

    vercel env rm "$key" "$VERCEL_ENV" -y >/dev/null 2>&1 || true
    printf "%s" "$value" | vercel env add "$key" "$VERCEL_ENV"
done < "$ENV_FILE"

echo ""
echo "✓ Secrets pushed"
echo ""
echo "Deploy with:"
echo "  vercel --prod"
echo "  fly deploy -a talkbox"
