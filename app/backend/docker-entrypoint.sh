#!/bin/sh
set -e

# ─── Tailscale (optional) ─────────────────────────────────────────────────────
# When TS_AUTHKEY is set, join the tailnet in userspace mode. When TS_FUNNEL=1,
# expose the local API (port 8000) over Tailscale Funnel so external services
# (e.g. Twilio webhooks) can reach https://${TS_HOSTNAME}.<tailnet>.ts.net.
# The whole block is skipped when TS_AUTHKEY is unset, so local/dev runs are
# unaffected.
if [ -n "${TS_AUTHKEY:-}" ]; then
  echo "[tailscale] starting tailscaled (userspace networking)…"
  /usr/local/bin/tailscaled \
    --tun=userspace-networking \
    --socket=/var/run/tailscale/tailscaled.sock \
    --state=/var/lib/tailscale/tailscaled.state &

  # Wait for the control socket to appear before issuing commands.
  i=0
  while [ ! -S /var/run/tailscale/tailscaled.sock ]; do
    i=$((i + 1))
    [ "$i" -ge 60 ] && break
    sleep 0.5
  done

  echo "[tailscale] bringing node up as '${TS_HOSTNAME:-talkbox}'…"
  /usr/local/bin/tailscale --socket=/var/run/tailscale/tailscaled.sock up \
    --authkey="${TS_AUTHKEY}" \
    --hostname="${TS_HOSTNAME:-talkbox}" \
    --accept-dns=false \
    || echo "[tailscale] 'up' failed — continuing without tailnet"

  if [ "${TS_FUNNEL:-0}" = "1" ]; then
    echo "[tailscale] enabling Funnel → http://127.0.0.1:8000 …"
    /usr/local/bin/tailscale --socket=/var/run/tailscale/tailscaled.sock funnel --bg 8000 \
      || echo "[tailscale] funnel failed — check tailnet ACL funnel attribute + HTTPS certs"
  fi
fi

exec "$@"
