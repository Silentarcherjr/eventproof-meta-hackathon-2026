from __future__ import annotations

import json

import pytest

from eventproof import ambiguity as am
from eventproof.meta.client import LiveCallLimit
from eventproof.repair.patch import RulePatch, apply_patch
from eventproof.schemas.rules import VisualRule

RUN = am.ROOT / "docs" / "evidence" / "runs" / "20261028T023754Z-a922b5bb"


@pytest.fixture(scope="module")
def demo_rules():
    a = VisualRule.model_validate(json.loads((RUN / "evidence.json").read_text())["rule"]["compiled_rule"])
    rep = json.loads((RUN / "challenge" / "repair_muse.json").read_text())
    d = next(d for d in rep["decisions"] if d["accepted"])
    return a, apply_patch(a, RulePatch.model_validate(d["proposal"]["patch"]))


def test_identical_rules_never_disagree(demo_rules):
    a, _ = demo_rules
    c = am.compare(a, a)
    assert c["disagree"] == 0 and c["pairs"] == []


def test_two_readings_disagree_where_expected_and_pair_straddles_the_boundary(demo_rules):
    a, b = demo_rules  # "any presence" vs "standing still": differ on drive-through and brief stops only
    c = am.compare(a, b)
    assert c["scenes"] == 150 and c["disagree"] > 0
    assert set(f for f, n in c["disagree_by_family"].items() if n) <= {"drive_through", "brief_stop"}
    for p in c["pairs"]:
        assert p["differ"]["verdicts"]["A"] != p["differ"]["verdicts"]["B"]
        assert p["agree"]["verdicts"]["A"] == p["agree"]["verdicts"]["B"]
        assert 0 <= p["t_differ"] < p["t_agree"] <= 1 and p["t_agree"] - p["t_differ"] < 0.01


def test_uncached_compile_needs_an_allowance(tmp_path):
    with pytest.raises(LiveCallLimit):
        am.compile_reading("Every box must linger.", "muse-spark-1.3", 0, tmp_path)
