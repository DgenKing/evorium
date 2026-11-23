from datetime import datetime,timedelta
from evorium import calendar_uk as cal,world,places,tick
from evorium.db import init_db,connect,npc_agents
from evorium.seed import seed_agents,CHARACTERS


def test_requested_dates_and_payday():
    for stamp in ['2026-12-25','2026-12-28','2027-01-01','2027-03-26','2027-03-29','2027-05-03','2027-05-31','2027-08-30']:
        assert cal.bank_holiday(datetime.fromisoformat(stamp))
    assert str(cal.payday(2026,11))=='2026-11-30'
    assert str(cal.payday(2027,5))=='2027-05-28' # Monday month-end is a bank holiday
    assert cal.payday_evening(datetime(2026,12,4,22)) # Friday after November payday
    assert not cal.payday_evening(datetime(2026,12,5,22))
    assert '32 days to Christmas' in cal.context(datetime(2026,11,23))
    assert 'Bank holiday' in cal.context(datetime(2026,12,28))
    assert 'Bonfire Night' in cal.context(datetime(2026,11,5))
    assert 'Payday' in cal.context(datetime(2026,11,30))


def test_festive_hours_and_routines_never_in_closed_place():
    christmas=datetime(2026,12,25)
    assert not world.pub_open(christmas.replace(hour=11,minute=59))
    assert world.pub_open(christmas.replace(hour=12))
    assert world.pub_open(christmas.replace(hour=15,minute=59))
    assert not world.pub_open(christmas.replace(hour=16))
    assert not places.is_open('shop',christmas.replace(hour=12))
    for stamp in ['2026-12-26','2026-12-28','2027-01-01']:
        day=datetime.fromisoformat(stamp)
        assert not places.is_open('shop',day.replace(hour=8,minute=59))
        assert places.is_open('shop',day.replace(hour=9))
        assert not places.is_open('shop',day.replace(hour=16))
    assert not world.pub_open(datetime(2027,1,1,11))
    assert world.pub_open(datetime(2027,1,1,12))
    for day in (christmas,datetime(2026,12,26),datetime(2027,1,1)):
        for slot in range(48):
            at=day+timedelta(minutes=slot*30)
            for a in CHARACTERS:
                location,_=world.routine(a[0],at,{'jess.shifts':4})
                for key,place in places.REGISTRY.items():
                    if location==place:assert places.is_open(key,at), (a[0],at)


def test_payday_extends_only_a_free_evening_visit():
    friday=datetime(2026,12,4,22,45)
    assert world.routine('Tommy Shaw',friday)[0]==world.PUB
    assert world.routine('Tommy Shaw',friday+timedelta(days=7))[0]!=world.PUB
    assert world.routine('Mohammed "Mo" Iqbal',friday)[1]=='driving'
    assert world.routine('Jess Hartley',friday,{'jess.shifts':4})[1]=='working the bar'


def test_events_idempotent_observed_by_attendees_and_notice_later(tmp_path):
    path=tmp_path/'w.sqlite3';init_db(path);seed_agents(path)
    at=datetime(2026,12,5,12)
    tick.update_routines(at,path)
    with connect(path) as c:present={r['id'] for r in c.execute('SELECT * FROM agents WHERE location=?',(world.PUB,))}
    cal.maintain(at,path);cal.maintain(at,path)
    with connect(path) as c:
        assert c.execute("SELECT count(*) FROM timeline WHERE kind='world_event'").fetchone()[0]==2
        holders={r[0] for r in c.execute("SELECT agent_id FROM facts WHERE subject='calendar'")}
        assert holders==present
        assert c.execute("SELECT count(*) FROM notices WHERE place='pub'").fetchone()[0]==2


def test_raffle_winner_is_present_apc_and_stable(tmp_path):
    path=tmp_path/'w.sqlite3';init_db(path);seed_agents(path)
    at=datetime(2026,12,20,20)
    tick.update_routines(at,path)
    with connect(path) as c:people=[dict(r) for r in c.execute("SELECT * FROM agents WHERE kind='npc' AND location=?",(world.PUB,))]
    chosen=cal.raffle_winner(people,'2026-12-20')
    assert chosen and chosen==cal.raffle_winner(list(reversed(people)),'2026-12-20')
    assert cal.raffle_winner([{'kind':'player','name':'Rob'}],'2026-12-20') is None
    cal.maintain(at,path);cal.maintain(at,path)
    with connect(path) as c:
        assert world._get(c,'calendar:raffle_winner:2026')==str(chosen['id'])
        assert c.execute("SELECT count(*) FROM timeline WHERE text LIKE '%won the Billet Christmas raffle%'").fetchone()[0]==1
        assert {r[0] for r in c.execute("SELECT agent_id FROM facts WHERE content LIKE '%won the Billet Christmas raffle%'")}=={p['id'] for p in people}


def test_late_restart_does_not_invent_a_past_raffle_attendance(tmp_path):
    path=tmp_path/'w.sqlite3';init_db(path);seed_agents(path)
    at=datetime(2026,12,21,20);tick.update_routines(at,path);cal.maintain(at,path)
    with connect(path) as c:
        assert world._get(c,'calendar:raffle_winner:2026') is None
        assert 'draw was missed' in c.execute("SELECT text FROM timeline WHERE text LIKE '%raffle draw was missed%'").fetchone()[0]
