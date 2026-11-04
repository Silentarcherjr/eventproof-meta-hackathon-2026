# Compile the law as written: findings

Pre-registered in `PREREGISTRATION.md` (commit 243dfa6). There were 12 live calls (8 compiles plus retries).
`report.json` recomputes from the cached compiles with 0 calls (`tests/validation/test_law_study.py`).

**The statutes** are copied verbatim from the legislatures:
- Maryland Transportation § 21-707(a): *"…shall stop at the near side of the intersection at a clearly marked stop
  line."*
- California Vehicle Code § 22450(a): *"…shall stop at a limit line, if marked…"*

Neither contains a single digit. Neither says how long a stop lasts or how slow counts as "stopped".

| statute | model | compiled | 30 real cars: right | wrong | verdicts that flip when the unwritten numbers change |
|---|---|---|---|---|---|
| Maryland | Muse Spark | 2/2 | **25/30** | 2 | **14** |
| California | Muse Spark | 2/2 | **25/30** | 2 | **14** |
| Maryland | Muse Wonder | 1/2 (1 invalid structure) | 18/22 | 1 | 13 |
| California | Muse Wonder | 1/2 (1 invalid structure) | 6/22 | 15 | 0 (its rule only checks a crossing) |

**What it shows:**
- **14 of 30 real verdicts hang on numbers that appear nowhere in the law.** Muse Spark turned "shall stop" into
  "still (≤ 0.05 frame widths/s) for at least 1.0 s".
  - Those 14 verdicts flip when the stop duration moves ±20 % or the speed that counts as "stopped" is halved or
    doubled.
  - 13 are tickets for cars that never stopped: Wroclaw cars crawling through on green, and one Novi Sad car.
  - 1 is the Novi Sad van that rolls through. It is judged PASS, which is wrong, and becomes VIOLATION when the numbers
    move.
- **A real quote used to justify a number it does not contain.**
  - Muse Spark labelled the stillness speed 0.05 as QUOTED with the words "shall stop": once for Maryland, twice for
    California.
  - The verbatim-quote check accepts it, because the words are in the statute.
  - Only the robustness re-run exposes that the verdicts depend on that number.
  - Spark is not consistent: the same statute and value were marked ASSUMED on the other scene.
- **The two models are not interchangeable on law text.** Muse Wonder failed 2 of 4 compiles (invalid node
  structure). One California reading reduced the statute to "crosses the line" and judged 15 of 22 cars wrong.
- **Errors common to all Spark readings:** the Wroclaw w3 silver car right behind another (judged PASS, wrong) and one
  untracked car.

**Changes after the run (disclosed):**
- **The first report had a scoring bug.** The statute rules name the entity "vehicle", the committed tracks are labelled
  "car", and the engine judges only tracks of the rule's own concept. The study now judges the same committed tracks
  under the rule's concept name. That first report is kept as `report_v0_scoring_bug.json`, and the model outputs are
  unchanged.
- **The "unwritten number" count was added after the run.** The pre-registered count, verdicts that flip when a value
  the model marked ASSUMED changes, depends on the model's own labels, which are inconsistent. Both counts are in
  `report.json` (`hang_on_assumed`, `hang_on_unwritten_number`).

**Limits:** two statutes, two scenes and 30 cars. Truth here equals the frozen labels: every car that stopped stood for
at least 4 s.
