"""What an agent knows, has been told, has promised — and how new knowledge is stored."""

import logging
import json
import sqlite3
from datetime import datetime, timedelta

from evorium.db import VISIBLE_IMPORTANCE
from evorium.models import Extraction
from evorium import timeline, relationships

DUE_FMT = "%Y-%m-%d %H:%M"

logger = logging.getLogger(__name__)

MAX_CERTAIN = 12
MAX_TOLD = 8
MAX_CLAIMS = 3
MAX_PROMISES = 6
MAX_RECENT = 3
MAX_FACTS_PER_SPEAKER = 3   # per conversation, after trivia is dropped
REPEAT_TOPIC_AFTER = 2      # a subject raised in this many conversations today counts as "already covered"
DEFAULT_DUE_HOURS = 72  # every promise gets a deadline, so the tick always checks it eventually


def _rows(connection, sql, params=()):
    return [dict(r) for r in connection.execute(sql, params).fetchall()]


def _mentions(text: str, name: str) -> bool:
    return name.split()[0].lower() in text.lower()


def open_commitments(connection: sqlite3.Connection, agent_id: int, limit=MAX_PROMISES) -> list[dict]:
    rows = _rows(connection,
        """SELECT c.*, a.name AS to_name
           FROM commitments c LEFT JOIN agents a ON a.id = c.to_agent_id
           WHERE c.agent_id = ? AND c.status = 'open' AND c.lapsed_at IS NULL ORDER BY c.id DESC LIMIT ?""",
        (agent_id, -1 if limit is None else limit))
    from evorium.promise_evidence import progress
    for p in rows:
        p['progress'] = progress(connection, p)
    return rows


def knowledge_for_prompt(connection: sqlite3.Connection, speaker: dict, listener: dict, now=None) -> dict:
    from evorium.plans import today
    from evorium import world
    now = now or world._real_now()
    sid, lid = speaker["id"], listener["id"]

    # Most important first, then most recent, so last week's crime outranks yesterday's small talk.
    certain = _rows(connection,
        """SELECT content FROM facts WHERE agent_id=? AND source IN ('seed','observed') AND importance>=?
           ORDER BY importance DESC, id DESC LIMIT ?""", (sid, VISIBLE_IMPORTANCE, MAX_CERTAIN))
    told = _rows(connection,
        """SELECT f.content, a.name AS by_name FROM facts f LEFT JOIN agents a ON a.id = f.source_agent_id
           WHERE f.agent_id=? AND f.source='told' AND f.importance>=? ORDER BY f.importance DESC, f.id DESC LIMIT 20""",
        (sid, VISIBLE_IMPORTANCE))
    # Then prefer what the listener told me or what concerns them (stable sort keeps importance order within each group).
    told.sort(key=lambda t: not ((t["by_name"] and t["by_name"] == listener["name"]) or _mentions(t["content"], listener["name"])))
    told = told[:MAX_TOLD]
    claims = _rows(connection,
        "SELECT content FROM facts WHERE agent_id=? AND source='claim' AND importance>=? ORDER BY importance DESC, id DESC LIMIT ?",
        (sid, VISIBLE_IMPORTANCE, MAX_CLAIMS))
    promises = open_commitments(connection, sid)
    their_promises = _rows(connection,
        "SELECT content || ' — due ' || coalesce(due_at,'unspecified') AS content FROM commitments WHERE agent_id=? AND to_agent_id=? AND status='open' AND lapsed_at IS NULL ORDER BY id DESC LIMIT 4",
        (lid, sid))
    people = _rows(connection,
        """SELECT n.name, n.description FROM npcs n
           WHERE n.introduced_by = ? OR EXISTS (
               SELECT 1 FROM facts f WHERE f.agent_id = ? AND lower(f.content) LIKE '%' || lower(n.name) || '%')
           ORDER BY n.id DESC LIMIT 4""", (sid, sid))
    last_with = connection.execute(
        """SELECT summary, sim_time FROM conversations
           WHERE summary IS NOT NULL AND ((agent_a_id=? AND agent_b_id=?) OR (agent_a_id=? AND agent_b_id=?))
           ORDER BY id DESC LIMIT 1""", (sid, lid, lid, sid)).fetchone()
    recent = _rows(connection,
        "SELECT content FROM memories WHERE agent_id=? ORDER BY id DESC LIMIT ?", (sid, MAX_RECENT))

    rel = relationships.get(connection, sid, lid)
    reasons = [r[0] for r in connection.execute('SELECT reason FROM relationship_events WHERE agent_id=? AND other_id=? ORDER BY id DESC LIMIT 2',(sid,lid))]
    broken = [r[0] for r in connection.execute("SELECT content FROM commitments WHERE agent_id=? AND to_agent_id=? AND status='broken' ORDER BY id DESC LIMIT 2",(lid,sid))]
    from evorium.economy import situation
    return {
        "situation": situation(connection, speaker, now),
        "plans": [f"{p['start_at']}: {p['action']} {p['place'] or ''} [{p['status']}] — {p['outcome'] or p['reason']}" for p in today(connection,sid,now)],
        "relationship": [relationships.describe(rel), *reasons],
        "broken_promises": broken,
        "certain": [c["content"] for c in certain],
        "told": [f'{t["content"]} (told to me by {t["by_name"] or "someone"})' for t in told],
        "claims": [c["content"] for c in claims],
        "promises": [p["content"] + (f" (to {p['to_name']})" if p["to_name"] else "") +
                     f" — due {p['due_at'] or 'unspecified'}; {p['progress']}" for p in promises],
        "their_promises": [p["content"] for p in their_promises],
        "people": [f'{p["name"]} — {p["description"]}' for p in people],
        "last_with_listener": (f'{last_with["sim_time"]}: {last_with["summary"]}' if last_with else None),
        "recent": [r["content"] for r in recent],
        "covered_today": covered_today(connection, sid, now),
    }


