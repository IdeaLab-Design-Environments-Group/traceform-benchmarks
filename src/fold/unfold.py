"""Cut a closed panel mesh to a spanning tree and lay it flat.

Unfolding a closed genus-0 solid to one non-overlapping sheet cuts a spanning
tree of the vertex graph (V-1 edges), which leaves E-V+1 = P-1 fold edges on P
panels -- necessarily a spanning tree of the panel dual.  That is why the cut
edges matter so much here: they are exactly the edges that would otherwise have
given a route an alternative, and in this benchmark they come back as *seams*.

Cut selection is **steepest-edge unfolding** (Schlickenrieder 1997), the
standard overlap-minimising heuristic.  It is used here for a second reason:
it never consults mountain/valley, so it cannot be accused of choosing the
crease set that flatters one router.  kiri's own planCuts is deliberately not
used -- it weights cuts toward high-dihedral ridges, which is why house.fkld
comes out all-mountain when house.stl has valleys.
"""
from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Set, Tuple

from fold.load import MeshError
from fold.planarise import PanelEdge, PanelMesh
from geom import (
    Vec2,
    Vec3,
    bbox_diagonal,
    cross2,
    dist2,
    dot3,
    polygon_area,
    polygons_overlap,
    sub2,
    sub3,
    unit3,
)


class UnfoldError(RuntimeError):
    """Raised when no acceptable flat layout could be produced."""


@dataclass
class Seam:
    """A cut edge: two lips that were one edge before cutting, and mate again
    when the sheet is folded.  Copper may bridge it at a cost."""

    index: int
    edge: int                       # PanelEdge index it came from
    panel_a: int
    panel_b: int
    theta: float                    # the signed dihedral it still folds through
    lip_a: Tuple[Vec2, Vec2]        # flat endpoints on panel_a
    lip_b: Tuple[Vec2, Vec2]        # flat endpoints on panel_b
    length: float


@dataclass
class Crease:
    """A fold edge kept intact: the panels stay joined across it in the sheet."""

    index: int
    edge: int
    panel_a: int
    panel_b: int
    theta: float
    a: Vec2
    b: Vec2
    length: float


@dataclass
class FlatPattern:
    model_id: str
    polygons: List[List[Vec2]]                 # per panel, ordered loop
    panel_vertices: List[Dict[int, Vec2]]      # per panel, mesh vertex -> flat pos
    creases: List[Crease]
    seams: List[Seam]
    boundary: List[Tuple[Vec2, Vec2]]          # outer edges, never crossable
    scale: float
    panel_mesh: PanelMesh = None

    @property
    def diagonal(self) -> float:
        return bbox_diagonal(p for poly in self.polygons for p in poly)

    @property
    def cycle_count(self) -> int:
        return len(self.seams)


# ------------------------------------------------------------------ cut tree
def _sphere_directions(count: int, seed: int) -> List[Vec3]:
    """Deterministic, well-spread candidate directions (Fibonacci sphere).

    The seed rotates the set, so `seed` in config.yaml genuinely changes which
    unfoldings are tried, and two runs with the same seed try the same ones.
    """
    out: List[Vec3] = []
    golden = math.pi * (3.0 - math.sqrt(5.0))
    offset = (seed % 997) / 997.0
    for i in range(count):
        y = 1.0 - 2.0 * (i + 0.5) / count
        r = math.sqrt(max(0.0, 1.0 - y * y))
        phi = golden * i + 2.0 * math.pi * offset
        out.append((math.cos(phi) * r, y, math.sin(phi) * r))
    return out


def steepest_edge_cut_tree(pm: PanelMesh, direction: Vec3) -> Set[int]:
    """Spanning tree of the vertex graph: each vertex takes its steepest edge.

    Every vertex except the one maximising ``direction . v`` selects the
    incident panel edge whose unit direction climbs fastest along ``direction``.
    Following steepest ascent from any vertex reaches the maximum without
    revisiting, so the selected edges are acyclic and span -- a cut tree.
    """
    verts = sorted({v for e in pm.edges for v in (e.v0, e.v1)})
    incident: Dict[int, List[int]] = defaultdict(list)
    for e in pm.edges:
        incident[e.v0].append(e.index)
        incident[e.v1].append(e.index)

    coords = pm.mesh.vertices
    height = {v: dot3(coords[v], direction) for v in verts}
    top = max(verts, key=lambda v: (height[v], v))

    cut: Set[int] = set()
    for v in verts:
        if v == top:
            continue
        best_edge = None
        best_slope = -math.inf
        for ei in incident[v]:
            e = pm.edges[ei]
            other = e.v1 if e.v0 == v else e.v0
            if height[other] <= height[v]:
                continue
            slope = dot3(unit3(sub3(coords[other], coords[v])), direction)
            if slope > best_slope or (slope == best_slope and ei < best_edge):
                best_slope = slope
                best_edge = ei
        if best_edge is None:
            # A local maximum other than the global one: attach it upward by
            # the highest neighbour available, keeping the forest spanning.
            best_edge = max(
                incident[v],
                key=lambda ei: (
                    height[pm.edges[ei].v1 if pm.edges[ei].v0 == v else pm.edges[ei].v0],
                    -ei,
                ),
            )
        cut.add(best_edge)
    return cut


