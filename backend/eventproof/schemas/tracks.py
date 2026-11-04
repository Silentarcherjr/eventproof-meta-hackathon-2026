"""Normalized perception output: per-frame object boxes with stable ids.

Every producer (SAM 3.1 adapter, synthetic ground truth, fixtures, mocks) emits this shape,
so the rule engine never depends on where tracks came from. `source` is mandatory so mocks
can never be confused with live model output.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

TrackSource = Literal["sam-3.1", "synthetic_ground_truth", "human_annotation", "fixture", "mock",
                      "dataset trajectory (INTERACTION, drone)"]


class Box(BaseModel):
    """Axis-aligned box in source pixels."""

    x1: float
    y1: float
    x2: float
    y2: float

    @model_validator(mode="after")
    def _ordered(self) -> Box:
        if self.x2 < self.x1 or self.y2 < self.y1:
            raise ValueError("box corners must satisfy x1<=x2 and y1<=y2")
        return self


class TrackFrame(BaseModel):
    frame_index: int = Field(ge=0)
    timestamp_ms: float = Field(ge=0)
    object_id: int = Field(ge=0)
    label: str
    box: Box
    confidence: float | None = Field(default=None, ge=0, le=1)
    occluded: bool = False
    mask_ref: str | None = None


class VideoInfo(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: float = Field(gt=0)
    frame_count: int = Field(gt=0)

    def frame_to_ms(self, frame_index: int) -> float:
        return frame_index * 1000.0 / self.fps


class TrackSet(BaseModel):
    video: VideoInfo
    frames: list[TrackFrame]
    source: TrackSource
    source_ref: str | None = Field(default=None, description="sha256 / job id / seed of the producer")

    @model_validator(mode="after")
    def _within_video(self) -> TrackSet:
        for f in self.frames:
            if f.frame_index >= self.video.frame_count:
                raise ValueError(f"frame_index {f.frame_index} outside video ({self.video.frame_count} frames)")
        return self
