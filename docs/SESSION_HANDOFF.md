# Session handoff

Written: 2026-10-27 (end of session 1, local). Overwrite at the end of every session, after push.

## State
- Gate G0/G2. Repo `Silentarcherjr/eventproof-meta-hackathon-2026` (private). Tag `hackathon-start-2026-10-27` = 039c084. HEAD green on CI.
- Commit identity: Anthony Morell <153972162+Silentarcherjr@users.noreply.github.com> (repo-local git config; set it again in fresh cloud clones). No assistant attribution trailers in commits.
- Done & verified: G0-02 repo, G0-05 CI, G1-02 DSL + evaluator, G2-01 renderer, G2-02 adversarial families + mock perception + runner (801df32), G3-01 + P1-01 minimizer and side-by-side replay (24f5f40).
- Live Meta: BLOCKED until the participant receives credits / `MODEL_API_KEY` (requested, not yet granted).

## Next exact task
1. G4-02: frozen holdout — separate seed range per family (e.g. 10_000+), generated + hashed into `benchmark/holdout_manifest.json` BEFORE any repair; a test asserts the repair code path cannot import/read it.
2. G4-01 (mock until Muse): repair loop — candidate repairs are DSL/param edits (dwell_ms, max_gap_frames, add IN_ZONE min_frames, anchor); accept only if they fix the counterexample AND do not regress on the holdout. Muse Spark proposes edits once the key arrives; until then a deterministic baseline proposer, clearly labelled.
3. G1-04: SAM 3.1 adapter against fixtures (wire format `<Nf>id<|box;...|>`), so the whole harness switches from mock to SAM the day the key arrives.

## Human actions pending
- C-03: Meta credits / key (requested). Put key in `backend/.env` when received.
- C-02: post the 4 questions in Discord #questions.
