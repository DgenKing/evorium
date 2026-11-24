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


def _cli(root: Path) -> Path | None:
    candidates = (root / "tools/web3d/node_modules/@gltf-transform/cli/bin/cli.js",
                  root / "tools/city/node_modules/@gltf-transform/cli/bin/cli.js")
    return next((path for path in candidates if path.exists()), None)


def _optimize(root: Path, path: Path, tier: str) -> bool:
    cli = _cli(root)
    node = shutil.which("node")
    if cli is None or node is None:
        return False
    ratio = "0.58" if tier == "low" else "0.88"
    with tempfile.NamedTemporaryFile(prefix="evorium-city-", suffix=".glb", dir=path.parent, delete=False) as tmp:
        temporary = Path(tmp.name)
    temporary.unlink()
    try:
        command = [node, str(cli), "optimize", str(path), str(temporary), "--compress", "meshopt",
                   "--meshopt-level", "high", "--simplify", "false", "--weld", "true",
                   "--texture-compress", "webp"]
        if "collision" not in path.name:
            command[command.index("--simplify") + 1] = "true"
            command.extend(("--simplify-ratio", ratio))
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
        if result.returncode:
            raise RuntimeError(f"gltf-transform failed for {path.name}: {result.stderr[-1500:]}")
        temporary.replace(path)
        return True
    finally:
        temporary.unlink(missing_ok=True)


def _measure(tier_dir: Path):
    files = sorted(tier_dir.glob("city*.glb"))
    if not files:
        raise FileNotFoundError(f"No city GLBs in {tier_dir}; run geometry and props first")
    return {"bytes": sum(p.stat().st_size for p in files),
            "triangles": sum(_triangles(p) for p in files if "collision" not in p.name),
            "files": {p.name: {"bytes": p.stat().st_size, "triangles": _triangles(p)} for p in files}}


def run(config, fixture=False):
    root = Path.cwd()
    static = root / config["outputs"]["static_dir"]
    reports = {}
    optimized = {}
    for tier in ("low", "high"):
        directory = static / "assets" / tier
        optimized[tier] = {p.name: _optimize(root, p, tier) for p in sorted(directory.glob("city*.glb"))}
        unoptimized = sorted(name for name, done in optimized[tier].items() if not done)
        if unoptimized and not fixture:
            raise RuntimeError("Meshopt is required for a real city export; run npm ci --prefix tools/web3d. "
                               f"Unoptimized {tier} files: {unoptimized}")
        reports[tier] = _measure(directory)
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
        measurement["package_triangles"] = section["triangles"]
        limit = config.get("lod_budgets_bytes", {}).get(tier)
        if limit is not None and section["bytes"] > limit:
            summary.setdefault("over_budget", {}).setdefault("bytes", {})[tier] = section["bytes"] - limit
        triangle_limit = config.get("triangle_budgets", {}).get(tier)
        if triangle_limit is not None and measurement["triangles"] > triangle_limit:
            summary.setdefault("over_budget", {}).setdefault("triangles", {})[tier] = measurement["triangles"] - triangle_limit
    build_report = root / config["outputs"]["build_dir"] / "budgets.json"
    build_report.parent.mkdir(parents=True, exist_ok=True)
    build_report.write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if summary.get("over_budget"):
        raise RuntimeError(f"City output exceeds the package download budget: {summary['over_budget']}")
    if not fixture:
        (data_dir / "budgets.json").write_text(json.dumps(base, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    import argparse
    import yaml
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="tools/city/config.yaml")
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(yaml.safe_load(Path(args.config).read_text()), args.fixture), indent=2))
