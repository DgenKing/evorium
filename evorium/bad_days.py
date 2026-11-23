"""Deterministic ordinary setbacks, persisted once daily. No model calls or routine-side reads."""
import hashlib
import json
from datetime import datetime,timedelta
from evorium import world,timeline
from evorium.db import connect,DEFAULT_DB_PATH,npc_agents
from evorium.memory import DUE_FMT

LABELS={'off_sick':'Off sick today','running_late':'Running late','hungover':'Hungover','none':''}
MOODS={'off_sick':'under the weather','hungover':'rough'}


def choose(name,day,late_pub=False,critical=False):
    if critical:return {'kind':'none','delay':0,'exempt':True}
    digest=hashlib.sha256(f'{name}|{day}'.encode()).digest()
    roll=int.from_bytes(digest[:8],'big')%10000
    if roll<300:kind='off_sick'
    elif roll<900:kind='running_late'
    elif late_pub and roll<4400:kind='hungover'
    else:kind='none'
    return {'kind':kind,'delay':60 if kind=='hungover' else 30+digest[8]%31 if kind=='running_late' else 0}


def critical(c,actor,now):
    day=now.strftime('%Y-%m-%d');aid=actor['id']
    if c.execute("SELECT 1 FROM scheduled_events WHERE agent_id=? AND substr(at,1,10)=? AND origin='seed'",(aid,day)).fetchone():return True
    if c.execute("SELECT 1 FROM offers WHERE status='open' AND (to_id=? OR from_id=?) AND substr(expires_at,1,10)=?",(aid,aid,day)).fetchone():return True
    if c.execute("SELECT 1 FROM commitments WHERE agent_id=? AND status='open' AND lapsed_at IS NULL AND (substr(due_at,1,10)=? OR substr(retry_at,1,10)=?)",(aid,day,day)).fetchone():return True
    return actor['name'].split()[0] in ('Dez','Gary') and day in ('2026-12-05','2026-12-20','2026-12-24','2026-12-31')


def _load(c,key):return json.loads(world._get(c,key,'{}'))


def records(c,now):return _load(c,'bad_days:'+now.strftime('%Y-%m-%d'))


def late_attendance(c,day):
    """Actual tick presence or a recorded conversation, never presumed drinking from a routine."""
    ids=set(_load(c,'late_pub:'+day).get('ids',[]))
    for r in c.execute("""SELECT v.agent_a_id,v.agent_b_id FROM conversations v WHERE v.location=?
        AND substr(v.sim_at,1,10)=? AND substr(v.sim_at,12,5)>'23:00' AND v.status IN ('running','completed')
        AND EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id=v.id)""",(world.PUB,day)):
        ids.update(r)
    return ids


def first_activity(name,now,stats):
    midnight=now.replace(hour=0,minute=0,second=0,microsecond=0)
    seen_home=False
    for minutes in range(0,24*60,5):
        at=midnight+timedelta(minutes=minutes)
        place,activity=world.routine(name,at,{**stats,'_bad_days':{}})
        if place==world.home_location(name):seen_home=True
        # A night driver's shift continuing across midnight is not a new morning departure.
        if seen_home and place!=world.home_location(name) and activity!='asleep':return at
    return midnight.replace(hour=9)


def blocks(record,now):
    if record.get('kind')=='off_sick':return True
    return bool(record.get('start') and record['start']<=now.strftime(DUE_FMT)<record.get('until',''))


def restore(c,aid,record):
    if record.get('mood_applied') and not record.get('mood_restored'):
        c.execute('UPDATE agents SET mood=? WHERE id=? AND mood=?',(record['mood_before'],aid,record['mood_applied']))
        record['mood_restored']=True


def maintain(now,db_path=DEFAULT_DB_PATH):
    day=now.strftime('%Y-%m-%d');key='bad_days:'+day
    with connect(db_path) as c:
        c.execute('BEGIN IMMEDIATE')
        old_day=world._get(c,'bad_days:last_day')
        if old_day and old_day!=day:
            old=_load(c,'bad_days:'+old_day)
            for aid,record in old.items():restore(c,int(aid),record)
            world._set(c,'bad_days:'+old_day,json.dumps(old))
        cast=npc_agents(c);today=records(c,now)
        eligible=late_attendance(c,(now-timedelta(days=1)).strftime('%Y-%m-%d'))
        inputs=world.routine_inputs(c,now)
        # Choose everybody before applying effects, so Jess's absence can reserve Dez to cover.
        for actor in cast:
            aid=str(actor['id'])
            if aid not in today:
                record=choose(actor['name'],day,actor['id'] in eligible,critical(c,actor,now))
                record['name']=actor['name'];record['new']=True
                today[aid]=record
        jess=next((r for r in today.values() if r['name'].startswith('Jess ')),{})
        for actor in cast:
            aid=str(actor['id']);record=today[aid]
            if record['kind']!='none' and critical(c,actor,now):
                restore(c,actor['id'],record);record.update(kind='none',exempt=True)
            if actor['name'].startswith('Dez ') and jess.get('kind')=='off_sick' and record['kind']=='off_sick':
                restore(c,actor['id'],record);record['kind']='none'
            if record.pop('new',False) and record['kind']!='none':
                start=first_activity(actor['name'],now,inputs)
                record['start']=start.strftime(DUE_FMT);record['until']=(start+timedelta(minutes=record['delay'])).strftime(DUE_FMT)
                record['mood_before']=actor['mood'];record['mood_applied']=MOODS.get(record['kind'])
                if record['mood_applied']:c.execute('UPDATE agents SET mood=? WHERE id=?',(record['mood_applied'],actor['id']))
                wording={'off_sick':"I'm off sick today.",'running_late':f"I'm running {record['delay']} minutes late for my first activity today.",'hungover':"I'm hungover after last night's late visit to the Billet; I'm taking the morning slowly."}[record['kind']]
                c.execute("INSERT INTO facts(agent_id,subject,content,source,importance) VALUES (?,'bad day',?,'observed',3)",(actor['id'],day+': '+wording))
                timeline.record(c,now,'bad_day',actor['name']+': '+LABELS[record['kind']],1,actor['id'])
            if record['kind']=='hungover' and now.strftime(DUE_FMT)>=max(record.get('until',''),day+' 12:00'):restore(c,actor['id'],record)
        world._set(c,key,json.dumps(today));world._set(c,'bad_days:last_day',day)
    if now.hour>=23:
        present={actor['id'] for actor in cast if world.whereabouts(actor,now,db_path)[0]==world.PUB}
        with connect(db_path) as c:
            c.execute('BEGIN IMMEDIATE')
            present.update(_load(c,'late_pub:'+day).get('ids',[]))
            world._set(c,'late_pub:'+day,json.dumps({'ids':sorted(present)}))



def prompt(record,now):
    kind=record.get('kind')
    if kind=='off_sick':return 'You are off sick today.'
    if kind=='hungover':return 'You feel rough this morning.' if now.hour<12 else 'You had a rough start today.'
    if kind=='running_late':return 'Your first activity starts '+str(record['delay'])+' minutes late today.'
    return ''
