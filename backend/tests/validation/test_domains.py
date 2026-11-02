"""New-domain real footage: verdicts recompute from the committed rules and SAM 3.1 tracks (no video, no API)."""

from __future__ import annotations

import json

import pytest

from eventproof.engine.evaluator import evaluate
from eventproof.schemas.rules import VisualRule
from eventproof.schemas.tracks import TrackSet
from eventproof.validation.real_video import ROOT

DIR = ROOT / "benchmark" / "real" / "domains"
REPORT = json.loads((DIR / "report_domains.json").read_text())


@pytest.mark.parametrize("clip", REPORT["clips"], ids=lambda c: c["clip"])
def test_verdicts_recompute(clip):
    run = DIR / "runs" / clip["run_id"]
    rule = VisualRule.model_validate(json.loads((run / "evidence.json").read_text())["rule"]["compiled_rule"])
    rep = evaluate(rule, TrackSet.model_validate_json((run / "tracks.json").read_text()))
    assert rep.overall == clip["before"]["overall"]
    assert {str(o.object_id): o.verdict for o in rep.objects} == clip["before"]["objects"]


def test_no_wrong_verdict_on_labelled_objects():
    rows = [r for c in REPORT["clips"] for r in c["objects"]["labeled"]]
    assert sum(r["agree_before"] for r in rows) == 7 and len(rows) == 8
    assert all(r["agree_before"] or r["before"] is None for r in rows)
