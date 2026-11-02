"""HTTP API: health, deterministic evaluation over supplied tracks, and end-to-end runs.

Credit and abuse guards (all per server process, read at start-up):
- EVENTPROOF_MAX_LIVE_SAM_CALLS / EVENTPROOF_MAX_LIVE_MUSE_CALLS: live (billed) Meta calls allowed; default 0 =
  cached results only. Each Muse request (rule compile attempt, repair round) and each SAM video counts as one.
- EVENTPROOF_MODE=showcase: no uploads and both allowances forced to 0, so only cached model outputs are served;
  recorded runs can be opened, challenged and repaired (Muse from its cache, baseline is free). Default "local".
- EVENTPROOF_RATE_LIMIT="<n>/<seconds>" per client IP for POST requests (default 30/600), and one heavy job at a
  time (others get 429). EVENTPROOF_TRUST_PROXY=1 takes the client IP from X-Forwarded-For (set it only behind
  your own proxy).
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
from collections import deque
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, ValidationError

from eventproof import pipeline, studio
from eventproof.engine.evaluator import evaluate
from eventproof.meta.client import LiveBudget, MetaApiUnavailable, MetaSettings
from eventproof.meta.muse_rules import Layout, MuseRuleCompiler
from eventproof.perception.sam import LiveCallLimit, SamTracker
from eventproof.schemas.evidence import RuleReport
from eventproof.schemas.rules import VisualRule
from eventproof.schemas.tracks import TrackSet
from eventproof.video.ingest import MAX_BYTES, VideoRejected

app = FastAPI(title="EventProof", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_methods=["GET", "POST"], allow_headers=["*"],
                   allow_origins=os.environ.get("EVENTPROOF_CORS_ORIGINS", "http://localhost:3000").split(","))


MODE = os.environ.get("EVENTPROOF_MODE", "local")
DEMO_RUNS = [r for r in os.environ.get("EVENTPROOF_DEMO_RUNS", "").split(",") if pipeline.RUN_ID_RE.match(r)]
_muse_allowed = int(os.environ.get("EVENTPROOF_MAX_LIVE_MUSE_CALLS", "0"))
MUSE_BUDGET = LiveBudget("muse-spark", 0 if MODE == "showcase" else _muse_allowed)
_n, _, _w = os.environ.get("EVENTPROOF_RATE_LIMIT", "30/600").partition("/")
RATE_N, RATE_WINDOW = int(_n), float(_w or 600)
TRUST_PROXY = os.environ.get("EVENTPROOF_TRUST_PROXY") == "1"
_hits: dict[str, deque] = {}
_hits_lock = threading.Lock()
_heavy = threading.Semaphore(1)
HEAVY = re.compile(r"^/runs(/[^/]+/(challenge|challenge/sam-confirm|repair|before-after|ambiguity))?$")


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for") if TRUST_PROXY else None
    return (fwd.split(",")[0].strip() if fwd else None) or (request.client.host if request.client else "?")


@app.middleware("http")
async def guards(request: Request, call_next):
    if request.method != "POST":
        return await call_next(request)
    ip, now = _client_ip(request), time.monotonic()
    with _hits_lock:
        q = _hits.setdefault(ip, deque())
        while q and now - q[0] > RATE_WINDOW:
            q.popleft()
        if len(q) >= RATE_N:
            return JSONResponse({"detail": f"rate limit: {RATE_N} requests per {RATE_WINDOW:.0f} s"}, status_code=429)
        q.append(now)
    if not HEAVY.match(request.url.path):
        return await call_next(request)
    if not _heavy.acquire(blocking=False):
        return JSONResponse({"detail": "another job is running; try again in a moment"}, status_code=429)
    try:
        return await call_next(request)
    finally:
        _heavy.release()


def _no_live_in_showcase(what: str) -> None:
    if MODE == "showcase":
        raise HTTPException(403, f"{what} is off in showcase mode (this server serves recorded runs only)")


@app.get("/health")
def health() -> dict:
    s = MetaSettings.from_env()
    t = get_tracker()
    return {"status": "ok", "mode": MODE, "meta_api_key_configured": bool(s.api_key), "muse_model": s.muse_model,
            "sam_model": s.sam_model, "live_calls_remaining": {"muse": MUSE_BUDGET.remaining,
                                                               "sam": max(0, t.max_live_calls - t.live_calls)},
            "rate_limit": f"{RATE_N}/{RATE_WINDOW:.0f}s", "demo_runs": DEMO_RUNS}


class EvaluateRequest(BaseModel):
    rule: VisualRule
    tracks: TrackSet


@app.post("/evaluate", response_model=RuleReport)
def evaluate_rule(req: EvaluateRequest) -> RuleReport:
    return evaluate(req.rule, req.tracks)


_tracker: SamTracker | None = None
_compiler: MuseRuleCompiler | None = None


def get_tracker() -> SamTracker:
    global _tracker
    if _tracker is None:
        allowed = 0 if MODE == "showcase" else int(os.environ.get("EVENTPROOF_MAX_LIVE_SAM_CALLS", "0"))
        _tracker = SamTracker(max_live_calls=allowed)
    return _tracker


def get_compiler() -> MuseRuleCompiler:
    global _compiler
    if _compiler is None:
        _compiler = MuseRuleCompiler(budget=MUSE_BUDGET)
    return _compiler


@app.post("/runs", response_model=pipeline.Evidence)
def create_run(video: Annotated[UploadFile, File()],
               rule_text: Annotated[str, Form(min_length=3, max_length=2000)],
               layout: Annotated[str, Form()]) -> pipeline.Evidence:
    _no_live_in_showcase("uploading a new video")
    try:
        lay = Layout.model_validate(json.loads(layout))
    except (json.JSONDecodeError, ValidationError) as e:
        raise HTTPException(422, f"invalid layout: {e}") from None
    suffix = Path(video.filename or "").suffix.lower()
    if suffix not in (".mp4", ".mov"):
        raise HTTPException(415, "only .mp4 / .mov uploads are accepted")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"upload{suffix}"
        with src.open("wb") as fh:
            copied = 0
            while chunk := video.file.read(1 << 20):
                copied += len(chunk)
                if copied > MAX_BYTES:
                    raise HTTPException(413, "video too large")
                fh.write(chunk)
        try:
            return pipeline.run(src, rule_text, lay, get_compiler(), get_tracker(), filename=Path(video.filename).name)
        except VideoRejected as e:
            raise HTTPException(422, f"video rejected: {e}") from None
        except (MetaApiUnavailable, LiveCallLimit) as e:
            raise HTTPException(503, str(e)) from None


def _run_file(run_id: str, name: str) -> Path:
    try:
        return pipeline.run_file(run_id, name)
    except ValueError:
        raise HTTPException(400, "invalid run id") from None
    except FileNotFoundError:
        raise HTTPException(404, "not found") from None


@app.get("/runs/{run_id}", response_model=pipeline.Evidence)
def get_run(run_id: str) -> pipeline.Evidence:
    return pipeline.Evidence.model_validate_json(_run_file(run_id, "evidence.json").read_text())


@app.get("/runs/{run_id}/tracks", response_model=TrackSet)
def get_tracks(run_id: str) -> TrackSet:
    return TrackSet.model_validate_json(_run_file(run_id, "tracks.json").read_text())


@app.get("/runs/{run_id}/video")
def get_video(run_id: str) -> FileResponse:
    return FileResponse(_run_file(run_id, "video.mp4"), media_type="video/mp4")


def _evidence(run_id: str) -> pipeline.Evidence:
    return pipeline.Evidence.model_validate_json(_run_file(run_id, "evidence.json").read_text())


@app.post("/runs/{run_id}/challenge", response_model=studio.ChallengeReport)
def run_challenge(run_id: str) -> studio.ChallengeReport:
    try:
        return studio.challenge(_evidence(run_id))
    except studio.ChallengeUnavailable as e:
        raise HTTPException(422, str(e)) from None


@app.post("/runs/{run_id}/challenge/sam-confirm")
def confirm_challenge(run_id: str) -> dict:
    try:
        return studio.confirm_with_sam(_evidence(run_id), get_tracker())
    except studio.ChallengeUnavailable as e:
        raise HTTPException(422, str(e)) from None
    except (MetaApiUnavailable, LiveCallLimit) as e:
        raise HTTPException(503, str(e)) from None


class RepairRequest(BaseModel):
    proposer: str = "muse"


@app.post("/runs/{run_id}/repair", response_model=studio.RepairRun)
def run_repair_endpoint(run_id: str, req: RepairRequest) -> studio.RepairRun:
    if req.proposer not in ("muse", "baseline"):
        raise HTTPException(422, "proposer must be 'muse' or 'baseline'")
    try:
        return studio.repair(_evidence(run_id), req.proposer, muse_budget=MUSE_BUDGET)
    except studio.ChallengeUnavailable as e:
        raise HTTPException(422, str(e)) from None
    except (MetaApiUnavailable, LiveCallLimit) as e:
        raise HTTPException(503, str(e)) from None


@app.post("/runs/{run_id}/before-after")
def before_after_endpoint(run_id: str, req: RepairRequest) -> dict:
    if req.proposer not in ("muse", "baseline"):
        raise HTTPException(422, "proposer must be 'muse' or 'baseline'")
    try:
        return studio.before_after(_evidence(run_id), req.proposer)
    except studio.ChallengeUnavailable as e:
        raise HTTPException(422, str(e)) from None


class AmbiguityRequest(BaseModel):
    text: str


@app.post("/runs/{run_id}/ambiguity")
def ambiguity_endpoint(run_id: str, req: AmbiguityRequest) -> dict:
    """Two readings of a rule text (Muse Spark, Muse Wonder) with this run's layout, and the minimal pair of synthetic
    scenes that separates them. Cached readings are free; live ones take from the Muse allowance."""
    try:
        return studio.ambiguity(_evidence(run_id), req.text, budget=MUSE_BUDGET)
    except studio.ChallengeUnavailable as e:
        raise HTTPException(422, str(e)) from None
    except (MetaApiUnavailable, LiveCallLimit) as e:
        raise HTTPException(503, str(e)) from None


@app.get("/runs/{run_id}/stored/{key}")
def stored_result(run_id: str, key: str) -> dict:
    """Reopen a run: a Challenge/Repair result computed earlier (404 if it was never computed)."""
    if not pipeline.RUN_ID_RE.match(run_id) or key not in studio.STORED:
        raise HTTPException(400, "invalid run id or key")
    out = studio.stored(run_id, key)
    if out is None:
        raise HTTPException(404, "not computed yet")
    return out


@app.get("/runs/{run_id}/certificate")
def run_certificate(run_id: str, chosen: str | None = None, format: str = "html"):  # noqa: A002
    """One-page rule certificate built from this run's recorded results (no model call). ?format=json for the data."""
    from eventproof import certificate

    _run_file(run_id, "evidence.json")  # validates the id and that the run exists
    cert = certificate.build(run_id, chosen=chosen)
    return cert if format == "json" else HTMLResponse(certificate.render_html(cert))


