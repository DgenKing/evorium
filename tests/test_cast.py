from evorium.seed import CHARACTERS
from datetime import datetime
from evorium import world
from evorium.db import init_db,connect,npc_agents
from evorium.seed import seed_agents
from evorium.prompts import build_extraction_messages
from evorium.relationships import get


def test_new_routines_and_free_flags():
    thursday=datetime(2026,11,19,14,15)
    assert world.routine('Simon Ferris',thursday)[0]=="Patel's News, Ancoats"
    assert world.is_free('Simon Ferris',thursday)
    assert not world.is_free('Simon Ferris',thursday.replace(hour=15))
    assert world.routine('Brenda Ashworth',thursday.replace(hour=9))[0]=="Patel's News, Ancoats"
    assert world.is_free('Brenda Ashworth',thursday.replace(hour=9))
    assert world.routine('Brenda Ashworth',datetime(2026,11,18,20))[0]==world.PUB
    mo='Mohammed "Mo" Iqbal'
    assert world.routine(mo,datetime(2026,11,17,19))[0]==world.PUB
    assert world.is_free(mo,datetime(2026,11,17,19))
    assert not world.is_free(mo,datetime(2026,11,17,20))
    assert world.routine(mo,datetime(2026,11,17,10))[1]=='asleep'
    assert world.routine(mo,datetime(2026,11,17,16,15))[0]=="Patel's News, Ancoats"


def test_expanded_seed_is_idempotent_and_cast_in_notes(tmp_path):
    path=tmp_path/'world.sqlite3';init_db(path);seed_agents(path);seed_agents(path)
    with connect(path) as c:
        cast=npc_agents(c);assert len(cast)==len(CHARACTERS)
        from evorium.seed import SEED_FACTS
        assert c.execute('select count(*) from facts').fetchone()[0]==len(SEED_FACTS)
        names={a['name']:a['id'] for a in cast}
        assert get(c,names['Brenda Ashworth'],names['Tommy Shaw'])['trust']==75
        assert get(c,names['Simon Ferris'],names['Tommy Shaw'])['trust']==40
        assert get(c,names['Mohammed "Mo" Iqbal'],names['Raj Patel'])['trust']==65
        prompt=build_extraction_messages(cast[0],cast[1],[],[],[],list(names),'now')[0]['content']
        assert all(name in prompt for name in ['Simon Ferris','Brenda Ashworth','Mohammed "Mo" Iqbal'])


def test_note_taker_cast_excludes_player_and_system(tmp_path):
    from evorium.sim import run_conversation
    from evorium.models import ActionProposal,Extraction
    path=tmp_path/'world.sqlite3';init_db(path);seed_agents(path)
    class Fake:
        def propose(self,aid,messages,schema=ActionProposal,max_tokens=300):
            if schema is Extraction:
                line=next(line for line in messages[0]['content'].splitlines() if line.startswith('- "new_people"'))
                assert 'World' not in line and 'Stranger' not in line
                assert 'Simon Ferris' in line and 'Brenda Ashworth' in line
                return Extraction(summary='Dez and Tommy talked.')
            return ActionProposal(say='Hello.',rationale='Greeting.',mood='happy')
    run_conversation(Fake(),1,3,1,path)


def test_new_apcs_join_an_existing_world_without_duplicating_facts(tmp_path, monkeypatch):
    # The live world was seeded with the original 8 characters and 26 facts. Restarting on the new code must
    # add the newcomers and their facts only: seed keys are list positions, so old facts must not repeat.
    from evorium import seed as seedmod
    path=tmp_path/'world.sqlite3';init_db(path)
    monkeypatch.setattr(seedmod,'CHARACTERS',seedmod.CHARACTERS[:8]);monkeypatch.setattr(seedmod,'SEED_FACTS',seedmod.SEED_FACTS[:26])
    seedmod.seed_agents(path)
    monkeypatch.undo()
    seedmod.seed_agents(path)
    with connect(path) as c:
        names=[a['name'] for a in npc_agents(c)]
        assert names[8:]==['Peggy Coyle','Liam Byrne','Anjali Patel','Pete Lomax','Hannah Kerr',
                           'Gary Walsh','Kirsty Doyle','Grace Adeyemi','Barry Hughes','Ronnie Clegg',
                           'Norman Pilling','Maxine Stott']
        assert c.execute('select count(*) from facts').fetchone()[0]==len(seedmod.SEED_FACTS)
        assert c.execute('select count(*) from (select content from facts group by agent_id,content having count(*)>1)').fetchone()[0]==0
        ids={a['name']:a['id'] for a in npc_agents(c)}
        assert get(c,ids['Anjali Patel'],ids['Raj Patel'])['trust']==85
        assert get(c,ids['Peggy Coyle'],ids['Brenda Ashworth'])['warmth']==75


