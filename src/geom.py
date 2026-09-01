"""Vector and segment primitives in plain floats, for bit-reproducible results."""
from __future__ import annotations

import math
from typing import Iterable, Sequence, Tuple

Vec3 = Tuple[float, float, float]
Vec2 = Tuple[float, float]


# 3D
def sub3(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add3(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def scale3(a: Vec3, k: float) -> Vec3:
    return (a[0] * k, a[1] * k, a[2] * k)


def dot3(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross3(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def norm3(a: Vec3) -> float:
    return math.sqrt(dot3(a, a))


def unit3(a: Vec3) -> Vec3:
    n = norm3(a)
    if n == 0.0:
        return (0.0, 0.0, 0.0)
    return (a[0] / n, a[1] / n, a[2] / n)


def dist3(a: Vec3, b: Vec3) -> float:
    return norm3(sub3(a, b))


def tri_normal(a: Vec3, b: Vec3, c: Vec3) -> Vec3:
    return unit3(cross3(sub3(b, a), sub3(c, a)))


def tri_area(a: Vec3, b: Vec3, c: Vec3) -> float:
    return 0.5 * norm3(cross3(sub3(b, a), sub3(c, a)))


def signed_dihedral(n1: Vec3, n2: Vec3, edge_dir: Vec3) -> float:
    """Signed dihedral in radians between two face normals about an edge, mountain positive.

    theta = -atan2((n1 x e_hat) . n2, n1 . n2), after kiri/src/pipeline/curvature.ts signedDihedral.
    """
    e = unit3(edge_dir)
    return -math.atan2(dot3(cross3(n1, e), n2), dot3(n1, n2))


# 2D
def sub2(a: Vec2, b: Vec2) -> Vec2:
    return (a[0] - b[0], a[1] - b[1])


def add2(a: Vec2, b: Vec2) -> Vec2:
    return (a[0] + b[0], a[1] + b[1])


def scale2(a: Vec2, k: float) -> Vec2:
    return (a[0] * k, a[1] * k)


def dot2(a: Vec2, b: Vec2) -> float:
    return a[0] * b[0] + a[1] * b[1]


def cross2(a: Vec2, b: Vec2) -> float:
    return a[0] * b[1] - a[1] * b[0]


def norm2(a: Vec2) -> float:
    return math.hypot(a[0], a[1])


def unit2(a: Vec2) -> Vec2:
    n = norm2(a)
    if n == 0.0:
        return (0.0, 0.0)
    return (a[0] / n, a[1] / n)


def dist2(a: Vec2, b: Vec2) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def nearest_on(p: Vec2, q: Vec2, r: Vec2, s: Vec2) -> Tuple[float, float, float]:
    """Exact distance between segments pq and rs as (d, t, u), with t and u clamped to [0, 1].

    The min over four point-to-segment distances is wrong for crossing segments.
    tests/test_geom.py pins (-10,0)-(10,0) vs (0,-10)-(0,10), whose distance is 0.
    """
    d1 = sub2(q, p)
    d2 = sub2(s, r)
    r0 = sub2(p, r)
    a = dot2(d1, d1)
    e = dot2(d2, d2)
    f = dot2(d2, r0)

    # Degenerate cases: one or both segments are points.
    if a <= 1e-18 and e <= 1e-18:
        return (dist2(p, r), 0.0, 0.0)
    if a <= 1e-18:
        u = min(1.0, max(0.0, f / e))
        return (dist2(p, add2(r, scale2(d2, u))), 0.0, u)
    c = dot2(d1, r0)
    if e <= 1e-18:
        t = min(1.0, max(0.0, -c / a))
        return (dist2(add2(p, scale2(d1, t)), r), t, 0.0)

    b = dot2(d1, d2)
    denom = a * e - b * b
    if denom > 1e-18:
        t = min(1.0, max(0.0, (b * f - c * e) / denom))
    else:
        # Parallel: any t works, take the start and let the clamps below fix it.
        t = 0.0
    u = (b * t + f) / e
    if u < 0.0:
        u = 0.0
        t = min(1.0, max(0.0, -c / a))
    elif u > 1.0:
        u = 1.0
        t = min(1.0, max(0.0, (b - c) / a))

    p1 = add2(p, scale2(d1, t))
    p2 = add2(r, scale2(d2, u))
    return (dist2(p1, p2), t, u)


def segments_cross(p: Vec2, q: Vec2, r: Vec2, s: Vec2) -> bool:
    """True if segments pq and rs properly intersect or touch."""
    return nearest_on(p, q, r, s)[0] <= 1e-9


def point_in_polygon(pt: Vec2, poly: Sequence[Vec2]) -> bool:
    """Winding-free even-odd ray cast.  Boundary points count as inside."""
    x, y = pt
    n = len(poly)
    inside = False
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        # On-edge test first, so a node exactly on a panel border is kept.
        if nearest_on(pt, pt, (ax, ay), (bx, by))[0] <= 1e-9:
            return True
        if (ay > y) != (by > y):
            xx = ax + (y - ay) * (bx - ax) / (by - ay)
            if xx > x:
                inside = not inside
    return inside


def polygon_area(poly: Sequence[Vec2]) -> float:
    """Signed area; positive for counter-clockwise."""
    total = 0.0
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        total += ax * by - bx * ay
    return 0.5 * total


def polygons_overlap(a: Sequence[Vec2], b: Sequence[Vec2], eps: float = 1e-4) -> bool:
    """Overlap test for possibly concave polygons, exact via edge-crossing and containment checks."""
    # Any pair of edges crossing with real penetration.
    n, m = len(a), len(b)
    for i in range(n):
        p, q = a[i], a[(i + 1) % n]
        for j in range(m):
            r, s = b[j], b[(j + 1) % m]
            d, _, _ = nearest_on(p, q, r, s)
            if d < -eps:  # unreachable; kept for symmetry of intent
                return True
            if d <= eps:
                # Edges touching along a shared crease are fine. Only transverse crossings count.
                d1 = sub2(q, p)
                d2 = sub2(s, r)
                if abs(cross2(unit2(d1), unit2(d2))) > 1e-6:
                    o1 = cross2(d1, sub2(r, p))
                    o2 = cross2(d1, sub2(s, p))
                    o3 = cross2(d2, sub2(p, r))
                    o4 = cross2(d2, sub2(q, r))
                    if (o1 * o2 < -eps) and (o3 * o4 < -eps):
                        return True
    # Full containment, which produces no edge crossings at all.
    if _centroid_inside(a, b) or _centroid_inside(b, a):
        return True
    return False


def _centroid_inside(inner: Sequence[Vec2], outer: Sequence[Vec2]) -> bool:
    cx = sum(p[0] for p in inner) / len(inner)
    cy = sum(p[1] for p in inner) / len(inner)
    return point_in_polygon((cx, cy), outer)


def bbox2(points: Iterable[Vec2]) -> Tuple[float, float, float, float]:
    pts = list(points)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def bbox_diagonal(points: Iterable[Vec2]) -> float:
    x0, y0, x1, y1 = bbox2(points)
    return math.hypot(x1 - x0, y1 - y0)
