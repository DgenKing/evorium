"""Police follow-ups use temporary worlds and fake dialogue only."""
from datetime import datetime, timedelta
import sqlite3
import pytest
from evorium import accounts, actions, cases, catchup, economy, memory, player, prompts, sim, tick, world
from evorium.db import MIGRATIONS, connect, init_db
from evorium.seed import seed_agents
from evorium.models import ActionProposal, Extraction

NOW = datetime(2026, 11, 23, 10, 5)
REPORT = 'Rob threatened to break my jaw and said he had a gun.'


class Fake:
    def __init__(self, extraction=None):
        self.calls = []
        self.extraction = extraction or Extraction(summary='Grace heard Rob’s account.')

    def propose(self, aid, messages, schema=ActionProposal, max_tokens=300):
        self.calls.append((aid, messages, schema, max_tokens))
        if schema is Extraction:
            return self.extraction
        return ActionProposal(say='Rob, I need to discuss the report about threatening Dez.', rationale='Follow up the report.', mood='calm')


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / 'cases.sqlite3'
    init_db(path)
    seed_agents(path)
    monkeypatch.setattr(world, 'now', lambda *a: NOW)
    with connect(path) as c:
        me = accounts.player_row(c)
        c.execute("UPDATE agents SET name='Rob' WHERE id=?", (me['id'],))
    economy.ensure(path, NOW)
    tick.update_routines(NOW, path)
    return path


def report(db, text=REPORT, importance=5, source='told', subject='Rob', at='2026-11-20 23:00'):
    with connect(db) as c:
        g = cases.grace(c)
        dez = c.execute("SELECT id FROM agents WHERE name LIKE 'Dez %'").fetchone()[0]
        cid = c.execute("INSERT INTO conversations(location,status,sim_at,agent_a_id,agent_b_id) VALUES (?,'completed',?,?,?)", (world.PUB, at, dez, g['id'])).lastrowid
        return c.execute('''INSERT INTO facts(agent_id,subject,content,source,source_agent_id,source_conversation_id,importance)
            VALUES (?,?,?,?,?,?,?)''', (g['id'], subject, text, source, dez, cid, importance)).lastrowid


def get_case(db, name='Rob'):
    with connect(db) as c:
        return dict(c.execute('SELECT v.* FROM cases v JOIN agents a ON a.id=v.subject_id WHERE a.name=? ORDER BY v.id DESC LIMIT 1', (name,)).fetchone())


def test_backfill_once_and_incremental_reports(db):
    fid = report(db)
    cases.maintain(NOW, db)
    first = get_case(db)
    assert first['opened_at'] == '2026-11-20 23:00'
    assert first['source_fact_id'] == fid
    cases.maintain(NOW, db)
    with connect(db) as c:
        assert c.execute('SELECT count(*) FROM cases').fetchone()[0] == 1
        cases.finish(c, first, 'advice', NOW)
    cases.maintain(NOW, db)
    assert get_case(db)['status'] == 'closed'  # old report never reopens on restart
    report(db, text='Rob threatened Dez again.', at='2026-11-24 10:00')
    cases.maintain(NOW + timedelta(days=1), db)
    assert get_case(db)['id'] != first['id']


@pytest.mark.parametrize('text,importance,source', [
    (REPORT, 4, 'told'), (REPORT, 5, 'claim'),
    ('Someone might cause trouble.', 5, 'told'),
    ('Rob said he was worried about gun crime.', 5, 'told'),
    ('Dez fears Rob may get angry.', 5, 'told'),
    ('Rob was threatened by Dez.', 5, 'told'),
    ('If Rob threatened Dez I would report it.', 5, 'told'),
    ('Rob did not threaten Dez.', 5, 'told'),
])
def test_ignore_nonreports(db, text, importance, source):
    report(db, text, importance, source)
    cases.maintain(NOW, db)
    with connect(db) as c:
        assert not c.execute('SELECT 1 FROM cases').fetchone()


def test_observed_and_one_open_case_per_subject(db):
    report(db, source='observed')
    report(db)
    cases.maintain(NOW, db)
    with connect(db) as c:
        assert c.execute('SELECT count(*) FROM cases').fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("INSERT INTO cases(subject_id,summary,opened_at,last_incident_at) VALUES (?,'duplicate','now','now')", (get_case(db)['subject_id'],))


