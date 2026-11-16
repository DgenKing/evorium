from datetime import datetime
import os
import subprocess
from evorium.db import connect, init_db, npc_agents
from evorium.seed import seed_agents
from evorium import tick, world


def test_database_override(tmp_path):
    env = dict(os.environ, EVORIUM_DB_PATH=str(tmp_path/'other.sqlite3'))
    out = subprocess.check_output(['.venv/bin/python','-c','from evorium.db import DEFAULT_DB_PATH; print(DEFAULT_DB_PATH)'],env=env,text=True)
    assert str(tmp_path/'other.sqlite3') in out


def test_kinds_and_real_timestamp(tmp_path):
    path=tmp_path/'world.sqlite3'; init_db(path); seed_agents(path)
    with connect(path) as c:
        assert len(npc_agents(c)) == 5
        system=c.execute("SELECT id FROM agents WHERE kind='system'").fetchone()[0]
        c.execute("INSERT INTO conversations(location,status,sim_at) VALUES ('pub','completed','2026-11-16 19:55')")
    assert system not in world.pick_pair([1,2,system],path)
    assert not tick.conversation_due(datetime(2026,11,16,20),20,path)
    assert tick.conversation_due(datetime(2026,11,16,20,16),20,path)
