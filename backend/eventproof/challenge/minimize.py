"""Counterexample minimization.

Given a failing case, produce:
1. a *reduced* failing scene: greedy delta-debugging over discrete reductions (drop objects, drop
   occluders, trim leading/trailing frames) that keeps the same failure (outcome + detector verdict);
2. a *boundary pair*: binary search along one physical knob between the failing scene (t=0) and a
   benign variant (t=1), returning two near-identical scenes where one fails and the other is
   judged correctly.

Both results are LOCAL minima within a fixed search budget, never claimed to be global.

    uv run python -m eventproof.challenge.minimize --family tailgate --seed 0
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, Field

from eventproof.challenge.runner import (
    CaseResult,
    Perceiver,
    bind_rule,
    family_registry,
    inspection_rule,
    mock_perceiver,
    run_case,
)
from eventproof.challenge.scene import SceneSpec, Waypoint
from eventproof.challenge.traffic import TRAFFIC_KNOBS, is_traffic, perfect_perceiver, require_dev_seed, traffic_rule
from eventproof.schemas.rules import VisualRule

MIN_FRAMES = 50  # SAM bills at least 50 frames; never produce shorter clips


def is_failure(r: CaseResult) -> bool:
    return r.outcome in ("spec_error", "perception_error")


def same_failure(a: CaseResult, b: CaseResult) -> bool:
    return is_failure(b) and (a.outcome, a.detector_verdict) == (b.outcome, b.detector_verdict)


class Evaluator:
    """Runs a case for a scene with a fixed detector; counts evaluations (search budget).

    The detector is either the hand-written inspection template (`dwell_ms`) or any `rule` (e.g. compiled by
    Muse), bound to each scene's geometry."""

    def __init__(self, dwell_ms: float, perceiver: Perceiver, rule: VisualRule | None = None):
        self.dwell_ms, self.perceiver, self.rule, self.calls = dwell_ms, perceiver, rule, 0

    def rule_for(self, scene: SceneSpec) -> VisualRule:
        if self.rule:
            return bind_rule(self.rule, scene)
        return traffic_rule(scene, self.dwell_ms / 1000) if is_traffic(scene) else inspection_rule(scene, self.dwell_ms)

    def __call__(self, scene: SceneSpec) -> CaseResult:
        self.calls += 1
        return run_case(scene, self.rule_for(scene), self.perceiver)


# ---- 1. discrete reduction ----------------------------------------------------------------------


def _shift(scene: SceneSpec, k: int, n_frames: int) -> SceneSpec:
    objs = [o.model_copy(update={"waypoints": [w.model_copy(update={"frame": w.frame - k}) for w in o.waypoints]})
            for o in scene.objects]
    occs = [o.model_copy(update={"start_frame": max(0, o.start_frame - k),
                                 "end_frame": None if o.end_frame is None else o.end_frame - k})
            for o in scene.occluders if o.end_frame is None or o.end_frame - k >= 0]
    return scene.model_copy(update={"objects": objs, "occluders": occs, "n_frames": n_frames})


def reduction_candidates(scene: SceneSpec):
    for i in range(len(scene.objects)):
        if len(scene.objects) > 1:
            yield f"drop object {scene.objects[i].object_id}", scene.model_copy(
                update={"objects": scene.objects[:i] + scene.objects[i + 1:]})
    for i in range(len(scene.occluders)):
        yield "drop occluder", scene.model_copy(update={"occluders": scene.occluders[:i] + scene.occluders[i + 1:]})
    last = max(w.frame for o in scene.objects for w in o.waypoints)
    tail = max(MIN_FRAMES, last + 3)
    if tail < scene.n_frames:
        yield f"trim tail to {tail} frames", scene.model_copy(update={"n_frames": tail})
    first = min(w.frame for o in scene.objects for w in o.waypoints)
    head = min(first - 2, scene.n_frames - MIN_FRAMES)
    if head > 0:
        yield f"trim {head} leading frames", _shift(scene, head, scene.n_frames - head)


class Reduction(BaseModel):
    steps: list[str]
    frames_before: int
    frames_after: int
    objects_before: int
    objects_after: int
    occluders_before: int
    occluders_after: int


def reduce_scene(scene: SceneSpec, ev: Evaluator, budget: int = 40) -> tuple[SceneSpec, CaseResult, Reduction]:
    base = ev(scene)
    if not is_failure(base):
        raise ValueError(f"scene is not a failing case (outcome={base.outcome})")
    cur, cur_r, steps = scene, base, []
    progress = True
    while progress and ev.calls < budget:
        progress = False
        for desc, cand in reduction_candidates(cur):
            r = ev(cand)
            if same_failure(base, r):
                cur, cur_r, progress = cand, r, True
                steps.append(desc)
                break
    red = Reduction(steps=steps, frames_before=scene.n_frames, frames_after=cur.n_frames,
                    objects_before=len(scene.objects), objects_after=len(cur.objects),
                    occluders_before=len(scene.occluders), occluders_after=len(cur.occluders))
    return cur, cur_r, red