def test_priority_pair_only_free_same_place_on_beat(db, monkeypatch):
    report(db, 'Tommy attacked Dez.', subject='Tommy')
    cases.maintain(NOW, db)
    # On the Monday street patrol Tommy is walking to the shops.
    when = NOW
    monkeypatch.setattr(world, 'now', lambda *a: when)
    with connect(db) as c:
        g = cases.grace(c)
        peggy = dict(c.execute("SELECT * FROM agents WHERE name LIKE 'Tommy %'").fetchone())
        c.execute('UPDATE agents SET location=? WHERE id IN (?,?)', (world.STREET, g['id'], peggy['id']))
    assert world.pick_pair([1, 3, g['id'], peggy['id']], db) == (g['id'], peggy['id'])
    with connect(db) as c:
        assert cases.priority(c, [g['id'], peggy['id']], when.replace(hour=7)) is None
        c.execute('UPDATE agents SET location=? WHERE id=?', (world.PUB, peggy['id']))
        assert cases.priority(c, [g['id'], peggy['id']], when) is None


def test_approach_reply_and_once_daily(db):
    report(db)
    cases.maintain(NOW, db)
    fake = Fake()
    player.enter(fake, 'street', db)
    assert cases.approach(fake, NOW, db)
    state = player.state(db)
    assert state['conversation']['messages'][0]['speaker_name'] == cases.GRACE
    assert 'open report about Rob' in fake.calls[0][1][0]['content']
    assert len(fake.calls) == 1 and fake.calls[0][3] == 300
    player.say(fake, state['conversation']['agent_b_id'], 'I am sorry. I should not have threatened him.', db)
    player.close(fake, db)
    assert get_case(db)['status'] == 'spoken_to'
    assert not cases.approach(fake, NOW, db)
    assert cases.approach(fake, NOW + timedelta(days=1), db)


def test_never_interrupt_player_or_busy_grace(db):
    report(db)
    cases.maintain(NOW, db)
    fake = Fake()
    player.enter(fake, 'street', db)
    with connect(db) as c:
        me = accounts.player_row(c)
        g = cases.grace(c)
        cid = c.execute("INSERT INTO conversations(location,status,agent_a_id,agent_b_id) VALUES (?,'running',?,1)", (world.STREET, me['id'])).lastrowid
    assert not cases.approach(fake, NOW, db)
    assert not fake.calls
    with connect(db) as c:
        c.execute("UPDATE conversations SET status='completed' WHERE id=?", (cid,))
        c.execute("INSERT INTO conversations(location,status,agent_a_id,agent_b_id) VALUES (?,'running',?,1)", (world.STREET, g['id']))
    assert not cases.approach(fake, NOW, db)
    assert not fake.calls


def test_away_notice_catchup_and_account_isolation(db):
    fake = Fake()
    report(db)
    catchup.seen(NOW - timedelta(hours=1), db)
    cases.maintain(NOW, db)
    assert not cases.approach(fake, NOW, db)
    assert 'wants a word' in player.state(db)['police']['notice']
    assert any('came looking' in x for x in catchup.get(None, NOW, db)['items'])
    cases.approach(fake, NOW, db)
    with connect(db) as c:
        assert c.execute("SELECT count(*) FROM facts WHERE subject='police visit'").fetchone()[0] == 1
    token = accounts.current.set('thomas')
    try:
        accounts.ensure_player('thomas', 'Thomas', db)
        player.enter(fake, 'street', db)
        assert not cases.approach(fake, NOW, db)
        assert not player.state(db)['police']['notice']
        assert not player.state(db)['conversation']
        assert not any('came looking' in x for x in catchup.get(None, NOW, db)['items'])
    finally:
        accounts.current.reset(token)
    player.enter(fake, 'street', db)
    assert cases.approach(fake, NOW, db)
    assert player.state(db)['conversation']['agent_a_id'] == get_case(db)['subject_id']


@pytest.mark.parametrize('key,outcome', [('give_advice','advice'), ('give_formal_warning','formal_warning')])
def test_spoken_outcomes_through_normal_writeup(db, key, outcome):
    report(db)
    cases.maintain(NOW, db)
    quote = 'I am giving you a formal warning about threatening Dez.' if outcome == 'formal_warning' else 'I am giving you words of advice about threatening Dez.'
    fake = Fake(Extraction(summary='Grace followed up the report.', per_agent={cases.GRACE: {'decision': {'action':key, 'args':{'person':'Rob'}, 'quote':quote}}}))
    player.enter(fake, 'street', db)
    cases.approach(fake, NOW, db)
    with connect(db) as c:
        conv = player.opened(c)
        c.execute('UPDATE messages SET text=? WHERE conversation_id=?', (quote, conv['id']))
    player.close(fake, db)
    assert get_case(db)['outcome'] == outcome
    assert player.state(db)['police']['outcomes'] == [outcome.replace('_',' ')]
    assert not player.state(db)['police']['notice']
    with connect(db) as c:
        assert c.execute("SELECT status FROM actions WHERE key=?", (key,)).fetchone()[0] == 'done'
        assert c.execute("SELECT 1 FROM facts WHERE agent_id=? AND source='observed' AND content LIKE 'PCSO Grace Adeyemi gave me%'", (get_case(db)['subject_id'],)).fetchone()
        assert c.execute("SELECT 1 FROM facts WHERE agent_id=? AND source='told' AND content LIKE 'Grace has spoken to Rob%'", (get_case(db)['reported_by'],)).fetchone()
        assert c.execute("SELECT 1 FROM timeline WHERE kind='serious' AND text LIKE 'PCSO Grace%'").fetchone()
        assert not cases.menu(c, cases.grace(c), accounts.player_row(c))


