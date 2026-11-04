"""Repeated statute compiles on the INTERACTION approaches (pre-registered in
`benchmark/interaction/REPEATS_PREREGISTRATION.md`): Spark and Wonder x 10 per statute, each a fresh call, each rule
judged with its own compiled values on the same 1,268 approaches. Measures stability of the silent choices.

    uv run python -m eventproof.validation.interaction_repeats compile --env-file .env --max-live 160
    uv run python -m eventproof.validation.interaction_repeats report
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import statistics
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from eventproof.engine.evaluator import evaluate
from eventproof.schemas.rules import Dwell, VisualRule, iter_events
from eventproof.validation.interaction import (
    BENCH,
    FRAME_M,
    ROOT,
    bind_rule,
    compilation_layout,
    count_codes,
    load_data,
    sha,
    to_trackset,
    write_json,
)

OUT = BENCH / 'repeats'
MODELS = ('muse-spark-1.3', 'muse-wonder-1.0')
STATUTES = ('ca-veh-22450a', 'md-tr-21-707a')
RUNS = 10
CALLS_PER_RUN = 4
TRANSPORT_RETRIES = 2
CODE = {'VIOLATION': 'V', 'PASS': 'P', 'UNKNOWN': 'U'}


def plan() -> list[tuple[str, str, int]]:
    return [(m, s, i) for s in STATUTES for m in MODELS for i in range(RUNS)]


def run_id(model: str, statute: str, i: int) -> str:
    return f'{statute}__{model}__{i:02d}'


def compile_one(settings, statute: dict, model: str, i: int, max_calls: int) -> dict:
    from eventproof.meta.client import LiveBudget
    from eventproof.meta.muse_rules import MuseRuleCompiler, RuleCompileError, UnsupportedRule

    rid = run_id(model, statute['id'], i)
    budget = LiveBudget(rid, max_calls)
    comp = MuseRuleCompiler(dataclasses.replace(settings, muse_model=model), cache_dir=OUT / 'cache' / rid,
                            law=True, anchor_field=True, budget=budget, max_attempts=2)
    rec = {'run': rid, 'model': model, 'statute': statute['id'], 'index': i, 'transport_errors': []}
    for _ in range(TRANSPORT_RETRIES + 1):
        try:
            res = comp.compile(statute['text'], compilation_layout())
        except UnsupportedRule as e:
            rec |= {'status': 'refused', 'error': str(e)}
        except RuleCompileError as e:
            rec |= {'status': 'invalid', 'error': str(e)}
        except Exception as e:  # noqa: BLE001 - transport errors are retried, then reported
            if type(e).__name__ == 'LiveCallLimit':
                rec |= {'status': 'call_cap', 'error': str(e)}
            else:
                rec['transport_errors'].append(f'{type(e).__name__}: {e}'[:300])
                continue
        else:
            rec |= {'status': 'ok', 'rule': json.loads(res.rule.canonical_json()), 'assumptions': res.assumptions,
                    'request_ids': res.request_ids, 'attempts': res.attempts, 'usage': res.usage}
        break
    else:
        rec |= {'status': 'transport_failed'}
    rec['live_calls'] = budget.used
    return rec


def compile_live(env_file: Path | None, max_live: int) -> None:
    from dotenv import load_dotenv

    from eventproof.meta.client import MetaSettings

    if (OUT / 'compiles.json').exists():
        raise FileExistsError('first run is kept')
    if max_live < len(plan()) * CALLS_PER_RUN:
        raise ValueError(f'pre-registered cap is {len(plan()) * CALLS_PER_RUN} calls')
    if env_file:
        load_dotenv(env_file)
    settings = MetaSettings.from_env()
    if not settings.api_key:
        raise RuntimeError('MODEL_API_KEY unavailable; STOP')
    statutes = {s['id']: s for s in json.loads((ROOT / 'benchmark/law/statutes.json').read_text())['statutes']}
    with ThreadPoolExecutor(4) as pool:
        runs = list(pool.map(lambda p: compile_one(settings, statutes[p[1]], p[0], p[2], CALLS_PER_RUN), plan()))
    write_json(OUT / 'compiles.json', {
        'schema': 'eventproof-interaction-repeats-compiles/1',
        'preregistration': 'benchmark/interaction/REPEATS_PREREGISTRATION.md',
        'preregistration_sha256': sha(BENCH / 'REPEATS_PREREGISTRATION.md'),
        'layout': compilation_layout().model_dump(mode='json'),
        'live_calls': sum(r['live_calls'] for r in runs),
        'code_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'runs': runs})
    print(json.dumps({'live_calls': sum(r['live_calls'] for r in runs),
                      'status': [r['status'] for r in runs]}))


def shape(node) -> str:
    """The rule's event structure without values, e.g. IMPLIES(OCCURS(CROSSES),BEFORE(DWELL,CROSSES))."""
    if isinstance(node, list):
        return ','.join(shape(n) for n in node)
    if not isinstance(node, dict):
        return ''
    kids = [shape(v) for k, v in node.items() if k != 'op' and isinstance(v, dict | list)]
    kids = [k for k in kids if k]
    return node.get('op', '') + (f"({','.join(kids)})" if kids else '')


