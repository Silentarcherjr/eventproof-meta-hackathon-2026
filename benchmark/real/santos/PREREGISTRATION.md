# Santos bike path: one-way rule on real footage from a new country (pre-registered BEFORE any model call)

Date: 2026-11-03. 159 new Pexels clips were screened by a subagent. The screen covered stop signs, traffic lights,
crossings, conveyors, production lines and bike lanes, and checked three things: is the camera fixed, are both outcomes
present, and can the truth be seen on frame sheets? Only one place passed every check: a bike path beside an avenue in
Santos, Brazil, filmed from both ends with a fixed camera (0 px shift). No conveyor or production clip had a fixed camera
together with a checkable stop. The labels below were checked by hand on 1 fps sheets with the line drawn.

| clip | source | labelled crossings |
|---|---|---|
| `santos_away.mp4` | Pexels 39044387, t 18–38 s | 4: 2 ride away from the camera (VIOLATION), 2 toward it (PASS) |
| `santos_toward.mp4` | Pexels 39026834, t 3–23 s | 4: 2 ride away (VIOLATION), 2 toward (PASS) |

- **Rule (both clips):** "Cyclists may cross the line on the bike path only toward the camera (from the far end of the
  path to the near end)."
- **Hashes:** in `labels/*.json`, frozen in `labels/MANIFEST.json`.
- **Procedure:** `real_video run` (≤ 2 Muse compiles, since the layouts differ, and ≤ 2 SAM calls). It uses the same
  label format and matching as the other real sets.
  - The "after" column applies the warehouse repair r3-0, which only touches DWELL, so it does not apply here.
  - Riders far up the path that never reach the line are not labelled; they appear as "extra" if tracked.
- **Reporting:** results are reported as they come. They are added to the real-footage totals in the README with this
  file linked.
