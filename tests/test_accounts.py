"""Accounts v1 against isolated worlds and fake model replies only."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from evorium import accounts, backoff, catchup, main, player, scene, sim, tick, world
from evorium.db import MIGRATIONS, connect, init_db
from evorium.models import ActionProposal, Extraction
from evorium.seed import seed_agents

NOW = datetime(2026, 11, 19, 18)
OWNER = ('any-name', 'test-owner-pass')
THOMAS = ('Thomas', 'test-friend-pass')


@contextmanager
def as_account(name):
    token = accounts.current.set(name)
    try:
        yield
    finally:
        accounts.current.reset(token)


class Fake:
    def propose(self, aid, messages, schema=ActionProposal, max_tokens=300):
        if schema is catchup.Previously:
            return schema(text='Offline account-specific catch-up.')
        if schema is Extraction:
            participant = messages[0]['content'].split('\nCONVERSATION:\n', 1)[1].split(':', 1)[0]
            notes = {
                name: {'facts': [{'subject': 'quiz', 'content': name + ' learned the quiz is Thursday.', 'source': 'told', 'told_by': 'Dez Whitworth'}],
                       'commitments': [{'content': 'Bring a quiz pencil', 'to': 'Dez Whitworth'}]}
                for name in ('Rob', 'Thomas')}
            notes['Dez Whitworth'] = {'facts': [{'subject': 'neighbour', 'content': participant + ' repairs bicycles.', 'source': 'told', 'told_by': participant}]}
            return Extraction(summary='Offline neighbours talked.', per_agent=notes)
        return ActionProposal(say='Hello neighbour.', rationale='Offline test.', mood='friendly')


@pytest.fixture
def api(tmp_path, monkeypatch):
    path = tmp_path / 'accounts.sqlite3'
    init_db(path)
    seed_agents(path)
    with connect(path) as c:
        c.execute("UPDATE agents SET name='Rob' WHERE account='owner'")
        for key, value in {'speed': '0', 'anchor_real': NOW.strftime(world.FMT), 'anchor_sim': NOW.strftime(world.FMT)}.items():
            world._set(c, key, value)
        owner_id = player.row(c)['id']
    tick.update_routines(NOW, path)
    monkeypatch.setattr(main, 'DEFAULT_DB_PATH', path)
    monkeypatch.setattr(main, 'DASHBOARD_PASSWORD', OWNER[1])
    monkeypatch.setattr(main, 'ACCOUNTS', {THOMAS[0]: THOMAS[1]})
    monkeypatch.setattr(main, 'DeferredClient', lambda *a: Fake())
    monkeypatch.setattr(world, 'now', lambda *a: NOW)
    return TestClient(main.app), path, owner_id


def get(client, path, auth=OWNER):
    result = client.get(path, auth=auth)
    assert result.status_code == 200, result.text
    return result.json()


def post(client, path, auth=OWNER, **body):
    return client.post(path, auth=auth, json=body)


def test_login_precedence_casefold_and_sync_context(api):
    client, path, owner_id = api
    assert get(client, '/me') == {'account': 'owner', 'name': 'Rob'}
    assert get(client, '/me', THOMAS) == {'account': 'thomas', 'name': 'Thomas'}
    assert get(client, '/me', ('tHoMaS', THOMAS[1]))['account'] == 'thomas'
    assert get(client, '/me', ('Thomas', OWNER[1]))['account'] == 'owner'
    assert get(client, '/player', THOMAS)['id'] != owner_id
    assert get(client, '/player')['id'] == owner_id
    for credentials in [('unknown', THOMAS[1]), ('Thomas', 'test-wrong-pass'), ('any', '')]:
        assert client.get('/me', auth=credentials).status_code == 401
    assert client.get('/me').status_code == 401
    # Identity is reset outside the middleware, including after rejected requests.
    assert accounts.current.get() == 'owner'
    with connect(path) as c:
        assert c.execute("SELECT count(*) FROM agents WHERE account='thomas'").fetchone()[0] == 1


def test_first_static_request_provisions_once_even_concurrently(api):
    client, path, _ = api
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(lambda _: client.get('/game', auth=THOMAS).status_code, range(8))) == [200] * 8
    with connect(path) as c:
        who = dict(c.execute("SELECT * FROM agents WHERE account='thomas'").fetchone())
        assert who['name'] == 'Thomas'
        assert who['occupation'] == 'New face in Ancoats'
        assert who['location'] == 'Not in the world'
        assert c.execute("SELECT count(*) FROM agents WHERE account='thomas'").fetchone()[0] == 1


def test_named_only_auth_and_local_development(api, monkeypatch):
    client, path, _ = api
    monkeypatch.setattr(main, 'DASHBOARD_PASSWORD', '')
    assert client.get('/me').status_code == 401
    assert get(client, '/me', THOMAS)['account'] == 'thomas'
    monkeypatch.setattr(main, 'ACCOUNTS', {})
    assert client.get('/me').json() == {'account': 'owner', 'name': 'Rob'}


def test_places_profiles_and_other_player_visibility(api):
    client, path, owner_id = api
    thomas_id = get(client, '/player', THOMAS)['id']
    assert post(client, '/player/enter', place='pub').status_code == 200
    assert post(client, '/player/enter', THOMAS, place='shop').status_code == 200
    assert get(client, '/player')['place'] == 'pub'
    assert get(client, '/player', THOMAS)['place'] == 'shop'
    owner_scene = get(client, '/world/scene')
    friend_scene = get(client, '/world/scene', THOMAS)
    assert owner_scene['player']['id'] == owner_id
    assert friend_scene['player']['id'] == thomas_id
    assert owner_scene['player']['place'] == 'pub'
    assert friend_scene['player']['place'] == 'shop'
    other = next(a for a in owner_scene['characters'] if a['kind'] == 'player')
    assert other['id'] == thomas_id and other['name'] == 'Thomas' and other['place'] == 'shop'
    assert other['portrait'] is None and other['visible']
    assert next(a for a in friend_scene['characters'] if a['kind'] == 'player')['id'] == owner_id
    assert get(client, '/player')['other_players'][0]['id'] == thomas_id
    for name in ('Dez', 'Dez Whitworth', 'Dez Smith', 'Rob Green', 'rOb'):
        assert post(client, '/player/profile', THOMAS, name=name).status_code == 409
    assert post(client, '/player/profile', THOMAS, name='Thomas Green', about='Neighbour').status_code == 200
    assert get(client, '/me', THOMAS)['name'] == 'Thomas Green'
    assert get(client, '/player')['name'] == 'Rob'
    assert post(client, '/player/leave', THOMAS).status_code == 200
    assert not any(a['kind'] == 'player' for a in get(client, '/world/scene')['characters'])
    assert get(client, '/player')['place'] == 'pub'
    before = path.read_bytes()
    scene.snapshot(path)
    assert path.read_bytes() == before  # rendering itself still opens SQLite read-only


def test_account_name_cannot_clash_with_apc(api, monkeypatch):
    client, path, _ = api
    monkeypatch.setattr(main, 'ACCOUNTS', {'Dez': 'test-dez-pass'})
    who = get(client, '/me', ('dez', 'test-dez-pass'))
    assert who['name'].startswith('Player1 — Dez')
    assert who['account'] == 'dez'


def test_separate_chats_facts_promises_and_reputation(api):
    client, path, owner_id = api
    thomas_id = get(client, '/player', THOMAS)['id']
    for auth in (OWNER, THOMAS):
        assert post(client, '/player/enter', auth, place='pub').status_code == 200
    assert post(client, '/player/say', to_agent_id=1, text='Hello from Rob.').status_code == 200
    owner_cid = get(client, '/player')['conversation']['id']
    response = post(client, '/player/say', THOMAS, to_agent_id=1, text='Hello from Thomas.')
    assert response.status_code == 409
    assert response.json()['detail'] == 'Dez is talking to Rob at the moment.'
    # The second player can independently speak to somebody else.
    assert post(client, '/player/say', THOMAS, to_agent_id=3, text='Hello Tommy.').status_code == 200
    friend_cid = get(client, '/player', THOMAS)['conversation']['id']
    assert friend_cid != owner_cid
    assert get(client, '/player')['conversation']['id'] == owner_cid
    assert post(client, '/player/end', THOMAS).status_code == 200
    assert get(client, '/player')['conversation']['id'] == owner_cid
    assert post(client, '/player/end').status_code == 200
    owner = get(client, '/player')
    friend = get(client, '/player', THOMAS)
    assert owner['learned'][0]['content'].startswith('Rob ')
    assert friend['learned'][0]['content'].startswith('Thomas ')
    owner_promise = owner['promises'][0]['id']
    friend_promise = friend['promises'][0]['id']
    assert post(client, f'/player/promises/{owner_promise}', THOMAS, done=True).status_code == 409
    assert post(client, f'/player/promises/{friend_promise}', THOMAS, done=True).status_code == 200
    assert get(client, '/player')['promises'][0]['id'] == owner_promise
    with connect(path) as c:
        trust = {r['other_id']: r['trust'] for r in c.execute('SELECT * FROM relationships WHERE agent_id=1 AND other_id IN (?,?)', (owner_id, thomas_id))}
        assert trust[thomas_id] == trust[owner_id] + 8
        assert c.execute('SELECT count(*) FROM llm_calls').fetchone()[0] == 0
    # Another player cannot be an APC chat target.
    assert post(client, '/player/say', to_agent_id=thomas_id, text='Hello.').status_code == 409


def test_busy_timeout_and_world_pair_selection(api):
    client, path, _ = api
    for auth in (OWNER, THOMAS):
        post(client, '/player/enter', auth, place='pub')
    post(client, '/player/say', THOMAS, to_agent_id=1, text='Hello.')
    busy = post(client, '/player/say', to_agent_id=1, text='Hello.')
    assert busy.status_code == 409 and 'Thomas' in busy.json()['detail']
    with pytest.raises(ValueError):
        world.pick_pair([1, 3], path)
    assert sim.mark_interrupted(path) == 0
    with connect(path) as c:
        c.execute("UPDATE messages SET created_at=strftime('%Y-%m-%dT%H:%M:%fZ','now','-4 minutes')")
    assert post(client, '/player/say', to_agent_id=1, text='Hello again.').status_code == 200


@pytest.mark.parametrize('startup', [False, True])
def test_maintenance_handles_all_players_and_restores_context(api, startup):
    client, path, _ = api
    for auth, aid in ((OWNER, 1), (THOMAS, 3)):
        post(client, '/player/enter', auth, place='pub')
        post(client, '/player/say', auth, to_agent_id=aid, text='Hello.')
    with connect(path) as c:
        if not startup:
            c.execute("UPDATE messages SET created_at='2020-01-01T00:00:00Z'")
        else:
            # Recover every orphan, even if an old version left two open chats for one player.
            c.execute("""INSERT INTO conversations(location,status,agent_a_id,agent_b_id)
                SELECT 'pub','running',id,1 FROM agents WHERE kind='player'""")
        c.execute("""INSERT INTO commitments(agent_id,content,due_at)
            SELECT id,'Old unkept promise','2020-01-01 00:00:00' FROM agents WHERE kind='player'""")
    with as_account('thomas'):
        player.maintenance(Fake(), NOW, path, startup=startup)
        assert accounts.current.get() == 'thomas'
    for auth in (OWNER, THOMAS):
        assert get(client, '/player', auth)['conversation'] is None
    with connect(path) as c:
        assert c.execute("SELECT count(*) FROM commitments WHERE content='Old unkept promise' AND status='broken'").fetchone()[0] == 2
        assert c.execute("SELECT count(*) FROM conversations WHERE status='running'").fetchone()[0] == 0


def test_catchup_checkpoints_gossip_cache_and_budget_are_per_account(api, monkeypatch):
    client, path, _ = api
    get(client, '/player', THOMAS)
    from types import SimpleNamespace
    monkeypatch.setattr(catchup, 'load', lambda: SimpleNamespace(CATCHUP_COOLDOWN_SECONDS=600))
    for account in ('owner', 'thomas'):
        with as_account(account):
            catchup.seen(NOW - timedelta(hours=4), path)
    with connect(path) as c:
        for content in ['Rob helped the neighbours.', 'Thomas helped the neighbours.', 'There are problems on the street.']:
            c.execute("INSERT INTO facts(agent_id,subject,content,source,importance) VALUES (1,'news',?,'observed',4)", (content,))
        for i in range(3):
            c.execute("INSERT INTO timeline(sim_at,kind,text,importance) VALUES (?,'event',?,4)", ((NOW-timedelta(hours=1)).strftime(world.FMT), f'World event {i}'))
    owner = get(client, '/catchup')
    friend = get(client, '/catchup', THOMAS)
    assert [x['content'] for x in owner['gossip']] == ['Rob helped the neighbours.']
    assert [x['content'] for x in friend['gossip']] == ['Thomas helped the neighbours.']
    assert owner['paragraph'] and friend['paragraph']
    with connect(path) as c:
        keys = [json.loads(r[0])[0] for r in c.execute('SELECT cache_key FROM catchup_cache')]
        assert sorted(keys) == ['owner', 'thomas']
        assert world._get(c, 'catchup_fact_checkpoint') == world._get(c, 'catchup_fact_checkpoint:thomas')
    assert post(client, '/catchup/seen', THOMAS).status_code == 200
    assert not get(client, '/catchup', THOMAS)['gossip']
    assert get(client, '/catchup')['gossip']
    with connect(path) as c:
        owner_seen = c.execute("SELECT last_seen_at FROM agents WHERE account='owner'").fetchone()[0]
        friend_seen = c.execute("SELECT last_seen_at FROM agents WHERE account='thomas'").fetchone()[0]
        assert owner_seen != friend_seen


def test_migration_14_preserves_every_existing_row(api, tmp_path):
    client, source, owner_id = api
    post(client, '/player/enter', place='pub')
    post(client, '/player/say', to_agent_id=1, text='Remember my history.')
    post(client, '/player/end')
    legacy = tmp_path / 'version13.sqlite3'
    with sqlite3.connect(legacy) as old, connect(source) as current:
        for migration in MIGRATIONS[:13]:
            for statement in migration:
                old.execute(statement)
        tables = [r[0] for r in old.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for table in tables:
            columns = [r[1] for r in old.execute(f'PRAGMA table_info({table})')]
            cols = ','.join(columns)
            placeholders = ','.join('?' for _ in columns)
            old.executemany(f'INSERT INTO {table} ({cols}) VALUES ({placeholders})',
                            [tuple(r) for r in current.execute(f'SELECT {cols} FROM {table}')])
        old.execute('PRAGMA user_version=13')
    upgraded = tmp_path / 'version13-copy.sqlite3'
    with sqlite3.connect(legacy) as old, sqlite3.connect(upgraded) as copy:
        old.backup(copy)
    init_db(upgraded)
    init_db(upgraded)
    with connect(legacy) as old, connect(upgraded) as new:
        for table in tables:
            columns = ','.join(r['name'] for r in old.execute(f'PRAGMA table_info({table})'))
            assert [tuple(r) for r in new.execute(f'SELECT {columns} FROM {table} ORDER BY rowid')] == [tuple(r) for r in old.execute(f'SELECT * FROM {table} ORDER BY rowid')]
        assert new.execute("SELECT id FROM agents WHERE account='owner'").fetchone()[0] == owner_id
        assert new.execute('PRAGMA user_version').fetchone()[0] == len(MIGRATIONS)
        assert new.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not new.execute('PRAGMA foreign_key_check').fetchall()


def test_parallel_requests_do_not_cross_account_context(api):
    client, path, owner_id = api
    thomas_id = get(client, '/player', THOMAS)['id']
    def identity(index):
        auth, expected = (OWNER, owner_id) if index % 2 else (THOMAS, thomas_id)
        return get(client, '/player', auth)['id'] == expected
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(pool.map(identity, range(16)))
    assert accounts.current.get() == 'owner'


def test_apc_memory_attributes_each_human_separately(api):
    client, path, owner_id = api
    thomas_id = get(client, '/player', THOMAS)['id']
    for auth in (OWNER, THOMAS):
        assert post(client, '/player/enter', auth, place='pub').status_code == 200
        assert post(client, '/player/say', auth, to_agent_id=1, text='I repair bicycles.').status_code == 200
        assert post(client, '/player/end', auth).status_code == 200
    with connect(path) as c:
        attributed = {r['source_agent_id']: r['content'] for r in c.execute("SELECT * FROM facts WHERE agent_id=1 AND source='told'")}
        assert attributed[owner_id] == 'Rob repairs bicycles.'
        assert attributed[thomas_id] == 'Thomas repairs bicycles.'
        assert c.execute("SELECT count(*) FROM agents WHERE account='owner'").fetchone()[0] == 1
