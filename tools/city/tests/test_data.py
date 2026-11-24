import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools/city'/f'{name}.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def test_classification_is_stable_and_respects_shop():
    c=module('classify')
    assert c.classify({'building':'retail','shop':'bakery','building:levels':'2'}) == ('shop','flat',2)
    assert c.classify({'building':'industrial','building:levels':'4'}) == ('mill_warehouse','flat',4)
    assert c.classify({'building':'apartments','building:levels':'5'}) == ('modern_flats','flat',5)

def test_height_defaults_and_levels():
    h=module('heights')
    assert h.DEFAULT_HEIGHTS['other']==6.4

def test_overpass_query_uses_box_without_attic_date():
    f=module('fetch')
    query=f.query_for_bbox((53.47,-2.23,53.48,-2.22))
    assert '[date:' not in query
    assert '(53.47,-2.23,53.48,-2.22)' in query
    assert f.USER_AGENT == 'Evorium-city-build/1.0'
    assert 'https://maps.mail.ru/osm/tools/overpass/api/interpreter' in f.OVERPASS_ENDPOINTS
