from datetime import datetime, timedelta
import pytest
from fastapi import HTTPException
from evorium import player, world, tick, sim
from evorium.db import connect, init_db
from evorium.seed import seed_agents
from evorium.models import Extraction, ActionProposal
from evorium.llm import InvalidProposal

class Fake:
    def __init__(self,extraction=None):self.extraction=extraction;self.calls=[]
    def propose(self,agent_id,messages,schema=ActionProposal,max_tokens=300):
        self.calls.append((schema,messages))
        if schema is Extraction:return self.extraction or Extraction(summary='Stranger talked to Dez.')
        return ActionProposal(say='Good to meet you.',rationale='Welcoming a new face.',mood='friendly')

@pytest.fixture
def db(tmp_path,monkeypatch):
    path=tmp_path/'world.sqlite3';init_db(path);seed_agents(path)
    monkeypatch.setattr(world,'now',lambda *a:datetime(2026,11,16,20))
    tick.update_routines(world.now(),path)
    return path


def test_player_reply_close_and_attributed_knowledge(db):
    client=Fake(Extraction(summary='Stranger likes darts.',per_agent={'Dez Whitworth':{'facts':[{'subject':'darts','content':'Stranger likes darts.','source':'told','told_by':'Stranger'}]},'Stranger':{'commitments':[{'content':'Bring darts','to':'Dez Whitworth'}],'facts':[{'subject':'pub','content':'Dez runs the pub.','source':'told','told_by':'Dez Whitworth'}]}}))
    player.enter(client,'pub',db)
    result=player.say(client,1,'I like darts.',db)
    assert len(sim.get_conversation(result['conversation_id'],db)['messages'])==2
    assert 'Do not assume anything else' in client.calls[0][1][0]['content']
    with pytest.raises(HTTPException) as e:player.profile('Sam','',db)
    assert e.value.status_code==409
    player.close(client,db)
    data=player.state(db)
    assert data['conversation'] is None and data['learned'] and data['promises']
    with connect(db) as c:
        f=c.execute("SELECT * FROM facts WHERE agent_id=1 AND source='told'").fetchone()
        assert f['source_agent_id']==data['id']
    player.resolve(data['promises'][0]['id'],True,'Brought them.',db)
    with connect(db) as c:assert c.execute("SELECT 1 FROM facts WHERE agent_id=1 AND subject='promise'").fetchone()


def test_missing_busy_and_pair_reservation(db):
    client=Fake();player.enter(client,'pub',db)
    with pytest.raises(HTTPException) as e:player.say(client,2,'Hello',db)
    assert e.value.status_code==409
    with connect(db) as c:
        cid=c.execute("INSERT INTO conversations(location,status,agent_a_id,agent_b_id) VALUES ('pub','running',1,4)").lastrowid
    with pytest.raises(HTTPException,match='talking to Jess'):player.say(client,1,'Hello',db)
    with connect(db) as c:c.execute("UPDATE conversations SET status='completed' WHERE id=?",(cid,))
    player.say(client,1,'Hello',db)
    assert 1 not in world.pick_pair([1,3,4],db)


def test_startup_closes_and_overdue_human_promises(db):
    client=Fake();player.enter(client,'pub',db);result=player.say(client,1,'Hello',db)
    assert sim.mark_interrupted(db)==0
    me=player.state(db)['id']
    with connect(db) as c:c.execute("INSERT INTO commitments(agent_id,to_agent_id,content,due_at) VALUES (?,1,'Bring darts','2026-11-15 19:00')",(me,))
    class NoModel:
        def propose(self,*a,**k):pytest.fail('Human promise must not ask model')
    tick.check_due_promises(NoModel(),world.now(),db)
    player.maintenance(client,world.now(),db,startup=True)
    assert sim.get_conversation(result['conversation_id'],db)['status']=='completed'
    with connect(db) as c:
        assert c.execute('SELECT status,outcome FROM commitments').fetchone()[:]==('broken','Never heard back.')
        assert me not in [a['id'] for a in tick._agents(c)]


def test_invalid_reply_keeps_human_line(db):
    class Bad(Fake):
        def propose(self,*a,**k):raise InvalidProposal('bad')
    player.enter(Fake(),'pub',db)
    with pytest.raises(HTTPException) as e:player.say(Bad(),1,'Hello',db)
    assert e.value.status_code==502
    assert len(player.state(db)['conversation']['messages'])==1


def test_profile_and_closed_place(db):
    for name in ['Dez','dez whitworth','x','World']:
        with pytest.raises(HTTPException):player.profile(name,'',db)
    assert player.profile('Sam','Neighbour',db)['name']=='Sam'
    with pytest.raises(HTTPException):player.enter(Fake(),'shop',db)
