# EventProof

**Rule QA for vision AI.** Write a visual rule in plain English. Muse Spark and SAM 3.1 build a detector for it in
seconds. EventProof then tries to break that detector, repairs it, and only keeps the repair if it holds on cases it
never saw.

![Before and after the repair: the same failing case judged by both rules](docs/media/before_after.png)

## The problem
An AI model can turn "every box must stay 1.5 s in inspection before packing" into a working video check almost
instantly. It also silently picks an interpretation. In our recorded run, Muse Spark wrote its assumption down:
*"'Stay at least 1.5 seconds' is DWELL … with any motion allowed, not requiring stopped."* With that reading, a box that
never stops but drifts slowly through the zone passes inspection: a **false PASS**, the dangerous kind of error for
compliance, safety and quality checks. Nobody sees it until it costs something.

EventProof is for the people who deploy such rules (warehouse and production-line QA, safety and compliance teams):
before a rule goes live, it shows where the rule is wrong, why, and whether a fix really generalizes.

## What it does
1. **Build.** Muse Spark compiles the sentence into a typed temporal rule (strict JSON schema, validated by Pydantic,
   never executed as code) and lists its assumptions. SAM 3.1 tracks every object in the video. A deterministic engine
   returns a verdict per object, with the decisive frames.
2. **Break.** Challenge Mode renders synthetic scenes whose truth is known (drive-through, brief stop, occlusion,
   tailgating) and searches for the smallest scene that fools the rule: a minimal pair of clips that differ in one
   factor, one judged wrong and one judged right. The failing scene is re-checked with real SAM 3.1 tracks to separate
   a wrong rule from wrong perception.
3. **Repair.** Muse Spark diagnoses the failure and proposes bounded patches (at most 3 operations on thresholds and
   conditions; no free-form code). It revises over up to 3 rounds using only visible development cases.
4. **Prove.** An independent grader accepts a patch only if it fixes the counterexample with **zero regressions** on a
   frozen hidden holdout. A third, pre-registered test set (including scene types no rule was designed for) is
   evaluated once, after every decision is recorded.

![Studio: rule, tracks, verdict and Challenge Mode results](docs/media/studio.png)

## Results (recorded run `20261028T023754Z-a922b5bb`, all numbers from committed files)
| Step | Result |
|---|---|
| Build | Rule compiled by Muse Spark; SAM 3.1 tracked both boxes (110/110 boxes matched on the reference clip, median IoU 1.00); verdict FAIL for the box that tailgated into packing at frame 88. |
| Break | 150 synthetic scenes → 44 failures. Clearest: a box that stood still 0.00 s but spent 1.84 s in the zone → rule says PASS, truth FAIL. Minimal pair on belt speed (0.1178 vs 0.1180). Real SAM 3.1 tracks confirm it: a rule error, not perception. |
| Repair | Muse Spark, 3 rounds, 8 patches. **2 accepted, 6 rejected** (1–26 holdout regressions each). Round 1 was too strict and rejected; the accepted patch counts time only while the box stands still (≤ 0.08 of the frame per second, ≥ 0.80 s). |
| Hidden holdout (200 scenes) | **144 → 164 correct**, dangerous false PASS 40 → 21, **0 regressions**. |
| Final test (pre-registered, 320 scenes, evaluated once) | Same scene types: **141 → 158 / 200**. Three scene types never seen before: **109 → 117 / 120**. 0 regressions. Accepted patches gained +17 on average vs. +7.3 for rejected ones: the grader's choices transfer. |
| Real footage (Pexels, 8 labelled parcel crossings, perception only) | Single SAM 3.1 request: 2/8 (object cap). Cropped + 5 s windows: **8/8**, 0 false, median 0.2 s. |
| Same final test with **real SAM 3.1 tracks** (80 scenes, pre-registered, 80 live calls) | **71 → 76 / 80**, false PASS **5 → 0**, 0 regressions; the only errors left are 4 abstentions behind an occluder. SAM gets 10/10 tailgating scenes right where the mock tracker gets 2/10. |

