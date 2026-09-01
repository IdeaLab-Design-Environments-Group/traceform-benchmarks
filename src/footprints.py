"""KiCad .kicad_mod -> pad positions and a body keep-out.

Pad coordinates are parsed from the vendored FabLib rather than typed by hand,
so the component geometry in this benchmark is the same geometry a fabricator
would get.  KiCad is millimetres with y growing downward; y is negated on read
so a pad above the body has positive y, matching the flat-pattern convention
used everywhere else here.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from geom import Vec2


@dataclass
class Pad:
    name: str
    at: Vec2
    size: Vec2


@dataclass
class Footprint:
    id: str
    pads: List[Pad]
    body: Tuple[float, float, float, float]   # x0, y0, x1, y1 keep-out, mm

    @property
    def terminal_count(self) -> int:
        return len(self.pads)

    @property
    def body_size(self) -> Vec2:
        return (self.body[2] - self.body[0], self.body[3] - self.body[1])


def _tokenize(text: str) -> list:
    """Parse the s-expression into nested lists."""
    tokens = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', text)
    stack: List[list] = [[]]
    for tok in tokens:
        if tok == "(":
            new: list = []
            stack[-1].append(new)
            stack.append(new)
        elif tok == ")":
            stack.pop()
        elif tok.startswith('"'):
            stack[-1].append(tok[1:-1])
        else:
            stack[-1].append(tok)
    return stack[0][0]


def _find_all(node, head: str):
    if isinstance(node, list):
        if node and node[0] == head:
            yield node
        for child in node:
            yield from _find_all(child, head)


def _num(x) -> float:
    return float(x)


def parse_footprint(path: str) -> Footprint:
    tree = _tokenize(open(path).read())
    fid = os.path.splitext(os.path.basename(path))[0]

    pads: List[Pad] = []
    for node in _find_all(tree, "pad"):
        name = str(node[1])
        at = next(_find_all(node, "at"), None)
        size = next(_find_all(node, "size"), None)
        layers = next(_find_all(node, "layers"), None)
        if at is None or size is None:
            continue
        # A terminal carries copper and has a real name; a bare mounting peg
        # named "" or "_N" is not something a net can connect to.
        if layers is not None:
            names = [str(x) for x in layers[1:]]
            if not any("Cu" in n or n == "*" for n in names):
                continue
        if name in ("", '""') or name.startswith("_"):
            continue
        pads.append(
            Pad(name=name,
                at=(_num(at[1]), -_num(at[2])),
                size=(_num(size[1]), _num(size[2]))))

    if not pads:
        raise ValueError(f"{fid}: no copper pads found")

    # Body keep-out: the courtyard if the footprint declares one, else the pad
    # extent with a small margin.
    xs: List[float] = []
    ys: List[float] = []
    for head in ("fp_line", "fp_rect", "fp_poly"):
        for node in _find_all(tree, head):
            layer = next(_find_all(node, "layer"), None)
            if layer is None or "CrtYd" not in str(layer[1]):
                continue
            for key in ("start", "end", "center", "xy"):
                for pt in _find_all(node, key):
                    xs.append(_num(pt[1]))
                    ys.append(-_num(pt[2]))
    if not xs:
        margin = 0.25
        xs = [p.at[0] + s for p in pads for s in (-p.size[0] / 2 - margin,
                                                  p.size[0] / 2 + margin)]
        ys = [p.at[1] + s for p in pads for s in (-p.size[1] / 2 - margin,
                                                  p.size[1] / 2 + margin)]
    return Footprint(id=fid, pads=sorted(pads, key=lambda p: p.name),
                     body=(min(xs), min(ys), max(xs), max(ys)))


def load_library(directory: str) -> Dict[str, Footprint]:
    out: Dict[str, Footprint] = {}
    for fn in sorted(os.listdir(directory)):
        if fn.endswith(".kicad_mod"):
            fp = parse_footprint(os.path.join(directory, fn))
            out[fp.id] = fp
    return out
