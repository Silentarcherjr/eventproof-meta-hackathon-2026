# Real footage (Pexels) — v2: cropped + windowed SAM 3.1 finds 8 of 8 crossings

Pre-registration: [`PREREGISTRATION_v2.md`](PREREGISTRATION_v2.md), pushed (3fa782f) before any v2 call, after v1.
Data: [`report_pexels_v2.json`](report_pexels_v2.json), per-window log [`tracking_v2.json`](tracking_v2.json), raw SAM
output in [`sam_cache/`](sam_cache/). CI recomputes it from the cached output (`backend/tests/validation/test_line_check_v2.py`).
**v1 stays the first result:** [`REPORT_pexels.md`](REPORT_pexels.md) (single request on the full frame: 2/8).

## What changed from v1
Only the perception input: the frame is cropped to the belt (x 160–640, y 60–300) and SAM 3.1 tracks 8 overlapping
50-frame windows; window tracks are stitched by box IoU. Same video, prompt, labels, line, window and matching as v1.
8 live `sam-3.1` requests, 2026-11-01 (≤ 400 billed frames, ≤ $0.21).

## Result
| metric | v1 (full frame, 1 request) | **v2 (crop + windows, 8 requests)** |
|---|---|---|
| labelled crossings found | 2 / 8 | **8 / 8** |
| false crossings in the scored window | 0 | **0** |
| median \|Δt\| to the hand label | 0.3 s | **0.2 s** (max 0.8 s: small cardboard box, 10.8 s vs. 10.0 s) |
| distinct track ids among the matches | 2 | **8** (no parcel merged with another) |

Every SAM crossing outside the scored window is the DURU box at 0.2 s, which was labelled "on the line at t=0, not scored".

## Limits
- One clip, n = 8 crossings; labels by one person from frame sheets (±0.3 s).
- The crop and window length were chosen by hand for this scene after seeing why v1 failed: a per-scene setup step, like
  drawing zones, not a general fix. Windows still reach the cap (up to 16 objects per frame in the 150–200 window), so a
  busier scene would need smaller crops or shorter windows.
- Perception only: no parcel stops in this clip, so the stop-at-inspection rule and the repair loop are not tested here.

## Takeaway
On real footage, SAM 3.1's per-request object cap is the binding constraint, not box quality: once each request sees few
enough objects, every parcel is found within 0.2 s (median) of a human label with no identity merges. EventProof's job is
to make such limits visible before a rule is trusted; v1 shows the failure, v2 the fix, both pre-registered.
