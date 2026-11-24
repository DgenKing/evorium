import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "tools" / "city"))

from geometry.mesh import Mesh, extrude_polygon, write_glb
from geometry.pipeline import run
from navmesh import validate as validate_navmesh


def test_extrusion_and_glb_are_deterministic(tmp_path):
    mesh = Mesh()
    # Concave L-shaped footprint catches caps that assume every footprint is a box.
    extrude_polygon(mesh, [[0, 0], [4, 0], [4, 1], [1, 1], [1, 3], [0, 3]], 6)
    first, second = tmp_path / "one.glb", tmp_path / "two.glb"
    write_glb(mesh, first)
    write_glb(mesh, second)
    assert first.read_bytes() == second.read_bytes()
    data = first.read_bytes()
    magic, version, total = struct.unpack_from("<4sII", data)
    assert (magic, version, total) == (b"glTF", 2, len(data))
    json_length, json_type = struct.unpack_from("<I4s", data, 12)
    assert json_type == b"JSON"
    doc = json.loads(data[20:20 + json_length])
    assert doc["asset"]["version"] == "2.0"
    assert len(doc["meshes"][0]["primitives"]) == 2
    assert doc["buffers"][0]["byteLength"] > 0


def test_bad_degenerate_ring_is_ignored():
    mesh = Mesh()
    extrude_polygon(mesh, [[0, 0], [1, 1]], 5)
    assert mesh.positions == []


def test_fixture_pipeline_writes_city_assets_and_nav_graph(tmp_path):
    build = tmp_path / "build"
    (build / "layers").mkdir(parents=True)
    (build / "buildings.json").write_text(json.dumps({"schema_version": 1, "buildings": [
        {"id": "way/42", "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [8, 0], [8, 6], [0, 6], [0, 0]]]},
         "height_m": 9.6, "height_source": "levels", "levels": 3, "type": "shop", "properties": {"shop": "yes"}},
        {"id": "way/43", "geometry": {"type": "Polygon", "coordinates": [[[10, 10], [14, 10], [14, 14], [10, 14], [10, 10]]]},
         "height_m": 6.4, "height_source": "levels", "levels": 2, "type": "terrace", "properties": {}}
    ]}))
    (build / "layers/roads.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"id": "way/7", "properties": {"highway": "residential"}, "geometry": {"type": "LineString", "coordinates": [[-12, 0], [12, 0]]}}
    ]}))
    static = tmp_path / "static"
    config = {"outputs": {"build_dir": str(build), "static_dir": str(static)},
              "area": {"bbox": [100, 200, 140, 230], "origin": [120, 215]},
              "snapshot_date": "fixture", "shuttle_street": {"position": [0, 0], "rotation_degrees": 90,
                                                                    "replace_radius": 3}}
    result = run(config, fixture=True)
    city = json.loads((static / "data/city.json").read_text())
    assert result["buildings"] == city["buildings"] == 1
    assert result["removed_overlap"] == 1
    assert city["roads"] == 1
    assert city["shuttle_street"]["rotation_degrees"] == 90
    assert city["bounds"] == {"min": [-20, -15], "max": [20, 15]}
    assert city["navmesh"]["graph"]["edges"]
    validate_navmesh(city["navmesh"])
    assert (static / "assets/low/city.glb").is_file()
    assert (static / "assets/high/city-collision.glb").is_file()
    city_glb = (static / "assets/high/city.glb").read_bytes()
    json_length = struct.unpack_from("<I", city_glb, 12)[0]
    gltf = json.loads(city_glb[20:20 + json_length])
    assert gltf["accessors"][0]["min"][1] == -0.1
    assert {material["name"] for material in gltf["materials"]} >= {"asphalt", "pavement", "kerb", "ground"}
