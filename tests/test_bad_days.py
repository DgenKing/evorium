from collections import Counter
from datetime import datetime,timedelta
import json
import pytest
from evorium import bad_days,world,tick,places,plans,memory
from evorium.db import init_db,connect
from evorium.seed import seed_agents

NOW=datetime(2026,11,19,18)


@pytest.fixture
def db(tmp_path):
    path=tmp_path/'w.sqlite3';init_db(path);seed_agents(path)
    return path


def force(monkeypatch,person,kind):
    def choose(name,day,late_pub=False,critical=False):
        return {'kind':kind if name.startswith(person+' ') and not critical else 'none','delay':45 if kind=='running_late' else 60 if kind=='hungover' else 0}
    monkeypatch.setattr(bad_days,'choose',choose)


def test_determinism_rates_and_hangover_eligibility():
    counts=Counter();not_late=Counter()
    for i in range(40000):
        day=(datetime(2026,1,1)+timedelta(days=i)).strftime('%Y-%m-%d')
        a=bad_days.choose('Tommy Shaw',day,True)
        assert a==bad_days.choose('Tommy Shaw',day,True)
        counts[a['kind']]+=1;not_late[bad_days.choose('Tommy Shaw',day,False)['kind']]+=1
        if a['kind']=='running_late':assert 30<=a['delay']<=60
    assert .025<counts['off_sick']/40000<.035
    assert .05<counts['running_late']/40000<.07
    assert .33<counts['hungover']/40000<.37
    assert not_late['hungover']==0
    assert bad_days.choose('Tommy Shaw','2026-11-19',True,True)['kind']=='none'


@pytest.mark.parametrize('source',['event','offer','promise','retry'])
def test_story_critical_exemptions(db,source):
    with connect(db) as c:
        actor=dict(c.execute('SELECT * FROM agents WHERE id=1').fetchone())
        if source=='event':c.execute("INSERT INTO scheduled_events(seed_key,at,agent_id,subject,content,origin) VALUES ('critical','2026-11-19 19:00',1,'letter','Important letter','seed')")
        elif source=='offer':c.execute("INSERT INTO offers(kind,from_id,to_id,amount,terms,status,created_at,expires_at) VALUES ('renewal',6,1,3300,'lease','open','2026-11-18 12:00','2026-11-19 19:00')")
        else:c.execute("INSERT INTO commitments(agent_id,content,due_at,retry_at) VALUES (1,'Important promise',?,?)",('2026-11-19 19:00' if source=='promise' else '2026-11-18 19:00','2026-11-19 19:00' if source=='retry' else None))
        assert bad_days.critical(c,actor,NOW)
        assert not bad_days.critical(c,actor,NOW+timedelta(days=1))


def test_jess_sick_dez_covers_and_no_private_condition_leaks(db,monkeypatch):
    force(monkeypatch,'Jess','off_sick')
    bad_days.maintain(NOW,db);bad_days.maintain(NOW,db)
    tick.update_routines(NOW,db)
    with connect(db) as c:
        values=world.routine_inputs(c,NOW)
        agents={r['name'].split()[0]:dict(r) for r in c.execute('SELECT * FROM agents')}
        assert agents['Jess']['location']==world.home_location('Jess Hartley')
        assert agents['Jess']['mood']=='under the weather'
        assert not world.is_free('Jess Hartley',NOW,values)
        assert world.pub_open(NOW,values)
        assert world.routine('Dez Whitworth',NOW,values)==(world.PUB,'covering Jess behind the bar')
        from evorium import scene
        assert scene.assign_spots([{'id':1,'first':'Dez','place':'pub','activity':'covering Jess behind the bar'}])[0]['waypoint']=='PUB_HOST'
        assert c.execute("SELECT count(*) FROM facts WHERE subject='bad day'").fetchone()[0]==1
        assert c.execute("SELECT count(*) FROM timeline WHERE kind='bad_day'").fetchone()[0]==1
        mine=memory.knowledge_for_prompt(c,agents['Jess'],agents['Tommy'],NOW)
        theirs=memory.knowledge_for_prompt(c,agents['Tommy'],agents['Dez'],NOW)
        assert 'off sick' in mine['environment'] and len(mine['environment'].splitlines())==2
        assert 'off sick' not in theirs['environment'] and not any('off sick' in f for f in theirs['certain'])


