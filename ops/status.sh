#!/bin/bash
# One-glance status of the deployment: the API service, the local model and the public endpoint.
printf '  %-14s %s\n' "cios" "$(systemctl --user is-active cios 2>/dev/null) / $(systemctl --user is-enabled cios 2>/dev/null)"
if systemctl is-active --quiet ollama 2>/dev/null; then o="active (system service)";
elif pgrep -x ollama >/dev/null || pgrep -f "ollama serve" >/dev/null; then o="running (process)"; else o="not running"; fi
printf '  %-14s %s\n' "ollama" "$o"
H=$(curl -s -m 10 http://127.0.0.1:${PORT:-8899}/api/health)
printf '  %-14s %s\n' "local" "$( [ -n "$H" ] && echo "$H" | python3 -c 'import sys,json; d=json.load(sys.stdin); print("ok · model", d["llm"]["model"], "on", d["llm"].get("placement", "?").upper(), "· today", d["today"], "· ledger", "intact" if d["ledger"]["intact"] else "BROKEN"); d["llm"].get("placement") == "cpu" and print("  WARNING: the model is on the CPU (~30x slower). The Ollama container has lost GPU access - restart it: docker restart cios-ollama")' || echo down)"
if command -v tailscale >/dev/null 2>&1 && tailscale funnel status 2>/dev/null | grep -q "Funnel on"; then
  printf '  %-14s %s\n' "public" "$(tailscale funnel status 2>/dev/null | grep -m1 -o 'https://[^ ]*')  (Tailscale Funnel)"
elif [ -s "${STATE_DIR:-$HOME/.local/state/cios}/public_url" ]; then
  exec "$(dirname "$0")/url.sh"
else
  printf '  %-14s %s\n' "public" "none"
fi
