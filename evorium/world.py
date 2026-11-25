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
from evorium.place_registry import REGISTRY

PUB, SHOP, STREET = (REGISTRY[key] for key in ('pub', 'shop', 'street'))


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
    from evorium.calendar_uk import hours
    opening,closing=hours("pub",dt)
    return not (stats or {}).get("pub.closed", 0) and opening <= dt.hour+dt.minute/60 < closing


def _between(dt, start, end) -> bool:
    h = dt.hour + dt.minute / 60
    return start <= h < end


def _base_routine_location(name: str, dt: datetime, stats=None) -> tuple[str, str]:
    """(location, activity) for a character at a sim datetime. Deterministic."""
    stats = stats or {}
    first = name.split()[0]
    if stats.get('pub.closed') and first in ('Dez', 'Jess'):
        return home_location(name), 'at home after the pub closed'
    if stats.get('shop.open', 1) == 0 and first == 'Raj':
        return home_location(name), 'at home after the shop closed'
    if stats.get('pub.quiz') == 2 and not stats.get('pub.closed') and dt.weekday() == 3 and _between(dt, 19.5, 22.5) and first in ('Tommy', 'Mohammed', 'Brenda', 'Chloe', 'Peggy', 'Hannah', 'Liam', 'Ronnie', 'Gary'):
        # Work still takes priority; Mo is driving after 19:30 on Thursdays.
        base_loc, base_act = _base_routine_location(name, dt)
        if base_act not in ('driving', 'at work', 'asleep'):
            return PUB, 'at the Thursday quiz'
    wd = dt.weekday()  # Mon=0
    first = name.split()[0]
    if first == "Dez":
        if pub_open(dt, stats) and _between(dt, 14, 14.5):
            return PUB, "having a quiet tea break at the bar"
        if pub_open(dt, stats) and _between(dt, 15.5, 15.67):
            return STREET, "out front for a breather"
        if pub_open(dt, stats):
            return PUB, "behind the bar"
        if _between(dt, 7, 9):
            return "Cash and carry, Openshaw", "doing the pub's shopping"
        return "Flat above The Crooked Billet", "off duty upstairs" if _between(dt, 7, 24) else "asleep"
    if first == "Jess":
        if wd == 1 and _between(dt,13,14) and pub_open(dt,stats):return PUB,"having lunch on her day off"
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
            return SHOP, "browsing the papers"
        if wd < 5 and _between(dt, 14.5, 16) and pub_open(dt, stats):
            return PUB, "having an afternoon half"
        return "Flat, Blossom Street", "at home" if _between(dt, 7, 23) else "asleep"
    if first == "Raj":
        if wd < 6 and _between(dt, 7, 19):
            return SHOP, "behind the counter"
        if wd in (1, 3, 4) and _between(dt, 20, 22) and pub_open(dt, stats):
            return PUB, "having a quiet half"
        if wd == 6 and _between(dt, 13, 15) and pub_open(dt, stats):
            return PUB, "Sunday pint"
        return "Home, Cheetham Hill", "with the family" if _between(dt, 7, 23) else "asleep"
    if first == "Chloe":
        if wd < 5 and _between(dt, 8.25, 8.6):
            return SHOP, "grabbing a coffee on the way to work"
        if wd < 5 and _between(dt, 9, 18):
            return "Architecture practice, Northern Quarter", "at work"
        if wd in (1, 2, 3, 4) and _between(dt, 18.25, 21.5) and pub_open(dt, stats):
            return PUB, "unwinding after work"
        if wd == 5 and _between(dt, 15, 20) and pub_open(dt, stats):
            return PUB, "Saturday afternoon drink"
        if wd == 5 and _between(dt, 9.5, 10):
            return SHOP, "picking up the property pages"
        if wd == 5 and _between(dt, 10, 15):
            return "Various flats, Ancoats", "flat viewings"
        return "Rented room, Stockport", "at home" if _between(dt, 7, 23) else "asleep"
    if first == 'Simon':
        if wd==3 and _between(dt,14,14.5):return SHOP,'visiting the newsagent'
        if wd in (0,1,2,4) and _between(dt,12.5,13.5) and pub_open(dt, stats):return PUB,'having lunch and looking over the terrace'
        if wd<5 and _between(dt,9,17.5):return 'Northgate Estates office, Spinningfields','at the office'
        return 'Home, Hale','at home' if _between(dt,7,23) else 'asleep'
    if first == 'Brenda':
        if wd<6 and _between(dt,9,9.5):return SHOP,'buying the morning paper'
        if wd in (0,2,4) and _between(dt,10,11):return STREET,'chatting to neighbours on the pavement'
        if ((wd in (1,3) and _between(dt,12.5,14)) or (wd==4 and _between(dt,14,16)) or (wd==2 and _between(dt,19,21)) or (wd in (5,6) and _between(dt,13,15))) and pub_open(dt, stats):return PUB,'catching up with the neighbours'
        return 'Home, Blossom Street','at home' if _between(dt,7,23) else 'asleep'
    if first == 'Mohammed':
        if _between(dt,5,12):return 'Home, Manchester','asleep'
        if wd<6 and _between(dt,13,13.33):return SHOP,'buying his lunch'
        if wd==2 and _between(dt,14,15.5) and pub_open(dt, stats):return PUB,'practising his darts'
        if wd<6 and _between(dt,16,16+20/60):return SHOP,'picking up supplies before his shift'
        if ((wd in (1,3,4) and _between(dt,18,19.5)) or (wd==6 and _between(dt,14,16))) and pub_open(dt, stats):return PUB,'here for darts and company'
        if _between(dt,19.5,24) or _between(dt,0,4):return 'Manchester','driving'
        return 'Home, Manchester','off duty'
    if first == 'Peggy':
        if wd<6 and _between(dt,9.5,9.75):return SHOP,'buying her paper and a quarter of mints'
        if wd<6 and _between(dt,12,14.5) and pub_open(dt, stats):return PUB,'having her half of stout at the bar'
        if wd<6 and _between(dt,14.5,15.5):return STREET,'sitting on the bench outside the Billet'
        if wd==6 and _between(dt,13,15) and pub_open(dt, stats):return PUB,'Sunday half with the regulars'
        return 'Sheltered flat, Ancoats','at home' if _between(dt,7,22) else 'asleep'
    if first == 'Liam':
        if wd<5 and _between(dt,7,7.4):return SHOP,'grabbing breakfast before work'
        if wd<5 and _between(dt,12.5,13.25) and pub_open(dt, stats):return PUB,'on his dinner break'
        if wd<5 and (_between(dt,10,10.25) or _between(dt,15,15.25)):return STREET,'on a smoke break'
        if wd<5 and _between(dt,16.5,16.75):return STREET,'heading home from the site'
        if wd<5 and _between(dt,7.5,16.5):return 'Mill conversion site, Ancoats','on the scaffold'
        if wd==4 and _between(dt,17,21) and pub_open(dt, stats):return PUB,'Friday pint after work'
        return 'Flat, Clayton','at home' if _between(dt,6.5,23.5) else 'asleep'
    if first == 'Anjali':
        if wd in (1,3) and _between(dt,18,19.5) and pub_open(dt,stats):return PUB,'meeting friends after lectures'
        if wd in (0,2,4) and _between(dt,14.75,15):return STREET,'walking up from the tram stop'
        if ((wd in (0,2,4) and _between(dt,15,19)) or (wd==5 and _between(dt,9,17))):return SHOP,'helping on the counter'
        if wd<5 and _between(dt,10,14):return 'Manchester Met, All Saints','at lectures'
        return 'Home, Cheetham Hill','studying at home' if _between(dt,7,23.5) else 'asleep'
    if first == 'Pete':
        if wd in (1,4) and (_between(dt,9.75,10) or _between(dt,10.75,11)):return STREET,'unloading the dray'
        if wd in (1,4) and _between(dt,10,10.75):return PUB,'delivering the barrels'
        if wd<5 and _between(dt,6,15):return 'Brewery round, Greater Manchester','on his delivery round'
        if wd==5 and _between(dt,13,16) and pub_open(dt, stats):return PUB,'Saturday afternoon pint'
        return 'Home, Failsworth','at home' if _between(dt,6,22.5) else 'asleep'
    if first == 'Hannah':
        if wd<5 and _between(dt,8.5,8.75):return SHOP,'picking up the papers and a coffee'
        if wd in (2,4) and _between(dt,17.5,19.5) and pub_open(dt, stats):return PUB,'having a drink and listening'
        if wd in (1,3) and _between(dt,12.5,13.5):return STREET,'asking passers-by about the terrace'
        if wd<5 and _between(dt,9,17.5):return 'Newsroom, Northern Quarter','working on her story'
        return 'Flat, Northern Quarter','at home' if _between(dt,7,24) else 'asleep'
    if first == 'Gary':
        if wd<6 and _between(dt,8.5,8.67):return SHOP,'dropping off the post'
        if wd<6 and _between(dt,8.67,9):return STREET,'doing his round along the terrace'
        if wd<6 and _between(dt,7,12.5):return 'Post round, Ancoats','on his post round'
        if wd in (0,2) and _between(dt,14,17) and pub_open(dt, stats):return PUB,'having an afternoon pint'
        return 'Home, Newton Heath','at home' if _between(dt,6,22.5) else 'asleep'
    if first == 'Kirsty':
        if _between(dt,10.5,11) or _between(dt,14,14.5):return STREET,'pushing the pram round the block'
        if wd<6 and _between(dt,11,11.33):return SHOP,'buying nappies and milk'
        if wd==2 and _between(dt,12,13.5) and pub_open(dt, stats):return PUB,'having lunch with Mia in the pram'
        return 'Flat, Miles Platting','at home with Mia' if _between(dt,6.5,23) else 'asleep'
    if first == 'Grace':
        if wd in (0,2,4) and _between(dt,10,11):return STREET,'talking to neighbours on the beat'
        if wd<5 and _between(dt,10,10.5):return STREET,'taking a tea break on the beat'
        if wd<5 and _between(dt,16,16.33):return STREET,'pausing for a word on her beat'
        if wd<5 and (_between(dt,10,10.33) or _between(dt,13.5,13.83) or _between(dt,16,16.33)):return STREET,'on patrol'
        if wd<5 and _between(dt,13.83,14):return SHOP,'checking in with the shop'
        if wd in (4,5) and _between(dt,22.75,23.25) and pub_open(dt, stats):return PUB,'looking in at closing time'
        if wd<5 and _between(dt,8,17):return 'Ancoats beat','on patrol'
        if wd in (4,5) and _between(dt,17,24):return 'Ancoats beat','on patrol'
        return 'Home, Gorton','at home' if _between(dt,7,23.5) else 'asleep'
    if first == 'Barry':
        if wd in (0,3) and _between(dt,10.5,11):return STREET,'having a flask of tea between windows'
        if wd==4 and _between(dt,17,19) and pub_open(dt,stats):return PUB,'Friday pint after his round'
        if wd in (0,3) and _between(dt,9,12):return STREET,'cleaning the windows along the terrace'
        if wd in (0,3) and _between(dt,12,13) and pub_open(dt, stats):return PUB,'having his dinner'
        if wd<5 and _between(dt,8,16):return 'Window round, East Manchester','cleaning windows'
        return 'Home, Beswick','at home' if _between(dt,6.5,22) else 'asleep'
    if first == 'Ronnie':
        if wd<6 and _between(dt,9.75,10.1):return SHOP,'getting his paper and the racing post'
        if wd in (0,2,4) and _between(dt,13,16) and pub_open(dt, stats):return PUB,'studying the form with a pint'
        if wd in (0,2,4) and _between(dt,16,16.17):return STREET,'heading home from the Billet'
        if wd==6 and _between(dt,13,15) and pub_open(dt, stats):return PUB,'Sunday pint with the lads'
        return 'Flat, Ancoats','at home' if _between(dt,7,22.5) else 'asleep'
    return "Ancoats", "about"



