# Studio: Challenge Mode + Repair on a live run — 2026-10-27

Run `20261028T023754Z-a922b5bb` (files in `docs/evidence/runs/20261028T023754Z-a922b5bb/`), done through the studio UI against the local backend.

1. **Build** — tailgate clip + rule text "Every blue box must stay at least 1.5 seconds in the inspection zone before it crosses into packing."
   Muse Spark compiled rule (cached from G1-03, request `chatcmpl-01a17fc4-ee68-75f3-97dd-afe01dc99296`); SAM 3.1 tracks (cached).
   Verdict FAIL, the tailgater flagged.
2. **Challenge** — the compiled rule bound to 150 synthetic dev scenes (mock tracker, labelled): 44 failures. Chosen counterexample
   `drive_through` #0 (spec error, dangerous false PASS): the box never stood still (0 ms) but drove 1.84 s through the zone; the rule
   says PASS, truth FAIL. Minimal pair on belt speed: t = 0.1178 fools the rule, t = 0.1180 is judged correctly (local minimum).
3. **SAM confirmation (1 LIVE SAM call)** — the failing scene through real SAM 3.1: rule still PASS, truth FAIL, i.e. the spec error is
   reproduced with real perception (`challenge/sam_confirm.json`).
4. **Repair with Muse Spark (3 rounds; served from the cache built while developing this exact context)** — round 1: correct diagnosis
   ("stay" means stopped; transit time was counted) but too strict (stillness alone at 1.5 s). Rounds 2–3 revised from VISIBLE dev feedback
   only (regression counts + examples). 8 proposals, all graded by the independent grader on the frozen hidden holdout `holdout_v2`
   (200 scenes): **2 accepted** — "DWELL still (≤ 0.05/s) ≥ 0.70 s" 144/200 → 166/200 and "≥ 0.80 s at ≤ 0.08/s" 144/200 → 164/200,
   0 regressions; **6 rejected** (1–26 holdout regressions each). `challenge/repair_muse.json` has every proposal, Muse's rationale, the dev
   screen and the holdout metrics.

Caveats: synthetic world; mock tracker for search and holdout scoring (SAM used for the confirmation only). Grading 8 proposals on one
holdout is a mild multiple-comparison risk: proposals are never ranked or chosen by holdout score, each is accepted or rejected on fixed
criteria.
