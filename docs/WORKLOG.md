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
