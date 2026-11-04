"""What counts as "stopped"? The compiled rule against independent human annotators on MEVA (CC BY 4.0, Kitware/IARPA).
Pre-registered in `benchmark/meva/PREREGISTRATION.md`.

`extract` (run once, needs the meva-data-repo checkout and PyYAML) turns the official Kitware annotations into committed
data: for every vehicle actor that moves (track >= 1 s, bottom-centre moves >= 5 % of the frame width), its boxes at
10 fps and whether the annotators gave it a `vehicle_stops` activity. `run` compiles "Every vehicle must come to a
complete stop." with Muse Spark and Muse Wonder (law-mode schema) over a whole-frame zone, judges every vehicle on the
annotators' own boxes (no SAM: perception held fixed) and scores against the annotators. `report` recomputes with 0 calls.

    uv run --with pyyaml python -m eventproof.validation.meva extract --repo <meva-data-repo>
    uv run python -m eventproof.validation.meva run --max-live 4 --out ../benchmark/meva/report.json
"""

from __future__ import annotations

import argparse
import dataclasses
import glob
import gzip
import json
from pathlib import Path

from eventproof.engine.evaluator import evaluate
from eventproof.meta.client import MetaSettings
from eventproof.meta.muse_rules import Layout, RuleCompileError
from eventproof.review.robustness import _map_events
from eventproof.schemas.rules import VisualRule
from eventproof.schemas.tracks import Box, TrackFrame, TrackSet, VideoInfo
from eventproof.validation.evaluate import ROOT, _git_head, wilson
from eventproof.validation.real_video import LimitedMuseCompiler, LiveCallLimit

