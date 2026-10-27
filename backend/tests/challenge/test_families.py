from __future__ import annotations

import re

import pytest

from eventproof.challenge.families import FAMILIES
from eventproof.challenge.render import ground_truth, oracle_view
from eventproof.challenge.runner import classify, inspection_rule, run_suite
from eventproof.challenge.truth import scene_truth
from eventproof.engine.evaluator import evaluate
from eventproof.perception import mock
from eventproof.perception.mock import iou

SEEDS = range(30)


@pytest.mark.parametrize("family", sorted(FAMILIES))
def test_families_are_deterministic_and_valid(family):
    for s in range(5):
        a, b = FAMILIES[family](s), FAMILIES[family](s)
        assert a.scene_hash() == b.scene_hash()
        assert a.n_frames >= 50 and a.family == family
        gt = ground_truth(a)
        assert {f.object_id for f in gt.frames} == {o.object_id for o in a.objects}, "every object is visible"


def test_brief_stop_truth_matches_scripted_stop():
    for s in SEEDS:
        scene = FAMILIES["brief_stop"](s)
        stop_s = float(re.search(r"stop_s=([\d.]+)", scene.notes).group(1))
        (t,) = scene_truth(scene)
        assert abs(t.station_stop_ms - stop_s * 1000) <= 1000 / scene.fps
        assert t.intended == ("PASS" if t.station_stop_ms >= 1000 else "VIOLATION")


def test_drive_through_is_never_inspected():
    assert all(scene_truth(FAMILIES["drive_through"](s))[0].intended == "VIOLATION" for s in SEEDS)


def test_tailgate_boxes_really_overlap_after_the_station():
    overlapping = 0
    for s in SEEDS:
        gt = ground_truth(FAMILIES["tailgate"](s))
        frames: dict[int, list] = {}
        for f in gt.frames:
            frames.setdefault(f.frame_index, []).append(f.box)
        overlapping += any(len(bs) == 2 and iou(*bs) > 0 for bs in frames.values())
    assert overlapping == len(SEEDS)


def test_mock_perception_is_labelled_and_exact_on_clean_scenes():
    """Sanity: on clean canonical scenes the naive tracker must agree with the oracle,
    so every error it shows elsewhere is caused by the adversarial factor, not by the mock."""
    for s in SEEDS:
        scene = FAMILIES["canonical"](s)
        gt = ground_truth(scene)
        perceived = mock.perceive(gt, seed=s)
        assert perceived.source == "mock" and perceived.source_ref.startswith(mock.MOCK_VERSION)
        rule = inspection_rule(scene)
        assert evaluate(rule, perceived).overall == evaluate(rule, oracle_view(gt)).overall


def test_classify():
    assert classify("FAIL", "FAIL", "FAIL") == "correct"
    assert classify("FAIL", "PASS", "PASS") == "spec_error"
    assert classify("FAIL", "FAIL", "PASS") == "perception_error"
    assert classify("PASS", "PASS", "UNKNOWN") == "abstained"


def test_suite_finds_both_error_kinds_and_none_on_clean_scenes():
    results = run_suite(sorted(FAMILIES), list(SEEDS), dwell_ms=1500)
    by = {}
    for r in results:
        by.setdefault(r.family, []).append(r)
    assert all(r.outcome == "correct" for r in by["canonical"])
    # slow belts keep a never-stopped box > 1.5 s in the zone: the rule itself is wrong
    assert any(r.outcome == "spec_error" for r in by["drive_through"])
    # merged detections hide an uninspected box: a dangerous false PASS from perception
    assert any(r.outcome == "perception_error" and r.detector_verdict == "PASS" for r in by["tailgate"])
    # identity loss under the occluder: false alarm on a box that was inspected
    assert any(r.outcome == "perception_error" and r.detector_verdict == "FAIL" for r in by["occluded_station"])
    assert all(r.perception_source == "mock" for r in results)
