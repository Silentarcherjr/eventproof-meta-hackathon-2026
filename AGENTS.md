# EventProof — instructions for development sessions

EventProof is a solo (Indie Developer) entry for the Meta Global AI Developer Hackathon 2026.
Build window: 2026-10-27 → 2026-11-04 21:00 America/Panama (= 21:00 EST). All code here is new work from 2026-10-27.

## Start of every session (local or cloud)
1. `git status && git fetch && git pull --ff-only` (in a fresh cloud env: clone the repo; never assume local files survive).
2. Read in order: `docs/SESSION_HANDOFF.md` → `docs/PROGRESS.md` → `.progress/tasks.json` → `docs/DECISIONS.md` → `docs/CLOUD_RUNBOOK.md`.
3. Check reality (CI, branches, tests) — **CI + SHA + evidence beat the text of the tracker**.
4. Pick ONE `READY` task, set it `IN_PROGRESS` in `.progress/tasks.json`.

## End of every session
1. Run `make test` (or `cd backend && uv run pytest`).
2. Commit small, push, confirm the push landed.
3. Update `.progress/tasks.json`, `docs/PROGRESS.md`, `docs/WORKLOG.md` (append-only), `docs/SESSION_HANDOFF.md`, `docs/STATUS.md`, `docs/COSTS.md`.
4. Chat summary format: `GATE | DONE_VERIFIED | IN_PROGRESS | BLOCKED | COMMITS/PRS | TESTS | META API REAL | COSTO | PRÓXIMO PASO`.

## Hard rules
- Task states: TODO, READY, IN_PROGRESS, BLOCKED, IN_REVIEW, DONE_VERIFIED, FAILED, DEFERRED. `DONE_VERIFIED` needs tests + merged SHA.
- Never invent metrics, never present mocks/replays as live Meta calls. Mocks are labelled `source: "mock"`.
- Model output is never executed: Muse emits DSL JSON validated by Pydantic; the engine runs known operators only.
- Secrets only via env (`MODEL_API_KEY`); never log or commit them. Never paste raw API responses with headers into docs.
- Human-only decisions: repo visibility change, spending beyond budget, licenses/terms, adding people, final submission.
- Dev tooling is not part of the product; Meta models (Muse Spark, SAM 3.1) are what power the product. Keep those roles distinct in docs.

## Layout
- `backend/` — FastAPI + Pydantic. `eventproof/schemas` (DSL, tracks, evidence), `eventproof/engine` (deterministic evaluator), `eventproof/meta` (Muse + SAM clients), `eventproof/challenge` (synthetic renderer, counterexample search).
- `frontend/` — Next.js studio (not yet created).
- `docs/` — tracker, decisions, compliance. `.progress/tasks.json` is the canonical task registry.
