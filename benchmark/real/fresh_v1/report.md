# EventProof real-video validation (n=6 clips)

**Real-world data, n=6 clips, no tuning.** Real-world videos (the participant's own recordings or licensed public footage; source in each label's notes), labelled by hand and frozen before any model ran. Reported separately from the synthetic results; never used to tune rules, thresholds, repairs or the grader.

- created 2026-11-04T10:12:07+00:00, eventproof 0.1.0, commit `59cacdd9fcc5`
- labels manifest sha256 `721c60e787c2c91be17f760ca663ec5ccd7053d1e11ece98b882e97ce60f40b0`
- live calls this run: Muse 2, SAM 6 (allowances 6 / 6); everything else served from cache
- repair ("after"): `muse-spark-1.3-r3-0` = DWELL(inspection) >= 0.80 s; DWELL(inspection) counts only while speed <= 0.08/s (first accepted proposal in the proposer's order; from `docs/evidence/runs/20261028T023754Z-a922b5bb/challenge/repair_muse.json`, sha256 `8031f8f43d3b`)
- matching: crossing objects paired in crossing order; others in first-frame order; leftovers reported

| | overall agrees | objects agree | evaluated |
|---|---|---|---|
| before repair | 5/6 | 7/10 | 6/6 |
| after repair | 5/6 | 6/10 | 6/6 |

Missed (labelled, not perceived): 2. Extra (perceived, not labelled): 46.

| clip | sha256 | run | evidence sha256 | Muse | SAM | expected | before | after |
|---|---|---|---|---|---|---|---|---|
| drone_north_1.mp4 | `8101c819af72` | `20261104T100932Z-337cfde2` | `3115082e06b0` | live | live | PASS | PASS | PASS |
| drone_north_2.mp4 | `0ab686bc8cd5` | `20261104T101019Z-47239bfe` | `4d63035c85fd` | cached | live | PASS | PASS | PASS |
| drone_north_3.mp4 | `0fac432542ab` | `20261104T101034Z-47b94894` | `9e2d1d16fe34` | cached | live | FAIL | FAIL | FAIL |
| drone_south_1.mp4 | `7d09d1aa8f0f` | `20261104T101049Z-87a1271a` | `0060049c5cfd` | live | live | FAIL | FAIL | FAIL |
| drone_south_2.mp4 | `08b8be359056` | `20261104T101133Z-87c253d6` | `30dc2998136b` | cached | live | PASS | PASS | PASS |
| drone_south_3.mp4 | `d2c0fe42ce7b` | `20261104T101149Z-b95f4e13` | `4a87c5ed40f6` | cached | live | PASS | FAIL | FAIL |

## drone_north_1.mp4 (completed)

| # | labelled object | intended | matched id | crossing | before | after |
|---|---|---|---|---|---|---|
| 0 | red car with white roof, northbound; stops in the zone well before the line and never crosses (from Muse Spark's note) | PASS | 0 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 1 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 2 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 3 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 4 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 5 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 6 | FALSE | PASS | PASS |

## drone_north_2.mp4 (completed)

| # | labelled object | intended | matched id | crossing | before | after |
|---|---|---|---|---|---|---|
| 0 | red car with white roof, small hatchback in right northbound lane | PASS | 0 | TRUE | PASS | PASS |
| extra | (not labelled) | - | 1 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 2 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 3 | FALSE | PASS | PASS |

## drone_north_3.mp4 (completed)

| # | labelled object | intended | matched id | crossing | before | after |
|---|---|---|---|---|---|---|
| 0 | silver van/pickup, middle lane | VIOLATION | 1 | TRUE | VIOLATION | VIOLATION |
| 1 | dark gray/black pickup, right-center lane | VIOLATION | 0 | TRUE | VIOLATION | VIOLATION |
| 2 | dark blue sedan, middle lane | VIOLATION | 2 | TRUE | UNKNOWN | UNKNOWN |
| 3 | black SUV/sedan, middle lane | VIOLATION | 4 | TRUE | VIOLATION | VIOLATION |
| extra | (not labelled) | - | 3 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 5 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 6 | FALSE | PASS | PASS |

## drone_south_1.mp4 (completed)

| # | labelled object | intended | matched id | crossing | before | after |
|---|---|---|---|---|---|---|
| 0 | black SUV in southbound left lane | VIOLATION | 1 | TRUE | VIOLATION | PASS |
| extra | (not labelled) | - | 0 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 2 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 3 | TRUE | VIOLATION | VIOLATION |
| extra | (not labelled) | - | 4 | TRUE | VIOLATION | VIOLATION |
| extra | (not labelled) | - | 5 | TRUE | VIOLATION | VIOLATION |
| extra | (not labelled) | - | 7 | TRUE | VIOLATION | VIOLATION |
| extra | (not labelled) | - | 8 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 9 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 10 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 11 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 12 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 13 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 14 | FALSE | PASS | PASS |

## drone_south_2.mp4 (completed)

| # | labelled object | intended | matched id | crossing | before | after |
|---|---|---|---|---|---|---|
| 0 | dark grey sedan in left southbound lane | PASS | None | None | None | None |
| extra | (not labelled) | - | 0 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 1 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 2 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 3 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 4 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 5 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 6 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 8 | TRUE | PASS | PASS |
| extra | (not labelled) | - | 9 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 10 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 11 | FALSE | PASS | PASS |

## drone_south_3.mp4 (completed)

| # | labelled object | intended | matched id | crossing | before | after |
|---|---|---|---|---|---|---|
| 0 | blue SUV in left southbound lane | PASS | None | None | None | None |
| 1 | white SUV in right southbound lane | PASS | 1 | TRUE | PASS | PASS |
| extra | (not labelled) | - | 0 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 2 | TRUE | PASS | PASS |
| extra | (not labelled) | - | 3 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 4 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 5 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 6 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 7 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 8 | TRUE | VIOLATION | VIOLATION |
| extra | (not labelled) | - | 9 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 10 | FALSE | PASS | PASS |
