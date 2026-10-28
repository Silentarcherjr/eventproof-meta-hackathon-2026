from __future__ import annotations

import pytest

from eventproof.schemas.rules import VisualRule
from eventproof.schemas.tracks import Box, TrackFrame, TrackSet, VideoInfo

W, H, FPS = 640, 360, 10.0

# Canonical demo rule: every blue box must dwell >= 500 ms in inspection before crossing into packing.
CANONICAL_RULE = {
    "rule_id": "inspect-before-packing",
    "entity": {"name": "package", "concept": "blue box"},
    "zones": [{"id": "inspection", "polygon": [[0.30, 0.0], [0.50, 0.0], [0.50, 1.0], [0.30, 1.0]]}],
    "lines": [{"id": "packing_entry", "a": [0.75, 0.0], "b": [0.75, 1.0]}],
    "check": {
        "op": "IMPLIES",
        "premise": {"op": "OCCURS", "event": {"op": "CROSSES", "line": "packing_entry"}},
        "conclusion": {
            "op": "BEFORE",
            "first": {"op": "DWELL", "zone": "inspection", "min_ms": 500},
            "then": {"op": "CROSSES", "line": "packing_entry"},
        },
    },
    "normalized_explanation": (
        "Each blue box that enters packing must have spent at least 0.5 s in inspection first."
    ),
}


@pytest.fixture
def rule() -> VisualRule:
    return VisualRule.model_validate(CANONICAL_RULE)


def path(xs: list[float], object_id: int = 0, y: float = 0.5, start: int = 0, label: str = "blue box",
         skip: set[int] | None = None, occluded: set[int] | None = None) -> list[TrackFrame]:
    """One object moving through normalized x positions, one per frame."""
    out = []
    for i, x in enumerate(xs):
        fi = start + i
        if skip and fi in skip:
            continue
        cx, cy = x * W, y * H
        out.append(TrackFrame(frame_index=fi, timestamp_ms=fi * 1000 / FPS, object_id=object_id, label=label,
                              box=Box(x1=cx - 10, y1=cy - 10, x2=cx + 10, y2=cy + 10),
                              occluded=bool(occluded and fi in occluded)))
    return out


def trackset(*frames: list[TrackFrame], n: int = 100) -> TrackSet:
    return TrackSet(video=VideoInfo(width=W, height=H, fps=FPS, frame_count=n),
                    frames=[f for fs in frames for f in fs], source="fixture", source_ref="unit-test")


def lerp(a: float, b: float, n: int) -> list[float]:
    return [a + (b - a) * i / (n - 1) for i in range(n)]


@pytest.fixture(autouse=True)
def _isolate_from_real_state(tmp_path, monkeypatch):
    """Tests never write to the real caches/runs and never reach the live Meta API unless a test injects a fake."""
    from eventproof import pipeline, studio
    from eventproof.meta import muse_repair, muse_rules
    from eventproof.perception import sam

    for mod in (muse_rules, muse_repair, sam):
        monkeypatch.setattr(mod, "CACHE_DIR", tmp_path / f"cache-{mod.__name__.rsplit('.', 1)[-1]}")
    for mod in (pipeline, studio):
        monkeypatch.setattr(mod, "RUNS_DIR", tmp_path / "runs")

    def _no_live(*a, **k):
        raise AssertionError("test tried to reach the live Meta API")

    for mod in (muse_rules, muse_repair, sam):
        monkeypatch.setattr(mod, "get_client", _no_live)
