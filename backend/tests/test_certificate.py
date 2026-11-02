from __future__ import annotations

from fastapi.testclient import TestClient

from eventproof import certificate, pipeline, studio
from eventproof.api import main as api

ROOT = certificate.ROOT
DEMO = ("20261028T023754Z-a922b5bb", ROOT / "docs" / "evidence" / "runs")
NOVI_SAD = ("20261102T040830Z-37064c4a", ROOT / "benchmark" / "real" / "novisad" / "runs")


def test_synthetic_run_repair_is_conditional_until_a_field_check():
    c = certificate.build(*DEMO[:1], runs_dir=DEMO[1])
    assert c["status"]["label"] == "REPAIR CONDITIONAL"
    assert c["challenge"]["failures"] == 44 and c["challenge"]["scenes"] == 150
    f = c["repair"]["first_accepted"]
    assert (f["before"]["correct"], f["after"]["correct"], f["regressions"]) == (144, 164, 0)
    assert c["final_test"]["in_distribution"]["after"] == 158 and c["field"] == []
    html = certificate.render_html(c)
    assert "REPAIR CONDITIONAL" in html and "144/200 → 164/200" in html


def test_real_traffic_rule_is_certified_for_checked_scenes_and_the_repair_is_flagged():
    c = certificate.build(*NOVI_SAD[:1], runs_dir=NOVI_SAD[1])
    assert c["status"]["label"] == "CERTIFIED FOR CHECKED SCENES"
    assert len(c["field"]) == 4 and sum(x["labelled"] for x in c["field"]) == 24
    assert sum(x["rule"]["right"] for x in c["field"]) == 22 and sum(x["repair"]["right"] for x in c["field"]) == 13
    assert any("do not deploy it" in r for r in c["status"]["reasons"])


def test_certificate_endpoint(monkeypatch):
    monkeypatch.setattr(pipeline, "RUNS_DIR", NOVI_SAD[1])
    monkeypatch.setattr(studio, "RUNS_DIR", NOVI_SAD[1])
    monkeypatch.setattr(certificate, "RUNS_DIR", NOVI_SAD[1])
    client = TestClient(api.app)
    r = client.get(f"/runs/{NOVI_SAD[0]}/certificate")
    assert r.status_code == 200 and "Rule certificate" in r.text and "CERTIFIED FOR CHECKED SCENES" in r.text
    assert client.get(f"/runs/{NOVI_SAD[0]}/certificate?format=json").json()["status"]["label"].startswith("CERTIFIED")
    assert client.get("/runs/not-a-run/certificate").status_code in (400, 404)
