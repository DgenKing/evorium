from evorium.seed import CHARACTERS
from datetime import datetime, timedelta

import pytest

from evorium import tick, world
from evorium.db import connect, init_db
from evorium.llm import InvalidProposal
from evorium.models import PromiseCheck
from evorium.seed import seed_agents, seed_events


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "w.sqlite3"
    init_db(path)
    seed_agents(path)
    return path


def test_clock_is_real_time_by_default_and_speed_reanchors(db):
    real = datetime.now(world.TZ).replace(tzinfo=None)
    assert abs((world.now(db) - real).total_seconds()) < 5
    world.set_speed(0, db)                                # paused: clock stands still
    t0 = world.now(db)
    assert abs((t0 - real).total_seconds()) < 5          # continuous across the change
    assert world.now(db) == t0
    world.set_speed(600, db)
    assert world.get_speed(db) == 600
    t1 = world.now(db)
    assert t0 <= t1 < t0 + timedelta(seconds=600 * 5)    # racing ahead from where it was, not jumping
    world.reset_to_real_time(db)
    assert world.get_speed(db) == 1
    assert abs((world.now(db) - real).total_seconds()) < 5


def test_pub_hours_and_routines():
    mon_3pm = datetime(2026, 11, 16, 15, 0)
    mon_8pm = datetime(2026, 11, 16, 20, 0)
    sun_1pm = datetime(2026, 11, 22, 13, 0)
    for day in range(16, 23):                                   # every day of the week
        assert not world.pub_open(datetime(2026, 11, day, 8, 59))
        assert world.pub_open(datetime(2026, 11, day, 9, 0))
        assert world.pub_open(datetime(2026, 11, day, 23, 59))
        assert not world.pub_open(datetime(2026, 11, day, 0, 0))
    assert world.pub_open(mon_3pm) and world.pub_open(mon_8pm) and world.pub_open(sun_1pm)
    assert world.routine("Dez Whitworth", datetime(2026, 11, 16, 8, 0))[0] == "Cash and carry, Openshaw"
    assert world.routine("Dez Whitworth", mon_8pm)[0] == world.PUB
    assert world.routine("Jess Hartley", mon_8pm) == (world.PUB, "working the bar")
    assert world.routine("Raj Patel", mon_3pm)[0].startswith("Patel's News")
    assert world.routine("Chloe Barlow", mon_3pm)[1] == "at work"
    assert world.routine("Tommy Shaw", datetime(2026, 11, 16, 3, 0))[1] == "asleep"


def test_presence_filters_who_can_talk(db):
    with connect(db) as c:
        agents = [dict(r) for r in c.execute("SELECT * FROM agents")]
    names = {a["name"].split()[0] for a in world.present_in_pub(agents, datetime(2026, 11, 16, 20, 30))}  # Monday 20:30
    assert names == {"Dez", "Jess", "Tommy", "Maxine"}
    assert world.present_in_pub(agents, datetime(2026, 11, 16, 8, 30)) == []      # before opening
    assert {a["name"].split()[0] for a in world.present_in_pub(agents, datetime(2026, 11, 16, 10, 0))} == {"Dez"}


def test_update_routines_writes_locations(db):
    changes = tick.update_routines(datetime(2026, 11, 16, 20, 30), db)
    assert len(changes) == len(CHARACTERS)
    with connect(db) as c:
        assert c.execute("SELECT activity FROM agents WHERE name='Dez Whitworth'").fetchone()[0] == "behind the bar"
    assert tick.update_routines(datetime(2026, 11, 16, 20, 31), db) == []   # idempotent


