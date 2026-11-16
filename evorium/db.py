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
)


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
