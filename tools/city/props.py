"""Deterministic street props derived from OSM features and road alignments."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


def _stable_fraction(seed: int, feature_id: str, index: int) -> float:
    raw = f"{seed}:{feature_id}:{index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big") / 2**64


def _lines(geometry: dict[str, Any]):
    kind, coords = geometry.get("type"), geometry.get("coordinates", [])
    if kind == "LineString":
        return [coords]
    if kind == "MultiLineString":
        return coords
    return []


def _features(path: Path):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("features", [])


def generate_props(layers: dict[str, list[dict[str, Any]]], seed: int,
                   bounds: tuple[float, float, float, float] | None = None,
                   exclusion: tuple[tuple[float, float], float] | None = None) -> list[dict[str, Any]]:
    """Create a stable OSM-sourced prop list; procedural lamps follow mapped roads."""
    props: list[dict[str, Any]] = []

    def inside(x: float, z: float) -> bool:
        return bounds is None or (bounds[0] <= x <= bounds[2] and bounds[1] <= z <= bounds[3])

    def add(ident: str, kind: str, x: float, z: float, yaw: float, source: str):
        excluded = exclusion is not None and math.dist((x, z), exclusion[0]) <= exclusion[1]
        if inside(x, z) and not excluded:
            props.append({"id": ident, "type": kind, "position": [round(x, 3), 0.0, round(z, 3)],
                          "yaw": round(yaw, 6), "source": source})

    for layer_name, features in sorted(layers.items()):
        for feature in sorted(features, key=lambda f: str(f.get("id", ""))):
            properties = feature.get("properties", {})
            ident = str(feature.get("id", properties.get("osm_id", "unknown")))
            geometry = feature.get("geometry", {})
            tags = properties
            if geometry.get("type") == "Point":
                coords = geometry.get("coordinates", [])
                if len(coords) < 2:
                    continue
                x, z = float(coords[0]), float(coords[1])
                if tags.get("natural") == "tree" or tags.get("landuse") == "forest":
                    add(f"{ident}:tree", "tree", x, z, 0, "OpenStreetMap tree")
                elif tags.get("amenity") == "bench":
                    add(f"{ident}:bench", "bench", x, z, _stable_fraction(seed, ident, 0) * math.tau,
                        "OpenStreetMap bench")
                elif tags.get("amenity") in {"waste_basket", "waste_disposal"}:
                    add(f"{ident}:bin", "bin", x, z, 0, "OpenStreetMap waste basket")
                elif tags.get("barrier") == "bollard":
                    add(f"{ident}:bollard", "bollard", x, z, 0, "OpenStreetMap bollard")
                elif tags.get("highway") == "street_lamp" or tags.get("man_made") == "street_lamp" or tags.get("amenity") == "street_lamp" or tags.get("lamp"):
                    add(f"{ident}:lamp", "lamp", x, z, 0, "OpenStreetMap street light")
                elif tags.get("highway") == "crossing" or tags.get("crossing"):
                    add(f"{ident}:marking", "road_marking", x, z,
                        _stable_fraction(seed, ident, 0) * math.tau, "OpenStreetMap crossing")
            elif tags.get("amenity") == "bench":
                for line in _lines(geometry):
                    if line:
                        x, z = line[0][:2]
                        add(f"{ident}:bench", "bench", float(x), float(z), 0, "OpenStreetMap bench")

    # Street lamps are placed from mapped road centrelines at fixed intervals. A
    # stable feature hash offsets the first post so adjacent roads do not align.
    for feature in sorted(layers.get("roads", []), key=lambda f: str(f.get("id", ""))):
        properties = feature.get("properties", {})
        ident = str(feature.get("id", properties.get("osm_id", "road")))
        if properties.get("highway") in {"footway", "path", "steps", "cycleway"}:
            continue
        for line in _lines(feature.get("geometry", {})):
            for segment_index, (a, b) in enumerate(zip(line, line[1:])):
                dx, dz = float(b[0]) - float(a[0]), float(b[1]) - float(a[1])
                length = math.hypot(dx, dz)
                if length < 10:
                    continue
                nx, nz = -dz / length, dx / length
                offset = 12.0 + 18.0 * _stable_fraction(seed, ident, segment_index)
                distance = offset
                lamp_index = 0
                while distance < length:
                    t = distance / length
                    side = -1 if _stable_fraction(seed, ident, segment_index * 1000 + lamp_index) < .5 else 1
                    x = float(a[0]) + dx * t + nx * side * 4.0
                    z = float(a[1]) + dz * t + nz * side * 4.0
                    add(f"{ident}:lamp:{segment_index}:{lamp_index}", "lamp", x, z,
                        math.atan2(dx, dz), f"procedural spacing on OSM road {ident}")
                    distance += 36.0
                    lamp_index += 1

    return sorted(props, key=lambda p: p["id"])


def _cylinder(mesh, x, z, radius, height, material, sides=8):
    from geometry.mesh import Mesh
    for i in range(sides):
        a0, a1 = math.tau * i / sides, math.tau * (i + 1) / sides
        p0 = (x + math.cos(a0) * radius, 0, z + math.sin(a0) * radius)
        p1 = (x + math.cos(a1) * radius, 0, z + math.sin(a1) * radius)
        q0, q1 = (p0[0], height, p0[2]), (p1[0], height, p1[2])
        mesh.quad(p0, p1, q1, q0, material)
        mesh.triangle((x, height, z), q0, q1, material)


def _box(mesh, x, z, width, depth, height, material, yaw=0):
    c, s = math.cos(yaw), math.sin(yaw)
    local = [(-width/2,-depth/2),(width/2,-depth/2),(width/2,depth/2),(-width/2,depth/2)]
    base = [(x+a*c-b*s, z+a*s+b*c) for a,b in local]
    top = [(px,height,pz) for px,pz in base]
    bottom = [(px,0,pz) for px,pz in base]
    mesh.quad(top[0],top[1],top[2],top[3],material)
    for i in range(4):
        j=(i+1)%4
        mesh.quad(bottom[i],bottom[j],top[j],top[i],material)


def _tree(mesh, x, z):
    _cylinder(mesh,x,z,.12,1.7,"tree_trunk",6)
    # Low-poly octahedral crown; location and scale come from the OSM tree point.
    top, bottom = (x, 4.5, z), (x, 1.3, z)
    ring=[(x+1.35,2.6,z),(x,2.6,z+1.35),(x-1.35,2.6,z),(x,2.6,z-1.35)]
    for i,p in enumerate(ring):
        q=ring[(i+1)%len(ring)]
        mesh.triangle(top,p,q,"tree_leaves")
        mesh.triangle(bottom,q,p,"tree_leaves")


def _mesh_for_props(props):
    from geometry.mesh import Mesh
    mesh = Mesh()
    for prop in props:
        x, _, z = prop["position"]
        yaw = float(prop["yaw"])
        kind = prop["type"]
        if kind == "lamp":
            _cylinder(mesh,x,z,.055,4.3,"lamp_post",6)
            _box(mesh,x+math.sin(yaw)*.28,z+math.cos(yaw)*.28,.08,.65,.12,"lamp_head",yaw)
        elif kind == "bollard":
            _cylinder(mesh,x,z,.13,.85,"bollard",8)
        elif kind == "bin":
            _box(mesh,x,z,.42,.42,.82,"street_bin",yaw)
        elif kind == "bench":
            _box(mesh,x,z,.9,.35,.48,"bench",yaw)
            _box(mesh,x,z,.9,.08,.95,"bench_back",yaw)
        elif kind == "tree":
            _tree(mesh,x,z)
        elif kind == "road_marking":
            _box(mesh,x,z,1.2,.12,.012,"road_marking",yaw)
    return mesh


def run(config, fixture=False):
    root = Path.cwd()
    build = root / config["outputs"]["build_dir"]
    layers = {p.stem: _features(p) for p in sorted((build / "layers").glob("*.geojson"))}
    bbox = config["area"]["bbox"]
    ox, oz = config["area"]["origin"]
    bounds = (bbox[0]-ox, bbox[1]-oz, bbox[2]-ox, bbox[3]-oz)
    shuttle = config.get("shuttle_street", {})
    shuttle_center = tuple(map(float, shuttle.get("position", [0, 0])))
    replace_radius = float(shuttle.get("replace_radius", 0))
    props = generate_props(layers, int(config.get("seed", 0)), bounds, (shuttle_center, replace_radius))
    if size := shuttle.get("footprint_size"):
        from geometry.pipeline import _inside_rectangle, _to_shuttle_local
        yaw = math.radians(shuttle.get("rotation_degrees", 0))
        props = [p for p in props if not _inside_rectangle(
            _to_shuttle_local(p["position"][::2], shuttle_center, yaw), size)]
    output = build / "props.json"
    output.write_text(json.dumps({"schema_version": 1, "props": props}, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    mesh = _mesh_for_props(props)
    for tier in ("low", "high"):
        from geometry.mesh import write_glb
        destination = root / config["outputs"]["static_dir"] / "assets" / tier / "city-props.glb"
        raw_destination = build / "export-source" / tier / "city-props.glb"
        if props:
            if fixture:
                write_glb(mesh, destination)
            write_glb(mesh, raw_destination)
        else:
            if fixture:
                destination.unlink(missing_ok=True)
            raw_destination.unlink(missing_ok=True)
    manifests = [build / "export-source/city.json"]
    if fixture:
        manifests.append(root / config["outputs"]["static_dir"] / "data/city.json")
    for manifest_path in manifests:
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["props"] = len(props)
            manifest_path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return {"props": len(props), "types": {kind: sum(p["type"] == kind for p in props) for kind in sorted({p["type"] for p in props})}}


if __name__ == "__main__":
    import argparse
    import yaml
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="tools/city/config.yaml")
    args = parser.parse_args()
    print(json.dumps(run(yaml.safe_load(Path(args.config).read_text())), indent=2))
