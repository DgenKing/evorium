from datetime import datetime,timedelta
from collections import Counter
import pytest
from evorium import world, actions, economy, memory
from evorium.db import init_db,connect,npc_agents
from evorium.seed import seed_agents,CHARACTERS
from evorium.models import Extraction

MONDAY=datetime(2026,11,16)


def test_every_apc_has_three_hours_shared_free_time():
    hours=world.shared_free_hours([a[0] for a in CHARACTERS],MONDAY,{'jess.shifts':4})
    assert min(hours.values())>=3, hours
    assert world.routine('Peggy Coyle',MONDAY.replace(hour=15))[0]==world.STREET
    assert world.routine('Jess Hartley',MONDAY.replace(day=19,hour=18),{'jess.shifts':4})[1]=='working the bar'


@pytest.fixture
def db(tmp_path,monkeypatch):
    path=tmp_path/'w.sqlite3';init_db(path);seed_agents(path)
    monkeypatch.setattr(world,'now',lambda *a:MONDAY.replace(hour=19))
    economy.ensure(path,MONDAY)
    return path


def add(c,a,b,at,status='completed'):
    return c.execute('INSERT INTO conversations(location,status,agent_a_id,agent_b_id,sim_at) VALUES (?,?,?,?,?)',
        (world.PUB,status,a,b,at.strftime('%Y-%m-%d %H:%M'))).lastrowid


def test_pair_cap_running_completed_and_next_day(db,monkeypatch):
    with connect(db) as c:
        add(c,1,3,MONDAY);add(c,3,1,MONDAY,'running')
    with pytest.raises(world.PairLimitReached):world.pick_pair([1,3],db)
    assert set(world.pick_pair([1,3],db,automatic=False))=={1,3}
    monkeypatch.setattr(world,'now',lambda *a:MONDAY+timedelta(days=1))
    assert set(world.pick_pair([1,3],db))=={1,3}


def test_player_chats_never_count_towards_pair_cap(db):
    with connect(db) as c:
        human=c.execute("SELECT id FROM agents WHERE kind='player'").fetchone()[0]
        for _ in range(4):add(c,human,1,MONDAY)
    assert set(world.pick_pair([1,3],db))=={1,3}


def test_automatic_picks_do_not_starve_any_apc(db,monkeypatch):
    totals=Counter()
    # Walk an actual routine week, one opportunity per sampled place/half hour, recording chosen pairs.
    with connect(db) as c:agents=npc_agents(c)
    from evorium import places
    for step in range(7*48):
        at=MONDAY+timedelta(minutes=step*30)
        monkeypatch.setattr(world,'now',lambda *a,at=at:at)
        groups={k:[] for k in places.REGISTRY}
        for a in agents:
            loc,_=world.routine(a['name'],at,{'jess.shifts':4})
            if world.is_free(a['name'],at,{'jess.shifts':4}):
                for k,place in places.REGISTRY.items():
                    if loc==place and places.is_open(k,at):groups[k].append(a['id'])
        for group in groups.values():
            if len(group)<2:continue
            try:a,b=world.pick_pair(group,db)
            except ValueError:continue
            totals.update([a,b])
            with connect(db) as c:add(c,a,b,at)
    assert all(totals[a['id']]>0 for a in agents),totals


def test_copied_decision_is_rejected_even_with_matching_speech(db):
    with connect(db) as c:
        actor=dict(c.execute('SELECT * FROM agents WHERE id=7').fetchone())
        cid=add(c,7,3,MONDAY,'running')
        result=actions.propose(c,actor,actions.EXAMPLE_DECISION,MONDAY.replace(hour=19),'conversation',cid,
            [{'speaker_id':7,'text':actions.EXAMPLE_DECISION['quote']}])
        assert result['status']=='rejected' and 'Copied example' in result['result']


def test_valid_spoken_decision_and_wrong_speaker(db):
    now=MONDAY.replace(hour=19)
    with connect(db) as c:
        cid=add(c,1,3,now,'running')
        words='I will put twenty pence on the pint now.'
        c.execute('INSERT INTO messages(conversation_id,speaker_id,text,rationale,sim_time) VALUES (?,?,?,?,?)', (cid,1,words,'test','now'))
        participants={r['name']:dict(r) for r in c.execute('SELECT * FROM agents WHERE id IN (1,3)')}
        ext=Extraction(summary='Dez changed the price.',per_agent={'Dez Whitworth':{'decision':{'action':'change_pint_price','args':{'pence':20},'quote':words}}})
        memory.store_extraction(c,cid,participants,ext,now)
        assert c.execute("SELECT status FROM actions WHERE key='change_pint_price'").fetchone()[0]=='done'
        actor=participants['Tommy Shaw']
        result=actions.propose(c,actor,{'action':'tell','args':{},'quote':words},now,'conversation',cid,[{'speaker_id':1,'text':words}])
        assert result['status']=='rejected' and 'verbatim' in result['result']
