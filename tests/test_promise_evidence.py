"""Offline evidence, attribution, clocks, lapses and false-claim regressions."""
import asyncio
import json
import random
import sqlite3
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from evorium import actions, catchup, economy, main, memory, plans, player, prompts, relationships, tick, world
from evorium.db import MIGRATIONS, connect, init_db
from evorium.models import Extraction, PromiseCheck
from evorium.promise_evidence import evidence_for, had_chance, progress, validate_target
from evorium.seed import seed_agents

START = datetime(2026, 11, 23, 12)
DUE = START + timedelta(hours=4)
FMT = memory.DUE_FMT
CHECKABLE = ['action', 'visit', 'talk', 'tell', 'make', 'pay', 'conditional']


class NoModel:
    def propose(self, *args, **kwargs):
        raise AssertionError('Promise bookkeeping must never call a provider.')


@pytest.fixture
def db(tmp_path):
    path = tmp_path / 'evidence.sqlite3'
    init_db(path)
    seed_agents(path)
    economy.ensure(path, START)
    return path


def promise(c, kind, start=START, due=DUE):
    fid = c.execute("SELECT id FROM facts WHERE agent_id=3 ORDER BY id LIMIT 1").fetchone()[0]
    targets = {
        'action': {'key': 'write_quiz_questions', 'args': {'count': 20}},
        'visit': {'place': 'pub'},
        'talk': {'person': 'Dez Whitworth'},
        'tell': {'person': 'Dez Whitworth', 'fact_id': fid},
        'make': {'item': 'quiz_questions', 'count': 40},
        'vague': {},
        'conditional': {'condition': 'If Dez announces the quiz',
                        'trigger': {'person': 'Dez Whitworth', 'kind': 'action', 'target': {'key': 'announce_quiz', 'args': {}}},
                        'promise': {'kind': 'visit', 'target': {'place': 'pub'}}},
    }
    if kind == 'pay':
        q = c.execute("INSERT INTO asks(kind,from_id,to_id,amount,created_at,expires_at) VALUES ('ask_loan',1,3,500,?,?)",
                      (start.strftime(FMT), due.strftime(FMT))).lastrowid
        target = {'ask_id': q}
    else:
        target = targets.get(kind, {})
    cid = c.execute("""INSERT INTO commitments(agent_id,to_agent_id,content,kind,target_json,made_at,due_at)
        VALUES (3,1,'Write forty quiz questions',?,?,?,?)""",
        (kind, json.dumps(target), start.strftime(FMT), due.strftime(FMT))).lastrowid
    return dict(c.execute('SELECT * FROM commitments WHERE id=?', (cid,)).fetchone())


def action(c, owner, key, args, at):
    return c.execute("""INSERT INTO actions(agent_id,key,args_json,reason,status,trigger,evidence,sim_at)
        VALUES (?,?,?,'Offline evidence','done','reaction','[]',?)""", (owner, key, json.dumps(args), at.strftime(FMT))).lastrowid


def trigger(c, at=START):
    action(c, 1, 'announce_quiz', {}, at)


def support(c, p, owner=3, at=None):
    at = at or START + timedelta(hours=1)
    t = json.loads(p['target_json']); kind = p['kind']
    if kind == 'action':
        action(c, owner, t['key'], t['args'], at)
    elif kind in ('visit', 'conditional'):
        if kind == 'conditional':
            trigger(c)
        c.execute("INSERT INTO timeline(sim_at,kind,agent_id,text,importance) VALUES (?,'arrival',?,?,1)",
                  (at.strftime(FMT), owner, f"Arrival ({world.PUB})"))
    elif kind in ('talk', 'tell'):
        cid = c.execute("""INSERT INTO conversations(location,status,sim_at,agent_a_id,agent_b_id)
            VALUES ('On the phone','completed',?,?,1)""", (at.strftime(FMT), owner)).lastrowid
        c.execute("INSERT INTO messages(conversation_id,speaker_id,text,rationale,sim_time) VALUES (?,?,'Quiz news','Offline',?)",
                  (cid, owner, at.strftime(FMT)))
        if kind == 'tell':
            content = c.execute('SELECT content FROM facts WHERE id=?', (t['fact_id'],)).fetchone()[0]
            c.execute("""INSERT INTO facts(agent_id,subject,content,source,source_agent_id,source_conversation_id)
                VALUES (1,'quiz',?,'told',?,?)""", (content, owner, cid))
    elif kind == 'make':
        for old in (0, 20):
            aid = action(c, owner, 'write_quiz_questions', {'count': 20}, at)
            c.execute("INSERT INTO stat_changes(key,old,new,reason,sim_at,action_id) VALUES ('pub.quiz_questions_ready',?,?,'Quiz',?,?)",
                      (old, old + 20, at.strftime(FMT), aid))
    elif kind == 'pay':
        c.execute("UPDATE asks SET status='accepted' WHERE id=?", (t['ask_id'],))
        action(c, owner, 'answer_ask', {'ask_id': t['ask_id'], 'answer': 'yes'}, at)


