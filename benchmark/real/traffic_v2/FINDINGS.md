# Real traffic v2 (Pexels, Wroclaw) and the pooled real-traffic result

Pre-registration: [`PREREGISTRATION.md`](PREREGISTRATION.md) (730d351, labels + manifest pushed before any call).
Data: [`report_wroclaw.json`](report_wroclaw.json) / [`.md`](report_wroclaw.md), run evidence and SAM 3.1 tracks in
[`runs/`](runs/), Muse Spark alone in [`spark_alone_wroclaw.json`](spark_alone_wroclaw.json), pooled numbers in
[`../POOLED.json`](../POOLED.json). CI recomputes all of them from committed files (no video, no API).
Live calls: Muse Spark 1 compile + 10 video calls, Muse Wonder 2, SAM 3.1 2 (380 frames).

## Wroclaw (2 clips, 16 labelled cars: 6 stand at a red light then go, 10 drive through on green)
| reading | w1 (queue) | w2 (free flow) | objects right |
|---|---|---|---|
| Muse Spark's rule ("wait" = standing still ≤ 0.05/s for 1.5 s) | 6/6, PASS ✓ | 8/10 + 2 abstained, FAIL ✓ | 14/16 |
| same rule + the repair accepted on synthetic data (≤ 0.08/s for 0.8 s) | 6/6, PASS ✓ | **0/10, PASS ✗** | **6/16** |
| Muse Wonder's rule (same reading as Spark here) | 6/6 | 8/10 + 2 abstained | 14/16 |
| Muse Spark alone, from video (5 runs per clip) | 5/5 runs right; counts exact 4/5 | 5/5 runs right; counts exact 2/5 | – |

**Why the repair fails here:** the camera looks along the road, so a car far away moves few pixels. At the far edge of
the zone (top 10 % of the frame) every free-flowing car moves below 0.08 frame widths/s for 1.2–2.0 s (engine count on
the SAM tracks), which the repaired rule takes as "standing still"; Muse Spark's 0.05/s for 1.5 s does not. A threshold in
image units that was tuned on a side view of a synthetic belt does not transfer to a perspective view.

## Pooled: 4 real traffic clips, 24 labelled cars (Novi Sad a/b + Wroclaw w1/w2)
| detector | labelled cars right | clip verdicts right |
|---|---|---|
| Muse Spark's rule → SAM 3.1 → engine | **22/24** (Wilson 95 % 0.74–0.98), 2 abstained, 0 wrong | 4/4 |
| Muse Wonder's rule → SAM 3.1 → engine | 22/24 (same verdicts) | 4/4 |
| + repair accepted on synthetic data | **13/24** (0.35–0.72) | 3/4 |
| Muse Spark alone from video | not scorable per car | 20/20 runs; crossings and violations counted exactly in **11/20** (0.34–0.74) |

## Post-hoc notes (do not change the result)
- w2: one more car crosses at ~18.4 s (my label sheet stopped at ~16 s); it is reported as an extra track, judged
  VIOLATION by Muse's rule and PASS by the repair. Muse Spark alone also reported 11–12 crossings in 3 of 5 runs.
- The 2 abstentions are cars whose track has a gap in the zone (UNKNOWN, not a wrong verdict).
- n is small and the labels are one person's; this shows a concrete failure mode, not an accuracy rate.
