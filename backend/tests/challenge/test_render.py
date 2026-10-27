from __future__ import annotations

import json
import shutil
import subprocess

import numpy as np
import pytest

from eventproof.challenge.render import (
    frames_digest,
    ground_truth,
    oracle_view,
    render_frames,
    render_scene,
)
from eventproof.challenge.scene import COLORS, Occluder, SceneSpec, canonical_scene
from eventproof.engine.evaluator import evaluate
from eventproof.schemas.rules import VisualRule
from tests.conftest import CANONICAL_RULE


def scene_rule(scene: SceneSpec, dwell_ms: float = 1500) -> VisualRule:
    rule = {**CANONICAL_RULE, "zones": [z.model_dump() for z in scene.zones],
            "lines": [ln.model_dump() for ln in scene.lines]}
    rule["check"] = {**rule["check"], "conclusion": {**rule["check"]["conclusion"],
                                                     "first": {"op": "DWELL", "zone": "inspection", "min_ms": dwell_ms}}}
    return VisualRule.model_validate(rule)


def test_same_seed_same_scene_and_pixels():
    a, b = canonical_scene(11), canonical_scene(11)
    assert a.scene_hash() == b.scene_hash()
    assert frames_digest(a) == frames_digest(b)


def test_different_seeds_differ():
    hashes = {canonical_scene(s).scene_hash() for s in range(20)}
    assert len(hashes) == 20


@pytest.mark.parametrize("seed", range(12))
def test_ground_truth_boxes_match_rendered_pixels(seed):
    scene = canonical_scene(seed)
    gt = ground_truth(scene)
    frames = {f: img for f, img in render_frames(scene)}
    assert gt.frames, "every canonical scene has visible objects"
    for tf in gt.frames[:: max(1, len(gt.frames) // 25)]:
        img = frames[tf.frame_index]
        x1, y1, x2, y2 = (int(v) for v in (tf.box.x1, tf.box.y1, tf.box.x2, tf.box.y2))
        cy = (y1 + y2) // 2
        assert tuple(img[cy, x1 + 3]) == COLORS["blue"], "box body is drawn where the ground truth says"
        if x1 >= 2:
            assert tuple(img[cy, x1 - 2]) != COLORS["blue"], "no box pixels left of the ground-truth box"


@pytest.mark.parametrize("seed", range(30))
def test_expected_verdict_follows_generated_behaviour(seed):
    """The oracle label must agree with how the generator moved each box (independent derivation)."""
    scene = canonical_scene(seed)
    report = evaluate(scene_rule(scene), oracle_view(ground_truth(scene)))
    for obj in scene.objects:
        inspected = len(obj.waypoints) == 4  # generator stops the box at the station
        verdict = next(o.verdict for o in report.objects if o.object_id == obj.object_id)
        assert verdict == ("PASS" if inspected else "VIOLATION"), f"seed {seed} object {obj.object_id}"


def test_occluder_marks_ground_truth_and_hides_pixels():
    scene = canonical_scene(3, n_objects=1)
    scene.occluders.append(Occluder(x1=0.25, y1=0.0, x2=0.55, y2=1.0))
    gt = ground_truth(scene)
    hidden = [f for f in gt.frames if f.occluded]
    assert hidden, "box passes under the occluder"
    f = hidden[0]
    img = dict(render_frames(scene))[f.frame_index]
    cx, cy = int((f.box.x1 + f.box.x2) / 2), int((f.box.y1 + f.box.y2) / 2)
    assert tuple(img[cy, cx]) != COLORS["blue"]
    assert all(not x.occluded for x in oracle_view(gt).frames)


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg not installed")
def test_mp4_encoding_is_valid_and_reproducible(tmp_path):
    scene = canonical_scene(5)
    r1 = render_scene(scene, tmp_path / "a")
    r2 = render_scene(scene, tmp_path / "b")
    assert r1.frames_sha256 == r2.frames_sha256
    assert r1.mp4_sha256 == r2.mp4_sha256
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
         "stream=codec_name,width,height,nb_read_frames,pix_fmt", "-of", "json", str(r1.directory / "video.mp4")],
        capture_output=True, text=True, check=True).stdout)["streams"][0]
    assert probe["codec_name"] == "h264" and probe["pix_fmt"] == "yuv420p"
    assert (probe["width"], probe["height"]) == (scene.width, scene.height)
    assert int(probe["nb_read_frames"]) == scene.n_frames
    manifest = json.loads((r1.directory / "manifest.json").read_text())
    assert manifest["scene_sha256"] == scene.scene_hash() and manifest["mp4_sha256"] == r1.mp4_sha256


def test_frames_are_uint8_rgb():
    scene = canonical_scene(1)
    _, img = next(iter(render_frames(scene)))
    assert img.dtype == np.uint8 and img.shape == (scene.height, scene.width, 3)


def test_naive_half_second_threshold_is_fooled_by_drive_through():
    """Documents the real ambiguity the Challenge search should rediscover: transit alone exceeds 0.5 s."""
    fooled = 0
    for seed in range(30):
        scene = canonical_scene(seed)
        report = evaluate(scene_rule(scene, dwell_ms=500), oracle_view(ground_truth(scene)))
        for obj in scene.objects:
            v = next(o.verdict for o in report.objects if o.object_id == obj.object_id)
            fooled += len(obj.waypoints) == 2 and v == "PASS"
    assert fooled > 0
