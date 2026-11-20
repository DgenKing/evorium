"""Offline-only Unreal smoke server: a DB copy, port 8011, fake model replies.
Run with the repository's .venv/bin/python. Never changes config.py or the live DB.
"""
import os
import sqlite3
import socket
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
DEST = Path(os.environ.get('EVORIUM_SMOKE_DB', '/tmp/evorium-smoke/smoke.sqlite3'))
LIVE = REPO / 'evorium.sqlite3'
assert DEST.resolve() != LIVE.resolve()
with socket.socket() as probe:
    if probe.connect_ex(('127.0.0.1',8011))==0:
        raise SystemExit('Port 8011 is already in use. Stop the existing smoke server before starting another; its database copy was not changed.')
DEST.parent.mkdir(parents=True, exist_ok=True)
# SQLite backup reads a consistent snapshot, including committed WAL records.
with sqlite3.connect(LIVE.as_uri() + '?mode=ro', uri=True) as source, sqlite3.connect(DEST) as target:
    source.backup(target)
os.environ['EVORIUM_DB_PATH'] = str(DEST)
os.environ['EVORIUM_LOG_FILE'] = ''
from evorium import configuration
configuration.load = lambda: SimpleNamespace(DASHBOARD_PASSWORD='', MAX_SPEND_USD=4)
from evorium import llm, world
from evorium.models import ActionProposal, Extraction

class FakeClient:
    def __init__(self, *args, **kwargs):
        self.settings = SimpleNamespace(max_spend_usd=4)
    def propose(self, agent_id, messages, schema=ActionProposal, max_tokens=300):
        if schema is Extraction:
            return Extraction(summary='Offline smoke test: Rob and the neighbour exchanged greetings.')
        if schema is ActionProposal:
            return ActionProposal(say='FAKE REPLY: Evening Rob. Good to see you.', rationale='Offline smoke test.', mood='friendly')
        if 'text' in schema.model_fields:
            return schema(text='Offline smoke test catch-up.')
        raise AssertionError('Unsupported fake schema: '+schema.__name__)

llm.DeepSeekClient = FakeClient
from evorium import main
main.DeepSeekClient = FakeClient
with sqlite3.connect(DEST) as c:
    for key,value in {'auto':'0','speed':'0','anchor_real':world._real_now().strftime(world.FMT),'anchor_sim':'2026-11-19 18:00:00','player_place':''}.items():
        c.execute('INSERT INTO world(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,value))
    c.execute("UPDATE conversations SET status='completed',ended_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE status='running'")
    c.execute("UPDATE agents SET name='Rob' WHERE kind='player'")
@main.app.get('/smoke/status')
def smoke_status():
    return {'fake_models': True, 'database_copy': str(DEST)}

@main.app.post('/smoke/at')
def smoke_at(payload: dict):
    from evorium import tick
    at = datetime.strptime(payload['at'], world.FMT)
    with sqlite3.connect(DEST) as c:
        for key, value in {'anchor_sim': at.strftime(world.FMT), 'anchor_real': world._real_now().strftime(world.FMT)}.items():
            c.execute('INSERT INTO world(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key,value))
    tick.update_routines(at, DEST)
    return {'sim_at': at.strftime(world.FMT), 'fake_models': True}

if __name__ == '__main__':
    import uvicorn
    print('OFFLINE SMOKE: database copy '+str(DEST)+'; fake replies; auto off; 127.0.0.1:8011',flush=True)
    uvicorn.run(main.app, host='127.0.0.1', port=8011)
