"""Bounded repair patches: the only way a repair may change a detector.

A patch is a short list of typed operations on a `VisualRule` (thresholds and tracking params). It
cannot touch the evaluator, the ground truth, zones/lines geometry, the entity or the AST shape.
Patches are data: whoever proposes them (baseline search or Muse Spark), they are validated here
and applied by this module; nothing proposed is ever executed.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from eventproof.schemas.rules import Dwell, VisualRule, iter_events


class SetDwell(BaseModel):
    op: Literal["set_dwell_min_ms"] = "set_dwell_min_ms"
    zone: str
    value: float = Field(ge=100, le=10_000)


class SetDwellStill(BaseModel):
    """Count only time spent (nearly) still in the zone: DWELL.max_speed, in frame units/s."""

    op: Literal["set_dwell_max_speed"] = "set_dwell_max_speed"
    zone: str
    max_speed: float = Field(ge=0.01, le=0.5)


class SetMaxGap(BaseModel):
    op: Literal["set_max_gap_frames"] = "set_max_gap_frames"
    value: int = Field(ge=0, le=30)


class SetMinConfidence(BaseModel):
    op: Literal["set_min_confidence"] = "set_min_confidence"
    value: float = Field(ge=0, le=0.95)


PatchOp = Annotated[SetDwell | SetDwellStill | SetMaxGap | SetMinConfidence, Field(discriminator="op")]


class RulePatch(BaseModel):
    ops: list[PatchOp] = Field(min_length=1, max_length=3)

    def describe(self) -> str:
        parts = []
        for o in self.ops:
            match o:
                case SetDwell(zone=z, value=v):
                    parts.append(f"DWELL({z}) >= {v / 1000:.2f} s")
                case SetDwellStill(zone=z, max_speed=v):
                    parts.append(f"DWELL({z}) counts only while speed <= {v:.2f}/s")
                case SetMaxGap(value=v):
                    parts.append(f"max_gap_frames = {v}")
                case SetMinConfidence(value=v):
                    parts.append(f"min_confidence = {v:.2f}")
        return "; ".join(parts)


class PatchError(ValueError):
    pass


def _structure(rule: VisualRule) -> dict:
    """Everything a patch must leave untouched: identity, geometry, entity and AST shape (thresholds blanked)."""
    d = rule.model_dump(mode="json")
    for k in ("version", "params", "normalized_explanation"):
        d.pop(k)

    def blank(x):
        if isinstance(x, dict):
            return {k: (None if k in ("min_ms", "max_speed") else blank(v)) for k, v in x.items()}
        if isinstance(x, list):
            return [blank(v) for v in x]
        return x

    return blank(d)


def apply_patch(rule: VisualRule, patch: RulePatch) -> VisualRule:
    d = rule.model_dump(mode="json")
    dwell_zones = {ev.zone for ev in iter_events(rule.check) if isinstance(ev, Dwell)}
    for o in patch.ops:
        match o:
            case SetDwell(zone=z, value=v):
                if z not in dwell_zones:
                    raise PatchError(f"rule has no DWELL on zone '{z}'")
                _set_dwell(d["check"], z, "min_ms", v)
            case SetDwellStill(zone=z, max_speed=v):
                if z not in dwell_zones:
                    raise PatchError(f"rule has no DWELL on zone '{z}'")
                _set_dwell(d["check"], z, "max_speed", v)
            case SetMaxGap(value=v):
                d["params"]["max_gap_frames"] = v
            case SetMinConfidence(value=v):
                d["params"]["min_confidence"] = v
    d["version"] = rule.version + 1
    d["normalized_explanation"] = f"{rule.normalized_explanation} [patched: {patch.describe()}]"[:600]
    out = VisualRule.model_validate(d)  # re-validated through the same schema as any new rule
    if _structure(out) != _structure(rule):
        raise PatchError("patch changed rule structure")
    return out


def _set_dwell(node, zone: str, key: str, value: float) -> None:
    if isinstance(node, dict):
        if node.get("op") == "DWELL" and node.get("zone") == zone:
            node[key] = value
        for v in node.values():
            _set_dwell(v, zone, key, value)
    elif isinstance(node, list):
        for v in node:
            _set_dwell(v, zone, key, value)
