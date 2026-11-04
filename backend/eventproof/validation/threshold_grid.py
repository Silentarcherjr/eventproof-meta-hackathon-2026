"""The numbers the law never wrote, as a grid: re-judge the 30 labelled real cars under every stop time x "still" speed,
with the rule Muse Spark compiled from each verbatim statute (benchmark/law). Deterministic, no model.
Pre-registered in `benchmark/law/PREREGISTRATION.md` (addendum 1).

    uv run python -m eventproof.validation.threshold_grid --out ../benchmark/law/grid.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eventproof.engine.evaluator import evaluate
from eventproof.review.robustness import _map_events
from eventproof.schemas.rules import VisualRule
from eventproof.schemas.tracks import TrackSet
from eventproof.validation.law_study import LAW, REAL, cars, statutes

TIMES_S = [round(0.25 * i, 2) for i in range(13)]  # 0.0 .. 3.0 s; 0.0 is evaluated as 1 ms (DWELL needs > 0)
SPEEDS = [round(0.01 * i, 2) for i in range(1, 21)] + [None]  # 0.01 .. 0.20 frame widths/s, then "any motion"
CODE = {"VIOLATION": "V", "PASS": "P", "UNKNOWN": "U", None: "-"}


def _set(rule: VisualRule, min_s: float, speed: float | None) -> VisualRule:
    r = _map_events(rule, lambda e: e | {"min_ms": max(1.0, min_s * 1000), "max_speed": speed}
                    if e.get("op") == "DWELL" else None)
    return r or rule


def grid() -> dict:
    rep = json.loads((LAW / "report.json").read_text())
    allc = cars()
    out = {"schema": "eventproof-law-grid/1", "preregistration": "benchmark/law/PREREGISTRATION.md (addendum 1)",
           "times_s": TIMES_S, "speeds": SPEEDS, "cars": [{k: c[k] for k in ("clip", "object_id", "description", "truth")}
                                                          for c in allc], "statutes": []}
    for st in statutes():
        rows = [r for r in rep["rows"] if r["statute"] == st["id"] and r["model"] == "muse-spark-1.3" and r["compiled"]]
        by_clip = {}
        for r in rows:
            rule = VisualRule.model_validate(r["rule"])
            for c in r["cars"]:
                by_clip.setdefault(c["clip"], rule)
        dwell = [e for e in json.dumps(rows[0]["rule"]["check"]).split('"op": "DWELL"')][1:]
        spark = {"min_s": 1.0, "speed": 0.05} if dwell else None
        tracks = {}
        cells = []
        for t_s in TIMES_S:
            for v in SPEEDS:
                codes = []
                for c in allc:
                    rule = _set(by_clip[c["clip"]], t_s, v)
                    if c["run_id"] not in tracks:
                        path = REAL / "anchor_v4" / "runs" / c["run_id"] / "tracks.json"
                        ts = TrackSet.model_validate_json(path.read_text())
                        tracks[c["run_id"]] = ts.model_copy(update={"frames": [
                            f.model_copy(update={"label": rule.entity.concept}) for f in ts.frames]})
                    key = (c["run_id"], t_s, v)
                    if key not in _memo:
                        _memo[key] = {o.object_id: o.verdict for o in evaluate(rule, tracks[c["run_id"]]).objects}
                    codes.append(CODE[_memo[key].get(c["object_id"]) if c["object_id"] is not None else None])
                truth = [c["truth"][0] for c in allc]
                cells.append({"min_s": t_s, "speed": v, "verdicts": "".join(codes),
                              "tickets": codes.count("V"),
                              "right": sum(a == b for a, b in zip(codes, truth, strict=True)),
                              "false_tickets": sum(a == "V" and b == "P" for a, b in zip(codes, truth, strict=True)),
                              "missed": sum(a == "P" and b == "V" for a, b in zip(codes, truth, strict=True)),
                              "abstained": codes.count("U"), "untracked": codes.count("-")})
        _memo.clear()
        out["statutes"].append({"id": st["id"], "citation": st["citation"], "text": st["text"], "spark_values": spark,
                                "cells": cells})
    return out


_memo: dict = {}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    g = grid()
    a.out.write_text(json.dumps(g) + "\n")
    for s in g["statutes"]:
        c = next(x for x in s["cells"] if x["min_s"] == 1.0 and x["speed"] == 0.05)
        best = max(x["right"] for x in s["cells"])
        print(s["id"], "at Spark's values:", c["right"], "right,", c["tickets"], "tickets;", "best cell right:", best,
              "; cells with best:", sum(x["right"] == best for x in s["cells"]), "of", len(s["cells"]))


if __name__ == "__main__":
    main()
