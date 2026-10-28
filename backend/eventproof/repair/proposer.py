"""Repair proposers. A proposer sees a `RepairContext` (the counterexample + the dev/challenge cases)
and returns bounded `RulePatch` proposals. It never sees the hidden holdout.

Isolation is enforced three ways (all covered by tests):
- this module imports neither `eventproof.challenge.holdout` nor `eventproof.repair.grader`;
- `RepairContext` is plain data built by the loop, checked by `loop.ensure_no_holdout` before use;
- the grader re-checks every proposal independently on the holdout; proposer claims are not trusted.

`BaselineProposer` is a deterministic search over a fixed grid. It is NOT Muse Spark and its
proposals are labelled `proposer="baseline-deterministic"`. A Muse proposer will implement the same
interface once API access exists, returning the same JSON patch schema.
"""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field

from eventproof.challenge.families import FAMILIES
from eventproof.challenge.runner import CaseResult, Perceiver, bind_rule, inspection_rule, mock_perceiver, run_case
from eventproof.challenge.scene import SceneSpec
from eventproof.repair.patch import RulePatch, SetDwell, SetDwellStill, SetMaxGap, apply_patch
from eventproof.schemas.rules import Dwell, VisualRule, iter_events


class CaseSummary(BaseModel):
    family: str
    seed: int
    scene_sha256: str
    intended: str
    oracle_verdict: str
    detector_verdict: str
    outcome: str

    @classmethod
    def of(cls, r: CaseResult) -> CaseSummary:
        return cls(**r.model_dump(include=set(cls.model_fields)))


class DetectorConfig(BaseModel):
    """The detector under repair: either the hand-written inspection template (dwell_ms, max_gap_frames) or any
    rule (e.g. compiled by Muse from the user's text), bound to each synthetic scene's geometry."""

    dwell_ms: float = 1500.0
    max_gap_frames: int = 3
    rule: VisualRule | None = None

    def rule_for(self, scene: SceneSpec, patch: RulePatch | None = None) -> VisualRule:
        rule = bind_rule(self.rule, scene) if self.rule else inspection_rule(scene, self.dwell_ms, self.max_gap_frames)
        return apply_patch(rule, patch) if patch else rule

    def dwell(self) -> tuple[str, float] | None:
        """(zone, min_ms) of the rule's first DWELL, the knob threshold repairs act on; None if it has none."""
        if not self.rule:
            return "inspection", self.dwell_ms
        ev = next((e for e in iter_events(self.rule.check) if isinstance(e, Dwell)), None)
        return (ev.zone, ev.min_ms) if ev else None

    def gap(self) -> int:
        return self.rule.params.max_gap_frames if self.rule else self.max_gap_frames


class RepairContext(BaseModel):
    detector: DetectorConfig
    perception: str
    counterexample: CaseSummary
    origin_scenes: list[SceneSpec] = Field(description="the failing scene and, if found, its minimized boundary twin")
    evidence: list[str] = Field(default_factory=list)
    dev_seeds: list[int]
    dev_results: list[CaseSummary]


class Proposal(BaseModel):
    proposal_id: str
    proposer: str
    patch: RulePatch
    rationale: str
    expected_effect: dict


class Proposer(Protocol):
    name: str

    def propose(self, ctx: RepairContext) -> list[Proposal]: ...


Kind = Literal["minimal", "dev_best"]


class BaselineProposer:
    """Fixed-grid search on the knob that matches the error type, screened on visible cases only."""

    name = "baseline-deterministic"

    def __init__(self, perceiver: Perceiver = mock_perceiver):
        self.perceiver = perceiver

    def candidates(self, ctx: RepairContext) -> list[RulePatch]:
        cx = ctx.counterexample
        if cx.outcome == "spec_error":
            dw = ctx.detector.dwell()
            if dw is None:
                return []  # no DWELL threshold to tune; only a model proposer can restructure such a rule
            zone, d0 = dw
            # rule too lenient (false PASS) -> demand longer dwell; too strict (false alarm) -> shorter
            factors = (1.1, 1.2, 1.33, 1.5, 2.0) if cx.detector_verdict == "PASS" else (0.9, 0.8, 0.67, 0.5)
            grid = [RulePatch(ops=[SetDwell(zone=zone, value=round(d0 * f, -2))]) for f in factors]
            # structural option after the threshold-only ones: time in the zone is not a stop, so count
            # only time spent still, then re-tune the threshold for "still" time
            still = SetDwellStill(zone=zone, max_speed=0.05)
            grid += [RulePatch(ops=[still, SetDwell(zone=zone, value=v)]) for v in dict.fromkeys((d0, 1000.0, 800.0, 600.0))]
            return grid
        # perception errors / abstentions: bridge longer tracking gaps
        return [RulePatch(ops=[SetMaxGap(value=v)]) for v in (6, 10, 15, 25) if v > ctx.detector.gap()]

    def _run(self, ctx: RepairContext, scene: SceneSpec, patch: RulePatch | None) -> CaseResult:
        return run_case(scene, ctx.detector.rule_for(scene, patch), self.perceiver)

    def propose(self, ctx: RepairContext) -> list[Proposal]:
        dev_scenes = [FAMILIES[r.family](r.seed) for r in ctx.dev_results]
        base_ok = [r.outcome == "correct" for r in ctx.dev_results]
        screened = []
        for patch in self.candidates(ctx):
            if not all(self._run(ctx, s, patch).outcome == "correct" for s in ctx.origin_scenes):
                continue
            after = [self._run(ctx, s, patch).outcome == "correct" for s in dev_scenes]
            regress = sum(b and not a for b, a in zip(base_ok, after, strict=True))
            screened.append((patch, sum(after), regress))
        if not screened:
            return []
        picks: dict[str, tuple[Kind, tuple]] = {}
        minimal = screened[0]  # grid is ordered by size of change
        picks[minimal[0].describe()] = ("minimal", minimal)
        safe = [s for s in screened if s[2] == 0]
        if safe:
            best = max(safe, key=lambda s: s[1])
            picks.setdefault(best[0].describe(), ("dev_best", best))
        n_dev, dev_before = len(dev_scenes), sum(base_ok)
        out = []
        for i, (desc, (kind, (patch, dev_after, regress))) in enumerate(picks.items()):
            why = ("smallest change on the grid that fixes the counterexample" if kind == "minimal"
                   else "best visible-case score among changes with no visible regressions")
            out.append(Proposal(
                proposal_id=f"{self.name}-{i}", proposer=self.name, patch=patch,
                rationale=f"{ctx.counterexample.outcome} on {ctx.counterexample.family}: {desc} ({why})",
                expected_effect={"fixes_counterexample": True, "dev_correct_before": dev_before,
                                 "dev_correct_after": dev_after, "dev_regressions": regress, "dev_cases": n_dev}))
        return out
