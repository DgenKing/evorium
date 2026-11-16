"""What an agent knows, has been told, has promised — and how new knowledge is stored."""

import logging
import sqlite3
from datetime import datetime, timedelta

from evorium.models import Extraction
from evorium import timeline, relationships

DUE_FMT = "%Y-%m-%d %H:%M"

logger = logging.getLogger(__name__)

MAX_CERTAIN = 12
MAX_TOLD = 8
MAX_CLAIMS = 3
MAX_PROMISES = 6
MAX_RECENT = 3
DEFAULT_DUE_HOURS = 72  # every promise gets a deadline, so the tick always checks it eventually


def _rows(connection, sql, params=()):
    return [dict(r) for r in connection.execute(sql, params).fetchall()]


def _mentions(text: str, name: str) -> bool:
    return name.split()[0].lower() in text.lower()


def open_commitments(connection: sqlite3.Connection, agent_id: int) -> list[dict]:
    return _rows(connection,
        """SELECT c.id, c.content, c.to_agent_id, a.name AS to_name, c.due_at
           FROM commitments c LEFT JOIN agents a ON a.id = c.to_agent_id
           WHERE c.agent_id = ? AND c.status = 'open' ORDER BY c.id DESC LIMIT ?""",
        (agent_id, MAX_PROMISES))