# ------------------------------------------------------------------ layout
def _panel_frame(pm: PanelMesh, pi: int) -> Dict[int, Vec2]:
    """Local 2D coordinates of a panel's loop, in its own plane."""
    panel = pm.panels[pi]
    loop = panel.loop
    origin = pm.mesh.vertices[loop[0]]
    u = unit3(sub3(pm.mesh.vertices[loop[1]], origin))
    n = panel.normal
    v = (
        n[1] * u[2] - n[2] * u[1],
        n[2] * u[0] - n[0] * u[2],
        n[0] * u[1] - n[1] * u[0],
    )
    out: Dict[int, Vec2] = {}
    for vi in loop:
        d = sub3(pm.mesh.vertices[vi], origin)
        out[vi] = (dot3(d, u), dot3(d, v))
    return out


def _place(local: Dict[int, Vec2], a: int, b: int, A: Vec2, B: Vec2,
           away_from: Vec2) -> Dict[int, Vec2]:
    """Rigidly map a panel's local frame so local[a]->A and local[b]->B.

    The reflection is chosen so the panel lands on the far side of AB from
    ``away_from`` (the parent's centroid), which is what stops a child from
    being laid straight back on top of its parent.
    """
    la, lb = local[a], local[b]
    d_local = sub2(lb, la)
    d_target = sub2(B, A)
    ang = math.atan2(d_target[1], d_target[0]) - math.atan2(d_local[1], d_local[0])
    ca, sa = math.cos(ang), math.sin(ang)

    placed: Dict[int, Vec2] = {}
    for vi, (x, y) in local.items():
        dx, dy = x - la[0], y - la[1]
        placed[vi] = (A[0] + ca * dx - sa * dy, A[1] + sa * dx + ca * dy)

    cx = sum(p[0] for p in placed.values()) / len(placed)
    cy = sum(p[1] for p in placed.values()) / len(placed)
    axis = sub2(B, A)
    side_child = cross2(axis, sub2((cx, cy), A))
    side_parent = cross2(axis, sub2(away_from, A))
    if side_child * side_parent > 0:
        # Reflect across the line AB.
        ux, uy = axis
        norm = math.hypot(ux, uy)
        ux, uy = ux / norm, uy / norm
        for vi, (x, y) in placed.items():
            dx, dy = x - A[0], y - A[1]
            proj = dx * ux + dy * uy
            rx, ry = 2 * proj * ux - dx, 2 * proj * uy - dy
            placed[vi] = (A[0] + rx, A[1] + ry)
    return placed


def _layout(pm: PanelMesh, cut: Set[int], isometry_tol: float
            ) -> Tuple[List[Dict[int, Vec2]], List[int]]:
    """BFS the panel dual over the fold edges, placing each panel isometrically."""
    fold_adj: Dict[int, List[Tuple[int, int]]] = defaultdict(list)
    for e in pm.edges:
        if e.index in cut:
            continue
        fold_adj[e.panel_a].append((e.panel_b, e.index))
        fold_adj[e.panel_b].append((e.panel_a, e.index))

    n = len(pm.panels)
    placed: List[Dict[int, Vec2]] = [None] * n
    order: List[int] = []
    root = 0
    placed[root] = _panel_frame(pm, root)
    order.append(root)
    queue = deque([root])
    while queue:
        p = queue.popleft()
        pc = placed[p]
        cx = sum(q[0] for q in pc.values()) / len(pc)
        cy = sum(q[1] for q in pc.values()) / len(pc)
        for q, ei in sorted(fold_adj[p]):
            if placed[q] is not None:
                continue
            e = pm.edges[ei]
            local = _panel_frame(pm, q)
            placed[q] = _place(local, e.v0, e.v1, pc[e.v0], pc[e.v1], (cx, cy))
            order.append(q)
            queue.append(q)

    missing = [i for i in range(n) if placed[i] is None]
    if missing:
        raise UnfoldError(
            f"fold edges do not span the panel graph: {len(missing)} panels unplaced"
        )

    # Isometry audit: every flat edge must equal its 3D rest length.
    for pi, pos in enumerate(placed):
        loop = pm.panels[pi].loop
        for k in range(len(loop)):
            a, b = loop[k], loop[(k + 1) % len(loop)]
            flat = dist2(pos[a], pos[b])
            rest = math.dist(pm.mesh.vertices[a], pm.mesh.vertices[b])
            if abs(flat - rest) > isometry_tol * max(1.0, rest):
                raise UnfoldError(
                    f"isometry audit failed on panel {pi} edge ({a},{b}): "
                    f"flat {flat:.9f} vs rest {rest:.9f}"
                )
    return placed, order


