"""Two-sided routing: the sign flips with the face, the price does not."""
import copy
import os

import pytest

from fold.load import load_mesh
from fold.planarise import planarise
from fold.strain import SheetSpec
from fold.unfold import unfold
from footprints import load_library
from layouts import build_layout
from routing.graph import INTRA, VIA, build_graph
from routing.methods import make_weight
from routing.router import route


@pytest.fixture(scope="module")
def cfg(cfg):  # noqa: F811 -- deliberately shadows the session fixture
    """Two-sided routing is no longer the shipped configuration -- the process
    these systems build for is copper on one face of one sheet -- but the
    machinery still exists and this module still pins it, so it switches it on
    for itself rather than relying on the default."""
    c = copy.deepcopy(cfg)
    c["routing"]["sides"]["enabled"] = True
    return c


@pytest.fixture(scope="module")
def house(cfg, root):
    mesh = load_mesh(os.path.join(root, "data", "meshes", "house.stl"),
                     cfg["mesh"]["weld_decimals"])
    pm = planarise(mesh, cfg["mesh"]["flat_eps_deg"], cfg["mesh"]["planarity_rel"])
    flat = unfold(pm, "house", cfg)
    graph = build_graph(flat, SheetSpec.from_config(cfg), cfg)
    library = load_library(os.path.join(root, "data", "footprints"))
    return flat, graph, library


def test_the_inner_face_sees_every_crease_negated(house):
    """Mirrored edges are appended in the base edges' order, so twin pairs are
    matched by position -- matching by node pair would collide where several
    seam samples join the same two nodes."""
    _flat, graph, _lib = house
    off = graph.side_offset
    assert off is not None and off > 0
    vias = sum(1 for e in graph.edges if e.kind == VIA)
    assert vias == off, "one via per outer node"
    base_count = (len(graph.edges) - vias) // 2
    for i in range(base_count):
        twin, mirror = graph.edges[i], graph.edges[base_count + i]
        assert mirror.u == twin.u + off and mirror.v == twin.v + off
        assert mirror.strain == -twin.strain
        assert mirror.theta == -twin.theta
        assert mirror.length == twin.length and mirror.kind == twin.kind


def test_every_method_pays_the_same_via_price(house, cfg):
    _flat, graph, _lib = house
    via = next(e for e in graph.edges if e.kind == VIA)
    plain = next(e for e in graph.edges if e.kind == INTRA)
    costs = {}
    for m in ("length_only", "mountain_penalty"):
        w = make_weight(m, graph, cfg)
        costs[m] = w(via)
    assert len(set(round(c, 9) for c in costs.values())) == 1
    assert costs["length_only"] == pytest.approx(
        cfg["routing"]["sides"]["via_cost_mm"])


def test_the_blind_baseline_buys_a_via_only_for_congestion(house, cfg):
    """length_only cannot see strain, but it can see congestion, and the far
    face doubles capacity -- so under tolls it may legitimately dive through.
    With the tolls zeroed there is no reason left, and it must route exactly
    as if the second face did not exist."""
    flat, graph, library = house
    quiet = copy.deepcopy(cfg)
    quiet["routing"]["occupied_toll_diagonals"] = 0.0
    quiet["routing"]["halo_toll_diagonals"] = 0.0
    layout = build_layout(flat, "B", library, quiet)
    r = route(graph, layout, "length_only", quiet)
    assert sum(t.via_count for t in r.traces) == 0


def test_switching_sides_off_restores_the_single_sided_graph(house, cfg, root):
    single = copy.deepcopy(cfg)
    single["routing"]["sides"]["enabled"] = False
    mesh = load_mesh(os.path.join(root, "data", "meshes", "house.stl"),
                     cfg["mesh"]["weld_decimals"])
    pm = planarise(mesh, cfg["mesh"]["flat_eps_deg"], cfg["mesh"]["planarity_rel"])
    flat = unfold(pm, "house", single)
    g1 = build_graph(flat, SheetSpec.from_config(single), single)
    assert g1.side_offset is None
    assert not any(e.kind == VIA for e in g1.edges)
