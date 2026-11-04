# Santos bike path: findings

Pre-registered in `PREREGISTRATION.md` (commit 8166afb) before any model call. Run once: `real_video run`, with
2 Muse Spark compiles and 2 SAM 3.1 calls. The report is `report_santos.json` / `.md`.

**Result: 0/8 labelled crossings judged.** Both clip verdicts were PASS, where FAIL was expected.

**Muse Spark got the logic right.** It compiled "only toward the camera" to `NOT CROSSES(to_left)`, the correct side
for that line, and listed that mapping in its assumptions. SAM 3.1 tracked the riders (7 and 8 tracks).

**Why every verdict failed: the anchor, and it was our default, not Muse's choice.** (Corrected 2026-11-04. An earlier
version of this file said Muse chose the anchor; it cannot, see below.)
- The engine reduces each box to one point before testing it against the line: the box centre or the bottom centre
  (`params.anchor`).
- The compiler's JSON schema gives Muse no field for that point, so every compiled rule gets EventProof's default, the
  box centre. Nobody, model or user, ever chose it.
- The camera looks along the path, so a rider near the camera fills most of the frame height. The line was drawn where
  the wheels touch the path, and the box centre never comes down to it. No rider "crosses" the line, so every rider
  passes. The rule judged nothing about the line at all.

This is the same kind of failure EventProof exists to catch, a sentence turned into a check through a silent choice.
This time the silent choice was in EventProof's own compiler. Neither the two readings nor Challenge Mode could catch
it, because both work on synthetic scenes whose geometry is chosen to fit the rule.

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

## v2: the rule rewritten to say where riders are measured (pre-registered in `PREREGISTRATION_v2.md`, e3d7b8a)

**Result: 1/8.**
- `santos_away`: clip verdict PASS, expected FAIL. No crossing was seen, and the rule check fired again.
- `santos_toward`: clip verdict FAIL, as expected. Only 1 of 4 riders was right: 3 matched, 1 not perceived.
- The run used 2 live Muse compiles. SAM came from the cache for `santos_away`. For `santos_toward` Muse named the
  concept "bicycle", so SAM made 1 new call.

**What it shows.** On `santos_away`, Muse Spark wrote in its assumptions *"the tracked point for CROSSES evaluation is
assumed to be where the wheels touch the path"*. The compiled rule still measured at the box centre, because the schema
has no field to carry that choice. Its explanation and the rule that runs disagree, and only the rule check on the
tracks showed it.

**The fix it calls for:** an `anchor` field in the compiler schema, with a new schema version and new
pre-registration. It is not made before the deadline, because changing the schema invalidates every cached compile that
CI uses to recompute the published numbers. Until then, the rule check refuses such rules.

On `santos_toward`, the "bicycle" boxes are short enough that their centres do cross the line. The remaining misses
come from riders passing each other, as stated as a risk before the run. The matching was not changed.
