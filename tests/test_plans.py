from datetime import datetime,timedelta
import pytest
from evorium import world,places,plans,tick
from evorium.db import connect,init_db
from evorium.seed import seed_agents
from evorium.models import ActionProposal,Extraction
from evorium.sim import get_conversation

@pytest.fixture
def db(tmp_path):
    p=tmp_path/'w.sqlite3';init_db(p);seed_agents(p);return p


def agent(db,aid):
    with connect(db) as c:return dict(c.execute('select * from agents where id=?',(aid,)).fetchone())


def proposal(**kw):
    return dict(action='visit',place='shop',person=None,hour=10,minute=0,duration_minutes=30,fulfils=None,reason='Buy a paper.',**kw) if not kw else {**proposal(),**kw}

@pytest.mark.parametrize('aid,change',[
    (2,{}),(3,{'place':'private'}),(3,{'hour':6}),(3,{'hour':18,'duration_minutes':120}),
    (3,{'action':'phone','person':'Tommy Shaw'}),(3,{'action':'phone','person':'Nobody'}),
    (3,{'action':'stay_home','hour':10}),(1,{'action':'stay_home','hour':20}),
    (3,{'minute':15}),(3,{'duration_minutes':200}),
])
def test_invalid_plans(db,aid,change):
    with pytest.raises(ValueError):plans.validate(proposal(**change),agent(db,aid),datetime(2026,11,16,8),db)


def test_visit_overrides_then_reverts_and_bounds(db):
    now=datetime(2026,11,16,8);a=agent(db,3)
    p=plans.validate(proposal(fulfils=999),a,now,db);assert p['fulfils_commitment_id'] is None
    with connect(db) as c:plans.insert(c,p)
    plans.execute(None,now.replace(hour=10),db)
    assert world.whereabouts(a,now.replace(hour=10,minute=10),db)[0]==places.REGISTRY['shop']
    assert {r['id'] for r in places.present(now.replace(hour=10,minute=10),db)['shop']}=={3,5}
    plans.execute(None,now.replace(hour=11),db)
    assert world.whereabouts(a,now.replace(hour=11),db)==world.routine(a['name'],now.replace(hour=11))
    with connect(db) as c:assert c.execute('select status from plans').fetchone()[0]=='done'


class Fake:
    calls=[]
    def propose(self,aid,messages,schema=ActionProposal,max_tokens=300):
        self.calls.append(schema)
        if schema is plans.DailyPlans:return schema(plans=[])
        if schema is Extraction:return schema(summary='Tommy rang Dez about the quiz.')
        return ActionProposal(say='I have written the quiz.',rationale='Reporting back.',mood='happy')


def test_phone_resolves_promise_and_location(db,monkeypatch):
    now=datetime(2026,11,16,8);a=agent(db,3)
    with connect(db) as c:cid=c.execute("INSERT INTO commitments(agent_id,to_agent_id,content) VALUES (3,1,'Ring Dez')").lastrowid
    p=plans.validate(proposal(action='phone',person='Dez Whitworth',hour=14,fulfils=cid),a,now,db)
    with connect(db) as c:plans.insert(c,p)
    monkeypatch.setattr(world,'now',lambda *args:now.replace(hour=14))
    client=Fake();plans.execute(client,world.now(),db,auto=True)
    with connect(db) as c:
        assert c.execute('select status from plans').fetchone()[0]=='done'
        assert c.execute('select status from commitments').fetchone()[0]=='done'
        conv=c.execute('select * from conversations').fetchone();assert conv['location']=='On the phone'


def test_phone_retries_once(db):
    now=datetime(2026,11,16,8);a=agent(db,3)
    p=plans.validate(proposal(action='phone',person='Dez Whitworth',hour=10),a,now,db)
    with connect(db) as c:
        plans.insert(c,p)
        c.execute("insert into conversations(location,status,agent_a_id,agent_b_id) values ('pub','running',1,4)")
    plans.execute(Fake(),now.replace(hour=10),db,auto=True)
    with connect(db) as c:
        r=c.execute('select * from plans').fetchone();assert r['attempts']==1 and r['status']=='planned'
    plans.execute(Fake(),now.replace(hour=10,minute=29),db,auto=True)
    plans.execute(Fake(),now.replace(hour=10,minute=30),db,auto=True)
    with connect(db) as c:assert tuple(c.execute('select status,outcome from plans').fetchone())==('missed','No answer.')


def test_planning_once_daily_and_per_place_gap(db):
    now=datetime(2026,11,16,8);client=Fake();client.calls=[]
    assert plans.daily(client,now,db)==5
    assert plans.daily(client,now+timedelta(hours=1),db)==0
    assert len(client.calls)==5
    with connect(db) as c:
        c.execute("insert into conversations(location,status,agent_a_id,agent_b_id,sim_at) values (?,'completed',1,3,?)",(world.PUB,now.strftime('%Y-%m-%d %H:%M')))
    assert not tick.conversation_due(now,20,db,world.PUB)
    assert tick.conversation_due(now,20,db,places.REGISTRY['shop'])
    assert not places.present(now.replace(hour=20),db)['shop']