# ---- 2. boundary pair along a physical knob -------------------------------------------------------

Knob = Callable[[SceneSpec, float], SceneSpec]


def knob_separate(scene: SceneSpec, t: float, max_dy: float = 0.15) -> SceneSpec:
    """Push the last object's path (after its first waypoint) down by t*max_dy, away from the others."""
    o = scene.objects[-1]
    wps = [o.waypoints[0]] + [w.model_copy(update={"y": min(0.95, w.y + t * max_dy)}) for w in o.waypoints[1:]]
    return scene.model_copy(update={"objects": scene.objects[:-1] + [o.model_copy(update={"waypoints": wps})]})


def knob_occluder_shrink(scene: SceneSpec, t: float) -> SceneSpec:
    """Shorten every occluder's active window by fraction t (t=1: occluders gone)."""
    occs = []
    for oc in scene.occluders:
        end = scene.n_frames - 1 if oc.end_frame is None else oc.end_frame
        new_end = oc.start_frame + round((1 - t) * (end - oc.start_frame))
        if new_end > oc.start_frame:
            occs.append(oc.model_copy(update={"end_frame": new_end}))
    return scene.model_copy(update={"occluders": occs})


def _retime(o, f: Callable[[list[Waypoint]], list[Waypoint]]):
    return o.model_copy(update={"waypoints": f(o.waypoints)})


def knob_speed_up(scene: SceneSpec, t: float, max_factor: float = 3.0) -> SceneSpec:
    """Compress every object's motion in time by up to max_factor (faster belt)."""
    k = 1 + t * (max_factor - 1)

    def f(wps: list[Waypoint]) -> list[Waypoint]:
        s = wps[0].frame
        out, last = [], None
        for w in wps:
            fr = s + round((w.frame - s) / k)
            fr = fr if last is None or fr > last else last + 1
            out.append(w.model_copy(update={"frame": fr}))
            last = fr
        return out

    return scene.model_copy(update={"objects": [_retime(o, f) for o in scene.objects]})


def knob_stop_extend(scene: SceneSpec, t: float, max_extra_s: float = 1.5) -> SceneSpec:
    """Lengthen stationary segments by up to max_extra_s (the box is held at the station longer)."""
    extra = round(t * max_extra_s * scene.fps)

    def f(wps: list[Waypoint]) -> list[Waypoint]:
        out, add = [], 0
        for i, w in enumerate(wps):
            if i > 0 and (wps[i - 1].x, wps[i - 1].y) == (w.x, w.y):
                add += extra
            out.append(w.model_copy(update={"frame": w.frame + add}))
        return out

    objs = [_retime(o, f) for o in scene.objects]
    last = max(w.frame for o in objs for w in o.waypoints)
    return scene.model_copy(update={"objects": objs, "n_frames": max(scene.n_frames, last + 3)})


KNOBS: dict[str, tuple[str, Knob]] = {
    "tailgate": ("object separation (dy, normalized)", knob_separate),
    "occluded_station": ("occluder duration", knob_occluder_shrink),
    "drive_through": ("belt speed", knob_speed_up),
    "brief_stop": ("station stop duration", knob_stop_extend),
}


class BoundaryPair(BaseModel):
    knob: str
    t_fail: float
    t_pass: float
    iterations: int
    fail: CaseResult
    passing: CaseResult
    fail_scene: SceneSpec
    pass_scene: SceneSpec


def boundary_pair(scene: SceneSpec, knob_name: str, knob: Knob, ev: Evaluator, base: CaseResult,
                  grid: int = 20, iters: int = 8) -> BoundaryPair | None:
    """Find nearby knob values where the same failure turns into a correct verdict.

    A coarse grid over t in [0, 1] locates a failing point directly followed by a correct one; if
    other outcomes (e.g. abstentions) sit in between, the bracket is the last failure before the
    first correct point. Bisection then narrows it, stopping if it meets another outcome. Returns
    None when the knob never yields a correct verdict.
    """
    ts = [i / grid for i in range(grid + 1)]
    results = [base] + [ev(knob(scene, x)) for x in ts[1:]]
    bracket = next(((i, i + 1) for i in range(grid)
                    if same_failure(base, results[i]) and results[i + 1].outcome == "correct"), None)
    if bracket is None:  # other outcomes sit in between: last failure before the first correct point
        first_ok = next((i for i, r in enumerate(results) if r.outcome == "correct"), None)
        if first_ok is None:
            return None
        last_fail = max(i for i in range(first_ok) if same_failure(base, results[i]))
        bracket = (last_fail, first_ok)
    lo, hi = ts[bracket[0]], ts[bracket[1]]
    lo_r, hi_r = results[bracket[0]], results[bracket[1]]
    n = 0
    for n in range(1, iters + 1):  # noqa: B007  (n reported as iterations)
        mid = (lo + hi) / 2
        r = ev(knob(scene, mid))
        if same_failure(base, r):
            lo, lo_r = mid, r
        elif r.outcome == "correct":
            hi, hi_r = mid, r
        else:
            break
    return BoundaryPair(knob=knob_name, t_fail=lo, t_pass=hi, iterations=grid + n, fail=lo_r, passing=hi_r,
                        fail_scene=knob(scene, lo), pass_scene=knob(scene, hi))


