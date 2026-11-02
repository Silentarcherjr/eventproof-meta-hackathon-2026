# EventProof

**AI-generated vision software that doesn't just claim to work, but actively searches for evidence that it might be
wrong.** Say a rule in plain English over a video. Muse Spark builds the vision check, SAM 3.1 tracks the objects, Muse
Wonder independently re-reads the rule. Then EventProof attacks its own check, finds the smallest scene that fools it,
repairs it, and only trusts the repair if it holds on unseen scenes and on labelled real footage. Every rule ends with a
one-page **certificate** a reviewer can sign, or refuse.

**Who needs it now.** Cities have started issuing stop-sign tickets from AI cameras: Takoma Park, Maryland issues $40
citations from automated stop-sign cameras since January 8, 2026 (a four-year state pilot; a city study found violation
rates up to 87% at some intersections), and Virginia passed a law in April 2026 allowing AI cameras to cite flagrant
stop-sign and crosswalk violations. What counts as a "full stop" is a rule someone writes; a privacy expert told IEEE
Spectrum that such systems' claims are *"rarely backed up by independent studies that validate what these AI technologies
can really do."* EventProof is that check, before deployment, for the **traffic-safety program manager** who signs off
on the rule and the **staff reviewer** who approves every citation. A false PASS is a dangerous driver who is never
cited; a false FAIL is a $40 ticket for a resident who did stop. The same loop applies to any zone-and-time rule a camera
enforces (inspection steps on a line, waiting zones, restricted areas).

**What it caught, on real footage (labels frozen before any model call):**
- A repair that passed every synthetic test **missed a real rolling stop and every car that never stopped** far from the
  camera: 16/30 labelled cars, against 27/30 (0 wrong verdicts) for the rule Muse Spark compiled.
- A new rule typed in the studio, *"Every car must remain behind the stop line for at least 2 seconds"*: **both Muse Spark
  and Muse Wonder read it as "be present", not "stop"**, so the two cars on the clip that never stopped pass. Two models
  agreeing is not proof; the certificate checks the rule against the clip's labels and says **NOT CERTIFIED (3/5)**.
- Asked to judge the same clips directly from video, **Muse Spark alone** got every clip verdict right but counted
  crossings and violations exactly in only 11/25 runs.

**At a glance:** 3 Meta models (Muse Spark, Muse Wonder, SAM 3.1) · 27/30 cars right on real traffic footage from 2 cities
(0 wrong verdicts) · per-rule certificate · one-command replay with no API key (`docker compose`) · 250+ backend tests,
CI recomputes every published number · MIT licensed.

![Real footage: the same SAM 3.1 tracks judged by two readings of "wait"](docs/media/real_traffic.png)

## The problem
An AI model can turn a sentence like "every car must wait 1.5 s before the stop line" into a working video check almost
instantly. It also silently picks an interpretation, and the choice decides the verdict:
- On **real drone footage of a crossing** (above), Muse Spark read "wait" as *standing still* and caught a van that
  crawls through without ever stopping. A repair that had passed every synthetic test read "still" as *slower than
  0.08 frame widths/s* and **let that real rolling stop pass**.
- In our recorded warehouse run, Muse Spark read "stay at least 1.5 s" as *"any motion allowed, not requiring stopped"*,
  so a box that never stops but drifts through inspection passes: a **false PASS**.

Both are the dangerous kind of error for compliance, safety and quality checks, and nobody sees them until they cost
something. The same loop serves anyone who deploys a visual rule (traffic enforcement, warehouse and production-line QA,
site safety): before a rule goes live, it shows where the rule is wrong, why, and whether a fix really generalizes.

