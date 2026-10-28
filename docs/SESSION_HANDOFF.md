# Session handoff

Written: 2026-10-27 (end of session 1, local). Overwrite at the end of every session, after push.

## State
- Gate G4. Repo `Silentarcherjr/eventproof-meta-hackathon-2026` (private). Tag `hackathon-start-2026-10-27` = 039c084.
- Commit identity: Anthony Morell <153972162+Silentarcherjr@users.noreply.github.com> (repo-local git config; set it again in fresh cloud clones). No assistant attribution trailers in commits.
- Done & verified: G1-03 (ac056a1, CI 40604985293), G0-03, G0-04, G1-04 (107d676, CI 40602048109), G0-02, G0-05, G1-02, G2-01, G2-02, G3-01, P1-01, G4-02 (frozen holdout_v2, c0c78de, CI run 40597330836). P0 11/27.
- G4-01 IN_PROGRESS: full loop works with the `baseline-deterministic` proposer + mock perception (one accepted, one rejected repair per counterexample, `benchmark/repairs/`). Missing: Muse Spark as proposer (same `RulePatch` JSON schema).
- Live Meta: WORKING. Key in `backend/.env` (local only). First SAM + Muse calls OK 2026-10-27 (`docs/evidence/2026-10-27_meta_api_smoke.md`). Raw SAM output cached in `artifacts/sam_cache/`.

## Next exact task
1. Done: SAM vs mock on 10 mock-failing cases (`benchmark/reports/2026-10-27_sam_vs_mock.json`): SAM fixes tailgate 5/5, abstains on occluded_station 5/5. Next for Challenge on SAM: search for scenes that fool SAM itself (harder families: tighter overlap, same-colour crossings, longer clips), each new case = 1 billed call, needs participant OK.
2. G1-06: frontend studio (upload, rule text, zone/line editor, overlay timeline) on top of `POST /runs`. A self-recorded phone video (G6-02, participant) would make the demo real-world.
3. G4-01 Muse part: `MuseProposer` returning `RulePatch` JSON, graded by the same `Grader`.
4. Never regenerate `benchmark/holdout/holdout_v2.json` in place.

## Human actions pending
- C-03: set a spend alert in the Meta Billing page and read the actual charge of the 2 smoke calls (for COSTS.md).
- C-02: post the 4 questions in Discord #questions.
- C-04: choose a license.
