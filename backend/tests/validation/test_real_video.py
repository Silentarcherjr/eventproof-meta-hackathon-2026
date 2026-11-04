from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from eventproof.challenge.render import encode_mp4, ground_truth
from eventproof.challenge.scene import INSPECTION, LANES, PACKING_LINE, SceneObject, SceneSpec, conveyor_path
from eventproof.challenge.truth import intended_overall, scene_truth
from eventproof.meta import muse_rules as mr
from eventproof.meta.muse_rules import Layout, LayoutLine, LayoutZone
from eventproof.perception import sam as sam_mod
from eventproof.perception.sam import LiveCallLimit, SamTracker
from eventproof.repair.patch import RulePatch, SetDwell
from eventproof.validation import real_video as rv
from eventproof.validation.real_video import ClipLabel, LabeledObject, LimitedMuseCompiler, Perceived, RealVideoError
from tests.perception.test_sam import FakeClient, encode_wire
from tests.test_muse_rules import GOOD, LAYOUT, FakeMuse
from tests.test_pipeline import RULE, SETTINGS

TEMPLATE = Path(__file__).resolve().parents[3] / "benchmark" / "real" / "labels" / "TEMPLATE.json"


def _scene() -> SceneSpec:
    """Two blue boxes: one stands still 2 s at the station, one drives through (crosses first)."""
    rng = np.random.default_rng(0)
    inspected = SceneObject(object_id=0, color="blue", waypoints=conveyor_path(rng, 0, LANES[0], 30, 45))
    drive = SceneObject(object_id=1, color="blue", waypoints=conveyor_path(rng, 5, LANES[2], 0, 45))
    return SceneSpec(seed=0, n_frames=80, zones=[INSPECTION], lines=[PACKING_LINE], objects=[inspected, drive])


def _labels_from_truth(scene: SceneSpec, clip: str, sha: str, keep: int | None = None, layout: Layout = LAYOUT) -> dict:
    truths = sorted(scene_truth(scene), key=lambda t: (t.crosses_packing_frame is None, t.crosses_packing_frame or 0))
    truths = truths[:keep] if keep else truths
    objects = [{"description": f"blue box {t.object_id}", "crosses_packing": t.crosses_packing_frame is not None,
                "stood_still_s": t.station_stop_ms / 1000, "intended": t.intended} for t in truths]
    return {"clip": clip, "clip_sha256": sha, "layout": layout.model_dump(mode="json"), "rule_text": RULE,
            "objects": objects, "expected_overall": intended_overall(truths), "labeled_by": "tester",
            "labeled_at": "2026-10-29T10:00:00-05:00"}


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    scene = _scene()
    d = tmp_path_factory.mktemp("clip")
    encode_mp4(scene, d / "clip01.mp4")
    return scene, d / "clip01.mp4"


@pytest.fixture
def setup(tmp_path, clip):
    """labels/ + videos/ with one labelled clip; returns a function to (re)write the label."""
    scene, src = clip
    videos, labels = tmp_path / "videos", tmp_path / "labels"
    videos.mkdir()
    labels.mkdir()
    (videos / "clip01.mp4").write_bytes(src.read_bytes())
    sha = rv.sha256_file(videos / "clip01.mp4")

    def write(**kw) -> dict:
        lab = _labels_from_truth(scene, "clip01.mp4", sha, **kw)
        (labels / "clip01.json").write_text(json.dumps(lab, indent=2))
        return lab

    write()
    return scene, labels, videos, write


@pytest.fixture
def fakes(monkeypatch, clip):
    scene, _ = clip
    muse, sam = FakeMuse([GOOD]), FakeClient(encode_wire(ground_truth(scene)))
    monkeypatch.setattr(mr, "get_client", lambda s: muse)
    monkeypatch.setattr(sam_mod, "get_client", lambda s: sam)
    return muse, sam


def _clients(tmp_path, muse_calls: int = 1, sam_calls: int = 1):
    return (LimitedMuseCompiler(SETTINGS, cache_dir=tmp_path / "mc", max_live_calls=muse_calls),
            SamTracker(SETTINGS, cache_dir=tmp_path / "sc", max_live_calls=sam_calls))


