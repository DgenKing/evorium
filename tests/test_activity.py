import json
from datetime import datetime, timedelta, timezone

import pytest

from evorium import greetings, main, places, world
from evorium.db import connect, init_db
from evorium.seed import seed_agents

NOW = datetime(2026, 11, 24, 10)
REAL = datetime(2026, 11, 24, 10, tzinfo=timezone.utc)


@pytest.fixture
def db(tmp_path):
    path = tmp_path / 'activity.sqlite3'
    init_db(path)
    seed_agents(path)
    return path


def people(*ids, location):
    return [dict(id=id, name=f'Neighbour {id}', location=location, activity='out for a walk') for id in ids]


def record(c, place, a, b, at):
    c.execute("""INSERT INTO conversations(location,status,agent_a_id,agent_b_id,sim_at)
                 VALUES (?,'completed',?,?,?)""", (places.REGISTRY[place],a,b,at.strftime('%Y-%m-%d %H:%M')))


def test_round_starts_one_due_place_and_skips_capped_pairs(db, monkeypatch):
    groups = dict(pub=people(1,3,location=world.PUB), shop=people(4,5,location=world.SHOP),
                  cafe=people(6,7,location=places.REGISTRY['cafe']))
    groups = {**dict.fromkeys(places.REGISTRY, ()), **groups}
    monkeypatch.setattr(world, 'now', lambda _: NOW)
    monkeypatch.setattr(places, 'present', lambda *_: groups)
    monkeypatch.setattr(main, '_state', {'conversations':0})
    with connect(db) as c:
        record(c, 'pub', 1, 3, NOW - timedelta(hours=2))
        record(c, 'pub', 1, 3, NOW - timedelta(hours=1))
        record(c, 'shop', 4, 5, NOW - timedelta(minutes=12))
        record(c, 'cafe', 6, 7, NOW - timedelta(minutes=12))
    assert [key for key,_ in places.opportunities(NOW-timedelta(minutes=1), db_path=db)] == ['pub']
    captured = []
    def fake(client, a, b, turns, db_path, *, location):
        key = places.BY_LOCATION[location]
        captured.append(key)
        with connect(db_path) as c:
            record(c,key,a,b,NOW)
    monkeypatch.setattr(main, 'run_conversation', fake)
    assert main._auto_conversations(object(), NOW, None, db) == {4,5}
    assert captured == ['shop']
    assert main._auto_conversations(object(), NOW, None, db) == {6,7}
    assert captured == ['shop', 'cafe']
    assert main._state['conversations'] == 2
    assert places.conversation_gap('pub') == 8
    assert places.conversation_gap('cafe', override=20) == 20
    assert [key for key,_ in places.opportunities(NOW, db_path=db)] == ['pub']


@pytest.mark.parametrize('hour, condition, expected', [
    (10, {}, 'Morning, Neighbour. All right?'),
    (14, {'condition':'snow'}, 'Afternoon, Neighbour. Watch your step.'),
    (19, {'raining':True}, 'Evening, Neighbour. Some rain, eh?'),
])
def test_short_hello_uses_no_model_or_memory(db, monkeypatch, hour, condition, expected):
    group = people(1,3,location=world.STREET)
    monkeypatch.setattr(places, 'present', lambda *_: {'street':group})
    monkeypatch.setattr(greetings.weather, 'read', lambda *_:condition)
    with connect(db) as c:
        world._set(c, 'scene.travel.1', json.dumps({'to':world.STREET,'started':REAL.timestamp()}))
        facts = c.execute('SELECT count(*) FROM facts').fetchone()[0]
    now=NOW.replace(hour=hour)
    assert greetings.run(now, db, real_at=REAL)
    assert not greetings.run(now, db, real_at=REAL)
    with connect(db) as c:
        settings = dict(c.execute('SELECT key,value FROM world'))
        first, reply = greetings.active(settings, REAL)
        assert (first['id'], first['to'], first['text']) == (1,3,expected)
        assert reply['id']==3 and reply['start']==first['start']+3
        assert all(len(line['text'])<=96 and '\n' not in line['text'] for line in (first,reply))
        assert not greetings.active(settings, REAL+timedelta(seconds=10))
        assert c.execute('SELECT count(*) FROM conversations').fetchone()[0] == 0
        assert c.execute('SELECT count(*) FROM llm_calls').fetchone()[0] == 0
        assert c.execute('SELECT count(*) FROM facts').fetchone()[0] == facts


def test_evening_routines_add_trips_and_keep_work_and_quiz():
    assert world.routine('Pete Lomax', NOW.replace(hour=17,minute=45))[0] == places.REGISTRY['offlicence']
    assert world.routine('Pete Lomax', NOW.replace(hour=14,minute=30))[1] == 'on his delivery round'
    assert world.routine('Kirsty Doyle', NOW.replace(hour=18,minute=15))[0] == places.REGISTRY['square']
    assert world.routine('Kirsty Doyle', NOW.replace(hour=18,minute=15), {'_weather':{'raining':True}})[0] != places.REGISTRY['square']
    assert world.routine('Tommy Shaw', NOW.replace(day=26,hour=20))[0] == world.PUB
