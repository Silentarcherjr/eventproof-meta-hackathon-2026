"""HTTP API: health, deterministic evaluation over supplied tracks, and end-to-end runs.

Credit and abuse guards (all per server process, read at start-up):
- EVENTPROOF_MAX_LIVE_SAM_CALLS / EVENTPROOF_MAX_LIVE_MUSE_CALLS: live (billed) Meta calls allowed; default 0 =
  cached results only. Each Muse request (rule compile attempt, repair round) and each SAM video counts as one.
- EVENTPROOF_MODE=showcase: no uploads and both allowances forced to 0, so only cached model outputs are served;
  recorded runs can be opened, challenged and repaired (Muse from its cache, baseline is free). Default "local".
  EVENTPROOF_MODE=hosted: like local (the allowances above apply), and the studio opens with the gallery of
  EVENTPROOF_DEMO_RUNS so a visitor picks a real clip and types a rule over it.
- EVENTPROOF_PATH_PREFIX=/api: also serve every route under that prefix (when a platform router forwards
  /api/* unchanged instead of stripping it).
- EVENTPROOF_RATE_LIMIT="<n>/<seconds>" per client IP for POST requests (default 30/600), and one heavy job at a
  time (others get 429). EVENTPROOF_TRUST_PROXY=1 takes the client IP from X-Forwarded-For (set it only behind
  your own proxy).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import threading
import time
from collections import deque
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, ValidationError

from eventproof import pipeline, studio
from eventproof.engine.evaluator import evaluate
from eventproof.meta.client import LiveBudget, MetaApiUnavailable, MetaSettings
from eventproof.meta.muse_rules import Layout, MuseRuleCompiler
from eventproof.perception.sam import LiveCallLimit, SamTracker
from eventproof.schemas.evidence import RuleReport
from eventproof.schemas.rules import VisualRule
from eventproof.schemas.tracks import TrackSet
from eventproof.video.ingest import MAX_BYTES, VideoRejected

app = FastAPI(title="EventProof", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_methods=["GET", "POST"], allow_headers=["*"],
                   allow_origins=os.environ.get("EVENTPROOF_CORS_ORIGINS", "http://localhost:3000").split(","))


MODE = os.environ.get("EVENTPROOF_MODE", "local")
DEMO_RUNS = [r for r in os.environ.get("EVENTPROOF_DEMO_RUNS", "").split(",") if pipeline.RUN_ID_RE.match(r)]
_muse_allowed = int(os.environ.get("EVENTPROOF_MAX_LIVE_MUSE_CALLS", "0"))
MUSE_BUDGET = LiveBudget("muse-spark", 0 if MODE == "showcase" else _muse_allowed)
_n, _, _w = os.environ.get("EVENTPROOF_RATE_LIMIT", "30/600").partition("/")
RATE_N, RATE_WINDOW = int(_n), float(_w or 600)
TRUST_PROXY = os.environ.get("EVENTPROOF_TRUST_PROXY") == "1"
_hits: dict[str, deque] = {}
_hits_lock = threading.Lock()
_heavy = threading.Semaphore(1)
HEAVY = re.compile(r"^/runs(/[^/]+/(challenge|challenge/sam-confirm|repair|before-after|ambiguity|rule|"
                   r"objects/\d+/defense))?$")


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for") if TRUST_PROXY else None
    return (fwd.split(",")[0].strip() if fwd else None) or (request.client.host if request.client else "?")


PATH_PREFIX = os.environ.get("EVENTPROOF_PATH_PREFIX", "").rstrip("/")


@app.middleware("http")
async def guards(request: Request, call_next):
    if request.method != "POST":
        return await call_next(request)
    ip, now = _client_ip(request), time.monotonic()
    with _hits_lock:
        q = _hits.setdefault(ip, deque())
        while q and now - q[0] > RATE_WINDOW:
            q.popleft()
        if len(q) >= RATE_N:
            return JSONResponse({"detail": f"rate limit: {RATE_N} requests per {RATE_WINDOW:.0f} s"}, status_code=429)
        q.append(now)
    if not HEAVY.match(request.url.path):
        return await call_next(request)
    if not _heavy.acquire(blocking=False):
        return JSONResponse({"detail": "another job is running; try again in a moment"}, status_code=429)
    try:
        return await call_next(request)
    finally:
        _heavy.release()


# registered after `guards`, so it runs first (Starlette: last added = outermost)
@app.middleware("http")
async def strip_prefix(request: Request, call_next):
    path = request.scope["path"]
    if PATH_PREFIX and (path == PATH_PREFIX or path.startswith(PATH_PREFIX + "/")):
        request.scope["path"] = path[len(PATH_PREFIX):] or "/"
    return await call_next(request)


def _no_live_in_showcase(what: str) -> None:
    if MODE == "showcase":
        raise HTTPException(403, f"{what} is off in showcase mode (this server serves recorded runs only)")


@app.get("/health")
def health() -> dict:
    s = MetaSettings.from_env()
    t = get_tracker()
    return {"status": "ok", "mode": MODE, "meta_api_key_configured": bool(s.api_key), "muse_model": s.muse_model,
            "sam_model": s.sam_model, "live_calls_remaining": {"muse": MUSE_BUDGET.remaining,
                                                               "sam": max(0, t.max_live_calls - t.live_calls)},
            "rate_limit": f"{RATE_N}/{RATE_WINDOW:.0f}s", "demo_runs": DEMO_RUNS, "demo_clips": _demo_clips()}


def _demo_clips() -> list[dict]:
    """The gallery: clip name and rule text of each demo run that exists on this server."""
    out = []
    for r in DEMO_RUNS:
        p = pipeline.RUNS_DIR / r / "evidence.json"
        if p.is_file():
            e = json.loads(p.read_text())
            out.append({"run_id": r, "clip": e["video"].get("filename"), "rule": e["rule"]["text"],
                        "overall": (e.get("result") or {}).get("overall")})
    return out


class EvaluateRequest(BaseModel):
    rule: VisualRule
    tracks: TrackSet


@app.post("/evaluate", response_model=RuleReport)
def evaluate_rule(req: EvaluateRequest) -> RuleReport:
    return evaluate(req.rule, req.tracks)


_tracker: SamTracker | None = None
_compiler: MuseRuleCompiler | None = None


def get_tracker() -> SamTracker:
    global _tracker
    if _tracker is None:
        allowed = 0 if MODE == "showcase" else int(os.environ.get("EVENTPROOF_MAX_LIVE_SAM_CALLS", "0"))
        _tracker = SamTracker(max_live_calls=allowed)
    return _tracker


def get_compiler() -> MuseRuleCompiler:
    global _compiler
    if _compiler is None:
        _compiler = MuseRuleCompiler(budget=MUSE_BUDGET, anchor_field=True)  # new compiles also pick the anchor
    return _compiler


@app.post("/runs", response_model=pipeline.Evidence)
def create_run(video: Annotated[UploadFile, File()],
               rule_text: Annotated[str, Form(min_length=3, max_length=2000)],
               layout: Annotated[str, Form()]) -> pipeline.Evidence:
    _no_live_in_showcase("uploading a new video")
    try:
        lay = Layout.model_validate(json.loads(layout))
    except (json.JSONDecodeError, ValidationError) as e:
        raise HTTPException(422, f"invalid layout: {e}") from None
    suffix = Path(video.filename or "").suffix.lower()
    if suffix not in (".mp4", ".mov"):
        raise HTTPException(415, "only .mp4 / .mov uploads are accepted")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"upload{suffix}"
        with src.open("wb") as fh:
            copied = 0
            while chunk := video.file.read(1 << 20):
                copied += len(chunk)
                if copied > MAX_BYTES:
                    raise HTTPException(413, "video too large")
                fh.write(chunk)
        try:
            return pipeline.run(src, rule_text, lay, get_compiler(), get_tracker(), filename=Path(video.filename).name)
        except VideoRejected as e:
            raise HTTPException(422, f"video rejected: {e}") from None
        except (MetaApiUnavailable, LiveCallLimit) as e:
            raise HTTPException(503, str(e)) from None


@app.post("/propose-layout")
def propose_layout(video: Annotated[UploadFile, File()],
                   rule_text: Annotated[str, Form(min_length=3, max_length=2000)]) -> dict:
    """Muse Spark drafts the zone and line from the first frame and the rule text; the user confirms or redraws."""
    from eventproof.meta.layout_proposer import LayoutProposer, first_frame_png
    from eventproof.meta.muse_rules import RuleCompileError

    _no_live_in_showcase("proposing a layout for a new video")
    suffix = Path(video.filename or "").suffix.lower()
    if suffix not in (".mp4", ".mov"):
        raise HTTPException(415, "only .mp4 / .mov uploads are accepted")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"upload{suffix}"
        src.write_bytes(video.file.read(MAX_BYTES + 1)[:MAX_BYTES])
        try:
            r = LayoutProposer(budget=MUSE_BUDGET).propose(first_frame_png(src), rule_text)
        except subprocess.CalledProcessError:
            raise HTTPException(422, "could not read the first frame") from None
        except RuleCompileError as e:
            raise HTTPException(422, str(e)) from None
        except (MetaApiUnavailable, LiveCallLimit) as e:
            raise HTTPException(503, str(e)) from None
    return {"layout": json.loads(r["layout"].model_dump_json()), "assumptions": r["assumptions"],
            "model": r["model"], "request_id": r["request_id"], "cached": r["cached"]}


class NewRuleRequest(BaseModel):
    rule_text: str
    layout: Layout | None = None


@app.post("/runs/{run_id}/rule", response_model=pipeline.Evidence)
def rerun_with_rule(run_id: str, req: NewRuleRequest) -> pipeline.Evidence:
    """A new rule on the same video (and, unless given, the same zones): a new run. The Muse compile counts against the
    live allowance unless cached; SAM tracks come from cache when the prompt is unchanged."""
    if not 3 <= len(req.rule_text.strip()) <= 2000:
        raise HTTPException(422, "rule_text must be 3-2000 characters")
    ev = pipeline.Evidence.model_validate_json(_run_file(run_id, "evidence.json").read_text())
    video = _run_file(run_id, "video.mp4")
    try:
        return pipeline.run(video, req.rule_text, req.layout or ev.rule.layout, get_compiler(), get_tracker(),
                            filename=ev.video.filename)
    except VideoRejected as e:
        raise HTTPException(422, f"video rejected: {e}") from None
    except (MetaApiUnavailable, LiveCallLimit) as e:
        raise HTTPException(503, str(e)) from None


def _run_file(run_id: str, name: str) -> Path:
    try:
        return pipeline.run_file(run_id, name)
    except ValueError:
        raise HTTPException(400, "invalid run id") from None
    except FileNotFoundError:
        raise HTTPException(404, "not found") from None


@app.get("/runs/{run_id}", response_model=pipeline.Evidence)
def get_run(run_id: str) -> pipeline.Evidence:
    return pipeline.Evidence.model_validate_json(_run_file(run_id, "evidence.json").read_text())


@app.get("/runs/{run_id}/tracks", response_model=TrackSet)
def get_tracks(run_id: str) -> TrackSet:
    return TrackSet.model_validate_json(_run_file(run_id, "tracks.json").read_text())


@app.get("/runs/{run_id}/video")
def get_video(run_id: str) -> FileResponse:
    return FileResponse(_run_file(run_id, "video.mp4"), media_type="video/mp4")


def _evidence(run_id: str) -> pipeline.Evidence:
    return pipeline.Evidence.model_validate_json(_run_file(run_id, "evidence.json").read_text())


@app.post("/runs/{run_id}/challenge", response_model=studio.ChallengeReport)
def run_challenge(run_id: str) -> studio.ChallengeReport:
    try:
        return studio.challenge(_evidence(run_id))
    except studio.ChallengeUnavailable as e:
        raise HTTPException(422, str(e)) from None


@app.post("/runs/{run_id}/challenge/sam-confirm")
def confirm_challenge(run_id: str) -> dict:
    try:
        return studio.confirm_with_sam(_evidence(run_id), get_tracker())
    except studio.ChallengeUnavailable as e:
        raise HTTPException(422, str(e)) from None
    except (MetaApiUnavailable, LiveCallLimit) as e:
        raise HTTPException(503, str(e)) from None


class RepairRequest(BaseModel):
    proposer: str = "muse"


@app.post("/runs/{run_id}/repair", response_model=studio.RepairRun)
def run_repair_endpoint(run_id: str, req: RepairRequest) -> studio.RepairRun:
    if req.proposer not in ("muse", "baseline"):
        raise HTTPException(422, "proposer must be 'muse' or 'baseline'")
    try:
        return studio.repair(_evidence(run_id), req.proposer, muse_budget=MUSE_BUDGET)
    except studio.ChallengeUnavailable as e:
        raise HTTPException(422, str(e)) from None
    except (MetaApiUnavailable, LiveCallLimit) as e:
        raise HTTPException(503, str(e)) from None


@app.post("/runs/{run_id}/before-after")
def before_after_endpoint(run_id: str, req: RepairRequest) -> dict:
    if req.proposer not in ("muse", "baseline"):
        raise HTTPException(422, "proposer must be 'muse' or 'baseline'")
    try:
        return studio.before_after(_evidence(run_id), req.proposer)
    except studio.ChallengeUnavailable as e:
        raise HTTPException(422, str(e)) from None


class AmbiguityRequest(BaseModel):
    text: str


@app.post("/runs/{run_id}/ambiguity")
def ambiguity_endpoint(run_id: str, req: AmbiguityRequest) -> dict:
    """Two readings of a rule text (Muse Spark, Muse Wonder) with this run's layout, and the minimal pair of synthetic
    scenes that separates them. Cached readings are free; live ones take from the Muse allowance."""
    try:
        return studio.ambiguity(_evidence(run_id), req.text, budget=MUSE_BUDGET)
    except studio.ChallengeUnavailable as e:
        raise HTTPException(422, str(e)) from None
    except (MetaApiUnavailable, LiveCallLimit) as e:
        raise HTTPException(503, str(e)) from None


@app.get("/runs/{run_id}/stored/{key}")
def stored_result(run_id: str, key: str) -> dict:
    """Reopen a run: a Challenge/Repair result computed earlier (404 if it was never computed)."""
    if not pipeline.RUN_ID_RE.match(run_id) or key not in studio.STORED:
        raise HTTPException(400, "invalid run id or key")
    out = studio.stored(run_id, key)
    if out is None:
        raise HTTPException(404, "not computed yet")
    return out


@app.get("/runs/{run_id}/certificate")
def run_certificate(run_id: str, chosen: str | None = None, format: str = "html"):  # noqa: A002
    """One-page rule certificate built from this run's recorded results (no model call). ?format=json for the data."""
    from eventproof import certificate

    _run_file(run_id, "evidence.json")  # validates the id and that the run exists
    cert = certificate.build(run_id, chosen=chosen)
    return cert if format == "json" else HTMLResponse(certificate.render_html(cert))


