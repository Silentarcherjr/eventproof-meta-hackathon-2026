# Benchmark reports

All reports here state their perception source. **`mock` = naive detector/tracker over synthetic ground truth
(`backend/eventproof/perception/mock.py`), NOT SAM 3.1.** They measure the Challenge harness and rule
quality, not Meta model quality.

| File | Perception | Rule | Seeds | Command |
|---|---|---|---|---|
| 2026-10-27_mock_suite_dwell1500.json | mock | DWELL ≥ 1.5 s before packing | 0–29 × 5 families | `uv run python -m eventproof.challenge.runner --seeds 0-29 --dwell-ms 1500` |
| 2026-10-27_sam_vs_mock.json | **mock AND live sam-3.1** | DWELL ≥ 1.5 s | tailgate 0,2,3,4,5; occluded_station 1,2,6,8,10 (mock-failing cases) | `uv run python -m eventproof.challenge.compare --cases tailgate:0,2,3,4,5 occluded_station:1,2,6,8,10 --max-live-calls 10` |
| 2026-10-27_mock_suite_dwell500.json | mock | DWELL ≥ 0.5 s before packing | 0–29 × 5 families | same with `--dwell-ms 500` |

Process requirement (ground truth intent): a box must stand still at the inspection station ≥ 1.0 s before crossing into packing.
Outcomes: correct / spec_error (rule disagrees with intent even on perfect tracks) / perception_error (tracks flip a correct rule) / abstained (UNKNOWN).
n = 30 scenes per family; small sample, synthetic only — do not generalize to production.

## SAM 3.1 vs mock on mock-failing cases (2026-10-27, 10 live SAM calls)
| Family | Truth | Mock | SAM 3.1 |
|---|---|---|---|
| tailgate (5 cases) | FAIL | PASS ×5 — merged boxes hide the uninspected one (dangerous false PASS) | FAIL ×5 — **correct**; both boxes tracked separately, median IoU 0.98–1.0 |
| occluded_station (5 cases) | PASS | FAIL ×5 — new id after the panel → false alarm | UNKNOWN ×5 — **abstained**; same id kept across the occlusion, but the stop happened under the panel so the inspection was never visible |

With SAM, 0/10 wrong verdicts (5 correct, 5 honest abstentions) vs 10/10 wrong with the mock. The abstentions are not a SAM
error: bridging the 20–35 frame blind spot (`max_gap_frames` 30) would turn them into PASS only by *assuming* the box stayed put,
which EventProof does not do by default. Selected cases are the ones the mock fails (not random); n = 10, synthetic only.
