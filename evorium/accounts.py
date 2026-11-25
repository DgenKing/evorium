"""Request identity and player ownership. Credentials stay in private configuration."""
import hmac
from contextvars import ContextVar

from evorium.db import DEFAULT_DB_PATH, connect

current = ContextVar('evorium_account', default='owner')


def setting_key(key, account=None):
    account = current.get() if account is None else account
    return key if account == 'owner' else f'{key}:{account}'


def authenticate(username, supplied, owner_secret, named):
    """Named credentials take precedence; the existing owner login remains a fallback."""
    if not owner_secret and not named:
        return 'owner', None
    if supplied is None:
        return None
    for display, secret in named.items():
        if (display.casefold() != 'owner' and username.casefold() == display.casefold()
                and secret and hmac.compare_digest(supplied.encode('utf-8'), secret.encode('utf-8'))):
            return display.casefold(), display
    if owner_secret and hmac.compare_digest(supplied.encode('utf-8'), str(owner_secret).encode('utf-8')):
        return 'owner', None
    return None


def player_row(c, account=None, display_name=None):
    account = current.get() if account is None else account
    found = c.execute("SELECT * FROM agents WHERE kind='player' AND account=?", (account,)).fetchone()
    if found:
        return dict(found)
    # Serialized by ensure_player for HTTP requests, or by the caller's write transaction.
    base = display_name or ('Stranger' if account == 'owner' else account)
    names = {r[0].casefold() for r in c.execute('SELECT name FROM agents')}
    reserved = names | {n.split()[0] for n in names if n}
    name = base
    suffix = 1
    while name.casefold() in reserved or name.split()[0].casefold() in reserved:
        name = f'Player{suffix} — {base[:18]}'
        suffix += 1
    c.execute("""INSERT INTO agents
        (name,age,occupation,background,personality,current_goal,mood,location,kind,account)
        VALUES (?,0,'New face in Ancoats','Known only through conversation','Human player',
        'Meet the neighbours','curious','Not in the world','player',?)""", (name, account))
    return dict(c.execute('SELECT * FROM agents WHERE account=?', (account,)).fetchone())


def ensure_player(account, display_name, db_path=DEFAULT_DB_PATH):
    with connect(db_path) as c:
        found = c.execute("SELECT * FROM agents WHERE kind='player' AND account=?", (account,)).fetchone()
        if found:
            return dict(found)
        c.execute('BEGIN IMMEDIATE')
        return player_row(c, account, display_name)


def other_players(c, settings=None, *, include_account=False):
    settings = dict(c.execute('SELECT key,value FROM world')) if settings is None else settings
    people = []
    for r in c.execute("SELECT id,name,kind,account,location,activity,mood FROM agents WHERE kind='player' AND account!=? ORDER BY id", (current.get(),)):
        place = settings.get(setting_key('player_place', r['account']))
        if place:
            person = {key: r[key] for key in ('id', 'name', 'kind', 'location', 'activity', 'mood')}
            if include_account:
                person['account'] = r['account']
            people.append(dict(person, place=place))
    return people
