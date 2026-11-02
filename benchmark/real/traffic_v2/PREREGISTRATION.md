# Real traffic footage v2 (Pexels, Wroclaw): full loop + baselines (pre-registered BEFORE any model call)

Date: 2026-11-02. Within the participant's approved budget. Reported separately; never used to tune anything.

## Footage
[Busy Urban Intersection in Wroclaw, Poland](https://www.pexels.com/video/busy-urban-intersection-in-wroclaw-poland-36366105/)
(Pexels License; not redistributed). Downloaded `15424065_1280_720_60fps.mp4`, sha256 `3afd7df6…0e3a`. Fixed camera on a
footbridge, looking along the approach lanes. Two 19 s clips, crop x0–330 y60–350, 10 fps, metadata stripped:
- `wroclaw_w1.mp4` (t 38.5–57.5 s): a red-light queue stands still, then drives off → 6 labelled cars, all PASS.
- `wroclaw_w2.mp4` (t 62.5–81.5 s): green light, free flow → 10 labelled cars, none stops, all VIOLATION.
Hashes in `labels/*.json`, frozen in `labels/MANIFEST.json`. Screened and rejected before any call: Taiwan 9322364 (almost no
crossing traffic in its 16 s), the winter intersection 36418720 (time-lapse with cuts).
Because every labelled car in a clip has the same intended verdict, object matching order cannot change the scores.

## Rule and truth (unchanged from the Novi Sad set)
"Every car must wait at least 1.5 seconds in the waiting zone before it crosses the stop line." Truth: stood still ≥ 1.0 s.

## Runs (all reported, whatever the result)
1. EventProof full loop (`real_video run`): Muse Spark compiles the rule for this layout (1 compile), SAM 3.1 tracks each
   clip (2 calls); before = Muse's rule, after = the synthetic-accepted repair r3-0. Per-object and per-clip agreement.
2. Muse Wonder's reading of the same text + layout (1 compile, up to 2 attempts), evaluated on the same committed tracks.
3. Muse Spark alone from video (`spark_alone`, same prompt version), 5 runs per clip (10 calls).
4. Pooled over all 4 real traffic clips (Novi Sad a/b + Wroclaw w1/w2): labelled objects right for each detector, with a
   Wilson 95 % interval; overall clip verdicts; counts-exact rate for Spark alone. Perspective note: speeds are in frame
   units, so distant cars move fewer pixels; any effect of that is reported, not corrected.
No layout, rule text, crop, label or threshold is changed after seeing model output.