@app.get("/runs/{run_id}/ledger")
def run_ledger(run_id: str) -> dict:
    """Build (or rebuild) the run's evidence ledger: every file hash, model/request ids, holdout manifests."""
    from eventproof import ledger

    _run_file(run_id, "evidence.json")  # validates the id and that the run exists
    return ledger.write(run_id)


FINAL_REPORT = Path(__file__).resolve().parents[3] / "benchmark" / "final" / "report_final_v1.json"


@app.get("/final-report")
def final_report() -> dict:
    """The pre-registered final test report (read-only file; the final set itself is not loaded by the API)."""
    if not FINAL_REPORT.is_file():
        raise HTTPException(404, "no final report")
    return json.loads(FINAL_REPORT.read_text())


@app.get("/runs/{run_id}/challenge/files/{name}")
def challenge_file(run_id: str, name: str) -> FileResponse:
    allowed = name in studio.CHALLENGE_FILES or name in studio.AMBIGUITY_FILES or re.fullmatch(r"decisive_f\d{4}\.png", name)
    if not pipeline.RUN_ID_RE.match(run_id) or not allowed:
        raise HTTPException(400, "invalid file")
    p = pipeline.RUNS_DIR / run_id / "challenge" / name
    if not p.is_file():
        raise HTTPException(404, "not found")
    return FileResponse(p)
