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
        cast=npc_agents(c);assert len(cast)==8
        assert c.execute('select count(*) from facts').fetchone()[0]==26
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