class Counterexample(BaseModel):
    family: str
    seed: int
    dwell_ms: float
    rule: VisualRule | None = Field(default=None, description="detector rule if not the dwell_ms template")
    perception: str
    original: CaseResult
    reduction: Reduction
    reduced: CaseResult
    reduced_scene: SceneSpec
    pair: BoundaryPair | None
    evaluations: int
    note: str = "Local minimum within the search budget; not a global minimum."


def minimize(family: str, seed: int, dwell_ms: float = 1500.0, perceiver: Perceiver = mock_perceiver,
             budget: int = 60, rule: VisualRule | None = None, world: str = "conveyor") -> Counterexample:
    if world == "traffic":
        require_dev_seed(seed)
    scene = family_registry(world)[family](seed)
    ev = Evaluator(dwell_ms, perceiver, rule)
    original = ev(scene)
    reduced_scene, reduced, red = reduce_scene(scene, ev, budget=budget // 2)
    pair = None
    knobs = TRAFFIC_KNOBS if is_traffic(scene) else KNOBS
    if family in knobs:
        name, knob = knobs[family]
        pair = boundary_pair(reduced_scene, name, knob, ev, reduced)
    return Counterexample(family=family, seed=seed, dwell_ms=dwell_ms, rule=rule, perception=original.perception_source,
                          original=original, reduction=red, reduced=reduced, reduced_scene=reduced_scene,
                          pair=pair, evaluations=ev.calls)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", choices=["conveyor", "traffic"], default="conveyor")
    ap.add_argument("--family", required=True)
    ap.add_argument("--perfect", action="store_true", help="use perfect tracks; no model calls")
    ap.add_argument("--naive-traffic", action="store_true", help="omit speed condition to expose rolling-stop bug")
    ap.add_argument("--seed", default="auto", help="integer, or 'auto' = first failing seed in 0-99")
    ap.add_argument("--dwell-ms", type=float, default=1500.0)
    ap.add_argument("--out", type=Path, default=Path("../artifacts/counterexamples"))
    ap.add_argument("--no-video", action="store_true")
    args = ap.parse_args()
    registry = family_registry(args.world)
    if args.family not in registry:
        ap.error(f"family must be one of {sorted(registry)}")
    perceiver = perfect_perceiver if args.perfect else mock_perceiver
    rule = None
    if args.naive_traffic:
        if args.world != "traffic":
            ap.error("--naive-traffic requires --world traffic")
        rule = traffic_rule(registry[args.family](0), args.dwell_ms / 1000, max_speed=None)
    if args.seed == "auto":
        ev = Evaluator(args.dwell_ms, perceiver, rule)
        seed = next((s for s in range(100) if is_failure(ev(registry[args.family](s)))), None)
        if seed is None:
            raise SystemExit(f"no failing case for {args.family} in seeds 0-99")
    else:
        seed = int(args.seed)
        if args.world == "traffic":
            require_dev_seed(seed)
        if not is_failure(Evaluator(args.dwell_ms, perceiver, rule)(registry[args.family](seed))):
            raise SystemExit(f"{args.family} seed {seed} is judged correctly; nothing to minimize")
    args.seed = seed
    cx = minimize(args.family, seed, args.dwell_ms, perceiver=perceiver, rule=rule, world=args.world)
    d = args.out / f"{args.family}-{args.seed}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "counterexample.json").write_text(cx.model_dump_json(indent=2))
    summary = {"dir": str(d), "perception": cx.perception, "original_outcome": cx.original.outcome,
               "reduction": cx.reduction.steps, "evaluations": cx.evaluations}
    if cx.pair:
        from eventproof.challenge.replay import export_pair

        summary.update(knob=cx.pair.knob, t_fail=round(cx.pair.t_fail, 4), t_pass=round(cx.pair.t_pass, 4),
                       fail=cx.pair.fail.detector_verdict, passing=cx.pair.passing.detector_verdict,
                       intended=cx.pair.fail.intended)
        summary["replay"] = export_pair(cx, d, video=not args.no_video)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
