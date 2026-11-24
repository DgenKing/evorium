"""Deterministic facade rules over source building footprints and road lines."""
from __future__ import annotations

import hashlib
import math
from typing import Any

from geometry.mesh import Mesh, extrude_polygon


def _poly_rings(geometry: dict[str, Any]) -> list[list[list[float]]]:
    kind, coords = geometry.get("type"), geometry.get("coordinates", [])
    if kind == "Polygon":
        return [coords[0]] if coords else []
    if kind == "MultiPolygon":
        return [poly[0] for poly in coords if poly]
    if coords and coords[0] and isinstance(coords[0][0], (int, float)):
        return [coords]
    return []


def _road_lines(roads: list[dict[str, Any]] | None) -> list[list[list[float]]]:
    result = []
    for feature in roads or []:
        geometry = feature.get("geometry", {})
        kind, coords = geometry.get("type"), geometry.get("coordinates", [])
        if kind == "LineString":
            result.append(coords)
        elif kind == "MultiLineString":
            result.extend(coords)
    return result


def _stable_fraction(identifier: str) -> float:
    return int(hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF


def _point_segment_distance(p, a, b):
    dx, dz = b[0] - a[0], b[1] - a[1]
    denom = dx * dx + dz * dz
    t = 0 if denom == 0 else max(0.0, min(1.0, ((p[0]-a[0])*dx + (p[1]-a[1])*dz) / denom))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dz))


def _edge_road_distance(edge, road_lines):
    _, a, b, _, _ = edge
    midpoint = ((float(a[0]) + float(b[0])) / 2, (float(a[1]) + float(b[1])) / 2)
    distances = [_point_segment_distance(midpoint, p, q)
                 for line in road_lines for p, q in zip(line, line[1:])]
    return min(distances, default=math.inf)


def _bar(mesh: Mesh, a, b, y, width, depth, material):
    """A slim horizontal sill/lintel strip parallel to a facade edge."""
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    if length <= 0:
        return
    nx, nz = (b[1] - a[1]) / length * depth / 2, -(b[0] - a[0]) / length * depth / 2
    p0 = (a[0], y, a[1]); p1 = (b[0], y, b[1])
    mesh.quad((p0[0] + nx, p0[1], p0[2] + nz), (p1[0] + nx, p1[1], p1[2] + nz),
              (p1[0] - nx, p1[1], p1[2] - nz), (p0[0] - nx, p0[1], p0[2] - nz), material)


