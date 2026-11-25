import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

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


def test_round_checks_each_due_place_and_skips_capped_pairs(db, monkeypatch):
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
    assert main._auto_conversations(object(), NOW, None, db) == {4,5,6,7}
    assert captured == ['shop', 'cafe']
    assert main._state['conversations'] == 2
    assert places.conversation_gap('pub') == 8
    assert places.conversation_gap('cafe', override=20) == 20
    assert [key for key,_ in places.opportunities(NOW, db_path=db)] == ['pub']


@pytest.mark.parametrize('notable', [None, 2])
def test_short_hello_uses_arrival_once_and_only_saves_notable_line(db, monkeypatch, notable):
    # Dez and Tommy have seeded familiarity through their relationship.
    group = people(1,3,location=world.STREET)
    group[0]['activity'] = 'heading to the pub'
    monkeypatch.setattr(places, 'present', lambda *_: {'street':group})
    with connect(db) as c:
        world._set(c, 'scene.travel.1', json.dumps({'to':world.STREET,'started':REAL.timestamp()}))
        facts = c.execute('SELECT count(*) FROM facts').fetchone()[0]
    calls = []
    def propose(a, messages, *, schema, max_tokens):
        calls.append(a)
        assert max_tokens == 90 and schema is greetings.Greeting
        return schema(lines=['Morning.', 'Off to the pub.'], notable_line=notable)
    fake = SimpleNamespace(propose=propose)
    assert greetings.run(fake, NOW, db, real_at=REAL)
    assert not greetings.run(fake, NOW, db, real_at=REAL)
    assert calls == [1]
    with connect(db) as c:
        settings = dict(c.execute('SELECT key,value FROM world'))
        lines = greetings.active(settings, REAL)
        assert [(line['id'], line['text']) for line in lines] == [(1,'Morning.'), (3,'Off to the pub.')]
        assert not greetings.active(settings, REAL+timedelta(seconds=10))
        assert c.execute('SELECT count(*) FROM conversations').fetchone()[0] == 0
        assert c.execute('SELECT count(*) FROM facts').fetchone()[0] == facts + bool(notable)


@pytest.mark.parametrize('lines', [[], ['one','two','three'], ['one\ntwo'], ['a'*97]])
def test_greeting_rejects_long_or_multiline_output(lines):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        greetings.Greeting(lines=lines)
