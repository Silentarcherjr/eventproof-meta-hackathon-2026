# EventProof real-video validation (n=2 clips)

**Real-world data, n=2 clips, no tuning.** Real-world videos (the participant's own recordings or licensed public footage; source in each label's notes), labelled by hand and frozen before any model ran. Reported separately from the synthetic results; never used to tune rules, thresholds, repairs or the grader.

- created 2026-11-02T04:09:18+00:00, eventproof 0.1.0, commit `45bde5e9961b`
- labels manifest sha256 `657b219060da4ab0807096582bc1866d465c1f2d8ab3f9b6f8bd9589d165b961`
- live calls this run: Muse 1, SAM 2 (allowances 1 / 2); everything else served from cache
- repair ("after"): `muse-spark-1.3-r3-0` = DWELL(inspection) >= 0.80 s; DWELL(inspection) counts only while speed <= 0.08/s (first accepted proposal in the proposer's order; from `docs/evidence/runs/20261028T023754Z-a922b5bb/challenge/repair_muse.json`, sha256 `8031f8f43d3b`)
- matching: crossing objects paired in crossing order; others in first-frame order; leftovers reported

| | overall agrees | objects agree | evaluated |
|---|---|---|---|
| before repair | 2/2 | 8/8 | 2/2 |
| after repair | 2/2 | 7/8 | 2/2 |

Missed (labelled, not perceived): 0. Extra (perceived, not labelled): 7.

| clip | sha256 | run | evidence sha256 | Muse | SAM | expected | before | after |
|---|---|---|---|---|---|---|---|---|
| novisad_approach_a.mp4 | `c1b8e02a6edd` | `20261102T040830Z-37064c4a` | `74838e409eda` | live | live | FAIL | FAIL | FAIL |
| novisad_approach_b.mp4 | `f9c2698045b0` | `20261102T040902Z-b6bc5a2e` | `c6ef15fd7699` | cached | live | PASS | PASS | PASS |

## novisad_approach_a.mp4 (completed)

| # | labelled object | intended | matched id | crossing | before | after |
|---|---|---|---|---|---|---|
| 0 | red car entering at the right edge ~2.0 s, rolls through and crosses ~4.2 s without stopping | VIOLATION | 6 | TRUE | VIOLATION | VIOLATION |
| 1 | silver sedan entering ~5.5 s, stands still ~7.5-11.5 s, crosses ~13.7 s | PASS | 7 | TRUE | PASS | PASS |
| 2 | white van entering ~13.8 s, rolls through at ~50 px/s (never stops, checked at 5 fps) and crosses ~17.0 s | VIOLATION | 8 | TRUE | VIOLATION | PASS |
| 3 | white car waiting in the left-hand lane the whole clip (upper of the two, lower-left of the frame) | PASS | 0 | FALSE | PASS | PASS |
| 4 | white car waiting in the left-hand lane the whole clip (lower, at the bottom-left edge) | PASS | 1 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 2 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 3 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 4 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 5 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 9 | FALSE | PASS | PASS |

## novisad_approach_b.mp4 (completed)

| # | labelled object | intended | matched id | crossing | before | after |
|---|---|---|---|---|---|---|
| 0 | white SUV already standing in the waiting zone at 0 s, stands still until ~5.5 s, crosses ~6.8 s | PASS | 2 | TRUE | PASS | PASS |
| 1 | white car waiting in the left-hand lane the whole clip (upper of the two, lower-left of the frame) | PASS | 0 | FALSE | PASS | PASS |
| 2 | white car waiting in the left-hand lane the whole clip (lower, at the bottom-left edge) | PASS | 1 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 3 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 4 | FALSE | PASS | PASS |
