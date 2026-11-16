"""Small daily proposals, deterministic validation and execution."""
import json
from datetime import datetime,timedelta
from typing import Literal, Any
from pydantic import BaseModel, Field, ConfigDict
from evorium import world, places, timeline, relationships
from evorium.db import DEFAULT_DB_PATH,connect,npc_agents
from evorium.events import emit
from evorium.llm import LLMError
from evorium.memory import DUE_FMT,open_commitments,knowledge_for_prompt,resolve_commitment

class PlanProposal(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    action: Literal['visit','phone','stay_home']
    place: str | None = None
    person: str | None = None
    hour: int = Field(ge=0,le=23)
    minute: Literal[0,30]
    duration_minutes: int = Field(ge=30,le=180)
    fulfils: int | None = None
    reason: str = Field(min_length=1,max_length=300)

class DailyPlans(BaseModel):
    plans: list[Any] = Field(max_length=2)


def moments(start,end):
    while start<end:
        yield start
        start+=timedelta(minutes=1)


def validate(proposal,agent,now,db_path=DEFAULT_DB_PATH):
    p=PlanProposal.model_validate(proposal)
    start=now.replace(hour=p.hour,minute=p.minute,second=0,microsecond=0)
    end=start+timedelta(minutes=p.duration_minutes)
    if start<=now or end.date()!=now.date():raise ValueError('Plan must start later today and end today.')
    with connect(db_path) as c:
        people=npc_agents(c)
        person=next((a for a in people if a['name']==p.person),None)
        count=c.execute("SELECT count(*) FROM plans WHERE agent_id=? AND sim_day=? AND status!='cancelled'",(agent['id'],now.date().isoformat())).fetchone()[0]
        overlaps=c.execute("SELECT 1 FROM plans WHERE agent_id=? AND status IN ('planned','active') AND start_at<? AND end_at>?",(agent['id'],end.strftime(DUE_FMT),start.strftime(DUE_FMT))).fetchone()
        fulfils=c.execute("SELECT id FROM commitments WHERE id=? AND agent_id=? AND status='open'",(p.fulfils,agent['id'])).fetchone() if p.fulfils else None
    if count>=2:raise ValueError('At most two plans per day.')
    if overlaps:raise ValueError('Plans cannot overlap.')
    if p.action=='visit':
        if p.place not in places.REGISTRY:raise ValueError('Unknown public place.')
        if not all(places.is_open(p.place,t) and world.is_free(agent['name'],t) for t in moments(start,end)):raise ValueError('Place closed or character working during visit.')
    elif p.action=='phone':
        if not person or person['id']==agent['id']:raise ValueError('Phone another NPC.')
        if not all(world.is_free(agent['name'],t) or (agent['name'].split()[0] in ('Dez','Raj','Simon') and world.routine(agent['name'],t)[1] in ('behind the bar','behind the counter','at the office')) for t in moments(start,end)):
            raise ValueError('Cannot phone while asleep or unavailable at work.')
    else:
        if start.hour<17 or not all(world.routine(agent['name'],t)[0]==world.PUB and world.is_free(agent['name'],t) for t in moments(start,end)):
            raise ValueError('Stay home can only replace an evening pub visit as a customer.')
    return {'agent_id':agent['id'],'action':p.action,'place':p.place if p.action=='visit' else None,'person_id':person['id'] if person and p.action=='phone' else None,
            'start_at':start.strftime(DUE_FMT),'end_at':end.strftime(DUE_FMT),'reason':p.reason,'fulfils_commitment_id':fulfils[0] if fulfils else None,'sim_day':now.date().isoformat()}


def insert(c,plan):
    cols=list(plan)
    return c.execute('INSERT INTO plans('+','.join(cols)+') VALUES ('+','.join('?' for _ in cols)+')',[plan[k] for k in cols]).lastrowid


def daily(client,now,db_path=DEFAULT_DB_PATH):
    if now.hour<7:return 0
    with connect(db_path) as c:agents=npc_agents(c)
    calls=0
    for a in agents:
        with connect(db_path) as c:
            if c.execute('SELECT 1 FROM plans WHERE agent_id=? AND sim_day=?',(a['id'],now.date().isoformat())).fetchone():continue
            knowledge=knowledge_for_prompt(c,a,a,now)
            promises=open_commitments(c,a['id'])
            relations=relationships.for_card(c,a['id'])
            # Reserve the day before any network call, including empty/failed proposals.
            marker=insert(c,{'agent_id':a['id'],'action':'stay_home','sim_day':now.date().isoformat(),'start_at':now.strftime(DUE_FMT),'end_at':now.strftime(DUE_FMT),'status':'cancelled','reason':'Daily planning attempted.'})
        timetable=[]
        for hour in range(7,24):
            t=now.replace(hour=hour,minute=0)
            loc,act=world.routine(a['name'],t)
            timetable.append(f"{hour:02d}:00 {act} at {loc} ({'free' if world.is_free(a['name'],t) else 'working or asleep'})")
        prompt=f'''You are {a['name']}, {a['occupation']}. {a['personality']} Goal: {a['current_goal']}.
It is {now.strftime(DUE_FMT)}. Most days you simply follow your routine; return an empty list unless you have a real reason.
Return JSON {{"plans": [{{"action":"visit|phone|stay_home","place":"pub|shop|null","person":"full NPC name or null","hour":0,"minute":0,"duration_minutes":30,"fulfils":null,"reason":"one sentence"}}]}}.
Use actual JSON null, zero to two plans, minute 0 or 30, duration 30–180. Only later today, while free; places must be open throughout. Phone another NPC; stay_home only replaces an evening pub customer visit.
Timetable: {json.dumps(timetable)}
Public places: pub (Mon–Thu 16–23, Fri–Sat 12–24, Sun 12–22:30); shop (Mon–Sat 07–19).
Open promises with ids and deadlines: {json.dumps(promises)}
Relationships and cast: {json.dumps(relations)}
Your knowledge: {json.dumps(knowledge)}'''
        calls+=1
        try:result=client.propose(a['id'],[{'role':'user','content':prompt}],schema=DailyPlans,max_tokens=300)
        except LLMError:
            emit(f"Daily planning unavailable for {a['name']}.",'error');continue
        valid=0
        for proposal in result.plans:
            try:plan=validate(proposal,a,now,db_path)
            except (ValueError,TypeError):
                emit(f"Invalid daily plan dropped for {a['name']}.",'error');continue
            with connect(db_path) as c:insert(c,plan)
            valid+=1
        if valid:
            with connect(db_path) as c:c.execute('DELETE FROM plans WHERE id=?',(marker,))
    return calls


def today(c,agent_id,now):
    return [dict(r) for r in c.execute('SELECT * FROM plans WHERE agent_id=? AND sim_day=? ORDER BY start_at,id',(agent_id,now.date().isoformat()))]


def busy(c,agent_id):
    return c.execute("""SELECT 1 FROM conversations v LEFT JOIN agents a ON a.id=v.agent_a_id
        WHERE v.status='running' AND (v.agent_a_id=? OR v.agent_b_id=?)
        AND (a.kind!='player' OR EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id=v.id AND julianday(m.created_at)>=julianday('now','-3 minutes')))""",(agent_id,agent_id)).fetchone() is not None


def execute(client,now,db_path=DEFAULT_DB_PATH,auto=False):
    with connect(db_path) as c:
        rows=[dict(r) for r in c.execute("SELECT * FROM plans WHERE status IN ('planned','active') AND start_at<=? ORDER BY start_at,id",(now.strftime(DUE_FMT),))]
        agents={a['id']:a for a in npc_agents(c)}
    for p in rows:
        a=agents[p['agent_id']];status=None;outcome='';conversation_id=None
        if p['action']=='phone':
            if not auto:continue
            other=agents.get(p['person_id'])
            with connect(db_path) as c:reachable=other and world.routine(other['name'],now)[1]!='asleep' and not busy(c,other['id']) and not busy(c,a['id'])
            if reachable:
                from evorium.sim import run_conversation,get_conversation
                try:
                    conversation_id=run_conversation(client,a['id'],other['id'],4,db_path,location='On the phone')
                except ValueError:reachable=False
                if reachable:
                    conv=get_conversation(conversation_id,db_path)
                    status='done' if conv['status']=='completed' else 'missed'
                    outcome=conv['summary'] or 'Call did not complete.'
            if not reachable:
                if p['attempts']==0:
                    with connect(db_path) as c:c.execute('UPDATE plans SET attempts=1,start_at=? WHERE id=?',((now+timedelta(minutes=30)).strftime(DUE_FMT),p['id']))
                    continue
                status='missed';outcome='No answer.'
        elif p['status']=='planned' and p['end_at']<=now.strftime(DUE_FMT):
            status='missed';outcome='The planned time passed before the action could start.'
        elif p['end_at']<=now.strftime(DUE_FMT):
            status='done';outcome=f"Went to {places.REGISTRY.get(p['place'],'home')} as promised."
        elif p['status']=='planned':
            status='active';outcome=f"{a['name']} {'visited '+places.REGISTRY[p['place']] if p['action']=='visit' else 'stayed home'}: {p['reason']}"
        if status:
            with connect(db_path) as c:
                c.execute('UPDATE plans SET status=?,outcome=? WHERE id=?',(status,outcome,p['id']))
                if status=='done' and p['fulfils_commitment_id']:
                    resolve_commitment(c,p['fulfils_commitment_id'],'done',outcome,now,conversation_id)
                timeline.record(c,now,'action',outcome,3 if status=='done' and p['fulfils_commitment_id'] else 2,a['id'],p['person_id'],conversation_id)
