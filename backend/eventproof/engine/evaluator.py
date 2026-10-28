"""Deterministic tri-state evaluator for `VisualRule` over a `TrackSet`.

Semantics (documented in ADR-003):
- Each tracked object is checked independently. Observations that are occluded or below
  `min_confidence` are treated as missing.
- Gaps of up to `max_gap_frames` missing frames are bridged (the object is assumed to keep its
  state). Longer gaps are "blind spots": an event that was not observed but could have happened
  inside a blind spot makes the result UNKNOWN instead of FALSE.
- Logic is Kleene three-valued; IMPLIES(p, c) == OR(NOT p, c).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot

from eventproof.engine.geometry import cross, point_in_polygon, segments_intersect
from eventproof.schemas.evidence import EventTrace, ObjectVerdict, RuleReport, Tri
from eventproof.schemas.rules import (
    And,
    Before,
    Crosses,
    Dwell,
    Event,
    Expr,
    Implies,
    InZone,
    Not,
    Occurs,
    Or,
    VisualRule,
)
from eventproof.schemas.tracks import TrackFrame, TrackSet


@dataclass(frozen=True)
class Obs:
    frame: int
    ts: float
    pt: tuple[float, float]


@dataclass(frozen=True)
class EventResult:
    status: Tri
    frame: int | None = None
    ts: float | None = None
    reason: str = ""


@dataclass
class ObjectTrack:
    object_id: int
    obs: list[Obs]
    blind_spots: list[tuple[int, int]]  # (last observed frame, next observed frame) with a long gap
    frame_ms: float
    first_frame: int
    last_frame: int
    _memo: dict[str, EventResult] = field(default_factory=dict)

    def blind_before(self, frame: int) -> bool:
        return any(nxt <= frame for _, nxt in self.blind_spots)

    def blind_between(self, start: int, end: int) -> bool:
        return any(prev >= start and nxt <= end for prev, nxt in self.blind_spots)


def _anchor(f: TrackFrame, w: int, h: int, mode: str) -> tuple[float, float]:
    cx = (f.box.x1 + f.box.x2) / 2 / w
    cy = (f.box.y2 if mode == "bottom_center" else (f.box.y1 + f.box.y2) / 2) / h
    return (cx, cy)


def build_tracks(rule: VisualRule, tracks: TrackSet) -> list[ObjectTrack]:
    p = rule.params
    w, h = tracks.video.width, tracks.video.height
    by_obj: dict[int, dict[int, TrackFrame]] = {}
    span: dict[int, list[int]] = {}
    for f in tracks.frames:
        if f.label != rule.entity.concept:
            continue
        span.setdefault(f.object_id, []).append(f.frame_index)
        if f.occluded or (f.confidence is not None and f.confidence < p.min_confidence):
            continue
        prev = by_obj.setdefault(f.object_id, {}).get(f.frame_index)
        if prev is None or (f.confidence or 0) > (prev.confidence or 0):
            by_obj[f.object_id][f.frame_index] = f
    out = []
    for oid in sorted(span):
        frames = by_obj.get(oid, {})
        obs = [Obs(i, frames[i].timestamp_ms, _anchor(frames[i], w, h, p.anchor)) for i in sorted(frames)]
        first, last = min(span[oid]), max(span[oid])
        # Sentinels make the track's own start/end count as observation edges, so unusable
        # (occluded / low-confidence) frames at either end also create blind spots.
        edges = [first - 1, *(o.frame for o in obs), last + 1]
        blind = [(a, b) for a, b in zip(edges, edges[1:], strict=False) if b - a - 1 > p.max_gap_frames]
        out.append(ObjectTrack(oid, obs, blind, 1000.0 / tracks.video.fps, first, last))
    return out


def _bridged(a: Obs, b: Obs, max_gap: int) -> bool:
    return b.frame - a.frame - 1 <= max_gap


SPEED_WINDOW_MS = 333.0  # long enough that +-1 px detector jitter does not read as motion


def _stillness(t: ObjectTrack, max_speed: float) -> list[bool]:
    """Per observation: average anchor speed (frame units/s) since the latest observation at least
    SPEED_WINDOW_MS earlier (or the track start) is <= max_speed. The first observation has no speed."""
    out, j = [], 0
    for o in t.obs:
        while j + 1 < len(t.obs) and o.ts - t.obs[j + 1].ts >= SPEED_WINDOW_MS:
            j += 1
        ref = t.obs[j]
        dt = (o.ts - ref.ts) / 1000.0
        out.append(dt > 0 and hypot(o.pt[0] - ref.pt[0], o.pt[1] - ref.pt[1]) / dt <= max_speed)
    return out


def eval_event(ev: Event, t: ObjectTrack, rule: VisualRule) -> EventResult:
    key = ev.model_dump_json()
    if key not in t._memo:
        t._memo[key] = _eval_event(ev, t, rule)
    return t._memo[key]


@dataclass(frozen=True)
class ZoneStep:
    obs: Obs
    in_zone: bool
    still: bool | None  # None: the event has no speed condition
    start: Obs | None  # start of the current counted run (None = not counting at this observation)
    counted_ms: float  # what DWELL has accumulated at this observation


def zone_steps(ev: InZone | Dwell, t: ObjectTrack, rule: VisualRule) -> list[ZoneStep]:
    """The per-observation counter behind IN_ZONE / DWELL. `_eval_event` decides from these steps, and the
    studio's before/after chart shows the same steps, so the picture and the verdict cannot disagree."""
    poly = next(z.polygon for z in rule.zones if z.id == ev.zone)
    still = _stillness(t, ev.max_speed) if isinstance(ev, Dwell) and ev.max_speed else None
    start: Obs | None = None
    prev: Obs | None = None
    out = []
    for i, o in enumerate(t.obs):
        in_zone = point_in_polygon(o.pt, poly)
        inside = in_zone and (still is None or still[i])
        if not inside or (prev is not None and not _bridged(prev, o, rule.params.max_gap_frames)):
            start = None
        if inside:
            start = start or o
        out.append(ZoneStep(o, in_zone, None if still is None else still[i], start,
                            o.ts - start.ts + t.frame_ms if start else 0.0))
        prev = o
    return out


