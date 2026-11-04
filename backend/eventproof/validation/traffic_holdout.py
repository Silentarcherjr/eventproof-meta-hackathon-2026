"""Sealed traffic holdout: the rule Muse Spark compiles vs the generator's stated contract, on perfect synthetic tracks
(pre-registered in `benchmark/traffic_sim/HOLDOUT_PREREGISTRATION.md`). Measures the rule, not perception.

    uv run python -m eventproof.validation.traffic_holdout --max-live 1 --out ../benchmark/traffic_sim/holdout_eval/report.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from eventproof.challenge.runner import bind_rule, run_case
from eventproof.challenge.scene import SceneSpec
from eventproof.challenge.traffic import perfect_perceiver, traffic_rule
from eventproof.meta.client import MetaSettings
from eventproof.meta.muse_rules import Layout
from eventproof.validation.evaluate import ROOT, _git_head
from eventproof.validation.real_video import LimitedMuseCompiler

SIM = ROOT / "benchmark" / "traffic_sim"
RULE_TEXT = "Every car must wait at least 1.5 seconds in the waiting zone before it crosses the stop line."


def layout(scene: SceneSpec) -> Layout:
    z, ln = scene.zones[0], scene.lines[0]
    return Layout.model_validate({
        "zones": [{"zone": {"id": z.id, "polygon": [list(p) for p in z.polygon]},
                   "description": "waiting zone: the approach lane just before the stop line (top-down view)"}],
        "lines": [{"line": {"id": ln.id, "a": list(ln.a), "b": list(ln.b)},
                   "description": "stop line across the approach; cars travel from left to right of the frame"}]})


def scenes() -> list[SceneSpec]:
    return [SceneSpec.model_validate_json(p.read_text()) for p in sorted((SIM / "v1" / "holdout").glob("*/scene.json"))]


def study(max_live: int) -> dict:
    sc = scenes()
    comp = LimitedMuseCompiler(MetaSettings.from_env(), cache_dir=SIM / "holdout_eval" / "cache",
                               max_live_calls=max_live, anchor_field=True)
    res = comp.compile(RULE_TEXT, layout(sc[0]))
    rows = {"muse_spark": [], "contract_rule": []}
    for s in sc:
        for name, rule in (("muse_spark", bind_rule(res.rule, s)), ("contract_rule", traffic_rule(s))):
            r = run_case(s, rule, perfect_perceiver)
            rows[name].append({"family": s.family, "seed": s.seed, "intended": r.intended,
                               "verdict": r.detector_verdict, "outcome": r.outcome})
    summary = {}
    for name, rs in rows.items():
        by = {}
        for r in rs:
            by.setdefault(r["family"], Counter())[r["outcome"]] += 1
        summary[name] = {"total": dict(Counter(r["outcome"] for r in rs)), "by_family": {f: dict(c) for f, c in by.items()}}
    return {"schema": "eventproof-traffic-holdout/1", "preregistration": "benchmark/traffic_sim/HOLDOUT_PREREGISTRATION.md",
            "perception": "synthetic perfect tracks (NOT SAM)", "scenes": len(sc), "rule_text": RULE_TEXT,
            "muse_rule": json.loads(res.rule.canonical_json()), "assumptions": res.assumptions,
            "request_ids": res.request_ids, "cached": res.cached, "live_calls": comp.live_calls,
            "summary": summary, "rows": rows, "code_commit": _git_head()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-live", type=int, default=0)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists() and a.max_live:
        raise SystemExit(f"{a.out} exists; the first report is kept")
    rep = study(a.max_live)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps(rep["summary"], indent=1))


if __name__ == "__main__":
    main()
