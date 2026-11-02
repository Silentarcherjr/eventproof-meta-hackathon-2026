"""WITH: a relation to an object of another tracked concept (near / on_top), held for a duration."""

from __future__ import annotations

from eventproof.engine.evaluator import evaluate
from eventproof.schemas.rules import VisualRule
from eventproof.schemas.tracks import Box, TrackFrame, TrackSet, VideoInfo

INFO = VideoInfo(width=100, height=100, fps=10, frame_count=60)


def frames(oid: int, label: str, boxes: dict[int, tuple[float, float, float, float]]) -> list[TrackFrame]:
    return [TrackFrame(frame_index=f, timestamp_ms=f * 100.0, object_id=oid, label=label,
                       box=Box(x1=b[0], y1=b[1], x2=b[2], y2=b[3])) for f, b in boxes.items()]


def rule(check: dict, concept: str = "person") -> VisualRule:
    return VisualRule.model_validate({
        "rule_id": "r", "entity": {"name": concept, "concept": concept},
        "zones": [{"id": "site", "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]]}], "check": check})


PPE = {"op": "IMPLIES", "premise": {"op": "OCCURS", "event": {"op": "IN_ZONE", "zone": "site"}},
       "conclusion": {"op": "OCCURS", "event": {"op": "WITH", "concept": "hard hat", "relation": "on_top", "min_ms": 500}}}


def test_hard_hat_on_top_of_the_person():
    worker = frames(1, "person", {f: (40, 30, 60, 90) for f in range(20)})
    bare = frames(2, "person", {f: (10, 30, 30, 90) for f in range(20)})
    hat = frames(7, "hard hat", {f: (45, 26, 55, 34) for f in range(20)})  # over worker 1's head
    loose = frames(8, "hard hat", {f: (12, 80, 20, 88) for f in range(20)})  # at worker 2's feet: not on top
    rep = evaluate(rule(PPE), TrackSet(video=INFO, source="mock", frames=worker + bare + hat + loose))
    v = {o.object_id: o.verdict for o in rep.objects}
    assert v == {1: "PASS", 2: "VIOLATION"} and rep.overall == "FAIL"  # the hats are not judged as entities


def test_hat_must_stay_on_for_min_ms():
    worker = frames(1, "person", {f: (40, 30, 60, 90) for f in range(20)})
    hat = frames(7, "hard hat", {f: (45, 26, 55, 34) for f in range(3)})  # only 0.3 s
    rep = evaluate(rule(PPE), TrackSet(video=INFO, source="mock", frames=worker + hat))
    assert rep.objects[0].verdict == "VIOLATION"


def test_near_forklift_for_a_duration():
    near = {"op": "NOT", "arg": {"op": "OCCURS", "event": {"op": "WITH", "concept": "forklift", "relation": "near",
                                                             "max_dist": 0.15, "min_ms": 1000}}}
    walker = frames(1, "person", {f: (10 + 2 * f, 40, 20 + 2 * f, 60) for f in range(30)})  # walks past the forklift
    loiter = frames(2, "person", {f: (62, 30, 72, 50) for f in range(30)})  # stays next to it
    forklift = frames(9, "forklift", {f: (55, 25, 85, 55) for f in range(30)})
    rep = evaluate(rule(near), TrackSet(video=INFO, source="mock", frames=walker + loiter + forklift))
    v = {o.object_id: o.verdict for o in rep.objects}
    assert v[2] == "VIOLATION" and v[1] == "PASS"
    assert rule(near).context_concepts() == ["forklift"]
