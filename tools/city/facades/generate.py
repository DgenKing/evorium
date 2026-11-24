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


def _window_template(kind, wall, *, low=False):
    """Repeat a full bay with masonry, a 12 cm reveal and a protected pane."""
    mesh = Mesh()
    tall = kind == "mill"
    lo, hi, sill, head = -.18, .18, .22, .82 if tall else .74

    def quad(x0, y0, x1, y1, z, material):
        mesh.quad((x0,y0,z),(x1,y0,z),(x1,y1,z),(x0,y1,z),material)

    if low:
        mesh.shade = .93
        quad(-.5,0,.5,1,0,wall or "brick")
        mesh.shade = .77
        quad(lo,sill,hi,head,.026,"glass")
        mesh.shade = .9
        quad(-.021,sill,.021,head,.037,"frame")
        return mesh
    if wall:
        mesh.shade = .86
        quad(-.5,0,.5,sill,0,wall)
        mesh.shade = 1
        for x0,y0,x1,y1 in ((-.5,sill,lo,head),(hi,sill,.5,head),(-.5,head,.5,1)):
            quad(x0,y0,x1,y1,0,wall)
        mesh.shade = .57
        corners = [(lo,sill),(hi,sill),(hi,head),(lo,head)]
        for a,b in zip(corners,corners[1:]+corners[:1]):
            mesh.quad((*a,0),(*b,0),(*b,-.12),(*a,-.12),"reveal")
    mesh.shade = .78
    quad(lo,sill,hi,head,-.12,"glass")
    mesh.shade = .9
    quad(-.016,sill,.016,head,-.105,"frame")
    quad(lo,(sill+head)/2-.017,hi,(sill+head)/2+.017,-.101,"frame")
    quad(lo-.027,sill-.032,hi+.027,sill-.008,.025,"facade_detail")
    if tall:
        # Segmental lintel above the tall, flat-sided mill pane.
        for index in range(3):
            x0, x1 = -.20 + .4*index/3, -.20 + .4*(index+1)/3
            y0, y1 = head+.025+.064*(1-(x0/.2)**2), head+.025+.064*(1-(x1/.2)**2)
            mesh.quad((x0,y0,.015),(x1,y1,.015),(x1,y1+.027,.015),(x0,y0+.027,.015),"facade_detail")
    else:
        quad(lo-.027,head+.012,hi+.027,head+.043,.022,"facade_detail")
    return mesh


def add_facades(mesh: Mesh, building: dict[str, Any], levels: int | None = None,
                roads: list[dict[str, Any]] | None = None, *, wall: str | None = None) -> dict[str, Any]:
    """Build masonry between openings and place shared window modules in the reveals."""
    height = float(building.get("wall_height", building.get("height_m", 8)))
    base = float(building.get("base_y", 0))
    props = building.get("properties", {})
    kind = str(building.get("type", "other"))
    is_shop = kind == "shop" or props.get("building") in {"retail", "commercial"} or bool(props.get("shop"))
    floors = max(1, min(15, int(levels or building.get("levels") or round(height / 3.2))))
    floor_h = height / floors
    lines = _road_lines(roads)
    windows = details = 0
    entrance = None
    pattern = "mill" if kind == "mill_warehouse" else "sash"
    template = _window_template(pattern, wall)
    template.low_detail = _window_template(pattern, wall, low=True)
    template_name = f"{pattern}-window-{wall or 'plain'}"
    for ring in _poly_rings(building.get("geometry", {})):
        if ring[0] == ring[-1]:
            ring = ring[:-1]
        if len(ring) < 3:
            continue
        pairs = list(zip(ring, ring[1:] + ring[:1]))
        outside = 1 if sum(a[0]*b[1] - b[0]*a[1] for a, b in pairs) > 0 else -1
        edges = [(math.dist(a,b), a, b, b[0]-a[0], b[1]-a[1], i)
                 for i,(a,b) in enumerate(pairs) if math.dist(a,b) > .01]
        distances = {e[5]: _edge_road_distance(e[:5], lines) for e in edges if e[0] >= 2.2}
        road_edge = min(distances, key=distances.get, default=None)
        for length, a, b, dx, dz, idx in edges:
            ux, uz = dx/length, dz/length
            nx, nz = outside*uz, -outside*ux
            def p(x, y, offset=0):
                return a[0]+ux*x+nx*offset, base+y, a[1]+uz*x+nz*offset
            def panel(x0, y0, x1, y1, material, offset=0):
                if x1-x0 > .005 and y1-y0 > .005:
                    mesh.quad(p(x0,y0,offset), p(x1,y0,offset), p(x1,y1,offset), p(x0,y1,offset), material)
            decorated = length >= 2.2 and height >= 2.2 and (
                wall is None or distances.get(idx, math.inf) <= 26 or length >= 14)
            has_door = idx == road_edge and distances.get(idx, math.inf) <= 12
            if not decorated:
                if wall: panel(0,0,length,height,wall)
                continue
            bays = max(1, min(12, round(length / (3.2 if pattern == "mill" else 3.1))))
            for floor in range(floors):
                if is_shop and has_door and not floor and wall:
                    panel(0,0,length,floor_h,wall)
                    continue
                for bay in range(bays):
                    center = (bay+.5)*length/bays
                    mesh.instance(template_name, template, p(center,floor*floor_h,0 if wall else .16),
                                  math.atan2(nx,nz),(length/bays,floor_h,1))
                    windows += 1
                    details += 2
            if has_door and (wall or is_shop):
                center = length/2
                if is_shop:
                    panel(.16, .3, length-.16, min(2.45, floor_h*.79), "shopfront", .105)
                    for step in (1,2,3):
                        x = length*step/4
                        panel(x-.035,.3,x+.035,min(2.45, floor_h*.79),"frame",.125)
                    panel(.16,min(2.45, floor_h*.79),length-.16,min(2.76,floor_h*.96),"frame",.12)
                panel(center-.48,0,center+.48,min(2.16,floor_h*.8),
                      "shopfront" if is_shop else "frame",.14)
                entrance = idx
            if kind in {"terrace", "mill_warehouse", "modern_flats"}:
                panel(0,height-.11,length,height+.035,"facade_detail",.03)
                if kind in {"mill_warehouse","modern_flats"}:
                    panel(0,height,length,height+.45,wall or "brick")
                    panel(0,height+.37,length,height+.46,"facade_detail",.065)
                details += 1
        if kind in {"terrace","mill_warehouse"} and _stable_fraction(str(building["id"])) > .22:
            cx = sum(float(p[0]) for p in ring)/len(ring)
            cz = sum(float(p[1]) for p in ring)/len(ring)
            r = .33
            extrude_polygon(mesh, [[cx-r,cz-r],[cx+r,cz-r],[cx+r,cz+r],[cx-r,cz+r]], .8,
                            base+float(building.get("height_m",height))-.2,wall or "brick","facade_detail")
            details += 1
    return {"windows": windows, "details": details, "door_edge": entrance}