def _run(tmp_path, labels, videos, out="report.json", muse_calls=1, sam_calls=1, clients=None):
    comp, trk = clients or _clients(tmp_path, muse_calls, sam_calls)
    return rv.run(labels, videos, tmp_path / out, sam_calls, muse_calls, compiler=comp, tracker=trk,
                  runs_dir=tmp_path / "runs")


# ---- labels -----------------------------------------------------------------------------------------------


def test_template_is_a_valid_label():
    lab = ClipLabel.model_validate_json(TEMPLATE.read_text())
    assert lab.packing_line == "packing_entry" and lab.process_truth_warnings() == []


@pytest.mark.parametrize("mutate,msg", [
    (lambda d: d.update(clip_sha256="abc"), "clip_sha256"),
    (lambda d: d.update(clip="../x/clip01.mp4"), "plain"),
    (lambda d: d.update(clip="clip01.avi"), "plain"),
    (lambda d: d.update(expected_overall="PASS"), "expected_overall must be FAIL"),
    (lambda d: d.update(labeled_at="2026-10-29T10:00:00"), "timezone"),
    (lambda d: d.update(packing_line="exit"), "packing_line"),
    (lambda d: d["objects"].reverse(), "first"),
    (lambda d: d["objects"].append({**d["objects"][0], "crosses_packing": False}), "cannot violate"),
    (lambda d: d["objects"][0].update(colour="blue"), "Extra inputs"),
])
def test_invalid_labels_are_rejected(clip, mutate, msg):
    scene, _ = clip
    d = _labels_from_truth(scene, "clip01.mp4", "0" * 64)
    d["objects"].append({"description": "never enters packing", "crosses_packing": False, "stood_still_s": 0,
                         "intended": "PASS"})
    ClipLabel.model_validate(d)
    mutate(d)
    with pytest.raises(ValidationError, match=msg):
        ClipLabel.model_validate(d)


def test_process_truth_disagreement_is_a_warning(clip):
    scene, _ = clip
    d = _labels_from_truth(scene, "clip01.mp4", "0" * 64)
    d["objects"][0]["intended"], d["expected_overall"] = "PASS", "PASS"  # the drive-through labelled PASS
    warnings = ClipLabel.model_validate(d).process_truth_warnings()
    assert len(warnings) == 1 and "implies VIOLATION" in warnings[0]


def test_check_and_freeze(setup):
    _, labels, videos, _ = setup
    (rows,) = rv.check(labels, videos)
    assert rows["clip"] == "clip01.mp4" and rows["reencode"] == [] and rows["warnings"] == []
    m = rv.freeze(labels, [rows])
    assert json.loads(m.read_text())["labels"] == {"clip01.json": rows["label_sha256"]}
    with pytest.raises(RealVideoError, match="already frozen"):
        rv.freeze(labels, [rows])
    assert rv.main(["check", str(labels), "--videos", str(videos)]) == 0


def test_check_refuses_a_clip_changed_after_labelling(setup):
    _, labels, videos, _ = setup
    v = videos / "clip01.mp4"
    v.write_bytes(v.read_bytes() + b"\0")
    with pytest.raises(RealVideoError, match="changed after labelling"):
        rv.check(labels, videos)
    assert rv.main(["check", str(labels), "--videos", str(videos)]) == 2


def test_run_requires_frozen_unchanged_labels(tmp_path, setup, fakes):
    _, labels, videos, write = setup
    muse, sam = fakes
    with pytest.raises(RealVideoError, match="check --freeze"):
        _run(tmp_path, labels, videos)
    rv.freeze(labels, rv.check(labels, videos))
    write(keep=1)  # edited after freezing
    with pytest.raises(RealVideoError, match="differ from the frozen"):
        _run(tmp_path, labels, videos)
    assert muse.calls == [] and sam.requests == [] and not (tmp_path / "runs").exists()


# ---- allowances -------------------------------------------------------------------------------------------


