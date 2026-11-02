"""Optional live SAM 3.1 pass on a fixed subset of final_v1 (pre-registered in
`benchmark/final/PREREGISTRATION_SAM_v1.md`, reported separately; the mock-tracker report stays primary).

Subset: seeds 40000–40009 of all 8 final_v1 families (80 scenes), chosen by seed index only. Each scene is rendered
to MP4 and tracked once by SAM 3.1 (prompt = the object concept, ground truth never sent). The raw SAM output is cached
by video sha256 under `benchmark/final/sam_v1/sam_cache/`, so the report is recomputed from committed files with
0 live calls. Scenes where SAM fails or its output does not parse are listed and left out of both the SAM and the
mock numbers.

    uv run python -m eventproof.validation.sam_pass track --max-live-sam-calls 80   # live calls, resumable
    uv run python -m eventproof.validation.sam_pass report --out ../benchmark/final/sam_v1/report_sam_v1.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eventproof.challenge.render import encode_mp4, ground_truth
from eventproof.challenge.replay import identity_events
from eventproof.challenge.runner import mock_perceiver, run_case
from eventproof.challenge.scene import SceneSpec
from eventproof.meta.client import LiveCallLimit
from eventproof.perception.sam import SamTracker, sha256_file, to_trackset
from eventproof.perception.sam_wire import SamParseError, parse_output
from eventproof.schemas.tracks import TrackSet
from eventproof.validation.evaluate import ROOT, _detector, _git_head, evaluate, sha256
from eventproof.validation.final import DEFAULT_PATH, FinalCase, load_frozen

SUBSET_SEEDS = range(40000, 40010)
OUT_DIR = ROOT / "benchmark" / "final" / "sam_v1"
CACHE_DIR = OUT_DIR / "sam_cache"
TRACKING = OUT_DIR / "tracking.json"
VIDEO_DIR = ROOT / "artifacts" / "sam_v1_videos"  # re-rendered bit-identically from the scene; not committed
PERCEPTION = "sam-3.1 (live Meta API, raw outputs cached in benchmark/final/sam_v1/sam_cache)"


def in_subset(c: FinalCase) -> bool:
    return c.seed in SUBSET_SEEDS


def _key(c: FinalCase) -> str:
    return f"{c.split}/{c.family}/{c.seed}"


def _mp4(scene: SceneSpec) -> Path:
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    mp4 = VIDEO_DIR / f"{scene.scene_hash()[:16]}.mp4"
    if not mp4.exists():
        encode_mp4(scene, mp4)
    return mp4


def _concept(scene: SceneSpec) -> str:
    return scene.objects[0].label if scene.objects else "box"


def track(max_live: int, tracker: SamTracker | None = None, manifest_path: Path = DEFAULT_PATH,
          tracking_path: Path = TRACKING) -> dict:
    """Track every subset scene (cache first, live within the allowance). Resumable; never re-calls a cached video."""
    tracker = tracker or SamTracker(cache_dir=CACHE_DIR, max_live_calls=max_live)
    _, cases = load_frozen(manifest_path)
    log = json.loads(tracking_path.read_text()) if tracking_path.exists() else {"scenes": {}}
    for c, scene in cases:
        if not in_subset(c) or log["scenes"].get(_key(c), {}).get("status") == "ok":
            continue
        mp4 = _mp4(scene)
        row = {"scene_sha256": c.scene_sha256, "mp4_sha256": sha256_file(mp4), "n_frames": scene.n_frames,
               "fps": scene.fps, "prompt": _concept(scene)}
        try:
            res = tracker.track(mp4, row["prompt"])
        except LiveCallLimit:
            break
        except Exception as e:  # API error: recorded, not hidden; a later run may retry it
            log["scenes"][_key(c)] = {**row, "status": "error", "error": f"{type(e).__name__}: {e}"[:300]}
            continue
        row.update(response_id=res.response_id, model=res.model, live_this_run=not res.cached,
                   latency_s=res.latency_s)
        try:
            ts = to_trackset(parse_output(res.deltas), ground_truth(scene).video, row["prompt"], res.source_ref)
            row.update(status="ok", boxes=len(ts.frames), track_ids=sorted({f.object_id for f in ts.frames}))
        except SamParseError as e:
            row.update(status="parse_error", error=str(e)[:300])
        log["scenes"][_key(c)] = row
    log["live_calls_this_run"] = tracker.live_calls
    log.setdefault("live_calls_per_run", []).append(tracker.live_calls)
    tracking_path.parent.mkdir(parents=True, exist_ok=True)
    tracking_path.write_text(json.dumps(log, indent=2, sort_keys=True) + "\n")
    return log


def sam_cached_perceiver(tracker: SamTracker, log: dict | None = None):
    """SAM tracks from the cache only. With the tracking log, the cache entry is found by the MP4 sha256 recorded at
    tracking time (the scene itself is checked against the frozen manifest), so no video has to be re-encoded."""
    memo: dict[str, TrackSet] = {}
    rows = {r["scene_sha256"]: r for r in (log or {}).get("scenes", {}).values() if r.get("status") == "ok"}

    def perceive(scene: SceneSpec, gt: TrackSet) -> TrackSet:
        h = scene.scene_hash()
        if h not in memo:
            row = rows.get(h)
            if row is None:
                memo[h] = tracker.tracks(_mp4(scene), _concept(scene), gt.video)
            else:
                c = json.loads((tracker.cache_dir / f"{tracker._key(row['mp4_sha256'], row['prompt'])}.json").read_text())
                ref = f"{c['model']}:{c['response_id']}:video={row['mp4_sha256'][:16]}:prompt={row['prompt']!r}:cached"
                memo[h] = to_trackset(parse_output(c["deltas"]), gt.video, row["prompt"], ref)
        return memo[h]

    return perceive


def perception_agreement(cases: list[tuple[FinalCase, SceneSpec]], sam) -> dict:
    """Unpatched Muse-run rule: per scene, mock vs SAM verdict and SAM identity errors against ground truth."""
    det = _detector("run-rule", {})
    rows, both = [], {"same_verdict": 0, "sam_right_mock_wrong": 0, "mock_right_sam_wrong": 0, "both_wrong": 0}
    for c, scene in cases:
        rule = det.rule_for(scene, None)
        m, s = run_case(scene, rule, mock_perceiver), run_case(scene, rule, sam)
        ev = identity_events(ground_truth(scene), sam(scene, ground_truth(scene)))
        rows.append({"case": _key(c), "truth": m.intended, "mock": m.detector_verdict, "sam": s.detector_verdict,
                     "sam_identity_events": [e.kind for e in ev][:6]})
        mc, sc = m.outcome == "correct", s.outcome == "correct"
        both["same_verdict"] += m.detector_verdict == s.detector_verdict
        both["sam_right_mock_wrong"] += sc and not mc
        both["mock_right_sam_wrong"] += mc and not sc
        both["both_wrong"] += not mc and not sc
    return {"rule": "studio run rule (Muse Spark), unpatched", "n": len(rows), **both,
            "scenes_with_sam_identity_events": sum(bool(r["sam_identity_events"]) for r in rows), "rows": rows}


def report(manifest_path: Path = DEFAULT_PATH, tracking_path: Path = TRACKING,
           tracker: SamTracker | None = None) -> dict:
    log = json.loads(tracking_path.read_text())
    _, cases = load_frozen(manifest_path)
    sub = [(c, s) for c, s in cases if in_subset(c)]
    missing = [_key(c) for c, _ in sub if _key(c) not in log["scenes"]]
    if missing:
        raise SystemExit(f"{len(missing)} subset scenes not tracked yet (run `track` first): {missing[:5]}")
    ok = {_key(c) for c, _ in sub if log["scenes"][_key(c)]["status"] == "ok"}
    tracker = tracker or SamTracker(cache_dir=CACHE_DIR, max_live_calls=0)  # report never calls the API
    sam = sam_cached_perceiver(tracker, log)
    keep = lambda c: in_subset(c) and _key(c) in ok  # noqa: E731
    return {
        "preregistration": "benchmark/final/PREREGISTRATION_SAM_v1.md",
        "tracking_sha256": sha256(tracking_path),
        "subset": {"seeds": [SUBSET_SEEDS.start, SUBSET_SEEDS.stop - 1], "scenes": len(sub), "tracked_ok": len(ok),
                   "excluded": {k: log["scenes"][k].get("error", log["scenes"][k]["status"])
                                for k in sorted(_key(c) for c, _ in sub) if k not in ok}},
        "sam_responses": sorted({r["response_id"] for r in log["scenes"].values() if r.get("response_id")}),
        "perception_agreement": perception_agreement([(c, s) for c, s in sub if keep(c)], sam),
        "sam": evaluate(manifest_path, sam, subset=keep, perception=PERCEPTION),
        "mock_same_scenes": evaluate(manifest_path, mock_perceiver, subset=keep),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("track")
    t.add_argument("--max-live-sam-calls", type=int, required=True)
    r = sub.add_parser("report")
    r.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if args.cmd == "track":
        log = track(args.max_live_sam_calls)
        st = [r["status"] for r in log["scenes"].values()]
        print(json.dumps({"tracked": len(st), "ok": st.count("ok"), "live_calls_this_run": log["live_calls_this_run"]}))
        return
    if args.out.exists():
        raise SystemExit(f"{args.out} exists; the first SAM report is kept (see PREREGISTRATION_SAM_v1.md)")
    rep = report()
    rep["code_commit"] = _git_head()
    args.out.write_text(json.dumps(rep, indent=2) + "\n")
    print(json.dumps({"written": str(args.out), "tracked_ok": rep["subset"]["tracked_ok"]}))


if __name__ == "__main__":
    main()