def add_facades(mesh: Mesh, building: dict[str, Any], levels: int | None = None,
                roads: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Add type-specific windows, door/shopfront and small source-footprint details.

    The nearest road-facing edge controls the shop entrance. Every placement is
    derived from the OSM footprint, OSM identifier and staged road geometry.
    """
    rings = _poly_rings(building.get("geometry", {}))
    if not rings:
        return {"windows": 0, "details": 0, "door_edge": None}
    ring = rings[0]
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    height = float(building.get("height_m", 8))
    if len(ring) < 3 or height < 2.2:
        return {"windows": 0, "details": 0, "door_edge": None}
    props = building.get("properties", {})
    kind = str(building.get("type", "other"))
    is_shop = kind == "shop" or bool(props.get("shop"))
    override_material = props.get("facade_material")
    facade_material = override_material if override_material in {"brick", "stone", "concrete"} else "facade_detail"
    floors = max(1, min(24, int(levels or building.get("levels") or round(height / 3.2))))
    floor_h = height / floors
    ident = str(building.get("id", props.get("osm_id", "building")))
    phase = _stable_fraction(ident)
    twice_area = sum(a[0]*b[1] - b[0]*a[1] for a, b in zip(ring, ring[1:] + ring[:1]))
    outside = 1 if twice_area > 0 else -1
    edges = []
    for idx, (a, b) in enumerate(zip(ring, ring[1:] + ring[:1])):
        dx, dz = float(b[0]) - float(a[0]), float(b[1]) - float(a[1])
        length = math.hypot(dx, dz)
        if length >= 2.2:
            edges.append((length, a, b, dx, dz, idx))
    if not edges:
        return {"windows": 0, "details": 0, "door_edge": None}
    lines = _road_lines(roads)
    road_distances = [(_edge_road_distance(edge[:5], lines), edge[5]) for edge in edges]
    closest_distance, road_edge = min(road_distances, default=(math.inf, None))
    # A distant road is not evidence for a road-facing door. The 12 m reach also
    # accommodates opposite pavement widths in a narrow urban street.
    door_edge = road_edge if is_shop and closest_distance <= 12.0 else None

    windows = details = 0
    facade_material = "shopfront" if is_shop else "facade_detail"
    for length, a, b, dx, dz, idx in edges:
        ux, uz = dx / length, dz / length
        bays = max(1, min(14, int(length / (2.0 if kind in {"mill_warehouse", "modern_flats"} else 3.0) + phase)))
        for floor in range(floors):
            y0 = float(building.get("base_y", 0)) + floor * floor_h
            pane_height = min(1.8 if kind == "mill_warehouse" else 1.5, floor_h * .56)
            sill_y = y0 + (0.72 if floor == 0 else floor_h * .2)
            pane_y = sill_y + .08
            for bay in range(bays):
                center = (bay + .5) * length / bays
                pane_width = min(1.35 if kind == "mill_warehouse" else 1.05, length / bays * .48)
                start, end = center - pane_width / 2, center + pane_width / 2
                # Keep every decorative pane just off the footprint wall to avoid z-fighting.
                offset_x, offset_z = dz / length * .05 * outside, -dx / length * .05 * outside
                p0 = (float(a[0]) + ux * start + offset_x, pane_y, float(a[1]) + uz * start + offset_z)
                p1 = (float(a[0]) + ux * end + offset_x, pane_y, float(a[1]) + uz * end + offset_z)
                mesh.quad(p0, p1, (p1[0], pane_y + pane_height, p1[2]), (p0[0], pane_y + pane_height, p0[2]), "glass")
                # Stone sill and lintel on masonry types; shopfronts get a strong lintel only.
                if not is_shop:
                    _bar(mesh, (p0[0], p0[2]), (p1[0], p1[2]), pane_y - .055, .07, .05, facade_material)
                    _bar(mesh, (p0[0], p0[2]), (p1[0], p1[2]), pane_y + pane_height + .045, .09, .06, facade_material)
                    details += 2
                elif floor == 0:
                    _bar(mesh, (p0[0], p0[2]), (p1[0], p1[2]), pane_y + pane_height + .045, .1, .07, "shopfront")
                    details += 1
                windows += 1
        if idx == door_edge and is_shop:
            door_width, door_height = min(1.1, length * .2), min(2.15, floor_h * .86)
            center = length * (.68 if phase > .5 else .32)
            start, end = center - door_width / 2, center + door_width / 2
            ox, oz = dz / length * .06 * outside, -dx / length * .06 * outside
            base = float(building.get("base_y", 0))
            p0 = (float(a[0]) + ux * start + ox, base, float(a[1]) + uz * start + oz)
            p1 = (float(a[0]) + ux * end + ox, base, float(a[1]) + uz * end + oz)
            mesh.quad(p0, p1, (p1[0], base + door_height, p1[2]), (p0[0], base + door_height, p0[2]), "shopfront")
            # Door jambs and header make the entrance legible without text or branding.
            _bar(mesh, (p0[0], p0[2]), (p1[0], p1[2]), base + door_height + .035, .08, .08, "shopfront")
            details += 1

    # A modest parapet follows terrace and warehouse roof edges, based only on the footprint.
    if kind in {"terrace", "mill_warehouse"}:
        top = float(building.get("base_y", 0)) + height
        for length, a, b, dx, dz, _ in edges:
            if length < 3:
                continue
            ux, uz = dx / length, dz / length
            offset_x, offset_z = dz / length * .05 * outside, -dx / length * .05 * outside
            p0 = (float(a[0]) + offset_x, top - .12, float(a[1]) + offset_z)
            p1 = (float(b[0]) + offset_x, top - .12, float(b[1]) + offset_z)
            _bar(mesh, (p0[0], p0[2]), (p1[0], p1[2]), p0[1], .16, .12, facade_material)
            details += 1
    # Stable chimney position from footprint centroid for older terraces and mills.
    if kind in {"terrace", "mill_warehouse"} and phase > .22:
        xs, zs = [float(p[0]) for p in ring], [float(p[1]) for p in ring]
        cx, cz = sum(xs) / len(xs), sum(zs) / len(zs)
        radius = .32 if kind == "terrace" else .55
        half = radius / 2
        extrude_polygon(mesh, [[cx-half, cz-half], [cx+half, cz-half], [cx+half, cz+half], [cx-half, cz+half]], .55, float(building.get("base_y", 0)) + height, facade_material, facade_material)
        details += 1
    return {"windows": windows, "details": details, "door_edge": door_edge}
