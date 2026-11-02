"""Field repair: repair a rule from failures seen on real footage, and accept a patch only if it holds on real footage from
another city AND on the synthetic hidden holdout. Pre-registered in `benchmark/field_repair/PREREGISTRATION.md`.

Starting point (R0): for each real clip, the rule Muse Spark compiled for it plus the repair accepted on synthetic data
(r3-0), i.e. the rule as it would be deployed after the synthetic stage; it fails in the field (16/30).

- Dev (visible to the proposers): Novi Sad clips a/b, their frozen labels and the engine's measurements on the committed
  SAM 3.1 tracks (per car: time in the zone, longest still run under several speed thresholds, verdict now).
- Real holdout (never shown): Wroclaw w1/w2/w3. Synthetic holdout: holdout_v2 (200 scenes) with the warehouse rule of the
  demo run + r3-0.
- Accepted only if: the dev failures are fixed; real-holdout correct strictly improves with 0 regressions; synthetic
  holdout has 0 regressions and no new false PASS.
- Proposers: Muse Spark (strict JSON, bounded ops: set_dwell_min_ms, set_dwell_max_speed; one revision round with dev-only
  feedback) and a deterministic grid baseline. Every proposal is graded; none is chosen by holdout score.

    uv run python -m eventproof.validation.field_repair run --max-live-calls 2 --out ../benchmark/field_repair/report.json
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import time
from pathlib import Path

from eventproof.challenge.holdout import DEFAULT_PATH as HOLDOUT
from eventproof.challenge.holdout import load_frozen, manifest_sha256
from eventproof.challenge.runner import mock_perceiver, run_case
from eventproof.engine.evaluator import build_tracks, evaluate, zone_steps
from eventproof.meta.client import LiveCallLimit, MetaSettings, get_client
from eventproof.repair.grader import metrics
from eventproof.repair.patch import PatchError, RulePatch, apply_patch
from eventproof.repair.proposer import DetectorConfig
from eventproof.schemas.rules import Dwell, VisualRule, iter_events
from eventproof.schemas.tracks import TrackSet
from eventproof.validation.evaluate import ROOT, _git_head
from eventproof.validation.real_video import load_labels, load_repair, match_objects, perceive

DEV = (("benchmark/real/novisad", "report_novisad.json"),)
HOLD = (("benchmark/real/traffic_v2", "report_wroclaw.json"), ("benchmark/real/traffic_v3", "report_wroclaw_w3.json"))
DEMO_RUN = ROOT / "docs" / "evidence" / "runs" / "20261028T023754Z-a922b5bb"
OUT_DIR = ROOT / "benchmark" / "field_repair"
CACHE = OUT_DIR / "cache"
SPEEDS = (0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.1)
PROMPT_VERSION = "field-repair/1"


# ---- data ----------------------------------------------------------------------------------------------------------

def clips(sets) -> list[dict]:
    out = []
    for folder, rep_name in sets:
        d = ROOT / folder
        labels = {lb.clip: lb for _, lb in load_labels(d / "labels")}
        for c in json.loads((d / rep_name).read_text())["clips"]:
            run = d / "runs" / c["run_id"]
            out.append({"clip": c["clip"], "label": labels[c["clip"]],
                        "rule": VisualRule.model_validate(
                            json.loads((run / "evidence.json").read_text())["rule"]["compiled_rule"]),
                        "tracks": TrackSet.model_validate_json((run / "tracks.json").read_text())})
    return out


def r0(rule: VisualRule) -> VisualRule:
    return apply_patch(rule, load_repair().patch)


def judge(clip: dict, rule: VisualRule) -> list[dict]:
    """Per labelled object: intended, verdict, matched track id."""
    lab, tracks = clip["label"], clip["tracks"]
    verdict = {o.object_id: o.verdict for o in evaluate(rule, tracks).objects}
    pair = dict(match_objects(lab.objects, perceive(rule, tracks, lab.packing_line)).pairs)
    return [{"i": i, "intended": o.intended, "verdict": verdict.get(pair.get(i)), "object_id": pair.get(i),
             "description": o.description} for i, o in enumerate(lab.objects)]


def measurements(clip: dict, rule: VisualRule, object_id: int | None) -> dict:
    """What the engine measures for one track: time inside the zone and the longest still run per speed threshold."""
    if object_id is None:
        return {"tracked": False}
    d = next(e for e in iter_events(rule.check) if isinstance(e, Dwell))
    t = next(t for t in build_tracks(rule, clip["tracks"]) if t.object_id == object_id)
    run = lambda s: max((st.counted_ms for st in zone_steps(d.model_copy(update={"max_speed": s}), t, rule)), default=0)  # noqa: E731
    return {"tracked": True, "in_zone_s": round(run(None) / 1000, 2),
            "longest_still_s": {str(s): round(run(s) / 1000, 2) for s in SPEEDS}}


# ---- proposers -----------------------------------------------------------------------------------------------------

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["diagnosis", "proposals"], "properties": {
    "diagnosis": {"type": "string"},
    "proposals": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                             "required": ["min_ms", "max_speed", "rationale"], "properties": {
        "min_ms": {"type": "number", "description": "DWELL min_ms, 100-10000"},
        "max_speed": {"type": "number", "description": "DWELL max_speed in frame widths per second, 0.01-0.5"},
        "rationale": {"type": "string"}}}}}}


def dev_brief(dev: list[dict]) -> str:
    rows = []
    for c in dev:
        rule = r0(c["rule"])
        for j in judge(c, rule):
            m = measurements(c, rule, j["object_id"])
            rows.append({"clip": c["clip"], "object": j["description"], "labelled": j["intended"], "rule_now": j["verdict"],
                         **m})
    d = next(e for e in iter_events(r0(dev[0]["rule"]).check) if isinstance(e, Dwell))
    return (f"Rule text: {dev[0]['label'].rule_text}\nCurrent DWELL: min_ms={d.min_ms}, max_speed={d.max_speed} "
            "(only time while the car's center moves at most max_speed frame widths per second, measured over 1/3 s, "
            "counts; the run must be continuous). Truth: a car that crosses must have stood still >= 1.0 s.\n"
            "Development clips (real drone footage). Per labelled car, measured on its SAM 3.1 track:\n"
            + "\n".join(json.dumps(r) for r in rows))


SYSTEM = """You repair a video rule's thresholds so its verdicts match labelled real footage. You may only change the DWELL
min_ms and max_speed. Propose 1 to 3 patches. Prefer patches that fix every labelled car shown, with margin, and that
would also hold on other real cameras (other distances and perspectives) you have not seen. Output only the JSON."""


class MuseFieldProposer:
    name = "muse-spark-1.3"

    def __init__(self, max_live: int, settings: MetaSettings | None = None, cache: Path = CACHE):
        self.settings = settings or MetaSettings.from_env()
        self.max_live, self.live, self.cache, self.trace = max_live, 0, cache, []

    def _call(self, messages: list[dict], tag: str) -> dict:
        key = hashlib.sha256(json.dumps([messages, self.settings.muse_model, PROMPT_VERSION]).encode()).hexdigest()
        p = self.cache / f"{key}.json"
        if p.exists():
            c = json.loads(p.read_text())
            self.trace.append({"round": tag, "request_id": c["request_id"], "cached": True})
            return c["out"]
        if self.live >= self.max_live:
            raise LiveCallLimit(f"field repair: allowance {self.max_live} used up")
        t0 = time.monotonic()
        resp = get_client(self.settings).chat.completions.create(
            model=self.settings.muse_model, messages=messages,
            response_format={"type": "json_schema",
                             "json_schema": {"name": "field_repair", "schema": SCHEMA, "strict": True}})
        self.live += 1
        out = json.loads(resp.choices[0].message.content or "{}")
        self.cache.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"out": out, "request_id": resp.id, "messages": messages,
                                 "usage": resp.usage.model_dump() if resp.usage else {},
                                 "latency_s": round(time.monotonic() - t0, 2)}, indent=1))
        self.trace.append({"round": tag, "request_id": resp.id, "cached": False})
        return out

    def propose(self, dev: list[dict]) -> list[dict]:
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": dev_brief(dev)}]
        out1 = self._call(msgs, "1")
        props = [dict(p, round=1) for p in out1["proposals"][:3]]
        fb = []
        for i, p in enumerate(props):
            res = dev_result(dev, patch_of(p))
            fb.append(f"proposal {i + 1} (min_ms={p['min_ms']}, max_speed={p['max_speed']}): dev cars right "
                      f"{res['right']}/{res['n']}" + (f"; still wrong: {res['wrong']}" if res["wrong"] else ""))
        msgs2 = msgs + [{"role": "assistant", "content": json.dumps(out1)},
                        {"role": "user", "content": "Results on the development clips:\n" + "\n".join(fb)
                         + "\nRevise: propose 1 to 3 patches."}]
        out2 = self._call(msgs2, "2")
        return props + [dict(p, round=2) for p in out2["proposals"][:3]], [out1["diagnosis"], out2["diagnosis"]]


def grid() -> list[dict]:
    return [{"min_ms": ms, "max_speed": s, "rationale": "grid", "round": 0}
            for s, ms in itertools.product((0.03, 0.04, 0.05, 0.06), (800.0, 1000.0, 1200.0, 1500.0))]


# ---- grading -------------------------------------------------------------------------------------------------------

def patch_of(p: dict) -> RulePatch:
    return RulePatch.model_validate({"ops": [
        {"op": "set_dwell_min_ms", "zone": "inspection", "value": min(10_000.0, max(100.0, float(p["min_ms"])))},
        {"op": "set_dwell_max_speed", "zone": "inspection", "max_speed": min(0.5, max(0.01, float(p["max_speed"])))}]})


def dev_result(dev: list[dict], patch: RulePatch) -> dict:
    rows = [(c["clip"], j) for c in dev for j in judge(c, apply_patch(r0(c["rule"]), patch))]
    wrong = [f"{clip}: {j['description'][:40]} labelled {j['intended']}, now {j['verdict']}" for clip, j in rows
             if j["verdict"] != j["intended"]]
    return {"n": len(rows), "right": len(rows) - len(wrong), "wrong": wrong}


def real_scores(sets: list[dict], patch: RulePatch | None) -> list[bool]:
    out = []
    for c in sets:
        rule = r0(c["rule"])
        rule = apply_patch(rule, patch) if patch else rule
        out += [j["verdict"] == j["intended"] for j in judge(c, rule)]
    return out


class SyntheticHoldout:
    def __init__(self):
        rule = VisualRule.model_validate(json.loads((DEMO_RUN / "evidence.json").read_text())["rule"]["compiled_rule"])
        self.det = DetectorConfig(rule=apply_patch(rule, load_repair().patch))
        self.manifest, self.scenes = load_frozen(HOLDOUT)
        self.sha = manifest_sha256(HOLDOUT)
        self.before = [run_case(s, self.det.rule_for(s), mock_perceiver) for s in self.scenes]

    def grade(self, patch: RulePatch) -> dict:
        after = [run_case(s, self.det.rule_for(s, patch), mock_perceiver) for s in self.scenes]
        mb, ma = metrics(self.before), metrics(after)
        reg = sum(b.outcome == "correct" and a.outcome != "correct" for b, a in zip(self.before, after, strict=True))
        return {"before": mb.correct, "after": ma.correct, "n": ma.n, "regressions": reg,
                "false_pass_before": mb.false_pass, "false_pass_after": ma.false_pass}


def grade(p: dict, dev: list[dict], hold: list[dict], syn: SyntheticHoldout, hold_before: list[bool]) -> dict:
    try:
        patch = patch_of(p)
    except (PatchError, ValueError) as e:
        return {"proposal": p, "accepted": False, "reasons": [f"unsafe patch: {e}"]}
    d = dev_result(dev, patch)
    after = real_scores(hold, patch)
    reg = sum(b and not a for b, a in zip(hold_before, after, strict=True))
    s = syn.grade(patch)
    reasons = []
    if d["wrong"]:
        reasons.append(f"dev not fixed ({d['right']}/{d['n']})")
    if reg:
        reasons.append(f"{reg} real-holdout regression(s)")
    if sum(after) <= sum(hold_before):
        reasons.append(f"real holdout did not improve ({sum(hold_before)} -> {sum(after)})")
    if s["regressions"]:
        reasons.append(f"{s['regressions']} synthetic-holdout regression(s)")
    if s["false_pass_after"] > s["false_pass_before"]:
        reasons.append("synthetic false PASS increased")
    ok = not reasons
    return {"proposal": p, "patch": patch.describe(), "dev": d, "real_holdout": {"n": len(after), "before": sum(hold_before),
            "after": sum(after), "regressions": reg}, "synthetic_holdout": s, "accepted": ok,
            "reasons": reasons or [f"verified: real holdout {sum(hold_before)} -> {sum(after)}/{len(after)}, synthetic "
                                   f"{s['before']} -> {s['after']}/{s['n']}, 0 regressions"]}


def run(max_live: int, proposer: MuseFieldProposer | None = None) -> dict:
    dev, hold = clips(DEV), clips(HOLD)
    syn = SyntheticHoldout()
    hold_before = real_scores(hold, None)
    muse = proposer or MuseFieldProposer(max_live)
    muse_props, diagnosis = muse.propose(dev)
    out = {"schema": "eventproof-field-repair/1", "preregistration": "benchmark/field_repair/PREREGISTRATION.md",
           "start_rule": "compiled rule + synthetic-accepted repair r3-0", "dev": [c["clip"] for c in dev],
           "real_holdout": [c["clip"] for c in hold], "synthetic_holdout": {"name": syn.manifest.name, "sha256": syn.sha},
           "dev_before": dev_result(dev, load_repair().patch) | {"note": "r0 = this patch already applied"},
           "muse": {"diagnosis": diagnosis, "trace": muse.trace,
                    "decisions": [grade(p, dev, hold, syn, hold_before) for p in muse_props]},
           "baseline_grid": {"decisions": [grade(p, dev, hold, syn, hold_before) for p in grid()]},
           "live_calls_this_run": muse.live}
    for k in ("muse", "baseline_grid"):
        dec = out[k]["decisions"]
        out[k]["accepted"] = sum(d["accepted"] for d in dec)
        out[k]["first_accepted"] = next((d for d in dec if d["accepted"]), None)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--max-live-calls", type=int, default=0)
    r.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"{a.out} exists; the first report is kept")
    rep = run(a.max_live_calls)
    rep["code_commit"] = _git_head()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, indent=2) + "\n")
    print(json.dumps({k: {kk: rep[k][kk] for kk in ("accepted",)} | {"n": len(rep[k]["decisions"])}
                      for k in ("muse", "baseline_grid")} | {"live": rep["live_calls_this_run"]}))


if __name__ == "__main__":
    main()
