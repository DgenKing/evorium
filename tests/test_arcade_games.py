
import pytest
from fastapi.testclient import TestClient

from evorium import arcade_games, main
from evorium.arcade import LAYOUT, NORMAN
from evorium.db import MIGRATIONS, connect, init_db
from evorium.seed import seed_agents


@pytest.fixture
def world_db(tmp_path, monkeypatch):
    path = tmp_path / 'games.sqlite3'
    init_db(path)
    seed_agents(path)
    monkeypatch.setattr(main, 'DEFAULT_DB_PATH', path)
    return path


def test_catalogue_documents_are_served_with_isolation(world_db):
    client = TestClient(main.app)
    catalogue = client.get('/static/games/games.json').json()
    assert len(catalogue) == 5
    assert {row['placement'] for row in catalogue} == {f'cabinet-{i}' for i in range(1,5)} | {'pool-table'}
    for game in catalogue:
        assert game['placement'] in LAYOUT['spots']
        path = arcade_games.GAMES_DIR / game['slug'] / 'index.html'
        assert path.is_file()
        response = client.get('/static/games/'+game['slug']+'/index.html')
        assert response.status_code == 200
        csp = response.headers['content-security-policy']
        for directive in ("sandbox allow-scripts", "default-src 'none'", "connect-src 'none'",
                          "frame-src 'none'", "frame-ancestors 'self'", "form-action 'none'"):
            assert directive in csp
        assert 'allow-same-origin' not in csp
        assert 'evoriumGameScore' in response.text
    assert "frame-src 'self'" in client.get('/world3d').headers['content-security-policy']


def test_score_validation_personal_bests_and_normans_notebook(world_db, monkeypatch):
    monkeypatch.setattr(main, 'DASHBOARD_PASSWORD', 'owner-test')
    monkeypatch.setattr(main, 'ACCOUNTS', {'friend': 'friend-test'})
    client = TestClient(main.app)
    owner = ('owner','owner-test')
    friend = ('friend','friend-test')
    route = '/arcade/scores/'
    assert client.post(route+'1941', json={'score':100}).status_code == 401
    for payload in ({'score':True}, {'score':'100'}, {'score':4.0}, {'score':-1},
                    {'score':2147483648}, {'score':3,'account':'friend'}, {}):
        assert client.post(route+'1941', auth=owner, json=payload).status_code == 422
    assert client.post(route+'fake', auth=owner, json={'score':1}).status_code == 404
    assert client.post(route+'gyro-chaos', auth=owner, json={'score':11}).status_code == 422
    for value, best, improved in [(200,200,True),(100,200,False),(400,400,True)]:
        assert client.post(route+'1941', auth=owner, json={'score':value}).json() == {'best':best,'improved':improved}
    for value, best in [(20,20), (25,20), (17,17)]:
        assert client.post(route+'evorium-darts', auth=owner, json={'score':value}).json()['best'] == best
    assert client.get(route.rstrip('/'),auth=friend).json() == {}
    assert client.post(route+'1941', auth=friend, json={'score':200}).json()['best'] == 200
    assert client.get(route.rstrip('/'),auth=owner).json() == {'1941':400,'evorium-darts':17}
    with connect(world_db) as c:
        notes = [r['content'] for r in c.execute("""SELECT content FROM facts JOIN agents ON agents.id=facts.agent_id
                WHERE name=? AND subject='arcade notebook'""", (NORMAN,))]
    assert len(notes) == 3
    assert any('400 points' in note and '1941' in note for note in notes)
    assert any('17 darts' in note for note in notes)


def test_append_only_migration_preserves_world(monkeypatch, tmp_path):
    import evorium.db as db
    path = tmp_path / 'old.sqlite3'
    with monkeypatch.context() as old:
        old.setattr(db, 'MIGRATIONS', MIGRATIONS[:17])
        init_db(path)
        seed_agents(path)
    with connect(path) as c:
        c.execute("UPDATE agents SET mood='saved mood' WHERE name=?", (NORMAN,))
        assert c.execute('PRAGMA user_version').fetchone()[0] == 17
    init_db(path)
    init_db(path)
    with connect(path) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0] == 18
        assert c.execute('SELECT mood FROM agents WHERE name=?', (NORMAN,)).fetchone()[0] == 'saved mood'
        assert c.execute('SELECT count(*) FROM arcade_scores').fetchone()[0] == 0
        assert c.execute('PRAGMA foreign_key_check').fetchall() == []


def test_floor_guide_lists_exactly_the_catalogue():
    from evorium import arcade_games
    guide = arcade_games.floor_guide()
    for game in arcade_games.GAMES.values():
        assert game['title'] in guide
    assert 'press E' in guide and "haven't got it" in guide


def test_arcade_staff_and_visitors_get_the_floor_guide():
    from evorium.memory import _arcade_guide
    from evorium.place_registry import REGISTRY
    assert 'WHAT IS ACTUALLY HERE' in _arcade_guide({'name': 'Norman Pilling', 'location': 'home'})
    assert 'WHAT IS ACTUALLY HERE' in _arcade_guide({'name': 'Dez Kowalski', 'location': REGISTRY['arcade']})
    assert _arcade_guide({'name': 'Dez Kowalski', 'location': REGISTRY['pub']}) == ''
