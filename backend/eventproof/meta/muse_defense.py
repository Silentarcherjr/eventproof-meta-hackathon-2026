"""Muse Spark as the defense: given one ticket (a VIOLATION verdict, the rule, the events that decided it), argue against
it by choosing from a closed menu of challenges, the same typed variants `review.robustness` can re-judge. Muse only
picks and argues; the engine decides whether a challenge actually overturns the ticket. Strict JSON schema; output is
data, never executed; responses cached by (messages, model, schema version).
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from eventproof.meta.client import LiveBudget, MetaSettings, get_client
from eventproof.meta.muse_rules import RuleCompileError

SCHEMA_VERSION = "defense-schema/1"
CACHE_DIR = Path(__file__).resolve().parents[3] / "artifacts" / "muse_cache" / "defense"

SYSTEM = """You are the defense lawyer for a driver (or other road user) who received an automated camera ticket.
You see the rule sentence, the rule the camera actually ran, and the evidence that decided the ticket.
Choose up to 4 challenges from the menu (ids only; you cannot invent others), each with a one-sentence argument a
reviewer would take seriously, and name the single strongest. If no challenge is credible, set concede=true and say why.
Do not claim facts that are not in the evidence. Output only the JSON the schema allows."""


def schema(menu_ids: list[str]) -> dict:
    ch = {"type": "object", "additionalProperties": False, "required": ["id", "argument"],
          "properties": {"id": {"type": "string", "enum": menu_ids}, "argument": {"type": "string"}}}
    return {"type": "object", "additionalProperties": False,
            "required": ["challenges", "strongest", "concede", "concession"],
            "properties": {"challenges": {"type": "array", "items": ch},
                           "strongest": {"type": "string", "enum": menu_ids + ["none"]},
                           "concede": {"type": "boolean"}, "concession": {"type": "string"}}}


def prompt(rule_text: str, rule: dict, verdict: dict, menu: list[dict]) -> str:
    ev = "\n".join(f"- {e['op']} {e['target']}: {e['status']} at frame {e.get('frame')} "
                   f"({e.get('timestamp_ms')} ms){' - ' + e['reason'] if e.get('reason') else ''}"
                   for e in verdict.get("events", []))
    opts = "\n".join(f"- {m['id']}: {m['label']}" for m in menu)
    return (f"Rule sentence: {rule_text}\nRule the camera ran (explanation): {rule.get('normalized_explanation')}\n"
            f"Measured point: {rule.get('params', {}).get('anchor')}\n"
            f"Ticket: object {verdict['object_id']} judged {verdict['verdict']}, frames {verdict['first_frame']}-"
            f"{verdict['last_frame']}.\nEngine explanation: {verdict.get('explanation')}\nDecisive events:\n{ev}\n\n"
            f"Challenge menu:\n{opts}")


class MuseDefense:
    def __init__(self, settings: MetaSettings | None = None, cache_dir: Path | None = None,
                 budget: LiveBudget | None = None, max_live_calls: int | None = None):
        self.settings = settings or MetaSettings.from_env()
        self.cache_dir = cache_dir or CACHE_DIR
        self.budget, self.max_live_calls, self.live_calls = budget, max_live_calls, 0

    def argue(self, rule_text: str, rule: dict, verdict: dict, menu: list[dict]) -> dict:
        ids = [m["id"] for m in menu]
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": prompt(rule_text, rule, verdict, menu)}]
        key = hashlib.sha256(json.dumps([messages, self.settings.muse_model, SCHEMA_VERSION]).encode()).hexdigest()
        cpath = self.cache_dir / f"{key}.json"
        if cpath.exists():
            return json.loads(cpath.read_text()) | {"cached": True}
        if self.max_live_calls is not None and self.live_calls >= self.max_live_calls:
            from eventproof.perception.sam import LiveCallLimit
            raise LiveCallLimit(f"defense: allowance {self.max_live_calls} used up")
        client = get_client(self.settings)
        if self.budget:
            self.budget.take("defense")
        t0 = time.monotonic()
        resp = client.chat.completions.create(
            model=self.settings.muse_model, messages=messages,
            response_format={"type": "json_schema", "json_schema": {"name": "defense", "schema": schema(ids),
                                                                    "strict": True}})
        self.live_calls += 1
        try:
            out = json.loads(resp.choices[0].message.content or "")
        except json.JSONDecodeError as e:
            raise RuleCompileError(f"defense returned non-JSON content: {e}") from None
        bad = [c["id"] for c in out["challenges"] if c["id"] not in ids]
        if bad or out["strongest"] not in ids + ["none"]:
            raise RuleCompileError(f"defense chose challenges outside the menu: {bad or out['strongest']}")
        rec = {"output": out, "request_id": resp.id, "model": self.settings.muse_model,
               "usage": resp.usage.model_dump() if resp.usage else {}, "latency_s": round(time.monotonic() - t0, 2)}
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cpath.write_text(json.dumps(rec, indent=2))
        return rec | {"cached": False}
