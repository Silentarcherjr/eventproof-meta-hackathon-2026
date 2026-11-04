"""Zero-call reconstruction and independent geometry/selection checks for real derivatives."""
from __future__ import annotations

import json
import math

import pytest

from eventproof.engine.evaluator import _stillness, build_tracks
from eventproof.schemas.rules import VisualRule
from eventproof.validation.interaction import (
    BENCH,
    FRAME_M,
    LOCATIONS,
    SOURCE,
    SPEEDS_MPS,
    TIMES_S,
    approach_segment,
    bind_rule,
    clip_y,
    compilation_layout,
    grid_rule,
    load_data,
    local,
    normalized,
    recompute,
    sha,
    to_trackset,
)


def fixture_approach():
    return {'id': 'test:10:20', 'origin': [0., 0.], 'ex': [1., 0.], 'ey': [0., 1.],
            'line_m': [[-3., 0.], [3., 0.]], 'lane_polygon_m': [[-3., -20.], [3., -20.], [3., 0.], [-3., 0.]],
            'zone_m': [[-3., -10.], [3., -10.], [3., 0.], [-3., 0.]]}


def fixture_rows():
    return [{'track_id': '1', 'frame_id': str(i + 1), 'timestamp_ms': str(100 * (i + 1)), 'agent_type': 'car',
             'x': '0', 'y': str(-12 + i), 'psi_rad': str(math.pi / 2), 'length': '4', 'width': '2'}
            for i in range(16)]


def fixture_rule():
    layout = compilation_layout()
    return VisualRule.model_validate({'rule_id': 'unit-stop', 'entity': {'name': 'vehicle', 'concept': 'car'},
        'zones': [z.zone.model_dump() for z in layout.zones], 'lines': [line.line.model_dump() for line in layout.lines],
        'check': {'op': 'BEFORE', 'first': {'op': 'DWELL', 'zone': 'stop_zone', 'min_ms': 1000, 'max_speed': .01},
                  'then': {'op': 'CROSSES', 'line': 'stop_line', 'direction': 'to_right'}}})


def test_grid_fixed_and_units():
    assert TIMES_S == [i * .25 for i in range(13)]
    assert len(TIMES_S) * len(SPEEDS_MPS) == 156
    assert normalized((10., -10.)) == (.6, .5)
    assert local((2., 3.), fixture_approach()) == (2., 3.)
    r = grid_rule(fixture_rule(), 0., 1.)
    assert r.check.first.min_ms == 1
    assert r.check.first.max_speed == 1 / FRAME_M
    assert grid_rule(r, 1., None).check.first.max_speed is None


def test_selection_complete_direction_type_gaps_and_lane():
    a, rows = fixture_approach(), fixture_rows()
    segment, reason = approach_segment(rows, a)
    assert reason == 'included'
    assert segment['crossing_sample'] == 12
    assert segment['samples'][0][:3] == [0., 0., -12.]
    assert approach_segment(rows[4:], a)[1] == 'incomplete_10m_approach'
    wrong_direction = [dict(row, y=str(3 - i)) for i, row in enumerate(rows)]
    assert approach_segment(wrong_direction, a)[1] == 'no_inbound_crossing'
    assert approach_segment([dict(row, x='10') for row in rows], a)[1] == 'no_inbound_crossing'
    assert approach_segment([dict(row, agent_type='truck') for row in rows], a)[1] == 'not_car'
    assert approach_segment(rows[:5] + rows[6:], a)[1] == 'noncontiguous_samples'
    altered = [dict(row) for row in rows]
    altered[8]['x'] = '5'
    assert approach_segment(altered, a)[1] == 'left_approach_lanelet'
    altered[8]['length'] = 'nan'
    assert approach_segment(altered, a)[1] == 'invalid_numeric'


