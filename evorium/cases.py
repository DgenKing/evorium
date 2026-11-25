"""Grace's proportionate report follow-ups. Scheduling and validation are Python-owned."""
import re
from datetime import datetime, timedelta
from evorium import world, timeline, accounts, places
from evorium.db import connect, DEFAULT_DB_PATH
from evorium.memory import DUE_FMT

GRACE = 'Grace Adeyemi'
OUTCOME_ACTIONS = ('give_advice', 'give_formal_warning')


def grace(c):
    r = c.execute("SELECT * FROM agents WHERE name=? AND kind='npc'", (GRACE,)).fetchone()
    return dict(r) if r else None


def on_beat(now):
    return (now.weekday() < 5 and 8 <= now.hour < 17) or (now.weekday() in (4, 5) and 17 <= now.hour < 24)


def active(c, subject_id):
    r = c.execute("SELECT * FROM cases WHERE subject_id=? AND status!='closed'", (subject_id,)).fetchone()
    return dict(r) if r else None


def report_subjects(c, fact):
    """Conservative named-actor grammar; mentions of a victim or vague fears aren't reports."""
    text = fact['content']
    for a in c.execute("SELECT * FROM agents WHERE kind IN ('npc','player') AND name!=?", (GRACE,)):
        first = a['name'].split()[0]
        actor = r'\b(?:' + re.escape(a['name']) + '|' + re.escape(first) + r')\b'
        # Require the named person to be the actor, not just somewhere in a story about harm.
        deed = (r"\s+(?:(?:has|had)\s+)?(?:been\s+)?(?:threaten(?:ed|s|ing)?|attack(?:ed|s)?|assault(?:ed|s)?|"
                r"hit|punched|hurt|harmed|struck)\b|\s+made\s+(?:a\s+)?threats?\b|[’']s\s+threats?\b|"
                r"\s+(?:said|says|told\s+me)\s+[\"'‘“]?(?:he|she|I|they)\s+(?:would|will|was\s+going\s+to)\s+"
                r"(?:break\s+(?:my|his|her|your)\s+jaw|shoot|kill|hurt|harm)\b")
        if re.search(actor + '(?:' + deed + ')', text, re.I):
            # Explicit negation is not an incident; avoid reports of hypothetical future behaviour.
            if re.search(r"\b(?:if|whether)\s+" + actor, text, re.I):
                continue
            yield dict(a)


def scan(c, now):
    g = grace(c)
    if not g:
        return
    checkpoint = int(world._get(c, 'cases_fact_checkpoint', '0'))
    rows = c.execute("""SELECT f.*,v.sim_at AS incident_at FROM facts f
        LEFT JOIN conversations v ON v.id=f.source_conversation_id
        WHERE f.agent_id=? AND f.id>? ORDER BY f.id""", (g['id'], checkpoint)).fetchall()
    for f in rows:
        if f['importance'] != 5 or f['source'] not in ('told', 'observed'):
            continue
        if f['source'] == 'told' and f['source_agent_id'] is None:
            continue
        for subject in report_subjects(c, f):
            incident = f['incident_at'] or now.strftime(DUE_FMT)
            existing = active(c, subject['id'])
            if existing:
                c.execute('UPDATE cases SET last_incident_at=max(last_incident_at,?) WHERE id=?', (incident, existing['id']))
                continue
            reporter = c.execute('SELECT name FROM agents WHERE id=?', (f['source_agent_id'],)).fetchone()
            label = f"{reporter['name']} reported" if f['source'] == 'told' else 'Grace observed'
            summary = f"{label}: {f['content']}"[:400]
            cid = c.execute('''INSERT INTO cases(subject_id,reported_by,source_fact_id,summary,opened_at,last_incident_at)
                VALUES (?,?,?,?,?,?)''', (subject['id'], f['source_agent_id'], f['id'], summary, incident, incident)).lastrowid
            timeline.record(c, now, 'case', f"Case #{cid}: Grace opened a report about {subject['name']}: {f['content'][:400]}", 4, g['id'], subject['id'])
    if rows:
        world._set(c, 'cases_fact_checkpoint', rows[-1]['id'])


def followup_line(c, speaker, listener):
    if speaker['name'] != GRACE:
        return []
    case = active(c, listener['id'])
    if not case:
        return []
    return [f"You have an open report about {listener['name']} to follow up: {case['summary']} "
            "Hear their account; owning it and an apology may merit advice; denial or repeating threats may merit a formal warning. "
            "Say your decision clearly. Advice or a formal warning only; no arrests, courts or other punishments."]


