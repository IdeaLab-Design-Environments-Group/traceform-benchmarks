import math

import pytest

from fold.strain import SheetSpec, bend_radius_mm, fold_strain, max_trace_width_mm


@pytest.fixture
def spec(cfg):
    return SheetSpec.from_config(cfg)


def test_fibre_offset_is_half_the_substrate_plus_the_foil(spec):
    assert spec.fibre_offset_mm == pytest.approx(spec.substrate_mm / 2 + spec.foil_mm)


def test_flat_fold_produces_no_strain(spec):
    assert abs(fold_strain(spec, 0.0)) < 1e-9


def test_strain_is_proportional_to_angle(spec):
    a = fold_strain(spec, math.radians(10))
    b = fold_strain(spec, math.radians(20))
    assert b == pytest.approx(2 * a, rel=1e-9)


def test_strain_is_inversely_proportional_to_hinge_width(spec):
    wide = SheetSpec(**{**spec.__dict__, "hinge_width_mm": spec.hinge_width_mm * 2})
    assert (fold_strain(wide, math.radians(30))
            == pytest.approx(fold_strain(spec, math.radians(30)) / 2, rel=1e-9))


def test_mountain_is_tension_and_valley_is_compression(spec):
    """Mountain positive, after kiri's signedDihedral and foldStrain."""
    theta = math.radians(90)
    assert fold_strain(spec, theta) > 0
    assert fold_strain(spec, -theta) < 0
    assert fold_strain(spec, theta) == pytest.approx(-fold_strain(spec, -theta))


def test_strain_matches_a_hand_computed_value(spec):
    # eps = (h/2 + t) * theta / w = 0.235 * (pi/6) / 2.0
    expected = 0.235 * (math.pi / 6) / 2.0
    assert fold_strain(spec, math.radians(30)) == pytest.approx(expected, rel=1e-9)


def test_bend_radius_is_the_arc_relation(spec):
    theta = math.radians(45)
    assert bend_radius_mm(spec, theta) == pytest.approx(spec.hinge_width_mm / theta)


def test_strain_is_not_clipped_at_the_fatigue_limit(spec):
    """kiri charges min(1, eps/eps_fatigue), whose ceiling is reached at about
    12 degrees on this sheet.  Clipped, a 15-degree and a 90-degree mountain
    price identically and traceform degenerates into mountain_penalty."""
    shallow = fold_strain(spec, math.radians(15))
    steep = fold_strain(spec, math.radians(90))
    assert shallow > spec.fatigue_strain, "both are already past the ceiling"
    assert steep > shallow * 5, "yet they must still be ordered"


def test_stiffening_bound_does_not_bind_on_this_sheet(spec, cfg):
    """Reported, not enforced: it sits orders of magnitude above the trace."""
    bound = max_trace_width_mm(spec, 20.0)
    assert bound > cfg["routing"]["trace_width_mm"] * 100