def covered_today(connection: sqlite3.Connection, agent_id: int, now) -> list[str]:
    """Subjects this person has already gone over in several conversations today, so they move on."""
    day = now.strftime("%Y-%m-%d")
    rows = connection.execute(
        """SELECT f.subject, COUNT(DISTINCT f.source_conversation_id) AS times FROM facts f
           JOIN conversations v ON v.id = f.source_conversation_id
           WHERE f.agent_id=? AND substr(v.sim_at,1,10)=? GROUP BY f.subject HAVING times>=?
           ORDER BY times DESC LIMIT 4""", (agent_id, day, REPEAT_TOPIC_AFTER)).fetchall()
    return [f"{r['subject']} (talked about in {r['times']} conversations today)" for r in rows]


def store_extraction(connection: sqlite3.Connection, conversation_id: int, participants: dict[str, dict],
                     extraction: Extraction, now: datetime | None = None) -> dict:
    """Persist facts, commitments and new people. Returns counts for the live feed."""
    now = now or datetime.now()
    counts = {"facts": 0, "trivia": 0, "commitments": 0, "people": 0, "resolved": 0, "updated": 0}
    restated: set[int] = set()
    all_agents = {r["name"]: r["id"] for r in connection.execute("SELECT id, name FROM agents")}
    first_names = {n.split()[0].lower(): i for n, i in all_agents.items()}

    def agent_id_for(name: str | None) -> int | None:
        if not name:
            return None
        return all_agents.get(name) or first_names.get(name.split()[0].lower())

    feelings_applied = set()
    for name, ext in extraction.per_agent.items():
        me = agent_id_for(name)
        if me is None or name not in participants and me not in {p["id"] for p in participants.values()}:
            continue
        from evorium import actions, economy
        if ext.decision:
            actor = dict(connection.execute('SELECT * FROM agents WHERE id=?', (me,)).fetchone())
            transcript = [dict(r) for r in connection.execute('SELECT speaker_id,text FROM messages WHERE conversation_id=?', (conversation_id,))]
            actions.propose(connection, actor, ext.decision, now, 'conversation', conversation_id, transcript)
        feeling = ext.feeling
        if me not in feelings_applied and feeling and feeling.reason.strip() and (feeling.trust_change or feeling.warmth_change):
            feelings_applied.add(me)
            other = next(p['id'] for p in participants.values() if p['id'] != me)
            relationships.adjust(connection,me,other,feeling.trust_change*2,feeling.warmth_change*2,feeling.reason,now,conversation_id)
        worth_keeping = sorted((f for f in ext.facts if f.importance >= VISIBLE_IMPORTANCE),
                               key=lambda f: -f.importance)[:MAX_FACTS_PER_SPEAKER]
        counts["trivia"] = counts.get("trivia", 0) + len(ext.facts) - len(worth_keeping)
        for f in worth_keeping:
            told_by = agent_id_for(f.told_by)
            if told_by == me or told_by not in {p["id"] for p in participants.values()}:
                told_by = None
            source = f.source
            # A 'told' fact with no identifiable teller inside the conversation is just a claim.
            if source == "told" and told_by is None:
                source = "claim"
            connection.execute(
                """INSERT INTO facts (agent_id, subject, content, source, source_agent_id, source_conversation_id, importance)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (me, f.subject.lower(), f.content, source, told_by, conversation_id, f.importance))
            if source == 'told' and 'raj' in f.content.lower() and any(word in f.content.lower() for word in ('accepted', 'surrender', 'sold', 'handover')):
                for pending in connection.execute('SELECT * FROM deferred_facts WHERE agent_id=? AND penalty<0', (me,)).fetchall():
                    relationships.adjust(connection, me, pending['source_id'], pending['penalty'], 0, pending['content'], now, conversation_id)
                    connection.execute('DELETE FROM deferred_facts WHERE id=?', (pending['id'],))
            if f.importance == 5:
                economy.schedule(connection, me, f"Important conversation {conversation_id}", now)
            if source == "claim":
                timeline.record(connection, now, 'rumour', f"{name}: {f.content}", 3, me, conversation_id=conversation_id)
            elif f.importance == 5 and not counts.get("serious"):
                counts["serious"] = 1   # one timeline entry per incident, not one per point of view
                timeline.record(connection, now, 'serious', f"{name}: {f.content}", 4, me, conversation_id=conversation_id)
            counts["facts"] += 1
        for c in ext.commitments:
            from evorium.promise_evidence import validate_target
            actor = dict(connection.execute('SELECT * FROM agents WHERE id=?', (me,)).fetchone())
            kind, target = validate_target(connection, actor, c.kind, c.target)
            due_at = (now + timedelta(hours=c.due_hours or DEFAULT_DUE_HOURS)).strftime(DUE_FMT)
            if c.replaces is not None:
                # Same promise restated with more detail or a new deadline: update it rather than add a duplicate.
                cur = connection.execute(
                    "UPDATE commitments SET content=?, due_at=?, to_agent_id=COALESCE(?, to_agent_id), kind=?, target_json=?, retry_at=NULL "
                    "WHERE id=? AND agent_id=? AND status='open' AND lapsed_at IS NULL",
                    (c.content, due_at, agent_id_for(c.to), kind, json.dumps(target), c.replaces, me))
                if cur.rowcount:
                    restated.add(c.replaces)
                    timeline.record(connection, now, 'promise_updated', f"{name}: {c.content}", 2, me, agent_id_for(c.to), conversation_id)
                    counts["updated"] += 1
                    schedule_promise(connection, c.replaces, now)
                    continue
            cid = connection.execute(
                "INSERT INTO commitments (agent_id, to_agent_id, content, source_conversation_id, due_at, kind, target_json, made_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (me, agent_id_for(c.to), c.content, conversation_id, due_at, kind, json.dumps(target), now.strftime(DUE_FMT))).lastrowid
            schedule_promise(connection, cid, now)
            timeline.record(connection, now, 'promise_made', f"{name} promised: {c.content}", 2, me, agent_id_for(c.to), conversation_id)
            counts["commitments"] += 1
        for p in ext.new_people:
            if agent_id_for(p.name) is not None:
                continue  # not new — it's one of the cast
            cur = connection.execute(
                """INSERT INTO npcs (name, description, introduced_by, source_conversation_id)
                   VALUES (?, ?, ?, ?) ON CONFLICT(name) DO NOTHING""",
                (p.name, p.description, me, conversation_id))
            counts["people"] += cur.rowcount
    participant_ids = tuple(p["id"] for p in participants.values())
    for cid in extraction.commitments_done:
        if cid in restated:
            continue  # restated in this conversation, so it is plainly not finished
        row = connection.execute("SELECT * FROM commitments WHERE id=?", (cid,)).fetchone()
        if row and row['agent_id'] in participant_ids:
            owner_kind = connection.execute('SELECT kind FROM agents WHERE id=?', (row['agent_id'],)).fetchone()[0]
            if owner_kind == 'npc':
                said = ' '.join(r[0] for r in connection.execute(
                    'SELECT text FROM messages WHERE conversation_id=? AND speaker_id=? ORDER BY id',
                    (conversation_id, row['agent_id']))) or 'Reported completed in conversation.'
                record_claim(connection, cid, row['agent_id'], said, now, conversation_id)
            else:
                counts['resolved'] += resolve_commitment(connection, cid, 'done', 'Reported completed in conversation.', now, conversation_id)
    return counts


KEPT_TRUST = 8
KEPT_WARMTH = 2
BROKEN_TRUST = -12
BROKEN_WARMTH = -4
FALSE_CLAIM_TRUST = -20
FALSE_CLAIM_WARMTH = -6


def schedule_promise(c, cid, now):
    from evorium import economy
    p = c.execute('SELECT * FROM commitments WHERE id=?', (cid,)).fetchone()
    if c.execute("SELECT kind FROM agents WHERE id=?", (p['agent_id'],)).fetchone()[0] != 'npc':
        return
    hours = max(1, (datetime.strptime(p['due_at'], DUE_FMT) - now).total_seconds() / 3600 - 24)
    economy.schedule(c, p['agent_id'], f"Promise {cid} due {p['due_at']}", now, hours)


def record_claim(c, cid, agent_id, said, now, conversation_id=None):
    """A report is a claim, even when evidence might later support it."""
    p = c.execute("SELECT * FROM commitments WHERE id=? AND agent_id=? AND status='open' AND lapsed_at IS NULL",
                  (cid, agent_id)).fetchone()
    if not p:
        return 0
    if conversation_id is not None and c.execute('SELECT 1 FROM promise_claims WHERE commitment_id=? AND source_conversation_id=?',
                                                (cid, conversation_id)).fetchone():
        return 0
    c.execute('INSERT INTO promise_claims(commitment_id,agent_id,said,sim_at,source_conversation_id) VALUES (?,?,?,?,?)',
              (cid, agent_id, said, now.strftime(DUE_FMT), conversation_id))
    c.execute('UPDATE commitments SET claimed_at=? WHERE id=?', (now.strftime(DUE_FMT), cid))
    timeline.record(c, now, 'promise_claim', f"Completion claimed, awaiting evidence: {p['content']}", 2, agent_id, p['to_agent_id'], conversation_id)
    return 1


def lapse_commitment(c, p, now, reason):
    cur = c.execute("UPDATE commitments SET lapsed_at=?,outcome=? WHERE id=? AND status='open' AND lapsed_at IS NULL",
                    (now.strftime(DUE_FMT), reason, p['id']))
    if not cur.rowcount:
        return 0
    name = c.execute('SELECT name FROM agents WHERE id=?', (p['agent_id'],)).fetchone()[0]
    text = f"{name}'s promise lapsed: {p['content']}. {reason}"
    timeline.record(c, now, 'promise_lapsed', text, 3, p['agent_id'], p['to_agent_id'])
    if p['to_agent_id']:
        c.execute("INSERT INTO facts(agent_id,subject,content,source,importance) VALUES (?,'promise',?,'observed',3)",
                  (p['to_agent_id'], text))
    return 1


def resolve_commitment(connection, cid, status, outcome, now, conversation_id=None, *, evidence_until=None):
    """Idempotent outcomes. APC completion always requires world evidence."""
    row = connection.execute("SELECT c.*, a.name, a.kind AS owner_kind FROM commitments c JOIN agents a ON a.id=c.agent_id WHERE c.id=? AND c.status='open' AND c.lapsed_at IS NULL", (cid,)).fetchone()
    if not row:
        return 0
    false_claim = False
    cutoff = evidence_until or now.strftime(DUE_FMT)
    if row['owner_kind'] == 'npc':
        from evorium.promise_evidence import evidence_for
        evidence = evidence_for(connection, dict(row) | {'evidence_until': cutoff})
        if status == 'done':
            if not evidence:
                return 0
            outcome = f"World records confirm completion ({len(evidence)} supporting record(s))."
        elif status == 'broken':
            false_claim = connection.execute("SELECT 1 FROM promise_claims WHERE commitment_id=? AND outcome='pending' AND sim_at<=?", (cid, cutoff)).fetchone() is not None
            outcome = ('Completion was claimed, but world records show no matching completion.' if false_claim else
                       'No matching completion in world records despite an opportunity before the deadline.')
        else:
            raise ValueError('Use lapse_commitment for neutral lapses.')
    changed = connection.execute("UPDATE commitments SET status=?, outcome=?, resolved_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=? AND status='open' AND lapsed_at IS NULL", (status, outcome, cid))
    if not changed.rowcount:
        return 0
    if row['owner_kind'] == 'npc' and (status == 'done' or false_claim):
        connection.execute("UPDATE promise_claims SET outcome=? WHERE commitment_id=? AND outcome='pending' AND sim_at<=?",
                           ('supported' if status == 'done' else 'false', cid, cutoff))
    text = f"{row['name']} {'kept' if status == 'done' else 'broke'} a promise: {row['content']} — {outcome}"
    timeline.record(connection, now, 'promise_kept' if status == 'done' else 'promise_broken',
                    text, 3 if status == 'done' else 4, row['agent_id'], row['to_agent_id'], conversation_id)
    if false_claim:
        timeline.record(connection, now, 'promise_false_claim', text, 4, row['agent_id'], row['to_agent_id'], conversation_id)
    if row['to_agent_id']:
        trust, warmth = ((KEPT_TRUST, KEPT_WARMTH) if status == 'done' else
                         (FALSE_CLAIM_TRUST, FALSE_CLAIM_WARMTH) if false_claim else (BROKEN_TRUST, BROKEN_WARMTH))
        relationships.adjust(connection, row['to_agent_id'], row['agent_id'], trust, warmth, text, now, conversation_id)
        fact_text = text
        if row['owner_kind'] == 'player':
            fact_text = (f"{row['name']} did what they promised: {row['content']}" if status == 'done' else
                         f"{row['name']} promised to {row['content']} and didn't.")
        connection.execute("INSERT INTO facts(agent_id,subject,content,source,importance) VALUES (?,'promise',?,'observed',4)",
                           (row['to_agent_id'], fact_text))
    if row['owner_kind'] == 'npc':
        connection.execute("INSERT INTO facts(agent_id,subject,content,source,importance) VALUES (?,'promise',?,'observed',4)",
                           (row['agent_id'], text))
    return 1
