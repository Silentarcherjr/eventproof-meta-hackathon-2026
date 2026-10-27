"""Run a detector (rule + perception) over adversarial families and classify every disagreement.

    uv run python -m eventproof.challenge.runner --seeds 0-29 --dwell-ms 1500

Outcomes per case (case = one scene):
- correct            detector verdict == intended verdict
- spec_error         rule on oracle tracks already disagrees with intent (the rule is wrong)
- perception_error   rule on oracle agrees with intent, perceived tracks flip the verdict
- abstained          detector says UNKNOWN (never counted as correct)
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel

from eventproof.challenge.families import FAMILIES
from eventproof.challenge.render import ground_truth, oracle_view
from eventproof.challenge.scene import SceneSpec
from eventproof.challenge.truth import ObjectTruth, intended_overall, scene_truth
from eventproof.engine.evaluator import evaluate
from eventproof.perception import mock
from eventproof.schemas.rules import VisualRule
from eventproof.schemas.tracks import TrackSet

Outcome = Literal["correct", "spec_error", "perception_error", "abstained"]
Perceiver = Callable[[SceneSpec, TrackSet], TrackSet]


class CaseResult(BaseModel):
    family: str
    seed: int
    scene_sha256: str
    perception_source: str
    rule_hash: str
    intended: Literal["PASS", "FAIL"]
    oracle_verdict: str
    detector_verdict: str
    outcome: Outcome
    truths: list[ObjectTruth]
    notes: str = ""


def inspection_rule(scene: SceneSpec, dwell_ms: float = 1500.0, max_gap_frames: int = 3) -> VisualRule:
    return VisualRule.model_validate({
        "rule_id": "inspect-before-packing",
        "entity": {"name": "package", "concept": "blue box"},
        "zones": [z.model_dump() for z in scene.zones],
        "lines": [ln.model_dump() for ln in scene.lines],
        "check": {
            "op": "IMPLIES",
            "premise": {"op": "OCCURS", "event": {"op": "CROSSES", "line": "packing_entry"}},
            "conclusion": {"op": "BEFORE", "first": {"op": "DWELL", "zone": "inspection", "min_ms": dwell_ms},
                           "then": {"op": "CROSSES", "line": "packing_entry"}},
        },
        "params": {"max_gap_frames": max_gap_frames},
        "normalized_explanation": f"Each blue box entering packing must first spend {dwell_ms / 1000:.1f} s in inspection.",
    })


def mock_perceiver(scene: SceneSpec, gt: TrackSet) -> TrackSet:
    return mock.perceive(gt, seed=scene.seed)


def classify(intended: str, oracle: str, detector: str) -> Outcome:
    if detector == "UNKNOWN":
        return "abstained"
    if detector == intended:
        return "correct"
    return "spec_error" if oracle != intended else "perception_error"


def run_case(scene: SceneSpec, rule: VisualRule, perceiver: Perceiver = mock_perceiver,
             min_stop_ms: float = 1000.0) -> CaseResult:
    gt = ground_truth(scene)
    truths = scene_truth(scene, rule.entity.concept, min_stop_ms)
    intended = intended_overall(truths)
    oracle = evaluate(rule, oracle_view(gt)).overall
    perceived = perceiver(scene, gt)
    detector = evaluate(rule, perceived).overall
    # NO_OBJECTS means nothing was seen; for a scene that has objects that is a miss, i.e. not a FAIL
    detector_v = "PASS" if detector == "NO_OBJECTS" else detector
    oracle_v = "PASS" if oracle == "NO_OBJECTS" else oracle
    return CaseResult(family=scene.family, seed=scene.seed, scene_sha256=scene.scene_hash(),
                      perception_source=perceived.source, rule_hash=rule.rule_hash(), intended=intended,
                      oracle_verdict=oracle_v, detector_verdict=detector_v,
                      outcome=classify(intended, oracle_v, detector_v), truths=truths, notes=scene.notes)


def run_suite(families: list[str], seeds: list[int], dwell_ms: float = 1500.0,
              perceiver: Perceiver = mock_perceiver) -> list[CaseResult]:
    results = []
    for fam in families:
        for s in seeds:
            scene = FAMILIES[fam](s)
            results.append(run_case(scene, inspection_rule(scene, dwell_ms), perceiver))
    return results


def summarize(results: list[CaseResult]) -> dict[str, dict[str, int]]:
    out: dict[str, Counter] = {}
    for r in results:
        out.setdefault(r.family, Counter())[r.outcome] += 1
    return {f: dict(c) for f, c in out.items()}


def _seeds(spec: str) -> list[int]:
    a, _, b = spec.partition("-")
    return list(range(int(a), int(b or a) + 1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--families", default=",".join(FAMILIES))
    ap.add_argument("--seeds", default="0-19")
    ap.add_argument("--dwell-ms", type=float, default=1500.0)
    ap.add_argument("--out", help="write all case results as JSON lines")
    args = ap.parse_args()
    results = run_suite(args.families.split(","), _seeds(args.seeds), args.dwell_ms)
    if args.out:
        with open(args.out, "w") as fh:
            for r in results:
                fh.write(r.model_dump_json() + "\n")
    print(json.dumps({"perception": "mock (NOT SAM)", "dwell_ms": args.dwell_ms, "cases": len(results),
                      "by_family": summarize(results)}, indent=2))


if __name__ == "__main__":
    main()
