"""Label review: drafts, Muse proposals and the save guard."""

from __future__ import annotations

from fastapi.testclient import TestClient

from eventproof.api.main import app


def test_label_set_lists_drafts_and_proposals():
    body = TestClient(app).get("/label/fresh_v1").json()
    assert len(body["clips"]) == 6 and all(c["proposal"] is not None for c in body["clips"])


def test_unknown_set_and_clip():
    c = TestClient(app)
    assert c.get("/label/nope").status_code == 404
    assert c.get("/label/fresh_v1/video/..%2Fx.mp4").status_code == 404
    assert c.post("/label/fresh_v1/nope.mp4", json={"objects": [], "reviewer": "x"}).status_code in (403, 404)
