"""The published cost functions, and the limiting cases that pin them apart.

The traceform cost is withheld (see README); its tests travel with it.
"""
import copy
import math
import os

import pytest

from fold.load import load_mesh
from fold.planarise import planarise
from fold.strain import SheetSpec
from fold.unfold import unfold
from footprints import load_library
from layouts import build_layout
from routing.graph import CREASE, INTRA, SEAM, Edge, build_graph
from routing.methods import make_weight
from routing.router import route


@pytest.fixture(scope="module")
def house(cfg, root):
    mesh = load_mesh(os.path.join(root, "data", "meshes", "house.stl"),
                     cfg["mesh"]["weld_decimals"])
    pm = planarise(mesh, cfg["mesh"]["flat_eps_deg"], cfg["mesh"]["planarity_rel"])
    flat = unfold(pm, "house", cfg)
    graph = build_graph(flat, SheetSpec.from_config(cfg), cfg)
    library = load_library(os.path.join(root, "data", "footprints"))
    return flat, graph, library


def _edge(kind, theta=0.0, strain=0.0, length=10.0):
    return Edge(index=0, u=0, v=1, length=length, kind=kind,
                theta=theta, strain=strain, fold_id=0)


def test_length_only_charges_only_length(house, cfg):
    _flat, graph, _lib = house
    w = make_weight("length_only", graph, cfg)
    assert w(_edge(INTRA, length=7.0)) == 7.0
    assert w(_edge(CREASE, theta=1.5, strain=0.2, length=7.0)) == 7.0


def test_mountain_penalty_adds_the_diagonal_to_a_mountain(house, cfg):
    _flat, graph, _lib = house
    w = make_weight("mountain_penalty", graph, cfg)
    flat_edge = _edge(CREASE, theta=0.0, strain=0.0)
    mountain = _edge(CREASE, theta=1.0, strain=0.2)
    shallow_valley = _edge(CREASE, theta=-1.0, strain=-0.2)
    steep_valley = _edge(CREASE, theta=-math.radians(175), strain=-0.4)
    assert w(mountain) == pytest.approx(flat_edge.length + graph.diagonal)
    assert w(shallow_valley) == pytest.approx(flat_edge.length)
    # A valley folded past closure lies back on itself and can short.
    assert w(steep_valley) == pytest.approx(flat_edge.length + graph.diagonal)


def test_mountain_penalty_cannot_tell_a_shallow_mountain_from_a_steep_one(house, cfg):
    """The baseline is binary in the fold angle: a 6 deg mountain and an 86 deg
    mountain cost exactly the same.  This is the gap traceform exists to close."""
    _flat, graph, _lib = house
    w = make_weight("mountain_penalty", graph, cfg)
    assert w(_edge(CREASE, theta=0.1, strain=0.01)) == \
           w(_edge(CREASE, theta=1.5, strain=0.30))


def test_every_method_pays_the_same_seam_cost(house, cfg):
    """So the seam mechanic cannot tilt the comparison toward any of them."""
    _flat, graph, _lib = house
    seam = _edge(SEAM, theta=0.0, strain=0.0, length=4.0)
    plain = _edge(INTRA, length=4.0)
    costs = {m: make_weight(m, graph, cfg)(seam) - make_weight(m, graph, cfg)(plain)
             for m in ("length_only", "mountain_penalty")}
    assert len(set(round(c, 9) for c in costs.values())) == 1
    assert costs["length_only"] == pytest.approx(cfg["routing"]["seam_cost_mm"])


def test_an_unknown_method_is_refused(house, cfg):
    _flat, graph, _lib = house
    with pytest.raises(ValueError):
        make_weight("wishful_thinking", graph, cfg)
