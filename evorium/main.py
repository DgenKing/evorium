"""FastAPI app: five characters, a real-time world, a dashboard."""

import logging
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from evorium import tick, world, timeline, player, relationships, places, plans, director
from evorium.db import DEFAULT_DB_PATH, connect, init_db, npc_agents
from evorium.events import emit, since
from evorium.llm import DeepSeekClient, LLMError, get_usage
from evorium.memory import open_commitments
from evorium.seed import seed_agents, seed_events
from evorium.sim import get_conversation, latest_conversation_id, mark_interrupted, run_conversation

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
STATIC = Path(__file__).resolve().parent / "static"
_run_lock = threading.Lock()
_last_error: dict = {"message": None}
_state = {"auto": False, "tick_thread": None, "stop": threading.Event(), "conversations": 0,
          "gap_minutes": tick.DEFAULT_CONVERSATION_GAP_MIN, "last_tick": None}
TICK_REAL_SECONDS = 5


def _tick_loop():
    while not _state["stop"].is_set():
        try:
            now = world.now(DEFAULT_DB_PATH)
            plans.execute(None,now,DEFAULT_DB_PATH,auto=False)
            for change in tick.update_routines(now, DEFAULT_DB_PATH):
                emit(f"[{world.describe(now)}] {change}")
            tick.deliver_events(now, DEFAULT_DB_PATH)
            player.maintenance(DeepSeekClient(DEFAULT_DB_PATH), now, DEFAULT_DB_PATH)
            if _state["auto"]:
                try:
                    client = DeepSeekClient(DEFAULT_DB_PATH)
                    timeline.daily_digest(client, now, DEFAULT_DB_PATH)
                    tick.check_due_promises(client, now, DEFAULT_DB_PATH)
                    plans.daily(client,now,DEFAULT_DB_PATH)
                    director.check(client,now,DEFAULT_DB_PATH)
                    if _run_lock.acquire(blocking=False):
                        try:
                            plans.execute(client,now,DEFAULT_DB_PATH,auto=True)
                            for key,present in places.opportunities(now,_state['gap_minutes'],DEFAULT_DB_PATH):
                                try:a,b=world.pick_pair([p['id'] for p in present],DEFAULT_DB_PATH)
                                except ValueError:continue
                                try:run_conversation(client,a,b,4 if key=='pub' else 2,DEFAULT_DB_PATH,location=places.REGISTRY[key])
                                except ValueError:continue
                                _state['conversations']+=1
                                break
                        finally:_run_lock.release()
                except LLMError as exc:
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
    init_db()
    seed_agents()
    seed_events(DEFAULT_DB_PATH, world.now(DEFAULT_DB_PATH))
    player.maintenance(DeepSeekClient(DEFAULT_DB_PATH), world.now(DEFAULT_DB_PATH), DEFAULT_DB_PATH, startup=True)
    stuck = mark_interrupted()
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


