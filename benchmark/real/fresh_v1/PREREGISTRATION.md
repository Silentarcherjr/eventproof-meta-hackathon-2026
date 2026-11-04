# Fresh real footage: a new camera view, labels proposed by Muse Spark and confirmed by a person (pre-registered BEFORE any model call)

Date: 2026-11-04. Written and committed before any Muse or SAM call on these clips.

**Why.** Every earlier real-footage result uses 46 labelled objects from views we had already studied. This set uses a
camera view never used before in this repository, with the compiler frozen as it is now (anchor schema, `muse-spark-1.3`).
It also measures a second question: can Muse Spark lower the cost of building an audit set (the contract block says a
city needs 188 error-free labelled tickets to promise <= 2 % false tickets)?

**Footage.** Pexels video 35172060 (Pexels License; not redistributed): a static top-down drone view of a signalised
intersection, 720x1280, 56 s. Two approaches, each cut into three windows (0-18.7, 18.7-37.4, 37.4-56.2 s), cropped,
10 fps, metadata stripped: `drone_south_{1,2,3}.mp4` (cars come from the top) and `drone_north_{1,2,3}.mp4` (cars come
from the bottom). Layout (waiting zone and stop line) drawn by hand on the first frame of each approach, in
`drafts/*.json`, before any model call.

**Rule** (unchanged from the earlier traffic sets): *"Every car must wait at least 1.5 seconds in the waiting zone before
it crosses the stop line."* Truth per car: VIOLATION if it crosses the line without standing still for 1.5 s in the zone
first; PASS if it crosses after standing still >= 1.5 s. Cars that never cross in the window are not labelled.

**Labelling protocol.**
1. Muse Spark 1.3 watches each clip (Files API, `input_video`, strict JSON) and proposes, for every car that crosses the
   line: a description, the crossing time, the time it stood still in the zone and PASS / VIOLATION. One live call per
   clip (6 in total). Proposals are stored as they come in `proposals/`.
2. The participant reviews every clip in the studio's label review page, watching the video: accepts, corrects or
   deletes each proposal and adds any car Muse missed. Only the participant's final labels count as truth.
3. The final labels are frozen with `real_video check --freeze` (sha256 manifest) **before** any rule compile or SAM call
   on these clips.

**Run.** `real_video run --anchor-schema --labels fresh_v1/labels --videos fresh_v1/videos`, at most 6 live Muse
compiles and 6 live SAM calls. No change to the engine, compiler, prompts or thresholds after seeing anything.

**Primary outcome:** labelled cars right / wrong / abstained / not tracked for the rule Muse Spark compiles, pooled over
the 6 clips, with a Wilson 95 % interval.

**Secondary outcomes:**
- Label assistance: share of Muse proposals the participant accepted unchanged (matched by crossing time within 1.0 s
  and the same verdict), corrected, deleted, and cars Muse missed.
- The tickets the rule issues on these clips through the robustness sweep and the approval gate (`review/triage.py`):
  how many are ROBUST, how many depend on an open choice, how many would auto-issue once the open choices are approved.

**Reporting.** Everything is reported as is, including failures and any clip with no crossings. No re-run, no repair.
