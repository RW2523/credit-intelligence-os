#!/bin/bash
# Credit Intelligence OS — one-command local launcher (macOS)
set -e
cd "$(dirname "$0")"
PORT="${PORT:-8899}"

if [ ! -d .venv ]; then
  echo "▸ creating python environment…"
  python3 -m venv .venv
  ./.venv/bin/pip -q install --upgrade pip
  ./.venv/bin/pip -q install fastapi "uvicorn[standard]" numpy scikit-learn httpx python-multipart pypdf
fi

# local model (optional — the platform degrades to deterministic agents without it)
if command -v ollama >/dev/null 2>&1; then
  pgrep -qx ollama || (ollama serve >/tmp/cios-ollama.log 2>&1 &)
  sleep 1
  if ! ollama list 2>/dev/null | grep -q "${CIOS_MODEL:-llama3.2:3b}"; then
    echo "▸ pulling small local model ${CIOS_MODEL:-llama3.2:3b} (one time, ~2 GB)…"
    ollama pull "${CIOS_MODEL:-llama3.2:3b}" || true
  fi
fi

if [ "${CIOS_RESET:-0}" = "1" ]; then
  echo "▸ resetting demo state…"
  rm -f data/cios.db
fi

echo "▸ Credit Intelligence OS → http://127.0.0.1:$PORT"
( sleep 3; open "http://127.0.0.1:$PORT" >/dev/null 2>&1 || true ) &
exec ./.venv/bin/python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port "$PORT"
