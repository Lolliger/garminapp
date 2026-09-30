# Public HTTPS for the relay: Tailscale Funnel

The phone (ntfy buttons) and the watch (via the phone, HTTPS only) must reach the relay from the internet.
Tailscale Funnel does that without opening a router port. Source: Tailscale docs "Tailscale Funnel" and
"tailscale funnel command" (read 2026-09-30). Funnel is marked *beta* there.

## What Funnel needs (from the docs)
- Tailscale v1.38.3 or later on the machine that runs the relay.
- MagicDNS and HTTPS certificates enabled for your tailnet, and a `funnel` node attribute in the tailnet policy file.
  The first `tailscale funnel ...` run opens a web page asking you to approve; it then creates the certificates and adds
  the attribute (default target `autogroup:member`).
- Only ports 443, 8443, 10000; only TLS; only names under your `*.ts.net` tailnet domain.
- Traffic is subject to non-configurable bandwidth limits (irrelevant here, our messages are tiny).
- Public DNS for the new name can take up to 10 minutes to appear.
- Repeatedly requesting new certificates can hit Let's Encrypt rate limits (docs: up to a 34 hour wait). Do not reset/recreate needlessly.

## Steps
1. Install Tailscale on the relay machine and log in (`tailscale up`).
2. Start the relay locally (never bind it to a public interface, Funnel connects to localhost):
   ```bash
   uvicorn relay.app:create_app --factory --host 127.0.0.1 --port 8000
   ```
3. Publish it (the docs' example is `tailscale funnel 3000`, `--bg` = run as background process):
   ```bash
   tailscale funnel --bg 8000
   ```
   Approve in the browser page on first use. The output shows `https://<machine>.<tailnet>.ts.net`
   with `|-- / proxy http://127.0.0.1:8000`.
4. Check: `tailscale funnel status` (add `--json` for machine-readable), then from any network (e.g. phone on mobile data):
   ```bash
   curl https://<machine>.<tailnet>.ts.net/health        # {"ok":true}
   curl -i https://<machine>.<tailnet>.ts.net/pending    # 401 without token = protected
   ```
5. In `.env`: `PUBLIC_URL=https://<machine>.<tailnet>.ts.net` (ntfy links, watch app).
   The hook can keep `RELAY_URL=http://127.0.0.1:8000` if it runs on the same machine as the relay,
   otherwise use the public URL.
6. Turn off: `tailscale funnel --bg 8000 off` (for `off`, the original flags are required, the target is optional)
   or `tailscale funnel reset` to clear the whole Funnel configuration.

## Security notes
- Funnel makes the whole relay reachable by anyone who knows the URL. Protection: every endpoint except
  `/health` and `/a/...` needs `RELAY_TOKEN` (32+ random chars); `/a/...` needs a valid HMAC signature.
  Keep `RELAY_TOKEN` and `LINK_SECRET` only in `.env`, and do not share the Funnel URL.
- Funnel relay servers cannot decrypt the traffic (TLS is terminated on your machine, per the docs).
- The Funnel process/`--bg` config must be running whenever you want remote answers; the docs I read do not say
  whether it survives a reboot, so check `tailscale funnel status` after restarting the machine.

## Not covered by these docs (verify yourself)
- Funnel request timeouts: not documented on the pages I read. The relay's long poll is capped at 55 s
  (`/wait`), and the hook re-polls, so it should be fine; the watch will use short requests.
- Alternative if Funnel does not work for you: Cloudflare Tunnel (needs a domain on Cloudflare; its docs are
  currently blocked in this sandbox, so no guide is written yet).
