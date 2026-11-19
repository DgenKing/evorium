"""Offline decisions, ledger, migrations and multi-day consequences."""
import json
import sqlite3
from datetime import datetime, timedelta
import pytest
from evorium import actions as a, economy as e, arcs, backoff, catchup, decide, director, main, memory, models, places, plans, sim, tick, timeline, world
from evorium.db import MIGRATIONS, connect, init_db, npc_agents
from evorium.llm import LLMError
from evorium.seed import seed_agents, seed_events

NOW = datetime(2026, 11, 19, 12)


@pytest.fixture
def saved(tmp_path):
    path = tmp_path / 'm4.sqlite3'
    init_db(path); seed_agents(path); seed_events(path, NOW - timedelta(days=3))
    e.ensure(path, NOW)
    return path


def actor(c, first):
    return a.person(c, first)


def proposal(key, args=None, evidence=None):
    return {'action': key, 'args': args or {}, 'reason': 'I need to make a practical choice.', 'evidence': evidence or []}


def choose(path, first, key, args=None, now=NOW, evidence=None):
    with connect(path) as c:
        c.execute('BEGIN IMMEDIATE')
        who = actor(c, first)
        who.update(location=world.PUB, activity='behind the bar')
        return a.propose(c, who, proposal(key, args, evidence), now)


def seed_offer(path, kind='renewal', amount=3900, now=NOW):
    with connect(path) as c:
        return e.offer(c, kind, actor(c, 'Simon')['id'], actor(c, 'Dez' if kind == 'renewal' else 'Raj')['id'], amount, 'new lease from 25 March 2027', now, now + timedelta(days=28))


def evidence(path, first):
    with connect(path) as c:
        return [c.execute('SELECT id FROM facts WHERE agent_id=? AND importance>=4 LIMIT 1', (actor(c, first)['id'],)).fetchone()[0]]


class Fail:
    def propose(self, *args, **kwargs):
        raise LLMError('Offline service unavailable')


class Script:
    def __init__(self, entries=()):
        self.entries = iter(entries)
        self.calls = []

    def propose(self, aid, messages, schema=None, max_tokens=300):
        self.calls.append((aid, schema, max_tokens, messages))
        if schema is actions.Decision:
            return schema.model_validate(next(self.entries))
        if schema is arcs.Narration:
            return schema(text='The neighbours made their choices. The pub carries on. Life on the terrace has changed.')
        if schema is catchup.Previously:
            return schema(text='Previously in Ancoats, the neighbours made decisions. Some offers changed. The pub carried on. Everyone had something to think about.')
        raise AssertionError(schema)


# Keep the fake client explicit so no fallback ever constructs a real provider.
actions = a


def test_settlement_targets_and_levers():
    values = {k: v[0] for k, v in e.START.items()}
    base = e.week(values)
    high = e.week({**values, 'pub.rent_month': 3900})
    quiz = e.week({**values, 'pub.rent_month': 3900, 'pub.quiz': 2, 'pub.pint_price_p': 480})
    assert 200 <= base['profit'] <= 400
    assert -300 <= high['profit'] <= -100
    assert quiz['profit'] > high['profit'] + 100
    assert e.week({**values, 'jess.shifts': 5})['profit'] < base['profit']
    assert e.week(values, 2)['profit'] < base['profit']


def test_ensure_delivered_seed_offers_are_idempotent(saved):
    with connect(saved) as c:
        c.execute("UPDATE scheduled_events SET delivered=1 WHERE seed_key IN ('northgate-figures','raj-figure')")
    e.ensure(saved, NOW); e.ensure(saved, NOW)
    with connect(saved) as c:
        rows = list(c.execute('SELECT * FROM offers'))
        assert len(rows) == 2
        for o in rows:
            assert datetime.strptime(o['expires_at'], memory.DUE_FMT) - datetime.strptime(o['created_at'], memory.DUE_FMT) == timedelta(days=28 if o['kind'] == 'renewal' else 30)


def test_event_delivery_creates_offer_and_reaction_once(saved):
    tick.deliver_events(NOW, saved); tick.deliver_events(NOW, saved)
    with connect(saved) as c:
        assert c.execute('SELECT count(*) FROM offers').fetchone()[0] == 2
        assert c.execute("SELECT count(*) FROM reactions WHERE reason LIKE 'Offer % arrived'").fetchone()[0] == 2
        assert all(r['created_at'] == NOW.strftime(memory.DUE_FMT) for r in c.execute('SELECT * FROM offers'))


@pytest.mark.parametrize('item', list(a.REGISTRY.values()), ids=lambda item: item.key)
def test_every_action_rejects_non_npc(saved, item):
    with connect(saved) as c:
        who = dict(c.execute("SELECT * FROM agents WHERE kind='player'").fetchone())
        with pytest.raises(ValueError):
            item.check(c, who, {}, NOW)


