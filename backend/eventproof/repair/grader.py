"""Independent grader: accepts or rejects a proposal using only the frozen hidden holdout.

Acceptance requires ALL of:
- the patch passes safety checks (bounded ops, schema-valid, rule structure unchanged);
- every origin scene (the counterexample) is now judged correctly;
- zero holdout regressions (no case that was correct becomes incorrect or abstained);
- no new dangerous false PASS on the holdout;
- holdout accuracy strictly improves — otherwise the repair "did not generalize" and is rejected.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from pydantic import BaseModel

from eventproof.challenge.holdout import DEFAULT_PATH, load_frozen, manifest_sha256
from eventproof.challenge.runner import CaseResult, Perceiver, mock_perceiver, run_case
from eventproof.challenge.scene import SceneSpec
from eventproof.repair.patch import PatchError, RulePatch
from eventproof.repair.proposer import DetectorConfig, Proposal


class HoldoutMetrics(BaseModel):
    n: int
    correct: int
    false_pass: int  # detector PASS, process truth FAIL: the dangerous error
    false_alarm: int
    abstained: int
    by_family: dict[str, dict[str, int]]


class RepairDecision(BaseModel):
    proposal: Proposal
    patch_description: str
    previous_rule_hash: str
    patched_rule_hash: str | None
    perception: str
    safety_checks: dict[str, bool]
    origin_outcomes_after: list[str]
    holdout_name: str
    holdout_manifest_sha256: str
    holdout_before: HoldoutMetrics
    holdout_after: HoldoutMetrics | None
    fixed_cases: list[str]
    regressions: list[str]
    accepted: bool
    reasons: list[str]


def metrics(results: list[CaseResult]) -> HoldoutMetrics:
    fam: dict[str, Counter] = {}
    for r in results:
        fam.setdefault(r.family, Counter())[r.outcome] += 1
    return HoldoutMetrics(
        n=len(results), correct=sum(r.outcome == "correct" for r in results),
        false_pass=sum(r.detector_verdict == "PASS" and r.intended == "FAIL" for r in results),
        false_alarm=sum(r.detector_verdict == "FAIL" and r.intended == "PASS" for r in results),
        abstained=sum(r.outcome == "abstained" for r in results), by_family={f: dict(c) for f, c in fam.items()})


class Grader:
    def __init__(self, detector: DetectorConfig, perceiver: Perceiver = mock_perceiver, holdout: Path = DEFAULT_PATH):
        self.detector, self.perceiver = detector, perceiver
        self.manifest, self.scenes = load_frozen(holdout)  # verifies every scene hash
        self.manifest_sha = manifest_sha256(holdout)
        self.before = self._run(None)

    def _run(self, patch: RulePatch | None) -> list[CaseResult]:
        return [run_case(s, self.detector.rule_for(s, patch), self.perceiver) for s in self.scenes]

    def grade(self, proposal: Proposal, origin_scenes: list[SceneSpec]) -> RepairDecision:
        probe = origin_scenes[0]
        prev_hash = self.detector.rule_for(probe).rule_hash()
        before_m = metrics(self.before)
        common = dict(proposal=proposal, patch_description=proposal.patch.describe(), previous_rule_hash=prev_hash,
                      perception=self.before[0].perception_source, holdout_name=self.manifest.name,
                      holdout_manifest_sha256=self.manifest_sha, holdout_before=before_m)
        try:
            patched = self.detector.rule_for(probe, proposal.patch)
        except (PatchError, ValueError) as e:
            return RepairDecision(**common, patched_rule_hash=None, safety_checks={"patch_applies": False},
                                  origin_outcomes_after=[], holdout_after=None, fixed_cases=[], regressions=[],
                                  accepted=False, reasons=[f"unsafe patch: {e}"])
        safety = {"patch_applies": True, "structure_unchanged": True, "rule_hash_changed": patched.rule_hash() != prev_hash}
        origin_after = [run_case(s, self.detector.rule_for(s, proposal.patch), self.perceiver).outcome
                        for s in origin_scenes]
        after = self._run(proposal.patch)
        after_m = metrics(after)
        pairs = [(f"{b.family}/{b.seed}", b.outcome == "correct", a.outcome == "correct")
                 for b, a in zip(self.before, after, strict=True)]
        fixed = [k for k, ok_b, ok_a in pairs if ok_a and not ok_b]
        regress = [k for k, ok_b, ok_a in pairs if ok_b and not ok_a]
        reasons = []
        if not all(safety.values()):
            reasons.append("safety check failed")
        if not all(o == "correct" for o in origin_after):
            reasons.append(f"does not fix the counterexample (origin outcomes {origin_after})")
        if regress:
            reasons.append(f"{len(regress)} holdout regression(s)")
        if after_m.false_pass > before_m.false_pass:
            reasons.append(f"false PASS increased {before_m.false_pass} -> {after_m.false_pass}")
        if after_m.correct <= before_m.correct:
            reasons.append(f"did not generalize: holdout correct {before_m.correct} -> {after_m.correct}")
        if not reasons:
            reasons.append(f"verified on unseen cases: {before_m.correct}/{before_m.n} -> {after_m.correct}/{after_m.n}, "
                           "0 regressions")
        accepted = len(reasons) == 1 and reasons[0].startswith("verified")
        return RepairDecision(**common, patched_rule_hash=patched.rule_hash(), safety_checks=safety,
                              origin_outcomes_after=origin_after, holdout_after=after_m, fixed_cases=fixed,
                              regressions=regress, accepted=accepted, reasons=reasons)
