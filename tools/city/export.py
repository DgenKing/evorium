"""Meshopt-export city GLBs and record package size/triangle measurements."""
from __future__ import annotations

import json
import math
import os
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path


def _read_gltf(path: Path) -> dict:
    data = path.read_bytes()
    if data[:4] != b"glTF" or len(data) < 20:
        raise ValueError(f"Not a GLB 2.0 file: {path}")
    length, kind = struct.unpack_from("<I4s", data, 12)
    if kind != b"JSON":
        raise ValueError(f"GLB has no JSON chunk: {path}")
    return json.loads(data[20:20 + length].decode("utf-8"))


def _triangles(path: Path) -> int:
    gltf = _read_gltf(path)
    accessors = gltf.get("accessors", [])
    total = 0
    for mesh in gltf.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            if "indices" in primitive:
                count = accessors[primitive["indices"]]["count"]
            else:
                count = accessors[primitive["attributes"]["POSITION"]]["count"]
            total += count // 3
    return total


def _instance_measurement(path: Path) -> dict:
    """Count submitted geometry and verify every facade pane is still a quad."""
    gltf = _read_gltf(path)
    accessors = gltf["accessors"]
    materials = gltf.get("materials", [])
    meshes = gltf.get("meshes", [])
    raw = path.read_bytes()
    bin_offset = 28 + struct.unpack_from("<I", raw, 12)[0]
    windows = 0
    triangles = 0
    for node in gltf.get("nodes", []):
        if "mesh" not in node:
            continue
        attrs = node.get("extensions", {}).get("EXT_mesh_gpu_instancing", {}).get("attributes")
        count = accessors[attrs["TRANSLATION"]]["count"] if attrs else 1
        panes = 0
        for primitive in meshes[node["mesh"]]["primitives"]:
            accessor = accessors[primitive["indices"]] if "indices" in primitive else accessors[primitive["attributes"]["POSITION"]]
            triangles += accessor["count"] // 3 * count
            if not attrs or "window" not in node.get("name", ""):
                continue
            if materials[primitive["material"]].get("name") not in {"glass", "M_UpperGlass"}:
                continue
            panes += 1
            view = gltf["bufferViews"][accessor["bufferView"]]
            if accessor["count"] != 6 or view.get("extensions"):
                raise ValueError(f"Expected two intact pane triangles in {node['name']}")
            offset = bin_offset + view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
            indices = struct.unpack_from("<6I", raw, offset)
            a, b = set(indices[:3]), set(indices[3:])
            if len(a) != 3 or len(b) != 3 or len(a | b) != 4 or len(a & b) != 2:
                raise ValueError(f"Window pane is not a quad in {node['name']}")
        if attrs and "window" in node.get("name", ""):
            if panes != 1:
                raise ValueError(f"Missing or duplicate pane in {node['name']}")
            windows += count
    return {"scene_triangles": triangles, "window_instances": windows}


def _cli(root: Path) -> Path | None:
    candidates = (root / "tools/web3d/node_modules/@gltf-transform/cli/bin/cli.js",
                  root / "tools/city/node_modules/@gltf-transform/cli/bin/cli.js")
    return next((path for path in candidates if path.exists()), None)


def _optimize(root: Path, path: Path, tier: str) -> bool:
    cli = _cli(root)
    node = shutil.which("node")
    if cli is None or node is None:
        return False
    with tempfile.NamedTemporaryFile(prefix="evorium-city-", suffix=".glb", dir=path.parent, delete=False) as tmp:
        temporary = Path(tmp.name)
    temporary.unlink()
    try:
        command = [node, str(cli), "optimize", str(path), str(temporary), "--compress", "meshopt",
                   "--meshopt-level", "high", "--simplify", "false", "--weld", "true",
                   "--join", "true", "--join-meshes", "false", "--join-named", "false", "--instance", "false", "--texture-compress", "webp"]
        if path.name in {"city.glb", "city-props.glb"}:
            command = [node, str(root / "tools/web3d/compress-city.mjs"), str(path), str(temporary)]
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
        if result.returncode:
            raise RuntimeError(f"gltf-transform failed for {path.name}: {result.stderr[-1500:]}")
        temporary.replace(path)
        return True
    finally:
        temporary.unlink(missing_ok=True)


def _measure(tier_dir: Path, city_json: Path):
    files = sorted(tier_dir.glob("city*.glb"))
    if not files:
        raise FileNotFoundError(f"No city GLBs in {tier_dir}; run geometry and props first")
    manifest_bytes = city_json.stat().st_size
    return {"bytes": sum(p.stat().st_size for p in files) + manifest_bytes,
            "triangles": sum(_triangles(p) for p in files if "collision" not in p.name),
            "files": {**{p.name: {"bytes": p.stat().st_size, "triangles": _triangles(p)} for p in files},
                      "city.json": {"bytes": manifest_bytes, "triangles": 0}}}


