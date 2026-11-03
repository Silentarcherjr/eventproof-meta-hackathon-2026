from __future__ import annotations

from fastapi.testclient import TestClient

from eventproof.api.main import app
from tests.conftest import CANONICAL_RULE, lerp, path, trackset

client = TestClient(app)


def test_health_never_leaks_key():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert set(body) == {"status", "mode", "meta_api_key_configured", "muse_model", "sam_model", "live_calls_remaining",
                         "rate_limit", "demo_runs", "demo_clips"}
    assert "sk-" not in str(body) and body["live_calls_remaining"] == {"muse": 0, "sam": 0}


def test_evaluate_endpoint_returns_violation():
    tracks = trackset(path(lerp(0.1, 0.9, 10)))
    r = client.post("/evaluate", json={"rule": CANONICAL_RULE, "tracks": tracks.model_dump(mode="json")})
    assert r.status_code == 200
    assert r.json()["overall"] == "FAIL"


def test_evaluate_rejects_unknown_operator():
    bad = {**CANONICAL_RULE, "check": {"op": "EVAL", "code": "1"}}
    tracks = trackset(path([0.1, 0.2]))
    r = client.post("/evaluate", json={"rule": bad, "tracks": tracks.model_dump(mode="json")})
    assert r.status_code == 422


def test_routes_also_served_under_the_path_prefix(monkeypatch):
    import eventproof.api.main as m
    monkeypatch.setattr(m, "PATH_PREFIX", "/api")
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/health").json()["status"] == "ok"
    tracks = trackset(path(lerp(0.1, 0.9, 10)))
    r = client.post("/api/evaluate", json={"rule": CANONICAL_RULE, "tracks": tracks.model_dump(mode="json")})
    assert r.status_code == 200 and r.json()["overall"] == "FAIL"


def test_demo_clips_list_only_runs_that_exist(monkeypatch, tmp_path):
    import json

    import eventproof.api.main as m
    run = tmp_path / "20261102T000000Z-aaaaaaaa"
    run.mkdir()
    (run / "evidence.json").write_text(json.dumps({"video": {"filename": "clip.mp4"}, "rule": {"text": "a rule"},
                                                   "result": {"overall": "FAIL"}}))
    monkeypatch.setattr(m.pipeline, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(m, "DEMO_RUNS", [run.name, "20261102T000000Z-bbbbbbbb"])
    assert m._demo_clips() == [{"run_id": run.name, "clip": "clip.mp4", "rule": "a rule", "overall": "FAIL"}]
