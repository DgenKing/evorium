"""Deterministic arcade rota and shared layout metadata."""
from datetime import date, timedelta
import json
from pathlib import Path

NORMAN = 'Norman Pilling'
MAXINE = 'Maxine Stott'
STAFF = (NORMAN, MAXINE)
NORMAN_HOME = 'Flat above Gun Street Amusements, Gun Street'
MAXINE_HOME = 'Flat, Blossom Street'
LAYOUT = json.loads((Path(__file__).parent / 'static/world3d/data/arcade.json').read_text(encoding='utf-8'))
EPOCH = date(2026, 11, 23)


def on_shift(at):
    """Select the sole staff member responsible, using UK wall time."""
    day = at.date() if at.hour >= 7 else at.date() - timedelta(days=1)
    week = (day - EPOCH).days // 7
    return STAFF[(week + (not 7 <= at.hour < 19)) % 2]


def handover(at):
    minute = at.hour * 60 + at.minute
    return 410 <= minute < 430 or 1130 <= minute < 1150


def staff_present(at, records=None):
    from evorium.bad_days import blocks
    records = records or {}
    return tuple(name for name in STAFF if (name == on_shift(at) or handover(at))
                 and not blocks(records.get(name, {}), at))


def staff_routine(name, at, values):
    from evorium import places, world
    first = name.split()[0]
    home = NORMAN_HOME if name == NORMAN else MAXINE_HOME
    responsible = on_shift(at)
    if name == responsible:
        return places.REGISTRY['arcade'], ('working the change booth in a tie' if first == 'Norman' and
                                           (at.hour < 7 or at.hour >= 19) else 'working the change booth')
    if handover(at):
        return places.REGISTRY['arcade'], 'handing over at the change booth'
    hour, wd = at.hour + at.minute / 60, at.weekday()
    daytime = 7 <= hour < 19
    if (daytime and 8 <= hour < 15) or (not daytime and (hour >= 22 or hour < 6)):
        return home, 'asleep'
    if wd in (0, 2, 4, 5, 6) and ((15 <= hour < 17) if daytime else (20 <= hour < 21.5)):
        if world.pub_open(at, values):
            return world.PUB, 'having a half after the shift'
    if wd == 3 and 15 <= hour < 16 and places.is_open('cafe', at, values):
        return places.REGISTRY['cafe'], 'having a coffee after the night shift'
    if wd in (1, 5) and 15 <= hour < 16 and places.is_open('shop', at, values):
        return world.SHOP, 'running errands after the shift'
    return home, 'at home with Gerald' if name == NORMAN else 'at home after the shift'


# New visits fit around the existing darts, Friday pub visit, and shop shifts.
VISITS = {
    'Mohammed': ((4, 5, 6), 1, 1 + 20/60, 'taking a night break by the coin pushers'),
    'Ronnie': ((1, 5), 15, 16, 'trying his luck on the fruit machines'),
    'Liam': ((4,), 21, 22, 'playing air hockey'),
    'Anjali': ((4, 6), 19, 20, 'trying the claw crane with friends'),
    'Kirsty': ((6,), 19, 19.5, 'watching Anjali try the claw crane'),
}
