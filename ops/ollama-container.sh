#!/bin/bash
# The shared Ollama container, created so it keeps the GPU across systemd reloads.
#
#   ops/ollama-container.sh --check   report whether the GPU fix is in place and the GPU is reachable
#   ops/ollama-container.sh           (re)create the container with the fix; rolls back if anything fails
#
# Why: Docker here uses the systemd cgroup driver on cgroup v2. `--gpus all` injects the NVIDIA device nodes
# through a runtime hook, outside the container's declared device list, so systemd's device allow-list for the
# container never includes them. Any `systemctl daemon-reload` — snapd runs one on every snap refresh — makes
# systemd re-apply that list, and the container loses /dev/nvidia*: `nvidia-smi` inside it fails with
# "Failed to initialize NVML: Unknown Error" and every model Ollama starts afterwards runs on the CPU (~30x
# slower). Declaring the device nodes with --device puts them in the allow-list, so a reload keeps them.
# (NVIDIA Container Toolkit docs: "Containers losing access to GPUs with error: Failed to initialize NVML".)
# Host-wide alternatives, both needing root: Docker's cgroupfs driver, or CDI device injection.
set -uo pipefail
NAME="${OLLAMA_CONTAINER:-cios-ollama}"
IMAGE="${OLLAMA_IMAGE:-ollama/ollama:latest}"
VOLUME="${OLLAMA_VOLUME:-cios_ollama}"
PUBLISH="${OLLAMA_PUBLISH:-127.0.0.1:11434:11434}"
URL="${OLLAMA_HOST:-http://127.0.0.1:11434}"

devices() {                       # every NVIDIA control and GPU node present on this host
  local d
  for d in /dev/nvidiactl /dev/nvidia-modeset /dev/nvidia-uvm /dev/nvidia-uvm-tools /dev/nvidia[0-9]*; do
    [ -c "$d" ] && printf -- '--device=%s:%s\n' "$d" "$d"
  done
}

check() {                         # 0 = fix in place and GPU reachable
  local id ok=0
  id=$(docker inspect "$NAME" --format '{{.Id}}' 2>/dev/null) || { echo "  container $NAME: missing"; return 1; }
  local allow; allow=$(systemctl show "docker-$id.scope" -p DeviceAllow 2>/dev/null)
  if echo "$allow" | grep -qE "/dev/char/195:|/dev/nvidia"; then
    echo "  device allow-list: NVIDIA devices declared — survives systemd reloads"
  else
    echo "  device allow-list: NVIDIA devices NOT declared — the next systemd reload will drop the GPU"; ok=1
  fi
  if docker exec "$NAME" nvidia-smi -L >/dev/null 2>&1; then
    echo "  GPU inside container: $(docker exec "$NAME" nvidia-smi -L 2>/dev/null | head -1)"
  else
    echo "  GPU inside container: NOT reachable ($(docker exec "$NAME" nvidia-smi -L 2>&1 | head -1))"; ok=1
  fi
  return $ok
}

if [ "${1:-}" = "--check" ]; then check; exit $?; fi

mapfile -t DEV < <(devices)
[ "${#DEV[@]}" -gt 0 ] || { echo "no NVIDIA device nodes found on this host"; exit 1; }
echo "devices: ${DEV[*]}"

had_old=0
if docker inspect "$NAME" >/dev/null 2>&1; then
  had_old=1
  docker rm -f "$NAME-previous" >/dev/null 2>&1
  docker stop "$NAME" >/dev/null && docker rename "$NAME" "$NAME-previous" || { echo "could not stop $NAME"; exit 1; }
fi

rollback() {
  echo "FAILED — rolling back"
  docker rm -f "$NAME" >/dev/null 2>&1
  if [ $had_old = 1 ]; then docker rename "$NAME-previous" "$NAME" && docker start "$NAME" >/dev/null; fi
  exit 1
}

docker run -d --name "$NAME" --restart unless-stopped --gpus all "${DEV[@]}" \
  -p "$PUBLISH" -v "$VOLUME:/root/.ollama" "$IMAGE" >/dev/null || rollback
for _ in $(seq 1 60); do curl -sf -m 2 "$URL/api/tags" >/dev/null && break; sleep 1; done
curl -sf -m 5 "$URL/api/tags" >/dev/null || rollback
check || rollback
[ $had_old = 1 ] && docker rm "$NAME-previous" >/dev/null
echo "OK — $NAME recreated with persistent GPU access (models kept in volume $VOLUME)"