@app.get("/runs/{run_id}/checks")
def run_checks(run_id: str) -> list[dict]:
    """Deterministic checks of the compiled rule against this run's tracks (e.g. a line no anchor point ever crosses)."""
    from eventproof import certificate

    return certificate.run_checks(_run_file(run_id, "evidence.json").parent, _evidence(run_id))


@app.get("/runs/{run_id}/robustness")
def run_robustness(run_id: str) -> list[dict]:
    """Would each verdict hold up? Every object re-judged under the typed variant menu (deterministic, no model)."""
    from eventproof.review.robustness import robustness

    ev = _evidence(run_id)
    if ev.status != "completed" or not ev.rule.compiled_rule:
        raise HTTPException(422, "run has no compiled rule")
    tracks = TrackSet.model_validate_json(_run_file(run_id, "tracks.json").read_text())
    return [x.model_dump() for x in robustness(VisualRule.model_validate(ev.rule.compiled_rule), tracks)]


_defense = None


@app.post("/runs/{run_id}/objects/{object_id}/defense")
def run_defense(run_id: str, object_id: int) -> dict:
    """Muse Spark argues against one ticket from the closed challenge menu; the engine says which challenges win."""
    global _defense
    from eventproof.meta.muse_defense import MuseDefense
    from eventproof.review.robustness import robustness, variants

    ev = _evidence(run_id)
    tracks = TrackSet.model_validate_json(_run_file(run_id, "tracks.json").read_text())
    rule = VisualRule.model_validate(ev.rule.compiled_rule)
    obj = next((o for o in evaluate(rule, tracks).objects if o.object_id == object_id), None)
    if obj is None or obj.verdict != "VIOLATION":
        raise HTTPException(422, "only a VIOLATION verdict (a ticket) can be defended")
    menu = [{"id": f"{v.family}:{v.value}", "label": v.label} for v, _, _ in variants(rule, tracks.video.height)]
    _defense = _defense or MuseDefense(budget=MUSE_BUDGET)
    try:
        d = _defense.argue(ev.rule.text, ev.rule.compiled_rule, obj.model_dump(mode="json"), menu)
    except (MetaApiUnavailable, LiveCallLimit) as e:
        raise HTTPException(503, str(e)) from None
    rb = next(x for x in robustness(rule, tracks, only={object_id}))
    wins = {f"{f['family']}:{f['value']}": f for f in rb.flips if f["verdict"] != "UNKNOWN"}
    labels = {m["id"]: m["label"] for m in menu}
    return {"object_id": object_id, "status": rb.status, "concede": d["output"]["concede"],
            "concession": d["output"]["concession"], "strongest": d["output"]["strongest"],
            "challenges": [{"id": c["id"], "label": labels.get(c["id"], c["id"]), "argument": c["argument"],
                            "overturns": c["id"] in wins} for c in d["output"]["challenges"]],
            "request_id": d.get("request_id"), "cached": d["cached"]}


