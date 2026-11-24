"""Create deterministic city meshes and walkable triangles from staged GeoJSON."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .mesh import Mesh, extrude_polygon, write_glb


def _poly_rings(geometry: dict[str, Any]):
    kind = geometry.get("type")
    coords = geometry.get("coordinates", [])
    if kind == "Polygon":
        return [coords[0]] if coords else []
    if kind == "MultiPolygon":
        return [p[0] for p in coords if p]
    # buildings.json also permits the concise raw [x,z] ring form.
    if coords and isinstance(coords[0][0], (int, float)):
        return [coords]
    return []


def _lines(geometry: dict[str, Any]):
    kind, coords = geometry.get("type"), geometry.get("coordinates", [])
    if kind == "LineString":
        return [coords]
    if kind == "MultiLineString":
        return coords
    return []


def _road_width(props: dict[str, Any]) -> float:
    width = props.get("width_m")
    if width is not None:
        return max(3.0, min(18.0, float(width)))
    kind = str(props.get("highway", props.get("road_type", "residential")))
    return 7.0 if kind in {"primary", "secondary", "tertiary", "trunk"} else 5.0


def _road_mesh(features: list[dict[str, Any]], exclude_center: tuple[float, float] | None = None,
               exclude_radius: float = 0.0) -> tuple[Mesh, dict[str, Any], list[dict[str, Any]]]:
    mesh, nav_vertices, nav_polygons, roads = Mesh(), [], [], []
    def add_strip(a, b, half_width, material, walkable=False):
        dx, dz = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dz)
        if length <= 1e-5:
            return
        px, pz = -dz / length * half_width, dx / length * half_width
        corners = [(a[0] + px, a[1] + pz), (b[0] + px, b[1] + pz),
                   (b[0] - px, b[1] - pz), (a[0] - px, a[1] - pz)]
        mesh.quad((corners[0][0], 0, corners[0][1]), (corners[1][0], 0, corners[1][1]),
                  (corners[2][0], 0, corners[2][1]), (corners[3][0], 0, corners[3][1]), material)
        if walkable:
            i = len(nav_vertices)
            nav_vertices.extend([[x, 0, z] for x, z in corners])
            nav_polygons.extend([[i, i + 1, i + 2], [i, i + 2, i + 3]])
    for feature in sorted(features, key=lambda f: str(f.get("id", f.get("properties", {}).get("osm_id", "")))):
        props = feature.get("properties", {})
        ident = str(feature.get("id", props.get("osm_id", "road")))
        width = _road_width(props)
        for line in _lines(feature.get("geometry", {})):
            for a, b in zip(line, line[1:]):
                length = math.hypot(b[0] - a[0], b[1] - a[1])
                pieces = max(1, math.ceil(length / 1.25))
                for part in range(pieces):
                    t0, t1 = part / pieces, (part + 1) / pieces
                    p0 = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
                    p1 = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
                    if exclude_center is not None and exclude_radius > 0 and _point_segment_distance(exclude_center, p0, p1) <= exclude_radius:
                        continue
                    # Roads are also walkable so a route graph can cross mapped streets
                    # instead of trapping characters on one pavement side.
                    add_strip(p0, p1, width / 2, "asphalt", True)
                    sidewalk = 1.6
                    offset = width / 2 + sidewalk / 2
                    dx, dz = p1[0] - p0[0], p1[1] - p0[1]
                    plen = math.hypot(dx, dz)
                    if not plen:
                        continue
                    nx, nz = -dz / plen, dx / plen
                    for sign in (-1, 1):
                        # Raised kerb, derived along the OSM road edge.
                        inner_p = (p0[0] + nx * (width / 2) * sign, p0[1] + nz * (width / 2) * sign)
                        inner_q = (p1[0] + nx * (width / 2) * sign, p1[1] + nz * (width / 2) * sign)
                        outer_p = (inner_p[0] + nx * .16 * sign, inner_p[1] + nz * .16 * sign)
                        outer_q = (inner_q[0] + nx * .16 * sign, inner_q[1] + nz * .16 * sign)
                        mesh.quad((inner_p[0], .14, inner_p[1]), (inner_q[0], .14, inner_q[1]),
                                  (outer_q[0], .14, outer_q[1]), (outer_p[0], .14, outer_p[1]), "kerb")
                        mesh.quad((outer_p[0], 0, outer_p[1]), (outer_q[0], 0, outer_q[1]),
                                  (outer_q[0], .14, outer_q[1]), (outer_p[0], .14, outer_p[1]), "kerb")
                        p = (p0[0] + nx * offset * sign, p0[1] + nz * offset * sign)
                        q = (p1[0] + nx * offset * sign, p1[1] + nz * offset * sign)
                        add_strip(p, q, sidewalk / 2, "pavement", True)
                    roads.append({"id": ident, "start": list(p0), "end": list(p1), "width_m": width})
    edge_polys: dict[tuple[tuple[float, float, float], tuple[float, float, float]], list[int]] = {}
    for pi, polygon in enumerate(nav_polygons):
        for j, idx in enumerate(polygon):
            p = tuple(round(v, 3) for v in nav_vertices[idx])
            q = tuple(round(v, 3) for v in nav_vertices[polygon[(j + 1) % len(polygon)]])
            edge_polys.setdefault(tuple(sorted((p, q))), []).append(pi)
    portals, graph_edges = [], []
    for edge, owners in sorted(edge_polys.items()):
        for j, first in enumerate(owners):
            for second in owners[j + 1:]:
                if first == second:
                    continue
                ca = [sum(nav_vertices[i][d] for i in nav_polygons[first]) / 3 for d in range(3)]
                cb = [sum(nav_vertices[i][d] for i in nav_polygons[second]) / 3 for d in range(3)]
                portals.append({"a": first, "b": second, "from": ca, "to": cb,
                                "midpoint": [(edge[0][d] + edge[1][d]) / 2 for d in range(3)],
                                "cost": round(math.dist(ca, cb), 4)})
                graph_edges.append([f"t{first}", f"t{second}"])
    centers = {f"t{i}": [sum(nav_vertices[j][d] for j in poly) / 3 for d in range(3)]
               for i, poly in enumerate(nav_polygons)}
    # OSM ways often meet geometrically at junctions without sharing vertex ids.
    # Join nearby surface-triangle centers to bridge those source-way seams.
    cell_size = 4.0
    buckets: dict[tuple[int, int], list[str]] = {}
    for name, point in sorted(centers.items()):
        cell = (math.floor(point[0] / cell_size), math.floor(point[2] / cell_size))
        for cx in range(cell[0] - 1, cell[0] + 2):
            for cz in range(cell[1] - 1, cell[1] + 2):
                for other in buckets.get((cx, cz), []):
                    if math.dist(point, centers[other]) <= cell_size:
                        graph_edges.append([name, other])
        buckets.setdefault(cell, []).append(name)
    graph_edges = sorted({tuple(sorted(edge)) for edge in graph_edges})
    nav = {"schema_version": 1, "vertices": nav_vertices, "polygons": nav_polygons,
           "portals": portals, "graph": {"nodes": centers, "edges": [list(edge) for edge in graph_edges]}}
    return mesh, nav, roads


def _load_buildings(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    return sorted(data.get("buildings", []), key=lambda b: str(b.get("id", "")))


def _feature_collection(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("features", [])


def _point_in_ring(point: tuple[float, float], ring: list) -> bool:
    x, z = point
    inside = False
    for a, b in zip(ring, ring[1:] + ring[:1]):
        ax, az, bx, bz = float(a[0]), float(a[1]), float(b[0]), float(b[1])
        if (az > z) != (bz > z) and x < (bx - ax) * (z - az) / ((bz - az) or 1e-30) + ax:
            inside = not inside
    return inside


def _point_segment_distance(point: tuple[float, float], a: list, b: list) -> float:
    x, z = point
    ax, az, bx, bz = float(a[0]), float(a[1]), float(b[0]), float(b[1])
    dx, dz = bx - ax, bz - az
    denom = dx * dx + dz * dz
    t = 0 if not denom else max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / denom))
    return math.hypot(x - (ax + t * dx), z - (az + t * dz))


def _overlaps_shuttle(building: dict[str, Any], center: tuple[float, float], radius: float) -> bool:
    """Return true when any supplied footprint overlaps the configured circular cutout."""
    if radius <= 0:
        return False
    for ring in _poly_rings(building.get("geometry", {})):
        pts = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
        if not pts:
            continue
        if _point_in_ring(center, pts) or any(math.dist(center, (float(p[0]), float(p[1]))) <= radius for p in pts):
            return True
        if any(_point_segment_distance(center, a, b) <= radius for a, b in zip(pts, pts[1:] + pts[:1])):
            return True
    return False


def run(config: dict[str, Any] | None = None, fixture: bool = False) -> dict[str, Any]:
    """Run geometry stage. Paths are resolved from repo root or config's build_dir.

    Accepts the normalized mapping returned by PyYAML; when omitted, reads the
    project's config.yaml. Outputs remain in tools/city/build and static city assets.
    """
    from facades.generate import add_facades
    root = Path.cwd()
    if config is None:
        import yaml
        config = yaml.safe_load((root / "tools/city/config.yaml").read_text())
    build_dir = root / config.get("outputs", {}).get("build_dir", "tools/city/build")
    static_dir = root / config.get("outputs", {}).get("static_dir", "evorium/static/world3d")
    buildings_path = build_dir / "buildings.json"
    roads_path = build_dir / "layers/roads.geojson"
    if fixture and not buildings_path.exists():
        raise FileNotFoundError("fixture build requires tools/city/build/buildings.json")
    all_buildings = _load_buildings(buildings_path)
    shuttle = config.get("shuttle_street", {})
    shuttle_center = tuple(shuttle.get("position", [0.0, 0.0]))
    replace_radius = float(shuttle.get("replace_radius", 0.0))
    buildings = [b for b in all_buildings if not _overlaps_shuttle(b, shuttle_center, replace_radius)]
    removed_buildings = len(all_buildings) - len(buildings)
    road_features = _feature_collection(roads_path)
    city_mesh = Mesh()
    for building in buildings:
        geometry = building.get("geometry", {})
        height = float(building.get("height_m", 8.0))
        base = float(building.get("base_y", 0.0))
        for ring in _poly_rings(geometry):
            extrude_polygon(city_mesh, ring, height, base, "facade", "roof")
        add_facades(city_mesh, building, building.get("levels"), road_features)
    road_mesh, navmesh, roads = _road_mesh(road_features, shuttle_center, replace_radius)
    city_mesh.extend(road_mesh)
    bounds = config.get("area", {}).get("bbox", [0, 0, 0, 0])
    origin = config.get("area", {}).get("origin", [0, 0])
    min_x, min_z = float(bounds[0]) - float(origin[0]), float(bounds[1]) - float(origin[1])
    max_x, max_z = float(bounds[2]) - float(origin[0]), float(bounds[3]) - float(origin[1])
    ground_y = float(config.get("area", {}).get("ground_y", -0.1))
    ground = Mesh()
    # Keep the fallback terrain just under the road/building base plane. Detailed
    # roads and building bases remain visible at y=0; this prevents ground z-fighting
    # over finished floors and leaves the surface available across gaps.
    ground.quad((min_x, ground_y, min_z), (max_x, ground_y, min_z),
                (max_x, ground_y, max_z), (min_x, ground_y, max_z), "ground")
    city_mesh.extend(ground)
    collision_mesh = Mesh()
    # Collision is intentionally lightweight and flat-sided; it excludes cosmetic props.
    for building in buildings:
        for ring in _poly_rings(building.get("geometry", {})):
            extrude_polygon(collision_mesh, ring, float(building.get("height_m", 8.0)),
                            float(building.get("base_y", 0.0)), "collision", "collision")
    collision_mesh.extend(road_mesh)
    collision_mesh.extend(ground)
    attribution = "© OpenStreetMap contributors; Environment Agency, Open Government Licence"
    manifest = {
        "schema_version": 1,
        "snapshot": config.get("snapshot_date", "unknown"),
        "origin_epsg": "EPSG:27700",
        "origin": config.get("area", {}).get("origin", [0, 0]),
        "bounds": {"min": [min_x, min_z], "max": [max_x, max_z]},
        "attribution": [attribution],
        "buildings": len(buildings),
        "roads": len(road_features),
        "props": 0,
        "navmesh": navmesh,
        "shuttle_street": {"position": shuttle.get("position", [0, 0]),
                           "rotation_degrees": shuttle.get("rotation_degrees", 0)},
    }
    for tier in ("low", "high"):
        asset_dir = static_dir / "assets" / tier
        write_glb(city_mesh, asset_dir / "city.glb")
        write_glb(collision_mesh, asset_dir / "city-collision.glb")
    static_dir.joinpath("data").mkdir(parents=True, exist_ok=True)
    (static_dir / "data/city.json").write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")
    return {"buildings": len(buildings), "removed_overlap": removed_buildings,
            "roads": len(road_features), "nav_polygons": len(navmesh["polygons"]),
            "ground_bounds": {"min": [min_x, min_z], "max": [max_x, max_z], "y": ground_y},
            "manifest": manifest}
