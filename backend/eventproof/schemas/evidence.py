"""Evaluator output: verdicts with the exact frames that justify them."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Tri = Literal["TRUE", "FALSE", "UNKNOWN"]
Verdict = Literal["PASS", "VIOLATION", "UNKNOWN"]
OverallVerdict = Literal["PASS", "FAIL", "UNKNOWN", "NO_OBJECTS"]


class EventTrace(BaseModel):
    op: str
    target: str
    status: Tri
    frame: int | None = None
    timestamp_ms: float | None = None
    reason: str = ""


class ObjectVerdict(BaseModel):
    object_id: int
    verdict: Verdict
    first_frame: int
    last_frame: int
    events: list[EventTrace]
    explanation: str


class RuleReport(BaseModel):
    rule_id: str
    rule_version: int
    rule_hash: str
    track_source: str
    track_source_ref: str | None
    overall: OverallVerdict
    objects: list[ObjectVerdict]
