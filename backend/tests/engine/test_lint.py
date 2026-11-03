"""anchor_check: a line that no object crosses at the rule's anchor point, while the other anchor would cross it."""

from __future__ import annotations

import json
from pathlib import Path

from eventproof.engine.lint import anchor_check, crossing_lines
from eventproof.schemas.rules import VisualRule
from eventproof.schemas.tracks import Box, TrackFrame, TrackSet, VideoInfo

INFO = VideoInfo(width=100, height=100, fps=10, frame_count=20)
ROOT = Path(__file__).resolve().parents[3]


def rule(anchor: str) -> VisualRule:
    return VisualRule.model_validate({
        "rule_id": "r", "entity": {"name": "cyclist", "concept": "cyclist"}, "params": {"anchor": anchor},
        "lines": [{"id": "l", "a": [0, 0.8], "b": [1, 0.8]}],
        "check": {"op": "NOT", "arg": {"op": "OCCURS", "event": {"op": "CROSSES", "line": "l", "direction": "to_left"}}}})


def tall_rider() -> TrackSet:  # a tall box whose bottom crosses y=0.8 while its centre stays above it
    fr = [TrackFrame(frame_index=f, timestamp_ms=f * 100.0, object_id=1, label="cyclist",
                     box=Box(x1=40, y1=30 + f, x2=60, y2=70 + 2 * f)) for f in range(20)]
    return TrackSet(video=INFO, source="mock", frames=fr)


def test_warns_when_only_the_other_anchor_crosses():
    w = anchor_check(rule("center"), tall_rider())
    assert len(w) == 1 and w[0]["line"] == "l" and w[0]["other_crossers"] == 1
    assert anchor_check(rule("bottom_center"), tall_rider()) == []
    assert crossing_lines(rule("center").check) == {"l"}


def test_recorded_real_runs():
    """Fires on the Santos runs whose box centres never reach the line (v1 both clips, v2 santos_away), silent on every
    other recorded real run (v2 santos_toward tracked 'bicycle': short boxes, centres do cross)."""
    fired = {}
    for ev in sorted(ROOT.glob("benchmark/real/*/runs/*/evidence.json")):
        e = json.loads(ev.read_text())
        if e["status"] != "completed":
            continue
        r = VisualRule.model_validate(e["rule"]["compiled_rule"])
        fired[f"{ev.parts[-4]}/{ev.parts[-2]}"] = bool(anchor_check(
            r, TrackSet.model_validate_json((ev.parent / "tracks.json").read_text())))
    assert {k for k, v in fired.items() if v} == {"santos/20261103T231056Z-2fdf0faa", "santos/20261103T231135Z-aa354fe9",
                                                  "santos/20261103T233625Z-e1540bd3"}
