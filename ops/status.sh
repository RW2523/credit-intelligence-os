#!/bin/bash
# One-glance status of the three services behind the deployment.
for s in ollama cios cios-tunnel; do
  printf '  %-14s %s\n' "$s" "$(systemctl --user is-active $s) / $(systemctl --user is-enabled $s 2>/dev/null)"
done
printf '  %-14s ' "local"; curl -s -o /dev/null -w '%{http_code}\n' -m 10 http://127.0.0.1:8899/api/health
exec "$(dirname "$0")/url.sh"
