"""FastAPI dashboard and the persistent neighbourhood heartbeat."""

import base64
import binascii
import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from evorium.configuration import load
from pydantic import BaseModel, Field

from evorium import accounts, scene, economy, actions, decide, backoff, tick, world, timeline, player, relationships, places, plans, director
from evorium.db import DEFAULT_DB_PATH, VISIBLE_IMPORTANCE, connect, init_db, npc_agents
from evorium.events import emit, since
from evorium.llm import DeepSeekClient, DeferredClient, LLMError, get_usage
from evorium.memory import open_commitments
from evorium.seed import seed_agents, seed_events
from evorium.sim import get_conversation, latest_conversation_id, mark_interrupted, run_conversation, turns_for

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
# EVORIUM_LOG_FILE picks another file; set it empty to turn the file log off (the tests do).
LOG_FILE = os.environ.get("EVORIUM_LOG_FILE", str(Path(__file__).resolve().parent.parent / "evorium.log"))
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


def _persistent_log():
    """Always keep a log on disk, however the server was started (terminal, nohup or systemd)."""
    root = logging.getLogger()
    if not LOG_FILE or any(getattr(h, "_evorium", False) for h in root.handlers):
        return
    try:
        handler = RotatingFileHandler(LOG_FILE, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    except OSError:
        return  # read-only install: carry on with console logging only
    handler._evorium = True
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(handler)


_persistent_log()


class _HidePolling(logging.Filter):
    """The dashboard polls several GET endpoints every second or two; keep those out of the terminal.
    Actions (POSTs), errors and anything else still show."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args if isinstance(record.args, tuple) else ()
        if len(args) >= 5 and args[1] == "GET" and str(args[4]).startswith("2"):
            return False
        return True


logging.getLogger("uvicorn.access").addFilter(_HidePolling())
STATIC = Path(__file__).resolve().parent / "static"
# The public marketing site (website/) is served at / without a login; the game lives at /game and behind it.
WEBSITE = Path(__file__).resolve().parent.parent / "website"
_run_lock = threading.Lock()
_last_error: dict = {"message": None}
_state = {"auto": False, "tick_thread": None, "stop": threading.Event(), "conversations": 0,
          "gap_minutes": tick.DEFAULT_CONVERSATION_GAP_MIN, "last_tick": None}
TICK_REAL_SECONDS = 5


def _tick_loop():
    while not _state["stop"].is_set():
        try:
            _state["last_tick"] = time.time()
            now = world.now(DEFAULT_DB_PATH)
            from evorium import weather
            weather.refresh(now, DEFAULT_DB_PATH)
            from evorium import bad_days
            bad_days.maintain(now, DEFAULT_DB_PATH)
            plans.execute(None,now,DEFAULT_DB_PATH,auto=False)
            for change in tick.update_routines(now, DEFAULT_DB_PATH):
                emit(f"[{world.describe(now)}] {change}")
            from evorium import calendar_uk
            calendar_uk.maintain(now, DEFAULT_DB_PATH)
            tick.deliver_events(now, DEFAULT_DB_PATH)
            tick.check_due_promises(None, now, DEFAULT_DB_PATH)
            economy.maintain(now, DEFAULT_DB_PATH)
            player.maintenance(DeferredClient(DEFAULT_DB_PATH), now, DEFAULT_DB_PATH)
            from evorium import cases
            cases.maintain(now, DEFAULT_DB_PATH)
            if _state["auto"] and not backoff.paused():
                try:
                    client = DeepSeekClient(DEFAULT_DB_PATH)
                    timeline.daily_digest(client, now, DEFAULT_DB_PATH)
                    if backoff.paused():raise LLMError('DeepSeek calls are paused while the service recovers.')
                    plans.daily(client,now,DEFAULT_DB_PATH)
                    if backoff.paused():raise LLMError('DeepSeek calls are paused while the service recovers.')
                    decide.run(client,now,DEFAULT_DB_PATH)
                    economy.maintain(now, DEFAULT_DB_PATH, client)
                    director.check(client,now,DEFAULT_DB_PATH)
                    if backoff.paused():raise LLMError('DeepSeek calls are paused while the service recovers.')
                    if _run_lock.acquire(blocking=False):
                        try:
                            cases.approach(client,now,DEFAULT_DB_PATH)
                            plans.execute(client,now,DEFAULT_DB_PATH,auto=True)
                            for key,present in places.opportunities(now,_state['gap_minutes'],DEFAULT_DB_PATH):
                                try:a,b=world.pick_pair([p['id'] for p in present],DEFAULT_DB_PATH)
                                except world.PairLimitReached:break
                                except ValueError:continue
                                try:run_conversation(client,a,b,turns_for(a,b,DEFAULT_DB_PATH),DEFAULT_DB_PATH,location=places.REGISTRY[key])
                                except ValueError:continue
                                _state['conversations']+=1
                                break
                        finally:_run_lock.release()
                except LLMError as exc:
                    backoff.failed(exc)
                    _last_error["message"] = str(exc)
                    if "budget cap" in str(exc) or "balance" in str(exc):
                        _state["auto"] = False
                        world.set_setting("auto", "0", DEFAULT_DB_PATH)
                        emit("Auto mode stopped: out of budget.", "error")
            _state["last_tick"] = time.time()
        except Exception:  # the heartbeat must never die
            logging.getLogger(__name__).exception("tick failed")
        _state["stop"].wait(TICK_REAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(DEFAULT_DB_PATH)
    seed_agents(DEFAULT_DB_PATH)
    seed_events(DEFAULT_DB_PATH, world.now(DEFAULT_DB_PATH))
    economy.ensure(DEFAULT_DB_PATH, world.now(DEFAULT_DB_PATH))
    from evorium import cases
    cases.maintain(world.now(DEFAULT_DB_PATH), DEFAULT_DB_PATH)
    player.maintenance(DeferredClient(DEFAULT_DB_PATH), world.now(DEFAULT_DB_PATH), DEFAULT_DB_PATH, startup=True)
    stuck = mark_interrupted(DEFAULT_DB_PATH)
    now = world.now(DEFAULT_DB_PATH)
    tick.update_routines(now, DEFAULT_DB_PATH)
    emit(f"Server started. Sim clock {world.describe(now)} at {world.get_speed(DEFAULT_DB_PATH):g}× real time. "
         f"Pub is {'open' if world.pub_open(now) else 'shut'}." + (f" Marked {stuck} interrupted conversation(s) failed." if stuck else ""))
    _state["auto"] = world.get_setting("auto", "0", DEFAULT_DB_PATH) == "1"
    try:
        _state["gap_minutes"] = int(world.get_setting("gap_minutes", str(tick.DEFAULT_CONVERSATION_GAP_MIN), DEFAULT_DB_PATH))
    except ValueError:
        _state["gap_minutes"] = tick.DEFAULT_CONVERSATION_GAP_MIN
    if _state["auto"]:
        emit(f"Auto mode resumed from before the restart (a conversation every ~{_state['gap_minutes']} sim-minutes).")
    _state["stop"] = threading.Event()
    t = threading.Thread(target=_tick_loop, daemon=True)
    _state["tick_thread"] = t
    t.start()
    yield
    _state["stop"].set()
    await run_in_threadpool(t.join, 30)


app = FastAPI(title="Evorium", lifespan=lifespan)
DASHBOARD_PASSWORD = getattr(load(), 'DASHBOARD_PASSWORD', '')
ACCOUNTS = getattr(load(), 'ACCOUNTS', {})


@app.middleware('http')
async def dashboard_auth(request, call_next):
    path = request.url.path
    if path in ('/', '/styles.css') or path.startswith('/images/'):
        return await call_next(request)   # the public website: no login, no account
    username, supplied = '', None
    try:
        scheme, encoded = request.headers.get('authorization', '').split(' ', 1)
        if scheme.lower() == 'basic':
            decoded = base64.b64decode(encoded, validate=True).decode('utf-8')
            if ':' in decoded:
                username, supplied = decoded.split(':', 1)
    except (ValueError, UnicodeDecodeError, binascii.Error):
        pass
    identity = accounts.authenticate(username, supplied, DASHBOARD_PASSWORD, ACCOUNTS)
    if identity is None:
        return Response('Authentication required.', status_code=401,
                        headers={'WWW-Authenticate': 'Basic realm="Evorium", charset="UTF-8"'})
    account, display = identity
    token = accounts.current.set(account)
    try:
        if account != 'owner':
            await run_in_threadpool(accounts.ensure_player, account, display, DEFAULT_DB_PATH)
        return await call_next(request)
    finally:
        accounts.current.reset(token)


app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.mount("/images", StaticFiles(directory=WEBSITE / "images"), name="website-images")


class RunRequest(BaseModel):
    turns: int = Field(default=4, ge=1, le=8)
    agent_a_id: int | None = None
    agent_b_id: int | None = None


class SpeedRequest(BaseModel):
    speed: float = Field(ge=0, le=10000)


class AutoRequest(BaseModel):
    gap_minutes: int = Field(default=tick.DEFAULT_CONVERSATION_GAP_MIN, ge=1, le=24 * 60)


@app.get("/world3d")
async def world3d():
    return FileResponse(STATIC / "world3d" / "index.html")


@app.get("/")
async def website():
    return FileResponse(WEBSITE / "index.html")


@app.get("/styles.css")
async def website_styles():
    return FileResponse(WEBSITE / "styles.css")


@app.get("/game")
async def index():
    return FileResponse(STATIC / "index.html")


@app.get("/agents")
async def agents():
    out = []
    now = world.now(DEFAULT_DB_PATH)
    with connect(DEFAULT_DB_PATH) as connection:
        for r in npc_agents(connection):
            aid = r["id"]
            facts = [dict(f) for f in connection.execute(
                """SELECT f.content, f.source, a.name AS by_name FROM facts f LEFT JOIN agents a ON a.id=f.source_agent_id
                   WHERE f.agent_id=? AND f.importance>=? ORDER BY f.id DESC LIMIT 8""", (aid, VISIBLE_IMPORTANCE))]
            counts = dict(connection.execute(
                "SELECT source, COUNT(*) FROM facts WHERE agent_id=? AND importance>=? GROUP BY source", (aid, VISIBLE_IMPORTANCE)).fetchall())
            memories = [dict(m) for m in connection.execute(
                "SELECT content, created_at FROM memories WHERE agent_id=? ORDER BY id DESC LIMIT 3", (aid,))]
            resolved = [dict(c) for c in connection.execute(
                "SELECT content, CASE WHEN lapsed_at IS NOT NULL THEN 'lapsed' ELSE status END AS status, outcome FROM commitments WHERE agent_id=? AND (status!='open' OR lapsed_at IS NOT NULL) ORDER BY id DESC LIMIT 3", (aid,))]
            today_action = connection.execute("SELECT result FROM actions WHERE agent_id=? AND status='done' AND substr(sim_at,1,10)=? AND key!='wait' ORDER BY id DESC LIMIT 1", (aid, now.strftime('%Y-%m-%d'))).fetchone()
            considering = connection.execute("SELECT result FROM actions WHERE agent_id=? AND status='considering' ORDER BY id DESC LIMIT 1", (aid,)).fetchone()
            from evorium import cases
            case_rows = [dict(v) for v in connection.execute("SELECT v.*,a.name AS subject_name FROM cases v JOIN agents a ON a.id=v.subject_id WHERE v.subject_id=? OR ?=? ORDER BY v.id DESC LIMIT 10", (aid, r['name'], cases.GRACE))]
            from evorium import bad_days
            condition=bad_days.records(connection,now).get(str(aid),{})
            out.append({"bad_day": bad_days.LABELS.get(condition.get('kind'),'') or '', "cases": case_rows, "today_action": today_action[0] if today_action else None, "considering": considering[0] if considering else None, **dict(r), "in_pub": r["location"] == world.PUB, "facts": facts, "fact_counts": counts,
                        "plans": plans.today(connection,aid,now), "relationships": relationships.for_card(connection, aid), "promises": open_commitments(connection, aid), "resolved": resolved, "memories": memories})
    return out


@app.get("/world/scene")
def world_scene():
    return scene.snapshot(DEFAULT_DB_PATH)


@app.get("/events")
async def events(after: int = 0):
    return since(after)


@app.get("/usage")
async def usage():
    data = get_usage(DEFAULT_DB_PATH)
    try:
        cap = DeepSeekClient(DEFAULT_DB_PATH).settings.max_spend_usd
    except LLMError:
        cap = None
    now = world.now(DEFAULT_DB_PATH)
    from evorium import weather,calendar_uk
    with connect(DEFAULT_DB_PATH) as c: weather_now = weather.read(c, now)
    data.update({
        "weather": weather_now, "calendar": calendar_uk.state(now),
        "ledger": economy.ledger(DEFAULT_DB_PATH, now), "director": world.get_setting("director","1",DEFAULT_DB_PATH)=="1", "places": places.describe(now,DEFAULT_DB_PATH), "max_spend_usd": cap, "last_error": _last_error["message"], "running": _run_lock.locked(),
        "auto": _state["auto"], "auto_conversations": _state["conversations"], "gap_minutes": _state["gap_minutes"],
        "sim_at": now.strftime("%Y-%m-%d %H:%M"), "sim_time": world.describe(now), "speed": world.get_speed(DEFAULT_DB_PATH), "pub_open": world.pub_open(now, economy.read(DEFAULT_DB_PATH)),
        "present": [p["name"].split()[0] for p in tick.who_is_in_the_pub(now, DEFAULT_DB_PATH)],
        "boot_id": BOOT_ID, "version": VERSION, "model_paused_until": backoff.until(),
        "tick_alive": _state["last_tick"] is not None and time.time() - _state["last_tick"] < TICK_REAL_SECONDS * 4,
    })
    return data


RESTART_GRACE_SECONDS = 30
BOOT_ID = f"{os.getpid()}-{time.time():.0f}"   # changes on every start, so the dashboard can tell a restart finished


def code_version(repo=Path(__file__).resolve().parent.parent):
    """The git commit this server is running, read once at start-up (so it changes on every auto-update)."""
    import subprocess
    try:
        out = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%h|%cd|%s", "--date=format:%d %b %H:%M"],
                             capture_output=True, text=True, timeout=5)
        commit, date, subject = out.stdout.strip().split("|", 2)
        dirty = subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True, timeout=5).stdout.strip() != ""
        return {"commit": commit, "date": date, "subject": subject, "modified": dirty}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {"commit": "unknown", "date": "", "subject": "Not a git checkout", "modified": False}


VERSION = code_version()


def _restart_process():
    """Let the reply reach the browser, stop the heartbeat cleanly, then re-run the same command line."""
    time.sleep(0.5)
    _state["stop"].set()
    thread = _state.get("tick_thread")
    if thread:
        thread.join(RESTART_GRACE_SECONDS)   # a conversation in progress gets time to finish
    for handler in logging.getLogger().handlers:
        handler.flush()
    # Same interpreter and arguments (works for `uvicorn ...`, `python -m uvicorn ...` and systemd).
    # The listening socket is not inherited, so the new process binds the port afresh.
    os.execv(sys.executable, [sys.executable, *sys.orig_argv[1:]])


@app.post("/server/restart")
async def restart_server():
    if any(arg.startswith(("--reload", "--workers")) for arg in sys.orig_argv):
        raise HTTPException(409, "Started with --reload or --workers; restart it from the terminal instead.")
    emit("Restart requested from the dashboard — reloading code. Back in a few seconds.")
    threading.Thread(target=_restart_process, name="restart", daemon=True).start()
    return {"restarting": True}


@app.post("/speed")
async def speed(req: SpeedRequest):
    if req.speed == 1:
        now = world.reset_to_real_time(DEFAULT_DB_PATH)
    else:
        now = world.set_speed(req.speed, DEFAULT_DB_PATH)
    emit(f"Clock speed set to {req.speed:g}×. Sim time {world.describe(now)}.")
    return {"speed": req.speed, "sim_time": world.describe(now)}


@app.post("/auto/start")
async def auto_start(req: AutoRequest):
    _state["auto"] = True
    _state["gap_minutes"] = req.gap_minutes
    _state["conversations"] = 0
    _last_error["message"] = None
    world.set_setting("auto", "1", DEFAULT_DB_PATH)
    world.set_setting("gap_minutes", req.gap_minutes, DEFAULT_DB_PATH)
    emit(f"Auto mode ON: a conversation every ~{req.gap_minutes} sim-minutes whenever two or more people are in the pub.")
    return {"auto": True}


@app.post("/auto/stop")
async def auto_stop():
    _state["auto"] = False
    world.set_setting("auto", "0", DEFAULT_DB_PATH)
    emit(f"Auto mode OFF after {_state['conversations']} conversations.")
    return {"auto": False}


@app.get("/conversations/latest")
async def latest():
    cid = latest_conversation_id(DEFAULT_DB_PATH)
    if cid is None:
        return {"id": None, "status": "none", "messages": []}
    return get_conversation(cid, DEFAULT_DB_PATH)


@app.get("/conversations/{conversation_id}")
async def conversation(conversation_id: int):
    conv = get_conversation(conversation_id, DEFAULT_DB_PATH)
    if conv is None:
        raise HTTPException(404, "No such conversation")
    return conv


@app.post("/conversations/run")
async def run(req: RunRequest):
    if backoff.paused():
        raise HTTPException(503, "DeepSeek is paused while the service recovers.")
    if not _run_lock.acquire(blocking=False):
        raise HTTPException(409, "A conversation is already running.")
    try:
        _last_error["message"] = None
        client = DeepSeekClient(DEFAULT_DB_PATH)
        now = world.now(DEFAULT_DB_PATH)
        groups = places.present(now, DEFAULT_DB_PATH)
        a, b = req.agent_a_id, req.agent_b_id
        candidates = [
            (key, [p['id'] for p in group]) for key, group in groups.items()
            if len(group) >= 2
        ]
        for key, ids in candidates:
            if a is not None and a not in ids or b is not None and b not in ids:
                continue
            if a is not None and b is not None and a != b:
                pair = a, b
            else:
                try:
                    pair = world.pick_pair(ids, DEFAULT_DB_PATH, automatic=False)
                except ValueError:
                    continue
                selected = a if a is not None else b
                if selected is not None and selected not in pair:
                    # Pick the companion among people available at the chosen place.
                    with connect(DEFAULT_DB_PATH) as connection:
                        from evorium.plans import busy
                        available = [i for i in ids if i != selected and not busy(connection, i)]
                    if not available:
                        continue
                    pair = (selected, available[0]) if a is not None else (available[0], selected)
            cid = await run_in_threadpool(run_conversation, client, *pair, req.turns, DEFAULT_DB_PATH,
                                          location=places.REGISTRY[key])
            break
        else:
            raise HTTPException(409, f"Choose two available neighbours at the same public place ({world.describe(now)}).")
        return get_conversation(cid, DEFAULT_DB_PATH)
    except ValueError as exc:
        raise HTTPException(409,str(exc))
    except LLMError as exc:
        _last_error["message"] = str(exc)
        raise HTTPException(502, str(exc))
    finally:
        _run_lock.release()


@app.get('/timeline')
async def timeline_data(since: str | None = None, until: str | None = None, agent_id: int | None = None, min_importance: int = 1, kind: str | None = None):
    return timeline.days(DEFAULT_DB_PATH, since=since, until=until, agent_id=agent_id, min_importance=min_importance, kinds=[kind] if kind else None)


@app.get('/timeline-page')
async def timeline_page():
    return FileResponse(STATIC / 'timeline.html')


@app.get('/guide')
async def guide_page():
    return FileResponse(STATIC / 'guide.html')


class ProfileRequest(BaseModel):
    name: str
    about: str = ''

class EnterRequest(BaseModel):
    place: str

class SayRequest(BaseModel):
    to_agent_id: int
    text: str

class PromiseRequest(BaseModel):
    done: bool
    note: str = Field(default='',max_length=300)

@app.get('/me')
def me():
    with connect(DEFAULT_DB_PATH) as c:
        who = accounts.player_row(c)
    return {'account': accounts.current.get(), 'name': who['name']}


@app.get('/player')
def player_state():
    return player.state(DEFAULT_DB_PATH)

@app.post('/player/profile')
def player_profile(req: ProfileRequest):
    return player.profile(req.name,req.about,DEFAULT_DB_PATH)

@app.post('/player/enter')
def player_enter(req: EnterRequest):
    return player.enter(DeferredClient(DEFAULT_DB_PATH),req.place,DEFAULT_DB_PATH)

@app.post('/player/leave')
def player_leave():
    return player.leave(DeferredClient(DEFAULT_DB_PATH),DEFAULT_DB_PATH)

@app.post('/player/say')
def player_say(req: SayRequest):
    return player.say(DeferredClient(DEFAULT_DB_PATH),req.to_agent_id,req.text,DEFAULT_DB_PATH)

@app.post('/player/end')
def player_end():
    player.close(DeferredClient(DEFAULT_DB_PATH),DEFAULT_DB_PATH)
    return player.state(DEFAULT_DB_PATH)

@app.post('/player/promises/{promise_id}')
def player_promise(promise_id: int, req: PromiseRequest):
    return player.resolve(promise_id,req.done,req.note,DEFAULT_DB_PATH)


class DirectorRequest(BaseModel):
    enabled: bool

@app.post('/director')
def director_toggle(req: DirectorRequest):
    world.set_setting('director','1' if req.enabled else '0',DEFAULT_DB_PATH)
    return {'enabled':req.enabled}


@app.get('/world/ledger')
def world_ledger():
    return economy.ledger(DEFAULT_DB_PATH, world.now(DEFAULT_DB_PATH))

@app.get('/actions')
def action_history(since: str | None = None):
    return actions.listing(DEFAULT_DB_PATH, since)

@app.get('/catchup')
def catchup_data():
    from evorium import catchup
    return catchup.get(DeferredClient(DEFAULT_DB_PATH), world.now(DEFAULT_DB_PATH), DEFAULT_DB_PATH)

@app.post('/catchup/seen')
def catchup_seen():
    from evorium import catchup
    catchup.seen(world.now(DEFAULT_DB_PATH), DEFAULT_DB_PATH)
    return {'seen': True}
