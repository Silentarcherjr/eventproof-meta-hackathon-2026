# Worklog (append-only — never delete entries, including failures)

## 2026-10-27 · session 1 · local macOS · orchestrator
- Read master plan v3 and Participant Guide (guide stored privately outside repo, sha256 f13e3551…596e). Built rules matrix (`docs/compliance/`).
- Read dev.meta.ai docs: Muse structured output (chat completions + `response_format.json_schema`, recursive schemas → HTTP 400) and SAM 3.1 (Responses API, `input_video` via `file_id`/URL, wire format `<Nf>id<|box;…|>`, min 50 frames billed, 16 objects/frame, official parser `meta-sam-parser`/`@meta-sam/parser`).
- Created repo skeleton, tracker (`.progress/tasks.json`, 36 tasks) + generator `scripts/progress.py`.
- Implemented typed DSL (`backend/eventproof/schemas/rules.py`) and deterministic tri-state evaluator (`engine/evaluator.py`), FastAPI `/health` + `/evaluate`.
- Tests: `uv run pytest` → 21 passed; `ruff check` clean.
- Meta smoke test: `check_meta_api.py muse` → `BLOCKED` (no MODEL_API_KEY; credits not claimed). No Meta credits spent.
- Issues: (1) a hypothesis property test failed on a 1e-12 edge-tolerance case → test now excludes the tolerance band (behaviour intended). (2) Running the unvetted `meta-sam-parser` PyPI package was denied by the local permission guard; SAM parser choice deferred to G1-04 (needs participant OK to install it).
- Open design note: Muse strict schemas cannot be recursive; G1-03 must send a depth-bounded (non-recursive) schema and convert it to the recursive AST.
- Pushed be4394d to private repo, tag hackathon-start-2026-10-27. CI run 40567887973: success. G0-02, G0-05, G1-02 → DONE_VERIFIED.
- Author email rewrite (participant request): both commits re-authored to the GitHub noreply address with original dates preserved (filter-branch), force-pushed by the participant. New SHAs: ec8e2f9 (tag hackathon-start-2026-10-27), 1fb61f1. Old SHAs be4394d/598280d no longer exist. CI run 40571762720 on 1fb61f1: success. Tracker SHAs updated.

## 2026-10-27 · session 1 (cont.) · local macOS · orchestrator
- Participant request: removed development-assistant attribution from the repo (docs wording neutral, session instructions file renamed to `AGENTS.md`, commit trailers removed). History rewritten again before any public release; new first commit 039c084 (tag `hackathon-start-2026-10-27`). Needs participant force-push.
- G2-01: `eventproof/challenge/scene.py` (seeded SceneSpec, canonical conveyor family) + `render.py` (integer-only numpy drawing → bit-identical frames; ffmpeg H.264 yuv420p single-thread bitexact; oracle ground truth TrackSet; manifest with scene/frames/mp4 sha256).
- Tests: 69 passed. Same seed ⇒ same frames and MP4 sha256 (verified locally, ffmpeg 8.1.1); GT boxes match drawn pixels; oracle verdict matches generator intent on 30 seeds.
- Finding (real, not staged): with a 0.5 s DWELL threshold, boxes merely driving through the inspection zone (~0.6–0.9 s inside) count as inspected → false PASS. Canonical clean family now uses 1.5 s threshold and 1.2–2.0 s stops; the 0.5 s weakness is kept as a regression test and as a target for Challenge Mode.
- Sample render: seed 4 / 3 objects → scene 3bd6d51c…, frames f6ead617…, mp4 e749e90b… (local artifact, untracked).
- Rewritten history force-pushed (with lease) — main 80fd3ab, tag 039c084. CI run 40574193970 (with ffmpeg) success. G2-01 → DONE_VERIFIED; G0-02/G0-05/G1-02 re-verified on the new history.

