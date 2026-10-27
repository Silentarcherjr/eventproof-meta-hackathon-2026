"""Adversarial scene families. Each is a pure function seed -> SceneSpec.

Families vary one physical factor that plausibly breaks a visual inspection detector. None of them
encodes an expected verdict: labels come from `truth.py` (scripted behaviour), never from the engine.

- drive_through:     box never stops but a slow belt keeps it inside the zone 0.5–2.0 s
- brief_stop:        box stops at the station for 0.3–2.4 s (threshold 1.5 s sits inside the range)
- occluded_station:  canonical scene with a panel covering the station for part of the clip
- tailgate:          an uninspected box catches up with an inspected one after the station and
                     travels overlapping it into packing (tests object separation / identity)
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from eventproof.challenge.scene import (
    INSPECTION,
    LANES,
    PACKING_LINE,
    Occluder,
    SceneObject,
    SceneSpec,
    Waypoint,
    canonical_scene,
    conveyor_path,
)

FPS = 15.0
X0, X1 = 0.06, 0.92
ZONE_WIDTH = 0.20  # inspection zone x-span used to convert transit time <-> belt speed


def _scene(seed: int, family: str, objects: list[SceneObject], n_frames: int, notes: str = "",
           occluders: list[Occluder] | None = None) -> SceneSpec:
    return SceneSpec(seed=seed, fps=FPS, n_frames=max(50, n_frames), zones=[INSPECTION], lines=[PACKING_LINE],
                     objects=objects, occluders=occluders or [], family=family, notes=notes)


def drive_through(seed: int) -> SceneSpec:
    rng = np.random.default_rng([seed, 1])
    transit_s = float(rng.uniform(0.5, 2.0))
    travel = round(transit_s * FPS * (X1 - X0) / ZONE_WIDTH)
    start = int(rng.integers(0, 10))
    lane = LANES[int(rng.integers(0, len(LANES)))]
    obj = SceneObject(object_id=0, color="blue", waypoints=conveyor_path(rng, start, lane, 0, travel, X0, X1))
    return _scene(seed, "drive_through", [obj], start + travel + 5, notes=f"transit_in_zone_s={transit_s:.3f}")


def brief_stop(seed: int) -> SceneSpec:
    rng = np.random.default_rng([seed, 2])
    stop_s = float(rng.uniform(0.3, 2.4))
    travel = int(rng.integers(round(2.5 * FPS), round(3.5 * FPS)))
    start = int(rng.integers(0, 10))
    lane = LANES[int(rng.integers(0, len(LANES)))]
    stop_frames = round(stop_s * FPS)
    obj = SceneObject(object_id=0, color="blue", waypoints=conveyor_path(rng, start, lane, stop_frames, travel, X0, X1))
    return _scene(seed, "brief_stop", [obj], start + travel + stop_frames + 5, notes=f"stop_s={stop_s:.3f}")


def occluded_station(seed: int) -> SceneSpec:
    rng = np.random.default_rng([seed, 3])
    base = canonical_scene(int(rng.integers(0, 2**31)), n_objects=int(rng.integers(1, 3)), fps=FPS, n_frames=120)
    target = base.objects[int(rng.integers(0, len(base.objects)))]
    lane = target.waypoints[0].y
    a = int(rng.integers(0, base.n_frames // 2))
    b = int(rng.integers(a + 15, base.n_frames))
    occ = Occluder(x1=0.31, x2=0.49, y1=max(0.0, lane - 0.10), y2=min(1.0, lane + 0.10), start_frame=a, end_frame=b)
    return base.model_copy(update={"seed": seed, "family": "occluded_station", "occluders": [occ],
                                   "notes": f"occluder frames {a}-{b} over lane {lane}"})


def tailgate(seed: int) -> SceneSpec:
    rng = np.random.default_rng([seed, 4])
    lane_a, lane_b = LANES[1], LANES[0]
    stop = round(float(rng.uniform(1.6, 2.0)) * FPS)
    travel = round(3.0 * FPS)
    start_a = int(rng.integers(20, 30))
    a = SceneObject(object_id=0, color="blue", waypoints=conveyor_path(rng, start_a, lane_a, stop, travel, X0, X1))
    t_leave = a.waypoints[2].frame
    t_meet = t_leave + int(rng.integers(3, 10))
    end_a = a.waypoints[-1].frame
    dx, dy = float(rng.uniform(-0.03, 0.05)), float(rng.uniform(0.0, 0.06))
    ax, ay = a.center_at(t_meet)
    t_start_b = max(0, t_meet - round(2.0 * FPS))
    b = SceneObject(object_id=1, color="blue", waypoints=[
        Waypoint(frame=t_start_b, x=X0, y=lane_b),
        Waypoint(frame=t_meet, x=min(0.97, ax + dx), y=min(1.0, ay + dy)),
        Waypoint(frame=end_a, x=min(0.97, X1 + dx), y=min(1.0, lane_a + dy)),
    ])
    return _scene(seed, "tailgate", [a, b], end_a + 5, notes=f"offset dx={dx:.3f} dy={dy:.3f}")


FAMILIES: dict[str, Callable[[int], SceneSpec]] = {
    "canonical": lambda s: canonical_scene(s),
    "drive_through": drive_through,
    "brief_stop": brief_stop,
    "occluded_station": occluded_station,
    "tailgate": tailgate,
}
