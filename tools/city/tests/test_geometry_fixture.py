"""Deterministic geometry export checks on a tiny synthetic offline fixture."""
from __future__ import annotations

import hashlib
import json
import sys
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CITY = ROOT / "tools" / "city"
sys.path.insert(0, str(CITY))


def _glb_triangles(path: Path) -> int:
    data = path.read_bytes()
    assert data[:4] == b"glTF"
    json_len = struct.unpack_from("<I", data, 12)[0]
    gltf = json.loads(data[20:20 + json_len].decode("utf-8").rstrip(" "))
    return sum(accessor["count"] for accessor in gltf["accessors"] if accessor.get("type") == "SCALAR") // 3


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fixture_geometry_export_is_byte_deterministic_and_under_budgets(tmp_path):
    from geometry.pipeline import run

    build = tmp_path / "build"
    static = tmp_path / "static"
    (build / "layers").mkdir(parents=True)
    buildings = {
        "schema_version": 1,
        "snapshot": "2026-11-24",
        "buildings": [{
            "id": "way/101",
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [8, 0], [8, 6], [0, 6], [0, 0]]]},
            "height_m": 8,
            "height_source": "osm_levels",
            "levels": 2,
            "type": "shop",
            "roof": "flat",
            "properties": {"shop": "bakery"},
        }],
    }
    roads = {"type": "FeatureCollection", "features": [{
        "type": "Feature", "id": "way/201", "properties": {"osm_id": 201, "highway": "residential"},
        "geometry": {"type": "LineString", "coordinates": [[-8, 0], [12, 0]]},
    }]}
    (build / "buildings.json").write_text(json.dumps(buildings, sort_keys=True), encoding="utf-8")
    (build / "layers/roads.geojson").write_text(json.dumps(roads, sort_keys=True), encoding="utf-8")
    config = {
        "snapshot_date": "2026-11-24",
        "area": {"bbox": [-20, -20, 20, 20], "origin": [0, 0]},
        "shuttle_street": {"position": [0, 0], "rotation_degrees": 0},
        "outputs": {"build_dir": str(build), "static_dir": str(static)},
    }

    first = run(config, fixture=True)
    paths = [static / "assets" / tier / name for tier in ("low", "high")
             for name in ("city.glb", "city-collision.glb")]
    paths.append(static / "data/city.json")
    first_hashes = [_sha256(path) for path in paths]
    first_tris = max(_glb_triangles(path) for path in paths if path.suffix == ".glb")

    second = run(config, fixture=True)
    assert second == first
    assert [_sha256(path) for path in paths] == first_hashes
    low_bytes = sum(path.stat().st_size for path in paths[:2])
    high_bytes = sum(path.stat().st_size for path in paths[2:4])
    assert low_bytes <= 8_000_000
    assert high_bytes <= 12_000_000
    assert first_tris < 150_000
    assert json.loads(paths[-1].read_text(encoding="utf-8"))["snapshot"] == "2026-11-24"
