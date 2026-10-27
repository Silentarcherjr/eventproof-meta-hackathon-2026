"""HTTP API. G0 surface: health + deterministic rule evaluation over supplied tracks."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from eventproof.engine.evaluator import evaluate
from eventproof.meta.client import MetaSettings
from eventproof.schemas.evidence import RuleReport
from eventproof.schemas.rules import VisualRule
from eventproof.schemas.tracks import TrackSet

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
