"""Brief encounters triggered by routine arrivals. No simulation work happens in the browser."""
from datetime import datetime, timezone
from itertools import combinations
import json

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError
from typing import Annotated

from evorium import places, world
from evorium.db import connect
from evorium.plans import busy

MAX_TOKENS = 90
DAILY_LIMIT = 24
ARRIVAL_SECONDS = 60
DISPLAY_SECONDS = 6
STATE_KEY = 'scene.greetings'
Line = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=96, pattern=r'^[^\r\n]+$')]


class Greeting(BaseModel):
    model_config = ConfigDict(extra='forbid')
    lines: list[Line] = Field(min_length=1, max_length=2)
    notable_line: int | None = Field(default=None, ge=1, le=2)


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


def run(client, now, db_path, *, exclude=(), real_at=None):
    stamp = (real_at or datetime.now(timezone.utc)).timestamp()
    day = now.date().isoformat()
    sim_stamp = (now - datetime(1970, 1, 1)).total_seconds()
    with connect(db_path) as c:
        settings = dict(c.execute('SELECT key,value FROM world'))
        state = json.loads(settings.get(STATE_KEY, '{}'))
    if state.get('day') != day:
        state = {'day': day, 'pairs': [], 'last': {}, 'recent': []}
    if len(state['pairs']) >= DAILY_LIMIT:
        return False

    groups = places.present(now, db_path)
    with connect(db_path) as c:
        c.execute('BEGIN IMMEDIATE')
        for key, people in groups.items():
            available = [p for p in people if p['id'] not in exclude and not busy(c, p['id'])
                         and sim_stamp - state['last'].get(str(p['id']), -1e12) >= 30*60]
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
                world._set(c, STATE_KEY, json.dumps(state))
                break
            else:
                continue
            break
        else:
            return False

    prompt = (
        f"{a['name']} ({a['activity']}) greets {b['name']} ({b['activity']}) at {places.PLACES[key].name}. "
        "Write one short line from the first person and optionally a reply from the second. "
        "Keep it natural. Don't introduce news, new world events, or promises. "
        'Return JSON {"lines":["Morning.","All right?"],"notable_line":null}. '
        "Use a 1-based notable_line only if that line shares meaningful personal information already given above."
    )
    proposal = client.propose(a['id'], [{'role': 'user', 'content': prompt}],
                              schema=Greeting, max_tokens=MAX_TOKENS)
    try:
        result = Greeting.model_validate(proposal)
    except ValidationError:
        return False
    shown = datetime.now(timezone.utc).timestamp() if real_at is None else stamp
    with connect(db_path) as c:
        state['recent'] = active({STATE_KEY: json.dumps(state)}, datetime.fromtimestamp(shown, timezone.utc))
        for index, (speaker, line) in enumerate(zip((a,b), result.lines)):
            state['recent'].append({'id': speaker['id'], 'place': key, 'text': line,
                                    'start': shown + index * 3})
        world._set(c, STATE_KEY, json.dumps(state))
        if result.notable_line and result.notable_line <= len(result.lines):
            index = result.notable_line - 1
            speaker, listener = ((a,b), (b,a))[index]
            content = f"{speaker['name']} said: {result.lines[index]}"
            c.execute('''INSERT INTO facts(agent_id, subject, content, source, source_agent_id, importance)
                         SELECT ?, 'street conversation', ?, 'told', ?, 3
                         WHERE NOT EXISTS(SELECT 1 FROM facts WHERE agent_id=? AND content=?)''',
                      (listener['id'], content, speaker['id'], listener['id'], content))
    return True
