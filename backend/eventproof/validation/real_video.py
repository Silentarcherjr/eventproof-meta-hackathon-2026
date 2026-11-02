"""Validation on real phone videos recorded by the participant, labelled BLIND before any model sees them.

Protocol: docs/REAL_VIDEO_PROTOCOL.md. One label file per clip (`benchmark/real/labels/*.json`, schema `ClipLabel`).

    uv run python -m eventproof.validation.real_video hash  <video>                 # sha256 + ffprobe facts + metadata tags
    uv run python -m eventproof.validation.real_video frame <video> <out.png>       # first frame, to measure the layout
    uv run python -m eventproof.validation.real_video check <labels_dir> [--videos D] [--freeze]
    uv run python -m eventproof.validation.real_video run --labels D --videos D --max-live-sam-calls N \\
        --max-live-muse-calls M --out report.json

- `check --freeze` writes `MANIFEST.json` (sha256 of every label file and clip). `run` refuses to start without it, or if
  any label or clip changed since: labels are fixed before any model output exists.
- Live calls need explicit allowances. Muse uncached compiles are counted before anything runs; both clients also raise
  `LiveCallLimit` before a call that would exceed the allowance. Cached outputs (recorded live responses) are free.
- Matching perceived objects to labelled ones: perceived objects whose CROSSES(packing line) is TRUE are sorted by
  crossing frame and paired in order with the labelled objects that cross; the remaining perceived objects (FALSE or
  UNKNOWN crossing) are sorted by first frame and paired with the labelled non-crossing objects. Leftovers are reported
  as `missed` (labelled, not perceived) or `extra` (perceived, not labelled; e.g. a SAM identity switch), never dropped.
- Each clip is judged twice with the same tracks: the rule Muse compiled ("before") and that rule after the first accepted
  Muse Spark repair of the recorded demo run ("after"). If the patch does not apply to a clip's rule, the reason is shown.
- Nothing here feeds back into rules, thresholds, repairs or the grader. The report refuses to overwrite an earlier one.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from eventproof import __version__, pipeline
from eventproof.engine.evaluator import build_tracks, eval_event, evaluate
from eventproof.meta.muse_rules import Layout, MuseRuleCompiler
from eventproof.perception.sam import LiveCallLimit, SamTracker
from eventproof.repair.patch import PatchError, RulePatch, apply_patch
from eventproof.schemas.evidence import RuleReport
from eventproof.schemas.rules import Crosses, VisualRule
from eventproof.schemas.tracks import TrackSet
from eventproof.video.ingest import _tool, inspect, probe, sha256_file

ROOT = Path(__file__).resolve().parents[3]
LABEL_SCHEMA = "eventproof-real-labels/1"
REPORT_SCHEMA = "eventproof-real-report/1"
MANIFEST = "MANIFEST.json"
NOT_LABELS = ("TEMPLATE.json", MANIFEST)
REPAIR_SOURCE = ROOT / "docs/evidence/runs/20261028T023754Z-a922b5bb/challenge/repair_muse.json"
MIN_STOP_S = 1.0  # process truth, same as the synthetic world
LOCATION_KEYS = ("location", "gps", "iso6709")
DISCLAIMER = ("Real-world videos (the participant's own recordings or licensed public footage; source in each label's "
              "notes), labelled by hand and frozen before any model ran. Reported separately from the synthetic results; "
              "never used to tune rules, thresholds, repairs or the grader.")


class RealVideoError(RuntimeError):
    pass


# ---- labels -------------------------------------------------------------------------------------------


class LabeledObject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(min_length=1, description="what the box looks like / where it runs, e.g. 'red box, near lane'")
    crosses_packing: bool
    stood_still_s: float = Field(ge=0, le=60, description="approx seconds standing still at the station before packing")
    intended: Literal["PASS", "VIOLATION"]


class ClipLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["eventproof-real-labels/1"] = LABEL_SCHEMA
    clip: str = Field(description="file name of the clip in the videos directory")
    clip_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    layout: Layout
    packing_line: str = "packing_entry"
    rule_text: str = Field(min_length=1)
    objects: list[LabeledObject] = Field(min_length=1, description="crossing objects in crossing order, then the rest")
    expected_overall: Literal["PASS", "FAIL"]
    labeled_by: str = Field(min_length=1)
    labeled_at: AwareDatetime
    notes: str = ""

    @field_validator("clip")
    @classmethod
    def _plain_name(cls, v: str) -> str:
        if not v or "/" in v or "\\" in v or v.startswith(".") or Path(v).suffix.lower() not in (".mp4", ".mov"):
            raise ValueError("clip must be a plain .mp4/.mov file name (no directories)")
        return v

    @model_validator(mode="after")
    def _consistent(self) -> ClipLabel:
        if self.packing_line not in {ln.line.id for ln in self.layout.lines}:
            raise ValueError(f"packing_line '{self.packing_line}' is not a line of the layout")
        crossing = [o.crosses_packing for o in self.objects]
        if crossing != sorted(crossing, reverse=True):
            raise ValueError("list objects that cross packing first (in crossing order), then those that do not")
        if any(not o.crosses_packing and o.intended != "PASS" for o in self.objects):
            raise ValueError("an object that never crosses into packing cannot violate the rule (intended must be PASS)")
        want = "FAIL" if any(o.intended == "VIOLATION" for o in self.objects) else "PASS"
        if self.expected_overall != want:
            raise ValueError(f"expected_overall must be {want} given the objects' intended verdicts")
        return self

    def process_truth_warnings(self) -> list[str]:
        """Labels disagreeing with the stated process truth (stood still >= 1.0 s before packing). Warnings, not
        errors: the stop duration is an estimate; the labeller decides."""
        out = []
        for i, o in enumerate(self.objects):
            truth = "PASS" if not o.crosses_packing or o.stood_still_s >= MIN_STOP_S else "VIOLATION"
            if o.intended != truth:
                out.append(f"object {i} ({o.description}): intended {o.intended} but stood_still_s={o.stood_still_s} "
                           f"implies {truth} under the >= {MIN_STOP_S} s process truth")
        return out


def load_labels(labels_dir: Path) -> list[tuple[Path, ClipLabel]]:
    files = sorted(p for p in labels_dir.glob("*.json") if p.name not in NOT_LABELS)
    if not files:
        raise RealVideoError(f"no label files in {labels_dir}")
    out, seen = [], {}
    for p in files:
        try:
            label = ClipLabel.model_validate_json(p.read_text())
        except ValidationError as e:
            raise RealVideoError(f"{p.name}: invalid label: {e}") from None
        if label.clip in seen:
            raise RealVideoError(f"{p.name} and {seen[label.clip]} label the same clip {label.clip}")
        seen[label.clip] = p.name
        out.append((p, label))
    return out


def check(labels_dir: Path, videos_dir: Path) -> list[dict]:
    """Validate every label and refuse if a clip is missing, unreadable or changed after labelling."""
    rows = []
    for p, label in load_labels(labels_dir):
        video = videos_dir / label.clip
        if not video.is_file():
            raise RealVideoError(f"{p.name}: clip {label.clip} not found in {videos_dir}")
        sha = sha256_file(video)
        if sha != label.clip_sha256:
            raise RealVideoError(f"{p.name}: {label.clip} changed after labelling (label {label.clip_sha256[:12]}, "
                                 f"file {sha[:12]}); refusing to use it")
        _, reasons = inspect(video)  # VideoRejected (duration, container, ...) propagates
        rows.append({"label_file": p.name, "label_sha256": sha256_file(p), "clip": label.clip, "clip_sha256": sha,
                     "reencode": reasons, "warnings": label.process_truth_warnings()})
    return rows


def freeze(labels_dir: Path, rows: list[dict]) -> Path:
    path = labels_dir / MANIFEST
    if path.exists():
        raise RealVideoError(f"{path} exists; labels are already frozen (never re-freeze after running a model)")
    path.write_text(json.dumps({
        "schema_version": LABEL_SCHEMA, "frozen_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "labels": {r["label_file"]: r["label_sha256"] for r in rows},
        "clips": {r["clip"]: r["clip_sha256"] for r in rows}}, indent=2) + "\n")
    return path


def verify_manifest(labels_dir: Path, rows: list[dict]) -> str:
    path = labels_dir / MANIFEST
    if not path.exists():
        raise RealVideoError(f"no {MANIFEST} in {labels_dir}: run `check --freeze` before running any model")
    m = json.loads(path.read_text())
    now = {r["label_file"]: r["label_sha256"] for r in rows}
    if m.get("labels") != now:
        changed = sorted(set(now.items()) ^ set(m.get("labels", {}).items()))
        raise RealVideoError(f"labels differ from the frozen {MANIFEST}: {[k for k, _ in changed]}")
    return sha256_file(path)


# ---- matching -----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Perceived:
    object_id: int
    crossing: str  # TRUE / FALSE / UNKNOWN for CROSSES(packing line)
    cross_frame: int | None
    first_frame: int

    @property
    def crosses(self) -> bool:
        return self.crossing == "TRUE"


def perceive(rule: VisualRule, tracks: TrackSet, line_id: str) -> list[Perceived]:
    ev = Crosses(line=line_id)
    out = []
    for t in build_tracks(rule, tracks):
        r = eval_event(ev, t, rule)
        out.append(Perceived(t.object_id, r.status, r.frame, t.first_frame))
    return out


@dataclass
class Match:
    pairs: list[tuple[int, int]]  # (label index, perceived object id)
    missed: list[int]
    extra: list[int]


def match_objects(labeled: list[LabeledObject], perceived: list[Perceived]) -> Match:
    pairs, missed, extra = [], [], []
    for want in (True, False):
        lab = [i for i, o in enumerate(labeled) if o.crosses_packing is want]
        per = sorted((p for p in perceived if p.crosses is want),
                     key=lambda p: (p.cross_frame if want else p.first_frame, p.object_id))
        pairs += list(zip(lab, (p.object_id for p in per), strict=False))
        missed += lab[len(per):]
        extra += [p.object_id for p in per[len(lab):]]
    return Match(sorted(pairs), sorted(missed), sorted(extra))


# ---- repair -------------------------------------------------------------------------------------------


class RepairChoice(BaseModel):
    source: str
    source_sha256: str
    run_id: str
    proposer: str
    proposal_id: str
    patch: RulePatch
    description: str
    choice: str = "first accepted proposal in the proposer's order"


def load_repair(path: Path = REPAIR_SOURCE) -> RepairChoice:
    raw = json.loads(path.read_text())
    accepted = [d for d in raw["decisions"] if d.get("accepted") is True]
    if not accepted:
        raise RealVideoError(f"{path.name}: no accepted repair")
    d = accepted[0]
    patch = RulePatch.model_validate(d["proposal"]["patch"])
    try:
        source = str(path.resolve().relative_to(ROOT))
    except ValueError:
        source = path.name
    return RepairChoice(source=source, source_sha256=sha256_file(path), run_id=raw["run_id"], proposer=raw["proposer"],
                        proposal_id=d["proposal"]["proposal_id"], patch=patch, description=patch.describe())


# ---- run ----------------------------------------------------------------------------------------------


class LimitedMuseCompiler(MuseRuleCompiler):
    """Muse compiler that refuses a live call beyond `max_live_calls` (raised before the client is created)."""

    def __init__(self, *a, max_live_calls: int = 0, **k):
        super().__init__(*a, **k)
        self.max_live_calls = max_live_calls

    def _call(self, messages, schema):
        if self.live_calls >= self.max_live_calls:
            raise LiveCallLimit(f"Muse Spark: not cached and live-call allowance {self.max_live_calls} is used up")
        return super()._call(messages, schema)

    def is_cached(self, text: str, layout: Layout) -> bool:
        return (self.cache_dir / f"{self._key(text, layout)}.json").exists()


def _side(report: RuleReport | None, label: ClipLabel, m: Match | None, error: str | None = None) -> dict:
    if report is None or m is None:
        return {"overall": None, "agrees_overall": False, "error": error}
    verdict = {o.object_id: o.verdict for o in report.objects}
    pair = dict(m.pairs)
    agree = sum(verdict.get(pair[i]) == o.intended for i, o in enumerate(label.objects) if i in pair)
    return {"overall": report.overall, "agrees_overall": report.overall == label.expected_overall,
            "rule_hash": report.rule_hash, "objects_agree": agree, "objects": {str(k): v for k, v in verdict.items()},
            "error": error}


def _objects_table(label: ClipLabel, per: list[Perceived], m: Match, before: RuleReport, after: RuleReport | None) -> dict:
    vb = {o.object_id: o.verdict for o in before.objects}
    va = {o.object_id: o.verdict for o in after.objects} if after else {}
    by_id, pair = {p.object_id: p for p in per}, dict(m.pairs)
    rows = []
    for i, o in enumerate(label.objects):
        oid = pair.get(i)
        p = by_id.get(oid) if oid is not None else None
        rows.append({"label_index": i, "description": o.description, "crosses_packing": o.crosses_packing,
                     "stood_still_s": o.stood_still_s, "intended": o.intended, "matched_object_id": oid,
                     "perceived_crossing": p.crossing if p else None, "perceived_cross_frame": p.cross_frame if p else None,
                     "before": vb.get(oid), "after": va.get(oid),
                     "agree_before": oid is not None and vb.get(oid) == o.intended,
                     "agree_after": oid is not None and after is not None and va.get(oid) == o.intended})
    extra = [{"object_id": oid, "perceived_crossing": by_id[oid].crossing, "perceived_cross_frame": by_id[oid].cross_frame,
              "first_frame": by_id[oid].first_frame, "before": vb.get(oid), "after": va.get(oid)} for oid in m.extra]
    return {"labeled": rows, "missed": m.missed, "extra": extra}


def _how(cached: bool | None) -> str | None:
    return None if cached is None else ("cached" if cached else "live")


def run_clip(label_file: Path, label: ClipLabel, video: Path, compiler: MuseRuleCompiler, tracker: SamTracker,
             repair: RepairChoice, runs_dir: Path | None) -> dict:
    ev = pipeline.run(video, label.rule_text, label.layout, compiler, tracker, runs_dir=runs_dir, filename=label.clip)
    row = {"label_file": label_file.name, "label_sha256": sha256_file(label_file), "clip": label.clip,
           "clip_sha256": label.clip_sha256, "run_id": ev.run_id, "status": ev.status,
           "evidence_sha256": ev.evidence_sha256, "ingested_sha256": ev.video.sha256, "reencoded": ev.video.reencoded,
           "muse": _how(ev.rule.cached), "sam": _how(ev.perception.cached if ev.perception else None),
           "rule_hash": ev.rule.rule_hash, "concept": ev.perception.prompt if ev.perception else None,
           "expected_overall": label.expected_overall, "n_labeled": len(label.objects)}
    if ev.status != "completed" or ev.result is None:
        err = ev.rule.error or (ev.perception.error if ev.perception else None) or ev.status
        return row | {"before": _side(None, label, None, err), "after": _side(None, label, None, err), "objects": None}
    rule = VisualRule.model_validate(ev.rule.compiled_rule)
    tracks = TrackSet.model_validate_json(((runs_dir or pipeline.RUNS_DIR) / ev.run_id / "tracks.json").read_text())
    per = perceive(rule, tracks, label.packing_line)
    m = match_objects(label.objects, per)
    after, after_error = None, None
    try:
        patched = apply_patch(rule, repair.patch)
    except (PatchError, ValidationError) as e:
        after_error = f"repair patch does not apply to this clip's rule: {e}"
    else:
        after = evaluate(patched, tracks)
    return row | {"n_perceived": len(per), "before": _side(ev.result, label, m),
                  "after": _side(after, label, m, after_error), "objects": _objects_table(label, per, m, ev.result, after)}


def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _summary(clips: list[dict]) -> dict:
    n = len(clips)
    out = {"clips": n}
    for side in ("before", "after"):
        done = [c for c in clips if c[side]["overall"] is not None]
        out[side] = {"evaluated": len(done), "overall_agree": sum(c[side]["agrees_overall"] for c in clips),
                     "objects_agree": sum(c[side].get("objects_agree", 0) for c in done),
                     "objects_labeled": sum(c["n_labeled"] for c in clips)}
    objs = [c["objects"] for c in clips if c["objects"]]
    out["missed"] = sum(len(o["missed"]) for o in objs)
    out["extra"] = sum(len(o["extra"]) for o in objs)
    return out


def run(labels_dir: Path, videos_dir: Path, out: Path, max_live_sam_calls: int, max_live_muse_calls: int,
        compiler: LimitedMuseCompiler | None = None, tracker: SamTracker | None = None, runs_dir: Path | None = None,
        repair_source: Path = REPAIR_SOURCE) -> dict:
    md = out.with_suffix(".md")
    for p in (out, md):
        if p.exists():
            raise RealVideoError(f"{p} exists; reports are never overwritten (choose a new --out)")
    rows = check(labels_dir, videos_dir)
    manifest_sha = verify_manifest(labels_dir, rows)
    labels = load_labels(labels_dir)
    repair = load_repair(repair_source)
    compiler = compiler or LimitedMuseCompiler(max_live_calls=max_live_muse_calls)
    compiler.max_live_calls = max_live_muse_calls
    tracker = tracker or SamTracker(max_live_calls=max_live_sam_calls)
    tracker.max_live_calls = max_live_sam_calls
    need = len({compiler._key(lb.rule_text, lb.layout) for _, lb in labels
                if not compiler.is_cached(lb.rule_text, lb.layout)})
    if need > max_live_muse_calls:
        raise LiveCallLimit(f"Muse Spark: {need} uncached rule compile(s) needed (>= {need} live calls), allowance is "
                            f"{max_live_muse_calls}; nothing was run")
    clips = []
    for p, label in labels:
        try:
            clips.append(run_clip(p, label, videos_dir / label.clip, compiler, tracker, repair, runs_dir))
        except LiveCallLimit as e:
            raise LiveCallLimit(f"{label.clip}: {e}. Clips before it are cached; re-run with a larger allowance "
                                "and a new --out. No report was written.") from None
    report = {"schema_version": REPORT_SCHEMA, "title": f"EventProof real-video validation (n={len(clips)} clips)",
              "data": "real-world", "n_clips": len(clips), "disclaimer": DISCLAIMER,
              "created_at": datetime.now(UTC).isoformat(timespec="seconds"), "eventproof_version": __version__,
              "code_commit": _git_head(), "labels_manifest_sha256": manifest_sha,
              "matching": "crossing objects paired in crossing order; others in first-frame order; leftovers reported",
              "repair": repair.model_dump(mode="json"),
              "allowances": {"muse": max_live_muse_calls, "sam": max_live_sam_calls},
              "live_calls": {"muse": compiler.live_calls, "sam": tracker.live_calls},
              "summary": _summary(clips), "clips": clips}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    md.write_text(markdown(report))
    return report


def markdown(r: dict) -> str:
    s = r["summary"]
    lines = [f"# {r['title']}", "", f"**Real-world data, n={r['n_clips']} clips, no tuning.** {r['disclaimer']}", "",
             f"- created {r['created_at']}, eventproof {r['eventproof_version']}, commit `{r['code_commit'][:12]}`",
             f"- labels manifest sha256 `{r['labels_manifest_sha256']}`",
             f"- live calls this run: Muse {r['live_calls']['muse']}, SAM {r['live_calls']['sam']} "
             f"(allowances {r['allowances']['muse']} / {r['allowances']['sam']}); everything else served from cache",
             f"- repair (\"after\"): `{r['repair']['proposal_id']}` = {r['repair']['description']} "
             f"({r['repair']['choice']}; from `{r['repair']['source']}`, sha256 `{r['repair']['source_sha256'][:12]}`)",
             f"- matching: {r['matching']}", "",
             "| | overall agrees | objects agree | evaluated |", "|---|---|---|---|"]
    for side in ("before", "after"):
        x = s[side]
        lines.append(f"| {side} repair | {x['overall_agree']}/{s['clips']} | {x['objects_agree']}/{x['objects_labeled']} "
                     f"| {x['evaluated']}/{s['clips']} |")
    lines += ["", f"Missed (labelled, not perceived): {s['missed']}. Extra (perceived, not labelled): {s['extra']}.", "",
              "| clip | sha256 | run | evidence sha256 | Muse | SAM | expected | before | after |",
              "|---|---|---|---|---|---|---|---|---|"]
    for c in r["clips"]:
        lines.append(f"| {c['clip']} | `{c['clip_sha256'][:12]}` | `{c['run_id']}` | `{c['evidence_sha256'][:12]}` "
                     f"| {c['muse']} | {c['sam']} | {c['expected_overall']} | {c['before']['overall']} "
                     f"| {c['after']['overall'] or 'n/a'} |")
    for c in r["clips"]:
        lines += ["", f"## {c['clip']} ({c['status']})"]
        for side in ("before", "after"):
            if c[side].get("error"):
                lines.append(f"- {side}: {c[side]['error']}")
        if not c["objects"]:
            continue
        lines += ["", "| # | labelled object | intended | matched id | crossing | before | after |",
                  "|---|---|---|---|---|---|---|"]
        for o in c["objects"]["labeled"]:
            lines.append(f"| {o['label_index']} | {o['description']} | {o['intended']} | {o['matched_object_id']} "
                         f"| {o['perceived_crossing']} | {o['before']} | {o['after']} |")
        for e in c["objects"]["extra"]:
            lines.append(f"| extra | (not labelled) | - | {e['object_id']} | {e['perceived_crossing']} | {e['before']} "
                         f"| {e['after']} |")
    return "\n".join(lines) + "\n"


# ---- helpers for recording ----------------------------------------------------------------------------


def metadata_tags(path: Path) -> dict[str, str]:
    r = subprocess.run([_tool("ffprobe"), "-v", "error", "-show_entries", "format_tags:stream_tags", "-of", "json",
                        str(path)], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return {}
    data = json.loads(r.stdout)
    tags = dict(data.get("format", {}).get("tags", {}))
    for i, s in enumerate(data.get("streams", [])):
        tags |= {f"stream{i}:{k}": v for k, v in s.get("tags", {}).items()}
    return tags


def hash_facts(path: Path) -> dict:
    v, reasons = inspect(path)
    fmt = probe(path)["format"]
    tags = metadata_tags(path)
    return {"file": path.name, "sha256": sha256_file(path), "container": fmt.get("format_name"),
            "duration_s": round(float(fmt.get("duration") or 0), 3), "codec": v.get("codec_name"),
            "size": f"{v.get('width')}x{v.get('height')}", "fps": v.get("avg_frame_rate"), "frames": v.get("nb_read_frames"),
            "reencode_on_ingest": reasons,
            "location_tags": sorted(k for k in tags if any(x in k.lower() for x in LOCATION_KEYS)),
            "metadata_tags": sorted(tags)}


def extract_frame(video: Path, out: Path) -> None:
    if out.exists():
        raise RealVideoError(f"{out} exists")
    subprocess.run([_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-i", str(video), "-frames:v", "1",
                    "-map_metadata", "-1", str(out)], check=True, timeout=60)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m eventproof.validation.real_video")
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("hash", help="sha256 + ffprobe facts + metadata tags of a clip")
    h.add_argument("video", type=Path)
    f = sub.add_parser("frame", help="write the first frame (as SAM will see it) to measure the layout")
    f.add_argument("video", type=Path)
    f.add_argument("out", type=Path)
    c = sub.add_parser("check", help="validate labels; refuse clips that changed after labelling")
    c.add_argument("labels", type=Path)
    c.add_argument("--videos", type=Path, help="default: <labels>/../videos")
    c.add_argument("--freeze", action="store_true", help=f"write {MANIFEST} (once, before any model run)")
    r = sub.add_parser("run", help="run the pipeline on every labelled clip and write the report")
    r.add_argument("--labels", type=Path, required=True)
    r.add_argument("--videos", type=Path, required=True)
    r.add_argument("--max-live-sam-calls", type=int, required=True)
    r.add_argument("--max-live-muse-calls", type=int, required=True)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--runs-dir", type=Path)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "hash":
            print(json.dumps(hash_facts(a.video), indent=2))
        elif a.cmd == "frame":
            extract_frame(a.video, a.out)
            print(a.out)
        elif a.cmd == "check":
            rows = check(a.labels, a.videos or a.labels.parent / "videos")
            for row in rows:
                print(f"OK {row['label_file']}: {row['clip']} sha256 {row['clip_sha256'][:12]} "
                      f"reencode={row['reencode'] or 'no'}")
                for w in row["warnings"]:
                    print(f"   WARNING {w}")
            if a.freeze:
                print(f"frozen: {freeze(a.labels, rows)}")
        else:
            rep = run(a.labels, a.videos, a.out, a.max_live_sam_calls, a.max_live_muse_calls, runs_dir=a.runs_dir)
            print(json.dumps({"written": str(a.out), "markdown": str(a.out.with_suffix(".md")), **rep["summary"],
                              "live_calls": rep["live_calls"]}, indent=2))
    except (RealVideoError, LiveCallLimit, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