@pytest.mark.parametrize('key,args', [
    ('change_pint_price', {'pence': 51}), ('change_pint_price', {'pence': 0}),
    ('set_jess_shifts', {'shifts': 7}), ('set_jess_shifts', {'shifts': 4}),
    ('counter_rent', {'amount': 4000}), ('ask_more', {'amount': 45000}),
    ('offer_rent_deal', {'amount': 3299, 'years': 3}),
    ('raise_offer', {'offer_id': 1, 'amount': 60001}),
    ('set_deadline', {'offer_id': 1, 'days': 15}), ('write_quiz_questions', {'count': 21}),
    ('start_petition', {'text': 'x' * 121}), ('ask_loan', {'person': 'Raj', 'amount': 10001}),
    ('answer_ask', {'ask_id': 1, 'answer': 'maybe'}), ('wait', {'invented': 1}),
])
def test_argument_bounds(saved, key, args):
    first = a.REGISTRY[key].who
    first = 'Tommy' if first == 'any' else first
    assert choose(saved, first, key, args)['status'] == 'rejected'


def test_wrong_actor_place_time_and_weekly_cooldown(saved):
    assert choose(saved, 'Raj', 'change_pint_price', {'pence': 20})['status'] == 'rejected'
    with connect(saved) as c:
        dez = actor(c, 'Dez')
        dez['location'] = 'Home'
        with pytest.raises(ValueError, match='pub'):
            a.check(c, dez, 'change_pint_price', {'pence': 20}, NOW)
    assert choose(saved, 'Dez', 'change_pint_price', {'pence': 20}, now=NOW.replace(hour=2))['status'] == 'rejected'
    assert choose(saved, 'Dez', 'change_pint_price', {'pence': 20})['status'] == 'done'
    assert choose(saved, 'Dez', 'change_pint_price', {'pence': 20}, now=NOW + timedelta(days=1))['status'] == 'rejected'
    assert choose(saved, 'Dez', 'change_pint_price', {'pence': 20}, now=NOW + timedelta(days=7))['status'] == 'done'


def test_shifts_facts_relationship_and_timeline(saved):
    with connect(saved) as c:
        before = relationships(c, 'Jess', 'Dez')
    row = choose(saved, 'Dez', 'set_jess_shifts', {'shifts': 2})
    assert row['status'] == 'done'
    with connect(saved) as c:
        after = relationships(c, 'Jess', 'Dez')
        assert after['trust'] == before['trust'] - 6
        assert after['warmth'] == before['warmth'] - 4
        assert e.stats(c)['jess.shifts'] == 2
        assert c.execute("SELECT count(*) FROM facts WHERE content=?", (row['result'],)).fetchone()[0] >= 2
        assert c.execute("SELECT 1 FROM timeline WHERE kind='action' AND text=?", (row['result'],)).fetchone()
        assert c.execute('SELECT action_id FROM stat_changes ORDER BY id DESC LIMIT 1').fetchone()[0] == row['id']


def relationships(c, one, two):
    from evorium.relationships import get
    return get(c, actor(c, one)['id'], actor(c, two)['id'])


def test_big_action_evidence_sleep_and_daily_limit(saved):
    oid = seed_offer(saved, 'surrender', 45000)
    assert choose(saved, 'Raj', 'accept_surrender', {'offer_id': oid})['status'] == 'rejected'
    ev = evidence(saved, 'Raj')
    assert choose(saved, 'Raj', 'accept_surrender', {'offer_id': oid}, evidence=ev)['status'] == 'considering'
    assert choose(saved, 'Raj', 'accept_surrender', {'offer_id': oid}, now=NOW + timedelta(hours=11), evidence=ev)['status'] == 'rejected'
    # Raj is asleep at midnight: reconsider next morning instead.
    later = NOW + timedelta(days=1)
    assert choose(saved, 'Raj', 'accept_surrender', {'offer_id': oid}, now=later, evidence=ev)['status'] == 'done'
    assert choose(saved, 'Raj', 'warn_neighbours', now=later)['status'] == 'rejected'
    assert e.read(saved)['raj.savings'] == 63000
    assert e.read(saved)['shop.open'] == 1
    e.maintain(later + timedelta(days=30), saved)
    assert e.read(saved)['shop.open'] == 0
    with connect(saved) as c:
        raj = actor(c, 'Raj')
    assert world.whereabouts(raj, later + timedelta(days=30), saved)[0] == world.home_location(raj['name'])
    assert not places.is_open('shop', NOW, e.read(saved))


def test_world_limit_two_big_actions(saved):
    renew = seed_offer(saved)
    surrender = seed_offer(saved, 'surrender', 45000)
    for first, key, args in [('Raj', 'refuse_surrender', {'offer_id': surrender}), ('Dez', 'accept_renewal', {'offer_id': renew}), ('Jess', 'start_job_hunt', {})]:
        assert choose(saved, first, key, args, evidence=evidence(saved, first))['status'] == 'considering'
    tomorrow = NOW + timedelta(days=1)
    assert choose(saved, 'Raj', 'refuse_surrender', {'offer_id': surrender}, tomorrow, evidence(saved, 'Raj'))['status'] == 'done'
    assert choose(saved, 'Dez', 'accept_renewal', {'offer_id': renew}, tomorrow, evidence(saved, 'Dez'))['status'] == 'done'
    assert choose(saved, 'Jess', 'start_job_hunt', now=tomorrow, evidence=evidence(saved, 'Jess'))['status'] == 'rejected'