BENCH = Path(__file__).resolve().parents[3] / "benchmark"


@app.get("/law/grid")
def law_grid() -> dict:
    """The numbers the statutes never wrote, as a grid over the 30 labelled real cars (benchmark/law/grid.json)."""
    p = BENCH / "law" / "grid.json"
    if not p.is_file():
        raise HTTPException(404, "grid not computed")
    return json.loads(p.read_text())


@app.get("/tickets/court")
def ticket_court() -> dict:
    """Every real ticket of the ticket study as a case file: prosecution (rule, decisive events), defense (Muse Spark,
    from its closed menu), ruling (the deterministic sweep), plus the contract-acceptance block."""
    from eventproof.review.triage import APPROVABLE, apply_audit, contract, gates

    rep = json.loads((BENCH / "tickets" / "report.json").read_text())
    audit = json.loads((BENCH / "real" / "santos" / "label_audit.json").read_text())
    rows = apply_audit(rep["rows"], audit)
    runs = {}
    for s in ("novisad", "traffic_v2", "traffic_v3", "domains", "santos"):
        for c in json.loads((BENCH / "real" / "anchor_v4" / f"report_{s}.json").read_text())["clips"]:
            runs[(s, c["clip"])] = c["run_id"]
    cases = []
    for r in rows:
        if "defense" not in r:
            continue
        run_id = runs[(r["set"], r["clip"])]
        run = BENCH / "real" / "anchor_v4" / "runs" / run_id
        ev = pipeline.Evidence.model_validate_json((run / "evidence.json").read_text())
        rule = VisualRule.model_validate(ev.rule.compiled_rule)
        tracks = TrackSet.model_validate_json((run / "tracks.json").read_text())
        obj = next(o for o in evaluate(rule, tracks).objects if o.object_id == r["object_id"])
        cases.append(r | {"run_id": run_id, "rule_text": ev.rule.text, "explanation": rule.normalized_explanation,
                          "anchor": rule.params.anchor, "events": [e.model_dump() for e in obj.events],
                          "first_frame": obj.first_frame, "last_frame": obj.last_frame})
    return {"summary": rep["summary"], "contract": contract(rows), "contract_pre_registered": contract(rep["rows"]),
            "audit": audit["finding"], "approvable": APPROVABLE, "gates": gates(rows), "cases": cases}


