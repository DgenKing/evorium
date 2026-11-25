"""Human participation, isolated request lock, and ordinary conversation notes."""
import threading
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from evorium import accounts, world, places, timeline, relationships, backoff
from evorium.db import DEFAULT_DB_PATH, connect
from evorium.memory import DUE_FMT, knowledge_for_prompt, open_commitments, resolve_commitment
from evorium.llm import InvalidProposal, LLMError
from evorium.prompts import build_messages
from evorium import sim

lock=threading.RLock()


def row(c):
    return accounts.player_row(c)


def opened(c):
    me = row(c)
    return c.execute("""SELECT * FROM conversations WHERE agent_a_id=? AND status='running'
        ORDER BY id DESC LIMIT 1""", (me['id'],)).fetchone()


def state(db_path=DEFAULT_DB_PATH):
    now=world.now(db_path)
    with connect(db_path) as c:
        me=row(c);conv=opened(c)
        learned=[dict(r) for r in c.execute('''SELECT f.*,a.name AS by_name FROM facts f
            LEFT JOIN agents a ON a.id=f.source_agent_id WHERE f.agent_id=? AND f.importance>=3 ORDER BY f.id DESC LIMIT 15''',(me['id'],))]
        promises=open_commitments(c,me['id'],limit=None)
        others=accounts.other_players(c)
        from evorium import cases
        police = cases.player_view(c, me['id'])
    return {'id':me['id'],'name':me['name'],'about':me['occupation'], 'place':world.get_setting(accounts.setting_key('player_place'),'',db_path),
            'conversation':sim.get_conversation(conv['id'],db_path) if conv else None,
            'police':police,'promises':promises,'learned':learned,'places':places.describe(now,db_path),'other_players':others}


def profile(name,about,db_path=DEFAULT_DB_PATH):
    name=name.strip();about=about.strip()
    if not 2<=len(name)<=30 or len(about)>200:raise HTTPException(409,'Use a name of 2–30 characters and an about of up to 200 characters.')
    with lock,connect(db_path) as c:
        c.execute('BEGIN IMMEDIATE')
        if opened(c):raise HTTPException(409,'End your conversation before changing your profile.')
        me=row(c)
        names=[r[0].casefold() for r in c.execute("SELECT name FROM agents WHERE id!=?", (me['id'],))]
        if name.casefold() in names or name.split()[0].casefold() in [n.split()[0] for n in names]:raise HTTPException(409,'Choose a name different from the characters.')
        c.execute("UPDATE agents SET name=?,occupation=? WHERE id=?",(name,about,me['id']))
    return state(db_path)


def close(client, db_path=DEFAULT_DB_PATH):
    with lock:
        with connect(db_path) as c:
            conv=opened(c)
            if not conv:return None
            a=sim._agent(c,conv['agent_a_id']);b=sim._agent(c,conv['agent_b_id'])
        full=sim.get_conversation(conv['id'],db_path)
        transcript=[{'speaker_name':m['speaker_name'],'text':m['text']} for m in full['messages']]
        summary=sim._take_notes(client,db_path,conv['id'],a,b,transcript,conv['sim_time']) if transcript and not backoff.paused() else ('They talked; detailed notes were unavailable while DeepSeek recovered.' if transcript else 'No words exchanged.')
        with connect(db_path) as c:
            from evorium import cases
            cases.spoken(c, conv['id'], world.now(db_path))
        sim._set_status(db_path,conv['id'],'completed',summary)
        now=world.now(db_path)
        with connect(db_path) as c:
            relationships.familiar(c,a['id'],b['id'])
            timeline.record(c,now,'conversation',summary,2,a['id'],b['id'],conv['id'])
            timeline.record(c,now,'player',f"{a['name']} finished talking with {b['name']}.",3,a['id'],b['id'],conv['id'])
        return conv['id']


def enter(client,place,db_path=DEFAULT_DB_PATH):
    with lock:
        now=world.now(db_path)
        if place not in places.REGISTRY:raise HTTPException(409,'Choose a public place.')
        if not places.is_open(place, now, places.opening_inputs(now, db_path)):raise HTTPException(409,'That place is shut right now.')
        if world.get_setting(accounts.setting_key('player_place'),'',db_path)!=place:close(client,db_path)
        with connect(db_path) as c:
            me=row(c);world._set(c,accounts.setting_key('player_place'),place)
            c.execute('UPDATE agents SET location=? WHERE id=?',(places.REGISTRY[place],me['id']))
            timeline.record(c,now,'player',f"{me['name']} entered {places.REGISTRY[place]}.",3,me['id'])
    return state(db_path)


def leave(client,db_path=DEFAULT_DB_PATH):
    with lock:
        close(client,db_path);now=world.now(db_path)
        with connect(db_path) as c:
            me=row(c);world._set(c,accounts.setting_key('player_place'),'')
            c.execute("UPDATE agents SET location='Not in the world' WHERE id=?",(me['id'],))
            timeline.record(c,now,'player',f"{me['name']} left.",3,me['id'])
    return state(db_path)


