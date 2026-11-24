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
        self.shades: list[float] = []
        self.shade = 1.0
        self.instances = {}

    def instance(self, name, prototype, translation, yaw, scale):
        group = self.instances.setdefault(name, (prototype, []))
        group[1].append((translation, yaw, scale))

    def triangle(self, a: Sequence[float], b: Sequence[float], c: Sequence[float], material: str = "default", *, shades=None) -> None:
        start = len(self.positions)
        self.positions.extend((tuple(map(float, a)), tuple(map(float, b)), tuple(map(float, c))))
        self.groups.setdefault(material, []).extend((start, start + 1, start + 2))
        self.shades.extend(shades if shades is not None else [self.shade] * 3)

    def quad(self, a: Sequence[float], b: Sequence[float], c: Sequence[float], d: Sequence[float], material: str = "default", *, shades=None) -> None:
        self.triangle(a, b, c, material, shades=shades[:3] if shades is not None else None)
        self.triangle(a, c, d, material, shades=(shades[0],shades[2],shades[3]) if shades is not None else None)

    def extend(self, other: "Mesh") -> None:
        offset = len(self.positions)
        self.positions.extend(other.positions)
        self.shades.extend(other.shades)
        for name, (prototype, instances) in other.instances.items():
            self.instances.setdefault(name, (prototype, []))[1].extend(instances)
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


def _split_mesh(mesh: Mesh, cell_size: float) -> list[Mesh]:
    """Partition triangles into spatial cells so the renderer can frustum-cull them."""
    cells: dict[tuple[int, int], Mesh] = {}
    for material in sorted(mesh.groups):
        indices = mesh.groups[material]
        for i in range(0, len(indices), 3):
            points = [mesh.positions[indices[j]] for j in range(i, i + 3)]
            x = sum(point[0] for point in points) / 3
            z = sum(point[2] for point in points) / 3
            key = (math.floor(x / cell_size), math.floor(z / cell_size))
            cell = cells.setdefault(key, Mesh())
            cell.triangle(*points, material, shades=[mesh.shades[k] for k in indices[i:i+3]])
    return [cells[key] for key in sorted(cells)]


