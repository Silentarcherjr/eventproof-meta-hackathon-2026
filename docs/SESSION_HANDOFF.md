# Session handoff

Written: 2026-10-28 ~10:45 Panama (session 1 cont., local). Overwrite at the end of every session, after push.

## State
- Repo `Silentarcherjr/eventproof-meta-hackathon-2026` (private). HEAD 11fb83d + docs commit; CI run 40717424645 green
  (backend 221 tests, frontend lint/tsc/4 Playwright, docker, tracker). P0 19/27, P1 3/7.
- Commit identity: Anthony Morell <153972162+Silentarcherjr@users.noreply.github.com>. No assistant attribution in commits or files.
- Product loop complete and verified: Build (Muse Spark → DSL, SAM 3.1 → tracks) → Break (Challenge Mode, SAM confirm) →
  Repair (Muse Spark, graded on hidden holdout_v2) → Before/after view → final_v1 independent test → evidence ledger.
- Demo run: `20261028T023754Z-a922b5bb` (open with `/?run=<id>`; committed copy in docs/evidence/runs/, full copy with video in
  artifacts/runs/ — gitignored; `deploy/export_showcase.sh` packages it).
- Three data tiers: dev seeds 0–29 (search + proposers), holdout_v2 20000–20039 (grader accept/reject), final_v1 40000–40039 +
  3 shift families (report-only, pre-registered, evaluated once). Never regenerate a frozen manifest in place.
- Live Meta calls need allowances everywhere: API env `EVENTPROOF_MAX_LIVE_MUSE_CALLS` / `EVENTPROOF_MAX_LIVE_SAM_CALLS`
  (default 0), CLI flags `--max-live-calls`, real-video `--max-live-*-calls`. Key only in `backend/.env` (local).

## Next exact task (no human decision needed)
1. P1-07 done 2026-11-01 (80 live SAM calls on final_v1 subset, `benchmark/final/sam_v1/`); mark DONE_VERIFIED once CI is
   green; ask the participant to re-read Billing for the exact charge.
2. P1-02: studio interaction polish (object select, synced scrub between timeline and before/after chart).
3. Keep PROGRESS/TASKS/HANDOFF/COSTS in sync after every change (`python scripts/progress.py render`).

## Waiting on the participant
- G6-02: record 2–3 clips per `docs/REAL_VIDEO_PROTOCOL.md`, label blind, `check --freeze`; approve ~1 Muse + 1 SAM call per clip.
- G7-01: record the 3-minute video from `docs/DEMO_SCRIPT.md` (every number sourced); add section 5b only with real-clip results.
- G6-01: approve a host (options/prices in `docs/DEPLOY_PROPOSAL.md`; runbook `deploy/README.md`). No infrastructure without approval.
- C-03 spend alert + read Billing; C-02 Discord questions; C-04 license; repo visibility (only after approval + audit).

## Run
`docker compose up --build` (studio :3000, API :8000; `EVENTPROOF_ARTIFACTS=./artifacts` reuses local caches).
Without Docker: `cd backend && EVENTPROOF_MAX_LIVE_SAM_CALLS=0 EVENTPROOF_MAX_LIVE_MUSE_CALLS=0 uv run uvicorn eventproof.api.main:app`;
`cd frontend && npm run dev`. Known nit: a run aborted by a Meta error leaves a run folder with only video.mp4.
