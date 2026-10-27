# Session handoff

Written: 2026-10-27 (end of session 1, local). Overwrite at the end of every session, after push.

## State
- Gate G4. Repo `Silentarcherjr/eventproof-meta-hackathon-2026` (private). Tag `hackathon-start-2026-10-27` = 039c084.
- Commit identity: Anthony Morell <153972162+Silentarcherjr@users.noreply.github.com> (repo-local git config; set it again in fresh cloud clones). No assistant attribution trailers in commits.
- Done & verified: G0-02, G0-05, G1-02, G2-01, G2-02, G3-01, P1-01, G4-02 (frozen holdout).
- G4-01 IN_PROGRESS: full loop works with the `baseline-deterministic` proposer + mock perception (one accepted, one rejected repair per counterexample, `benchmark/repairs/`). Missing: Muse Spark as proposer (same `RulePatch` JSON schema).
- Live Meta: BLOCKED until the participant receives credits / `MODEL_API_KEY`.

## Next exact task
1. G1-04: SAM 3.1 adapter against fixtures (wire format `<Nf>id<|box;...|>`), so the harness switches from mock to SAM the day the key arrives. Installing `meta-sam-parser` needs participant OK.
2. G4-01 (Muse part) once the key exists: `MuseProposer` implementing `Proposer`, prompt = `RepairContext` JSON, `response_format` = `RulePatch` JSON schema; grade with the same `Grader`.
3. Perception-error repairs (occluded_station, tailgate) are out of reach for rule patches: candidate = bounded track-stitching filter (ID association), graded on the same holdout. P1, only if time.
4. Never regenerate `benchmark/holdout/holdout_v1.json` in place; a new holdout gets a new name and seed range.

## Human actions pending
- C-03: Meta credits / key (requested). Put key in `backend/.env` when received.
- C-02: post the 4 questions in Discord #questions.
- C-04: choose a license.
