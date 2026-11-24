from __future__ import annotations

import importlib.util
import json
import struct
from pathlib import Path
import pytest

CITY = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("city_export", CITY / "export.py")
EXPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORT)


def write_glb(path: Path, triangle_count=1):
    count = triangle_count * 3
    document = {"asset": {"version": "2.0"}, "accessors": [{"count": count}],
                "meshes": [{"primitives": [{"indices": 0}]}]}
    chunk = json.dumps(document, separators=(",", ":")).encode()
    chunk += b" " * ((-len(chunk)) % 4)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack("<4sII", b"glTF", 2, 20 + len(chunk)) +
                     struct.pack("<I4s", len(chunk), b"JSON") + chunk)


def test_glb_triangle_count_and_measurement(tmp_path):
    low = tmp_path / "low"
    write_glb(low / "city.glb", 12)
    write_glb(low / "city-collision.glb", 20)
    city_json = tmp_path / "city.json"
    city_json.write_text("{}")
    report = EXPORT._measure(low, city_json)
    assert report["triangles"] == 12
    assert report["files"]["city-collision.glb"]["triangles"] == 20


def test_fixture_export_report_does_not_rewrite_base_budget(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(EXPORT, "_optimize", lambda root, path, tier: False)
    static = tmp_path / "static"
    for tier in ("low", "high"):
        write_glb(static / "assets" / tier / "city.glb", 3)
    (static / "data").mkdir(parents=True)
    (static / "data/city.json").write_text("{}")
    original = {tier: {"bytes": 100, "triangles": 50} for tier in ("low", "high")}
    budget_path = static / "data/budgets.json"
    budget_path.write_text(json.dumps(original))
    config = {"outputs": {"static_dir": "static", "build_dir": "build"},
              "lod_budgets_bytes": {"low": 10000, "high": 10000}}
    first = EXPORT.run(config, fixture=True)
    second = EXPORT.run(config, fixture=True)
    assert first["tiers"] == second["tiers"]
    assert json.loads(budget_path.read_text()) == original
    assert json.loads((tmp_path / "build/budgets.json").read_text())["tiers"] == first["tiers"]


def test_over_budget_refuses_to_replace_static_budget(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(EXPORT, "_optimize", lambda root, path, tier: False)
    static = tmp_path / "static"
    for tier in ("low", "high"):
        write_glb(static / "assets" / tier / "city.glb", 4)
    (static / "data").mkdir(parents=True)
    (static / "data/city.json").write_text("{}")
    original = {tier: {"bytes": 100, "triangles": 50} for tier in ("low", "high")}
    budget_path = static / "data/budgets.json"
    budget_path.write_text(json.dumps(original))
    config = {"outputs": {"static_dir": "static", "build_dir": "build"},
              "lod_budgets_bytes": {"low": 10, "high": 10}}
    with pytest.raises(RuntimeError, match="exceeds"):
        EXPORT.run(config, fixture=True)
    assert json.loads(budget_path.read_text()) == original


def test_triangle_cap_refuses_to_replace_static_budget(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(EXPORT, "_optimize", lambda root, path, tier: False)
    static = tmp_path / "static"
    for tier in ("low", "high"):
        write_glb(static / "assets" / tier / "city.glb", 4)
    (static / "data").mkdir(parents=True)
    (static / "data/city.json").write_text("{}")
    original = {tier: {"bytes": 100, "triangles": 50} for tier in ("low", "high")}
    budget_path = static / "data/budgets.json"
    budget_path.write_text(json.dumps(original))
    config = {"outputs": {"static_dir": "static", "build_dir": "build"},
              "lod_budgets_bytes": {"low": 10000, "high": 10000},
              "triangle_budgets": {"low": 3, "high": 10}}
    with pytest.raises(RuntimeError, match="exceeds"):
        EXPORT.run(config, fixture=True)
    assert json.loads(budget_path.read_text()) == original
    report = json.loads((tmp_path / "build/budgets.json").read_text())
    assert report["over_budget"]["triangles"] == {"low": 1}


def test_optimized_instanced_window_keeps_two_triangles(tmp_path):
    import shutil
    import sys
    sys.path.insert(0, str(CITY))
    from facades.generate import _window_template
    from geometry.mesh import Mesh, write_glb

    root = CITY.parents[1]
    if not shutil.which("node") or EXPORT._cli(root) is None:
        pytest.skip("npm ci --prefix tools/web3d is needed for the GLB compression check")
    mesh = Mesh()
    for i in range(23):
        mesh.instance("sash-window-brick", _window_template("sash", "brick"),
                      (i*3.1,0,0), 0, (3.1,3.2,1))
    path = tmp_path / "city.glb"
    write_glb(mesh,path,chunk_size=50)
    assert EXPORT._optimize(root,path,"low")
    output = EXPORT._instance_measurement(path)
    assert output["window_instances"] == 23

    doc = EXPORT._read_gltf(path)
    glass = next(i for i,m in enumerate(doc["materials"]) if m["name"] == "glass")
    pane = next(p for m in doc["meshes"] for p in m["primitives"] if p["material"] == glass)
    data = bytearray(path.read_bytes())
    offset = 20
    json_size = struct.unpack_from("<I", data, 12)[0]
    old = f'"bufferView":{doc["accessors"][pane["indices"]]["bufferView"]},"componentType":5125,"count":6'.encode()
    new = old[:-1] + b"3"
    assert old in data[offset:offset+json_size]
    data[offset:offset+json_size] = data[offset:offset+json_size].replace(old,new,1)
    path.write_bytes(data)
    with pytest.raises(ValueError, match="pane triangles"):
        EXPORT._instance_measurement(path)
