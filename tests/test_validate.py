"""The validator must catch violations that the router did not report itself."""
import os

import pytest

from fold.load import load_mesh
from fold.planarise import planarise
from fold.strain import SheetSpec
from fold.unfold import unfold
from footprints import load_library
from layouts import build_layout
from routing.graph import build_graph
from routing.router import Trace, route
from validate import validate


@pytest.fixture(scope="module")
def instance(cfg, root):
    mesh = load_mesh(os.path.join(root, "data", "meshes", "house.stl"),
                     cfg["mesh"]["weld_decimals"])
    pm = planarise(mesh, cfg["mesh"]["flat_eps_deg"], cfg["mesh"]["planarity_rel"])
    flat = unfold(pm, "house", cfg)
    graph = build_graph(flat, SheetSpec.from_config(cfg), cfg)
    library = load_library(os.path.join(root, "data", "footprints"))
    layout = build_layout(flat, "A", library, cfg)
    result = route(graph, layout, "length_only", cfg)
    return flat, layout, result


def test_a_clean_run_reports_no_cut_violations(instance, cfg):
    flat, layout, result = instance
    assert validate(flat, layout, result, cfg).cut_violation_count == 0


def test_an_injected_cut_crossing_is_caught(instance, cfg):
    """The graph builds no edge across a boundary, so this can only come from a
    bug -- which is exactly why the check is recomputed from geometry."""
    flat, layout, result = instance
    a, b = flat.boundary[0]
    # A segment straddling a boundary edge, crossing it transversally.
    mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    dx, dy = b[0] - a[0], b[1] - a[1]
    nx, ny = -dy, dx
    scale = 5.0 / max(1e-9, (nx * nx + ny * ny) ** 0.5)
    seg = ((mid[0] - nx * scale, mid[1] - ny * scale),
           (mid[0] + nx * scale, mid[1] + ny * scale))

    poisoned = list(result.traces) + [
        Trace(net="GHOST", edges=[], segments=[seg], panels=[],
              length_mm=10.0, crossings=[], connected=True)]
    original, result.traces = result.traces, poisoned
    try:
        report = validate(flat, layout, result, cfg)
    finally:
        result.traces = original
    assert report.cut_violation_count >= 1
    assert any(net == "GHOST" for net, _seg in report.cut_violations)


def test_an_injected_clearance_violation_is_caught(instance, cfg):
    """Two nets a hair apart: below trace_width + clearance, so it is a defect
    even though the traces never touch."""
    flat, layout, result = instance
    gap = (cfg["routing"]["trace_width_mm"] + cfg["routing"]["clearance_mm"]) * 0.5
    x, y = flat.polygons[0][0]
    a = Trace(net="GHOST_A", edges=[], segments=[((x, y), (x + 20.0, y))],
              panels=[], length_mm=20.0, crossings=[], connected=True)
    b = Trace(net="GHOST_B", edges=[],
              segments=[((x, y + gap), (x + 20.0, y + gap))],
              panels=[], length_mm=20.0, crossings=[], connected=True)

    original, result.traces = result.traces, list(result.traces) + [a, b]
    try:
        report = validate(flat, layout, result, cfg)
    finally:
        result.traces = original
    pairs = {(p[0], p[1]) for p in report.clearance_violations}
    assert ("GHOST_A", "GHOST_B") in pairs
    assert report.min_separation_mm <= gap + 1e-9


def test_two_nets_sharing_copper_are_reported_as_a_short(instance, cfg):
    flat, layout, result = instance
    x, y = flat.polygons[0][0]
    seg = ((x, y), (x + 20.0, y))
    a = Trace(net="GHOST_A", edges=[], segments=[seg], panels=[],
              length_mm=20.0, crossings=[], connected=True)
    b = Trace(net="GHOST_B", edges=[], segments=[seg], panels=[],
              length_mm=20.0, crossings=[], connected=True)
    original, result.traces = result.traces, list(result.traces) + [a, b]
    try:
        report = validate(flat, layout, result, cfg)
    finally:
        result.traces = original
    assert ("GHOST_A", "GHOST_B") in set(report.short_pairs)


def test_the_validator_never_consults_the_router(instance, cfg):
    """Its verdict must come from the trace geometry, so blanking the router's
    own bookkeeping must not change the geometric findings."""
    flat, layout, result = instance
    before = validate(flat, layout, result, cfg)
    expanded, result.nodes_expanded = result.nodes_expanded, 0
    runtime, result.runtime_ms = result.runtime_ms, 0.0
    try:
        after = validate(flat, layout, result, cfg)
    finally:
        result.nodes_expanded, result.runtime_ms = expanded, runtime
    assert before.cut_violation_count == after.cut_violation_count
    assert before.clearance_violation_count == after.clearance_violation_count