def test_muse_allowance_zero_raises_before_any_client_call(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(mr, "get_client", lambda s: called.append(1))
    comp = LimitedMuseCompiler(SETTINGS, cache_dir=tmp_path, max_live_calls=0)
    with pytest.raises(LiveCallLimit, match="Muse Spark.*allowance 0"):
        comp.compile(RULE, LAYOUT)
    assert called == [] and comp.live_calls == 0


def test_run_with_zero_muse_allowance_runs_nothing(tmp_path, setup, fakes):
    _, labels, videos, _ = setup
    muse, sam = fakes
    rv.freeze(labels, rv.check(labels, videos))
    with pytest.raises(LiveCallLimit, match="1 uncached rule compile"):
        _run(tmp_path, labels, videos, muse_calls=0)
    assert muse.calls == [] and sam.requests == [] and not (tmp_path / "runs").exists()


def test_run_with_zero_sam_allowance_stops_with_clear_error(tmp_path, setup, fakes):
    _, labels, videos, _ = setup
    muse, sam = fakes
    rv.freeze(labels, rv.check(labels, videos))
    with pytest.raises(LiveCallLimit, match="clip01.mp4: not cached and live-call allowance 0.*No report"):
        _run(tmp_path, labels, videos, sam_calls=0)
    assert sam.requests == [] and not (tmp_path / "report.json").exists()


# ---- matching ---------------------------------------------------------------------------------------------


def _obj(crosses: bool, intended: str = "PASS") -> LabeledObject:
    return LabeledObject(description="x", crosses_packing=crosses, stood_still_s=2.0 if intended == "PASS" else 0,
                         intended=intended)


def test_matching_pairs_by_crossing_order_and_reports_leftovers():
    labeled = [_obj(True, "VIOLATION"), _obj(True), _obj(False)]
    perceived = [Perceived(7, "TRUE", 40, 0), Perceived(3, "TRUE", 12, 5), Perceived(9, "FALSE", None, 2),
                 Perceived(4, "UNKNOWN", None, 30), Perceived(5, "TRUE", 70, 50)]
    m = rv.match_objects(labeled, perceived)
    assert m.pairs == [(0, 3), (1, 7), (2, 9)]  # crossers by crossing frame; non-crossers by first frame
    assert m.missed == [] and m.extra == [4, 5]  # an UNKNOWN crossing counts as not crossing
    m = rv.match_objects(labeled, [Perceived(1, "TRUE", 10, 0)])
    assert m.pairs == [(0, 1)] and m.missed == [1, 2] and m.extra == []


# ---- end to end -------------------------------------------------------------------------------------------


def test_run_report_before_and_after_repair(tmp_path, setup, fakes):
    scene, labels, videos, _ = setup
    muse, sam = fakes
    rv.freeze(labels, rv.check(labels, videos))
    rep = _run(tmp_path, labels, videos)
    assert rep["n_clips"] == 1 and rep["data"] == "real-world" and "never used to tune" in rep["disclaimer"]
    assert rep["live_calls"] == {"muse": 1, "sam": 1} and len(muse.calls) == 1
    assert rep["repair"]["proposal_id"] == rv.load_repair().proposal_id
    assert rep["repair"]["patch"]["ops"][0]["value"] == 800.0
    (c,) = rep["clips"]
    assert c["status"] == "completed" and (c["muse"], c["sam"]) == ("live", "live") and c["run_id"]
    from eventproof import pipeline
    ev = pipeline.load(c["run_id"], tmp_path / "runs")
    assert ev.verify() and ev.evidence_sha256 == c["evidence_sha256"] and c["clip_sha256"] == ev.video.original_sha256
    assert c["expected_overall"] == "FAIL"
    for side in ("before", "after"):
        assert c[side]["overall"] == "FAIL" and c[side]["agrees_overall"] and c[side]["objects_agree"] == 2
    assert c["before"]["rule_hash"] != c["after"]["rule_hash"]
    objs = c["objects"]
    assert [o["matched_object_id"] for o in objs["labeled"]] == [1, 0]  # the drive-through crosses first
    assert [o["intended"] for o in objs["labeled"]] == ["VIOLATION", "PASS"]
    assert objs["missed"] == [] and objs["extra"] == []
    md = (tmp_path / "report.md").read_text()
    assert "n=1 clips, no tuning" in md and c["run_id"] in md and c["evidence_sha256"][:12] in md

    # a re-run is served from cache (no new calls) but never overwrites the report
    with pytest.raises(RealVideoError, match="never overwritten"):
        _run(tmp_path, labels, videos)
    again = _run(tmp_path, labels, videos, out="report2.json", muse_calls=0, sam_calls=0)
    assert again["live_calls"] == {"muse": 0, "sam": 0} and (again["clips"][0]["muse"], again["clips"][0]["sam"]) == (
        "cached", "cached") and len(muse.calls) == 1 and len([r for r in sam.requests if r[0] == "stream"]) == 1


def test_extra_perceived_object_is_reported_not_hidden(tmp_path, setup, fakes):
    _, labels, videos, write = setup
    write(keep=1)  # the labeller only listed the drive-through
    rv.freeze(labels, rv.check(labels, videos))
    (c,) = _run(tmp_path, labels, videos)["clips"]
    assert c["n_labeled"] == 1 and c["n_perceived"] == 2
    assert c["objects"]["labeled"][0]["matched_object_id"] == 1 and c["before"]["objects_agree"] == 1
    (extra,) = c["objects"]["extra"]
    assert extra["object_id"] == 0 and extra["before"] == "PASS" and extra["perceived_crossing"] == "TRUE"
    assert "| extra |" in (tmp_path / "report.md").read_text()


def test_repair_that_does_not_apply_is_reported(tmp_path, clip, monkeypatch):
    scene, src = clip
    layout = Layout(zones=[LayoutZone(zone=INSPECTION.model_copy(update={"id": "station"}), description="station")],
                    lines=[LayoutLine(line=PACKING_LINE, description="packing entry")])
    out = copy.deepcopy(GOOD)
    out["nodes"][2]["first"]["zone"] = "station"
    monkeypatch.setattr(mr, "get_client", lambda s: FakeMuse([out]))
    monkeypatch.setattr(sam_mod, "get_client", lambda s: FakeClient(encode_wire(ground_truth(scene))))
    labels, videos = tmp_path / "labels", tmp_path / "videos"
    labels.mkdir()
    videos.mkdir()
    (videos / "clip01.mp4").write_bytes(src.read_bytes())
    lab = _labels_from_truth(scene, "clip01.mp4", rv.sha256_file(videos / "clip01.mp4"), layout=layout)
    (labels / "clip01.json").write_text(json.dumps(lab))
    rv.freeze(labels, rv.check(labels, videos))
    (c,) = _run(tmp_path, labels, videos)["clips"]
    assert c["before"]["overall"] == "FAIL" and c["after"]["overall"] is None
    assert "no DWELL on zone 'inspection'" in c["after"]["error"]
    assert all(o["after"] is None and not o["agree_after"] for o in c["objects"]["labeled"])


def test_load_repair_takes_first_accepted(tmp_path):
    r = rv.load_repair()
    raw = json.loads(rv.REPAIR_SOURCE.read_text())
    first = next(d for d in raw["decisions"] if d["accepted"])
    assert r.proposal_id == first["proposal"]["proposal_id"]
    assert r.patch == RulePatch.model_validate(first["proposal"]["patch"])
    assert r.source == "docs/evidence/runs/20261028T023754Z-a922b5bb/challenge/repair_muse.json"
    none = tmp_path / "r.json"
    none.write_text(json.dumps({**raw, "decisions": [{**d, "accepted": False} for d in raw["decisions"]]}))
    with pytest.raises(RealVideoError, match="no accepted"):
        rv.load_repair(none)
    assert isinstance(r.patch.ops[0], SetDwell)


def test_hash_facts(clip):
    _, src = clip
    f = rv.hash_facts(src)
    assert f["sha256"] == rv.sha256_file(src) and f["size"] == "640x360" and f["location_tags"] == []
    assert f["reencode_on_ingest"] == []


def test_timed_matching_pairs_by_side_and_time():
    from eventproof.validation.real_video import LabeledObject, Perceived, match_objects

    lab = [LabeledObject(description="rides away", crosses_packing=True, stood_still_s=0, intended="VIOLATION",
                         cross_s=1.5, cross_dir="to_left"),
           LabeledObject(description="rides toward", crosses_packing=True, stood_still_s=0, intended="PASS",
                         cross_s=1.6, cross_dir="to_right")]
    # the toward-camera rider crosses first in the tracks: crossing order would swap them
    per = [Perceived(7, "TRUE", 14, 0, 1400.0, "to_right"), Perceived(9, "TRUE", 28, 0, 2800.0, "to_left"),
           Perceived(3, "FALSE", None, 0)]
    m = match_objects(lab, per)
    assert m.pairs == [(1, 7)] and m.missed == [0]  # rider 0's track crosses to_left at 2.8 s: 1.3 s away, too far
    lab[0] = lab[0].model_copy(update={"cross_s": 2.5})
    assert match_objects(lab, per).pairs == [(0, 9), (1, 7)]
