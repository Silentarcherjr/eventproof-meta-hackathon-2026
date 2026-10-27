from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from eventproof.engine.geometry import point_in_polygon, segments_intersect

unit = st.floats(min_value=0, max_value=1, allow_nan=False)


@given(unit, unit, unit, unit, unit, unit)
def test_rectangle_membership_matches_bounds(x0, x1, y0, y1, px, py):
    lo_x, hi_x = sorted((x0, x1))
    lo_y, hi_y = sorted((y0, y1))
    poly = [(lo_x, lo_y), (hi_x, lo_y), (hi_x, hi_y), (lo_x, hi_y)]
    expected = lo_x <= px <= hi_x and lo_y <= py <= hi_y
    # points within numeric tolerance of an edge are deliberately "inside"; skip that band
    near_edge = min(abs(px - lo_x), abs(px - hi_x), abs(py - lo_y), abs(py - hi_y)) < 1e-9
    if hi_x - lo_x > 1e-9 and hi_y - lo_y > 1e-9 and not near_edge:
        assert point_in_polygon((px, py), poly) == expected


@given(unit, unit, unit, unit, unit, unit, unit, unit)
def test_segment_intersection_is_symmetric(a, b, c, d, e, f, g, h):
    p1, p2, q1, q2 = (a, b), (c, d), (e, f), (g, h)
    assert segments_intersect(p1, p2, q1, q2) == segments_intersect(q1, q2, p1, p2)
