# Santos v2: the rule rewritten after the rule check (pre-registered BEFORE any model call)

Date: 2026-11-04.

**Why this run exists.** The first run (`PREREGISTRATION.md`, `FINDINGS.md`) judged 0/8 crossings. Muse Spark measured
each rider at the box centre, which never reaches a line drawn at the wheels. The studio's rule check now flags exactly
this case. This run is what a user does next: rewrite the sentence to say where riders are measured, and check again.
The first result stays as reported. This is a new test and is reported separately; it does not replace the first one.

- **Same clips, same layout, same 8 labelled crossings, same matching** (crossing order).
- **Only the rule text changes:** "Cyclists may cross the line on the bike path only toward the camera (from the far end
  of the path to the near end); measure each rider where the wheels touch the path."
- **Labels:** `labels_v2/` (frozen, `labels_v2/MANIFEST.json`).
- **Procedure:** `real_video run --labels labels_v2` with at most 2 Muse compiles and 2 SAM calls. SAM comes from the
  cache if Muse picks the same concept.
- **Known risk, stated before the run:** on `santos_toward`, two riders pass each other in opposite directions. The
  post-hoc diagnostic of the first run showed that crossing-order matching can pair them wrongly. The matching is not
  changed for this run.
- **Reporting:** results are reported as they come, whatever they are.
