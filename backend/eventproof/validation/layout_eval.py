"""Does a layout proposed by Muse Spark (from the first frame + rule text) give the same verdicts as the hand-drawn one?
Pre-registered in `benchmark/layout/PREREGISTRATION.md`.

For every labelled real clip: Muse Spark proposes a zone and a line; the rule that was compiled for the clip keeps its
logic and thresholds, only its geometry is replaced by the proposal; the committed SAM 3.1 tracks are judged again and
compared with the frozen labels (same matching as `real_video`). Reported per clip: zone IoU and line angle/offset against
the hand layout, labelled objects right with the hand layout and with the proposed one.

    uv run python -m eventproof.validation.layout_eval run --max-live-calls 6 --out ../benchmark/layout/report.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eventproof.engine.evaluator import evaluate
from eventproof.meta.layout_proposer import LayoutProposer, first_frame_png, line_agreement, polygon_iou
from eventproof.meta.muse_rules import Layout
from eventproof.schemas.rules import VisualRule
from eventproof.schemas.tracks import TrackSet
from eventproof.validation.evaluate import ROOT, _git_head, wilson
from eventproof.validation.real_video import ClipLabel, load_labels, match_objects, perceive

SETS = (("benchmark/real/novisad", "report_novisad.json"), ("benchmark/real/traffic_v2", "report_wroclaw.json"),
        ("benchmark/real/traffic_v3", "report_wroclaw_w3.json"))
OUT_DIR = ROOT / "benchmark" / "layout"


def with_geometry(rule: VisualRule, layout: Layout) -> VisualRule:
    """Same rule, geometry from `layout` (matched by id)."""
    zones = {z.zone.id: z.zone for z in layout.zones}
    lines = {ln.line.id: ln.line for ln in layout.lines}
    return rule.model_copy(update={"zones": [zones.get(z.id, z) for z in rule.zones],
                                   "lines": [lines.get(ln.id, ln) for ln in rule.lines]})


def score(label: ClipLabel, rule: VisualRule, tracks: TrackSet) -> dict:
    verdict = {o.object_id: o.verdict for o in evaluate(rule, tracks).objects}
    pair = dict(match_objects(label.objects, perceive(rule, tracks, label.packing_line)).pairs)
    rows = [(verdict.get(pair.get(i)), o.intended) for i, o in enumerate(label.objects)]
    return {"right": sum(v == w for v, w in rows), "abstained": sum(v == "UNKNOWN" for v, _ in rows),
            "missing": sum(v is None for v, _ in rows)}


def run(max_live: int, proposer: LayoutProposer | None = None, frames: dict[str, bytes] | None = None) -> dict:
    proposer = proposer or LayoutProposer(cache_dir=OUT_DIR / "cache", max_live_calls=max_live)
    clips = []
    for folder, rep_name in SETS:
        d = ROOT / folder
        labels = {lb.clip: (p, lb) for p, lb in load_labels(d / "labels")}
        for c in json.loads((d / rep_name).read_text())["clips"]:
            _, lab = labels[c["clip"]]
            run_dir = d / "runs" / c["run_id"]
            rule = VisualRule.model_validate(json.loads((run_dir / "evidence.json").read_text())["rule"]["compiled_rule"])
            tracks = TrackSet.model_validate_json((run_dir / "tracks.json").read_text())
            png = (frames or {}).get(c["clip"]) or first_frame_png(d / "videos" / c["clip"])
            prop = proposer.propose(png, lab.rule_text)
            pl = prop["layout"]
            hz, hl = lab.layout.zones[0].zone, lab.layout.lines[0].line
            pz, plin = pl.zones[0].zone, pl.lines[0].line
            clips.append({
                "clip": c["clip"], "set": d.name, "labelled": len(lab.objects), "request_id": prop["request_id"],
                "proposed": json.loads(pl.model_dump_json()), "assumptions": prop["assumptions"],
                "zone_iou": round(polygon_iou(hz.polygon, pz.polygon), 3),
                "line": line_agreement((hl.a, hl.b), (plin.a, plin.b)),
                "hand": score(lab, rule, tracks), "proposed_layout": score(lab, with_geometry(rule, pl), tracks)})
    n = sum(c["labelled"] for c in clips)
    tot = {k: sum(c[k]["right"] for c in clips) for k in ("hand", "proposed_layout")}
    return {"schema": "eventproof-layout-eval/1", "preregistration": "benchmark/layout/PREREGISTRATION.md",
            "model": proposer.settings.muse_model, "live_calls_this_run": proposer.live_calls, "labelled": n,
            "right": tot, "right_ci95": {k: wilson(v, n) for k, v in tot.items()},
            "median_zone_iou": sorted(c["zone_iou"] for c in clips)[len(clips) // 2], "clips": clips}


def main() -> None:
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
    print(json.dumps({k: rep[k] for k in ("labelled", "right", "median_zone_iou", "live_calls_this_run")}))


if __name__ == "__main__":
    main()
