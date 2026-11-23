"""Read-only catch-up, with an explicit player checkpoint and bounded cached narration."""
import json
import re
import threading
import time
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from evorium import accounts, timeline, world, backoff
from evorium.db import DEFAULT_DB_PATH, connect, system_id
from evorium.memory import DUE_FMT
from evorium.llm import LLMError
from evorium.configuration import load

_lock = threading.Lock()


class Previously(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    text: str = Field(min_length=1, max_length=1600)


def seen(now, db_path=DEFAULT_DB_PATH):
    with connect(db_path) as c:
        me = accounts.player_row(c)
        c.execute("UPDATE agents SET last_seen_at=? WHERE id=?", (now.strftime(DUE_FMT), me['id']))
        world._set(c, accounts.setting_key('catchup_fact_checkpoint'), c.execute('SELECT coalesce(max(id),0) FROM facts').fetchone()[0])


def get(client, now, db_path=DEFAULT_DB_PATH):
    with _lock:
        return _get(client, now, db_path)


def _get(client, now, db_path):
    with connect(db_path) as c:
        me = accounts.player_row(c)
        since = me['last_seen_at'] or now.strftime(DUE_FMT)
        if me['last_seen_at'] is None:
            world._set(c, accounts.setting_key('catchup_fact_checkpoint'), c.execute('SELECT coalesce(max(id),0) FROM facts').fetchone()[0])
            c.execute('UPDATE agents SET last_seen_at=? WHERE id=?', (since, me['id']))
        events = [dict(r) for r in c.execute("SELECT * FROM timeline WHERE sim_at>? AND sim_at<=? AND importance>=3 AND kind!='case' ORDER BY id DESC LIMIT 15", (since, now.strftime(DUE_FMT)))]
        stats = [dict(r) for r in c.execute('SELECT * FROM stat_changes WHERE sim_at>? AND sim_at<=? ORDER BY id DESC LIMIT 30', (since, now.strftime(DUE_FMT)))]
        offers = [dict(r) for r in c.execute('SELECT * FROM offers WHERE (created_at>? OR resolved_at>?) AND created_at<=? ORDER BY id DESC LIMIT 20', (since, since, now.strftime(DUE_FMT)))]
        actions = [dict(r) for r in c.execute("SELECT * FROM actions WHERE status='done' AND key!='wait' AND sim_at>? AND sim_at<=? ORDER BY id DESC LIMIT 20", (since, now.strftime(DUE_FMT)))]
        name_word = re.compile(r'\b' + re.escape(me['name']) + r'\b', re.I)
        gossip = [dict(r) for r in c.execute("SELECT f.content,a.name FROM facts f JOIN agents a ON a.id=f.agent_id WHERE a.kind='npc' AND instr(lower(f.content),lower(?))>0 AND f.importance>=3 AND f.id>? ORDER BY f.id DESC LIMIT 50", (me['name'], int(world._get(c, accounts.setting_key('catchup_fact_checkpoint'), '0'))))
                  if name_word.search(r['content'])][:5]
        police_visits = [r[0] for r in c.execute("SELECT content FROM facts WHERE agent_id=? AND subject='police visit' AND id>? ORDER BY id DESC LIMIT 5", (me['id'], int(world._get(c, accounts.setting_key('catchup_fact_checkpoint'), '0'))))]
        latest = c.execute('SELECT coalesce(max(id),0) FROM timeline').fetchone()[0]
        key = json.dumps([accounts.current.get(), since, latest, police_visits])
        cache = c.execute('SELECT text FROM catchup_cache WHERE cache_key=?', (key,)).fetchone()
        bullets = list(dict.fromkeys(police_visits + [r['text'] for r in events] + [r['reason'] for r in stats] + [f"A £{r['amount']:,} {r['kind']} offer is {r['status']}." for r in offers] + [r['result'] for r in actions] + [f"{r['name']}: {r['content']}" for r in gossip]))
        paragraph = cache[0] if cache else None
        last = float(world._get(c, accounts.setting_key('catchup_model_at'), '0'))
        sid = system_id(c)
        allowed = time.time() - last >= max(600, int(getattr(load(), 'CATCHUP_COOLDOWN_SECONDS', 600))) and world._get(c, accounts.setting_key('catchup_model_day')) != now.strftime('%Y-%m-%d')
        if bullets and not cache and allowed and len(bullets) >= 3 and client and not backoff.paused():
            # Reserve the real-time budget before calling, including failures.
            world._set(c, accounts.setting_key('catchup_model_day'), now.strftime('%Y-%m-%d'))
            reserved_at = time.time()
            world._set(c, accounts.setting_key('catchup_model_at'), reserved_at)
            c.execute('INSERT INTO catchup_cache VALUES (?,?,?)', (key, '', reserved_at))
        else:
            allowed = False
    if allowed:
        try:
            paragraph = client.propose(sid, [{'role': 'user', 'content': 'Write Previously in Ancoats: 4–6 plain sentences from these facts only. Return JSON {"text":"..."}.\n' + '\n'.join(bullets[:30])}], schema=Previously, max_tokens=250).text
        except LLMError:
            paragraph = None
        with connect(db_path) as c:
            c.execute('UPDATE catchup_cache SET text=? WHERE cache_key=?', (paragraph or '', key))
    return {'since': since, 'gap_hours': max(0, (now - datetime.strptime(since, DUE_FMT)).total_seconds() / 3600),
            'paragraph': paragraph, 'items': bullets, 'timeline': events, 'stat_changes': stats, 'offers': offers, 'actions': actions, 'gossip': gossip}
