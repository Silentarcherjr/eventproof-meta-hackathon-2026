"""Regression: every number published in benchmark/ and docs/evidence/ is recomputed and must match exactly.
If one of these fails, a code change altered a reported result: re-run and re-report, never edit the expectation
to make it pass silently."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eventproof.challenge.runner import DEV_SEEDS, run_suite, summarize
from eventproof.repair.grader import Grader
from eventproof.repair.patch import RulePatch
from eventproof.repair.proposer import DetectorConfig, Proposal
from eventproof.schemas.rules import VisualRule

ROOT = Path(__file__).resolve().parents[3]
MUSE_RUN = ROOT / "docs/evidence/runs/20261028T023754Z-a922b5bb"


def _json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text())


@pytest.mark.parametrize("dwell", [1500, 500])
def test_mock_challenge_suites(dwell):
    rep = _json(f"benchmark/reports/2026-10-27_mock_suite_dwell{dwell}.json")
    from eventproof.challenge.families import FAMILIES

    results = run_suite(list(FAMILIES), list(DEV_SEEDS), float(dwell))
    assert len(results) == rep["cases"] and summarize(results) == rep["by_family"]


def _regrade(detector: DetectorConfig, decisions: list[dict], origin) -> None:
    g = Grader(detector)
    for d in decisions:
        p = d["proposal"]
        prop = Proposal(proposal_id=p["proposal_id"], proposer=p["proposer"], patch=RulePatch.model_validate(p["patch"]),
                        rationale=p["rationale"], expected_effect=p["expected_effect"])
        got = g.grade(prop, origin)
        assert got.holdout_manifest_sha256 == d["holdout_manifest_sha256"]
        assert got.holdout_before.correct == d["holdout_before"]["correct"]
        assert (got.holdout_after and got.holdout_after.correct) == (d["holdout_after"] and d["holdout_after"]["correct"])
        assert got.accepted == d["accepted"] and got.regressions == d["regressions"], d["patch_description"]


def _origin(family: str, seed: int, rule: VisualRule | None = None, dwell_ms: float = 1500.0):
    """The origin scenes exactly as the repair loop built them (the original case + the failing side of the pair)."""
    from eventproof.challenge.families import FAMILIES
    from eventproof.challenge.minimize import minimize

    cx = minimize(family, seed, dwell_ms=dwell_ms, rule=rule)
    return [FAMILIES[family](seed)] + ([cx.pair.fail_scene] if cx.pair else [])


def test_recorded_muse_repair_decisions_regrade_identically():
    ev = json.loads((MUSE_RUN / "evidence.json").read_text())
    det = DetectorConfig(rule=VisualRule.model_validate(ev["rule"]["compiled_rule"]))
    rep = json.loads((MUSE_RUN / "challenge/repair_muse.json").read_text())
    cx = json.loads((MUSE_RUN / "challenge/challenge.json").read_text())["counterexample"]
    _regrade(det, rep["decisions"], _origin(cx["family"], cx["seed"], rule=det.rule))


@pytest.mark.parametrize("name", ["drive_through-0", "brief_stop-5"])
def test_recorded_baseline_repair_decisions_regrade_identically(name):
    rep = _json(f"benchmark/repairs/{name}.json")
    det = DetectorConfig(**rep["detector_before"])
    _regrade(det, rep["decisions"], _origin(rep["family"], rep["seed"], dwell_ms=det.dwell_ms))


def test_final_v1_report_is_reproducible():
    from eventproof.validation.evaluate import evaluate

    committed = _json("benchmark/final/report_final_v1.json")
    committed.pop("code_commit")
    assert json.loads(json.dumps(evaluate())) == committed
