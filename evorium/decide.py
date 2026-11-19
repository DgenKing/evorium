"""Persisted, bounded reactions to concrete changes in a character's life."""
import json
from datetime import datetime, timedelta
from evorium import actions, economy, relationships
from evorium.db import DEFAULT_DB_PATH, connect
from evorium.memory import DUE_FMT
from evorium.llm import LLMError
from evorium.events import emit
from evorium.configuration import load

MAX_WORLD_CALLS = 12


def run(client, now, db_path=DEFAULT_DB_PATH):
    called = 0
    day = now.strftime('%Y-%m-%d')
    with connect(db_path) as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM reactions WHERE status='pending' AND due_at<=? ORDER BY due_at,id", (now.strftime(DUE_FMT),))]
    for r in rows:
        with connect(db_path) as c:
            # Also re-check the row under the write lock, so two callers cannot spend twice.
            c.execute('BEGIN IMMEDIATE')
            if not c.execute("SELECT 1 FROM reactions WHERE id=? AND status='pending'", (r['id'],)).fetchone():
                continue
            world_count = c.execute('SELECT count(*) FROM reactions WHERE substr(called_at,1,10)=?', (day,)).fetchone()[0]
            count = c.execute('SELECT count(*) FROM reactions WHERE agent_id=? AND substr(called_at,1,10)=?', (r['agent_id'], day)).fetchone()[0]
            urgent = c.execute("SELECT 1 FROM offers WHERE to_id=? AND status='open' AND expires_at<=?", (r['agent_id'], (now + timedelta(hours=48)).strftime(DUE_FMT))).fetchone()
            if world_count >= max(1, min(MAX_WORLD_CALLS, int(getattr(load(), 'REACTION_CALLS_PER_DAY', MAX_WORLD_CALLS)))) or count >= (2 if urgent else 1):
                tomorrow = (now + timedelta(days=1)).replace(hour=7, minute=0)
                c.execute('UPDATE reactions SET due_at=? WHERE id=?', (tomorrow.strftime(DUE_FMT), r['id']))
                continue
            actor = dict(c.execute('SELECT * FROM agents WHERE id=?', (r['agent_id'],)).fetchone())
            facts = [dict(f) for f in c.execute('SELECT id,content FROM facts WHERE agent_id=? AND importance>=4 ORDER BY id DESC LIMIT 12', (actor['id'],))]
            relations = [{k: rel[k] for k in ('name', 'trust', 'warmth')} for rel in relationships.for_card(c, actor['id'])]
            prompt = f'''Think as {actor['name']} would, about money, family, loyalty, pride and fear.
Personality: {actor['personality']}. Mood: {actor['mood']}. Goal: {actor['current_goal']}.
Now: {now.strftime(DUE_FMT)}. Trigger: {r['reason']}.
Situation: {json.dumps(economy.situation(c, actor, now))}
Important facts with ids: {json.dumps(facts)}
Relationships: {json.dumps(relations)}
Valid actions and argument schemas: {json.dumps(actions.candidates(c, actor, now))}
Most days do nothing. wait is always valid. Big decisions require evidence and sleeping on it: propose the same choice again after twelve hours.
Return JSON {{"action":"wait","args":{{}},"reason":"one sentence","evidence":[],"new_goal":null}}.'''
            c.execute("UPDATE reactions SET status='called',called_at=? WHERE id=?", (now.strftime(DUE_FMT), r['id']))
        called += 1
        try:
            result = client.propose(actor['id'], [{'role': 'user', 'content': prompt}], schema=actions.Decision, max_tokens=350)
        except LLMError:
            emit(f"{actor['name']} could not think through the news just now.", 'error')
            # Calls count even when they fail; leave other reactions pending for recovery.
            raise
        with connect(db_path) as c:
            c.execute('BEGIN IMMEDIATE')
            actions.propose(c, actor, result, now, 'reaction')
    return called
