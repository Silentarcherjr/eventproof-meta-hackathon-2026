# EventProof real-video validation (n=2 clips)

**Real-world data, n=2 clips, no tuning.** Real-world videos (the participant's own recordings or licensed public footage; source in each label's notes), labelled by hand and frozen before any model ran. Reported separately from the synthetic results; never used to tune rules, thresholds, repairs or the grader.

- created 2026-11-02T06:27:33+00:00, eventproof 0.1.0, commit `730d351cdc1a`
- labels manifest sha256 `15c344751eef333631902699a2760e95a8694eafd151d8ea315a41566b72d8b5`
- live calls this run: Muse 1, SAM 2 (allowances 1 / 2); everything else served from cache
- repair ("after"): `muse-spark-1.3-r3-0` = DWELL(inspection) >= 0.80 s; DWELL(inspection) counts only while speed <= 0.08/s (first accepted proposal in the proposer's order; from `docs/evidence/runs/20261028T023754Z-a922b5bb/challenge/repair_muse.json`, sha256 `8031f8f43d3b`)
- matching: crossing objects paired in crossing order; others in first-frame order; leftovers reported

| | overall agrees | objects agree | evaluated |
|---|---|---|---|
| before repair | 2/2 | 14/16 | 2/2 |
| after repair | 1/2 | 6/16 | 2/2 |

Missed (labelled, not perceived): 0. Extra (perceived, not labelled): 9.

| clip | sha256 | run | evidence sha256 | Muse | SAM | expected | before | after |
|---|---|---|---|---|---|---|---|---|
| wroclaw_w1.mp4 | `7afdd2395e71` | `20261102T062640Z-bcbc3bb9` | `e2bc8c41ae87` | live | live | PASS | PASS | PASS |
| wroclaw_w2.mp4 | `6ea7f78f3262` | `20261102T062718Z-8e72f75c` | `28984e777302` | cached | live | FAIL | FAIL | PASS |

## wroclaw_w1.mp4 (completed)

| # | labelled object | intended | matched id | crossing | before | after |
|---|---|---|---|---|---|---|
| 0 | dark Lexus, lane 1, first in the red-light queue; crosses ~4.9 s | PASS | 3 | TRUE | PASS | PASS |
| 1 | white sedan, lane 2, first in queue; crosses ~5.8 s | PASS | 0 | TRUE | PASS | PASS |
| 2 | light blue car, lane 1, second in queue; crosses ~7.4 s | PASS | 1 | TRUE | PASS | PASS |
| 3 | grey-blue car, lane 2, second in queue; crosses ~8.6 s | PASS | 2 | TRUE | PASS | PASS |
| 4 | dark car, lane 2, third in queue; crosses ~10.9 s | PASS | 5 | TRUE | PASS | PASS |
| 5 | white SUV, lane 1, behind the motorcycle in the queue; crosses ~12.1 s | PASS | 4 | TRUE | PASS | PASS |
| extra | (not labelled) | - | 6 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 7 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 8 | FALSE | PASS | PASS |

## wroclaw_w2.mp4 (completed)

| # | labelled object | intended | matched id | crossing | before | after |
|---|---|---|---|---|---|---|
| 0 | grey hatchback, lane 1; crosses ~4.75 s | VIOLATION | 1 | TRUE | VIOLATION | PASS |
| 1 | white car, lane 2; crosses ~7.4 s | VIOLATION | 2 | TRUE | VIOLATION | PASS |
| 2 | dark green-grey SUV, lane 2; crosses ~8.75 s | VIOLATION | 3 | TRUE | VIOLATION | PASS |
| 3 | silver car, lane 1; crosses ~9.25 s | VIOLATION | 4 | TRUE | VIOLATION | PASS |
| 4 | dark car, lane 1; crosses ~10.6 s | VIOLATION | 5 | TRUE | VIOLATION | PASS |
| 5 | silver hatchback, lane 2; crosses ~11.0 s | VIOLATION | 6 | TRUE | UNKNOWN | PASS |
| 6 | white SUV, lane 1; crosses ~12.25 s | VIOLATION | 7 | TRUE | UNKNOWN | PASS |
| 7 | grey car, lane 2; crosses ~13.25 s | VIOLATION | 8 | TRUE | VIOLATION | PASS |
| 8 | green SUV, lane 2; crosses ~15.0 s | VIOLATION | 10 | TRUE | VIOLATION | PASS |
| 9 | silver car, lane 1; crosses ~15.7 s | VIOLATION | 9 | TRUE | VIOLATION | PASS |
| extra | (not labelled) | - | 0 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 11 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 12 | TRUE | VIOLATION | PASS |
| extra | (not labelled) | - | 13 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 14 | FALSE | PASS | PASS |
| extra | (not labelled) | - | 15 | FALSE | PASS | PASS |
