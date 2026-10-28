from __future__ import annotations

import json
import shutil

from fastapi.testclient import TestClient

from eventproof import ledger, pipeline, studio
from eventproof.api import main as api
from tests.test_studio import run  # noqa: F401  module fixture: a completed run with Challenge results


def test_ledger_lists_every_file_and_verifies(run):  # noqa: F811
    ev, _, runs = run
    studio.repair(ev, "baseline", runs_dir=runs)
    led = ledger.write(ev.run_id, runs)
    d = runs / ev.run_id
    assert {"evidence.json", "video.mp4", "tracks.json", "rule.json", "challenge/challenge.json",
            "challenge/repair_baseline.json", "challenge/counterexample.mp4"} <= set(led["files"])
    assert led["evidence_seal_valid"] and led["verdict"] == ev.result.overall
    assert led["repairs"]["baseline"]["holdout"][0][0] == "holdout_v2"
    assert [m["stage"] for m in led["models"]][:2] == ["rule", "perception"]
    assert ledger.verify(d) == []


def test_ledger_detects_tampering(run, tmp_path):  # noqa: F811
    ev, _, runs = run
    led = ledger.write(ev.run_id, runs)
    d = tmp_path / ev.run_id  # tamper with a copy; the run fixture is shared
    shutil.copytree(runs / ev.run_id, d)
    (d / "challenge" / "challenge.json").write_text("{}")
    assert ledger.verify(d) == ["changed: challenge/challenge.json"]
    forged = dict(led, verdict="PASS")
    assert "ledger_sha256 does not match its content" in ledger.verify(d, forged)
    raw = json.loads((d / "evidence.json").read_text())
    raw["result"]["overall"] = "PASS"
    (d / "evidence.json").write_text(json.dumps(raw))
    assert "evidence.json seal is broken" in ledger.verify(d)


def test_ledger_endpoint(run, monkeypatch):  # noqa: F811
    ev, _, runs = run
    monkeypatch.setattr(pipeline, "RUNS_DIR", runs)
    monkeypatch.setattr(ledger, "RUNS_DIR", runs)
    c = TestClient(api.app)
    assert c.get(f"/runs/{ev.run_id}/ledger").json()["run_id"] == ev.run_id
    assert c.get("/runs/../ledger").status_code in (400, 404)
