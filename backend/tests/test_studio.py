from __future__ import annotations

import copy
import json

import pytest
from fastapi.testclient import TestClient

from eventproof import pipeline, studio
from eventproof.api import main as api
from eventproof.challenge.families import FAMILIES
from eventproof.challenge.holdout import load_frozen
from eventproof.challenge.render import encode_mp4, ground_truth
from eventproof.meta import muse_repair as mrep
from eventproof.meta import muse_rules as mr
from eventproof.meta.muse_rules import MuseRuleCompiler
from eventproof.perception import sam as sam_mod
from eventproof.perception.sam import SamTracker
from tests.perception.test_sam import FakeClient, encode_wire
from tests.repair.test_repair import _eventproof_imports
from tests.test_muse_rules import GOOD, LAYOUT, FakeMuse
from tests.test_pipeline import RULE, SETTINGS


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    """A completed run (fake Muse + fake SAM) whose compiled rule is the canonical DWELL >= 1.5 s rule."""
    tmp = tmp_path_factory.mktemp("studio")
    scene = FAMILIES["canonical"](3)
    clip = tmp / "clip.mp4"
    encode_mp4(scene, clip)
    mp = pytest.MonkeyPatch()
    mp.setattr(mr, "get_client", lambda s: FakeMuse([GOOD]))
    mp.setattr(sam_mod, "get_client", lambda s: FakeClient(encode_wire(ground_truth(scene))))
    ev = pipeline.run(clip, RULE, LAYOUT, MuseRuleCompiler(SETTINGS, cache_dir=tmp / "mc"),
                      SamTracker(SETTINGS, cache_dir=tmp / "sc", max_live_calls=1), runs_dir=tmp / "runs")
    mp.undo()
    rep = studio.challenge(ev, runs_dir=tmp / "runs")
    yield ev, rep, tmp / "runs"


def test_challenge_finds_the_clearest_spec_error(run):
    ev, rep, runs = run
    assert rep.perception.startswith("mock") and rep.suite_cases == 150 and rep.failures > 0
    cx = rep.counterexample
    got = (cx["family"], cx["outcome"], cx["detector_verdict"], cx["intended"])
    assert got == ("drive_through", "spec_error", "PASS", "FAIL")
    assert cx["truths"][0]["station_stop_ms"] == 0  # the box never stopped
    assert cx["t_pass"] - cx["t_fail"] < 0.01 and cx["pass_verdict"] == "FAIL"
    d = runs / ev.run_id / "challenge"
    assert all((d / f).exists() for f in rep.files) and "side_by_side.mp4" in rep.files


def test_rule_outside_the_synthetic_world_is_refused(run, tmp_path):
    ev, _, _ = run
    bad = ev.model_copy(deep=True)
    bad.rule.compiled_rule = json.loads(json.dumps(bad.rule.compiled_rule).replace('"inspection"', '"dock"'))
    with pytest.raises(studio.ChallengeUnavailable, match="synthetic world"):
        studio.challenge(bad, runs_dir=tmp_path)


def test_baseline_repair_on_the_compiled_rule(run):
    ev, _, runs = run
    out = studio.repair(ev, "baseline", runs_dir=runs)
    assert [d.accepted for d in out.decisions] == [False, True]
    assert out.decisions[1].holdout_after.correct > out.decisions[1].holdout_before.correct


def _muse_out(*patches):
    return {"diagnosis": "spec_error: transit time counts as dwell",
            "proposals": [{"ops": ops, "rationale": "r", "expected_effect": "e", "confidence": 0.6} for ops in patches]}


STILL = [{"op": "set_dwell_max_speed", "zone": "inspection", "max_speed": 0.05},
         {"op": "set_dwell_min_ms", "zone": "inspection", "value": 700}]
TOO_STRICT = [{"op": "set_dwell_max_speed", "zone": "inspection", "max_speed": 0.05}]


def test_muse_repair_revises_with_visible_feedback_only(run, monkeypatch, tmp_path):
    ev, _, runs = run
    fake = FakeMuse([_muse_out(TOO_STRICT, [{"op": "set_max_gap_frames", "value": 999}]), _muse_out(STILL)])
    monkeypatch.setattr(mrep, "get_client", lambda s: fake)
    out = studio.repair(ev, "muse", runs_dir=runs, muse_settings=SETTINGS, muse_cache=tmp_path / "muse")
    rounds = out.trace["rounds"]
    assert len(rounds) == 2 and rounds[0]["invalid_proposals"][0]["ops"] == [{"op": "set_max_gap_frames", "value": 999}]
    feedback = fake.calls[1]["messages"][-1]["content"]
    assert "dev regressions" in feedback and "stood still" in feedback
    manifest, _ = load_frozen()
    sent = json.dumps([c["messages"] for c in fake.calls])
    assert not any(c.scene_sha256 in sent for c in manifest.cases), "holdout never reaches Muse"
    assert not any(str(s) in sent for s in range(20_000, 20_040))
    by = {d.patch_description: d for d in out.decisions}
    assert len(by) == 2 and out.proposer == "muse-spark-1.3"
    strict = next(d for k, d in by.items() if "0.70" not in k)
    good = next(d for k, d in by.items() if "0.70" in k)
    assert not strict.accepted and strict.regressions
    assert good.accepted and good.proposal.expected_effect["dev_screen"]["dev_regressions"] == 0


def test_muse_repair_module_cannot_reach_the_holdout():
    reach = _eventproof_imports("eventproof.meta.muse_repair")
    assert "eventproof.challenge.holdout" not in reach and "eventproof.repair.grader" not in reach


