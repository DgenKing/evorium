"""SQLite connections and ordered, transactional schema migrations."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DEFAULT_DB_PATH = Path(os.environ.get("EVORIUM_DB_PATH") or Path(__file__).resolve().parent.parent / "evorium.sqlite3")

# Append migrations; never edit one after it has been applied to a saved world.
# PRAGMA user_version records how many migrations have been applied.
MIGRATIONS = (
    (
        """CREATE TABLE agents (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            age INTEGER NOT NULL CHECK (age >= 0),
            occupation TEXT NOT NULL,
            background TEXT NOT NULL,
            personality TEXT NOT NULL,
            current_goal TEXT NOT NULL,
            mood TEXT NOT NULL,
            location TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        )""",
        """CREATE TABLE conversations (
            id INTEGER PRIMARY KEY,
            location TEXT NOT NULL,
            started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            ended_at TEXT,
            status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed'))
        )""",
        """CREATE TABLE messages (
            id INTEGER PRIMARY KEY,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id),
            speaker_id INTEGER NOT NULL REFERENCES agents(id),
            text TEXT NOT NULL,
            rationale TEXT NOT NULL,
            sim_time TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        )""",
        """CREATE TABLE llm_calls (
            id INTEGER PRIMARY KEY,
            agent_id INTEGER NOT NULL REFERENCES agents(id),
            model TEXT NOT NULL,
            input_tokens INTEGER NOT NULL CHECK (input_tokens >= 0),
            output_tokens INTEGER NOT NULL CHECK (output_tokens >= 0),
            est_cost_usd REAL NOT NULL CHECK (est_cost_usd >= 0),
            ok INTEGER NOT NULL CHECK (ok IN (0, 1)),
            error TEXT,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        )""",
        """CREATE TABLE memories (
            id INTEGER PRIMARY KEY,
            agent_id INTEGER NOT NULL REFERENCES agents(id),
            content TEXT NOT NULL,
            importance INTEGER NOT NULL CHECK (importance BETWEEN 1 AND 10),
            source_conversation_id INTEGER NOT NULL REFERENCES conversations(id),
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        )""",
        "CREATE INDEX messages_conversation ON messages(conversation_id, id)",
        "CREATE INDEX memories_agent ON memories(agent_id, id)",
    ),
    # Migration 2: structured knowledge, commitments, NPC registry, world clock.
    (
        """CREATE TABLE facts (
            id INTEGER PRIMARY KEY,
            agent_id INTEGER NOT NULL REFERENCES agents(id),
            subject TEXT NOT NULL,
            content TEXT NOT NULL,
            source TEXT NOT NULL CHECK (source IN ('seed', 'observed', 'told', 'claim')),
            source_agent_id INTEGER REFERENCES agents(id),
            source_conversation_id INTEGER REFERENCES conversations(id),
            seed_key TEXT UNIQUE,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        )""",
        "CREATE INDEX facts_agent ON facts(agent_id, id)",
        """CREATE TABLE commitments (
            id INTEGER PRIMARY KEY,
            agent_id INTEGER NOT NULL REFERENCES agents(id),
            to_agent_id INTEGER REFERENCES agents(id),
            content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done', 'broken')),
            source_conversation_id INTEGER REFERENCES conversations(id),
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            resolved_at TEXT
        )""",
        "CREATE INDEX commitments_agent ON commitments(agent_id, status)",
        """CREATE TABLE npcs (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL,
            introduced_by INTEGER REFERENCES agents(id),
            source_conversation_id INTEGER REFERENCES conversations(id),
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        )""",
        """CREATE TABLE world (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )""",
        "ALTER TABLE conversations ADD COLUMN sim_time TEXT",
        "ALTER TABLE conversations ADD COLUMN summary TEXT",
        "ALTER TABLE conversations ADD COLUMN agent_a_id INTEGER REFERENCES agents(id)",
        "ALTER TABLE conversations ADD COLUMN agent_b_id INTEGER REFERENCES agents(id)",
    ),
    # Migration 3: real-time world — routines, promise deadlines, scheduled events.
    (
        "ALTER TABLE agents ADD COLUMN activity TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE commitments ADD COLUMN due_at TEXT",
        "ALTER TABLE commitments ADD COLUMN outcome TEXT",
        """CREATE TABLE scheduled_events (
            id INTEGER PRIMARY KEY,
            at TEXT NOT NULL,
            agent_id INTEGER NOT NULL REFERENCES agents(id),
            subject TEXT NOT NULL,
            content TEXT NOT NULL,
            delivered INTEGER NOT NULL DEFAULT 0,
            seed_key TEXT UNIQUE
        )""",
    ),
    # Migration 4: participant kinds and sortable simulation timestamps.
    (
        "ALTER TABLE agents ADD COLUMN kind TEXT NOT NULL DEFAULT 'npc' CHECK (kind IN ('npc','player','system'))",
        "ALTER TABLE conversations ADD COLUMN sim_at TEXT",
    ),
    # Migration 5: permanent timeline and daily digests.
    (
        """CREATE TABLE timeline (id INTEGER PRIMARY KEY, sim_at TEXT NOT NULL, kind TEXT NOT NULL,
        agent_id INTEGER REFERENCES agents(id), other_id INTEGER REFERENCES agents(id), text TEXT NOT NULL,
        importance INTEGER NOT NULL CHECK (importance BETWEEN 1 AND 5), conversation_id INTEGER REFERENCES conversations(id),
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))""",
        "CREATE INDEX timeline_sim_at ON timeline(sim_at)",
        """CREATE TABLE digests(day TEXT PRIMARY KEY, text TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))""",
    ),
    # Migration 6: directed relationships and their evidence.
    (
        """CREATE TABLE relationships(agent_id INTEGER REFERENCES agents(id),other_id INTEGER REFERENCES agents(id),
        trust INTEGER NOT NULL DEFAULT 50 CHECK(trust BETWEEN 0 AND 100),warmth INTEGER NOT NULL DEFAULT 50 CHECK(warmth BETWEEN 0 AND 100),
        familiarity INTEGER NOT NULL DEFAULT 0 CHECK(familiarity BETWEEN 0 AND 100),
        updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),PRIMARY KEY(agent_id,other_id))""",
        """CREATE TABLE relationship_events(id INTEGER PRIMARY KEY,agent_id INTEGER REFERENCES agents(id),other_id INTEGER REFERENCES agents(id),
        d_trust INTEGER,d_warmth INTEGER,reason TEXT NOT NULL,conversation_id INTEGER REFERENCES conversations(id),sim_at TEXT,
        created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))""",
    ),
    # Migration 7: validated daily plans, with explicit sim-day and retry state.
    (
        """CREATE TABLE plans(id INTEGER PRIMARY KEY,agent_id INTEGER NOT NULL REFERENCES agents(id),
        action TEXT CHECK(action IN ('visit','phone','stay_home')),place TEXT,person_id INTEGER REFERENCES agents(id),
        start_at TEXT,end_at TEXT,reason TEXT,fulfils_commitment_id INTEGER REFERENCES commitments(id),
        status TEXT DEFAULT 'planned' CHECK(status IN ('planned','active','done','missed','cancelled')),outcome TEXT,
        sim_day TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,
        created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))""",
        "CREATE INDEX plans_agent_day ON plans(agent_id,sim_day)",
    ),
    # Migration 8: distinguish seeded and director-origin events.
    ("ALTER TABLE scheduled_events ADD COLUMN origin TEXT NOT NULL DEFAULT 'seed'",),
    # Migration 9: fact importance (1 trivia … 5 harm/crime/big decision). Below 3 is hidden from prompts.
    (
        "ALTER TABLE facts ADD COLUMN importance INTEGER NOT NULL DEFAULT 3 CHECK (importance BETWEEN 1 AND 5)",
        "UPDATE facts SET importance=4 WHERE source='seed'",
        """UPDATE facts SET importance=5 WHERE source='observed' AND source_conversation_id IS NULL
           AND content IN (SELECT content FROM scheduled_events WHERE delivered=1 AND origin='seed')""",
        "CREATE INDEX facts_agent_importance ON facts(agent_id, importance, id)",
    ),
    # Migration 10: durable world ledger and visibility.
    (
        "ALTER TABLE scheduled_events ADD COLUMN delivered_at TEXT",
        "UPDATE scheduled_events SET delivered_at=at WHERE delivered=1",
        "CREATE TABLE stats(key TEXT PRIMARY KEY,value INTEGER NOT NULL,visible_to TEXT NOT NULL,updated_at TEXT NOT NULL)",
        "CREATE TABLE stat_changes(id INTEGER PRIMARY KEY,key TEXT NOT NULL,old INTEGER,new INTEGER,reason TEXT NOT NULL,sim_at TEXT NOT NULL,action_id INTEGER)",
        "CREATE TABLE offers(id INTEGER PRIMARY KEY,kind TEXT CHECK(kind IN ('surrender','renewal','loan','job')),from_id INTEGER REFERENCES agents(id),to_id INTEGER REFERENCES agents(id),amount INTEGER NOT NULL,terms TEXT NOT NULL,status TEXT CHECK(status IN ('open','accepted','refused','expired','withdrawn')),created_at TEXT NOT NULL,expires_at TEXT NOT NULL,resolved_at TEXT,source_action_id INTEGER)",
        "CREATE TABLE notices(id INTEGER PRIMARY KEY,place TEXT NOT NULL,text TEXT NOT NULL,by_id INTEGER REFERENCES agents(id),since TEXT NOT NULL,until TEXT,price_rise INTEGER NOT NULL DEFAULT 0)",
        "CREATE TABLE notice_seen(notice_id INTEGER REFERENCES notices(id),agent_id INTEGER REFERENCES agents(id),PRIMARY KEY(notice_id,agent_id))",
    ),
    # Migration 11: validated decisions and durable reaction queues.
    (
        "CREATE TABLE actions(id INTEGER PRIMARY KEY,agent_id INTEGER NOT NULL REFERENCES agents(id),key TEXT NOT NULL,args_json TEXT NOT NULL,reason TEXT NOT NULL,status TEXT CHECK(status IN ('considering','done','rejected')),trigger TEXT CHECK(trigger IN ('plan','conversation','reaction','player')),evidence TEXT NOT NULL,sim_at TEXT NOT NULL,conversation_id INTEGER REFERENCES conversations(id),result TEXT)",
        "CREATE INDEX actions_agent_time ON actions(agent_id,sim_at)",
        "CREATE TABLE asks(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,from_id INTEGER REFERENCES agents(id),to_id INTEGER REFERENCES agents(id),amount INTEGER,status TEXT NOT NULL DEFAULT 'open',created_at TEXT NOT NULL,expires_at TEXT NOT NULL,action_id INTEGER)",
        "CREATE TABLE reactions(id INTEGER PRIMARY KEY,agent_id INTEGER NOT NULL REFERENCES agents(id),reason TEXT NOT NULL,due_at TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',called_at TEXT,UNIQUE(agent_id,reason))",
        "CREATE TABLE memberships(kind TEXT NOT NULL,agent_id INTEGER REFERENCES agents(id),PRIMARY KEY(kind,agent_id))",
        "CREATE TABLE deferred_facts(id INTEGER PRIMARY KEY,agent_id INTEGER REFERENCES agents(id),source_id INTEGER REFERENCES agents(id),content TEXT NOT NULL,penalty INTEGER NOT NULL DEFAULT 0)",
    ),
    # Migration 12: Python-owned story outcomes.
    (
        "CREATE TABLE arcs(id INTEGER PRIMARY KEY,key TEXT UNIQUE NOT NULL,status TEXT CHECK(status IN ('active','resolved')),started_at TEXT NOT NULL,resolved_at TEXT,outcome TEXT,summary TEXT)",
    ),
    # Migration 13: returning player checkpoint and persistent summary cache.
    (
        "ALTER TABLE agents ADD COLUMN last_seen_at TEXT",
        "CREATE TABLE catchup_cache(cache_key TEXT PRIMARY KEY,text TEXT NOT NULL,created_at REAL NOT NULL)",
    ),
    # Migration 14: preserve the original player and add stable account ownership.
    (
        "ALTER TABLE agents ADD COLUMN account TEXT",
        "UPDATE agents SET account='owner' WHERE id=(SELECT min(id) FROM agents WHERE kind='player')",
        "CREATE UNIQUE INDEX agents_account ON agents(account) WHERE account IS NOT NULL",
    ),
    # Migration 15: evidence-backed promises; keep the original table and status CHECK intact.
    (
        "ALTER TABLE commitments ADD COLUMN kind TEXT CHECK(kind IN ('action','visit','talk','tell','make','pay','conditional','vague'))",
        "ALTER TABLE commitments ADD COLUMN target_json TEXT",
        "ALTER TABLE commitments ADD COLUMN made_at TEXT",
        "ALTER TABLE commitments ADD COLUMN retry_at TEXT",
        "ALTER TABLE commitments ADD COLUMN claimed_at TEXT",
        "ALTER TABLE commitments ADD COLUMN lapsed_at TEXT",
        "UPDATE commitments SET made_at=(SELECT sim_at FROM conversations WHERE id=commitments.source_conversation_id)",
        """CREATE TABLE promise_claims(id INTEGER PRIMARY KEY,
            commitment_id INTEGER NOT NULL REFERENCES commitments(id),
            agent_id INTEGER NOT NULL REFERENCES agents(id), said TEXT NOT NULL, sim_at TEXT NOT NULL,
            source_conversation_id INTEGER REFERENCES conversations(id),
            outcome TEXT NOT NULL DEFAULT 'pending' CHECK(outcome IN ('pending','supported','false')))""",
        "CREATE INDEX promise_claims_commitment ON promise_claims(commitment_id,outcome)",
        "CREATE INDEX commitments_due ON commitments(due_at) WHERE status='open' AND lapsed_at IS NULL",
    ),
    # Migration 16: Grace's reports, preserving every existing world row.
    (
        """CREATE TABLE cases(id INTEGER PRIMARY KEY, subject_id INTEGER NOT NULL REFERENCES agents(id),
            reported_by INTEGER REFERENCES agents(id), source_fact_id INTEGER REFERENCES facts(id),
            source_timeline_id INTEGER REFERENCES timeline(id), summary TEXT NOT NULL, opened_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','spoken_to','closed')),
            outcome TEXT CHECK(outcome IN ('advice','formal_warning','no_further_action')), closed_at TEXT,
            spoken_at TEXT, last_incident_at TEXT NOT NULL, last_attempt_day TEXT, last_looked_day TEXT)""",
        "CREATE UNIQUE INDEX cases_open_subject ON cases(subject_id) WHERE status!='closed'",
    ),
)

VISIBLE_IMPORTANCE = 3  # facts scored below this are kept in the database but never shown to characters


def npc_agents(connection):
    return [dict(r) for r in connection.execute("SELECT * FROM agents WHERE kind='npc' ORDER BY id")]


def system_id(connection):
    return connection.execute("SELECT id FROM agents WHERE kind='system'").fetchone()[0]


@contextmanager
def connect(db_path: str | Path = DEFAULT_DB_PATH) -> Iterator[sqlite3.Connection]:
    """Commit successful work, roll back failures, and always close connections."""
    connection = sqlite3.connect(db_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    with connect(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version > len(MIGRATIONS):
            raise RuntimeError("Database schema is newer than this Evorium version.")
        for index in range(version, len(MIGRATIONS)):
            for statement in MIGRATIONS[index]:
                connection.execute(statement)
            connection.execute(f"PRAGMA user_version = {index + 1}")
