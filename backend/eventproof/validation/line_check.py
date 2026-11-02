"""Line-crossing check of SAM 3.1 on real footage against hand labels (pre-registered in
`benchmark/real/pexels/PREREGISTRATION.md`; perception only, reported separately).

    uv run python -m eventproof.validation.line_check run --max-live-sam-calls 1 \
        --out ../benchmark/real/pexels/report_pexels.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eventproof.perception.sam import SamTracker, sha256_file
from eventproof.schemas.tracks import TrackSet, VideoInfo
from eventproof.validation.evaluate import ROOT, _git_head, sha256

DIR = ROOT / "benchmark" / "real" / "pexels"


def crossings(ts: TrackSet, x0: float) -> list[dict]:
    """Every right-to-left passage of a track's box center over x = x0 (fraction of width), between consecutive
    detections of that track."""
    by: dict[int, list] = {}
    for f in sorted(ts.frames, key=lambda f: f.frame_index):
        by.setdefault(f.object_id, []).append(f)
    out = []
    w = ts.video.width
    for oid, fs in by.items():
        for a, b in zip(fs, fs[1:], strict=False):
            if (a.box.x1 + a.box.x2) / 2 / w > x0 >= (b.box.x1 + b.box.x2) / 2 / w:
                out.append({"track_id": oid, "frame": b.frame_index, "t_s": round(b.timestamp_ms / 1000, 2)})
    return sorted(out, key=lambda c: c["t_s"])


def match(labels: list[float], found: list[float], tol: float) -> list[tuple[int, int]]:
    """Order-preserving one-to-one matching with |dt| <= tol: most pairs first, then smallest total |dt|."""
    n, m = len(labels), len(found)
    best = [[(0, 0.0)] * (m + 1) for _ in range(n + 1)]  # (pairs, -sum|dt|)
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            cand = [best[i + 1][j], best[i][j + 1]]
            dt = abs(labels[i] - found[j])
            if dt <= tol:
                k, s = best[i + 1][j + 1]
                cand.append((k + 1, s - dt))
            best[i][j] = max(cand)
    pairs, i, j = [], 0, 0
    while i < n and j < m:
        dt = abs(labels[i] - found[j])
        if dt <= tol and best[i][j] == (best[i + 1][j + 1][0] + 1, best[i + 1][j + 1][1] - dt):
            pairs.append((i, j))
            i, j = i + 1, j + 1
        elif best[i][j] == best[i + 1][j]:
            i += 1
        else:
            j += 1
    return pairs


def score(clip: dict, ts: TrackSet, lab: dict) -> dict:
    lo, hi = lab["scored_window_s"]
    found = crossings(ts, lab["line"]["x"])
    truth = clip["crossings_s"]
    pairs = match(truth, [c["t_s"] for c in found], lab["match_tolerance_s"])
    matched_found = {j for _, j in pairs}
    false = [c for j, c in enumerate(found) if j not in matched_found and lo <= c["t_s"] <= hi]
    dts = sorted(abs(truth[i] - found[j]["t_s"]) for i, j in pairs)
    return {
        "labels": len(truth), "matched": len(pairs), "missed": [truth[i] for i in range(len(truth))
                                                               if i not in {i for i, _ in pairs}],
        "false_crossings_in_window": false,
        "median_abs_dt_s": dts[len(dts) // 2] if dts else None,
        "distinct_track_ids_matched": len({found[j]["track_id"] for _, j in pairs}),
        "pairs": [{"label_s": truth[i], "sam": found[j]} for i, j in pairs],
        "all_sam_crossings": found,
        "sam_tracks": len({f.object_id for f in ts.frames}), "sam_boxes": len(ts.frames),
    }


def run(max_live: int, tracker: SamTracker | None = None) -> dict:
    lab = json.loads((DIR / "labels.json").read_text())
    tracker = tracker or SamTracker(cache_dir=DIR / "sam_cache", max_live_calls=max_live)
    out = {"preregistration": "benchmark/real/pexels/PREREGISTRATION.md", "labels_sha256": sha256(DIR / "labels.json"),
           "perception": "sam-3.1 (live Meta API, raw output cached in benchmark/real/pexels/sam_cache)", "clips": {}}
    for name, clip in lab["clips"].items():
        video = DIR / "videos" / f"{name}.mp4"
        if sha256_file(video) != clip["prepared_sha256"]:
            raise SystemExit(f"{video} does not match the labelled sha256")
        v = clip["video"]
        ts = tracker.tracks(video, clip["prompt"], VideoInfo(width=v["width"], height=v["height"], fps=v["fps"],
                                                             frame_count=v["frames"]))
        out["clips"][name] = {"source_ref": ts.source_ref, **score(clip, ts, lab)}
    out["live_sam_calls_this_run"] = tracker.live_calls
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--max-live-sam-calls", type=int, default=0)
    r.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit(f"{args.out} exists; the first report is kept")
    rep = run(args.max_live_sam_calls)
    rep["code_commit"] = _git_head()
    args.out.write_text(json.dumps(rep, indent=2) + "\n")
    print(json.dumps({k: {kk: c[kk] for kk in ("labels", "matched", "median_abs_dt_s", "distinct_track_ids_matched")}
                      | {"false": len(c["false_crossings_in_window"])} for k, c in rep["clips"].items()}))


if __name__ == "__main__":
    main()
