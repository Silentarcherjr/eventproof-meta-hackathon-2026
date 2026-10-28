"""Muse Spark as repair proposer: counterexample context -> bounded `RulePatch` proposals.

Implements the same `Proposer` interface as the deterministic baseline. Muse sees only the
`RepairContext` (the counterexample, what a reviewer saw on it, and aggregate outcomes on the visible dev
cases); the loop checks that context for holdout leaks before calling `propose`, and the independent
grader decides acceptance on the hidden holdout. Muse's own predictions are recorded, never trusted.

Up to MAX_ROUNDS rounds: after each round the proposals are screened on the VISIBLE dev scenes (does it fix
the counterexample, how many dev regressions); if none is clean, those dev numbers go back to Muse for a
revision. The hidden holdout is never used here. All proposals of all rounds are returned and graded.

Output is strict JSON (constant-size schema), validated by the `RulePatch` model; invalid proposals are
dropped and reported, never applied. Responses are cached by (conversation, model, schema version).
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from eventproof.challenge.families import FAMILIES
from eventproof.challenge.runner import Perceiver, mock_perceiver, run_case
from eventproof.meta.client import MetaSettings, get_client
from eventproof.meta.muse_rules import _nullable, _obj, _op
from eventproof.repair.patch import RulePatch
from eventproof.repair.proposer import Proposal, RepairContext

SCHEMA_VERSION = "repair-schema/1"
MAX_ROUNDS = 3
CACHE_DIR = Path(__file__).resolve().parents[3] / "artifacts" / "muse_cache" / "repair"

SYSTEM = """You repair a video rule written in EventProof's DSL after a counterexample showed it gives the wrong verdict.
You may ONLY propose bounded patches made of these operations (max 3 per patch):
- set_dwell_min_ms(zone, value): the DWELL threshold in ms (100-10000)
- set_dwell_max_speed(zone, max_speed): make DWELL count only time spent (nearly) still; speed in frame-widths per
  second over ~1/3 s; 0.05 means "stopped" (0.01-0.5)
