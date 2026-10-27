# Session handoff

Written: 2026-10-27 (end of session 1, local). Overwrite at the end of every session, after push.

## State
- Gate G4. Repo `Silentarcherjr/eventproof-meta-hackathon-2026` (private). Tag `hackathon-start-2026-10-27` = 039c084.
- Commit identity: Anthony Morell <153972162+Silentarcherjr@users.noreply.github.com> (repo-local git config; set it again in fresh cloud clones). No assistant attribution trailers in commits.
- Done & verified: G0-02, G0-05, G1-02, G2-01, G2-02, G3-01, P1-01, G4-02 (frozen holdout_v2, c0c78de, CI run 40597330836). P0 7/27.
- G4-01 IN_PROGRESS: full loop works with the `baseline-deterministic` proposer + mock perception (one accepted, one rejected repair per counterexample, `benchmark/repairs/`). Missing: Muse Spark as proposer (same `RulePatch` JSON schema).
- Live Meta: credits available per participant; key not yet in `backend/.env` on this machine. SAM adapter ready (G1-04 fixtures done).

## Next exact task
1. G1-04 live part (needs `MODEL_API_KEY` in `backend/.env`): render one canonical clip and run `uv run python ../scripts/check_meta_api.py sam --video <clip.mp4> --prompt "blue box"` (1 call, >= 50 frames billed). If the strict parser fails, the real format differs from the docs: fix the parser + add the real line as a fixture. Then G0-03 (Muse smoke) and G0-04 (SAM smoke) evidence in `docs/evidence/`.
2. Run Challenge Mode on SAM with a small allowance (e.g. `runner --perception sam --families tailgate,occluded_station --seeds 0-4 --max-live-calls 10`) and compare with mock.
3. G4-01 Muse part: `MuseProposer` returning `RulePatch` JSON; G1-03 Muse rule → DSL (depth-bounded schema).
4. Never regenerate `benchmark/holdout/holdout_v2.json` in place; a new holdout gets a new name and seed range.

## Human actions pending
- C-03: credits claimed per participant. Put `MODEL_API_KEY=...` in `backend/.env` (gitignored) and set a spend alert.
- C-02: post the 4 questions in Discord #questions.
- C-04: choose a license.
