#!/usr/bin/env bash
#
# Source of truth for how this VPS exposes services on the Tailscale tailnet.
#
# `tailscale serve` rules persist across reboots, but they live in tailscaled's
# state, not in version control. This script makes that config reproducible:
# it is idempotent (resets first, then reapplies), so re-running it reconciles
# the tailnet routing to exactly what is written here.
#
# Usage:   sudo ./scripts/tailnet-serve.sh
#
# Tailscale Serve only issues valid HTTPS on ports 443, 8443 and 10000.
set -euo pipefail

# --- Edit these to match the host, then run the script ----------------------
# Root of the tailnet name (no port). Point it at whatever should answer there.
HERMES_BACKEND="http://127.0.0.1:8000"
# Codebase Architect (container binds 127.0.0.1:47800 by default).
ARCHITECT_BACKEND="http://127.0.0.1:47800"
ARCHITECT_PORT=8443
# ---------------------------------------------------------------------------

echo ">> resetting existing serve rules"
tailscale serve reset

echo ">> root (https://<name>.ts.net/) -> ${HERMES_BACKEND}"
tailscale serve --bg --https=443 "${HERMES_BACKEND}"

echo ">> architect (https://<name>.ts.net:${ARCHITECT_PORT}/) -> ${ARCHITECT_BACKEND}"
tailscale serve --bg --https="${ARCHITECT_PORT}" "${ARCHITECT_BACKEND}"

echo
echo ">> current state:"
tailscale serve status
