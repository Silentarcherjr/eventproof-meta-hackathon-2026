from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from eventproof.challenge.scene import INSPECTION, PACKING_LINE
from eventproof.meta import muse_rules as mr
from eventproof.meta.client import MetaSettings
from eventproof.meta.muse_rules import (
    Layout,
    LayoutLine,
    LayoutZone,
    MuseRuleCompiler,
    RuleCompileError,
    UnsupportedRule,
    build_schema,
    to_visual_rule,
)

LAYOUT = Layout(zones=[LayoutZone(zone=INSPECTION, description="inspection station")],
                lines=[LayoutLine(line=PACKING_LINE, description="packing entry")])

CROSS = {"op": "CROSSES", "line": "packing_entry", "direction": "any"}
DWELL = {"op": "DWELL", "zone": "inspection", "min_ms": 1500, "max_speed": None}


def node(op, children=(), event=None, first=None, then=None, within_ms=None):
    return {"op": op, "children": list(children), "event": event, "first": first, "then": then, "within_ms": within_ms}


GOOD = {
    "supported": True, "unsupported_reason": "", "rule_id": "Inspect before packing!",
    "entity_name": "package", "entity_concept": "blue box",
    "nodes": [node("IMPLIES", [1, 2]), node("OCCURS", event=CROSS), node("BEFORE", first=DWELL, then=CROSS)],
    "root": 0,
    "normalized_explanation": "Each blue box entering packing must first spend 1.5 s in inspection.",
    "assumptions": ["'at least 1.5 seconds' means continuously"],
}


def _walk(node, fn):
    fn(node)
    if isinstance(node, dict):
        for v in node.values():
            _walk(v, fn)
    elif isinstance(node, list):
        for v in node:
            _walk(v, fn)


def test_schema_is_strict_compatible_and_acyclic():
    s = build_schema(LAYOUT)
    assert "anyOf" not in s and s["type"] == "object"

    def strict(n):
        if isinstance(n, dict) and n.get("type") == "object":
            assert n["additionalProperties"] is False and set(n["required"]) == set(n["properties"])
        assert not (isinstance(n, dict) and ("oneOf" in n or "allOf" in n))

    _walk(s, strict)
    assert "$defs" not in s and "$ref" not in json.dumps(s), "constant-size schema: no refs to expand"
    assert len(json.dumps(s)) < 8000
    zone_enums = []
    _walk(s, lambda n: zone_enums.append(n["enum"]) if isinstance(n, dict) and "enum" in n and "zone" not in n else None)
    assert ["inspection"] in zone_enums and ["packing_entry"] in zone_enums


def test_good_output_converts_with_geometry_from_layout():
    rule = to_visual_rule(GOOD, LAYOUT)
    assert rule.rule_id == "inspect-before-packing"
    assert rule.zones == [INSPECTION] and rule.lines == [PACKING_LINE]
    assert rule.check.conclusion.first.max_speed is None and rule.check.conclusion.within_ms is None
    assert rule.check.premise.event.line == "packing_entry"


@pytest.mark.parametrize("mutate", [
    lambda o: o["nodes"][2]["first"].update(min_ms=-5),
    lambda o: o["nodes"][1]["event"].update(line="nowhere"),
    lambda o: o["nodes"].__setitem__(1, {**o["nodes"][1], "op": "EVAL"}),
    lambda o: o.update(entity_concept=""),
    lambda o: o.update(nodes=[node("AND", [1]), node("OCCURS", event=CROSS)]),  # AND needs >= 2 args
    lambda o: o["nodes"][1].update(event=None),  # OCCURS without its event
])
def test_invalid_model_output_is_rejected(mutate):
    out = copy.deepcopy(GOOD)
    mutate(out)
    with pytest.raises(ValidationError):
        to_visual_rule(out, LAYOUT)