@pytest.mark.parametrize('kind', CHECKABLE)
def test_claim_without_evidence_never_kept(db, kind):
    with connect(db) as c:
        p = promise(c, kind)
        before = relationships.get(c, 1, 3)['trust']
        assert memory.record_claim(c, p['id'], 3, 'I did it.', START) == 1
        assert memory.resolve_commitment(c, p['id'], 'done', 'I did it.', DUE) == 0
        assert relationships.get(c, 1, 3)['trust'] == before
        assert c.execute('SELECT status FROM commitments').fetchone()[0] == 'open'


@pytest.mark.parametrize('kind', CHECKABLE)
def test_evidence_kept_once_with_one_trust_change(db, kind):
    with connect(db) as c:
        p = promise(c, kind)
        memory.record_claim(c, p['id'], 3, 'Done.', START)
        support(c, p)
        assert evidence_for(c, p)
        before = relationships.get(c, 1, 3)['trust']
        assert memory.resolve_commitment(c, p['id'], 'done', 'Model story must be ignored', DUE) == 1
        assert memory.resolve_commitment(c, p['id'], 'done', 'Again', DUE) == 0
        assert relationships.get(c, 1, 3)['trust'] == before + 8
        assert c.execute("SELECT count(*) FROM relationship_events WHERE reason LIKE '%kept a promise%'").fetchone()[0] == 1
        assert c.execute('SELECT outcome FROM promise_claims').fetchone()[0] == 'supported'
        assert 'Model story' not in c.execute('SELECT outcome FROM commitments').fetchone()[0]


@pytest.mark.parametrize('kind', CHECKABLE)
@pytest.mark.parametrize('wrong', ['owner', 'time'])
def test_wrong_owner_or_old_evidence_does_not_count(db, kind, wrong):
    with connect(db) as c:
        p = promise(c, kind)
        support(c, p, owner=2 if wrong == 'owner' else 3,
                at=START - timedelta(minutes=1) if wrong == 'time' else START + timedelta(hours=1))
        assert evidence_for(c, p) is None
        assert memory.resolve_commitment(c, p['id'], 'done', 'Claim', DUE) == 0


@pytest.mark.parametrize('kind', CHECKABLE)
def test_no_opportunity_retries_once_without_moving_deadline(db, monkeypatch, kind):
    with connect(db) as c:
        p = promise(c, kind)
        if kind == 'conditional':
            trigger(c)
        before = relationships.get(c, 1, 3)['trust']
    monkeypatch.setattr(world, 'is_free', lambda *a: False)
    assert tick.check_due_promises(NoModel(), DUE, db) == 1
    with connect(db) as c:
        row = dict(c.execute('SELECT * FROM commitments').fetchone())
        assert row['due_at'] == DUE.strftime(FMT)
        assert row['retry_at'] == (DUE + timedelta(days=1)).strftime(FMT)
        assert not row['lapsed_at'] and row['status'] == 'open'
        assert relationships.get(c, 1, 3)['trust'] == before
    assert tick.check_due_promises(NoModel(), DUE + timedelta(hours=1), db) == 0
    assert tick.check_due_promises(NoModel(), DUE + timedelta(days=1), db) == 1
    with connect(db) as c:
        assert c.execute('SELECT lapsed_at FROM commitments').fetchone()[0]
        assert relationships.get(c, 1, 3)['trust'] == before


