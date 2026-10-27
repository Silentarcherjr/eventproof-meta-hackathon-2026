from __future__ import annotations

from fastapi.testclient import TestClient

from eventproof.api.main import app
from tests.conftest import CANONICAL_RULE, lerp, path, trackset

client = TestClient(app)


def test_health_never_leaks_key():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert set(body) == {"status", "meta_api_key_configured", "muse_model", "sam_model"}


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