OUT = ROOT / "benchmark" / "meva"
CAMS = ("hospital.G436", "school.G336", "school.G424", "school.G328", "school.G339", "bus.G340")
W, H, FPS, STEP = 1920, 1080, 30.0, 3  # MEVA ground cameras; keep every 3rd annotated frame (10 fps)
RULE_TEXT = "Every vehicle must come to a complete stop."
LAYOUT = Layout.model_validate({"zones": [{"zone": {"id": "scene", "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]]},
                                           "description": "the whole camera view"}]})
MODELS = ("muse-spark-1.3", "muse-wonder-1.0")
TIMES_S = [round(0.25 * i, 2) for i in range(13)]
SPEEDS = [round(0.01 * i, 2) for i in range(1, 21)] + [None]


def extract(repo: Path) -> dict:
    import yaml  # offline tool only

    L = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    pop, clips = [], 0
    (OUT / "tracks").mkdir(parents=True, exist_ok=True)
    for f in sorted(glob.glob(str(repo / "annotation/DIVA-phase-2/MEVA/kitware/**/*.activities.yml"), recursive=True)):
        if not any(c in f for c in CAMS):
            continue
        base = f[: -len(".activities.yml")]
        clip = Path(base).name
        tdocs = yaml.load(open(base + ".types.yml"), Loader=L) or []
        types = {d["types"]["id1"]: next(iter(d["types"]["cset3"])) for d in tdocs if d.get("types")}
        stops = set()
        for a in yaml.load(open(f), Loader=L) or []:
            a = a.get("act")
            if a and next(iter(a["act2"])) == "vehicle_stops":
                stops |= {x["id1"] for x in a["actors"]}
        boxes: dict[int, list] = {}
        for d in yaml.load(open(base + ".geom.yml"), Loader=L) or []:
            g = d.get("geom")
            if g and types.get(g["id1"]) == "vehicle" and g["ts0"] % STEP == 0:
                boxes.setdefault(g["id1"], []).append((g["ts0"], *map(int, g["g0"].split())))
        frames, last = [], 0
        for aid, bs in boxes.items():
            bs.sort()
            xs = [(b[1] + b[3]) / 2 / W for b in bs]
            if len(bs) * STEP / FPS < 1.0 or max(xs) - min(xs) < 0.05:
                continue
            pop.append({"clip": clip, "camera": clip.split(".")[-2] + "." + clip.split(".")[-1], "actor": aid,
                        "stopped": aid in stops, "seconds": round(len(bs) * STEP / FPS, 1)})
            for ts, x1, y1, x2, y2 in bs:
                frames.append([ts, aid, x1, y1, x2, y2])
                last = max(last, ts)
        if frames:
            clips += 1
            with gzip.open(OUT / "tracks" / f"{clip}.json.gz", "wt") as fh:
                json.dump({"frame_count": last + 1, "frames": frames}, fh)
    meta = {"schema": "eventproof-meva-population/1",
            "source": "MEVA (Kitware Inc., IARPA), CC BY 4.0, https://mevadata.org/; official Kitware annotations, "
                      "meva-data-repo annotation/DIVA-phase-2/MEVA/kitware",
            "citation": "Corona et al., MEVA: A Large-Scale Multiview, Multimodal Video Dataset for Activity Detection, "
                        "WACV 2021",
            "cameras": CAMS, "clips": clips, "vehicles": len(pop), "stopped": sum(p["stopped"] for p in pop),
            "population": pop}
    (OUT / "population.json").write_text(json.dumps(meta, indent=1) + "\n")
    return meta


def load_tracks(clip: str) -> TrackSet:
    with gzip.open(OUT / "tracks" / f"{clip}.json.gz", "rt") as fh:
        d = json.load(fh)
    fr = [TrackFrame(frame_index=ts, timestamp_ms=ts * 1000 / FPS, object_id=aid, label="vehicle",
                     box=Box(x1=x1, y1=y1, x2=x2, y2=y2)) for ts, aid, x1, y1, x2, y2 in d["frames"]]
    return TrackSet(video=VideoInfo(width=W, height=H, fps=FPS, frame_count=d["frame_count"]), frames=fr,
                    source="human_annotation", source_ref="MEVA Kitware annotations (CC BY 4.0)")


def _named(rule: VisualRule, tracks: TrackSet) -> TrackSet:
    return tracks.model_copy(update={"frames": [f.model_copy(update={"label": rule.entity.concept}) for f in tracks.frames]})


def score(verdicts: dict[tuple, str], pop: list[dict]) -> dict:
    right = sum((verdicts.get((p["clip"], p["actor"])) == "PASS") == p["stopped"]
                and verdicts.get((p["clip"], p["actor"])) in ("PASS", "VIOLATION") for p in pop)
    false_stop = sum(verdicts.get((p["clip"], p["actor"])) == "PASS" and not p["stopped"] for p in pop)
    missed = sum(verdicts.get((p["clip"], p["actor"])) == "VIOLATION" and p["stopped"] for p in pop)
    unk = sum(verdicts.get((p["clip"], p["actor"])) not in ("PASS", "VIOLATION") for p in pop)
    return {"n": len(pop), "right": right, "agreement": round(right / len(pop), 3), "ci95": wilson(right, len(pop)),
            "false_stopped": false_stop, "missed_stops": missed, "undecided": unk}


def judge(rule: VisualRule, pop: list[dict]) -> dict[tuple, str]:
    out = {}
    for clip in sorted({p["clip"] for p in pop}):
        for o in evaluate(rule, _named(rule, load_tracks(clip))).objects:
            out[(clip, o.object_id)] = o.verdict
    return out


def study(max_live: int = 0) -> dict:
    meta = json.loads((OUT / "population.json").read_text())
    pop = meta["population"]
    rows, live = [], 0
    for model in MODELS:
        s = dataclasses.replace(MetaSettings.from_env(), muse_model=model)
        comp = LimitedMuseCompiler(s, cache_dir=OUT / "cache" / model, max_live_calls=max(0, max_live - live), law=True)
        try:
            res = comp.compile(RULE_TEXT, LAYOUT)
        except (RuleCompileError, LiveCallLimit) as e:
            rows.append({"model": model, "compiled": False, "error": f"{type(e).__name__}: {e}"[:300]})
            live += comp.live_calls
            continue
        live += comp.live_calls
        rule = res.rule
        v = judge(rule, pop)
        per_cam = {c: score(v, [p for p in pop if p["camera"] == c]) for c in sorted({p["camera"] for p in pop})}
        rows.append({"model": model, "compiled": True, "cached": res.cached, "request_ids": res.request_ids,
                     "rule": json.loads(rule.canonical_json()), "assumptions": res.assumptions,
                     "provenance": res.raw_output.get("provenance", []), "total": score(v, pop), "per_camera": per_cam})
    return {"rows": rows, "live_calls": live, "population": {k: meta[k] for k in ("clips", "vehicles", "stopped")}}


def grid(rule: VisualRule) -> list[dict]:
    """Every stop time x 'still' speed of the law grid, same rule shape, scored against the annotators."""
    pop = json.loads((OUT / "population.json").read_text())["population"]
    tracks = {c: _named(rule, load_tracks(c)) for c in sorted({p["clip"] for p in pop})}
    cells = []
    for t_s in TIMES_S:
        for sp in SPEEDS:
            r = _map_events(rule, lambda e, t=t_s, v=sp: e | {"min_ms": max(1.0, t * 1000), "max_speed": v}
                            if e.get("op") == "DWELL" else None) or rule
            v = {}
            for c, ts in tracks.items():
                for o in evaluate(r, ts).objects:
                    v[(c, o.object_id)] = o.verdict
            cells.append({"min_s": t_s, "speed": sp} | score(v, pop))
    return cells


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("--repo", type=Path, required=True)
    r = sub.add_parser("run")
    r.add_argument("--max-live", type=int, default=0)
    r.add_argument("--out", type=Path, required=True)
    sub.add_parser("report")
    a = ap.parse_args()
    if a.cmd == "extract":
        m = extract(a.repo)
        print({k: m[k] for k in ("clips", "vehicles", "stopped")})
        return
    if a.cmd == "run" and a.out.exists():
        raise SystemExit(f"{a.out} exists; the first report is kept")
    rep = {"schema": "eventproof-meva-study/1", "preregistration": "benchmark/meva/PREREGISTRATION.md", **study(
        a.max_live if a.cmd == "run" else 0)}
    spark = next((x for x in rep["rows"] if x["model"] == "muse-spark-1.3" and x["compiled"]), None)
    if spark:
        rep["grid"] = grid(VisualRule.model_validate(spark["rule"]))
    if a.cmd == "run":
        rep["code_commit"] = _git_head()
        a.out.write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps([{k: x.get(k) for k in ("model", "compiled", "total")} for x in rep["rows"]], indent=1))


if __name__ == "__main__":
    main()
