"""Deterministically classify OSM building footprints and roof defaults."""
from __future__ import annotations
import json
import argparse
from pathlib import Path


def classify(tags):
    tags = tags or {}
    shop = tags.get('shop')
    building = str(tags.get('building','')).lower()
    levels = parse_levels(tags.get('building:levels'))
    if shop:
        kind='shop'
    elif any(word in ' '.join((building,str(tags.get('name','')),str(tags.get('industrial','')))).lower()
             for word in ('mill','warehouse','industrial','factory')):
        kind='mill_warehouse'
    elif building == 'apartments' or (building == 'residential' and levels and levels >= 4):
        kind='modern_flats'
    elif building in {'terrace','house','semidetached_house','detached'} or (building=='residential' and (levels or 1)<=3):
        kind='terrace'
    else:
        kind='other'
    roof=str(tags.get('roof:shape','')).lower()
    roof = roof if roof in {'flat','gabled','hipped','pyramidal','mansard','skillion'} else ('flat' if kind in {'modern_flats','mill_warehouse','shop'} else 'gabled')
    return kind,roof,levels


def parse_levels(value):
    try:
        n=float(str(value).replace(',','.'))
        return int(n) if n>0 else None
    except (TypeError,ValueError):
        return None


def enrich(source, output):
    data=json.loads(Path(source).read_text())
    for feature in data.get('features',[]):
        kind,roof,levels=classify(feature.get('properties',{}))
        feature['properties'].update({'building_type':kind,'roof':roof,'levels':levels})
    Path(output).write_text(json.dumps(data,sort_keys=True,separators=(',',':'))+'\n')
    return data

def run(config, fixture=False):
    root=Path(__file__).resolve().parents[2]
    build=root/config['outputs']['build_dir']
    return enrich(build/'layers/buildings.geojson',build/'classified-buildings.geojson')

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',nargs='?',default='tools/city/build/layers/buildings.geojson')
    p.add_argument('output',nargs='?',default='tools/city/build/classified-buildings.geojson')
    a=p.parse_args();enrich(a.source,a.output)