def test_quiz_petition_darts_and_limits(saved):
    assert choose(saved, 'Dez', 'start_quiz')['status'] == 'rejected'
    assert choose(saved, 'Dez', 'announce_quiz')['status'] == 'done'
    for day in range(2):
        assert choose(saved, 'Tommy', 'write_quiz_questions', {'count': 20}, NOW + timedelta(days=day))['status'] == 'done'
    assert choose(saved, 'Dez', 'start_quiz', now=NOW + timedelta(days=2))['status'] == 'done'
    assert e.read(saved)['pub.quiz'] == 2
    assert choose(saved, 'Brenda', 'start_petition', {'text': 'Save our terrace'})['status'] == 'done'
    assert choose(saved, 'Chloe', 'sign_petition')['status'] == 'done'
    assert choose(saved, 'Chloe', 'sign_petition', now=NOW + timedelta(days=1))['status'] == 'rejected'
    assert choose(saved, 'Mohammed', 'start_darts_team')['status'] == 'done'
    assert choose(saved, 'Raj', 'join_darts')['status'] == 'done'
    values = e.read(saved)
    assert values['terrace.petition'] == 2 and values['mo.darts_signups'] == 1
    thursday = NOW.replace(hour=20)
    for first in ('Tommy', 'Brenda', 'Chloe'):
        with connect(saved) as c:
            name = actor(c, first)['name']
        assert world.routine(name, thursday, values)[0] == world.PUB
    assert world.routine('Jess Hartley', thursday, values)[1] == 'working the bar'
    assert world.routine('Jess Hartley', NOW.replace(day=23, hour=20), values)[1] != 'working the bar'


@pytest.mark.parametrize('speaker,quote,expected', [
    ('Dez', 'I will put the pint price up today', 'done'),
    ('Raj', 'I will put the pint price up today', 'rejected'),
    ('Dez', 'I have decided to raise all the prices', 'rejected'),
    ('Dez', 'put the pint price', 'rejected'),
])
def test_conversation_quote_must_be_verbatim_and_speakers_own(saved, speaker, quote, expected):
    with connect(saved) as c:
        dez = actor(c, 'Dez'); dez['location'] = world.PUB
        cid = c.execute("INSERT INTO conversations(location,status) VALUES ('pub','completed')").lastrowid
        c.execute("INSERT INTO messages(conversation_id,speaker_id,text,rationale,sim_time) VALUES (?,?,?,'reason','now')", (cid, actor(c, speaker)['id'], 'I will put the pint price up today.'))
        ext = models.Extraction.model_validate({'summary': 'Dez and Raj discussed the pint price.', 'per_agent': {'Dez Whitworth': {'decision': {'action': 'change_pint_price', 'args': {'pence': 20}, 'quote': quote}}}})
        c.execute('UPDATE agents SET location=? WHERE id=?', (world.PUB, dez['id']))
        memory.store_extraction(c, cid, {'Dez Whitworth': dez, 'Raj Patel': actor(c, 'Raj')}, ext, NOW)
        assert c.execute('SELECT status FROM actions ORDER BY id DESC LIMIT 1').fetchone()[0] == expected


def test_notices_once_and_price_relationship_next_visit(saved):
    choose(saved, 'Dez', 'change_pint_price', {'pence': 20})
    with connect(saved) as c:
        tommy = actor(c, 'Tommy'); tommy['location'] = world.PUB
        before = relationships(c, 'Tommy', 'Dez')['warmth']
        e.observe(c, tommy, NOW)
        e.observe(c, tommy, NOW)
        assert c.execute("SELECT count(*) FROM facts WHERE agent_id=? AND content LIKE 'The Billet%pint now%';", (tommy['id'],)).fetchone()[0] == 1
        assert relationships(c, 'Tommy', 'Dez')['warmth'] == before - 2


def test_offer_expiry_facts_and_asks(saved):
    oid = seed_offer(saved)
    assert choose(saved, 'Dez', 'counter_rent', {'amount': 3400})['status'] == 'done'
    e.maintain(NOW + timedelta(days=4), saved)
    with connect(saved) as c:
        assert c.execute('SELECT status FROM asks').fetchone()[0] == 'expired'
        assert c.execute("SELECT 1 FROM facts WHERE content LIKE '%hasn''t replied%'").fetchone()
    e.maintain(NOW + timedelta(days=29), saved)
    with connect(saved) as c:
        assert c.execute('SELECT status FROM offers WHERE id=?', (oid,)).fetchone()[0] == 'expired'
        assert c.execute("SELECT count(*) FROM facts WHERE content LIKE '%offer expired%'").fetchone()[0] == 2
        assert c.execute("SELECT 1 FROM timeline WHERE kind='offer' AND importance=4 AND text LIKE '%expired%'").fetchone()