# These visits fill spare time and leave all existing work and social windows in place.
CITY_OUTINGS = (
    ('Chloe', (0, 2, 4), 8.6, 9, 'cafe', 'having a coffee before work'),
    ('Jess', (0, 2, 4), 10, 10.5, 'cafe', 'having a coffee after cleaning'),
    ('Brenda', (1, 3), 10, 10.5, 'cafe', 'having a pot of tea'),
    ('Peggy', (1, 3), 10, 10.5, 'cafe', 'having a pot of tea'),
    ('Gary', (1, 3), 12.5, 13.5, 'square', 'eating lunch after his round'),
    ('Kirsty', (1, 3), 12.5, 13.5, 'square', 'eating lunch with Mia'),
    ('Tommy', (6,), 12, 13, 'towpath', 'taking his Sunday canal walk'),
    ('Ronnie', (6,), 12, 13, 'towpath', 'taking a walk beside the canal'),
    ('Barry', (1, 3), 18, 18.5, 'offlicence', 'picking up a tin for later'),
    ('Liam', (1, 3), 18, 18.5, 'offlicence', 'picking up a tin on the way home'),
)


def _routine_location(name,dt,stats=None):
    stats=stats or {}
    from evorium import calendar_uk,bad_days
    record=stats.get('_bad_days',{}).get(name,{})
    if record.get('kind')=='off_sick':return home_location(name),'off sick at home'
    if bad_days.blocks(record,dt):return home_location(name),'running late getting ready'
    location,activity=_base_routine_location(name,dt,stats)
    jess=stats.get('_bad_days',{}).get('Jess Hartley',{})
    if name.startswith('Dez ') and jess.get('kind')=='off_sick' and pub_open(dt,stats) and _base_routine_location('Jess Hartley',dt,stats)[1]=='working the bar':
        location,activity=PUB,'covering Jess behind the bar'
    # Extend only an actual evening pub visit, by at most an hour, when free and awake.
    if calendar_uk.payday_evening(dt) and 19<=dt.hour<23 and location==home_location(name) and activity!='asleep' and pub_open(dt,stats):
        for minutes in range(5,61,5):
            previous,doing=_base_routine_location(name,dt-timedelta(minutes=minutes),stats)
            if previous==PUB and doing not in ('behind the bar','working the bar'):
                location,activity=PUB,'staying a little longer for payday company'
                break
    from evorium import places
    if location == home_location(name) and activity != 'asleep':
        for who, days, start, end, key, doing in CITY_OUTINGS:
            if name.split()[0] == who and dt.weekday() in days and _between(dt, start, end):
                if places.is_open(key, dt, stats):
                    location, activity = REGISTRY[key], doing
                break
    for key,place in places.REGISTRY.items():
        if location==place and not places.is_open(key,dt,stats):
            return home_location(name),'at home while the '+key+' is shut'
    w=stats.get('_weather',{})
    first=name.split()[0]
    if w.get('raining'):
        if first=='Peggy' and location==STREET:
            return (PUB,'staying inside out of the rain') if pub_open(dt,stats) else (home_location(name),'staying home out of the rain')
        if first in ('Brenda','Barry') and location==STREET and activity in ('chatting to neighbours on the pavement','having a flask of tea between windows'):
            return (PUB,'having tea out of the rain') if pub_open(dt,stats) else (home_location(name),'staying home out of the rain')
        if first=='Grace' and location==STREET and activity in ('taking a tea break on the beat','pausing for a word on her beat','talking to neighbours on the beat'):
            return (places.REGISTRY['shop'],'pausing inside out of the rain') if places.is_open('shop',dt,stats) else (location,'sheltering in a doorway on her beat')
        if first=='Hannah' and location==STREET and activity=='asking passers-by about the terrace' and pub_open(dt,stats):return PUB,'asking neighbours about the terrace indoors'
        if first=='Kirsty' and location==STREET:return home_location(name),'skipping the pram walk in the rain'
        if first=='Liam' and activity=='on a smoke break':
            if dt.minute<5:return STREET,'having a quick smoke in a doorway'
            return 'Mill conversion site, Ancoats','on the scaffold'
        if first=='Barry' and 'cleaning' in activity and w.get('condition') in ('heavy_rain','thunder'):
            return home_location(name),'window round stopped by heavy rain'
    return location,activity


