"""Conservative, infrequent proposals for a stalled world."""
import json
import re
from datetime import datetime,timedelta
from typing import Literal
from pydantic import BaseModel,Field,ConfigDict
from evorium import world,places,plans,timeline
from evorium.db import DEFAULT_DB_PATH,connect,npc_agents,system_id
from evorium.events import emit
from evorium.llm import LLMError
from evorium.memory import DUE_FMT

CHECK_EVERY_HOURS=2
LOOP_WINDOW_HOURS=6
LOOP_CONVERSATIONS=3


class Proposal(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True,populate_by_name=True)
    type: Literal['letter','phone_call','small_incident','chance_meeting']
    for_name: str = Field(alias='for')
    with_name: str | None = Field(default=None,alias='with')
    content: str = Field(min_length=1,max_length=300)
    in_hours: int = Field(ge=1,le=24)
    rationale: str = Field(min_length=1,max_length=300)


def stall_report(now,db_path=DEFAULT_DB_PATH):
    low=(now-timedelta(hours=24)).strftime(DUE_FMT);high=(now+timedelta(hours=24)).strftime(DUE_FMT)
    with connect(db_path) as c:
        important=c.execute('SELECT 1 FROM timeline WHERE importance>=3 AND sim_at>=? AND sim_at<=? LIMIT 1',(low,now.strftime(DUE_FMT))).fetchone() is not None
        pending=c.execute('SELECT 1 FROM scheduled_events WHERE delivered=0 AND at<=? LIMIT 1',(high,)).fetchone() is not None
        recent=c.execute("SELECT 1 FROM scheduled_events WHERE origin='director' AND delivered=1 AND at>=? AND at<=?",(low,now.strftime(DUE_FMT))).fetchone() is not None
        recent=recent or c.execute("SELECT 1 FROM timeline WHERE kind='director' AND sim_at>=? AND sim_at<=?",(low,now.strftime(DUE_FMT))).fetchone() is not None
        # Going round in circles: the same subject in several conversations lately, and nothing serious happening.
        loop_low=(now-timedelta(hours=LOOP_WINDOW_HOURS)).strftime(DUE_FMT)
        looping=c.execute("""SELECT f.subject FROM facts f JOIN conversations v ON v.id=f.source_conversation_id
            WHERE v.sim_at>=? AND v.sim_at<=? GROUP BY f.subject HAVING COUNT(DISTINCT v.id)>=? LIMIT 1""",
            (loop_low,now.strftime(DUE_FMT),LOOP_CONVERSATIONS)).fetchone()
        serious=c.execute('SELECT 1 FROM timeline WHERE importance>=4 AND sim_at>=? AND sim_at<=? LIMIT 1',(low,now.strftime(DUE_FMT))).fetchone() is not None
    looping=looping[0] if looping and not serious else None
    stalled=not (important or pending or recent) or bool(looping and not pending and not recent)
    return {'stalled':stalled,'recent_important':important,'pending_event':pending,'recent_director':recent,'looping_on':looping}


def validate(proposal,now,db_path=DEFAULT_DB_PATH):
    p=Proposal.model_validate(proposal)
    with connect(db_path) as c:
        cast={a['name']:a for a in npc_agents(c)}
        names=[r[0] for r in c.execute('SELECT name FROM npcs')]
        seeds=[r[0] for r in c.execute("SELECT content FROM facts WHERE source='seed'")]+[r[0] for r in c.execute("SELECT content FROM scheduled_events WHERE origin='seed'")]
        exists=c.execute("SELECT 1 FROM timeline WHERE kind='director' AND substr(sim_at,1,10)=?",(now.date().isoformat(),)).fetchone()
    if exists:raise ValueError('Only one director event per sim day.')
    if p.for_name not in cast or (p.type=='chance_meeting' and (p.with_name not in cast or p.with_name==p.for_name)):
        raise ValueError('Director participants must be distinct NPCs.')
    if '£' in p.content or re.search(r'\d[\d,.]*\s*(?:k\b|thousand\b)',p.content,re.I):raise ValueError('Director cannot set money terms.')
    # Reject unfamiliar proper-name tokens. This deliberately prefers dropping a proposal
    # over admitting an invented person; no NER service or additional model call.
    known_text=' '.join([*cast,*names,*seeds])
    allowed={word.casefold() for word in re.findall(r"[A-Za-z][A-Za-z'-]*",known_text)}
    allowed.update(w.casefold() for w in ['You','Your','A','An','The','It','They','He','She','I','Please','Dear','We','Someone','There','This','After','At','When','While','One'])
    capitalised=re.findall(r"\b[A-Z][a-z]+(?:[-'][A-Za-z]+)*\b",p.content)
    if any(word.casefold() not in allowed for word in capitalised):raise ValueError('Unrecognised person or organisation in content.')
    # Lower-case full unknown names after a sender cue are also rejected.
    sender=re.search(r'\bfrom\s+([a-z]+\s+[a-z]+)',p.content)
    if sender and all(word.casefold() not in allowed for word in sender.group(1).split()):raise ValueError('Unknown sender.')
    if p.type=='small_incident':
        if not re.search(r'\b(barrel|late delivery|burst pipe|child.{0,30}(?:ill|sick)|(?:ill|sick).{0,30}child)\b',p.content,re.I):
            raise ValueError('Only a barrel going off, late delivery, burst pipe or child off school ill.')
        if re.search(r'\b(fire|dead|death|police|arrest|evict|demoli|closure|redevelop|rent|lease|offer|injur|hospital|explosion|robbery)\w*',p.content,re.I):raise ValueError('Incident is not mundane.')
    if p.type in ('letter','phone_call'):
        # Seeded correspondents and organisations only, never a newly invented NPC.
        seeded_text=' '.join(seeds)
        correspondents=[name for name in cast if name in seeded_text]
        correspondents += re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b',seeded_text)
        # A member of the cast is an established person even without a seed fact naming them.
        correspondents += list(cast)
        if not any(name.casefold() in p.content.casefold() for name in correspondents):raise ValueError('Letter or phone call must identify an established sender.')
        if re.search(r'\b(agreed|approved|sold|signed|demolish|evict|new rent|new offer)\b',p.content,re.I):raise ValueError('Director cannot settle established story terms.')
    return p,cast


