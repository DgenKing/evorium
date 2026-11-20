from evorium.seed import CHARACTERS
"""A deterministic, local-only day across planning, shop chat, digest and player."""
from datetime import datetime,timedelta
from evorium import plans,places,sim,timeline,world,player,tick
from evorium.db import init_db,connect,npc_agents
from evorium.seed import seed_agents
from evorium.models import ActionProposal,Extraction,PromiseCheck


def test_complete_day_without_external_api(tmp_path,monkeypatch):
    path=tmp_path/'smoke.sqlite3';init_db(path);seed_agents(path)
    now=datetime(2026,11,17,7)
    monkeypatch.setattr(world,'now',lambda *a:now)
    class Fake:
        def propose(self,aid,messages,schema=ActionProposal,max_tokens=300):
            if schema is plans.DailyPlans:return plans.DailyPlans(plans=[])
            if schema is timeline.Digest:return timeline.Digest(digest='The neighbours talked at the shop and the pub. Tommy discussed the quiz. They went home.')
            if schema is PromiseCheck:return PromiseCheck(done=True,what_happened='Done.',mood='happy')
            if schema is Extraction:
                if 'Sam' in messages[0]['content'] and 'CONVERSATION:\nSam:' in messages[0]['content']:
                    return Extraction(summary='Sam told Dez about bicycles.',per_agent={'Dez Whitworth':{'facts':[{'subject':'player','content':'Sam repairs bicycles.','source':'told','told_by':'Sam'}]}})
                return Extraction(summary='Neighbours talked about life in Ancoats.')
            return ActionProposal(say='Good to see you.',rationale='Greeting a neighbour.',mood='friendly')
    client=Fake()
    assert plans.daily(client,now,path)==len(CHARACTERS)
    now=now.replace(hour=9,minute=5)
    present=places.present(now,path)['shop'];assert len(present)==2
    sim.run_conversation(client,present[0]['id'],present[1]['id'],2,path,location=places.REGISTRY['shop'])
    for hour in (19,21):
        now=now.replace(hour=hour)
        sim.run_conversation(client,1,3,2,path,location=world.PUB)
    now=(now+timedelta(days=1)).replace(hour=0,minute=1)
    assert timeline.daily_digest(client,now,path)
    now=now.replace(hour=20)
    player.profile('Sam','Repairs bicycles.',path);player.enter(client,'pub',path)
    player.say(client,1,'I repair bicycles.',path);player.say(client,1,'I enjoy darts.',path);player.close(client,path)
    with connect(path) as c:
        me=c.execute("select id from agents where kind='player'").fetchone()[0]
        assert c.execute("select 1 from facts where source='told' and source_agent_id=? and agent_id=1",(me,)).fetchone()
        assert c.execute("select 1 from timeline where kind='player' and agent_id=?",(me,)).fetchone()
        assert c.execute('select count(*) from llm_calls').fetchone()[0]==0
        assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