- set_max_gap_frames(value): unobserved frames bridged inside one track (0-30); longer gaps make results UNKNOWN
- set_min_confidence(value): ignore detections below this confidence (0-0.95)
Semantics: DWELL(zone, min_ms) is true once the object has been continuously inside the zone for min_ms.
The rule is checked per tracked object. A patch is accepted only if it fixes the counterexample AND causes no
regression on unseen cases, so prefer the change that captures the intent behind the rule text over the
smallest numeric tweak that flips this one case. Propose 1 to 3 alternatives, best first."""


def _schema() -> dict:
    zone = {"type": "string"}
    op = {"anyOf": [
        _obj({"op": _op("set_dwell_min_ms"), "zone": zone, "value": {"type": "number"}}),
        _obj({"op": _op("set_dwell_max_speed"), "zone": zone, "max_speed": {"type": "number"}}),
        _obj({"op": _op("set_max_gap_frames"), "value": {"type": "integer"}}),
        _obj({"op": _op("set_min_confidence"), "value": {"type": "number"}}),
    ]}
    proposal = _obj({
        "ops": {"type": "array", "items": op, "description": "1 to 3 operations"},
        "rationale": {"type": "string", "description": "why this captures the intended rule"},
        "expected_effect": {"type": "string", "description": "what changes on the counterexample and in general"},
        "confidence": _nullable({"type": "number", "description": "0-1, your own estimate"}),
    })
    return _obj({"diagnosis": {"type": "string", "description": "spec error or perception error, and why"},
                 "proposals": {"type": "array", "items": proposal, "description": "1 to 3, best first"}})


def user_prompt(ctx: RepairContext, rule_text: str | None) -> str:
    rule = ctx.detector.rule.model_dump(mode="json", include={"entity", "check", "params"}) if ctx.detector.rule else {
        "template": "IMPLIES(OCCURS(CROSSES packing_entry), BEFORE(DWELL inspection >= dwell_ms, CROSSES packing_entry))",
        "dwell_ms": ctx.detector.dwell_ms, "max_gap_frames": ctx.detector.max_gap_frames}
    cx = ctx.counterexample
    dev = Counter((r.family, r.outcome) for r in ctx.dev_results)
    dev_lines = "\n".join(f"- {f}: {o} x{n}" for (f, o), n in sorted(dev.items()))
    return (f"Rule text written by the user:\n{rule_text or '(not available)'}\n\n"
            f"Rule as compiled (JSON):\n{json.dumps(rule)}\n\n"
            f"Counterexample ({cx.family} scene): the rule said {cx.detector_verdict}, the reviewed truth is {cx.intended} "
            f"({cx.outcome}; with perfect tracks the rule says {cx.oracle_verdict}).\n"
            + "\n".join(f"- {e}" for e in ctx.evidence)
            + f"\n\nOutcomes of the current rule on {len(ctx.dev_results)} visible dev scenes "
            f"(perception: {ctx.perception}):\n" + dev_lines)


class MuseProposer:
    def __init__(self, settings: MetaSettings | None = None, rule_text: str | None = None, cache_dir: Path | None = None,
                 perceiver: Perceiver = mock_perceiver, max_rounds: int = MAX_ROUNDS):
        self.settings = settings or MetaSettings.from_env()
        self.name = self.settings.muse_model
        self.rule_text, self.perceiver, self.max_rounds = rule_text, perceiver, max_rounds
        self.cache_dir = cache_dir or CACHE_DIR
        self.live_calls = 0
        self.last: dict = {}

    def _call(self, messages: list[dict]) -> tuple[dict, str, dict, bool]:
        key = hashlib.sha256(json.dumps([messages, self.settings.muse_model, SCHEMA_VERSION]).encode()).hexdigest()
        cpath = self.cache_dir / f"{key}.json"
        if cpath.exists():
            c = json.loads(cpath.read_text())
            return c["output"], c["request_id"], c["usage"], True
        client = get_client(self.settings)
        resp = client.chat.completions.create(
            model=self.settings.muse_model, messages=messages,
            response_format={"type": "json_schema",
                             "json_schema": {"name": "eventproof_repair", "schema": _schema(), "strict": True}})
        self.live_calls += 1
        out = json.loads(resp.choices[0].message.content or "{}")
        usage = resp.usage.model_dump() if resp.usage else {}
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cpath.write_text(json.dumps({"output": out, "request_id": resp.id, "usage": usage}, indent=2))
        return out, resp.id, usage, False

    def _screen(self, ctx: RepairContext, patch: RulePatch) -> dict:
        """Visible-data check only: origin scenes + dev scenes."""
        fixes = all(run_case(s, ctx.detector.rule_for(s, patch), self.perceiver).outcome == "correct"
                    for s in ctx.origin_scenes)
        regress = fixed = 0
        examples: list[str] = []
        for r in ctx.dev_results:
            s = FAMILIES[r.family](r.seed)
            after = run_case(s, ctx.detector.rule_for(s, patch), self.perceiver)
            ok = after.outcome == "correct"
            if r.outcome == "correct" and not ok:
                regress += 1
                if len(examples) < 5:  # what a reviewer would point at on a visible clip
                    facts = "; ".join(f"object {t.object_id} stood still {t.station_stop_ms:.0f} ms, labelled {t.intended}"
                                      for t in after.truths)
                    examples.append(f"{r.family}: {facts}; patched rule says {after.detector_verdict} (was correct)")
            fixed += r.outcome != "correct" and ok
        return {"fixes_counterexample": fixes, "dev_regressions": regress, "dev_fixed": fixed,
                "dev_cases": len(ctx.dev_results), "regression_examples": examples}

    def propose(self, ctx: RepairContext) -> list[Proposal]:
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_prompt(ctx, self.rule_text)}]
        proposals: list[Proposal] = []
        rounds = []
        for rnd in range(1, self.max_rounds + 1):
            out, rid, usage, cached = self._call(messages)
            batch, rejected, feedback = [], [], []
            for i, p in enumerate(out.get("proposals", [])[:3]):
                try:
                    patch = RulePatch.model_validate({"ops": p.get("ops", [])})
                except ValidationError as e:
                    rejected.append({"index": i, "ops": p.get("ops"), "error": str(e.errors()[0]["msg"])})
                    feedback.append(f"proposal {i + 1}: invalid ({e.errors()[0]['msg']})")
                    continue
                screen = self._screen(ctx, patch)
                batch.append(Proposal(
                    proposal_id=f"{self.name}-r{rnd}-{i}", proposer=self.name, patch=patch,
                    rationale=p.get("rationale", ""),
                    expected_effect={"model_claim": p.get("expected_effect", ""), "model_confidence": p.get("confidence"),
                                     "round": rnd, "request_id": rid, "cached": cached, "dev_screen": screen}))
                feedback.append(f"proposal {i + 1} ({patch.describe()}): fixes counterexample="
                                f"{screen['fixes_counterexample']}, dev regressions={screen['dev_regressions']}, "
                                f"dev fixed={screen['dev_fixed']} of {screen['dev_cases']}"
                                + "".join(f"\n    e.g. {x}" for x in screen["regression_examples"]))
            proposals += batch
            rounds.append({"round": rnd, "diagnosis": out.get("diagnosis", ""), "request_id": rid, "cached": cached,
                           "usage": usage, "invalid_proposals": rejected})
            clean = any(p.expected_effect["dev_screen"]["fixes_counterexample"]
                        and p.expected_effect["dev_screen"]["dev_regressions"] == 0 for p in batch)
            if clean or rnd == self.max_rounds:
                break
            messages += [{"role": "assistant", "content": json.dumps(out)},
                         {"role": "user", "content": "Results of your proposals on the visible dev scenes:\n"
                          + "\n".join(feedback) + "\nNone fixes the counterexample without dev regressions. Revise."}]
        self.last = {"rounds": rounds, "diagnosis": rounds[0]["diagnosis"]}
        return proposals
