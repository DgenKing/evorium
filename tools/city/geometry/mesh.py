"""Small deterministic triangle mesh builder and minimal GLB 2.0 writer.

All input geometry is in local metres. The module deliberately contains no
geography: it only turns supplied OSM-derived polygons/lines into triangles.
"""
from __future__ import annotations

import json
import math
import struct
from pathlib import Path
from typing import Iterable, Sequence


class Mesh:
    def __init__(self) -> None:
        self.positions: list[tuple[float, float, float]] = []
        self.groups: dict[str, list[int]] = {}

    def triangle(self, a: Sequence[float], b: Sequence[float], c: Sequence[float], material: str = "default") -> None:
        start = len(self.positions)
        self.positions.extend((tuple(map(float, a)), tuple(map(float, b)), tuple(map(float, c))))
        self.groups.setdefault(material, []).extend((start, start + 1, start + 2))

    def quad(self, a: Sequence[float], b: Sequence[float], c: Sequence[float], d: Sequence[float], material: str = "default") -> None:
        self.triangle(a, b, c, material)
        self.triangle(a, c, d, material)

    def extend(self, other: "Mesh") -> None:
        offset = len(self.positions)
        self.positions.extend(other.positions)
        for material, indices in other.groups.items():
            self.groups.setdefault(material, []).extend(i + offset for i in indices)


def _area(ring: Sequence[Sequence[float]]) -> float:
    return sum(ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1] for i in range(len(ring))) / 2


def triangulate_simple_ring(ring: Sequence[Sequence[float]]) -> list[tuple[int, int, int]]:
    """Ear-clip a simple 2D ring; stable for both winding directions."""
    points = [tuple(map(float, p[:2])) for p in ring]
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    if len(points) < 3:
        return []
    order = list(range(len(points)))
    if _area(points) < 0:
        order.reverse()

    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def inside(p, a, b, c):
        eps = -1e-10
        return cross(a, b, p) >= eps and cross(b, c, p) >= eps and cross(c, a, p) >= eps

    result = []
    while len(order) > 3:
        ear = None
        for at, cur in enumerate(order):
            prev, nxt = order[at - 1], order[(at + 1) % len(order)]
            if cross(points[prev], points[cur], points[nxt]) <= 1e-10:
                continue
            if any(inside(points[k], points[prev], points[cur], points[nxt]) for k in order if k not in (prev, cur, nxt)):
                continue
            ear = at
            result.append((prev, cur, nxt))
            break
        if ear is None:
            raise ValueError("Polygon is not a simple ring or contains a degenerate edge")
        order.pop(ear)
    result.append(tuple(order))
    return result


def extrude_polygon(mesh: Mesh, ring: Sequence[Sequence[float]], height: float, base_y: float = 0.0,
                    wall: str = "stone", roof: str = "roof") -> None:
    """Add an extruded [x,z] footprint, emitting a flat roof and vertical walls."""
    points = [tuple(map(float, p[:2])) for p in ring]
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    if len(points) < 3 or height <= 0:
        return
    top = base_y + float(height)
    for i, (x, z) in enumerate(points):
        nx, nz = points[(i + 1) % len(points)]
        mesh.quad((x, base_y, z), (nx, base_y, nz), (nx, top, nz), (x, top, z), wall)
    for a, b, c in triangulate_simple_ring(points):
        # Convert GIS [x,z] to scene [x,y,z].
        mesh.triangle((points[a][0], top, points[a][1]), (points[b][0], top, points[b][1]),
                      (points[c][0], top, points[c][1]), roof)


