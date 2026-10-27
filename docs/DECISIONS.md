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
