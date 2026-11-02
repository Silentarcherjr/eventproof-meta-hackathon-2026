import json

from eventproof.validation.evaluate import ROOT
from eventproof.validation.real_pooled import pooled


def test_pooled_real_traffic_numbers_recompute_from_committed_files(monkeypatch):
    from eventproof.meta import muse_rules

    monkeypatch.setattr(muse_rules, "get_client", lambda s: (_ for _ in ()).throw(AssertionError("no API calls")))
    committed = json.loads((ROOT / "benchmark" / "real" / "POOLED.json").read_text())
    assert json.loads(json.dumps(pooled())) == committed
    r = committed["readings"]
    assert committed["labelled_cars"] == 24
    assert r["muse_spark_rule"]["objects_right"] == 22 and r["muse_spark_rule_plus_synthetic_repair"]["objects_right"] == 13


def test_pooled_v2_with_the_added_window_recomputes():
    from eventproof.validation.real_pooled import SETS_V2

    committed = json.loads((ROOT / "benchmark" / "real" / "POOLED_v2.json").read_text())
    assert json.loads(json.dumps(pooled(SETS_V2))) == committed
    assert committed["labelled_cars"] == 30
