# EventProof real-video validation (n=2 clips)

**Real-world data, n=2 clips, no tuning.** Real-world videos (the participant's own recordings or licensed public footage; source in each label's notes), labelled by hand and frozen before any model ran. Reported separately from the synthetic results; never used to tune rules, thresholds, repairs or the grader.

- created 2026-11-03T23:12:18+00:00, eventproof 0.1.0, commit `8166afbd5eba`
- labels manifest sha256 `1c00f712392d17fdcfc1720eab303bb37980560020d9fac203482d80a6fea0a0`
- live calls this run: Muse 2, SAM 2 (allowances 2 / 2); everything else served from cache
- repair ("after"): `muse-spark-1.3-r3-0` = DWELL(inspection) >= 0.80 s; DWELL(inspection) counts only while speed <= 0.08/s (first accepted proposal in the proposer's order; from `docs/evidence/runs/20261028T023754Z-a922b5bb/challenge/repair_muse.json`, sha256 `8031f8f43d3b`)
- matching: crossing objects paired in crossing order; others in first-frame order; leftovers reported

| | overall agrees | objects agree | evaluated |
|---|---|---|---|
| before repair | 0/2 | 0/8 | 2/2 |
| after repair | 0/2 | 0/8 | 0/2 |

Missed (labelled, not perceived): 8. Extra (perceived, not labelled): 15.

| clip | sha256 | run | evidence sha256 | Muse | SAM | expected | before | after |
|---|---|---|---|---|---|---|---|---|
| santos_away.mp4 | `0907db49a03d` | `20261103T231056Z-2fdf0faa` | `11344038fdb4` | live | live | FAIL | PASS | n/a |
| santos_toward.mp4 | `c62f0afcc38e` | `20261103T231135Z-aa354fe9` | `d96507094c59` | live | live | FAIL | PASS | n/a |

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
| 0 | man in brown jacket with a red crate, rides away from the camera, crosses ~1.5 s | VIOLATION | None | None | None | None |
| 1 | woman in white helmet with a basket, rides toward the camera, crosses ~3.5 s | PASS | None | None | None | None |
| 2 | man in a 'BANNED' t-shirt with a basket, rides toward the camera, crosses ~11.5 s | PASS | None | None | None | None |
| 3 | woman in lavender, enters at the bottom ~13 s, rides away, crosses ~17.5 s | VIOLATION | None | None | None | None |
| extra | (not labelled) | - | 0 | FALSE | PASS | None |
| extra | (not labelled) | - | 1 | FALSE | PASS | None |
| extra | (not labelled) | - | 2 | FALSE | PASS | None |
| extra | (not labelled) | - | 4 | FALSE | PASS | None |
| extra | (not labelled) | - | 5 | FALSE | PASS | None |
| extra | (not labelled) | - | 6 | FALSE | PASS | None |
| extra | (not labelled) | - | 7 | FALSE | PASS | None |
| extra | (not labelled) | - | 8 | FALSE | PASS | None |