LABEL_SETS = {"fresh_v1": BENCH / "real" / "fresh_v1"}
_CLIP = re.compile(r"^[a-z0-9_]+\.mp4$")


def _label_set(set_id: str) -> Path:
    if set_id not in LABEL_SETS:
        raise HTTPException(404, "unknown label set")
    return LABEL_SETS[set_id]


@app.get("/label/{set_id}")
def label_set(set_id: str) -> dict:
    """Label review: each clip's draft (rule, layout), Muse Spark's proposed labels and the person's saved labels."""
    d = _label_set(set_id)
    clips = []
    for p in sorted((d / "drafts").glob("*.json")):
        prop, saved = d / "proposals" / p.name, d / "labels" / p.name
        clips.append({"draft": json.loads(p.read_text()),
                      "proposal": json.loads(prop.read_text()) if prop.is_file() else None,
                      "saved": json.loads(saved.read_text()) if saved.is_file() else None})
    return {"set": set_id, "frozen": (d / "labels" / "MANIFEST.json").is_file(), "writable": MODE == "local",
            "clips": clips}


@app.get("/label/{set_id}/video/{clip}")
def label_video(set_id: str, clip: str) -> FileResponse:
    if not _CLIP.match(clip):
        raise HTTPException(404, "no such clip")
    f = _label_set(set_id) / "videos" / clip
    if not f.is_file():
        raise HTTPException(404, "no such clip")
    return FileResponse(f, media_type="video/mp4")


