#!/usr/bin/env bash
#
# Publish the Hostinger-managed hermes dashboard on this host's Tailscale IP,
# WITHOUT modifying the Hostinger-managed container.
#
# hermes binds 0.0.0.0:4860 inside its own container (not published on the host).
# This runs a tiny socat forwarder container on hermes' docker network that
# publishes 4860 on the Tailscale IP and connects to hermes by name (stable
# across restarts). It survives reboots via --restart unless-stopped.
#
# Usage:   sudo ./scripts/hermes-tailnet.sh
#          sudo HERMES_CONTAINER=<name> ./scripts/hermes-tailnet.sh   # override
set -euo pipefail

HERMES_PORT="${HERMES_PORT:-4860}"
HERMES_IMAGE="ghcr.io/hostinger/hvps-hermes-agent"
HERMES_CONTAINER="${HERMES_CONTAINER:-}"

IP="$(tailscale ip -4 2>/dev/null | head -n1 || true)"
[[ -n "${IP}" ]] || { echo "!! no Tailscale IP (is tailscaled up?)" >&2; exit 1; }

# Auto-detect the hermes container if not given.
if [[ -z "${HERMES_CONTAINER}" ]]; then
  HERMES_CONTAINER="$(docker ps --filter "ancestor=${HERMES_IMAGE}:latest" \
    --format '{{.Names}}' | head -n1)"
fi
[[ -n "${HERMES_CONTAINER}" ]] || {
  echo "!! could not auto-detect hermes; set HERMES_CONTAINER=<name> (docker ps)" >&2
  exit 1
}

# First docker network the hermes container is attached to (for embedded DNS).
NET="$(docker inspect -f \
  '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' \
  "${HERMES_CONTAINER}" | awk '{print $1}')"
[[ -n "${NET}" ]] || { echo "!! could not read hermes' docker network" >&2; exit 1; }

echo ">> hermes container: ${HERMES_CONTAINER}  network: ${NET}"
docker rm -f hermes-tailnet >/dev/null 2>&1 || true
docker run -d --name hermes-tailnet --restart unless-stopped \
  --network "${NET}" \
  -p "${IP}:${HERMES_PORT}:${HERMES_PORT}" \
  alpine/socat \
  "tcp-listen:${HERMES_PORT},fork,reuseaddr" \
  "tcp-connect:${HERMES_CONTAINER}:${HERMES_PORT}"

echo ">> hermes now on  http://${IP}:${HERMES_PORT}/"