## 2026-10-27 · session 1 (cont.) · local macOS · orchestrator — G2-02
- Added process truth (`challenge/truth.py`), 4 adversarial families (`challenge/families.py`: drive_through, brief_stop, occluded_station, tailgate), labelled mock perception (`perception/mock.py`), and suite runner with error taxonomy (`challenge/runner.py`).
- Mistake caught: first run used a 1.5 s *stationary* intent while the canonical family scripts 1.2–2.0 s stops → 6 artefactual spec errors on clean scenes. Intent fixed to ≥ 1.0 s stationary; canonical now 30/30 correct.
- **Real engine bug found by the harness:** an anchor landing exactly on the packing line (cross product 0) hid the crossing (drive_through seed 20, via mock jitter). Fixed CROSSES to compare against the last strictly-sided observation; regression test added. DWELL failure reason text clarified.
- Results (mock perception, NOT SAM; 30 seeds/family; `benchmark/reports/`): with DWELL 1.5 s → canonical 30/30 correct; drive_through 11 spec errors (slow belt transit > 1.5 s counts as inspection); brief_stop 3 spec errors (near threshold); occluded_station 11 perception errors (identity loss → false alarm); tailgate 19 perception errors with false PASS (merged detection hides an uninspected box) + 6 abstained. With DWELL 0.5 s spec errors dominate (e.g. canonical 22/30).
- Tests: 81 passed; ruff clean.
- CI run 40575797601 (801df32): success → G2-02 DONE_VERIFIED.

## 2026-10-27 · session 1 (cont.) · local macOS · orchestrator — G3-01
- `challenge/minimize.py` (reduction + boundary pair, CLI with `--seed auto`), `challenge/replay.py` (identity events, perception divergence, decisive PNGs, side-by-side H.264 replay with perceived-track overlays), `render.encode_frames` refactor.
- Fixed during development: (1) first bisection stopped at an abstention and returned a non-minimal pair (t 0 vs 1) → grid + bisection with fallback bracket; (2) "merged" falsely reported for boxes that merely touch → coverage ≥ 0.6 instead of IoU; (3) decisive frames missed the moment the pair diverges → added perception divergence frame.
- Results (mock perception): tailgate-0 pair at separation t 0.2861 vs 0.2863 — scenes differ by ≤123 px per frame in 24 frames; failing side merges both boxes into track 0 at f45 (false PASS), passing side splits them at f53. occluded_station-1: occluder 75% vs 90% shorter → identity loss (new id) at f34 → false alarm. drive_through-0 and brief_stop-5: spec-error boundaries on belt speed / stop duration.
- Evidence committed: `benchmark/counterexamples/tailgate-0/` (2 PNG + replay.json + summary.json, 32 KB). Videos stay in `artifacts/` (untracked).
- Tests: 97 passed; ruff clean.
- CI run 40579483313 (24f5f40): success → G3-01 and P1-01 DONE_VERIFIED.

## 2026-10-27 · session 1 (cont.) · local macOS · orchestrator — G4-02 / G4-01
- G4-02: `challenge/holdout.py` + frozen manifest `benchmark/holdout/holdout_v1.json` (seeds 20000–20039 × 5 families = 200 scenes, sha256 f4ef37bb…ad82), committed alone in 8ed7a02 before any repair code. Seeds 10000–10039 were used in a design scan, so they were dropped from the holdout to keep it unseen.
- G4-01 harness: `repair/patch.py` (bounded RulePatch ops), `repair/proposer.py` (RepairContext + `baseline-deterministic` grid proposer, NOT Muse), `repair/grader.py` (independent holdout grading, accept/reject with reasons), `repair/loop.py` (CLI). Isolation tests: import closure, leak check on context, spy proposer.
- First result: threshold-only repairs could never separate a slow drive-through from a short stop (rejected for regressions). Root cause: DWELL measured time in zone, intent is "stood still". Added optional `DWELL.max_speed` to the DSL (engine change by the developer, not by the repairer).
- Results (mock perception, baseline proposer; `benchmark/repairs/`): drive_through-0 → "DWELL ≥ 2.0 s" REJECTED (holdout 144→152/200 but 11 regressions, false alarms 13→24); "DWELL still (≤0.05/s) ≥ 0.8 s" ACCEPTED (144→166/200, 0 regressions, false PASS 40→19). brief_stop-5 → "DWELL ≥ 1.7 s" rejected (1 regression), stillness patch accepted. occluded_station-1 / tailgate-0: no bounded rule patch fixes them (perception errors) → no proposal.
- Tests: 111 passed; ruff clean.
- CI run 40596781387 failed: the frozen-holdout drift check refused `tailgate/20017` on Linux (scene hash differs from macOS arm64; last-bit float difference from numpy, likely FMA). Fixed by quantizing scene coordinates to 1e-6; re-froze as `holdout_v2` (same seeds). Repair results re-run on v2: identical numbers. tailgate-0 evidence: PNGs/frames identical, scene hashes updated.

