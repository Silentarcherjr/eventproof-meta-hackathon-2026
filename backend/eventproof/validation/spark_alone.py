"""Baseline: Muse Spark judges a rule straight from the video, with no typed rule, no SAM tracks and no engine
(pre-registered in `benchmark/real/spark_alone/PREREGISTRATION.md`). Same clips, rule text, layout and frozen labels as
the real-video runs, so the two approaches are compared on identical inputs.

    uv run python -m eventproof.validation.spark_alone run --labels ../benchmark/real/novisad/labels \
        --videos ../benchmark/real/novisad/videos --runs 5 --max-live-calls 10 \
        --out ../benchmark/real/spark_alone/report.json

Each call uploads the clip (Files API) and asks Muse Spark 1.3 (Responses API, input_video) for a strict-JSON verdict.
Raw responses are cached by (clip sha256, prompt, run index) and committed, so the report recomputes with 0 calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from eventproof.meta.client import LiveCallLimit, MetaSettings, get_client
from eventproof.validation.evaluate import ROOT, _git_head, wilson
from eventproof.validation.real_video import ClipLabel, load_labels, sha256_file

DIR = ROOT / "benchmark" / "real" / "spark_alone"
CACHE = DIR / "cache"
PROMPT_VERSION = "spark-alone/1"

SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["crossings", "overall", "notes"],
    "properties": {
        "crossings": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["description", "approx_cross_time_s", "waited_s", "verdict"],
            "properties": {"description": {"type": "string"}, "approx_cross_time_s": {"type": "number"},
                           "waited_s": {"type": "number"},
                           "verdict": {"type": "string", "enum": ["PASS", "VIOLATION"]}}}},
        "overall": {"type": "string", "enum": ["PASS", "FAIL"]},
        "notes": {"type": "string"},
    },
}


def prompt(label: ClipLabel, duration_s: float, fps: float, size: tuple[int, int]) -> str:
    zones = "\n".join(f"- zone '{z.zone.id}': {z.description}; polygon (x, y as fractions of width, height, origin "
                      f"top-left): {[list(p) for p in z.zone.polygon]}" for z in label.layout.zones)
    lines = "\n".join(f"- line '{ln.line.id}': {ln.description}; from {list(ln.line.a)} to {list(ln.line.b)}"
                      for ln in label.layout.lines)
    entity = label.rule_text.split()[1] if len(label.rule_text.split()) > 1 else "object"
    return (f"You are checking a rule on a video ({size[0]}x{size[1]} px, {fps:g} fps, {duration_s:.1f} s).\n"
            f"Rule: {label.rule_text}\nLayout:\n{zones}\n{lines}\n"
            f"Watch the whole video. List every {entity} whose position crosses the line '{label.packing_line}' during "
            "the video, in crossing order, with the approximate crossing time, how long it waited in the zone "
            "before crossing, and whether it satisfies the rule (PASS) or not (VIOLATION). Objects that never cross do "
            "not need to be listed. overall is FAIL if any listed object is a VIOLATION, else PASS. Answer in JSON only.")


def _key(clip_sha: str, text: str, run: int, model: str) -> str:
    return hashlib.sha256(json.dumps([clip_sha, text, run, model, PROMPT_VERSION]).encode()).hexdigest()


class SparkAlone:
    def __init__(self, settings: MetaSettings | None = None, cache_dir: Path = CACHE, max_live_calls: int = 0):
        self.settings = settings or MetaSettings.from_env()
        self.cache_dir, self.max_live_calls, self.live_calls = cache_dir, max_live_calls, 0

    def judge(self, video: Path, text: str, run: int) -> dict:
        vsha = sha256_file(video)
        cpath = self.cache_dir / f"{_key(vsha, text, run, self.settings.muse_model)}.json"
        if cpath.exists():
            return json.loads(cpath.read_text()) | {"cached": True}
        if self.live_calls >= self.max_live_calls:
            raise LiveCallLimit(f"Muse Spark (video baseline): allowance {self.max_live_calls} used up")
        client = get_client(self.settings)
        t0 = time.monotonic()
        with video.open("rb") as fh:
            up = client.files.create(file=fh, purpose="user_data")
        resp = client.responses.create(
            model=self.settings.muse_model,
            input=[{"role": "user", "content": [{"type": "input_text", "text": text},
                                                 {"type": "input_video", "file_id": up.id}]}],
            text={"format": {"type": "json_schema", "name": "verdict", "schema": SCHEMA, "strict": True}})
        self.live_calls += 1
        raw = resp.output_text or ""
        try:
            parsed, error = json.loads(raw), None
        except json.JSONDecodeError as e:
            parsed, error = None, f"non-JSON output: {e}"
        rec = {"model": self.settings.muse_model, "response_id": resp.id, "video_sha256": vsha, "run": run,
               "prompt_version": PROMPT_VERSION, "raw": raw, "parsed": parsed, "error": error,
               "usage": resp.usage.model_dump() if resp.usage else {}, "latency_s": round(time.monotonic() - t0, 2)}
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cpath.write_text(json.dumps(rec, indent=1) + "\n")
        return rec | {"cached": False}


def score(label: ClipLabel, out: dict | None) -> dict:
    truth_cross = [o for o in label.objects if o.crosses_packing]
    truth_viol = sum(o.intended == "VIOLATION" for o in truth_cross)
    if not out:
        return {"valid": False}
    got = out["crossings"]
    return {"valid": True, "overall": out["overall"], "overall_agrees": out["overall"] == label.expected_overall,
            "crossings_reported": len(got), "crossings_true": len(truth_cross),
            "violations_reported": sum(c["verdict"] == "VIOLATION" for c in got), "violations_true": truth_viol}


def run(labels_dir: Path, videos_dir: Path, runs: int, judge: SparkAlone) -> dict:
    from fractions import Fraction

    from eventproof.video.ingest import probe

    clips = []
    for p, label in load_labels(labels_dir):
        video = videos_dir / label.clip
        if sha256_file(video) != label.clip_sha256:
            raise SystemExit(f"{video} does not match its frozen label")
        data = probe(video)
        v = next(s for s in data["streams"] if s.get("codec_type") == "video")
        text = prompt(label, float(data["format"]["duration"]), float(Fraction(v["avg_frame_rate"])),
                      (v["width"], v["height"]))
        rows = []
        for r in range(runs):
            rec = judge.judge(video, text, r)
            rows.append({"run": r, "response_id": rec["response_id"], "cached": rec["cached"], "error": rec["error"],
                         "usage": rec["usage"], **score(label, rec["parsed"]), "answer": rec["parsed"]})
        clips.append({"label_file": p.name, "clip": label.clip, "clip_sha256": label.clip_sha256,
                      "expected_overall": label.expected_overall, "prompt_sha256": hashlib.sha256(text.encode()).hexdigest(),
                      "runs": rows})
    valid = [r for c in clips for r in c["runs"] if r["valid"]]
    k = sum(r["overall_agrees"] for r in valid)
    exact = sum(r["violations_reported"] == r["violations_true"] and r["crossings_reported"] == r["crossings_true"]
                for r in valid)
    return {"schema": "eventproof-spark-alone/1", "preregistration": "benchmark/real/spark_alone/PREREGISTRATION.md",
            "model": judge.settings.muse_model, "prompt_version": PROMPT_VERSION, "runs_per_clip": runs,
            "live_calls_this_run": judge.live_calls,
            "summary": {"calls": sum(len(c["runs"]) for c in clips), "valid": len(valid), "overall_agree": k,
                        "overall_agree_ci95": wilson(k, len(valid)), "counts_exact": exact},
            "clips": clips}


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--labels", type=Path, required=True)
    r.add_argument("--videos", type=Path, required=True)
    r.add_argument("--runs", type=int, default=5)
    r.add_argument("--max-live-calls", type=int, default=0)
    r.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"{a.out} exists; the first report is kept")
    rep = run(a.labels, a.videos, a.runs, SparkAlone(max_live_calls=a.max_live_calls))
    rep["code_commit"] = _git_head()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, indent=2) + "\n")
    print(json.dumps(rep["summary"]))


if __name__ == "__main__":
    main()
