"""Fixed action menu. Every entry point uses the same transactional validation path."""
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model
from evorium import economy as e, relationships, timeline, world
from evorium.db import DEFAULT_DB_PATH, connect, npc_agents
from evorium.events import emit
from evorium.memory import DUE_FMT


class Args(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)


def schema(name, **fields):
    return create_model(name, __base__=Args, **fields)


Empty = Args
Price = schema('Price', pence=(int, Field(ge=-30, le=50)))
Shifts = schema('Shifts', shifts=(int, Field(ge=2, le=6)))
OfferID = schema('OfferID', offer_id=(int, Field(ge=1)))
Rent = schema('Rent', amount=(int, Field(ge=2400, le=3899)))
More = schema('More', amount=(int, Field(ge=45001, le=90000)))
Raise = schema('Raise', offer_id=(int, Field(ge=1)), amount=(int, Field(ge=1, le=e.MAX_SURRENDER)))
Deal = schema('Deal', amount=(int, Field(ge=e.MIN_RENT)), years=(int, Field(ge=1, le=10)))
Deadline = schema('Deadline', offer_id=(int, Field(ge=1)), days=(int, Field(ge=3, le=14)))
Loan = schema('Loan', person=(str, Field(min_length=1, max_length=60)), amount=(int, Field(ge=500, le=10000)))
Questions = schema('Questions', count=(int, Field(ge=5, le=20)))
Petition = schema('Petition', text=(str, Field(min_length=1, max_length=120)))
Answer = schema('Answer', ask_id=(int, Field(ge=1)), answer=(Literal['yes', 'no'], ...))
PolicePerson = schema('PolicePerson', person=(str, Field(min_length=1, max_length=60)))
Tell = schema('Tell', person=(str, Field(min_length=1, max_length=60)), fact_id=(int, Field(ge=1)))


@dataclass(frozen=True)
class Action:
    key: str
    who: str
    args_schema: type[BaseModel]
    importance: int = 3
    big: bool = False
    cooldown_hours: int = 0
    witnesses: str = 'none'

    def check(self, c, actor, args, now):
        return check(c, actor, self.key, args, now)

    def apply(self, c, actor, args, now):
        return apply(c, actor, self.key, args, now)


MENU = [
    ('change_pint_price', 'Dez', Price, False, 168, 'place'),
    ('set_jess_shifts', 'Dez', Shifts, False, 168, 'target'),
    ('announce_quiz', 'Dez', Empty, False, 0, 'place'),
    ('start_quiz', 'Dez', Empty, False, 0, 'place'),
    ('ring_northgate', 'Dez', Empty, False, 0, 'none'),
    ('counter_rent', 'Dez', Rent, False, 0, 'target'),
    ('accept_renewal', 'Dez', OfferID, True, 0, 'target'),
    ('refuse_renewal', 'Dez', OfferID, True, 0, 'target'),
    ('ask_loan', 'Dez', Loan, False, 0, 'target'),
    ('accept_surrender', 'Raj', OfferID, True, 0, 'target'),
    ('refuse_surrender', 'Raj', OfferID, True, 0, 'target'),
    ('ask_more', 'Raj', More, False, 0, 'target'),
    ('warn_neighbours', 'Raj', Empty, False, 0, 'target'),
    ('raise_offer', 'Simon', Raise, False, 0, 'target'),
    ('offer_rent_deal', 'Simon', Deal, False, 0, 'target'),
    ('set_deadline', 'Simon', Deadline, False, 0, 'target'),
    ('ask_more_hours', 'Jess', Empty, False, 168, 'target'),
    ('start_job_hunt', 'Jess', Empty, True, 0, 'none'),
    ('write_quiz_questions', 'Tommy', Questions, False, 0, 'none'),
    ('start_petition', 'Brenda', Petition, False, 0, 'place'),
    ('sign_petition', 'any', Empty, False, 0, 'none'),
    ('start_darts_team', 'Mohammed', Empty, False, 0, 'place'),
    ('join_darts', 'any', Empty, False, 0, 'none'),
    ('answer_ask', 'any', Answer, False, 0, 'target'),
    ('tell', 'any', Tell, False, 0, 'target'),
    ('give_advice', 'Grace', PolicePerson, False, 0, 'none'),
    ('give_formal_warning', 'Grace', PolicePerson, False, 0, 'none'),
    ('wait', 'any', Empty, False, 0, 'none'),
    # A job offer also needs a real choice, through the same guarded path.
    ('accept_job', 'Jess', OfferID, True, 0, 'target'),
    ('refuse_job', 'Jess', OfferID, False, 0, 'none'),
]
REGISTRY = {key: Action(key, who, model, 4 if big else 3, big, cooldown, witnesses)
            for key, who, model, big, cooldown, witnesses in MENU}


