import sqlite3

import pytest

from evorium.db import MIGRATIONS, connect, init_db
from evorium.seed import seed_agents


def test_schema_is_created_and_initialization_is_idempotent(tmp_path):
    path = tmp_path / "world.sqlite3"
    init_db(path)
    init_db(path)
    with connect(path) as connection:
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )}
        assert tables == {"agents", "messages", "conversations", "llm_calls", "memories",
                          "facts", "commitments", "npcs", "world", "scheduled_events", "timeline", "digests", "relationships", "relationship_events"}
        assert connection.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_restart_preserves_characters_and_changed_state(tmp_path):
    path = tmp_path / "world.sqlite3"
    init_db(path)
    seed_agents(path)
    with connect(path) as connection:
        original = [dict(row) for row in connection.execute("SELECT * FROM agents WHERE kind='npc' ORDER BY id")]
        assert [row["name"] for row in original] == [
            "Dez Whitworth", "Chloe Barlow", "Tommy Shaw", "Jess Hartley", "Raj Patel",
        ]
        connection.execute("UPDATE agents SET mood = 'relieved' WHERE id = ?", (original[0]["id"],))
    init_db(path)
    seed_agents(path)
    with connect(path) as connection:
        restored = [dict(row) for row in connection.execute("SELECT * FROM agents WHERE kind='npc' ORDER BY id")]
    original[0]["mood"] = "relieved"
    assert restored == original


def test_foreign_keys_and_rollback(tmp_path):
    path = tmp_path / "world.sqlite3"
    init_db(path)
    with pytest.raises(sqlite3.IntegrityError):
        with connect(path) as connection:
            connection.execute("INSERT INTO conversations (location, status) VALUES ('pub', 'running')")
            connection.execute(
                """INSERT INTO messages (conversation_id, speaker_id, text, rationale, sim_time)
                   VALUES (1, 999, 'Hello', 'Greeting', 'turn-1')"""
            )
    with connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 0


def test_newer_database_is_rejected(tmp_path):
    path = tmp_path / "world.sqlite3"
    init_db(path)
    with connect(path) as connection:
        connection.execute(f"PRAGMA user_version = {len(MIGRATIONS) + 1}")
    with pytest.raises(RuntimeError, match="newer"):
        init_db(path)
