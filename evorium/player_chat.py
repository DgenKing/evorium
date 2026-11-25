"""Private human messages, separate from simulation conversations."""
import time

from fastapi import HTTPException

from evorium import accounts, world
from evorium.db import connect

PAGE_SIZE = 100
BUBBLE_SECONDS = 14

FIELDS = """m.id, m.sender_id, m.recipient_id, m.text, m.sent_at, m.read_at, m.nearby_place,
            s.account AS sender, s.name AS sender_name, r.account AS recipient, r.name AS recipient_name"""
JOINS = """FROM player_chat m JOIN agents s ON s.id=m.sender_id JOIN agents r ON r.id=m.recipient_id"""


def _peer(c, account, allowed, *, create=False):
    account = account.casefold()
    if account == accounts.current.get() or account not in allowed:
        raise HTTPException(404, 'Choose another player account.')
    row = c.execute("SELECT id,name FROM agents WHERE kind='player' AND account=?", (account,)).fetchone()
    if row is None and create:
        row = accounts.player_row(c, account, allowed[account])
    return account, row


def _message(c, message_id):
    return dict(c.execute(f'SELECT {FIELDS} {JOINS} WHERE m.id=?', (message_id,)).fetchone())


def send(db_path, allowed, peer, text, *, now=None):
    text = text.strip()
    if not 1 <= len(text) <= 300:
        raise HTTPException(422, 'Write between 1 and 300 characters.')
    with connect(db_path) as c:
        c.execute('BEGIN IMMEDIATE')
        now = time.time() if now is None else now
        sender = accounts.player_row(c)
        last = c.execute('SELECT sent_at FROM player_chat WHERE sender_id=? ORDER BY id DESC LIMIT 1',
                         (sender['id'],)).fetchone()
        if last and now - last[0] < 1:
            raise HTTPException(429, 'Wait a second between messages.')
        account, target = _peer(c, peer, allowed, create=True)
        place = world._get(c, accounts.setting_key('player_place'))
        near = place if place and place == world._get(c, accounts.setting_key('player_place', account)) else None
        message_id = c.execute("""INSERT INTO player_chat(sender_id,recipient_id,text,sent_at,nearby_place)
                                  VALUES (?,?,?,?,?)""",
                               (sender['id'], target['id'], text, now, near)).lastrowid
        return _message(c, message_id)


def inbox(db_path, allowed, after):
    account = accounts.current.get()
    with connect(db_path) as c:
        c.execute('BEGIN')
        who = accounts.player_row(c)['id']
        profiles = dict(c.execute("SELECT account,name FROM agents WHERE kind='player'"))
        contacts = [{'account': key, 'name': profiles.get(key, name)} for key, name in allowed.items() if key != account]
        contacts.sort(key=lambda person: person['name'].casefold())
        unread = [dict(row) for row in c.execute(
            f"""SELECT {FIELDS} {JOINS} WHERE m.recipient_id=? AND m.read_at IS NULL
                 ORDER BY m.id DESC LIMIT ?""", (who, PAGE_SIZE))]
        if after is None:
            cursor = c.execute('SELECT coalesce(max(id),0) FROM player_chat WHERE sender_id=? OR recipient_id=?',
                               (who, who)).fetchone()[0]
            messages = []
        else:
            messages = [dict(row) for row in c.execute(
                f"""SELECT {FIELDS} {JOINS} WHERE m.id>? AND (m.sender_id=? OR m.recipient_id=?)
                     ORDER BY m.id LIMIT ?""", (after, who, who, PAGE_SIZE))]
            cursor = messages[-1]['id'] if messages else after
    return {'cursor': cursor, 'messages': messages, 'unread': unread, 'contacts': contacts, 'account': account}


def thread(db_path, allowed, peer):
    with connect(db_path) as c:
        _, target = _peer(c, peer, allowed)
        if target is None:
            return []
        who = accounts.player_row(c)['id']
        other = target['id']
        rows = c.execute(f"""SELECT {FIELDS} {JOINS}
            WHERE (m.sender_id=? AND m.recipient_id=?) OR (m.sender_id=? AND m.recipient_id=?)
            ORDER BY m.id DESC LIMIT ?""", (who, other, other, who, PAGE_SIZE))
        return [dict(row) for row in reversed(rows.fetchall())]


def read(db_path, allowed, peer, through):
    with connect(db_path) as c:
        _, target = _peer(c, peer, allowed)
        if target is not None:
            who = accounts.player_row(c)['id']
            c.execute("""UPDATE player_chat SET read_at=? WHERE sender_id=? AND recipient_id=?
                         AND id<=? AND read_at IS NULL""", (time.time(), target['id'], who, through))


def speech_activity(c, at):
    """The rendering snapshot gets only a sender's recent activity time and place."""
    return {(r['sender_id'], r['nearby_place']): r['sent_at'] for r in c.execute(
        """SELECT sender_id, nearby_place, max(sent_at) AS sent_at FROM player_chat
           WHERE sent_at>? AND sent_at<=? AND nearby_place IS NOT NULL
           GROUP BY sender_id, nearby_place""", (at - BUBBLE_SECONDS, at))}
