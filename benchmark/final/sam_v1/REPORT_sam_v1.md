# final_v1 — live SAM 3.1 pass (80 scenes), reported separately

Pre-registration: [`../PREREGISTRATION_SAM_v1.md`](../PREREGISTRATION_SAM_v1.md) (commit 0db2b2d, pushed before the first
call). Data: [`report_sam_v1.json`](report_sam_v1.json), per-scene log [`tracking.json`](tracking.json), raw SAM output
[`sam_cache/`](sam_cache/) (80 responses, request ids in the report). CI recomputes every number below from those files
with 0 API calls (`backend/tests/validation/test_sam_pass.py`). The primary final_v1 result (mock tracker, 320 scenes) is
unchanged: [`../REPORT_final_v1.md`](../REPORT_final_v1.md).

## Run
- 2026-11-01, `sam-3.1`, prompt `box`, 80 live calls (2 trial + 78), 8,087 frames, ~7 s per call. 80/80 tracked and parsed,
  0 excluded. Cost: at most ≈ $4.3 by the bound in the pre-registration; exact charge to be read from the Billing page.

## S1 — the repair, judged with real SAM 3.1 tracks
Studio run rule (compiled by Muse Spark) and all 8 Muse Spark proposals; same 80 scenes for both trackers.

| rule | SAM 3.1: correct / 80 | false PASS | fixed / regressed vs. unpatched | mock tracker: correct / 80 |
|---|---|---|---|---|
| unpatched | **71** (43/50 + 28/30) | 5 | – | 64 |
| accepted r3-0 (DWELL ≥ 0.80 s, only while speed ≤ 0.08/s) | **76** (46/50 + 30/30) | **0** | 5 / **0** | 69 |
| accepted r3-1 (DWELL ≥ 0.70 s, only while speed ≤ 0.05/s) | 75 (46/50 + 29/30) | 1 | 4 / 0 | 69 |
| 6 rejected proposals | 63–75 (mean change −0.2) | 0 | 5 / 0–13 | 60–69 |

- **S1 holds:** both grader-accepted patches improve correct with SAM tracks and lower false PASS (5 → 0 and 5 → 1), with
  0 regressions in either split. Accepted patches gain +4.5 on average, rejected ones −0.2: the grader's choices made on the
  mock-tracked holdout carry over to real perception.
- With r3-0, every remaining SAM error is an **abstention** (4 occluded_station scenes, verdict UNKNOWN because the box is
  hidden behind the occluder): no wrong PASS or FAIL left on these 80 scenes.
- Baseline grid repairs (accepted ones): also 76/80, 0 regressions; the two rejected ones 74 and 73.

## S2 — mock vs. SAM perception (unpatched rule)
- Same verdict on 68/80 scenes. SAM right where the mock was wrong: 8; mock right where SAM was wrong: 1; both wrong: 8
  (the specification errors: drive_through ×3, stop_and_go ×1, two_stops ×1, which the repair fixes, plus occlusion).
- Disagreements are all in two families. **tailgate:** SAM 10/10 correct, mock 2/10 (the mock merges the two boxes or
  abstains). SAM still makes identity errors on 7 of these scenes (id switches / new ids) but they do not change the
  verdict. **occluded_station:** SAM abstains on 4 scenes (UNKNOWN), where the mock gave 3 false alarms and 1 correct FAIL.
- Consequence for the primary report: the mock tracker is *pessimistic* on these families, so its tailgate and occlusion
  numbers understate real-perception accuracy; the specification errors and their repair look the same with both trackers.

## Limits
Synthetic scenes (a scripted conveyor world), n = 80, one prompt, one SAM model version. Not a substitute for real
camera footage (see `docs/REAL_VIDEO_PROTOCOL.md`).
