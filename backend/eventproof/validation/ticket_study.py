"""Would these tickets hold up? Robustness of every labelled real verdict, and Muse Spark arguing the defense of every
real ticket. Pre-registered in `benchmark/tickets/PREREGISTRATION.md`.

Objects: the 46 labelled real objects of the anchor-field re-run (benchmark/real/anchor_v4). For each matched object,
`review.robustness` gives ROBUST / FRAGILE / DEPENDS_ON_THRESHOLD / DEPENDS_ON_MEANING / UNSTABLE (no model). For each
ticket (a VIOLATION verdict on a labelled object), Muse Spark picks and argues challenges from the same closed menu;
the engine says which of its challenges overturn the ticket.

    uv run python -m eventproof.validation.ticket_study run --max-live 25 --out ../benchmark/tickets/report.json
    uv run python -m eventproof.validation.ticket_study report     # recompute from cache, 0 API calls
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from eventproof.engine.evaluator import evaluate
from eventproof.meta.muse_defense import MuseDefense
from eventproof.review.robustness import robustness, variants
from eventproof.schemas.rules import VisualRule
from eventproof.schemas.tracks import TrackSet
from eventproof.validation.evaluate import ROOT, _git_head

REAL = ROOT / "benchmark" / "real" / "anchor_v4"
OUT = ROOT / "benchmark" / "tickets"
SETS = ("novisad", "traffic_v2", "traffic_v3", "domains", "santos")


def vid(family: str, value) -> str:
    return f"{family}:{value}"


def study(max_live: int = 0) -> dict:
    defense = MuseDefense(cache_dir=OUT / "cache", max_live_calls=max_live)
    rows = []
    for s in SETS:
        rep = json.loads((REAL / f"report_{s}.json").read_text())
        for c in rep["clips"]:
            run = REAL / "runs" / c["run_id"]
            ev = json.loads((run / "evidence.json").read_text())
            rule = VisualRule.model_validate(ev["rule"]["compiled_rule"])
            tracks = TrackSet.model_validate_json((run / "tracks.json").read_text())
            rb = {x.object_id: x for x in robustness(rule, tracks)}
            verdicts = {o.object_id: o for o in evaluate(rule, tracks).objects}
            menu = [{"id": vid(v.family, v.value), "label": v.label} for v, _, _ in variants(rule, tracks.video.height)]
            for row in c["objects"]["labeled"]:
                oid = row["matched_object_id"]
                r = {"set": s, "clip": c["clip"], "object_id": oid, "description": row["description"],
                     "intended": row["intended"], "verdict": row["before"],
                     "correct": "untracked" if oid is None else "right" if row["agree_before"]
                     else "abstained" if row["before"] == "UNKNOWN" else "wrong"}
                if oid is not None:
                    x = rb[oid]
                    r |= {"status": x.status, "smallest_flip": x.smallest_flip,
                          "flipping": sorted({vid(f["family"], f["value"]) for f in x.flips if f["verdict"] != "UNKNOWN"})}
                    if row["before"] == "VIOLATION":
                        d = defense.argue(ev["rule"]["text"], ev["rule"]["compiled_rule"],
                                          verdicts[oid].model_dump(mode="json"), menu)
                        out = d["output"]
                        chosen = [ch["id"] for ch in out["challenges"]]
                        r["defense"] = {"chosen": chosen, "strongest": out["strongest"], "concede": out["concede"],
                                        "arguments": out["challenges"], "concession": out["concession"],
                                        "request_id": d.get("request_id"), "cached": d["cached"],
                                        "strongest_overturns": out["strongest"] in r["flipping"],
                                        "any_overturns": any(ch in r["flipping"] for ch in chosen)}
                rows.append(r)
    return {"rows": rows, "live_calls": defense.live_calls}


def summary(rows: list[dict]) -> dict:
    tracked = [r for r in rows if r["correct"] != "untracked"]
    tickets = [r for r in rows if "defense" in r]
    beatable = [r for r in tickets if r["flipping"]]
    wrong_t = [r for r in tickets if r["correct"] == "wrong"]
    return {
        "objects": len(rows), "untracked": len(rows) - len(tracked),
        "status_by_correctness": {f"{k[0]}/{k[1]}": v for k, v in
                                  sorted(Counter((r["status"], r["correct"]) for r in tracked).items())},
        "H1_wrong_not_robust": f"{sum(r['status'] != 'ROBUST' for r in tracked if r['correct'] == 'wrong')}/"
                               f"{sum(r['correct'] == 'wrong' for r in tracked)}",
        "H2_wrong_among_robust": sum(r["correct"] == "wrong" for r in tracked if r["status"] == "ROBUST"),
        "robust": sum(r["status"] == "ROBUST" for r in tracked),
        "tickets": len(tickets), "tickets_beatable_by_menu": len(beatable),
        "defense_strongest_overturns": sum(r["defense"]["strongest_overturns"] for r in tickets),
        "defense_any_overturns": sum(r["defense"]["any_overturns"] for r in tickets),
        "defense_found_on_beatable": f"{sum(r['defense']['any_overturns'] for r in beatable)}/{len(beatable)}",
        "defense_conceded_on_unbeatable": f"{sum(r['defense']['concede'] for r in tickets if not r['flipping'])}/"
                                          f"{sum(1 for r in tickets if not r['flipping'])}",
        "wrong_tickets_overturned_by_defense": f"{sum(r['defense']['any_overturns'] for r in wrong_t)}/{len(wrong_t)}",
    }


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
    rep = {"schema": "eventproof-ticket-study/1", "preregistration": "benchmark/tickets/PREREGISTRATION.md",
           "summary": summary(res["rows"]), **res}
    if a.cmd == "run":
        rep["code_commit"] = _git_head()
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(rep, indent=2) + "\n")
    print(json.dumps(rep["summary"], indent=1))


if __name__ == "__main__":
    main()
