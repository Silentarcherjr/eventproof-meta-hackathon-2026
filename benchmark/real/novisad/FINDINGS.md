# Real traffic footage (Pexels, Novi Sad) — the full loop on real video: findings

Pre-registration: [`PREREGISTRATION.md`](PREREGISTRATION.md), labels + manifest frozen and pushed (45bde5e) before any
model call. Machine report: [`report_novisad.json`](report_novisad.json) / [`report_novisad.md`](report_novisad.md).
Committed run evidence (rule, SAM 3.1 tracks, sealed evidence; no video): [`runs/`](runs/). CI recomputes every verdict
from those files (`backend/tests/validation/test_novisad.py`). n = 2 clips, 6 labelled objects (4 crossing). Small.

## Setup
Top-down drone view of a signalised crossing. Rule (same ambiguity as the demo's "stay"):
*"Every car must wait at least 1.5 seconds in the waiting zone before it crosses the stop line."* Truth: a car that
crosses must have stood still ≥ 1.0 s in the zone. Live calls: Muse Spark 1 (compile), SAM 3.1 2 (one per clip).

## Result (as pre-registered)
| | overall verdict | labelled objects right |
|---|---|---|
| rule compiled by Muse Spark ("before") | **2/2** | **8/8** (incl. both cars that never stopped) |
| + synthetic-grade repair r3-0 ("after") | 2/2 | **7/8** |
Missed: 0. Extra tracks: 7, all real cars, all judged PASS (correct, none crossed): 5 edge transients that the labels
listed as not labelled, plus 1 car waiting in the left lane in both clips that the labeller missed.

## What happened
- **Muse read "wait" as "stopped" this time** (its written assumption: *"'wait' interpreted as stopped still, so DWELL
  max_speed=0.05"*). In the demo run it read "stay" as any presence, which is the error Challenge Mode found. Same rule
  shape, different verb, different reading: the reason a rule must be checked, not trusted.
- **The rolling van:** the deterministic engine shows it crawled at 0.04–0.09 frame-widths/s for ~2 s while entering, then
  accelerated to ~0.25/s; it never stood still (labelled VIOLATION). Muse's threshold (≤ 0.05/s for 1.5 s) catches it.
  The repair accepted on synthetic data (≤ 0.08/s for 0.8 s) counts the crawl as standing still and passes it: **a
  threshold tuned on synthetic scenes does not transfer to this real crawl**. It is the only object it gets wrong.
- SAM 3.1 on the cropped approach: every labelled car found, crossings in the labelled order, no identity merge on the
  crossing cars (the dark car at the frame edge was split into two short tracks).

## Post-hoc notes (do not change the result)
- Label times were approximate: the van enters at ~11.6 s, not ~13.8 s as written; its verdict label is unaffected.
- One waiting car (centre-bottom of the crop) was not labelled; it is reported as an extra with the correct PASS.

## Takeaway
On real footage EventProof's loop did what it is for: it surfaced, with numbers, that a repair validated on synthetic
holdouts was too permissive for a real slow roll, while Muse's own stricter reading was right. A real deployment should
re-grade a repair on labelled footage of the target scene before accepting it; here n is too small to do more than show it.
