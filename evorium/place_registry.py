"""Public place definitions shared by simulation, dashboard, and scene."""
from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path

from evorium.arcade import LAYOUT


@dataclass(frozen=True)
class Place:
    location: str
    name: str
    kind: str
    indoor: bool
    spots: tuple[str, ...]
    hours: tuple[int, int] = (0, 24)
    landmark: str = 'henry'
    rain_closes: bool = False
    holiday_hours: tuple[int, int] | None = None


PLACES = {
    'pub': Place('The Crooked Billet, Ancoats, Manchester', 'The Crooked Billet',
                 'pub', True, ('PUB_BOOTH', 'PUB_BAR', 'PUB_WINDOW')),
    'shop': Place("Patel's News, Ancoats", "Patel's News",
                  'shop', True, ('NEWS_QUEUE', 'NEWS_RACK', 'NEWS_CHILLER')),
    'street': Place('Henry Street, Ancoats', 'Henry Street', 'street', False,
                    ('STREET_WAIT', 'STREET_LINK')),
    'cafe': Place('Bobbin Café, Ancoats', 'Bobbin Café', 'café', True,
                  ('r59c', 'r59b'), (7, 16), 'way/1127826005', holiday_hours=(9, 14)),
    'square': Place('Cutting Room Square, Ancoats', 'Cutting Room Square', 'square', False,
                    ('r6f6', 'r44f', 'r44e'), landmark='way/198725251', rain_closes=True),
    'towpath': Place('Rochdale Canal towpath, Ancoats', 'Rochdale Canal towpath', 'towpath',
                      False, ('r457', 'r456'), (8, 18), 'way/1429556814', rain_closes=True),
    'offlicence': Place('Spindle Off-Licence, Ancoats', 'Spindle Off-Licence', 'off-licence',
                        True, ('r4a5',), (12, 21), 'way/679024763', holiday_hours=(12, 17)),
    'arcade': Place('Gun Street Amusements, Ancoats', 'Gun Street Amusements', 'arcade', True,
                    ('arcade-coin-a', 'arcade-coin-b', 'arcade-fruit', 'arcade-claw', 'arcade-hockey'),
                    landmark=LAYOUT['osm_id']),
}
REGISTRY = {key: place.location for key, place in PLACES.items()}
BY_LOCATION = {location: key for key, location in REGISTRY.items()}

# Exterior doors are visual stand-ins for the cast's homes beyond this map.
HOME_DOORS = {
    'Blossom Street': ('way/1127565117', 'r312'),
    'Great Ancoats Street': ('way/262185690', 'r1a'),
    'Jersey Street': ('way/259475216', 'r395'),
}


def home_door(first):
    if first == 'Norman':
        return 'arcade-home'
    if first == 'Maxine':
        return HOME_DOORS['Blossom Street'][1]
    if first == 'Dez':
        return 'UPSTAIRS'
    if first in ('Tommy', 'Brenda', 'Peggy', 'Ronnie', 'Kirsty', 'Jess'):
        return HOME_DOORS['Blossom Street'][1]
    if first in ('Raj', 'Anjali', 'Pete', 'Gary', 'Grace'):
        return HOME_DOORS['Jersey Street'][1]
    return HOME_DOORS['Great Ancoats Street'][1]

@lru_cache(maxsize=1)
def city_nodes():
    path = Path(__file__).parent / 'static/world3d/data/city.json'
    return json.loads(path.read_text(encoding='utf-8'))['navmesh']['graph']['nodes']


def map_entry(place):
    if place.landmark == 'henry':
        return {}
    if place.kind == 'arcade':
        return {'osmId': place.landmark}
    return {'osmId': place.landmark, 'position': city_nodes()[place.spots[0]][::2]}
