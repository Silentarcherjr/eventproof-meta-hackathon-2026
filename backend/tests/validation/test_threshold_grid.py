"""The unwritten-numbers grid recomputes (no model) and matches the law study at Spark's own values; contract block."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from eventproof.api.main import app
from eventproof.review.triage import contract, labels_needed
from eventproof.validation import threshold_grid
from eventproof.validation.law_study import LAW

GRID = json.loads((LAW / "grid.json").read_text())


def test_grid_recomputes():
    assert threshold_grid.grid() == GRID


def test_spark_cell_matches_the_law_study():
    rep = json.loads((LAW / "report.json").read_text())
    for st in GRID["statutes"]:
        cell = next(c for c in st["cells"] if c["min_s"] == 1.0 and c["speed"] == 0.05)
        s = next(x for x in rep["summary"] if x["statute"] == st["id"] and x["model"] == "muse-spark-1.3")
        assert cell["right"] == s["right"] == 25
    tickets = [c["tickets"] for c in GRID["statutes"][0]["cells"]]
    assert (min(tickets), max(tickets)) == (0, 17)


def test_contract_block():
    rows = json.loads((LAW.parent / "tickets" / "report.json").read_text())["rows"]
    c = contract(rows)
    assert c["all_tickets"] == {"tickets": 20, "false_tickets": 1, "upper_95": 0.236}
    assert c["auto_issued"]["tickets"] == 4 and c["auto_issued"]["false_tickets"] == 0
    assert c["held_for_review"]["false_tickets"] == 1  # the wrongly issued ticket is held, not auto-issued
    assert labels_needed(0.02) == 188 and labels_needed(0.05) == 73


def test_endpoints():
    cl = TestClient(app)
    assert len(cl.get("/law/grid").json()["statutes"]) == 2
    court = cl.get("/tickets/court").json()
    assert len(court["cases"]) == 20 and all(c["events"] for c in court["cases"])
