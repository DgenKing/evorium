"""The only places where public encounters can happen."""
from evorium import world
from evorium.db import DEFAULT_DB_PATH, connect, npc_agents

REGISTRY={'pub':world.PUB,'shop':"Patel's News, Ancoats"}


def is_open(key, now, stats=None):
    stats = stats or {}
    if key=='pub':return world.pub_open(now, stats)
    if stats.get('shop.open', 1) == 0:return False
    return key=='shop' and now.weekday()<6 and 7<=now.hour<19


def present(now, db_path=DEFAULT_DB_PATH):
    with connect(db_path) as c:
        from evorium.economy import stats
        values=stats(c)
        agents=npc_agents(c)
    result={key:[] for key in REGISTRY}
    for agent in agents:
        loc,activity=world.whereabouts(agent,now,db_path)
        agent.update(location=loc,activity=activity)
        for key,name in REGISTRY.items():
            if loc==name and is_open(key,now,values):result[key].append(agent)
    return result


def describe(now, db_path=DEFAULT_DB_PATH):
    people=present(now,db_path)
    from evorium.economy import read
    values=read(db_path)
    return [{'key':key,'name':name,'open':is_open(key,now,values),'reason':'' if is_open(key,now,values) else 'Closed at this time.',
             'people':[{'id':a['id'],'name':a['name']} for a in people[key]]} for key,name in REGISTRY.items()]


def opportunities(now,gap,db_path=DEFAULT_DB_PATH):
    """Oldest-served place first so faster clocks cannot starve the shop."""
    from evorium.tick import conversation_due
    people=present(now,db_path)
    with connect(db_path) as c:
        last={key:c.execute('SELECT coalesce(max(id),0) FROM conversations WHERE location=?',(name,)).fetchone()[0] for key,name in REGISTRY.items()}
    return [(key,people[key]) for key in sorted(REGISTRY,key=lambda key:last[key])
            if len(people[key])>=2 and conversation_due(now,gap,db_path,REGISTRY[key])]
