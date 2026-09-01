"""Merge coplanar triangles into polygonal panels and sign every panel edge."""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from fold.load import MeshError, TriMesh
from geom import Vec3, dist3, signed_dihedral, sub3, tri_area


@dataclass
class Panel:
    index: int
    tris: List[int]
    loop: List[int]          # ordered vertex indices, consistent with winding
    normal: Vec3
    area: float


@dataclass
class PanelEdge:
    index: int
    v0: int
    v1: int
    panel_a: int
    panel_b: int
    theta: float             # signed dihedral in radians, mountain positive
    length: float

    @property
    def assignment(self) -> str:
        if self.theta > 0:
            return "M"
        if self.theta < 0:
            return "V"
        return "F"


@dataclass
class PanelMesh:
    mesh: TriMesh
    panels: List[Panel]
    edges: List[PanelEdge]
    panel_edges: Dict[int, List[int]]   # panel index -> edge indices

    @property
    def cycle_count(self) -> int:
        """Independent cycles in the panel adjacency graph (connected)."""
        return len(self.edges) - len(self.panels) + 1


class _DisjointSet:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def _dihedral_of_edge(mesh: TriMesh, key: Tuple[int, int]) -> float:
    """Signed dihedral, mountain positive, on an outward-oriented mesh.

    Edge direction comes from the first face's winding. The (a<b) key would make the sign
    depend on vertex numbering. tests/test_fold.py pins the cube for this.
    """
    f1, f2 = mesh.edge_faces[key]
    a, b = key
    face = mesh.faces[f1]
    directed = {(face[k], face[(k + 1) % 3]) for k in range(3)}
    if (a, b) in directed:
        edge_dir = sub3(mesh.vertices[b], mesh.vertices[a])
    else:
        edge_dir = sub3(mesh.vertices[a], mesh.vertices[b])
    return signed_dihedral(mesh.normal(f1), mesh.normal(f2), edge_dir)


def _order_loop(directed: Sequence[Tuple[int, int]]) -> List[int]:
    """Chain directed boundary edges into a single closed vertex loop."""
    nxt = {}
    for a, b in directed:
        if a in nxt:
            raise MeshError("panel boundary is not a simple loop (vertex repeats)")
        nxt[a] = b
    start = directed[0][0]
    loop = [start]
    cur = nxt[start]
    while cur != start:
        loop.append(cur)
        if cur not in nxt:
            raise MeshError("panel boundary loop is open")
        cur = nxt[cur]
        if len(loop) > len(directed):
            raise MeshError("panel boundary loop did not close")
    if len(loop) != len(directed):
        raise MeshError(
            f"panel boundary has {len(directed)} edges but the loop closed "
            f"after {len(loop)} -- panel is multiply connected"
        )
    return loop


def planarise(mesh: TriMesh, flat_eps_deg: float,
              planarity_rel: float = 1e-4) -> PanelMesh:
    """Merge coplanar triangles into panels and sign every surviving edge.

    planarity_rel is relative to the mesh bbox diagonal since models range from unit scale to 120mm.
    """
    flat_eps = math.radians(flat_eps_deg)
    xs = [v[0] for v in mesh.vertices]
    ys = [v[1] for v in mesh.vertices]
    zs = [v[2] for v in mesh.vertices]
    extent = math.sqrt((max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2
                       + (max(zs) - min(zs)) ** 2)
    planarity_tol = planarity_rel * extent

    # 1. Union triangles across near-flat edges.
    dsu = _DisjointSet(len(mesh.faces))
    theta_of: Dict[Tuple[int, int], float] = {}
    for key, faces in mesh.edge_faces.items():
        theta = _dihedral_of_edge(mesh, key)
        theta_of[key] = theta
        if abs(theta) < flat_eps:
            dsu.union(faces[0], faces[1])

    groups: Dict[int, List[int]] = defaultdict(list)
    for fi in range(len(mesh.faces)):
        groups[dsu.find(fi)].append(fi)

    panel_of_face: Dict[int, int] = {}
    panels: List[Panel] = []
    for pi, root in enumerate(sorted(groups)):
        tris = sorted(groups[root])
        for fi in tris:
            panel_of_face[fi] = pi

        directed: List[Tuple[int, int]] = []
        owned = set()
        for fi in tris:
            f = mesh.faces[fi]
            for k in range(3):
                owned.add((f[k], f[(k + 1) % 3]))
        for a, b in sorted(owned):
            if (b, a) not in owned:
                directed.append((a, b))

        loop = _order_loop(directed)
        area = sum(mesh.area(fi) for fi in tris)
        normal = mesh.normal(tris[0])

        # Planarity audit: chained near-flat merges can build a non-planar panel.
        origin = mesh.vertices[loop[0]]
        for vi in loop:
            d = sub3(mesh.vertices[vi], origin)
            off = abs(d[0] * normal[0] + d[1] * normal[1] + d[2] * normal[2])
            if off > planarity_tol:
                raise MeshError(
                    f"panel {pi} is not planar: vertex {vi} lies {off:.6f} off "
                    f"its plane (tolerance {planarity_tol:.6f}). Lower "
                    f"mesh.flat_eps_deg so curved regions are not merged."
                )

        panels.append(
            Panel(index=pi, tris=tris, loop=loop, normal=normal, area=area)
        )

    # 2. Every non-flat edge becomes a panel edge.
    edges: List[PanelEdge] = []
    panel_edges: Dict[int, List[int]] = defaultdict(list)
    for key in sorted(mesh.edge_faces):
        f1, f2 = mesh.edge_faces[key]
        pa, pb = panel_of_face[f1], panel_of_face[f2]
        if pa == pb:
            continue  # interior to a panel: merged away
        a, b = key
        ei = len(edges)
        edges.append(
            PanelEdge(
                index=ei,
                v0=a,
                v1=b,
                panel_a=min(pa, pb),
                panel_b=max(pa, pb),
                theta=theta_of[key],
                length=dist3(mesh.vertices[a], mesh.vertices[b]),
            )
        )
        panel_edges[pa].append(ei)
        panel_edges[pb].append(ei)

    return PanelMesh(
        mesh=mesh, panels=panels, edges=edges, panel_edges=dict(panel_edges)
    )
