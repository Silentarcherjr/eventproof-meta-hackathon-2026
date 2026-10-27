# Session handoff

Written: 2026-10-27 (end of session 1, local). Overwrite at the end of every session, after push.

## State
- Gate G0/G2. Repo `Silentarcherjr/eventproof-meta-hackathon-2026` (private). Tag `hackathon-start-2026-10-27` = 039c084. HEAD green on CI.
- Commit identity: Anthony Morell <153972162+Silentarcherjr@users.noreply.github.com> (repo-local git config; set it again in fresh cloud clones). No assistant attribution trailers in commits.
- Done & verified: G0-02 repo, G0-05 CI, G1-02 DSL + tri-state evaluator, G2-01 deterministic renderer (MP4 + oracle ground truth).
- Live Meta: BLOCKED until the participant receives credits / `MODEL_API_KEY` (requested, not yet granted).

## Next exact task
1. G2-02 adversarial families in `backend/eventproof/challenge/`: (a) drive-through near the dwell threshold, (b) occluder over the inspection station, (c) two boxes crossing lanes (ID-swap bait), (d) brief entry. Each family = seeded generator + expected label from `oracle_view`.
2. Labelled mock perception (`source="mock"`): a lossy tracker over ground truth (drops occluded frames, swaps ids when boxes overlap) to develop the Challenge search while SAM is unavailable. Never present as SAM.
3. G2-03 search loop: run families × seeds, compare detector verdict vs oracle, keep failing cases with seed + hashes.

## Human actions pending
- C-03: Meta credits / key (requested). Put key in `backend/.env` when received.
- C-02: post the 4 questions in Discord #questions.