def test_closed_place_and_sleep_are_no_chance(db):
    with connect(db) as c:
        asleep = promise(c, 'action', START.replace(hour=0), START.replace(hour=4))
        assert not had_chance(c, asleep, asleep['due_at'])
        closed = promise(c, 'visit', START.replace(hour=7), START.replace(hour=9))
        assert not had_chance(c, closed, closed['due_at'])


@pytest.mark.parametrize('kind', CHECKABLE)
def test_deadline_resolves_database_evidence_without_model(db, kind):
    with connect(db) as c:
        p = promise(c, kind)
        support(c, p)
    assert tick.check_due_promises(NoModel(), DUE, db) == 1
    assert tick.check_due_promises(NoModel(), DUE, db) == 0
    with connect(db) as c:
        assert c.execute('SELECT status FROM commitments').fetchone()[0] == 'done'


def test_honest_miss_and_false_claim_are_different(db):
    with connect(db) as c:
        p = promise(c, 'make')
        before = relationships.get(c, 1, 3)['trust']
        warmth = relationships.get(c, 1, 3)['warmth']
        memory.record_claim(c, p['id'], 3, "I've handed over all forty.", START)
    tick.check_due_promises(NoModel(), DUE, db)
    tick.check_due_promises(NoModel(), DUE, db)
    with connect(db) as c:
        assert c.execute('SELECT status FROM commitments').fetchone()[0] == 'broken'
        assert c.execute('SELECT outcome FROM promise_claims').fetchone()[0] == 'false'
        assert relationships.get(c, 1, 3)['trust'] == before + memory.FALSE_CLAIM_TRUST
        assert relationships.get(c, 1, 3)['warmth'] == warmth + memory.FALSE_CLAIM_WARMTH
        fact = c.execute("SELECT content FROM facts WHERE agent_id=1 AND subject='promise'").fetchone()[0]
        assert 'claimed' in fact and 'no matching completion' in fact
        assert c.execute("SELECT count(*) FROM timeline WHERE kind='promise_false_claim'").fetchone()[0] == 1
        p = promise(c, 'make')
        before = relationships.get(c, 1, 3)['trust']
    tick.check_due_promises(NoModel(), DUE, db)
    with connect(db) as c:
        assert relationships.get(c, 1, 3)['trust'] == before + memory.BROKEN_TRUST


@pytest.mark.parametrize('kind', ['vague', None, 'conditional'])
def test_uncheckable_or_untriggered_lapses_neutrally_with_fact(db, kind):
    with connect(db) as c:
        p = promise(c, kind)
        memory.record_claim(c, p['id'], 3, 'Done.', START)
        before = relationships.get(c, 1, 3)['trust']
    tick.check_due_promises(NoModel(), DUE, db)
    with connect(db) as c:
        row = c.execute('SELECT * FROM commitments').fetchone()
        assert row['status'] == 'open' and row['lapsed_at']
        assert relationships.get(c, 1, 3)['trust'] == before
        assert c.execute("SELECT count(*) FROM facts WHERE agent_id=1 AND subject='promise'").fetchone()[0] == 1


@pytest.mark.parametrize('kind,target', [
    ('action', {'key': 'accept_surrender', 'args': {'offer_id': 1}}),
    ('action', {'key': 'invented', 'args': {}}),
    ('visit', {'place': 'moon'}), ('talk', {'person': 'Stranger that does not exist'}),
    ('tell', {'person': 'Dez Whitworth', 'fact_id': 999999}),
    ('make', {'item': 'cake', 'count': 1}), ('pay', {'amount': 500}),
    ('conditional', {'condition': 'If I hear anything', 'promise': {'kind': 'visit', 'target': {'place': 'pub'}}}),
])
def test_invalid_targets_are_vague(db, kind, target):
    with connect(db) as c:
        owner = dict(c.execute('SELECT * FROM agents WHERE id=3').fetchone())
        assert validate_target(c, owner, kind, target) == ('vague', {})


