# Session handoff

Written: 2026-10-27 (end of session 1, local). Overwrite at the end of every session, after push.

## State
- Gate G4. Repo `Silentarcherjr/eventproof-meta-hackathon-2026` (private). Tag `hackathon-start-2026-10-27` = 039c084.
- Commit identity: Anthony Morell <153972162+Silentarcherjr@users.noreply.github.com> (repo-local git config; set it again in fresh cloud clones). No assistant attribution trailers in commits.
- Done & verified: G2-03, G4-01 (a15ece1, CI 40623377551), G1-06 (608f707, CI 40620125624), G1-01, G1-05 (69a8890, CI 40618714010), G1-03 (ac056a1, CI 40604985293), G0-03, G0-04, G1-04 (107d676, CI 40602048109), G0-02, G0-05, G1-02, G2-01, G2-02, G3-01, P1-01, G4-02 (frozen holdout_v2, c0c78de, CI run 40597330836). P0 16/27.
- G4-01 DONE: Muse Spark proposes RulePatch repairs (3 rounds, visible dev feedback only); 2 of 8 accepted on holdout_v2 (144→166, 144→164), 6 rejected. Baseline proposer kept for comparison.
- Live Meta: WORKING. Key in `backend/.env` (local only). First SAM + Muse calls OK 2026-10-27 (`docs/evidence/2026-10-27_meta_api_smoke.md`). Raw SAM output cached in `artifacts/sam_cache/`.

## Next exact task
1. G5-02 + G6-01: Dockerfile/compose (backend with ffmpeg + frontend) and a deployed demo URL (human decides hosting/spend).
2. G5-01: before/after metrics view polish (non-technical 60-second read); P1-04 baselines/ablations table from real runs.
3. G6-02 (participant): 2–3 self-recorded phone clips of boxes passing a marked zone, for a real-world run.
4. G7-01: 3-minute demo script around Build → Break (counterexample) → SAM confirm → Muse repair → holdout verification.
5. Never regenerate `benchmark/holdout/holdout_v2.json` in place.

Run locally: backend `cd backend && EVENTPROOF_MAX_LIVE_SAM_CALLS=2 uv run uvicorn eventproof.api.main:app`; studio `cd frontend && npm run dev`.

## Human actions pending
- C-03: set a spend alert in the Meta Billing page and read the actual charge of the 2 smoke calls (for COSTS.md).
- C-02: post the 4 questions in Discord #questions.
- C-04: choose a license.