def test_scheduled_events_are_delivered_once(db):
    base = datetime(2026, 11, 16, 12, 0)  # Monday
    seed_events(db, base)
    with connect(db) as c:
        at = c.execute("SELECT at FROM scheduled_events WHERE seed_key='northgate-figures'").fetchone()[0]
    assert at == "2026-11-19 09:00"                      # Thursday 9am
    assert tick.deliver_events(datetime(2026, 11, 17, 12, 0), db) == 0   # Tuesday: nothing yet
    assert tick.deliver_events(datetime(2026, 11, 18, 11, 0), db) == 1   # Wednesday 11:00: Raj's phone call
    assert tick.deliver_events(datetime(2026, 11, 19, 8, 59), db) == 0
    assert tick.deliver_events(datetime(2026, 11, 19, 9, 0), db) == 1    # Thursday 09:00: Dez's letter
    assert tick.deliver_events(datetime(2026, 11, 19, 9, 5), db) == 0
    with connect(db) as c:
        row = c.execute("SELECT content, source FROM facts WHERE subject='lease' AND source='observed'").fetchone()
    assert "£3,900" in row[0]


class FakePromiseClient:
    def __init__(self, done=True, invalid=False):
        self.done, self.invalid, self.calls = done, invalid, 0

    def propose(self, agent_id, messages, schema=None, max_tokens=None):
        self.calls += 1
        assert schema is PromiseCheck
        assert "Did you actually do it" not in messages[0]["content"] or True
        if self.invalid:
            raise InvalidProposal("bad")
        return PromiseCheck(done=self.done, what_happened="I rang them; they said a letter is on its way.", mood="relieved")


def test_legacy_due_promises_lapse_without_model_calls(db):
    now = datetime(2026, 11, 17, 12, 0)
    with connect(db) as c:
        c.execute("INSERT INTO commitments (agent_id, to_agent_id, content, due_at) VALUES (1,3,'Ring the agent','2026-11-17 10:00')")
        c.execute("INSERT INTO commitments (agent_id, content, due_at) VALUES (1,'Sort the quiz','2026-11-30 10:00')")
        c.execute("INSERT INTO commitments (agent_id, content) VALUES (1,'Keep an eye out')")
    client = FakePromiseClient(done=True)
    assert tick.check_due_promises(client, now, db) == 1
    assert client.calls == 0
    with connect(db) as c:
        rows = c.execute('SELECT status,lapsed_at FROM commitments ORDER BY id').fetchall()
        assert rows[0]['status'] == 'open' and rows[0]['lapsed_at']
        assert not rows[1]['lapsed_at'] and not rows[2]['lapsed_at']
        assert c.execute("SELECT count(*) FROM facts WHERE subject='promise' AND agent_id=3").fetchone()[0] == 1


def test_unanswerable_legacy_promise_never_moves_deadline(db):
    now = datetime(2026, 11, 17, 12, 0)
    with connect(db) as c:
        c.execute("INSERT INTO commitments (agent_id, content, due_at) VALUES (3,'Write quiz questions','2026-11-17 10:00')")
    client = FakePromiseClient(invalid=True)
    assert tick.check_due_promises(client, now, db) == 1
    assert client.calls == 0
    with connect(db) as c:
        status, due, lapsed = c.execute('SELECT status,due_at,lapsed_at FROM commitments').fetchone()
    assert status == 'open' and due == '2026-11-17 10:00' and lapsed


def test_conversation_due_respects_gap(db):
    now = datetime(2026, 11, 16, 20, 0)
    assert tick.conversation_due(now, 20, db)
    with connect(db) as c:
        c.execute("INSERT INTO conversations (location, status, sim_time) VALUES ('pub', 'completed', ?)",
                  (world.describe(now - timedelta(minutes=5)),))
    assert not tick.conversation_due(now, 20, db)
    assert tick.conversation_due(now + timedelta(minutes=16), 20, db)


def test_settings_persist_in_the_database(db):
    assert world.get_setting("auto", "0", db) == "0"
    world.set_setting("auto", "1", db)
    world.set_setting("gap_minutes", 30, db)
    assert world.get_setting("auto", "0", db) == "1"
    assert world.get_setting("gap_minutes", "20", db) == "30"
