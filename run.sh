#!/bin/bash
# Credit Intelligence OS — one-command local launcher (Linux / macOS)
set -e
cd "$(dirname "$0")"
PORT="${PORT:-8899}"
HOST="${HOST:-127.0.0.1}"

# Pick an interpreter that has ready-built wheels for this platform.
PYBIN="${PYTHON:-}"
if [ -z "$PYBIN" ]; then
  for c in python3.12 python3.11 python3.13 python3; do
    command -v "$c" >/dev/null 2>&1 && PYBIN="$(command -v $c)" && break
  done
fi
[ -n "$PYBIN" ] || { echo "no python3 found"; exit 1; }

if [ ! -d .venv ]; then
  echo "▸ creating python environment ($PYBIN)…"
  "$PYBIN" -m venv .venv
  ./.venv/bin/pip -q install --upgrade pip
  ./.venv/bin/pip -q install fastapi "uvicorn[standard]" numpy scikit-learn httpx python-multipart pypdf
fi

# local model (optional — the platform degrades to deterministic agents without it)
if command -v ollama >/dev/null 2>&1; then
  # systemd-managed on most Linux installs; fall back to a bare daemon otherwise
  if ! curl -sf -m 2 "${OLLAMA_HOST:-http://127.0.0.1:11434}/api/tags" >/dev/null 2>&1; then
    systemctl start ollama 2>/dev/null || (nohup ollama serve >/tmp/cios-ollama.log 2>&1 &)
    sleep 2
  fi
  WANT="${CIOS_MODEL:-llama3.2:3b}"
  # match on the base name — a host holding llama3.2:latest already satisfies llama3.2:3b
  if ! ollama list 2>/dev/null | awk '{print $1}' | grep -q "^${WANT%%:*}:"; then
    echo "▸ pulling small local model $WANT (one time, ~2 GB)…"
    ollama pull "$WANT" || true
  fi
fi

if [ "${CIOS_RESET:-0}" = "1" ]; then
  echo "▸ resetting demo state…"
  rm -f data/cios.db
fi

echo "▸ Credit Intelligence OS → http://$HOST:$PORT"
if [ "${CIOS_OPEN:-1}" = "1" ]; then
  ( sleep 3
    URL="http://127.0.0.1:$PORT"
    if command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL"
    elif command -v open >/dev/null 2>&1; then open "$URL"
    fi >/dev/null 2>&1 || true ) &
fi
exec ./.venv/bin/python -m uvicorn main:app --app-dir backend --host "$HOST" --port "$PORT"
