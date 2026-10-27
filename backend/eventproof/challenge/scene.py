"""Synthetic scene specification and seeded generators.

A `SceneSpec` fully determines a video: same spec ⇒ same pixels ⇒ same ground truth. Objects move
piecewise-linearly between waypoints; occluders are static rectangles active for a frame range.
Ground truth comes from this geometry, never from any model under test.
"""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

import numpy as np
from pydantic import AfterValidator, BaseModel, Field, model_validator

from eventproof.schemas.rules import Line, Zone

GENERATOR_VERSION = "scene-gen/1"

COLORS: dict[str, tuple[int, int, int]] = {
    "blue": (40, 95, 220),
    "red": (215, 60, 50),
    "green": (50, 170, 80),
    "orange": (235, 140, 30),
}


# Scene coordinates are quantized to 1e-6. numpy's C code may use fused multiply-add on arm64 but not on
# x86, so a sampled float can differ in its last bit across machines; quantizing makes scene hashes (and the
# frozen holdout) platform independent. 1e-6 of a 640 px frame is far below one pixel.
Coord = Annotated[float, Field(ge=0, le=1), AfterValidator(lambda v: round(v, 6))]


class Waypoint(BaseModel):
    frame: int = Field(ge=0)
    x: Coord = Field(description="normalized box center")
    y: Coord


class SceneObject(BaseModel):
    object_id: int = Field(ge=0)
    color: Literal["blue", "red", "green", "orange"]
    size: tuple[float, float] = Field(default=(0.07, 0.12), description="normalized (w, h)")
    waypoints: list[Waypoint] = Field(min_length=1)

    @property
    def label(self) -> str:
        return f"{self.color} box"

    @model_validator(mode="after")
    def _sorted(self) -> SceneObject:
        frames = [w.frame for w in self.waypoints]
        if frames != sorted(frames) or len(set(frames)) != len(frames):
            raise ValueError("waypoint frames must be strictly increasing")
        return self

    def center_at(self, frame: int) -> tuple[float, float] | None:
        wps = self.waypoints
        if frame < wps[0].frame or frame > wps[-1].frame:
            return None
        for a, b in zip(wps, wps[1:], strict=False):
            if a.frame <= frame <= b.frame:
                u = (frame - a.frame) / (b.frame - a.frame)
                return (a.x + (b.x - a.x) * u, a.y + (b.y - a.y) * u)
        return (wps[-1].x, wps[-1].y)


class Occluder(BaseModel):
    x1: Coord
    y1: Coord
    x2: Coord
    y2: Coord
    start_frame: int = Field(default=0, ge=0)
    end_frame: int | None = None

    def active(self, frame: int) -> bool:
        return frame >= self.start_frame and (self.end_frame is None or frame <= self.end_frame)


class SceneSpec(BaseModel):
    seed: int
    generator: str = GENERATOR_VERSION
    width: int = 640
    height: int = 360
    fps: float = 15.0
    n_frames: int = Field(default=120, ge=50, description="SAM bills >= 50 frames; keep clips >= 50")
    zones: list[Zone]
    lines: list[Line]
    objects: list[SceneObject] = Field(max_length=16)
    occluders: list[Occluder] = Field(default_factory=list)
    family: str = "canonical"
    notes: str = ""

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def scene_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


# ---- Canonical warehouse layout (matches the demo rule "inspect before packing") -----------------

INSPECTION = Zone(id="inspection", polygon=[(0.30, 0.10), (0.50, 0.10), (0.50, 0.90), (0.30, 0.90)])
PACKING_LINE = Line(id="packing_entry", a=(0.75, 0.05), b=(0.75, 0.95))
LANES = (0.28, 0.50, 0.72)
INSPECT_X = 0.40


def conveyor_path(rng: np.random.Generator, start: int, lane: float, inspect_frames: int,
                  travel_frames: int, x0: float = 0.06, x1: float = 0.92) -> list[Waypoint]:
    """Move along a lane; optionally stop at the inspection station for `inspect_frames`."""
    if inspect_frames <= 0:
        return [Waypoint(frame=start, x=x0, y=lane), Waypoint(frame=start + travel_frames, x=x1, y=lane)]
    to_station = max(1, round(travel_frames * (INSPECT_X - x0) / (x1 - x0)))
    rest = max(1, travel_frames - to_station)
    t_arrive = start + to_station
    t_leave = t_arrive + inspect_frames
    return [
        Waypoint(frame=start, x=x0, y=lane),
        Waypoint(frame=t_arrive, x=INSPECT_X, y=lane),
        Waypoint(frame=t_leave, x=INSPECT_X, y=lane),
        Waypoint(frame=t_leave + rest, x=x1, y=lane),
    ]


def canonical_scene(seed: int, n_objects: int | None = None, fps: float = 15.0, n_frames: int = 120) -> SceneSpec:
    """1–3 blue boxes, each randomly inspected (stops 1.2–2.0 s) or not, on distinct lanes.

    Clean family: designed so that a DWELL threshold of 1.5 s separates the classes with margin.
    Just driving through the inspection zone takes ~0.6–0.9 s, which is *above* a naive 0.5 s
    threshold — that near-threshold ambiguity is left to the adversarial families on purpose.
    """
    rng = np.random.default_rng(seed)
    k = n_objects if n_objects is not None else int(rng.integers(1, 4))
    lanes = rng.permutation(len(LANES))[:k]
    objects = []
    for oid, lane_idx in enumerate(lanes):
        inspected = bool(rng.random() < 0.5)
        inspect_frames = round(float(rng.uniform(1.2, 2.0)) * fps) if inspected else 0
        travel = int(rng.integers(round(2.5 * fps), round(4.0 * fps)))
        latest_start = max(0, n_frames - 1 - travel - inspect_frames)
        start = int(rng.integers(0, latest_start + 1))
        objects.append(SceneObject(object_id=oid, color="blue",
                                   waypoints=conveyor_path(rng, start, LANES[lane_idx], inspect_frames, travel)))
    return SceneSpec(seed=seed, fps=fps, n_frames=n_frames, zones=[INSPECTION], lines=[PACKING_LINE],
                     objects=objects, family="canonical")
