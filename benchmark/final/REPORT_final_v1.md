# final_v1 — results of the pre-registered evaluation (run once, 2026-10-28)

Freeze: commit 56001c5 (manifest sha256 `3f955049…cad28`). Evaluator: commit fb46a25, tested only on dev seeds before
this run. Raw output: `report_final_v1.json` (input file hashes, per-family counts, every regressed case).
Perception: mock tracker (NOT SAM 3.1), so the remaining errors are partly the mock's. n is small; this is synthetic data.

## Unpatched rule (the rule Muse Spark compiled; the baseline template rule gives identical results)
| split | correct | 95% CI | false PASS | errors |
|---|---|---|---|---|
| in_distribution (200) | 141 | 0.64–0.76 | 37 | 17 spec errors (drive_through 15, brief_stop 2), 31 perception errors, 11 abstained (occluded_station, tailgate) |
| shift (120, families never seen before) | 109 | 0.84–0.95 | 11 | 11 spec errors (stop_and_go 7, two_stops 4) |

## Every proposal (12), grader decision vs. final result
| proposer | patch | grader on holdout_v2 | final in_distribution (fixed / regressed, p) | final shift (fixed / regressed, p) |
|---|---|---|---|---|
| Muse | still ≤ 0.05/s ≥ 0.70 s | **accepted** 144→166 | **158** (17 / 0, p<0.001) | **118** (9 / 0, p=0.004) |
| Muse | still ≤ 0.08/s ≥ 0.80 s | **accepted** 144→164 | **158** (17 / 0, p<0.001) | **117** (8 / 0, p=0.008) |
| Muse | still ≤ 0.05/s (1.5 s kept) | rejected 144→156 | 145 (38 / 34) | 99 (11 / 21) |
| Muse | still ≤ 0.10/s (1.5 s kept) | rejected 144→145 | 135 (21 / 27) | 110 (11 / 10) |
| Muse | still, ≥ 1.10 s | rejected 144→161 | 152 (17 / 6) | 120 (11 / 0) |
| Muse | still, ≥ 1.00 s | rejected 144→159 | 150 (17 / 8) | 120 (11 / 0) |
| Muse | still, ≥ 1.20 s | rejected 144→155 | 149 (18 / 10) | 115 (11 / 5) |
| Muse | still, ≥ 1.00 s (other speed) | rejected 144→164 | 156 (17 / 2) | 118 (9 / 0) |
| Baseline | DWELL ≥ 2.0 s | rejected 144→152 | 150 (16 / 7) | 116 (7 / 0) |
| Baseline | still ≤ 0.05/s ≥ 0.80 s | **accepted** 144→166 | **158** (17 / 0, p<0.001) | **120** (11 / 0, p<0.001) |
| Baseline | DWELL ≥ 1.7 s | rejected 144→153 | 149 (9 / 1) | 114 (5 / 0) |
| Baseline | same stillness patch (2nd counterexample) | **accepted** 144→166 | **158** (17 / 0) | **120** (11 / 0) |

## Pre-registered hypotheses
- **H1: holds.** Every accepted patch: 141→158/200 in distribution (95% CI 0.73–0.84), false PASS 37→20, **0 regressions**.
  All 17 spec errors are fixed. The 42 errors left are perception errors and abstentions of the mock tracker
  (occluded_station, tailgate), which a rule patch cannot fix.
- **H2: holds.** On the never-seen families every accepted patch improves with 0 regressions: Muse 109→118 and 109→117,
  baseline 109→120/120. False PASS 11→2 / 3 / 0.
- **H3: holds.** Mean gain, accepted vs. rejected: in distribution +17.0 vs. +7.3, shift +9.75 vs. +5.0. 7 of the 8 rejected
  patches have regressions on final_v1; none of the 4 accepted have any. The grader's choice transfers to unseen data.

## What this does not show
- Muse's accepted patches are slightly weaker than the baseline's on `stop_and_go` (2–3 slow-belt boxes still counted
  as inspected vs. 0): a looser speed limit (0.08/s) or a shorter dwell (0.70 s) lets a slow mover pass. Reported, not tuned.
- Mock perception only. SAM 3.1 on a final_v1 subset is optional and needs budget approval.
- Synthetic conveyor world; real-video validation is a separate track (`docs/REAL_VIDEO_PROTOCOL.md`).
