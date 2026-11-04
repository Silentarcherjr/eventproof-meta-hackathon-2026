"""Run a detector (rule + perception) over adversarial families and classify every disagreement.

    uv run python -m eventproof.challenge.runner --seeds 0-29 --dwell-ms 1500
    uv run python -m eventproof.challenge.runner --perception sam --families canonical --seeds 0-1 --max-live-calls 2

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
from eventproof.challenge.traffic import TrafficTruth, is_traffic, perfect_perceiver, traffic_rule
from eventproof.challenge.traffic import scene_truth as traffic_truth
from eventproof.challenge.truth import ObjectTruth, intended_overall, scene_truth
from eventproof.engine.evaluator import evaluate
from eventproof.perception import mock
from eventproof.schemas.rules import VisualRule
from eventproof.schemas.tracks import TrackSet

Outcome = Literal["correct", "spec_error", "perception_error", "abstained"]
Perceiver = Callable[[SceneSpec, TrackSet], TrackSet]
DEV_SEEDS = range(0, 30)  # challenge cases: visible to the counterexample search and to repair proposers


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
    truths: list[ObjectTruth | TrafficTruth]
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


class WorldMismatch(ValueError):
    pass


def bind_rule(rule: VisualRule, scene: SceneSpec) -> VisualRule:
    """Put any rule (e.g. compiled by Muse) into a synthetic scene: zone/line geometry is taken from the scene,
    matched by id, and the entity concept becomes the scene's object label. Logic and thresholds are kept."""
    zones, lines = {z.id: z for z in scene.zones}, {ln.id: ln for ln in scene.lines}
    missing = [z.id for z in rule.zones if z.id not in zones] + [ln.id for ln in rule.lines if ln.id not in lines]
    if missing:
        raise WorldMismatch(f"rule references {missing}; the synthetic world has zones {sorted(zones)} "
                            f"and lines {sorted(lines)}")
    label = "car" if is_traffic(scene) else (scene.objects[0].label if scene.objects else rule.entity.concept)
    return rule.model_copy(update={"zones": [zones[z.id] for z in rule.zones], "lines": [lines[ln.id] for ln in rule.lines],
                                   "entity": rule.entity.model_copy(update={"concept": label})})


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
    truths = traffic_truth(scene) if is_traffic(scene) else scene_truth(scene, rule.entity.concept, min_stop_ms)
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
              perceiver: Perceiver = mock_perceiver, world: str = "conveyor") -> list[CaseResult]:
    registry = family_registry(world)
    results = []
    for fam in families:
        for s in seeds:
            if world == "traffic":
                from eventproof.challenge.traffic import require_dev_seed

                require_dev_seed(s)
            scene = registry[fam](s)
            rule = traffic_rule(scene, dwell_ms / 1000) if world == "traffic" else inspection_rule(scene, dwell_ms)
            results.append(run_case(scene, rule, perceiver))
    return results


def family_registry(world: str) -> dict[str, Callable[[int], SceneSpec]]:
    if world == "conveyor":
        return FAMILIES
    if world == "traffic":
        from eventproof.challenge.traffic import TRAFFIC_FAMILIES

        return TRAFFIC_FAMILIES
    raise ValueError(f"unknown challenge world {world!r}")


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
    ap.add_argument("--world", choices=["conveyor", "traffic"], default="conveyor")
    ap.add_argument("--families", help="comma-separated; default: all families of selected world")
    ap.add_argument("--seeds", default="0-19")
    ap.add_argument("--dwell-ms", type=float, default=1500.0)
    ap.add_argument("--out", help="write all case results as JSON lines")
    ap.add_argument("--perception", choices=["mock", "sam", "perfect"], default="mock")
    ap.add_argument("--max-live-calls", type=int, default=0,
                    help="SAM only: live (billed) calls allowed in this run; cached results are free")
    args = ap.parse_args()
    perceiver: Perceiver = mock_perceiver
    if args.perception == "perfect":
        perceiver = perfect_perceiver
    if args.perception == "sam":
        from eventproof.perception.sam import SamTracker, sam_perceiver

        tracker = SamTracker(max_live_calls=args.max_live_calls)
        perceiver = sam_perceiver(tracker)
    families = args.families.split(",") if args.families else list(family_registry(args.world))
    results = run_suite(families, _seeds(args.seeds), args.dwell_ms, perceiver, world=args.world)
    if args.out:
        with open(args.out, "w") as fh:
            for r in results:
                fh.write(r.model_dump_json() + "\n")
    label = {"mock": "mock (NOT SAM)", "perfect": "synthetic perfect tracks (NOT SAM)"}.get(args.perception)
    if args.perception == "sam":
        label = f"sam-3.1 ({tracker.live_calls} live calls, rest cached)"
    print(json.dumps({"perception": label, "dwell_ms": args.dwell_ms, "cases": len(results),
                      "by_family": summarize(results)}, indent=2))


if __name__ == "__main__":
    main()
