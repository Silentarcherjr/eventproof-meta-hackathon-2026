from __future__ import annotations

import pytest

from eventproof.challenge.holdout import (
    DEFAULT_PATH,
    DEV_SEEDS,
    HOLDOUT_SEEDS,
    HoldoutDrift,
    HoldoutManifest,
    build_manifest,
    load_frozen,
)


def test_seed_ranges_are_disjoint_from_everything_the_search_sees():
    # the minimizer's --seed auto scans 0-99; the design scan touched 10000-10039
    assert not set(HOLDOUT_SEEDS) & set(range(100))
    assert not set(HOLDOUT_SEEDS) & set(range(10_000, 10_040))
    assert not set(HOLDOUT_SEEDS) & set(DEV_SEEDS)


def test_committed_manifest_matches_generators():
    m, scenes = load_frozen()
    assert m == build_manifest(), "generators drifted: the frozen holdout would no longer be the same test set"
    assert len(scenes) == len(m.cases) == len(m.families) * len(HOLDOUT_SEEDS)
    assert all(s.seed in HOLDOUT_SEEDS for s in scenes)


def test_tampered_manifest_is_refused(tmp_path):
    m = HoldoutManifest.model_validate_json(DEFAULT_PATH.read_text())
    bad = m.model_copy(update={"cases": [m.cases[0].model_copy(update={"scene_sha256": "0" * 64})] + m.cases[1:]})
    p = tmp_path / "h.json"
    p.write_text(bad.model_dump_json())
    with pytest.raises(HoldoutDrift):
        load_frozen(p)
    # recomputing cases_sha256 does not help: scenes are regenerated and compared one by one
    from eventproof.challenge.holdout import _cases_hash

    p.write_text(bad.model_copy(update={"cases_sha256": _cases_hash(bad.cases)}).model_dump_json())
    with pytest.raises(HoldoutDrift):
        load_frozen(p)
