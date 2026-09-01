"""Route each net as a growing tree. Congestion is tolled, only component bodies block."""
from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

from geom import Vec2, dist2
from layouts import Layout, Placement
from routing.dijkstra import dijkstra, trace_back
from routing.graph import CREASE, INTRA, SEAM, VIA, Edge, RoutingGraph
from routing.methods import make_weight


@dataclass
class Crossing:
    kind: str
    fold_id: int
    theta_deg: float
    strain: float
    at: Vec2


@dataclass
class Trace:
    net: str
    edges: List[int]
    segments: List[Tuple[Vec2, Vec2]]
    panels: List[int]
    length_mm: float
    crossings: List[Crossing]
    connected: bool
    # Face per segment, aligned with `segments`. Empty when single-sided (outer face).
    segment_sides: List[int] = field(default_factory=list)
    via_count: int = 0


@dataclass
class RouteResult:
    traces: List[Trace]
    stranded: List[Tuple[str, str]]        # (net, "ref.pad")
    terminal_nodes: Dict[Tuple[str, str], int]
    nodes_expanded: int
    runtime_ms: float
    graph: "RoutingGraph" = None           # the graph actually routed on,
                                           # includes pad nodes, so the validator can resolve edge indices


def _blocked_nodes(graph: RoutingGraph, layout: Layout) -> Set[int]:
    """Nodes under a component body, outer face only. Far-face copper can run underneath."""
    blocked: Set[int] = set()
    limit = graph.side_offset if graph.side_offset is not None else len(graph.nodes)
    for pl in layout.placements:
        x0, y0, x1, y1 = pl.rect
        for ni in range(limit):
            x, y = graph.nodes[ni]
            if x0 <= x <= x1 and y0 <= y <= y1:
                blocked.add(ni)
    return blocked


def attach_terminals(graph: RoutingGraph, layout: Layout, blocked: Set[int],
                     cfg: dict) -> Tuple[RoutingGraph, Dict[Tuple[str, str], int],
                                         List[Tuple[str, str]], Set[int]]:
    """Give each pad its own node, joined to the lattice by short escape edges.
    Pads sit in the body keep-out, so snapping to a free node strands most Xiao pads."""
    escape_max = cfg["routing"].get("pad_escape_mm", 12.0)
    escape_fanout = cfg["routing"].get("pad_escape_fanout", 6)

    nodes = list(graph.nodes)
    node_panel = list(graph.node_panel)
    edges = list(graph.edges)
    incident = {k: list(v) for k, v in graph.incident.items()}

    term: Dict[Tuple[str, str], int] = {}
    lost: List[Tuple[str, str]] = []
    pad_nodes: Set[int] = set()
    # Each pad claims its escape nodes. Shared ones short nets at the USB (pads 2.0mm apart).
    claimed: Set[int] = set()

    for net in layout.nets:
        for ref, pad in net.points:
            pl = layout.by_ref(ref)
            at = pl.pad_at(pad)
            # Pads live on the outer face: parts are mounted on one side.
            limit = (graph.side_offset if graph.side_offset is not None
                     else len(graph.nodes))
            near = sorted(
                ((dist2(graph.nodes[ni], at), ni)
                 for ni in range(limit)
                 if ni not in blocked and ni not in claimed
                 and dist2(graph.nodes[ni], at) <= escape_max
                 and graph.node_panel[ni] == pl.panel),
                key=lambda t: (t[0], t[1]))[:escape_fanout]
            if not near:
                # Nothing unclaimed in reach, so share nodes. The validator reports the crowding,
                # and a stranded pad would be a false negative.
                near = sorted(
                    ((dist2(graph.nodes[ni], at), ni)
                     for ni in range(limit)
                     if ni not in blocked
                     and dist2(graph.nodes[ni], at) <= escape_max
                     and graph.node_panel[ni] == pl.panel),
                    key=lambda t: (t[0], t[1]))[:escape_fanout]
            if not near:
                lost.append((net.name, f"{ref}.{pad}"))
                continue
            claimed.update(ni for _d, ni in near)
            pn = len(nodes)
            nodes.append(at)
            node_panel.append(pl.panel)
            pad_nodes.add(pn)
            for d, ni in near:
                ei = len(edges)
                edges.append(Edge(index=ei, u=pn, v=ni, length=d, kind=INTRA))
                incident.setdefault(pn, []).append(ei)
                incident.setdefault(ni, []).append(ei)
            term[(net.name, f"{ref}.{pad}")] = pn

    node_grid = list(graph.node_grid) + [None] * (len(nodes) - len(graph.nodes))
    g2 = RoutingGraph(flat=graph.flat, nodes=nodes, node_panel=node_panel,
                      node_grid=node_grid, side_offset=graph.side_offset,
                      edges=edges, incident=incident,
                      pitch=graph.pitch, strain_max=graph.strain_max,
                      diagonal=graph.diagonal)
    return g2, term, lost, pad_nodes


