# Decisions (ADRs)

## ADR-001 — 2026-10-27 — Repo private during build, public before submission
- Decision: create `Silentarcherjr/eventproof-meta-hackathon-2026` as **private**; switch to public only with explicit participant approval after a secrets/license audit, no later than 2026-11-03.
- Why: Participant Guide §4 says "Repositories must be public" but does not say from when. Pending answer in #questions (task C-02).
- Consequence: anonymous-access check (`curl` without credentials) is part of G7-01.

## ADR-002 — 2026-10-27 — Model output is data, never code
- Decision: Muse Spark returns a JSON DSL (validated with Pydantic, sent as `response_format: json_schema`). The engine evaluates a closed set of operators. No `eval`, no generated Python/JS in P0.
- Why: safety, reproducibility, and so judges can audit what the model decided vs. what the engine computed.

## ADR-003 — 2026-10-27 — Tri-state verdicts
- Decision: every per-object check returns TRUE / FALSE / UNKNOWN (Kleene logic). Observation gaps (occlusion, lost track) longer than `max_gap_frames` that could hide an event yield UNKNOWN, never PASS.

## ADR-004 — 2026-10-27 — Stack
- Backend Python 3.12 + FastAPI + Pydantic v2, managed with `uv`. OpenAI-compatible SDK against `https://api.meta.ai/v1` (`muse-spark-1.3` via chat completions with json_schema; `sam-3.1` via Responses API streaming, per dev.meta.ai docs checked 2026-10-27).
- SAM parsing: official `meta-sam-parser` (PyPI) / `@meta-sam/parser` (npm) preferred over hand parsing; hand parser only as a documented fallback if the official Python package lacks stream parsing.
- Frontend Next.js + TypeScript + Tailwind (to be created in G1-06).

## ADR-005 — 2026-10-27 — Work local first, cloud sessions resume from GitHub
- The participant works mostly locally on macOS and alternates with cloud dev sessions. GitHub is the source of truth; every session starts/ends with the protocol in `AGENTS.md`.

## ADR-006 — 2026-10-27 — Error taxonomy and process truth
- Ground-truth intent comes from scripted behaviour (`challenge/truth.py`: box stationary ≥ 1.0 s at the station before crossing the packing line), computed from waypoints — a different code path from the rule engine.
- Every disagreement is classified: spec_error (rule on perfect tracks ≠ intent), perception_error (perceived tracks flip a rule that is right on perfect tracks), abstained (UNKNOWN). This keeps perception (SAM) and reasoning (Muse/DSL) failures separate, as the plan requires.
- Until SAM is available, a naive mock tracker (`perception/mock.py`, `source="mock"`) stands in. Its outputs are always labelled and never presented as SAM; it doubles as a baseline later.

## ADR-007 — 2026-10-27 — Counterexample minimization claims
- Two stages: (1) greedy discrete reduction (drop objects/occluders, trim head/tail, never below 50 frames) that must preserve the *same* failure (outcome + detector verdict); (2) a boundary pair along one physical knob per family (separation, occluder duration, belt speed, stop duration): coarse 20-point grid + up to 8 bisection steps.
- Results are reported as LOCAL minima within an explicit evaluation budget, never as global minima. Both scenes of a pair are stored and re-evaluated in tests, so the flip is reproducible, not asserted.
- Decisive frames = first identity events on the failing scene (merge / lost / new id / switch vs ground truth) + the first frame where perceived tracks diverge between the pair; for spec errors (perception fine) the rule's own event frames.
- Pillow added for overlay text (HPND license; to list in LICENSE_INVENTORY).

