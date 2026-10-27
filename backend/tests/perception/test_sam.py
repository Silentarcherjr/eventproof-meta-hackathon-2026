from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from eventproof.challenge.families import FAMILIES
from eventproof.challenge.render import ground_truth
from eventproof.challenge.runner import inspection_rule, run_case
from eventproof.meta import client as meta_client
from eventproof.meta.client import MetaApiUnavailable, MetaSettings
from eventproof.perception import sam as sam_mod
from eventproof.perception.sam import LiveCallLimit, SamTracker, sam_perceiver, to_trackset
from eventproof.perception.sam_wire import SamParseError, parse_line, parse_output, split_deltas
from eventproof.schemas.tracks import TrackSet, VideoInfo

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "sam"


def encode_wire(ts: TrackSet, with_conf: bool = True) -> list[str]:
    """Test helper: ground-truth tracks -> documented SAM wire lines (inclusive x2/y2; masks are placeholders)."""
    by: dict[int, list] = {}
    for f in ts.frames:
        if not f.occluded:
            by.setdefault(f.frame_index, []).append(f)
    lines = []
    for fi in sorted(by):
        recs = []
        for f in sorted(by[fi], key=lambda f: f.object_id):
            b = f.box
            c = ";c=0.9375" if with_conf else ""
            recs.append(f"{f.object_id}<|box;x1={int(b.x1)};y1={int(b.y1)};x2={int(b.x2) - 1};y2={int(b.y2) - 1};"
                        f"w={ts.video.width};h={ts.video.height}{c}|><|mask;x=0;y=0;data=4,4,!a|>b|>")
        lines.append(f"<{fi}f>" + ",".join(recs))
    return lines


# ---- wire parsing ------------------------------------------------------------------------------


def test_documented_fixture_parses_with_skips_sparse_ids_and_hostile_payloads():
    frames = parse_output((FIXTURES / "two_objects_skips.txt").read_text().splitlines())
    assert [f.frame for f in frames] == [0, 3, 4]  # frames 1-2 had no detections: no line
    assert [r.object_id for r in frames[0].records] == [0, 2]  # ids are not dense
    r0 = frames[0].records[0]
    assert (r0.x1, r0.y1, r0.x2, r0.y2, r0.w, r0.h, r0.confidence) == (211, 228, 270, 254, 320, 334, 0.9609375)
    assert r0.mask.encoding == "~" and r0.mask.payload_chars == len("Ab|>c,d1<|box;e")
    assert frames[1].records[0].mask.encoding == "!"


def test_record_without_mask_and_without_confidence():
    f = parse_line("<7f>3<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|>")
    assert f.frame == 7 and f.records[0].confidence is None and f.records[0].mask is None


@pytest.mark.parametrize("bad", [
    "0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|>",                       # no frame marker
    "<1f>0<|box;x1=1;y1=2;x2=3;w=10;h=10|>",                         # missing y2
    "<1f>0<|box;x1=5;y1=2;x2=3;y2=4;w=10;h=10|>",                    # inverted
    "<1f>0<|box;x1=1;y1=2;x2=10;y2=4;w=10;h=10|>",                   # x2 inclusive must be < w
    "<1f>0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10;c=1.5|>",              # confidence out of range
    "<1f>0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10;z=1|>",                # unknown field
    "<1f>0<|box;x1=a;y1=2;x2=3;y2=4;w=10;h=10|>",                    # non-numeric
    "<1f>0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|>,0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|>",  # duplicate id
    "<1f>0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|>;1<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|>",  # bad separator
])
def test_malformed_lines_raise(bad):
    with pytest.raises(SamParseError):
        parse_line(bad)


def test_output_level_errors():
    box = "<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|>"
    with pytest.raises(SamParseError, match="twice"):
        parse_output([f"<1f>0{box}", f"<1f>1{box}"])
    with pytest.raises(SamParseError, match="frame size"):
        parse_output([f"<1f>0{box}", "<2f>0<|box;x1=1;y1=2;x2=3;y2=4;w=20;h=10|>"])
    assert parse_output([]) == []  # zero matches: empty output is valid


def test_split_deltas_tolerates_chunking():
    lines = (FIXTURES / "two_objects_skips.txt").read_text().splitlines()
    one_per_delta = split_deltas(lines)  # documented case: one line per delta, no newline
    assert one_per_delta == lines
    blob = "\n".join(lines) + "\n"
    assert split_deltas([blob]) == lines
    assert split_deltas([blob[i:i + 7] for i in range(0, len(blob), 7)]) == lines  # arbitrary splits with newlines


@settings(max_examples=40, deadline=None)
@given(st.sampled_from(sorted(FAMILIES)), st.integers(0, 50), st.booleans())
def test_roundtrip_ground_truth_through_wire(family, seed, with_conf):
    scene = FAMILIES[family](seed)
    gt = ground_truth(scene)
    ts = to_trackset(parse_output(encode_wire(gt, with_conf)), gt.video, "blue box", "test")
    visible = sorted((f.frame_index, f.object_id, f.box.model_dump()) for f in gt.frames if not f.occluded)
    assert sorted((f.frame_index, f.object_id, f.box.model_dump()) for f in ts.frames) == visible
    assert ts.source == "sam-3.1"


