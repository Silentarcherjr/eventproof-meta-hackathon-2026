# Real footage (Pexels) — SAM 3.1 line-crossing check: 2 of 8 found

Pre-registration: [`PREREGISTRATION.md`](PREREGISTRATION.md) and hand labels [`labels.json`](labels.json), committed and
pushed (c1907a7) before the SAM call. Data: [`report_pexels.json`](report_pexels.json), raw SAM output in
[`sam_cache/`](sam_cache/). CI recomputes the report from the cached output (`backend/tests/validation/test_line_check.py`).
Perception only; no rule, repair or grader was tuned on this.

## Clip and run
[Packages Moving on a Conveyor Belt](https://www.pexels.com/video/packages-moving-on-a-conveyor-belt-5903898/)
(Pexels License), fixed camera, real parcels flowing right to left, cluttered background. Prepared at 10 fps, 640×360,
203 frames, metadata stripped. 1 live `sam-3.1` call, prompt `package`, 2026-11-01. The second clip (4156510) was
excluded before any call because its camera moves.

## Result (as pre-registered)
| metric | value |
|---|---|
| labelled crossings of the center line | 8 |
| found by SAM 3.1 + crossing geometry | **2** (blue parcel at 3.0 s vs. label 2.9 s; black parcel at 4.5 s vs. 4.2 s) |
| missed | 6 (labels at 5.6, 7.5, 10.0, 13.6, 15.9, 18.8 s) |
| false crossings in the window | 0 |
| distinct track ids among the matches | 2 (no merge) |

## Why (diagnosis after the fact, not used to change the result)
- SAM returned exactly **16 objects on every frame** (the documented per-frame cap), and **all 16 tracks start at frame 0**.
  No parcel that entered the view later got a track.
- 9 of the 16 slots are static objects (background clutter behind the belt, bags in the foreground), so the cap was spent
  at frame 0 on things that never move.
- Track 0 starts on the DURU box at the line and drifts to the right (0.51 → 0.71): it re-attached to other parcels.

So on this kind of scene (cluttered, continuous inflow) a single SAM 3.1 request misses most late arrivals. This is a
perception limit, and it matters: a parcel without a track is invisible to every rule downstream (no verdict at all, not
a FAIL). Checks like this one are how it shows up. Possible mitigations, **not run**: crop to the belt before tracking, or track in short overlapping
windows so new objects get slots. Either would be a new, separately pre-registered run reported next to this one.