def judge(rule: VisualRule, data: dict) -> str:
    aa = {a['id']: a for a in data['approaches']}
    out = []
    for v in data['vehicles']:
        a = aa[v['approach_id']]
        out.append(CODE[evaluate(bind_rule(rule, a), to_trackset(v, a, rule.entity.concept)).objects[0].verdict])
    return ''.join(out)


def describe(rule: VisualRule) -> dict:
    dwells = [e for e in iter_events(rule.check) if isinstance(e, Dwell)]
    return {'shape': shape(json.loads(rule.canonical_json())['check']), 'anchor': rule.params.anchor,
            'dwell': [{'min_s': d.min_ms / 1000, 'max_speed_frame_widths_s': d.max_speed,
                       'max_speed_mps': None if d.max_speed is None else round(d.max_speed * FRAME_M, 6)}
                      for d in dwells]}


def summary(rows: list[dict], n: int) -> dict:
    ok = [r for r in rows if r['status'] == 'ok']
    t = [r['tickets'] for r in ok]
    status = {}
    for r in rows:
        status[r['status']] = status.get(r['status'], 0) + 1
    return {'runs': len(rows), 'status': status,
            'tickets_min': min(t, default=None), 'tickets_median': statistics.median(t) if t else None,
            'tickets_max': max(t, default=None),
            'share_min': min(t) / n if t else None, 'share_max': max(t) / n if t else None,
            'distinct_verdict_strings': len({r['verdicts'] for r in ok}),
            'distinct_values': sorted({json.dumps(r['dwell'], sort_keys=True) for r in ok}),
            'distinct_shapes': sorted({r['shape'] for r in ok}), 'anchors': sorted({r['anchor'] for r in ok})}


def recompute(compiles: dict, data: dict) -> dict:
    n = len(data['vehicles'])
    rows = []
    for r in compiles['runs']:
        row = {k: r[k] for k in ('run', 'model', 'statute', 'index', 'status')}
        if r['status'] == 'ok':
            rule = VisualRule.model_validate(r['rule'])
            codes = judge(rule, data)
            row |= describe(rule) | count_codes(codes) | {'has_dwell': any(isinstance(e, Dwell)
                                                                           for e in iter_events(rule.check)),
                                                           'verdicts': codes}
        rows.append(row)
    ok = [r for r in rows if r['status'] == 'ok']
    changed = sum(len({r['verdicts'][i] for r in ok}) > 1 for i in range(n)) if ok else 0
    first = json.loads((BENCH / 'compile.json').read_text())
    groups = {f'{s}__{m}': summary([r for r in rows if r['statute'] == s and r['model'] == m], n)
              for s in STATUTES for m in MODELS}
    return {'schema': 'eventproof-interaction-repeats/1',
            'preregistration': 'benchmark/interaction/REPEATS_PREREGISTRATION.md',
            'approaches': n, 'live_calls': compiles['live_calls'],
            'main_study_compile': describe(VisualRule.model_validate(first['rule'])),
            'overall': summary(rows, n) | {'approaches_changing_across_rules': changed},
            'groups': groups, 'runs': rows}


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('compile')
    c.add_argument('--env-file', type=Path)
    c.add_argument('--max-live', type=int, required=True)
    sub.add_parser('report')
    a = ap.parse_args()
    if a.cmd == 'compile':
        compile_live(a.env_file, a.max_live)
    else:
        rep = recompute(json.loads((OUT / 'compiles.json').read_text()), load_data())
        write_json(OUT / 'report.json', rep)
        print(json.dumps({k: rep[k] for k in ('live_calls', 'overall', 'groups')}, indent=1)[:6000])


if __name__ == '__main__':
    main()