def menu(c, speaker, listener):
    return speaker['name'] == GRACE and active(c, listener['id']) is not None


def outcome_case(c, actor, person, conversation_id):
    if actor['name'] != GRACE or conversation_id is None:
        raise ValueError('Grace must speak her decision in the subject’s conversation.')
    conv = c.execute("SELECT * FROM conversations WHERE id=? AND status='running'", (conversation_id,)).fetchone()
    if not conv or actor['id'] not in (conv['agent_a_id'], conv['agent_b_id']):
        raise ValueError('This is not Grace’s conversation.')
    sid = conv['agent_b_id'] if conv['agent_a_id'] == actor['id'] else conv['agent_a_id']
    subject = c.execute('SELECT * FROM agents WHERE id=?', (sid,)).fetchone()
    if person not in (subject['name'], subject['name'].split()[0]):
        raise ValueError('The decision must concern the person Grace is talking to.')
    case = active(c, sid)
    if not case:
        raise ValueError('There is no open case about this person.')
    return case


def finish(c, case, outcome, now):
    g = grace(c)
    subject = c.execute('SELECT name FROM agents WHERE id=?', (case['subject_id'],)).fetchone()[0]
    phrase = {'advice': 'words of advice', 'formal_warning': 'a formal warning', 'no_further_action': 'no further action'}[outcome]
    text = (f"PCSO Grace Adeyemi closed the report about {subject} with {phrase}. Report: {case['summary']}")
    changed = c.execute("UPDATE cases SET status='closed',outcome=?,closed_at=? WHERE id=? AND status!='closed'", (outcome, now.strftime(DUE_FMT), case['id']))
    if not changed.rowcount:
        return text
    timeline.record(c, now, 'serious', text, 4, g['id'], case['subject_id'])
    personal = (f"PCSO Grace Adeyemi gave me {phrase} about the report: {case['summary']}" if outcome != 'no_further_action'
                else 'PCSO Grace Adeyemi closed my report with no further action.')
    facts = [(case['subject_id'], personal, 'observed'), (g['id'], text, 'observed')]
    if case['reported_by']:
        facts.append((case['reported_by'], f"Grace has spoken to {subject}; the outcome was {phrase}. Report: {case['summary']}", 'told'))
    for aid, content, source in facts:
        c.execute('''INSERT INTO facts(agent_id,subject,content,source,source_agent_id,importance)
            VALUES (?,'police follow-up',?,?,?,4)''', (aid, content, source, g['id']))
    return text


def spoken(c, conversation_id, now):
    g = grace(c)
    if not g:
        return
    conv = c.execute('SELECT * FROM conversations WHERE id=?', (conversation_id,)).fetchone()
    if g['id'] not in (conv['agent_a_id'], conv['agent_b_id']):
        return
    sid = conv['agent_b_id'] if conv['agent_a_id'] == g['id'] else conv['agent_a_id']
    if c.execute('SELECT 1 FROM messages WHERE conversation_id=? AND speaker_id=?', (conversation_id, g['id'])).fetchone():
        case = active(c, sid)
        if case and case['status'] == 'open':
            timeline.record(c, now, 'case', f"Case #{case['id']}: Grace spoke to the subject; follow-up remains open.", 3, g['id'], sid, conversation_id)
        c.execute("UPDATE cases SET status='spoken_to',spoken_at=coalesce(spoken_at,?) WHERE subject_id=? AND status!='closed'", (now.strftime(DUE_FMT), sid))


def maintain(now, db_path=DEFAULT_DB_PATH):
    with connect(db_path) as c:
        c.execute('BEGIN IMMEDIATE')
        scan(c, now)
        for case in c.execute("SELECT * FROM cases WHERE status='spoken_to'").fetchall():
            since = max(case['spoken_at'], case['last_incident_at'])
            if now >= datetime.strptime(since, DUE_FMT) + timedelta(days=3):
                finish(c, dict(case), 'no_further_action', now)


def engaged(c, agent_id):
    # Follow-ups never take someone out of any still-open player chat, including idle reservations.
    return c.execute("SELECT 1 FROM conversations WHERE status='running' AND (agent_a_id=? OR agent_b_id=?)", (agent_id, agent_id)).fetchone() is not None