def conversation(c, at=START):
    cid = c.execute("INSERT INTO conversations(location,status,sim_at,agent_a_id,agent_b_id) VALUES ('pub','completed',?,3,1)",
                    (at.strftime(FMT),)).lastrowid
    c.execute("INSERT INTO messages(conversation_id,speaker_id,text,rationale,sim_time) VALUES (?,3,'I did it.','Claim',?)", (cid, at.strftime(FMT)))
    people = {r['name']: dict(r) for r in c.execute('SELECT * FROM agents WHERE id IN (1,3)')}
    return cid, people


def test_conversation_claim_closes_nothing_and_keeps_said_text(db):
    with connect(db) as c:
        p = promise(c, 'make')
        cid, people = conversation(c)
        result = memory.store_extraction(c, cid, people, Extraction(summary='Claim', commitments_done=[p['id']]), START)
        assert result['resolved'] == 0
        assert c.execute('SELECT status FROM commitments').fetchone()[0] == 'open'
        claim = c.execute('SELECT * FROM promise_claims').fetchone()
        assert claim['said'] == 'I did it.' and claim['outcome'] == 'pending' and claim['source_conversation_id'] == cid
        assert c.execute('SELECT claimed_at FROM commitments').fetchone()[0] == START.strftime(FMT)


@pytest.mark.parametrize('claim_path', ['model', 'conversation'])
def test_fifty_seed_audit_never_keeps_self_certified_quiz(db, claim_path):
    # Fake PromiseCheck(done=True) is deliberately offered: the tick must never ask for it.
    class LyingClient:
        calls = 0
        def propose(self, *args, **kwargs):
            self.calls += 1
            return PromiseCheck(done=True, what_happened='All forty done.', mood='happy')
    kept = 0
    client = LyingClient()
    for seed in range(50):
        rng = random.Random(seed)
        with connect(db) as c:
            p = promise(c, 'make')
            if claim_path == 'conversation':
                cid, people = conversation(c, START + timedelta(minutes=rng.randrange(60)))
                memory.store_extraction(c, cid, people, Extraction(summary='Claim', commitments_done=[p['id']]), START)
        tick.check_due_promises(client, DUE, db)
        with connect(db) as c:
            kept += c.execute("SELECT count(*) FROM commitments WHERE id=? AND status='done'", (p['id'],)).fetchone()[0]
    assert kept == 0 and client.calls == 0


@pytest.mark.parametrize('done', [True, False])
def test_human_player_can_still_resolve_own_promise(db, monkeypatch, done):
    with connect(db) as c:
        me = player.row(c)['id']
        pid = c.execute("INSERT INTO commitments(agent_id,to_agent_id,content) VALUES (?,1,'Bring darts')", (me,)).lastrowid
    monkeypatch.setattr(world, 'now', lambda *a: START)
    player.resolve(pid, done, 'My outcome.', db)
    with connect(db) as c:
        assert c.execute('SELECT status,outcome FROM commitments').fetchone()[:] == ('done' if done else 'broken', 'My outcome.')


def test_typed_example_and_normalization_are_preserved(db):
    text = prompts.build_extraction_messages({'name': 'Tommy Shaw', 'location': 'pub'}, {'name': 'Dez Whitworth'}, [], [], [], [], 'now')[0]['content']
    example = text.split('Return JSON exactly like:', 1)[1]
    assert '"kind": "make", "target": {"item": "quiz_questions", "count": 40}' in example
    with connect(db) as c:
        cid, people = conversation(c)
        ext = Extraction(summary='Promise', per_agent={'Tommy Shaw': {'commitments': [
            {'content': 'Write forty quiz questions', 'kind': 'make', 'target': {'item': 'quiz_questions', 'count': 40}}]}})
        assert ext.per_agent['Tommy Shaw'].commitments[0].target['count'] == 40
        memory.store_extraction(c, cid, people, ext, START)
        p = dict(c.execute('SELECT * FROM commitments').fetchone())
        assert p['kind'] == 'make' and p['made_at'] == START.strftime(FMT)
        assert '0 of 40' in progress(c, p)
        support(c, p)
        assert '40 of 40' in progress(c, p)