def test_sam_confirm(run, monkeypatch, tmp_path):
    ev, _, runs = run
    cx = studio.load_counterexample(ev.run_id, runs)
    fake = FakeClient(encode_wire(ground_truth(cx.pair.fail_scene)))  # a perfect "SAM"
    monkeypatch.setattr(sam_mod, "get_client", lambda s: fake)
    monkeypatch.setattr(sam_mod, "CACHE_DIR", tmp_path)
    res = studio.confirm_with_sam(ev, SamTracker(SETTINGS, cache_dir=tmp_path / "c", max_live_calls=1), runs_dir=runs)
    assert res["still_fails_with_sam"] and res["sam"]["perception_source"] == "sam-3.1" and res["live_sam_calls"] == 1


def test_api_endpoints(run, monkeypatch):
    ev, _, runs = run
    monkeypatch.setattr(pipeline, "RUNS_DIR", runs)
    monkeypatch.setattr(studio, "RUNS_DIR", runs)
    c = TestClient(api.app)
    r = c.post(f"/runs/{ev.run_id}/challenge")
    assert r.status_code == 200 and r.json()["counterexample"]["family"] == "drive_through"
    assert c.get(f"/runs/{ev.run_id}/challenge/files/side_by_side.mp4").status_code == 200
    png = r.json()["files"][-1]
    assert c.get(f"/runs/{ev.run_id}/challenge/files/{png}").headers["content-type"] == "image/png"
    assert c.get(f"/runs/{ev.run_id}/challenge/files/counterexample.json").status_code == 400
    assert c.get(f"/runs/{ev.run_id}/challenge/files/..%2Fevidence.json").status_code in (400, 404)
    assert c.post(f"/runs/{ev.run_id}/repair", json={"proposer": "gpt"}).status_code == 422
    rb = c.post(f"/runs/{ev.run_id}/repair", json={"proposer": "baseline"})
    assert rb.status_code == 200 and any(d["accepted"] for d in rb.json()["decisions"])


def test_repair_before_challenge_is_refused(run, tmp_path):
    ev, _, _ = run
    other = copy.deepcopy(ev)
    with pytest.raises(studio.ChallengeUnavailable, match="Challenge Mode first"):
        studio.repair(other, "baseline", runs_dir=tmp_path)


def test_before_after_uses_first_accepted_and_engine_counter(run):
    ev, _, runs = run
    studio.repair(ev, "baseline", runs_dir=runs)
    out = studio.before_after(ev, "baseline", runs_dir=runs)
    assert out["accepted"] == 1 and out["decision"]["proposal_id"] == "baseline-deterministic-1"
    b, a = out["before"], out["after"]
    assert (b["verdict"], b["correct"], a["verdict"], a["correct"]) == ("PASS", False, "FAIL", True)
    assert "moving or not" in b["plain"] and "stands still" in a["plain"]
    # the chart series is the evaluator's own counter: the old rule reached its threshold, the new one never did
    assert max(x["counted_ms"] for s in b["series"].values() for x in s) >= b["threshold_ms"]
    assert max(x["counted_ms"] for s in a["series"].values() for x in s) < a["threshold_ms"]
    assert (runs / ev.run_id / "challenge" / "counterexample.mp4").exists()
    assert studio.stored(ev.run_id, "before-after-baseline", runs)["after"]["verdict"] == "FAIL"


def test_stored_and_final_report_endpoints(run, monkeypatch):
    ev, _, runs = run
    monkeypatch.setattr(pipeline, "RUNS_DIR", runs)
    monkeypatch.setattr(studio, "RUNS_DIR", runs)
    c = TestClient(api.app)
    assert c.get(f"/runs/{ev.run_id}/stored/challenge").json()["counterexample"]["family"] == "drive_through"
    assert c.get(f"/runs/{ev.run_id}/stored/nope").status_code == 400
    assert c.get(f"/runs/{ev.run_id}/stored/sam-confirm").status_code in (200, 404)
    assert c.post(f"/runs/{ev.run_id}/before-after", json={"proposer": "x"}).status_code == 422
    r = c.get("/final-report")
    assert r.status_code == 200 and r.json()["final_set"] == "final_v1"


def test_new_rule_on_the_same_video_is_a_new_run(run, monkeypatch, tmp_path):
    ev, _, runs = run
    monkeypatch.setattr(pipeline, "RUNS_DIR", runs)
    monkeypatch.setattr(mr, "get_client", lambda s: FakeMuse([GOOD]))
    monkeypatch.setattr(api, "_compiler", MuseRuleCompiler(SETTINGS, cache_dir=tmp_path / "mc"))
    scene = FAMILIES["canonical"](3)
    monkeypatch.setattr(sam_mod, "get_client", lambda s: FakeClient(encode_wire(ground_truth(scene))))
    monkeypatch.setattr(api, "_tracker", SamTracker(SETTINGS, cache_dir=tmp_path / "sc", max_live_calls=1))
    c = TestClient(api.app)
    text = "Every blue box must stand still for 2 seconds at inspection before packing."
    r = c.post(f"/runs/{ev.run_id}/rule", json={"rule_text": text})
    assert r.status_code == 200
    new = r.json()
    assert new["run_id"] != ev.run_id and new["rule"]["text"] == text and new["video"]["sha256"] == ev.video.sha256
    assert new["rule"]["layout"] == ev.rule.layout.model_dump(mode="json")
    assert c.post(f"/runs/{ev.run_id}/rule", json={"rule_text": "x"}).status_code == 422
