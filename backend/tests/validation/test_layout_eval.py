from __future__ import annotations

import json

import pytest

from eventproof.meta import layout_proposer as lp
from eventproof.meta.client import LiveCallLimit
from eventproof.validation import layout_eval as le


def test_geometry_helpers():
    sq = [(0, 0), (1, 0), (1, 1), (0, 1)]
    assert lp.polygon_iou(sq, sq) == pytest.approx(1.0)
    assert lp.polygon_iou(sq, [(0, 0), (0.5, 0), (0.5, 1), (0, 1)]) == pytest.approx(0.5, abs=0.01)
    assert lp.line_agreement(((0, 0), (1, 0)), ((0, 0), (0, 1)))["angle_deg"] == 90.0


def test_model_output_is_validated_not_trusted():
    good = {"zone_polygon": [[0, 0.5], [1.2, 0.5], [1, 1], [0, 1]], "zone_description": "z", "line_a": [0, 0.5],
            "line_b": [1, 0.5], "line_description": "l", "travel_direction": "down", "assumptions": []}
    layout = lp.to_layout(good)
    assert layout.zones[0].zone.polygon[1] == (1.0, 0.5)  # clipped into the frame
    with pytest.raises(lp.RuleCompileError):
        lp.to_layout(good | {"zone_polygon": [[0, 0], [1, 1]]})


def test_uncached_proposal_needs_an_allowance(tmp_path):
    with pytest.raises(LiveCallLimit):
        lp.LayoutProposer(cache_dir=tmp_path, max_live_calls=0).propose(b"png", "rule")


def test_committed_report_recomputes_from_cached_proposals(monkeypatch):
    monkeypatch.setattr(lp, "get_client", lambda s: pytest.fail("no API calls"))
    committed = json.loads((le.OUT_DIR / "report.json").read_text())
    frames = {}
    for folder, _ in le.SETS:  # first frames: from the local videos when present, else skip (videos are not committed)
        for v in (le.ROOT / folder / "videos").glob("*.mp4"):
            frames[v.name] = lp.first_frame_png(v)
    if len(frames) < len(committed["clips"]):
        pytest.skip("real-footage videos are not in this checkout")
    rep = le.run(0, frames=frames)
    for k in ("code_commit", "live_calls_this_run"):
        committed.pop(k, None)
        rep.pop(k, None)
    assert json.loads(json.dumps(rep)) == committed


def test_committed_scores_recompute_from_the_recorded_proposals():
    """Without videos (CI): re-score every clip from the proposal recorded in the report and the committed tracks."""
    from eventproof.meta.muse_rules import Layout
    from eventproof.schemas.rules import VisualRule
    from eventproof.schemas.tracks import TrackSet
    from eventproof.validation.real_video import load_labels

    rep = json.loads((le.OUT_DIR / "report.json").read_text())
    for folder, rep_name in le.SETS:
        d = le.ROOT / folder
        labels = {lb.clip: lb for _, lb in load_labels(d / "labels")}
        for c in json.loads((d / rep_name).read_text())["clips"]:
            row = next(x for x in rep["clips"] if x["clip"] == c["clip"])
            run = d / "runs" / c["run_id"]
            rule = VisualRule.model_validate(json.loads((run / "evidence.json").read_text())["rule"]["compiled_rule"])
            tracks = TrackSet.model_validate_json((run / "tracks.json").read_text())
            lab = labels[c["clip"]]
            assert le.score(lab, rule, tracks) == row["hand"]
            assert le.score(lab, le.with_geometry(rule, Layout.model_validate(row["proposed"])), tracks) == row["proposed_layout"]
    assert rep["right"] == {"hand": 27, "proposed_layout": 20}


def test_propose_layout_endpoint_uses_the_cache_and_the_allowance(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from eventproof.api import main as api

    out = {"zone_polygon": [[0.1, 0.5], [0.9, 0.5], [0.9, 0.9], [0.1, 0.9]], "zone_description": "waiting area",
           "line_a": [0.1, 0.5], "line_b": [0.9, 0.5], "line_description": "stop line", "travel_direction": "upwards",
           "assumptions": ["a"]}

    class Fake:
        def __init__(self):
            self.chat = type("C", (), {"completions": type("X", (), {"create": staticmethod(self.create)})()})()
            self.calls = 0

        def create(self, **kw):
            self.calls += 1
            msg = type("M", (), {"content": json.dumps(out)})()
            return type("R", (), {"id": "chatcmpl-x", "usage": None, "choices": [type("Ch", (), {"message": msg})()]})()

    fake = Fake()
    monkeypatch.setattr(lp, "get_client", lambda s: fake)
    monkeypatch.setattr(lp, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(lp.LayoutProposer.__init__, "__defaults__", (None, tmp_path, None, None))
    monkeypatch.setattr(api.MUSE_BUDGET, "limit", 1)
    monkeypatch.setattr(api.MUSE_BUDGET, "used", 0)
    from eventproof.challenge.families import FAMILIES
    from eventproof.challenge.render import encode_mp4

    clip = tmp_path / "c.mp4"
    encode_mp4(FAMILIES["canonical"](1), clip)
    c = TestClient(api.app)
    files = {"video": ("c.mp4", clip.read_bytes(), "video/mp4")}
    r = c.post("/propose-layout", files=files, data={"rule_text": "Every car must stop."})
    assert r.status_code == 200 and r.json()["layout"]["lines"][0]["line"]["id"] == "packing_entry" and fake.calls == 1
    r2 = c.post("/propose-layout", files=files, data={"rule_text": "Every car must stop."})
    assert r2.json()["cached"] is True and fake.calls == 1  # same frame + text: no new call, no allowance used
    r3 = c.post("/propose-layout", files=files, data={"rule_text": "Another rule entirely."})
    assert r3.status_code == 503  # allowance used up
