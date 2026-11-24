#!/usr/bin/env python3
"""Fetch OSM/LiDAR inputs and prepare deterministic local-metre GeoJSON layers.

This is the only city script which makes network requests. Raw responses stay
under ignored tools/city/raw/; cleaned layers and the manifest stay in tools/city/build/.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import tempfile
import zipfile
from contextlib import ExitStack
import json
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'tools/city/config.yaml'
OVERPASS_ENDPOINTS = (
    'https://overpass-api.de/api/interpreter',
    'https://overpass.private.coffee/api/interpreter',
    'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
)
USER_AGENT = 'Evorium-city-build/1.0'
EA_TILE_URL = "https://environment.data.gov.uk/tiles/collections/survey"
EA_PRODUCTS = {"dsm": "lidar_composite_first_return_dsm", "dtm": "lidar_composite_dtm"}
EA_TILES = ("SJ8095", "SJ8595")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def download_lidar(config_path=CONFIG, *, opener=urllib.request.urlopen):
    """Mosaic the cached (or downloaded) 2022 EA tiles on a 1 m BNG grid."""
    import rasterio
    from rasterio.merge import merge

    cfg = config_path if isinstance(config_path, dict) else yaml.safe_load(Path(config_path).read_text())
    west, south, east, north = cfg["area"]["bbox"]
    bounds = (west - 20, south - 20, east + 20, north + 20)
    raw = ROOT / "tools/city/raw"
    raw.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=raw, prefix="lidar-") as work:
        work = Path(work)
        for kind, product in EA_PRODUCTS.items():
            with ExitStack() as stack:
                sources = []
                for tile in EA_TILES:
                    archive = raw / f"{product}_{tile}.zip"
                    if not archive.exists():
                        request = urllib.request.Request(
                            f"{EA_TILE_URL}/{product}/2022/1/{tile}",
                            headers={"User-Agent": USER_AGENT},
                        )
                        download = work / archive.name
                        with opener(request, timeout=240) as response, download.open("wb") as stream:
                            shutil.copyfileobj(response, stream)
                        with zipfile.ZipFile(download) as package:
                            if not any(name.lower().endswith(".tif") for name in package.namelist()):
                                raise ValueError(f"No elevation TIFF in {download.name}")
                        download.replace(archive)
                    with zipfile.ZipFile(archive) as package:
                        members = [name for name in package.namelist() if name.lower().endswith(".tif")]
                        for index, member in enumerate(sorted(members)):
                            raster = work / f"{kind}-{tile}-{index}.tif"
                            with package.open(member) as source, raster.open("wb") as stream:
                                shutil.copyfileobj(source, stream)
                            dataset = stack.enter_context(rasterio.open(raster))
                            if dataset.crs.to_epsg() != 27700 or dataset.res != (1, 1):
                                raise ValueError(f"Unexpected raster grid in {member}")
                            sources.append(dataset)
                if not sources:
                    raise ValueError(f"No EA {kind} rasters found")
                data, transform = merge(sources, bounds=bounds, res=(1, 1),
                                        nodata=-9999, dtype="float32")
                output = work / f"lidar_{kind}.tif"
                with rasterio.open(output, "w", driver="GTiff", width=data.shape[2],
                                   height=data.shape[1], count=1, dtype="float32", crs="EPSG:27700",
                                   transform=transform, nodata=-9999, compress="deflate") as target:
                    target.write(data)
        for kind in EA_PRODUCTS:
            (work / f"lidar_{kind}.tif").replace(raw / f"lidar_{kind}.tif")
    return {kind: {"sha256": digest(raw / f"lidar_{kind}.tif")} for kind in EA_PRODUCTS}


def download_tree(*, opener=urllib.request.urlopen):
    """Fetch the two pinned CC0 Kenney Mini Arena tree source files."""
    base = ("https://raw.githubusercontent.com/KenneyNL/Starter-Kit-Basic-Scene/main/"
            "sample/Mini%20Arena/Models/GLB%20format/")
    files = {
        "tree.glb": ("kenney-tree.glb", "f8632c9758a78f60aa4ca68bf0e5ac972770167a5608e179293a12552d8fc2ef"),
        "Textures/colormap.png": ("Textures/colormap.png", "cdc845e1c8704c69d87dbf872c9004b470fc838f4b2830fb7e4fc4a530c80e10"),
    }
    raw = ROOT / "tools/city/raw"
    for name, (target, expected) in files.items():
        path = raw / target
        if path.is_file() and digest(path) == expected:
            continue
        request = urllib.request.Request(base+name, headers={"User-Agent": USER_AGENT})
        with opener(request, timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"Kenney source mismatch for {name}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return {target: expected for target, expected in files.values()}


def write_preview(layers, bounds, destination):
    """Draw a labelled, deterministic area preview without a plotting dependency."""
    from PIL import Image, ImageDraw, ImageFont
    west, south, east, north = bounds
    width, height, pad = 1200, 900, 48
    image = Image.new('RGB', (width, height), '#f5f1e8')
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    def pixel(x, z):
        return (pad + round((x-west)/(east-west)*(width-2*pad)),
                height-pad-round((z-south)/(north-south)*(height-2*pad)))
    colors={'roads':'#b8a98d','buildings':'#a9493d','water':'#70a9bd','shops':'#e4a743',
            'landuse':'#88a87b','trees':'#32734d','props':'#6651a3'}
    def draw_geom(g, color, is_building=False):
        typ=g['type']; coords=g.get('coordinates')
        def path(points): return [pixel(float(p[0]),float(p[1])) for p in points]
        if typ=='Point':
            x,y=pixel(*coords[:2]);draw.ellipse((x-3,y-3,x+3,y+3),fill=color)
        elif typ=='LineString':
            if len(coords)>1: draw.line(path(coords),fill=color,width=2)
        elif typ=='Polygon':
            if coords and len(coords[0])>2: draw.polygon(path(coords[0]),fill=color if is_building else None,outline=color)
        elif typ=='MultiPolygon':
            for poly in coords:
                if poly and len(poly[0])>2: draw.polygon(path(poly[0]),fill=color if is_building else None,outline=color)
        elif typ=='MultiLineString':
            for line in coords:
                if len(line)>1: draw.line(path(line),fill=color,width=2)
    draw.text((pad,10),'Evorium · Ancoats five-street data preview (British National Grid metres)',fill='#17191c',font=font)
    for name in ('landuse','water','roads','buildings','shops','trees','props'):
        for f in layers.get(name,[]): draw_geom(f['geometry'],colors[name],name in {'buildings','shops'})
    x=pad
    for name in ('roads','buildings','shops','water','landuse','trees','props'):
        draw.rectangle((x,height-28,x+12,height-16),fill=colors[name]);draw.text((x+17,height-30),name,fill='#17191c',font=font);x+=112
    destination.parent.mkdir(parents=True,exist_ok=True)
    image.save(destination,optimize=False)


def query_for_bbox(bbox):
    """Build Overpass query using WGS84 bounds (south,west,north,east)."""
    s, w, n, e = bbox
    return f'''[out:json][timeout:180];(way["building"]({s},{w},{n},{e});way["highway"]({s},{w},{n},{e});way["shop"]({s},{w},{n},{e});way["landuse"]({s},{w},{n},{e});way["natural"]({s},{w},{n},{e});way["leisure"]({s},{w},{n},{e});way["waterway"]({s},{w},{n},{e});node["natural"="tree"]({s},{w},{n},{e});node["amenity"~"^(bench|waste_basket|street_lamp)$"]({s},{w},{n},{e});node["man_made"="street_lamp"]({s},{w},{n},{e});node["barrier"="bollard"]({s},{w},{n},{e});node["highway"="street_lamp"]({s},{w},{n},{e});node["highway"="crossing"]({s},{w},{n},{e}););out body geom;'''


def element_geometry(el):
    from shapely.geometry import LineString, Point, Polygon
    typ = el.get('type')
    if typ == 'node':
        return Point(el['lon'], el['lat'])
    coords = [(p['lon'], p['lat']) for p in el.get('geometry', [])]
    if len(coords) < 2:
        return None
    if typ == 'way' and coords[0] == coords[-1] and len(coords) >= 4:
        try:
            return Polygon(coords)
        except Exception:
            pass
    return LineString(coords)


def fetch(config_path=CONFIG, *, opener=urllib.request.urlopen, fixture=False, refresh=False):
    from pyproj import Transformer
    from shapely.geometry import Polygon, box, mapping
    from shapely.ops import transform
    cfg = config_path if isinstance(config_path, dict) else yaml.safe_load(Path(config_path).read_text())
    west, south, east, north = cfg['area']['bbox']
    origin_x, origin_y = cfg['area']['origin']
    to_wgs = Transformer.from_crs(cfg['area']['crs'], 'EPSG:4326', always_xy=True)
    # Densify box edges before projecting to avoid a corner-only approximation.
    boundary = Polygon([(west, south), (east, south), (east, north), (west, north)]).segmentize(25)
    wgs_boundary = transform(to_wgs.transform, boundary)
    minlon, minlat, maxlon, maxlat = wgs_boundary.bounds
    raw_dir = ROOT / 'tools/city/raw'
    build = ROOT / cfg['outputs']['build_dir']
    raw_dir.mkdir(parents=True, exist_ok=True)
    build.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / 'osm-overpass.json'
    if fixture:
        raw_path = ROOT/'tools/city/tests/fixtures/osm.json'
    elif refresh or not raw_path.exists():
        query = query_for_bbox((minlat, minlon, maxlat, maxlon))
        body = urllib.parse.urlencode({'data': query}).encode()
        headers = {'User-Agent': USER_AGENT, 'Content-Type': 'application/x-www-form-urlencoded'}
        errors = []
        # Public Overpass instances can be temporarily overloaded. All endpoints
        # execute the same query; the fetched bytes are pinned by SHA-256.
        for endpoint in OVERPASS_ENDPOINTS:
            request = urllib.request.Request(endpoint, data=body, headers=headers)
            try:
                with opener(request, timeout=240) as response:
                    response_bytes = response.read()
                response_payload = json.loads(response_bytes)
                if response_payload.get('remark'):
                    raise RuntimeError(response_payload['remark'])
                if not isinstance(response_payload.get('elements'), list):
                    raise RuntimeError('Overpass response has no elements list')
                if not response_payload['elements']:
                    raise RuntimeError('Overpass returned no elements for the configured area')
                raw_path.write_bytes(response_bytes)
                break
            except Exception as exc:
                errors.append(f'{endpoint}: {exc}')
        else:
            raise RuntimeError('All Overpass endpoints failed: ' + '; '.join(errors))
    raw_bytes = raw_path.read_bytes()
    payload = json.loads(raw_bytes)
    to_local = Transformer.from_crs('EPSG:4326', cfg['area']['crs'], always_xy=True)
    clip = box(west, south, east, north)
    layers = {'buildings': [], 'roads': [], 'shops': [], 'landuse': [], 'water': [], 'trees': [], 'props': []}
    for el in sorted(payload.get('elements', []), key=lambda x: (x.get('type',''), int(x.get('id',0)))):
        g = element_geometry(el)
        if g is None or g.is_empty:
            continue
        g = transform(to_local.transform, g)
        if not g.intersects(clip):
            continue
        g = g.intersection(clip)
        if g.is_empty:
            continue
        g = transform(lambda x,y,z=None:(x-origin_x,y-origin_y), g)
        tags = el.get('tags', {})
        props = {'osm_id': int(el['id']), 'osm_type': el.get('type','way'), 'source': 'OpenStreetMap', **tags}
        record = {'type':'Feature','id':f"{props['osm_type']}/{props['osm_id']}", 'properties':props,'geometry':mapping(g)}
        if 'building' in tags: layer='buildings'
        elif 'highway' in tags: layer='roads'
        elif 'shop' in tags: layer='shops'
        elif tags.get('natural') == 'tree': layer='trees'
        elif tags.get('amenity') in {'bench','waste_basket','street_lamp'} or tags.get('man_made') == 'street_lamp' or tags.get('barrier') == 'bollard' or tags.get('highway') in {'crossing','street_lamp'}: layer='props'
        elif 'waterway' in tags or tags.get('natural') == 'water': layer='water'
        else: layer='landuse'
        layers[layer].append(record)
    for name, features in layers.items():
        out = build / 'layers' / f'{name}.geojson'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({'type':'FeatureCollection','features':features}, sort_keys=True, separators=(',',':'))+'\n')
    write_preview(layers, (west-origin_x,south-origin_y,east-origin_x,north-origin_y), build/'preview.png')
    manifest = {'schema_version':1,'source':'OpenStreetMap Overpass API','snapshot_date':str(cfg.get('snapshot_date') or date.today()),
                'query_bbox_wgs84':[minlat,minlon,maxlat,maxlon], 'bbox_epsg27700':[west,south,east,north],
                'origin_epsg27700':[origin_x,origin_y], 'raw_file':str(raw_path.relative_to(ROOT)),
                'raw_sha256':digest(raw_path),'counts':{k:len(v) for k,v in sorted(layers.items())}}
    (build/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    return manifest


def run(config, fixture=False):
    # Reuse the saved source snapshot by default; network refresh is explicit.
    return fetch(config, fixture=fixture)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, default=CONFIG)
    p.add_argument('--refresh', action='store_true', help='download a new Overpass snapshot')
    p.add_argument('--fixture', action='store_true', help='use the committed offline test fixture')
    p.add_argument('--tree', action='store_true', help='fetch the pinned CC0 Kenney tree source')
    p.add_argument('--lidar', action='store_true', help='download or use cached EA tiles and build the clipped DSM/DTM pair')
    args=p.parse_args()
    try:
        if args.tree:
            print(json.dumps(download_tree(), indent=2))
            return
        if args.lidar:
            print(json.dumps(download_lidar(args.config), indent=2))
            return
        result=fetch(args.config,fixture=args.fixture,refresh=args.refresh)
    except Exception as exc:
        print(f'City source fetch failed: {exc}',file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()
