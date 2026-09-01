"""Three component placements per model: a control, the main result, and an adversary.

Placement never reads mountain/valley. Mesh, creases and seams are fixed per model.
"""
from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

from footprints import Footprint
from fold.unfold import FlatPattern
from geom import Vec2, bbox2, dist2, point_in_polygon, polygon_area

# id -> (footprint file stem, label). The Schottky uses the 1206 resistor land pattern
# since FabLib has no 1206 diode and the pads match.
PARTS = {
    "xiao": ("Module_XIAO_Generic_SocketSMD", "Xiao socket"),
    "usb": ("Conn_USB_A_Plain", "USB connector"),
    "led": ("LED_1206", "LED 1206"),
    "res": ("R_1206", "Resistor 1206"),
    "cap": ("C_1206", "Capacitor 1206"),
    "diode": ("R_1206", "Schottky diode 1206"),
    "sw": ("Switch_Slide_Top_CnK_JS102011JCQN_8.5x3.5mm", "Slide switch"),
    "hdr2": ("PinSocket_01x02_P2.54mm_Vertical_SMD", "Header 1x02"),
    "hdr4": ("PinSocket_01x04_P2.54mm_Vertical_SMD", "Header 1x04"),
}


@dataclass
class Placement:
    ref: str
    part: str
    footprint: Footprint
    panel: int
    at: Vec2
    rect: Tuple[float, float, float, float]     # keep-out in sheet mm

    def pad_at(self, name: str) -> Vec2:
        for p in self.footprint.pads:
            if p.name == name:
                return (self.at[0] + p.at[0], self.at[1] + p.at[1])
        raise KeyError(f"{self.ref}: no pad {name}")


@dataclass
class Net:
    name: str
    points: List[Tuple[str, str]]               # (ref, pad name)


@dataclass
class Layout:
    layout_id: str
    placements: List[Placement]
    nets: List[Net]

    @property
    def component_count(self) -> int:
        return len(self.placements)

    @property
    def net_count(self) -> int:
        return len(self.nets)

    @property
    def terminal_count(self) -> int:
        return sum(len(n.points) for n in self.nets)

    def by_ref(self, ref: str) -> Placement:
        for p in self.placements:
            if p.ref == ref:
                return p
        raise KeyError(ref)


class PlacementError(RuntimeError):
    pass


# panel graph
def panel_graph(flat: FlatPattern) -> Dict[int, List[int]]:
    adj: Dict[int, Set[int]] = defaultdict(set)
    for c in flat.creases:
        adj[c.panel_a].add(c.panel_b)
        adj[c.panel_b].add(c.panel_a)
    for s in flat.seams:
        adj[s.panel_a].add(s.panel_b)
        adj[s.panel_b].add(s.panel_a)
    return {k: sorted(v) for k, v in adj.items()}


def _bfs(adj: Dict[int, List[int]], start: int, n: int) -> List[int]:
    dist = [-1] * n
    dist[start] = 0
    q = deque([start])
    while q:
        u = q.popleft()
        for v in adj.get(u, ()):
            if dist[v] < 0:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist


def _boundary_panels(flat: FlatPattern) -> List[int]:
    """Panels with a seam lip, where a connector can reach the outside once folded."""
    out: Set[int] = set()
    for s in flat.seams:
        out.add(s.panel_a)
        out.add(s.panel_b)
    return sorted(out)


# placement
def _fits(poly: Sequence[Vec2], rect: Tuple[float, float, float, float]) -> bool:
    x0, y0, x1, y1 = rect
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for c in corners:
        if not point_in_polygon(c, poly):
            return False
    # No panel edge may cross the body: a rigid part on a crease would crack or delaminate.
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if x0 <= a[0] <= x1 and y0 <= a[1] <= y1:
            return False
        for j in range(4):
            p, q = corners[j], corners[(j + 1) % 4]
            from geom import nearest_on
            d, t, u = nearest_on(p, q, a, b)
            if d < 1e-9 and 1e-6 < t < 1 - 1e-6 and 1e-6 < u < 1 - 1e-6:
                return False
    return True