def test_lapsed_never_open_in_prompts_views_plans_or_catchup(db, monkeypatch):
    with connect(db) as c:
        p = promise(c, 'vague')
        memory.lapse_commitment(c, p, DUE, 'Uncheckable.')
        me = player.row(c)['id']
        c.execute('UPDATE agents SET last_seen_at=? WHERE id=?', (START.strftime(FMT), me))
        human = c.execute("INSERT INTO commitments(agent_id,content,lapsed_at) VALUES (?,'Human lapsed',?)", (me, DUE.strftime(FMT))).lastrowid
        owner = dict(c.execute('SELECT * FROM agents WHERE id=3').fetchone())
        listener = dict(c.execute('SELECT * FROM agents WHERE id=1').fetchone())
        assert not memory.open_commitments(c, 3)
        assert not memory.open_commitments(c, me)
        knowledge = memory.knowledge_for_prompt(c, owner, listener, DUE)
        assert not knowledge['promises']
        assert not memory.knowledge_for_prompt(c, listener, owner, DUE)['their_promises']
        assert memory.resolve_commitment(c, p['id'], 'done', 'Done', DUE) == 0
    assert tick.check_due_promises(NoModel(), DUE, db) == 0
    monkeypatch.setattr(main, 'DEFAULT_DB_PATH', db)
    monkeypatch.setattr(world, 'now', lambda *a: DUE)
    cards = asyncio.run(main.agents())
    card = next(a for a in cards if a['id'] == 3)
    assert card['promises'] == [] and card['resolved'][0]['status'] == 'lapsed'
    assert not player.state(db)['promises']
    with pytest.raises(HTTPException):
        player.resolve(human, True, 'Done', db)
    player.maintenance(NoModel(), DUE + timedelta(days=5), db)
    with connect(db) as c:
        assert c.execute('SELECT status FROM commitments WHERE id=?', (human,)).fetchone()[0] == 'open'
    proposal = {'action': 'visit', 'place': 'shop', 'hour': 17, 'minute': 0, 'duration_minutes': 30, 'fulfils': p['id'], 'reason': 'Paper'}
    assert plans.validate(proposal, owner, DUE, db)['fulfils_commitment_id'] is None
    text = prompts.build_extraction_messages(owner, listener, [], [], [dict(p, owner=owner['name'], lapsed_at='yes')], [], 'now')[0]['content']
    assert f"id {p['id']} (Tommy" not in text
    recap = catchup.get(None, DUE + timedelta(hours=1), db)
    assert 'promises' not in recap  # catch-up reads outcomes, never open-promises rows
    assert any(e['kind'] == 'promise_lapsed' and 'lapsed' in e['text'] for e in recap['timeline'])


def test_migration_15_preserves_v14_world_and_plan_foreign_keys(tmp_path):
    original = tmp_path / 'version14.sqlite3'; copy = tmp_path / 'copy.sqlite3'
    with connect(original) as c:
        for migration in MIGRATIONS[:14]:
            for statement in migration:
                c.execute(statement)
        c.execute('PRAGMA user_version=14')
    seed_agents(original)
    with connect(original) as c:
        cid, _ = conversation(c)
        pid = c.execute("INSERT INTO commitments(agent_id,to_agent_id,content,source_conversation_id) VALUES (3,1,'Legacy quiz',?)", (cid,)).lastrowid
        c.execute("INSERT INTO commitments(agent_id,content) VALUES (3,'No source')")
        plans.insert(c, {'agent_id': 3, 'action': 'visit', 'place': 'pub', 'fulfils_commitment_id': pid, 'sim_day': '2026-11-23'})
        before = [dict(r) for r in c.execute('SELECT * FROM commitments')]
        schema = c.execute("SELECT sql FROM sqlite_master WHERE name='commitments'").fetchone()[0]
    with sqlite3.connect(original) as src, sqlite3.connect(copy) as dst:
        src.backup(dst)
    init_db(copy); init_db(copy)
    with connect(copy) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0] == 15
        assert not c.execute('PRAGMA foreign_key_check').fetchall()
        after = [dict(r) for r in c.execute('SELECT * FROM commitments')]
        for old, new in zip(before, after):
            assert all(new[k] == v for k, v in old.items())
        assert after[0]['made_at'] == START.strftime(FMT) and after[1]['made_at'] is None
        assert after[0]['kind'] is None
        assert [p['content'] for p in memory.open_commitments(c, 3)] == ['No source', 'Legacy quiz']
        assert c.execute('SELECT fulfils_commitment_id FROM plans').fetchone()[0] == pid
        assert "CHECK (status IN ('open', 'done', 'broken'))" in schema
        assert "CHECK (status IN ('open', 'done', 'broken'))" in c.execute("SELECT sql FROM sqlite_master WHERE name='commitments'").fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("UPDATE commitments SET status='lapsed'")