def routine_inputs(c,at,real_at=None):
    from evorium import economy,weather,bad_days
    return {**economy.stats(c),'_weather':weather.read(c,at,real_at),
            '_bad_days':{r['name']:r for r in bad_days.records(c,at).values()}}


def _routine(name,dt,stats=None):
    location,activity=_routine_location(name,dt,stats)
    free=activity not in ('off sick at home','running late getting ready','covering Jess behind the bar','asleep','behind the bar',"doing the pub's shopping",'working the bar','cleaning shift','behind the counter','at work','at the office','driving','on the scaffold','helping on the counter','at lectures','delivering the barrels','on his delivery round','working on her story','on his post round','on patrol','cleaning windows','doing his round along the terrace','cleaning the windows along the terrace')
    return location,activity,free


def routine(name,dt,stats=None):
    return _routine(name,dt,stats)[:2]


def is_free(name,dt,stats=None):
    return _routine(name,dt,stats)[2]


def home_location(name):
    return {'Dez':'Flat above The Crooked Billet','Jess':'Flat, Miles Platting','Tommy':'Flat, Blossom Street',
            'Raj':'Home, Cheetham Hill','Chloe':'Rented room, Stockport','Simon':'Home, Hale','Brenda':'Home, Blossom Street','Mohammed':'Home, Manchester','Peggy':'Sheltered flat, Ancoats','Liam':'Flat, Clayton',
            'Anjali':'Home, Cheetham Hill','Pete':'Home, Failsworth','Hannah':'Flat, Northern Quarter',
            'Gary':'Home, Newton Heath','Kirsty':'Flat, Miles Platting','Grace':'Home, Gorton','Barry':'Home, Beswick','Ronnie':'Flat, Ancoats'}.get(name.split()[0],'Home, Ancoats')