def test_clipped_wait_zone_is_ten_metres():
    zone = clip_y([[-3., -20.], [3., -20.], [3., 5.], [-3., 5.]], -10, 0)
    assert sorted(map(tuple, zone)) == [(-3., -10.), (-3., 0.), (3., -10.), (3., 0.)]


def test_yaw_dimensions_timestamps_and_source():
    a = fixture_approach()
    segment, _ = approach_segment(fixture_rows(), a)
    v = {'id': 'real-id', 'track_id': 7, **segment}
    ts = to_trackset(v, a, 'car')
    assert ts.source == SOURCE
    assert ts.source_ref == 'real-id'
    assert [f.timestamp_ms for f in ts.frames] == [i * 100 for i in range(16)]
    box = ts.frames[0].box
    assert box.x2 - box.x1 == pytest.approx(200.)  # 2 m width at 100 px/m
    assert box.y2 - box.y1 == pytest.approx(400.)  # 4 m length, heading downstream
    v['samples'][0][3] = 0.
    box = to_trackset(v, a, 'car').frames[0].box
    assert box.x2 - box.x1 == pytest.approx(400.)
    assert box.y2 - box.y1 == pytest.approx(200.)
    # Same world car after rotated coordinate frame has the same physical displacement.
    rotated = dict(a, ex=[0., 1.], ey=[-1., 0.])
    assert local((2., 3.), rotated) == (3., -2.)


def test_engine_speed_mapping():
    a = fixture_approach()
    vehicle = {'id': 'constant-speed', 'track_id': 1,
               'samples': [[i * 100., 0., -9 + i * .1, math.pi / 2, 4., 2.] for i in range(50)]}
    rule = bind_rule(fixture_rule(), a)
    track = build_tracks(rule, to_trackset(vehicle, a, 'car'))[0]
    assert not _stillness(track, .009)[10]  # 0.9 m/s is below actual 1 m/s
    assert _stillness(track, .011)[10]  # 1.1 m/s is above actual 1 m/s


def test_committed_population_and_map_evidence():
    data = load_data()
    population = json.loads((BENCH / 'population.json').read_text())
    assert sha(BENCH / 'derived.json.gz') == population['derived_sha256']
    assert data['source'] == SOURCE
    assert set(v['location'] for v in data['vehicles']) <= set(LOCATIONS)
    assert len(data['vehicles']) == population['included_approaches']
    assert len({v['id'] for v in data['vehicles']}) == len(data['vehicles'])
    assert len({(v['location'], v['recording'], v['track_id'], v['id'].split('/')[-1]) for v in data['vehicles']}) == len(
        data['vehicles'])
    for a in data['approaches']:
        assert a['stop_sign_ids'] or a['regulatory_subtype'] == 'all_way_stop'
        assert all(-10.00000001 <= p[1] <= .00000001 for p in a['zone_m'])
        assert a['line_id'] in a['id'] and a['lanelet_id'] in a['id']
        assert abs(sum(x * y for x, y in zip(a['ex'], a['ey'], strict=True))) < 1e-10
        assert math.hypot(*a['ex']) == pytest.approx(1.)
        assert math.hypot(*a['ey']) == pytest.approx(1.)
    for v in data['vehicles']:
        assert v['samples'][0][2] <= -10.
        assert all(b[0] - a[0] == 100. for a, b in zip(v['samples'], v['samples'][1:], strict=False))


def test_report_recomputes_every_cell_zero_calls():
    # Global conftest forbids live clients. No raw archive, env file or network is opened.
    committed = json.loads((BENCH / 'report.json').read_text())
    compiled = json.loads((BENCH / 'compile.json').read_text())
    assert compiled['live_calls'] <= 2
    assert compiled['model'] == 'muse-spark-1.3'
    assert compiled['preregistration_sha256'] == sha(BENCH / 'PREREGISTRATION.md')
    assert recompute(load_data(), compiled) == committed