## ADR-008 — 2026-10-27 — Frozen holdout and repair acceptance
- Hidden holdout `holdout_v1` (superseded by `holdout_v2`, see below): seeds 20000–20039 × 5 families (200 scenes), manifest with per-scene sha256 committed in 8ed7a02 before any repair code. Seeds 10000–10039 were looked at during a design scan and are therefore excluded. `load_frozen` regenerates every scene and refuses to grade on any hash drift.
- Isolation: proposers live in `repair/proposer.py`, which cannot import the holdout, grader or loop (static import-closure test); the loop checks every `RepairContext` for holdout seeds/hashes before a proposer sees it; the grader re-evaluates everything itself.
- Repairs are bounded `RulePatch` ops (DWELL threshold, DWELL max_speed, max_gap_frames, min_confidence), re-validated through the rule schema; zones, lines, entity and AST shape cannot change.
- Accept only if: safe, fixes the counterexample, 0 holdout regressions, no increase of false PASS, and holdout accuracy strictly improves. Otherwise rejected with reasons ("did not generalize" when accuracy does not improve).
- DSL extension: `DWELL.max_speed` (optional, frame units/s over ~1/3 s) so a rule can say "still in the zone", which is what the process intent means. Default unchanged; the schema field changes `rule_hash` of existing rules (recorded evidence updated).
- Until Muse access exists, the proposer is a deterministic grid search labelled `baseline-deterministic`; a Muse proposer must return the same patch JSON.
- 2026-10-27, CI finding: `holdout_v1` hashes were platform dependent (tailgate/20017 differed on Linux x86 vs macOS arm64; numpy may use FMA on arm64 so a sampled float differs in its last bit). The drift check refused to grade, as designed. Fix: scene coordinates are quantized to 1e-6 in `SceneSpec`; `holdout_v2` = same seeds and physical scenes with stable hashes. All repair verdicts and holdout metrics were re-run on v2 and are identical to v1; tailgate-0 evidence PNGs/frames identical, only scene hashes updated.

## ADR-009 — 2026-10-27 — SAM 3.1 adapter
- Hand-written strict parser for the documented wire format (`perception/sam_wire.py`) instead of `meta-sam-parser` (not installed; needs participant approval). Boxes only: x2/y2 are inclusive on the wire and converted to exclusive; frames without detections emit no line; ids are sparse. Malformed input raises with the line number — never skipped silently.
- Mask payloads (base85, alphabet unpublished) are kept opaque (`mask_ref`); a mask token ends only at `|>` followed by end of line or the next `,<id><|box;` record, so payload characters cannot break parsing.
- `SamTracker` caches the raw output by (video sha256, model, prompt, metadata) under `artifacts/sam_cache/` (untracked). Cache hits are real SAM output and are labelled `:cached` in `source_ref`.
- Credits guard: live calls need an explicit allowance (`max_live_calls`, default 0; CLI `--max-live-calls`). Without key or allowance the call raises; there is no fallback to mock.
- Challenge Mode uploads only rendered pixels to SAM; ground truth never leaves the process.
- 2026-10-27, first live call: mask tokens carry `;c=<conf>` before `data=`; the parser accepts it (optional) and stores it on `SamMask.confidence`.

## ADR-010 — 2026-10-27 — Muse rule compiler (G1-03)
- `meta/muse_rules.py`: natural language + layout (zones/lines with descriptions) → `VisualRule`. Geometry never comes from the model; zone/line ids are JSON-schema enums. `to_left`/`to_right` are translated into image directions in the prompt.
- Expression emitted as a flat node list (children = indices), rebuilt into a tree in code: each node used exactly once, no cycles, no unused nodes, arity checked; then the normal rule schema validates depth, ids and ranges. Reason: Muse expands `$ref`s, so a depth-unrolled recursive grammar cost 194,990 prompt tokens per call (measured); the node list costs ~1,420.
- `supported=false` path: the model must refuse rules the DSL cannot express (verified live on a helmet rule).
- Invalid output: one retry with the validation error, then `RuleCompileError`; invalid rules are never cached. Model output is data only.

## ADR-011 — 2026-10-27 — End-to-end runs and evidence (G1-01, G1-05)
- Ingestion (`video/ingest.py`): MP4/MOV, one video stream, ≤ 20 s, ≤ 100 MB, ≤ 3840 px. Already H.264/yuv420p/CFR/unrotated files are used byte-for-byte (hash and SAM cache key unchanged); others are re-encoded (codec, pixel format, VFR → CFR, rotation applied to pixels, odd sizes).
- Pipeline (`pipeline.py`): ingest → Muse compile → SAM (prompt = compiled entity concept) → evaluate. Unsupported/invalid rules stop before any SAM call. Evidence JSON per run under `artifacts/runs/<run_id>/` with input hashes, compiled rule + assumptions, model request/response ids, live vs cached flags, tracks hash, verdicts; sealed with `evidence_sha256` over canonical JSON, verifiable from the raw file (`verify_evidence_file`). No local paths, no key.
- API: `POST /runs` (multipart video + rule_text + layout JSON), `GET /runs/{id}` (id pattern-checked). Live SAM calls from the API need `EVENTPROOF_MAX_LIVE_SAM_CALLS` (default 0 → 503 instead of spending).

