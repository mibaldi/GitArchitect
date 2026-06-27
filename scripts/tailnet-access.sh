#!/usr/bin/env bash
#
# Access model: everything over the tailnet by IP:port. Tailscale is the only
# door; no reverse proxy and no `tailscale serve` in the path.
#
# This script is a read-only helper: it clears any stale `tailscale serve`
# rules (so routing stays unambiguous) and prints the host's Tailscale IP plus
# the documented service map, so you always know "what's where".
#
# Usage:   ./scripts/tailnet-access.sh
set -euo pipefail

# Service -> container port map. Edit to match this host.
# Format: "port  service"
SERVICES=(
  "47800  Codebase Architect"
  "8000   engramunified"
  "8765   engram MCP"
  "5678   n8n"
  "32777  vikunja"
  "8088   mibaldiutils"
  "4860   hermes (via scripts/hermes-tailnet.sh forwarder)"
)

IP="$(tailscale ip -4 2>/dev/null | head -n1 || true)"
if [[ -z "${IP}" ]]; then
  echo "!! could not read Tailscale IP (is tailscaled up?)" >&2
  exit 1
fi

# In this model we don't use Serve; clear leftover rules if any exist.
if tailscale serve status >/dev/null 2>&1; then
  tailscale serve reset >/dev/null 2>&1 || true
fi

echo "Tailscale IP: ${IP}"
echo
echo "Reach each service at http://${IP}:<port>/ :"
for entry in "${SERVICES[@]}"; do
  port="${entry%% *}"
  name="${entry#* }"
  name="${name#"${name%%[![:space:]]*}"}"   # ltrim
  printf "  http://%s:%-6s ->  %s\n" "${IP}" "${port}" "${name}"
done
