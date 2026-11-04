"""Preregistered stop-law sensitivity on measured INTERACTION trajectories; never video/SAM.

Stages: maps/derive (raw directory) -> compile (explicit live allowance) -> report.
Reproduction from derived.json.gz and compile.json requires no raw data or API.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

from eventproof.engine.evaluator import build_tracks, evaluate, zone_steps
from eventproof.engine.geometry import point_in_polygon, segments_intersect
from eventproof.meta.muse_rules import Layout, LayoutLine, LayoutZone
from eventproof.review.robustness import _map_events
from eventproof.schemas.rules import Dwell, Line, VisualRule, Zone, iter_events
from eventproof.schemas.tracks import Box, TrackFrame, TrackSet, VideoInfo

ROOT = Path(__file__).resolve().parents[3]
BENCH = ROOT / 'benchmark' / 'interaction'
LOCATIONS = tuple('DR_USA_Intersection_' + s for s in ('EP0', 'EP1', 'GL', 'MA'))
FRAME_M = 100.0
PIXELS = 10000
SOURCE = 'dataset trajectory (INTERACTION, drone)'
TIMES_S = [i / 4 for i in range(13)]
SPEEDS_MPS = [0.05, 0.10, 0.20, 0.30, 0.50, 0.75, 1., 1.25, 1.50, 1.75, 2., None]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def tags(element) -> dict:
    return {t.get('k'): t.get('v') for t in element.findall('tag')}


def members(element, role: str, kind: str | None = None) -> list[str]:
    return [m.get('ref') for m in element.findall('member')
            if m.get('role') == role and (kind is None or m.get('type') == kind)]


def local(point, approach) -> tuple[float, float]:
    dx, dy = point[0] - approach['origin'][0], point[1] - approach['origin'][1]
    return (dx * approach['ex'][0] + dy * approach['ex'][1],
            dx * approach['ey'][0] + dy * approach['ey'][1])


def normalized(point) -> tuple[float, float]:
    return 0.5 + point[0] / FRAME_M, 0.6 + point[1] / FRAME_M


def clip_y(poly: list, lower: float, upper: float) -> list:
    """Sutherland-Hodgman against two horizontal half planes, in metric units."""
    for edge, sign in [(lower, 1), (upper, -1)]:
        out = []
        for a, b in zip(poly, poly[1:] + poly[:1], strict=True):
            ia, ib = sign * (a[1] - edge) >= 0, sign * (b[1] - edge) >= 0
            if ia:
                out.append(a)
            if ia != ib:
                t = (edge - a[1]) / (b[1] - a[1])
                out.append((a[0] + t * (b[0] - a[0]), edge))
        poly = out
    # remove repeated vertices without changing the polygon
    return [p for i, p in enumerate(poly) if math.dist(p, poly[i - 1]) > 1e-9]


def select_maps(raw: Path) -> dict:
    approaches, excluded, inputs = [], [], []
    for location in LOCATIONS:
        osm, xy = (raw / 'maps' / (location + suffix) for suffix in ('.osm', '.osm_xy'))
        root = ET.parse(osm).getroot()
        metric = ET.parse(xy).getroot()
        nodes = {n.get('id'): (float(n.get('x')), float(n.get('y'))) for n in metric.findall('node')}
        ways = {w.get('id'): w for w in root.findall('way')}
        relations = {r.get('id'): r for r in root.findall('relation')}
        coords = {key: [nodes[n.get('ref')] for n in way.findall('nd')] for key, way in ways.items()}
        inputs.extend({'path': 'maps/' + p.name, 'sha256': sha(p)} for p in (osm, xy))
        selected = {}
        for rid, reg in relations.items():
            rt = tags(reg)
            if rt.get('type') != 'regulatory_element' or rt.get('subtype') == 'speed_limit':
                continue
            signs = sorted(s for s in members(reg, 'refers', 'way')
                           if tags(ways[s]).get('subtype') == 'usR1-1')
            refs = sorted(set(members(reg, 'ref_line', 'way')))
            accept = rt.get('subtype') == 'all_way_stop' or (rt.get('subtype') == 'right_of_way' and signs)
            if not accept or not refs:
                excluded.append({'location': location, 'regulatory_id': rid, 'tags': rt,
                                 'reason': 'not explicit STOP or missing ref_line'})
                continue
            for lid in members(reg, 'yield', 'relation'):
                lanelet = relations[lid]
                left, right = (coords[members(lanelet, role, 'way')[0]] for role in ('left', 'right'))
                # OSM ways are not necessarily stored in the direction of travel.
                if math.dist(left[0], right[-1]) < math.dist(left[0], right[0]):
                    right = list(reversed(right))
                endpoints = [tuple((a + b) / 2 for a, b in zip(left[i], right[i], strict=True)) for i in (0, -1)]
                distance, line_id, near = min((min(math.dist(ep, p) for p in coords[ref]), ref, j)
                                            for ref in refs for j, ep in enumerate(endpoints))
                line = coords[line_id]
                p, q = line[0], line[-1]
                length = math.dist(p, q)
                ex = ((q[0] - p[0]) / length, (q[1] - p[1]) / length)
                ey = (-ex[1], ex[0])
                origin = tuple((a + b) / 2 for a, b in zip(p, q, strict=True))
                far = endpoints[1 - near]
                if sum((origin[k] - far[k]) * ey[k] for k in (0, 1)) < 0:
                    ey = tuple(-x for x in ey)
                a = {'id': f'{location}:{line_id}:{lid}', 'location': location, 'line_id': line_id,
                     'lanelet_id': lid, 'regulatory_ids': [rid], 'stop_sign_ids': signs,
                     'regulatory_subtype': rt['subtype'], 'endpoint_distance_m': distance,
                     'origin': origin, 'ex': ex, 'ey': ey, 'line_world': line,
                     'lanelet_world': left + list(reversed(right)),
                     'reason': 'all_way_stop yield' if rt['subtype'] == 'all_way_stop' else 'yield with explicit usR1-1'}
                a['lane_polygon_m'] = [local(p, a) for p in a['lanelet_world']]
                a['zone_m'] = clip_y(a['lane_polygon_m'], -10, 0)
                a['line_m'] = [local(p, a) for p in (line[0], line[-1])]
                if not 3 <= len(a['zone_m']) <= 32:
                    raise ValueError(f'unsupported zone geometry: {a["id"]}')
                # orient line left-to-right in local x, for known inbound +y
                a['line_m'].sort()
                key = (line_id, lid)
                if key in selected:
                    selected[key]['regulatory_ids'].append(rid)
                else:
                    selected[key] = a
        approaches.extend(selected[key] for key in sorted(selected))
    return {'schema': 'eventproof-interaction-maps/1', 'approaches': approaches,
            'excluded_regulations': excluded, 'inputs': inputs}


def in_lane(point, poly, tolerance=0.25) -> bool:
    if point_in_polygon(point, poly):
        return True
    for a, b in zip(poly, poly[1:] + poly[:1], strict=True):
        vx, vy = b[0] - a[0], b[1] - a[1]
        denom = vx * vx + vy * vy
        t = max(0., min(1., ((point[0] - a[0]) * vx + (point[1] - a[1]) * vy) / denom)) if denom else 0.
        if math.dist(point, (a[0] + t * vx, a[1] + t * vy)) <= tolerance:
            return True
    return False


def approach_segment(rows: list[dict], a: dict) -> tuple[dict | None, str]:
    """Select purely by spatial completeness; never look at speed, dwell or verdict."""
    if any(r['agent_type'] != 'car' for r in rows):
        return None, 'not_car'
    fields = ('timestamp_ms', 'x', 'y', 'psi_rad', 'length', 'width')
    try:
        values = [[float(r[k]) for k in fields] for r in rows]
    except (ValueError, KeyError):
        return None, 'invalid_numeric'
    if any(not all(math.isfinite(v) for v in vs) or vs[4] <= 0 or vs[5] <= 0 for vs in values):
        return None, 'invalid_numeric'
    pts = [local((vs[1], vs[2]), a) for vs in values]
    line = a['line_m']
    crossings = [i for i in range(1, len(pts)) if pts[i - 1][1] < 0 <= pts[i][1]
                 and segments_intersect(pts[i - 1], pts[i], line[0], line[1])]
    if not crossings:
        return None, 'no_inbound_crossing'
    crossing = crossings[0]
    before = [i for i in range(crossing) if pts[i][1] <= -10 and line[0][0] <= pts[i][0] <= line[1][0]
              and point_in_polygon(pts[i], a['lane_polygon_m'])]
    if not before:
        return None, 'incomplete_10m_approach'
    start = before[0]
    # Only enforce lane occupancy on the final 10 metres, as preregistered.
    if any(not in_lane(p, a['lane_polygon_m']) for p in pts[start:crossing] if -10 <= p[1] <= 0):
        return None, 'left_approach_lanelet'
    end = min(len(rows), crossing + 11)
    for i in range(start + 1, end):
        if values[i][0] - values[i - 1][0] != 100 or int(rows[i]['frame_id']) - int(rows[i - 1]['frame_id']) != 1:
            return None, 'noncontiguous_samples'
    samples = [[vs[0] - values[start][0], *p, vs[3], vs[4], vs[5]]
               for vs, p in zip(values[start:end], pts[start:end], strict=True)]
    return {'samples': samples, 'crossing_sample': crossing - start,
            'source_start_frame': int(rows[start]['frame_id']), 'source_start_timestamp_ms': values[start][0]}, 'included'


def derive(raw: Path, out: Path) -> None:
    if out.exists():
        raise FileExistsError('first derived data is kept')
    maps = select_maps(raw)
    write_json(BENCH / 'maps.json', maps)
    candidates, inputs, counts = [], [], Counter()
    for location in LOCATIONS:
        aa = [a for a in maps['approaches'] if a['location'] == location]
        for path in sorted((raw / 'recorded_trackfiles' / location).glob('vehicle_tracks_*.csv')):
            inputs.append({'path': f'recorded_trackfiles/{location}/{path.name}', 'sha256': sha(path)})
            tracks = defaultdict(list)
            with path.open() as f:
                for row in csv.DictReader(f):
                    tracks[row['track_id']].append(row)
            for tid in sorted(tracks, key=int):
                rows = tracks[tid]
                counts[location + ':input_tracks'] += 1
                per_line = {}
                for a in aa:
                    segment, reason = approach_segment(rows, a)
                    counts[location + ':' + reason] += 1
                    if segment is not None:
                        per_line.setdefault(a['line_id'], (a, segment))
                for a, segment in per_line.values():
                    candidates.append({'id': f'{location}/{path.stem}/{tid}/{a["line_id"]}', 'location': location,
                                       'recording': path.name, 'track_id': int(tid), 'approach_id': a['id'], **segment})
    data = {'schema': 'eventproof-interaction-derived/1', 'source': SOURCE, 'sample_columns':
            ['relative_timestamp_ms', 'local_x_m', 'local_y_m', 'world_yaw_rad', 'length_m', 'width_m'],
            'approaches': maps['approaches'], 'vehicles': candidates}
    with out.open('wb') as f:
        with gzip.GzipFile(filename='', mode='wb', fileobj=f, mtime=0) as z:
            z.write(json.dumps(data, separators=(',', ':'), allow_nan=False).encode())
    write_json(BENCH / 'population.json', {'schema': 'eventproof-interaction-population/1',
               'archive_sha256': sha(raw / 'INTERACTION-Dataset-DR-v1_1.rar'),
               'derived_sha256': sha(out), 'counts_track_lanelet_candidates': dict(sorted(counts.items())),
               'inputs': inputs, 'included_approaches': len(candidates),
               'unique_recording_tracks': len({(v['location'], v['recording'], v['track_id']) for v in candidates})})
    print(json.dumps({'included_approaches': len(candidates), 'derived_bytes': out.stat().st_size}))


def compilation_layout() -> Layout:
    return Layout(zones=[LayoutZone(zone=Zone(id='stop_zone', polygon=[(.45, .5), (.55, .5), (.55, .6), (.45, .6)]),
                                    description='Approach lane waiting zone: last 10 metres before marked STOP limit line. '
                                    'Top-down metric square, 100 metres wide/high. Zone drawn 10 m wide for compilation; '
                                    'actual mapped approach-lane polygon is bound for evaluation. '
                                    '+y is inbound/downstream.')],
                  lines=[LayoutLine(line=Line(id='stop_line', a=(.45, .6), b=(.55, .6)),
                                    description='Marked STOP limit line across inbound approach, left to right; '
                                    'vehicles approach from y<0.6 and cross towards y>0.6. Frame width = 100 metres. '
                                    'Boxes represent vehicles viewed from above; their centre is metric position, '
                                    'bottom_center is downstream AABB edge, not wheels.')])


def compile_live(env_file: Path | None, max_live: int) -> None:
    from dotenv import load_dotenv

    from eventproof.meta.client import LiveBudget, MetaSettings
    from eventproof.meta.muse_rules import MuseRuleCompiler

    if not 1 <= max_live <= 2:
        raise ValueError('explicit live allowance must be 1 or 2')
    if (BENCH / 'compile.json').exists():
        raise FileExistsError('first compilation is kept')
    if env_file:
        load_dotenv(env_file)
    settings = MetaSettings.from_env()
    if not settings.api_key:
        raise RuntimeError('MODEL_API_KEY unavailable; STOP, no substitute rule')
    statutes = json.loads((ROOT / 'benchmark/law/statutes.json').read_text())['statutes']
    statute = next(s for s in statutes if s['id'] == 'ca-veh-22450a')
    budget = LiveBudget('interaction Muse Spark', max_live)
    compiler = MuseRuleCompiler(settings, cache_dir=BENCH / 'cache', law=True, anchor_field=True,
                                budget=budget, max_attempts=2)
    if settings.muse_model != 'muse-spark-1.3':
        raise ValueError('expected muse-spark-1.3')
    result = compiler.compile(statute['text'], compilation_layout())
    if not any(isinstance(e, Dwell) for e in iter_events(result.rule.check)):
        raise RuntimeError('no DWELL in actual compiled rule; preregistered study cannot proceed')
    write_json(BENCH / 'compile.json', {'schema': 'eventproof-interaction-compile/1', 'statute': statute,
               'layout': compilation_layout().model_dump(mode='json'), 'live_calls': budget.used,
               'preregistration_sha256': sha(BENCH / 'PREREGISTRATION.md'),
               'code_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
               **result.model_dump(mode='json')})
    print(json.dumps({'live_calls': budget.used, 'request_ids': result.request_ids,
                      'dwell': [e.model_dump() for e in iter_events(result.rule.check) if isinstance(e, Dwell)]}))


def load_data(path: Path = BENCH / 'derived.json.gz') -> dict:
    with gzip.open(path, 'rt') as f:
        return json.load(f)


def to_trackset(vehicle: dict, a: dict, concept: str) -> TrackSet:
    frames = []
    for i, (ts, x, y, yaw, length, width) in enumerate(vehicle['samples']):
        # Resolve world heading into local orthonormal basis; preserve all four corners.
        ux, uy = math.cos(yaw), math.sin(yaw)
        heading = (ux * a['ex'][0] + uy * a['ex'][1], ux * a['ey'][0] + uy * a['ey'][1])
        lateral = (-uy * a['ex'][0] + ux * a['ex'][1], -uy * a['ey'][0] + ux * a['ey'][1])
        hx = abs(heading[0]) * length / 2 + abs(lateral[0]) * width / 2
        hy = abs(heading[1]) * length / 2 + abs(lateral[1]) * width / 2
        p, q = normalized((x - hx, y - hy)), normalized((x + hx, y + hy))
        frames.append(TrackFrame(frame_index=i, timestamp_ms=ts, object_id=vehicle['track_id'], label=concept,
                                  box=Box(x1=p[0] * PIXELS, y1=p[1] * PIXELS, x2=q[0] * PIXELS, y2=q[1] * PIXELS)))
    return TrackSet(video=VideoInfo(width=PIXELS, height=PIXELS, fps=10, frame_count=len(frames)), frames=frames,
                    source=SOURCE, source_ref=vehicle['id'])


def bind_rule(rule: VisualRule, a: dict) -> VisualRule:
    payload = rule.model_dump(mode='json')
    payload['zones'] = [{'id': z.id, 'polygon': [normalized(p) for p in a['zone_m']]} for z in rule.zones]
    payload['lines'] = [{'id': line.id, 'a': normalized(a['line_m'][0]), 'b': normalized(a['line_m'][1])}
                        for line in rule.lines]
    return VisualRule.model_validate(payload)


def grid_rule(rule: VisualRule, seconds: float, mps: float | None) -> VisualRule:
    result = _map_events(rule, lambda e: e | {'min_ms': max(1., seconds * 1000),
                                             'max_speed': None if mps is None else mps / FRAME_M}
                         if e.get('op') == 'DWELL' else None)
    if result is None:
        raise ValueError('no dwell to vary')
    return result


def count_codes(codes: str) -> dict:
    n = len(codes)
    return {'approaches': n, 'tickets': codes.count('V'), 'pass': codes.count('P'), 'unknown': codes.count('U'),
            'ticket_share': codes.count('V') / n if n else None}


def recompute(data: dict, compiled: dict) -> dict:
    rule = VisualRule.model_validate(compiled['rule'])
    dwell = next(e for e in iter_events(rule.check) if isinstance(e, Dwell))
    aa = {a['id']: a for a in data['approaches']}
    settings = [(t, s) for t in TIMES_S for s in SPEEDS_MPS]
    codes = [[] for _ in settings]
    original, boundaries = [], []
    code = {'VIOLATION': 'V', 'PASS': 'P', 'UNKNOWN': 'U'}
    for v in data['vehicles']:
        a = aa[v['approach_id']]
        bound = bind_rule(rule, a)
        ts = to_trackset(v, a, rule.entity.concept)
        original.append(code[evaluate(bound, ts).objects[0].verdict])
        for i, (seconds, mps) in enumerate(settings):
            variant = grid_rule(bound, seconds, mps)
            codes[i].append(code[evaluate(variant, ts).objects[0].verdict])
        track = build_tracks(bound, ts)[0]
        maxima = []
        for mps in SPEEDS_MPS:
            ev = dwell.model_copy(update={'max_speed': None if mps is None else mps / FRAME_M})
            maxima.append(round(max((st.counted_ms for st in zone_steps(ev, track, bound)), default=0.) / 1000, 6))
        boundaries.append(maxima)
    verdicts = [''.join(c) for c in codes]
    original = ''.join(original)
    def group(indices):
        cells = [{**count_codes(''.join(c[i] for i in indices)), 'min_s': t, 'max_speed_mps': s}
                 for (t, s), c in zip(settings, verdicts, strict=True)]
        numeric = [c for c in cells if c['max_speed_mps'] is not None]
        def spread(cc):
            lo, hi = min(c['tickets'] for c in cc), max(c['tickets'] for c in cc)
            n = len(indices)
            return {'min_tickets': lo, 'max_tickets': hi, 'spread_tickets': hi - lo,
                    'min_share': lo / n if n else None, 'max_share': hi / n if n else None,
                    'spread_percentage_points': (hi - lo) * 100 / n if n else None}
        vehicles = [data['vehicles'][i] for i in indices]
        return {'unique_recording_tracks': len({(v['location'], v['recording'], v['track_id']) for v in vehicles}),
                'compiled': count_codes(''.join(original[i] for i in indices)), 'grid_spread': spread(cells),
                'numeric_only_spread': spread(numeric),
                'changed_across_grid': sum(len({c[i] for c in verdicts}) > 1 for i in indices), 'cells': cells}
    indices = list(range(len(data['vehicles'])))
    if not indices:
        raise ValueError('empty eligible population; no sensitivity report')
    return {'schema': 'eventproof-interaction-report/1', 'source': SOURCE,
            'preregistration': 'benchmark/interaction/PREREGISTRATION.md',
            'times_s': TIMES_S, 'speeds_mps': SPEEDS_MPS,
            'compiled_values': {'min_s': dwell.min_ms / 1000, 'max_speed_frame_widths_s': dwell.max_speed,
                                'max_speed_mps': None if dwell.max_speed is None else dwell.max_speed * FRAME_M,
                                'anchor': rule.params.anchor},
            'vehicle_ids': [v['id'] for v in data['vehicles']], 'compiled_verdicts': original,
            'grid_verdicts': verdicts,
            'longest_continuous_dwell_s_by_vehicle_and_speed': boundaries,
            'boundary_note': 'Engine counter, including one 100 ms sample; '
                             'grid verdicts also enforce compiled temporal AST. '
                             'This is not a human stopped/rolled label or a universal physical speed cutoff.',
            'pooled': group(indices),
            'locations': {loc: group([i for i in indices if data['vehicles'][i]['location'] == loc]) for loc in LOCATIONS},
            'approaches': {aid: group([i for i in indices if data['vehicles'][i]['approach_id'] == aid])
                           for aid in aa if any(data['vehicles'][i]['approach_id'] == aid for i in indices)}}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='command', required=True)
    for command in ('maps', 'derive'):
        p = sub.add_parser(command)
        p.add_argument('--raw', type=Path, required=True)
    p = sub.add_parser('compile')
    p.add_argument('--env-file', type=Path)
    p.add_argument('--max-live', type=int, required=True)
    sub.add_parser('report')
    args = ap.parse_args()
    if args.command == 'maps':
        write_json(BENCH / 'maps.json', select_maps(args.raw))
    elif args.command == 'derive':
        derive(args.raw, BENCH / 'derived.json.gz')
    elif args.command == 'compile':
        compile_live(args.env_file, args.max_live)
    else:
        if (BENCH / 'report.json').exists():
            raise FileExistsError('first report is kept')
        compiled = json.loads((BENCH / 'compile.json').read_text())
        report = recompute(load_data(), compiled)
        write_json(BENCH / 'report.json', report)
        print(json.dumps({k: v for k, v in report['pooled'].items() if k != 'cells'}))


if __name__ == '__main__':
    main()
