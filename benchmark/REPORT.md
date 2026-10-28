# Baselines and ablations (P1-04) — from committed results only

No number here is new: each row is read from the file named in its source column, and `backend/tests/regression/`
recomputes them in CI. Synthetic conveyor world; Challenge, holdout and final scoring use the mock tracker (NOT SAM 3.1).

| detector | how it was made | hidden holdout_v2 (200) correct · false PASS | final_v1 same kinds (200) | final_v1 new kinds (120) | source |
|---|---|---|---|---|---|
| Hand-written DSL (DWELL ≥ 1.5 s) | manual template | 144 · 40 | 141 · 37 | 109 · 11 | `benchmark/repairs/*.json`, `final/report_final_v1.json` |
| Muse Spark, no Challenge | rule compiled from the sentence | 144 · 40 | 141 · 37 | 109 · 11 | `docs/evidence/runs/20261028T023754Z-a922b5bb/`, final report |
| **Muse Spark + Challenge + Muse repair** (first accepted, shown in the studio) | still ≤ 0.08/s, ≥ 0.80 s | **164 · 21** | **158 · 20** | **117 · 3** | `…/challenge/repair_muse.json`, final report |
| Muse Spark + Challenge + Muse repair (second accepted) | still ≤ 0.05/s, ≥ 0.70 s | 166 · 19 | 158 · 20 | 118 · 2 | same |
| Hand-written DSL + Challenge + baseline grid repair | still ≤ 0.05/s, ≥ 0.80 s | 166 · 19 | 158 · 20 | 120 · 0 | `benchmark/repairs/drive_through-0.json`, final report |

Reading it:
- Muse Spark compiles the sentence into a rule that behaves exactly like the hand-written one (same verdicts on all 520
  scenes): compiling is faithful, but both share the same specification error (moving time counts as "stay").
- Challenge Mode + repair is what moves the numbers: +20–22 on the holdout, +17 on the final same-kind split, +8–11 on
  never-seen families, with 0 regressions in every accepted case.
- Muse Spark's repairs are slightly weaker than the deterministic grid search on one never-seen family (stop_and_go: 2–3
  errors vs 0). The grid search is not a model: it searched a fixed space around the same counterexample. Muse's value is
  that it found the fix from the counterexample and the user's own words, with the diagnosis written down.
- The remaining ~42 errors per 200 are perception errors / abstentions of the mock tracker under occlusion and tailgating;
  no rule patch can fix them. SAM 3.1 handled the tailgate cases correctly (5/5) and abstained on the 5 occlusion cases
  (`benchmark/reports/2026-10-27_sam_vs_mock.json`) — on 10 cases only.

Rule-compile quality on the natural-language rule set: `benchmark/rules/2026-10-27_muse_compile_report.json`.
