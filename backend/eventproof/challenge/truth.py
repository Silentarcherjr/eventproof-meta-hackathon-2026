"""Process truth: what *actually* happened to each object, derived from the scene's waypoints.

This is deliberately a different code path from the rule engine. The engine judges perceived
tracks against a rule (e.g. "dwell >= 1.5 s in the inspection zone"); process truth judges the
physical behaviour the generator scripted (e.g. "the box stood still at the station for >= 1.5 s").
Comparing the two separates three kinds of disagreement:

- spec error:        rule(oracle tracks) != process truth   → the rule does not express the intent
- perception error:  rule(perceived)     != rule(oracle)     → tracking/segmentation failed
- correct:           rule(perceived)     == process truth
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from eventproof.challenge.scene import SceneObject, SceneSpec

Intended = Literal["PASS", "VIOLATION"]


class ObjectTruth(BaseModel):
    object_id: int
    label: str
    station_stop_ms: float
    crosses_packing_frame: int | None
    intended: Intended


def _zone_bounds(scene: SceneSpec, zone_id: str) -> tuple[float, float, float, float]:
    poly = next(z.polygon for z in scene.zones if z.id == zone_id)
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _line_x(scene: SceneSpec, line_id: str) -> float:
    ln = next(ln for ln in scene.lines if ln.id == line_id)
    if ln.a[0] != ln.b[0]:
        raise ValueError("process truth only supports the vertical packing line used by the generators")
    return ln.a[0]


def object_truth(scene: SceneSpec, obj: SceneObject, min_stop_ms: float = 1000.0,
                 zone_id: str = "inspection", line_id: str = "packing_entry") -> ObjectTruth:
    x1, y1, x2, y2 = _zone_bounds(scene, zone_id)
    line_x = _line_x(scene, line_id)
    crossing = next((f for f in range(obj.waypoints[0].frame, obj.waypoints[-1].frame + 1)
                     if (c := obj.center_at(f)) and c[0] >= line_x), None)
    stop_frames = 0
    for a, b in zip(obj.waypoints, obj.waypoints[1:], strict=False):
        stationary = (a.x, a.y) == (b.x, b.y)
        at_station = x1 <= a.x <= x2 and y1 <= a.y <= y2
        if stationary and at_station and (crossing is None or b.frame <= crossing):
            stop_frames = max(stop_frames, b.frame - a.frame)
    stop_ms = stop_frames * 1000.0 / scene.fps
    ok = crossing is None or stop_ms >= min_stop_ms
    return ObjectTruth(object_id=obj.object_id, label=obj.label, station_stop_ms=stop_ms,
                       crosses_packing_frame=crossing, intended="PASS" if ok else "VIOLATION")


def scene_truth(scene: SceneSpec, label: str = "blue box", min_stop_ms: float = 1000.0) -> list[ObjectTruth]:
    return [object_truth(scene, o, min_stop_ms) for o in scene.objects if o.label == label]


def intended_overall(truths: list[ObjectTruth]) -> Literal["PASS", "FAIL"]:
    return "FAIL" if any(t.intended == "VIOLATION" for t in truths) else "PASS"
