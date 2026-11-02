# Real traffic footage (Pexels, Novi Sad) — full EventProof loop (pre-registered BEFORE any model call)

Date: 2026-11-01. Approved by the participant. Reported separately; never used to tune rules, thresholds, repairs or the grader.

## Footage
[High Angle View of a Busy Intersection in Novi Sad, Serbia](https://www.pexels.com/video/high-angle-view-of-a-busy-intersection-in-novi-sad-serbia-15411757/)
(Pexels License; not redistributed). Downloaded file `15411757-hd_1280_720_25fps.mp4`, sha256 `a0464e68…92ff`.
Hovering drone, top-down; landmarks stay at the same pixels at 0 %, 50 % and 100 % of the clip (camera checked fixed).
Frames 0–20 and 1014–1056 are black (fades). Prepared clips (metadata stripped, crop x1010–1280 y330–720, 10 fps, ≤ 20 s
because the ingest accepts at most 20 s): `novisad_approach_a.mp4` (frames 46–520) and `novisad_approach_b.mp4`
(frames 521–1013). Hashes in `labels/*.json`, frozen in `labels/MANIFEST.json`.

## Analogy to the synthetic world (same rule shape, same process truth)
Waiting zone before the crossing = `inspection`; stop line at the near edge of the crossing = `packing_entry`. Process truth
(unchanged): a car that crosses the line must have **stood still ≥ 1.0 s** in the zone. The rule text deliberately keeps
the demo's ambiguity ("wait" like "stay"):
> Every car must wait at least 1.5 seconds in the waiting zone before it crosses the stop line.

## Labels (hand, from 2–5 fps frame sheets)
- clip a: red car rolls through (VIOLATION); silver sedan stands ~4 s then crosses (PASS); white van rolls through at
  ~50 px/s without stopping, i.e. a rolling stop (VIOLATION); 2 white cars waiting in the left lane all clip (PASS).
  Expected overall FAIL.
- clip b: white SUV stands ≥ 5.5 s then crosses (PASS); the same 2 waiting cars (PASS). Expected overall PASS.
- Edge transients (< 2 s partly in view) are not labelled; tracks on them are reported as extra.

## Procedure (existing `real_video run`, unchanged logic)
`uv run python -m eventproof.validation.real_video run --labels ../benchmark/real/novisad/labels --videos ../benchmark/real/novisad/videos --max-live-sam-calls 2 --max-live-muse-calls 1 --out ../benchmark/real/novisad/report_novisad.json`
- Muse Spark compiles the rule once (1 live call; the second clip reuses it). SAM 3.1 tracks each clip once (2 live calls,
  ≤ 387 frames, ≤ $0.21 by the COSTS.md bound). The deterministic engine judges every object.
- "before" = the rule as Muse compiled it; "after" = the same rule with the first grader-accepted Muse repair of the recorded
  demo run (made on synthetic data before this footage was chosen). Matching objects: as documented in `real_video.py`.
- Reported as is: per-object and per-clip agreement with the labels, before and after; misses and extras.
No layout, rule text, crop or label is changed after seeing any model output.
