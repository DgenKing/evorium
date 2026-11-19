"""The world tick: deterministic bookkeeping that runs every few real seconds, no matter the speed.

- moves characters along their routines
- delivers scheduled world events as observed facts
- checks promises that have come due (one cheap model call each)
- starts a conversation when it's time and two people are in the pub
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from evorium import world, timeline, places, economy
from evorium.db import DEFAULT_DB_PATH, connect, npc_agents
from evorium.events import emit
from evorium.llm import InvalidProposal, LLMError
from evorium.memory import DUE_FMT, resolve_commitment
from evorium.models import PromiseCheck
from evorium.prompts import build_promise_check_messages

logger = logging.getLogger(__name__)
PROMISE_CHECK_MAX_TOKENS = 200
MAX_PROMISE_CHECKS_PER_TICK = 2
DEFAULT_CONVERSATION_GAP_MIN = 20  # sim minutes between auto conversations


def _agents(connection) -> list[dict]:
    return npc_agents(connection)


def update_routines(now: datetime, db_path: str | Path = DEFAULT_DB_PATH) -> list[str]:
    """Set each agent's location/activity from their routine. Returns human-readable changes."""
    changes = []
    with connect(db_path) as connection:
        for a in _agents(connection):
            loc, act = world.whereabouts(a, now, db_path)
            if loc != a["location"] or act != a["activity"]:
                connection.execute("UPDATE agents SET location=?, activity=? WHERE id=?", (loc, act, a["id"]))
                if loc != a['location'] and (loc in places.REGISTRY.values() or a['location'] in places.REGISTRY.values()):
                    timeline.record(connection, now, 'arrival', f"{a['name']} → {act} ({loc})", 1, a['id'])
                a.update(location=loc, activity=act)
                changes.append(f"{a['name'].split()[0]} → {act} ({loc.split(',')[0]})")
            economy.observe(connection, a, now)
    return changes


def deliver_events(now: datetime, db_path: str | Path = DEFAULT_DB_PATH) -> int:
    delivered = 0
    with connect(db_path) as connection:
        rows = connection.execute(
            """SELECT e.id, e.agent_id, e.subject, e.content, e.origin, a.name FROM scheduled_events e
               JOIN agents a ON a.id = e.agent_id WHERE e.delivered = 0 AND e.at <= ? ORDER BY e.at""",
            (now.strftime(DUE_FMT),)).fetchall()
        for r in rows:
            # Story events matter; director nudges (a barrel going off) are ordinary news.
            importance = 5 if r["origin"] == "seed" else 3
            connection.execute("INSERT INTO facts (agent_id, subject, content, source, importance) VALUES (?, ?, ?, 'observed', ?)",
                               (r["agent_id"], r["subject"], r["content"], importance))
            connection.execute("INSERT INTO memories (agent_id, content, importance, source_conversation_id) "
                               "SELECT ?, ?, 8, id FROM conversations ORDER BY id LIMIT 1", (r["agent_id"], r["content"]))
            connection.execute("UPDATE scheduled_events SET delivered=1,delivered_at=? WHERE id=?", (now.strftime(DUE_FMT), r["id"]))
            timeline.record(connection, now, 'world_event', f"{r['name']}: {r['content']}", 5, r['agent_id'])
            emit(f"WORLD EVENT for {r['name']}: {r['content']}")
            if importance == 5:
                economy.schedule(connection, r["agent_id"], f"World news {r['id']}", now)
            delivered += 1
        economy.seed_offers(connection)
    return delivered


def check_due_promises(client, now: datetime, db_path: str | Path = DEFAULT_DB_PATH) -> int:
    """Ask characters whether they kept promises that have come due. Bounded per tick."""
    with connect(db_path) as connection:
        due = [dict(r) for r in connection.execute(
            """SELECT c.id, c.agent_id, c.content, c.due_at, t.name AS to_name
               FROM commitments c JOIN agents owner ON owner.id=c.agent_id LEFT JOIN agents t ON t.id = c.to_agent_id
               WHERE owner.kind='npc' AND c.status='open' AND c.due_at IS NOT NULL AND c.due_at <= ?
               ORDER BY c.due_at LIMIT ?""", (now.strftime(DUE_FMT), MAX_PROMISE_CHECKS_PER_TICK))]
        agents = {a["id"]: a for a in _agents(connection)}
    handled = 0
    for p in due:
        agent = agents[p["agent_id"]]
        loc, act = world.whereabouts(agent, now, db_path)
        messages = build_promise_check_messages(agent, p, world.describe(now), loc, act)
        try:
            result = client.propose(agent["id"], messages, schema=PromiseCheck, max_tokens=PROMISE_CHECK_MAX_TOKENS)
        except InvalidProposal:
            result = None
        except LLMError as exc:
            emit(f"Promise check skipped ({exc}).", "error")
            return handled
        with connect(db_path) as connection:
            if result is None:
                # Can't ask — push the deadline back a day rather than guess.
                later = (now + timedelta(days=1)).strftime(DUE_FMT)
                connection.execute("UPDATE commitments SET due_at=? WHERE id=?", (later, p["id"]))
                continue
            status = "done" if result.done else "broken"
            resolve_commitment(connection, p["id"], status, result.what_happened, now)
            connection.execute("INSERT INTO facts (agent_id, subject, content, source, importance) VALUES (?, 'promise', ?, 'observed', 4)",
                               (agent["id"], f"About my promise to {p['content'][0].lower() + p['content'][1:]}: {result.what_happened}"))
            connection.execute("UPDATE agents SET mood=? WHERE id=?", (result.mood.lower(), agent["id"]))
        emit(f"PROMISE {status.upper()} — {agent['name']}: \"{p['content']}\" → {result.what_happened}")
        handled += 1
    return handled


def conversation_due(now: datetime, gap_minutes: int, db_path: str | Path = DEFAULT_DB_PATH, location=None) -> bool:
    with connect(db_path) as connection:
        row = connection.execute(
            """SELECT v.sim_time, v.sim_at FROM conversations v LEFT JOIN agents a ON a.id=v.agent_a_id
            WHERE v.status IN ('completed','running') AND (a.kind='npc' OR a.id IS NULL)
            AND (? IS NULL OR v.location=?) ORDER BY v.id DESC LIMIT 1""",(location,location)).fetchone()
    if row is None or not (row["sim_at"] or row["sim_time"]):
        return True
    try:
        last = (datetime.strptime(row["sim_at"], DUE_FMT) if row["sim_at"] else
                datetime.strptime(row["sim_time"], "%A %d %B, %H:%M").replace(year=now.year))
    except ValueError:
        return True
    if not row["sim_at"] and last > now + timedelta(days=300):  # year boundary
        last = last.replace(year=now.year - 1)
    if last > now:  # history is "ahead" because the clock was fast-forwarded then snapped back to real time
        return True
    return now - last >= timedelta(minutes=gap_minutes)


def who_is_in_the_pub(now: datetime, db_path: str | Path = DEFAULT_DB_PATH) -> list[dict]:
    from evorium.places import present
    return present(now,db_path)["pub"]
