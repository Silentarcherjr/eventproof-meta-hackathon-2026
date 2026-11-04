# Session handoff

Written: 2026-11-04, America/Panama (UTC-5).

## Current branch and scope
- `interaction-stops`, isolated worktree `/Users/anthonymorell/Desktop/eventproof-interaction`,
  created from origin/main **d31abdf** (parent main CI verified green before work).
- P1-INTERACTION-STOPS: IN_REVIEW; no merge requested or performed. Do not push main.
- Preregistration **1d04084** was pushed before any outcome analysis or live call.
- Main evidence: benchmark/interaction/FINDINGS.md, report.json, compile.json, maps.json, population.json,
  derived.json.gz (3.2 MiB), ATTRIBUTION.md. Raw archive/CSVs outside Git: /private/tmp/interaction/.
- Code: backend/eventproof/validation/interaction.py; tests: backend/tests/validation/test_interaction.py.
  TrackSource adds explicit dataset provenance; evaluator and law compiler unchanged.

## Results and limits
- 1268 approaches from 1254 recording/track identities (not linked between recordings).
- Numeric grid (13 times x 11 speeds): 119–1073 tickets / 1268, 9.38–84.62%, 75.24 pp spread.
  Adding any-motion control (156 total cells): 0–1073, 1073 approaches flip across full grid.
- One live Muse Spark law-mode compile of verbatim CA 22450(a): 1 s and 0.05 frame widths/s.
  Fixed 100 m width means **5 m/s**, outside grid; separate compiled result 10/1268 (0.79%).
  Speed labelled QUOTED by Muse with 'shall stop', which contains no numeric speed.
- EP0 539, EP1 453, MA 276, GL 0. GL's map lanelets stop about 3 m before line; strict lane
  continuity excludes them. Short MA lanes also excluded. No post-outcome inclusion tuning.
- No human violation labels, no video or SAM; sensitivity, not accuracy or actual lawful tickets.

## Verification
- Full backend suite: **415 passed, 1 skipped** including exact report regeneration of every cell,
  compiled value and dwell boundary using only committed derivatives and no live clients.
- Ruff import separator corrected; final full pytest and Ruff repeated before final commit.
- Preregistration push independently confirmed by git ls-remote; final push confirmed before chat handoff.
- Branch CI is not triggered by push (workflow main/PR only); no branch CI-success claim.
- No deployment/frontend changes. One live model call, 1967 in / 6395 out tokens; 0 SAM.
  Actual billed USD unknown; estimated $0.0296 at historical documented rates.

## Next step
Review the pushed branch and reproduce with `cd backend && uv run pytest -q && uv run ruff check .`.
Do not call the model again for reproduction. No merge in this session; only a reviewed merged SHA
can make the tracker DONE_VERIFIED. Separate traffic-visuals remains IN_REVIEW; its frozen evidence
and earlier handoff are preserved in Git history and docs/WORKLOG.md. Human submission/visibility
decisions remain outside this task.
