"""The only places where public encounters can happen."""
from evorium import world
from evorium.db import DEFAULT_DB_PATH, connect, npc_agents

from evorium.place_registry import BY_LOCATION, PLACES, REGISTRY, map_entry


def is_open(key, now, stats=None):
    stats = stats or {}
    place = PLACES.get(key)
    if place is None or (place.rain_closes and stats.get('_weather', {}).get('raining')):
        return False
    if key == 'pub':
        return world.pub_open(now, stats)
    if key == 'shop' and stats.get('shop.open', 1) == 0:
        return False
    from evorium.calendar_uk import hours
    opening = hours(key, now)
    return bool(opening and opening[0] <= now.hour + now.minute / 60 < opening[1])


def opening_inputs(now, db_path):
    with connect(db_path) as c:
        from evorium import economy, weather
        return {**economy.stats(c), '_weather': weather.read(c, now)}


def present(now, db_path=DEFAULT_DB_PATH):
    with connect(db_path) as c:
        values = world.routine_inputs(c, now)
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
    values = opening_inputs(now, db_path)
    return [{'key':key,'name':name,'label':PLACES[key].name,'landmark':PLACES[key].landmark,'spots':PLACES[key].spots,'map':map_entry(PLACES[key]),'open':is_open(key,now,values),'reason':'' if is_open(key,now,values) else 'Closed at this time.',
             'people':[{'id':a['id'],'name':a['name']} for a in people[key]]} for key,name in REGISTRY.items()]


def opportunities(now,gap,db_path=DEFAULT_DB_PATH):
    """Oldest-served place first so faster clocks cannot starve the shop."""
    from evorium.tick import conversation_due
    people=present(now,db_path)
    with connect(db_path) as c:
        last={key:c.execute('SELECT coalesce(max(id),0) FROM conversations WHERE location=?',(name,)).fetchone()[0] for key,name in REGISTRY.items()}
        from evorium import cases
        preferred = {key: cases.priority(c, [a['id'] for a in people[key]], now) is not None for key in REGISTRY}
    return [(key,people[key]) for key in sorted(REGISTRY,key=lambda key:(not preferred[key], last[key]))
            if len(people[key])>=2 and conversation_due(now,gap,db_path,REGISTRY[key])]