@pytest.mark.parametrize('kind', CHECKABLE)
def test_future_evidence_cannot_resolve_at_deadline(db, kind):
    with connect(db) as c:
        p = promise(c, kind)
        support(c, p, at=DUE + timedelta(minutes=1))
        assert memory.resolve_commitment(c, p['id'], 'done', 'From the future', DUE) == 0
    # The heartbeat can arrive late; it must still use the actual deadline.
    tick.check_due_promises(NoModel(), DUE + timedelta(hours=2), db)
    with connect(db) as c:
        assert c.execute('SELECT status FROM commitments').fetchone()[0] != 'done'


@pytest.mark.parametrize('kind', ['talk', 'tell'])
def test_incomplete_conversation_or_missing_owner_message_is_not_evidence(db, kind):
    with connect(db) as c:
        p = promise(c, kind)
        support(c, p)
        c.execute("UPDATE conversations SET status='running'")
        assert evidence_for(c, p) is None
        c.execute("UPDATE conversations SET status='completed'")
        c.execute('DELETE FROM messages WHERE speaker_id=3')
        assert evidence_for(c, p) is None


@pytest.mark.parametrize('kind', ['talk', 'tell'])
def test_promise_making_conversation_cannot_fulfil_its_own_future_promise(db, kind):
    with connect(db) as c:
        p = promise(c, kind)
        support(c, p, at=START)
        cid = c.execute('SELECT id FROM conversations').fetchone()[0]
        p['source_conversation_id'] = cid
        assert evidence_for(c, p) is None


def test_action_arguments_and_specific_information_must_match(db):
    with connect(db) as c:
        p = promise(c, 'action')
        action(c, 3, 'write_quiz_questions', {'count': 5}, START)
        assert evidence_for(c, p) is None
        p = promise(c, 'tell')
        another = c.execute("INSERT INTO facts(agent_id,subject,content,source) VALUES (3,'other','Unrelated news','observed')").lastrowid
        action(c, 3, 'tell', {'person': 'Dez Whitworth', 'fact_id': another}, START)
        assert evidence_for(c, p) is None
        action(c, 3, 'tell', {'person': 'Dez', 'fact_id': json.loads(p['target_json'])['fact_id']}, START)
        assert evidence_for(c, p)


def test_visit_plan_matches_target_window_and_only_visit(db):
    with connect(db) as c:
        p = promise(c, 'visit')
        target = {'place': 'shop', 'start_at': '2026-11-23 13:00', 'end_at': '2026-11-23 14:00'}
        p['target_json'] = json.dumps(target)
        pid = plans.insert(c, {'agent_id': 3, 'action': 'visit', 'place': 'shop', 'status': 'done',
                              'start_at': '2026-11-23 12:30', 'end_at': '2026-11-23 13:00', 'sim_day': '2026-11-23'})
        assert evidence_for(c, p) is None
        c.execute("UPDATE plans SET start_at='2026-11-23 13:00',end_at='2026-11-23 13:30' WHERE id=?", (pid,))
        assert evidence_for(c, p)
        c.execute("UPDATE plans SET action='stay_home' WHERE id=?", (pid,))
        assert evidence_for(c, p) is None


