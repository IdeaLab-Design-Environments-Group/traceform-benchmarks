"""Draw the flat pattern and its routed copper, as SVG and as PNG.

Both come off the same scene list.  Rendering them independently is how the
vector and the raster quietly drift apart, and the PNG exists precisely so a
figure can be assembled without re-deriving anything.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw

from fold.unfold import FlatPattern
from geom import Vec2, bbox2
from layouts import Layout
from routing.router import RouteResult

# Mountain reads warm, valley cool, cut/seam neutral -- the same reading as an
# origami crease pattern, so the picture is legible to anyone who has seen one.
COL_PANEL = "#f6f3ec"
COL_PANEL_EDGE = "#d8d2c4"
COL_MOUNTAIN = "#c0392b"
COL_VALLEY = "#2471a3"
COL_SEAM = "#7f8c8d"
COL_BODY = "#34495e"
COL_PAD = "#f1c40f"
NET_COLOURS = ["#16a085", "#8e44ad", "#d35400", "#2c3e50", "#27ae60",
               "#c0392b", "#2980b9", "#f39c12", "#7f8c8d", "#1abc9c",
               "#9b59b6", "#e74c3c", "#3498db", "#e67e22", "#95a5a6",
               "#00838f", "#6d4c41"]


@dataclass
class Scene:
    polygons: List[Tuple[Sequence[Vec2], str, str, float]] = field(default_factory=list)
    lines: List[Tuple[Vec2, Vec2, str, float, bool]] = field(default_factory=list)
    rects: List[Tuple[Tuple[float, float, float, float], str, str]] = field(
        default_factory=list)
    dots: List[Tuple[Vec2, float, str]] = field(default_factory=list)

    def polygon(self, pts, fill, stroke, width=0.4):
        self.polygons.append((list(pts), fill, stroke, width))

    def line(self, a, b, colour, width=0.5, dashed=False):
        self.lines.append((a, b, colour, width, dashed))

    def rect(self, box, fill, stroke):
        self.rects.append((box, fill, stroke))

    def dot(self, at, r, colour):
        self.dots.append((at, r, colour))


def build_scene(flat: FlatPattern, layout: Layout, result: RouteResult,
                cfg: dict) -> Scene:
    scene = Scene()
    for poly in flat.polygons:
        scene.polygon(poly, COL_PANEL, COL_PANEL_EDGE, 0.3)

    for c in flat.creases:
        scene.line(c.a, c.b, COL_MOUNTAIN if c.theta > 0 else COL_VALLEY, 0.9)
    for s in flat.seams:
        scene.line(s.lip_a[0], s.lip_a[1], COL_SEAM, 0.7)
        scene.line(s.lip_b[0], s.lip_b[1], COL_SEAM, 0.7)

    width = cfg["routing"]["trace_width_mm"]
    for i, tr in enumerate(result.traces):
        colour = NET_COLOURS[i % len(NET_COLOURS)]
        sides = (tr.segment_sides if len(tr.segment_sides) == len(tr.segments)
                 else [0] * len(tr.segments))
        for (a, b), side in zip(tr.segments, sides):
            scene.line(a, b, colour, width, dashed=side == 1)
        for c in tr.crossings:
            if c.kind == "seam":
                scene.dot(c.at, width * 1.4, COL_SEAM)

    for pl in layout.placements:
        scene.rect(pl.rect, "none", COL_BODY)
        for pad in pl.footprint.pads:
            at = (pl.at[0] + pad.at[0], pl.at[1] + pad.at[1])
            scene.dot(at, max(pad.size) / 2.0, COL_PAD)
    return scene


def _frame(flat: FlatPattern, margin: float):
    x0, y0, x1, y1 = bbox2(p for poly in flat.polygons for p in poly)
    return (x0 - margin, y0 - margin, x1 + margin, y1 + margin)


def write_svg(path: str, scene: Scene, flat: FlatPattern, title: str,
              cfg: dict) -> None:
    margin = cfg["render"]["margin_mm"]
    x0, y0, x1, y1 = _frame(flat, margin)
    w, h = x1 - x0, y1 - y0

    def T(p: Vec2) -> Tuple[float, float]:
        # FOLD-style patterns are y-up; SVG is y-down.
        return (p[0] - x0, y1 - p[1])

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.2f}mm" '
           f'height="{h:.2f}mm" viewBox="0 0 {w:.3f} {h:.3f}">',
           f'<title>{title}</title>',
           f'<rect width="{w:.3f}" height="{h:.3f}" fill="#ffffff"/>']

    out.append('<g id="panels">')
    for pts, fill, stroke, sw in scene.polygons:
        d = " ".join(f"{T(p)[0]:.3f},{T(p)[1]:.3f}" for p in pts)
        out.append(f'<polygon points="{d}" fill="{fill}" stroke="{stroke}" '
                   f'stroke-width="{sw:.2f}"/>')
    out.append("</g>")

    out.append('<g id="folds">')
    for a, b, colour, sw, dashed in scene.lines:
        if colour in (COL_MOUNTAIN, COL_VALLEY, COL_SEAM):
            ta, tb = T(a), T(b)
            dash = ' stroke-dasharray="2,1.5"' if colour == COL_SEAM else ""
            out.append(f'<line x1="{ta[0]:.3f}" y1="{ta[1]:.3f}" '
                       f'x2="{tb[0]:.3f}" y2="{tb[1]:.3f}" stroke="{colour}" '
                       f'stroke-width="{sw:.2f}"{dash}/>')
    out.append("</g>")

    out.append('<g id="traces">')
    for a, b, colour, sw, dashed in scene.lines:
        if colour not in (COL_MOUNTAIN, COL_VALLEY, COL_SEAM):
            ta, tb = T(a), T(b)
            out.append(f'<line x1="{ta[0]:.3f}" y1="{ta[1]:.3f}" '
                       f'x2="{tb[0]:.3f}" y2="{tb[1]:.3f}" stroke="{colour}" '
                       f'stroke-width="{sw:.2f}" stroke-linecap="round"/>')
    out.append("</g>")

    out.append('<g id="parts">')
    for (bx0, by0, bx1, by1), fill, stroke in scene.rects:
        p0, p1 = T((bx0, by1)), T((bx1, by0))
        out.append(f'<rect x="{p0[0]:.3f}" y="{p0[1]:.3f}" '
                   f'width="{p1[0]-p0[0]:.3f}" height="{p1[1]-p0[1]:.3f}" '
                   f'fill="none" stroke="{stroke}" stroke-width="0.3"/>')
    for at, r, colour in scene.dots:
        t = T(at)
        out.append(f'<circle cx="{t[0]:.3f}" cy="{t[1]:.3f}" r="{r:.3f}" '
                   f'fill="{colour}"/>')
    out.append("</g></svg>")
    open(path, "w").write("\n".join(out))


def write_png(path: str, scene: Scene, flat: FlatPattern, cfg: dict) -> None:
    margin = cfg["render"]["margin_mm"]
    px_w = cfg["render"]["png_width_px"]
    x0, y0, x1, y1 = _frame(flat, margin)
    w, h = x1 - x0, y1 - y0
    k = px_w / w
    px_h = max(1, int(round(h * k)))

    img = Image.new("RGB", (px_w, px_h), "#ffffff")
    draw = ImageDraw.Draw(img)

    def T(p: Vec2) -> Tuple[float, float]:
        return ((p[0] - x0) * k, (y1 - p[1]) * k)

    for pts, fill, stroke, sw in scene.polygons:
        xy = [T(p) for p in pts]
        draw.polygon(xy, fill=fill, outline=stroke)
    for a, b, colour, sw, dashed in scene.lines:
        draw.line([T(a), T(b)], fill=colour,
                  width=max(1, int(round(sw * k))))
    for (bx0, by0, bx1, by1), fill, stroke in scene.rects:
        p0, p1 = T((bx0, by1)), T((bx1, by0))
        draw.rectangle([p0, p1], outline=stroke, width=max(1, int(round(0.3 * k))))
    for at, r, colour in scene.dots:
        cx, cy = T(at)
        rr = max(1.0, r * k)
        draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=colour)

    img.save(path, "PNG", optimize=True)
