"""Public rendering snapshot. This endpoint opens SQLite read-only and never calls a model."""
import json
import sqlite3
from contextlib import closing
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from evorium import accounts, greetings, places, world
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
            if activity in ('behind the bar', 'working the bar', 'covering Jess behind the bar'):
                waypoint = 'PUB_BAR' if first == 'Jess' else 'PUB_HOST'
            elif activity == 'at his usual table':
                waypoint = 'PUB_WINDOW'
            elif 'darts' in activity:
                waypoint = 'PUB_DART'
            else:
                waypoint = places.PLACES[place].spots[pools[place] % len(places.PLACES[place].spots)]
                pools['pub'] += 1
        elif place == 'shop':
            if activity == 'behind the counter':
                waypoint = 'NEWS_TILL'
            else:
                waypoint = places.PLACES[place].spots[pools[place] % len(places.PLACES[place].spots)]
                pools['shop'] += 1
        elif place in places.PLACES:
            spots = places.PLACES[place].spots
            waypoint = spots[pools[place] % len(spots)]
            pools[place] += 1
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
        from evorium import weather
        weather_now = weather.from_settings(settings, now, real_at)
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
        from evorium.place_registry import home_door
        characters = []
        for agent in c.execute("SELECT id,name,kind,location,activity,mood FROM agents WHERE kind='npc' ORDER BY id"):
            # The persisted presence is exactly what the dashboard shows; the heartbeat owns it.
            location, activity = agent['location'], agent['activity'] or ''
            place = places.BY_LOCATION.get(location, 'away')
            if place == 'away' and location in (world.STREET, 'Ancoats'):
                place = 'street'
            if location == 'Ancoats' and activity == 'walking to the shops':
                place = 'street'
            first = first_name(agent['name'])
            portrait = first.lower() + '.png'
            door = home_door(first) if location == world.home_location(agent['name']) else 'STREET_LEFT'
            journey = json.loads(settings.get(f"scene.travel.{agent['id']}", 'null'))
            travel = None
            if journey and journey['to'] == location:
                age = real_at.timestamp() - journey['started']
                if 0 <= age < 360:
                    origin = journey['from']
                    origin_place = places.BY_LOCATION.get(origin)
                    origin_spot = (places.PLACES[origin_place].spots[0] if origin_place else
                                   home_door(first) if origin == world.home_location(agent['name']) else 'STREET_LEFT')
                    travel = {'from': origin_spot, 'age': age, 'id': journey['started']}
            characters.append({'id': agent['id'], 'name': agent['name'], 'first': first, 'kind': 'npc',
                               'place': place, 'door': door, 'travel': travel, 'activity': activity, 'mood': agent['mood'],
                               'talking_to': talk.get(agent['id']),
                               'conversation_id': None, 'line': None, 'line_at': None,
                               **lines.get(agent['id'], {}),
                               'portrait': '/static/portraits/' + portrait if (PORTRAITS / portrait).is_file() else None})
        me = c.execute("SELECT id,name FROM agents WHERE kind='player' AND account=?", (accounts.current.get(),)).fetchone()
        player = {'id': me['id'], 'name': me['name'], 'place': settings.get(accounts.setting_key('player_place')) or 'street', 'talking_to': talk.get(me['id'])} if me else None
        for other in accounts.other_players(c, settings):
            characters.append({'id': other['id'], 'name': other['name'], 'first': other['name'], 'kind': 'player',
                               'place': other['place'], 'activity': 'visiting', 'mood': other['mood'],
                               'talking_to': talk.get(other['id']), 'conversation_id': None,
                               'line': None, 'line_at': None, **lines.get(other['id'], {}), 'portrait': None})
        notices = [dict(row) for row in c.execute('SELECT place,text FROM notices WHERE julianday(since)<=julianday(?) AND (until IS NULL OR julianday(until)>julianday(?)) ORDER BY id', (stamp, stamp))]
    hour = now.hour + now.minute / 60
    daylight = 0.0 if hour < 7 or hour >= 19 else 1.0 if hour < 17 else (19 - hour) / 2
    from evorium import calendar_uk
    return {'calendar':calendar_uk.state(now),'weather':weather_now,'sim_at': stamp, 'sim_time': world.describe(now), 'speed': speed, 'daylight': daylight,
            'pub_open': places.is_open('pub', now, values), 'shop_open': places.is_open('shop', now, values),
            'greetings': greetings.active(settings, real_at), 'notices': notices, 'places': public_places(now, {**values, '_weather': weather_now}), 'characters': assign_spots(characters), 'player': player}


def public_places(now, values):
    return [
        {'key': key, 'name': place.name, 'location': place.location, 'kind': place.kind,
         'indoor': place.indoor, 'landmark': place.landmark, 'spots': place.spots,
         'open': places.is_open(key, now, values)}
        for key, place in places.PLACES.items()
    ]
