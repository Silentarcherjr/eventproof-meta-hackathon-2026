"""HTTP API: health, deterministic evaluation over supplied tracks, and end-to-end runs.

Live SAM calls from the API need an explicit per-process allowance: EVENTPROOF_MAX_LIVE_SAM_CALLS
(default 0 = cached results only), so an exposed server cannot spend credits unattended.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ValidationError

from eventproof import pipeline
from eventproof.engine.evaluator import evaluate
from eventproof.meta.client import MetaApiUnavailable, MetaSettings
from eventproof.meta.muse_rules import Layout, MuseRuleCompiler
from eventproof.perception.sam import LiveCallLimit, SamTracker
from eventproof.schemas.evidence import RuleReport
from eventproof.schemas.rules import VisualRule
from eventproof.schemas.tracks import TrackSet
from eventproof.video.ingest import MAX_BYTES, VideoRejected

app = FastAPI(title="EventProof", version="0.1.0")


@app.get("/health")
def health() -> dict:
    s = MetaSettings.from_env()
    return {"status": "ok", "meta_api_key_configured": bool(s.api_key), "muse_model": s.muse_model, "sam_model": s.sam_model}


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
        _tracker = SamTracker(max_live_calls=int(os.environ.get("EVENTPROOF_MAX_LIVE_SAM_CALLS", "0")))
    return _tracker


def get_compiler() -> MuseRuleCompiler:
    global _compiler
    if _compiler is None:
        _compiler = MuseRuleCompiler()
    return _compiler


@app.post("/runs", response_model=pipeline.Evidence)
def create_run(video: Annotated[UploadFile, File()],
               rule_text: Annotated[str, Form(min_length=3, max_length=2000)],
               layout: Annotated[str, Form()]) -> pipeline.Evidence:
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


@app.get("/runs/{run_id}", response_model=pipeline.Evidence)
def get_run(run_id: str) -> pipeline.Evidence:
    try:
        return pipeline.load(run_id)
    except ValueError:
        raise HTTPException(400, "invalid run id") from None
    except FileNotFoundError:
        raise HTTPException(404, "run not found") from None
