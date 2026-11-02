"""Ambiguity finder: two Meta models read the same sentence; where their rules disagree, show the user the smallest
pair of scenes that separates the two readings and let them choose (pre-registered in
`benchmark/ambiguity/PREREGISTRATION.md`).

1. Muse Spark and Muse Wonder each compile the rule text (same strict schema, same layout) and state their assumptions.
2. Both rules are run on the synthetic development suite with ground-truth tracks (no perception noise), so any
   difference in verdicts is a difference of interpretation, never of tracking.
3. For each scene family where they disagree, a knob (belt speed, stop length, ...) is bisected from a disagreeing scene
   towards one where they agree: the result is a near-identical pair of scenes, one on each side of the boundary.
4. The question shown to the user: "here the two readings give different verdicts; which one do you mean?"

    uv run python -m eventproof.ambiguity run --max-live-calls 16 --out ../benchmark/ambiguity/report.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path

from pydantic import BaseModel

from eventproof.challenge.families import FAMILIES
from eventproof.challenge.minimize import KNOBS
from eventproof.challenge.render import ground_truth, oracle_view
from eventproof.challenge.runner import bind_rule
from eventproof.challenge.scene import SceneSpec
from eventproof.challenge.truth import intended_overall, scene_truth
from eventproof.engine.evaluator import evaluate
from eventproof.meta.client import LiveCallLimit, MetaSettings
from eventproof.meta.muse_rules import Layout, MuseRuleCompiler, RuleCompileError
from eventproof.schemas.rules import VisualRule

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "benchmark" / "ambiguity"
MODELS = ("muse-spark-1.3", "muse-wonder-1.0")
SEEDS = range(0, 30)  # the development seeds Challenge Mode already uses; never the holdout or final seeds
LAYOUT = Layout.model_validate({
    "zones": [{"zone": {"id": "inspection", "polygon": [[0.3, 0.1], [0.5, 0.1], [0.5, 0.9], [0.3, 0.9]]},
               "description": "inspection station on the conveyor"}],
    "lines": [{"line": {"id": "packing_entry", "a": [0.75, 0.05], "b": [0.75, 0.95]},
               "description": "entry of the packing area; boxes travel left to right"}]})
TEXTS = (  # fixed before any call; same meaning to a casual reader, different verbs
    "Every box must stay at least 1.5 seconds in the inspection zone before it crosses into packing.",
    "Every box must stop in the inspection zone for at least 1.5 seconds before it crosses into packing.",
    "Every box must wait at least 1.5 seconds in the inspection zone before it crosses into packing.",
    "Every box must pause in the inspection zone for 1.5 seconds before entering packing.",
    "Boxes must spend at least 1.5 seconds in the inspection zone before entering packing.",
    "No box may enter packing without being held in the inspection zone for 1.5 seconds.",
    "Every box must be inspected for at least 1.5 seconds before it crosses into packing.",
    "Every box must remain at the inspection station for at least 1.5 seconds before packing.",
)


class Reading(BaseModel):
    model: str
    ok: bool
    rule: VisualRule | None = None
    assumptions: list[str] = []
    refusal: str | None = None
    request_ids: list[str] = []
    cached: bool | None = None


def compile_reading(text: str, model: str, max_live: int, cache_root: Path,
                    layout: Layout = LAYOUT) -> tuple[Reading, int]:
    settings = dataclasses.replace(MetaSettings.from_env(), muse_model=model)
    comp = MuseRuleCompiler(settings, cache_dir=cache_root / model)  # default 2 attempts, as in the product
    key = comp._key(text, layout)
    refusal = comp.cache_dir / f"{key}.refusal.json"
    if refusal.exists():  # the compiler caches accepted rules; declined/invalid outcomes are cached here
        return Reading(model=model, ok=False, refusal=json.loads(refusal.read_text())["refusal"], cached=True), 0
    if not (comp.cache_dir / f"{key}.json").exists() and max_live <= 0:
        raise LiveCallLimit(f"{model}: compile of {text[:40]!r} is not cached and the allowance is used up")
    try:
        c = comp.compile(text, layout)
    except RuleCompileError as e:  # UnsupportedRule (the model declined) or an output that did not validate
        msg = f"{type(e).__name__}: {e}"[:400]
        comp.cache_dir.mkdir(parents=True, exist_ok=True)
        refusal.write_text(json.dumps({"model": model, "text": text, "refusal": msg}, indent=2) + "\n")
        return Reading(model=model, ok=False, refusal=msg, cached=False), comp.live_calls
    return Reading(model=model, ok=True, rule=c.rule, assumptions=c.assumptions, request_ids=c.request_ids,
                   cached=c.cached), comp.live_calls


def verdict(rule: VisualRule, scene: SceneSpec) -> str:
    return evaluate(bind_rule(rule, scene), oracle_view(ground_truth(scene))).overall


def truth(scene: SceneSpec) -> str:
    label = scene.objects[0].label if scene.objects else "box"
    return intended_overall(scene_truth(scene, label))


def minimal_pair(a: VisualRule, b: VisualRule, scene: SceneSpec, family: str, grid: int = 20,
                 iters: int = 8) -> dict | None:
    """Bisect the family's knob from this disagreeing scene (t=0) to the nearest scene where the readings agree."""
    if family not in KNOBS:
        return None
    name, knob = KNOBS[family]
    differ = lambda s: verdict(a, s) != verdict(b, s)  # noqa: E731
    ts = [i / grid for i in range(grid + 1)]
    first_agree = next((t for t in ts[1:] if not differ(knob(scene, t))), None)
    if first_agree is None:
        return None
    lo, hi = max(t for t in ts if t < first_agree), first_agree
    for _ in range(iters):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if differ(knob(scene, mid)) else (lo, mid)
    s_lo, s_hi = knob(scene, lo), knob(scene, hi)
    side = lambda s: {"scene_sha256": s.scene_hash(), "truth": truth(s), "verdicts": {  # noqa: E731
        "A": verdict(a, s), "B": verdict(b, s)}}
    return {"family": family, "seed": scene.seed, "knob": name, "t_differ": round(lo, 5), "t_agree": round(hi, 5),
            "differ": side(s_lo), "agree": side(s_hi)}