def _eval_event(ev: Event, t: ObjectTrack, rule: VisualRule) -> EventResult:
    max_gap = rule.params.max_gap_frames
    if isinstance(ev, InZone | Dwell):
        still = isinstance(ev, Dwell) and ev.max_speed
        for st in zone_steps(ev, t, rule):
            o, start = st.obs, st.start
            if start is None:
                continue
            if isinstance(ev, InZone) and o.frame - start.frame + 1 >= ev.min_frames:
                return EventResult("TRUE", start.frame, start.ts, f"inside {ev.zone} from frame {start.frame}")
            if isinstance(ev, Dwell) and st.counted_ms >= ev.min_ms:
                how = "still " if still else ""
                return EventResult("TRUE", o.frame, o.ts, f"dwelled {ev.min_ms:.0f} ms {how}in {ev.zone}")
        need = f"{ev.min_frames} consecutive frames" if isinstance(ev, InZone) else f"{ev.min_ms:.0f} ms"
        if still:
            need += " still"
        if t.blind_spots:
            return EventResult("UNKNOWN", reason=f"{need} in {ev.zone} not observed; "
                                                 f"{len(t.blind_spots)} blind spot(s) could hide it")
        return EventResult("FALSE", reason=f"never {need} in {ev.zone}")

    assert isinstance(ev, Crosses)
    line = next(ln for ln in rule.lines if ln.id == ev.line)
    # A blind spot at either end of the track hides where the object was, so a crossing is possible.
    possible = any(a < t.first_frame or b > t.last_frame for a, b in t.blind_spots)
    # Compare each observation with the last one that was strictly on one side, so an anchor that
    # lands exactly on the line for some frames still registers the crossing (found by Challenge Mode).
    prev: Obs | None = None
    prev_side = 0.0
    for o in t.obs:
        side = cross(line.a, line.b, o.pt)
        if side == 0:
            continue
        if prev is not None and side * prev_side < 0 and segments_intersect(prev.pt, o.pt, line.a, line.b):
            direction = "to_right" if side > 0 else "to_left"
            if ev.direction in ("any", direction):
                if _bridged(prev, o, max_gap):
                    return EventResult("TRUE", o.frame, o.ts, f"crossed {ev.line} ({direction}) at frame {o.frame}")
                possible = True
        prev, prev_side = o, side
    if possible:
        return EventResult("UNKNOWN", reason=f"side of {ev.line} changed inside a blind spot")
    return EventResult("FALSE", reason=f"never crossed {ev.line}")


