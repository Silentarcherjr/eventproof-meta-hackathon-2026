"""Credit and abuse guards of the API: live-call budgets, showcase mode, rate limit, one heavy job at a time."""

from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient

from eventproof.api import main as api
from eventproof.meta import muse_rules as mr
from eventproof.meta.client import LiveBudget, LiveCallLimit
from eventproof.meta.muse_rules import MuseRuleCompiler
from tests.test_muse_rules import GOOD, LAYOUT, FakeMuse
from tests.test_pipeline import SETTINGS


def test_budget_is_shared_and_thread_safe():
    b = LiveBudget("x", 5)
    errors = []

    def worker():
        try:
            b.take()
        except LiveCallLimit as e:
            errors.append(e)

    ts = [threading.Thread(target=worker) for _ in range(12)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert b.used == 5 and b.remaining == 0 and len(errors) == 7


def test_compiler_stops_before_a_call_beyond_the_budget(monkeypatch, tmp_path):
    fake = FakeMuse([GOOD, GOOD])
    monkeypatch.setattr(mr, "get_client", lambda s: fake)
    comp = MuseRuleCompiler(SETTINGS, cache_dir=tmp_path, budget=LiveBudget("muse", 1))
    comp.compile("Every blue box must stay 1.5 s in inspection before packing.", LAYOUT)
    with pytest.raises(LiveCallLimit):
        comp.compile("A different rule text, so not cached.", LAYOUT)
    assert len(fake.calls) == 1, "the refused compile never reached the client"
    # cached results are free
    comp.compile("Every blue box must stay 1.5 s in inspection before packing.", LAYOUT)


def test_showcase_mode_refuses_uploads(monkeypatch):
    monkeypatch.setattr(api, "MODE", "showcase")
    r = TestClient(api.app).post("/runs", data={"rule_text": "abc", "layout": "{}"},
                                 files={"video": ("a.mp4", b"x", "video/mp4")})
    assert r.status_code == 403 and "showcase" in r.json()["detail"]


def test_rate_limit_per_client(monkeypatch):
    monkeypatch.setattr(api, "RATE_N", 2)
    monkeypatch.setattr(api, "_hits", {})
    c = TestClient(api.app)
    codes = [c.post("/runs/bad-id/challenge").status_code for _ in range(3)]
    assert codes[:2] == [400, 400] and codes[2] == 429


def test_one_heavy_job_at_a_time(monkeypatch):
    monkeypatch.setattr(api, "_hits", {})
    assert api._heavy.acquire(blocking=False)
    try:
        r = TestClient(api.app).post("/runs/20261028T023754Z-a922b5bb/challenge")
        assert r.status_code == 429 and "another job" in r.json()["detail"]
    finally:
        api._heavy.release()
