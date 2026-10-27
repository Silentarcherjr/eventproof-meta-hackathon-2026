# Cloud / local runbook

## Resume
```
git clone https://github.com/Silentarcherjr/eventproof-meta-hackathon-2026.git   # fresh env only
cd eventproof-meta-hackathon-2026 && git pull --ff-only
cd backend && uv sync && uv run pytest
python3 ../scripts/progress.py check
```
Then follow the start-of-session list in `AGENTS.md`.

## Credentials (by NAME only)
- `MODEL_API_KEY` — Meta Model API. Local: `backend/.env` (gitignored). Cloud: environment secret. Never echo it.
- GitHub — `gh` CLI auth of the participant account. No extra collaborators.

## Commands
- Tests: `cd backend && uv run pytest`
- Lint: `cd backend && uv run ruff check .`
- Tracker: `python3 scripts/progress.py set <ID> <STATE> --sha <sha>` then commit.
- Meta smoke tests (spend real credits, a few cents): `cd backend && uv run python ../scripts/check_meta_api.py muse|sam`
- API dev server: `cd backend && uv run uvicorn eventproof.api.main:app --reload`

## Rollback
- Every stable point gets a tag `rc-YYYYMMDD-N`. Roll back with `git checkout <tag>`; never force-push main.
