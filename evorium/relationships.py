"""Directed relationships: Python owns bounded changes and their evidence."""
from evorium import timeline

TRUST=('do not trust','are wary of','have no strong view on','trust','trust completely')
WARMTH=('dislike','are cool towards','are neutral about','like','are very fond of')


def band(value):
    return 0 if value<30 else 1 if value<45 else 2 if value<65 else 3 if value<80 else 4


def get(c,a,b):
    c.execute('INSERT INTO relationships(agent_id,other_id) VALUES (?,?) ON CONFLICT DO NOTHING',(a,b))
    return dict(c.execute('SELECT * FROM relationships WHERE agent_id=? AND other_id=?',(a,b)).fetchone())


def describe(row):
    return f"You {TRUST[band(row['trust'])]} and {WARMTH[band(row['warmth'])]} them."


def adjust(c,a,b,d_trust,d_warmth,reason,sim_at,conversation_id=None):
    before=get(c,a,b)
    trust=max(0,min(100,before['trust']+d_trust));warmth=max(0,min(100,before['warmth']+d_warmth))
    c.execute("UPDATE relationships SET trust=?,warmth=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE agent_id=? AND other_id=?",(trust,warmth,a,b))
    c.execute('''INSERT INTO relationship_events(agent_id,other_id,d_trust,d_warmth,reason,conversation_id,sim_at)
        VALUES (?,?,?,?,?,?,?)''',(a,b,trust-before['trust'],warmth-before['warmth'],reason,conversation_id,sim_at.strftime(timeline.FMT) if hasattr(sim_at,'strftime') else sim_at))
    after={**before,'trust':trust,'warmth':warmth}
    if abs(d_trust)>=8 or abs(d_warmth)>=8 or band(trust)!=band(before['trust']) or band(warmth)!=band(before['warmth']):
        names={r['id']:r['name'] for r in c.execute('SELECT id,name FROM agents WHERE id IN (?,?)',(a,b))}
        timeline.record(c,sim_at,'relationship',f"{names[a]} → {names[b]}: {describe(after)} (was: {describe(before)}) — {reason}",3,a,b,conversation_id)
    return after


def familiar(c,a,b):
    for first,other in ((a,b),(b,a)):
        get(c,first,other)
        c.execute("UPDATE relationships SET familiarity=min(100,familiarity+1),updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE agent_id=? AND other_id=?",(first,other))


def for_card(c,aid):
    result=[]
    for other in c.execute("SELECT id,name FROM agents WHERE kind!='system' AND id!=? ORDER BY id",(aid,)).fetchall():
        r=get(c,aid,other['id'])
        reason=c.execute('SELECT reason FROM relationship_events WHERE agent_id=? AND other_id=? ORDER BY id DESC LIMIT 1',(aid,other['id'])).fetchone()
        result.append({'id':other['id'],'name':other['name'],'trust':TRUST[band(r['trust'])],'warmth':WARMTH[band(r['warmth'])],'reason':reason[0] if reason else ''})
    return result


def seed(c):
    names={r['name']:r['id'] for r in c.execute("SELECT id,name FROM agents WHERE kind!='system'")}
    def insert(a,b,trust,warmth):
        if a in names and b in names:c.execute('INSERT INTO relationships(agent_id,other_id,trust,warmth) VALUES (?,?,?,?) ON CONFLICT DO NOTHING',(names[a],names[b],trust,warmth))
    pairs=[('Dez Whitworth','Tommy Shaw',80,75),('Tommy Shaw','Jess Hartley',65,70),('Raj Patel','Dez Whitworth',60,55),('Raj Patel','Tommy Shaw',55,55),('Brenda Ashworth','Tommy Shaw',75,70),('Brenda Ashworth','Dez Whitworth',60,60),('Mohammed "Mo" Iqbal','Raj Patel',65,65),('Mohammed "Mo" Iqbal','Dez Whitworth',55,60)]
    for a,b,t,w in pairs:insert(a,b,t,w);insert(b,a,t,w)
    insert('Dez Whitworth','Jess Hartley',75,65);insert('Jess Hartley','Dez Whitworth',65,65)
    for name in names:
        if name!='Simon Ferris':insert('Simon Ferris',name,40,45);insert(name,'Simon Ferris',40,45)
    for a in names:
        for b in names:
            if a!=b:insert(a,b,50,50)