Sources for the deployment facts above: [MoCo Show, 2026-01-07](https://mocoshow.com/?p=121089) and
[2025-12-08](https://mocoshow.com/?p=119749) (Takoma Park pilot, $40 fine, staff review of every citation);
[The Baltimore Banner, 2026-01-07](https://www.thebanner.com/community/transportation/artificial-intelligence-takoma-park-stop-RVZ4ACYBYREI3N2MEQ3IBJM76A/)
(87% violation rates in the city study); [WTVR](https://www.wtvr.com/news/local-news/ai-cameras-virginia-stop-signs-june-17-2026)
(Virginia SB84); [IEEE Spectrum, 2025-07-05](https://spectrum.ieee.org/ai-intersection-monitoring) (quote: Daniel Schwarz, NYCLU).

## What it does
1. **Build.** Muse Spark compiles the sentence into a typed temporal rule (strict JSON schema, validated by Pydantic,
   never executed as code) and lists its assumptions. SAM 3.1 tracks every object in the video. A deterministic engine
   returns a verdict per object, with the decisive frames.
   **Two readings:** Muse Wonder reads the same sentence independently. If the two rules behave differently, EventProof
   shows the smallest pair of scenes that separates them ("the box never stopped but was inside 1.53 s: PASS or FAIL?")
   and the user picks the meaning, instead of a model picking it silently.
2. **Break.** Challenge Mode renders synthetic scenes whose truth is known (drive-through, brief stop, occlusion,
   tailgating) and searches for the smallest scene that fools the rule: a minimal pair of clips that differ in one
   factor, one judged wrong and one judged right. The failing scene is re-checked with real SAM 3.1 tracks to separate
   a wrong rule from wrong perception.
3. **Repair.** Muse Spark diagnoses the failure and proposes bounded patches (at most 3 operations on thresholds and
   conditions; no free-form code). It revises over up to 3 rounds using only visible development cases.
4. **Prove.** An independent grader accepts a patch only if it fixes the counterexample with **zero regressions** on a
   frozen hidden holdout. A third, pre-registered test set (including scene types no rule was designed for) is
   evaluated once, after every decision is recorded. Real labelled footage is the last check (it caught the repair above).
5. **Certify.** One printable page per rule (`/runs/<id>/certificate`, "Rule certificate" in the studio): the sentence,
   both readings and the one the reviewer chose, the counterexamples, hidden-holdout and final-test results, every
   labelled real clip it was checked on, model request ids and file hashes. Its status follows fixed rules: a wrong
   verdict on labelled footage → NOT CERTIFIED; an object perception never tracked → CONDITIONAL (perception gap); a
   repair with no field check yet → REPAIR CONDITIONAL. No model writes it.

![Before and after the repair: the same failing case judged by both rules](docs/media/before_after.png)

## Results on real footage (labels frozen and pushed before any model call)
**Pooled over 5 real traffic clips (30 hand-labelled cars, 2 cities):** Muse Spark's rule → SAM 3.1 → engine judged
**27/30 cars right** (2 abstained, 1 car SAM 3.1 never tracked, **0 wrong verdicts**; Wilson 95 % 0.74–0.97). The repair
that passed every synthetic test: **16/30**. Muse Spark alone from the video: right clip verdict 25/25 runs, but counted
crossings and violations exactly in only 11/25. [pooled](benchmark/real/traffic_v3/FINDINGS.md) · first pooled result
(4 clips, 22/24 vs 13/24): [here](benchmark/real/traffic_v2/FINDINGS.md)

| Test | Result |
|---|---|
| **New rule typed in the studio** (Novi Sad clip, *"remain behind the stop line for at least 2 seconds"*) | Muse Spark and Muse Wonder both read it as presence, not stopping (0/150 synthetic scenes where they differ). All 10 cars PASS, including the 2 that never stopped. Challenge Mode: 36/150 failures. Certificate vs the clip's frozen labels: **NOT CERTIFIED, 3/5**. [run](docs/evidence/runs/20261102T080747Z-6b0ae7d4) |
| **Traffic, Wroclaw** — footbridge view along the road; 2 clips, 16 labelled cars (6 wait at red, 10 drive through on green) | Muse Spark's rule: 14/16 (2 abstained). Synthetic-accepted repair: **6/16** — it passes all 10 cars that never stop, because far from the camera they move under its 0.08 frame-widths/s "still" threshold (perspective). [findings](benchmark/real/traffic_v2/FINDINGS.md) |
| **Traffic, full loop** — Pexels drone view of a crossing in Novi Sad; 2 clips, 6 labelled cars (2 stop, 2 roll through, 2 wait); 1 Muse + 2 SAM calls | Rule compiled by Muse Spark: **8/8 labelled objects right**, both clip verdicts right, incl. a real rolling stop. Same rule + the repair accepted on synthetic data: **7/8** — it passes the rolling stop. SAM 3.1 found every labelled car. [findings](benchmark/real/novisad/FINDINGS.md) |
| **Baseline: Muse Spark alone** — same 2 clips, rule and labels; Muse Spark watches the video and answers directly; 5 runs per clip | Overall verdict right in 10/10 runs (the red car is obvious), but crossings and violations counted right in only **5/10** — **0/5 on the clip with the rolling stop**. The rolling van is flagged in 1/5 runs, and in 3/5 runs it reports waiting cars as crossing. EventProof: 8/8 objects, deterministic, with evidence. [findings](benchmark/real/spark_alone/FINDINGS.md) |
| **Parcels, perception** — Pexels conveyor clip, 8 hand-labelled line crossings | One SAM 3.1 request on the full frame: **2/8** (it fills its 16-objects-per-frame cap at frame 0, later parcels get no track). Cropped to the belt, 5 s overlapping windows: **8/8**, 0 false, median 0.2 s from the label. [v1](benchmark/real/pexels/REPORT_pexels.md) · [v2](benchmark/real/pexels/REPORT_pexels_v2.md) |

## Results on synthetic scenes with known truth (recorded run `20261028T023754Z-a922b5bb`)
| Step | Result |
|---|---|
| Build | Rule compiled by Muse Spark; SAM 3.1 tracked both boxes (110/110 boxes matched on the reference clip, median IoU 1.00); verdict FAIL for the box that tailgated into packing at frame 88. |
| Break | 150 synthetic scenes → 44 failures. Clearest: a box that stood still 0.00 s but spent 1.84 s in the zone → rule says PASS, truth FAIL. Minimal pair on belt speed (0.1178 vs 0.1180). Real SAM 3.1 tracks confirm it: a rule error, not perception. |
| Repair | Muse Spark, 3 rounds, 8 patches. **2 accepted, 6 rejected** (1–26 holdout regressions each). Round 1 was too strict and rejected; the accepted patch counts time only while the box stands still (≤ 0.08 of the frame per second, ≥ 0.80 s). |
| Hidden holdout (200 scenes) | **144 → 164 correct**, dangerous false PASS 40 → 21, **0 regressions**. |
| Final test (pre-registered, 320 scenes, evaluated once) | Same scene types: **141 → 158 / 200**. Three scene types never seen before: **109 → 117 / 120**. 0 regressions. Accepted patches gained +17 on average vs. +7.3 for rejected ones: the grader's choices transfer. |
| **Two readings** (Muse Spark vs. Muse Wonder, 8 phrasings of the same rule, 150 scenes) | Both models compiled 6; same behaviour on 4; **"wait" and "remain" read differently** (Spark: standing still, Wonder: just inside) → verdicts differ on 45/150 scenes; minimal pair found automatically (belt speed 0.11777 vs 0.11797: 1.53 s vs 1.47 s inside). In the traffic scene Wonder also reads "wait" as standing still. [findings](benchmark/ambiguity/FINDINGS.md) |
| Same final test with **real SAM 3.1 tracks** (80 scenes, pre-registered, 80 live calls) | **71 → 76 / 80**, false PASS **5 → 0**, 0 regressions; the only errors left are 4 abstentions behind an occluder. SAM gets 10/10 tailgating scenes right where the mock tracker gets 2/10. |

Full comparison (hand-written rule, Muse rule, Muse repair, baseline grid repair): [`benchmark/REPORT.md`](benchmark/REPORT.md).
Final test protocol and results: [`benchmark/final/`](benchmark/final/) (SAM 3.1 pass: [`benchmark/final/sam_v1/`](benchmark/final/sam_v1/REPORT_sam_v1.md)).
Each recorded run has a hash-sealed evidence ledger (file hashes, model request ids, live vs. cached outputs) that anyone
can re-verify, and CI recomputes every number above from committed files (no video, no API key).

![Studio: rule, tracks, verdict and Challenge Mode results](docs/media/studio.png)

## Why Meta models
- **Muse Spark (`muse-spark-1.3`)** does the two reasoning-heavy jobs: rule compilation through a constant-size strict
  JSON schema (~1.4k prompt tokens; it refuses rules it cannot express, e.g. "workers must wear a helmet") and failure
  diagnosis + repair proposals.
- **Muse Wonder (`muse-wonder-1.0`)** gives an independent second reading of every rule through the same strict schema,
  so EventProof can detect ambiguous sentences and ask the user, instead of trusting one model's interpretation.
- **SAM 3.1 (`sam-3.1`)** gives text-prompted video tracks with stable ids. It keeps two overlapping boxes apart where
  a naive tracker merges them (5/5 tailgating cases right with SAM, 0/5 with the mock tracker) and confirms
  counterexamples on real tracks.
- Meta API spend for the whole build: at most about $6 of the $150 credits ($0.74 read from Billing before the real-footage
  and SAM final-test passes, plus their per-frame bounds). Live calls need explicit per-process allowances (default 0);
  everything else is served from a cache of recorded responses.

## Honest limits
- Real footage is small: 4 traffic clips (24 labelled cars, 2 cities) and 1 conveyor clip (8 crossings), labelled by one
  person from frame sheets. It shows concrete failures and fixes; it is not an accuracy benchmark. Crops are a setup step.
- The large-scale evidence is synthetic (a conveyor world with scripted truth). Holdout and primary final scoring use a
  deterministic mock tracker (n = 200–320); an 80-scene subset re-run with real SAM 3.1 tracks gives the same conclusion
  (the mock is pessimistic on tailgating and occlusion).
- A repair that passes synthetic holdouts can still be too permissive on real footage (the traffic van above): repairs
  should be re-graded on labelled footage of the target scene before deployment.
- On one never-seen synthetic scene type (slow belt with a stop) Muse's patches leave 2–3 errors that a deterministic
  grid search fixes. Reported, not tuned away.
- A protocol for clips recorded by the user is ready ([`docs/REAL_VIDEO_PROTOCOL.md`](docs/REAL_VIDEO_PROTOCOL.md)).

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

Engineering: FastAPI + Pydantic backend, Next.js studio, 245 backend tests + Playwright end-to-end tests in CI,
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
MIT ([`LICENSE`](LICENSE)) for the code in this repository. Third-party components and media keep their own licenses
(`docs/compliance/LICENSE_INVENTORY.md`); the Pexels clips are not redistributed, only referenced by URL and sha256.