def _place_on_panel(flat: FlatPattern, panel: int, fp: Footprint,
                    taken: List[Tuple[float, float, float, float]],
                    margin: float, pack: bool,
                    step: float = 1.5) -> Optional[Tuple[Vec2, tuple]]:
    poly = flat.polygons[panel]
    px0, py0, px1, py1 = bbox2(poly)
    bx0, by0, bx1, by1 = fp.body
    w, h = bx1 - bx0, by1 - by0
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)

    candidates: List[Tuple[float, Vec2]] = []
    x = px0
    while x <= px1:
        y = py0
        while y <= py1:
            # `pack` crowds parts into a corner (layout C), else they gather at the panel centre.
            key = (x + y) if pack else math.hypot(x - cx, y - cy)
            candidates.append((key, (x, y)))
            y += step
        x += step
    candidates.sort(key=lambda t: (round(t[0], 6), t[1]))

    for _, (x, y) in candidates:
        rect = (x + bx0 - margin, y + by0 - margin,
                x + bx1 + margin, y + by1 + margin)
        if not _fits(poly, rect):
            continue
        clash = False
        for t in taken:
            if not (rect[2] < t[0] or t[2] < rect[0]
                    or rect[3] < t[1] or t[3] < rect[1]):
                clash = True
                break
        if clash:
            continue
        return (x, y), rect
    return None


# layouts: ref -> (part id, panel slot), slot indexes the panel list each layout picks.
# Pinned to slots: first-fit puts the whole circuit on one panel and all methods tie.
_SPEC = {
    # A: supply on the hub, load on a neighbour panel. One short crossing, no alternative.
    "A": [("U1", "xiao", 0), ("J1", "usb", 0), ("D1", "diode", 0),
          ("C1", "cap", 0), ("R1", "res", 1), ("LED1", "led", 1)],
    # B: supply at one end of the panel-graph diameter, three loads at the far end.
    # Every load net must cross, and a cyclic panel graph gives it more than one way.
    "B": [("U1", "xiao", 0), ("J1", "usb", 0), ("D1", "diode", 0),
          ("C1", "cap", 0), ("R1", "res", 1), ("LED1", "led", 1),
          ("R2", "res", 2), ("LED2", "led", 2), ("J2", "hdr2", 3)],
    # C: one part per panel across the smallest panels that will seat one.
    "C": [("U1", "xiao", 0), ("J1", "usb", 1), ("D1", "diode", 2),
          ("C1", "cap", 3), ("R1", "res", 4), ("LED1", "led", 5),
          ("R2", "res", 6), ("LED2", "led", 7), ("R3", "res", 8),
          ("LED3", "led", 9), ("J2", "hdr2", 10), ("J3", "hdr4", 11),
          ("SW1", "sw", 12)],
}


def _nets_for(layout_id: str) -> List[Net]:
    """Power in at the USB connector, regulator on the Xiao socket.
    No battery: a coin-cell holder is a big rigid body that must stay off creases."""
    nets = [
        Net("VBUS", [("J1", "1"), ("D1", "1")]),
        Net("V5", [("D1", "2"), ("U1", "12"), ("C1", "1")]),
        Net("USB_DM", [("J1", "2"), ("U1", "10")]),
        Net("USB_DP", [("J1", "3"), ("U1", "11")]),
        Net("DRV1", [("U1", "1"), ("R1", "1")]),
        Net("LEDA1", [("R1", "2"), ("LED1", "1")]),
    ]
    gnd = [("J1", "4"), ("U1", "13"), ("C1", "2"), ("LED1", "2")]
    if layout_id in ("B", "C"):
        nets += [
            Net("DRV2", [("U1", "2"), ("R2", "1")]),
            Net("LEDA2", [("R2", "2"), ("LED2", "1")]),
            Net("IO1", [("U1", "3"), ("J2", "1")]),
        ]
        gnd += [("LED2", "2"), ("J2", "2")]
    if layout_id == "C":
        nets += [
            Net("DRV3", [("U1", "4"), ("R3", "1")]),
            Net("LEDA3", [("R3", "2"), ("LED3", "1")]),
            Net("IO2", [("U1", "5"), ("J3", "1")]),
            Net("IO3", [("U1", "6"), ("J3", "2")]),
            Net("IO4", [("U1", "7"), ("J3", "3")]),
            Net("SWSIG", [("U1", "8"), ("SW1", "2")]),
            Net("SWPU", [("SW1", "1"), ("U1", "9")]),
        ]
        gnd += [("LED3", "2"), ("J3", "4"), ("SW1", "3")]
    nets.append(Net("GND", gnd))
    return nets


