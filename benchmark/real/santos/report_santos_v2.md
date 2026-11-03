# EventProof real-video validation (n=2 clips)

**Real-world data, n=2 clips, no tuning.** Real-world videos (the participant's own recordings or licensed public footage; source in each label's notes), labelled by hand and frozen before any model ran. Reported separately from the synthetic results; never used to tune rules, thresholds, repairs or the grader.

- created 2026-11-03T23:37:23+00:00, eventproof 0.1.0, commit `24755c4fdba5`
- labels manifest sha256 `9ed7964dfd0e03735874409794a7dc8d9101948a3f4671fb3cb6f89f16d15e88`
- live calls this run: Muse 2, SAM 1 (allowances 2 / 2); everything else served from cache
- repair ("after"): `muse-spark-1.3-r3-0` = DWELL(inspection) >= 0.80 s; DWELL(inspection) counts only while speed <= 0.08/s (first accepted proposal in the proposer's order; from `docs/evidence/runs/20261028T023754Z-a922b5bb/challenge/repair_muse.json`, sha256 `8031f8f43d3b`)
- matching: crossing objects paired in crossing order; others in first-frame order; leftovers reported

| | overall agrees | objects agree | evaluated |
|---|---|---|---|
| before repair | 1/2 | 1/8 | 2/2 |
| after repair | 0/2 | 0/8 | 0/2 |

Missed (labelled, not perceived): 5. Extra (perceived, not labelled): 8.

| clip | sha256 | run | evidence sha256 | Muse | SAM | expected | before | after |
|---|---|---|---|---|---|---|---|---|
| santos_away.mp4 | `0907db49a03d` | `20261103T233625Z-e1540bd3` | `33e47c1186d8` | live | cached | FAIL | PASS | n/a |
| santos_toward.mp4 | `c62f0afcc38e` | `20261103T233642Z-0a5f3e2c` | `f02e7f72d260` | live | live | FAIL | FAIL | n/a |

## santos_away.mp4 (completed)
- after: repair patch does not apply to this clip's rule: rule has no DWELL on zone 'inspection'

| # | labelled object | intended | matched id | crossing | before | after |
|---|---|---|---|---|---|---|
| 0 | man in black shirt with a basket, rides away from the camera, crosses ~1 s | VIOLATION | None | None | None | None |
| 1 | rider in red helmet with backpack, enters at the right edge, rides away, crosses ~8.5 s | VIOLATION | None | None | None | None |
| 2 | man in orange shirt, rides toward the camera, crosses ~13.5 s | PASS | None | None | None | None |
| 3 | girl in black with a basket, behind the orange man, rides toward the camera, crosses ~14.5 s | PASS | None | None | None | None |
| extra | (not labelled) | - | 0 | FALSE | PASS | None |
| extra | (not labelled) | - | 1 | FALSE | PASS | None |
| extra | (not labelled) | - | 2 | FALSE | PASS | None |
| extra | (not labelled) | - | 3 | FALSE | PASS | None |
| extra | (not labelled) | - | 4 | FALSE | PASS | None |
| extra | (not labelled) | - | 5 | FALSE | PASS | None |
| extra | (not labelled) | - | 6 | FALSE | PASS | None |

## santos_toward.mp4 (completed)
- after: repair patch does not apply to this clip's rule: rule has no DWELL on zone 'inspection'

| # | labelled object | intended | matched id | crossing | before | after |
|---|---|---|---|---|---|---|
| 0 | man in brown jacket with a red crate, rides away from the camera, crosses ~1.5 s | VIOLATION | 0 | TRUE | PASS | None |
| 1 | woman in white helmet with a basket, rides toward the camera, crosses ~3.5 s | PASS | 2 | TRUE | PASS | None |
| 2 | man in a 'BANNED' t-shirt with a basket, rides toward the camera, crosses ~11.5 s | PASS | 3 | TRUE | VIOLATION | None |
| 3 | woman in lavender, enters at the bottom ~13 s, rides away, crosses ~17.5 s | VIOLATION | None | None | None | None |
| extra | (not labelled) | - | 1 | FALSE | PASS | None |
