#!/bin/bash
# Tokens per second and first-token latency for the configured models on this machine.
# Requests the same context as the app (CIOS_NUM_CTX; unset = the server default) so it never forces a reload mid-demo.
H="${OLLAMA_HOST:-http://127.0.0.1:11434}"
for M in "${@:-qwen3:30b-a3b-instruct-2507-q4_K_M llama3.2:3b}"; do for m in $M; do
  curl -s "$H/api/generate" -d "{\"model\":\"$m\",\"prompt\":\"Terangkan potongan gaji Biro ANGKASA dalam tiga ayat.\",\"stream\":false,\"keep_alive\":\"4h\"${CIOS_NUM_CTX:+,\"options\":{\"num_ctx\":$CIOS_NUM_CTX}}}" |
  python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d['model']:40} load {d.get('load_duration',0)/1e9:5.1f}s  first-token {d.get('prompt_eval_duration',0)/1e9:5.2f}s  {d['eval_count']/(d['eval_duration']/1e9):5.1f} tok/s\")"
done; done
