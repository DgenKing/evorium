"""Real-time world clock (with optional speed multiplier), weekly routines and presence.

Sim time = anchor_sim + (real_now - anchor_real) * speed. At speed 1 it IS the real UK clock.
Pure Python, no model calls.
"""

import random
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from evorium.db import DEFAULT_DB_PATH, connect

TZ = ZoneInfo("Europe/London")
FMT = "%Y-%m-%d %H:%M:%S"
PUB = "The Crooked Billet, Ancoats, Manchester"
STREET = "Shuttle Street, Ancoats"   # the pavement outside the pub and shop: people pass, stop and chat here


def _real_now() -> datetime:
    return datetime.now(TZ).replace(tzinfo=None)


def _get(connection, key, default=None):
    row = connection.execute("SELECT value FROM world WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def _set(connection, key, value):
    connection.execute("INSERT INTO world (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (key, str(value)))


def _anchors(connection):
    speed = float(_get(connection, "speed", "1"))
    anchor_real = _get(connection, "anchor_real")
    anchor_sim = _get(connection, "anchor_sim")
    if anchor_real is None or anchor_sim is None:
        now = _real_now()
        _set(connection, "anchor_real", now.strftime(FMT))
        _set(connection, "anchor_sim", now.strftime(FMT))
        _set(connection, "speed", speed)
        return now, now, speed
    return datetime.strptime(anchor_real, FMT), datetime.strptime(anchor_sim, FMT), speed


def get_setting(key: str, default: str | None = None, db_path: str | Path = DEFAULT_DB_PATH) -> str | None:
    """Small persisted settings (e.g. whether auto mode is on) so they survive a restart."""
    with connect(db_path) as connection:
        return _get(connection, key, default)


def set_setting(key: str, value, db_path: str | Path = DEFAULT_DB_PATH) -> None:
    with connect(db_path) as connection:
        _set(connection, key, value)


def now(db_path: str | Path = DEFAULT_DB_PATH) -> datetime:
    with connect(db_path) as connection:
        anchor_real, anchor_sim, speed = _anchors(connection)
    return anchor_sim + (_real_now() - anchor_real) * speed


def get_speed(db_path: str | Path = DEFAULT_DB_PATH) -> float:
    with connect(db_path) as connection:
        return float(_get(connection, "speed", "1"))


def set_speed(speed: float, db_path: str | Path = DEFAULT_DB_PATH) -> datetime:
    """Re-anchor so sim time is continuous across the change. Speed 1 with no drift snaps back to real time."""
    speed = max(0.0, float(speed))
    current = now(db_path)
    with connect(db_path) as connection:
        _set(connection, "anchor_real", _real_now().strftime(FMT))
        _set(connection, "anchor_sim", current.strftime(FMT))
        _set(connection, "speed", speed)
    return current


def reset_to_real_time(db_path: str | Path = DEFAULT_DB_PATH) -> datetime:
    with connect(db_path) as connection:
        n = _real_now()
        _set(connection, "anchor_real", n.strftime(FMT))
        _set(connection, "anchor_sim", n.strftime(FMT))
        _set(connection, "speed", 1)
    return n


def describe(dt: datetime) -> str:
    return dt.strftime("%A %d %B, %H:%M")


# ---- Pub hours and routines -------------------------------------------------

def pub_open(dt: datetime, stats=None) -> bool:
    """Open every day 09:00 until midnight."""
    return not (stats or {}).get("pub.closed", 0) and 9 <= dt.hour < 24


def _between(dt, start, end) -> bool:
    h = dt.hour + dt.minute / 60
    return start <= h < end


def _routine_location(name: str, dt: datetime, stats=None) -> tuple[str, str]:
    """(location, activity) for a character at a sim datetime. Deterministic."""
    stats = stats or {}
    first = name.split()[0]
    if stats.get('pub.closed') and first in ('Dez', 'Jess'):
        return home_location(name), 'at home after the pub closed'
    if stats.get('shop.open', 1) == 0 and first == 'Raj':
        return home_location(name), 'at home after the shop closed'
    if stats.get('pub.quiz') == 2 and not stats.get('pub.closed') and dt.weekday() == 3 and _between(dt, 19.5, 22.5) and first in ('Tommy', 'Mohammed', 'Brenda', 'Chloe', 'Peggy', 'Hannah', 'Liam'):
        # Work still takes priority; Mo is driving after 19:30 on Thursdays.
        base_loc, base_act = _routine_location(name, dt)
        if base_act not in ('driving', 'at work', 'asleep'):
            return PUB, 'at the Thursday quiz'
    wd = dt.weekday()  # Mon=0
    first = name.split()[0]
    if first == "Dez":
        if pub_open(dt, stats) and _between(dt, 15.5, 15.67):
            return STREET, "out front for a breather"
        if pub_open(dt, stats):
            return PUB, "behind the bar"
        if _between(dt, 7, 9):
            return "Cash and carry, Openshaw", "doing the pub's shopping"
        return "Flat above The Crooked Billet", "off duty upstairs" if _between(dt, 7, 24) else "asleep"
    if first == "Jess":
        if wd in ((3, 4, 5, 6, 2, 1)[:stats["jess.shifts"]] if "jess.shifts" in stats else (0, 1, 3, 4)) and _between(dt, 17, 23):
            return PUB, "working the bar"
        if wd < 5 and _between(dt, 6, 10):
            return "Office block, Great Ancoats Street", "cleaning shift"
        if wd in (2, 5) and _between(dt, 19.5, 22) and pub_open(dt, stats):
            return PUB, "having a drink on her night off"
        return "Flat, Miles Platting", "at home with Alfie" if _between(dt, 7, 23) else "asleep"
    if first == "Tommy":
        if (wd == 3 and _between(dt, 18, 22.5)) or (wd != 3 and _between(dt, 19, 22.5)):
            if pub_open(dt, stats):
                return PUB, "at his usual table"
        if _between(dt, 10, 10.5) or _between(dt, 11.5, 12):
            return STREET, "walking to the shops"
        if _between(dt, 10.5, 11.5) and wd < 6:
            return "Patel's News, Ancoats", "browsing the papers"
        if wd < 5 and _between(dt, 14.5, 16) and pub_open(dt, stats):
            return PUB, "having an afternoon half"
        return "Flat, Blossom Street", "at home" if _between(dt, 7, 23) else "asleep"
    if first == "Raj":
        if wd < 6 and _between(dt, 7, 19):
            return "Patel's News, Ancoats", "behind the counter"
        if wd in (1, 3, 4) and _between(dt, 20, 22) and pub_open(dt, stats):
            return PUB, "having a quiet half"
        if wd == 6 and _between(dt, 13, 15) and pub_open(dt, stats):
            return PUB, "Sunday pint"
        return "Home, Cheetham Hill", "with the family" if _between(dt, 7, 23) else "asleep"
    if first == "Chloe":
        if wd < 5 and _between(dt, 8.25, 8.6):
            return "Patel's News, Ancoats", "grabbing a coffee on the way to work"
        if wd < 5 and _between(dt, 9, 18):
            return "Architecture practice, Northern Quarter", "at work"
        if wd in (1, 2, 3, 4) and _between(dt, 18.25, 21.5) and pub_open(dt, stats):
            return PUB, "unwinding after work"
        if wd == 5 and _between(dt, 15, 20) and pub_open(dt, stats):
            return PUB, "Saturday afternoon drink"
        if wd == 5 and _between(dt, 9.5, 10):
            return "Patel's News, Ancoats", "picking up the property pages"
        if wd == 5 and _between(dt, 10, 15):
            return "Various flats, Ancoats", "flat viewings"
        return "Rented room, Stockport", "at home" if _between(dt, 7, 23) else "asleep"
    if first == 'Simon':
        if wd==3 and _between(dt,14,14.5):return "Patel's News, Ancoats",'visiting the newsagent'
        if wd==1 and _between(dt,12.5,13.5) and pub_open(dt, stats):return PUB,'having lunch and looking over the terrace'
        if wd<5 and _between(dt,9,17.5):return 'Northgate Estates office, Spinningfields','at the office'
        return 'Home, Hale','at home' if _between(dt,7,23) else 'asleep'
    if first == 'Brenda':
        if wd<6 and _between(dt,9,9.5):return "Patel's News, Ancoats",'buying the morning paper'
        if wd in (0,2,4) and _between(dt,10,11):return STREET,'chatting to neighbours on the pavement'
        if ((wd in (1,3) and _between(dt,12.5,14)) or (wd==4 and _between(dt,14,16)) or (wd==2 and _between(dt,19,21)) or (wd in (5,6) and _between(dt,13,15))) and pub_open(dt, stats):return PUB,'catching up with the neighbours'
        return 'Home, Blossom Street','at home' if _between(dt,7,23) else 'asleep'
    if first == 'Mohammed':
        if _between(dt,5,12):return 'Home, Manchester','asleep'
        if wd<6 and _between(dt,13,13.33):return "Patel's News, Ancoats",'buying his lunch'
        if wd==2 and _between(dt,14,15.5) and pub_open(dt, stats):return PUB,'practising his darts'
        if wd<6 and _between(dt,16,16+20/60):return "Patel's News, Ancoats",'picking up supplies before his shift'
        if ((wd in (1,3,4) and _between(dt,18,19.5)) or (wd==6 and _between(dt,14,16))) and pub_open(dt, stats):return PUB,'here for darts and company'
        if _between(dt,19.5,24) or _between(dt,0,4):return 'Manchester','driving'
        return 'Home, Manchester','off duty'
    if first == 'Peggy':
        if wd<6 and _between(dt,9.5,9.75):return "Patel's News, Ancoats",'buying her paper and a quarter of mints'
        if wd<6 and _between(dt,12,14.5) and pub_open(dt, stats):return PUB,'having her half of stout at the bar'
        if wd<6 and _between(dt,14.5,15.5):return STREET,'sitting on the bench outside the Billet'
        if wd==6 and _between(dt,13,15) and pub_open(dt, stats):return PUB,'Sunday half with the regulars'
        return 'Sheltered flat, Ancoats','at home' if _between(dt,7,22) else 'asleep'
    if first == 'Liam':
        if wd<5 and _between(dt,7,7.4):return "Patel's News, Ancoats",'grabbing breakfast before work'
        if wd<5 and _between(dt,12.5,13.25) and pub_open(dt, stats):return PUB,'on his dinner break'
        if wd<5 and (_between(dt,10,10.25) or _between(dt,15,15.25)):return STREET,'on a smoke break'
        if wd<5 and _between(dt,16.5,16.75):return STREET,'heading home from the site'
        if wd<5 and _between(dt,7.5,16.5):return 'Mill conversion site, Ancoats','on the scaffold'
        if wd==4 and _between(dt,17,21) and pub_open(dt, stats):return PUB,'Friday pint after work'
        return 'Flat, Clayton','at home' if _between(dt,6.5,23.5) else 'asleep'
    if first == 'Anjali':
        if wd in (0,2,4) and _between(dt,14.75,15):return STREET,'walking up from the tram stop'
        if ((wd in (0,2,4) and _between(dt,15,19)) or (wd==5 and _between(dt,9,17))):return "Patel's News, Ancoats",'helping on the counter'
        if wd<5 and _between(dt,10,14):return 'Manchester Met, All Saints','at lectures'
        return 'Home, Cheetham Hill','studying at home' if _between(dt,7,23.5) else 'asleep'
    if first == 'Pete':
        if wd in (1,4) and (_between(dt,9.75,10) or _between(dt,10.75,11)):return STREET,'unloading the dray'
        if wd in (1,4) and _between(dt,10,10.75):return PUB,'delivering the barrels'
        if wd<5 and _between(dt,6,15):return 'Brewery round, Greater Manchester','on his delivery round'
        if wd==5 and _between(dt,13,16) and pub_open(dt, stats):return PUB,'Saturday afternoon pint'
        return 'Home, Failsworth','at home' if _between(dt,6,22.5) else 'asleep'
    if first == 'Hannah':
        if wd<5 and _between(dt,8.5,8.75):return "Patel's News, Ancoats",'picking up the papers and a coffee'
        if wd in (2,4) and _between(dt,17.5,19.5) and pub_open(dt, stats):return PUB,'having a drink and listening'
        if wd in (1,3) and _between(dt,12.5,13.5):return STREET,'asking passers-by about the terrace'
        if wd<5 and _between(dt,9,17.5):return 'Newsroom, Northern Quarter','working on her story'
        return 'Flat, Northern Quarter','at home' if _between(dt,7,24) else 'asleep'
    return "Ancoats", "about"



def _routine(name,dt,stats=None):
    location,activity=_routine_location(name,dt,stats)
    free=activity not in ('asleep','behind the bar',"doing the pub's shopping",'working the bar','cleaning shift','behind the counter','at work','at the office','driving','on the scaffold','helping on the counter','at lectures','delivering the barrels','on his delivery round','working on her story')
    return location,activity,free


def routine(name,dt,stats=None):
    return _routine(name,dt,stats)[:2]


def is_free(name,dt,stats=None):
    return _routine(name,dt,stats)[2]


def home_location(name):
    return {'Dez':'Flat above The Crooked Billet','Jess':'Flat, Miles Platting','Tommy':'Flat, Blossom Street',
            'Raj':'Home, Cheetham Hill','Chloe':'Rented room, Stockport','Simon':'Home, Hale','Brenda':'Home, Blossom Street','Mohammed':'Home, Manchester','Peggy':'Sheltered flat, Ancoats','Liam':'Flat, Clayton',
            'Anjali':'Home, Cheetham Hill','Pete':'Home, Failsworth','Hannah':'Flat, Northern Quarter'}.get(name.split()[0],'Home, Ancoats')


def whereabouts(agent,now,db_path=DEFAULT_DB_PATH):
    with connect(db_path) as c:
        from evorium.economy import stats
        values = stats(c)
        if (values.get("pub.closed") and agent["name"].split()[0] in ("Dez", "Jess")) or (values.get("shop.open", 1) == 0 and agent["name"].split()[0] == "Raj"):
            return routine(agent["name"], now, values)
        plan=c.execute("""SELECT * FROM plans WHERE agent_id=? AND status='active' AND action IN ('visit','stay_home')
            AND start_at<=? AND end_at>? ORDER BY id DESC LIMIT 1""",(agent['id'],now.strftime('%Y-%m-%d %H:%M'),now.strftime('%Y-%m-%d %H:%M'))).fetchone()
    if plan:
        if plan['action']=='stay_home':return home_location(agent['name']),'staying home'
        from evorium.places import REGISTRY
        from evorium.places import is_open
        if not is_open(plan['place'], now, values):
            return routine(agent['name'], now, values)
        return REGISTRY[plan['place']], 'popping into the shop' if plan['place']=='shop' else 'in for a drink'
    loc, act = routine(agent['name'],now,values)
    if loc == PUB and not pub_open(now, values):
        return home_location(agent['name']), 'at home while the pub is shut'
    return loc, act

def present_in_pub(agents: list[dict], dt: datetime) -> list[dict]:
    return [a for a in agents if a.get("kind", "npc") == "npc" and routine(a["name"], dt)[0] == PUB]


def pick_pair(ids: list[int], db_path: str | Path = DEFAULT_DB_PATH, recent_window: int = 3) -> tuple[int, int]:
    """Prefer pairs that haven't met recently. Never repeat a pair from the last `recent_window` conversations if avoidable."""
    with connect(db_path) as connection:
        rows = connection.execute(
            "SELECT id, agent_a_id, agent_b_id FROM conversations WHERE agent_a_id IS NOT NULL ORDER BY id DESC LIMIT 50"
        ).fetchall()
        allowed = {r[0] for r in connection.execute("SELECT id FROM agents WHERE kind='npc'")}
        busy = {r[0] for r in connection.execute("""SELECT v.agent_b_id FROM conversations v JOIN agents a ON a.id=v.agent_a_id
            WHERE a.kind='player' AND v.status='running' AND EXISTS (SELECT 1 FROM messages m
            WHERE m.conversation_id=v.id AND julianday(m.created_at)>=julianday('now','-3 minutes'))""")}
        allowed -= busy
    ids = [i for i in ids if i in allowed]
    if len(ids) < 2:
        raise ValueError("Fewer than two available characters.")
    last_seen: dict[frozenset, int] = {}
    person_seen: dict[int, int] = {}
    recent: set[frozenset] = set()
    for rank, r in enumerate(rows):
        key = frozenset((r["agent_a_id"], r["agent_b_id"]))
        last_seen.setdefault(key, rank)
        person_seen.setdefault(r["agent_a_id"], rank)
        person_seen.setdefault(r["agent_b_id"], rank)
        if rank < recent_window:
            recent.add(key)
    pairs = [(a, b) for i, a in enumerate(ids) for b in ids[i + 1:]]
    candidates = [p for p in pairs if frozenset(p) not in recent] or pairs
    # Favour pairs who haven't met lately AND people who haven't spoken lately, so quiet characters get a turn
    # rather than whoever is always behind the bar.
    weights = [(1 + last_seen.get(frozenset(p), 50)) * (1 + (person_seen.get(p[0], 50) + person_seen.get(p[1], 50)) / 2)
               for p in candidates]
    a, b = random.choices(candidates, weights=weights, k=1)[0]
    return (a, b) if random.random() < 0.5 else (b, a)