def test_quieter_apcs_now_have_company():
    tue=datetime(2026,11,17)
    assert world.routine('Brenda Ashworth',tue.replace(hour=13))[0]==world.PUB          # pensioners' lunch
    assert world.routine('Peggy Coyle',tue.replace(hour=13))[0]==world.PUB              # her half of stout
    assert world.routine('Chloe Barlow',tue.replace(hour=8,minute=20))[0]=="Patel's News, Ancoats"
    assert world.routine('Chloe Barlow',datetime(2026,11,19,19))[0]==world.PUB          # Thursdays too now
    assert world.routine('Pete Lomax',tue.replace(hour=10,minute=15))==(world.PUB,'delivering the barrels')
    assert not world.is_free('Pete Lomax',tue.replace(hour=10,minute=15))
    assert world.routine('Anjali Patel',datetime(2026,11,16,16))==("Patel's News, Ancoats",'helping on the counter')
    assert world.routine('Liam Byrne',tue.replace(hour=12,minute=45))[0]==world.PUB
    assert world.routine('Hannah Kerr',datetime(2026,11,18,18))[0]==world.PUB
    assert world.routine('Simon Ferris',tue.replace(hour=13))[0]==world.PUB


def test_pick_pair_favours_people_who_have_not_spoken(tmp_path):
    import random
    path=tmp_path/'world.sqlite3';init_db(path);seed_agents(path)
    with connect(path) as c:
        ids={a['name'].split()[0]:a['id'] for a in npc_agents(c)}
        for _ in range(6):
            c.execute("INSERT INTO conversations(location,status,sim_time,agent_a_id,agent_b_id) VALUES ('pub','completed','x',?,?)",(ids['Dez'],ids['Jess']))
            c.execute("INSERT INTO conversations(location,status,sim_time,agent_a_id,agent_b_id) VALUES ('pub','completed','x',?,?)",(ids['Dez'],ids['Tommy']))
    random.seed(1)
    picks=[frozenset(world.pick_pair([ids['Dez'],ids['Jess'],ids['Tommy'],ids['Brenda']],path)) for _ in range(300)]
    with_brenda=sum(ids['Brenda'] in p for p in picks)
    assert with_brenda>200   # Brenda hasn't spoken, so most conversations include her


def test_apcs_on_shuttle_street_show_up_in_the_scene(tmp_path):
    from evorium import scene, tick
    path=tmp_path/'world.sqlite3';init_db(path);seed_agents(path)
    tue_1500=datetime(2026,11,17,15,5)   # Liam's afternoon smoke break; Peggy on the bench
    assert world.routine('Liam Byrne',tue_1500)==(world.STREET,'on a smoke break')
    assert world.routine('Peggy Coyle',tue_1500)==(world.STREET,'sitting on the bench outside the Billet')
    freeze_clock(path,tue_1500)
    tick.update_routines(tue_1500,path)
    data=scene.snapshot(path)
    on_street={p['first'] for p in data['characters'] if p['place']=='street' and p['visible']}
    assert {'Liam','Peggy'} <= on_street


