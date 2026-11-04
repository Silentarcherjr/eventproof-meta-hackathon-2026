from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from eventproof.api import main as api
from eventproof.challenge import lab
from eventproof.challenge.render import sha256_file
from eventproof.challenge.traffic import traffic_rule
from eventproof.meta.client import LiveBudget
from eventproof.meta.muse_rules import CompiledRule, MuseRuleCompiler


@pytest.fixture
def client():
    return TestClient(api.app)


@pytest.mark.parametrize("family", lab.FAMILIES)
def test_all_showcase_cars_judge_and_contract_choices_match_truth(client, family):
    response = client.get(f"/lab/{family}/0/judge?max_speed=0.01&any_direction=true")
    assert response.status_code == 200
    result = response.json()
    assert result["source"] == "synthetic" and result["cars"]
    for car in result["cars"]:
        assert car["your"]["verdict"] == car["truth"]["intended"]
        assert car["your"]["events"] and car["spark"]["events"]
    video = client.get(f"/lab/{family}/0/video")
    assert video.status_code == 200 and video.headers["content-type"] == "video/mp4"
    assert b"ftyp" in video.content[:40]


@pytest.mark.parametrize(("family", "choice"), [("rolling_stop", "standing-still speed"),
                                               ("wrong_way", "crossing direction")])
def test_spark_defaults_and_controls_explain_flip(client, family, choice):
    baseline = client.get(f"/lab/{family}/0/judge").json()
    assert baseline["controls"] == {"max_speed": 0.05, "any_direction": False}
    assert baseline["cars"][0]["spark"]["verdict"] == baseline["cars"][0]["your"]["verdict"] == "PASS"
    assert baseline["cars"][0]["truth"]["intended"] == "VIOLATION"
    fixed = client.get(f"/lab/{family}/0/judge?max_speed=0.01&any_direction=true").json()
    assert choice in fixed["explanation"] and "Car 0: PASS → VIOLATION" in fixed["explanation"]


def test_summary_from_report_and_real_minimal_pair(client):
    scenes = client.get("/lab/scenes").json()
    report = lab.report()
    assert scenes["summary"]["scenes"] == report["scenes"]
    assert scenes["summary"]["correct"] == report["summary"]["muse_spark"]["total"]["correct"]
    assert scenes["summary"]["disagreements"] == report["summary"]["muse_spark"]["total"]["spec_error"]
    assert scenes["summary"]["two_choices_explain_all"]
    assert {s["family"] for s in scenes["scenes"]} == set(lab.FAMILIES)
    assert all(s["seed"] == 0 for s in scenes["scenes"])
    pair = client.get("/lab/pair").json()
    assert pair["motion_frame_difference"] == 1
    assert pair["sides"]["fail"]["cars"][0]["naive"]["verdict"] == "PASS"
    assert pair["sides"]["pass"]["cars"][0]["naive"]["verdict"] == "VIOLATION"
    for side in pair["sides"].values():
        assert side["cars"][0]["truth"]["intended"] == "VIOLATION"
        assert client.get(side["video_url"]).status_code == 200


@pytest.mark.parametrize("path", [
    "/lab/fake/0/judge", "/lab/full_stop/1/judge", "/lab/full_stop/100000/judge",
    "/lab/fake/0/video", "/lab/queue/1/video", "/lab/pair/unknown/video",
])
def test_unknown_scene_is_404(client, path):
    assert client.get(path).status_code == 404


@pytest.mark.parametrize("query", [
    "max_speed=0", "max_speed=0.0049", "max_speed=0.1001", "max_speed=nan", "max_speed=inf",
    "max_speed=-0.01", "max_speed=garbage", "max_speed=None", "any_direction=yes", "any_direction=1",
])
def test_strict_control_validation(client, query):
    assert client.get(f"/lab/full_stop/0/judge?{query}").status_code == 422


def test_any_motion_and_endpoints(client):
    for speed in ("none", "0.005", "0.10"):
        assert client.get(f"/lab/rolling_stop/0/judge?max_speed={speed}&any_direction=false").status_code == 200


def test_prefilled_compile_replays_at_zero_cost(client, monkeypatch):
    def no_call(*args, **kwargs):
        pytest.fail("recorded compile must not make a model call")

    monkeypatch.setattr(MuseRuleCompiler, "_call", no_call)
    before = api.MUSE_BUDGET.used
    response = client.post("/lab/compile", json={"rule_text": lab.report()["rule_text"]})
    assert response.status_code == 200
    result = response.json()
    assert result["cached"] and result["provenance"] == "recorded response"
    assert result["request_ids"] == lab.report()["request_ids"]
    assert result["assumptions"] == lab.report()["assumptions"]
    assert result["wrong_scenes"] == ["rolling_stop", "wrong_way"]
    assert len(result["scenes"]) == len(lab.FAMILIES) and api.MUSE_BUDGET.used == before


