"""Validate and export the walkable graph embedded by the geometry stage."""
from __future__ import annotations

import json
from pathlib import Path


def validate(navmesh: dict) -> None:
    vertices = navmesh.get("vertices", [])
    polygons = navmesh.get("polygons", [])
    if navmesh.get("schema_version") != 1:
        raise ValueError("Unsupported city navmesh schema")
    for polygon in polygons:
        if len(polygon) < 3 or any(not isinstance(i, int) or i < 0 or i >= len(vertices) for i in polygon):
            raise ValueError("Navmesh polygon references an invalid vertex")
    graph = navmesh.get("graph", {})
    nodes, edges = graph.get("nodes", {}), graph.get("edges", [])
    if not nodes or not edges:
        raise ValueError("Navmesh graph is empty or disconnected")
    for edge in edges:
        if len(edge) != 2 or edge[0] not in nodes or edge[1] not in nodes:
            raise ValueError("Navmesh graph edge references a missing node")


def run(config, fixture=False):
    root = Path.cwd()
    static = root / config["outputs"]["static_dir"]
    build = root / config["outputs"]["build_dir"]
    manifest_path = static / "data/city.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    nav = manifest.get("navmesh")
    if not isinstance(nav, dict):
        raise ValueError("city.json has no embedded navmesh")
    validate(nav)
    out = build / "navmesh.json"
    out.write_text(json.dumps(nav, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return {"vertices": len(nav["vertices"]), "polygons": len(nav["polygons"]),
            "graph_nodes": len(nav["graph"]["nodes"]), "graph_edges": len(nav["graph"]["edges"])}