def test_second_batch_routines():
    mon=datetime(2026,11,16)
    assert world.routine('Gary Walsh',mon.replace(hour=8,minute=50))==(world.STREET,'doing his round along the terrace')
    assert world.routine('Barry Hughes',mon.replace(hour=10))==(world.STREET,'cleaning the windows along the terrace')
    assert world.routine('Ronnie Clegg',mon.replace(hour=14))[0]==world.PUB
    assert world.routine('Kirsty Doyle',mon.replace(hour=10,minute=40))[0]==world.STREET
    assert world.routine('Grace Adeyemi',mon.replace(hour=13,minute=40))==(world.STREET,'on patrol')
    assert not world.is_free('Grace Adeyemi',mon.replace(hour=13,minute=40))
    assert world.routine('Grace Adeyemi',datetime(2026,11,20,22,50))==(world.PUB,'looking in at closing time')


def test_player_can_talk_to_an_apc_on_the_street(tmp_path):
    from evorium import player, tick
    from evorium.models import ActionProposal
    from fastapi import HTTPException
    path=tmp_path/'world.sqlite3';init_db(path);seed_agents(path)
    tue_1505=datetime(2026,11,17,15,5)   # Peggy is on the bench outside the Billet
    freeze_clock(path,tue_1505)
    tick.update_routines(world.now(path),path)
    with connect(path) as c:
        peggy=c.execute("SELECT id FROM agents WHERE name='Peggy Coyle'").fetchone()[0]
        dez=c.execute("SELECT id FROM agents WHERE name='Dez Whitworth'").fetchone()[0]
    class Fake:
        def propose(self,aid,messages,schema=None,max_tokens=0):
            return ActionProposal(say="Afternoon, love. Sit yourself down.",rationale='friendly',mood='chatty')
    reply=player.say(Fake(),peggy,'hi',path)               # no place entered: you're on the street
    assert reply['reply']['text'].startswith('Afternoon')
    assert world.get_setting('player_place','',path)=='street'
    try:
        player.say(Fake(),dez,'hi',path)                   # Dez is inside behind the bar, not on the street
        assert False, 'should refuse'
    except HTTPException as e:
        assert e.status_code==409


def freeze_clock(path, at):
    """Stop the sim clock at `at`: both anchors and speed 0 (setting one anchor alone resets to real time)."""
    with connect(path) as c:
        world._set(c, 'anchor_real', world._real_now().strftime(world.FMT))
        world._set(c, 'anchor_sim', at.strftime(world.FMT))
        world._set(c, 'speed', 0)


def test_apcs_know_the_jobs_of_people_they_know_but_not_strangers(tmp_path):
    # Live bug, 23 Nov: Ronnie said Grace (the PCSO) "pulls pints"; he'd only ever been told names.
    from evorium.db import connect, init_db
    from evorium.memory import knowledge_for_prompt
    from evorium.prompts import build_messages
    from evorium.seed import seed_agents
    path = tmp_path / 'w.sqlite3'
    init_db(path); seed_agents(path)
    with connect(path) as c:
        agents = {r['name'].split()[0]: dict(r) for r in c.execute('SELECT * FROM agents')}
        known = knowledge_for_prompt(c, agents['Ronnie'], agents['Tommy'])['acquaintances']
        assert 'Grace Adeyemi: Police community support officer' in known      # a public face
        assert not any(k.startswith('Tommy') or k.startswith('Ronnie') for k in known)  # not the listener or himself
        assert not any(k.startswith('Simon') for k in known)                    # never met: his Northgate job stays hidden
        c.execute('UPDATE relationships SET familiarity=3 WHERE agent_id=? AND other_id=?', (agents['Ronnie']['id'], agents['Simon']['id']))
        known = knowledge_for_prompt(c, agents['Ronnie'], agents['Tommy'])['acquaintances']
        assert any(k.startswith('Simon Ferris: Asset Manager at Northgate Estates') for k in known)
        text = build_messages(agents['Ronnie'], agents['Tommy'], [], knowledge_for_prompt(c, agents['Ronnie'], agents['Tommy']), 'now')[0]['content']
        assert 'PEOPLE ROUND HERE YOU KNOW, AND WHAT THEY DO' in text and 'Grace Adeyemi: Police community support officer' in text
