"""Kit material bindings and compact instanced facade modules."""
from io import BytesIO
import json
import math
from pathlib import Path

KIT = Path(__file__).resolve().parents[1] / "raw/kit"
BINDINGS = {
    "asphalt": ("M_Asphalt", 1.11), "pavement": ("M_Terrazzo", 1.6),
    "kerb": ("M_Stone", 1.10), "glass": ("M_UpperGlass", 1),
    "facade_detail": ("M_Stone", 1.10), "roof": ("M_Slate", 1.24),
    "brick": ("M_ShopBrick", .90), "mill_brick": ("M_MillBrick", 1.24),
    "stone": ("M_Stone", 1.10), "plaster": ("M_CreamPlaster", 2.0),
    "setts": ("M_Setts", .69), "ground": ("M_Asphalt", 1.11),
    "road_marking": ("M_FadedTrafficPaint", 1),
}
WALLS = {"brick", "mill_brick", "stone", "plaster"}
FINISH_COLORS = {"frame": [.055, .075, .064, 1], "reveal": [.13, .086, .058, 1],
                 "mill_brick": [.223, .076, .045, 1], "plaster": [.56, .49, .37, 1]}


def wall_material(building):
    override = building.get("properties", {}).get("facade_material")
    if override in ("brick", "stone", "concrete"):
        return "plaster" if override == "concrete" else override
    kind = building.get("type")
    if kind == "mill_warehouse":
        return "mill_brick"
    if kind in {"terrace", "shop"}:
        return "brick"
    token = str(building.get("id", "building")).encode()
    bucket = sum(token) % 9
    return "stone" if bucket == 0 else "plaster" if bucket in (1,2) else "brick"


def texture_materials(materials, append_blob, tier):
    """Embed only the kit maps referenced by this mesh as small WebP images."""
    from PIL import Image

    manifest = json.loads((KIT / "material_manifest.json").read_text())
    images, textures, cached = [], [], {}
    for material in materials:
        binding = BINDINGS.get(material["name"])
        if binding is None:
            continue
        kit_name, _ = binding
        record = manifest[kit_name]
        pbr = material["pbrMetallicRoughness"]
        pbr.update(baseColorFactor=record["base_color_linear"], roughnessFactor=record["roughness"])
        if material["name"] == "glass":
            material["name"] = "M_UpperGlass"
        for channel, filename in sorted(record["textures"].items()):
            if channel != "BaseColor" and tier != "high":
                continue
            if filename not in cached:
                size = (128 if channel == "BaseColor" else 64) if tier == "high" else 48
                with Image.open(KIT / "Textures" / filename) as image:
                    image = image.convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
                    out = BytesIO()
                    image.save(out, "WEBP", quality=78, method=6)
                index = len(images)
                images.append({"name": filename, "mimeType": "image/webp",
                               "bufferView": append_blob(out.getvalue(), None)})
                textures.append({"extensions": {"EXT_texture_webp": {"source": index}}})
                cached[filename] = index
            texture = {"index": cached[filename]}
            if channel == "BaseColor":
                pbr["baseColorTexture"] = texture
                tint = .64 if material["name"] == "pavement" else 1
                pbr["baseColorFactor"] = [tint, tint, tint, 1]
            elif channel == "Normal":
                material["normalTexture"] = dict(texture, scale=.65)
            elif channel == "Roughness":
                pbr["metallicRoughnessTexture"] = texture
                pbr["roughnessFactor"] = 1
    return images, textures


def surface_uv(point, normal, tile_size):
    x, y, z = point
    nx, ny, nz = normal
    if abs(ny) > .55:
        return x / tile_size, z / tile_size
    length = math.hypot(nx, nz) or 1
    return (x*nz - z*nx) / (length*tile_size), -y / tile_size