def knowledge_for_prompt(connection: sqlite3.Connection, speaker: dict, listener: dict) -> dict:
    sid, lid = speaker["id"], listener["id"]

    certain = _rows(connection,
        "SELECT content FROM facts WHERE agent_id=? AND source IN ('seed','observed') ORDER BY source DESC, id DESC LIMIT ?",
        (sid, MAX_CERTAIN))
    told = _rows(connection,
        """SELECT f.content, a.name AS by_name FROM facts f LEFT JOIN agents a ON a.id = f.source_agent_id
           WHERE f.agent_id=? AND f.source='told' ORDER BY f.id DESC LIMIT 20""", (sid,))
    # Prioritise what the listener told me or what concerns them, then most recent.
    told.sort(key=lambda t: not ((t["by_name"] and t["by_name"] == listener["name"]) or _mentions(t["content"], listener["name"])))
    told = told[:MAX_TOLD]
    claims = _rows(connection,
        "SELECT content FROM facts WHERE agent_id=? AND source='claim' ORDER BY id DESC LIMIT ?", (sid, MAX_CLAIMS))
    promises = open_commitments(connection, sid)
    their_promises = _rows(connection,
        "SELECT content FROM commitments WHERE agent_id=? AND to_agent_id=? AND status='open' ORDER BY id DESC LIMIT 4",
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
    return {
        "relationship": [relationships.describe(rel), *reasons],
        "broken_promises": broken,
        "certain": [c["content"] for c in certain],
        "told": [f'{t["content"]} (told to me by {t["by_name"] or "someone"})' for t in told],
        "claims": [c["content"] for c in claims],
        "promises": [p["content"] + (f" (to {p['to_name']})" if p["to_name"] else "") for p in promises],
        "their_promises": [p["content"] for p in their_promises],
        "people": [f'{p["name"]} — {p["description"]}' for p in people],
        "last_with_listener": (f'{last_with["sim_time"]}: {last_with["summary"]}' if last_with else None),
        "recent": [r["content"] for r in recent],
    }


def store_extraction(connection: sqlite3.Connection, conversation_id: int, participants: dict[str, dict],
                     extraction: Extraction, now: datetime | None = None) -> dict:
    """Persist facts, commitments and new people. Returns counts for the live feed."""
    now = now or datetime.now()
    counts = {"facts": 0, "commitments": 0, "people": 0, "resolved": 0, "updated": 0}
    restated: set[int] = set()
    all_agents = {r["name"]: r["id"] for r in connection.execute("SELECT id, name FROM agents")}
    first_names = {n.split()[0].lower(): i for n, i in all_agents.items()}

    def agent_id_for(name: str | None) -> int | None:
        if not name:
            return None
        return all_agents.get(name) or first_names.get(name.split()[0].lower())

    for name, ext in extraction.per_agent.items():
        me = agent_id_for(name)
        if me is None or name not in participants and me not in {p["id"] for p in participants.values()}:
            continue
        feeling = ext.feeling
        if feeling and feeling.reason.strip() and (feeling.trust_change or feeling.warmth_change):
            other = next(p['id'] for p in participants.values() if p['id'] != me)
            relationships.adjust(connection,me,other,feeling.trust_change*2,feeling.warmth_change*2,feeling.reason,now,conversation_id)
        for f in ext.facts:
            told_by = agent_id_for(f.told_by)
            if told_by == me or told_by not in {p["id"] for p in participants.values()}:
                told_by = None
            source = f.source
            # A 'told' fact with no identifiable teller inside the conversation is just a claim.
            if source == "told" and told_by is None:
                source = "claim"
            connection.execute(
                """INSERT INTO facts (agent_id, subject, content, source, source_agent_id, source_conversation_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (me, f.subject.lower(), f.content, source, told_by, conversation_id))
            if source == "claim":
                timeline.record(connection, now, 'rumour', f"{name}: {f.content}", 3, me, conversation_id=conversation_id)
            counts["facts"] += 1
        for c in ext.commitments:
            due_at = (now + timedelta(hours=c.due_hours or DEFAULT_DUE_HOURS)).strftime(DUE_FMT)
            if c.replaces is not None:
                # Same promise restated with more detail or a new deadline: update it rather than add a duplicate.
                cur = connection.execute(
                    "UPDATE commitments SET content=?, due_at=?, to_agent_id=COALESCE(?, to_agent_id) "
                    "WHERE id=? AND agent_id=? AND status='open'",
                    (c.content, due_at, agent_id_for(c.to), c.replaces, me))
                if cur.rowcount:
                    restated.add(c.replaces)
                    timeline.record(connection, now, 'promise_updated', f"{name}: {c.content}", 2, me, agent_id_for(c.to), conversation_id)
                    counts["updated"] += 1
                    continue
            connection.execute(
                "INSERT INTO commitments (agent_id, to_agent_id, content, source_conversation_id, due_at) VALUES (?, ?, ?, ?, ?)",
                (me, agent_id_for(c.to), c.content, conversation_id, due_at))
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
            counts['resolved'] += resolve_commitment(connection, cid, 'done', 'Reported completed in conversation.', now, conversation_id)
    return counts


def resolve_commitment(connection, cid, status, outcome, now, conversation_id=None):
    """One idempotent path for every promise outcome."""
    row = connection.execute("SELECT c.*, a.name FROM commitments c JOIN agents a ON a.id=c.agent_id WHERE c.id=? AND c.status='open'",(cid,)).fetchone()
    if not row: return 0
    connection.execute("UPDATE commitments SET status=?, outcome=?, resolved_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",(status,outcome,cid))
    timeline.record(connection, now, 'promise_kept' if status=='done' else 'promise_broken',
        f"{row['name']} {'kept' if status=='done' else 'broke'} a promise: {row['content']} — {outcome}",
        3 if status=='done' else 4, row['agent_id'], row['to_agent_id'], conversation_id)
    if row['to_agent_id']:
        relationships.adjust(connection,row['to_agent_id'],row['agent_id'],8 if status=='done' else -12,2 if status=='done' else -4,
            f"{'Kept' if status=='done' else 'Broke'} a promise: {row['content']} — {outcome}",now,conversation_id)
        if connection.execute("SELECT kind FROM agents WHERE id=?",(row['agent_id'],)).fetchone()[0]=='player':
            text=(f"{row['name']} did what they promised: {row['content']}" if status=='done' else f"{row['name']} promised to {row['content']} and didn't.")
            connection.execute("INSERT INTO facts(agent_id,subject,content,source) VALUES (?,'promise',?,'observed')",(row['to_agent_id'],text))
    return 1