## 2026-10-27 · session 1 (cont.) · local macOS · orchestrator — G1-04
- Participant reports Meta credits are now available; `backend/.env` with `MODEL_API_KEY` not yet present on this machine, so no live call made. $0 spent.
- Re-read dev.meta.ai SAM docs (segmenting, reading-segmentation, client-libraries) for the exact wire format.
- `perception/sam_wire.py` (strict parser), `perception/sam.py` (TrackSet conversion, cached live tracker with live-call allowance, Challenge perceiver). `scripts/check_meta_api.py sam` now parses the real stream strictly. Runner: `--perception sam --max-live-calls N`.
- Tests: 130 passed (documented-format fixture with skipped frames, sparse ids and hostile mask payloads; 9 malformed-line cases; delta chunking; hypothesis round trip ground truth → wire → TrackSet over all families; fake-client request shape, cache labelling, key never cached; credits guard; SAM perceiver inside Challenge Mode).
- Participant added `MODEL_API_KEY` to `backend/.env` (verified loaded: length only, never printed).
- FIRST LIVE CALLS. SAM 3.1 on canonical seed 0 (2 objects, 120 frames): strict parser failed on line 1 — live mask token has `c=` before `data=` (not in docs' example). Fixed from the cached raw output (no second call); 5 real lines committed as fixture. SAM vs ground truth: 110/110 boxes, IoU median 1.000, ≤1 px error, stable ids, verdict correct.
- Muse Spark structured-output smoke: OK, 4.03 s, 504 completion tokens (479 reasoning).
- Evidence: `docs/evidence/2026-10-27_meta_api_smoke.md`. 2 live calls total; charge not read from Billing (UNKNOWN).
- Tests: 131 passed.
- Participant approved up to 10 SAM calls for Challenge Mode. `challenge/compare.py` ran 10 mock-failing scenes through live SAM 3.1 (10 live calls, cached): tailgate 5/5 correct with SAM (mock: 5 false PASS); occluded_station 5/5 UNKNOWN with SAM (mock: 5 false alarms). SAM kept the same id across 20–35 frame full occlusions; the detector abstains because the stop itself was hidden. Report `benchmark/reports/2026-10-27_sam_vs_mock.json`. Tests: 132 passed.
- Metric bug found in own code: `identity_events` reported "merged" for heavily overlapping boxes even when the detector returned 2 boxes; now requires fewer boxes than visible objects. Report regenerated from cache (0 new calls). Checked per object: SAM fails exactly the uninspected tailgate box and passes the inspected one in 5/5.

## 2026-10-27 · session 1 (cont.) · local macOS · orchestrator — G1-03
- `meta/muse_rules.py` (schema, prompt, node-list → tree conversion, compiler with retry + cache, benchmark CLI); `benchmark/rules/` (5 NL rules + live report); real outputs as fixture.
- Live finding: first schema (3 unrolled `$defs` levels) worked but cost 194,990 prompt tokens per call (refs expanded). Redesigned to a flat node list: ~1,420 prompt tokens, same AST.
- Results (live muse-spark-1.3): R1 canonical compiled to the same AST as the hand-written rule; R2 ("stopped") used DWELL max_speed 0.05; R3 IN_ZONE→CROSSES; R4 within_ms 6000; R5 helmet → supported=false. All first attempt.
- Muse calls this task: 6 (1 × ~195k + 5 × ~1.4k prompt tokens; 2.1k–3.8k completion tokens each).
- Tests: 150 passed.

## 2026-10-27 · session 1 (cont.) · local macOS · orchestrator — G1-01 / G1-05
- `video/ingest.py`, `pipeline.py`, API `POST /runs` + `GET /runs/{id}`; dependency `python-multipart` (FastAPI's form parser).
- Live E2E run `20261028T020157Z-6137d1f3` on a new tailgate clip: 1 live SAM call, Muse rule from cache. Overall FAIL; the violating object is the tailgater (checked against ground truth). Evidence in `docs/evidence/runs/20261028T020157Z-6137d1f3/`.
- Found in review: evidence stored the video's local path (would leak temp paths via the API) → schema /2 records the file name; raw-file verification added so older evidence still verifies.
- Tests: 163 passed (ingestion with real ffmpeg-made files: passthrough, mpeg4 + rotation normalized, too long / webm / fake rejected; pipeline incl. tamper detection, unsupported & invalid rules stop before SAM; API incl. 415/422/413/400/404 and 503 without allowance).

## 2026-10-27 · session 1 (cont.) · local macOS · orchestrator — G1-06
- `frontend/` studio (Next.js 15, TS, Tailwind): upload, zone/line editor, rule examples, results (verdicts, decisive-frame buttons, Muse assumptions, DSL, provenance), synced track overlay, timeline. Backend: run keeps video; `/runs/{id}/tracks`, `/runs/{id}/video`; CORS.
- Verified in the browser against the real backend (cached Muse + SAM, 0 new calls): FAIL, object #1 VIOLATION; clicking the f88 marker shows both boxes at the packing line. Fixed during review: overlapping labels; results kept showing after edits → stale banner; default favicon (third-party logo) removed.
- Playwright: 2 tests pass (upload → verdict/overlay/timeline/stale; API error shown). Backend: 163 passed. `npm audit`: 0 after postcss override.

## 2026-10-27 · session 1 (cont.) · local macOS · orchestrator — Challenge + Repair in the studio (G2-03, G4-01)
- Backend: challenge/repair generalized to any compiled rule (`bind_rule`, `DetectorConfig(rule=...)`), `eventproof/studio.py`, API `POST /runs/{id}/challenge`, `/challenge/sam-confirm`, `/repair`, `GET /runs/{id}/challenge/files/{name}`; `MuseProposer` with dev-feedback rounds.
- Live Muse repair development on drive_through-0: round 1 right diagnosis but too strict (21 dev regressions); with count-only feedback round 2 blamed perception; with concrete visible examples round 2 → 4 regressions, round 3 → 0; 2 of 8 proposals accepted on the holdout (144→166, 144→164). About 6 Muse calls.
- Studio: Challenge panel (suite table, counterexample in plain words, side-by-side replay, SAM confirm, Muse/baseline repair, holdout headline). Verified in the browser on run `20261028T023754Z-a922b5bb` with 1 live SAM call (spec error reproduced with real SAM). Evidence `docs/evidence/2026-10-27_studio_challenge_repair.md`.
- Bugs found: a test wrote fake Muse outputs to the real cache (fixed + autouse isolation fixture); Playwright `next build` clobbered the dev server's `.next` (separate `NEXT_DIST_DIR`).
- Process slip: a docs-writing shell command used an unquoted heredoc containing backticks, so the shell executed the quoted server commands (backend failed on the busy port; a frontend dev server started on :3001 and was killed). No files changed by it; docs then written from a script file.
- Tests: backend 171 passed; Playwright 3 passed.

## 2026-10-28 · session 1 (cont.) · local macOS · infra — Docker compose (G5-02), deploy proposal (G6-01)
- Added `backend/Dockerfile`, `frontend/Dockerfile`, `compose.yaml`, `.dockerignore`s; studio proxies `/api/*` to the backend; README "Run it (Docker)"; CI `docker` job.
- Verified: fresh `git clone` → `docker compose up --build --wait` healthy (~70 s), key-less upload 503, bad file 415. Full flow through the containers on cached inputs with the key forced empty and 0 live SAM calls: run, Challenge, baseline repair (166/200), SAM confirm from cache — identical to local results. Evidence `docs/evidence/2026-10-28_docker_compose.md`.
- Found: ESLint was linting the local `.next-e2e` build output (ignored now; CI never had that folder).
- Deploy: options and prices researched (`docs/DEPLOY_PROPOSAL.md`); nothing deployed, waiting on the human decision. Meta calls this task: 0.
- Tests: backend 171 passed, ruff clean; frontend lint, tsc, Playwright 3 passed.

## 2026-10-28 · session 1 (cont.) · local macOS · orchestrator + 1 subagent — final test, before/after, guards, ledger, real-video flow
- final_v1: frozen + pre-registered (56001c5), evaluator (fb46a25, tested on dev seeds only), single evaluation (1764a16):
  H1–H3 hold; accepted repairs 141→158/200 (0 regressions) and 109→117/118/120 of 120 on shift families. Found and reported:
  Muse's patches leave 2–3 stop_and_go errors that the baseline patch fixes.
- G5-01 before/after view (02841c4): verdict cards, counterexample video with overlay, engine counter chart, holdout + final_v1
  cards, hashes; `?run=` reopens recorded runs; headline no longer ranks by holdout score. Browser-checked at 1440 px; 2 overlay
  bugs fixed (overlay height, grid stretch).
- Guards + deploy/ + ledger + regression tests (f46798d). Showcase stack verified locally behind Caddy: no key, 403 on upload,
  Muse repair and SAM confirm served from cache, 429 after 20 POSTs, forged X-Forwarded-For ignored.
- Real-video flow by a subagent in a worktree (296433c), reviewed and merged (11fb83d).
- Demo script draft `docs/DEMO_SCRIPT.md` with a claims→source table. Docs de-contradicted (PROGRESS, COSTS, DEPLOY_PROPOSAL, HANDOFF).
- Tests: backend 221, Playwright 4; CI 40717424645 green. Meta calls: 0.
## 2026-11-01 · session 1 (cont.) · local macOS · orchestrator — README and demo replay
- Credits read by the participant: $149.26 of $150 left ($0.74 spent in total). COSTS.md updated.

  fresh clone replays it with no key (verified in Docker from a clean clone). 0 Meta calls.
## 2026-11-01 · session 1 (cont.) · local macOS · orchestrator — P1-07 live SAM 3.1 pass on final_v1
- Participant approved up to $5. Subset fixed by seed index (40000–40009 × 8 families = 80 scenes) and pre-registered in
  `benchmark/final/PREREGISTRATION_SAM_v1.md`, committed and pushed (3c32c7b) before the first call.
- `validation/sam_pass.py`: resumable tracking with a hard live-call cap, report computed from the cache only (0 calls),
  refuses to overwrite. 2 trial calls, then 78: 80/80 ok, 0 parse errors, ~7 s each. Raw outputs committed (1.4 MB).
- Result: Muse-run rule 71 → 76 / 80 with SAM tracks after the accepted patch, false PASS 5 → 0, 0 regressions; remaining
  errors are 4 abstentions (occlusion). Mock vs SAM: 68/80 same verdict; SAM 10/10 on tailgate vs mock 2/10.
- CI test recomputes the published SAM report from committed raw outputs (no API, no video re-encode).
## 2026-11-01 · session 1 (cont.) · local macOS · orchestrator — P1-08 Pexels real-footage check
- Participant approved using 2 Pexels clips. Reviewed ~15 Pexels clips first (frames only): none shows a box stopping at a
  station, so only a perception check is possible. Clip 4156510 excluded before any call (moving camera).
- Clip 5903898: hand labels (8 right-to-left crossings of the center line) + pre-registration pushed (c1907a7) before the call.
- 1 live SAM call: **2/8 crossings found**, 0 false, no merges. Cause: 16 objects/frame cap filled at frame 0 (9 of them static
  clutter), no new tracks for parcels arriving later. Reported as is; mitigations (crop, windowed tracking) not run.
- v2 (approved): crop to belt + 8 overlapping 50-frame windows + IoU stitching, pre-registered (3fa782f) before the calls.
  8 live SAM calls: **8/8 crossings, 0 false, median |dt| 0.2 s, 8 distinct ids**. v1 kept as the first result.
## 2026-11-01 · session 1 (cont.) · local macOS · orchestrator — P1-09 real traffic footage, full loop
- No usable stop-sign footage on Pexels; chose a top-down drone view of a signalised crossing in Novi Sad (15411757).
  Camera checked fixed (landmarks at 0/50/100 %). Cropped to one approach, 2 clips of <= 20 s (ingest limit).
- Labels (2 clips, 6 cars: 2 rolling through incl. a slow-roll van, 2 stopping 4-5.5 s, 2 waiting all clip) + manifest +
  pre-registration pushed (45bde5e) before any call. 1 Muse + 2 SAM live calls.
- Result: Muse compiled "wait" as stopped (max_speed 0.05): 8/8 objects right. Synthetic-accepted repair r3-0 (<= 0.08/s,
  0.8 s): 7/8, passes the slow-roll van (crawl 0.04-0.09/s). Reported as is; post-hoc label notes in FINDINGS.md.
## 2026-11-02 · session 1 (cont.) · local macOS · orchestrator — P1-10 Muse Spark-alone baseline
- Participant approved up to $60 more. Official prices read (SAM $0.20 / 1k frames; Spark $1.25 / $4.25 per 1M tokens).
- Screened ~20 more Pexels traffic clips (frames only); usable fixed-camera ones downloaded for later labelling (Wroclaw
  36366105, Taiwan 9322364); the winter one is a time-lapse with cuts (rejected).
- Baseline pre-registered (d9531ee) then run: Muse Spark judging from video, 5 runs per Novi Sad clip. Overall verdict 10/10,
  counts exact 5/10 (0/5 on the rolling-stop clip); rolling van flagged 1/5; waiting cars reported as crossing in 3/5.
- P1-11 ambiguity finder (`eventproof/ambiguity.py`): Muse Spark and Muse Wonder compile 8 phrasings; behaviour compared on
  the 150-scene dev suite with oracle tracks; minimal pair by knob bisection. Pre-registered (19bfe76). Both compiled 6;
  agreed on 4; "wait" and "remain" read differently (Spark: still, Wonder: present), 45/150 scenes differ, minimal pairs
  found (belt speed 0.11777/0.11797; stop knob 0.24434/0.24453). Wonder: 1 malformed runaway output, 1 declined.
- Studio "Two readings" panel + API `/runs/{id}/ambiguity` (854f8c6): both readings with assumptions, disagreement count, the
  minimal pair rendered as two clips with scene facts (stood still / inside the zone), the user picks the meaning. Live
  readings take from the Muse allowance; the readings cache ships in the backend image. CI 41397438034 green.
- C-04: MIT license added at the participant's choice (2026-11-02, provisional until the rules are checked).
## 2026-11-02 · session 1 (cont.) · local macOS · orchestrator — P1-12 real traffic v2 (Wroclaw) + pooled result
- Screened Taiwan (rejected: almost no crossings) and Wroclaw; 2 Wroclaw clips (red-light queue; green free flow), 16 cars
  labelled at 4 fps, frozen + pre-registered (730d351) before any call.
- Muse rule 14/16 (2 abstained); synthetic-accepted repair 6/16 (perspective: far cars < 0.08/s for 1.2-2.0 s); Wonder = Spark
  reading; Spark alone overall 10/10, counts exact 6/10. Pooled 4 clips / 24 cars: Muse rule 22/24, repair 13/24, Spark alone
  counts exact 11/20. One car crossing at 18.4 s in w2 was not labelled (post-hoc note). `real_pooled.py` + CI test.
- CI 41401253197 failed: Wonder's Wroclaw reading was not committed (cache file untracked); committed in c7ec295, CI 41401675641 green.
## 2026-11-02 · session 1 (cont.) · local macOS · orchestrator — certificate, more real footage
- Rule certificate (7812f91): one printable page per run with a fixed status rule; API `/runs/{id}/certificate`; studio links.
- Factory footage: ~15 Pexels factory/forklift/bottling clips screened; none usable for a zone-time rule with a fixed camera.
- Wroclaw w3 (t 81.5-90.6 s, 6 cars) pre-registered (45ba9ba): rule 5/6 (1 car never tracked by SAM), repair 3/6, Spark alone
  counts exact 0/5. Pooled 5 clips / 30 cars: rule 27/30 (0 wrong verdicts), repair 16/30. Certificate: untracked objects
  make a rule CONDITIONAL (perception gap), wrong verdicts make it NOT CERTIFIED.
- New-rule-on-same-video (1d9fbfb). Demo rule typed on the Novi Sad clip: "Every car must remain behind the stop line for at
  least 2 seconds before it crosses it." Muse Spark and Muse Wonder both read it as presence (no stopping); verdicts all PASS;
  Challenge Mode 36/150 failures; certificate checks the run against the clip's frozen labels: 3/5, the 2 cars that never
  stopped judged PASS -> NOT CERTIFIED. Evidence in docs/evidence/runs/20261102T080747Z-6b0ae7d4.
- P1-14 layout proposer (Muse Spark, first frame + rule text -> zone + line, strict schema, validated): pre-registered; 5 real
  clips: same verdicts as hand zones on Novi Sad (8/8); Wroclaw has no painted stop line in the crop -> proxy line, 20/30 vs
  27/30 overall. Studio: "Suggest zone and line" draft with Muse's assumptions; API POST /propose-layout within the allowance.
- Studio stepper (Build → Break → Repair → Certify) with live status per run; e2e +1 test (new rule on the same video).
- P1-15 field repair (pre-registered): Muse Spark repairs from Novi Sad failures; its patches lift Wroclaw 9 -> 19/22 but move
  min_ms to 1.0 s, 7 synthetic regressions -> 0/4 accepted; grid 3/16 accepted (<= 0.03-0.05/s, >= 0.8 s: Wroclaw 19/22,
  synthetic 166/200, 0 regressions).
- P1-16 new domains: 109 Pexels clips screened (subagent; 7 usable); 2 used (zebra one-way, bike one-way; 3 clips, 8 objects),
  pre-registered; Muse compiled NOT CROSSES(wrong direction); 7/8 right, 0 wrong verdicts. Store/toll/other clips not used
  (ambiguous truth, or rules about objects that never cross, which the label format does not cover).
- 2026-11-02 P1-17 two-object rules on real footage: 99 Pexels clips screened (subagent) for hard hats, forklifts, helmets,
  umbrellas, dogs; 1 usable (39488108, rainy crossing from above). `on_top` changed to box overlap with the head band
  (disclosed), labels frozen and pre-registered (291009f) before any call. Run: Muse escalated to WITH, SAM tracked
  pedestrians + umbrellas; overall FAIL as labelled, 2/4 right, 1 wrong (neighbour's umbrella, min_ms 0), 1 not tracked.
  `with_pilot report` recomputes with 0 calls (CI test). ≈ $0.05.