def _pack_glb(mesh: Mesh) -> bytes:
    if not mesh.positions:
        mesh.triangle((0, 0, 0), (.001, 0, 0), (0, 0, .001))
    packed_positions = b"".join(struct.pack("<3f", *p) for p in mesh.positions)
    # Three unique vertices per face make normals correct at hard edges.
    normals: list[tuple[float, float, float]] = []
    for i in range(0, len(mesh.positions), 3):
        a, b, c = mesh.positions[i:i + 3]
        u = (b[0]-a[0], b[1]-a[1], b[2]-a[2]); v = (c[0]-a[0], c[1]-a[1], c[2]-a[2])
        n = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        length = math.sqrt(sum(t*t for t in n)) or 1
        normals.extend([tuple(t/length for t in n)] * 3)
    packed_normals = b"".join(struct.pack("<3f", *n) for n in normals)
    # Keep indices local to each material primitive and use one shared index accessor.
    all_indices = list(range(len(mesh.positions)))
    packed_indices = b"".join(struct.pack("<I", i) for i in all_indices)
    blobs = [packed_positions, packed_normals, packed_indices]
    views, offset = [], 0
    for blob, target in zip(blobs, (34962, 34962, 34963)):
        pad = (-offset) % 4
        offset += pad
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(blob), "target": target})
        offset += len(blob)
    binary = bytearray()
    for blob in blobs:
        binary.extend(b"\0" * ((-len(binary)) % 4)); binary.extend(blob)
    mins = [min(p[i] for p in mesh.positions) for i in range(3)]
    maxs = [max(p[i] for p in mesh.positions) for i in range(3)]
    accessors = [
        {"bufferView": 0, "componentType": 5126, "count": len(mesh.positions), "type": "VEC3", "min": mins, "max": maxs},
        {"bufferView": 1, "componentType": 5126, "count": len(normals), "type": "VEC3"},
        {"bufferView": 2, "componentType": 5125, "count": len(all_indices), "type": "SCALAR"},
    ]
    material_names = sorted(mesh.groups)
    colors = {"asphalt": [0.16, 0.17, 0.18, 1], "pavement": [0.46, 0.45, 0.42, 1],
              "kerb": [0.58, 0.56, 0.51, 1],
              "glass": [0.10, 0.18, 0.22, 1], "shopfront": [0.22, 0.23, 0.21, 1],
              "roof": [0.38, 0.36, 0.33, 1], "facade": [0.61, 0.57, 0.51, 1],
              "brick": [0.46, 0.22, 0.17, 1], "stone": [0.65, 0.61, 0.54, 1],
              "concrete": [0.49, 0.51, 0.52, 1],
              "lamp_post": [0.15, 0.17, 0.18, 1], "lamp_head": [0.95, 0.63, 0.28, 1],
              "street_bin": [0.20, 0.31, 0.27, 1], "bench": [0.31, 0.19, 0.12, 1],
              "bench_back": [0.35, 0.22, 0.14, 1], "bollard": [0.74, 0.67, 0.47, 1],
              "tree_trunk": [0.27, 0.17, 0.10, 1], "tree_leaves": [0.13, 0.31, 0.18, 1],
              "road_marking": [0.84, 0.81, 0.70, 1]}
    materials = [{"name": n, "doubleSided": True, "pbrMetallicRoughness": {
        "baseColorFactor": colors.get(n, [0.55, 0.53, 0.49, 1]), "metallicFactor": 0, "roughnessFactor": 0.92}}
        for n in material_names]
    primitives = [{"attributes": {"POSITION": 0, "NORMAL": 1}, "indices": 2, "material": i, "mode": 4} for i, _ in enumerate(material_names)]
    # Mesh is duplicated by material in the common index accessor; each primitive's
    # index list must refer to only its own triangles. Build a compact index buffer.
    index_data = bytearray(); prims = []; cursor = 0
    for mi, name in enumerate(material_names):
        indices = mesh.groups[name]
        start = len(index_data)
        for index in indices:
            index_data.extend(struct.pack("<I", index))
        prims.append({"attributes": {"POSITION": 0, "NORMAL": 1}, "indices": len(accessors), "material": mi, "mode": 4})
        accessors.append({"bufferView": 3, "byteOffset": start, "componentType": 5125, "count": len(indices), "type": "SCALAR"})
        cursor += len(indices)
    # Replace packed full index buffer with per-material indices.
    blobs = [packed_positions, packed_normals, bytes(index_data)]
    views, offset = [], 0
    for blob, target in zip(blobs, (34962, 34962, 34963)):
        offset += (-offset) % 4
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(blob), "target": target})
        offset += len(blob)
    accessors = accessors[:3] + [{"bufferView": 2, "byteOffset": sum(len(mesh.groups[k]) * 4 for k in material_names[:mi]),
                                "componentType": 5125, "count": len(mesh.groups[name]), "type": "SCALAR"}
                               for mi, name in enumerate(material_names)]
    gltf = {"asset": {"version": "2.0", "generator": "Evorium deterministic city builder"},
            "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1}, "indices": 3 + i, "material": i, "mode": 4}
                                        for i, _ in enumerate(material_names)]}],
            "materials": materials, "buffers": [{"byteLength": len(binary) + len(index_data)}],
            "bufferViews": views, "accessors": accessors}
    # Assemble true aligned payload with positions, normals, then grouped indices.
    payload = bytearray(packed_positions); payload.extend(b"\0" * ((-len(payload)) % 4)); payload.extend(packed_normals)
    payload.extend(b"\0" * ((-len(payload)) % 4)); payload.extend(index_data)
    gltf["buffers"][0]["byteLength"] = len(payload)
    js = json.dumps(gltf, sort_keys=True, separators=(",", ":")).encode("utf-8")
    js += b" " * ((-len(js)) % 4)
    payload.extend(b"\0" * ((-len(payload)) % 4))
    total = 12 + 8 + len(js) + 8 + len(payload)
    return struct.pack("<4sII", b"glTF", 2, total) + struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(payload), b"BIN\0") + payload


def write_glb(mesh: Mesh, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(_pack_glb(mesh))
