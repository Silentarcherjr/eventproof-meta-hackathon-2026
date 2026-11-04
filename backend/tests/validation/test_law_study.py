"""Statute study: the committed report recomputes from the cached compiles (0 API calls)."""

from __future__ import annotations

import json

from eventproof.validation import law_study


def test_report_recomputes_from_cache():
    rep = json.loads((law_study.LAW / "report.json").read_text())
    res = law_study.study(0)
    assert law_study.summary(res["rows"]) == rep["summary"] and res["live_calls"] == 0
    spark = [s for s in rep["summary"] if s["model"] == "muse-spark-1.3"]
    assert [(s["right"], s["cars"], s["hang_on_unwritten_number"]) for s in spark] == [(25, 30, 14), (25, 30, 14)]


def test_statutes_contain_no_number():
    assert not any(ch.isdigit() for st in law_study.statutes() for ch in st["text"])
