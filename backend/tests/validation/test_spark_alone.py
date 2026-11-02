from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from eventproof.meta.client import LiveCallLimit, MetaSettings
from eventproof.validation import spark_alone as sa
from eventproof.validation.real_video import load_labels

KEYED = MetaSettings(api_key="test-key-not-real", base_url="https://example.invalid/v1", muse_model="muse-spark-1.3",
                     sam_model="sam-3.1", budget_usd=1)
LABELS = sa.ROOT / "benchmark" / "real" / "novisad" / "labels"
ANSWER = {"crossings": [{"description": "red car", "approx_cross_time_s": 4.0, "waited_s": 0.0, "verdict": "VIOLATION"}],
          "overall": "FAIL", "notes": ""}


class FakeClient:
    def __init__(self):
        self.calls = []
        self.files = SimpleNamespace(create=lambda file, purpose: SimpleNamespace(id="file-x"))
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(id=f"resp-{len(self.calls)}", output_text=json.dumps(ANSWER), usage=None)


def test_request_shape_cache_and_allowance(tmp_path, monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(sa, "get_client", lambda s: fake)
    video = tmp_path / "v.mp4"
    video.write_bytes(b"not a video")
    j = sa.SparkAlone(KEYED, cache_dir=tmp_path / "c", max_live_calls=1)
    rec = j.judge(video, "rule text", 0)
    assert rec["parsed"] == ANSWER and not rec["cached"] and j.live_calls == 1
    content = fake.calls[0]["input"][0]["content"]
    assert content[1] == {"type": "input_video", "file_id": "file-x"}
    assert fake.calls[0]["text"]["format"]["strict"] is True
    assert j.judge(video, "rule text", 0)["cached"] and len(fake.calls) == 1
    with pytest.raises(LiveCallLimit):
        j.judge(video, "rule text", 1)
    assert "test-key-not-real" not in next((tmp_path / "c").glob("*.json")).read_text()


def test_prompt_is_neutral_and_score_counts():
    (_, label_a), _ = load_labels(LABELS)
    text = sa.prompt(label_a, 19.0, 10, (270, 390))
    assert label_a.rule_text in text and "still" not in text.lower()
    s = sa.score(label_a, ANSWER)
    assert s == {"valid": True, "overall": "FAIL", "overall_agrees": True, "crossings_reported": 1,
                 "crossings_true": 3, "violations_reported": 1, "violations_true": 2}
    assert sa.score(label_a, None) == {"valid": False}


def test_committed_report_recomputes_from_committed_answers():
    rep = json.loads((sa.DIR / "report.json").read_text())
    labels = {lb.clip: lb for _, lb in load_labels(LABELS)}
    cached = {json.loads(p.read_text())["response_id"]: json.loads(p.read_text()) for p in sa.CACHE.glob("*.json")}
    valid = []
    for c in rep["clips"]:
        for r in c["runs"]:
            assert cached[r["response_id"]]["parsed"] == r["answer"]
            s = sa.score(labels[c["clip"]], r["answer"])
            assert {k: r[k] for k in s} == s
            valid.append(s)
    summ = rep["summary"]
    assert summ["valid"] == len(valid) == 10
    assert summ["overall_agree"] == sum(s["overall_agrees"] for s in valid) == 10
    assert summ["counts_exact"] == sum(s["violations_reported"] == s["violations_true"]
                                       and s["crossings_reported"] == s["crossings_true"] for s in valid) == 5
