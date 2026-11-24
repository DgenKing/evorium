"""Attach stable building heights, preferring EA DSM-DTM then OSM levels."""
from __future__ import annotations
import json
import argparse
import hashlib
from pathlib import Path

DEFAULT_HEIGHTS={'terrace':7.5,'mill_warehouse':12.0,'modern_flats':12.8,'shop':6.4,'other':6.4}

def _sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()


def _geometry(feature):
    from shapely.geometry import shape
    return shape(feature['geometry'])


def raster_height(feature, dsm, dtm, origin=(0, 0), *, with_roof=False):
    """Median positive surface-minus-ground sample in the footprint; None if unavailable."""
    import numpy as np
    from rasterio.mask import mask
    from rasterio.warp import transform_geom
    from shapely.affinity import translate
    geom=translate(_geometry(feature), *origin)
    geom_dict=geom.__geo_interface__
    if str(dsm.crs) != 'EPSG:27700':
        geom_dict=transform_geom('EPSG:27700',dsm.crs,geom_dict)
    shapes=[geom_dict]
    try:
        a, _=mask(dsm,shapes,crop=True,filled=False)
        b, _=mask(dtm,shapes,crop=True,filled=False)
        valid=~(np.ma.getmaskarray(a[0])|np.ma.getmaskarray(b[0]))
        diff=np.asarray(a[0].filled(float('nan'))-b[0].filled(float('nan')))
        valid &= np.isfinite(diff) & (diff>1.5) & (diff<100)
        vals=diff[valid]
        if not vals.size:
            return (None, None) if with_roof else None
        height = float(np.median(vals))
        # Erode the footprint mask to remove mixed edge pixels before estimating roof relief.
        roof = None
        if min(valid.shape) >= 5:
            interior = valid[1:-1,1:-1].copy()
            for rows, cols in ((slice(None,-2),slice(1,-1)),(slice(2,None),slice(1,-1)),
                               (slice(1,-1),slice(None,-2)),(slice(1,-1),slice(2,None))):
                interior &= valid[rows,cols]
            roof_values = diff[1:-1,1:-1][interior]
            if roof_values.size >= 20:
                lo, hi = np.percentile(roof_values, [15,85])
                relief = hi-lo
                if relief < .55:
                    roof = "flat"
                elif 1.05 < relief < 3.6:
                    roof = "gabled"
        return (height, roof) if with_roof else height
    except (ValueError, IndexError):
        return (None, None) if with_roof else None


def enrich(source, output, dsm_path=None, dtm_path=None, snapshot=None, overrides=None, origin=(0, 0)):
    data=json.loads(Path(source).read_text())
    dsm=dtm=None
    if dsm_path and dtm_path and Path(dsm_path).exists() and Path(dtm_path).exists():
        import rasterio
        dsm=rasterio.open(dsm_path); dtm=rasterio.open(dtm_path)
        if dsm.crs != dtm.crs:
            dsm.close();dtm.close();raise ValueError('DSM and DTM CRS do not match')
        if (dsm.transform != dtm.transform or dsm.width != dtm.width or dsm.height != dtm.height):
            dsm.close();dtm.close();raise ValueError('DSM and DTM grids do not align; warp DTM to DSM grid first')
    counts={'lidar':0,'osm_levels':0,'default':0,'override':0}
    buildings=[]
    try:
        for f in data.get('features',[]):
            p=f.get('properties',{})
            ident=str(f.get('id',f"{p.get('osm_type','way')}/{p.get('osm_id','unknown')}"))
            kind=p.get('building_type','other')
            h, roof = raster_height(f,dsm,dtm,origin,with_roof=True) if dsm else (None, None)
            source_name='lidar'
            levels=p.get('levels')
            if h is None and levels:
                h=float(levels)*3.2;source_name='osm_levels'
            if h is None:
                h=DEFAULT_HEIGHTS.get(kind,DEFAULT_HEIGHTS['other']);source_name='default'
            override=(overrides or {}).get(ident,{})
            if 'height_m' in override:
                h=float(override['height_m'])
                if h <= 0:
                    raise ValueError(f'Invalid landmark height for {ident}')
                source_name='override'
            if override.get('facade_material'):
                p['facade_material']=str(override['facade_material'])
            counts[source_name]+=1
            buildings.append({'id':ident,
                              'geometry':f['geometry'],'height_m':round(float(h),2),'height_source':source_name,
                              'levels':levels,'type':kind,'roof':roof if kind == 'terrace' and roof else p.get('roof','gabled'),'properties':p})
    finally:
        if dsm:dsm.close();dtm.close()
    result={'schema_version':1,'snapshot':snapshot or 'unknown','height_counts':counts,'buildings':sorted(buildings,key=lambda b:b['id'])}
    Path(output).write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
    return result

def run(config, fixture=False):
    root=Path(__file__).resolve().parents[2]
    build=root/config['outputs']['build_dir']
    import classify
    import yaml
    classify.enrich(build/'layers/buildings.geojson',build/'classified-buildings.geojson')
    dsm=root/config['inputs']['lidar_dsm'];dtm=root/config['inputs']['lidar_dtm']
    landmark_config=yaml.safe_load((root/'tools/city/landmarks.yaml').read_text(encoding='utf-8'))
    if landmark_config.get('schema_version') != 1:
        raise ValueError('Unsupported landmarks.yaml schema')
    result=enrich(build/'classified-buildings.geojson',build/'buildings.json',dsm,dtm,
                  config.get('snapshot_date'),landmark_config.get('overrides',{}), config['area']['origin'])
    manifest=build/'manifest.json'
    if manifest.exists():
        data=json.loads(manifest.read_text());data['height_counts']=result['height_counts']
        for label,path in (('lidar_dsm',dsm),('lidar_dtm',dtm)):
            if path.exists():
                data.setdefault('input_sha256',{})[label]=_sha256(path)
        manifest.write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')
    return result

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',nargs='?',default='tools/city/build/classified-buildings.geojson')
    p.add_argument('output',nargs='?',default='tools/city/build/buildings.json')
    p.add_argument('--dsm',default='tools/city/raw/lidar_dsm.tif')
    p.add_argument('--dtm',default='tools/city/raw/lidar_dtm.tif')
    a=p.parse_args()
    result=enrich(a.source,a.output,a.dsm,a.dtm)
    print(json.dumps(result['height_counts'],sort_keys=True))
