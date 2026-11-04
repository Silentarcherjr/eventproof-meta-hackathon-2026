"""Compile the law as written: verbatim stop-line statutes -> Muse Spark and Muse Wonder (law mode: every value QUOTED
from the statute, verified as an exact substring, or ASSUMED) -> the 30 labelled real cars.
Pre-registered in `benchmark/law/PREREGISTRATION.md`.

For each statute x model x scene layout (Novi Sad, Wroclaw): the compiled rule, its provenance, and per labelled car the
verdict and whether that verdict flips when a value the model marked ASSUMED is varied (engine re-run, no model):
"how many real tickets hang on a number the law never wrote". Truth for a car under these statutes: PASS if it stopped
(labelled stood_still_s > 0) or never crossed, VIOLATION if it crossed without stopping (on these clips this equals the
frozen labels: every car that stopped stood >= 4 s).

    uv run python -m eventproof.validation.law_study run --max-live 12 --out ../benchmark/law/report.json
    uv run python -m eventproof.validation.law_study report      # recompute from the cached compiles, 0 API calls
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path

from eventproof.engine.evaluator import evaluate
from eventproof.meta.client import MetaSettings
from eventproof.meta.muse_rules import Layout, MuseRuleCompiler, RuleCompileError
from eventproof.review.robustness import robustness
from eventproof.schemas.tracks import TrackSet
from eventproof.validation.evaluate import ROOT, _git_head
from eventproof.validation.real_video import LimitedMuseCompiler, LiveCallLimit, load_labels

LAW = ROOT / "benchmark" / "law"
REAL = ROOT / "benchmark" / "real"
SETS = ("novisad", "traffic_v2", "traffic_v3")
MODELS = ("muse-spark-1.3", "muse-wonder-1.0")
# which robustness variant families vary which provenance parameter
FAMILY_PARAM = {"min_ms": "DWELL.min_ms", "stillness": "DWELL.max_speed", "stillness_meaning": "DWELL.max_speed",
                "anchor": "anchor", "line_shift": "CROSSES.line"}


def statutes() -> list[dict]:
    return json.loads((LAW / "statutes.json").read_text())["statutes"]


def cars() -> list[dict]:
    """Every labelled car of the traffic sets, with its clip's layout, run (anchor_v4) and matched track."""
    out = []
    for s in SETS:
        labels = {lb.clip: lb for _, lb in load_labels(REAL / s / "labels")}
        rep = json.loads((REAL / "anchor_v4" / f"report_{s}.json").read_text())
        for c in rep["clips"]:
            lab = labels[c["clip"]]
            for row, obj in zip(c["objects"]["labeled"], lab.objects, strict=True):
                out.append({"set": s, "clip": c["clip"], "run_id": c["run_id"], "layout": lab.layout,
                            "object_id": row["matched_object_id"], "description": obj.description,
                            "truth": "PASS" if (not obj.crosses_packing or obj.stood_still_s > 0) else "VIOLATION"})
    return out


def compiler(model: str, max_live: int) -> MuseRuleCompiler:
    s = dataclasses.replace(MetaSettings.from_env(), muse_model=model)
    return LimitedMuseCompiler(s, cache_dir=LAW / "cache" / model, max_live_calls=max_live, law=True)


def study(max_live: int = 0) -> dict:
    allc = cars()
    layouts: dict[str, Layout] = {}
    for c in allc:
        layouts.setdefault(json.dumps(c["layout"].model_dump(mode="json"), sort_keys=True), c["layout"])
    tracks = {c["run_id"]: TrackSet.model_validate_json(
        (REAL / "anchor_v4" / "runs" / c["run_id"] / "tracks.json").read_text()) for c in allc}
    rows, live = [], 0
    for st in statutes():
        for model in MODELS:
            comp = compiler(model, max(0, max_live - live))
            for lkey, layout in layouts.items():
                try:
                    res = comp.compile(st["text"], layout)
                except (RuleCompileError, LiveCallLimit) as e:
                    rows.append({"statute": st["id"], "model": model, "compiled": False,
                                 "error": f"{type(e).__name__}: {e}"[:300]})
                    continue
                finally:
                    live += comp.live_calls
                    comp.live_calls = 0
                rule, prov = res.rule, res.raw_output.get("provenance", [])
                assumed = {p["param"].split("[")[0] for p in prov if p["source"] == "ASSUMED"}
                group = [c for c in allc if json.dumps(c["layout"].model_dump(mode="json"), sort_keys=True) == lkey]
                per_car = []
                for run_id in sorted({c["run_id"] for c in group}):
                    t = tracks[run_id]
                    verdict = {o.object_id: o.verdict for o in evaluate(rule, t).objects}
                    rb = {x.object_id: x for x in robustness(rule, t)}
                    for c in (c for c in group if c["run_id"] == run_id):
                        oid = c["object_id"]
                        v = verdict.get(oid) if oid is not None else None
                        flips = rb[oid].flips if oid is not None and oid in rb else []
                        hang = sorted({f["family"] for f in flips if f["verdict"] != "UNKNOWN"
                                       and FAMILY_PARAM.get(f["family"]) in assumed})
                        per_car.append({"clip": c["clip"], "object_id": oid, "description": c["description"],
                                        "truth": c["truth"], "verdict": v, "right": v == c["truth"],
                                        "hangs_on_assumed": hang})
                rows.append({"statute": st["id"], "model": model, "compiled": True, "cached": res.cached,
                             "request_ids": res.request_ids, "layout": lkey[:60],
                             "rule": json.loads(rule.canonical_json()), "provenance": prov,
                             "assumptions": res.assumptions, "cars": per_car})
    return {"rows": rows, "live_calls": live}


def summary(rows: list[dict]) -> list[dict]:
    out = []
    for st in statutes():
        for model in MODELS:
            rs = [r for r in rows if r["statute"] == st["id"] and r["model"] == model]
            cs = [c for r in rs if r["compiled"] for c in r["cars"]]
            prov = [p for r in rs if r["compiled"] for p in r["provenance"]]
            out.append({"statute": st["id"], "model": model, "compiled": sum(r["compiled"] for r in rs), "of": len(rs),
                        "cars": len(cs), "right": sum(c["right"] for c in cs),
                        "wrong": sum(c["verdict"] not in (None, "UNKNOWN") and not c["right"] for c in cs),
                        "hang_on_assumed": sum(bool(c["hangs_on_assumed"]) for c in cs),
                        "quoted": sum(p["source"] == "QUOTED" for p in prov),
                        "assumed": sum(p["source"] == "ASSUMED" for p in prov)})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--max-live", type=int, default=0)
    r.add_argument("--out", type=Path, required=True)
    sub.add_parser("report")
    a = ap.parse_args()
    if a.cmd == "run" and a.out.exists():
        raise SystemExit(f"{a.out} exists; the first report is kept")
    res = study(a.max_live if a.cmd == "run" else 0)
    rep = {"schema": "eventproof-law-study/1", "preregistration": "benchmark/law/PREREGISTRATION.md",
           "summary": summary(res["rows"]), **res}
    if a.cmd == "run":
        rep["code_commit"] = _git_head()
        a.out.write_text(json.dumps(rep, indent=2) + "\n")
    print(json.dumps(rep["summary"], indent=1))


if __name__ == "__main__":
    main()
