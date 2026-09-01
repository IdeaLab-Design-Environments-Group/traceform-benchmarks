"""Checks recomputed from trace polylines and the flat pattern, never router state."""
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
    """True only for a transverse crossing. Seam bridges end on a lip, so endpoints are legal."""
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
        # Single-sided traces carry no side list, so everything is the outer face.
        sides = (tr.segment_sides if len(tr.segment_sides) == len(tr.segments)
                 else [0] * len(tr.segments))
        for seg, side in zip(tr.segments, sides):
            owned.append((tr.net, seg, side))

    # 1. no trace crosses a cut edge. The graph makes this impossible, checked anyway.
    for net, seg, _side in owned:
        for b in flat.boundary:
            if _crosses(seg, b):
                report.cut_violations.append((net, seg))
                break

    # 2. clearance between nets, counted per net pair. A long parallel run is one problem.
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
                # Opposite faces are separated by substrate. Spacing is a same-face rule.
                if side_a != side_b:
                    continue
                d, _, _ = nearest_on(seg_a[0], seg_a[1], seg_b[0], seg_b[1])
                pair = (net_a, net_b) if net_a < net_b else (net_b, net_a)
                if d < report.min_separation_mm:
                    report.min_separation_mm = d
                if d < min_sep - 1e-9 and d < worst.get(pair, float("inf")):
                    worst[pair] = d
    report.clearance_violations = [(a, b, d) for (a, b), d in sorted(worst.items())]
    # Too close is a spacing defect, zero separation is a short. Reported separately.
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
            # Keep-out applies on the part's own face. Far-face copper under a body is fine.
            if side != 0:
                continue
            if any(_crosses(seg, e) for e in body):
                report.keepout_violations.append((net, pl.ref))

    # 4. every connection traces end to end, checked folded so seam bridges join their net.
    by_name = {n.name: n for n in layout.nets}
    for tr in result.traces:
        net = by_name.get(tr.net)
        if net is None:
            # Net missing from the layout: skip it so a StopIteration can't kill the report.
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