def test_unrelated_plan_cannot_complete_quiz_or_someone_elses_promise(db):
    with connect(db) as c:
        p = promise(c, 'make')
        plans.insert(c, {'agent_id': 3, 'action': 'visit', 'place': 'pub', 'status': 'active',
                        'start_at': '2026-11-23 13:00', 'end_at': '2026-11-23 14:00', 'sim_day': '2026-11-23',
                        'fulfils_commitment_id': p['id']})
    plans.execute(NoModel(), START.replace(hour=14), db)
    with connect(db) as c:
        assert c.execute('SELECT status FROM commitments').fetchone()[0] == 'open'
        # Even valid evidence belonging to someone else cannot make this plan theirs.
        p = promise(c, 'visit')
        support(c, p)
        plans.insert(c, {'agent_id': 2, 'action': 'visit', 'place': 'pub', 'status': 'active',
                        'start_at': '2026-11-23 13:00', 'end_at': '2026-11-23 14:00', 'sim_day': '2026-11-23',
                        'fulfils_commitment_id': p['id']})
    plans.execute(NoModel(), START.replace(hour=14), db)
    with connect(db) as c:
        assert c.execute('SELECT status FROM commitments WHERE id=?', (p['id'],)).fetchone()[0] == 'open'


def test_real_quiz_actions_accumulate_only_the_owners_stat_changes(db):
    with connect(db) as c:
        p = promise(c, 'make', due=DUE + timedelta(days=3))
        actor = dict(c.execute('SELECT * FROM agents WHERE id=3').fetchone())
        proposal = {'action': 'write_quiz_questions', 'args': {'count': 20}, 'reason': 'Keep my promise.', 'evidence': []}
        assert actions.propose(c, actor, proposal, START, 'plan')['status'] == 'done'
        assert '20 of 40' in progress(c, p)
        assert evidence_for(c, p) is None
        assert actions.propose(c, actor, proposal, START + timedelta(days=1), 'plan')['status'] == 'done'
        assert '40 of 40' in progress(c, p)
        assert memory.resolve_commitment(c, p['id'], 'done', '', START + timedelta(days=1)) == 1


def test_pay_requires_attributed_accepted_settlement_not_just_offer_status(db):
    with connect(db) as c:
        oid = economy.offer(c, 'surrender', 6, 5, 45000, 'Lease surrender', START, DUE)
        p = promise(c, 'vague')
        c.execute("UPDATE commitments SET agent_id=5,kind='pay',target_json=? WHERE id=?", (json.dumps({'offer_id': oid}), p['id']))
        p = dict(c.execute('SELECT * FROM commitments WHERE id=?', (p['id'],)).fetchone())
        c.execute("UPDATE offers SET status='accepted',resolved_at=? WHERE id=?", (DUE.strftime(FMT), oid))
        assert evidence_for(c, p) is None
        action(c, 6, 'accept_surrender', {'offer_id': oid}, DUE)
        assert evidence_for(c, p) is None
        action(c, 5, 'accept_surrender', {'offer_id': oid}, DUE)
        assert evidence_for(c, p)


def test_old_condition_does_not_trigger_new_promise(db):
    with connect(db) as c:
        p = promise(c, 'conditional')
        trigger(c, START - timedelta(minutes=1))
    tick.check_due_promises(NoModel(), DUE, db)
    with connect(db) as c:
        assert c.execute('SELECT lapsed_at FROM commitments').fetchone()[0]
        assert not c.execute('SELECT 1 FROM relationship_events').fetchall()


def test_deadline_bookkeeping_still_bounded(db):
    with connect(db) as c:
        for _ in range(tick.MAX_PROMISE_CHECKS_PER_TICK + 1):
            promise(c, 'vague')
    assert tick.check_due_promises(NoModel(), DUE, db) == tick.MAX_PROMISE_CHECKS_PER_TICK
    assert tick.check_due_promises(NoModel(), DUE, db) == 1
