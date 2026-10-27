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
