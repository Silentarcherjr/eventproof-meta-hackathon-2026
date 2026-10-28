# Deploy proposal (G6-01) — 2026-10-28

Status: **proposal, nothing deployed.** Hosting choice and spend are a human decision (AGENTS.md).
Update 2026-10-28: the guards below are implemented and the Showcase stack is verified locally — see `deploy/README.md`.

## What has to run
The two containers from `compose.yaml` (G5-02): `backend` (FastAPI + ffmpeg, image 1.16 GB) and `studio` (Next.js
standalone, 458 MB; it proxies `/api/*` to the backend, so the public surface is one origin). Measured on the local
stack: idle 63 MB + 38 MB RAM; backend peak 266 MB during Challenge + baseline Repair. Runs and model caches need
a persistent disk (a few MB per run).

## The real cost risk is Meta credits, not hosting
Implemented: process-wide allowances for both models (`EVENTPROOF_MAX_LIVE_MUSE_CALLS`, `EVENTPROOF_MAX_LIVE_SAM_CALLS`,
default 0), `EVENTPROOF_MODE=showcase` (no uploads, allowances forced to 0), per-IP rate limit, one heavy job at a time.
Before any public URL, one of these modes must be chosen:

| Mode | What a visitor can do | Meta credits at risk |
|---|---|---|
| **Showcase** (no key on the server) | Open pre-loaded demo runs (cached Muse + SAM outputs), run Challenge Mode and baseline Repair (free, deterministic), see the cached Muse repair and its holdout verdict | **0** |
| **Capped live** (key on the server) | All of the above + new uploads/rules: Muse compiles live, SAM live up to a cap | bounded by new caps: per-process Muse and SAM call limits, per-IP rate limit, one heavy job at a time |
| Judges-only live | Capped live behind a shared password given in the submission | as capped live, but only judges |

Showcase is ready (`deploy/compose.showcase.yaml`, `deploy/export_showcase.sh`). A live mode only needs the participant to
choose the allowances and set the Meta spend alert first.

## Hosting options (prices read 2026-10-28 from the providers' pages; excl. VAT)

| Option | Plan | Price | Fit |
|---|---|---|---|
| **A. One VM + this compose + Caddy (HTTPS)** | DigitalOcean Basic 2 GB / 1 vCPU, NYC | $12/mo ($0.01786/h, capped at the monthly price) | Same stack as tested locally; disk included; full control. Needs SSH setup and OS updates. |
| A'. Same, cheaper | DigitalOcean 1 GB ($6/mo) or Hetzner CPX02 1 GB, EU (€6.49/mo incl. IPv4) | $6–7/mo | Enough for measured RAM; little headroom for ffmpeg re-encoding of large uploads. Hetzner US plans start at €17.99. |
| B. Fly.io | 2 × shared-cpu-1x 1 GB + 1 GB volume | ≈ $13.55/mo (per-second billing, no free tier) | Managed TLS and deploys from the Dockerfiles; two apps to wire (private network). |
| C. Render | 2 × Starter (512 MB) + disk | ≈ $14/mo + $0.25/GB disk | Managed; Free tier unsuitable (spins down after 15 min, ~1 min cold start, no persistent disk). |

Hosting from now until ~2026-12-31 (judging): A ≈ $24, A' ≈ $12–14, B ≈ $27, C ≈ $28+. A domain is optional
(Caddy can get a certificate for an `sslip.io` hostname of the server IP).

## Recommendation
**Option A (DigitalOcean 2 GB, ~$12/mo) in Showcase mode first**, then switch on capped live mode for the demo
recording and judging if you want visitors to upload their own clips. Reasons: it runs the exact compose verified
in CI, the 2 GB gives headroom for re-encoding, and Showcase mode guarantees zero Meta spend from strangers.

## What you would do vs. what I would do
- You: create the hosting account and payment method, create the server (or an API token for it), decide the
  mode, and set the spend alert in the Meta dashboard (C-03).
- I (done): caps, rate limit, showcase mode, `deploy/` (Caddyfile, override, export script, runbook).
- I (after approval): the deploy over SSH once you give access, and the healthcheck evidence for G6-01.

Sources: digitalocean.com/pricing/droplets, hetzner.com/cloud/regular-performance, docs.fly.io/about/pricing,
render.com/docs/free; Render Starter/disk prices from secondary sources (official table did not load) — confirm before choosing C.
