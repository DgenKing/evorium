from collections import defaultdict
from datetime import datetime, timedelta
import json

import pytest

from evorium import memory, places, scene, sim, tick, world
from evorium.db import connect, init_db
from evorium.models import ActionProposal, Extraction
from evorium.place_registry import HOME_DOORS, city_nodes
from evorium.seed import seed_agents


@pytest.fixture
def db(tmp_path):
    path = tmp_path / 'city.sqlite3'
    init_db(path)
    seed_agents(path)
    return path


def test_places_use_connected_city_spots():
    from pathlib import Path
    manifest = Path(scene.__file__).parent / 'static/world3d/data/city.json'
    neighbors = defaultdict(list)
    graph = json.loads(manifest.read_text())['navmesh']['graph']
    for a, b in graph['edges']:
        neighbors[a].append(b)
        neighbors[b].append(a)
    start = min(city_nodes(), key=lambda node: sum((a-b)**2 for a, b in zip(city_nodes()[node], (4.9, 0, 5.48))))
    reached = {start}
    queue = [start]
    for node in queue:
        for other in neighbors[node]:
            if other not in reached:
                queue.append(other)
                reached.add(other)
    assert all(spot in reached for place in places.PLACES.values()
               if place.landmark != 'henry' for spot in place.spots)
    assert all(door in reached for _, door in HOME_DOORS.values())


def test_outings_and_rain_preserve_shared_free_time(db):
    with connect(db) as c:
        names = [r[0] for r in c.execute("SELECT name FROM agents WHERE kind='npc'")]
    monday = datetime(2026, 11, 23)
    assert min(world.shared_free_hours(names, monday).values()) >= 3
    for first, days, start, _, key, _ in world.CITY_OUTINGS:
        name = next(n for n in names if n.startswith(first + ' '))
        at = monday + timedelta(days=days[0], hours=start, minutes=1)
        assert world.routine(name, at)[0] == places.REGISTRY[key]
        assert world.is_free(name, at)
        if places.PLACES[key].rain_closes:
            assert world.routine(name, at, {'_weather': {'raining': True}})[0] == world.home_location(name)
    assert not places.is_open('cafe', datetime(2026, 12, 25, 12))


def test_cafe_meeting_is_recorded_and_checked(db, monkeypatch):
    at = datetime(2026, 11, 24, 10, 5)
    monkeypatch.setattr(world, 'now', lambda *_: at)
    tick.update_routines(at, db)
    people = places.present(at, db)['cafe']
    first, second = people[:2]

    class Fake:
        def propose(self, *args, **kwargs):
            if kwargs.get('schema') is Extraction or (len(args) > 2 and args[2] is Extraction):
                return Extraction(summary='Offline café meeting')
            return ActionProposal(say='Good to see you at the café.', rationale='Offline.', mood='friendly')

    cafe = places.REGISTRY['cafe']
    with connect(db) as c:
        participants = {person['name']: person for person in (first, second)}
        extraction = Extraction.model_validate({'summary': 'Plans for coffee', 'per_agent': {
            first['name']: {'commitments': [{'content': 'Meet at the café', 'to': second['name'],
                                             'kind': 'talk', 'target': {'place': 'cafe', 'person': second['name']},
                                             'due_hours': 2}]}}})
        memory.store_extraction(c, None, participants, extraction, at - timedelta(hours=1))
        promise = dict(c.execute('SELECT * FROM commitments').fetchone())
    from evorium.promise_evidence import evidence_for
    sim.run_conversation(Fake(), first['id'], second['id'], 2, db, location=world.PUB)
    with connect(db) as c:
        assert not evidence_for(c, promise)
    cid = sim.run_conversation(Fake(), first['id'], second['id'], 2, db, location=cafe)
    with connect(db) as c:
        assert evidence_for(c, promise)[0]['id'] == cid


def test_old_locations_survive_initialisation(db):
    with connect(db) as c:
        c.execute('UPDATE agents SET location=? WHERE id=1', (world.PUB,))
        version = c.execute('PRAGMA user_version').fetchone()[0]
    init_db(db)
    with connect(db) as c:
        assert c.execute('SELECT location FROM agents WHERE id=1').fetchone()[0] == world.PUB
        assert c.execute('PRAGMA user_version').fetchone()[0] == version
    assert scene.snapshot(db)['characters'][0]['place'] == 'pub'