def _map2d_data(build: Path, config: dict):
    """Small deterministic, local-metre overview geometry for the dashboard map."""
    def load(name):
        return json.loads((build / "layers" / f"{name}.geojson").read_text(encoding="utf-8"))
    def point(p):
        return [round(float(p[0]), 1), round(float(p[1]), 1)]
    def simplify(points, tolerance=1.0):
        # Stable radial-distance simplification preserves the recognizable OSM outline.
        kept = []
        for p in points:
            q = point(p)
            if not kept or (q[0]-kept[-1][0])**2+(q[1]-kept[-1][1])**2 >= tolerance*tolerance:
                kept.append(q)
        if len(points) > 2 and kept[-1] != point(points[-1]): kept.append(point(points[-1]))
        return kept
    def rings(feature):
        g=feature.get("geometry",{}); c=g.get("coordinates",[])
        if g.get("type")=="Polygon": return c[:1]
        if g.get("type")=="MultiPolygon": return [poly[0] for poly in c if poly]
        return []
    from geometry.pipeline import _overlaps_shuttle

    shuttle=config.get("shuttle_street",{})
    position=shuttle.get("position",[0,0]);yaw=math.radians(float(shuttle.get("rotation_degrees",0)))
    sx,sz=(float(v) for v in shuttle.get("footprint_size",[35.1,23.4]))
    buildings=[]
    for f in sorted(load("buildings")["features"],key=lambda x:str(x.get("id",""))):
        shape=rings(f)
        if shape:
            props=f.get("properties",{})
            building={"id":str(f.get("id", "")),"type":props.get("building", "yes"),"shape":simplify(shape[0],.6)}
            if _overlaps_shuttle(f, position, yaw, (sx,sz)):
                building["replaced_by_henry"]=True
            buildings.append(building)
    roads=[]
    spaces=[]
    for f in sorted(load("roads")["features"],key=lambda x:str(x.get("id",""))):
        g=f.get("geometry",{}); c=g.get("coordinates",[]); kind=g.get("type")
        lines=[c] if kind=="LineString" else c if kind=="MultiLineString" else []
        props=f.get("properties",{})
        if props.get("place")=="square" and props.get("name"):
            for shape in rings(f):
                spaces.append({"id":str(f.get("id","")),"name":props["name"],"type":"square","shape":simplify(shape)})
        for line in lines:
            if len(line)>1:
                roads.append({"id":str(f.get("id","")),"type":props.get("highway","path"),"name":props.get("name",""),
                              "width":round(float(props.get("width_m", 5 if props.get("highway") not in {"footway","path","steps","cycleway"} else 1.8)),1),"line":simplify(line,1.5)})
    for layer in ("landuse","water"):
        for f in sorted(load(layer)["features"],key=lambda x:str(x.get("id",""))):
            shape=rings(f)
            if not shape: continue
            props=f.get("properties",{}); spaces.append({"id":str(f.get("id","")),"name":props.get("name",""),"type":props.get("leisure",props.get("landuse",props.get("water","open"))),"shape":simplify(shape[0],1.0)})
    trees=[]
    for f in sorted(load("trees")["features"],key=lambda x:str(x.get("id",""))):
        c=f.get("geometry",{}).get("coordinates",[])
        if len(c)>=2 and isinstance(c[0],(int,float)): trees.append(point(c))
    footprint=[]
    for lx,lz in ((-sx/2,-sz/2),(sx/2,-sz/2),(sx/2,sz/2),(-sx/2,sz/2)):
        footprint.append([round(float(position[0])+lx*math.cos(yaw)+lz*math.sin(yaw),1),
                          round(float(position[1])-lx*math.sin(yaw)+lz*math.cos(yaw),1)])
    return {"schema_version":1,"origin":config.get("area",{}).get("origin",[0,0]),
            "bounds":[[round(float(config["area"]["bbox"][0])-float(config["area"]["origin"][0]),1),round(float(config["area"]["bbox"][1])-float(config["area"]["origin"][1]),1)],
                      [round(float(config["area"]["bbox"][2])-float(config["area"]["origin"][0]),1),round(float(config["area"]["bbox"][3])-float(config["area"]["origin"][1]),1)]],
            "buildings":buildings,"roads":roads,"open_spaces":spaces,"trees":trees,
            "henry":{"position":position,"rotation_degrees":shuttle.get("rotation_degrees",0),"size":[sx,sz],"shape":footprint}}


