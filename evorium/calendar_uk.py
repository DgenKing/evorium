"""Fixed England holiday dates and fictional terrace events; no external calendar calls."""
from datetime import date,datetime,timedelta
import calendar
import hashlib
from evorium.db import connect,DEFAULT_DB_PATH

# Verified against https://www.gov.uk/bank-holidays on 23 Nov 2026. Extend this table for later years.
BANK_HOLIDAYS={
 '2026-01-01':"New Year's Day",'2026-04-03':'Good Friday','2026-04-06':'Easter Monday',
 '2026-05-04':'Early May bank holiday','2026-05-25':'Spring bank holiday','2026-08-31':'Summer bank holiday',
 '2026-12-25':'Christmas Day','2026-12-28':'Boxing Day substitute',
 '2027-01-01':"New Year's Day",'2027-03-26':'Good Friday','2027-03-29':'Easter Monday',
 '2027-05-03':'Early May bank holiday','2027-05-31':'Spring bank holiday','2027-08-30':'Summer bank holiday',
 '2027-12-27':'Christmas Day substitute','2027-12-28':'Boxing Day substitute',
}


def bank_holiday(at):return BANK_HOLIDAYS.get(at.strftime('%Y-%m-%d'))


def hours(place,at):
    md=(at.month,at.day)
    if place=='pub':
        if md==(12,25):return 12,16
        return (12,24) if md==(1,1) else (9,24)
    if place=='shop':
        if md==(12,25):return None
        if md==(12,26) or bank_holiday(at):return 9,16
        return (7,19) if at.weekday()<6 else None
    from evorium.place_registry import PLACES
    definition = PLACES.get(place)
    if not definition:
        return None
    if definition.holiday_hours is not None:
        if md == (12, 25):
            return None
        if bank_holiday(at) or md == (12, 26):
            return definition.holiday_hours
    return definition.hours


def payday(year,month):
    last=date(year,month,calendar.monthrange(year,month)[1])
    while last.weekday()>4 or bank_holiday(last):last-=timedelta(days=1)
    return last


def payday_evening(at):
    today=at.date()
    for month in (today.replace(day=1),today.replace(day=1)-timedelta(days=1)):
        pay=payday(month.year,month.month)
        friday=pay+timedelta(days=(4-pay.weekday())%7 or 7)
        if today in (pay,friday):return True
    return False


def context(at):
    christmas=date(at.year,12,25)
    if at.date()>christmas:christmas=date(at.year+1,12,25)
    tags=[]
    if bank_holiday(at):tags.append('Bank holiday: '+bank_holiday(at))
    if at.date()==payday(at.year,at.month):tags.append('Payday')
    if (at.month,at.day)==(12,24):tags.append('Christmas Eve')
    if (at.month,at.day)==(12,31):tags.append("New Year's Eve")
    if (at.month,at.day)==(11,5):tags.append('Bonfire Night')
    line=f"Today: {at.strftime('%A %d %B')}. {(christmas-at.date()).days} days to Christmas."
    return line+(' '+'; '.join(tags)+'.' if tags else '')


def state(at):
    return {'label':context(at),'bank_holiday':bank_holiday(at),'payday':at.date()==payday(at.year,at.month),
        'decorations':datetime(2026,12,5,12)<=at<datetime(2027,1,6),
        'raffle_tickets':datetime(2026,12,5,12)<=at<datetime(2026,12,20,20)}


EVENTS=(
 ('decorations','2026-12-05 12:00','The Christmas decorations went up in the Crooked Billet.'),
 ('tickets','2026-12-05 12:00','Christmas raffle tickets are on sale in the Crooked Billet; the draw is 20 December at 20:00.'),
 ('raffle','2026-12-20 20:00','Christmas raffle draw'),
 ('christmas_eve','2026-12-24 19:00','It is Christmas Eve: the Billet is having its festive evening.'),
 ('new_year_eve','2026-12-31 20:00',"It is New Year's Eve at the Crooked Billet."),
)


def raffle_winner(people,day):
    candidates=sorted((p for p in people if p['kind']=='npc'),key=lambda p:p['name'])
    if not candidates:return None
    number=int.from_bytes(hashlib.sha256(('raffle|'+day).encode()).digest()[:8],'big')
    return candidates[number%len(candidates)]


def maintain(now,db_path=DEFAULT_DB_PATH):
    from evorium import world,timeline
    from evorium.memory import DUE_FMT
    with connect(db_path) as c:
        c.execute('BEGIN IMMEDIATE')
        for key,stamp,text in EVENTS:
            at=datetime.strptime(stamp,DUE_FMT)
            marker='calendar:'+key+':2026'
            if now<at or world._get(c,marker):continue
            # Never award a past draw using a later day's attendance.
            people=[dict(r) for r in c.execute("SELECT * FROM agents WHERE kind='npc' AND location=?",(world.PUB,))] if now.date()==at.date() else []
            if key=='raffle':
                winner=raffle_winner(people,stamp[:10])
                text=(f"{winner['name']} won the Billet Christmas raffle." if winner else
                      'The Christmas raffle draw was missed; no winner was recorded.' if now.date()!=at.date() else
                      'No Christmas raffle winner was recorded: nobody was present for the draw.')
                if winner:world._set(c,'calendar:raffle_winner:2026',winner['id'])
            timeline.record(c,at,'world_event',text,3)
            for p in people:
                c.execute("INSERT INTO facts(agent_id,subject,content,source,importance) VALUES (?,'calendar',?,'observed',3)",(p['id'],text))
            if key in ('decorations','tickets'):
                until='2027-01-06 00:00' if key=='decorations' else '2026-12-20 20:00'
                nid=c.execute('INSERT INTO notices(place,text,since,until) VALUES (?,?,?,?)',('pub',text,stamp,until)).lastrowid
                for p in people:c.execute('INSERT OR IGNORE INTO notice_seen VALUES (?,?)',(nid,p['id']))
            world._set(c,marker,stamp)