def say(client,to_agent_id,text,db_path=DEFAULT_DB_PATH):
    with lock:
        if backoff.paused():raise HTTPException(503,"DeepSeek is paused while the service recovers.")
        now=world.now(db_path);text=text.strip();place=world.get_setting(accounts.setting_key('player_place'),'',db_path)
        if not 1<=len(text)<=500:raise HTTPException(409,'Say between 1 and 500 characters.')
        if not place:
            # Outside the pub and shop means you're on Henry Street: talking to someone there puts you on the street.
            if not any(a['id']==to_agent_id for a in places.present(now,db_path).get('street',[])):
                raise HTTPException(409,'Walk into a place before speaking.')
            place='street'
            with connect(db_path) as c:
                me=row(c);world._set(c,accounts.setting_key('player_place'),'street')
                c.execute('UPDATE agents SET location=? WHERE id=?',(world.STREET,me['id']))
        target=next((a for a in places.present(now,db_path).get(place,[]) if a['id']==to_agent_id),None)
        if target is None:raise HTTPException(409,'That person is not here right now.')
        with connect(db_path) as c:
            current=opened(c)
        if current and current['agent_b_id']!=to_agent_id:close(client,db_path)
        with connect(db_path) as c:
            c.execute('BEGIN IMMEDIATE')
            me=row(c);current=opened(c)
            busy=c.execute("""SELECT v.*,a.name AS a_name,b.name AS b_name FROM conversations v
                JOIN agents a ON a.id=v.agent_a_id JOIN agents b ON b.id=v.agent_b_id
                WHERE v.status='running' AND a.kind='npc' AND b.kind='npc' AND (a.id=? OR b.id=?)""",(to_agent_id,to_agent_id)).fetchone()
            rival=c.execute("""SELECT a.name FROM conversations v JOIN agents a ON a.id=v.agent_a_id
                WHERE a.kind='player' AND a.id!=? AND v.agent_b_id=? AND v.status='running'
                AND EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id=v.id
                    AND julianday(m.created_at)>=julianday('now','-3 minutes'))
                ORDER BY v.id DESC LIMIT 1""",(me['id'],to_agent_id)).fetchone()
            if rival:
                raise HTTPException(409,f"{target['name'].split()[0]} is talking to {rival['name']} at the moment.")
            if busy:
                other=busy['b_name'] if busy['agent_a_id']==to_agent_id else busy['a_name']
                raise HTTPException(409,f"{target['name'].split()[0]} is talking to {other.split()[0]} at the moment. Try again in a minute.")
            if current and c.execute('SELECT count(*) FROM messages WHERE conversation_id=?',(current['id'],)).fetchone()[0]+2>40:
                raise HTTPException(409,'This conversation has no room for another exchange within the 40-message limit. End it before starting another.')
            cid=current['id'] if current else c.execute('''INSERT INTO conversations
                (location,status,sim_time,sim_at,agent_a_id,agent_b_id) VALUES (?,'running',?,?,?,?)''',
                (places.REGISTRY[place],world.describe(now),now.strftime(DUE_FMT),me['id'],to_agent_id)).lastrowid
            c.execute('INSERT INTO messages(conversation_id,speaker_id,text,rationale,sim_time) VALUES (?,?,?,?,?)',(cid,me['id'],text,'(player)',world.describe(now)))
            knowledge=knowledge_for_prompt(c,target,me,now)
        full=sim.get_conversation(cid,db_path)
        transcript=[{'speaker_name':m['speaker_name'],'text':m['text']} for m in full['messages']]
        try:proposal=client.propose(to_agent_id,build_messages(target,me,transcript,knowledge,world.describe(now)))
        except InvalidProposal:raise HTTPException(502,"They didn't seem to hear you. Try again.") from None
        except LLMError as exc:raise HTTPException(502,str(exc)) from None
        with connect(db_path) as c:
            c.execute('INSERT INTO messages(conversation_id,speaker_id,text,rationale,sim_time) VALUES (?,?,?,?,?)',(cid,to_agent_id,proposal.say,proposal.rationale,world.describe(now)))
            c.execute('UPDATE agents SET mood=? WHERE id=?',(proposal.mood.lower(),to_agent_id))
        return {'conversation_id':cid,'reply':{'text':proposal.say,'rationale':proposal.rationale,'mood':proposal.mood}}


def resolve(promise_id,done,note,db_path=DEFAULT_DB_PATH):
    with lock:
        now=world.now(db_path)
        with connect(db_path) as c:
            me=row(c)
            p=c.execute("SELECT * FROM commitments WHERE id=? AND agent_id=? AND status='open' AND lapsed_at IS NULL",(promise_id,me['id'])).fetchone()
            if not p:raise HTTPException(409,'That is not one of your open promises.')
            resolve_commitment(c,promise_id,'done' if done else 'broken',note.strip()[:300] or ('Done.' if done else "Didn't do it."),now)
    return state(db_path)


def maintenance(client,now,db_path=DEFAULT_DB_PATH,startup=False):
    if not lock.acquire(blocking=False):return
    try:
        with connect(db_path) as c:
            players = [dict(r) for r in c.execute("SELECT * FROM agents WHERE kind='player' AND account IS NOT NULL")]
            due=c.execute("""SELECT p.id FROM commitments p JOIN agents a ON a.id=p.agent_id
                WHERE a.kind='player' AND p.status='open' AND p.lapsed_at IS NULL AND p.due_at<?""",((now-timedelta(hours=24)).strftime(DUE_FMT),)).fetchall()
            for p in due:resolve_commitment(c,p['id'],'broken','Never heard back.',now)
        for who in players:
            token=accounts.current.set(who['account'])
            try:
                while True:
                    with connect(db_path) as c:
                        current=opened(c)
                        if current:
                            last=c.execute('SELECT max(created_at) FROM messages WHERE conversation_id=? AND speaker_id=?',
                                (current['id'],current['agent_a_id'])).fetchone()[0] or current['started_at']
                            inactive=datetime.now(timezone.utc)-datetime.fromisoformat(last.replace('Z','+00:00'))>=timedelta(minutes=5)
                        else:inactive=False
                    if not current or not (startup or inactive):break
                    close(client,db_path)
            finally:
                accounts.current.reset(token)
    finally:lock.release()
