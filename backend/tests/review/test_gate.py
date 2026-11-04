"""Approval gate: a rule issues nothing while a ticket turns on an open choice nobody approved."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from eventproof.api.main import app
from eventproof.review.triage import apply_audit, gate, gates

BENCH = Path(__file__).resolve().parents[3] / "benchmark"


def _t(status, flipping, correct="right"):
    return {"verdict": "VIOLATION", "status": status, "flipping": flipping, "correct": correct}


def test_withheld_until_every_open_choice_is_approved():
    rows = [_t("ROBUST", []), _t("DEPENDS_ON_THRESHOLD", ["stillness:2.0"]),
            _t("FRAGILE", ["anchor:center", "stillness:0.5"]), {"verdict": "PASS", "status": "ROBUST"}]
    g = gate(rows, set())
    assert g["decision"] == "WITHHELD" and g["auto_issued"]["tickets"] == 0
    assert [m["family"] for m in g["missing"]] == ["scope", "stillness"] and g["missing"][1]["tickets"] == 2
    assert gate(rows, {"stillness"})["decision"] == "WITHHELD"  # nobody said where the rule may run
    g = gate(rows, {"scope", "stillness"})
    assert g["decision"] == "DEPLOYABLE"
    assert g["auto_issued"]["tickets"] == 2 and g["held_for_review"] == {"tickets": 1, "false_tickets": 0,
                                                                         "because": ["anchor"]}


def test_measurement_cannot_be_approved():
    assert set(gates([_t("FRAGILE", ["anchor:center", "line_shift:0.01"])])) == {"", "scope"}


def test_real_tickets():
    rep = json.loads((BENCH / "tickets" / "report.json").read_text())
    rows = apply_audit(rep["rows"], json.loads((BENCH / "real" / "santos" / "label_audit.json").read_text()))
    g = gates(rows)
    assert g[""]["decision"] == "WITHHELD" and g["stillness,stillness_meaning"]["decision"] == "WITHHELD"
    both = g["scope,stillness,stillness_meaning"]
    assert both["decision"] == "DEPLOYABLE"
    assert (both["auto_issued"], both["held_for_review"]["tickets"]) == ({"tickets": 17, "false_tickets": 0}, 3)


def test_court_endpoint_carries_gates():
    body = TestClient(app).get("/tickets/court").json()
    assert body["gates"][""]["decision"] == "WITHHELD" and "stillness" in body["approvable"]
