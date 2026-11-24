from __future__ import annotations

import importlib.util
from pathlib import Path

CITY = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("city_props", CITY / "props.py")
PROPS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROPS)


def fixture_layers():
    return {
        "roads": [{"id": "way/7", "properties": {"highway": "residential"},
                   "geometry": {"type": "LineString", "coordinates": [[0, 0], [100, 0]]}}],
        "trees": [{"id": "node/9", "properties": {"natural": "tree"},
                   "geometry": {"type": "Point", "coordinates": [8, 2]}}],
        "amenities": [{"id": "node/10", "properties": {"amenity": "bench"},
                       "geometry": {"type": "Point", "coordinates": [12, 4]}}],
    }


def test_props_are_stable_and_seeded():
    layers = fixture_layers()
    a = PROPS.generate_props(layers, 42, (-5, -5, 110, 10))
    b = PROPS.generate_props(layers, 42, (-5, -5, 110, 10))
    c = PROPS.generate_props(layers, 43, (-5, -5, 110, 10))
    assert a == b
    assert a != c
    assert [p["id"] for p in a] == sorted(p["id"] for p in a)


def test_props_use_supported_types_and_stay_in_bounds():
    props = PROPS.generate_props(fixture_layers(), 42, (0, 0, 100, 10))
    assert {p["type"] for p in props} <= {"lamp", "bin", "bollard", "bench", "tree", "road_marking"}
    assert any(p["type"] == "tree" and p["source"] == "OpenStreetMap tree" for p in props)
    assert any(p["type"] == "bench" and p["source"] == "OpenStreetMap bench" for p in props)
    assert all(0 <= p["position"][0] <= 100 and 0 <= p["position"][2] <= 10 for p in props)
