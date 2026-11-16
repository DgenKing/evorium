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

def pub_open(dt: datetime) -> bool:
    h = dt.hour + dt.minute / 60
    if dt.weekday() in (4, 5):        # Fri, Sat
        return 12 <= h < 24
    if dt.weekday() == 6:             # Sun
        return 12 <= h < 22.5
    return 16 <= h < 23               # Mon–Thu


def _between(dt, start, end) -> bool:
    h = dt.hour + dt.minute / 60
    return start <= h < end


def _routine_location(name: str, dt: datetime) -> tuple[str, str]:
    """(location, activity) for a character at a sim datetime. Deterministic."""
    wd = dt.weekday()  # Mon=0
    first = name.split()[0]
    if first == "Dez":
        if pub_open(dt):
            return PUB, "behind the bar"
        if _between(dt, 9, 12):
            return "Cash and carry, Openshaw", "doing the pub's shopping"
        return "Flat above The Crooked Billet", "off duty upstairs" if _between(dt, 7, 24) else "asleep"
    if first == "Jess":
        if wd in (0, 1, 3, 4) and _between(dt, 17, 23):
            return PUB, "working the bar"
        if wd < 5 and _between(dt, 6, 10):
            return "Office block, Great Ancoats Street", "cleaning shift"
        if wd in (2, 5) and _between(dt, 19.5, 22) and pub_open(dt):
            return PUB, "having a drink on her night off"
        return "Flat, Miles Platting", "at home with Alfie" if _between(dt, 7, 23) else "asleep"
    if first == "Tommy":
        if (wd == 3 and _between(dt, 18, 22.5)) or (wd != 3 and _between(dt, 19, 22.5)):
            if pub_open(dt):
                return PUB, "at his usual table"
        if _between(dt, 10, 12):
            return "Ancoats", "walking to the shops"
        return "Flat, Blossom Street", "at home" if _between(dt, 7, 23) else "asleep"
    if first == "Raj":
        if wd < 6 and _between(dt, 7, 19):
            return "Patel's News, Ancoats", "behind the counter"
        if wd in (1, 3, 4) and _between(dt, 20, 22) and pub_open(dt):
            return PUB, "having a quiet half"
        if wd == 6 and _between(dt, 13, 15) and pub_open(dt):
            return PUB, "Sunday pint"
        return "Home, Cheetham Hill", "with the family" if _between(dt, 7, 23) else "asleep"
    if first == "Chloe":
        if wd < 5 and _between(dt, 9, 18):
            return "Architecture practice, Northern Quarter", "at work"
        if wd in (1, 2, 4) and _between(dt, 18.5, 22) and pub_open(dt):
            return PUB, "unwinding after work"
        if wd == 5 and _between(dt, 15, 20) and pub_open(dt):
            return PUB, "Saturday afternoon drink"
        if wd == 5 and _between(dt, 10, 15):
            return "Various flats, Ancoats", "flat viewings"
        return "Rented room, Stockport", "at home" if _between(dt, 7, 23) else "asleep"
    return "Ancoats", "about"



def _routine(name,dt):
    location,activity=_routine_location(name,dt)
    free=activity not in ('asleep','behind the bar',"doing the pub's shopping",'working the bar','cleaning shift','behind the counter','at work','at the office','driving')
    return location,activity,free


def routine(name,dt):
    return _routine(name,dt)[:2]


def is_free(name,dt):
    return _routine(name,dt)[2]


def home_location(name):
    return {'Dez':'Flat above The Crooked Billet','Jess':'Flat, Miles Platting','Tommy':'Flat, Blossom Street',
            'Raj':'Home, Cheetham Hill','Chloe':'Rented room, Stockport','Simon':'Home, Hale','Brenda':'Home, Blossom Street','Mohammed':'Home, Manchester'}.get(name.split()[0],'Home, Ancoats')


def whereabouts(agent,now,db_path=DEFAULT_DB_PATH):
    with connect(db_path) as c:
        plan=c.execute("""SELECT * FROM plans WHERE agent_id=? AND status='active' AND action IN ('visit','stay_home')
            AND start_at<=? AND end_at>? ORDER BY id DESC LIMIT 1""",(agent['id'],now.strftime('%Y-%m-%d %H:%M'),now.strftime('%Y-%m-%d %H:%M'))).fetchone()
    if plan:
        if plan['action']=='stay_home':return home_location(agent['name']),'staying home'
        from evorium.places import REGISTRY
        return REGISTRY[plan['place']], 'popping into the shop' if plan['place']=='shop' else 'in for a drink'
    return routine(agent['name'],now)

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
    recent: set[frozenset] = set()
    for rank, r in enumerate(rows):
        key = frozenset((r["agent_a_id"], r["agent_b_id"]))
        last_seen.setdefault(key, rank)
        if rank < recent_window:
            recent.add(key)
    pairs = [(a, b) for i, a in enumerate(ids) for b in ids[i + 1:]]
    candidates = [p for p in pairs if frozenset(p) not in recent] or pairs
    weights = [1 + last_seen.get(frozenset(p), 50) for p in candidates]
    a, b = random.choices(candidates, weights=weights, k=1)[0]
    return (a, b) if random.random() < 0.5 else (b, a)
