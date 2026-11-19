"""The terrace ledger. Whole pounds, except the explicitly named pint price in pence."""
from datetime import datetime, timedelta
from evorium.db import DEFAULT_DB_PATH, connect, npc_agents
from evorium import timeline, relationships, world
from evorium.memory import DUE_FMT
from evorium.events import emit

BASE_PINTS = 700
FOOD = 300
STOCK_FRACTION = .40
HOURLY_PAY = 12.21
SHIFT_HOURS = 6
OVERHEADS = 525  # tuned weekly running costs: +£240 at old rent, −£106 at renewal rent
DRAWINGS = 500
QUIZ_PINTS = 110
MAX_SURRENDER = 60000
MIN_RENT = 3300
LEASE_END = (datetime(2027, 3, 25) - datetime(1970, 1, 1)).days
START = {
    'pub.pint_price_p': (460, 'public'), 'pub.rent_month': (2400, 'Dez,Simon'),
    'pub.lease_end': (LEASE_END, 'Dez,Simon,Jess'), 'pub.savings': (6000, 'Dez'),
    'pub.takings_last_week': (BASE_PINTS * 460 // 100 + FOOD, 'Dez,Jess'), 'pub.quiz': (0, 'public'),
    'pub.quiz_questions_ready': (0, 'Tommy,Dez,Jess'), 'jess.shifts': (4, 'Jess,Dez'),
    'jess.job_hunting': (0, 'Jess'), 'shop.open': (1, 'public'), 'raj.savings': (18000, 'Raj'),
    'terrace.petition': (0, 'public'), 'mo.darts_signups': (0, 'public'),
    'chloe.flat_found': (0, 'Chloe'), 'pub.closed': (0, 'public'),
}


def stats(c):
    return {r['key']: r['value'] for r in c.execute('SELECT key,value FROM stats')}


def read(db_path=DEFAULT_DB_PATH):
    with connect(db_path) as c:
        return stats(c)


def change(c, key, value, reason, now, action_id=None):
    row = c.execute('SELECT value FROM stats WHERE key=?', (key,)).fetchone()
    old = row[0] if row else None
    c.execute('INSERT INTO stats VALUES (?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',
              (key, int(value), START.get(key, (0, 'public'))[1], now.strftime(DUE_FMT)))
    if old != value:
        c.execute('INSERT INTO stat_changes(key,old,new,reason,sim_at,action_id) VALUES (?,?,?,?,?,?)',
                  (key, old, value, reason, now.strftime(DUE_FMT), action_id))


def fact(c, aid, text, now, importance=4, source_id=None):
    fid = c.execute("INSERT INTO facts(agent_id,subject,content,source,source_agent_id,importance) VALUES (?,'terrace',?,?,?,?)",
                     (aid, text, 'told' if source_id else 'observed', source_id, importance)).lastrowid
    if importance == 5:
        schedule(c, aid, f'Important news {fid}', now)
    return fid


def schedule(c, aid, reason, now, hours=2):
    c.execute('INSERT OR IGNORE INTO reactions(agent_id,reason,due_at) VALUES (?,?,?)',
              (aid, reason, (now + timedelta(hours=max(1, min(36, hours)))).strftime(DUE_FMT)))


def offer(c, kind, sender, recipient, amount, terms, now, expires, action_id=None):
    oid = c.execute("INSERT INTO offers(kind,from_id,to_id,amount,terms,status,created_at,expires_at,source_action_id) VALUES (?,?,?,?,?,'open',?,?,?)",
                    (kind, sender, recipient, amount, terms, now.strftime(DUE_FMT), expires.strftime(DUE_FMT), action_id)).lastrowid
    text = f"A {kind} offer of £{amount:,}: {terms}. Reply by {expires.strftime('%d %b')}."
    for aid in {sender, recipient} - {None}:
        fact(c, aid, text, now)
    schedule(c, recipient, f'Offer {oid} arrived', now)
    timeline.record(c, now, 'offer', text, 4, recipient, sender)
    return oid


def seed_offers(c):
    cast = {a['name'].split()[0]: a['id'] for a in npc_agents(c)}
    if not all(n in cast for n in ('Simon', 'Dez', 'Raj')):
        return
    for seed, kind, to, amount, days, terms in (
        ('northgate-figures', 'renewal', 'Dez', 3900, 28, 'new lease from 25 March 2027'),
        ('raj-figure', 'surrender', 'Raj', 45000, 30, 'surrender the shop lease; handover in 30 days'),
    ):
        event = c.execute('SELECT coalesce(delivered_at,at) AS at FROM scheduled_events WHERE seed_key=? AND delivered=1', (seed,)).fetchone()
        if event and not c.execute('SELECT 1 FROM offers WHERE kind=?', (kind,)).fetchone():
            at = datetime.strptime(event['at'], DUE_FMT)
            offer(c, kind, cast['Simon'], cast[to], amount, terms, at, at + timedelta(days=days))


def ensure(db_path, now):
    with connect(db_path) as c:
        for key, (value, visible) in START.items():
            c.execute('INSERT OR IGNORE INTO stats VALUES (?,?,?,?)', (key, value, visible, now.strftime(DUE_FMT)))
        c.execute("INSERT OR IGNORE INTO arcs(key,status,started_at) VALUES ('northgate','active',?)", (now.strftime(DUE_FMT),))
        if world._get(c, 'settlement_cursor') is None:
            world._set(c, 'settlement_cursor', now.strftime(DUE_FMT))
        seed_offers(c)


def week(values, falling_out=0):
    price = values.get('pub.pint_price_p', 460)
    steps = (price - 460) / 10
    multiplier = max(0, 1 - steps * .04) if steps >= 0 else 1 - steps * .03
    shifts = values.get('jess.shifts', 4)
    pints = BASE_PINTS * multiplier + (QUIZ_PINTS if values.get('pub.quiz') == 2 else 0)
    if shifts < 3:
        pints *= .92
    pints = max(0, round(pints - falling_out * 15))
    revenue = round(pints * price / 100 + FOOD)
    costs = round(revenue * STOCK_FRACTION + HOURLY_PAY * SHIFT_HOURS * shifts + OVERHEADS + values.get('pub.rent_month', 2400) * 12 / 52 + DRAWINGS)
    return {'pints': pints, 'revenue': revenue, 'costs': costs, 'profit': revenue - costs}


def settlement(c, now):
    s = stats(c)
    dez = c.execute("SELECT id FROM agents WHERE name LIKE 'Dez %'").fetchone()[0]
    cold = c.execute("SELECT count(*) FROM relationships r JOIN agents a ON a.id=r.agent_id WHERE r.other_id=? AND r.warmth<45 AND a.kind='npc' AND a.name NOT LIKE 'Simon %'", (dez,)).fetchone()[0]
    result = week(s, cold)
    reason = f"The Billet took £{result['revenue']:,} this week; after costs it {'made' if result['profit'] >= 0 else 'lost'} £{abs(result['profit']):,}."
    change(c, 'pub.takings_last_week', result['revenue'], reason, now)
    change(c, 'pub.savings', s['pub.savings'] + result['profit'], reason, now)
    timeline.record(c, now, 'action', reason, 3, dez)
    emit(reason)
    if s['pub.savings'] + result['profit'] < 1000 and not world._get(c, 'savings_warning'):
        world._set(c, 'savings_warning', '1')
        text = 'Dez has less than £1,000 left to keep the Billet going.'
        timeline.record(c, now, 'world_event', text, 4, dez)
        fact(c, dez, text, now)
    return result


def notice(c, place, text, aid, now, rise=0):
    nid = c.execute('INSERT INTO notices(place,text,by_id,since,price_rise) VALUES (?,?,?,?,?)',
                    (place, text, aid, now.strftime(DUE_FMT), rise)).lastrowid
    from evorium import places
    for a in npc_agents(c):
        if a['location'] == places.REGISTRY[place]:
            schedule(c, a['id'], f'Notice {nid}', now)
    return nid


def observe(c, actor, now):
    from evorium import places
    place = next((key for key, name in places.REGISTRY.items() if actor['location'] == name), None)
    if not place:
        return
    for n in c.execute('SELECT * FROM notices WHERE place=? AND since<=? AND (until IS NULL OR until>?)', (place, now.strftime(DUE_FMT), now.strftime(DUE_FMT))).fetchall():
        if c.execute('INSERT OR IGNORE INTO notice_seen VALUES (?,?)', (n['id'], actor['id'])).rowcount:
            fact(c, actor['id'], n['text'], now, 3)
            if n['price_rise'] >= 20 and actor['id'] != n['by_id'] and actor['name'].split()[0] != 'Simon':
                relationships.adjust(c, actor['id'], n['by_id'], 0, -2, 'The pint price went up.', now)
    for f in c.execute('SELECT * FROM deferred_facts WHERE agent_id=?', (actor['id'],)).fetchall():
        source = c.execute('SELECT location FROM agents WHERE id=?', (f['source_id'],)).fetchone()
        learned = stats(c).get('shop.open', 1) == 0 if f['penalty'] else source and source[0] == actor['location']
        if learned:
            fact(c, actor['id'], f['content'], now, source_id=None if f['penalty'] else f['source_id'])
            relationships.adjust(c, actor['id'], f['source_id'], f['penalty'] or 5, 0, f['content'], now)
            c.execute('DELETE FROM deferred_facts WHERE id=?', (f['id'],))


def situation(c, actor, now):
    name = actor['name'].split()[0]
    lines = []
    # Decisions and offers take precedence over routine public numbers.
    for r in c.execute("SELECT * FROM actions WHERE agent_id=? AND status='considering' ORDER BY id DESC LIMIT 1", (actor['id'],)):
        lines.append(f"You were leaning towards {r['key'].replace('_', ' ')}: {r['reason']}")
    for r in c.execute("SELECT * FROM offers WHERE status='open' AND (to_id=? OR from_id=?) ORDER BY expires_at", (actor['id'], actor['id'])):
        lines.append(f"Offer {r['id']}: {r['kind']}, £{r['amount']:,}; {r['terms']}; expires {r['expires_at']}.")
    for r in c.execute("SELECT * FROM asks WHERE status='open' AND (to_id=? OR from_id=?)", (actor['id'], actor['id'])):
        lines.append(f"Ask {r['id']}: {r['kind'].replace('_', ' ')}, amount {r['amount'] or 'none'}; reply by {r['expires_at']}.")
    if name == 'Simon':
        lines.append('Your authority: up to £60,000 / no lower than £3,300.')
    private, public = [], []
    for r in c.execute('SELECT * FROM stats'):
        visible = r['visible_to']
        if visible != 'public' and name not in visible.split(',') and not (visible == 'pub_regulars' and name != 'Simon'):
            continue
        key, value = r['key'], r['value']
        if key in ('terrace.petition', 'mo.darts_signups') and not value:
            continue
        if key == 'pub.lease_end':
            value = (datetime(1970, 1, 1) + timedelta(days=value)).strftime('%d %b %Y')
        elif key == 'pub.pint_price_p':
            value = f'£{value / 100:.2f}'
        elif any(w in key for w in ('savings', 'rent_month', 'takings', 'budget')):
            value = f'about £{value:,}'
        elif key == 'pub.quiz':
            value = ['not yet announced', 'announced', 'running weekly'][value]
        label = key.replace('.', ' ').replace('_', ' ')
        (public if visible == 'public' else private).append(f'{label}: {value}')
    # Group routine figures so current offers cannot crowd the pint price or savings out.
    grouped = []
    if private:
        grouped.append('Your figures: ' + '; '.join(private))
    if public:
        grouped.append('Around the terrace: ' + '; '.join(public))
    if len(lines) > 4:
        lines = lines[:3] + [' '.join(lines[3:])]
    return lines + grouped



def maintain(now, db_path=DEFAULT_DB_PATH, client=None):
    with connect(db_path) as c:
        seed_offers(c)
        at = now.strftime(DUE_FMT)
        for o in c.execute("SELECT * FROM offers WHERE status='open'").fetchall():
            if o['expires_at'] <= at:
                c.execute("UPDATE offers SET status='expired',resolved_at=? WHERE id=?", (at, o['id']))
                text = f"The £{o['amount']:,} {o['kind']} offer expired without agreement."
                timeline.record(c, now, 'offer', text, 4, o['to_id'], o['from_id'])
                for aid in {o['from_id'], o['to_id']} - {None}:
                    fact(c, aid, text, now)
            elif o['expires_at'] <= (now + timedelta(days=3)).strftime(DUE_FMT):
                schedule(c, o['to_id'], f"Offer {o['id']} is nearly due", now)
        for ask in c.execute("SELECT * FROM asks WHERE status='open' AND expires_at<=?", (at,)).fetchall():
            c.execute("UPDATE asks SET status='expired' WHERE id=?", (ask['id'],))
            other = c.execute('SELECT name FROM agents WHERE id=?', (ask['to_id'],)).fetchone()[0]
            fact(c, ask['from_id'], f"{other} hasn't replied to my request.", now)
        closes = world._get(c, 'shop_closes_at')
        if closes and closes <= at and stats(c).get('shop.open', 1):
            text = "Raj handed over Patel's News after accepting Northgate's surrender offer; the shop is shut."
            change(c, 'shop.open', 0, text, now)
            raj = c.execute("SELECT id FROM agents WHERE name LIKE 'Raj %'").fetchone()[0]
            for place in ('pub', 'shop'):
                notice(c, place, text, raj, now)
            timeline.record(c, now, 'world_event', text, 4, raj)
        s = stats(c)
        lease = datetime(1970, 1, 1) + timedelta(days=s.get('pub.lease_end', LEASE_END))
        hunt = world._get(c, 'job_hunt_started')
        if hunt and at >= (datetime.strptime(hunt, DUE_FMT) + timedelta(days=14)).strftime(DUE_FMT) and s.get('jess.job_hunting') and s.get('jess.shifts', 4) <= 4:
            if not c.execute("SELECT 1 FROM offers WHERE kind='job'").fetchone():
                jess = c.execute("SELECT id FROM agents WHERE name LIKE 'Jess %'").fetchone()[0]
                offer(c, 'job', None, jess, 440, 'Bar work elsewhere, six evenings a week', now, now + timedelta(days=7))
        cursor = datetime.strptime(world._get(c, 'settlement_cursor', at), DUE_FMT)
        due = cursor.replace(hour=23, minute=59, second=0, microsecond=0) + timedelta(days=(6 - cursor.weekday()) % 7)
        if due <= cursor:
            due += timedelta(days=7)
        while due <= now:
            if due >= lease and not s.get('pub.closed'):
                renewal = c.execute("SELECT * FROM offers WHERE kind='renewal' AND status='accepted' ORDER BY id DESC LIMIT 1").fetchone()
                if renewal:
                    change(c, 'pub.rent_month', renewal['amount'], 'The new pub lease has begun.', due)
                else:
                    change(c, 'pub.closed', 1, 'The pub lease ended without a renewal.', due)
            if not stats(c).get('pub.closed'):
                settlement(c, due)
                if stats(c)['pub.savings'] < -2000:
                    change(c, 'pub.closed', 1, 'The Billet ran out of money.', due)
                    world._set(c, 'pub_bust', '1')
            due += timedelta(days=7)
        if now >= lease and not s.get('pub.closed'):
            renewal = c.execute("SELECT * FROM offers WHERE kind='renewal' AND status='accepted' ORDER BY id DESC LIMIT 1").fetchone()
            if renewal:
                change(c, 'pub.rent_month', renewal['amount'], 'The new pub lease has begun.', now)
            else:
                change(c, 'pub.closed', 1, 'The pub lease ended without a renewal.', now)
        world._set(c, 'settlement_cursor', max(now, cursor).strftime(DUE_FMT))
    from evorium import arcs
    arcs.maintain(now, db_path, client)


def ledger(db_path, now):
    with connect(db_path) as c:
        return {'stats': stats(c), 'offers': [dict(r) for r in c.execute('SELECT * FROM offers ORDER BY id DESC')],
                'notices': [dict(r) for r in c.execute('SELECT * FROM notices WHERE since<=? AND (until IS NULL OR until>?)', (now.strftime(DUE_FMT), now.strftime(DUE_FMT)))],
                'arcs': [dict(r) for r in c.execute('SELECT * FROM arcs ORDER BY id')]}
