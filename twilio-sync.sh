#!/usr/bin/env bash
# twilio-sync.sh — systemd-friendly wrapper for Talk Box Twilio webhook sync.
set -euo pipefail
exec "$(dirname "$(realpath "$0")")/talkbox" twilio-sync
