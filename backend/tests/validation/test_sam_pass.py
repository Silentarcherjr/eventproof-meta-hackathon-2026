from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from eventproof.challenge.render import ground_truth
from eventproof.meta.client import MetaSettings
from eventproof.perception import sam as sam_mod
from eventproof.perception.sam import SamTracker
from eventproof.validation import sam_pass
from eventproof.validation.final import load_frozen

KEYED = MetaSettings(api_key="test-key-not-real", base_url="https://example.invalid/v1", muse_model="muse-spark-1.3",
                     sam_model="sam-3.1", budget_usd=1)


def _wire(gt) -> list[str]:
    by: dict[int, list] = {}
    for f in gt.frames:
        if not f.occluded:
            by.setdefault(f.frame_index, []).append(f)
    return [f"<{fi}f>" + ",".join(
        f"{f.object_id}<|box;x1={int(f.box.x1)};y1={int(f.box.y1)};x2={int(f.box.x2) - 1};y2={int(f.box.y2) - 1};"
        f"w={gt.video.width};h={gt.video.height};c=0.9|>" for f in sorted(by[fi], key=lambda f: f.object_id))
        for fi in sorted(by)]


class PerfectSam:
    """Fake API client: answers each upload with the ground-truth boxes of the scene the MP4 was rendered from."""

    def __init__(self, scenes, broken: set[str] = frozenset()):
        self.by_prefix = {s.scene_hash()[:16]: s for _, s in scenes}
        self.broken, self.streams, self._last = broken, 0, None
        self.files = SimpleNamespace(create=self._upload)
        self.responses = SimpleNamespace(stream=self._stream)

    def _upload(self, file, purpose):
        self._last = self.by_prefix[file.name.rsplit("/", 1)[-1][:16]]
        return SimpleNamespace(id="file-fake")

    def _stream(self, **kw):
        scene, outer = self._last, self
        outer.streams += 1
        lines = ["<0f>garbage"] if scene.family in self.broken else _wire(ground_truth(scene))

        class _S:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def __iter__(self):
                for ln in lines:
                    yield SimpleNamespace(type="response.output_text.delta", delta=ln)

            def get_final_response(self):
                return SimpleNamespace(id=f"resp-{outer.streams}")

        return _S()


@pytest.fixture
def small(tmp_path, monkeypatch):
    monkeypatch.setattr(sam_pass, "SUBSET_SEEDS", range(40000, 40001))  # 8 scenes, one per family
    monkeypatch.setattr(sam_pass, "VIDEO_DIR", tmp_path / "videos")
    _, cases = load_frozen()
    return tmp_path, [(c, s) for c, s in cases if c.seed == 40000]


def test_track_respects_allowance_resumes_and_never_recalls(small, monkeypatch):
    tmp, scenes = small
    fake = PerfectSam(scenes)
    monkeypatch.setattr(sam_mod, "get_client", lambda s: fake)
    log_path = tmp / "tracking.json"
    log = sam_pass.track(3, SamTracker(KEYED, cache_dir=tmp / "c", max_live_calls=3), tracking_path=log_path)
    assert fake.streams == 3 and len(log["scenes"]) == 3
    log = sam_pass.track(10, SamTracker(KEYED, cache_dir=tmp / "c", max_live_calls=10), tracking_path=log_path)
    assert fake.streams == 8 and len(log["scenes"]) == 8 and log["live_calls_per_run"] == [3, 5]
    assert all(r["status"] == "ok" and r["response_id"].startswith("resp-") for r in log["scenes"].values())
    assert "test-key-not-real" not in log_path.read_text()


def test_report_uses_cache_only_and_excludes_unparseable_scenes(small, monkeypatch):
    tmp, scenes = small
    fake = PerfectSam(scenes, broken={"two_stops"})
    monkeypatch.setattr(sam_mod, "get_client", lambda s: fake)
    log_path = tmp / "tracking.json"
    sam_pass.track(8, SamTracker(KEYED, cache_dir=tmp / "c", max_live_calls=8), tracking_path=log_path)
    monkeypatch.setattr(sam_mod, "get_client", lambda s: pytest.fail("report must not call the API"))
    rep = sam_pass.report(tracking_path=log_path, tracker=SamTracker(KEYED, cache_dir=tmp / "c", max_live_calls=0))
    assert rep["subset"]["tracked_ok"] == 7 and list(rep["subset"]["excluded"]) == ["shift/two_stops/40000"]
    assert rep["sam"]["n_cases"] == rep["mock_same_scenes"]["n_cases"] == 7
    assert rep["sam"]["perception"].startswith("sam-3.1") and rep["mock_same_scenes"]["perception"] == "mock (NOT SAM)"
    assert rep["perception_agreement"]["n"] == 7
    json.dumps(rep)


def test_report_refuses_until_every_subset_scene_is_tracked(small, tmp_path):
    log_path = tmp_path / "tracking.json"
    log_path.write_text(json.dumps({"scenes": {}}))
    with pytest.raises(SystemExit, match="not tracked yet"):
        sam_pass.report(tracking_path=log_path)
