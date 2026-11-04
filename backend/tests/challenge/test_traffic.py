"""Development cases only; the real holdout is exported, never evaluated or tuned here."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from eventproof.challenge.minimize import Evaluator, boundary_pair, minimize
from eventproof.challenge.render import frames_digest, ground_truth, render_frames
from eventproof.challenge.runner import bind_rule, run_case, run_suite
from eventproof.challenge.scene import SceneObject, SceneSpec, Waypoint
from eventproof.challenge.traffic import (
    DEV_SEEDS,
    HOLDOUT_SEEDS,
    TRAFFIC_FAMILIES,
    TrafficTracks,
    box_at,
    full_stop,
    knob_speed,
    knob_stop_distance,
    knob_stop_duration,
    perfect_perceiver,
    perfect_tracks,
    rolling_stop,
    scene_truth,
    traffic_rule,
)
from eventproof.challenge.traffic_export import freeze, verify
from eventproof.engine.evaluator import evaluate

EXPECTED = {
    "full_stop": ["PASS"], "rolling_stop": ["VIOLATION"], "no_stop": ["VIOLATION"],
    "brief_stop": ["VIOLATION"], "queue": ["PASS", "VIOLATION"], "occluded": ["PASS"],
    "wrong_way": ["VIOLATION"], "tailgate": ["PASS", "PASS"],
}


def hand_scene(points):
    scene = full_stop(0)
    obj = SceneObject(object_id=0, color="blue", size=(0.06, 0.08),
                      waypoints=[Waypoint(frame=f, x=x, y=0.53) for f, x in points])
    return SceneSpec.model_validate({**scene.model_dump(), "objects": [obj.model_dump()],
                                     "occluders": [], "n_frames": 80})


@pytest.mark.parametrize("name", sorted(TRAFFIC_FAMILIES))
def test_determinism(name):
    a, b = TRAFFIC_FAMILIES[name](7), TRAFFIC_FAMILIES[name](7)
    assert a.scene_hash() == b.scene_hash()
    assert frames_digest(a) == frames_digest(b)
    assert perfect_tracks(a).model_dump_json() == perfect_tracks(b).model_dump_json()
    assert scene_truth(a) == scene_truth(b)
    assert SceneSpec.model_validate_json(a.model_dump_json()).scene_hash() == a.scene_hash()


@pytest.mark.parametrize("name", sorted(TRAFFIC_FAMILIES))
def test_family_truth_and_per_car_engine_verdicts(name):
    for seed in DEV_SEEDS:
        scene = TRAFFIC_FAMILIES[name](seed)
        truth = scene_truth(scene)
        assert [t.intended for t in truth] == EXPECTED[name]
        assert all(t.crossed_line for t in truth)
        assert all(t.direction == ("wrong_way" if name == "wrong_way" else "forward") for t in truth)
        if name in {"full_stop", "occluded", "tailgate"}:
            assert all(t.stationary_seconds >= 2.1 and t.standing_still_seconds >= 1.5 for t in truth)
        if name in {"rolling_stop", "no_stop", "wrong_way"}:
            assert all(t.stationary_seconds == t.standing_still_seconds == 0 for t in truth)
        if name == "brief_stop":
            assert 0 < truth[0].stationary_seconds < 1.5
        if name == "queue":
            follower = scene.objects[1]
            assert follower.waypoints[2].frame - follower.waypoints[1].frame >= 29
            assert follower.waypoints[1].x < 0.54  # the long stop is outside the waiting zone
            assert truth[1].standing_still_seconds == 0
        if name == "tailgate":
            for f in range(scene.objects[0].waypoints[-1].frame + 1):
                a, b = scene.objects[0].center_at(f), scene.objects[1].center_at(f)
                assert 0.066 < a[0] - b[0] < 0.084 and a[1] == b[1]
        report = evaluate(traffic_rule(scene), perfect_tracks(scene))
        assert {o.object_id: o.verdict for o in report.objects} == {t.object_id: t.intended for t in truth}
        assert run_case(scene, traffic_rule(scene), perfect_perceiver).outcome == "correct"
        assert report.track_source == "synthetic"


@pytest.mark.parametrize(("end_stop", "seconds", "verdict"), [(37, 1.4, "VIOLATION"), (38, 1.5, "PASS")])
def test_hand_checked_sampled_boundary(end_stop, seconds, verdict):
    # Fast arrival at f20; f24 is the first still sample after the 0.4 s speed window.
    scene = hand_scene([(0, 0.1), (20, 0.65), (end_stop, 0.65), (end_stop + 12, 0.92)])
    truth = scene_truth(scene)[0]
    assert truth.standing_still_seconds == seconds
    assert truth.stationary_seconds == (end_stop - 20) / 10
    assert truth.intended == verdict
    assert evaluate(traffic_rule(scene), perfect_tracks(scene)).objects[0].verdict == verdict


def test_hand_checked_speed_separate_stops_and_late_stops():
    for dx, expected in [(0.016, "PASS"), (0.04, "VIOLATION")]:
        scene = hand_scene([(0, 0.1), (20, 0.58), (40, 0.58 + dx), (55, 0.92)])
        assert scene_truth(scene)[0].stationary_seconds == 0
        assert scene_truth(scene)[0].intended == expected
        assert evaluate(traffic_rule(scene), perfect_tracks(scene)).objects[0].verdict == expected
    for points in (
        [(0, 0.1), (12, 0.58), (22, 0.58), (27, 0.66), (37, 0.66), (50, 0.92)],
        [(0, 0.92), (20, 0.65), (50, 0.65), (70, 0.1)],
    ):
        scene = hand_scene(points)
        assert scene_truth(scene)[0].intended == "VIOLATION"
        assert evaluate(traffic_rule(scene), perfect_tracks(scene)).objects[0].verdict == "VIOLATION"


def test_no_crossing_and_touching_line():
    for points in ([(0, 0.1), (30, 0.7)], [(0, 0.1), (30, 0.72)]):
        scene = hand_scene(points)
        truth = scene_truth(scene)[0]
        assert not truth.crossed_line and truth.direction == "none" and truth.intended == "PASS"
        assert evaluate(traffic_rule(scene), perfect_tracks(scene)).objects[0].verdict == "PASS"
    scene = hand_scene([(0, 0.1), (30, 0.72), (33, 0.72), (50, 0.92)])
    assert scene_truth(scene)[0].crossing_frame == 34


def test_occlusion_flags_and_pixels_do_not_erase_physical_truth():
    scene = TRAFFIC_FAMILIES["occluded"](0)
    visible = ground_truth(scene)
    assert any(t.occluded for t in visible.frames if t.label == "car")
    assert not any(t.occluded for t in perfect_tracks(scene).frames)
    assert scene_truth(scene) == scene_truth(scene.model_copy(update={"occluders": []}))
    images = dict(render_frames(scene))
    f = next(t for t in visible.frames if t.occluded)
    x, y = scene.objects[0].center_at(f.frame_index)
    assert tuple(images[f.frame_index][round(y * scene.height), round(x * scene.width)]) == (128, 128, 132)


def test_perspective_jitter_and_box_alignment():
    scene = rolling_stop(5)
    images = dict(render_frames(scene))
    for tf in perfect_tracks(scene).frames[::9]:
        obj = next(o for o in scene.objects if o.object_id == tf.object_id)
        x, y = obj.center_at(tf.frame_index)
        assert (tf.box.x1 + tf.box.x2) / 2 == pytest.approx(x * scene.width)
        assert (tf.box.y1 + tf.box.y2) / 2 == pytest.approx(y * scene.height)
        assert tf.box == box_at(scene, obj, tf.frame_index)
        assert tuple(images[tf.frame_index][round(tf.box.y1), round(tf.box.x1)]) != (57, 60, 63)
    clean = scene.model_copy(update={"notes": json.dumps({**json.loads(scene.notes), "box_jitter": 0})})
    assert frames_digest(scene) != frames_digest(clean)
    assert scene_truth(scene) == scene_truth(clean)


@pytest.mark.parametrize("knob", [knob_stop_duration, knob_speed, knob_stop_distance])
def test_knobs_validate_and_change_only_one_car(knob):
    scene = TRAFFIC_FAMILIES["tailgate"](3)
    assert knob(scene, 0).scene_hash() == scene.scene_hash()
    altered = knob(scene, 1)
    SceneSpec.model_validate(altered.model_dump())
    assert altered.objects[1:] == scene.objects[1:]
    assert altered.objects[0] != scene.objects[0]
    with pytest.raises(ValueError):
        knob(scene, -0.1)


def test_minimizer_finds_rolling_stop_pair():
    scene = rolling_stop(0)
    naive = traffic_rule(scene, max_speed=None)
    assert run_case(scene, naive, perfect_perceiver).outcome == "spec_error"
    cx = minimize("rolling_stop", 0, rule=naive, perceiver=perfect_perceiver, world="traffic")
    pair = cx.pair
    assert pair is not None and pair.t_pass - pair.t_fail < 0.01
    assert cx.original.detector_verdict == pair.fail.detector_verdict == "PASS"
    assert pair.passing.detector_verdict == "FAIL" and pair.passing.outcome == "correct"
    assert pair.fail.intended == pair.passing.intended == "FAIL"
    ev = Evaluator(1500, perfect_perceiver, naive)
    assert ev(pair.fail_scene) == pair.fail and ev(pair.pass_scene) == pair.passing
    assert bind_rule(naive, pair.fail_scene).entity.concept == "car"
    a, b = pair.fail_scene.objects[0], pair.pass_scene.objects[0]
    assert [(w.x, w.y) for w in a.waypoints] == [(w.x, w.y) for w in b.waypoints]
    assert a.waypoints[2].frame - b.waypoints[2].frame == 1


def test_duration_and_distance_boundary_search():
    scene = full_stop(2)
    ev = Evaluator(4000, perfect_perceiver, traffic_rule(scene, wait_s=4))
    pair = boundary_pair(scene, "duration", knob_stop_duration, ev, ev(scene))
    assert pair is not None and pair.fail.detector_verdict != pair.passing.detector_verdict
    pair = boundary_pair(scene, "distance", knob_stop_distance, ev, ev(scene))
    assert pair is not None and pair.passing.outcome == "correct"


def test_runner_and_holdout_isolation():
    assert not set(DEV_SEEDS) & set(HOLDOUT_SEEDS)
    assert len(HOLDOUT_SEEDS) * len(TRAFFIC_FAMILIES) == 200
    results = run_suite(list(TRAFFIC_FAMILIES), [0, 1], perceiver=perfect_perceiver, world="traffic")
    assert len(results) == 16 and all(r.outcome == "correct" for r in results)
    with pytest.raises(ValueError, match="holdout"):
        minimize("rolling_stop", HOLDOUT_SEEDS.start, world="traffic")
    with pytest.raises(ValueError, match="holdout"):
        run_suite(["full_stop"], [HOLDOUT_SEEDS.start], world="traffic")


def test_export_hashes_provenance_and_refusal_to_overwrite(tmp_path, monkeypatch):
    import eventproof.engine.evaluator as engine

    monkeypatch.setattr(engine, "evaluate", lambda *a, **k: pytest.fail("export must not run a detector"))
    out = tmp_path / "release"
    # Tiny test fixture uses separate seeds, never the real holdout.
    release = freeze(out, encode=False, dev_seeds=[901], holdout_seeds=[902], families=["full_stop"])
    assert release == verify(out) and release["engine_evaluation"] == "not run"
    with pytest.raises(FileExistsError):
        freeze(out, encode=False)
    tracks_path = next((out / "dev").glob("*/tracks.json"))
    tracks = TrafficTracks.model_validate_json(tracks_path.read_text())
    assert tracks.source == "synthetic" and not any(t.occluded for t in tracks.frames)
    tracks_path.write_text(tracks_path.read_text() + " ")
    with pytest.raises(ValueError, match="hash drift"):
        verify(out)
    with pytest.raises(ValueError, match="overlap"):
        freeze(tmp_path / "bad", encode=False, dev_seeds=[1], holdout_seeds=[1])
    assert not (tmp_path / "bad").exists()


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="ffmpeg not installed")
def test_export_mp4_valid_deterministic_and_hashed(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for out in (a, b):
        freeze(out, dev_seeds=[901], holdout_seeds=[902], families=["rolling_stop"])
        verify(out)
    ma, mb = next((a / "dev").glob("*/manifest.json")), next((b / "dev").glob("*/manifest.json"))
    assert ma.read_bytes() == mb.read_bytes()
    scene = rolling_stop(901)
    probe = json.loads(subprocess.run([
        "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
        "stream=codec_name,width,height,nb_read_frames", "-of", "json", str(ma.parent / "video.mp4"),
    ], capture_output=True, text=True, check=True).stdout)["streams"][0]
    assert probe["codec_name"] == "h264"
    assert (probe["width"], probe["height"], int(probe["nb_read_frames"])) == (480, 270, scene.n_frames)


def test_committed_release_hashes_only():
    # Verifies frozen bytes, without regenerating trajectories or evaluating holdout labels.
    out = Path(__file__).resolve().parents[3] / "benchmark" / "traffic_sim" / "v1"
    if not out.exists():
        pytest.skip("release not frozen yet")
    release = verify(out, require_video=False)
    assert release["splits"]["dev"]["cases"] == 320
    assert release["splits"]["holdout"]["cases"] == 200
