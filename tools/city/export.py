"""Meshopt-export city GLBs and record package size/triangle measurements."""
from __future__ import annotations

import json
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


def run(config, fixture=False):
    root = Path.cwd()
    static = root / config["outputs"]["static_dir"]
    build = root / config["outputs"]["build_dir"]
    raw = build / "export-source"
    if not fixture and not (raw / "city.json").is_file():
        raise FileNotFoundError("Run geometry and props before exporting the city")
    source_manifest = raw / "city.json" if raw.is_dir() else static / "data/city.json"
    with tempfile.TemporaryDirectory(prefix="export-", dir=build) if raw.is_dir() else tempfile.TemporaryDirectory() as temp:
        return _export(config, fixture, root, static, build, raw, source_manifest, Path(temp))


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
