#!/usr/bin/env bash
#
# Access model: everything over the tailnet by IP:port. Tailscale is the only
# door; no reverse proxy and no `tailscale serve` in the path.
#
# Read-only helper: clears any stale `tailscale serve` rules, then prints this
# host's Tailscale IP and MagicDNS name plus the service map — and probes each
# port so you can see at a glance what is actually up.
#
# Usage:   ./scripts/tailnet-access.sh
set -euo pipefail

# Service -> host-published port. Edit to match this host.
# Format: "port  service".  (mariadb 3306 is container-internal only -> omitted.)
SERVICES=(
  "47800  Codebase Architect"
  "8000   engramunified"
  "8765   engram MCP"
  "5432   engram postgres"
  "5678   n8n"
  "32777  vikunja"
  "8088   mibaldiutils"
  "4860   hermes (forwarder)"
)

IP="$(tailscale ip -4 2>/dev/null | head -n1 || true)"
if [[ -z "${IP}" ]]; then
  echo "!! could not read Tailscale IP (is tailscaled up?)" >&2
  exit 1
fi

# MagicDNS name (best-effort; empty if unavailable).
NAME="$(tailscale status --json 2>/dev/null \
  | grep -m1 '"DNSName"' \
  | sed -E 's/.*"DNSName": *"([^"]+)".*/\1/; s/\.$//' || true)"

# In this model we don't use Serve; clear leftover rules if any exist.
if tailscale serve status >/dev/null 2>&1; then
  tailscale serve reset >/dev/null 2>&1 || true
fi

# Probe a TCP port (2s timeout). Echoes "up" / "down" without tripping set -e.
probe() {
  if timeout 2 bash -c "</dev/tcp/$1/$2" >/dev/null 2>&1; then
    echo "up"
  else
    echo "down"
  fi
}

host="${NAME:-${IP}}"
echo "Tailscale IP:   ${IP}"
[[ -n "${NAME}" ]] && echo "MagicDNS name:  ${NAME}"
echo
printf "%-22s %-6s %-5s %s\n" "SERVICE" "PORT" "STATE" "URL"
for entry in "${SERVICES[@]}"; do
  port="${entry%% *}"
  name="${entry#* }"
  name="${name#"${name%%[![:space:]]*}"}"   # ltrim
  state="$(probe "${IP}" "${port}")"
  printf "%-22s %-6s %-5s http://%s:%s/\n" "${name}" "${port}" "${state}" "${host}" "${port}"
done
