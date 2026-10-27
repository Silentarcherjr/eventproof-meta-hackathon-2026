from __future__ import annotations

import json

import pytest

from eventproof.challenge.families import FAMILIES
from eventproof.challenge.minimize import (
    KNOBS,
    MIN_FRAMES,
    Evaluator,
    is_failure,
    minimize,
    reduce_scene,
    same_failure,
)
from eventproof.challenge.render import ground_truth
from eventproof.challenge.replay import export_pair, identity_events, perception_divergence
from eventproof.challenge.runner import mock_perceiver

CASES = [("tailgate", 0), ("occluded_station", 1), ("drive_through", 0), ("brief_stop", 5)]


@pytest.fixture(scope="module")
def counterexamples():
    return {(f, s): minimize(f, s) for f, s in CASES}


@pytest.mark.parametrize("family", sorted(KNOBS))
def test_knob_at_zero_is_identity(family):
    scene = FAMILIES[family](0)
    _, knob = KNOBS[family]
    assert knob(scene, 0.0).scene_hash() == scene.scene_hash()


@pytest.mark.parametrize("case", CASES)
def test_reduction_preserves_the_same_failure(case, counterexamples):
    cx = counterexamples[case]
    assert is_failure(cx.original) and same_failure(cx.original, cx.reduced)
    assert cx.reduced_scene.n_frames >= MIN_FRAMES
    assert cx.reduction.frames_after <= cx.reduction.frames_before
    assert cx.perception == "mock"


@pytest.mark.parametrize("case", CASES)
def test_boundary_pair_is_a_real_flip(case, counterexamples):
    pair = counterexamples[case].pair
    assert pair is not None
    assert pair.t_fail < pair.t_pass
    assert same_failure(counterexamples[case].reduced, pair.fail)
    assert pair.passing.outcome == "correct"
    # re-evaluating the stored scenes reproduces both verdicts (nothing is cached or asserted by hand)
    ev = Evaluator(counterexamples[case].dwell_ms, mock_perceiver)
    assert ev(pair.fail_scene).detector_verdict == pair.fail.detector_verdict
    assert ev(pair.pass_scene).outcome == "correct"


def test_tailgate_pair_is_near_identical(counterexamples):
    pair = counterexamples[("tailgate", 0)].pair
    assert pair.t_pass - pair.t_fail < 0.01
    gt = ground_truth(pair.fail_scene)
    events = identity_events(gt, mock_perceiver(pair.fail_scene, gt))
    assert any(e.kind == "merged" for e in events)
    gt_p = ground_truth(pair.pass_scene)
    assert perception_divergence(mock_perceiver(pair.fail_scene, gt), mock_perceiver(pair.pass_scene, gt_p)) is not None


def test_minimize_is_deterministic(counterexamples):
    again = minimize("tailgate", 0)
    first = counterexamples[("tailgate", 0)]
    assert again.pair.fail_scene.scene_hash() == first.pair.fail_scene.scene_hash()
    assert again.pair.pass_scene.scene_hash() == first.pair.pass_scene.scene_hash()


def test_non_failing_scene_is_rejected():
    scene = FAMILIES["canonical"](0)
    with pytest.raises(ValueError):
        reduce_scene(scene, Evaluator(1500.0, mock_perceiver))


def test_export_pair_writes_evidence(tmp_path, counterexamples):
    res = export_pair(counterexamples[("tailgate", 0)], tmp_path, video=False)
    assert res["decisive_pngs"] and all((tmp_path / p).exists() for p in res["decisive_pngs"])
    saved = json.loads((tmp_path / "replay.json").read_text())
    assert saved["fail_scene_sha256"] != saved["pass_scene_sha256"]
    assert saved["scene_difference"]["frames_differing"] > 0
