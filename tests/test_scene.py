import json
from datetime import datetime, timezone

import pytest
from evorium import scene, world, tick
from evorium.db import init_db, connect
from evorium.seed import seed_agents

@pytest.fixture
def db(tmp_path):
    path=tmp_path/'scene.sqlite3'
    init_db(path);seed_agents(path)
    with connect(path) as c:
        world._set(c,'speed',0)
        world._set(c,'anchor_real','2026-11-19 18:00:00')
        world._set(c,'anchor_sim','2026-11-19 18:00:00')
    tick.update_routines(datetime(2026,11,19,18),path)
    return path

def person(i,place,first='Dez',activity='visiting'):
    return dict(id=i,place=place,first=first,activity=activity)

def test_spots_slots_and_determinism():
    people=[person(1,'pub',activity='behind the bar'),person(2,'pub','Jess','working the bar'),person(3,'pub','Tommy','at his usual table'),person(4,'pub','Mo','here for darts and company')]
    people += [person(i,'pub',str(i)) for i in range(5,12)]
    a=scene.assign_spots(people)
    assert [p['waypoint'] for p in a[:4]]==['PUB_HOST','PUB_BAR','PUB_WINDOW','PUB_DART']
    assert a[4]['waypoint']=='PUB_BOOTH' and a[7]['slot']==1
    assert scene.assign_spots(list(reversed(people)))==a
    shop=scene.assign_spots([person(1,'shop','Raj','behind the counter')]+[person(i,'shop') for i in range(2,6)])
    assert [p['waypoint'] for p in shop]==['NEWS_TILL','NEWS_QUEUE','NEWS_RACK','NEWS_CHILLER','NEWS_QUEUE']
    assert shop[-1]['slot']==1

def test_empty_conversations_visibility_privacy_and_no_writes(db):
    before=db.read_bytes()
    data=scene.snapshot(db)
    assert before==db.read_bytes()
    assert len(data['characters'])==8
    dez=next(a for a in data['characters'] if a['first']=='Dez')
    assert dez['waypoint']=='PUB_HOST' and dez['visible'] and dez['line'] is None
    assert dez['portrait']=='/static/portraits/dez.png'
    assert any(a['place']=='away' and not a['visible'] for a in data['characters'])
    assert data['pub_open'] and data['shop_open'] and data['daylight']==.5
    for forbidden in ('rationale','facts','background','current_goal','stats','personality'):
        assert forbidden not in json.dumps(data)

def test_recent_lines_expiry_and_no_private_rationale(db):
    now=datetime(2026,11,19,18,tzinfo=timezone.utc)
    with connect(db) as c:
        cid=c.execute("INSERT INTO conversations(location,status,agent_a_id,agent_b_id,ended_at) VALUES (?,'completed',1,3,'2026-11-19T17:59:00Z')",(world.PUB,)).lastrowid
        c.execute("INSERT INTO messages(conversation_id,speaker_id,text,rationale,sim_time,created_at) VALUES (?,1,'Hello street','SECRET','18:00','2026-11-19T17:59:00Z')",(cid,))
    data=scene.snapshot(db,real_at=now)
    assert next(a for a in data['characters'] if a['id']==1)['line']=='Hello street'
    assert 'SECRET' not in json.dumps(data)
    later=scene.snapshot(db,real_at=now.replace(minute=3))
    assert all(a['line'] is None for a in later['characters'])
    with connect(db) as c:c.execute("UPDATE conversations SET status='running' WHERE id=?",(cid,))
    running=scene.snapshot(db,real_at=now.replace(minute=3))
    assert next(a for a in running['characters'] if a['id']==1)['talking_to']==3

def test_unanchored_world_is_read_only(db):
    with connect(db) as c:c.execute("DELETE FROM world WHERE key LIKE 'anchor_%'")
    before=db.read_bytes()
    scene.snapshot(db)
    assert db.read_bytes()==before

def test_street_and_away():
    result=scene.assign_spots([person(1,'street'),person(2,'street'),person(3,'away')])
    assert [a['waypoint'] for a in result]==['STREET_WAIT','STREET_LINK',None]
    assert not result[-1]['visible']


def test_notices_at_exact_minute_boundary(db):
    with connect(db) as c:
        c.execute("INSERT INTO notices(place,text,since,until) VALUES ('pub','Current notice','2026-11-19 18:00:00','2026-11-19 19:00:00')")
        c.execute("INSERT INTO notices(place,text,since,until) VALUES ('shop','Expired notice','2026-11-19 17:00:00','2026-11-19 18:00:00')")
    assert scene.snapshot(db)['notices']==[{'place':'pub','text':'Current notice'}]