def test_menu_only_for_open_subject_and_spoken_attribution_checks(db):
    report(db)
    cases.maintain(NOW, db)
    fake = Fake()
    player.enter(fake, 'street', db)
    cases.approach(fake, NOW, db)
    with connect(db) as c:
        g, me = cases.grace(c), accounts.player_row(c)
        other = dict(c.execute('SELECT * FROM agents WHERE id=1').fetchone())
        assert cases.menu(c, g, me) and not cases.menu(c, g, other)
        assert not cases.menu(c, other, me)
        menu = actions.candidates(c, g, NOW)
        assert any(x['action'] == 'give_advice' for x in menu)
        cid = player.opened(c)['id']
        valid = 'I am giving you words of advice about threatening Dez.'
        decision = {'action':'give_advice','args':{'person':'Rob'},'quote':valid}
        for transcript in ([], [{'speaker_id': me['id'], 'text': valid}]):
            assert actions.propose(c, g, decision, NOW, 'conversation', cid, transcript)['status'] == 'rejected'
        wrong = {**decision, 'args': {'person':'Dez'}}
        assert actions.propose(c, g, wrong, NOW, 'conversation', cid, [{'speaker_id':g['id'],'text':valid}])['status'] == 'rejected'
        assert actions.propose(c, g, {'action':'give_advice','args':{'person':'Rob'},'reason':'Just decide.'}, NOW)['status'] == 'rejected'
        assert get_case(db)['status'] == 'open'
        messages = prompts.build_extraction_messages(g, other, [], [], [], [], 'now', {g['name']:False})
        assert 'give_advice' not in messages[0]['content']


def test_timeout_three_game_days_and_new_incident_resets_clock(db):
    report(db)
    cases.maintain(NOW, db)
    fake = Fake()
    player.enter(fake, 'street', db)
    cases.approach(fake, NOW, db)
    player.close(fake, db)
    cases.maintain(NOW + timedelta(days=2), db)
    assert get_case(db)['status'] == 'spoken_to'
    report(db, 'Rob threatened Dez again.', at='2026-11-25 10:05')
    cases.maintain(NOW + timedelta(days=3), db)
    assert get_case(db)['status'] == 'spoken_to'
    cases.maintain(NOW + timedelta(days=5), db)
    assert get_case(db)['outcome'] == 'no_further_action'
    cases.maintain(NOW + timedelta(days=6), db)
    with connect(db) as c:
        assert c.execute("SELECT count(*) FROM timeline WHERE kind='serious' AND text LIKE '%no further action%'").fetchone()[0] == 1


def test_upgrade_15_preserves_world_and_foreign_keys(tmp_path):
    path = tmp_path / 'old.sqlite3'
    with sqlite3.connect(path) as c:
        for migration in MIGRATIONS[:15]:
            for statement in migration:
                c.execute(statement)
        c.execute('PRAGMA user_version=15')
    seed_agents(path)
    with connect(path) as c:
        before = [tuple(r) for r in c.execute('SELECT * FROM facts')]
    init_db(path)
    init_db(path)
    with connect(path) as c:
        assert [tuple(r) for r in c.execute('SELECT * FROM facts')] == before
        assert not c.execute('PRAGMA foreign_key_check').fetchall()
        assert c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


def test_notice_stops_once_grace_has_spoken(db):
    fake = Fake()
    report(db)
    cases.maintain(NOW, db)
    player.enter(fake, 'street', db)
    assert 'wants a word' in player.state(db)['police']['notice']
    assert cases.approach(fake, NOW, db)
    player.close(fake, db)
    assert get_case(db)['status'] == 'spoken_to'
    assert not player.state(db)['police']['notice']
