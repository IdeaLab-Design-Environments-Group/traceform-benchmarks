"""Loading, planarising and unfolding: the invariants the whole benchmark rests on."""
import math
import os

import pytest

from fold.load import MeshError, TriMesh, build_topology, load_mesh, orient, weld
from fold.planarise import planarise
from fold.unfold import UnfoldError, steepest_edge_cut_tree, unfold
from geom import dist2

MODELS = ["house", "church", "bat_body"]


def _cube() -> TriMesh:
    v = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
         (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    faces = []
    for a, b, c, d in quads:
        faces += [(a, b, c), (a, c, d)]
    mesh = TriMesh(vertices=[tuple(map(float, p)) for p in v], faces=faces)
    build_topology(mesh)
    orient(mesh)
    build_topology(mesh)
    return mesh


@pytest.fixture(scope="session")
def loaded(cfg, root):
    out = {}
    for m in cfg["models"]:
        mesh = load_mesh(os.path.join(root, m["mesh"]), cfg["mesh"]["weld_decimals"])
        pm = planarise(mesh, cfg["mesh"]["flat_eps_deg"], cfg["mesh"]["planarity_rel"])
        out[m["id"]] = (mesh, pm, unfold(pm, m["id"], cfg))
    return out


def test_a_cube_is_six_panels_all_folding_the_same_way(cfg):
    """A convex solid has no reflex edges, so every crease takes one sign.
    This is exactly why a convex model cannot exercise the benchmark."""
    pm = planarise(_cube(), cfg["mesh"]["flat_eps_deg"], cfg["mesh"]["planarity_rel"])
    assert len(pm.panels) == 6
    assert len(pm.edges) == 12
    signs = {e.assignment for e in pm.edges}
    assert signs == {"M"} or signs == {"V"}
    for e in pm.edges:
        assert abs(abs(math.degrees(e.theta)) - 90.0) < 1e-6


def test_binary_stl_is_rejected_rather_than_misread(tmp_path):
    blob = tmp_path / "b.stl"
    blob.write_bytes(b"\0" * 84 + b"\1" * 50)
    with pytest.raises(MeshError):
        load_mesh(str(blob))


def test_an_open_mesh_is_rejected(tmp_path):
    one = tmp_path / "one.stl"
    one.write_text("solid s\nfacet normal 0 0 1\nouter loop\n"
                   "vertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\n"
                   "endloop\nendfacet\nendsolid s\n")
    with pytest.raises(MeshError, match="open"):
        load_mesh(str(one))


@pytest.mark.parametrize("model", MODELS)
def test_models_are_closed_genus_zero(loaded, model):
    mesh, _pm, _flat = loaded[model]
    assert mesh.euler == 2
    assert all(len(f) == 2 for f in mesh.edge_faces.values())


@pytest.mark.parametrize("model", MODELS)
def test_the_convex_models_are_all_mountain(loaded, model):
    """house, church and bat_body are convex solids, so they have no reflex
    edges and every crease is a mountain.  Recorded as a test because it is a
    limit on what those models can show: with no valleys there is no
    tension-versus-compression alternative, and compression_crossing_count is
    necessarily zero in every one of their rows."""
    _mesh, pm, _flat = loaded[model]
    signs = [e.assignment for e in pm.edges]
    assert signs.count("M") == len(pm.edges)
    assert signs.count("V") == 0


def test_a_non_convex_model_does_yield_valleys(cfg, root):
    """The pipeline detects valleys where they exist -- so the all-mountain
    result above is a property of those meshes, not a bug in the sign."""
    path = os.path.join(root, "data", "meshes", "bat-wing-left.stl")
    if not os.path.exists(path):
        pytest.skip("bat-wing-left.stl not vendored")
    mesh = load_mesh(path, cfg["mesh"]["weld_decimals"])
    pm = planarise(mesh, cfg["mesh"]["flat_eps_deg"], cfg["mesh"]["planarity_rel"])
    signs = [e.assignment for e in pm.edges]
    assert signs.count("V") > 0
    assert signs.count("M") > 0


def test_merging_across_a_curved_region_is_refused(cfg, root):
    """A chain of near-flat steps builds a panel that is not planar; laying it
    out then silently stretches its edges.  Guarded at the merge."""
    path = os.path.join(root, "data", "meshes", "bat-wing-left.stl")
    if not os.path.exists(path):
        pytest.skip("bat-wing-left.stl not vendored")
    mesh = load_mesh(path, cfg["mesh"]["weld_decimals"])
    with pytest.raises(MeshError, match="not planar"):
        planarise(mesh, 1.0, cfg["mesh"]["planarity_rel"])


@pytest.mark.parametrize("model", MODELS)
def test_unfolding_obeys_the_euler_arithmetic(loaded, model):
    """Cutting a closed genus-0 solid leaves a spanning tree of the panel dual:
    P-1 creases.  Everything else becomes a seam, and the seam count is exactly
    the number of independent cycles the seams give back."""
    _mesh, pm, flat = loaded[model]
    assert len(flat.creases) == len(flat.polygons) - 1
    assert len(flat.creases) + len(flat.seams) == len(pm.edges)
    assert len(flat.seams) == flat.cycle_count
    assert flat.cycle_count > 0


@pytest.mark.parametrize("model", MODELS)
def test_unfolding_is_isometric(loaded, model, cfg):
    """Every flat edge must equal its 3D rest length, or the pattern would not
    fold back onto the model."""
    mesh, pm, flat = loaded[model]
    for pi, panel in enumerate(pm.panels):
        loop = panel.loop
        pos = flat.panel_vertices[pi]
        for k in range(len(loop)):
            a, b = loop[k], loop[(k + 1) % len(loop)]
            flat_len = dist2(pos[a], pos[b])
            rest = math.dist(mesh.vertices[a], mesh.vertices[b]) * flat.scale
            assert flat_len == pytest.approx(rest, rel=1e-9, abs=1e-9)


@pytest.mark.parametrize("model", MODELS)
def test_flat_pattern_has_no_overlapping_panels(loaded, model, cfg):
    from geom import polygons_overlap
    _mesh, _pm, flat = loaded[model]
    polys = flat.polygons
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            assert not polygons_overlap(polys[i], polys[j],
                                        cfg["unfold"]["overlap_eps_mm"])


@pytest.mark.parametrize("model", MODELS)
def test_a_seam_keeps_the_fold_angle_of_the_edge_it_replaced(loaded, model):
    _mesh, pm, flat = loaded[model]
    for s in flat.seams:
        assert s.theta == pm.edges[s.edge].theta


def test_cut_tree_is_a_spanning_tree_of_the_vertex_graph(loaded, cfg):
    """Steepest-edge selects one edge per vertex bar the highest: V-1 edges,
    acyclic because every choice strictly climbs."""
    _mesh, pm, _flat = loaded["house"]
    cut = steepest_edge_cut_tree(pm, (0.3, 0.5, 0.81))
    verts = {v for e in pm.edges for v in (e.v0, e.v1)}
    assert len(cut) == len(verts) - 1


def test_the_cut_tree_never_looks_at_mountain_or_valley(loaded):
    """Outcome-blind by construction: flipping every sign leaves it unchanged."""
    _mesh, pm, _flat = loaded["house"]
    before = steepest_edge_cut_tree(pm, (0.3, 0.5, 0.81))
    for e in pm.edges:
        e.theta = -e.theta
    after = steepest_edge_cut_tree(pm, (0.3, 0.5, 0.81))
    for e in pm.edges:
        e.theta = -e.theta
    assert before == after
