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
    report = EXPORT._measure(low)
    assert report["triangles"] == 12
    assert report["files"]["city-collision.glb"]["triangles"] == 20


def test_fixture_export_report_does_not_rewrite_base_budget(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(EXPORT, "_optimize", lambda root, path, tier: False)
    static = tmp_path / "static"
    for tier in ("low", "high"):
        write_glb(static / "assets" / tier / "city.glb", 3)
    (static / "data").mkdir(parents=True)
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
