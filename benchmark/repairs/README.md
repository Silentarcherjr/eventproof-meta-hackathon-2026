# Repair decisions

**Proposer: `baseline-deterministic` (fixed-grid search, NOT Muse Spark). Perception: `mock` (NOT SAM 3.1).**
These files measure the repair + verification harness, not Meta models.

Each file is a `RepairReport` from `uv run python -m eventproof.repair.loop --family <f> --seed auto --out ../benchmark/repairs`:
counterexample → repair context (dev seeds 0–29 only, checked for holdout leaks) → proposals → independent grading on the
frozen hidden holdout `benchmark/holdout/holdout_v1.json` (seeds 20000–20039 × 5 families = 200 scenes, committed in 8ed7a02 before any repair code).

Acceptance = patch is safe (bounded ops, schema-valid, rule structure unchanged) AND fixes the counterexample AND 0 holdout
regressions AND no more false PASS AND holdout accuracy strictly improves.

| Counterexample | Proposal | Holdout correct | Regressions | Decision |
|---|---|---|---|---|
| drive_through-0 (spec error, false PASS) | DWELL ≥ 2.0 s (minimal threshold change) | 144 → 152 /200 | 11 (8 brief_stop, 2 canonical, 1 occluded_station) | rejected |
| drive_through-0 | count DWELL only while speed ≤ 0.05/s; DWELL ≥ 0.8 s | 144 → 166 /200 | 0 | **accepted** |
| brief_stop-5 (spec error, false PASS) | DWELL ≥ 1.7 s | 144 → 153 /200 | 1 (occluded_station/20021) | rejected |
| brief_stop-5 | same stillness patch as above | 144 → 166 /200 | 0 | **accepted** |
| occluded_station-1, tailgate-0 (perception errors) | none: no bounded rule patch fixes the counterexample | — | — | no proposal |

Perception errors (identity loss under occlusion, merged detections) are not repairable by rule thresholds; they need
SAM-quality perception or a tracking repair. n = 200 synthetic scenes; do not generalize to production.
