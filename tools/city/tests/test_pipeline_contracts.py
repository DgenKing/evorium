"""Offline tests for contracts and deterministic preprocessing (no API/network calls)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import jsonschema
from referencing import Registry, Resource
import yaml

ROOT = Path(__file__).resolve().parents[3]
CITY = ROOT / "tools" / "city"
FIXTURE = CITY / "tests" / "fixtures" / "buildings.geojson"


def load_module(name):
    path = CITY / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"city_{name}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def validate(data, schema_name):
    schema_path = CITY / "schema" / schema_name
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    store = {}
    for path in (CITY / "schema").glob("*.schema.json"):
        candidate = json.loads(path.read_text(encoding="utf-8"))
        if "$id" in candidate:
            store[candidate["$id"]] = candidate
    registry = Registry().with_resources(
        (uri, Resource.from_contents(candidate)) for uri, candidate in store.items()
    )
    jsonschema.Draft202012Validator(schema, registry=registry).validate(data)


def test_contract_schemas_are_parseable_and_config_fits_area_budget():
    config = yaml.safe_load((CITY / "config.yaml").read_text(encoding="utf-8"))
    assert config["area"]["crs"] == "EPSG:27700"
    west, south, east, north = config["area"]["bbox"]
    assert east - west == 400
    assert north - south == 300
    assert config["lod_budgets_bytes"] == {"low": 8_000_000, "high": 12_000_000}
    assert config["triangle_budgets"] == {"low": 150_000, "high": 400_000}
    for path in (CITY / "schema").glob("*.schema.json"):
        json.loads(path.read_text(encoding="utf-8"))


def test_classification_and_height_outputs_are_byte_deterministic(tmp_path):
    classify = load_module("classify")
    heights = load_module("heights")
    classified = tmp_path / "classified.geojson"
    classified_again = tmp_path / "classified-again.geojson"
    classify.enrich(FIXTURE, classified)
    classify.enrich(FIXTURE, classified_again)
    assert classified.read_bytes() == classified_again.read_bytes()

    buildings = tmp_path / "buildings.json"
    buildings_again = tmp_path / "buildings-again.json"
    result = heights.enrich(classified, buildings)
    heights.enrich(classified, buildings_again)
    assert buildings.read_bytes() == buildings_again.read_bytes()
    assert [b["id"] for b in result["buildings"]] == ["way/101", "way/102"]
    assert result["buildings"][0]["height_source"] == "osm_levels"
    assert result["buildings"][0]["height_m"] == 6.4
    assert result["buildings"][1]["height_source"] == "default"


def test_height_output_matches_buildings_contract_with_pinned_snapshot(tmp_path):
    classify = load_module("classify")
    heights = load_module("heights")
    classified = tmp_path / "classified.geojson"
    output = tmp_path / "buildings.json"
    classify.enrich(FIXTURE, classified)
    result = heights.enrich(classified, output, snapshot="2026-11-24")
    validate(result, "buildings.schema.json")


def test_landmark_overrides_change_only_height_and_material(tmp_path):
    classify = load_module("classify")
    heights = load_module("heights")
    classified = tmp_path / "classified.geojson"
    output = tmp_path / "buildings.json"
    classify.enrich(FIXTURE, classified)
    result = heights.enrich(classified, output, snapshot="2026-11-24",
                            overrides={"way/101": {"height_m": 18, "facade_material": "brick"}})
    building = next(b for b in result["buildings"] if b["id"] == "way/101")
    assert building["height_m"] == 18
    assert building["height_source"] == "override"
    assert building["properties"]["facade_material"] == "brick"
    assert result["height_counts"]["override"] == 1
    validate(result, "buildings.schema.json")


def test_city_manifest_schema_supports_embedded_navmesh():
    manifest = {
        "schema_version": 1,
        "snapshot": "2026-11-24",
        "origin_epsg": "EPSG:27700",
        "origin": [384320, 398150],
        "attribution": ["© OpenStreetMap contributors", "Contains public sector information licensed under OGL"],
        "buildings": 2,
        "roads": 1,
        "props": 0,
        "navmesh": {"schema_version": 1, "graph": {"nodes": {}, "edges": []}},
        "render": "city.glb",
        "collision": "city-collision.glb",
        "shuttle_street": {"position": [0, 0], "rotation_degrees": 0},
    }
    validate(manifest, "city.schema.json")


def test_file_budgets_are_defined_for_full_scene():
    config = yaml.safe_load((CITY / "config.yaml").read_text(encoding="utf-8"))
    assert max(config["lod_budgets_bytes"].values()) == 12_000_000
    assert max(config["triangle_budgets"].values()) == 400_000