Full comparison (hand-written rule, Muse rule, Muse repair, baseline grid repair): [`benchmark/REPORT.md`](benchmark/REPORT.md).
Final test protocol and results: [`benchmark/final/`](benchmark/final/) (SAM 3.1 pass: [`benchmark/final/sam_v1/`](benchmark/final/sam_v1/REPORT_sam_v1.md)). Each recorded run has a hash-sealed evidence
ledger (file hashes, model request ids, live vs. cached outputs) that anyone can re-verify.

## Why Meta models
- **Muse Spark (`muse-spark-1.3`)** does the two reasoning-heavy jobs: rule compilation through a constant-size strict
  JSON schema (~1.4k prompt tokens; it refuses rules it cannot express, e.g. "workers must wear a helmet") and failure
  diagnosis + repair proposals.
- **SAM 3.1 (`sam-3.1`)** gives text-prompted video tracks with stable ids. It keeps two overlapping boxes apart where
  a naive tracker merges them (5/5 tailgating cases right with SAM, 0/5 with the mock tracker) and confirms
  counterexamples on real tracks.
- Meta API spend: **$0.74** of the $150 credits before the 80-call SAM 3.1 final-test pass (bounded at ≤ $4.3). Live calls need explicit per-process
  allowances (default 0); everything else is served from a cache of recorded responses.

## Honest limits
- The large-scale evidence is synthetic (a conveyor world with scripted truth). Holdout and primary final scoring use a
  deterministic mock tracker (n = 200–320); an 80-scene subset of the final test was re-run with real SAM 3.1 tracks and
  gives the same conclusion (the mock is pessimistic on tailgating and occlusion).
- Real public footage (one Pexels clip, cluttered, parcels arriving continuously; n = 8 hand-labelled line crossings,
  perception only): a single SAM 3.1 request found **2 of 8**, because it fills its 16-objects-per-frame cap at the first
  frame and later parcels get no track ([v1](benchmark/real/pexels/REPORT_pexels.md)). Cropped to the belt and tracked in
  overlapping 5 s windows: **8 of 8**, 0 false, median 0.2 s from the label ([v2](benchmark/real/pexels/REPORT_pexels_v2.md)).
  Both pre-registered; the crop is a per-scene setup step.
- On one never-seen scene type (slow belt with a stop) Muse's patches leave 2–3 errors that a deterministic grid search
  fixes. Reported, not tuned away.
- Real phone-video validation has a blind-labelling protocol ([`docs/REAL_VIDEO_PROTOCOL.md`](docs/REAL_VIDEO_PROTOCOL.md)); results will be reported separately.

## Run it
```
docker compose up --build        # studio http://localhost:3000 · API http://localhost:8000/health
```
Replay the recorded run with no key and no credits (it ships in [`demo/`](demo/)):
`EVENTPROOF_ARTIFACTS=./demo/showcase docker compose up --build`, then open
`http://localhost:3000/?run=20261028T023754Z-a922b5bb`. For live runs put `MODEL_API_KEY` in `backend/.env` and allow
calls explicitly: `EVENTPROOF_MAX_LIVE_MUSE_CALLS=6 EVENTPROOF_MAX_LIVE_SAM_CALLS=3 docker compose up`.

Without Docker: `cd backend && uv sync && uv run pytest && uv run uvicorn eventproof.api.main:app` and
`cd frontend && npm ci && npm run dev`.

Engineering: FastAPI + Pydantic backend, Next.js studio, 221 backend tests + Playwright end-to-end tests in CI,
regression tests that recompute every published number, images pinned by digest. Showcase deployment (no key, no
uploads, rate-limited) in [`deploy/`](deploy/).

## Repository map
- `backend/eventproof/` — `meta/` (Muse Spark, SAM 3.1 clients), `engine/` (deterministic evaluator), `challenge/`
  (renderer, scene families, counterexample search), `repair/` (patches, proposers, grader), `validation/` (final test,
  real video), `ledger.py`
- `frontend/` — studio (upload, rule, zones, timeline, Challenge, before/after)
- `benchmark/` — holdout and final manifests, reports · `docs/` — evidence, decisions, protocols

## Team
Solo developer (Indie Developer track), built during the hackathon window (Oct 27 – Nov 4, 2026). See `docs/NEW_WORK.md`.

## License
To be added before submission — see `docs/compliance/LICENSE_INVENTORY.md`.
