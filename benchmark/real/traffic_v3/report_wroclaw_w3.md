# EventProof real-video validation (n=1 clips)

**Real-world data, n=1 clips, no tuning.** Real-world videos (the participant's own recordings or licensed public footage; source in each label's notes), labelled by hand and frozen before any model ran. Reported separately from the synthetic results; never used to tune rules, thresholds, repairs or the grader.

- created 2026-11-02T07:57:36+00:00, eventproof 0.1.0, commit `adab6f62e464`
- labels manifest sha256 `86e81b80467313ccff68bc5f7dc9929e1e588a2d0476ef817d23baa58486bc1b`
- live calls this run: Muse 0, SAM 1 (allowances 1 / 1); everything else served from cache
- repair ("after"): `muse-spark-1.3-r3-0` = DWELL(inspection) >= 0.80 s; DWELL(inspection) counts only while speed <= 0.08/s (first accepted proposal in the proposer's order; from `docs/evidence/runs/20261028T023754Z-a922b5bb/challenge/repair_muse.json`, sha256 `8031f8f43d3b`)
- matching: crossing objects paired in crossing order; others in first-frame order; leftovers reported

| | overall agrees | objects agree | evaluated |
|---|---|---|---|
| before repair | 1/1 | 5/6 | 1/1 |
| after repair | 1/1 | 3/6 | 1/1 |

Missed (labelled, not perceived): 1. Extra (perceived, not labelled): 4.

| clip | sha256 | run | evidence sha256 | Muse | SAM | expected | before | after |
|---|---|---|---|---|---|---|---|---|
| wroclaw_w3.mp4 | `9596099ad337` | `20261102T075727Z-dd8a89d8` | `3723e37a12a5` | cached | live | FAIL | FAIL | FAIL |

## wroclaw_w3.mp4 (completed)

| # | labelled object | intended | matched id | crossing | before | after |
|---|---|---|---|---|---|---|
| 0 | white car, lane 1, already at the line in the first frame; crosses ~0.3 s, never stops | VIOLATION | 2 | TRUE | VIOLATION | VIOLATION |
| 1 | silver hatchback, lane 1; crosses ~2.1 s, never stops | VIOLATION | 7 | TRUE | VIOLATION | VIOLATION |
| 2 | dark sedan, lane 2; crosses ~2.9 s, never stops | VIOLATION | 5 | TRUE | VIOLATION | VIOLATION |
| 3 | silver hatchback, lane 1; crosses ~4.2 s, never stops | VIOLATION | 3 | TRUE | VIOLATION | PASS |
| 4 | silver car, lane 1, right behind; crosses ~4.8 s, never stops | VIOLATION | 6 | TRUE | VIOLATION | PASS |
| 5 | grey-green SUV, lane 2; crosses ~5.8 s, never stops | VIOLATION | None | None | None | None |
| extra | (not labelled) | - | 0 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 1 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 4 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 8 | FALSE | PASS | PASS |
