"""Would this verdict hold up? Re-judge every object under a fixed, typed set of changes to the rule's assumptions, in
three tiers, and report per object (the first tier that flips it decides):
- FRAGILE: a small MEASUREMENT change flips it (line drawn +-1..3 % of the frame away, measured point, half the
  frames): the verdict hangs on how the scene was measured;
- DEPENDS_ON_THRESHOLD: only a THRESHOLD change flips it (required time +-20 %, the "standing still" speed x0.5 / x2):
  numbers a sentence like "come to a full stop" never states;
- DEPENDS_ON_MEANING: only a different MEANING flips it ("any motion" vs "only while still", another model's reading);
- ROBUST: nothing flips it; UNSTABLE: changes only make it undecidable (UNKNOWN).

Deterministic and model-free: the same compiled rule and SAM 3.1 tracks, the engine re-run once per variant. The
variants are the assumptions a resident contesting a ticket would challenge:
- where the line is drawn: the geometry moved by +-1..3 % of the frame along the line's normal;
- which point of the object is measured: box centre <-> bottom centre;
- how long: every DWELL time threshold +-20 %;
- what counts as standing still: "any motion" <-> "only while still" (max_speed), and the stillness threshold x0.5 / x2;
- the evidence itself: every other frame dropped (half the frame rate);
- another model's reading of the same sentence (when one is given, e.g. Muse Wonder's).
Variants are ordered by size, so the first one that flips a verdict is the smallest reported change.
"""

from __future__ import annotations

from collections.abc import Callable
from math import hypot
from typing import Literal

from pydantic import BaseModel

from eventproof.engine.evaluator import evaluate
from eventproof.engine.lint import crossing_lines
from eventproof.schemas.rules import VisualRule
from eventproof.schemas.tracks import TrackSet

Family = Literal["line_shift", "anchor", "min_ms", "stillness", "stillness_meaning", "frames", "reading"]
SHIFTS = (0.01, -0.01, 0.02, -0.02, 0.03, -0.03)
STILL_DEFAULT = 0.05  # the compiler's own "only while stopped" value (muse_rules.SYSTEM)


MEANING = ("stillness_meaning", "reading")
THRESHOLD = ("min_ms", "stillness")


class Variant(BaseModel):
    family: Family
    value: float | str
    label: str  # plain words, e.g. "line drawn 2 % of the frame lower (7 px)"
    size: int  # ordering: smaller = less of a change

    @property
    def tier(self) -> str:
        return "meaning" if self.family in MEANING else "threshold" if self.family in THRESHOLD else "measurement"


class ObjectRobustness(BaseModel):
    object_id: int
    verdict: str
    status: Literal["ROBUST", "FRAGILE", "DEPENDS_ON_THRESHOLD", "DEPENDS_ON_MEANING", "UNSTABLE"]
    flips: list[dict]  # [{variant label, family, value, verdict}] in variant order
    smallest_flip: str | None


def _shift_geometry(rule: VisualRule, line_id: str | None, d: float) -> VisualRule:
    """Translate every zone and line by d (frame fraction) along the normal of `line_id` (or straight down)."""
    nx, ny = 0.0, 1.0
    ln = next((x for x in rule.lines if x.id == line_id), None)
    if ln is not None:
        dx, dy = ln.b[0] - ln.a[0], ln.b[1] - ln.a[1]
        n = hypot(dx, dy)
        nx, ny = -dy / n, dx / n
        if ny < 0 or (ny == 0 and nx < 0):  # point "down / right" so +d reads as "lower"
            nx, ny = -nx, -ny
    mv = lambda p: (p[0] + d * nx, p[1] + d * ny)  # noqa: E731
    return rule.model_copy(update={
        "zones": [z.model_copy(update={"polygon": [mv(p) for p in z.polygon]}) for z in rule.zones],
        "lines": [x.model_copy(update={"a": mv(x.a), "b": mv(x.b)}) for x in rule.lines]})


def _map_events(rule: VisualRule, fn: Callable[[dict], dict | None]) -> VisualRule | None:
    """Apply fn to every event dict of the check; None if fn changed nothing."""
    changed = False

    def walk(x):
        nonlocal changed
        if isinstance(x, dict):
            if x.get("op") in ("IN_ZONE", "DWELL", "CROSSES", "WITH"):
                y = fn(x)
                if y is not None and y != x:
                    changed = True
                    return y
                return x
            return {k: walk(v) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(v) for v in x]
        return x

    check = walk(rule.check.model_dump())
    return VisualRule.model_validate(rule.model_dump() | {"check": check}) if changed else None


