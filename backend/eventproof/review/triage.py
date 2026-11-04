"""Contract acceptance: what a city could write into a camera vendor's contract, filled in from labelled real tickets.

From the ticket study (benchmark/tickets/report.json):
- the false-ticket rate it has measured: wrong tickets / tickets, with its Wilson 95 % upper bound, for every ticket
  and for the tickets an "auto-issue only ROBUST" policy would send without review;
- how many labelled, error-free tickets a city would need before it could state "false tickets <= 2 %" or "<= 5 %"
  (the smallest n whose Wilson upper bound for 0/n is at or under the target);
- the queue the policy creates: auto-issued vs held for a human reviewer.
Deterministic; no model. This states what the evidence supports, not a certification.
"""

from __future__ import annotations

import math


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """Wilson 95 % interval (same formula as validation.evaluate.wilson; the API may not import the validation package,
    which keeps selection code away from the final test set)."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 4), round(c + h, 4))


def labels_needed(target: float, limit: int = 100_000) -> int:
    """Smallest n with Wilson 95 % upper bound of 0/n <= target."""
    lo, hi = 1, limit
    while lo < hi:
        mid = (lo + hi) // 2
        if wilson(0, mid)[1] <= target:
            hi = mid
        else:
            lo = mid + 1
    return lo


def contract(rows: list[dict]) -> dict:
    tickets = [r for r in rows if r.get("verdict") == "VIOLATION" and r.get("status")]
    robust = [r for r in tickets if r["status"] == "ROBUST"]
    held = [r for r in tickets if r["status"] != "ROBUST"]

    def rate(xs: list[dict]) -> dict:
        wrong = sum(r["correct"] == "wrong" for r in xs)
        lo, hi = wilson(wrong, len(xs)) if xs else (0.0, 1.0)
        return {"tickets": len(xs), "false_tickets": wrong, "upper_95": round(hi, 3)}

    return {
        "policy": "auto-issue a ticket only if it is ROBUST (no change in the menu overturns it); hold every other ticket "
                  "for a human reviewer, with the smallest change that overturns it",
        "all_tickets": rate(tickets), "auto_issued": rate(robust),
        "held_for_review": {"tickets": len(held), "false_tickets": sum(r["correct"] == "wrong" for r in held),
                            "by_status": {s: sum(r["status"] == s for r in held)
                                          for s in sorted({r["status"] for r in held})}},
        "labels_needed_error_free": {"2%": labels_needed(0.02), "5%": labels_needed(0.05)},
    }


# The choices a sentence or statute leaves open. A person can sign a value for each (a contract parameter); measurement
# changes (line position, measured point, frame rate) are evidence quality and cannot be signed away.
APPROVABLE = {"min_ms": "how long counts as waiting", "stillness": "how slow counts as standing still",
              "stillness_meaning": "whether the wait must be standing still", "reading": "which reading of the sentence"}


def _families(r: dict) -> set[str]:
    return {f.split(":")[0] for f in r.get("flipping", [])}


def gate(rows: list[dict], approved: set[str]) -> dict:
    """Approval gate. While any ticket turns on an open choice nobody approved, the rule is WITHHELD: it issues nothing.
    Once those choices are signed, a change to a signed value is a change of contract, not an objection; a ticket is
    auto-issued if nothing else overturns it, and held for a human if a measurement change still does."""
    tickets = [r for r in rows if r.get("verdict") == "VIOLATION" and r.get("status")]
    open_ = {f for r in tickets for f in _families(r) if f in APPROVABLE} - approved
    missing = [{"family": f, "label": APPROVABLE[f], "tickets": sum(f in _families(r) for r in tickets)}
               for f in sorted(open_)]
    auto = [r for r in tickets if not (_families(r) - approved)] if not open_ else []
    held = [r for r in tickets if r not in auto] if not open_ else []
    wrong = lambda xs: sum(r["correct"] == "wrong" for r in xs)  # noqa: E731
    return {"approved": sorted(approved), "decision": "WITHHELD" if open_ else "DEPLOYABLE",
            "reason": ("Rule withheld: " + "; ".join(f"{m['label']} has no approved value ({m['tickets']} tickets "
                                                     "depend on it)" for m in missing)) if open_ else
                      "Every open choice the tickets depend on has an approved value.",
            "missing": missing, "tickets": len(tickets),
            "auto_issued": {"tickets": len(auto), "false_tickets": wrong(auto)},
            "held_for_review": {"tickets": len(held), "false_tickets": wrong(held),
                                "because": sorted({f for r in held for f in _families(r) - approved})}}


def gates(rows: list[dict]) -> dict[str, dict]:
    """The gate for every set of approvals over the choices these tickets depend on, keyed by the sorted names
    joined with ','; '' is nothing approved."""
    fams = sorted({f for r in rows for f in _families(r) if f in APPROVABLE})
    out = {}
    for m in range(1 << len(fams)):
        sel = {f for i, f in enumerate(fams) if m >> i & 1}
        out[",".join(sorted(sel))] = gate(rows, sel)
    return out


def apply_audit(rows: list[dict], audit: dict) -> list[dict]:
    """Rows with the corrections of a label audit applied (pre-registered rows are not modified; see label_audit.json)."""
    fix = {(c["set"], audit["clip"], c["object_id"]): c["audited_label"].split()[0] for c in audit["corrections"]}
    out = []
    for r in rows:
        lab = fix.get((r.get("set"), r.get("clip"), r.get("object_id")))
        if lab is None or r.get("verdict") in (None, "UNKNOWN"):
            out.append(r)
        else:
            out.append(r | {"intended": lab, "correct": "right" if r["verdict"] == lab else "wrong", "audited": True})
    return out
