from fastapi.testclient import TestClient

from evorium import db, main
from evorium.seed import seed_agents


def test_position_is_private_and_saved_per_account_and_map(tmp_path, monkeypatch):
    path = tmp_path / 'world.sqlite3'
    db.init_db(path)
    seed_agents(path)
    monkeypatch.setattr(main, 'DEFAULT_DB_PATH', path)
    monkeypatch.setattr(main, 'DASHBOARD_PASSWORD', 'owner-test')
    monkeypatch.setattr(main, 'ACCOUNTS', {'friend': 'friend-test'})
    client = TestClient(main.app)
    owner, friend = ('owner', 'owner-test'), ('friend', 'friend-test')
    route = '/player/position'
    city = {'map': 'city', 'x': 6.5, 'y': .05, 'z': -14.25, 'yaw': 1.75}
    kit = dict(city, map='kit', z=2)
    updated = dict(city, x=-7.5, yaw=-1)
    assert client.get(route, params={'map': 'city'}).status_code == 401
    assert client.get(route, params={'map': 'city'}, auth=owner).json() is None
    for payload in [city, kit, updated]:
        assert client.post(route, auth=owner, json=payload).status_code == 204
    assert client.get(route, params={'map': 'city'}, auth=friend).json() is None
    assert client.post(route, auth=friend, json=city).status_code == 204
    assert client.get(route, params={'map': 'city'}, auth=friend).json() == city
    response = client.get(route, params={'map': 'city'}, auth=owner)
    assert response.json() == updated
    assert response.headers['cache-control'] == 'private, no-store'
    assert client.get(route, params={'map': 'kit'}, auth=owner).json() == kit

    for fields in [{'x': 201}, {'z': -151}, {'y': 4}, {'x': True}, {'z': '0'},
                   {'map': 'fake'}, {'yaw': 'NaN'}, {'account': 'friend'}]:
        assert client.post(route, auth=owner, json=dict(city, **fields)).status_code == 422
    assert client.get(route, params={'map': 'city'}, auth=owner).json() == updated
    with db.connect(path) as c:
        c.execute("UPDATE player_positions SET x=201 WHERE account='owner' AND map='city'")
    # A damaged or obsolete checkpoint is returned as absent for the Billet fallback.
    assert client.get(route, params={'map': 'city'}, auth=owner).json() is None


def test_migration_upgrades_a_copy_without_changing_the_existing_world(tmp_path, monkeypatch):
    old = tmp_path / 'previous.sqlite3'
    path = tmp_path / 'copy.sqlite3'
    with monkeypatch.context() as older:
        older.setattr(db, 'MIGRATIONS', db.MIGRATIONS[:19])
        db.init_db(old)
        seed_agents(old)
        with db.connect(old) as c:
            c.execute("""INSERT INTO llm_calls
                         (agent_id, model, input_tokens, output_tokens, est_cost_usd, ok, budget_scope)
                         VALUES (1, 'fake', 100, 30, .000066, 1, 'background')""")
    with db.connect(old) as source, db.connect(path) as copy:
        source.backup(copy)
        agents = copy.execute('SELECT * FROM agents ORDER BY id').fetchall()
        calls = copy.execute('SELECT * FROM llm_calls ORDER BY id').fetchall()
        assert copy.execute('PRAGMA user_version').fetchone()[0] == 19
    for _ in range(2):
        db.init_db(path)
        with db.connect(path) as c:
            assert c.execute('PRAGMA user_version').fetchone()[0] == len(db.MIGRATIONS)
            assert c.execute('SELECT * FROM agents ORDER BY id').fetchall() == agents
            assert c.execute('SELECT * FROM llm_calls ORDER BY id').fetchall() == calls
            assert c.execute('SELECT count(*) FROM player_positions').fetchone()[0] == 0
    with db.connect(old) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0] == 19