def _slot_panels(flat: FlatPattern, layout_id: str, adj, areas, boundary):
    """Return (slots, fallback): slot panels and a fallback ranking, by distance and area only.

    A part too big for its slot walks the fallback. Fine meshes rarely fit a 21mm socket.
    """
    n = len(flat.polygons)
    if layout_id == "A":
        hub = max(range(n), key=lambda i: (areas[i], -i))
        neighbours = sorted(adj.get(hub, []), key=lambda i: (-areas[i], i))
        if not neighbours:
            raise PlacementError("layout A: hub panel has no neighbour")
        slots = [hub, neighbours[0]]
        rest = sorted((i for i in range(n) if i not in slots),
                      key=lambda i: (-areas[i], i))
        return slots, slots + rest

    if layout_id == "B":
        best = (-1, 0, 0)
        for s0 in range(n):
            d = _bfs(adj, s0, n)
            far = max(range(n), key=lambda i: (d[i], -i))
            if d[far] > best[0]:
                best = (d[far], s0, far)
        _, hub, _far = best
        d = _bfs(adj, hub, n)
        ranked = sorted((i for i in range(n) if i != hub),
                        key=lambda i: (-d[i], -areas[i], i))
        return [hub] + ranked[:3], [hub] + ranked

    if layout_id == "C":
        # Smallest panels first, so the parts crowd and their nets interleave.
        order = sorted(range(n), key=lambda i: (areas[i], i))
        return order, order

    raise ValueError(layout_id)


def build_layout(flat: FlatPattern, layout_id: str, library: Dict[str, Footprint],
                 cfg: dict) -> Layout:
    adj = panel_graph(flat)
    n = len(flat.polygons)
    areas = [abs(polygon_area(p)) for p in flat.polygons]
    margin = cfg["routing"]["clearance_mm"]
    boundary = set(_boundary_panels(flat))
    slots, fallback = _slot_panels(flat, layout_id, adj, areas, boundary)
    pack = layout_id == "C"

    placements: List[Placement] = []
    taken_by_panel: Dict[int, List[tuple]] = defaultdict(list)
    for ref, part, slot in _SPEC[layout_id]:
        stem, _label = PARTS[part]
        fp = library[stem]
        # Slot's own panel first, then the fallback order, so oversized parts still get seated.
        home = slots[slot % len(slots)]
        order = [home] + [p for p in fallback if p != home]
        if ref == "J1":
            # The USB must reach the sheet edge to plug in, so pin it to a panel with a cut edge.
            edged = [p for p in order if p in boundary]
            order = edged + [p for p in order if p not in edged]
        seated = None
        for panel in order:
            got = _place_on_panel(flat, panel, fp, taken_by_panel[panel],
                                  margin, pack)
            if got is not None:
                at, rect = got
                seated = Placement(ref=ref, part=part, footprint=fp,
                                   panel=panel, at=at, rect=rect)
                taken_by_panel[panel].append(rect)
                break
        if seated is None:
            raise PlacementError(
                f"layout {layout_id}: no panel could seat {ref} ({stem}, "
                f"{fp.body_size[0]:.1f}x{fp.body_size[1]:.1f}mm) clear of every crease"
            )
        placements.append(seated)

    return Layout(layout_id=layout_id, placements=placements,
                  nets=_nets_for(layout_id))