def eval_expr(expr: Expr, t: ObjectTrack, rule: VisualRule, traces: list[EventTrace]) -> Tri:
    match expr:
        case Occurs(event=ev):
            r = eval_event(ev, t, rule)
            traces.append(_trace(ev, r))
            return r.status
        case Before(first=f_ev, then=t_ev, within_ms=within):
            f, th = eval_event(f_ev, t, rule), eval_event(t_ev, t, rule)
            traces += [_trace(f_ev, f), _trace(t_ev, th)]
            if "FALSE" in (f.status, th.status):
                return "FALSE"
            if f.status == th.status == "TRUE":
                if f.frame < th.frame:
                    if within is None or th.ts - f.ts <= within:
                        return "TRUE"
                    return "UNKNOWN" if t.blind_between(f.frame, th.frame) else "FALSE"
                # first was seen only after `then`; it might still have happened unseen earlier
                return "UNKNOWN" if t.blind_before(th.frame) else "FALSE"
            return "UNKNOWN"
        case Not(arg=a):
            return {"TRUE": "FALSE", "FALSE": "TRUE", "UNKNOWN": "UNKNOWN"}[eval_expr(a, t, rule, traces)]
        case And(args=xs):
            vals = [eval_expr(x, t, rule, traces) for x in xs]
            return "FALSE" if "FALSE" in vals else ("TRUE" if all(v == "TRUE" for v in vals) else "UNKNOWN")
        case Or(args=xs):
            vals = [eval_expr(x, t, rule, traces) for x in xs]
            return "TRUE" if "TRUE" in vals else ("FALSE" if all(v == "FALSE" for v in vals) else "UNKNOWN")
        case Implies(premise=p, conclusion=c):
            return eval_expr(Or(args=[Not(arg=p), c]), t, rule, traces)
    raise TypeError(f"unknown expression {expr!r}")


def _target(ev: Event) -> str:
    return ev.line if isinstance(ev, Crosses) else ev.zone


def _trace(ev: Event, r: EventResult) -> EventTrace:
    return EventTrace(op=ev.op, target=_target(ev), status=r.status, frame=r.frame, timestamp_ms=r.ts, reason=r.reason)


def evaluate(rule: VisualRule, tracks: TrackSet) -> RuleReport:
    objects = []
    for t in build_tracks(rule, tracks):
        traces: list[EventTrace] = []
        status = eval_expr(rule.check, t, rule, traces)
        seen, uniq = set(), []
        for tr in traces:
            k = (tr.op, tr.target)
            if k not in seen:
                seen.add(k)
                uniq.append(tr)
        verdict = {"TRUE": "PASS", "FALSE": "VIOLATION", "UNKNOWN": "UNKNOWN"}[status]
        explanation = f"object {t.object_id}: {verdict} — " + "; ".join(f"{tr.op} {tr.target}: {tr.reason}" for tr in uniq)
        objects.append(ObjectVerdict(object_id=t.object_id, verdict=verdict, first_frame=t.first_frame,
                                     last_frame=t.last_frame, events=uniq, explanation=explanation))
    verdicts = {o.verdict for o in objects}
    if not objects:
        overall = "NO_OBJECTS"
    elif "VIOLATION" in verdicts:
        overall = "FAIL"
    elif "UNKNOWN" in verdicts:
        overall = "UNKNOWN"
    else:
        overall = "PASS"
    return RuleReport(rule_id=rule.rule_id, rule_version=rule.version, rule_hash=rule.rule_hash(),
                      track_source=tracks.source, track_source_ref=tracks.source_ref, overall=overall, objects=objects)
