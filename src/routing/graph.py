"""The routing graph: nodes on panels, edges within panels and across folds.

Node lattice is global, so nodes on either side of a crease line up.  Three
kinds of edge leave a panel, and the whole benchmark keys off the distinction:

  crease   the panels are still joined here; copper bends through theta
  seam     the panels were cut apart; the lips mate when folded, so copper may
           bridge the joint at a cost, still bending through the same theta
  boundary never crossable -- and no edge is ever created across one, which is
           why cut_violation_count is structurally zero and any nonzero value
           is a bug rather than a result
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from fold.strain import SheetSpec, fold_strain
from fold.unfold import FlatPattern
from geom import Vec2, bbox2, dist2, nearest_on, point_in_polygon

CREASE = "crease"
SEAM = "seam"
INTRA = "intra"
VIA = "via"


@dataclass
class Edge:
    index: int
    u: int
    v: int
    length: float
    kind: str
    theta: float = 0.0        # signed fold angle, mountain positive
    strain: float = 0.0       # signed outer-fibre strain
    fold_id: int = -1         # crease or seam index
    cross_at: Optional[Tuple[Vec2, Vec2]] = None   # the two lip points bridged


@dataclass
class RoutingGraph:
    flat: FlatPattern
    nodes: List[Vec2]
    node_panel: List[int]
    node_grid: List[Optional[Tuple[int, int]]]
    # First index of the inner-face twin nodes, or None when routing is
    # single-sided.  Node i and node i+side_offset are the same point on the
    # sheet, seen from the two faces; every fold edge on the inner side carries
    # the copper's-eye view of the crease -- theta and strain negated -- because
    # a mountain that stretches copper on the outer face compresses it on the
    # inner one.  That one flip is what makes every sign- or strain-aware
    # method side-aware with no further changes, while length_only, which never
    # reads either field, stays blind: the control.
    side_offset: Optional[int]
    edges: List[Edge]
    incident: Dict[int, List[int]]
    pitch: float
    strain_max: float
    diagonal: float
    blocked: set = field(default_factory=set)

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)


def _segment_inside(poly: Sequence[Vec2], p: Vec2, q: Vec2) -> bool:
    """True if pq stays within the panel: no transverse crossing of its border."""
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        d, t, u = nearest_on(p, q, a, b)
        if d > 1e-9:
            continue
        # Touching the border is fine (the crease is the border); a crossing
        # strictly through the interior of both segments is not.
        if 1e-6 < t < 1 - 1e-6 and 1e-6 < u < 1 - 1e-6:
            return False
    mid = ((p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0)
    return point_in_polygon(mid, poly)


def _nearest_node(nodes_by_panel: Dict[int, List[int]], nodes: List[Vec2],
                  panel: int, target: Vec2, limit: float) -> Optional[int]:
    best, best_d = None, limit
    for ni in nodes_by_panel.get(panel, ()):
        d = dist2(nodes[ni], target)
        if d < best_d:
            best, best_d = ni, d
    return best


def build_graph(flat: FlatPattern, spec: SheetSpec, cfg: dict) -> RoutingGraph:
    pitch = cfg["routing"]["grid_pitch_mm"]

    # ------------------------------------------------------- node lattice
    x0, y0, x1, y1 = bbox2(p for poly in flat.polygons for p in poly)
    nodes: List[Vec2] = []
    node_panel: List[int] = []
    node_grid: List[Optional[Tuple[int, int]]] = []
    nodes_by_panel: Dict[int, List[int]] = defaultdict(list)
    grid_index: Dict[Tuple[int, int, int], int] = {}

    nx = int(math.ceil((x1 - x0) / pitch)) + 1
    ny = int(math.ceil((y1 - y0) / pitch)) + 1
    for pi, poly in enumerate(flat.polygons):
        px0, py0, px1, py1 = bbox2(poly)
        i0 = max(0, int((px0 - x0) / pitch) - 1)
        i1 = min(nx, int((px1 - x0) / pitch) + 2)
        j0 = max(0, int((py0 - y0) / pitch) - 1)
        j1 = min(ny, int((py1 - y0) / pitch) + 2)
        for i in range(i0, i1):
            for j in range(j0, j1):
                p = (x0 + i * pitch, y0 + j * pitch)
                if not point_in_polygon(p, poly):
                    continue
                ni = len(nodes)
                nodes.append(p)
                node_panel.append(pi)
                node_grid.append((i, j))
                nodes_by_panel[pi].append(ni)
                grid_index[(pi, i, j)] = ni

    # ------------------------------------------------- intra-panel edges
    edges: List[Edge] = []
    seen = set()
    for (pi, i, j), u in sorted(grid_index.items()):
        poly = flat.polygons[pi]
        for di, dj in ((1, 0), (0, 1), (1, 1), (1, -1)):
            v = grid_index.get((pi, i + di, j + dj))
            if v is None:
                continue
            key = (min(u, v), max(u, v))
            if key in seen:
                continue
            if not _segment_inside(poly, nodes[u], nodes[v]):
                continue
            seen.add(key)
            edges.append(
                Edge(index=len(edges), u=u, v=v,
                     length=dist2(nodes[u], nodes[v]), kind=INTRA)
            )

    # ------------------------------------------------------ fold crossings
    def add_crossings(fold_id: int, theta: float, seg_a: Tuple[Vec2, Vec2],
                      seg_b: Tuple[Vec2, Vec2], pa: int, pb: int, kind: str) -> None:
        """Sample along the fold and join the nearest node on each side.

        For a crease both segments are the same line, so this joins across it.
        For a seam they are the two lips, far apart in the flat pattern but
        coincident once folded -- the copper runs to one lip and resumes at the
        other, which is what a taped joint is.
        """
        strain = fold_strain(spec, theta)
        length = dist2(seg_a[0], seg_a[1])
        count = max(1, int(length / pitch))
        for k in range(count):
            s = (k + 0.5) / count
            ma = (seg_a[0][0] + s * (seg_a[1][0] - seg_a[0][0]),
                  seg_a[0][1] + s * (seg_a[1][1] - seg_a[0][1]))
            mb = (seg_b[0][0] + s * (seg_b[1][0] - seg_b[0][0]),
                  seg_b[0][1] + s * (seg_b[1][1] - seg_b[0][1]))
            na = _nearest_node(nodes_by_panel, nodes, pa, ma, 2.0 * pitch)
            nb = _nearest_node(nodes_by_panel, nodes, pb, mb, 2.0 * pitch)
            if na is None or nb is None or na == nb:
                continue
            if kind == CREASE:
                span = dist2(nodes[na], nodes[nb])
            else:
                # A seam bridge is not a flat traverse: the copper only runs
                # from each node out to its own lip.
                span = dist2(nodes[na], ma) + dist2(nodes[nb], mb)
            edges.append(
                Edge(index=len(edges), u=na, v=nb, length=span, kind=kind,
                     theta=theta, strain=strain, fold_id=fold_id,
                     cross_at=(ma, mb))
            )

    for c in flat.creases:
        add_crossings(c.index, c.theta, (c.a, c.b), (c.a, c.b),
                      c.panel_a, c.panel_b, CREASE)
    for s in flat.seams:
        add_crossings(s.index, s.theta, s.lip_a, s.lip_b,
                      s.panel_a, s.panel_b, SEAM)

    # ------------------------------------------------------ two-sided routing
    side_offset: Optional[int] = None
    sides_cfg = cfg["routing"].get("sides", {})
    if sides_cfg.get("enabled"):
        side_offset = len(nodes)
        nodes = nodes + list(nodes)
        node_panel = node_panel + list(node_panel)
        node_grid = node_grid + list(node_grid)
        mirrored: List[Edge] = []
        for e in edges:
            mirrored.append(
                Edge(index=len(edges) + len(mirrored),
                     u=e.u + side_offset, v=e.v + side_offset,
                     length=e.length, kind=e.kind,
                     theta=-e.theta, strain=-e.strain,
                     fold_id=e.fold_id, cross_at=e.cross_at))
        edges = edges + mirrored
        # A via at every node: a plated hole (or, in tape, a through-tab) that
        # carries the trace to the other face.  Zero planar length; its price
        # lives in the cost functions and is identical for every method, so
        # the mechanism itself cannot tilt the comparison.
        for i in range(side_offset):
            edges.append(Edge(index=len(edges), u=i, v=i + side_offset,
                              length=0.0, kind=VIA))

    incident: Dict[int, List[int]] = defaultdict(list)
    for e in edges:
        incident[e.u].append(e.index)
        incident[e.v].append(e.index)

    strain_max = max((abs(e.strain) for e in edges if e.kind != INTRA), default=1.0)
    if strain_max <= 0:
        strain_max = 1.0

    return RoutingGraph(
        flat=flat, nodes=nodes, node_panel=node_panel, node_grid=node_grid,
        side_offset=side_offset, edges=edges, incident=dict(incident),
        pitch=pitch, strain_max=strain_max, diagonal=flat.diagonal,
    )