@pytest.mark.parametrize("nodes,root,msg", [
    ([node("NOT", [0])], 0, "twice"),                                                      # cycle
    ([node("AND", [1, 1]), node("OCCURS", event=CROSS)], 0, "twice"),                       # shared node
    ([node("OCCURS", event=CROSS), node("OCCURS", event=CROSS)], 0, "unused"),              # ignored node
    ([node("NOT", [5])], 0, "out of range"),
    ([node("IMPLIES", [1]), node("OCCURS", event=CROSS)], 0, "premise, conclusion"),
    ([node("OCCURS", [1], event=CROSS), node("OCCURS", event=CROSS)], 0, "must not have children"),
])
def test_malformed_node_graphs_are_rejected(nodes, root, msg):
    with pytest.raises(RuleCompileError, match=msg):
        to_visual_rule({**GOOD, "nodes": nodes, "root": root}, LAYOUT)


def test_unsupported_is_reported_not_guessed():
    with pytest.raises(UnsupportedRule, match="helmet"):
        to_visual_rule({**GOOD, "supported": False, "unsupported_reason": "helmet colour is not observable"}, LAYOUT)


class FakeMuse:
    def __init__(self, outputs):
        self.outputs, self.calls = list(outputs), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls.append(copy.deepcopy(kw))
        out = self.outputs.pop(0)
        return SimpleNamespace(id=f"req-{len(self.calls)}", choices=[SimpleNamespace(message=SimpleNamespace(
            content=out if isinstance(out, str) else json.dumps(out)))], usage=None)


@pytest.fixture
def settings():
    return MetaSettings(api_key="test-key-not-real", base_url="https://example.invalid/v1",
                        muse_model="muse-spark-1.3", sam_model="sam-3.1", budget_usd=1)


def test_compiler_retries_once_with_the_validation_error(tmp_path, monkeypatch, settings):
    bad = copy.deepcopy(GOOD)
    bad["nodes"][2]["first"]["min_ms"] = -5
    fake = FakeMuse([bad, GOOD])
    monkeypatch.setattr(mr, "get_client", lambda s: fake)
    c = MuseRuleCompiler(settings, cache_dir=tmp_path)
    res = c.compile("Every blue box must spend 1.5 s in inspection before packing.", LAYOUT)
    assert res.attempts == 2 and res.request_ids == ["req-1", "req-2"] and not res.cached
    rf = fake.calls[0]["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True
    assert "failed validation" in fake.calls[1]["messages"][-1]["content"]
    again = c.compile("Every blue box must spend 1.5 s in inspection before packing.", LAYOUT)
    assert again.cached and again.rule == res.rule and len(fake.calls) == 2
    assert "test-key-not-real" not in next(tmp_path.glob("*.json")).read_text()


def test_compiler_gives_up_and_never_caches_invalid_rules(tmp_path, monkeypatch, settings):
    bad = copy.deepcopy(GOOD)
    bad["nodes"][1]["event"]["line"] = "nowhere"
    monkeypatch.setattr(mr, "get_client", lambda s: FakeMuse([bad, bad]))
    with pytest.raises(RuleCompileError, match="after 2 attempts"):
        MuseRuleCompiler(settings, cache_dir=tmp_path).compile("x", LAYOUT)
    assert not list(tmp_path.glob("*.json"))
    monkeypatch.setattr(mr, "get_client", lambda s: FakeMuse(["not json"]))
    with pytest.raises(RuleCompileError, match="non-JSON"):
        MuseRuleCompiler(settings, cache_dir=tmp_path).compile("x", LAYOUT)


def test_real_muse_outputs_still_convert():
    """Outputs of live muse-spark-1.3 calls (2026-10-27) keep compiling to the same rules."""
    from pathlib import Path

    data = json.loads((Path(__file__).parent / "fixtures" / "muse" / "real_compiles.json").read_text())
    assert len(data["outputs"]) >= 4
    for item in data["outputs"].values():
        rule = to_visual_rule(item["raw_output"], LAYOUT)
        assert rule.entity.concept == "blue box"
        assert rule.check.op == "IMPLIES"
