# Session handoff

Written: 2026-10-27 (end of session 1, local). Overwrite at the end of every session, after push.

## State
- Gate G0/G2. Repo `Silentarcherjr/eventproof-meta-hackathon-2026` (private). Tag `hackathon-start-2026-10-27` = 039c084. HEAD green on CI.
- Commit identity: Anthony Morell <153972162+Silentarcherjr@users.noreply.github.com> (repo-local git config; set it again in fresh cloud clones). No assistant attribution trailers in commits.
- Done & verified: G0-02 repo, G0-05 CI, G1-02 DSL + evaluator, G2-01 renderer, G2-02 adversarial families + mock perception + runner (801df32).
- Live Meta: BLOCKED until the participant receives credits / `MODEL_API_KEY` (requested, not yet granted).

## Next exact task
1. G3-01: counterexample minimizer (shrink a failing family case: shorter clip, smaller offset/occlusion window, while the outcome stays a failure) + export of decisive frames side by side.
2. G4-02: frozen holdout = separate seed range per family, generated and hashed before any repair; repairer never sees it.
3. G1-04: SAM 3.1 adapter against fixtures, so G2-03 switches to real SAM the day the key arrives.

## Human actions pending
- C-03: Meta credits / key (requested). Put key in `backend/.env` when received.
- C-02: post the 4 questions in Discord #questions.
