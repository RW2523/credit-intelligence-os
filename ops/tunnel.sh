#!/bin/bash
# Runs a Cloudflare quick tunnel in front of the local app and records the public URL.
#
# NOTE: a trycloudflare.com quick tunnel URL is ephemeral by design — Cloudflare mints a
# new hostname every time cloudflared starts. The *service* is permanent (auto-restart,
# starts at boot); the hostname is not. For a URL that never changes you need a named
# tunnel, which requires a Cloudflare account + domain (`cloudflared tunnel login`).
set -u
PORT="${PORT:-8899}"
STATE_DIR="${STATE_DIR:-$HOME/.local/state/cios}"
LOG="$STATE_DIR/tunnel.log"
URL_FILE="$STATE_DIR/public_url"
mkdir -p "$STATE_DIR"
: > "$LOG"

# Wait for the origin to answer before dialling out, so the tunnel never advertises a dead app.
for _ in $(seq 1 60); do
  curl -sf -m 2 "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1 && break
  sleep 2
done

# Scrape the assigned hostname out of the startup banner and publish it to $URL_FILE.
( tail -n +1 -F "$LOG" 2>/dev/null | while IFS= read -r line; do
    case "$line" in
      *trycloudflare.com*)
        u=$(printf '%s\n' "$line" | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | head -1)
        if [ -n "$u" ] && [ "$u" != "$(cat "$URL_FILE" 2>/dev/null)" ]; then
          printf '%s\n' "$u" > "$URL_FILE"
          printf '%s  %s\n' "$(date -Is)" "$u" >> "$STATE_DIR/url_history"
        fi
        ;;
    esac
  done ) &
WATCHER=$!
trap 'kill $WATCHER 2>/dev/null' EXIT

exec "${CLOUDFLARED:-/home/echomind/bin/cloudflared}" tunnel --no-autoupdate --url "http://127.0.0.1:$PORT" >>"$LOG" 2>&1