def test_simon_limits_answer_and_replacement(saved):
    oid = seed_offer(saved)
    assert choose(saved, 'Dez', 'counter_rent', {'amount': 2500})['status'] == 'done'
    with connect(saved) as c:
        qid = c.execute('SELECT id FROM asks').fetchone()[0]
    assert choose(saved, 'Simon', 'answer_ask', {'ask_id': qid, 'answer': 'yes'})['status'] == 'rejected'
    assert choose(saved, 'Simon', 'offer_rent_deal', {'amount': 3500, 'years': 3})['status'] == 'done'
    with connect(saved) as c:
        assert c.execute('SELECT status FROM offers WHERE id=?', (oid,)).fetchone()[0] == 'withdrawn'
        assert c.execute("SELECT amount FROM offers WHERE status='open'").fetchone()[0] == 3500


def test_loan_and_hours_answers(saved):
    assert choose(saved, 'Dez', 'ask_loan', {'person': 'Raj Patel', 'amount': 1000})['status'] == 'done'
    with connect(saved) as c:
        qid = c.execute('SELECT id FROM asks').fetchone()[0]
        before = relationships(c, 'Dez', 'Raj')['warmth']
    assert choose(saved, 'Raj', 'answer_ask', {'ask_id': qid, 'answer': 'yes'})['status'] == 'done'
    assert e.read(saved)['pub.savings'] == 7000
    assert e.read(saved)['raj.savings'] == 17000
    with connect(saved) as c:
        assert relationships(c, 'Dez', 'Raj')['warmth'] == before + 8
    assert choose(saved, 'Jess', 'ask_more_hours')['status'] == 'done'
    with connect(saved) as c:
        qid = c.execute('SELECT max(id) FROM asks').fetchone()[0]
    assert choose(saved, 'Dez', 'answer_ask', {'ask_id': qid, 'answer': 'yes'}, NOW + timedelta(days=1))['status'] == 'done'
    assert e.read(saved)['jess.shifts'] == 5


def test_tell_separate_limit_and_warning(saved):
    assert choose(saved, 'Raj', 'warn_neighbours')['status'] == 'done'
    ev = evidence(saved, 'Raj')[0]
    assert choose(saved, 'Raj', 'tell', {'person': 'Dez', 'fact_id': ev})['status'] == 'done'
    assert choose(saved, 'Raj', 'tell', {'person': 'Tommy', 'fact_id': ev})['status'] == 'rejected'
    with connect(saved) as c:
        assert c.execute("SELECT 1 FROM facts WHERE source='told' AND source_agent_id=?", (actor(c, 'Raj')['id'],)).fetchone()


def test_reaction_budget_postpones_and_urgent_second_call(saved):
    with connect(saved) as c:
        for i in range(14):
            e.schedule(c, actor(c, 'Dez')['id'], f'News {i}', NOW, 1)
    client = Script([proposal('wait')] * 20)
    assert decide.run(client, NOW + timedelta(hours=2), saved) == 1
    with connect(saved) as c:
        assert c.execute("SELECT count(*) FROM reactions WHERE status='pending' AND due_at LIKE '2026-11-20%'").fetchone()[0] == 13
    oid = seed_offer(saved, now=NOW - timedelta(days=27))
    with connect(saved) as c:
        e.schedule(c, actor(c, 'Dez')['id'], 'Urgent expiry', NOW, 1)
    assert decide.run(client, NOW + timedelta(hours=3), saved) == 1
    with connect(saved) as c:
        for i in range(12):
            c.execute("INSERT INTO reactions(agent_id,reason,due_at,status,called_at) VALUES (?,?,?,'called',?)", (actor(c, 'Tommy')['id'], f'Spent {i}', NOW.strftime(memory.DUE_FMT), NOW.strftime(memory.DUE_FMT)))
        e.schedule(c, actor(c, 'Raj')['id'], 'New request', NOW, 1)
    assert decide.run(client, NOW + timedelta(hours=4), saved) == 0


@pytest.mark.parametrize('outcome', ['renewed', 'pub_closed', 'pub_bust'])
def test_northgate_outcomes_and_narration_fallback(saved, outcome):
    if outcome == 'renewed':
        renew = seed_offer(saved); surrender = seed_offer(saved, 'surrender', 45000)
        with connect(saved) as c:
            c.execute("UPDATE offers SET status=CASE WHEN kind='renewal' THEN 'accepted' ELSE 'refused' END")
        now = NOW
    elif outcome == 'pub_closed':
        now = datetime(2027, 3, 25, 12)
    else:
        now = datetime(2026, 11, 22, 23, 59)
        with connect(saved) as c:
            e.change(c, 'pub.savings', -3000, 'No money left.', NOW)
    e.maintain(now, saved, Fail())
    with connect(saved) as c:
        arc = c.execute("SELECT * FROM arcs WHERE key='northgate'").fetchone()
        assert arc['outcome'] == outcome and arc['summary']
        assert c.execute("SELECT count(*) FROM timeline WHERE kind='arc' AND importance=5").fetchone()[0] == 1
        assert c.execute('SELECT count(*) FROM facts WHERE content=?', (arc['summary'],)).fetchone()[0] == 8
        if outcome != 'renewed':
            assert e.stats(c)['pub.closed'] == 1
    e.maintain(now, saved, Fail())