class LabelSave(BaseModel):
    objects: list[dict]
    reviewer: str


@app.post("/label/{set_id}/{clip}")
def label_save(set_id: str, clip: str, body: LabelSave) -> dict:
    """Save the person's labels for one clip (local mode only, refused once the set is frozen). Checked again by
    `real_video check --freeze` before any model runs on the clip."""
    if MODE != "local":
        raise HTTPException(403, "labels can only be saved in local mode")
    d = _label_set(set_id)
    if not _CLIP.match(clip) or not (d / "drafts" / clip.replace(".mp4", ".json")).is_file():
        raise HTTPException(404, "no such clip")
    if (d / "labels" / "MANIFEST.json").is_file():
        raise HTTPException(409, "labels are frozen")
    keys = {"description", "crosses_packing", "stood_still_s", "intended", "cross_s", "cross_dir"}
    objs = [{k: o[k] for k in keys if k in o} for o in body.objects]
    if not objs or any(not str(o.get("description", "")).strip() for o in objs):
        raise HTTPException(422, "every clip needs at least one described object")
    objs.sort(key=lambda o: (not o.get("crosses_packing"), o.get("cross_s") or 0))
    draft = json.loads((d / "drafts" / clip.replace(".mp4", ".json")).read_text())
    lab = draft | {"objects": objs,
                   "expected_overall": "FAIL" if any(o.get("intended") == "VIOLATION" for o in objs) else "PASS",
                   "labeled_by": body.reviewer, "labeled_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    lab["labeled_at"] = lab["labeled_at"][:-2] + ":" + lab["labeled_at"][-2:]
    (d / "labels").mkdir(exist_ok=True)
    (d / "labels" / clip.replace(".mp4", ".json")).write_text(json.dumps(lab, indent=1) + "\n")
    return {"saved": clip, "objects": len(objs)}


@app.get("/runs/{run_id}/ledger")
def run_ledger(run_id: str) -> dict:
    """Build (or rebuild) the run's evidence ledger: every file hash, model/request ids, holdout manifests."""
    from eventproof import ledger

    _run_file(run_id, "evidence.json")  # validates the id and that the run exists
    return ledger.write(run_id)


FINAL_REPORT = Path(__file__).resolve().parents[3] / "benchmark" / "final" / "report_final_v1.json"


@app.get("/final-report")
def final_report() -> dict:
    """The pre-registered final test report (read-only file; the final set itself is not loaded by the API)."""
    if not FINAL_REPORT.is_file():
        raise HTTPException(404, "no final report")
    return json.loads(FINAL_REPORT.read_text())


@app.get("/runs/{run_id}/challenge/files/{name}")
def challenge_file(run_id: str, name: str) -> FileResponse:
    allowed = name in studio.CHALLENGE_FILES or name in studio.AMBIGUITY_FILES or re.fullmatch(r"decisive_f\d{4}\.png", name)
    if not pipeline.RUN_ID_RE.match(run_id) or not allowed:
        raise HTTPException(400, "invalid file")
    p = pipeline.RUNS_DIR / run_id / "challenge" / name
    if not p.is_file():
        raise HTTPException(404, "not found")
    return FileResponse(p)
