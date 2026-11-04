# What each Meta model contributes

Every row compares a model against a matched alternative on the same inputs, from results already recorded in this
repository (no new model calls). Each row also says where the model failed. The deterministic engine, never a model,
issues every verdict.

| Model and task | Matched comparison | Result | Where it failed | Source |
|---|---|---|---|---|
| **Muse Spark** compiles a sentence into a typed rule | Same 30 labelled real cars and SAM 3.1 tracks: Spark's rule vs. a repair that passed every synthetic test | **27/30 right, 0 wrong verdicts** vs. 16/30 | 3 not judged: 2 abstentions, 1 car SAM 3.1 never tracked | `benchmark/real/POOLED_v2.json` |
| **Muse Spark** alone, watching the video | Same clips and rule; Spark answers directly (5 runs per clip) | Overall verdict right in 25/25 runs, but crossings and violations counted right in only **11/25** runs | Not the same endpoint as per-car verdicts: this is why Spark compiles the rule instead of judging the video | `benchmark/real/spark_alone/` |
| **Muse Spark** compiles a verbatim statute (Maryland, California) | Its own assumed values vs. every value in a 13 x 21 grid | At its values, 25/30 right; the same law gives 0 to 17 tickets across the grid | Labelled the stillness speed 0.05 "quoted" though the statute has no digit | `benchmark/law/` |
| **Muse Spark** (vision) drafts zones from the first frame | Hand-drawn zones on the same 5 clips | Same verdicts on the drone view (8/8) | On the footbridge view it placed a proxy line and once read the direction backwards | `benchmark/layout/` |
| **Muse Spark** argues the driver's defense from a closed menu | The deterministic sweep over the same menu | Won 8 of the 16 beatable tickets; conceded 3 of the 4 robust ones | Also conceded a ticket the pre-registered labels called wrong; the label audit shows it was right | `benchmark/tickets/` |
| **Muse Spark** proposes bounded repairs | Grader with 200 hidden synthetic scenes, zero-regression rule | 2 of 8 repairs accepted; 144 → 164 / 200 | The accepted repair scored 16/30 on real cars: synthetic tests alone were not enough | `docs/evidence/runs/20261028T023754Z-a922b5bb/challenge/` |
| **Muse Wonder** gives an independent second reading | Same 8 phrasings and 150 scenes as Spark | "wait" and "remain" read differently: verdicts differ on **45/150** scenes, minimal pair found | Shared mistake: both read "remain behind the line for 2 s" as presence; the certificate refused the rule (3/5 on labels) | README "Two readings"; `docs/evidence/runs/20261102T080747Z-6b0ae7d4/` |
| **Muse Spark / Muse Wonder** propose labels from the video for a person to confirm | The person's audited labels on 6 clips of a new camera view | Spark found 9 of 13 crossings; Wonder, never shown to the reviewer, 11 of 13 | Spark missed 4 of 5 cars in one clip and the first review accepted it; Wonder and the SAM tracks caught them | `benchmark/real/fresh_v1/` |
| **SAM 3.1** tracks objects by text prompt | Mock tracker on the same pre-registered 80-scene final test | **71 → 76 / 80**, false PASS 5 → 0; tailgating 10/10 vs. 2/10 | 4 abstentions behind an occluder; on real footage some cars are not tracked | `benchmark/final/` |

Numbers are copied from the committed reports listed in the last column, which CI recomputes.
