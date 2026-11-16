"""Permanent simulation history and bounded daily digests."""
from datetime import datetime, timedelta
from pydantic import BaseModel, ConfigDict, Field
from evorium.db import DEFAULT_DB_PATH, connect, system_id
from evorium.llm import LLMError
from evorium import world

FMT = '%Y-%m-%d %H:%M'


def record(connection, sim_at, kind, text, importance, agent_id=None, other_id=None, conversation_id=None):
    if isinstance(sim_at, datetime):
        sim_at = sim_at.strftime(FMT)
    return connection.execute('''INSERT INTO timeline
        (sim_at,kind,text,importance,agent_id,other_id,conversation_id) VALUES (?,?,?,?,?,?,?)''',
        (sim_at,kind,text,importance,agent_id,other_id,conversation_id)).lastrowid


def entries(db_path=DEFAULT_DB_PATH, since=None, until=None, agent_id=None, kinds=None, min_importance=1, limit=500):
    clauses=['t.importance>=?']; params=[min_importance]
    for column, op, value in [('sim_at','>=',since),('sim_at','<=',until)]:
        if value:
            clauses.append(f't.{column}{op}?'); params.append(value)
    if agent_id is not None:
        clauses.append('(t.agent_id=? OR t.other_id=?)'); params.extend([agent_id,agent_id])
    if kinds:
        clauses.append('t.kind IN ('+','.join('?' for _ in kinds)+')'); params.extend(kinds)
    params.append(max(1,min(limit,500)))
    with connect(db_path) as c:
        return [dict(r) for r in c.execute('''SELECT t.*, a.name AS agent_name, b.name AS other_name
            FROM timeline t LEFT JOIN agents a ON a.id=t.agent_id LEFT JOIN agents b ON b.id=t.other_id
            WHERE '''+' AND '.join(clauses)+' ORDER BY t.sim_at DESC,t.id DESC LIMIT ?',params)]


def days(db_path=DEFAULT_DB_PATH, **filters):
    grouped={}
    for entry in entries(db_path,**filters):
        day=entry['sim_at'][:10]
        grouped.setdefault(day,{'day':day,'label':datetime.strptime(day,'%Y-%m-%d').strftime('%A %d %B'),'digest':None,'entries':[]})['entries'].append(entry)
    with connect(db_path) as c:
        for day, group in grouped.items():
            row=c.execute('SELECT text FROM digests WHERE day=?',(day,)).fetchone()
            group['digest']=row[0] if row else None
    return {'days':list(grouped.values())}


class Digest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    digest: str = Field(min_length=1,max_length=1800)


def daily_digest(client, now, db_path=DEFAULT_DB_PATH):
    day=(now-timedelta(days=1)).strftime('%Y-%m-%d')
    with connect(db_path) as c:
        if c.execute('SELECT 1 FROM digests WHERE day=?',(day,)).fetchone(): return False
        rows=c.execute('SELECT sim_at,text FROM timeline WHERE substr(sim_at,1,10)=? AND importance>=2 ORDER BY sim_at,id',(day,)).fetchall()
        if len(rows)<3: return False
        key='digest_attempts:'+day
        attempts=int(world._get(c,key,'0'))
        if attempts>=2: return False
        world._set(c,key,attempts+1)
        aid=system_id(c)
    try:
        result=client.propose(aid,[{'role':'user','content':
            'Summarise this day in 3 to 5 sentences, plain past tense. Name people; invent nothing. Return JSON {"digest":"..."}.\n'+
            '\n'.join(r['sim_at']+' '+r['text'] for r in rows)}],schema=Digest,max_tokens=250)
    except LLMError:
        return False
    with connect(db_path) as c:
        c.execute('INSERT INTO digests(day,text) VALUES (?,?) ON CONFLICT(day) DO NOTHING',(day,result.digest))
    return True
