# 3-minute demo — script (v2, 2026-11-02)

Every number on screen and in the narration is read from a committed file (table at the end). Recorded runs are
replayed from their cache and say so; nothing mock is called Meta. The video is produced by `demo/video/build.sh`
(screen capture of the real studio with Playwright, narration with a synthetic voice, cards rendered from HTML).

| # | screen | narration |
|---|---|---|
| 1 | Title card | AI can now build a video checker from one sentence. Muse Spark writes the rule, SAM 3.1 tracks every object. But who checks the checker? |
| 2 | Studio, run `20261102T040830Z-37064c4a` (Novi Sad, real drone footage): video with tracks, rule, assumptions, timeline | Here is real drone footage of a crossing in Novi Sad. The rule: every car must wait one and a half seconds before the stop line. Muse Spark turns it into a typed rule, never code, and writes down its assumptions: wait means standing still. SAM 3.1 tracks the cars, and a deterministic engine judges each one. This white van crawls through without ever stopping: a violation, with the exact frames. |
| 3 | Studio, demo run, "Two readings" panel with the minimal pair | But the same words can mean different things. EventProof asks a second Meta model, Muse Wonder, to read the rule too. For boxes on a conveyor, Spark reads wait as standing still; Wonder reads it as just being inside. The two rules disagree on 45 of 150 test scenes, and EventProof finds the smallest pair that separates them: a box that never stops, inside for 1.53 seconds. You decide what you meant. |
| 4 | Studio, demo run, Challenge Mode: suite table, counterexample, repair decisions | Then it attacks the rule. Challenge Mode renders 150 synthetic scenes with known truth and finds 44 failures. It shrinks the clearest one to a minimal pair: the same scene with the belt speed changed in the fourth decimal. Muse Spark diagnoses the failure and proposes bounded patches. An independent grader tests each one on 200 hidden scenes: 2 of 8 accepted, with zero regressions. |
| 5 | Before → after view, holdout and final-test cards | Correct verdicts on the hidden scenes go from 144 to 164. A third test set, frozen before anything was evaluated, confirms it, and re-run with real SAM 3.1 tracks, false passes drop from 5 to 0. |
| 6 | Real-traffic figure (`docs/media/real_traffic.png`), then the pooled table | So is that repair safe to deploy? We checked it on real footage, with labels frozen before any model ran. It is not. On a real rolling stop, and on cars far from the camera, its threshold calls a crawling car still. Across 24 labelled cars in two cities, Muse Spark's own rule gets 22 right. The repair that passed every synthetic test gets 13. And Muse Spark watching the video alone gets the headline right, but miscounts the cars in 9 of 20 runs. |
| 7 | Closing card | EventProof does not trust a model's reading, a synthetic test, or itself. Every number here is recomputed in CI from committed evidence. Build it, break it, repair it, and prove it on real video. |

## Claims → source
| claim | source |
|---|---|
| Novi Sad rule, "wait" = standing still (`max_speed 0.05`), van VIOLATION | `benchmark/real/novisad/runs/20261102T040830Z-37064c4a/evidence.json`, `report_novisad.json` |
| Spark vs Wonder, 45/150, minimal pair 1.53 s inside | `benchmark/ambiguity/report.json`, `FINDINGS.md` |
| 150 scenes, 44 failures, belt-speed pair, 2/8 accepted, 0 regressions, 144 → 164 | `docs/evidence/runs/20261028T023754Z-a922b5bb/challenge/*.json` |
| final test confirms; SAM pass false PASS 5 → 0 | `benchmark/final/REPORT_final_v1.md`, `benchmark/final/sam_v1/REPORT_sam_v1.md` |
| 24 cars, 22 vs 13, Spark alone counts wrong in 9/20 runs | `benchmark/real/POOLED.json` |
| every number recomputed in CI | `backend/tests/regression/`, `backend/tests/validation/` |

Limits stated in the README, not in the narration for time: small real set labelled by one person; synthetic voice.
