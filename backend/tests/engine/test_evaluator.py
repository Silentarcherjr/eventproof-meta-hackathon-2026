from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from eventproof.engine.evaluator import evaluate
from eventproof.schemas.rules import VisualRule
from tests.conftest import CANONICAL_RULE, W, lerp, path, trackset

# x positions: inspection zone is x in [0.30, 0.50]; packing line at x = 0.75. 10 fps.
INSPECTED = lerp(0.1, 0.4, 4) + [0.4] * 8 + lerp(0.45, 0.9, 6)  # ~1.2 s in inspection, then packing
SKIPPED = lerp(0.1, 0.9, 10)  # rushes through: ~0.2 s in inspection
NEVER_PACKED = lerp(0.1, 0.4, 4) + [0.4] * 3  # stays before the line


def test_inspected_package_passes(rule):
    report = evaluate(rule, trackset(path(INSPECTED)))
    assert report.overall == "PASS"
    (obj,) = report.objects
    dwell = next(e for e in obj.events if e.op == "DWELL")
    cross = next(e for e in obj.events if e.op == "CROSSES")
    assert dwell.status == cross.status == "TRUE"
    assert dwell.frame < cross.frame


def test_skipped_inspection_is_violation_with_frame(rule):
    report = evaluate(rule, trackset(path(SKIPPED)))
    assert report.overall == "FAIL"
    cross = next(e for e in report.objects[0].events if e.op == "CROSSES")
    assert cross.status == "TRUE" and cross.frame is not None


def test_object_that_never_enters_packing_passes_vacuously(rule):
    assert evaluate(rule, trackset(path(NEVER_PACKED))).overall == "PASS"


def test_mixed_objects_fail_overall_and_keep_per_object_verdicts(rule):
    report = evaluate(rule, trackset(path(INSPECTED, object_id=1), path(SKIPPED, object_id=2, y=0.2)))
    assert report.overall == "FAIL"
    assert {o.object_id: o.verdict for o in report.objects} == {1: "PASS", 2: "VIOLATION"}


def test_long_occlusion_before_crossing_is_unknown_not_pass_or_fail(rule):
    # Box disappears for 8 frames (> max_gap 3) exactly where inspection happens, then shows up past it.
    xs = lerp(0.1, 0.25, 3) + [0.4] * 8 + lerp(0.55, 0.9, 5)
    occluded = set(range(3, 11))
    report = evaluate(rule, trackset(path(xs, occluded=occluded)))
    assert report.overall == "UNKNOWN"


def test_short_gap_is_bridged(rule):
    report = evaluate(rule, trackset(path(INSPECTED, skip={6, 7})))  # 2 missing frames inside inspection
    assert report.overall == "PASS"


def test_low_confidence_counts_as_missing(rule):
    frames = path(INSPECTED)
    for f in frames:
        f.confidence = 0.2
    strict = VisualRule.model_validate({**CANONICAL_RULE, "params": {"min_confidence": 0.5}})
    # The object exists but is never reliably seen: that must be UNKNOWN, never a vacuous PASS.
    assert evaluate(strict, trackset(frames)).overall == "UNKNOWN"
    assert evaluate(rule, trackset(frames)).overall == "PASS"


def test_other_labels_are_ignored(rule):
    report = evaluate(rule, trackset(path(SKIPPED, label="red box")))
    assert report.overall == "NO_OBJECTS"


def test_direction_filter():
    r = VisualRule.model_validate({**CANONICAL_RULE, "check": {
        "op": "OCCURS", "event": {"op": "CROSSES", "line": "packing_entry", "direction": "to_left"}}})
    # walking a=(0.75,0)->b=(0.75,1) (downwards), moving +x ends on the left side in image coords
    assert evaluate(r, trackset(path(SKIPPED))).overall == "PASS"
    r2 = VisualRule.model_validate({**CANONICAL_RULE, "check": {
        "op": "OCCURS", "event": {"op": "CROSSES", "line": "packing_entry", "direction": "to_right"}}})
    assert evaluate(r2, trackset(path(SKIPPED))).overall == "FAIL"


def test_within_ms():
    r = VisualRule.model_validate({**CANONICAL_RULE, "check": {
        "op": "BEFORE", "first": {"op": "IN_ZONE", "zone": "inspection"},
        "then": {"op": "CROSSES", "line": "packing_entry"}, "within_ms": 600}})
    assert evaluate(r, trackset(path(INSPECTED))).overall == "FAIL"  # zone entry -> crossing took 1300 ms
    assert evaluate(r, trackset(path(SKIPPED))).overall == "PASS"  # 500 ms


def test_report_is_deterministic_and_hash_stable(rule):
    ts = trackset(path(INSPECTED, object_id=1), path(SKIPPED, object_id=2))
    a, b = evaluate(rule, ts), evaluate(rule, ts)
    assert a.model_dump() == b.model_dump()
    assert len(rule.rule_hash()) == 64
    assert rule.rule_hash() == VisualRule.model_validate(CANONICAL_RULE).rule_hash()


@pytest.mark.parametrize("patch", [
    {"check": {"op": "OCCURS", "event": {"op": "IN_ZONE", "zone": "nope"}}},
    {"check": {"op": "OCCURS", "event": {"op": "CROSSES", "line": "nope"}}},
    {"check": {"op": "EVAL", "code": "__import__('os')"}},
    {"zones": [{"id": "z", "polygon": [[0, 0], [2, 0], [0, 1]]}]},
    {"rule_id": "Bad Id!"},
])
def test_invalid_rules_rejected(patch):
    with pytest.raises(ValidationError):
        VisualRule.model_validate({**CANONICAL_RULE, **patch})


def test_crossing_detected_when_anchor_lands_exactly_on_line(rule):
    """Regression (found by Challenge Mode, drive_through seed 20): an anchor exactly on the line
    for one or more frames used to hide the crossing entirely."""
    xs = [0.60, 0.70, 0.75, 0.75, 0.80, 0.90]
    report = evaluate(rule, trackset(path(xs)))
    cross = next(e for e in report.objects[0].events if e.op == "CROSSES")
    assert cross.status == "TRUE" and cross.frame == 4
    assert report.overall == "FAIL"


def _still_rule(max_speed: float | None, min_ms: float = 500):
    d = copy.deepcopy(CANONICAL_RULE)
    d["check"]["conclusion"]["first"].update({"min_ms": min_ms, "max_speed": max_speed})
    return VisualRule.model_validate(d)


def test_dwell_max_speed_separates_slow_transit_from_a_stop():
    slow = lerp(0.1, 0.9, 40)  # 0.2/s: ~1 s inside the 0.2-wide zone without ever stopping
    stop = lerp(0.1, 0.4, 8) + [0.4] * 8 + lerp(0.4, 0.9, 10)  # 0.8 s standing still at the station
    for xs, plain, still in ((slow, "PASS", "FAIL"), (stop, "PASS", "PASS")):
        ts = trackset(path(xs), n=len(xs))
        assert evaluate(_still_rule(None), ts).overall == plain
        assert evaluate(_still_rule(0.05), ts).overall == still


def test_dwell_max_speed_tolerates_pixel_jitter():
    xs = lerp(0.1, 0.4, 8) + [0.4 + (i % 2) / W for i in range(8)] + lerp(0.4, 0.9, 10)  # +-1 px while stopped
    assert evaluate(_still_rule(0.05), trackset(path(xs), n=len(xs))).overall == "PASS"
