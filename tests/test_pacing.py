from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest

from evorium import cases, main, pacing, places, world
from evorium.db import connect, init_db
from evorium.llm import DailyBudgetReached, DeepSeekClient, PacingWait, Settings, get_usage, is_peak
from evorium.seed import seed_agents

CAP = .15
DAY = datetime(2026, 11, 24, tzinfo=timezone.utc)
COST = Decimal('.004')


@pytest.fixture
def db(tmp_path):
    path = tmp_path / 'pacing.sqlite3'
    init_db(path)
    seed_agents(path)
    return path


def charge(c, at, cost, scope='auto', cid=None):
    c.execute("""INSERT INTO llm_calls
                 (agent_id,model,input_tokens,output_tokens,est_cost_usd,ok,created_at,budget_scope,conversation_id)
                 VALUES (1,'fake',1,1,?,1,?,?,?)""", (float(cost),pacing.stamp(at),scope,cid))


def allowance(db, at, kind='auto'):
    with connect(db) as c:
        return pacing.available(c, at, CAP, kind)


def test_weights_real_midnight_and_evening_catchup(db):
    at = lambda hour: DAY + timedelta(hours=hour)
    assert pacing.planned(at(12), CAP) <= Decimal('.15') * Decimal('.15')
    assert pacing.planned(at(20), CAP)-pacing.planned(at(19), CAP) > pacing.planned(at(18), CAP)-pacing.planned(at(17), CAP)
    assert allowance(db, at(12)) == 0   # The previous morning's unused allowance cannot spill into lunch.
    assert allowance(db, at(17)) == pacing.planned(at(17), CAP)
    assert allowance(db, at(23)) == 0
    assert allowance(db, at(24)) == 0
    for day, length in [(29,23),(25,25)]:
        switch = datetime(2026,3 if length==23 else 10,day,12,tzinfo=timezone.utc)
        start,end = map(datetime.fromisoformat,pacing.day_bounds(switch))
        assert (end-start).total_seconds() == length*3600
    # The duplicated autumn hour earns steady allowance in UTC, without jumping back.
    a = datetime(2026,10,25,0,50,tzinfo=timezone.utc)
    b = a + timedelta(minutes=15)
    assert pacing.planned(b, CAP) > pacing.planned(a, CAP)


def test_fake_day_paces_spend_and_starts_at_most_one_conversation_per_tick(db, monkeypatch):
    real_at = DAY
    visits = []
    monkeypatch.setattr(main, '_state', {'conversations':0})
    monkeypatch.setattr(places, 'opportunities', lambda *_: [('pub',[{'id':1},{'id':3}]),
                                                             ('shop',[{'id':2},{'id':4}])])
    monkeypatch.setattr(world, 'pick_pair', lambda ids,*_: ids)
    monkeypatch.setattr(main, 'turns_for', lambda *_:4)

    client = DeepSeekClient(db, Settings('fake', max_daily_spend_usd=CAP))
    client.clock = lambda: real_at

    def run_fake(_client, a, b, turns, path, *, location):
        visits.append(real_at)
        # Five billed requests per chat, including notes, with peak pricing applied.
        with connect(path) as c:
            cid=c.execute("INSERT INTO conversations(location,status,agent_a_id,agent_b_id) VALUES (?,'completed',?,?)",
                          (location,a,b)).lastrowid
            for _ in range(turns+1):
                charge(c, real_at, COST*(2 if is_peak(real_at) else 1)/5, pacing.scope.get(), cid)

    monkeypatch.setattr(main, 'run_conversation', run_fake)
    for minute in range(0,1440,10):
        real_at = DAY + timedelta(minutes=minute)
        before = len(visits)
        main._auto_conversations(client, real_at.replace(tzinfo=None), None, db)
        assert len(visits)-before <= 1
        spent = get_usage(db, at=real_at)['daily_spend_usd']
        assert spent <= float(pacing.planned(real_at, CAP))
        assert spent <= CAP*.70
        if minute == 720:
            assert spent <= CAP*.15
        if minute == 1020:
            before_evening = spent
        if minute == 1370:
            evening = spent-before_evening
    assert evening > spent/2
    assert main._state['conversations'] == len(visits)


def test_provider_admission_preserves_player_headroom_and_caps_retry(db):
    at = DAY.replace(hour=22, minute=55)
    with connect(db) as c:
        charge(c, at-timedelta(hours=1), '.103')
    http_hits = []

    def reply(request):
        http_hits.append(request)
        return httpx.Response(200, json={
            'usage':{'prompt_tokens':100,'completion_tokens':30},
            'choices':[{'finish_reason':'stop','message':{'content':
                       '{"say":"All right?","rationale":"A greeting.","mood":"friendly"}'}}],
        })

    with httpx.Client(transport=httpx.MockTransport(reply)) as http:
        client=DeepSeekClient(db,Settings('fake',max_daily_spend_usd=CAP),http)
        client.clock=lambda:at
        prompt=[{'role':'user','content':'Hello. '*2000}]
        with pacing.spending('auto'), pytest.raises(PacingWait):
            client.propose(1,prompt)
        assert not http_hits
        # The same request can use the player's allowance.
        assert client.propose(1,prompt).say == 'All right?'
        with connect(db) as c:
            charge(c, at, '.04696', 'player')
        with pytest.raises(DailyBudgetReached, match='too tired'):
            client.propose(1,prompt)
        assert len(http_hits)==1
    assert get_usage(db,at=at)['daily_spend_usd']<=CAP


def test_scheduled_and_grace_chats_use_the_tick_slot(db, monkeypatch):
    calls=[]
    client=object()
    no_op=lambda *_:None
    for module,name in [(main.timeline,'daily_digest'),(main.plans,'daily'),(main.decide,'run'),
                        (main.economy,'maintain'),(main.director,'check')]:
        monkeypatch.setattr(module,name,no_op)
    monkeypatch.setattr(cases,'approach',lambda *_: calls.append('Grace') or True)
    monkeypatch.setattr(main.plans,'execute',lambda *_, **kw: calls.append(kw['phone_limit']) or 1)
    monkeypatch.setattr(main,'_auto_conversations',lambda *_:calls.append('places'))
    main._paid_tick(client,DAY,None,db)
    assert calls==['Grace']
    calls.clear()
    monkeypatch.setattr(cases,'approach',lambda *_:False)
    main._paid_tick(client,DAY,None,db)
    assert calls==[1]
