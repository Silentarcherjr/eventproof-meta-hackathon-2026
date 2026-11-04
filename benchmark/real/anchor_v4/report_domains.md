# EventProof real-video validation (n=3 clips)

**Real-world data, n=3 clips, no tuning.** Real-world videos (the participant's own recordings or licensed public footage; source in each label's notes), labelled by hand and frozen before any model ran. Reported separately from the synthetic results; never used to tune rules, thresholds, repairs or the grader.

- created 2026-11-03T23:55:16+00:00, eventproof 0.1.0, commit `27395f47465d`
- labels manifest sha256 `d8aca66e436b30df674943fcf73c950136569624f25e4a78a7154be36eb9cf8f`
- live calls this run: Muse 2, SAM 0 (allowances 3 / 3); everything else served from cache
- repair ("after"): `muse-spark-1.3-r3-0` = DWELL(inspection) >= 0.80 s; DWELL(inspection) counts only while speed <= 0.08/s (first accepted proposal in the proposer's order; from `docs/evidence/runs/20261028T023754Z-a922b5bb/challenge/repair_muse.json`, sha256 `8031f8f43d3b`)
- matching: crossing objects paired in crossing order; others in first-frame order; leftovers reported

| | overall agrees | objects agree | evaluated |
|---|---|---|---|
| before repair | 3/3 | 7/8 | 3/3 |
| after repair | 0/3 | 0/8 | 0/3 |

Missed (labelled, not perceived): 1. Extra (perceived, not labelled): 1.

| clip | sha256 | run | evidence sha256 | Muse | SAM | expected | before | after |
|---|---|---|---|---|---|---|---|---|
| bike_oneway_a.mp4 | `17837fba177a` | `20261103T235420Z-ac9b7224` | `878fc1ba0f20` | live | cached | PASS | PASS | n/a |
| bike_oneway_b.mp4 | `f636d9c91f41` | `20261103T235443Z-b7cbbaa3` | `b382d9e0daf1` | cached | cached | FAIL | FAIL | n/a |
| crosswalk_oneway.mp4 | `e8e0c41a0ef0` | `20261103T235444Z-ab7fcf5d` | `27ab4d0d660a` | live | cached | FAIL | FAIL | n/a |

## bike_oneway_a.mp4 (completed)
- after: repair patch does not apply to this clip's rule: rule has no DWELL on zone 'inspection'

| # | labelled object | intended | matched id | crossing | before | after |
|---|---|---|---|---|---|---|
| 0 | cyclist in white and black, rides left to right, passes the midpoint ~1.2 s | PASS | 0 | TRUE | PASS | None |

## bike_oneway_b.mp4 (completed)
- after: repair patch does not apply to this clip's rule: rule has no DWELL on zone 'inspection'

| # | labelled object | intended | matched id | crossing | before | after |
|---|---|---|---|---|---|---|
| 0 | cyclist in orange, rides right to left, passes the midpoint ~15.7 s | VIOLATION | 0 | TRUE | VIOLATION | None |

## crosswalk_oneway.mp4 (completed)
- after: repair patch does not apply to this clip's rule: rule has no DWELL on zone 'inspection'

| # | labelled object | intended | matched id | crossing | before | after |
|---|---|---|---|---|---|---|
| 0 | man in dark clothes, walks right to left, crosses the middle ~3.1 s | VIOLATION | 1 | TRUE | VIOLATION | None |
| 1 | second man, walks right to left behind him, crosses ~4.2 s | VIOLATION | 0 | TRUE | VIOLATION | None |
| 2 | cyclist, rides left to right, crosses ~7.8 s | PASS | 2 | TRUE | PASS | None |
| 3 | second cyclist, rides left to right, crosses ~8.4 s | PASS | 3 | TRUE | PASS | None |
| 4 | woman, walks left to right, crosses ~10.0 s | PASS | 4 | TRUE | PASS | None |
| 5 | person at the top-left corner ~5-9 s, leaves without crossing the middle | PASS | None | None | None | None |
| extra | (not labelled) | - | 5 | TRUE | PASS | None |