def compare(a: VisualRule, b: VisualRule) -> dict:
    rows = []
    for fam, make in FAMILIES.items():
        for seed in SEEDS:
            s = make(seed)
            rows.append({"family": fam, "seed": seed, "truth": truth(s), "A": verdict(a, s), "B": verdict(b, s)})
    dis = [r for r in rows if r["A"] != r["B"]]
    pairs = []
    for fam in sorted({r["family"] for r in dis}):
        r = next(x for x in dis if x["family"] == fam)
        p = minimal_pair(a, b, FAMILIES[fam](r["seed"]), fam)
        if p:
            pairs.append(p)
    acc = {k: sum(r[k] == r["truth"] for r in rows) for k in ("A", "B")}
    return {"scenes": len(rows), "disagree": len(dis),
            "disagree_by_family": {f: sum(r["family"] == f for r in dis) for f in FAMILIES},
            "correct_vs_process_truth": acc, "pairs": pairs, "disagreeing_scenes": dis[:40]}


def run(max_live: int, cache_root: Path = OUT_DIR / "cache", texts: tuple[str, ...] = TEXTS) -> dict:
    out, live = [], 0
    for text in texts:
        readings = []
        for model in MODELS:
            r, used = compile_reading(text, model, max_live - live, cache_root)
            live += used
            readings.append(r)
        a, b = readings
        row = {"text": text, "A": a.model_dump(mode="json"), "B": b.model_dump(mode="json")}
        if a.ok and b.ok:
            same = a.rule.rule_hash() == b.rule.rule_hash()
            row["identical_rules"] = same
            row["comparison"] = None if same else compare(a.rule, b.rule)
        else:
            row["identical_rules"] = False
            row["comparison"] = None
        out.append(row)
    both = [r for r in out if r["A"]["ok"] and r["B"]["ok"]]
    summary = {"texts": len(out), "both_compiled": len(both),
               "refused_by": {m: sum(not r[k]["ok"] for r in out) for k, m in zip("AB", MODELS, strict=True)},
               "identical": sum(r["identical_rules"] for r in both),
               "behave_differently": sum(bool(r["comparison"] and r["comparison"]["disagree"]) for r in both),
               "with_minimal_pair": sum(bool(r["comparison"] and r["comparison"]["pairs"]) for r in both)}
    return {"schema": "eventproof-ambiguity/1", "preregistration": "benchmark/ambiguity/PREREGISTRATION.md",
            "models": {"A": MODELS[0], "B": MODELS[1]}, "suite": {"families": list(FAMILIES), "seeds": [0, 29],
                                                                 "tracks": "ground truth (oracle)"},
            "live_calls_this_run": live, "summary": summary, "texts": out}


def main() -> None:
    from eventproof.validation.evaluate import _git_head

    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--max-live-calls", type=int, default=0)
    r.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"{a.out} exists; the first report is kept")
    rep = run(a.max_live_calls)
    rep["code_commit"] = _git_head()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, indent=2) + "\n")
    print(json.dumps(rep["summary"]))


if __name__ == "__main__":
    main()