def _edge_segments(graph: RoutingGraph, e: Edge) -> List[Tuple[Vec2, Vec2]]:
    """Flat-pattern segments of a routed edge. A seam bridge is two runs, one per lip."""
    u, v = graph.nodes[e.u], graph.nodes[e.v]
    if e.kind == SEAM and e.cross_at is not None:
        ma, mb = e.cross_at
        return [(u, ma), (mb, v)]
    return [(u, v)]


def _search_for(method: str):
    """Search for a method: the shared Dijkstra, or traceform's withheld one if present."""
    if method != "traceform":
        def plain(graph, sources, weight, *, blocked, targets, node_cost,
                  no_transit, cfg):
            return dijkstra(graph, sources, weight, blocked=blocked,
                            targets=targets, node_cost=node_cost,
                            no_transit=no_transit)
        return plain
    from routing import traceform_impl
    return traceform_impl.search


def route(graph: RoutingGraph, layout: Layout, method: str, cfg: dict) -> RouteResult:
    weight = make_weight(method, graph, cfg)
    rc = cfg["routing"]
    occupied_toll = rc["occupied_toll_diagonals"] * graph.diagonal
    halo_toll = rc["halo_toll_diagonals"] * graph.diagonal
    clear = rc["trace_width_mm"] + rc["clearance_mm"]

    blocked = _blocked_nodes(graph, layout)
    graph, term_nodes, stranded, pad_nodes = attach_terminals(
        graph, layout, blocked, cfg)

    def side_of(ni: int) -> int:
        off = graph.side_offset
        return 0 if off is None or ni < off else 1

    # Clearance halo via a spatial hash, same-face pairs only (twins share coordinates).
    # Lattice edges miss it whenever the pitch exceeds `clear`, leaving the halo empty.
    halo_of: Dict[int, List[int]] = defaultdict(list)
    cell = max(clear, 1e-6)
    buckets: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for ni, (x, y) in enumerate(graph.nodes):
        buckets[(int(math.floor(x / cell)), int(math.floor(y / cell)))].append(ni)
    for (bx, by), members in buckets.items():
        near: List[int] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                near.extend(buckets.get((bx + dx, by + dy), ()))
        for ni in members:
            p_i = graph.nodes[ni]
            for nj in near:
                if nj != ni and side_of(nj) == side_of(ni) \
                        and dist2(p_i, graph.nodes[nj]) < clear:
                    halo_of[ni].append(nj)

    # Crossing diagonals of one lattice cell share no node, so each one prices its partner.
    diagonal_partner: Dict[int, int] = {}
    diag_by_cell: Dict[Tuple[int, int, int, int], List[int]] = defaultdict(list)
    for e in graph.edges:
        if e.kind != INTRA:
            continue
        ga, gb = graph.node_grid[e.u], graph.node_grid[e.v]
        if ga is None or gb is None:
            continue
        di, dj = gb[0] - ga[0], gb[1] - ga[1]
        if abs(di) != 1 or abs(dj) != 1:
            continue
        cell = (graph.node_panel[e.u], min(ga[0], gb[0]), min(ga[1], gb[1]),
                side_of(e.u))
        diag_by_cell[cell].append(e.index)
    for members in diag_by_cell.values():
        if len(members) == 2:
            a, b = members
            diagonal_partner[a] = b
            diagonal_partner[b] = a

    used: Set[int] = set()
    used_edges: Set[int] = set()
    halo: Set[int] = set()

    # Copper used by another net is tolled (kiri's OCCUPIED_TOLL). A hard block would strand
    # terminals on a single-layer socket fan-out. Shared copper shows up in short_pair_count.
    # Running near another net pays the lighter halo toll.
    def node_cost(v: int) -> float:
        if v in used:
            return occupied_toll
        if v in halo:
            return halo_toll
        return 0.0

    def priced(e: Edge) -> float:
        cost = weight(e)
        partner = diagonal_partner.get(e.index)
        if e.index in used_edges or (partner is not None and partner in used_edges):
            cost += occupied_toll
        return cost

    # Widest net (GND) first, small nets thread around it. Order depends only on the netlist.
    order = cfg["routing"].get("net_order", "widest_first")
    if order == "widest_first":
        nets = sorted(layout.nets, key=lambda n: (-len(n.points), n.name))
    elif order == "narrowest_first":
        nets = sorted(layout.nets, key=lambda n: (len(n.points), n.name))
    else:
        nets = list(layout.nets)

    t0 = time.perf_counter()
    traces: List[Trace] = []
    expanded = 0

    for net in nets:
        keys = [(net.name, f"{ref}.{pad}") for ref, pad in net.points]
        present = [term_nodes[k] for k in keys if k in term_nodes]
        if len(present) < 2:
            if present:
                used.update(present)
            traces.append(Trace(net=net.name, edges=[], segments=[], panels=[],
                                length_mm=0.0, crossings=[],
                                connected=len(present) == len(keys),
                                segment_sides=[], via_count=0))
            continue

        tree: Set[int] = {present[0]}
        loose = set(present[1:])
        net_edges: List[int] = []
        ok = True
        while loose:
            search = _search_for(method)
            res = search(graph, tree, priced, blocked=blocked,
                         targets=set(loose), node_cost=node_cost,
                         no_transit=pad_nodes, cfg=cfg)
            expanded += res.nodes_expanded
            reachable = [t for t in sorted(loose) if t in res.dist]
            if not reachable:
                ok = False
                for k in keys:
                    if term_nodes.get(k) in loose:
                        stranded.append(k)
                break
            nearest = min(reachable, key=lambda t: (res.dist[t], t))
            path = trace_back(graph, res, nearest)
            net_edges.extend(path)
            for ei in path:
                e = graph.edges[ei]
                used_edges.add(ei)
                tree.add(e.u)
                tree.add(e.v)
            tree.add(nearest)
            loose.discard(nearest)

        segments: List[Tuple[Vec2, Vec2]] = []
        segment_sides: List[int] = []
        crossings: List[Crossing] = []
        panels: List[int] = []
        length = 0.0
        vias = 0
        off = graph.side_offset
        for ei in net_edges:
            e = graph.edges[ei]
            segs = _edge_segments(graph, e)
            segments.extend(segs)
            segment_sides.extend(
                [0 if off is None or e.u < off else 1] * len(segs))
            length += e.length
            for n in (e.u, e.v):
                p = graph.node_panel[n]
                if not panels or panels[-1] != p:
                    panels.append(p)
            if e.kind == VIA:
                vias += 1
            elif e.kind != INTRA:
                at = e.cross_at[0] if e.cross_at else graph.nodes[e.u]
                crossings.append(
                    Crossing(kind=e.kind, fold_id=e.fold_id,
                             theta_deg=math.degrees(e.theta),
                             strain=e.strain, at=at))

        for n in tree:
            used.add(n)
            for m in halo_of.get(n, ()):
                halo.add(m)

        traces.append(Trace(net=net.name, edges=net_edges, segments=segments,
                            panels=panels, length_mm=length,
                            crossings=crossings, connected=ok,
                            segment_sides=segment_sides, via_count=vias))

    runtime_ms = (time.perf_counter() - t0) * 1000.0
    # Report traces in netlist order, whatever order they were routed in.
    position = {n.name: i for i, n in enumerate(layout.nets)}
    traces.sort(key=lambda t: position[t.net])
    return RouteResult(traces=traces, stranded=sorted(set(stranded)),
                       terminal_nodes=term_nodes, nodes_expanded=expanded,
                       runtime_ms=runtime_ms, graph=graph)
