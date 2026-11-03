# Santos bike path: findings

Pre-registered in `PREREGISTRATION.md` (commit 2eae88a) before any model call. Run once: `real_video run`, with
2 Muse Spark compiles and 2 SAM 3.1 calls. The report is `report_santos.json` / `.md`.

**Result: 0/8 labelled crossings judged.** Both clip verdicts were PASS, where FAIL was expected.

**Muse Spark got the logic right.** It compiled "only toward the camera" to `NOT CROSSES(to_left)`, the correct side
for that line, and listed that mapping in its assumptions. SAM 3.1 tracked the riders (7 and 8 tracks).

**Why every verdict failed: the anchor.** Muse also chose `anchor: center`: each box is reduced to its centre before it
is tested against the line. This choice is not in its assumptions. The camera looks along the path, so a rider near the
camera fills most of the frame height. The line was drawn where the wheels touch the path, and the box centre never
comes down to it. No rider "crosses" the line, so every rider passes. The rule was not exactly wrong; it judged nothing
about the line at all.

This is the same kind of failure EventProof exists to catch: a sentence turned into a check through a silent choice.
Here neither the two readings nor Challenge Mode could catch it, because both work on synthetic scenes whose geometry
is chosen to fit the rule.

**What changed in the product (after this run; the 0/8 above stands):** a deterministic rule check, `engine/lint.py`
(`anchor_check`).
- For every line the rule depends on, it counts the tracked objects that cross the line at the rule's anchor and at the
  other anchor.
- If none cross at the rule's anchor and some cross at the other, the studio shows "The rule cannot see what it judges".
  The certificate is then NOT CERTIFIED, with the reason.
- On the recorded real runs it fires on both Santos runs and on no other run. This is tested in CI
  (`tests/engine/test_lint.py`).

**Post-hoc diagnostic, not counted anywhere:** the same tracks with `anchor: bottom_center`, no new calls.
- `santos_away`: 4/4 right.
- `santos_toward`: 1/4 right. Riders who pass each other swap track order, so crossing-order matching mismatches them.

A re-run with a changed rule or layout would be a new pre-registered test; none was made.
