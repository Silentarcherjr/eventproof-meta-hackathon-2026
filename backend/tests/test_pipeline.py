from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eventproof import pipeline
from eventproof.api import main as api
from eventproof.challenge.families import FAMILIES
from eventproof.challenge.render import encode_mp4, ground_truth
from eventproof.meta import muse_rules as mr
from eventproof.meta.client import MetaSettings
from eventproof.meta.muse_rules import MuseRuleCompiler
from eventproof.perception import sam as sam_mod
from eventproof.perception.sam import SamTracker
from eventproof.video.ingest import VideoRejected, ingest
from tests.perception.test_sam import FakeClient, encode_wire
from tests.test_muse_rules import GOOD, LAYOUT, FakeMuse

FFMPEG = shutil.which("ffmpeg")
SETTINGS = MetaSettings(api_key="test-key-not-real", base_url="https://example.invalid/v1",
                        muse_model="muse-spark-1.3", sam_model="sam-3.1", budget_usd=1)
RULE = "Every blue box must stay at least 1.5 seconds in the inspection zone before it crosses into packing."


def _ffmpeg(*args: str) -> None:
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


# ---- ingestion ---------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def videos(tmp_path_factory):
    d = tmp_path_factory.mktemp("videos")
    src = "testsrc2=size=320x240:rate=10"
    _ffmpeg("-f", "lavfi", "-i", f"{src}:duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(d / "ok.mp4"))
    _ffmpeg("-f", "lavfi", "-i", f"{src}:duration=2", "-c:v", "mpeg4", str(d / "mpeg4.mp4"))
    _ffmpeg("-display_rotation", "90", "-i", str(d / "ok.mp4"), "-c", "copy", str(d / "rotated.mp4"))
    _ffmpeg("-f", "lavfi", "-i", f"{src}:duration=25", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
            str(d / "long.mp4"))
    _ffmpeg("-f", "lavfi", "-i", f"{src}:duration=2", "-c:v", "libvpx-vp9", str(d / "clip.webm"))
    (d / "fake.mp4").write_text("this is not a video")
    return d


def test_good_video_passes_through_unchanged(videos, tmp_path):
    v = ingest(videos / "ok.mp4", tmp_path)
    assert not v.reencoded and v.path == videos / "ok.mp4" and v.sha256 == v.original_sha256
    assert (v.info.width, v.info.height, v.info.fps, v.info.frame_count) == (320, 240, 10.0, 20)


def test_other_codecs_and_rotation_are_normalized(videos, tmp_path):
    v = ingest(videos / "mpeg4.mp4", tmp_path)
    assert v.reencoded and v.codec == "h264" and any("mpeg4" in r for r in v.reencode_reasons)
    assert v.sha256 != v.original_sha256 and v.info.frame_count == 20
    r = ingest(videos / "rotated.mp4", tmp_path)
    assert r.reencoded and (r.info.width, r.info.height) == (240, 320), "rotation applied to pixels"


@pytest.mark.parametrize("name,msg", [("long.mp4", "duration"), ("clip.webm", "container"), ("fake.mp4", "not a readable")])
def test_bad_videos_are_rejected(videos, tmp_path, name, msg):
    with pytest.raises(VideoRejected, match=msg):
        ingest(videos / name, tmp_path)


# ---- pipeline ----------------------------------------------------------------------------------------


@pytest.fixture
def clip(tmp_path):
    scene = FAMILIES["canonical"](3)
    path = tmp_path / "clip.mp4"
    encode_mp4(scene, path)
    return scene, path


def _fakes(monkeypatch, scene, muse_outputs):
    muse, sam = FakeMuse(muse_outputs), FakeClient(encode_wire(ground_truth(scene)))
    monkeypatch.setattr(mr, "get_client", lambda s: muse)
    monkeypatch.setattr(sam_mod, "get_client", lambda s: sam)
    return muse, sam


def test_end_to_end_evidence(tmp_path, monkeypatch, clip):
    scene, path = clip
    _, sam = _fakes(monkeypatch, scene, [GOOD])
    ev = pipeline.run(path, RULE, LAYOUT, MuseRuleCompiler(SETTINGS, cache_dir=tmp_path / "mc"),
                      SamTracker(SETTINGS, cache_dir=tmp_path / "sc", max_live_calls=1), runs_dir=tmp_path / "runs")
    assert ev.status == "completed" and ev.verify()
    assert ev.result.overall == "FAIL" and ev.result.track_source == "sam-3.1"
    assert ev.rule.rule_hash == ev.result.rule_hash and ev.rule.request_ids == ["req-1"]
    assert ev.perception.prompt == "blue box" and ev.perception.cached is False
    assert ev.video.sha256 == ev.video.original_sha256 and not ev.video.reencoded
    d = tmp_path / "runs" / ev.run_id
    assert {p.name for p in d.iterdir()} >= {"evidence.json", "rule.json", "tracks.json"}
    on_disk = pipeline.load(ev.run_id, tmp_path / "runs")
    assert on_disk.verify() and on_disk == ev
    assert "test-key-not-real" not in (d / "evidence.json").read_text()
    assert pipeline.verify_evidence_file(d / "evidence.json") and ev.video.filename == "clip.mp4"
    assert str(tmp_path) not in (d / "evidence.json").read_text(), "no local paths in evidence"
    raw = json.loads((d / "evidence.json").read_text())
    raw["result"]["overall"] = "PASS"
    (tmp_path / "forged.json").write_text(json.dumps(raw))
    assert not pipeline.verify_evidence_file(tmp_path / "forged.json")
    # tampering with the verdict is detectable
    forged = on_disk.model_copy(deep=True)
    forged.result.overall = "PASS"
    assert not forged.verify()


def test_unsupported_rule_stops_before_sam(tmp_path, monkeypatch, clip):
    scene, path = clip
    _, sam = _fakes(monkeypatch, scene, [{**GOOD, "supported": False, "unsupported_reason": "needs helmets"}])
    ev = pipeline.run(path, "wear helmets", LAYOUT, MuseRuleCompiler(SETTINGS, cache_dir=tmp_path / "mc"),
                      SamTracker(SETTINGS, cache_dir=tmp_path / "sc", max_live_calls=1), runs_dir=tmp_path / "runs")
    assert ev.status == "rule_unsupported" and "helmets" in ev.rule.error and ev.perception is None
    assert sam.requests == [] and ev.verify()


def test_invalid_rule_is_recorded_not_evaluated(tmp_path, monkeypatch, clip):
    scene, path = clip
    bad = copy.deepcopy(GOOD)
    bad["nodes"][1]["event"]["line"] = "nowhere"
    _, sam = _fakes(monkeypatch, scene, [bad, bad])
    ev = pipeline.run(path, RULE, LAYOUT, MuseRuleCompiler(SETTINGS, cache_dir=tmp_path / "mc"),
                      SamTracker(SETTINGS, cache_dir=tmp_path / "sc", max_live_calls=1), runs_dir=tmp_path / "runs")
    assert ev.status == "rule_invalid" and ev.result is None and sam.requests == []


# ---- API ---------------------------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch, clip):
    scene, _ = clip
    _fakes(monkeypatch, scene, [GOOD])
    monkeypatch.setattr(pipeline, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(api, "_compiler", MuseRuleCompiler(SETTINGS, cache_dir=tmp_path / "mc"))
    monkeypatch.setattr(api, "_tracker", SamTracker(SETTINGS, cache_dir=tmp_path / "sc", max_live_calls=1))
    return TestClient(api.app)


def _post(client, path: Path, name: str = "clip.mp4", layout: str | None = None):
    with path.open("rb") as fh:
        return client.post("/runs", files={"video": (name, fh, "video/mp4")},
                           data={"rule_text": RULE, "layout": layout or LAYOUT.model_dump_json()})


def test_api_run_and_fetch(client, clip):
    _, path = clip
    r = _post(client, path)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed" and body["result"]["overall"] == "FAIL"
    again = client.get(f"/runs/{body['run_id']}")
    assert again.status_code == 200 and again.json() == body


def test_api_rejections(client, clip, tmp_path):
    _, path = clip
    assert _post(client, path, name="clip.avi").status_code == 415
    assert _post(client, path, layout="{not json").status_code == 422
    fake = tmp_path / "fake.mp4"
    fake.write_text("not a video")
    assert _post(client, fake).status_code == 422
    assert client.get("/runs/..%2F..%2Fetc").status_code in (400, 404)
    assert client.get("/runs/not-a-run").status_code == 400
    assert client.get("/runs/20260101T000000Z-deadbeef").status_code == 404


def test_api_without_allowance_does_not_spend(client, clip, monkeypatch, tmp_path):
    _, path = clip
    monkeypatch.setattr(api, "_tracker", SamTracker(SETTINGS, cache_dir=tmp_path / "empty", max_live_calls=0))
    r = _post(client, path)
    assert r.status_code == 503 and "allowance" in r.json()["detail"]


def test_evidence_files_are_json(tmp_path, monkeypatch, clip):
    scene, path = clip
    _fakes(monkeypatch, scene, [GOOD])
    ev = pipeline.run(path, RULE, LAYOUT, MuseRuleCompiler(SETTINGS, cache_dir=tmp_path / "mc"),
                      SamTracker(SETTINGS, cache_dir=tmp_path / "sc", max_live_calls=1), runs_dir=tmp_path / "runs")
    for f in ev.files.values():
        json.loads((tmp_path / "runs" / ev.run_id / f).read_text())


def test_api_rejects_oversize_upload(client, clip, monkeypatch):
    _, path = clip
    monkeypatch.setattr(api, "MAX_BYTES", 1000)
    assert _post(client, path).status_code == 413
