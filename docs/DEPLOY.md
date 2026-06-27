# Deploying Codebase Architect on the VPS

Access model: **everything over the tailnet by `IP:port`.** Tailscale is the
only door into the VPS — no service is published to the public internet, and
there is no reverse proxy or `tailscale serve` in the path. Each service binds
to the host's Tailscale IP and is reached at `http://<tailscale-ip>:<port>/`.

This is the simplest model to keep **stable** (survives reboots, no proxy to
break) and **understandable** (one port map, one rule).

## The one rule: bind address decides exposure

A container's host bind decides who can reach it:

- `100.x.y.z:PORT` (the **Tailscale IP**) → reachable at `IP:PORT` from any
  device on the tailnet, and from nowhere else. **This is what we want.**
- `127.0.0.1:PORT` → host-only; not reachable from other tailnet devices.
- `0.0.0.0:PORT` → **exposed to the public internet.** Never use it here.

Find this host's Tailscale IP with `tailscale ip -4` (e.g. `100.83.238.95`).

## Service / port map

The human-readable index of the box. Keep it current.

| Service | Container | Host bind | URL |
|---------|-----------|-----------|-----|
| Codebase Architect | `gitarchitect-api-1` | `100.83.238.95:47800` | `http://100.83.238.95:47800/` |
| engramunified | _memory-api_ | `100.83.238.95:8000` | `http://100.83.238.95:8000/` |
| engram MCP | _memory-mcp_ | `100.83.238.95:8765` | `http://100.83.238.95:8765/` |
| n8n | `n8n-n8n-1` | `100.83.238.95:5678` | `http://100.83.238.95:5678/` |
| vikunja | `vikunja-1` | `100.83.238.95:32777` | `http://100.83.238.95:32777/` |
| mibaldiutils | `mibaldiutils-web-1` | `100.83.238.95:8088` | `http://100.83.238.95:8088/` |
| hermes (Hostinger) | `hermes-agent-*` | container `4860` (via forwarder) | `http://100.83.238.95:4860/` |
| postgres (engram) | `*-postgres-1` | `100.83.238.95:5432` | internal/tailnet only |

> hermes is the **Hostinger-managed** agent dashboard. It binds `0.0.0.0:4860`
> *inside its own container* (docker IP `172.19.0.2:4860`) and is also reachable
> via Hostinger's proxy at `srv1188691.hstgr.cloud`. We do **not** edit its
> compose (Hostinger would overwrite it) — see "Exposing hermes" below.

> Anything bound to `0.0.0.0` **on the host** (e.g. vikunja `0.0.0.0:32777`,
> Traefik `0.0.0.0:80/443`) is public — repoint it to the Tailscale IP or remove
> it. (A container's *internal* `0.0.0.0` bind, like hermes', is not host-public
> unless a `ports:` entry publishes it.)

## Exposing hermes on the tailnet (without touching Hostinger's container)

hermes' container does not publish `4860` on the host, and we can't edit its
compose. Instead run a tiny `socat` forwarder container that publishes `4860` on
the Tailscale IP and connects to hermes by name over its docker network (so it
keeps working across restarts):

```bash
sudo ./scripts/hermes-tailnet.sh        # -> http://100.83.238.95:4860/
```

It auto-detects the hermes container and its network; override with
`HERMES_CONTAINER=<name>` if detection fails (`docker ps` to find it). The
forwarder runs with `--restart unless-stopped`, so it survives reboots. Removing
it: `docker rm -f hermes-tailnet`.

## Putting a service on the Tailscale IP

For each service's compose file, change the published address from
`127.0.0.1`/`0.0.0.0` to the Tailscale IP:

```yaml
ports:
  - "100.83.238.95:5678:5678"   # was 127.0.0.1:5678 or 0.0.0.0:5678
```

then `docker compose up -d` that stack. For **Codebase Architect** this is a
one-liner via `.env` (no compose edit needed):

```bash
cd GitArchitect
echo 'BIND_ADDR=100.83.238.95' >> .env
docker compose up -d
# -> http://100.83.238.95:47800/
```

## Turn off Tailscale Serve (not used in this model)

If a previous setup added `tailscale serve` rules, clear them so routing isn't
ambiguous — everything is plain `IP:port` now:

```bash
tailscale serve reset
tailscale serve status        # should print nothing
```

## Lock the public edge

Tailscale is the only intended door, so drop public inbound at the firewall and
keep just what Tailscale needs (plus SSH if you don't use Tailscale SSH):

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 41641/udp      # Tailscale
sudo ufw allow 22/tcp         # SSH (omit if you use `tailscale ssh`)
sudo ufw enable
```

With every service bound to `100.x.y.z`, nothing answers on the public IP even
without ufw — but the firewall makes it explicit and catches mistakes.

## Architect lifecycle

```bash
cd GitArchitect
git pull origin master                 # latest
docker compose up -d --build           # (re)build and run, detached
docker compose logs -f api             # tail logs
docker compose down                    # stop
```

`restart: unless-stopped` is set, so it comes back after a reboot. To scan a
local project, mount it read-only (see the commented volume in
`docker-compose.yml`) and use its in-container path as the scan source.

## Reboot checklist

```bash
docker ps                                      # every container Up, bound to 100.x.y.z
tailscale ip -4                                # host still on the tailnet
curl -I http://100.83.238.95:47800/health      # architect healthy
```

`scripts/tailnet-access.sh` prints the Tailscale IP and the same port map for a
quick "what's where" at any time.
