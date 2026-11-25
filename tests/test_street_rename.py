import sqlite3
from pathlib import Path

from evorium.db import MIGRATIONS, init_db


OLD = "Shuttle Street"
NEW = "Henry Street"


def test_migration_17_renames_saved_text_once_and_preserves_history(tmp_path):
    path = tmp_path / "old-world.sqlite3"
    connection = sqlite3.connect(path)
    for version, migration in enumerate(MIGRATIONS[:16], start=1):
        for step in migration:
            if callable(step):
                step(connection)
            else:
                connection.execute(step)
        connection.execute(f"PRAGMA user_version={version}")
    connection.execute(
        "INSERT INTO agents(name,age,occupation,background,personality,current_goal,mood,location) "
        "VALUES ('A',30,'x','from Shuttle Street','x','visit Shuttle Street','ok','Shuttle Street, Ancoats')"
    )
    connection.execute("INSERT INTO conversations(location,status,summary) VALUES ('Shuttle Street, Ancoats','completed','Met on Shuttle Street')")
    connection.execute("INSERT INTO messages(conversation_id,speaker_id,text,rationale,sim_time) VALUES (1,1,'Shuttle Street','Shuttle Street','now')")
    connection.execute("INSERT INTO memories(agent_id,content,importance,source_conversation_id) VALUES (1,'Remember Shuttle Street',4,1)")
    connection.execute("INSERT INTO facts(agent_id,subject,content,source) VALUES (1,'place','Shuttle Street','seed')")
    connection.execute("INSERT INTO commitments(agent_id,content,target_json) VALUES (1,'Go to Shuttle Street','{\"place\":\"Shuttle Street\"}')")
    connection.execute("INSERT INTO promise_claims(commitment_id,agent_id,said,sim_at) VALUES (1,1,'I went to Shuttle Street','now')")
    connection.execute("INSERT INTO scheduled_events(at,agent_id,subject,content) VALUES ('now',1,'Walk','Meet on Shuttle Street')")
    connection.execute("INSERT INTO timeline(sim_at,kind,text,importance) VALUES ('now','event','Shuttle Street',3)")
    connection.execute("INSERT INTO relationship_events(agent_id,other_id,reason) VALUES (1,1,'Shuttle Street')")
    connection.execute("INSERT INTO plans(agent_id,action,place,reason,sim_day) VALUES (1,'visit','Shuttle Street','Meet on Shuttle Street','today')")
    connection.execute("INSERT INTO offers(kind,amount,terms,status,created_at,expires_at) VALUES ('loan',1,'Shuttle Street','open','now','later')")
    connection.execute("INSERT INTO cases(subject_id,summary,opened_at,last_incident_at) VALUES (1,'Shuttle Street','now','now')")
    connection.execute("INSERT INTO actions(agent_id,key,args_json,reason,status,trigger,evidence,sim_at) VALUES (1,'visit','{\"place\":\"Shuttle Street\"}','Go to Shuttle Street','done','plan','At Shuttle Street','now')")
    connection.execute("INSERT INTO notices(place,text,since) VALUES ('Shuttle Street','At Shuttle Street','now')")
    connection.execute("INSERT INTO catchup_cache(cache_key,text,created_at) VALUES ('key','Meet on Shuttle Street',0)")
    connection.execute("INSERT INTO digests(day,text) VALUES ('today','Shuttle Street')")
    connection.execute("INSERT INTO npcs(name,description) VALUES ('Neighbour','Lives on Shuttle Street')")
    connection.execute("INSERT INTO world(key,value) VALUES ('place','Shuttle Street')")
    connection.commit()
    connection.close()

    init_db(path)
    connection = sqlite3.connect(path)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)
    for table, column in (("agents", "location"), ("agents", "background"), ("agents", "current_goal"),
                          ("conversations", "location"), ("conversations", "summary"), ("memories", "content"),
                          ("facts", "content"), ("commitments", "content"), ("commitments", "target_json"),
                          ("scheduled_events", "content"), ("relationship_events", "reason"), ("plans", "place"),
                          ("plans", "reason"), ("promise_claims", "said"), ("offers", "terms"),
                          ("cases", "summary"), ("actions", "args_json"), ("actions", "reason"),
                          ("actions", "evidence"), ("notices", "place"), ("notices", "text"),
                          ("catchup_cache", "text"), ("digests", "text"), ("npcs", "description"),
                          ("world", "value")):
        value = connection.execute(f"SELECT \"{column}\" FROM \"{table}\" LIMIT 1").fetchone()[0]
        assert OLD not in value
        assert NEW in value
    assert connection.execute("SELECT text,rationale FROM messages").fetchone() == (OLD, OLD)
    assert connection.execute("SELECT text FROM timeline").fetchone() == (OLD,)
    tables = [row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )]
    before = {table: connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall() for table in tables}
    connection.close()
    init_db(path)
    connection = sqlite3.connect(path)
    after = {table: connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall() for table in tables}
    assert after == before
    assert connection.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)
    connection.close()


def test_evorium_has_no_old_street_name_outside_migration():
    root = Path(__file__).resolve().parents[1] / "evorium"
    hits = []
    for path in root.rglob("*"):
        if path.is_file() and path.name != "db.py":
            try:
                if OLD in path.read_text(encoding="utf-8"):
                    hits.append(str(path.relative_to(root)))
            except (UnicodeDecodeError, OSError):
                pass
    assert hits == []