def test_lateness_postpones_only_first_activity_and_visit_cannot_override(db,monkeypatch):
    force(monkeypatch,'Jess','running_late')
    at=NOW.replace(hour=6,minute=10)
    assert bad_days.first_activity('Mohammed \"Mo\" Iqbal',at,{}).hour==13
    bad_days.maintain(at,db)
    with connect(db) as c:
        values=world.routine_inputs(c,at)
        assert world.routine('Jess Hartley',at,values)[0]==world.home_location('Jess Hartley')
        assert not world.is_free('Jess Hartley',at,values)
        assert world.routine('Jess Hartley',at.replace(hour=7),values)[1]=='cleaning shift'
        assert world.routine('Jess Hartley',NOW,values)[1]=='working the bar'
        jess=dict(c.execute("SELECT * FROM agents WHERE name='Jess Hartley'").fetchone())
        plans.insert(c,{'agent_id':jess['id'],'action':'visit','place':'pub','start_at':'2026-11-19 06:00','end_at':'2026-11-19 07:00','sim_day':'2026-11-19','status':'active'})
    assert world.whereabouts(jess,at,db)[0]==world.home_location(jess['name'])
    plans.execute(None,at,db,auto=False)
    with connect(db) as c:assert c.execute('SELECT status FROM plans').fetchone()[0]=='missed'


def test_late_pub_attendance_comes_from_record_not_guessing(db):
    with connect(db) as c:
        assert bad_days.late_attendance(c,'2026-11-18')==set()
        cid=c.execute("INSERT INTO conversations(location,status,agent_a_id,agent_b_id,sim_at) VALUES (?,'completed',1,3,'2026-11-18 23:30')",(world.PUB,)).lastrowid
        c.execute("INSERT INTO messages(conversation_id,speaker_id,text,rationale,sim_time) VALUES (?,3,'Evening.','test','23:30')",(cid,))
        assert bad_days.late_attendance(c,'2026-11-18')=={1,3}
        world._set(c,'late_pub:2026-11-18',json.dumps({'ids':[4]}))
        assert bad_days.late_attendance(c,'2026-11-18')=={1,3,4}


def test_mood_restore_does_not_overwrite_dialogue_and_day_is_idempotent(db,monkeypatch):
    force(monkeypatch,'Jess','off_sick')
    bad_days.maintain(NOW,db)
    with connect(db) as c:c.execute("UPDATE agents SET mood='angry' WHERE name='Jess Hartley'")
    force(monkeypatch,'Jess','none')
    bad_days.maintain(NOW+timedelta(days=1),db)
    with connect(db) as c:assert c.execute("SELECT mood FROM agents WHERE name='Jess Hartley'").fetchone()[0]=='angry'


def test_hangover_slow_morning_and_midday_mood_restore(db,monkeypatch):
    force(monkeypatch,'Tommy','hungover')
    at=NOW.replace(hour=10,minute=30)
    bad_days.maintain(at,db)
    with connect(db) as c:
        values=world.routine_inputs(c,at)
        assert world.routine('Tommy Shaw',at,values)[0]==world.home_location('Tommy Shaw')
        assert c.execute("SELECT mood FROM agents WHERE name='Tommy Shaw'").fetchone()[0]=='rough'
    bad_days.maintain(at.replace(hour=12),db)
    with connect(db) as c:assert c.execute("SELECT mood FROM agents WHERE name='Tommy Shaw'").fetchone()[0]!='rough'


def test_dashboard_and_scene_expose_realism_without_provider_calls(db,monkeypatch):
    from types import SimpleNamespace
    from datetime import timezone
    from fastapi.testclient import TestClient
    from evorium import main
    force(monkeypatch,'Jess','off_sick')
    bad_days.maintain(NOW,db);tick.update_routines(NOW,db)
    monkeypatch.setattr(main,'DEFAULT_DB_PATH',db)
    monkeypatch.setattr(world,'now',lambda *a:NOW)
    monkeypatch.setattr(main,'get_usage',lambda *a:{})
    monkeypatch.setattr(main,'DeepSeekClient',lambda *a:SimpleNamespace(settings=SimpleNamespace(max_spend_usd=4)))
    with connect(db) as c:
        world._set(c,'speed',0)
        world._set(c,'anchor_real',world._real_now().strftime(world.FMT))
        world._set(c,'anchor_sim',NOW.strftime(world.FMT))
        world._set(c,'weather_reading',json.dumps({'time':datetime.now(timezone.utc).timestamp(),'temperature':7,'condition':'rain','raining':True,'wind':12}))
    client=TestClient(main.app)
    usage=client.get('/usage').json()
    assert usage['weather']['condition']=='rain' and usage['weather']['source']=='cached'
    assert 'days to Christmas' in usage['calendar']['label']
    agents=client.get('/agents').json()
    assert next(a for a in agents if a['name']=='Jess Hartley')['bad_day']=='Off sick today'
    snapshot=client.get('/world/scene').json()
    assert snapshot['weather']['condition']=='rain' and 'calendar' in snapshot
    assert all('bad_day' not in a for a in snapshot['characters']) # god-view condition stays off the public scene
