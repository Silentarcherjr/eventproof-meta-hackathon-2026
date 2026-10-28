# EventProof

**AI builds visual apps. Then tries to break them.**

Give EventProof a short video and a rule in plain language ("every package must pass inspection before entering the shipping area"). It:

1. **Builds** a detector — Muse Spark turns the rule into a typed, auditable temporal DSL; SAM 3.1 turns the video into object tracks.
2. **Breaks** it — Challenge Mode renders controlled synthetic scenes (crossings, occlusions, brief entries, near-threshold timing) with independent ground truth and searches for the smallest scene that fools the detector.
3. **Repairs** it — Muse Spark proposes a bounded change to the rule/tracking parameters.
4. **Proves** it — the repair is accepted only if it improves results on a frozen holdout it never saw.

> Status: under construction for the Meta Global AI Developer Hackathon 2026 (build window Oct 27 – Nov 4, 2026). See `docs/STATUS.md`.

## Why Meta models
- **Muse Spark** (`muse-spark-1.3`): natural language → structured DSL via JSON-schema output; repair proposals.
- **SAM 3.1** (`sam-3.1`): text-prompted video segmentation + stable track IDs.
The deterministic engine never executes model-generated code.

## Evidence
- Final independent test (pre-registered, evaluated once): `benchmark/final/REPORT_final_v1.md`
- Recorded demo run with its evidence ledger: `docs/evidence/runs/20261028T023754Z-a922b5bb/`
- Real-video validation protocol: `docs/REAL_VIDEO_PROTOCOL.md` · Showcase deploy runbook: `deploy/README.md`

## Run it (Docker)
```
docker compose up --build        # studio: http://localhost:3000, API: http://localhost:8000/health
```
Without a key everything starts and uploads answer 503. Put `MODEL_API_KEY` in `backend/.env` (see `.env.example`)
and allow live calls explicitly (default 0, cached results are free):
`EVENTPROOF_MAX_LIVE_MUSE_CALLS=6 EVENTPROOF_MAX_LIVE_SAM_CALLS=3 docker compose up`. Reopen a recorded run with `/?run=<run_id>`.
Images are pinned by digest and dependencies come from `uv.lock` / `package-lock.json`.

## Quickstart (backend, without Docker)
```
cd backend
uv sync
uv run pytest
cp ../.env.example .env   # add MODEL_API_KEY for live Meta calls
uv run uvicorn eventproof.api.main:app --reload
```

## Team
Solo developer (Indie Developer track). See `docs/NEW_WORK.md`.

## License
Pending — see `docs/compliance/LICENSE_INVENTORY.md`.
