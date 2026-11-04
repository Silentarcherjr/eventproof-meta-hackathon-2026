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
