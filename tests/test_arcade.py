from datetime import datetime, timedelta, timezone

import pytest

from evorium import arcade, memory, places, scene, seed, sim, tick, world
from evorium.db import connect, init_db
from evorium.models import ActionProposal, Extraction


@pytest.fixture
def db(tmp_path):
    path = tmp_path / 'arcade.sqlite3'
    init_db(path)
    seed.seed_agents(path)
    return path


@pytest.mark.parametrize('start', [datetime(2026, 3, 2, tzinfo=timezone.utc),
                                  datetime(2026, 10, 5, tzinfo=timezone.utc)])
def test_shift_coverage_over_eight_weeks_including_clock_change(start):
    for minute in range(0, 8 * 7 * 1440, 5):
        at = (start + timedelta(minutes=minute)).astimezone(world.TZ).replace(tzinfo=None)
        active = [name for name in arcade.STAFF if world.routine(name, at)[1].startswith('working the change booth')]
        assert active == [arcade.on_shift(at)]
        assert len(arcade.staff_present(at)) == (2 if arcade.handover(at) else 1)
        assert places.is_open('arcade', at)
    monday = datetime(2026, 11, 23, 7)
    assert arcade.on_shift(monday) == arcade.NORMAN
    assert arcade.on_shift(monday + timedelta(days=7)) == arcade.MAXINE
    assert arcade.on_shift(monday + timedelta(hours=12)) == arcade.MAXINE
    # At the weekly swap the outgoing night worker continues into the day.
    assert arcade.on_shift(monday - timedelta(minutes=5)) == arcade.NORMAN
    for offset in (-10, 0, 9):
        for hour in (0, 12):
            at = monday + timedelta(minutes=offset, hours=hour)
            assert all(world.routine(name, at)[0] == places.REGISTRY['arcade'] for name in arcade.STAFF)
            assert not any(world.is_free(name, at) for name in arcade.STAFF)


def test_christmas_and_bad_day_leave_arcade_open_with_shut_booth(db):
    now = datetime(2026, 12, 25, 7)
    on = arcade.on_shift(now)
    bad = {'kind':'off_sick','name':on}
    with connect(db) as c:
        import json
        for key,value in {'anchor_sim':now.strftime(world.FMT),'anchor_real':now.strftime(world.FMT),'speed':0,
                          'bad_days:2026-12-25':json.dumps({'1':bad})}.items():
            world._set(c,key,value)
    tick.update_routines(now, db)
    snapshot = scene.snapshot(db, real_at=now.replace(tzinfo=timezone.utc))
    assert places.is_open('arcade', now, {'_weather':{'raining':True}})
    assert places.is_open('arcade', datetime(2026, 12, 25, 2))
    assert snapshot['arcade_booth_open'] is False
    assert world.routine(on, now, {'_bad_days':{on:bad}})[0] == world.home_location(on)


def test_arcade_conversation_and_meeting_promise(db, monkeypatch):
    at = datetime(2026, 11, 27, 21, 10)
    monkeypatch.setattr(world, 'now', lambda *_: at)
    tick.update_routines(at, db)
    group = {a['name']:a for a in places.present(at, db)['arcade']}
    assert {'Liam Byrne', arcade.MAXINE} <= group.keys()
    maxine, liam = group[arcade.MAXINE], group['Liam Byrne']
    class Fake:
        def propose(self, *args, schema=ActionProposal, **kwargs):
            if len(args)>2:
                schema=args[2]
            return Extraction(summary='They met at the arcade.') if schema is Extraction else ActionProposal(
                say='Fancy a game?',rationale='Offline test.',mood='friendly')
    with connect(db) as c:
        extraction = Extraction.model_validate({'summary':'A plan','per_agent':{maxine['name']:{
            'commitments':[{'content':'Meet at the arcade','to':liam['name'],'kind':'talk','due_hours':2,
                            'target':{'person':liam['name'],'place':'arcade'}}]}}})
        memory.store_extraction(c, None, {maxine['name']:maxine, liam['name']:liam}, extraction, at-timedelta(hours=1))
        promise = dict(c.execute('SELECT * FROM commitments').fetchone())
    cid = sim.run_conversation(Fake(),maxine['id'],liam['id'],2,db,location=places.REGISTRY['arcade'])
    from evorium.promise_evidence import evidence_for
    with connect(db) as c:
        assert evidence_for(c,promise)[0]['id'] == cid


def test_existing_seed_appends_staff_once(tmp_path, monkeypatch):
    path = tmp_path / 'old-world.sqlite3'
    init_db(path)
    with monkeypatch.context() as old:
        old.setattr(seed,'CHARACTERS',seed.CHARACTERS[:18])
        old.setattr(seed,'SEED_FACTS',tuple(row for row in seed.SEED_FACTS if row[0] not in arcade.STAFF))
        seed.seed_agents(path)
    with connect(path) as c:
        c.execute("UPDATE agents SET current_goal='Keep the saved goal' WHERE id=1")
        before = dict(c.execute('SELECT name,id FROM agents'))
    seed.seed_agents(path)
    seed.seed_agents(path)
    with connect(path) as c:
        after = dict(c.execute('SELECT name,id FROM agents'))
        assert set(after)-set(before) == set(arcade.STAFF)
        assert {name:after[name] for name in before} == before
        assert c.execute('SELECT current_goal FROM agents WHERE id=1').fetchone()[0] == 'Keep the saved goal'
        assert c.execute("SELECT count(*) FROM facts WHERE seed_key LIKE 'Norman Pilling|%'").fetchone()[0] == 4
        assert c.execute("SELECT count(*) FROM facts WHERE seed_key LIKE 'Maxine Stott|%'").fetchone()[0] == 4