def test_rent_starts_at_lease_not_acceptance(saved):
    oid = seed_offer(saved)
    with connect(saved) as c:
        c.execute("UPDATE offers SET status='accepted' WHERE id=?", (oid,))
    e.maintain(NOW + timedelta(days=1), saved)
    assert e.read(saved)['pub.rent_month'] == 2400
    e.maintain(datetime(2027, 3, 25, 12), saved)
    assert e.read(saved)['pub.rent_month'] == 3900


def test_catchup_cache_checkpoint_and_failure(saved):
    catchup.seen(NOW, saved)
    with connect(saved) as c:
        for i in range(3):
            timeline.record(c, NOW + timedelta(hours=3), 'action', f'The neighbours made decision {i}.', 3)
        me = c.execute("SELECT name FROM agents WHERE kind='player'").fetchone()[0]
        e.fact(c, actor(c, 'Raj')['id'], f'{me} visited the shop.', NOW)
    client = Script()
    data = catchup.get(client, NOW + timedelta(hours=4), saved)
    again = catchup.get(client, NOW + timedelta(hours=4), saved)
    assert data['gap_hours'] == 4 and data['gossip']
    assert data['paragraph'] == again['paragraph'] and len(client.calls) == 1
    catchup.seen(NOW + timedelta(hours=4), saved)
    assert not catchup.get(client, NOW + timedelta(hours=5), saved)['items']
    with connect(saved) as c:
        c.execute('DELETE FROM catchup_cache')
        for i in range(3):
            timeline.record(c, NOW + timedelta(hours=6), 'action', f'Later decision {i}.', 3)
    fallback = catchup.get(Fail(), NOW + timedelta(hours=7), saved)
    assert fallback['items'] and not fallback['paragraph']


def test_director_cannot_act_and_pending_is_not_stalled(saved):
    oid = seed_offer(saved)
    assert not director.stall_report(NOW + timedelta(days=3), saved)['stalled']
    for content in ('Simon Ferris accepts the offer.', 'Dez Whitworth closes the pub.', 'Simon Ferris offers rent at 3500 pounds.'):
        with pytest.raises(ValueError):
            director.validate({'type': 'letter', 'for': 'Dez Whitworth', 'content': content, 'in_hours': 1, 'rationale': 'Move things on'}, NOW, saved)


def test_migrations_from_v9_keep_all_history(tmp_path):
    path = tmp_path / 'old.sqlite3'
    c = sqlite3.connect(path)
    for migration in MIGRATIONS[:9]:
        for statement in migration:
            c.execute(statement)
    c.execute('PRAGMA user_version=9'); c.commit(); c.close()
    seed_agents(path); seed_events(path, NOW)
    with connect(path) as c:
        c.execute("UPDATE scheduled_events SET delivered=1")
        c.execute("INSERT INTO conversations(location,status,summary) VALUES ('pub','completed','Saved history')")
        c.execute("INSERT INTO messages(conversation_id,speaker_id,text,rationale,sim_time) VALUES (1,1,'Saved words','reason','now')")
        old = {table: c.execute('SELECT count(*) FROM ' + table).fetchone()[0] for table in ('agents', 'conversations', 'messages', 'facts', 'scheduled_events')}
    init_db(path); e.ensure(path, NOW); init_db(path); e.ensure(path, NOW)
    with connect(path) as c:
        for table, count in old.items():
            assert c.execute('SELECT count(*) FROM ' + table).fetchone()[0] >= count
        assert c.execute('PRAGMA user_version').fetchone()[0] == 13
        assert c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert c.execute('SELECT count(*) FROM offers').fetchone()[0] == 2


def test_pause_excludes_empty_failures_and_preserves_non_model_work(saved, monkeypatch):
    monkeypatch.setattr(world, 'now', lambda *args: NOW)
    with connect(saved) as c:
        cid = c.execute("INSERT INTO conversations(location,status) VALUES ('pub','failed')").lastrowid
        timeline.record(c, NOW, 'conversation', 'No words', 2, conversation_id=cid)
    assert sim.latest_conversation_id(saved) is None
    assert not timeline.entries(saved)
    backoff.failed(LLMError('Connection unavailable'))
    with pytest.raises(LLMError):
        sim.run_conversation(Fail(), 1, 3, db_path=saved)
    # Tick routines and seed letters still run while no call is allowed.
    tick.update_routines(NOW, saved); tick.deliver_events(NOW, saved)
    with connect(saved) as c:
        assert c.execute('SELECT count(*) FROM conversations').fetchone()[0] == 1
        assert c.execute('SELECT count(*) FROM offers').fetchone()[0] == 2
    first = backoff.until()
    backoff.failed(LLMError('Still unavailable'))
    assert backoff.until() == first
    backoff.succeeded(); assert backoff.until() is None


