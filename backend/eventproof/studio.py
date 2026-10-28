"""Challenge Mode and Repair for a completed run (used by the studio API).

Challenge world: the synthetic conveyor (zones 'inspection', line 'packing_entry'), whose process truth is
scripted, so every verdict can be scored. The run's compiled rule is bound to each synthetic scene's geometry
(`bind_rule`). The search uses the labelled MOCK tracker (free, deterministic); spec errors are preferred as
counterexamples because they do not depend on perception. `confirm_with_sam` re-checks the failing scene of the
pair with live SAM 3.1 (1 call). Repair proposals come from Muse Spark or the deterministic baseline and are
graded by the independent `Grader` on the frozen hidden holdout.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from pydantic import BaseModel

from eventproof.challenge.families import FAMILIES
from eventproof.challenge.minimize import Counterexample, is_failure, minimize
from eventproof.challenge.replay import export_pair
from eventproof.challenge.runner import DEV_SEEDS, CaseResult, mock_perceiver, run_case
from eventproof.perception.sam import SamTracker, sam_perceiver
from eventproof.pipeline import RUNS_DIR, Evidence
from eventproof.repair.grader import RepairDecision
from eventproof.repair.loop import run_repair
from eventproof.repair.proposer import BaselineProposer, DetectorConfig
from eventproof.schemas.rules import VisualRule

CHALLENGE_FILES = ("side_by_side.mp4", "replay.json")


class ChallengeUnavailable(ValueError):
    pass


class ChallengeReport(BaseModel):
    run_id: str
    rule_hash: str
    world: str = "synthetic conveyor (process truth: box stands still >= 1.0 s at inspection before packing)"
    perception: str
    suite: dict[str, dict[str, int]]
    suite_cases: int
    failures: int
    counterexample: dict | None
    files: list[str] = []


class RepairRun(BaseModel):
    run_id: str
    proposer: str
    decisions: list[RepairDecision]
    trace: dict = {}
    holdout_note: str = ("Graded on the frozen hidden holdout (200 synthetic scenes, mock perception). The proposer "
                         "never saw it; every proposal is graded, none is picked by its holdout score.")


def _dir(run_id: str, runs_dir: Path | None) -> Path:
    return (runs_dir or RUNS_DIR) / run_id / "challenge"


def _rule(ev: Evidence) -> VisualRule:
    if ev.status != "completed" or not ev.rule.compiled_rule:
        raise ChallengeUnavailable("the run has no compiled rule")
    return VisualRule.model_validate(ev.rule.compiled_rule)


def _priority(r: CaseResult) -> tuple:
    # spec errors first (perception-independent), dangerous false PASS before false alarms, then the clearest case:
    # the violating object that stood still the least (a box that never stopped beats a borderline stop)
    stop = min((t.station_stop_ms for t in r.truths if t.intended == "VIOLATION"), default=float("inf"))
    return (r.outcome != "spec_error", r.detector_verdict != "PASS", stop, r.family, r.seed)


def challenge(ev: Evidence, runs_dir: Path | None = None) -> ChallengeReport:
    rule = _rule(ev)
    det = DetectorConfig(rule=rule)
    try:
        results = [run_case(s, det.rule_for(s)) for f in sorted(FAMILIES) for s in (FAMILIES[f](i) for i in DEV_SEEDS)]
    except ValueError as e:  # WorldMismatch: rule ids not in the synthetic world
        raise ChallengeUnavailable(str(e)) from None
    suite: dict[str, Counter] = {}
    for r in results:
        suite.setdefault(r.family, Counter())[r.outcome] += 1
    fails = sorted((r for r in results if is_failure(r)), key=_priority)
    out = _dir(ev.run_id, runs_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = ChallengeReport(run_id=ev.run_id, rule_hash=rule.rule_hash(), perception="mock (NOT SAM)",
                             suite={f: dict(c) for f, c in suite.items()}, suite_cases=len(results),
                             failures=len(fails), counterexample=None)
    if fails:
        cx = minimize(fails[0].family, fails[0].seed, rule=rule)
        (out / "counterexample.json").write_text(cx.model_dump_json())
        summary = {"family": cx.family, "seed": cx.seed, "outcome": cx.original.outcome,
                   "detector_verdict": cx.original.detector_verdict, "intended": cx.original.intended,
                   "oracle_verdict": cx.original.oracle_verdict, "truths": [t.model_dump() for t in cx.original.truths],
                   "notes": FAMILIES[cx.family](cx.seed).notes, "reduction": cx.reduction.steps,
                   "evaluations": cx.evaluations}
        if cx.pair:
            replay = export_pair(cx, out, video=True)
            summary |= {"knob": cx.pair.knob, "t_fail": cx.pair.t_fail, "t_pass": cx.pair.t_pass,
                        "pass_verdict": cx.pair.passing.detector_verdict,
                        "decisive_frames": replay["decisive_frames"], "scene_difference": replay["scene_difference"],
                        "identity_events_fail": replay["identity_events_fail"][:6]}
            report.files = list(CHALLENGE_FILES) + replay["decisive_pngs"]
        report.counterexample = summary
    (out / "challenge.json").write_text(report.model_dump_json(indent=2))
    return report


def load_counterexample(run_id: str, runs_dir: Path | None = None) -> Counterexample:
    p = _dir(run_id, runs_dir) / "counterexample.json"
    if not p.exists():
        raise ChallengeUnavailable("run Challenge Mode first (no counterexample for this run)")
    return Counterexample.model_validate_json(p.read_text())


def confirm_with_sam(ev: Evidence, tracker: SamTracker, runs_dir: Path | None = None) -> dict:
    """Run the failing scene of the pair (or the original) through live SAM 3.1 and re-score it."""
    cx = load_counterexample(ev.run_id, runs_dir)
    scene = cx.pair.fail_scene if cx.pair else cx.reduced_scene
    det = DetectorConfig(rule=_rule(ev))
    r = run_case(scene, det.rule_for(scene), sam_perceiver(tracker))
    m = run_case(scene, det.rule_for(scene), mock_perceiver)
    res = {"scene_sha256": scene.scene_hash(), "sam": r.model_dump(include={"perception_source", "detector_verdict",
                                                                               "intended", "oracle_verdict", "outcome"}),
           "mock_outcome": m.outcome, "still_fails_with_sam": is_failure(r), "live_sam_calls": tracker.live_calls}
    (_dir(ev.run_id, runs_dir) / "sam_confirm.json").write_text(json.dumps(res, indent=2))
    return res


def repair(ev: Evidence, proposer_name: str, runs_dir: Path | None = None, muse_settings=None,
           muse_cache: Path | None = None) -> RepairRun:
    cx = load_counterexample(ev.run_id, runs_dir)
    det = DetectorConfig(rule=_rule(ev))
    if proposer_name == "muse":
        from eventproof.meta.muse_repair import MuseProposer

        kw = {"cache_dir": muse_cache} if muse_cache else {}
        proposer = MuseProposer(muse_settings, rule_text=ev.rule.text, **kw)
    elif proposer_name == "baseline":
        proposer = BaselineProposer()
    else:
        raise ValueError("proposer must be 'muse' or 'baseline'")
    rep = run_repair(cx.family, cx.seed, proposer=proposer, detector=det, cx=cx)
    trace = getattr(proposer, "last", {}) or {}
    out = RepairRun(run_id=ev.run_id, proposer=rep.proposer, decisions=rep.decisions, trace=trace)
    (_dir(ev.run_id, runs_dir) / f"repair_{proposer_name}.json").write_text(out.model_dump_json(indent=2))
    return out
