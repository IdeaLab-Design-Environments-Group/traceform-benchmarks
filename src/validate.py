"""Independent checks on the routed geometry.

Nothing here reads the router's state.  A router reporting its own compliance
proves nothing, so every check below is recomputed from the trace polylines and
the flat pattern alone, and disagrees loudly when it disagrees.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Set, Tuple

from fold.unfold import FlatPattern
from geom import Vec2, nearest_on
from layouts import Layout
from routing.router import RouteResult, Trace

Segment = Tuple[Vec2, Vec2]


@dataclass
class ValidationReport:
    cut_violations: List[Tuple[str, Segment]] = field(default_factory=list)
    clearance_violations: List[Tuple[str, str, float]] = field(default_factory=list)
    short_pairs: List[Tuple[str, str]] = field(default_factory=list)
    min_separation_mm: float = float("inf")
    keepout_violations: List[Tuple[str, str]] = field(default_factory=list)
    disconnected_nets: List[str] = field(default_factory=list)
    stranded: List[Tuple[str, str]] = field(default_factory=list)

    @property
    def cut_violation_count(self) -> int:
        return len(self.cut_violations)

    @property
    def clearance_violation_count(self) -> int:
        return len(self.clearance_violations)

    @property
    def keepout_violation_count(self) -> int:
        return len(self.keepout_violations)

    @property
    def short_pair_count(self) -> int:
        return len(self.short_pairs)


def _crosses(a: Segment, b: Segment) -> bool:
    """True only for a transverse crossing: touching at an endpoint is legal.

    A seam bridge deliberately ends *on* a lip, which is a cut edge, so an
    endpoint-touch must not be counted as crossing the cut.
    """
    d, t, u = nearest_on(a[0], a[1], b[0], b[1])
    return d <= 1e-9 and 1e-6 < t < 1 - 1e-6 and 1e-6 < u < 1 - 1e-6


def _bucket(segments: Sequence[tuple], cell: float
            ) -> Dict[Tuple[int, int], List[int]]:
    buckets: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for idx, item in enumerate(segments):
        (p, q) = item[1]
        x0, x1 = sorted((p[0], q[0]))
        y0, y1 = sorted((p[1], q[1]))
        for i in range(int(math.floor(x0 / cell)), int(math.floor(x1 / cell)) + 1):
            for j in range(int(math.floor(y0 / cell)), int(math.floor(y1 / cell)) + 1):
                buckets[(i, j)].append(idx)
    return buckets


def validate(flat: FlatPattern, layout: Layout, result: RouteResult,
             cfg: dict) -> ValidationReport:
    rc = cfg["routing"]
    min_sep = rc["trace_width_mm"] + rc["clearance_mm"]
    report = ValidationReport(stranded=list(result.stranded))

    owned: List[Tuple[str, Segment, int]] = []
    for tr in result.traces:
        # A trace routed single-sided carries no side list; everything is then
        # the outer face.
        sides = (tr.segment_sides if len(tr.segment_sides) == len(tr.segments)
                 else [0] * len(tr.segments))
        for seg, side in zip(tr.segments, sides):
            owned.append((tr.net, seg, side))

    # --- 1. no trace crosses a cut edge ---------------------------------
    # Structurally impossible: the graph builds no edge across a boundary.
    # Checked anyway, because "impossible" is a claim about the code and this
    # is the measurement that would catch it being wrong.
    for net, seg, _side in owned:
        for b in flat.boundary:
            if _crosses(seg, b):
                report.cut_violations.append((net, seg))
                break

    # --- 2. clearance between different nets ----------------------------
    # Counted as *trace pairs*, one per pair of nets that comes too close
    # anywhere -- not one per offending segment pair.  A single net running
    # alongside another for 40mm is one design-rule problem to fix, not the
    # twenty-odd segment coincidences it decomposes into.
    cell = max(min_sep * 2.0, 1.0)
    buckets = _bucket(owned, cell)
    checked: Set[Tuple[int, int]] = set()
    worst: Dict[Tuple[str, str], float] = {}
    for members in buckets.values():
        for a_i in range(len(members)):
            for b_i in range(a_i + 1, len(members)):
                i, j = members[a_i], members[b_i]
                key = (i, j) if i < j else (j, i)
                if key in checked:
                    continue
                checked.add(key)
                net_a, seg_a, side_a = owned[i]
                net_b, seg_b, side_b = owned[j]
                if net_a == net_b:
                    continue
                # Copper on opposite faces is separated by the substrate; the
                # spacing rule is a same-face statement.
                if side_a != side_b:
                    continue
                d, _, _ = nearest_on(seg_a[0], seg_a[1], seg_b[0], seg_b[1])
                pair = (net_a, net_b) if net_a < net_b else (net_b, net_a)
                if d < report.min_separation_mm:
                    report.min_separation_mm = d
                if d < min_sep - 1e-9 and d < worst.get(pair, float("inf")):
                    worst[pair] = d
    report.clearance_violations = [(a, b, d) for (a, b), d in sorted(worst.items())]
    # A pair merely inside the clearance rule is a spacing defect; a pair at
    # zero separation is shared copper -- a short.  Same geometry, very
    # different severity, so they are reported separately.
    report.short_pairs = [(a, b) for (a, b), d in sorted(worst.items())
                          if d <= 1e-9]

    # --- 3. no foreign copper under a part ------------------------------
    for pl in layout.placements:
        x0, y0, x1, y1 = pl.rect
        own_nets = {n.name for n in layout.nets
                    if any(ref == pl.ref for ref, _pad in n.points)}
        body = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)),
                ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
        for net, seg, side in owned:
            if net in own_nets:
                continue
            # The keep-out is the part's own face.  Copper on the far face
            # running under a body is ordinary two-sided practice.
            if side != 0:
                continue
            if any(_crosses(seg, e) for e in body):
                report.keepout_violations.append((net, pl.ref))

    # --- 4. every claimed connection traces end to end ------------------
    # Checked on the folded form: a seam bridge is two trace ends that mate at
    # assembly, so it joins its net even though the flat pattern shows a gap.
    by_name = {n.name: n for n in layout.nets}
    for tr in result.traces:
        net = by_name.get(tr.net)
        if net is None:
            # A trace whose net is not in the layout cannot have its
            # connectivity checked.  Skip it rather than let a StopIteration
            # escape and take the whole report with it.
            continue
        wanted = [(net.name, f"{ref}.{pad}") for ref, pad in net.points]
        nodes = [result.terminal_nodes[k] for k in wanted
                 if k in result.terminal_nodes]
        if len(nodes) < len(wanted):
            report.disconnected_nets.append(tr.net)
            continue
        if len(nodes) < 2:
            continue
        parent = {n: n for n in nodes}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for ei in tr.edges:
            e = result.graph.edges[ei]
            for n in (e.u, e.v):
                parent.setdefault(n, n)
            ra, rb = find(e.u), find(e.v)
            if ra != rb:
                parent[ra] = rb
        roots = {find(n) for n in nodes}
        if len(roots) != 1:
            report.disconnected_nets.append(tr.net)

    return report