def _pack_glb(mesh: Mesh, chunk_size: float | None = None, tier: str | None = None) -> bytes:
    from .finish import BINDINGS, FINISH_COLORS, surface_uv, texture_materials
    meshes = _split_mesh(mesh, chunk_size) if chunk_size else [mesh]
    meshes = [m for m in meshes if m.positions]
    if not meshes:
        empty = Mesh(); empty.triangle((0, 0, 0), (.001, 0, 0), (0, 0, .001)); meshes = [empty]
    prototypes = {name: (getattr(item[0], "low_detail", item[0]) if tier == "low" else item[0])
                  for name, item in sorted(mesh.instances.items())}
    material_names = sorted({name for m in [*meshes, *prototypes.values()] for name in m.groups})
    colors = {"asphalt": [0.16, 0.17, 0.18, 1], "pavement": [0.46, 0.45, 0.42, 1],
              "kerb": [0.58, 0.56, 0.51, 1], "glass": [0.10, 0.18, 0.22, 1],
              "shopfront": [0.22, 0.23, 0.21, 1], "roof": [0.38, 0.36, 0.33, 1],
              "facade": [0.61, 0.57, 0.51, 1], "brick": [0.46, 0.22, 0.17, 1],
              "stone": [0.65, 0.61, 0.54, 1], "concrete": [0.49, 0.51, 0.52, 1],
              "lamp_post": [0.15, 0.17, 0.18, 1], "lamp_head": [0.95, 0.63, 0.28, 1],
              "street_bin": [0.20, 0.31, 0.27, 1], "bench": [0.31, 0.19, 0.12, 1],
              "bench_back": [0.35, 0.22, 0.14, 1], "bollard": [0.74, 0.67, 0.47, 1],
              "tree_trunk": [0.27, 0.17, 0.10, 1], "tree_leaves": [0.13, 0.31, 0.18, 1],
              "road_marking": [0.84, 0.81, 0.70, 1]}
    colors.update(FINISH_COLORS)
    materials = [{"name": n, "doubleSided": True, "pbrMetallicRoughness": {
        "baseColorFactor": colors.get(n, [0.55, 0.53, 0.49, 1]), "metallicFactor": 0, "roughnessFactor": 0.92}}
        for n in material_names]
    payload = bytearray(); views = []; accessors = []; gltf_meshes = []; nodes = []

    def append_blob(data: bytes, target: int | None) -> int:
        payload.extend(b"\0" * ((-len(payload)) % 4))
        index = len(views)
        views.append({"buffer": 0, "byteOffset": len(payload), "byteLength": len(data)})
        if target is not None:
            views[-1]["target"] = target
        payload.extend(data)
        return index

    for mesh_index, item in enumerate([*meshes, *prototypes.values()]):
        positions = item.positions
        normals = []
        for i in range(0, len(positions), 3):
            a, b, c = positions[i:i + 3]
            u = (b[0]-a[0], b[1]-a[1], b[2]-a[2]); v = (c[0]-a[0], c[1]-a[1], c[2]-a[2])
            n = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
            length = math.sqrt(sum(t*t for t in n)) or 1
            normals.extend([tuple(t/length for t in n)] * 3)
        uv = [(0.0, 0.0)] * len(positions)
        if tier:
            for material_name, indices in item.groups.items():
                tile_size = BINDINGS.get(material_name, ("", 1))[1]
                for i in indices:
                    point = positions[i]
                    if mesh_index >= len(meshes) and material_name in {"brick", "mill_brick", "stone", "plaster", "facade_detail"}:
                        point = (point[0]*3.1, point[1]*3.2, point[2])
                    uv[i] = surface_uv(point, normals[i], tile_size)
        vertices, remap, unique = [], [], {}
        for pos, normal, tex, shade in zip(positions, normals, uv, item.shades):
            key = (tuple(round(x,4) for x in pos), tuple(round(x,3) for x in normal),
                   tuple(round(x,4) for x in tex), round(shade*255))
            index = unique.get(key)
            if index is None:
                index = len(vertices)
                unique[key] = index
                vertices.append(key)
            remap.append(index)
        positions, normals, uv, shades = zip(*vertices)
        pos_view = append_blob(b"".join(struct.pack("<3f", *v) for v in positions), 34962)
        if tier:
            normal_view = append_blob(b"".join(struct.pack("<4b", *(round(v*127) for v in n),0) for n in normals), 34962)
            views[normal_view]["byteStride"] = 4
        else:
            normal_view = append_blob(b"".join(struct.pack("<3f", *v) for v in normals), 34962)
        pos_accessor = len(accessors)
        accessors.append({"bufferView": pos_view, "componentType": 5126, "count": len(positions), "type": "VEC3",
                          "min": [min(v[i] for v in positions) for i in range(3)],
                          "max": [max(v[i] for v in positions) for i in range(3)]})
        normal_accessor = len(accessors)
        accessors.append({"bufferView": normal_view, "componentType": 5126, "count": len(normals), "type": "VEC3"})
        if tier:
            accessors[-1].update(componentType=5120, normalized=True)
            uv_accessor = len(accessors)
            accessors.append({"bufferView": append_blob(b"".join(struct.pack("<2f", *v) for v in uv), 34962),
                              "componentType": 5126, "count": len(uv), "type": "VEC2"})
            color_accessor = len(accessors)
            if min(shades) < 255:
                colors8 = b"".join(bytes((v,v,v,255)) for v in shades)
                accessors.append({"bufferView": append_blob(colors8, 34962), "componentType": 5121,
                                  "normalized": True, "count": len(positions), "type": "VEC4"})
        primitives = []
        for material_index, name in enumerate(material_names):
            indices = item.groups.get(name)
            if not indices: continue
            index_view = append_blob(b"".join(struct.pack("<I", remap[v]) for v in indices), 34963)
            index_accessor = len(accessors)
            accessors.append({"bufferView": index_view, "componentType": 5125, "count": len(indices), "type": "SCALAR"})
            attributes = {"POSITION": pos_accessor, "NORMAL": normal_accessor}
            if tier:
                attributes.update(TEXCOORD_0=uv_accessor)
                if min(shades) < 255:
                    attributes["COLOR_0"] = color_accessor
            primitives.append({"attributes": attributes,
                               "indices": index_accessor, "material": material_index, "mode": 4})
        gltf_meshes.append({"primitives": primitives})
        if mesh_index < len(meshes):
            nodes.append({"name": f"city-cell-{mesh_index:03d}", "mesh": mesh_index})
    for index, (name, (_, instances)) in enumerate(sorted(mesh.instances.items())):
        cells = {}
        for translation, yaw, scale in instances:
            step = 30 if tier == "low" else 55
            key = math.floor(translation[0] / step), math.floor(translation[2] / step)
            cells.setdefault(key, []).append((translation, yaw, scale))
        for key, values in sorted(cells.items()):
            attributes = {}
            columns = (
                ("TRANSLATION", [v[0] for v in values], "VEC3", "<3f"),
                ("ROTATION", [(0, math.sin(v[1]/2), 0, math.cos(v[1]/2)) for v in values], "VEC4", "<4f"),
                ("SCALE", [v[2] for v in values], "VEC3", "<3f"),
            )
            for semantic, vectors, kind, fmt in columns:
                attributes[semantic] = len(accessors)
                view = append_blob(b"".join(struct.pack(fmt, *v) for v in vectors), 34962)
                accessors.append({"bufferView": view, "componentType": 5126,
                                  "count": len(values), "type": kind})
            nodes.append({"name": f"{name}-{key[0]}-{key[1]}", "mesh": len(meshes) + index,
                          "extensions": {"EXT_mesh_gpu_instancing": {"attributes": attributes}}})
    images, textures = texture_materials(materials, append_blob, tier) if tier else ([], [])
    extensions = []
    if tier:
        extensions.append("KHR_mesh_quantization")
    if images:
        extensions.append("EXT_texture_webp")
    if prototypes:
        extensions.append("EXT_mesh_gpu_instancing")
    gltf = {"asset": {"version": "2.0", "generator": "Evorium deterministic city builder"},
            "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}], "nodes": nodes,
            "meshes": gltf_meshes, "materials": materials,
            "buffers": [{"byteLength": len(payload)}], "bufferViews": views, "accessors": accessors}
    if extensions:
        gltf.update(extensionsUsed=extensions, extensionsRequired=extensions)
    if images:
        gltf.update(images=images, textures=textures)
    js = json.dumps(gltf, sort_keys=True, separators=(",", ":")).encode("utf-8")
    js += b" " * ((-len(js)) % 4)
    payload.extend(b"\0" * ((-len(payload)) % 4))
    total = 12 + 8 + len(js) + 8 + len(payload)
    return struct.pack("<4sII", b"glTF", 2, total) + struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(payload), b"BIN\0") + payload


def write_glb(mesh: Mesh, path: str | Path, *, chunk_size: float | None = None, tier: str | None = None) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(_pack_glb(mesh, chunk_size, tier))
