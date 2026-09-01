"""Route every net, on any of the three cost functions.

Nets are routed in a fixed order and each grows as a tree: a multi-source
search from what is already connected out to the nearest terminal still
loose.  Same Dijkstra throughout; only the edge weight changes with the method.

Congestion is priced, not forbidden -- kiri's OCCUPIED_TOLL, "a used node is
dear, never forbidden".  A router that strands a terminal to keep its spacing
is a worse router, so the only hard obstacle here is a component body.  That
also means every stranded terminal in the results came from a part physically
enclosing a pad, never from the strain penalty, which is always finite.
"""
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
    # Which face each segment runs on, index-aligned with `segments`.  Empty
    # when routing is single-sided; the validator then assumes the outer face.
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
                                           # pad nodes included, so the
                                           # validator can resolve edge indices
                                           # without a module-level cache


def _blocked_nodes(graph: RoutingGraph, layout: Layout) -> Set[int]:
    """Nodes under a component body, on the face the part is mounted on.

    Only the outer face: a part occupies its own side of the sheet, and copper
    on the far face runs under it freely -- which is half the point of having
    a second face at all."""
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
    """Give every pad its own node, joined to the lattice by escape edges.

    A pad sits under its own component body, and the body is a keep-out, so
    snapping each pad to "the nearest free lattice node" strands any pad more
    than a hop from the part's edge -- which on a 21mm Xiao socket is most of
    them.  Modelling the pad as a real node with a short escape to open
    substrate is both truer to fabrication and the only way the keep-out means
    what it should: no *through* traffic under a part, but its own pads still
    connect.
    """
    escape_max = cfg["routing"].get("pad_escape_mm", 12.0)
    escape_fanout = cfg["routing"].get("pad_escape_fanout", 6)

    nodes = list(graph.nodes)
    node_panel = list(graph.node_panel)
    edges = list(graph.edges)
    incident = {k: list(v) for k, v in graph.incident.items()}

    term: Dict[Tuple[str, str], int] = {}
    lost: List[Tuple[str, str]] = []
    pad_nodes: Set[int] = set()
    # Each pad claims its escape nodes exclusively.  Sharing them shorts nets
    # together at the connector: the USB pads sit 2.0mm apart, so without this
    # four different nets fan out through the same lattice node and the
    # occupied toll, being finite, cannot price its way out of a place with no
    # alternative.
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
                # Nothing unclaimed within reach.  Fall back on shared nodes
                # rather than strand the pad: a crowded escape is a clearance
                # problem the validator will report, but a stranded terminal
                # would be a false negative -- the pad is physically reachable.
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
    """Flat-pattern geometry of one routed edge.

    A seam bridge is not a traverse across the sheet: the copper runs out to
    its own lip on each side and the two ends mate when the model is folded.
    Rendering it as one long segment would draw a trace straight across the
    pattern that no fabricator would cut.
    """
    u, v = graph.nodes[e.u], graph.nodes[e.v]
    if e.kind == SEAM and e.cross_at is not None:
        ma, mb = e.cross_at
        return [(u, ma), (mb, v)]
    return [(u, v)]


def _search_for(method: str):
    """Which shortest-path search a method uses.

    The published methods all share the one Dijkstra, so the cost is the only
    thing that varies between them.  traceform substitutes its own search and
    is withheld (see README); its module is imported only if present.
    """
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

    # Clearance halo: every node within `clear` of another, found through a
    # spatial hash rather than the edge list.  Same-face pairs only: the twin
    # node on the far face shares these exact coordinates, and copper separated
    # by the substrate is not a clearance problem.  Deriving it from lattice edges
    # is wrong whenever the pitch exceeds `clear` -- the halo then contains
    # nothing at all and quietly stops charging for crowding.
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

    # Two diagonals of the same lattice cell cross in mid-air.  Node occupancy
    # alone never notices -- the two edges share no node -- so two nets can
    # short straight through each other's diagonal.  Each diagonal is paired
    # with the one it crosses, and using either prices the other.
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

    # Copper already carrying another net is dear but not forbidden, following
    # kiri's OCCUPIED_TOLL.  Forbidding it outright was tried and is worse: a
    # single-layer fan-out from a 14-pin socket cannot avoid crossings at all,
    # so a hard block does not remove the conflict, it converts it into a
    # stranded terminal -- three to five of them even in the control layout.
    # Tolling keeps connectivity and surfaces the conflict as a measurement:
    # `short_pair_count` counts the net pairs sharing copper, which is exactly
    # the set of places a real board would need a jumper or a second layer.
    # Reported, never hidden.  Running merely *near* another net is the
    # lighter `halo` toll.
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

    # Net order.  The biggest multi-terminal net (GND) has to reach everywhere,
    # so it goes first and the small nets thread around it; left until last it
    # finds every corridor already claimed and strands.  The order depends only
    # on the netlist, never on the method, so it cannot tilt the comparison.
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
