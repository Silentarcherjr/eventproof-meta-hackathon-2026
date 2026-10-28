# Deploying the showcase (prepared, NOT deployed)

Nothing here has been run on a server. Choosing a host and paying for it is the participant's decision
(`docs/DEPLOY_PROPOSAL.md`). Everything below was verified locally with the same files (2026-10-28):
`EVENTPROOF_DOMAIN=:80 docker compose -f compose.yaml -f deploy/compose.showcase.yaml up -d --build`.

## What a visitor can and cannot do
- Opens the recorded demo run automatically (real Muse Spark and SAM 3.1 outputs, served from their cache).
- Can run Challenge Mode, the baseline repair, the Muse repair (cached rounds only) and SAM confirm (cached only).
- Cannot upload (403), cannot trigger any live Meta call: the server has no key and both allowances are 0.
- Rate limit 20 POST requests per 10 minutes per visitor, one heavy job at a time (429 otherwise).
- Caddy: automatic HTTPS, 1 MB request bodies, `X-Frame-Options DENY`, no `Server` header; optional password.

Verified locally: `/api/health` reports `mode: showcase`, `meta_api_key_configured: false`, live calls remaining 0/0;
upload → 403; Muse repair → 2 of 8 accepted, all 3 rounds `cached: true`; SAM confirm from cache; rate limit → 429 after
20 POSTs; a forged `X-Forwarded-For` does not reset it (Caddy overwrites it).

## Steps (after the participant approves a host)
1. On this machine: `deploy/export_showcase.sh` → `showcase-data.tgz` (runs + caches only; never `backend/.env`).
2. Server (Ubuntu 24.04, 1–2 GB RAM): install Docker Engine + compose plugin from Docker's apt repository.
3. Copy the repo (the repo is private: use a read-only deploy key, or `git archive` + scp) and `showcase-data.tgz`.
4. `mkdir -p showcase-data && tar -xzf showcase-data.tgz -C showcase-data && sudo chown -R 10001 showcase-data`
   (10001 = the backend container user; Challenge writes its outputs into the run folder).
5. Point a DNS name at the server (or use `<ip>.sslip.io`), open ports 80/443 only.
6. `EVENTPROOF_DOMAIN=demo.example.com docker compose -f compose.yaml -f deploy/compose.showcase.yaml up -d --build`
7. Evidence for G6-01: `curl -fsS https://demo.example.com/api/health` (mode showcase, key false) + screenshot.

Do not copy `backend/.env` to the server. To give judges live uploads later, that is a separate decision with its own
allowances (`EVENTPROOF_MAX_LIVE_MUSE_CALLS`, `EVENTPROOF_MAX_LIVE_SAM_CALLS`) and a spend alert set first.
