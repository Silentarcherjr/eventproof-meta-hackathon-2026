from __future__ import annotations

import json

import pytest

from eventproof.validation import field_repair as fr


def test_patch_is_bounded_and_dev_brief_has_no_holdout():
    p = fr.patch_of({"min_ms": 50, "max_speed": 9})
    assert p.ops[0].value == 100.0 and p.ops[1].max_speed == 0.5
    brief = fr.dev_brief(fr.clips(fr.DEV))
    assert "novisad" in brief and "wroclaw" not in brief.lower()


def test_committed_report_recomputes_from_cached_muse_answers(monkeypatch):
    path = fr.OUT_DIR / "report.json"
    if not path.exists():
        pytest.skip("report not produced yet")
    monkeypatch.setattr(fr, "get_client", lambda s: pytest.fail("no API calls"))
    committed = json.loads(path.read_text())
    rep = fr.run(0)
    for k in ("code_commit", "live_calls_this_run"):
        committed.pop(k, None)
        rep.pop(k, None)
    for t in rep["muse"]["trace"] + committed["muse"]["trace"]:
        t.pop("cached")
    assert json.loads(json.dumps(rep)) == committed
