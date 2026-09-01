"""ASCII STL -> welded, oriented, validated triangle mesh.

The benchmark's three models are closed genus-0 solids.  That is asserted here
rather than assumed, because the unfolding step's guarantees (Euler arithmetic,
seam count, cycle count) all rest on it.
"""
from __future__ import annotations

import hashlib
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from geom import Vec3, cross3, dist3, dot3, sub3, tri_area, tri_normal


class MeshError(RuntimeError):
    """Raised when an input mesh violates an assumption the pipeline needs."""


@dataclass
class TriMesh:
    vertices: List[Vec3]
    faces: List[Tuple[int, int, int]]
    source: str = ""
    sha256: str = ""

    # edge key (a<b) -> list of face indices
    edge_faces: Dict[Tuple[int, int], List[int]] = field(default_factory=dict)

    def normal(self, f: int) -> Vec3:
        a, b, c = self.faces[f]
        return tri_normal(self.vertices[a], self.vertices[b], self.vertices[c])

    def area(self, f: int) -> float:
        a, b, c = self.faces[f]
        return tri_area(self.vertices[a], self.vertices[b], self.vertices[c])

    @property
    def euler(self) -> int:
        return len(self.vertices) - len(self.edge_faces) + len(self.faces)


def _edge_key(a: int, b: int) -> Tuple[int, int]:
    return (a, b) if a < b else (b, a)


def parse_ascii_stl(text: str) -> List[Tuple[Vec3, Vec3, Vec3]]:
    """Parse ASCII STL into raw triangles.  Binary STL is rejected loudly."""
    stripped = text.lstrip()
    if not stripped.startswith("solid") or "facet" not in text[:4096]:
        raise MeshError("not an ASCII STL (binary STL is not supported)")
    tokens = text.split()
    tris: List[Tuple[Vec3, Vec3, Vec3]] = []
    current: List[Vec3] = []
    for i, tok in enumerate(tokens):
        if tok == "vertex":
            current.append(
                (float(tokens[i + 1]), float(tokens[i + 2]), float(tokens[i + 3]))
            )
            if len(current) == 3:
                tris.append((current[0], current[1], current[2]))
                current = []
    if not tris:
        raise MeshError("ASCII STL contained no facets")
    return tris


def weld(tris: Sequence[Tuple[Vec3, Vec3, Vec3]], decimals: int) -> TriMesh:
    """Collapse coincident vertices; STL is triangle soup with no shared indices."""
    index: Dict[Tuple[float, ...], int] = {}
    vertices: List[Vec3] = []
    faces: List[Tuple[int, int, int]] = []
    for tri in tris:
        idx = []
        for p in tri:
            key = tuple(round(c, decimals) for c in p)
            if key not in index:
                index[key] = len(vertices)
                vertices.append(p)
            idx.append(index[key])
        if len(set(idx)) == 3:  # drop degenerates created by welding
            faces.append((idx[0], idx[1], idx[2]))
    return TriMesh(vertices=vertices, faces=faces)


def build_topology(mesh: TriMesh) -> None:
    edge_faces: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for fi, f in enumerate(mesh.faces):
        for k in range(3):
            edge_faces[_edge_key(f[k], f[(k + 1) % 3])].append(fi)
    mesh.edge_faces = dict(edge_faces)


def orient(mesh: TriMesh) -> None:
    """Propagate a consistent winding by BFS, then flip so normals point outward.

    Outwardness is decided by the signed volume of the closed surface: a mesh
    wound outward encloses positive volume.
    """
    adjacency: Dict[int, List[int]] = defaultdict(list)
    for faces in mesh.edge_faces.values():
        if len(faces) == 2:
            adjacency[faces[0]].append(faces[1])
            adjacency[faces[1]].append(faces[0])

    seen = [False] * len(mesh.faces)
    for start in range(len(mesh.faces)):
        if seen[start]:
            continue
        seen[start] = True
        queue = deque([start])
        while queue:
            u = queue.popleft()
            fu = mesh.faces[u]
            directed_u = {(fu[k], fu[(k + 1) % 3]) for k in range(3)}
            for v in adjacency[u]:
                if seen[v]:
                    continue
                seen[v] = True
                fv = mesh.faces[v]
                directed_v = {(fv[k], fv[(k + 1) % 3]) for k in range(3)}
                # Consistent neighbours traverse their shared edge oppositely.
                if directed_u & directed_v:
                    mesh.faces[v] = (fv[0], fv[2], fv[1])
                queue.append(v)

    volume = 0.0
    for f in mesh.faces:
        a, b, c = (mesh.vertices[i] for i in f)
        volume += dot3(a, cross3(b, c)) / 6.0
    if volume < 0.0:
        mesh.faces = [(f[0], f[2], f[1]) for f in mesh.faces]


def validate_closed_genus_zero(mesh: TriMesh) -> None:
    boundary = [k for k, v in mesh.edge_faces.items() if len(v) == 1]
    nonmanifold = [k for k, v in mesh.edge_faces.items() if len(v) > 2]
    if boundary:
        raise MeshError(f"mesh is open: {len(boundary)} boundary edges")
    if nonmanifold:
        raise MeshError(f"mesh is non-manifold: {len(nonmanifold)} edges with >2 faces")

    adjacency: Dict[int, List[int]] = defaultdict(list)
    for faces in mesh.edge_faces.values():
        adjacency[faces[0]].append(faces[1])
        adjacency[faces[1]].append(faces[0])
    seen = set()
    components = 0
    for start in range(len(mesh.faces)):
        if start in seen:
            continue
        components += 1
        seen.add(start)
        stack = [start]
        while stack:
            u = stack.pop()
            for v in adjacency[u]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
    if components != 1:
        raise MeshError(f"mesh has {components} disconnected components, expected 1")
    if mesh.euler != 2:
        raise MeshError(
            f"mesh has Euler characteristic {mesh.euler}, expected 2 (genus 0). "
            "The unfolding guarantees rely on genus 0."
        )


def load_mesh(path: str, weld_decimals: int = 4) -> TriMesh:
    raw = open(path, "rb").read()
    tris = parse_ascii_stl(raw.decode("utf-8", "replace"))
    mesh = weld(tris, weld_decimals)
    mesh.source = path
    mesh.sha256 = hashlib.sha256(raw).hexdigest()
    build_topology(mesh)
    orient(mesh)
    build_topology(mesh)
    validate_closed_genus_zero(mesh)
    return mesh
