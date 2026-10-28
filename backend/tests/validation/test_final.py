from __future__ import annotations

import pytest

from eventproof.challenge.families import FAMILIES
from eventproof.challenge.holdout import HOLDOUT_SEEDS
from eventproof.challenge.runner import DEV_SEEDS
from eventproof.validation.final import (
    DEFAULT_PATH,
    FINAL_SEEDS,
    SHIFT_FAMILIES,
    FinalDrift,
    FinalManifest,
    _cases_hash,
    build_manifest,
    load_frozen,
)
from tests.repair.test_repair import _eventproof_imports


def test_final_seeds_and_families_are_new():
    assert not set(FINAL_SEEDS) & (set(DEV_SEEDS) | set(HOLDOUT_SEEDS) | set(range(100)) | set(range(10_000, 10_040)))
    assert not set(SHIFT_FAMILIES) & set(FAMILIES)


def test_committed_manifest_matches_generators():
    m, cases = load_frozen()
    assert m == build_manifest(), "generators drifted: final_v1 would no longer be the same test set"
    assert len(cases) == 320 and {c.split for c, _ in cases} == {"in_distribution", "shift"}


def test_tampered_manifest_is_refused(tmp_path):
    m = FinalManifest.model_validate_json(DEFAULT_PATH.read_text())
    bad = m.model_copy(update={"cases": [m.cases[0].model_copy(update={"scene_sha256": "0" * 64})] + m.cases[1:]})
    p = tmp_path / "f.json"
    p.write_text(bad.model_copy(update={"cases_sha256": _cases_hash(bad.cases)}).model_dump_json())
    with pytest.raises(FinalDrift):
        load_frozen(p)


@pytest.mark.parametrize("module", ["eventproof.repair.grader", "eventproof.repair.proposer", "eventproof.repair.loop",
                                    "eventproof.meta.muse_repair", "eventproof.studio", "eventproof.api.main"])
def test_selection_code_cannot_reach_the_final_set(module):
    assert not any(m.startswith("eventproof.validation") for m in _eventproof_imports(module))


def test_stats_helpers():
    from eventproof.validation.evaluate import sign_test, wilson

    lo, hi = wilson(166, 200)
    assert 0.77 < lo < 0.83 < hi < 0.88
    assert wilson(0, 0) == (0.0, 1.0)
    assert sign_test(0, 0) == 1.0 and sign_test(10, 0) == round(2 / 1024, 6) and sign_test(3, 3) == 1.0


def test_evaluator_on_a_mini_manifest_of_dev_scenes(tmp_path):
    """Exercise the evaluator end to end without touching final_v1: a manifest of DEV seeds."""
    from eventproof.validation import evaluate as ev
    from eventproof.validation.final import FinalCase, generator

    cases = [FinalCase(split=sp, family=f, seed=s, scene_sha256=generator(sp, f)(s).scene_hash())
             for sp, f in (("in_distribution", "drive_through"), ("shift", "stop_and_go")) for s in range(3)]
    splits = {"in_distribution": ["drive_through"], "shift": ["stop_and_go"]}
    m = FinalManifest(name="mini", seed_range=(0, 2), splits=splits,
                      cases=cases, cases_sha256=_cases_hash(cases))
    p = tmp_path / "mini.json"
    p.write_text(m.model_dump_json())
    rep = ev.evaluate(p)
    assert set(rep["inputs"]) == {s[0] for s in ev.SOURCES}
    n_props = sum(i["proposals"] for i in rep["inputs"].values())
    assert len(rep["patches"]) == n_props and n_props >= 10
    for r in rep["patches"]:
        for sp, s in r["splits"].items():
            base = rep["baselines"][r["source"]][sp]["correct"]
            assert s["correct"] - base == r["fixed"][sp] - r["regressed"][sp]
            assert s["n"] == 3
