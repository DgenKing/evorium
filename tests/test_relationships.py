from datetime import datetime
import pytest
from evorium.db import init_db, connect
from evorium.seed import seed_agents
from evorium import relationships, timeline
from evorium.memory import resolve_commitment, store_extraction
from evorium.models import Extraction

@pytest.fixture
def db(tmp_path):
    p=tmp_path/'w.sqlite3';init_db(p);seed_agents(p);return p


def test_clamp_bands_and_timeline(db):
    with connect(db) as c:
        r=relationships.adjust(c,1,2,100,-100,'Evidence.',datetime(2026,11,16,20))
        assert r['trust']==100 and r['warmth']==0
        assert relationships.describe(r)=='You trust completely and dislike them.'
        assert c.execute("select count(*) from timeline where kind='relationship'").fetchone()[0]==1
        relationships.adjust(c,1,2,-1,1,'Small.',datetime(2026,11,16,20))
        assert c.execute("select count(*) from timeline where kind='relationship'").fetchone()[0]==1
    assert [relationships.band(n) for n in [29,30,44,45,64,65,79,80]]==[0,1,1,2,2,3,3,4]


@pytest.mark.parametrize('status,delta',[('done',8),('broken',-12)])
def test_promise_effect_is_directed_and_idempotent(db,status,delta):
    with connect(db) as c:
        before=relationships.get(c,4,1)['trust'];reverse=relationships.get(c,1,4)['trust']
        cid=c.execute("insert into commitments(agent_id,to_agent_id,content) values (1,4,'Ring agent')").lastrowid
        resolve_commitment(c,cid,status,'Outcome.',datetime(2026,11,16,20))
        resolve_commitment(c,cid,status,'Outcome.',datetime(2026,11,16,20))
        assert relationships.get(c,4,1)['trust']==before+delta
        assert relationships.get(c,1,4)['trust']==reverse


@pytest.mark.parametrize('feeling,expected',[
    ({'trust_change':2,'warmth_change':-2,'reason':'Dez shared his worry.'},4),
    ({'trust_change':2,'warmth_change':2,'reason':' '},0),
    ({'trust_change':3,'warmth_change':0,'reason':'Too large.'},0),
    ({'trust_change':0,'warmth_change':0,'reason':'Nothing happened.'},0),
])
def test_feelings_are_bounded(db,feeling,expected):
    with connect(db) as c:
        people={r['name']:dict(r) for r in c.execute('select * from agents where id in (1,2)')}
        cid=c.execute("insert into conversations(location,status) values ('pub','completed')").lastrowid
        store_extraction(c,cid,people,Extraction.model_validate({'summary':'s','per_agent':{'Chloe Barlow':{'feeling':feeling}}}),datetime(2026,11,16,20))
        assert relationships.get(c,2,1)['trust']==50+expected
