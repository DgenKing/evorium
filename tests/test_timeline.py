from datetime import datetime, timedelta
import pytest
from evorium import timeline, tick
from evorium.db import init_db, connect
from evorium.seed import seed_agents, seed_events
from evorium.llm import InvalidProposal
from evorium.memory import store_extraction, resolve_commitment
from evorium.models import Extraction

@pytest.fixture
def db(tmp_path):
    p=tmp_path/'w.sqlite3';init_db(p);seed_agents(p);return p


def test_filters_and_triggered_kinds(db):
    now=datetime(2026,11,16,20)
    with connect(db) as c:
        participants={r['name']:dict(r) for r in c.execute('select * from agents where id in (1,3)')}
        cid=c.execute("insert into conversations(location,status) values ('pub','completed')").lastrowid
        store_extraction(c,cid,participants,Extraction(summary='s',per_agent={'Dez Whitworth':{'facts':[{'subject':'r','content':'A rumour','source':'claim'}],'commitments':[{'content':'Ring Tommy','to':'Tommy Shaw'}]}}),now)
        promise=c.execute('select id from commitments').fetchone()[0]
        store_extraction(c,cid,participants,Extraction(summary='s',per_agent={'Dez Whitworth':{'commitments':[{'content':'Ring Tommy tomorrow','replaces':promise}]}}),now)
        resolve_commitment(c,promise,'done','Called',now)
        other=c.execute("insert into commitments(agent_id,content) values (3,'Bring quiz')").lastrowid
        resolve_commitment(c,other,'broken','Forgot',now)
    tick.update_routines(now,db);seed_events(db,now);tick.deliver_events(now+timedelta(days=4),db)
    kinds={e['kind'] for e in timeline.entries(db)}
    assert {'rumour','promise_made','promise_updated','promise_kept','promise_broken','world_event','arrival'}<=kinds
    assert all(e['importance']>=3 for e in timeline.entries(db,min_importance=3))
    assert all(1 in (e['agent_id'],e['other_id']) for e in timeline.entries(db,agent_id=1))
    assert all(e['kind']=='rumour' for e in timeline.entries(db,kinds=['rumour']))
    assert timeline.entries(db,since='2030-01-01')==[]


def test_digest_once_and_bounded_failures(db):
    now=datetime(2026,11,17,0,1)
    with connect(db) as c:
        for i in range(3):timeline.record(c,now-timedelta(hours=1),'conversation','Dez talked to Tommy.',2,1,3)
    class Client:
        calls=0;fail=True
        def propose(self,agent_id,messages,schema,max_tokens):
            self.calls+=1;assert max_tokens==250
            if self.fail:raise InvalidProposal('bad')
            return schema(digest='Dez talked to Tommy. They discussed the pub. They went home.')
    client=Client()
    assert not timeline.daily_digest(client,now,db)
    client.fail=False
    assert timeline.daily_digest(client,now,db)
    assert not timeline.daily_digest(client,now,db)
    assert client.calls==2
    assert timeline.days(db)['days'][0]['digest']


def test_digest_gives_up_after_two_failures(db):
    now=datetime(2026,11,17,0,1)
    with connect(db) as c:
        for _ in range(3):timeline.record(c,now-timedelta(hours=1),'conversation','Dez and Tommy talked.',2,1,3)
    class Bad:
        calls=0
        def propose(self,*a,**k):self.calls+=1;raise InvalidProposal('bad')
    client=Bad()
    for _ in range(5):assert not timeline.daily_digest(client,now,db)
    assert client.calls==2


def test_shop_departure_records_an_arrival(db):
    from evorium import places
    morning=datetime(2026,11,17,9,15)
    tick.update_routines(morning,db)
    before=len(timeline.entries(db,kinds=['arrival']))
    tick.update_routines(morning.replace(minute=35),db)
    arrivals=timeline.entries(db,kinds=['arrival'])
    assert len(arrivals)==before+1
    assert arrivals[0]['agent_name']=='Brenda Ashworth'