def test_new_wording_uses_shared_compiler_and_traffic_layout(client, monkeypatch):
    captured = []

    class FakeCompiler:
        def compile(self, text, layout):
            captured.append((text, layout))
            return CompiledRule(rule=traffic_rule(lab.scene("full_stop", 0)), assumptions=["fake compiler for test"],
                                model="test-fake", request_ids=["fake-test-only"], attempts=1,
                                cached=False, usage=[], raw_output={})

    monkeypatch.setattr(api, "get_compiler", lambda: FakeCompiler())
    result = client.post("/lab/compile", json={"rule_text": "Cars must stop before the stop line."})
    assert result.status_code == 200
    assert captured[0][0] == "Cars must stop before the stop line."
    assert captured[0][1].zones[0].zone.id == "waiting"
    assert captured[0][1].lines[0].line.id == "stop_line"
    assert "left to right" in captured[0][1].lines[0].description
    assert result.json()["provenance"] == "compiled live by Muse Spark"  # fake compiler; no live test call
    assert result.json()["wrong_scenes"] == []


def test_zero_budget_blocks_new_wording_before_paid_request(client, monkeypatch, tmp_path):
    from eventproof.meta import muse_rules

    def no_paid(*args, **kwargs):
        pytest.fail("shared budget must block the paid request")

    budget = LiveBudget("muse-spark", 0)
    compiler = MuseRuleCompiler(cache_dir=tmp_path, budget=budget, anchor_field=True)
    monkeypatch.setattr(api, "MODE", "hosted")
    monkeypatch.setattr(api, "_compiler", compiler)
    monkeypatch.setattr(api, "MUSE_BUDGET", budget)
    monkeypatch.setattr(muse_rules, "get_client", lambda *a: SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=no_paid))))
    response = client.post("/lab/compile", json={"rule_text": "Every car must wait exactly seven seconds."})
    assert response.status_code == 503 and budget.used == compiler.live_calls == 0
    assert "allowance" in response.json()["detail"]


def test_rate_limit_and_shared_heavy_guard(client, monkeypatch):
    monkeypatch.setattr(api, "RATE_N", 0)
    assert client.post("/lab/compile", json={"rule_text": lab.report()["rule_text"]}).status_code == 429
    monkeypatch.setattr(api, "RATE_N", 30)
    assert api._heavy.acquire(blocking=False)
    try:
        assert client.post("/lab/compile", json={"rule_text": lab.report()["rule_text"]}).status_code == 429
    finally:
        api._heavy.release()


@pytest.mark.parametrize("body", [{"rule_text": ""}, {"rule_text": "x" * 2001}, {"rule_text": 4},
                                 {"rule_text": "hello", "layout": {}}, {}])
def test_invalid_compile_input(client, body):
    assert client.post("/lab/compile", json=body).status_code == 422


def test_showcase_video_hashes():
    for path in lab.SHOWCASE.glob("*/*/manifest.json"):
        manifest = json.loads(path.read_text())
        assert sha256_file(path.parent / "video.mp4") == manifest["mp4_sha256"]
    assert len(list(lab.SHOWCASE.glob("*/*/video.mp4"))) == len(lab.FAMILIES) + 2


def test_api_import_closure_cannot_reach_evaluation_tooling():
    from tests.repair.test_repair import _eventproof_imports

    assert not any(m.startswith("eventproof.validation") for m in _eventproof_imports("eventproof.api.main"))


def test_custom_rule_does_not_silently_relabel_cars_as_another_concept(client, monkeypatch):
    rule = traffic_rule(lab.scene("full_stop", 0))
    rule.entity.concept = "pedestrian"
    fake = SimpleNamespace(compile=lambda *a: CompiledRule(
        rule=rule, assumptions=["fake test only"], model="test-fake", request_ids=[], attempts=1,
        cached=True, usage=[], raw_output={}))
    monkeypatch.setattr(api, "get_compiler", lambda: fake)
    result = client.post("/lab/compile", json={"rule_text": "Every pedestrian must stop."})
    assert result.status_code == 200
    assert all(c["your"] is None and "pedestrian" in c["why"] for s in result.json()["scenes"] for c in s["cars"])