def variants(rule: VisualRule, height_px: int, other_reading: VisualRule | None = None
             ) -> list[tuple[Variant, VisualRule, bool]]:
    """(variant, rule to judge with, halve the frames?) in size order."""
    out: list[tuple[Variant, VisualRule, bool]] = []
    lines = sorted(crossing_lines(rule.check)) or [x.id for x in rule.lines]
    line_id = lines[0] if lines else None
    for i, d in enumerate(SHIFTS):
        where = f"line '{line_id}'" if line_id else "zones"
        out.append((Variant(family="line_shift", value=d, size=10 + i,
                            label=f"{where} drawn {abs(d) * 100:.0f} % of the frame "
                                  f"{'lower' if d > 0 else 'higher'} ({abs(d) * height_px:.0f} px)"),
                    _shift_geometry(rule, line_id, d), False))
    other = "bottom_center" if rule.params.anchor == "center" else "center"
    out.append((Variant(family="anchor", value=other, size=20,
                        label=f"object measured at its {other.replace('_', ' ')} instead of its "
                              f"{rule.params.anchor.replace('_', ' ')}"),
                rule.model_copy(update={"params": rule.params.model_copy(update={"anchor": other})}), False))
    for f, word in ((0.8, "20 % shorter"), (1.2, "20 % longer")):
        r = _map_events(rule, lambda e, f=f: e | {"min_ms": round(e["min_ms"] * f, 1)} if e.get("op") == "DWELL" else None)
        if r:
            out.append((Variant(family="min_ms", value=f, size=30 if f < 1 else 31,
                                label=f"required time {word}"), r, False))
    dwell_still = _map_events(rule, lambda e: e | {"max_speed": None}
                              if e.get("op") == "DWELL" and e.get("max_speed") else None)
    if dwell_still:
        out.append((Variant(family="stillness_meaning", value="any_motion", size=40,
                            label="time counts even while moving (no full stop required)"), dwell_still, False))
        for f in (0.5, 2.0):
            r = _map_events(rule, lambda e, f=f: e | {"max_speed": round(e["max_speed"] * f, 4)}
                            if e.get("op") == "DWELL" and e.get("max_speed") else None)
            out.append((Variant(family="stillness", value=f, size=41 if f < 1 else 42,
                                label=f"'standing still' threshold x{f:g}"), r, False))
    else:
        r = _map_events(rule, lambda e: e | {"max_speed": STILL_DEFAULT} if e.get("op") == "DWELL" else None)
        if r:
            out.append((Variant(family="stillness_meaning", value="still_only", size=40,
                                label="time counts only while standing still"), r, False))
    out.append((Variant(family="frames", value=0.5, size=50, label="every other video frame dropped"), rule, True))
    if other_reading is not None:
        out.append((Variant(family="reading", value="other_model", size=60,
                            label="the other model's reading of the same sentence"), other_reading, False))
    return out


def _halve(tracks: TrackSet) -> TrackSet:
    return tracks.model_copy(update={"frames": [f for f in tracks.frames if f.frame_index % 2 == 0]})


def robustness(rule: VisualRule, tracks: TrackSet, other_reading: VisualRule | None = None,
               only: set[int] | None = None) -> list[ObjectRobustness]:
    base = {o.object_id: o.verdict for o in evaluate(rule, tracks).objects}
    flips: dict[int, list[dict]] = {k: [] for k in base}
    half = None
    for v, r, halve in variants(rule, tracks.video.height, other_reading):
        if halve:
            half = half or _halve(tracks)
        got = {o.object_id: o.verdict for o in evaluate(r, half if halve else tracks).objects}
        for oid, b in base.items():
            g = got.get(oid, "UNKNOWN")
            if g != b:
                flips[oid].append({"variant": v.label, "family": v.family, "tier": v.tier, "value": v.value,
                                   "verdict": g})
    out = []
    for oid, b in sorted(base.items()):
        if only is not None and oid not in only:
            continue
        hard = [f for f in flips[oid] if f["verdict"] != "UNKNOWN" and b != "UNKNOWN"]
        tiers = {t: [f for f in hard if f["tier"] == t] for t in ("measurement", "threshold", "meaning")}
        status = ("FRAGILE" if tiers["measurement"] else "DEPENDS_ON_THRESHOLD" if tiers["threshold"]
                  else "DEPENDS_ON_MEANING" if tiers["meaning"] else "UNSTABLE" if flips[oid] else "ROBUST")
        first = (tiers["measurement"] or tiers["threshold"] or tiers["meaning"] or flips[oid] or [None])[0]
        out.append(ObjectRobustness(object_id=oid, verdict=b, status=status, flips=flips[oid],
                                    smallest_flip=first and f"{first['variant']} -> {first['verdict']}"))
    return out
