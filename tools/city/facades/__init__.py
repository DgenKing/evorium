from .generate import add_facades


def run(config, fixture=False):
    """Report facade-ready footprints; geometry embeds them during city mesh export."""
    import json
    from pathlib import Path

    source = Path.cwd() / config["outputs"]["build_dir"] / "buildings.json"
    buildings = json.loads(source.read_text(encoding="utf-8")).get("buildings", [])
    return {"facade_buildings": len(buildings), "generated_in": "geometry"}

__all__ = ["add_facades", "run"]
