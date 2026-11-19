"""Public rendering snapshot. This endpoint opens SQLite read-only and never calls a model."""
import sqlite3
from contextlib import closing
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from evorium import places, world
from evorium.db import DEFAULT_DB_PATH

PORTRAITS = Path(__file__).parent / 'static' / 'portraits'


def first_name(name):
    return 'Mo' if name.startswith('Mohammed ') else name.split()[0]


def assign_spots(characters):
    """Stable ID order, independent customer pools, and explicit shared-spot slots."""
    pools = Counter()
    slots = Counter()
    result = []
    for person in sorted(characters, key=lambda item: item['id']):
        item = dict(person)
        place, activity, first = item['place'], item['activity'], item['first']
        waypoint = None
        if place == 'pub':
            if activity in ('behind the bar', 'working the bar'):
                waypoint = 'PUB_BAR' if first == 'Jess' else 'PUB_HOST'
            elif activity == 'at his usual table':
                waypoint = 'PUB_WINDOW'
            elif 'darts' in activity:
                waypoint = 'PUB_DART'
            else:
                waypoint = ('PUB_BOOTH', 'PUB_BAR', 'PUB_WINDOW')[pools['pub'] % 3]
                pools['pub'] += 1
        elif place == 'shop':
            if activity == 'behind the counter':
                waypoint = 'NEWS_TILL'
            else:
                waypoint = ('NEWS_QUEUE', 'NEWS_RACK', 'NEWS_CHILLER')[pools['shop'] % 3]
                pools['shop'] += 1
        elif place == 'street':
            waypoint = ('STREET_WAIT', 'STREET_LINK')[pools['street'] % 2]
            pools['street'] += 1
        item.update(waypoint=waypoint, slot=slots[waypoint] if waypoint else 0, visible=waypoint is not None)
        if waypoint:
            slots[waypoint] += 1
        result.append(item)
    return result


def snapshot(db_path=DEFAULT_DB_PATH, *, real_at=None):
    real_at = real_at or datetime.now(timezone.utc)
    # URI mode=ro also makes future accidental writes fail instead of altering a world.
    with closing(sqlite3.connect(Path(db_path).resolve().as_uri() + '?mode=ro', uri=True)) as c:
        c.row_factory = sqlite3.Row
        c.execute('BEGIN')  # one consistent read snapshot while the heartbeat runs
        settings = dict(c.execute('SELECT key,value FROM world').fetchall())
        speed = float(settings.get('speed', 1))
        if settings.get('anchor_real') and settings.get('anchor_sim'):
            elapsed = (real_at.astimezone(world.TZ).replace(tzinfo=None) - datetime.strptime(settings['anchor_real'], world.FMT)).total_seconds()
            now = datetime.strptime(settings['anchor_sim'], world.FMT) + timedelta(seconds=elapsed * speed)
        else:
            now = real_at.astimezone(world.TZ).replace(tzinfo=None)
        stamp = now.strftime('%Y-%m-%d %H:%M')
        values = dict(c.execute('SELECT key,value FROM stats').fetchall())
        cutoff = (real_at - timedelta(minutes=2)).isoformat()
        conversations = c.execute('''SELECT * FROM conversations WHERE status='running'
            OR (status='completed' AND julianday(ended_at)>=julianday(?)) ORDER BY id''', (cutoff,)).fetchall()
        talk, lines = {}, {}
        for conv in conversations:
            a, b = conv['agent_a_id'], conv['agent_b_id']
            if conv['status'] == 'running':
                talk[a] = b
                talk[b] = a
            for message in c.execute('SELECT speaker_id,text,created_at FROM messages WHERE conversation_id=? ORDER BY id', (conv['id'],)):
                lines[message['speaker_id']] = {'conversation_id': conv['id'], 'line': message['text'], 'line_at': message['created_at']}
        characters = []
        for agent in c.execute("SELECT id,name,kind,location,activity,mood FROM agents WHERE kind='npc' ORDER BY id"):
            # The persisted presence is exactly what the dashboard shows; the heartbeat owns it.
            location, activity = agent['location'], agent['activity'] or ''
            place = next((key for key, name in places.REGISTRY.items() if name == location), 'away')
            if location == 'Ancoats' and activity == 'walking to the shops':
                place = 'street'
            first = first_name(agent['name'])
            portrait = first.lower() + '.png'
            characters.append({'id': agent['id'], 'name': agent['name'], 'first': first, 'kind': 'npc',
                               'place': place, 'activity': activity, 'mood': agent['mood'],
                               'talking_to': talk.get(agent['id']),
                               'conversation_id': None, 'line': None, 'line_at': None,
                               **lines.get(agent['id'], {}),
                               'portrait': '/static/portraits/' + portrait if (PORTRAITS / portrait).is_file() else None})
        me = c.execute("SELECT id,name FROM agents WHERE kind='player'").fetchone()
        player = {'id': me['id'], 'name': me['name'], 'place': settings.get('player_place') or 'street', 'talking_to': talk.get(me['id'])} if me else None
        notices = [dict(row) for row in c.execute('SELECT place,text FROM notices WHERE julianday(since)<=julianday(?) AND (until IS NULL OR julianday(until)>julianday(?)) ORDER BY id', (stamp, stamp))]
    hour = now.hour + now.minute / 60
    daylight = 0.0 if hour < 7 or hour >= 19 else 1.0 if hour < 17 else (19 - hour) / 2
    return {'sim_at': stamp, 'sim_time': world.describe(now), 'speed': speed, 'daylight': daylight,
            'pub_open': places.is_open('pub', now, values), 'shop_open': places.is_open('shop', now, values),
            'notices': notices, 'characters': assign_spots(characters), 'player': player}
