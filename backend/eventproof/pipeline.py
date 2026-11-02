"""End-to-end run: video + natural-language rule + layout -> evidence JSON.

    ingest (ffprobe/normalize) -> Muse Spark (rule -> DSL) -> SAM 3.1 (concept -> tracks) -> evaluator -> evidence

The evidence file records what a reviewer needs to re-check a verdict: input hashes, the exact rule the model
produced (and the assumptions it made), model ids and request/response ids, whether each model output was
live or served from cache, the track hash, and the per-object verdicts with their decisive frames.
`evidence_sha256` covers everything else in the file (canonical JSON), so edits are detectable.

If Muse marks the rule unsupported or produces an invalid rule, the run stops before any SAM call.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from eventproof import __version__
from eventproof.engine.evaluator import evaluate
from eventproof.meta.muse_rules import Layout, MuseRuleCompiler, RuleCompileError, UnsupportedRule
from eventproof.perception.sam import SamTracker, to_trackset
from eventproof.perception.sam_wire import SamParseError, parse_output
from eventproof.schemas.evidence import RuleReport
from eventproof.schemas.tracks import VideoInfo
from eventproof.video.ingest import IngestedVideo, ingest

RUNS_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "runs"
RUN_ID_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$")
EVIDENCE_SCHEMA = "eventproof-evidence/2"  # /2: video recorded by file name, not local path

Status = Literal["completed", "rule_unsupported", "rule_invalid", "perception_failed"]


class VideoRecord(BaseModel):
    filename: str
    sha256: str
    original_sha256: str
    info: VideoInfo
    duration_s: float
    codec: str
    reencoded: bool
    reencode_reasons: list[str]

    @classmethod
    def of(cls, v: IngestedVideo, filename: str) -> VideoRecord:
        return cls(filename=filename, **v.model_dump(exclude={"path"}))


class RuleStage(BaseModel):
    text: str
    text_sha256: str
    layout: Layout
    model: str
    request_ids: list[str] = []
    cached: bool | None = None
    attempts: int | None = None
    usage: list[dict] = []
    compiled_rule: dict | None = None
    rule_hash: str | None = None
    assumptions: list[str] = []
    error: str | None = None


class PerceptionStage(BaseModel):
    model: str
    prompt: str
    source_ref: str | None = None
    cached: bool | None = None
    tracks_sha256: str | None = None
    frames_with_detections: int = 0
    boxes: int = 0
    track_ids: list[int] = []
    error: str | None = None
    context: list[dict] = []  # other concepts a WITH event refers to: one SAM request each (prompt, source_ref, cached)


class Evidence(BaseModel):
    schema_version: str = EVIDENCE_SCHEMA
    run_id: str
    created_at: str
    eventproof_version: str
    status: Status
    video: VideoRecord
    rule: RuleStage
    perception: PerceptionStage | None = None
    result: RuleReport | None = None
    files: dict[str, str] = {}
    evidence_sha256: str = ""

    def body_sha256(self) -> str:
        body = self.model_dump(mode="json", exclude={"evidence_sha256"})
        return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def seal(self) -> Evidence:
        self.evidence_sha256 = self.body_sha256()
        return self

    def verify(self) -> bool:
        return self.evidence_sha256 == self.body_sha256()


def verify_evidence_file(path: Path) -> bool:
    """Check an evidence.json as stored, independent of the current model version."""
    raw = json.loads(path.read_text())
    claimed = raw.pop("evidence_sha256", "")
    return claimed == hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def new_run_id() -> str:
    return f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


CONTEXT_ID_OFFSET = 1000


def run(video: Path, rule_text: str, layout: Layout, compiler: MuseRuleCompiler, tracker: SamTracker,
        runs_dir: Path | None = None, run_id: str | None = None, filename: str | None = None) -> Evidence:
    run_id = run_id or new_run_id()
    out = (runs_dir or RUNS_DIR) / run_id
    out.mkdir(parents=True, exist_ok=False)
    vid = ingest(video, out / "work")  # VideoRejected propagates: nothing to record yet
    kept = out / "video.mp4"  # the exact bytes SAM saw, so the studio can replay them with the overlay
    shutil.copyfile(vid.path, kept)
    vid = vid.model_copy(update={"path": kept})
    rule_stage = RuleStage(text=rule_text, text_sha256=_sha(rule_text), layout=layout, model=compiler.settings.muse_model)
    ev = Evidence(run_id=run_id, created_at=datetime.now(UTC).isoformat(timespec="seconds"),
                  eventproof_version=__version__, status="completed", video=VideoRecord.of(vid, filename or video.name),
                  rule=rule_stage)
    try:
        compiled = compiler.compile(rule_text, layout)
    except UnsupportedRule as e:
        ev.status, rule_stage.error = "rule_unsupported", str(e)
        return _write(ev, out)
    except RuleCompileError as e:
        ev.status, rule_stage.error = "rule_invalid", str(e)
        return _write(ev, out)
    rule = compiled.rule
    rule_stage.request_ids, rule_stage.cached, rule_stage.attempts = compiled.request_ids, compiled.cached, compiled.attempts
    rule_stage.usage, rule_stage.assumptions = compiled.usage, compiled.assumptions
    rule_stage.compiled_rule, rule_stage.rule_hash = json.loads(rule.canonical_json()), rule.rule_hash()
    (out / "rule.json").write_text(rule.model_dump_json(indent=2))
    ev.files["rule"] = "rule.json"

    perc = PerceptionStage(model=tracker.settings.sam_model, prompt=rule.entity.concept)
    ev.perception = perc
    try:
        res = tracker.track(vid.path, rule.entity.concept)
        tracks = to_trackset(parse_output(res.deltas), vid.info, rule.entity.concept, res.source_ref)
    except SamParseError as e:
        ev.status, perc.error = "perception_failed", f"SAM output could not be parsed: {e}"
        return _write(ev, out)
    try:
        for k, concept in enumerate(rule.context_concepts(), start=1):  # a second tracked concept (WITH events)
            cres = tracker.track(vid.path, concept)
            ctx = to_trackset(parse_output(cres.deltas), vid.info, concept, cres.source_ref)
            offset = CONTEXT_ID_OFFSET * k  # keep object ids of different concepts apart
            tracks.frames += [f.model_copy(update={"object_id": f.object_id + offset}) for f in ctx.frames]
            perc.context.append({"prompt": concept, "source_ref": cres.source_ref, "cached": cres.cached,
                                 "boxes": len(ctx.frames), "track_ids": sorted({f.object_id + offset for f in ctx.frames})})
    except SamParseError as e:
        ev.status, perc.error = "perception_failed", f"SAM output for a context concept could not be parsed: {e}"
        return _write(ev, out)
    tracks_json = tracks.model_dump_json()
    (out / "tracks.json").write_text(tracks_json)
    ev.files["tracks"] = "tracks.json"
    perc.source_ref, perc.cached, perc.tracks_sha256 = tracks.source_ref, res.cached, _sha(tracks_json)
    perc.frames_with_detections = len({f.frame_index for f in tracks.frames})
    own = [f for f in tracks.frames if f.label == rule.entity.concept]
    perc.boxes, perc.track_ids = len(own), sorted({f.object_id for f in own})
    ev.result = evaluate(rule, tracks)
    return _write(ev, out)


def _write(ev: Evidence, out: Path) -> Evidence:
    ev.files["evidence"] = "evidence.json"
    ev.files["video"] = "video.mp4"
    shutil.rmtree(out / "work", ignore_errors=True)
    ev.seal()
    (out / "evidence.json").write_text(ev.model_dump_json(indent=2) + "\n")
    return ev


def run_file(run_id: str, name: str, runs_dir: Path | None = None) -> Path:
    """Path of a known file of a run; the id is pattern-checked and names are a fixed set (no traversal)."""
    if not RUN_ID_RE.match(run_id) or name not in ("evidence.json", "rule.json", "tracks.json", "video.mp4"):
        raise ValueError("invalid run id or file")
    p = (runs_dir or RUNS_DIR) / run_id / name
    if not p.is_file():
        raise FileNotFoundError(name)
    return p


def load(run_id: str, runs_dir: Path | None = None) -> Evidence:
    return Evidence.model_validate_json(run_file(run_id, "evidence.json", runs_dir).read_text())
