from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest
from pydantic import ValidationError

from eventproof.challenge.families import FAMILIES
from eventproof.challenge.holdout import HOLDOUT_SEEDS, load_frozen
from eventproof.challenge.minimize import minimize
from eventproof.repair.grader import Grader
from eventproof.repair.loop import HoldoutLeak, build_context, ensure_no_holdout, run_repair
from eventproof.repair.patch import PatchError, RulePatch, SetDwell, apply_patch
from eventproof.repair.proposer import BaselineProposer, DetectorConfig, Proposal, RepairContext

DET = DetectorConfig(dwell_ms=1500.0)


# ---- patches ---------------------------------------------------------------------------------------


def test_patch_ops_are_bounded_by_schema():
    for bad in ({"op": "set_dwell_min_ms", "zone": "inspection", "value": 50_000},
                {"op": "set_max_gap_frames", "value": 500},
                {"op": "set_dwell_max_speed", "zone": "inspection", "max_speed": 5},
                {"op": "set_zone_polygon", "zone": "inspection", "polygon": []}):
        with pytest.raises(ValidationError):
            RulePatch.model_validate({"ops": [bad]})
    with pytest.raises(ValidationError):
        RulePatch.model_validate({"ops": [{"op": "set_max_gap_frames", "value": 5}] * 4})


def test_apply_patch_changes_only_thresholds():
    scene = FAMILIES["canonical"](0)
    rule = DET.rule_for(scene)
    patch = RulePatch.model_validate({"ops": [{"op": "set_dwell_max_speed", "zone": "inspection", "max_speed": 0.05},
                                              {"op": "set_dwell_min_ms", "zone": "inspection", "value": 800}]})
    out = apply_patch(rule, patch)
    assert out.version == rule.version + 1 and out.rule_hash() != rule.rule_hash()
    assert out.zones == rule.zones and out.lines == rule.lines and out.entity == rule.entity
    dwell = out.check.conclusion.first
    assert (dwell.min_ms, dwell.max_speed) == (800, 0.05)
    assert rule.check.conclusion.first.min_ms == 1500, "original rule is not mutated"
    with pytest.raises(PatchError):
        apply_patch(rule, RulePatch(ops=[SetDwell(zone="packing", value=800)]))


# ---- holdout isolation -------------------------------------------------------------------------------


def _eventproof_imports(module: str, seen: set[str] | None = None) -> set[str]:
    """Transitive closure of eventproof.* modules imported by `module` (static, via AST)."""
    seen = seen if seen is not None else set()
    spec = importlib.util.find_spec(module)
    assert spec and spec.origin
    for node in ast.walk(ast.parse(Path(spec.origin).read_text())):
        names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
            [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
        for n in names:
            if n.startswith("eventproof") and n not in seen and importlib.util.find_spec(n):
                seen.add(n)
                _eventproof_imports(n, seen)
    return seen


def test_proposer_cannot_reach_the_holdout_or_the_grader():
    reach = _eventproof_imports("eventproof.repair.proposer")
    assert "eventproof.challenge.holdout" not in reach
    assert "eventproof.repair.grader" not in reach
    assert "eventproof.repair.loop" not in reach


@pytest.fixture(scope="module")
def ctx() -> RepairContext:
    return build_context(minimize("drive_through", 0), DET)


def test_repair_context_excludes_holdout(ctx):
    manifest, _ = load_frozen()
    ensure_no_holdout(ctx, manifest)  # does not raise
    blob = ctx.model_dump_json()
    assert not any(c.scene_sha256 in blob for c in manifest.cases)
    assert all(s not in HOLDOUT_SEEDS for s in ctx.dev_seeds)


def test_leaky_context_is_refused(ctx):
    manifest, scenes = load_frozen()
    with pytest.raises(HoldoutLeak):
        ensure_no_holdout(ctx.model_copy(update={"origin_scenes": [*ctx.origin_scenes, scenes[0]]}), manifest)
    with pytest.raises(HoldoutLeak):
        ensure_no_holdout(ctx.model_copy(update={"evidence": [f"hint {manifest.cases[3].scene_sha256}"]}), manifest)


class SpyProposer(BaselineProposer):
    name = "spy"

    def propose(self, ctx):
        self.seen = ctx.model_dump_json()
        return super().propose(ctx)


def test_proposer_only_ever_receives_a_clean_context():
    spy = SpyProposer()
    run_repair("drive_through", 0, proposer=spy)
    manifest, _ = load_frozen()
    assert not any(c.scene_sha256 in spy.seen for c in manifest.cases)


# ---- grading ---------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def report():
    return run_repair("drive_through", 0)


def test_one_repair_accepted_and_one_rejected_on_unseen_cases(report):
    assert report.perception == "mock" and report.proposer == "baseline-deterministic"
    rejected = [d for d in report.decisions if not d.accepted]
    accepted = [d for d in report.decisions if d.accepted]
    assert rejected and accepted
    # the naive threshold bump fixes the counterexample but breaks unseen cases
    naive = rejected[0]
    assert all(o == "correct" for o in naive.origin_outcomes_after) and naive.regressions
    good = accepted[0]
    assert not good.regressions and good.holdout_after.correct > good.holdout_before.correct
    assert good.holdout_after.false_pass <= good.holdout_before.false_pass


def test_decision_metrics_are_consistent(report):
    for d in report.decisions:
        assert d.holdout_after.correct - d.holdout_before.correct == len(d.fixed_cases) - len(d.regressions)
        assert d.holdout_before.n == d.holdout_after.n == len(load_frozen()[0].cases)
        assert d.patched_rule_hash != d.previous_rule_hash


def test_grader_rejects_a_patch_that_does_not_fix_the_counterexample(ctx):
    noop = Proposal(proposal_id="t", proposer="test", patch=RulePatch(ops=[SetDwell(zone="inspection", value=1500)]),
                    rationale="no-op", expected_effect={})
    d = Grader(DET).grade(noop, ctx.origin_scenes)
    assert not d.accepted
    assert any("does not fix" in r for r in d.reasons) and any("did not generalize" in r for r in d.reasons)