def test_to_trackset_rejects_size_mismatch_and_out_of_range_frames():
    frames = parse_output((FIXTURES / "two_objects_skips.txt").read_text().splitlines())
    with pytest.raises(SamParseError, match="frame size"):
        to_trackset(frames, VideoInfo(width=640, height=360, fps=15, frame_count=10), "x", "t")
    with pytest.raises(SamParseError, match="beyond"):
        to_trackset(frames, VideoInfo(width=320, height=334, fps=15, frame_count=4), "x", "t")
    ts = to_trackset(frames, VideoInfo(width=320, height=334, fps=10, frame_count=10), "blue box", "t")
    f = ts.frames[0]
    assert (f.box.x2, f.box.y2, f.timestamp_ms) == (271, 255, 0.0)  # inclusive -> exclusive
    assert ts.frames[-1].timestamp_ms == 400.0 and ts.frames[-1].mask_ref == "f4/o2"


# ---- live call path (fake client, no network) ----------------------------------------------------


class FakeClient:
    """Stands in for the OpenAI-compatible client; records the request shape."""

    def __init__(self, lines: list[str]):
        self.lines, self.requests = lines, []
        self.files = SimpleNamespace(create=self._upload)
        self.responses = SimpleNamespace(stream=self._stream)

    def _upload(self, file, purpose):
        self.requests.append(("upload", purpose))
        return SimpleNamespace(id="file-fake")

    def _stream(self, **kw):
        self.requests.append(("stream", kw))
        lines = self.lines

        class _S:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def __iter__(self):
                yield SimpleNamespace(type="response.created")
                for ln in lines:
                    yield SimpleNamespace(type="response.output_text.delta", delta=ln)
                yield SimpleNamespace(type="response.completed")

            def get_final_response(self):
                return SimpleNamespace(id="resp-fake")

        return _S()


@pytest.fixture
def keyed():
    return MetaSettings(api_key="test-key-not-real", base_url="https://example.invalid/v1",
                        muse_model="muse-spark-1.3", sam_model="sam-3.1", budget_usd=1)


def test_tracker_request_shape_and_cache(tmp_path, monkeypatch, keyed):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"not really a video")
    fake = FakeClient((FIXTURES / "two_objects_skips.txt").read_text().splitlines())
    monkeypatch.setattr(sam_mod, "get_client", lambda s: fake)
    tr = SamTracker(keyed, cache_dir=tmp_path / "cache", max_live_calls=1)
    info = VideoInfo(width=320, height=334, fps=10, frame_count=10)
    ts = tr.tracks(video, "blue box", info)
    assert tr.live_calls == 1 and ts.source == "sam-3.1" and "resp-fake" in ts.source_ref
    assert "cached" not in ts.source_ref
    kind, req = fake.requests[1]
    content = req["input"][0]["content"]
    assert req["model"] == "sam-3.1" and req["metadata"]["include_confidence"] == "true"
    assert content == [{"type": "input_text", "text": "blue box"}, {"type": "input_video", "file_id": "file-fake"}]
    assert fake.requests[0] == ("upload", "user_data")
    cached_file = next((tmp_path / "cache").glob("*.json"))
    assert "test-key-not-real" not in cached_file.read_text()
    # second call: served from cache, labelled as such, no new request
    ts2 = tr.tracks(video, "blue box", info)
    assert tr.live_calls == 1 and len(fake.requests) == 2
    assert ts2.source_ref.endswith(":cached") and ts2.frames == ts.frames


def test_no_key_and_no_cache_is_blocked_not_mocked(tmp_path, monkeypatch):
    monkeypatch.setattr(meta_client.os, "environ", {})
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    tr = SamTracker(MetaSettings.from_env(), cache_dir=tmp_path / "cache", max_live_calls=1)
    with pytest.raises(MetaApiUnavailable):
        tr.track(video, "blue box")


def test_live_calls_need_an_explicit_allowance(tmp_path, monkeypatch, keyed):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    fake = FakeClient([])
    monkeypatch.setattr(sam_mod, "get_client", lambda s: fake)
    with pytest.raises(LiveCallLimit):
        SamTracker(keyed, cache_dir=tmp_path / "cache").track(video, "blue box")  # default allowance 0
    assert fake.requests == []  # nothing uploaded


def test_sam_perceiver_in_challenge_mode_with_perfect_fake_sam(tmp_path, monkeypatch, keyed):
    scene = FAMILIES["canonical"](3)
    gt = ground_truth(scene)
    fake = FakeClient(encode_wire(gt))
    monkeypatch.setattr(sam_mod, "get_client", lambda s: fake)
    tracker = SamTracker(keyed, cache_dir=tmp_path / "cache", max_live_calls=1)
    perceive = sam_perceiver(tracker, video_dir=tmp_path / "videos")
    r = run_case(scene, inspection_rule(scene), perceive)
    assert r.perception_source == "sam-3.1" and r.outcome == "correct"
    assert (tmp_path / "videos" / f"{scene.scene_hash()[:16]}.mp4").exists()
    # what was uploaded is the rendered video only; ground truth never leaves the process
    assert all("frames" not in json.dumps(req, default=str) for k, req in fake.requests if k == "stream")