## ADR-012 — 2026-10-27 — Studio frontend (G1-06)
- Next.js 15 (App Router) + TypeScript + Tailwind 4 in `frontend/`, single page: upload, zone/line editor drawn over the video (normalized coordinates, same as the DSL), rule text, run, then verdicts, Muse's assumptions, compiled DSL, provenance, track overlay synced to the video (frame = floor(t·fps), the backend's convention) and a per-object timeline whose event markers seek to the decisive frame.
- Results are flagged "stale" as soon as the rule or layout is edited after a run, so a verdict is never shown next to inputs it was not computed from.
- Backend: each run keeps `video.mp4` (exact bytes SAM saw); `GET /runs/{id}/tracks` and `/video`; CORS origins via `EVENTPROOF_CORS_ORIGINS` (default http://localhost:3000).
- CI: Playwright smoke with the API mocked from a recorded real run (no Meta calls in CI). npm `overrides.postcss` pins the patched PostCSS (Next 15 bundles a vulnerable one; `npm audit`: 0).

## ADR-013 — 2026-10-27 — Challenge + Repair for any compiled rule; Muse as repairer
- `bind_rule` maps any rule onto the synthetic conveyor world by zone/line id (entity concept → scene label); rules referencing other ids are refused for Challenge (422), not silently remapped.
- Studio Challenge prefers spec errors (perception-independent) and, among them, the clearest case (violating object with the least time standing still). Perception errors from the mock are still listed in the suite table.
- `confirm_with_sam`: the pair's failing scene is re-scored with live SAM (1 call, needs the API allowance).
- `MuseProposer` (meta/muse_repair.py): strict-JSON RulePatch proposals; up to 3 rounds; between rounds Muse gets only VISIBLE dev results (regression counts + up to 5 examples of what a reviewer saw). Every proposal of every round is graded; none is selected by holdout score. The prompt never contains holdout seeds/hashes (test).
- Test isolation: autouse fixture redirects all caches/runs to tmp and blocks live Meta clients; it was added after a test wrote fake Muse outputs into the real cache (entries removed).

## ADR-014 — 2026-10-28 — Container stack (G5-02) and deploy proposal (G6-01)
- `compose.yaml` at the repo root: `backend` (python:3.12-slim + ffmpeg, uv --frozen) and `studio` (Next.js standalone). Base images pinned by digest; both run as non-root with healthchecks.
- The studio proxies `/api/*` to the backend (Next rewrites, build-time `API_PROXY_TARGET`, proxy timeout 300 s), so a deployment exposes one origin and the backend needs no public port. Outside Docker nothing changes (`NEXT_PUBLIC_API_URL` default stays `http://localhost:8000`).
- Runs/caches live in a named volume; `EVENTPROOF_ARTIFACTS=./artifacts` binds the repo folder to reuse local caches. A bind mount by default would break on Linux hosts (root-owned folder vs. non-root container user).
- Live SAM stays at 0 by default in compose. Hosting is not chosen: `docs/DEPLOY_PROPOSAL.md` lists options and prices and flags that Muse calls from the API are not capped yet, which must be fixed (or the server run without a key) before any public URL.

## ADR-015 — 2026-10-28 — Third data tier, before/after view, guards, ledger
- final_v1 (report-only): 5 Challenge families at new seeds 40000–40039 + 3 shift families that exist only there. Frozen and
  pre-registered (56001c5) before the evaluator existed; evaluator tested on dev seeds only (fb46a25); run once (1764a16). It
  evaluates every recorded proposal (accepted and rejected), so it also measures whether the grader's choice transfers.
  `eventproof.validation` cannot be imported by grader/proposers/studio/API (test); the API serves only the report file.
- Studio headline and before/after use the FIRST accepted proposal in the proposer's order, never the best holdout score
  (ranking by holdout would reintroduce selection on it).
- The before/after chart plots `engine.evaluator.zone_steps`, the same counter `_eval_event` decides from (refactor, no
  behaviour change: all published numbers re-checked by tests/regression).
- Guards: `LiveBudget` shared per process for Muse (compile attempts, repair rounds); SAM keeps its per-process allowance;
  showcase mode forces both to 0 and refuses uploads; per-IP rate limit; one heavy job at a time.
- Evidence ledger per run (`eventproof/ledger.py`): file hashes, model/request ids live vs cached, holdout manifests, seal check.
- Real-video validation (separate worktree, merged 296433c): blind labels frozen by a manifest before any model run.
