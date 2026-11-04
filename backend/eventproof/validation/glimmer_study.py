"""Muse Glimmer (Meta open weights, served locally by llama.cpp) on the two statute studies, unchanged
(pre-registered in `benchmark/glimmer/PREREGISTRATION.md`). Only the model and the endpoint differ: the law study
(30 labelled real cars) and the INTERACTION repeats (1,268 approaches) run with their own code.

    llama-server -m Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf --port 8081 --jinja -c 32768
    uv run python -m eventproof.validation.glimmer_study run --base-url http://127.0.0.1:8081/v1
    uv run python -m eventproof.validation.glimmer_study report          # recompute from the recordings, 0 calls
"""
from __future__ import annotations

import argparse
import dataclasses
import json

from eventproof.meta.client import MetaSettings
from eventproof.validation import interaction_repeats, law_study
from eventproof.validation.evaluate import ROOT, _git_head
from eventproof.validation.interaction import load_data, sha, write_json
from eventproof.validation.real_video import LimitedMuseCompiler

OUT = ROOT / "benchmark" / "glimmer"
MODEL = "muse-glimmer-30b-q4km"
RUNS = 3


def settings(base_url: str) -> MetaSettings:
    # a local OpenAI-compatible server needs no key; any non-empty value passes the client check
    return dataclasses.replace(MetaSettings.from_env(), api_key="local", base_url=base_url, muse_model=MODEL)


def use_glimmer(base_url: str, max_live: int) -> None:
    """Point both studies at Glimmer and at this study's own recordings (their committed reports stay untouched)."""
    law_study.MODELS = (MODEL,)
    law_study.compiler = lambda model, live: LimitedMuseCompiler(settings(base_url), cache_dir=OUT / "law_cache",
                                                                 max_live_calls=live, law=True)
    interaction_repeats.MODELS = (MODEL,)
    interaction_repeats.RUNS = RUNS
    interaction_repeats.OUT = OUT / "interaction"


def law(base_url: str, max_live: int) -> dict:
    use_glimmer(base_url, max_live)
    res = law_study.study(max_live)
    return {"schema": "eventproof-glimmer-law/1", "preregistration": "benchmark/glimmer/PREREGISTRATION.md",
            "model": MODEL, "summary": law_study.summary(res["rows"]), **res}


def interaction_compiles(base_url: str) -> dict:
    use_glimmer(base_url, 0)
    s = settings(base_url)
    statutes = {x["id"]: x for x in law_study.statutes()}
    runs = [interaction_repeats.compile_one(s, statutes[st], MODEL, i, interaction_repeats.CALLS_PER_RUN)
            for st, _m, i in interaction_repeats.plan()]
    return {"schema": "eventproof-interaction-repeats-compiles/1",
            "preregistration": "benchmark/glimmer/PREREGISTRATION.md",
            "preregistration_sha256": sha(OUT / "PREREGISTRATION.md"),
            "live_calls": sum(r["live_calls"] for r in runs), "code_commit": _git_head(), "runs": runs}


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--base-url", required=True)
    r.add_argument("--arm", choices=("law", "interaction", "both"), default="both")
    sub.add_parser("report")
    a = ap.parse_args()
    if a.cmd == "run":
        if a.arm in ("law", "both"):
            rep = law(a.base_url, 8)
            rep["code_commit"] = _git_head()
            write_json(OUT / "law_report.json", rep)
            print(json.dumps(rep["summary"], indent=1))
        if a.arm in ("interaction", "both"):
            if (OUT / "interaction" / "compiles.json").exists():
                raise SystemExit("first run is kept")
            write_json(OUT / "interaction" / "compiles.json", interaction_compiles(a.base_url))
    use_glimmer("http://unused", 0)
    rep = law_study.study(0)
    write_json(OUT / "law_report.json", {**json.loads((OUT / "law_report.json").read_text()),
                                         "summary": law_study.summary(rep["rows"])})
    comp = OUT / "interaction" / "compiles.json"
    if comp.exists():
        ir = interaction_repeats.recompute(json.loads(comp.read_text()), load_data())
        write_json(OUT / "interaction" / "report.json", ir)
        print(json.dumps({k: ir[k] for k in ("overall", "groups")}, indent=1)[:3000])


if __name__ == "__main__":
    main()
