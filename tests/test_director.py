from datetime import datetime,timedelta
import pytest
from evorium import director,world,timeline
from evorium.db import init_db,connect
from evorium.seed import seed_agents,seed_events

@pytest.fixture
def db(tmp_path):
    p=tmp_path/'w.sqlite3';init_db(p);seed_agents(p);return p


def proposal(**kw):
    return {**{'type':'small_incident','for':'Dez Whitworth','with':None,'content':'You find a barrel has gone off.','in_hours':2,'rationale':'An everyday inconvenience.'},**kw}


def test_stall_report_and_pending_seed_suppression(db):
    now=datetime(2026,11,16,20)
    assert director.stall_report(now,db)['stalled']
    seed_events(db,now)
    assert not director.stall_report(now+timedelta(days=1),db)['stalled']
    with connect(db) as c:timeline.record(c,now,'promise_broken','Forgot the quiz.',4,1)
    assert not director.stall_report(now,db)['stalled']


@pytest.mark.parametrize('changes',[
    {'for':'Stranger'},{'for':'Nobody'}, {'content':'You lose £50 on a barrel.'},
    {'content':'You lose 50k on a barrel.'},{'content':'You lose 50 thousand on a barrel.'},
    {'content':'You meet Peter Morgan with a barrel.'},{'content':'You see a robbery.'},
    {'content':'You find a burst pipe and the police arrive.'},
    {'type':'letter','content':'You receive a letter from a new stranger.'},
    {'type':'phone_call','content':'You hear from Peter Morgan.'},
    {'type':'chance_meeting','with':'Stranger'}, {'type':'chance_meeting','with':'Dez Whitworth'},
    {'type':'letter','content':'You hear that Northgate Estates approved demolition.'},
    {'in_hours':25},
])
def test_invalid_proposals(db,changes):
    with pytest.raises(ValueError):director.validate(proposal(**changes),datetime(2026,11,16,20),db)


def test_director_once_per_day_and_toggle(db):
    now=datetime(2026,11,16,20)
    class Fake:
        calls=0
        def propose(self,aid,messages,schema,max_tokens):
            self.calls+=1;assert max_tokens==300
            return schema.model_validate(proposal())
    f=Fake();world.set_setting('director','0',db)
    assert not director.check(f,now,db)
    init_db(db);assert world.get_setting('director','1',db)=='0'
    world.set_setting('director','1',db)
    assert director.check(f,now,db)
    assert not director.check(f,now+timedelta(hours=1),db)
    with pytest.raises(ValueError):director.validate(proposal(),now,db)
    assert f.calls==1
    with connect(db) as c:assert c.execute("select origin from scheduled_events").fetchone()[0]=='director'


def test_chance_meeting_creates_plans_without_fact(db):
    now=datetime(2026,11,17,12)
    class Fake:
        def propose(self,aid,messages,schema,max_tokens):return schema.model_validate(proposal(type='chance_meeting',**{'for':'Tommy Shaw','with':'Chloe Barlow','in_hours':7,'content':'You meet Chloe Barlow for a chat.'}))
    assert director.check(Fake(),now,db)
    with connect(db) as c:
        rows=c.execute("select * from plans where status='planned'").fetchall()
        assert len(rows)==2 and rows[0]['place']==rows[1]['place']=='pub'
        assert c.execute('select count(*) from scheduled_events').fetchone()[0]==0