def test_scripted_northgate_story_over_several_days(saved):
    renewal = seed_offer(saved)
    surrender = seed_offer(saved, 'surrender', 45000)
    script = Script([
        proposal('refuse_surrender', {'offer_id': surrender}, evidence(saved, 'Raj')),
        proposal('refuse_surrender', {'offer_id': surrender}, evidence(saved, 'Raj')),
        proposal('raise_offer', {'offer_id': surrender, 'amount': 55000}),
        # The raised offer's id is inserted below before these choices.
    ])
    def step(first, now):
        with connect(saved) as c:
            who = actor(c, first); who['location'] = world.PUB
            choice = script.propose(who['id'], [], schema=a.Decision, max_tokens=350)
            result = a.propose(c, who, choice, now)
            assert c.execute('SELECT 1 FROM timeline WHERE kind=\'action\' AND text=?', (result['result'],)).fetchone()
            return result
    assert step('Raj', NOW)['status'] == 'considering'
    assert step('Raj', NOW + timedelta(days=1))['status'] == 'done'
    assert step('Simon', NOW + timedelta(days=2))['status'] == 'done'
    with connect(saved) as c:
        raised = c.execute("SELECT id FROM offers WHERE kind='surrender' AND status='open'").fetchone()[0]
        assert c.execute('SELECT amount FROM offers WHERE id=?', (raised,)).fetchone()[0] == 55000
    script.entries = iter([
        proposal('accept_surrender', {'offer_id': raised}, evidence(saved, 'Raj')),
        proposal('accept_surrender', {'offer_id': raised}, evidence(saved, 'Raj')),
        proposal('counter_rent', {'amount': 3400}),
        proposal('offer_rent_deal', {'amount': 3500, 'years': 3}),
    ])
    assert step('Raj', NOW + timedelta(days=2))['status'] == 'considering'
    assert step('Raj', NOW + timedelta(days=3))['status'] == 'done'
    assert step('Dez', NOW + timedelta(days=3))['status'] == 'done'
    assert step('Simon', NOW + timedelta(days=4))['status'] == 'done'
    with connect(saved) as c:
        deal = c.execute("SELECT id FROM offers WHERE kind='renewal' AND status='open'").fetchone()[0]
    script.entries = iter([proposal('accept_renewal', {'offer_id': deal}, evidence(saved, 'Dez'))] * 2)
    assert step('Dez', NOW + timedelta(days=4))['status'] == 'considering'
    assert step('Dez', NOW + timedelta(days=5))['status'] == 'done'
    e.maintain(NOW + timedelta(days=5), saved, script)
    with connect(saved) as c:
        arc = c.execute("SELECT * FROM arcs WHERE key='northgate'").fetchone()
        assert arc['outcome'] == 'renewed' and '3,500' in arc['summary']
        assert c.execute("SELECT 1 FROM facts WHERE content LIKE '%accepted%55,000%'").fetchone()
        assert c.execute("SELECT 1 FROM facts WHERE content LIKE '%accepted%3,500%'").fetchone()
        assert e.stats(c)['pub.rent_month'] == 2400


def test_job_hunt_and_choice(saved):
    ev = evidence(saved, 'Jess')
    assert choose(saved, 'Jess', 'start_job_hunt', evidence=ev)['status'] == 'considering'
    tomorrow = NOW + timedelta(days=1)
    assert choose(saved, 'Jess', 'start_job_hunt', now=tomorrow, evidence=ev)['status'] == 'done'
    e.maintain(tomorrow + timedelta(days=14), saved)
    with connect(saved) as c:
        job = c.execute("SELECT * FROM offers WHERE kind='job'").fetchone()
        assert job
    at = tomorrow + timedelta(days=14)
    assert choose(saved, 'Jess', 'accept_job', {'offer_id': job['id']}, at, ev)['status'] == 'considering'
    assert choose(saved, 'Jess', 'accept_job', {'offer_id': job['id']}, at + timedelta(days=1), ev)['status'] == 'done'
    assert e.read(saved)['jess.shifts'] == 0