def check(client,now,db_path=DEFAULT_DB_PATH):
    if world.get_setting('director','1',db_path)!='1':return False
    previous=world.get_setting('director_check',None,db_path)
    if previous and timedelta(0)<=now-datetime.strptime(previous,DUE_FMT)<timedelta(hours=CHECK_EVERY_HOURS):return False
    world.set_setting('director_check',now.strftime(DUE_FMT),db_path)
    report=stall_report(now,db_path)
    if not report['stalled']:return False
    with connect(db_path) as c:
        if c.execute("SELECT 1 FROM timeline WHERE kind='director' AND substr(sim_at,1,10)=?",(now.date().isoformat(),)).fetchone():return False
        cast=npc_agents(c);aid=system_id(c)
        known=[r[0] for r in c.execute('SELECT name FROM npcs')]
    recent=timeline.entries(db_path,since=(now-timedelta(days=3)).strftime(DUE_FMT),until=now.strftime(DUE_FMT))
    prompt='''Nudge a stalled Manchester neighbourhood with one mundane event. Invent no people or money terms, and do not contradict existing facts.
Return JSON {"type":"small_incident","for":"full cast name","with":null,"content":"one or two sentences in second person, at most 300 characters","in_hours":1,"rationale":"why this helps"}.
Allowed types: letter, phone_call, small_incident, chance_meeting. For a letter or phone call name an established sender, asking for an update or arranging an ordinary appointment; do not settle offers, leases or planning decisions.
Small incidents ONLY: a barrel going off, late delivery, burst pipe, child off school ill. Chance meetings require two cast members and free time in an open pub or shop. No new fact is created for a meeting.
'''+(f"Conversations keep circling back to '{report['looping_on']}'. Give someone something different to think or talk about. " if report['looping_on'] else '')+f"Now: {now.strftime(DUE_FMT)}. Cast: {json.dumps([{'name':a['name'],'occupation':a['occupation']} for a in cast])}. Other known people: {json.dumps(known)}. Established organisation: Northgate Estates.\nRecent timeline: {json.dumps([{'at':e['sim_at'],'text':e['text']} for e in recent])}"
    try:
        proposal=client.propose(aid,[{'role':'user','content':prompt}],schema=Proposal,max_tokens=300)
        p,cast=validate(proposal,now,db_path)
        at=(now+timedelta(hours=p.in_hours)).replace(second=0,microsecond=0)
        meeting=[]
        if p.type=='chance_meeting':
            # Pick the earliest half-hour at/after the requested delay, within 24 hours.
            slot=at.replace(minute=0 if at.minute==0 else 30 if at.minute<=30 else 0)
            if slot<at:slot+=timedelta(hours=1) if at.minute>30 else timedelta(minutes=30)
            found=False
            while slot<=now+timedelta(hours=24):
                for place in places.REGISTRY:
                    try:
                        meeting=[plans.validate({'action':'visit','place':place,'hour':slot.hour,'minute':slot.minute,'duration_minutes':30,'reason':p.content},cast[name],slot.replace(hour=0,minute=0) if slot.date()!=now.date() else now,db_path) for name in (p.for_name,p.with_name)]
                        # validate uses the provided day's date. For tomorrow, use midnight exactly.
                        if any(x['start_at']!=slot.strftime(DUE_FMT) for x in meeting):raise ValueError('Wrong meeting day.')
                        found=True;break
                    except ValueError:continue
                if found:break
                slot+=timedelta(minutes=30)
            if not found:raise ValueError('No valid free meeting slot.')
        with connect(db_path) as c:
            if meeting:
                for plan in meeting:plans.insert(c,plan)
            else:
                c.execute("INSERT INTO scheduled_events(at,agent_id,subject,content,origin) VALUES (?,?,?,?,'director')",(at.strftime(DUE_FMT),cast[p.for_name]['id'],p.type,p.content))
            timeline.record(c,now,'director',f"{p.type.replace('_',' ')} for {p.for_name}: {p.content} — {p.rationale}",4,cast[p.for_name]['id'],cast[p.with_name]['id'] if meeting else None)
        return True
    except (LLMError,ValueError,TypeError):
        emit(f'Director proposal dropped or unavailable. Next check in {CHECK_EVERY_HOURS} sim-hours.','error')
        return False
