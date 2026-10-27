"""MOCK perception: a deliberately naive detector + tracker over synthetic ground truth.

This is NOT SAM 3.1 and must never be presented as such. Every TrackSet it emits has
`source="mock"`. It exists so Challenge Mode can be developed and tested while live Meta access is
blocked, and later as a baseline to compare SAM against.

Failure modes are generic tracker behaviours, not scripted outcomes:
- objects whose center is occluded are not detected;
- boxes overlapping with IoU >= `merge_iou` are reported as one merged detection;
- association is greedy nearest-centroid with a gate; a track unmatched for `max_age` frames dies
  and a reappearing object gets a new id.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from eventproof.schemas.tracks import Box, TrackFrame, TrackSet

MOCK_VERSION = "mock-tracker/1"


@dataclass(frozen=True)
class MockParams:
    merge_iou: float = 0.25
    gate_px: float = 60.0
    max_age: int = 5
    jitter_px: int = 1


def iou(a: Box, b: Box) -> float:
    ix = max(0.0, min(a.x2, b.x2) - max(a.x1, b.x1))
    iy = max(0.0, min(a.y2, b.y2) - max(a.y1, b.y1))
    inter = ix * iy
    union = (a.x2 - a.x1) * (a.y2 - a.y1) + (b.x2 - b.x1) * (b.y2 - b.y1) - inter
    return inter / union if union > 0 else 0.0


def _detect(frame_gt: list[TrackFrame], p: MockParams) -> list[tuple[str, Box]]:
    """Per-frame detections: drop occluded objects, merge strongly overlapping ones."""
    dets = [(f.label, f.box) for f in frame_gt if not f.occluded]
    merged = True
    while merged:
        merged = False
        for i in range(len(dets)):
            for j in range(i + 1, len(dets)):
                if iou(dets[i][1], dets[j][1]) >= p.merge_iou:
                    a, b = dets[i][1], dets[j][1]
                    u = Box(x1=min(a.x1, b.x1), y1=min(a.y1, b.y1), x2=max(a.x2, b.x2), y2=max(a.y2, b.y2))
                    dets = [d for k, d in enumerate(dets) if k not in (i, j)] + [(dets[i][0], u)]
                    merged = True
                    break
            if merged:
                break
    return dets


def _center(b: Box) -> tuple[float, float]:
    return (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2


def perceive(gt: TrackSet, seed: int = 0, params: MockParams | None = None) -> TrackSet:
    p = params or MockParams()
    rng = np.random.default_rng([seed, 99])
    by_frame: dict[int, list[TrackFrame]] = {}
    for f in gt.frames:
        by_frame.setdefault(f.frame_index, []).append(f)

    tracks: dict[int, tuple[tuple[float, float], int]] = {}  # id -> (last center, last frame)
    next_id = 0
    out: list[TrackFrame] = []
    for fi in range(gt.video.frame_count):
        dets = _detect(sorted(by_frame.get(fi, []), key=lambda f: f.object_id), p)
        pairs = []
        for di, (_, box) in enumerate(dets):
            c = _center(box)
            for tid, (tc, _) in tracks.items():
                d = float(np.hypot(c[0] - tc[0], c[1] - tc[1]))
                if d <= p.gate_px:
                    pairs.append((d, tid, di))
        used_t, used_d, assign = set(), set(), {}
        for _, tid, di in sorted(pairs):
            if tid not in used_t and di not in used_d:
                used_t.add(tid)
                used_d.add(di)
                assign[di] = tid
        for di, (label, box) in enumerate(dets):
            tid = assign.get(di)
            if tid is None:
                tid, next_id = next_id, next_id + 1
            j = rng.integers(-p.jitter_px, p.jitter_px + 1, size=4)
            jb = Box(x1=max(0, box.x1 + j[0]), y1=max(0, box.y1 + j[1]),
                     x2=min(gt.video.width, max(box.x1 + j[0] + 1, box.x2 + j[2])),
                     y2=min(gt.video.height, max(box.y1 + j[1] + 1, box.y2 + j[3])))
            tracks[tid] = (_center(jb), fi)
            out.append(TrackFrame(frame_index=fi, timestamp_ms=fi * 1000.0 / gt.video.fps, object_id=tid,
                                  label=label, box=jb, confidence=None))
        tracks = {t: v for t, v in tracks.items() if fi - v[1] <= p.max_age}
    return TrackSet(video=gt.video, frames=out, source="mock", source_ref=f"{MOCK_VERSION} {gt.source_ref}")