def _overlap_pairs(polys: Sequence[Sequence[Vec2]], eps: float) -> int:
    count = 0
    n = len(polys)
    for i in range(n):
        for j in range(i + 1, n):
            if polygons_overlap(polys[i], polys[j], eps):
                count += 1
    return count


# ------------------------------------------------------------------ driver
def unfold(pm: PanelMesh, model_id: str, cfg: dict) -> FlatPattern:
    ucfg = cfg["unfold"]
    tries = _sphere_directions(ucfg.get("candidate_directions", 96), cfg["seed"])

    best = None
    for direction in tries:
        cut = steepest_edge_cut_tree(pm, direction)
        try:
            placed, _ = _layout(pm, cut, ucfg["isometry_tol_mm"])
        except UnfoldError:
            continue
        polys = [[placed[pi][v] for v in pm.panels[pi].loop]
                 for pi in range(len(pm.panels))]
        bad = _overlap_pairs(polys, ucfg["overlap_eps_mm"])
        if best is None or bad < best[0]:
            best = (bad, cut, placed, polys)
        if bad == 0:
            break

    if best is None:
        raise UnfoldError(f"{model_id}: no candidate cut tree produced a valid layout")
    bad, cut, placed, polys = best
    if bad > 0:
        raise UnfoldError(
            f"{model_id}: best of {len(tries)} unfoldings still has {bad} "
            "overlapping panel pairs"
        )

    # Scale so the flat pattern's total panel area matches the configured
    # sheet.  Area rather than bbox diagonal: a circuit needs substrate to sit
    # on, and normalising by diagonal punishes an elongated pattern like
    # bat_body, whose panels came out too small to seat a part at all.
    area = sum(abs(polygon_area(poly)) for poly in polys)
    scale = math.sqrt(cfg["sheet"]["area_mm2"] / area)
    placed = [{v: (p[0] * scale, p[1] * scale) for v, p in pos.items()}
              for pos in placed]
    polys = [[placed[pi][v] for v in pm.panels[pi].loop]
             for pi in range(len(pm.panels))]

    creases: List[Crease] = []
    seams: List[Seam] = []
    for e in pm.edges:
        if e.index in cut:
            seams.append(
                Seam(
                    index=len(seams),
                    edge=e.index,
                    panel_a=e.panel_a,
                    panel_b=e.panel_b,
                    theta=e.theta,
                    lip_a=(placed[e.panel_a][e.v0], placed[e.panel_a][e.v1]),
                    lip_b=(placed[e.panel_b][e.v0], placed[e.panel_b][e.v1]),
                    length=e.length * scale,
                )
            )
        else:
            creases.append(
                Crease(
                    index=len(creases),
                    edge=e.index,
                    panel_a=e.panel_a,
                    panel_b=e.panel_b,
                    theta=e.theta,
                    a=placed[e.panel_a][e.v0],
                    b=placed[e.panel_a][e.v1],
                    length=e.length * scale,
                )
            )

    # Boundary = every lip of every seam.  These are the fabrication edges the
    # material is actually severed along; a trace may never cross one.
    boundary = [s.lip_a for s in seams] + [s.lip_b for s in seams]

    return FlatPattern(
        model_id=model_id,
        polygons=polys,
        panel_vertices=placed,
        creases=creases,
        seams=seams,
        boundary=boundary,
        scale=scale,
        panel_mesh=pm,
    )