def whereabouts(agent,now,db_path=DEFAULT_DB_PATH):
    with connect(db_path) as c:
        from evorium.economy import stats
        values = routine_inputs(c, now)
        if (values.get("pub.closed") and agent["name"].split()[0] in ("Dez", "Jess")) or (values.get("shop.open", 1) == 0 and agent["name"].split()[0] == "Raj"):
            return routine(agent["name"], now, values)
        from evorium import bad_days
        if bad_days.blocks(values.get('_bad_days',{}).get(agent['name'],{}),now):return routine(agent['name'],now,values)
        plan=c.execute("""SELECT * FROM plans WHERE agent_id=? AND status='active' AND action IN ('visit','stay_home')
            AND start_at<=? AND end_at>? ORDER BY id DESC LIMIT 1""",(agent['id'],now.strftime('%Y-%m-%d %H:%M'),now.strftime('%Y-%m-%d %H:%M'))).fetchone()
    if plan:
        if plan['action']=='stay_home':return home_location(agent['name']),'staying home'
        from evorium import places
        if not places.is_open(plan['place'], now, values):
            return routine(agent['name'], now, values)
        return REGISTRY[plan['place']], {'shop':'popping into the shop','street':'out on the street','pub':'in for a drink'}.get(plan['place'],'visiting '+places.PLACES[plan['place']].name)
    loc, act = routine(agent['name'],now,values)
    if loc == PUB and not pub_open(now, values):
        return home_location(agent['name']), 'at home while the pub is shut'
    return loc, act

