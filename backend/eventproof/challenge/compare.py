"""Run the same scenes through mock perception and live SAM 3.1 and compare against ground truth.

    uv run python -m eventproof.challenge.compare --cases tailgate:0,2,3,4,5 occluded_station:1,2,6,8,10 \
        --max-live-calls 10 --out ../benchmark/reports/2026-10-27_sam_vs_mock.json

SAM results are cached by video sha256, so re-running is free; the report says how many calls were live.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from eventproof.challenge.families import FAMILIES
from eventproof.challenge.render import ground_truth
from eventproof.challenge.replay import identity_events
from eventproof.challenge.runner import inspection_rule, mock_perceiver, run_case
from eventproof.perception.mock import iou
from eventproof.perception.sam import SamTracker, sam_perceiver
from eventproof.schemas.tracks import TrackSet


def box_quality(gt: TrackSet, ts: TrackSet) -> dict:
    """Per visible ground-truth box: best IoU with any perceived box on that frame."""
    by: dict[int, list] = {}
    for f in ts.frames:
        by.setdefault(f.frame_index, []).append(f)
    best = [max((iou(g.box, p.box) for p in by.get(g.frame_index, [])), default=0.0)
            for g in gt.frames if not g.occluded]
    n_gt = sum(not g.occluded for g in gt.frames)
    return {"gt_visible_boxes": n_gt, "perceived_boxes": len(ts.frames),
            "matched_iou50": sum(b >= 0.5 for b in best),
            "median_iou": round(statistics.median(best), 3) if best else None,
            "track_ids": sorted({f.object_id for f in ts.frames})}


def compare(cases: list[tuple[str, int]], tracker: SamTracker, dwell_ms: float = 1500.0) -> list[dict]:
    sam = sam_perceiver(tracker)
    rows = []
    for fam, seed in cases:
        scene = FAMILIES[fam](seed)
        gt = ground_truth(scene)
        rule = inspection_rule(scene, dwell_ms)
        row = {"family": fam, "seed": seed, "scene_sha256": scene.scene_hash(), "notes": scene.notes}
        for name, perceiver in (("mock", mock_perceiver), ("sam", sam)):
            tracks = perceiver(scene, gt)
            r = run_case(scene, rule, lambda s, g, t=tracks: t)
            row[name] = {"source": tracks.source, "source_ref": tracks.source_ref, "intended": r.intended,
                         "detector_verdict": r.detector_verdict, "outcome": r.outcome,
                         "identity_events": [e.model_dump() for e in identity_events(gt, tracks)][:8],
                         **box_quality(gt, tracks)}
        rows.append(row)
    return rows


def _cases(specs: list[str]) -> list[tuple[str, int]]:
    out = []
    for spec in specs:
        fam, _, seeds = spec.partition(":")
        out += [(fam, int(s)) for s in seeds.split(",")]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", nargs="+", required=True, help="family:seed,seed,...")
    ap.add_argument("--max-live-calls", type=int, default=0)
    ap.add_argument("--dwell-ms", type=float, default=1500.0)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    tracker = SamTracker(max_live_calls=args.max_live_calls)
    rows = compare(_cases(args.cases), tracker, args.dwell_ms)
    report = {"perception": ["mock (NOT SAM)", "sam-3.1 (live Meta API)"], "live_sam_calls_this_run": tracker.live_calls,
              "dwell_ms": args.dwell_ms, "cases": rows}
    if args.out:
        args.out.write_text(json.dumps(report, indent=2) + "\n")
    for r in rows:
        m, s = r["mock"], r["sam"]
        print(f"{r['family']:>16}-{r['seed']:<3} truth {m['intended']:4}  mock {m['detector_verdict']:7} {m['outcome']:16}"
              f" sam {s['detector_verdict']:7} {s['outcome']:16} sam ids {s['track_ids']} "
              f"iou {s['median_iou']} matched {s['matched_iou50']}/{s['gt_visible_boxes']}")
    print(f"live SAM calls this run: {tracker.live_calls}")


if __name__ == "__main__":
    main()