def test_ring_deadline_ask_more_and_refuse_renewal(saved):
    oid = seed_offer(saved)
    assert choose(saved, 'Simon', 'set_deadline', {'offer_id': oid, 'days': 7})['status'] == 'done'
    assert choose(saved, 'Dez', 'ring_northgate')['status'] == 'done'
    with connect(saved) as c:
        assert c.execute("SELECT 1 FROM plans WHERE action='phone' AND person_id=?", (actor(c, 'Simon')['id'],)).fetchone()
    later = NOW + timedelta(days=1)
    ev = evidence(saved, 'Dez')
    assert choose(saved, 'Dez', 'refuse_renewal', {'offer_id': oid}, later, ev)['status'] == 'considering'
    assert choose(saved, 'Dez', 'refuse_renewal', {'offer_id': oid}, later + timedelta(days=1), ev)['status'] == 'done'
    assert choose(saved, 'Dez', 'counter_rent', {'amount': 3400}, later + timedelta(days=2))['status'] == 'done'
    surrender = seed_offer(saved, 'surrender', 45000)
    assert choose(saved, 'Raj', 'ask_more', {'amount': 90000})['status'] == 'done'
    with connect(saved) as c:
        qid = c.execute("SELECT id FROM asks WHERE kind='ask_more'").fetchone()[0]
    assert choose(saved, 'Simon', 'answer_ask', {'ask_id': qid, 'answer': 'yes'}, later)['status'] == 'rejected'
    assert choose(saved, 'Simon', 'answer_ask', {'ask_id': qid, 'answer': 'no'}, later)['status'] == 'done'


def test_visibility_and_menu_do_not_expose_simon_limits(saved):
    seed_offer(saved)
    with connect(saved) as c:
        for who in npc_agents(c):
            situation = e.situation(c, who, NOW)
            menu = a.candidates(c, who, NOW)
            assert len(situation) <= 6
            if who['name'].startswith('Simon'):
                assert '60,000' in ' '.join(situation) and '3,300' in ' '.join(situation)
            else:
                assert '60,000' not in json.dumps(situation) and '3300' not in json.dumps(menu)
            if not who['name'].startswith('Dez'):
                assert 'pub savings' not in json.dumps(situation)


