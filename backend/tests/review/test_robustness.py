"""Ticket robustness: measurement, threshold and meaning tiers; quote checking for law mode; defense menu schema."""

from __future__ import annotations

import pytest

from eventproof.meta.muse_defense import schema as defense_schema
from eventproof.meta.muse_rules import RuleCompileError, check_quotes
from eventproof.review.robustness import robustness, variants
from eventproof.schemas.rules import VisualRule
from eventproof.schemas.tracks import Box, TrackFrame, TrackSet, VideoInfo

INFO = VideoInfo(width=100, height=100, fps=10, frame_count=60)
RULE = VisualRule.model_validate({
    "rule_id": "stop", "entity": {"name": "car", "concept": "car"},
    "zones": [{"id": "wait", "polygon": [[0, 0.3], [1, 0.3], [1, 0.6], [0, 0.6]]}],
    "lines": [{"id": "stop", "a": [0, 0.6], "b": [1, 0.6]}],
    "check": {"op": "IMPLIES", "premise": {"op": "OCCURS", "event": {"op": "CROSSES", "line": "stop"}},
              "conclusion": {"op": "OCCURS", "event": {"op": "DWELL", "zone": "wait", "min_ms": 1000, "max_speed": 0.05}}}})


def car(oid: int, ys: list[float]) -> list[TrackFrame]:
    return [TrackFrame(frame_index=f, timestamp_ms=f * 100.0, object_id=oid, label="car",
                       box=Box(x1=40, y1=y - 5, x2=50, y2=y + 5)) for f, y in enumerate(ys)]


def test_tiers():
    stopper = car(1, [35 + f for f in range(5)] + [40.0] * 20 + [40 + 2 * f for f in range(1, 15)])  # stops 2 s
    roller = car(2, [35 + 0.7 * f for f in range(60)])  # crawls 7 px/s through the line, never still
    tracks = TrackSet(video=INFO, source="mock", frames=stopper + roller)
    st = {x.object_id: x for x in robustness(RULE, tracks)}
    assert st[1].verdict == "PASS" and st[1].status == "ROBUST"
    assert st[2].verdict == "VIOLATION" and st[2].status in ("DEPENDS_ON_THRESHOLD", "DEPENDS_ON_MEANING")
    fams = {v.family for v, _, _ in variants(RULE, 100)}
    assert {"line_shift", "anchor", "min_ms", "stillness", "stillness_meaning", "frames"} <= fams


def test_quotes_must_be_verbatim():
    law = "the driver ... shall stop at the near side of the intersection at a clearly marked stop line."
    ok = {"provenance": [{"param": "CROSSES.line", "source": "QUOTED", "quote": "at a clearly  marked stop line"},
                         {"param": "DWELL.min_ms", "source": "ASSUMED", "quote": ""}]}
    check_quotes(ok, law)
    bad = {"provenance": [{"param": "DWELL.min_ms", "source": "QUOTED", "quote": "for at least 3 seconds"}]}
    with pytest.raises(RuleCompileError):
        check_quotes(bad, law)


def test_defense_menu_is_closed():
    s = defense_schema(["anchor:center", "frames:0.5"])
    assert s["properties"]["challenges"]["items"]["properties"]["id"]["enum"] == ["anchor:center", "frames:0.5"]
    assert "none" in s["properties"]["strongest"]["enum"]