def priority(c, ids, now):
    g = grace(c)
    if not g or g['id'] not in ids or not on_beat(now) or engaged(c, g['id']):
        return None
    for case in c.execute("SELECT * FROM cases WHERE status!='closed' AND coalesce(last_attempt_day,'')!=? ORDER BY id", (now.strftime('%Y-%m-%d'),)):
        subject = c.execute('SELECT * FROM agents WHERE id=?', (case['subject_id'],)).fetchone()
        if (case['subject_id'] in ids and not engaged(c, case['subject_id'])
                and world.is_free(subject['name'], now) and subject['location'] == g['location']):
            return g['id'], case['subject_id']
    return None


def player_view(c, player_id):
    rows = [dict(r) for r in c.execute('SELECT id,status,outcome FROM cases WHERE subject_id=? ORDER BY id DESC', (player_id,))]
    # Only until she has actually spoken to them; after that the case waits for her decision quietly.
    return {'notice': 'PCSO Grace Adeyemi wants a word' if any(r['status'] == 'open' for r in rows) else '',
            'outcomes': [r['outcome'].replace('_', ' ') for r in rows if r['outcome']]}


def approach(client, now, db_path=DEFAULT_DB_PATH):
    """One ordinary dialogue call; use the existing player-first conversation representation."""
    from evorium import player, sim, backoff
    from evorium.llm import DailyBudgetReached, PacingWait
    from evorium.memory import knowledge_for_prompt
    from evorium.prompts import build_messages
    if not on_beat(now) or backoff.paused():
        return False
    with player.lock:
        present = places.present(now, db_path)
        with connect(db_path) as c:
            c.execute('BEGIN IMMEDIATE')
            g = grace(c)
            if not g or engaged(c, g['id']):
                return False
            place = next((k for k, people in present.items() if any(p['id'] == g['id'] for p in people)), None)
            if not place:
                return False
            g['location'] = places.REGISTRY[place]
            day = now.strftime('%Y-%m-%d')
            for case in c.execute("""SELECT v.*,a.account FROM cases v JOIN agents a ON a.id=v.subject_id
                    WHERE a.kind='player' AND v.status!='closed' ORDER BY v.id""").fetchall():
                me = sim._agent(c, case['subject_id'])
                if world._get(c, accounts.setting_key('player_place', me['account']), '') != place:
                    if case['last_looked_day'] != day:
                        c.execute('UPDATE cases SET last_looked_day=? WHERE id=?', (day, case['id']))
                        c.execute("""INSERT INTO facts(agent_id,subject,content,source,source_agent_id,importance)
                            VALUES (?,'police visit','PCSO Grace Adeyemi came looking for you and wants a word.','observed',?,4)""", (me['id'], g['id']))
                    continue
                if case['last_attempt_day'] == day or c.execute("SELECT 1 FROM conversations WHERE agent_a_id=? AND status='running'", (me['id'],)).fetchone():
                    continue
                cid = c.execute("""INSERT INTO conversations(location,status,sim_time,sim_at,agent_a_id,agent_b_id)
                    VALUES (?,'running',?,?,?,?)""", (g['location'], world.describe(now), now.strftime(DUE_FMT), me['id'], g['id'])).lastrowid
                c.execute('UPDATE cases SET last_attempt_day=? WHERE id=?', (day, case['id']))
                knowledge = knowledge_for_prompt(c, g, me, now)
                break
            else:
                return False
        try:
            proposal = client.propose(g['id'], build_messages(g, me, [], knowledge, world.describe(now)), max_tokens=300)
        except (PacingWait, DailyBudgetReached):
            with connect(db_path) as c:
                c.execute('UPDATE cases SET last_attempt_day=? WHERE id=?', (case['last_attempt_day'], case['id']))
            sim._set_status(db_path, cid, 'failed')
            raise
        except Exception:
            sim._set_status(db_path, cid, 'failed')
            raise
        with connect(db_path) as c:
            c.execute('INSERT INTO messages(conversation_id,speaker_id,text,rationale,sim_time) VALUES (?,?,?,?,?)',
                      (cid, g['id'], proposal.say, proposal.rationale, world.describe(now)))
            c.execute('UPDATE agents SET mood=? WHERE id=?', (proposal.mood.lower(), g['id']))
        return True