def export_map2d(build: Path, static: Path, config: dict):
    data=_map2d_data(build,config)
    encoded=json.dumps(data,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n"
    if len(encoded.encode("utf-8"))>=150_000: raise ValueError("map2d.json exceeds 150 KB")
    destination=static/"data/map2d.json"; destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(encoded,encoding="utf-8")
    return {"map2d_bytes":len(encoded.encode("utf-8")),"map2d_buildings":len(data["buildings"]),"map2d_roads":len(data["roads"])}


def run(config, fixture=False):
    root = Path.cwd()
    static = root / config["outputs"]["static_dir"]
    build = root / config["outputs"]["build_dir"]
    if os.environ.get("EVORIUM_MAP2D_ONLY") == "1":
        return export_map2d(build, static, config)
    raw = build / "export-source"
    if not fixture and not (raw / "city.json").is_file():
        raise FileNotFoundError("Run geometry and props before exporting the city")
    source_manifest = raw / "city.json" if raw.is_dir() else static / "data/city.json"
    with tempfile.TemporaryDirectory(prefix="export-", dir=build) if raw.is_dir() else tempfile.TemporaryDirectory() as temp:
        result = _export(config, fixture, root, static, build, raw, source_manifest, Path(temp))
    if not fixture and all((build / "layers" / f"{name}.geojson").is_file() for name in ("buildings", "roads", "landuse", "water", "trees")):
        result.update(export_map2d(build, static, config))
    return result


def _export(config, fixture, root, static, build, raw, source_manifest, temp):
    reports = {}
    optimized = {}
    for tier in ("low", "high"):
        directory = temp / tier if raw.is_dir() else static / "assets" / tier
        if raw.is_dir():
            shutil.copytree(raw / tier, directory)
        optimized[tier] = {p.name: _optimize(root, p, tier) for p in sorted(directory.glob("city*.glb"))}
        unoptimized = sorted(name for name, done in optimized[tier].items() if not done)
        if unoptimized and not fixture:
            raise RuntimeError("Meshopt is required for a real city export; run npm ci --prefix tools/web3d. "
                               f"Unoptimized {tier} files: {unoptimized}")
        measurement = reports[tier] = _measure(directory, source_manifest)
        if not fixture:
            measurements = [_instance_measurement(p) for p in sorted(directory.glob("city*.glb"))
                            if "collision" not in p.name]
            measurement.update({key: sum(item[key] for item in measurements)
                                for key in ("scene_triangles", "window_instances")})
    data_dir = static / "data"
    base = json.loads((data_dir / "budgets.json").read_text(encoding="utf-8"))
    summary = {"schema_version": 1, "optimized": optimized, "tiers": reports,
               "limits": {"bytes": config.get("lod_budgets_bytes", {}),
                          "triangles": config.get("triangle_budgets", {})}}
    for tier, measurement in reports.items():
        section = base[tier]
        base_bytes = section.setdefault("cityBaseBytes", section["bytes"])
        base_triangles = section.setdefault("cityBaseTriangles", section["triangles"])
        section["bytes"] = base_bytes + measurement["bytes"]
        section["megabytes"] = round(section["bytes"] / 1_000_000, 6)
        section["triangles"] = base_triangles + measurement["triangles"]
        section["city"] = measurement
        measurement["package_bytes"] = section["bytes"]
        measurement["package_megabytes"] = section["megabytes"]
        measurement["package_triangles"] = base_triangles + measurement.get("scene_triangles", measurement["triangles"])
        limit = config.get("lod_budgets_bytes", {}).get(tier)
        if limit is not None and section["bytes"] > limit:
            summary.setdefault("over_budget", {}).setdefault("bytes", {})[tier] = section["bytes"] - limit
        triangle_limit = config.get("triangle_budgets", {}).get(tier)
        if triangle_limit is not None and measurement["triangles"] > triangle_limit:
            summary.setdefault("over_budget", {}).setdefault("triangles", {})[tier] = measurement["triangles"] - triangle_limit
    build_report = build / "budgets.json"
    build_report.parent.mkdir(parents=True, exist_ok=True)
    build_report.write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if summary.get("over_budget"):
        raise RuntimeError(f"City output exceeds the package download budget: {summary['over_budget']}")
    if raw.is_dir():
        for tier in ("low", "high"):
            directory = static / "assets" / tier
            directory.mkdir(parents=True, exist_ok=True)
            for path in sorted((temp / tier).glob("city*.glb")):
                shutil.copyfile(path, directory / path.name)
            if not (temp / tier / "city-props.glb").exists():
                (directory / "city-props.glb").unlink(missing_ok=True)
        shutil.copyfile(source_manifest, data_dir / "city.json")
    return summary


if __name__ == "__main__":
    import argparse
    import yaml
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="tools/city/config.yaml")
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(yaml.safe_load(Path(args.config).read_text()), args.fixture), indent=2))
