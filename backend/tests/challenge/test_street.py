"""Street presentation must not move, relabel or replace any measured traffic artifact."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eventproof.challenge.render import frames_digest, ground_truth, render_frames, render_scene, sha256_file
from eventproof.challenge.scene import SceneSpec, canonical_scene
from eventproof.challenge.street import car_rect, frame_labels
from eventproof.challenge.traffic import TRAFFIC_FAMILIES, box_at, perfect_tracks, scene_truth

ROOT = Path(__file__).resolve().parents[3] / "benchmark" / "traffic_sim"


@pytest.mark.parametrize("family", ["full_stop", "rolling_stop", "queue", "wrong_way"])
def test_default_style_keeps_exact_frozen_v1_raw_frame_hash(family):
    scene = TRAFFIC_FAMILIES[family](0)
    frozen = ROOT / "v1" / "dev" / scene.scene_hash()[:16]
    manifest = json.loads((frozen / "manifest.json").read_text())
    assert frames_digest(scene) == manifest["frames_sha256"]
    assert frames_digest(scene, style="default") == manifest["frames_sha256"]
    # The pre-existing annotation bytes are independent of render style or overlay.
    assert ground_truth(scene).model_dump_json() == (frozen / "ground_truth.json").read_text()


@pytest.mark.parametrize("family", sorted(TRAFFIC_FAMILIES))
def test_street_style_is_deterministic(family):
    scene = TRAFFIC_FAMILIES[family](0)
    a = frames_digest(scene, style="street", overlay=True)
    b = frames_digest(SceneSpec.model_validate_json(scene.model_dump_json()), style="street", overlay=True)
    assert a == b
    assert a != frames_digest(scene, style="street")
    assert a != frames_digest(scene)


@pytest.mark.parametrize("family", sorted(TRAFFIC_FAMILIES))
def test_styles_preserve_scene_tracks_and_truth_byte_for_byte(tmp_path, family):
    scene = TRAFFIC_FAMILIES[family](0)
    spec, gt = scene.model_dump_json(), ground_truth(scene).model_dump_json()
    tracks, truth = perfect_tracks(scene).model_dump_json(), [t.model_dump_json() for t in scene_truth(scene)]
    old = render_scene(scene, tmp_path / "default", encode=False)
    new = render_scene(scene, tmp_path / "street", encode=False, style="street", overlay=True)
    for name in ("scene.json", "ground_truth.json"):
        assert (old.directory / name).read_bytes() == (new.directory / name).read_bytes()
    assert scene.model_dump_json() == spec
    assert ground_truth(scene).model_dump_json() == gt
    assert perfect_tracks(scene).model_dump_json() == tracks
    assert [t.model_dump_json() for t in scene_truth(scene)] == truth
    # Every visual car uses the existing exact analytic box, including jitter and perspective.
    indices = []
    for frame, image in render_frames(scene, style="street", overlay=True):
        indices.append(frame)
        assert image.shape == (scene.height, scene.width, 3) and str(image.dtype) == "uint8"
        for obj in scene.objects:
            box = box_at(scene, obj, frame)
            expected = None if box is None else tuple(round(v) for v in (box.x1, box.y1, box.x2, box.y2))
            assert car_rect(scene, obj, frame) == expected
    assert indices == list(range(scene.n_frames))


@pytest.mark.parametrize("family", sorted(TRAFFIC_FAMILIES))
def test_overlays_read_existing_contract_truth_and_never_announce_future_verdict(family):
    scene = TRAFFIC_FAMILIES[family](0)
    truths = {t.object_id: t for t in scene_truth(scene)}
    for frame in range(scene.n_frames):
        prefix = scene.model_copy(update={"n_frames": frame + 1})
        observed = {t.object_id: t for t in scene_truth(prefix)}
        for label in frame_labels(scene, frame):
            truth = truths[label["object_id"]]
            assert label["standing_still_seconds"] == observed[truth.object_id].standing_still_seconds
            assert label["crossing_frame"] == truth.crossing_frame
            if truth.crossing_frame is None or frame < truth.crossing_frame:
                assert label["verdict"] is None
            else:
                assert label["verdict"] == truth.intended
                assert label["standing_still_seconds"] == truth.standing_still_seconds


def test_render_style_is_explicit_and_frozen_export_cannot_be_restyled(tmp_path):
    scene = TRAFFIC_FAMILIES["full_stop"](0)
    with pytest.raises(ValueError, match="unknown render style"):
        render_scene(scene, tmp_path / "bad", style="not-a-style")
    with pytest.raises(ValueError, match="overlays require street"):
        frames_digest(scene, overlay=True)
    with pytest.raises(ValueError, match="requires a traffic scene"):
        frames_digest(canonical_scene(0), style="street")
    assert not (tmp_path / "bad").exists()
    protected = tmp_path / "frozen" / scene.scene_hash()[:16]
    protected.mkdir(parents=True)
    blob = b'{"files_sha256": {"scene.json":"sealed"}}'
    (protected / "manifest.json").write_bytes(blob)
    with pytest.raises(ValueError, match="frozen traffic export cannot be restyled"):
        render_scene(scene, protected.parent, style="street")
    assert (protected / "manifest.json").read_bytes() == blob
    assert not (protected / "scene.json").exists()


def test_showcase_index_seals_new_video_and_manifest_hashes():
    root = ROOT / "showcase"
    index = json.loads((root / "index.json").read_text())
    assert index["render_style"] == "street/1" and index["overlay"] is True
    entries = [*index["scenes"].values(), *index["pair"].values()]
    assert len(entries) == 10
    for entry in entries:
        directory = root / entry["directory"]
        manifest = json.loads((directory / "manifest.json").read_text())
        scene = SceneSpec.model_validate_json((directory / "scene.json").read_text())
        assert scene.seed == 0 and scene.scene_hash() == entry["scene_sha256"] == manifest["scene_sha256"]
        assert manifest["render_style"] == index["render_style"] and manifest["overlay"]
        assert sha256_file(directory / "video.mp4") == entry["mp4_sha256"] == manifest["mp4_sha256"]
        assert sha256_file(directory / "manifest.json") == entry["manifest_sha256"]
        assert frames_digest(scene, style="street", overlay=True) == entry["frames_sha256"] == manifest["frames_sha256"]
        assert (directory / "video.mp4").stat().st_size < 1_000_000
        assert ground_truth(scene).model_dump_json().encode() == (directory / "ground_truth.json").read_bytes()
