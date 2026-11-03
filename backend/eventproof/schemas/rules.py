"""EventProof visual/temporal rule DSL.

A rule is a typed AST with a closed set of operators. It is produced by Muse Spark (or by hand),
validated here, and evaluated by `eventproof.engine`. Nothing in a rule is ever executed as code.

Coordinates of zones and lines are normalized to [0, 1] of the frame so rules survive re-encoding
and resolution changes.
"""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

Point = tuple[Annotated[float, Field(ge=0, le=1)], Annotated[float, Field(ge=0, le=1)]]

MAX_DEPTH = 8


class Zone(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,40}$")
    polygon: list[Point] = Field(min_length=3, max_length=32)


class Line(BaseModel):
    """Directed segment a→b. 'to_left'/'to_right' are judged walking from a to b (image coordinates)."""

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,40}$")
    a: Point
    b: Point

    @model_validator(mode="after")
    def _non_degenerate(self) -> Line:
        if self.a == self.b:
            raise ValueError("line endpoints must differ")
        return self


class EntitySpec(BaseModel):
    name: str = Field(description="Role in the rule, e.g. 'package'")
    concept: str = Field(description="SAM text prompt / track label, e.g. 'blue box'", min_length=1, max_length=60)


# ---- Events: things that happen to one tracked object ----------------------------------------


class InZone(BaseModel):
    op: Literal["IN_ZONE"] = "IN_ZONE"
    zone: str
    min_frames: int = Field(default=1, ge=1, le=600, description="consecutive frames inside to count as entered")


class Dwell(BaseModel):
    op: Literal["DWELL"] = "DWELL"
    zone: str
    min_ms: float = Field(gt=0, le=600_000)
    max_speed: float | None = Field(
        default=None, gt=0, le=10,
        description="if set, only time spent (nearly) still counts: anchor speed in frame units/s, "
                    "measured over ~1/3 s, must stay <= max_speed")


class Crosses(BaseModel):
    op: Literal["CROSSES"] = "CROSSES"
    line: str
    direction: Literal["any", "to_left", "to_right"] = "any"


class With(BaseModel):
    """A relation to an object of ANOTHER tracked concept, held continuously for >= min_ms (frame-by-frame, same frame):
    'near' = anchor-to-anchor distance <= max_dist (frame units); 'on_top' = the other object's box overlaps the object's
    head band, from 15 % of its height above the box to 35 % into it (e.g. a hard hat, or an umbrella seen from above)."""

    op: Literal["WITH"] = "WITH"
    concept: str = Field(min_length=1, max_length=60, description="SAM text prompt of the other object, e.g. 'forklift'")
    relation: Literal["near", "on_top"] = "near"
    max_dist: float = Field(default=0.1, gt=0, le=1.5)
    min_ms: float = Field(default=0.0, ge=0, le=600_000)


Event = Annotated[InZone | Dwell | Crosses | With, Field(discriminator="op")]


# ---- Expressions: tri-state logic over events ---------------------------------------------------


class Occurs(BaseModel):
    op: Literal["OCCURS"] = "OCCURS"
    event: Event


class Before(BaseModel):
    """TRUE iff `first` occurs and its first occurrence precedes the first occurrence of `then`."""

    op: Literal["BEFORE"] = "BEFORE"
    first: Event
    then: Event
    within_ms: float | None = Field(default=None, gt=0)


class Not(BaseModel):
    op: Literal["NOT"] = "NOT"
    arg: Expr


class And(BaseModel):
    op: Literal["AND"] = "AND"
    args: list[Expr] = Field(min_length=2, max_length=8)


class Or(BaseModel):
    op: Literal["OR"] = "OR"
    args: list[Expr] = Field(min_length=2, max_length=8)


class Implies(BaseModel):
    op: Literal["IMPLIES"] = "IMPLIES"
    premise: Expr
    conclusion: Expr


Expr = Annotated[Occurs | Before | Not | And | Or | Implies, Field(discriminator="op")]

for _m in (Not, And, Or, Implies):
    _m.model_rebuild()


class RuleParams(BaseModel):
    """Tunable knobs. Repairs may only change these and the AST — never the evaluator."""

    anchor: Literal["center", "bottom_center"] = "center"
    max_gap_frames: int = Field(default=3, ge=0, le=120, description="unobserved frames bridged by interpolation")
    min_confidence: float = Field(default=0.0, ge=0, le=1)


class VisualRule(BaseModel):
    rule_id: str = Field(pattern=r"^[a-z][a-z0-9_\-]{0,60}$")
    version: int = Field(default=1, ge=1)
    entity: EntitySpec
    zones: list[Zone] = Field(default_factory=list, max_length=16)
    lines: list[Line] = Field(default_factory=list, max_length=16)
    check: Expr
    params: RuleParams = Field(default_factory=RuleParams)
    normalized_explanation: str = Field(default="", max_length=600)

    @model_validator(mode="after")
    def _references_resolve(self) -> VisualRule:
        zone_ids = {z.id for z in self.zones}
        line_ids = {ln.id for ln in self.lines}
        if len(zone_ids) != len(self.zones) or len(line_ids) != len(self.lines):
            raise ValueError("duplicate zone or line id")
        for ev in iter_events(self.check):
            if isinstance(ev, InZone | Dwell) and ev.zone not in zone_ids:
                raise ValueError(f"unknown zone '{ev.zone}'")
            if isinstance(ev, Crosses) and ev.line not in line_ids:
                raise ValueError(f"unknown line '{ev.line}'")
        if expr_depth(self.check) > MAX_DEPTH:
            raise ValueError(f"rule deeper than {MAX_DEPTH}")
        return self

    def context_concepts(self) -> list[str]:
        """Concepts other than the entity that the rule refers to (each needs its own tracks)."""
        return sorted({e.concept for e in iter_events(self.check) if isinstance(e, With)} - {self.entity.concept})

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def rule_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


def iter_events(expr: Expr):
    match expr:
        case Occurs(event=e):
            yield e
        case Before(first=a, then=b):
            yield a
            yield b
        case Not(arg=a):
            yield from iter_events(a)
        case And(args=xs) | Or(args=xs):
            for x in xs:
                yield from iter_events(x)
        case Implies(premise=p, conclusion=c):
            yield from iter_events(p)
            yield from iter_events(c)


def expr_depth(expr: Expr) -> int:
    match expr:
        case Not(arg=a):
            return 1 + expr_depth(a)
        case And(args=xs) | Or(args=xs):
            return 1 + max(expr_depth(x) for x in xs)
        case Implies(premise=p, conclusion=c):
            return 1 + max(expr_depth(p), expr_depth(c))
        case _:
            return 1
