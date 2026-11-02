"""Umbrella pilot: matching labelled people to tracks, and the recorded report recomputes with 0 API calls."""

from __future__ import annotations

import json

import pytest

from eventproof.schemas.tracks import Box, TrackFrame, TrackSet, VideoInfo
from eventproof.validation import with_pilot
from eventproof.validation.with_pilot import Person, match


def _p(x: float, y: float) -> Person:
    return Person(description="p", t_s=1.0, feet=(x, y), umbrella=False, intended="VIOLATION")


def test_match_is_nearest_feet_and_one_to_one():
    info = VideoInfo(width=100, height=100, fps=10, frame_count=20)
    fr = [TrackFrame(frame_index=10, timestamp_ms=1000, object_id=oid, label="person",
                     box=Box(x1=x - 5, y1=y - 30, x2=x + 5, y2=y))
          for oid, x, y in ((1, 20, 60), (2, 70, 80), (3, 22, 62))]
    ts = TrackSet(video=info, source="mock", frames=fr)
    assert match([_p(0.2, 0.6), _p(0.7, 0.8), _p(0.95, 0.1)], ts, {1, 2, 3}) == {0: 1, 1: 2}


def test_recorded_report_recomputes():
    rep = with_pilot.DIR / "report.json"
    if not rep.exists():
        pytest.skip("pilot not run yet")
    old = json.loads(rep.read_text())
    if "result" not in old:
        pytest.skip("run did not complete")
    assert with_pilot.recompute()["result"] == old["result"]
