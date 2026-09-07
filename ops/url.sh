#!/bin/bash
# Print the current public URL (and whether it is actually serving).
U=$(cat "${STATE_DIR:-$HOME/.local/state/cios}/public_url" 2>/dev/null)
[ -n "$U" ] || { echo "no public URL yet — is cios-tunnel running? (systemctl --user status cios-tunnel)"; exit 1; }
CODE=$(curl -s -o /dev/null -w '%{http_code}' -m 20 "$U/api/health")
echo "$U   [health HTTP $CODE]"
