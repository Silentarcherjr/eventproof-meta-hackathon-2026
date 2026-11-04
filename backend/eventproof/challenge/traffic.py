"""Deterministic traffic world, version 1; synthetic geometry, never model output.

Truth contract (also used for perfect-track evaluation):
* Coordinates are normalized image coordinates; the car CENTER is the anchor, not its bumper.
  Cars travel left-to-right in one/two approach lanes. The vertical stop line is x=0.72;
  the waiting zone is 0.54<=x<=0.70, 0.36<=y<=0.72. Cross traffic is context, not an approach car.
* A crossing is the first observed change between STRICT sides of the finite line, retaining
  the previous side when a center lands exactly on it. Direction is forward or wrong_way.
* Operational stillness is center speed <=0.01 frame units/second, measured across the
  preceding ceil(0.333*fps) frames (or since the first observation). The first sample has
  no measured speed. This explicit smoothing window avoids treating box-size jitter as motion.
* Standing-still seconds are the longest consecutive run of in-zone, still samples strictly
  BEFORE the first crossing. Each qualifying sample represents 1/fps seconds. Separate stops
  are not added together. This is sampled, windowed stillness, not exact continuous rest time;
  stationary_seconds additionally reports exact zero-speed waypoint time for audit.
* A car that crosses must have >=1.5 such seconds: PASS, otherwise VIOLATION. A car that
  never crosses passes vacuously. A wrong-way car without a prior in-zone wait violates the
  same rule; direction is reported, not an extra unspoken traffic-law requirement.
* Truth uses waypoint geometry only, independently of the engine and rendered/perceived boxes.
  Occluders never erase physical truth. Perfect tracks include hidden cars with flags cleared;
  visibility-aware tracks retain occlusion flags and can lead to UNKNOWN instead.

The generator makes at most one crossing per car. Camera tilt is a deliberately simple
perspective SIZE scaling, not a calibrated camera or a claim of physical photorealism.
Box jitter changes symmetric extents, never the true center or the truth label.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from math import ceil, hypot
from typing import Literal

import numpy as np
from pydantic import BaseModel

from eventproof.challenge.scene import Occluder, SceneObject, SceneSpec, Waypoint
from eventproof.schemas.rules import Line, VisualRule, Zone
from eventproof.schemas.tracks import Box, TrackSet

TRAFFIC_GENERATOR = "traffic-gen/1"
FPS = 10.0
WAIT_SECONDS = 1.5
STILL_SPEED = 0.01
SPEED_WINDOW_SECONDS = 0.333
STOP_X = 0.72
WAITING = Zone(id="waiting", polygon=[(0.54, 0.36), (0.70, 0.36), (0.70, 0.72), (0.54, 0.72)])
STOP_LINE = Line(id="stop_line", a=(STOP_X, 0.34), b=(STOP_X, 0.74))
DEV_SEEDS = range(40)
HOLDOUT_SEEDS = range(100_000, 100_025)  # 25 x 8 families = 200; export only, never a search input


def is_traffic(scene: SceneSpec) -> bool:
    return scene.generator == TRAFFIC_GENERATOR


def require_dev_seed(seed: int) -> None:
    if seed in HOLDOUT_SEEDS:
        raise ValueError("frozen traffic holdout seeds must never be used for development/search")


def object_label(obj: SceneObject) -> str:
    return "car" if obj.color == "blue" else "cross traffic"


def _car(oid: int, lane: float, arrive: int, hold: int, depart: int, stop_x: float,
         creep: float = 0.0, start_x: float = 0.10) -> SceneObject:
    points = [(0, start_x), (arrive, stop_x)]
    if hold:
        points.append((arrive + hold, stop_x + creep))
    points.append((arrive + hold + depart, 0.92))
    return SceneObject(object_id=oid, color="blue", size=(0.065, 0.075),
                       waypoints=[Waypoint(frame=f, x=x, y=lane) for f, x in points])


def _generate(seed: int, family: str) -> SceneSpec:
    if seed < 0:
        raise ValueError("traffic seeds must be nonnegative")
    # One common RNG stream makes seed knobs comparable across families.
    rng = np.random.default_rng([seed, 7301])
    lanes = int(rng.integers(1, 3))
    lane = 0.53 if lanes == 1 else (0.45, 0.63)[int(rng.integers(0, 2))]
    arrive = int(rng.integers(18, 29))
    depart = int(rng.integers(15, 22))
    stop_x = round(float(rng.uniform(0.635, 0.665)), 6)
    hold = int(rng.integers(21, 28))  # windowed stillness remains >=1.5 s
    tilt = round(float(rng.uniform(-0.25, 0.25)), 6)
    jitter = round(float(rng.uniform(0.0005, 0.002)), 6)
    occluders: list[Occluder] = []
    if family == "rolling_stop":
        # Four seconds crawling inside the zone fools a naive DWELL without max_speed.
        hold = int(rng.integers(25, 36))
        creep = round(float(rng.uniform(0.018, 0.024)) * hold / FPS, 6)
        stop_x = 0.56
        cars = [_car(0, lane, arrive, hold, depart, stop_x, creep)]
    elif family == "no_stop":
        cars = [_car(0, lane, arrive, 0, depart, stop_x)]
    elif family == "brief_stop":
        cars = [_car(0, lane, arrive, int(rng.integers(4, 12)), depart, stop_x)]
    elif family == "queue":
        leader = _car(0, lane, arrive, hold, depart, stop_x, start_x=0.32)
        follower = _car(1, lane, arrive + 3, hold + 8, depart + 5, 0.43)
        cars = [leader, follower]  # follower's long stop is OUTSIDE the waiting zone
    elif family == "wrong_way":
        cars = [SceneObject(object_id=0, color="blue", size=(0.065, 0.075), waypoints=[
            Waypoint(frame=0, x=0.92, y=lane),
            Waypoint(frame=arrive + depart, x=0.10, y=lane),
        ])]
    elif family == "tailgate":
        lead = _car(0, lane, arrive, hold, depart, stop_x)
        separation = round(float(rng.uniform(0.067, 0.083)), 6)
        follower = lead.model_copy(update={"object_id": 1, "waypoints": [
            w.model_copy(update={"x": round(w.x - separation, 6)}) for w in lead.waypoints]})
        cars = [lead, follower]
    else:
        cars = [_car(0, lane, arrive, hold, depart, stop_x)]
        if family == "occluded":
            # A static truck on the near side hides the approach during the stop.
            occluders = [Occluder(x1=0.55, x2=0.70, y1=round(lane - 0.065, 6),
                                 y2=round(lane + 0.065, 6), start_frame=max(0, arrive - 3),
                                 end_frame=arrive + hold - 2)]
    end = max(o.waypoints[-1].frame for o in cars)
    cross_traffic = bool(rng.integers(0, 2))
    if cross_traffic:
        cars.append(SceneObject(object_id=10, color="green", size=(0.045, 0.10), waypoints=[
            Waypoint(frame=0, x=0.84, y=0.12), Waypoint(frame=end, x=0.84, y=0.88)]))
    notes = json.dumps({"lanes": lanes, "camera_tilt": tilt, "box_jitter": jitter,
                        "cross_traffic": cross_traffic}, sort_keys=True, separators=(",", ":"))
    return SceneSpec(seed=seed, generator=TRAFFIC_GENERATOR, width=480, height=270, fps=FPS,
                     n_frames=max(50, end + 4), zones=[WAITING.model_copy(deep=True)],
                     lines=[STOP_LINE.model_copy(deep=True)], objects=cars,
                     occluders=occluders, family=family, notes=notes)


def full_stop(seed: int) -> SceneSpec:
    return _generate(seed, "full_stop")


def rolling_stop(seed: int) -> SceneSpec:
    return _generate(seed, "rolling_stop")


def no_stop(seed: int) -> SceneSpec:
    return _generate(seed, "no_stop")


def brief_stop(seed: int) -> SceneSpec:
    return _generate(seed, "brief_stop")


def queue(seed: int) -> SceneSpec:
    return _generate(seed, "queue")


def occluded(seed: int) -> SceneSpec:
    return _generate(seed, "occluded")


def wrong_way(seed: int) -> SceneSpec:
    return _generate(seed, "wrong_way")


def tailgate(seed: int) -> SceneSpec:
    return _generate(seed, "tailgate")


TRAFFIC_FAMILIES: dict[str, Callable[[int], SceneSpec]] = {
    "full_stop": full_stop, "rolling_stop": rolling_stop, "no_stop": no_stop,
    "brief_stop": brief_stop, "queue": queue, "occluded": occluded,
    "wrong_way": wrong_way, "tailgate": tailgate,
}


class TrafficTracks(TrackSet):
    """Traffic-local provenance extension; the shared schema and old frozen hashes stay unchanged."""

    source: Literal["synthetic"] = "synthetic"


class TrafficTruth(BaseModel):
    object_id: int
    label: str = "car"
    crossed_line: bool
    crossing_frame: int | None
    direction: Literal["forward", "wrong_way", "none"]
    standing_still_seconds: float
    stationary_seconds: float
    intended: Literal["PASS", "VIOLATION"]


def object_truth(scene: SceneSpec, obj: SceneObject) -> TrafficTruth:
    """Compute from unrounded trajectory centers; no renderer or engine imports."""
    zone = next(z for z in scene.zones if z.id == "waiting")
    line = next(ln for ln in scene.lines if ln.id == "stop_line")
    if line.a[0] != line.b[0]:
        raise ValueError("traffic truth requires a vertical stop line")
    xmin, xmax = min(x for x, _ in zone.polygon), max(x for x, _ in zone.polygon)
    ymin, ymax = min(y for _, y in zone.polygon), max(y for _, y in zone.polygon)
    lx = line.a[0]
    low_y, high_y = sorted((line.a[1], line.b[1]))
    first = max(0, obj.waypoints[0].frame)
    last = min(scene.n_frames - 1, obj.waypoints[-1].frame)
    crossing, direction = None, "none"
    previous = None
    for f in range(first, last + 1):
        x, y = obj.center_at(f)
        if x == lx:
            continue
        if previous is not None:
            px, py = previous
            if (x - lx) * (px - lx) < 0:
                hit_y = py + (y - py) * (lx - px) / (x - px)
                if low_y <= hit_y <= high_y:
                    crossing, direction = f, "forward" if x > px else "wrong_way"
                    break
        previous = (x, y)
    window = ceil(SPEED_WINDOW_SECONDS * scene.fps)
    run, longest = 0, 0
    for f in range(first, crossing if crossing is not None else last + 1):
        x, y = obj.center_at(f)
        ref = max(first, f - window)
        rx, ry = obj.center_at(ref)
        dt = (f - ref) / scene.fps
        still = dt > 0 and hypot(x - rx, y - ry) / dt <= STILL_SPEED
        run = run + 1 if xmin <= x <= xmax and ymin <= y <= ymax and still else 0
        longest = max(longest, run)
    exact = 0.0
    for a, b in zip(obj.waypoints, obj.waypoints[1:], strict=False):
        if (a.x, a.y) == (b.x, b.y) and xmin <= a.x <= xmax and ymin <= a.y <= ymax:
            end = min(b.frame, crossing if crossing is not None else last)
            exact = max(exact, max(0, end - max(a.frame, first)) / scene.fps)
    seconds = longest / scene.fps
    return TrafficTruth(object_id=obj.object_id, crossed_line=crossing is not None,
                        crossing_frame=crossing, direction=direction, standing_still_seconds=seconds,
                        stationary_seconds=exact,
                        intended="PASS" if crossing is None or seconds >= WAIT_SECONDS else "VIOLATION")


def scene_truth(scene: SceneSpec) -> list[TrafficTruth]:
    return [object_truth(scene, o) for o in scene.objects if object_label(o) == "car"]


def traffic_rule(scene: SceneSpec, wait_s: float = WAIT_SECONDS,
                 max_speed: float | None = STILL_SPEED) -> VisualRule:
    """Hand-written closed DSL; max_speed=None deliberately models the naive residence-time bug."""
    crossing = {"op": "CROSSES", "line": "stop_line", "direction": "any"}
    return VisualRule.model_validate({
        "rule_id": "wait-before-stop-line", "entity": {"name": "vehicle", "concept": "car"},
        "zones": [z.model_dump() for z in scene.zones], "lines": [ln.model_dump() for ln in scene.lines],
        "params": {"anchor": "center", "max_gap_frames": 3},
        "check": {"op": "IMPLIES", "premise": {"op": "OCCURS", "event": crossing},
                  "conclusion": {"op": "BEFORE",
                                 "first": {"op": "DWELL", "zone": "waiting", "min_ms": wait_s * 1000,
                                           "max_speed": max_speed}, "then": crossing}},
        "normalized_explanation": f"Every car must wait at least {wait_s:g} seconds in the waiting zone before crossing.",
    })


def box_at(scene: SceneSpec, obj: SceneObject, frame: int) -> Box | None:
    """Analytic box with symmetric deterministic jitter; rasterization happens only in render.py."""
    center = obj.center_at(frame)
    if center is None:
        return None
    knobs = json.loads(scene.notes)
    x, y = center
    perspective = 1 + knobs["camera_tilt"] * (x - STOP_X)
    # Integer arithmetic avoids platform-dependent PRNG operations in the render loop.
    noise = ((scene.seed * 1103515245 + obj.object_id * 12345 + frame * 2654435761) % 2001 - 1000) / 1000
    w = obj.size[0] * perspective + knobs["box_jitter"] * noise
    h = obj.size[1] * perspective - knobs["box_jitter"] * noise
    return Box(x1=(x - w / 2) * scene.width, x2=(x + w / 2) * scene.width,
               y1=(y - h / 2) * scene.height, y2=(y + h / 2) * scene.height)


def perfect_tracks(scene: SceneSpec) -> TrackSet:
    from eventproof.challenge.render import ground_truth, oracle_view

    return oracle_view(ground_truth(scene))


def perfect_perceiver(scene: SceneSpec, gt: TrackSet) -> TrackSet:
    from eventproof.challenge.render import oracle_view

    return oracle_view(gt)


def _replace_first(scene: SceneSpec, waypoints: list[Waypoint]) -> SceneSpec:
    obj = scene.objects[0].model_copy(update={"waypoints": waypoints})
    objects = [obj, *scene.objects[1:]]
    last = max(o.waypoints[-1].frame for o in objects)
    # Validate after every mutation; no generated code or unvalidated model instructions.
    return SceneSpec.model_validate({**scene.model_dump(), "objects": [o.model_dump() for o in objects],
                                     "n_frames": max(scene.n_frames, last + 4)})


def knob_stop_duration(scene: SceneSpec, t: float) -> SceneSpec:
    """Extend the first slow/stopped segment by up to 3 s; preserve its endpoints and all other cars."""
    if not 0 <= t <= 1:
        raise ValueError("knob must be in [0, 1]")
    wps = scene.objects[0].waypoints
    if t == 0 or len(wps) < 4:
        return scene.model_copy(deep=True)
    extra = round(t * 3 * scene.fps)
    out = [w.model_copy(update={"frame": w.frame + (extra if i >= 2 else 0)}) for i, w in enumerate(wps)]
    return _replace_first(scene, out)


def knob_speed(scene: SceneSpec, t: float) -> SceneSpec:
    """Speed up only the first car's crawl/motion by up to 8x; zero preserves the scene exactly."""
    if not 0 <= t <= 1:
        raise ValueError("knob must be in [0, 1]")
    if t == 0:
        return scene.model_copy(deep=True)
    wps = scene.objects[0].waypoints
    if len(wps) >= 4:
        old = wps[2].frame - wps[1].frame
        new = max(1, round(old / (1 + 7 * t)))
        out = [w.model_copy(update={"frame": w.frame - (old - new if i >= 2 else 0)})
               for i, w in enumerate(wps)]
    else:
        start = wps[0].frame
        out = [w.model_copy(update={"frame": start + round((w.frame - start) / (1 + 7 * t))}) for w in wps]
    return _replace_first(scene, out)


def knob_stop_distance(scene: SceneSpec, t: float) -> SceneSpec:
    """Move only the first car's slow/stop segment up to 0.24 frame units farther from the line."""
    if not 0 <= t <= 1:
        raise ValueError("knob must be in [0, 1]")
    if t == 0:
        return scene.model_copy(deep=True)
    wps = scene.objects[0].waypoints
    out = [Waypoint(frame=w.frame, x=w.x - 0.24 * t if 0 < i < len(wps) - 1 else w.x, y=w.y)
           for i, w in enumerate(wps)]
    return _replace_first(scene, out)


TRAFFIC_KNOBS = {name: ("traffic crawl speed", knob_speed) for name in TRAFFIC_FAMILIES}
TRAFFIC_KNOBS.update({"brief_stop": ("traffic stop duration", knob_stop_duration),
                     "full_stop": ("traffic stop distance", knob_stop_distance),
                     "queue": ("traffic stop distance", knob_stop_distance)})
