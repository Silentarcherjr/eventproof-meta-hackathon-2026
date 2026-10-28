# Docker compose — reproducible stack (G5-02) — 2026-10-28

Commit ba982f7. Local host: macOS arm64, Colima (Docker 29.5.2, Compose 5.5.1).

## Reproducibility
- Base images pinned by digest: `python:3.12-slim-bookworm@sha256:e697c818…`, `node:22-bookworm-slim@sha256:4b150b48…`,
  `ghcr.io/astral-sh/uv:0.12.10@sha256:2bb3ebca…`. Python deps `uv sync --frozen` from `uv.lock`; Node deps `npm ci`.
  Remaining non-pinned input: Debian apt `ffmpeg` (bookworm security updates).
- Both containers run as non-root; healthchecks on `/health` and `/`. The studio proxies `/api/*` to the backend
  (one origin; proxy timeout raised to 300 s for live runs and Muse repairs).

## Fresh clone (no `artifacts/`, no `.env`)
`git clone` into an empty folder → `docker compose up --build --wait`: backend and studio healthy in ~70 s
(base layers already pulled). `GET /api/health` → `meta_api_key_configured:false`; upload → **503** "MODEL_API_KEY is
not set; live Meta calls are BLOCKED"; a .txt upload → 415. The named volume is writable by the container user.

## Full flow through the containers, 0 Meta calls
Stack started with the local caches bound (`EVENTPROOF_ARTIFACTS=./artifacts`), `MODEL_API_KEY` forced empty and
`EVENTPROOF_MAX_LIVE_SAM_CALLS=0`, so any cache miss would have failed instead of spending.
- `POST /api/runs` with the inputs of run `20261028T023754Z-a922b5bb` → run `20261028T143421Z-44c23111`, completed,
  Muse rule and SAM tracks both `cached: true`, verdict FAIL (same as the original run).
- Challenge → 44 failures, counterexample `drive_through` spec error (same as before); `side_by_side.mp4` 200;
  video Range request 206.
- Baseline repair → "DWELL ≥ 2.00 s" rejected, "still ≤ 0.05/s, ≥ 0.80 s" accepted, holdout 166/200 (same as local).
- SAM confirm → served from cache, `live_sam_calls: 0`, still fails with SAM.
- Studio UI (browser) uploaded the clip and showed the FAIL verdict, overlay and timeline.

Memory: idle backend 63 MB, studio 38 MB; backend peak 266 MB during Challenge + Repair. Images: backend 1.16 GB, studio 458 MB.
CI: new `docker` job builds the compose stack on ubuntu and checks both healthchecks.
