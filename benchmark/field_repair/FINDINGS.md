# Field repair: results

Pre-registration: [`PREREGISTRATION.md`](PREREGISTRATION.md). Data: [`report.json`](report.json), Muse Spark answers in
[`cache/`](cache/) (2 live calls). CI recomputes the whole report from committed files (`test_field_repair.py`).

Start: the rule as deployed after the synthetic stage (Muse's rule + synthetic-accepted repair r3-0): real holdout
(Wroclaw, 22 cars) **9/22**, dev (Novi Sad, 8 cars) 7/8, synthetic holdout 164/200.

| proposer | proposals | accepted | what happened |
|---|---|---|---|
| Muse Spark (2 rounds, saw only Novi Sad) | 4 | **0** | Every proposal fixes the real footage: dev 8/8, **Wroclaw 9 → 19/22**, 0 regressions. All are rejected because Muse also raised the minimum stop to 1.0 s, which breaks 7–8 short synthetic stops that were right before (164 → 159/200). |
| grid baseline | 16 | 3 | DWELL ≥ 0.8 s with stillness ≤ 0.03, 0.04 or 0.05 frame widths/s: **Wroclaw 9 → 19/22 and synthetic 164 → 166/200, 0 regressions in both**. |

Reading it:
- The diagnosis transferred: Muse Spark, shown only one city, found the right lever (count only truly still time, ≤ 0.04
  instead of 0.08) and its patches carried to a second city with a different camera (9 → 19 of 22 cars).
- The two-world grader stopped a change nobody asked for: moving "1.5 s" to "1.0 s" matched the field labels but silently
  changed what the rule does elsewhere. Requiring zero regressions on both real and synthetic holdouts is what separated
  the fix from the side effect.
- The accepted field repair (≤ 0.04/s, ≥ 0.8 s) comes from the deterministic grid, not from Muse. The 3 remaining Wroclaw
  errors are the 2 abstentions and the car SAM 3.1 never tracked; no labelled car gets a wrong verdict.
- Disclosed: 3 of the 16 grid patches were dry-run before the pre-registration (see there).
