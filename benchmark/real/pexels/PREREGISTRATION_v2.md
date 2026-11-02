# Pexels line-crossing check — v2 (pre-registered BEFORE any v2 SAM call)

Date: 2026-11-01. Approved by the participant after seeing v1 (2/8). v1 (`REPORT_pexels.md`) stays the first result;
v2 is reported next to it and does not replace it. Code: `backend/eventproof/validation/line_check_v2.py`.

## What changes (and only this)
v1 failed because SAM 3.1 filled its 16-objects-per-frame cap at frame 0 (9 slots on static clutter) and gave no track to
parcels arriving later. v2 changes perception input only:
1. **Crop to the belt:** x 160–640, y 60–300 of the 640×360 frame (480×240), chosen from the first frame. It removes most
   background shelves and the foreground bags; the center line x = 320 lies inside it.
2. **Overlapping windows:** 50 frames (5 s) every 25 frames → 8 requests (frames 0–50, 25–75, …, 175–203).
3. **Stitching:** each window's track continues the global track with the highest mean box IoU on the shared frames
   (≥ 0.3, one-to-one); otherwise it starts a new id. On frames already covered, the earlier window's box is kept.

## Unchanged from v1
Same prepared video (sha256 `f7fca634…b2`), prompt `package`, labels (`labels.json`, 8 crossings, untouched), line
x = 0.5 of the full frame, crossing definition, scored window [1.0, 19.0] s, matching tolerance 1.0 s, metrics.

## Cost
8 requests × 50 billed frames = 400 frames, ≤ $0.21 by the bound in `docs/COSTS.md`. Cap: `--max-live-sam-calls 8`.
No crop, window, IoU threshold or prompt is changed after seeing the v2 output; a v3 would need its own pre-registration.
