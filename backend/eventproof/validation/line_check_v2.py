"""v2 of the Pexels line-crossing check (pre-registered in `benchmark/real/pexels/PREREGISTRATION_v2.md`): the same
labels and scoring as v1, but SAM 3.1 sees the video cropped to the belt and in short overlapping windows, so parcels
that arrive later get free object slots. Window tracks are stitched back into full-frame tracks by box IoU on the
overlapping frames. v1 stays the first reported result.

    uv run python -m eventproof.validation.line_check_v2 run --max-live-sam-calls 8 \
        --out ../benchmark/real/pexels/report_pexels_v2.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from eventproof.perception.mock import iou
from eventproof.perception.sam import SamTracker, sha256_file, to_trackset
from eventproof.perception.sam_wire import parse_output
from eventproof.schemas.tracks import Box, TrackFrame, TrackSet, VideoInfo
from eventproof.validation.evaluate import _git_head, sha256
from eventproof.validation.line_check import DIR, score

CLIP = "pexels_5903898"
CROP = (160, 60, 480, 240)  # x, y, w, h in source pixels, chosen from the first frame before any v2 call
WINDOW, STEP = 50, 25  # frames (SAM bills at least 50 frames per request)
MIN_IOU = 0.3
LOG = DIR / "tracking_v2.json"


def windows(n_frames: int) -> list[tuple[int, int]]:
    starts = range(0, max(1, n_frames - WINDOW + STEP), STEP)
    return [(s, min(s + WINDOW, n_frames)) for s in starts if s < n_frames]


def encode_window(src: Path, start: int, end: int, out: Path) -> None:
    x, y, w, h = CROP
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-vf",
                    f"trim=start_frame={start}:end_frame={end},setpts=PTS-STARTPTS,crop={w}:{h}:{x}:{y}",
                    "-an", "-map_metadata", "-1", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium",
                    "-crf", "18", "-threads", "1", str(out)], check=True)


def to_full_frame(ts: TrackSet, start: int, fps: float) -> list[TrackFrame]:
    x, y, _, _ = CROP
    return [f.model_copy(update={"frame_index": f.frame_index + start,
                                 "timestamp_ms": (f.frame_index + start) * 1000.0 / fps,
                                 "box": Box(x1=f.box.x1 + x, y1=f.box.y1 + y, x2=f.box.x2 + x, y2=f.box.y2 + y)})
            for f in ts.frames]


def stitch(window_frames: list[list[TrackFrame]], video: VideoInfo) -> TrackSet:
    """Window tracks -> global tracks. A window track continues the global track with the highest mean IoU on their
    shared frames (>= MIN_IOU, one-to-one, greedy by IoU); otherwise it starts a new global id. On frames that a global
    track already covers, the earlier window's box is kept."""
    glob: dict[int, dict[int, TrackFrame]] = {}
    nxt = 0
    for frames in window_frames:
        local: dict[int, dict[int, TrackFrame]] = {}
        for f in frames:
            local.setdefault(f.object_id, {})[f.frame_index] = f
        cand = []
        for lid, lf in local.items():
            for gid, gf in glob.items():
                shared = lf.keys() & gf.keys()
                if shared:
                    m = sum(iou(lf[k].box, gf[k].box) for k in shared) / len(shared)
                    if m >= MIN_IOU:
                        cand.append((m, lid, gid))
        assign, used = {}, set()
        for _, lid, gid in sorted(cand, reverse=True):
            if lid not in assign and gid not in used:
                assign[lid] = gid
                used.add(gid)
        for lid in sorted(local):
            gid = assign.get(lid)
            if gid is None:
                gid, nxt = nxt, nxt + 1
                glob[gid] = {}
            for k, f in local[lid].items():
                glob[gid].setdefault(k, f.model_copy(update={"object_id": gid}))
    out = [f for g in glob.values() for f in g.values()]
    return TrackSet(video=video, frames=sorted(out, key=lambda f: (f.frame_index, f.object_id)), source="sam-3.1",
                    source_ref=f"sam-3.1 windowed ({len(window_frames)} requests), see tracking_v2.json")


def run(max_live: int, tracker: SamTracker | None = None) -> dict:
    lab = json.loads((DIR / "labels.json").read_text())
    clip = lab["clips"][CLIP]
    v = clip["video"]
    info = VideoInfo(width=v["width"], height=v["height"], fps=v["fps"], frame_count=v["frames"])
    tracker = tracker or SamTracker(cache_dir=DIR / "sam_cache", max_live_calls=max_live)
    src = DIR / "videos" / f"{CLIP}.mp4"
    log = json.loads(LOG.read_text()) if LOG.exists() else {"windows": []}
    recorded = {(w["start"], w["end"]): w for w in log["windows"]}
    per_window, rows = [], []
    for s, e in windows(v["frames"]):
        winfo = VideoInfo(width=CROP[2], height=CROP[3], fps=v["fps"], frame_count=e - s)
        rec = recorded.get((s, e))
        if src.exists():
            if sha256_file(src) != clip["prepared_sha256"]:
                raise SystemExit(f"{src} does not match the labelled sha256")
            mp4 = DIR / "videos" / f"{CLIP}_v2_{s:03d}_{e:03d}.mp4"
            if not mp4.exists():
                encode_window(src, s, e, mp4)
            res = tracker.track(mp4, clip["prompt"])
            deltas, rid, vsha, cached = res.deltas, res.response_id, res.video_sha256, res.cached
        else:  # videos are not committed: use the cached raw output recorded for this window
            c = json.loads((tracker.cache_dir / f"{tracker._key(rec['mp4_sha256'], clip['prompt'])}.json").read_text())
            deltas, rid, vsha, cached = c["deltas"], c["response_id"], rec["mp4_sha256"], True
        ts = to_trackset(parse_output(deltas), winfo, clip["prompt"], rid)
        per_window.append(to_full_frame(ts, s, v["fps"]))
        rows.append({"start": s, "end": e, "mp4_sha256": vsha, "response_id": rid, "live": not cached,
                     "objects": len({f.object_id for f in ts.frames}),
                     "max_per_frame": max((sum(1 for f in ts.frames if f.frame_index == k) for k in range(e - s)),
                                          default=0)})
    if src.exists():
        LOG.write_text(json.dumps({"crop": CROP, "window": WINDOW, "step": STEP, "windows": rows}, indent=2) + "\n")
    stitched = stitch(per_window, info)
    return {"preregistration": "benchmark/real/pexels/PREREGISTRATION_v2.md", "labels_sha256": sha256(DIR / "labels.json"),
            "perception": "sam-3.1 (live Meta API, cropped + windowed; raw outputs in benchmark/real/pexels/sam_cache)",
            "crop": CROP, "window": WINDOW, "step": STEP, "windows": [{k: r[k] for k in ("start", "end", "response_id",
                                                                                      "objects", "max_per_frame")}
                                                                     for r in rows],
            "clips": {CLIP: score(clip, stitched, lab)}, "live_sam_calls_this_run": tracker.live_calls}


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--max-live-sam-calls", type=int, default=0)
    r.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit(f"{args.out} exists; the first v2 report is kept")
    rep = run(args.max_live_sam_calls)
    rep["code_commit"] = _git_head()
    args.out.write_text(json.dumps(rep, indent=2) + "\n")
    c = rep["clips"][CLIP]
    print(json.dumps({k: c[k] for k in ("labels", "matched", "missed", "median_abs_dt_s", "distinct_track_ids_matched",
                                        "sam_tracks")} | {"false": len(c["false_crossings_in_window"])}))


if __name__ == "__main__":
    main()
