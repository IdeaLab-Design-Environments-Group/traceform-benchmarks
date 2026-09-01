"""The shared shortest-path search.

The comparison is only meaningful if the search is identical and the *cost* is
the only thing that varies, so there is one implementation here and the
published methods differ solely in the weight callback handed to it.

The traceform router replaces this search as well as the cost; it is withheld
(see README) and `router.route` reaches it through an optional import.

Ties are broken by node index rather than by heap order, so the search is
deterministic and two runs of the benchmark produce identical paths.
"""
from __future__ import annotations

import heapq
import math
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from routing.graph import Edge, RoutingGraph

WeightFn = Callable[[Edge], float]


class SearchResult:
    __slots__ = ("dist", "prev_edge", "nodes_expanded")

    def __init__(self, dist: Dict[int, float], prev_edge: Dict[int, int],
                 nodes_expanded: int) -> None:
        self.dist = dist
        self.prev_edge = prev_edge
        self.nodes_expanded = nodes_expanded


def dijkstra(graph: RoutingGraph, sources: Iterable[int], weight: WeightFn,
             blocked: Optional[set] = None,
             targets: Optional[set] = None,
             node_cost: Optional[Callable[[int], float]] = None,
             no_transit: Optional[set] = None) -> SearchResult:
    """Multi-source Dijkstra over the routing graph.

    `blocked` nodes are removed outright -- that is how a component body keeps
    copper from running underneath it.  Nothing else is ever removed: every
    mechanical penalty is a finite cost, so the search can always fall back on
    a bad crossing when there is no alternative.

    `node_cost` prices arriving at a node, which is how congestion is charged:
    a node another net already used is dear, never forbidden.

    `no_transit` nodes may be reached but not routed through, unless the search
    started there.  Pads are such nodes: copper connects to a pad, but a trace
    belonging to some other net may not hop across a part by way of it.
    """
    blocked = blocked or set()
    dist: Dict[int, float] = {}
    prev_edge: Dict[int, int] = {}
    heap: List[Tuple[float, int]] = []
    for s in sorted(sources):
        if s in blocked:
            continue
        dist[s] = 0.0
        heapq.heappush(heap, (0.0, s))

    sources_set = set(dist)
    remaining = set(targets) if targets is not None else None
    expanded = 0
    settled = set()
    while heap:
        d, u = heapq.heappop(heap)
        if u in settled:
            continue
        settled.add(u)
        expanded += 1
        if remaining is not None and u in remaining:
            # Dijkstra settles in nondecreasing distance, so the first target
            # settled is the nearest one -- which is all the net-tree growth
            # actually asks for.  Continuing to settle the rest would expand
            # the whole graph for an answer that is already known.
            break
        if no_transit is not None and u in no_transit and u not in sources_set:
            continue
        for ei in graph.incident.get(u, ()):
            e = graph.edges[ei]
            v = e.v if e.u == u else e.u
            if v in blocked or v in settled:
                continue
            nd = d + weight(e)
            if node_cost is not None:
                nd += node_cost(v)
            if nd < dist.get(v, math.inf) - 1e-12:
                dist[v] = nd
                prev_edge[v] = ei
                heapq.heappush(heap, (nd, v))
    return SearchResult(dist, prev_edge, expanded)


def trace_back(graph: RoutingGraph, result: SearchResult, target: int) -> List[int]:
    """Edge indices from the nearest source to `target`, source-first."""
    path: List[int] = []
    cur = target
    while cur in result.prev_edge:
        ei = result.prev_edge[cur]
        path.append(ei)
        e = graph.edges[ei]
        cur = e.v if e.u == cur else e.u
    path.reverse()
    return path
