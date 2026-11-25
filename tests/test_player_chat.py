import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from evorium import accounts, db, main, player_chat, world
from evorium.seed import seed_agents

ROB = ('rob', 'owner-test')
THOMAS = ('Thomas', 'tom-test')
PAT = ('Pat', 'pat-test')
CHAT = '/player-chat'


@pytest.fixture
def setup_chat(tmp_path, monkeypatch):
    path = tmp_path / 'chat.sqlite3'
    db.init_db(path)
    seed_agents(path)
    clock = [time.time()]
    monkeypatch.setattr(player_chat, 'time', SimpleNamespace(time=lambda:clock[0]))
    monkeypatch.setattr(main, 'DEFAULT_DB_PATH', path)
    monkeypatch.setattr(main, 'DASHBOARD_PASSWORD', ROB[1])
    monkeypatch.setattr(main, 'ACCOUNTS', {'Thomas': THOMAS[1], 'Pat': PAT[1]})
    return TestClient(main.app), path, clock


def send(client, auth, peer, text, **extra):
    return client.post(CHAT+'/send', params={'peer':peer}, auth=auth, json={'text':text, **extra})


def thread(client, auth, peer):
    return client.get(CHAT+'/thread', params={'peer':peer}, auth=auth)


def test_private_send_and_fetch_require_auth_and_never_impersonate(setup_chat):
    client, _, clock = setup_chat
    assert client.get(CHAT).status_code == 401
    assert thread(client, None, 'thomas').status_code == 401
    assert send(client, None, 'thomas', 'hello').status_code == 401
    assert send(client, ROB, 'thomas', 'forged', sender='pat').status_code == 422
    assert send(client, ROB, 'thomas', 'forged', recipient='pat').status_code == 422
    assert send(client, ROB, 'owner', 'self').status_code == 404
    assert send(client, ROB, 'dez', 'APC').status_code == 404
    response = send(client, ROB, 'THOMAS', '  Private tea <b>plan</b>  ')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'private, no-store'
    first = response.json()
    assert (first['sender'],first['recipient'],first['text']) == ('owner','thomas','Private tea <b>plan</b>')
    assert thread(client, PAT, 'thomas').json() == []
    assert thread(client, PAT, 'owner').json() == []
    outsider = client.get(CHAT, params={'after':0}, auth=PAT).json()
    assert outsider['messages'] == outsider['unread'] == []
    assert client.post(CHAT+'/read', params={'peer':'owner'}, auth=PAT, json={'through':first['id']}).status_code == 200
    assert client.get(CHAT,auth=THOMAS).json()['unread'] == [first]
    second = send(client, THOMAS, 'owner', 'My reply').json()
    assert second['id'] > first['id']
    for who, peer in [(ROB,'thomas'),(THOMAS,'owner')]:
        assert thread(client, who, peer).json() == [first, second]
        reply = client.get(CHAT, params={'after':first['id']}, auth=who).json()
        assert reply['messages'] == [second]
        assert reply['cursor'] == second['id']


def test_offline_delivery_and_read_receipts_are_recipient_scoped(setup_chat):
    client, path, clock = setup_chat
    with db.connect(path) as c:
        assert not c.execute("SELECT 1 FROM agents WHERE account='thomas'").fetchone()
        events = c.execute('SELECT count(*) FROM timeline').fetchone()[0]
        facts = c.execute('SELECT count(*) FROM facts').fetchone()[0]
    # The recipient hasn't used the world yet.
    response = send(client, ROB, 'thomas', 'Offline message 4bef4')
    assert response.status_code == 200
    message = response.json()
    inbox = client.get(CHAT, auth=THOMAS)
    assert inbox.headers['cache-control'] == 'private, no-store'
    assert inbox.json()['unread'] == [message]
    assert inbox.json()['messages'] == []
    assert inbox.json()['cursor'] == message['id']
    assert client.post(CHAT+'/read', params={'peer':'thomas'}, auth=ROB, json={'through':message['id']}).status_code == 200
    assert client.get(CHAT, auth=THOMAS).json()['unread'] == [message]
    assert client.post(CHAT+'/read', params={'peer':'owner'}, auth=THOMAS, json={'through':message['id']}).status_code == 200
    assert client.get(CHAT, auth=THOMAS).json()['unread'] == []
    assert thread(client, THOMAS, 'owner').json()[0]['read_at'] == clock[0]

    for url in ['/world/scene','/events','/timeline','/conversations/latest','/player','/agents']:
        response = client.get(url, auth=PAT)
        assert response.is_success and '4bef4' not in response.text
    with db.connect(path) as c:
        assert c.execute('SELECT count(*) FROM llm_calls').fetchone()[0] == 0
        assert c.execute('SELECT count(*) FROM conversations').fetchone()[0] == 0
        assert c.execute('SELECT count(*) FROM timeline').fetchone()[0] == events
        assert c.execute('SELECT count(*) FROM facts').fetchone()[0] == facts


def test_rate_limit_is_per_account_and_speech_snapshot_contains_no_text(setup_chat):
    client, path, clock = setup_chat
    for text in ['', '   ', 'x'*301]:
        assert send(client, ROB, 'thomas', text).status_code == 422
    for auth, account in [(ROB,'owner'),(THOMAS,'thomas')]:
        assert client.get('/me',auth=auth).status_code == 200
        world.set_setting(accounts.setting_key('player_place',account),'pub',path)
    body = 'keep this private ' + 'x'*282
    original=send(client, ROB, 'thomas', body)
    assert original.status_code == 200 and original.json()['nearby_place'] == 'pub'
    assert send(client, ROB, 'pat', 'different recipient').status_code == 429
    assert send(client, THOMAS, 'owner', 'Different sender').status_code == 200
    public=client.get('/world/scene',auth=PAT).json()
    speakers={p['account']:p for p in public['characters'] if p['kind']=='player'}
    assert speakers['owner']['speaking_at'] == clock[0]
    assert speakers['thomas']['speaking_at'] == clock[0]
    assert body not in str(public)
    clock[0] += .9
    assert send(client, ROB, 'pat', 'too soon').status_code == 429
    clock[0] += .2
    assert send(client, ROB, 'pat', 'next second').status_code == 200


def test_append_only_migration_on_version_20_world_copy(tmp_path, monkeypatch):
    old, copy = tmp_path/'old.sqlite3', tmp_path/'copy.sqlite3'
    with monkeypatch.context() as previous:
        previous.setattr(db,'MIGRATIONS',db.MIGRATIONS[:20])
        db.init_db(old)
        seed_agents(old)
    with db.connect(old) as source, db.connect(copy) as target:
        assert source.execute('PRAGMA user_version').fetchone()[0] == 20
        source.backup(target)
        agents = source.execute('SELECT * FROM agents ORDER BY id').fetchall()
    for _ in range(2):
        db.init_db(copy)
        with db.connect(copy) as c:
            assert c.execute('PRAGMA user_version').fetchone()[0] == 21
            assert c.execute('SELECT * FROM agents ORDER BY id').fetchall() == agents
            assert c.execute('SELECT count(*) FROM player_chat').fetchone()[0] == 0
    with db.connect(old) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0] == 20
