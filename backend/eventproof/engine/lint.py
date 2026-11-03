"""Checks of a compiled rule against the tracks it judges, run before its verdicts are trusted (deterministic, no model).

anchor_check: a CROSSES event is judged on one point of each box, the rule's anchor (box centre or bottom centre),
set without knowing where the line was drawn (the compiler's schema has no anchor field; the default is the box
centre). If no tracked object's anchor ever crosses a line the rule depends on, while the other anchor crosses it for
some objects, the line was most likely drawn for the other point (e.g. at the wheels or feet of tall objects while the
rule anchors at the box centre) and every verdict about that line is vacuous. Found on real footage (benchmark/real/santos/FINDINGS.md): 0/8 crossings seen with the centre.
"""

from __future__ import annotations

from eventproof.engine.evaluator import evaluate
from eventproof.schemas.rules import Crosses, Occurs, VisualRule
from eventproof.schemas.tracks import TrackSet

ANCHORS = ("center", "bottom_center")


def crossing_lines(node) -> set[str]:
    """Ids of the lines a rule's check refers to through CROSSES events."""
    d = node.model_dump() if hasattr(node, "model_dump") else node
    out: set[str] = set()

    def walk(x):
        if isinstance(x, dict):
            if x.get("op") == "CROSSES":
                out.add(x["line"])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(d)
    return out


def crossers(rule: VisualRule, tracks: TrackSet, line: str, anchor: str) -> int:
    """How many tracked objects cross `line` (either direction) when boxes are reduced to `anchor`."""
    probe = rule.model_copy(update={"params": rule.params.model_copy(update={"anchor": anchor}),
                                    "check": Occurs(event=Crosses(line=line))})
    return sum(o.verdict == "PASS" for o in evaluate(probe, tracks).objects)


def anchor_check(rule: VisualRule, tracks: TrackSet) -> list[dict]:
    """One warning per line that no object crosses with the rule's anchor but some cross with the other one."""
    out = []
    for line in sorted(crossing_lines(rule.check)):
        used = rule.params.anchor
        other = next(a for a in ANCHORS if a != used)
        n_used, n_other = crossers(rule, tracks, line, used), crossers(rule, tracks, line, other)
        if n_used == 0 and n_other > 0:
            out.append({"check": "anchor", "line": line, "anchor": used, "crossers": n_used, "other_anchor": other,
                        "other_crossers": n_other,
                        "message": f"no tracked object's {used.replace('_', ' ')} ever crosses line '{line}', but "
                                   f"{n_other} object(s) cross it at the {other.replace('_', ' ')}: the line was probably "
                                   f"drawn for that point, so every verdict about it is vacuous. Redraw the line or "
                                   f"say where objects are measured in the rule text."})
    return out
