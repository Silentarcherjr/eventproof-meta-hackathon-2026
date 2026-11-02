# Real-footage check on a public Pexels clip (pre-registered BEFORE any SAM call)

Date: 2026-11-01. Approved by the participant (2 Pexels clips; ~1 SAM call each). Reported separately; never used to
tune rules, repairs or the grader. Videos are not committed (`*.mp4` is git-ignored); source URL + sha256 are in
`labels.json`, so anyone can download and verify them.

## What this tests (and what it does not)
Perception on real footage of real parcels on a real conveyor: does SAM 3.1 + EventProof's line-crossing geometry find
the parcels that cross a line, at the right time, without merging or splitting them? It does **not** test the
stop-at-inspection rule or the repair loop: no parcel in the clip stops, so there is no PASS case.

## Clips
- `pexels_5903898` (20.3 s, fixed camera): used.
- `pexels_4156510`: excluded after looking at the frames and before any model call: the camera moves, so no fixed line
  can be defined.

## Truth (labels.json)
Vertical line at x = 0.5 of the frame; a crossing = a parcel's center moving from right of the line to left of it.
8 crossings in the scored window [1.0, 19.0] s, read by hand from frame sheets. Two parcels sit on the line at the first
or last frame and are not scored.

## Procedure and metrics (fixed now)
1. One SAM 3.1 call, prompt `package`, on the prepared 10 fps file (203 frames). Raw output committed in `sam_cache/`.
2. A SAM crossing = a track whose box center x goes from > 0.5 to ≤ 0.5 between consecutive detections (every such event
   counts, so jitter shows up as extra crossings).
3. Matching: labels and SAM crossings sorted by time, one-to-one, |Δt| ≤ 1.0 s (optimal assignment).
4. Report: matched / 8 (recall), SAM crossings in the window that match no label (false crossings), median |Δt|,
   number of distinct SAM track ids among the matched crossings (8 = no merges), every crossing listed.
No threshold, prompt or line position is changed after seeing the SAM output.