def present_in_pub(agents: list[dict], dt: datetime) -> list[dict]:
    return [a for a in agents if a.get("kind", "npc") == "npc" and routine(a["name"], dt)[0] == PUB]


def pick_pair(ids: list[int], db_path: str | Path = DEFAULT_DB_PATH, recent_window: int = 3, *, automatic=True) -> tuple[int, int]:
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
        day = now(db_path).strftime('%Y-%m-%d')
        pair_counts = {frozenset((r['agent_a_id'],r['agent_b_id'])):r['n'] for r in connection.execute("""SELECT v.agent_a_id,v.agent_b_id,count(*) AS n FROM
            (SELECT min(agent_a_id,agent_b_id) AS agent_a_id,max(agent_a_id,agent_b_id) AS agent_b_id FROM conversations
             WHERE status IN ('completed','running') AND substr(sim_at,1,10)=?
             AND agent_a_id IN (SELECT id FROM agents WHERE kind='npc') AND agent_b_id IN (SELECT id FROM agents WHERE kind='npc')) v
            GROUP BY v.agent_a_id,v.agent_b_id""", (day,))}
        from evorium import cases
        preferred = cases.priority(connection, [i for i in ids if i in allowed], now(db_path))
        if preferred and (not automatic or pair_counts.get(frozenset(preferred),0)<2):
            return preferred
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
    if automatic:
        pairs = [p for p in pairs if pair_counts.get(frozenset(p),0)<2]
        if not pairs:
            raise PairLimitReached('This pair has talked enough today; let the place be quiet.')
    candidates = [p for p in pairs if frozenset(p) not in recent] or pairs
    oldest = max(max(person_seen.get(a,50),person_seen.get(b,50)) for a,b in candidates)
    candidates = [p for p in candidates if max(person_seen.get(p[0],50),person_seen.get(p[1],50))==oldest]
    # Favour pairs who haven't met lately AND people who haven't spoken lately, so quiet characters get a turn
    # rather than whoever is always behind the bar.
    weights = [(1 + last_seen.get(frozenset(p), 50)) * (1 + (person_seen.get(p[0], 50) + person_seen.get(p[1], 50)) / 2)
               for p in candidates]
    a, b = random.choices(candidates, weights=weights, k=1)[0]
    return (a, b) if random.random() < 0.5 else (b, a)


class PairLimitReached(ValueError):
    """Silence at this opportunity, rather than shopping around other places."""


def shared_free_hours(names, start, stats=None):
    """Pure audit: count full shared 30-minute slots, checking every minute, not just arrival."""
    from evorium import places
    hours = dict.fromkeys(names, 0.0)
    for slot in range(7*48):
        begin=start.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(minutes=30*slot)
        shared=None
        for minute in range(30):
            at=begin+timedelta(minutes=minute)
            groups={key:[] for key in places.REGISTRY}
            for name in names:
                location,_,free=_routine(name,at,stats)
                if free:
                    for key,place in places.REGISTRY.items():
                        if location==place and places.is_open(key,at,stats):groups[key].append(name)
            together={name for group in groups.values() if len(group)>1 for name in group}
            shared=together if shared is None else shared & together
            if not shared:break
        for name in shared:hours[name]+=.5
    return hours
