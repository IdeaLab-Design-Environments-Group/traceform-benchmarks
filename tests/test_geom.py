import math

from geom import (nearest_on, point_in_polygon, polygon_area, polygons_overlap,
                  signed_dihedral)


def test_crossing_segments_are_zero_apart():
    """The bug kiri hit: a minimum over four point-to-segment projections
    reports 10 here, where the true distance is 0."""
    d, t, u = nearest_on((-10, 0), (10, 0), (0, -10), (0, 10))
    assert d == 0.0
    assert 0.0 < t < 1.0 and 0.0 < u < 1.0


def test_parallel_and_collinear_distances():
    assert nearest_on((0, 0), (10, 0), (0, 5), (10, 5))[0] == 5.0
    assert nearest_on((0, 0), (1, 0), (2, 0), (3, 0))[0] == 1.0
    assert nearest_on((0, 0), (0, 0), (3, 4), (3, 4))[0] == 5.0


def test_touching_at_an_endpoint_is_zero_but_not_transverse():
    d, t, u = nearest_on((0, 0), (1, 0), (1, 0), (2, 1))
    assert d == 0.0
    assert math.isclose(t, 1.0) and math.isclose(u, 0.0)


def test_point_in_polygon_includes_the_border():
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon((5, 5), square)
    assert point_in_polygon((0, 5), square)      # on an edge
    assert not point_in_polygon((-0.5, 5), square)


def test_polygon_area_sign_follows_winding():
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert polygon_area(square) == 100.0
    assert polygon_area(list(reversed(square))) == -100.0


def test_overlap_detection():
    a = [(0, 0), (10, 0), (10, 10), (0, 10)]
    b = [(5, 5), (15, 5), (15, 15), (5, 15)]
    far = [(100, 100), (110, 100), (110, 110)]
    inside = [(2, 2), (4, 2), (4, 4), (2, 4)]
    shares_edge = [(10, 0), (20, 0), (20, 10), (10, 10)]
    assert polygons_overlap(a, b)
    assert not polygons_overlap(a, far)
    assert polygons_overlap(a, inside)          # containment, no edge crossing
    assert not polygons_overlap(a, shares_edge)  # a shared crease is not overlap


def test_signed_dihedral_is_zero_when_flat_and_signed_otherwise():
    up = (0.0, 0.0, 1.0)
    edge = (1.0, 0.0, 0.0)
    assert abs(signed_dihedral(up, up, edge)) < 1e-12
    a = signed_dihedral(up, (0.0, -1.0, 0.0), edge)
    b = signed_dihedral(up, (0.0, 1.0, 0.0), edge)
    assert abs(abs(a) - math.pi / 2) < 1e-12
    assert a * b < 0, "the two bend directions must take opposite signs"
