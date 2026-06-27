# Deploying Codebase Architect on the VPS

How Codebase Architect fits onto a shared VPS that already runs other
services, so the setup stays **stable** (survives reboots) and
**understandable** (one source of truth, no ad-hoc commands).

## Two network planes

The VPS has two ways in. Keep them separate and pick *one* per service.

| Plane | Address | Ingress | Use for |
|-------|---------|---------|---------|
| Internet | `eth0` public IP | **Traefik** on `:80`/`:443` by hostname | only what must be public |
| Tailnet | Tailscale IP (`100.x.y.z`) | **Tailscale Serve** (HTTPS on 443/8443/10000) or direct `IP:port` | everything private |

They coexist because Tailscale intercepts tailnet traffic in userspace
*before* it reaches Traefik's `0.0.0.0:443`. So a `tailscale serve` rule
shadows Traefik **only for the tailnet**, never for the public plane.

## Bind addresses — the rule that keeps it sane

A container's host bind decides who can reach it:

- `127.0.0.1:PORT` → host-only. Reachable on the tailnet **only** via a
  `tailscale serve` rule that proxies to it. *Default and safest.*
- `100.x.y.z:PORT` (Tailscale IP) → reachable directly at `IP:PORT` from any
  tailnet device, no Serve needed.
- `0.0.0.0:PORT` → **exposed to the public internet.** Use only deliberately.

Codebase Architect defaults to `127.0.0.1:47800` (see `docker-compose.yml`,
`BIND_ADDR`/`HOST_PORT`). Leave it host-only and publish it with Serve.

## Service / port map (fill in for your host)

Keep this table current — it is the human-readable index of the box.

| Service | Container | Host bind | Reached as |
|---------|-----------|-----------|------------|
| Codebase Architect | `gitarchitect-api-1` | `127.0.0.1:47800` | `https://<name>.ts.net:8443/` (Serve) |
| hermes (root) | _your hermes container_ | `…:8000` | `https://<name>.ts.net/` (Serve, root) |
| Traefik | `*-traefik-1` | `0.0.0.0:80,443` | public ingress by hostname |
| _add the rest…_ | | | |

## Tailnet routing is in version control

`tailscale serve` rules persist across reboots but live in tailscaled state,
not git. To make them reproducible, the desired state is encoded in
[`scripts/tailnet-serve.sh`](../scripts/tailnet-serve.sh). Edit the backends at
the top, then:

```bash
sudo ./scripts/tailnet-serve.sh        # idempotent: reset + reapply
tailscale serve status                 # verify
```

Target state:

```
https://<name>.ts.net          ->  hermes        (root, no port)
https://<name>.ts.net:8443     ->  Codebase Architect
```

If the root shows a 502, the hermes backend isn't listening on the address in
the rule. Check where it actually binds (`ss -tlnp | grep :8000`) and point the
script at that (e.g. the Tailscale IP instead of `127.0.0.1`).

## Architect lifecycle

```bash
cd GitArchitect
git pull origin master                 # get the latest
docker compose up -d --build           # (re)build and run, detached
docker compose logs -f api             # tail logs
docker compose down                    # stop
```

`restart: unless-stopped` is already set, so the container comes back after a
reboot. To scan a local project, mount it read-only (see the commented volume
in `docker-compose.yml`) and use its in-container path as the scan source.

## Reboot checklist

After `sudo reboot`, confirm the box came back clean:

```bash
docker ps                              # every expected container Up
tailscale serve status                 # both rules present (root + :8443)
curl -I http://127.0.0.1:47800/health  # architect healthy
```

If a `tailscale serve` rule is missing, just re-run `scripts/tailnet-serve.sh`.
