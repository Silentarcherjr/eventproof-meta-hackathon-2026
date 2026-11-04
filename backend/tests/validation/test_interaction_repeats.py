"""Repeated statute compiles: zero-call recomputation of the committed report, plus the pieces it relies on."""
from __future__ import annotations

import json

from eventproof.schemas.rules import VisualRule
from eventproof.validation.interaction import BENCH, load_data, sha
from eventproof.validation.interaction_repeats import CALLS_PER_RUN, OUT, describe, plan, recompute, run_id, shape


def test_plan_is_the_preregistered_forty_runs():
    runs = plan()
    assert len(runs) == 40 and len({run_id(*r) for r in runs}) == 40
    assert len(runs) * CALLS_PER_RUN == 160


def test_shape_drops_values_keeps_structure():
    node = {'op': 'IMPLIES', 'if': {'op': 'OCCURS', 'event': {'op': 'CROSSES', 'line': 'l'}},
            'then': {'op': 'BEFORE', 'first': {'op': 'DWELL', 'zone': 'z', 'min_ms': 1000}, 'second':
                     {'op': 'CROSSES', 'line': 'l'}}}
    assert shape(node) == 'IMPLIES(OCCURS(CROSSES),BEFORE(DWELL,CROSSES))'


def test_main_compile_replays_its_ten_tickets():
    first = json.loads((BENCH / 'compile.json').read_text())
    fake = {'live_calls': 0, 'runs': [{'run': 'x', 'model': 'muse-spark-1.3', 'statute': 'ca-veh-22450a',
                                       'index': 0, 'status': 'ok', 'rule': first['rule']}]}
    rep = recompute(fake, load_data())
    assert rep['runs'][0]['tickets'] == 10
    assert rep['main_study_compile'] == describe(VisualRule.model_validate(first['rule']))


def test_committed_report_recomputes_zero_calls():
    compiles = json.loads((OUT / 'compiles.json').read_text())
    assert compiles['preregistration_sha256'] == sha(BENCH / 'REPEATS_PREREGISTRATION.md')
    assert len(compiles['runs']) == 40 and compiles['live_calls'] <= 160
    assert recompute(compiles, load_data()) == json.loads((OUT / 'report.json').read_text())