def test_extract_explicit_stop_and_deduplicate_from_osm(tmp_path, monkeypatch):
    from eventproof.validation import interaction as m

    monkeypatch.setattr(m, 'LOCATIONS', ('test',))
    monkeypatch.setattr(m, 'BENCH', tmp_path / 'derived')
    maps = tmp_path / 'maps'
    maps.mkdir()
    # Opposite stored directions for the two boundary ways; nearest ref_line must win.
    xml = '''<osm>
    <node id="1" x="-2" y="-20"/><node id="2" x="-2" y="0"/>
    <node id="3" x="2" y="-20"/><node id="4" x="2" y="0"/>
    <node id="5" x="-2" y="100"/><node id="6" x="2" y="100"/>
    <way id="11"><nd ref="1"/><nd ref="2"/></way>
    <way id="12"><nd ref="4"/><nd ref="3"/></way>
    <way id="13"><nd ref="2"/><nd ref="4"/><tag k="type" v="stop_line"/></way>
    <way id="14"><nd ref="5"/><nd ref="6"/><tag k="type" v="stop_line"/></way>
    <way id="15"><nd ref="4"/><tag k="type" v="traffic_sign"/><tag k="subtype" v="usR1-1"/></way>
    <relation id="30"><member type="way" ref="11" role="left"/>
    <member type="way" ref="12" role="right"/><tag k="type" v="lanelet"/></relation>
    <relation id="31"><member type="way" ref="11" role="left"/>
    <member type="way" ref="12" role="right"/><tag k="type" v="lanelet"/></relation>
    <relation id="50"><member type="way" ref="13" role="ref_line"/>
    <member type="way" ref="14" role="ref_line"/><member type="way" ref="13" role="ref_line"/>
    <member type="way" ref="15" role="refers"/><member type="relation" ref="31" role="yield"/>
    <member type="relation" ref="30" role="yield"/>
    <tag k="type" v="regulatory_element"/><tag k="subtype" v="right_of_way"/></relation>
    <relation id="51"><member type="way" ref="13" role="ref_line"/>
    <member type="way" ref="15" role="refers"/><member type="relation" ref="30" role="yield"/>
    <tag k="type" v="regulatory_element"/><tag k="subtype" v="right_of_way"/></relation>
    <relation id="52"><member type="way" ref="14" role="ref_line"/>
    <member type="relation" ref="31" role="yield"/>
    <tag k="type" v="regulatory_element"/><tag k="subtype" v="right_of_way"/></relation>
    </osm>'''
    for suffix in ('.osm', '.osm_xy'):
        (maps / ('test' + suffix)).write_text(xml)
    evidence = m.select_maps(tmp_path)
    assert len(evidence['approaches']) == 2
    assert {a['line_id'] for a in evidence['approaches']} == {'13'}
    assert evidence['approaches'][0]['regulatory_ids'] == ['50', '51']
    assert evidence['approaches'][0]['lanelet_id'] == '30'
    assert evidence['approaches'][0]['ey'] == (0., 1.)
    assert evidence['excluded_regulations'][0]['regulatory_id'] == '52'
    # Full derivation must count one track/line once even with duplicate eligible lanelets.
    raw_tracks = tmp_path / 'recorded_trackfiles/test'
    raw_tracks.mkdir(parents=True)
    import csv
    with (raw_tracks / 'vehicle_tracks_000.csv').open('w') as f:
        rows = fixture_rows()
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (tmp_path / 'INTERACTION-Dataset-DR-v1_1.rar').write_bytes(b'unit-test archive hash input')
    m.BENCH.mkdir()
    m.derive(tmp_path, m.BENCH / 'derived.json.gz')
    derived = m.load_data(m.BENCH / 'derived.json.gz')
    assert len(derived['vehicles']) == 1
    assert derived['vehicles'][0]['approach_id'] == 'test:13:30'
    # A yield-only sign cannot be treated as STOP.
    (maps / 'test.osm').write_text(xml.replace('usR1-1', 'usR1-2'))
    assert not m.select_maps(tmp_path)['approaches']
