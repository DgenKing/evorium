"""Story outcomes belong to Python; the model can only narrate the result."""
from datetime import datetime, timedelta
from pydantic import BaseModel, ConfigDict, Field
from evorium import economy as e, timeline, world, backoff
from evorium.db import connect, npc_agents, system_id
from evorium.memory import DUE_FMT
from evorium.llm import LLMError
from evorium.events import emit

TEMPLATES = [
    {'key': 'darts_league', 'days': 14, 'stat': 'mo.darts_signups', 'target': 6,
     'person': 'Mohammed', 'fact': 'The local darts league needs six signups within two weeks.'},
    {'key': 'chloe_flat', 'days': 21, 'stat': 'chloe.flat_found', 'target': 1,
     'person': 'Chloe', 'fact': 'Chloe has three weeks to find a flat she can afford; Northgate can arrange a viewing through Simon.'},
]


class Narration(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    text: str = Field(min_length=1, max_length=1600)


def resolve(c, arc, outcome, summary, now):
    cur = c.execute("UPDATE arcs SET status='resolved',resolved_at=?,outcome=?,summary=? WHERE id=? AND status='active'", (now.strftime(DUE_FMT), outcome, summary, arc['id']))
    if not cur.rowcount:
        return
    timeline.record(c, now, 'arc', summary, 5)
    for a in npc_agents(c):
        e.fact(c, a['id'], summary, now, 5)
    emit(summary)


def maintain(now, db_path, client=None):
    pending = None
    with connect(db_path) as c:
        s = e.stats(c)
        for arc in c.execute("SELECT * FROM arcs WHERE status='active'").fetchall():
            outcome = None
            if arc['key'] == 'northgate':
                renewal = c.execute("SELECT * FROM offers WHERE kind='renewal' AND status='accepted' ORDER BY id DESC LIMIT 1").fetchone()
                raj = c.execute("SELECT * FROM offers WHERE kind='surrender' ORDER BY id DESC LIMIT 1").fetchone()
                if raj and raj['status'] not in ('accepted', 'refused', 'expired'):
                    raj = None
                if s.get('pub.closed'):
                    outcome = 'pub_bust' if world._get(c, 'pub_bust') else 'pub_closed'
                    summary = ('The Billet ran out of money and closed.' if outcome == 'pub_bust' else 'The Billet’s lease ended without a renewal, and the pub closed.') + ' Dez and Jess must find a new start. The neighbours will remember what happened.'
                elif renewal and raj:
                    outcome = 'renewed'
                    summary = f"Dez renewed the Billet's lease at £{renewal['amount']:,} a month. Raj's surrender offer was {raj['status']}. The terrace moves on with the consequences of their choices."
                else:
                    unresolved = c.execute("SELECT * FROM offers WHERE kind='renewal' AND status IN ('refused','expired') ORDER BY id DESC LIMIT 1").fetchone()
                    if unresolved and raj and not renewal and not world._get(c, 'northgate_answer_due'):
                        due = (now + timedelta(days=14)).strftime(DUE_FMT)
                        world._set(c, 'northgate_answer_due', due)
                        dez = c.execute("SELECT id FROM agents WHERE name LIKE 'Dez %'").fetchone()[0]
                        e.fact(c, dez, 'There are fourteen days to reopen talks with Northgate; otherwise the pub will close when the lease ends.', now)
                        e.schedule(c, dez, 'Find an answer for the pub', now)
            else:
                template = next(t for t in TEMPLATES if t['key'] == arc['key'])
                deadline = datetime.strptime(arc['started_at'], DUE_FMT) + timedelta(days=template['days'])
                value = s.get(template['stat'], 0)
                if value >= template['target'] or now >= deadline:
                    outcome = 'succeeded' if value >= template['target'] else 'missed_deadline'
                    summary = (f"Mo's darts team {'found its six players' if outcome == 'succeeded' else 'missed the league deadline'}." if arc['key'] == 'darts_league' else f"Chloe {'found a flat she could afford' if outcome == 'succeeded' else 'needs more time to find an affordable flat'}.")
            if outcome:
                # Commit the deterministic fallback before optional narration/network I/O.
                resolve(c, arc, outcome, summary, now)
                pending = (arc['id'], outcome, summary)
    if client and not backoff.paused():
        with connect(db_path) as c:
            # A deterministic tick may have resolved the arc while calls were paused.
            for arc in c.execute("SELECT * FROM arcs WHERE status='resolved' ORDER BY id"):
                if not world._get(c, f"arc_narrated:{arc['id']}"):
                    pending = (arc['id'], arc['outcome'], arc['summary'])
                    world._set(c, f"arc_narrated:{arc['id']}", '1')
                    break
            else:
                pending = None
    if pending and client and not backoff.paused():
        aid, outcome, summary = pending
        try:
            with connect(db_path) as c:
                sid = system_id(c)
            result = client.propose(sid, [{'role': 'user', 'content': 'Write 3–4 plain sentences about how this story ended. Narration only: do not add events, figures, people or decisions. Return JSON {"text":"..."}. Facts: ' + summary}], schema=Narration, max_tokens=300)
        except LLMError:
            return
        with connect(db_path) as c:
            # Keep canonical outcome facts in the entry even if narration gets creative.
            text = summary + '\n' + result.text
            c.execute('UPDATE arcs SET summary=? WHERE id=?', (text, aid))
            c.execute("UPDATE timeline SET text=? WHERE kind='arc' AND text=?", (text, summary))


def start_next(now, db_path):
    """Called only by the director; templates supply facts, never model-written state."""
    with connect(db_path) as c:
        if c.execute("SELECT 1 FROM arcs WHERE status='active'").fetchone():
            return False
        last = c.execute('SELECT resolved_at FROM arcs ORDER BY resolved_at DESC LIMIT 1').fetchone()
        if not last or now < datetime.strptime(last[0], DUE_FMT) + timedelta(days=2):
            return False
        for t in TEMPLATES:
            if c.execute('SELECT 1 FROM arcs WHERE key=?', (t['key'],)).fetchone():
                continue
            c.execute("INSERT INTO arcs(key,status,started_at) VALUES (?,'active',?)", (t['key'], now.strftime(DUE_FMT)))
            if t['stat'] not in e.stats(c):
                e.change(c, t['stat'], 0, t['fact'], now)
            actor = next(a for a in npc_agents(c) if a['name'].split()[0] == t['person'])
            e.fact(c, actor['id'], t['fact'], now, 5)
            timeline.record(c, now, 'arc', t['fact'], 4, actor['id'])
            if t['key'] == 'chloe_flat':
                deadline = (now + timedelta(days=t['days'])).strftime(DUE_FMT)
                world._set(c, 'chloe_flat_deadline', deadline)
                c.execute('INSERT OR IGNORE INTO stats VALUES (?,?,?,?)', ('chloe.flat_budget', 900, 'Chloe', now.strftime(DUE_FMT)))
                simon = next(a for a in npc_agents(c) if a['name'].split()[0] == 'Simon')
                qid = c.execute("INSERT INTO asks(kind,from_id,to_id,amount,created_at,expires_at) VALUES ('flat_viewing',?,?,?,?,?)", (simon['id'], actor['id'], 850, now.strftime(DUE_FMT), deadline)).lastrowid
                c.execute("INSERT INTO scheduled_events(at,agent_id,subject,content,origin) VALUES (?,?,? ,?,'director')", ((now + timedelta(hours=2)).strftime(DUE_FMT), actor['id'], 'flat', 'Simon Ferris has arranged a viewing of a Northgate flat within your budget. You can answer his invitation.'))
                e.schedule(c, actor['id'], f'Flat viewing invitation {qid}', now, 4)
            return True
    return False
