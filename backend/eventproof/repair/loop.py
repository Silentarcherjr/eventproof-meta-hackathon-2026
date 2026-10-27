"""Repair loop: counterexample -> context (no holdout) -> proposals -> independent holdout grading.

    uv run python -m eventproof.repair.loop --family drive_through --seed auto --out ../benchmark/repairs

Every report states the proposer and the perception source. With mock perception and the baseline
proposer, results measure the repair/verification harness, not Meta models.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import BaseModel

from eventproof.challenge.families import FAMILIES
from eventproof.challenge.holdout import DEFAULT_PATH, HOLDOUT_SEEDS, HoldoutManifest
from eventproof.challenge.minimize import Counterexample, is_failure, minimize
from eventproof.challenge.runner import DEV_SEEDS, Perceiver, mock_perceiver, run_case
from eventproof.repair.grader import Grader, RepairDecision
from eventproof.repair.proposer import BaselineProposer, CaseSummary, DetectorConfig, Proposer, RepairContext


class HoldoutLeak(RuntimeError):
    pass


class RepairReport(BaseModel):
    family: str
    seed: int
    perception: str
    proposer: str
    detector_before: DetectorConfig
    context_sha_note: str = "RepairContext checked by ensure_no_holdout before it reached the proposer"
    decisions: list[RepairDecision]
    note: str = "Synthetic scenes, small n; results measure the harness and must not be generalized to production."


def build_context(cx: Counterexample, detector: DetectorConfig, perceiver: Perceiver = mock_perceiver) -> RepairContext:
    origin = [FAMILIES[cx.family](cx.seed)] + ([cx.pair.fail_scene] if cx.pair else [])
    dev_scenes = [FAMILIES[f](i) for f in sorted(FAMILIES) for i in DEV_SEEDS]
    dev = [run_case(s, detector.rule_for(s), perceiver) for s in dev_scenes]
    evidence = [f"original outcome {cx.original.outcome}, detector {cx.original.detector_verdict}, "
                f"truth {cx.original.intended}", *(f"reduction: {s}" for s in cx.reduction.steps)]
    if cx.pair:
        evidence.append(f"boundary pair on {cx.pair.knob}: fails at t={cx.pair.t_fail:.4f}, "
                        f"passes at t={cx.pair.t_pass:.4f}")
    return RepairContext(detector=detector, perception=cx.perception, counterexample=CaseSummary.of(cx.original),
                         origin_scenes=origin, evidence=evidence, dev_seeds=list(DEV_SEEDS),
                         dev_results=[CaseSummary.of(r) for r in dev])


def ensure_no_holdout(ctx: RepairContext, manifest: HoldoutManifest) -> None:
    """Refuse a context that mentions any holdout seed or scene hash."""
    blob = ctx.model_dump_json()
    seeds = {ctx.counterexample.seed, *ctx.dev_seeds, *(r.seed for r in ctx.dev_results),
             *(s.seed for s in ctx.origin_scenes)}
    if leaked := seeds & set(HOLDOUT_SEEDS):
        raise HoldoutLeak(f"holdout seeds in repair context: {sorted(leaked)[:5]}")
    if hit := next((c for c in manifest.cases if c.scene_sha256 in blob), None):
        raise HoldoutLeak(f"holdout scene {hit.family}/{hit.seed} in repair context")


def run_repair(family: str, seed: int, dwell_ms: float = 1500.0, proposer: Proposer | None = None,
               perceiver: Perceiver = mock_perceiver, holdout: Path = DEFAULT_PATH) -> RepairReport:
    detector = DetectorConfig(dwell_ms=dwell_ms)
    proposer = proposer or BaselineProposer(perceiver)
    cx = minimize(family, seed, dwell_ms, perceiver)
    ctx = build_context(cx, detector, perceiver)
    grader = Grader(detector, perceiver, holdout)  # loads + verifies the frozen holdout; proposer never gets it
    ensure_no_holdout(ctx, grader.manifest)
    proposals = proposer.propose(ctx)
    decisions = [grader.grade(p, ctx.origin_scenes) for p in proposals]
    return RepairReport(family=family, seed=seed, perception=cx.perception, proposer=proposer.name,
                        detector_before=detector, decisions=decisions)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", required=True, choices=sorted(FAMILIES))
    ap.add_argument("--seed", default="auto", help="integer, or 'auto' = first failing dev seed")
    ap.add_argument("--dwell-ms", type=float, default=1500.0)
    ap.add_argument("--out", type=Path, default=Path("../artifacts/repairs"))
    args = ap.parse_args()
    det = DetectorConfig(dwell_ms=args.dwell_ms)
    if args.seed == "auto":
        seed = next((s for s in DEV_SEEDS
                     if is_failure(run_case(sc := FAMILIES[args.family](s), det.rule_for(sc), mock_perceiver))), None)
        if seed is None:
            raise SystemExit(f"no failing dev case for {args.family}")
    else:
        seed = int(args.seed)
    rep = run_repair(args.family, seed, args.dwell_ms)
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{args.family}-{seed}.json"
    path.write_text(rep.model_dump_json(indent=2) + "\n")
    print(json.dumps({"report": str(path), "perception": rep.perception, "proposer": rep.proposer,
                      "decisions": [{"patch": d.patch_description, "accepted": d.accepted, "reasons": d.reasons}
                                    for d in rep.decisions]}, indent=2))


if __name__ == "__main__":
    main()
