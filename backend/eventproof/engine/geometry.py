"""Pure 2D geometry in normalized [0,1] image coordinates (y grows downward)."""

from __future__ import annotations

Pt = tuple[float, float]


def point_in_polygon(p: Pt, poly: list[Pt]) -> bool:
    """Ray casting; points exactly on an edge count as inside."""
    x, y = p
    inside = False
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        if _on_segment(p, (x1, y1), (x2, y2)):
            return True
        if (y1 > y) != (y2 > y):
            x_cross = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_cross:
                inside = not inside
    return inside


def cross(a: Pt, b: Pt, p: Pt) -> float:
    """z of (b-a) x (p-a). With y pointing down, > 0 means p is on the right walking a→b."""
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def segments_intersect(p1: Pt, p2: Pt, q1: Pt, q2: Pt) -> bool:
    d1, d2 = cross(q1, q2, p1), cross(q1, q2, p2)
    d3, d4 = cross(p1, p2, q1), cross(p1, p2, q2)
    if ((d1 > 0) != (d2 > 0)) and d1 != 0 and d2 != 0 and ((d3 > 0) != (d4 > 0)) and d3 != 0 and d4 != 0:
        return True
    return (
        (d1 == 0 and _on_segment(p1, q1, q2))
        or (d2 == 0 and _on_segment(p2, q1, q2))
        or (d3 == 0 and _on_segment(q1, p1, p2))
        or (d4 == 0 and _on_segment(q2, p1, p2))
    )


def _on_segment(p: Pt, a: Pt, b: Pt, eps: float = 1e-12) -> bool:
    if abs(cross(a, b, p)) > eps:
        return False
    return min(a[0], b[0]) - eps <= p[0] <= max(a[0], b[0]) + eps and min(a[1], b[1]) - eps <= p[1] <= max(
        a[1], b[1]
    ) + eps
