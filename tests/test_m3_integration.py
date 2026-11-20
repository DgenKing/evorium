from evorium.seed import CHARACTERS
"""End-to-end routes and migration preservation; no model/network requests."""
import sqlite3
from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from evorium import main, world, player, timeline, tick
from evorium.db import init_db,connect,MIGRATIONS,npc_agents
from evorium.seed import seed_agents
from evorium.models import ActionProposal,Extraction

class Fake:
    def propose(self,aid,messages,schema=ActionProposal,max_tokens=300):
        if schema is Extraction:return Extraction(summary='Sam talked to Dez about bicycles.',per_agent={
            'Dez Whitworth':{'facts':[{'subject':'player','content':'Sam repairs bicycles.','source':'told','told_by':'Sam'}]},
            'Sam':{'commitments':[{'content':'Bring darts','to':'Dez Whitworth'}]}})
        return ActionProposal(say='Bring your darts along.',rationale='Welcoming a neighbour.',mood='friendly')

@pytest.fixture
def api(tmp_path,monkeypatch):
    path=tmp_path/'world.sqlite3';init_db(path);seed_agents(path)
    monkeypatch.setattr(main,'DEFAULT_DB_PATH',path)
    monkeypatch.setattr(main,'DASHBOARD_PASSWORD','')
    monkeypatch.setattr(main,'DeepSeekClient',lambda *a:Fake())
    monkeypatch.setattr(main,'DeferredClient',lambda *a:Fake())
    monkeypatch.setattr(world,'now',lambda *a:datetime(2026,11,17,20))
    tick.update_routines(world.now(),path)
    return TestClient(main.app),path


def test_routes_full_player_exchange(api):
    client,path=api
    assert len(client.get('/agents').json())==len(CHARACTERS)
    assert client.post('/player/profile',json={'name':'Sam','about':'Neighbour'}).status_code==200
    assert client.post('/player/enter',json={'place':'shop'}).status_code==409
    assert client.post('/player/enter',json={'place':'pub'}).status_code==200
    for text in ['I repair bicycles.','I will bring darts tomorrow.']:
        assert client.post('/player/say',json={'to_agent_id':1,'text':text}).status_code==200
    assert client.post('/player/end').status_code==200
    state=client.get('/player').json()
    assert state['conversation'] is None
    assert client.post('/player/promises/'+str(state['promises'][0]['id']),json={'done':True,'note':'Brought them.'}).status_code==200
    with connect(path) as c:
        assert c.execute("SELECT count(*) FROM facts WHERE agent_id=1 AND source='told' AND source_agent_id=?",(state['id'],)).fetchone()[0]==1
        assert c.execute("SELECT count(*) FROM timeline WHERE kind='conversation'").fetchone()[0]==1
    assert client.get('/timeline').json()['days']
    assert client.post('/director',json={'enabled':False}).status_code==200
    assert world.get_setting('director','1',path)=='0'
    assert client.post('/player/leave').json()['place']==''


def test_say_validation_limit_and_idle_close(api):
    client,path=api
    client.post('/player/enter',json={'place':'pub'})
    for text in ['   ','x'*501]:assert client.post('/player/say',json={'to_agent_id':1,'text':text}).status_code==409
    client.post('/player/say',json={'to_agent_id':1,'text':'Hello'})
    state=client.get('/player').json();cid=state['conversation']['id']
    with connect(path) as c:
        for _ in range(38):c.execute("INSERT INTO messages(conversation_id,speaker_id,text,rationale,sim_time) VALUES (?,?,'a','(player)','now')",(cid,state['id']))
    assert client.post('/player/say',json={'to_agent_id':1,'text':'Hello'}).status_code==409
    with connect(path) as c:c.execute("UPDATE messages SET created_at='2020-01-01T00:00:00Z' WHERE conversation_id=?",(cid,))
    player.maintenance(Fake(),world.now(),path)
    assert client.get('/player').json()['conversation'] is None


def test_migration_from_version_three_preserves_state(tmp_path):
    path=tmp_path/'old.sqlite3'
    c=sqlite3.connect(path)
    for migration in MIGRATIONS[:3]:
        for statement in migration:c.execute(statement)
    c.execute('PRAGMA user_version=3')
    c.execute("INSERT INTO agents(name,age,occupation,background,personality,current_goal,mood,location) VALUES ('Saved neighbour',42,'Work','History','Dry','Keep going','calm','Home')")
    c.execute("INSERT INTO conversations(location,status,summary,agent_a_id) VALUES ('pub','completed','An earlier conversation.',1)")
    c.execute("INSERT INTO scheduled_events(at,agent_id,subject,content,seed_key) VALUES ('2026-11-19 09:00',1,'lease','Pending letter','saved-event')")
    c.commit();c.close()
    init_db(path);seed_agents(path);init_db(path);seed_agents(path)
    with connect(path) as c:
        assert c.execute('select summary from conversations where id=1').fetchone()[0]=='An earlier conversation.'
        assert tuple(c.execute("select at,delivered,origin from scheduled_events where seed_key='saved-event'").fetchone())==('2026-11-19 09:00',0,'seed')
        assert c.execute("select mood from agents where name='Saved neighbour'").fetchone()[0]=='calm'
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


def test_lifespan_closes_orphan_with_fake_notes(api,monkeypatch):
    client,path=api
    client.post('/player/profile',json={'name':'Sam','about':''})
    client.post('/player/enter',json={'place':'pub'})
    client.post('/player/say',json={'to_agent_id':1,'text':'Hello'})
    cid=client.get('/player').json()['conversation']['id']
    monkeypatch.setattr(main,'_tick_loop',lambda:None)
    with TestClient(main.app) as started:
        assert started.get('/player').json()['conversation'] is None
    with connect(path) as c:assert c.execute('select status from conversations where id=?',(cid,)).fetchone()[0]=='completed'


@pytest.mark.parametrize('hour,expect_shop',[(9,True),(8,False),(20,False)])
def test_auto_shop_encounters_need_two_present(api,monkeypatch,hour,expect_shop):
    client,path=api
    now=datetime(2026,11,17,hour)
    monkeypatch.setattr(world,'now',lambda *a:now)
    from evorium.plans import DailyPlans
    from evorium.timeline import Digest
    from evorium.director import Proposal
    class AutoFake(Fake):
        def propose(self,aid,messages,schema=ActionProposal,max_tokens=300):
            if schema is DailyPlans:return DailyPlans(plans=[])
            if schema is Digest:return Digest(digest='Neighbours talked about the pub.')
            if schema is Proposal:return Proposal.model_validate({'type':'small_incident','for':'Dez Whitworth','content':'You find a barrel has gone off.','in_hours':2,'rationale':'An ordinary problem.'})
            return super().propose(aid,messages,schema,max_tokens)
    class Once:
        stopped=False
        def is_set(self):return self.stopped
        def wait(self,*a):self.stopped=True
    state=dict(main._state,auto=True,stop=Once(),conversations=0)
    monkeypatch.setattr(main,'_state',state)
    monkeypatch.setattr(main,'DeepSeekClient',lambda *a:AutoFake())
    main._tick_loop()
    with connect(path) as c:
        rows=c.execute("select id from conversations where location=? and status='completed'",("Patel's News, Ancoats",)).fetchall()
        assert bool(rows)==expect_shop
        # First time this pair has talked, so it gets the longer story-length conversation.
        if rows:assert c.execute('select count(*) from messages where conversation_id=?',(rows[0][0],)).fetchone()[0]==6
