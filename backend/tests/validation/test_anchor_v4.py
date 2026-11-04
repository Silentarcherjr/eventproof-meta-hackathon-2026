"""Compiler with the anchor field, re-run on every frozen real set: verdicts recompute from the committed rules and
SAM 3.1 tracks (no video, no API), and the pooled counts in FINDINGS.md hold."""

from __future__ import annotations

import json

import pytest

from eventproof.engine.evaluator import evaluate
from eventproof.engine.lint import anchor_check
from eventproof.schemas.rules import VisualRule
from eventproof.schemas.tracks import TrackSet
from eventproof.validation.real_video import ROOT

DIR = ROOT / "benchmark" / "real" / "anchor_v4"
SETS = ("novisad", "traffic_v2", "traffic_v3", "domains", "santos")
REPORTS = {s: json.loads((DIR / f"report_{s}.json").read_text()) for s in SETS}
CLIPS = [c for r in REPORTS.values() for c in r["clips"]]


@pytest.mark.parametrize("clip", CLIPS, ids=lambda c: c["clip"])
def test_verdicts_recompute_and_rule_check_is_silent(clip):
    run = DIR / "runs" / clip["run_id"]
    ev = json.loads((run / "evidence.json").read_text())
    rule = VisualRule.model_validate(ev["rule"]["compiled_rule"])
    tracks = TrackSet.model_validate_json((run / "tracks.json").read_text())
    rep = evaluate(rule, tracks)
    assert rep.overall == clip["before"]["overall"]
    assert {str(o.object_id): o.verdict for o in rep.objects} == clip["before"]["objects"]
    assert anchor_check(rule, tracks) == []


def test_pooled_counts():
    rows = [r for c in CLIPS for r in c["objects"]["labeled"]]
    right = sum(r["agree_before"] for r in rows)
    unjudged = sum(r["before"] is None for r in rows)
    abstained = sum(r["before"] == "UNKNOWN" for r in rows)
    assert (len(rows), right, len(rows) - right - unjudged - abstained, abstained, unjudged) == (46, 38, 3, 2, 3)
    assert all(r["compiler_schema"] == "rule-schema/4-anchor" for r in REPORTS.values())
