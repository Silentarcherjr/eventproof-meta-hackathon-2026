"""Two-concept rule on real footage: pedestrians on a crossing and the umbrellas they hold (WITH ... on_top).
Pre-registered in `benchmark/real/with_umbrella/PREREGISTRATION.md`.

The label format of `real_video` is about objects crossing a line; here each labelled person carries a point (where
their feet are, as fractions of the frame) at a clip time and an intended verdict. A labelled person is matched to the
tracked entity whose box bottom-centre comes closest to that point within +-0.3 s (at most MATCH_DIST away, each track
used once). Reported: labelled people right / wrong / abstained (UNKNOWN) / not tracked, plus unlabelled tracked people.

    uv run python -m eventproof.validation.with_pilot run --max-muse 2 --max-sam 2 \
        --out ../benchmark/real/with_umbrella/report.json
    uv run python -m eventproof.validation.with_pilot report     # recompute from the recorded run, 0 API calls
"""

from __future__ import annotations

import argparse
import json
from math import hypot
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from eventproof import pipeline
from eventproof.meta.muse_rules import Layout
from eventproof.perception.sam import SamTracker
from eventproof.pipeline import Evidence
from eventproof.schemas.tracks import TrackSet
from eventproof.validation.evaluate import ROOT, _git_head
from eventproof.validation.real_video import LimitedMuseCompiler, sha256_file

DIR = ROOT / "benchmark" / "real" / "with_umbrella"
MATCH_DIST, MATCH_WINDOW_MS = 0.12, 300.0


class Person(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str
    t_s: float = Field(ge=0)
    feet: tuple[float, float]
    umbrella: bool
    intended: Literal["PASS", "VIOLATION"]


class PilotLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["eventproof-with-labels/1"]
    labeled_by: str
    labeled_at: str
    source: str
    clip: str
    clip_sha256: str
    rule_text: str
    layout: Layout
    people: list[Person]


def load(d: Path = DIR) -> PilotLabel:
    return PilotLabel.model_validate_json((d / "labels.json").read_text())


def match(people: list[Person], tracks: TrackSet, entity_ids: set[int]) -> dict[int, int]:
    w, h = tracks.video.width, tracks.video.height
    cands = []
    for i, p in enumerate(people):
        best: dict[int, float] = {}
        for f in tracks.frames:
            if f.object_id in entity_ids and abs(f.timestamp_ms - p.t_s * 1000) <= MATCH_WINDOW_MS:
                d = hypot((f.box.x1 + f.box.x2) / 2 / w - p.feet[0], f.box.y2 / h - p.feet[1])
                best[f.object_id] = min(d, best.get(f.object_id, d))
        cands += [(d, i, oid) for oid, d in best.items() if d <= MATCH_DIST]
    out, used = {}, set()
    for _d, i, oid in sorted(cands):
        if i not in out and oid not in used:
            out[i] = oid
            used.add(oid)
    return out


def score(label: PilotLabel, ev: Evidence, tracks: TrackSet) -> dict:
    verdict = {o.object_id: o.verdict for o in ev.result.objects}
    m = match(label.people, tracks, set(verdict))
    rows = []
    for i, p in enumerate(label.people):
        v = verdict.get(m[i]) if i in m else None
        rows.append({"person": i, "description": p.description, "umbrella": p.umbrella, "intended": p.intended,
                     "matched_object_id": m.get(i), "verdict": v,
                     "outcome": "not tracked" if v is None else "abstained" if v == "UNKNOWN"
                     else "right" if v == p.intended else "wrong"})
    count = {k: sum(r["outcome"] == k for r in rows) for k in ("right", "wrong", "abstained", "not tracked")}
    return {"labelled": len(rows), **count, "overall": ev.result.overall,
            "expected_overall": "FAIL" if any(p.intended == "VIOLATION" for p in label.people) else "PASS",
            "unlabelled_tracked": sorted(set(verdict) - set(m.values())), "people": rows}


def _report(label: PilotLabel, ev: Evidence, tracks: TrackSet) -> dict:
    return {"schema": "eventproof-with-pilot/1", "preregistration": "benchmark/real/with_umbrella/PREREGISTRATION.md",
            "data": "real-world (public footage, Pexels)", "source": label.source, "clip": label.clip,
            "labels_sha256": sha256_file(DIR / "labels.json"), "run_id": ev.run_id, "rule_text": label.rule_text,
            "compiled_rule": ev.rule.compiled_rule, "muse_request_ids": ev.rule.request_ids,
            "context_concepts": ev.perception.context if ev.perception else None,
            "result": score(label, ev, tracks)}


def run(max_muse: int, max_sam: int, out: Path) -> dict:
    if out.exists():
        raise SystemExit(f"{out} exists; the first report is kept")
    label = load()
    video = DIR / "videos" / label.clip
    if sha256_file(video) != label.clip_sha256:
        raise SystemExit("clip hash does not match the frozen label")
    compiler = LimitedMuseCompiler(max_live_calls=max_muse)
    tracker = SamTracker(max_live_calls=max_sam)
    ev = pipeline.run(video, label.rule_text, label.layout, compiler, tracker, runs_dir=DIR / "runs", filename=label.clip)
    if ev.status != "completed" or ev.result is None:
        rep = {"schema": "eventproof-with-pilot/1", "run_id": ev.run_id, "status": ev.status,
               "error": ev.rule.error or (ev.perception.error if ev.perception else None)}
    else:
        rep = _report(label, ev, TrackSet.model_validate_json((DIR / "runs" / ev.run_id / "tracks.json").read_text()))
    rep |= {"live_calls": {"muse": compiler.live_calls, "sam": tracker.live_calls}, "code_commit": _git_head()}
    out.write_text(json.dumps(rep, indent=2) + "\n")
    return rep


def recompute(report: Path = DIR / "report.json") -> dict:
    rep = json.loads(report.read_text())
    run_dir = DIR / "runs" / rep["run_id"]
    ev = Evidence.model_validate_json((run_dir / "evidence.json").read_text())
    return _report(load(), ev, TrackSet.model_validate_json((run_dir / "tracks.json").read_text()))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--max-muse", type=int, default=0)
    r.add_argument("--max-sam", type=int, default=0)
    r.add_argument("--out", type=Path, required=True)
    sub.add_parser("report")
    a = ap.parse_args()
    rep = run(a.max_muse, a.max_sam, a.out) if a.cmd == "run" else recompute()
    print(json.dumps(rep.get("result", rep), indent=2)[:3000])


if __name__ == "__main__":
    main()
