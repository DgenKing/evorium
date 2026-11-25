"""Brief encounters triggered by routine arrivals. No simulation work happens in the browser."""
from datetime import datetime, timezone
from itertools import combinations
import json

from evorium import places, weather, world
from evorium.db import connect
from evorium.plans import busy

DAY_LIMIT = 24
EVENING_LIMIT = 40
ARRIVAL_SECONDS = 60
DISPLAY_SECONDS = 6
STATE_KEY = 'scene.greetings'


def _lines(now, condition, listener):
    first = listener.split()[0]
    salutation = 'Morning' if now.hour < 12 else 'Afternoon' if now.hour < 17 else 'Evening'
    if condition.get('raining'):
        return f'{salutation}, {first}. Some rain, eh?', 'I know. Absolutely soaking.'
    if condition.get('condition') == 'snow':
        return f'{salutation}, {first}. Watch your step.', 'Aye. Slippy out there.'
    return f'{salutation}, {first}. All right?', 'Not bad, ta. You?'


def active(settings, real_at=None):
    now = (real_at or datetime.now(timezone.utc)).timestamp()
    recent = json.loads(settings.get(STATE_KEY, '{}')).get('recent', [])
    return [line for line in recent if line['start'] + DISPLAY_SECONDS > now]


def _arrived(settings, person, now):
    arrival = json.loads(settings.get(f"scene.travel.{person['id']}", 'null'))
    return (arrival and arrival['to'] == person['location']
            and 0 <= now - arrival['started'] < ARRIVAL_SECONDS)


def _known(c, a, b):
    # Seeded acquaintances have a relationship outside the neutral default.
    return all(c.execute('''SELECT 1 FROM relationships WHERE agent_id=? AND other_id=?
                            AND (familiarity>0 OR trust!=50 OR warmth!=50)''', ids).fetchone()
               for ids in ((a,b), (b,a)))


def run(now, db_path, *, exclude=(), real_at=None):
    real_at = real_at or datetime.now(timezone.utc)
    stamp = real_at.timestamp()
    day = now.date().isoformat()
    sim_stamp = (now - datetime(1970, 1, 1)).total_seconds()
    evening = 17 <= now.hour < 23
    limit, gap = (EVENING_LIMIT, 15) if evening else (DAY_LIMIT, 30)
    groups = places.present(now, db_path)
    with connect(db_path) as c:
        c.execute('BEGIN IMMEDIATE')
        settings = dict(c.execute("SELECT key,value FROM world WHERE key=? OR key LIKE 'scene.travel.%'", (STATE_KEY,)))
        state = json.loads(settings.get(STATE_KEY, '{}'))
        if state.get('day') != day:
            state = {'day': day, 'pairs': [], 'last': {}, 'recent': []}
        if len(state['pairs']) >= limit:
            return False
        for key, people in groups.items():
            available = [p for p in people if p['id'] not in exclude and not busy(c, p['id'])
                         and sim_stamp - state['last'].get(str(p['id']), -1e12) >= gap*60]
            for a, b in combinations(available, 2):
                pair = sorted((a['id'], b['id']))
                if pair in state['pairs'] or not _known(c, *pair):
                    continue
                if _arrived(settings, b, stamp):
                    a, b = b, a
                elif not _arrived(settings, a, stamp):
                    continue
                state['pairs'].append(pair)
                state['last'].update({str(i): sim_stamp for i in pair})
                state['recent'] = active({STATE_KEY: json.dumps(state)}, real_at)
                lines = _lines(now, weather.read(c, now, real_at), b['name'])
                for index, (speaker, listener, text) in enumerate(((a,b,lines[0]), (b,a,lines[1]))):
                    state['recent'].append({'id': speaker['id'], 'to': listener['id'], 'place': key,
                                            'text': text, 'start': stamp + index * 3})
                world._set(c, STATE_KEY, json.dumps(state))
                return True
    return False