class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    action: str = Field(max_length=60)
    args: dict = Field(default_factory=dict)
    reason: str = Field(min_length=1, max_length=400)
    evidence: list[int] = Field(default_factory=list, max_length=12)
    new_goal: str | None = Field(default=None, min_length=1, max_length=120)


class SpokenDecision(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    action: str = Field(max_length=60)
    args: dict = Field(default_factory=dict)
    quote: str = Field(min_length=1, max_length=1200)


def person(c, name):
    rows = [a for a in npc_agents(c) if name in (a['name'], a['name'].split()[0])]
    if len(rows) != 1:
        raise ValueError('Choose an established neighbour by name.')
    return rows[0]


def open_offer(c, actor, now, oid=None, kind=None, sender=False):
    clause = 'from_id' if sender else 'to_id'
    rows = c.execute(f"SELECT * FROM offers WHERE {clause}=? AND status='open' AND expires_at>? AND (? IS NULL OR id=?) AND (? IS NULL OR kind=?) ORDER BY id DESC", (actor['id'], now.strftime(DUE_FMT), oid, oid, kind, kind)).fetchall()
    if not rows:
        raise ValueError('There is no matching open offer to answer.')
    return dict(rows[0])


def negotiation_offer(c, actor, now, kind, sender=False, oid=None):
    """A refusal can be met with a fresh improved offer, without erasing history."""
    try:
        return open_offer(c, actor, now, oid, kind, sender)
    except ValueError:
        column = 'from_id' if sender else 'to_id'
        row = c.execute(f"SELECT * FROM offers WHERE {column}=? AND kind=? AND status IN ('refused','expired') AND (? IS NULL OR id=?) ORDER BY id DESC LIMIT 1", (actor['id'], kind, oid, oid)).fetchone()
        if not row:
            raise ValueError('There is no offer to reopen.')
        resolved = datetime.strptime(row['resolved_at'] or row['expires_at'], DUE_FMT)
        if now > resolved + timedelta(days=14):
            raise ValueError('The fourteen-day window to reopen talks has passed.')
        return dict(row)


def guards(c, actor, item, args, now):
    day = now.strftime('%Y-%m-%d')
    if item.key == 'wait':
        return
    extra = "key='tell'" if item.key == 'tell' else "key NOT IN ('tell','wait')"
    if c.execute(f"SELECT 1 FROM actions WHERE agent_id=? AND status='done' AND substr(sim_at,1,10)=? AND {extra}", (actor['id'], day)).fetchone():
        raise ValueError('Already acted today; sleep on the next decision.')
    if item.big:
        count = c.execute("SELECT count(*) FROM actions WHERE status='done' AND substr(sim_at,1,10)=? AND key IN (" + ','.join('?' for a in REGISTRY.values() if a.big) + ')', (day, *[a.key for a in REGISTRY.values() if a.big])).fetchone()[0]
        if count >= 2:
            raise ValueError('Two major decisions have already happened today.')
    if item.cooldown_hours:
        last = c.execute("SELECT sim_at FROM actions WHERE agent_id=? AND key=? AND status='done' ORDER BY id DESC LIMIT 1", (actor['id'], item.key)).fetchone()
        if last and now < datetime.strptime(last[0], DUE_FMT) + timedelta(hours=item.cooldown_hours):
            raise ValueError('It is too soon to do that again.')


def check(c, actor, key, args, now):
    if key not in REGISTRY:
        raise ValueError('That is not on the action menu.')
    item = REGISTRY[key]
    if actor.get('kind', 'npc') != 'npc' or (item.who != 'any' and actor['name'].split()[0] != item.who):
        raise ValueError('This character cannot take that action.')
    a = item.args_schema.model_validate(args).model_dump()
    guards(c, actor, item, a, now)
    s = e.stats(c)
    if key in ('give_advice', 'give_formal_warning'):
        from evorium import cases
        conv = c.execute("SELECT id FROM conversations WHERE status='running' AND (agent_a_id=? OR agent_b_id=?) ORDER BY id DESC LIMIT 1", (actor['id'], actor['id'])).fetchone()
        cases.outcome_case(c, actor, a['person'], conv['id'] if conv else None)
    if key == 'wait':
        return a
    if world.routine(actor['name'], now)[1] == 'asleep':
        raise ValueError('They are asleep; decide when awake.')
    if key in ('change_pint_price', 'announce_quiz', 'start_quiz', 'start_darts_team'):
        if actor['location'] != world.PUB or s.get('pub.closed') or not world.pub_open(now):
            raise ValueError('They need to be in the open pub.')
    if key == 'change_pint_price' and (not a['pence'] or s.get('pub.pint_price_p', 460) + a['pence'] < 100):
        raise ValueError('Choose a real, affordable change in pint price.')
    if key == 'set_jess_shifts' and a['shifts'] == s.get('jess.shifts', 4):
        raise ValueError('Those are already Jess’s shifts.')
    if key == 'announce_quiz' and s.get('pub.quiz', 0) != 0:
        raise ValueError('The quiz has already been announced.')
    if key == 'start_quiz' and (s.get('pub.quiz') != 1 or s.get('pub.quiz_questions_ready', 0) < 40):
        raise ValueError('Announce the quiz and prepare forty questions first.')
    if key == 'ring_northgate':
        simon = person(c, 'Simon')
        if world.routine(simon['name'], now)[1] == 'asleep' or actor['activity'] == 'asleep':
            raise ValueError('Simon is not reachable now.')
        from evorium import plans
        if plans.busy(c, simon['id']) or plans.busy(c, actor['id']):
            raise ValueError('Someone is already on a call.')
    if key in ('accept_renewal', 'refuse_renewal', 'accept_surrender', 'refuse_surrender', 'accept_job', 'refuse_job'):
        open_offer(c, actor, now, a['offer_id'], 'renewal' if key.endswith('renewal') else 'surrender' if key.endswith('surrender') else 'job')
    if key in ('counter_rent', 'ask_more'):
        negotiation_offer(c, actor, now, 'renewal' if key == 'counter_rent' else 'surrender')
        if c.execute("SELECT 1 FROM asks WHERE from_id=? AND kind=? AND status='open'", (actor['id'], key)).fetchone():
            raise ValueError('Wait for an answer to the last request.')
    if key in ('raise_offer', 'set_deadline'):
        o = negotiation_offer(c, actor, now, 'surrender', True, a['offer_id']) if key == 'raise_offer' else open_offer(c, actor, now, a['offer_id'], sender=True)
        if key == 'raise_offer' and (o['kind'] != 'surrender' or a['amount'] <= o['amount']):
            raise ValueError('A raised surrender offer must be higher.')
        if key == 'set_deadline' and (now + timedelta(days=a['days'])).strftime(DUE_FMT) >= o['expires_at']:
            raise ValueError('The new deadline must be earlier.')
    if key == 'offer_rent_deal':
        negotiation_offer(c, actor, now, 'renewal', True)
    if key in ('ask_loan', 'tell'):
        other = person(c, a['person'])
        if other['id'] == actor['id']:
            raise ValueError('Choose another person.')
        if key == 'ask_loan':
            savings = s.get(other['name'].split()[0].lower() + '.savings')
            if savings is not None and savings < a['amount']:
                raise ValueError('They do not have enough savings to lend that much.')
        else:
            if not c.execute('SELECT 1 FROM facts WHERE id=? AND agent_id=? AND importance>=3', (a['fact_id'], actor['id'])).fetchone():
                raise ValueError('They do not know that fact well enough to tell it.')
            if c.execute("SELECT 1 FROM actions WHERE agent_id=? AND key='tell' AND status='done' AND args_json=? AND substr(sim_at,1,10)=?", (actor['id'], json.dumps(a, sort_keys=True), now.strftime('%Y-%m-%d'))).fetchone():
                raise ValueError('They already told that person today.')
    if key == 'warn_neighbours' and c.execute("SELECT 1 FROM actions WHERE key=? AND status='done'", (key,)).fetchone():
        raise ValueError('Raj has already warned the neighbours.')
    if key == 'start_job_hunt' and s.get('jess.job_hunting'):
        raise ValueError('Jess is already looking for work.')
    if key == 'write_quiz_questions':
        agreed = c.execute("SELECT 1 FROM facts WHERE agent_id=? AND lower(content) LIKE '%quiz%' UNION ALL SELECT 1 FROM commitments WHERE agent_id=? AND status='open' AND lapsed_at IS NULL AND lower(content) LIKE '%quiz%'", (actor['id'], actor['id'])).fetchone()
        if s.get('pub.quiz', 0) == 0 and not agreed:
            raise ValueError('The quiz needs announcing or agreeing with Dez first.')
        if s.get('pub.quiz_questions_ready', 0) >= 60:
            raise ValueError('There are already enough questions.')
    if key in ('start_petition', 'start_darts_team'):
        stat = 'terrace.petition' if key == 'start_petition' else 'mo.darts_started'
        if s.get(stat):
            raise ValueError('That has already started.')
    if key in ('sign_petition', 'join_darts'):
        kind = 'petition' if key == 'sign_petition' else 'darts'
        if not s.get('terrace.petition' if kind == 'petition' else 'mo.darts_started'):
            raise ValueError('That has not started yet.')
        if c.execute('SELECT 1 FROM memberships WHERE kind=? AND agent_id=?', (kind, actor['id'])).fetchone():
            raise ValueError('They have already signed up.')
    if key == 'answer_ask':
        ask = c.execute("SELECT * FROM asks WHERE id=? AND to_id=? AND status='open' AND expires_at>?", (a['ask_id'], actor['id'], now.strftime(DUE_FMT))).fetchone()
        if not ask:
            raise ValueError('There is no unanswered request for this character.')
        if a['answer'] == 'yes' and ask['kind'] == 'ask_loan':
            balance = s.get(actor['name'].split()[0].lower() + '.savings')
            if balance is not None and balance < ask['amount']:
                raise ValueError('The lender no longer has enough savings.')
        if a['answer'] == 'yes' and ask['kind'] in ('counter_rent', 'ask_more'):
            limit = e.MIN_RENT if ask['kind'] == 'counter_rent' else e.MAX_SURRENDER
            if (ask['kind'] == 'counter_rent' and ask['amount'] < limit) or (ask['kind'] == 'ask_more' and ask['amount'] > limit):
                raise ValueError('That request exceeds Simon’s authority.')
            negotiation_offer(c, actor, now, 'renewal' if ask['kind'] == 'counter_rent' else 'surrender', True)
        if a['answer'] == 'yes' and ask['kind'] == 'flat_viewing' and ask['amount'] > s.get('chloe.flat_budget', 900):
            raise ValueError('That flat is beyond Chloe’s budget.')
        if a['answer'] == 'yes' and ask['kind'] == 'ask_more_hours' and s.get('jess.shifts', 4) >= 6:
            raise ValueError('Jess already works six shifts.')
    return a


def ask(c, actor, target, key, amount, now):
    aid = c.execute('INSERT INTO asks(kind,from_id,to_id,amount,created_at,expires_at) VALUES (?,?,?,?,?,?)',
                    (key, actor['id'], target['id'], amount, now.strftime(DUE_FMT), (now + timedelta(hours=72)).strftime(DUE_FMT))).lastrowid
    e.schedule(c, target['id'], f'Request {aid} arrived', now)
    return aid


def replace_offer(c, old, amount, terms, now):
    c.execute("UPDATE offers SET status='withdrawn',resolved_at=? WHERE id=? AND status='open'", (now.strftime(DUE_FMT), old['id']))
    return e.offer(c, old['kind'], old['from_id'], old['to_id'], amount, terms, now, max(datetime.strptime(old['expires_at'], DUE_FMT), now + timedelta(days=3)))


def apply(c, actor, key, a, now):
    s = e.stats(c)
    targets = []
    name = actor['name']
    text = f"{name} chose to {key.replace('_', ' ')}."
    def stat(k, v, why):
        e.change(c, k, v, why, now)
    if key in ('give_advice', 'give_formal_warning'):
        from evorium import cases
        conv = c.execute("SELECT id FROM conversations WHERE status='running' AND (agent_a_id=? OR agent_b_id=?) ORDER BY id DESC LIMIT 1", (actor['id'], actor['id'])).fetchone()
        case = cases.outcome_case(c, actor, a['person'], conv['id'] if conv else None)
        text = cases.finish(c, case, 'advice' if key == 'give_advice' else 'formal_warning', now)
    elif key == 'change_pint_price':
        value = s['pub.pint_price_p'] + a['pence']
        text = f"{name} changed the Billet's pint price to £{value / 100:.2f}."
        stat('pub.pint_price_p', value, text)
        e.notice(c, 'pub', f"The Billet's pint now costs £{value / 100:.2f}.", actor['id'], now, a['pence'])
    elif key == 'set_jess_shifts':
        jess = person(c, 'Jess'); targets.append(jess['id'])
        up = a['shifts'] > s['jess.shifts']
        text = f"{name} set Jess's bar shifts to {a['shifts']} evenings a week."
        stat('jess.shifts', a['shifts'], text)
        relationships.adjust(c, jess['id'], actor['id'], 4 if up else -6, 4 if up else -4, text, now)
    elif key in ('announce_quiz', 'start_quiz'):
        stat('pub.quiz', 1 if key == 'announce_quiz' else 2, text)
        text = f"{name} {'announced the return of' if key == 'announce_quiz' else 'started'} the Thursday quiz."
        e.notice(c, 'pub', 'Quiz night returns Thursday 8pm' if key == 'announce_quiz' else 'Weekly quiz every Thursday at 8pm', actor['id'], now)
        if key == 'start_quiz':
            relationships.adjust(c, person(c, 'Tommy')['id'], actor['id'], 0, 6, text, now)
    elif key == 'ring_northgate':
        from evorium import plans
        other = person(c, 'Simon')
        at = (now + timedelta(minutes=30)).replace(second=0, microsecond=0)
        plans.insert(c, {'agent_id': actor['id'], 'action': 'phone', 'person_id': other['id'], 'start_at': at.strftime(DUE_FMT), 'end_at': (at + timedelta(minutes=30)).strftime(DUE_FMT), 'reason': 'Discuss the pub lease.', 'sim_day': at.strftime('%Y-%m-%d')})
        text = f'{name} arranged to ring Simon within the hour.'
    elif key in ('counter_rent', 'ask_more', 'ask_more_hours', 'ask_loan'):
        other = person(c, a['person'] if key == 'ask_loan' else 'Dez' if key == 'ask_more_hours' else 'Simon')
        ask(c, actor, other, key, a.get('amount'), now); targets.append(other['id'])
        text = f"{name} asked {other['name']} about {key.replace('_', ' ')}" + (f" at £{a['amount']:,}." if 'amount' in a else '.')
    elif key.startswith(('accept_', 'refuse_')):
        o = open_offer(c, actor, now, a['offer_id'])
        accepted = key.startswith('accept_')
        c.execute('UPDATE offers SET status=?,resolved_at=? WHERE id=?', ('accepted' if accepted else 'refused', now.strftime(DUE_FMT), o['id']))
        targets.extend([o['from_id']] if o['from_id'] else [])
        text = f"{name} {'accepted' if accepted else 'refused'} the £{o['amount']:,} {o['kind']} offer."
        timeline.record(c, now, 'offer', text, 4, actor['id'], o['from_id'])
        if accepted and o['kind'] == 'surrender':
            stat('raj.savings', s['raj.savings'] + o['amount'], text)
            world._set(c, 'shop_closes_at', (now + timedelta(days=30)).strftime(DUE_FMT))
            warned = c.execute("SELECT 1 FROM actions WHERE key='warn_neighbours' AND status='done'").fetchone()
            if not warned:
                for n in ('Dez', 'Brenda', 'Tommy'):
                    c.execute('INSERT INTO deferred_facts(agent_id,source_id,content,penalty) VALUES (?,?,?,-8)', (person(c, n)['id'], actor['id'], 'Raj accepted the surrender without warning the neighbours.'))
        if not accepted and o['kind'] == 'renewal':
            c.execute("UPDATE agents SET current_goal='Find a new place for the pub.' WHERE id=?", (actor['id'],))
        if not accepted and o['from_id']:
            e.schedule(c, o['from_id'], f"Offer {o['id']} refused", now)
        if accepted and o['kind'] == 'job':
            stat('jess.job_hunting', 0, text)
            stat('jess.shifts', 0, 'Jess took work elsewhere.')
    elif key in ('raise_offer', 'offer_rent_deal'):
        o = negotiation_offer(c, actor, now, 'surrender' if key == 'raise_offer' else 'renewal', True, a.get('offer_id'))
        terms = o['terms'] if key == 'raise_offer' else f"new lease from 25 March 2027, {a['years']} years"
        replace_offer(c, o, a['amount'], terms, now)
        targets.append(o['to_id']); text = f"{name} offered £{a['amount']:,} for the {o['kind']}."
    elif key == 'set_deadline':
        o = open_offer(c, actor, now, a['offer_id'], sender=True)
        expires = (now + timedelta(days=a['days'])).strftime(DUE_FMT)
        c.execute('UPDATE offers SET expires_at=? WHERE id=?', (expires, o['id']))
        text = f"{name} brought the offer deadline forward to {expires}."
        targets.append(o['to_id']); e.schedule(c, o['to_id'], f"Deadline changed for offer {o['id']}", now)
    elif key == 'warn_neighbours':
        text = 'Raj says Northgate own the whole terrace.'
        for n in ('Dez', 'Brenda', 'Tommy'):
            other = person(c, n)
            if other['location'] in (world.PUB, "Patel's News, Ancoats"):
                e.fact(c, other['id'], text, now, source_id=actor['id'])
                relationships.adjust(c, other['id'], actor['id'], 5, 0, text, now)
            else:
                c.execute('INSERT INTO deferred_facts(agent_id,source_id,content) VALUES (?,?,?)', (other['id'], actor['id'], text))
    elif key == 'start_job_hunt':
        stat('jess.job_hunting', 1, text); world._set(c, 'job_hunt_started', now.strftime(DUE_FMT))
    elif key == 'write_quiz_questions':
        count = min(60, s['pub.quiz_questions_ready'] + a['count'])
        text = f"{name} wrote {a['count']} quiz questions; {count} are ready."
        stat('pub.quiz_questions_ready', count, text)
    elif key == 'start_petition':
        text = f"There's a petition about the terrace: {a['text']}"
        stat('terrace.petition', 1, text)
        c.execute("INSERT INTO memberships VALUES ('petition',?)", (actor['id'],))
        for place in ('pub', 'shop'):
            e.notice(c, place, text, actor['id'], now)
    elif key == 'start_darts_team':
        stat('mo.darts_started', 1, text)
        e.notice(c, 'pub', 'Mo is starting a darts team. Six players needed.', actor['id'], now)
    elif key in ('sign_petition', 'join_darts'):
        kind = 'petition' if key == 'sign_petition' else 'darts'
        c.execute('INSERT INTO memberships VALUES (?,?)', (kind, actor['id']))
        statkey = 'terrace.petition' if kind == 'petition' else 'mo.darts_signups'
        stat(statkey, s.get(statkey, 0) + 1, text)
    elif key == 'tell':
        other = person(c, a['person'])
        content = c.execute('SELECT content FROM facts WHERE id=?', (a['fact_id'],)).fetchone()[0]
        e.fact(c, other['id'], content, now, 3, actor['id'])
        text = f"{name} told {other['name']}: {content}"
    elif key == 'answer_ask':
        q = dict(c.execute('SELECT * FROM asks WHERE id=?', (a['ask_id'],)).fetchone())
        yes = a['answer'] == 'yes'; targets.append(q['from_id'])
        c.execute('UPDATE asks SET status=? WHERE id=?', ('accepted' if yes else 'refused', q['id']))
        text = f"{name} {'agreed to' if yes else 'refused'} the request about {q['kind'].replace('_', ' ')}."
        if q['kind'] == 'ask_loan':
            if yes:
                senderkey = name.split()[0].lower() + '.savings'
                if senderkey in s:
                    stat(senderkey, s[senderkey] - q['amount'], text)
                stat('pub.savings', s['pub.savings'] + q['amount'], text)
                c.execute("UPDATE offers SET status='accepted',resolved_at=? WHERE id=?", (now.strftime(DUE_FMT), e.offer(c, 'loan', actor['id'], q['from_id'], q['amount'], 'Neighbour loan; repayment to be agreed', now, now + timedelta(days=30))))
            relationships.adjust(c, q['from_id'], actor['id'], 0, 8 if yes else -3, text, now)
        elif yes and q['kind'] in ('counter_rent', 'ask_more'):
            o = negotiation_offer(c, actor, now, 'renewal' if q['kind'] == 'counter_rent' else 'surrender', True)
            replace_offer(c, o, q['amount'], o['terms'], now)
        elif yes and q['kind'] == 'flat_viewing':
            stat('chloe.flat_found', 1, 'Chloe accepted an affordable flat after a viewing.')
        elif yes and q['kind'] == 'ask_more_hours':
            stat('jess.shifts', min(6, s['jess.shifts'] + 1), text)
            relationships.adjust(c, q['from_id'], actor['id'], 4, 4, text, now)
    return [text, targets]


def propose(c, actor, proposal, now, trigger='reaction', conversation_id=None, transcript=None):
    """Keep every rejection; savepoint prevents a partial effect on unexpected errors."""
    raw = proposal.model_dump() if isinstance(proposal, BaseModel) else dict(proposal)
    key = raw.get('action', '')
    args = raw.get('args', {})
    evidence = raw.get('evidence', [])
    reason = raw.get('reason', raw.get('quote', 'A decision in conversation.'))
    aid = c.execute('INSERT INTO actions(agent_id,key,args_json,reason,status,trigger,evidence,sim_at,conversation_id) VALUES (?,?,?,?,?,?,?,?,?)',
                    (actor['id'], key, json.dumps(args, sort_keys=True), reason, 'rejected', trigger, json.dumps(evidence), now.strftime(DUE_FMT), conversation_id)).lastrowid
    c.execute('SAVEPOINT action_effects')
    try:
        if trigger == 'conversation':
            spoken = SpokenDecision.model_validate(raw)
            quote = spoken.quote.casefold()
            if len(quote.split()) < 6 or not any(quote in t['text'].casefold() and t['speaker_id'] == actor['id'] for t in (transcript or [])):
                raise ValueError('The decision needs six verbatim words spoken by this character.')
            evidence = [r[0] for r in c.execute('SELECT id FROM facts WHERE agent_id=? AND importance>=4 ORDER BY id DESC LIMIT 3', (actor['id'],))]
        else:
            raw = Decision.model_validate(raw).model_dump()
            evidence = raw['evidence']
        if key in ('give_advice', 'give_formal_warning'):
            from evorium import cases
            if trigger != 'conversation':
                raise ValueError('Grace must speak the outcome in conversation.')
            cases.outcome_case(c, actor, args.get('person'), conversation_id)
        args = check(c, actor, key, args, now)
        item = REGISTRY[key]
        status = 'done'
        if item.big:
            if not any(c.execute('SELECT 1 FROM facts WHERE id=? AND agent_id=? AND importance>=4', (fid, actor['id'])).fetchone() for fid in evidence):
                raise ValueError('A major decision needs an important fact this character knows.')
            previous = c.execute("SELECT * FROM actions WHERE agent_id=? AND key=? AND args_json=? AND status='considering' ORDER BY id DESC LIMIT 1", (actor['id'], key, json.dumps(args, sort_keys=True))).fetchone()
            if previous:
                if now < datetime.strptime(previous['sim_at'], DUE_FMT) + timedelta(hours=12):
                    raise ValueError('Sleep on this decision for at least twelve hours.')
            else:
                status = 'considering'
                text = f"{actor['name']} is seriously thinking about {key.replace('_', ' ')}."
                e.schedule(c, actor['id'], f'Reconsider action {aid}', now, 16)
        if status == 'done':
            before = c.execute('SELECT coalesce(max(id),0) FROM stat_changes').fetchone()[0]
            obefore = c.execute('SELECT coalesce(max(id),0) FROM offers').fetchone()[0]
            text, targets = apply(c, actor, key, args, now)
            c.execute('UPDATE stat_changes SET action_id=? WHERE id>?', (aid, before))
            c.execute('UPDATE offers SET source_action_id=? WHERE id>?', (aid, obefore))
            c.execute('UPDATE asks SET action_id=? WHERE action_id IS NULL AND from_id=? AND created_at=?', (aid, actor['id'], now.strftime(DUE_FMT)))
            e.fact(c, actor['id'], text, now, 4 if item.big else 3)
            for target in set(targets) - {actor['id']}:
                e.fact(c, target, text, now)
            if item.witnesses == 'place':
                for other in npc_agents(c):
                    if other['id'] != actor['id'] and other['location'] == actor['location']:
                        e.fact(c, other['id'], text, now, 3)
            if item.big:
                c.execute("UPDATE actions SET status='rejected',result='Superseded by a completed decision.' WHERE agent_id=? AND status='considering'", (actor['id'],))
        c.execute('UPDATE actions SET status=?,result=?,evidence=? WHERE id=?', (status, text, json.dumps(evidence), aid))
        timeline.record(c, now, 'action', text, item.importance, actor['id'], conversation_id=conversation_id)
        goal = raw.get('new_goal')
        if goal and not c.execute("SELECT 1 FROM timeline WHERE kind='goal' AND agent_id=? AND substr(sim_at,1,10)=?", (actor['id'], now.strftime('%Y-%m-%d'))).fetchone():
            old = c.execute('SELECT current_goal FROM agents WHERE id=?', (actor['id'],)).fetchone()[0]
            c.execute('UPDATE agents SET current_goal=? WHERE id=?', (goal, actor['id']))
            timeline.record(c, now, 'goal', f"{actor['name']} now wants to {goal} (previously: {old}).", 2, actor['id'])
        c.execute('RELEASE action_effects')
        emit(text)
    except (ValueError, TypeError, KeyError) as exc:
        c.execute('ROLLBACK TO action_effects'); c.execute('RELEASE action_effects')
        if isinstance(exc, ValidationError):
            first = exc.errors()[0] if exc.errors() else {}
            exc = f"{'.'.join(str(p) for p in first.get('loc', ())) or 'details'}: {first.get('msg', 'invalid')}"
        text = f"{actor['name']} could not {key.replace('_', ' ')}: {exc}"
        c.execute('UPDATE actions SET result=? WHERE id=?', (text, aid))
        emit(text, 'error')
    return dict(c.execute('SELECT * FROM actions WHERE id=?', (aid,)).fetchone())


def candidates(c, actor, now):
    """Offer only actions with at least one currently valid example, never hidden limits."""
    s = e.stats(c)
    result = []
    for item in REGISTRY.values():
        examples = [{}]
        key = item.key
        if key == 'change_pint_price': examples = [{'pence': n} for n in (20, -10)]
        elif key == 'set_jess_shifts': examples = [{'shifts': n} for n in range(2, 7)]
        elif key in ('accept_renewal', 'refuse_renewal', 'accept_surrender', 'refuse_surrender', 'set_deadline', 'raise_offer', 'accept_job', 'refuse_job'):
            examples = [{'offer_id': r['id'], **({'days': 3} if key == 'set_deadline' else {'amount': min(e.MAX_SURRENDER, r['amount'] + 5000)} if key == 'raise_offer' else {})} for r in c.execute("SELECT * FROM offers WHERE status IN ('open','refused','expired')")]
        elif key == 'counter_rent': examples = [{'amount': 3400}]
        elif key == 'ask_more': examples = [{'amount': 55000}]
        elif key == 'offer_rent_deal': examples = [{'amount': 3500, 'years': 3}]
        elif key == 'ask_loan': examples = [{'person': a['name'], 'amount': 1000} for a in npc_agents(c)]
        elif key == 'write_quiz_questions': examples = [{'count': 20}]
        elif key == 'start_petition': examples = [{'text': 'Keep our terrace businesses open'}]
        elif key == 'answer_ask': examples = [{'ask_id': r['id'], 'answer': v} for r in c.execute("SELECT id FROM asks WHERE to_id=? AND status='open'", (actor['id'],)) for v in ('yes', 'no')]
        elif key in ('give_advice', 'give_formal_warning'):
            examples = [{'person': r['name']} for r in c.execute("SELECT a.name FROM cases v JOIN agents a ON a.id=v.subject_id WHERE v.status!='closed'")]
        elif key == 'tell': examples = [{'person': a['name'], 'fact_id': r['id']} for a in npc_agents(c) if a['id'] != actor['id'] for r in c.execute('SELECT id FROM facts WHERE agent_id=? AND importance>=3 ORDER BY id DESC LIMIT 2', (actor['id'],))]
        valid = []
        for args in examples:
            try:
                check(c, actor, key, args, now)
                valid.append(args)
            except (ValueError, TypeError):
                pass
        if valid:
            result.append({'action': key, 'examples': valid[:8], 'args': item.args_schema.model_json_schema(), 'big': item.big})
    return result


def listing(db_path=DEFAULT_DB_PATH, since=None):
    with connect(db_path) as c:
        return [dict(r) for r in c.execute('SELECT * FROM actions WHERE (? IS NULL OR sim_at>=?) ORDER BY id DESC LIMIT 200', (since, since))]