app = FastAPI(title="Evorium", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class RunRequest(BaseModel):
    turns: int = Field(default=4, ge=1, le=8)
    agent_a_id: int | None = None
    agent_b_id: int | None = None


class SpeedRequest(BaseModel):
    speed: float = Field(ge=0, le=10000)


class AutoRequest(BaseModel):
    gap_minutes: int = Field(default=tick.DEFAULT_CONVERSATION_GAP_MIN, ge=1, le=24 * 60)


@app.get("/")
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
                   WHERE f.agent_id=? ORDER BY f.id DESC LIMIT 8""", (aid,))]
            counts = dict(connection.execute(
                "SELECT source, COUNT(*) FROM facts WHERE agent_id=? GROUP BY source", (aid,)).fetchall())
            memories = [dict(m) for m in connection.execute(
                "SELECT content, created_at FROM memories WHERE agent_id=? ORDER BY id DESC LIMIT 3", (aid,))]
            resolved = [dict(c) for c in connection.execute(
                "SELECT content, status, outcome FROM commitments WHERE agent_id=? AND status!='open' ORDER BY id DESC LIMIT 3", (aid,))]
            out.append({**dict(r), "in_pub": r["location"] == world.PUB, "facts": facts, "fact_counts": counts,
                        "plans": plans.today(connection,aid,now), "relationships": relationships.for_card(connection, aid), "promises": open_commitments(connection, aid), "resolved": resolved, "memories": memories})
    return out


@app.get("/events")
async def events(after: int = 0):
    return since(after)


@app.get("/usage")
async def usage():
    data = get_usage(DEFAULT_DB_PATH)
    try:
        cap = DeepSeekClient().settings.max_spend_usd
    except LLMError:
        cap = None
    now = world.now(DEFAULT_DB_PATH)
    data.update({
        "director": world.get_setting("director","1",DEFAULT_DB_PATH)=="1", "places": places.describe(now,DEFAULT_DB_PATH), "max_spend_usd": cap, "last_error": _last_error["message"], "running": _run_lock.locked(),
        "auto": _state["auto"], "auto_conversations": _state["conversations"], "gap_minutes": _state["gap_minutes"],
        "sim_time": world.describe(now), "speed": world.get_speed(DEFAULT_DB_PATH), "pub_open": world.pub_open(now),
        "present": [p["name"].split()[0] for p in tick.who_is_in_the_pub(now, DEFAULT_DB_PATH)],
        "tick_alive": _state["last_tick"] is not None and time.time() - _state["last_tick"] < TICK_REAL_SECONDS * 4,
    })
    return data


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
    if not _run_lock.acquire(blocking=False):
        raise HTTPException(409, "A conversation is already running.")
    try:
        _last_error["message"] = None
        client = DeepSeekClient(DEFAULT_DB_PATH)
        now = world.now(DEFAULT_DB_PATH)
        present = tick.who_is_in_the_pub(now, DEFAULT_DB_PATH)
        ids = [p["id"] for p in present]
        a, b = req.agent_a_id, req.agent_b_id
        if a is not None and b is not None and a != b:
            if a not in ids or b not in ids:
                with connect(DEFAULT_DB_PATH) as connection:
                    names = {r["id"]: r["name"].split()[0] for r in connection.execute("SELECT id, name FROM agents")}
                missing = [names[x] for x in (a, b) if x not in ids]
                raise HTTPException(409, f"{' and '.join(missing)} not in the pub right now ({world.describe(now)}). "
                                         f"In: {', '.join(names[i] for i in ids) or 'nobody'}.")
        else:
            if len(ids) < 2:
                raise HTTPException(409, f"Fewer than two people in the pub right now ({world.describe(now)}). "
                                         f"In: {', '.join(p['name'].split()[0] for p in present) or 'nobody'}. Speed the clock up or wait.")
            try:a, b = world.pick_pair(ids, DEFAULT_DB_PATH)
            except ValueError:raise HTTPException(409,'Fewer than two available people; someone is talking to the player.')
        cid = await run_in_threadpool(run_conversation, client, a, b, req.turns, DEFAULT_DB_PATH)
        return get_conversation(cid, DEFAULT_DB_PATH)
    except ValueError as exc:
        raise HTTPException(409,str(exc))
    except LLMError as exc:
        _last_error["message"] = str(exc)
        raise HTTPException(502, str(exc))
    finally:
        _run_lock.release()


@app.get('/timeline')
async def timeline_data(since: str | None = None, until: str | None = None, agent_id: int | None = None, min_importance: int = 1):
    return timeline.days(DEFAULT_DB_PATH, since=since, until=until, agent_id=agent_id, min_importance=min_importance)


@app.get('/timeline-page')
async def timeline_page():
    return FileResponse(STATIC / 'timeline.html')


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

@app.get('/player')
def player_state():
    return player.state(DEFAULT_DB_PATH)

@app.post('/player/profile')
def player_profile(req: ProfileRequest):
    return player.profile(req.name,req.about,DEFAULT_DB_PATH)

@app.post('/player/enter')
def player_enter(req: EnterRequest):
    return player.enter(DeepSeekClient(DEFAULT_DB_PATH),req.place,DEFAULT_DB_PATH)

@app.post('/player/leave')
def player_leave():
    return player.leave(DeepSeekClient(DEFAULT_DB_PATH),DEFAULT_DB_PATH)

@app.post('/player/say')
def player_say(req: SayRequest):
    return player.say(DeepSeekClient(DEFAULT_DB_PATH),req.to_agent_id,req.text,DEFAULT_DB_PATH)

@app.post('/player/end')
def player_end():
    player.close(DeepSeekClient(DEFAULT_DB_PATH),DEFAULT_DB_PATH)
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
