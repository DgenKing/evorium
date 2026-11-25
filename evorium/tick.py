"""The world tick: deterministic bookkeeping that runs every few real seconds, no matter the speed.

- moves characters along their routines
- delivers scheduled world events as observed facts
- checks promises against database evidence (no model calls)
- starts a conversation when it's time and two people are in the pub
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from evorium import world, timeline, places, economy
from evorium.db import DEFAULT_DB_PATH, connect, npc_agents
from evorium.events import emit
from evorium.memory import DUE_FMT, resolve_commitment

logger = logging.getLogger(__name__)
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
                    world._set(connection, f"scene.travel.{a['id']}", json.dumps({
                        'from': a['location'], 'to': loc, 'started': datetime.now(timezone.utc).timestamp(),
                    }))
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
    """Resolve bounded due APC promises using game records, never a model's answer."""
    from evorium.memory import lapse_commitment
    from evorium.promise_evidence import evidence_for, effective_promise, had_chance, made_at, validate_target, _target
    handled = 0
    with connect(db_path) as c:
        c.execute('BEGIN IMMEDIATE')
        due = [dict(r) for r in c.execute(
            """SELECT p.* FROM commitments p JOIN agents a ON a.id=p.agent_id
            WHERE a.kind='npc' AND p.status='open' AND p.lapsed_at IS NULL AND p.due_at IS NOT NULL
            AND coalesce(p.retry_at,p.due_at)<=? ORDER BY coalesce(p.retry_at,p.due_at),p.id LIMIT ?""",
            (now.strftime(DUE_FMT), MAX_PROMISE_CHECKS_PER_TICK))]
        for p in due:
            # Use the scheduled deadline/retry, even if the heartbeat arrives late.
            cutoff = p['retry_at'] or p['due_at']
            p['evidence_until'] = cutoff
            actor = dict(c.execute('SELECT * FROM agents WHERE id=?', (p['agent_id'],)).fetchone())
            kind, _ = validate_target(c, actor, p['kind'], _target(p))
            effective = effective_promise(c, p) if kind != 'vague' else p
            if kind == 'vague' or not made_at(c, p):
                lapse_commitment(c, p, now, 'This promise cannot be verified; no completion was established.')
            elif effective is None:
                lapse_commitment(c, p, now, 'The condition was not established by world records; no penalty.')
            elif evidence_for(c, p):
                resolve_commitment(c, p['id'], 'done', '', now, evidence_until=cutoff)
            elif c.execute("SELECT 1 FROM promise_claims WHERE commitment_id=? AND outcome='pending' AND sim_at<=?", (p['id'], cutoff)).fetchone():
                resolve_commitment(c, p['id'], 'broken', '', now, evidence_until=cutoff)
            elif had_chance(c, effective, cutoff):
                resolve_commitment(c, p['id'], 'broken', '', now, evidence_until=cutoff)
            elif not p['retry_at']:
                retry = (datetime.strptime(p['due_at'], DUE_FMT) + timedelta(days=1)).strftime(DUE_FMT)
                c.execute('UPDATE commitments SET retry_at=? WHERE id=?', (retry, p['id']))
            else:
                lapse_commitment(c, p, now, 'No full hour of opportunity before the deadline or its retry; no penalty.')
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
