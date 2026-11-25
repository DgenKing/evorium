from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
import json
import httpx
import pytest
from evorium import weather,world,memory,prompts,plans,places
from evorium.db import connect,init_db
from evorium.seed import CHARACTERS, seed_agents

REAL=datetime(2026,11,23,12,tzinfo=timezone.utc)
NOW=REAL.replace(tzinfo=None)


def payload(code=61):
    return {'current':{'time':REAL.timestamp(),'temperature_2m':7,'wind_speed_10m':12,'precipitation':.5,'rain':.5,'cloud_cover':90,'weather_code':code}}


@pytest.fixture
def db(tmp_path,monkeypatch):
    p=tmp_path/'w.sqlite3';init_db(p);seed_agents(p)
    monkeypatch.setattr(weather,'load',lambda:SimpleNamespace(WEATHER_ENABLED=True))
    return p


@pytest.mark.parametrize('code,expected',[(0,'clear'),(3,'cloudy'),(45,'fog'),(51,'drizzle'),(61,'rain'),(65,'heavy_rain'),(71,'snow'),(95,'thunder')])
def test_code_parsing(code,expected):
    assert weather.parse(payload(code))['condition']==expected


def test_refresh_cache_fallback_stale_and_clock_rule(db,monkeypatch):
    calls=[]
    def get(*a,**kw):
        calls.append(kw)
        return httpx.Response(200,json=payload(),request=httpx.Request('GET',weather.URL))
    monkeypatch.setattr(weather.httpx,'get',get)
    assert weather.refresh(NOW,db,real_at=REAL)
    assert not weather.refresh(NOW+timedelta(minutes=29),db,real_at=REAL+timedelta(minutes=29))
    assert len(calls)==1 and calls[0]['timeout']==3
    with connect(db) as c:assert weather.read(c,NOW,REAL)['source']=='real'
    def fail(*a,**kw):raise httpx.ConnectError('offline')
    monkeypatch.setattr(weather.httpx,'get',fail)
    assert not weather.refresh(NOW+timedelta(minutes=31),db,real_at=REAL+timedelta(minutes=31))
    with connect(db) as c:
        assert weather.read(c,NOW,REAL+timedelta(hours=5))['condition']=='rain'
        assert weather.read(c,NOW,REAL+timedelta(hours=6,seconds=1))['condition']=='unknown'
        world._set(c,'speed',60)
        assert weather.read(c,NOW,REAL)['source']=='cached'
    assert not weather.refresh(NOW,db,real_at=REAL+timedelta(hours=1))
    world.set_setting('speed',1,db)
    assert not weather.refresh(NOW+timedelta(days=2),db,real_at=REAL+timedelta(hours=1))


def test_no_reading_malformed_response_and_failure_never_crash(db,monkeypatch):
    monkeypatch.setattr(weather.httpx,'get',lambda *a,**kw:httpx.Response(200,json={'current':{}},request=httpx.Request('GET',weather.URL)))
    assert not weather.refresh(NOW,db,real_at=REAL)
    with connect(db) as c:assert weather.read(c,NOW,REAL)['condition']=='unknown'
    bad=payload();bad['current']['temperature_2m']=float('nan')
    with pytest.raises(ValueError):weather.parse(bad)


def test_pure_rain_routines_and_dry_equivalents():
    rain={'_weather':{'raining':True,'condition':'rain'}}
    heavy={'_weather':{'raining':True,'condition':'heavy_rain'}}
    monday=NOW.replace(hour=15)
    assert world.routine('Peggy Coyle',monday)[0]==world.STREET
    assert world.routine('Peggy Coyle',monday,rain)[0]==world.PUB
    walk=NOW.replace(hour=14,minute=15)
    assert world.routine('Kirsty Doyle',walk)[0]==world.STREET
    assert world.routine('Kirsty Doyle',walk,rain)[0]==world.home_location('Kirsty Doyle')
    assert 'doorway' in world.routine('Liam Byrne',NOW.replace(hour=10,minute=2),rain)[1]
    assert world.routine('Liam Byrne',NOW.replace(hour=10,minute=8),rain)[1]=='on the scaffold'
    assert world.routine('Liam Byrne',NOW.replace(hour=10,minute=8))[1]=='on a smoke break'
    assert world.routine('Barry Hughes',NOW.replace(hour=9),heavy)[0]==world.home_location('Barry Hughes')
    assert world.routine('Barry Hughes',NOW.replace(hour=9),rain)[0]==world.STREET
    assert world.routine('Barry Hughes',NOW.replace(hour=10,minute=30),rain)[0]==world.PUB
    assert world.routine('Brenda Ashworth',NOW.replace(hour=10,minute=30),rain)[0]==world.PUB
    assert world.routine('Grace Adeyemi',NOW.replace(hour=10,minute=5),rain)[0]==places.REGISTRY['shop']
    assert world.routine('Hannah Kerr',NOW.replace(day=24,hour=13),rain)[0]==world.PUB


def test_dialogue_and_planning_receive_cached_weather_line(db,monkeypatch):
    with connect(db) as c:
        world._set(c,'weather_reading',json.dumps(weather.parse(payload())))
        agents=[dict(r) for r in c.execute('SELECT * FROM agents WHERE id IN (1,3)')]
        monkeypatch.setattr(weather,'_real',lambda *a:REAL)
        knowledge=memory.knowledge_for_prompt(c,*agents,NOW)
        assert knowledge['environment'].splitlines()==['Weather in Ancoats: rain, 7°C.','Today: Monday 23 November. 32 days to Christmas.']
        text=prompts.build_messages(*agents,[],knowledge,'now')[0]['content']
        assert text.count('Weather in Ancoats:')==1
    # The morning planner serializes the same knowledge; no separate weather/model call.
    class Fake:
        calls=[]
        def propose(self,aid,messages,**kw):
            self.calls.append(messages[0]['content'])
            return plans.DailyPlans(plans=[])
    fake=Fake();plans.daily(fake,NOW,db)
    assert len(fake.calls) == len(CHARACTERS)
    assert all('Weather in Ancoats:' in text for text in fake.calls)
