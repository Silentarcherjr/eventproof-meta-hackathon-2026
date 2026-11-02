"""The published Novi Sad (Pexels) results are recomputed from the committed rule + SAM tracks: no video, no API."""

from __future__ import annotations

import json

import pytest

from eventproof.engine.evaluator import evaluate
from eventproof.repair.patch import apply_patch
from eventproof.schemas.rules import VisualRule
from eventproof.schemas.tracks import TrackSet
from eventproof.validation.real_video import ROOT, load_repair

DIR = ROOT / "benchmark" / "real" / "novisad"
REPORT = json.loads((DIR / "report_novisad.json").read_text())


@pytest.mark.parametrize("clip", REPORT["clips"], ids=lambda c: c["clip"])
def test_before_and_after_verdicts_recompute_from_committed_tracks(clip):
    run = DIR / "runs" / clip["run_id"]
    ev = json.loads((run / "evidence.json").read_text())
    rule = VisualRule.model_validate(ev["rule"]["compiled_rule"])
    tracks = TrackSet.model_validate_json((run / "tracks.json").read_text())
    assert ev["perception"]["tracks_sha256"] and tracks.source == "sam-3.1"
    before = evaluate(rule, tracks)
    after = evaluate(apply_patch(rule, load_repair().patch), tracks)
    for side, rep in (("before", before), ("after", after)):
        assert rep.overall == clip[side]["overall"]
        assert {str(o.object_id): o.verdict for o in rep.objects} == clip[side]["objects"]


def test_rolling_van_is_the_one_object_the_synthetic_repair_gets_wrong():
    rows = [r for c in REPORT["clips"] for r in c["objects"]["labeled"]]
    assert sum(r["agree_before"] for r in rows) == 8 and sum(r["agree_after"] for r in rows) == 7
    (wrong,) = [r for r in rows if not r["agree_after"]]
    assert wrong["intended"] == "VIOLATION" and wrong["after"] == "PASS" and "van" in wrong["description"]
