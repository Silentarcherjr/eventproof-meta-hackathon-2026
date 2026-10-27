# Benchmark reports

All reports here state their perception source. **`mock` = naive detector/tracker over synthetic ground truth
(`backend/eventproof/perception/mock.py`), NOT SAM 3.1.** They measure the Challenge harness and rule
quality, not Meta model quality.

| File | Perception | Rule | Seeds | Command |
|---|---|---|---|---|
| 2026-10-27_mock_suite_dwell1500.json | mock | DWELL ≥ 1.5 s before packing | 0–29 × 5 families | `uv run python -m eventproof.challenge.runner --seeds 0-29 --dwell-ms 1500` |
| 2026-10-27_mock_suite_dwell500.json | mock | DWELL ≥ 0.5 s before packing | 0–29 × 5 families | same with `--dwell-ms 500` |

Process requirement (ground truth intent): a box must stand still at the inspection station ≥ 1.0 s before crossing into packing.
Outcomes: correct / spec_error (rule disagrees with intent even on perfect tracks) / perception_error (tracks flip a correct rule) / abstained (UNKNOWN).
n = 30 scenes per family; small sample, synthetic only — do not generalize to production.