def test_backoff_delays_and_recovery(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(backoff.time, 'time', lambda: clock[0])
    for minutes in (1, 2, 4, 8, 15, 15):
        backoff.failed(LLMError('No reply'))
        assert backoff._until - clock[0] == minutes * 60
        clock[0] = backoff._until + 1
    backoff.succeeded(); assert not backoff.paused()
    backoff.failed(LLMError('Local budget cap reached')); assert not backoff.paused()
    backoff.failed(LLMError('DeepSeek account balance exhausted')); assert not backoff.paused()


def test_follow_on_templates_and_resolution(saved):
    with connect(saved) as c:
        c.execute("UPDATE arcs SET status='resolved',resolved_at=?,outcome='renewed',summary='The pub remains open.'", (NOW.strftime(memory.DUE_FMT),))
    assert not arcs.start_next(NOW + timedelta(days=1), saved)
    assert arcs.start_next(NOW + timedelta(days=2), saved)
    with connect(saved) as c:
        e.change(c, 'mo.darts_signups', 6, 'Six neighbours signed up.', NOW + timedelta(days=3))
    arcs.maintain(NOW + timedelta(days=3), saved)
    assert arcs.start_next(NOW + timedelta(days=5), saved)
    with connect(saved) as c:
        invitation = c.execute("SELECT id FROM asks WHERE kind='flat_viewing'").fetchone()[0]
    assert choose(saved, 'Chloe', 'answer_ask', {'ask_id': invitation, 'answer': 'yes'}, NOW + timedelta(days=6))['status'] == 'done'
    arcs.maintain(NOW + timedelta(days=6), saved)
    with connect(saved) as c:
        assert c.execute("SELECT outcome FROM arcs WHERE key='chloe_flat'").fetchone()[0] == 'succeeded'


def test_tick_pause_runs_bookkeeping_without_conversations(saved, monkeypatch):
    monkeypatch.setattr(main, 'DEFAULT_DB_PATH', saved)
    monkeypatch.setattr(world, 'now', lambda *args: NOW)
    class Once:
        stopped = False
        def is_set(self): return self.stopped
        def wait(self, *args): self.stopped = True
    monkeypatch.setattr(main, '_state', {**main._state, 'auto': True, 'stop': Once()})
    def forbidden(*args, **kwargs):
        raise AssertionError('No model client should be needed during the pause')
    monkeypatch.setattr(main, 'DeepSeekClient', forbidden)
    backoff.failed(LLMError('Service unavailable'))
    main._tick_loop()
    with connect(saved) as c:
        assert c.execute('SELECT count(*) FROM conversations').fetchone()[0] == 0
        assert c.execute('SELECT count(*) FROM offers').fetchone()[0] == 2
        assert c.execute("SELECT 1 FROM agents WHERE activity='behind the bar'").fetchone()


def test_pending_raised_offer_does_not_resolve_arc(saved):
    renew = seed_offer(saved); original = seed_offer(saved, 'surrender', 45000)
    with connect(saved) as c:
        c.execute("UPDATE offers SET status='accepted' WHERE id=?", (renew,))
        c.execute("UPDATE offers SET status='refused',resolved_at=? WHERE id=?", (NOW.strftime(memory.DUE_FMT), original))
        e.offer(c, 'surrender', actor(c, 'Simon')['id'], actor(c, 'Raj')['id'], 55000, 'A fresh offer', NOW, NOW + timedelta(days=7))
    arcs.maintain(NOW, saved)
    with connect(saved) as c:
        assert c.execute("SELECT status FROM arcs WHERE key='northgate'").fetchone()[0] == 'active'


def test_settlements_are_idempotent_and_cross_lease_correctly(saved):
    oid = seed_offer(saved)
    lease = datetime(2027, 3, 25)
    with connect(saved) as c:
        c.execute("UPDATE offers SET status='accepted' WHERE id=?", (oid,))
        world._set(c, 'settlement_cursor', '2027-03-20 12:00')
    e.maintain(datetime(2027, 3, 29, 12), saved)
    with connect(saved) as c:
        rows = list(c.execute("SELECT * FROM stat_changes WHERE key='pub.savings' ORDER BY id"))
        assert len(rows) == 2
        assert rows[0]['new'] - rows[0]['old'] > 200
        assert rows[1]['new'] - rows[1]['old'] < -100
    e.maintain(datetime(2027, 3, 29, 12), saved)
    with connect(saved) as c:
        assert c.execute("SELECT count(*) FROM stat_changes WHERE key='pub.savings'").fetchone()[0] == 2


def test_new_api_payloads_use_existing_polling(saved, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(main, 'DEFAULT_DB_PATH', saved)
    monkeypatch.setattr(main, 'DASHBOARD_PASSWORD', '')
    monkeypatch.setattr(world, 'now', lambda *args: NOW)
    choose(saved, 'Dez', 'change_pint_price', {'pence': 20})
    client = TestClient(main.app)
    assert client.get('/world/ledger').json()['stats']['pub.pint_price_p'] == 480
    assert client.get('/agents').json()[0]['today_action']
    assert client.get('/usage').json()['ledger']['notices']
    assert client.get('/actions?since=2026-11-19%2000:00').json()
    assert client.get('/catchup').status_code == 200
    assert client.post('/catchup/seen').json()['seen']
    assert client.get('/timeline?kind=action').json()['days']


# ---- Review fixes (19 Nov) ---------------------------------------------------

def test_note_taker_menu_never_shows_simons_limits(saved):
    from evorium.prompts import build_extraction_messages
    with connect(saved) as c:
        dez, simon, raj = actor(c, 'Dez'), actor(c, 'Simon'), actor(c, 'Raj')
    for x, y in ((dez, simon), (simon, raj)):
        text = build_extraction_messages(x, y, [{'speaker_name': x['name'], 'text': 'hi'}], [], [], [], 'now')[0]['content']
        assert '60000' not in text and '3300' not in text
    text = build_extraction_messages(dez, raj, [{'speaker_name': dez['name'], 'text': 'hi'}], [], [], [], 'now')[0]['content']
    assert 'change_pint_price' in text and 'accept_surrender' in text and 'raise_offer' not in text


def test_gossip_matches_the_player_name_as_a_whole_word(saved):
    with connect(saved) as c:
        c.execute("UPDATE agents SET name='Rob', last_seen_at=? WHERE kind='player'", ((NOW - timedelta(hours=5)).strftime(memory.DUE_FMT),))
        world._set(c, 'catchup_fact_checkpoint', c.execute('SELECT max(id) FROM facts').fetchone()[0])
        dez = actor(c, 'Dez')['id']
        for text in ('The real problem is the rent.', 'Rob was asking about the lease.'):
            c.execute("INSERT INTO facts(agent_id,subject,content,source,importance) VALUES (?,'x',?,'observed',4)", (dez, text))
    gossip = catchup.get(None, NOW, saved)['gossip']
    assert [g['content'] for g in gossip] == ['Rob was asking about the lease.']


def test_invalid_model_reply_does_not_pause_the_world(saved):
    import httpx
    from evorium.llm import DeepSeekClient, InvalidProposal, Settings
    bad = httpx.Response(200, json={'choices': [{'message': {'content': 'not json'}, 'finish_reason': 'stop'}],
                                    'usage': {'prompt_tokens': 10, 'completion_tokens': 2}})
    with httpx.Client(transport=httpx.MockTransport(lambda r: bad)) as http:
        with pytest.raises(InvalidProposal):
            DeepSeekClient(saved, Settings('fake-test-key'), http).propose(1, [{'role': 'user', 'content': 'x'}])
    assert not backoff.paused()
    down = httpx.Response(503, json={})
    with httpx.Client(transport=httpx.MockTransport(lambda r: down)) as http:
        with pytest.raises(LLMError):
            DeepSeekClient(saved, Settings('fake-test-key'), http).propose(1, [{'role': 'user', 'content': 'x'}])
    assert backoff.paused()


def test_rejection_reason_is_one_readable_line(saved):
    row = choose(saved, 'Dez', 'change_pint_price', {'pence': 99})
    assert row['status'] == 'rejected'
    assert '\n' not in row['result'] and 'pence' in row['result'] and 'errors.pydantic.dev' not in row['result']
