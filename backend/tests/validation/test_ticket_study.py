"""Ticket study: the committed report recomputes from the robustness engine and the cached defense calls (0 API calls)."""

from __future__ import annotations

import json

from eventproof.validation import ticket_study


def test_report_recomputes_from_cache():
    rep = json.loads((ticket_study.OUT / "report.json").read_text())
    res = ticket_study.study(0)
    assert ticket_study.summary(res["rows"]) == rep["summary"] and res["live_calls"] == 0
    s = rep["summary"]
    assert (s["tickets"], s["robust"], s["defense_found_on_beatable"]) == (20, 24, "8/16")
