# EVORIUM — Build Brief 3: player, relationships, actions, timeline, director, cast

You are the developer on Evorium. This brief tells you exactly what to build next. Read these first, in this order:

1. `EVORIUM_CORE_IDEA.md` — the vision.
2. `README.md` — what exists and how to run it.
3. `EVORIUM_M1_FINDINGS.md` — why the memory system looks the way it does.
4. Every file in `evorium/` and `tests/`. The codebase is about 1,500 lines; read all of it before changing anything.

Build all eight phases below, in order, without stopping to ask between phases. Commit locally after each phase. Do not push; the owner pushes.

---

## 0. Ground rules (apply to every phase)

### What exists today

- `evorium/db.py` — SQLite, `MIGRATIONS` tuple (3 migrations applied), `connect()`, `init_db()`. `DEFAULT_DB_PATH` is `evorium.sqlite3` in the project root.
- `evorium/world.py` — sim clock (real UK time × a speed multiplier, anchored in the `world` key/value table), `routine(name, dt) -> (location, activity)` as hardcoded weekly timetables, `pub_open()`, `present_in_pub()`, `pick_pair()`, `get_setting()` / `set_setting()`.
- `evorium/tick.py` — `update_routines`, `deliver_events` (scheduled world events become `observed` facts), `check_due_promises` (asks the character "did you do it?"), `conversation_due`, `who_is_in_the_pub`.
- `evorium/main.py` — FastAPI app. A daemon thread runs `_tick_loop()` every 5 real seconds. Auto mode ("Let them live") is persisted in the `world` table and restored on startup.
- `evorium/sim.py` — `run_conversation(client, a_id, b_id, turns, db_path)`: alternating turns, then `_take_notes()` makes one extraction call.
- `evorium/memory.py` — `knowledge_for_prompt()` builds what a speaker knows; `store_extraction()` persists facts (`seed` / `observed` / `told` / `claim`), commitments (with deadlines, `replaces` support) and new named people (`npcs`).
- `evorium/prompts.py` — dialogue system prompt, extraction prompt, promise-check prompt.
- `evorium/llm.py` — `DeepSeekClient.propose(agent_id, messages, schema=ActionProposal, max_tokens=300)`. Returns a validated pydantic object. Raises `InvalidProposal` (bad JSON twice) or `LLMError` (network, budget cap). Every call is recorded in `llm_calls` and counted against `MAX_SPEND_USD`.
- `evorium/seed.py` — five characters, 16 seed facts, 2 scheduled events. All inserts are `ON CONFLICT DO NOTHING`, so seeding is safe to re-run on a live database.
- `evorium/static/index.html` — single-page dashboard, plain JS, polls `/agents`, `/usage`, `/conversations/latest` every 2 s and `/events` every 1 s.
- 45 tests pass (`python -m pytest -q`). None hit the real API.

### Hard constraints

1. **A live world is running. Do not lose it.** `evorium.sqlite3` holds a real-time run that started on Monday 16 November 2026. Two scheduled events are pending (Raj's phone call Wednesday 11:00, Dez's letter Thursday 09:00). Never delete, recreate or reseed-over this file. Before applying your first migration, copy it: `cp evorium.sqlite3 evorium-backup-pre-m3.sqlite3`.
2. **Schema changes only by appending to `MIGRATIONS`.** Never edit migrations 1–3. One new migration per phase is fine. Every migration must apply cleanly to the live database and to an empty one.
3. **Never touch `config.py`, never print or log the API key, never use `python-dotenv` or `.env` files.** New settings go in `config.example.py` with safe defaults and are read with `getattr(config, "NAME", default)` so the owner's existing `config.py` keeps working unedited.
4. **Stack is fixed:** Python, FastAPI, `sqlite3`, `httpx`, pydantic, plain HTML/CSS/JS. No new dependencies, no ORM, no frontend framework, no build step, no Docker.
5. **The model proposes; Python decides.** Every model response is JSON, validated by a pydantic schema, then checked against world rules before anything is written. Invalid proposals are dropped and logged with `emit(..., "error")`, never applied.
6. **Tests never hit the real API.** Use the `FakeClient` pattern in `tests/test_sim.py`. Every phase adds tests and leaves the whole suite green.
7. **Real API spend during this whole build: under $0.30.** Do smoke tests against a copy of the database on another port (see Phase 0), not the live one.
8. **Model settings stay as they are:** `deepseek-flash`, temperature 0.8, JSON response mode. Keep `max_tokens` small; state the value for each new call.
9. **Keep it runnable.** After each phase: tests green, the server starts, the dashboard loads.
10. **UI rules:** escape every string with the existing `esc()` helper. The "EVORIUM" title links to `/`. Never add a "Home" link to any navigation.
11. **Do not invent requirements.** Where this brief is silent, pick the simplest option and list it under "Assumptions" in your final report.

### Running and restarting the live server

```bash
# stop
PID=$(ss -ltnp | grep ':8000 ' | sed -E 's/.*pid=([0-9]+).*/\1/'); [ -n "$PID" ] && kill "$PID"
# start (detached, logs to server.log, which is git-ignored)
setsid nohup .venv/bin/python -m uvicorn evorium.main:app --host 127.0.0.1 --port 8000 >> server.log 2>&1 < /dev/null &
```

Restart the live server only at the end of a phase, after tests pass. Auto mode resumes by itself.

---

## Phase 0 — Preparation

1. **Database path override.** In `db.py`, let the environment variable `EVORIUM_DB_PATH` override `DEFAULT_DB_PATH`. Use it for smoke tests: `EVORIUM_DB_PATH=/tmp/evorium-smoke.sqlite3 uvicorn evorium.main:app --port 8001`.
2. **Agent kinds.** Migration 4: `ALTER TABLE agents ADD COLUMN kind TEXT NOT NULL DEFAULT 'npc'` (values `npc`, `player`, `system`). Seed one `system` row named `World` (age 0, other text fields a short placeholder). Use its id as `agent_id` for model calls that belong to no character (director, digest). Add a helper `npc_agents(connection)` and use it everywhere the code currently iterates over all agents: `tick._agents`, `who_is_in_the_pub`, `/agents`, `pick_pair` callers, the cast list. The `World` row and the player row must never appear on a card, in a routine update or in an NPC pair.
3. **Real sim timestamps.** Conversations store only a label like `Monday 16 November, 18:21` with no year. Migration 4 also adds `conversations.sim_at TEXT` (format `%Y-%m-%d %H:%M`, the existing `DUE_FMT`). Write it for every new conversation. Make `tick.conversation_due` use `sim_at` when present and fall back to the old label parsing when it is NULL.

Tests: path override; kind filter excludes player and system rows from routines and pairing; `conversation_due` with `sim_at`.

---

## Phase 1 — Timeline

A permanent, readable record of what happened, written by Python at the moment each thing happens. Later phases call `timeline.record()`.

**Migration:** `timeline(id, sim_at TEXT NOT NULL, kind TEXT NOT NULL, agent_id, other_id, text TEXT NOT NULL, importance INTEGER NOT NULL CHECK (importance BETWEEN 1 AND 5), conversation_id, created_at)` with an index on `sim_at`; and `digests(day TEXT PRIMARY KEY, text TEXT NOT NULL, created_at)`.

**Module `evorium/timeline.py`:**

- `record(connection, sim_at, kind, text, importance, agent_id=None, other_id=None, conversation_id=None)`.
- `entries(db_path, since=None, until=None, agent_id=None, kinds=None, min_importance=1, limit=500)`.

**Kinds and importance.** Record these now, at the place in the code where each happens:

| kind | when | importance |
|---|---|---|
| `conversation` | a conversation completes (text = its summary) | 2 |
| `promise_made` | `store_extraction` inserts a commitment | 2 |
| `promise_updated` | a commitment is replaced in place | 2 |
| `promise_kept` | a commitment becomes `done` (either path) | 3 |
| `promise_broken` | a commitment becomes `broken` | 4 |
| `world_event` | `deliver_events` delivers a scheduled event | 5 |
| `rumour` | a fact is stored with source `claim` | 3 |
| `arrival` | a routine change moves someone into or out of a public place | 1 |

Later phases add `relationship`, `action`, `player` and `director`.

**Daily digest.** On the first tick after 00:00 sim time, if auto mode is on, the previous sim day has at least three timeline rows of importance ≥ 2, and no digest exists for that day: one model call (`max_tokens` 250, `agent_id` = the `World` row) given that day's rows, returning `{"digest": "<3 to 5 sentences, plain past tense, names people, invents nothing>"}`. Store it in `digests`. On failure, skip silently; try again next tick at most twice.

**API:** `GET /timeline?since=&until=&agent_id=&min_importance=` returns `{"days": [{"day": "2026-11-16", "label": "Monday 16 November", "digest": "..."|null, "entries": [...]}]}`, newest day first.

**Page:** `evorium/static/timeline.html`, served at `/timeline-page`. Grouped by day, digest at the top of each day, each entry showing time, an icon or coloured tag per kind, the text, and the people involved. Filters: character dropdown, "important only" checkbox (importance ≥ 3). A "since your last visit" divider using a `localStorage` timestamp. Add a "Timeline" link in the dashboard header.

Tests: each kind is recorded by its trigger; filters; digest is created once and not duplicated; digest failure does not break the tick.

---

## Phase 2 — The player enters the world

The player is a person in the world with the same knowledge boundaries as anyone else: characters know only what the player tells them, and others find out only if someone passes it on.

### Data

- Seed one `agents` row with `kind='player'`, name `Stranger`, occupation `New face in Ancoats`, other fields short placeholders.
- Player state in the `world` settings table: `player_place` (`pub`, `shop` or empty string for "not in the world").
- A player conversation is an ordinary `conversations` row with `agent_a_id` = the player and `agent_b_id` = the character, status `running` until closed.

### Endpoints

| Endpoint | Behaviour |
|---|---|
| `GET /player` | Name, about, current place, the open conversation with its messages (or null), the player's open promises, what the player has learned (their `facts` rows, newest 15), and each public place with whether it is open and who is there. |
| `POST /player/profile` `{name, about}` | Name 2–30 characters, must not equal any character's full or first name; `about` up to 200 characters (stored in `occupation`). Refuse with 409 while a player conversation is open. |
| `POST /player/enter` `{place}` | 409 if the place is shut. Records a `player` timeline entry (importance 3). |
| `POST /player/leave` | Closes any open conversation (see below), clears the place, records a timeline entry. |
| `POST /player/say` `{to_agent_id, text}` | See below. |
| `POST /player/end` | Closes the open conversation. |
| `POST /player/promises/{id}` `{done: bool, note}` | Resolves one of the player's own promises. |

### `POST /player/say`

1. Validate: player is in a place; the character is an NPC in that same place right now; text is 1–500 characters after trimming; the conversation has fewer than 40 messages. Otherwise 409 with a plain-English reason.
2. If the character is in a `running` NPC-to-NPC conversation, return 409: "Jess is talking to Dez at the moment. Try again in a minute."
3. If the player has an open conversation with a different character, close that one first.
4. Insert the player's line into `messages` (rationale `(player)`).
5. Build the character's reply with the existing `build_messages(speaker=character, listener=player_row, transcript, knowledge, sim_label)` and `client.propose(character_id, messages)`. Insert the reply, update the character's mood.
6. Return `{conversation_id, reply: {text, rationale, mood}}`. On `InvalidProposal`, return 502 "They didn't seem to hear you. Try again." and keep the player's line.

Use a dedicated lock for player requests; do not take the global `_run_lock`. `pick_pair` must skip any character whose player conversation had a message in the last 3 real minutes.

### Closing a player conversation

Closing runs the normal `_take_notes()` path with `a` = player and `b` = character, so:

- What the player said becomes `told` facts for the character with `source_agent_id` = the player. The character can repeat it to others, attributed.
- Anything the player asserts that is not in the character's known facts is hearsay to them, exactly as for any other speaker.
- Promises the player made become `commitments` rows owned by the player. Promises the character made to the player work as they already do.
- What the character told the player becomes the player's own `facts` rows (shown in the UI as "What you've learned").

Also close automatically: when the player leaves; when the player has been silent for 5 real minutes (checked by the tick, even when auto mode is off); and on server startup for any player conversation left `running`. Change `sim.mark_interrupted()` so it does not mark player conversations failed.

### The player's promises

The tick cannot ask a human "did you do it?". For commitments owned by the player:

- `check_due_promises` must skip them.
- The UI lists them with "Done" and "Didn't do it" buttons, calling `POST /player/promises/{id}`.
- If one is more than 24 sim-hours overdue and unanswered, the tick marks it `broken` with outcome "Never heard back."
- On resolution, the character it was promised to gets an `observed` fact ("Stranger did what they promised: …" or "Stranger promised to … and didn't.") and a timeline entry.

### Prompt change

In `prompts.build_messages`, when the listener is the player, add one line to the system prompt: "{name} is someone you know only from what is listed here. Do not assume anything else about them." Nothing else changes.

### Dashboard

A "You" panel above the transcript:

- Name and "about" (editable), and where you are.
- Buttons: "Walk into the Crooked Billet", "Go into Patel's News" (disabled with the reason when shut), "Leave".
- When inside: who is here, click a person to talk; a chat thread with your lines and theirs (their rationale in small grey text, as in the existing transcript); a text box, Send on Enter; "End conversation".
- "Your promises" with the two buttons, and "What you've learned".

Tests: say → reply stored; character not present → 409; character busy → 409; closing produces `told` facts attributed to the player; a player promise is skipped by the due-check and broken after 24 h; startup closes an orphaned player conversation instead of failing it; the player never appears in NPC pairing or routines.

---

## Phase 3 — Relationships

How each character feels about each other one, changed only by things that actually happened.

**Migration:**

- `relationships(agent_id, other_id, trust INTEGER NOT NULL DEFAULT 50, warmth INTEGER NOT NULL DEFAULT 50, familiarity INTEGER NOT NULL DEFAULT 0, updated_at, PRIMARY KEY (agent_id, other_id))`. Directed: Jess→Dez and Dez→Jess are separate rows. Values clamped to 0–100.
- `relationship_events(id, agent_id, other_id, d_trust, d_warmth, reason TEXT NOT NULL, conversation_id, sim_at, created_at)`.

**Module `evorium/relationships.py`:** `get(connection, a, b)` (creates the row at defaults if missing), `adjust(connection, a, b, d_trust, d_warmth, reason, sim_at, conversation_id=None)` (clamps, writes the event), `describe(row) -> str`.

**Seeded starting values** (insert only if the row does not exist):

| From → To | trust | warmth |
|---|---|---|
| Dez ↔ Tommy | 80 | 75 |
| Dez → Jess | 75 | 65 |
| Jess → Dez | 65 | 65 |
| Tommy ↔ Jess | 65 | 70 |
| Raj ↔ Dez | 60 | 55 |
| Raj ↔ Tommy | 55 | 55 |
| everyone ↔ Chloe | 50 | 50 |
| everyone ↔ the player | 50 | 50 |

**Rules that change them (all in Python):**

| Event | Effect |
|---|---|
| A conversation completes | `familiarity` +1 both ways |
| A promise to X is kept | X→promiser: trust +8, warmth +2 |
| A promise to X is broken | X→promiser: trust −12, warmth −4 |
| The note-taker proposes a feeling (below) | up to ±4 on each axis |

**Feeling proposal.** Extend the extraction schema: each speaker may include `"feeling": {"trust_change": -2..2, "warmth_change": -2..2, "reason": "<one short sentence citing what the other person actually said or did in this conversation>"}` about the other speaker. Python multiplies each by 2, ignores the proposal if `reason` is empty or both changes are 0, and applies it once. Add to the extraction prompt: "Most conversations change nothing; use 0 unless something in this conversation clearly earned or cost trust or warmth."

**Bands for prompts and UI** (never show the model raw numbers):

- trust: below 30 "do not trust", 30–44 "are wary of", 45–64 "have no strong view on", 65–79 "trust", 80+ "trust completely".
- warmth: below 30 "dislike", 30–44 "are cool towards", 45–64 "are neutral about", 65–79 "like", 80+ "are very fond of".

**Prompt.** In `knowledge_for_prompt` / `build_messages`, add a section: "HOW YOU FEEL ABOUT {OTHER}: You {trust band} and {warmth band} them." followed by up to two most recent `relationship_events` reasons. Also add a section "PROMISES {OTHER} HAS BROKEN TO YOU" (most recent 2 broken commitments).

**Timeline.** Record kind `relationship` (importance 3) when a single change is 8 or more on either axis, or when a change crosses a band boundary. Text example: "Jess now is wary of Dez (was: trusts) — he promised to ring the agent and didn't."

**Dashboard.** Each card gets a "Relationships" list: one line per other character with both bands and the latest reason on hover.

Tests: clamping; kept and broken promise effects go to the promisee's row only; feeling proposal bounds and the empty-reason rule; band text; a band crossing writes a timeline row.

---

## Phase 4 — Places and actions

Today the only thing a character can do is talk, and where they are is a fixed timetable. This phase lets them choose from a short list of real actions that Python validates and executes.

### Places

New module `evorium/places.py` with a registry of **public** places:

| key | name | open |
|---|---|---|
| `pub` | The Crooked Billet, Ancoats, Manchester | existing `world.pub_open()` |
| `shop` | Patel's News, Ancoats | Monday–Saturday 07:00–19:00 |

Everything else (homes, workplaces) is private: nobody meets there.

Generalise presence: `places.present(now, db_path) -> {place_key: [npc rows]}`. Keep `who_is_in_the_pub` working as a thin wrapper. In auto mode, each tick: for each public place with two or more NPCs present, if the gap since the last conversation **at that place** has elapsed, start one (pub: 4 turns; shop: 2 turns). Still only one conversation at a time globally.

`run_conversation` gains an optional `location: str | None` parameter that overrides the stored location and the "Where and when" line in the prompt.

### Free time

Characters may only deviate from their timetable when they are free. Refactor `world.routine` internally so each branch also yields a `free` flag, exposed as `world.is_free(name, dt) -> bool`. Keep `world.routine()` returning the same 2-tuple so existing tests pass. Free means: at home, off duty, out walking, or in the pub as a customer. Not free: asleep, any work shift (Dez behind the bar, Jess working or cleaning, Raj behind the counter, Chloe at work).

### Plans

**Migration:** `plans(id, agent_id, action TEXT CHECK (action IN ('visit','phone','stay_home')), place TEXT, person_id INTEGER, start_at TEXT, end_at TEXT, reason TEXT, fulfils_commitment_id INTEGER, status TEXT DEFAULT 'planned' CHECK (status IN ('planned','active','done','missed','cancelled')), outcome TEXT, created_at)`.

**Daily planning call.** On the first tick after 07:00 sim time each sim day, in auto mode, for each NPC without a plan row created that sim day: one model call (`max_tokens` 300). The prompt gives the character's identity, today's default timetable in plain words, their open promises with deadlines, the relationship bands, and their knowledge sections. It asks:

```json
{"plans": [
  {"action": "visit" | "phone" | "stay_home",
   "place": "pub" | "shop" | null,
   "person": "<full name of a character>" | null,
   "hour": 0-23, "minute": 0 | 30,
   "duration_minutes": 30-180,
   "fulfils": <id of one of your open promises> | null,
   "reason": "<one short sentence>"}
]}
```

Zero, one or two plans. The prompt must say: "Most days you simply follow your routine; return an empty list unless you have a real reason."

**Validation (reject the individual plan, keep the rest):**

- `visit`: place is a public place, open for the whole visit; the character is free for the whole visit; starts later today.
- `phone`: `person` is an NPC and not themselves; the caller is free or on a work shift where a phone is plausible (Dez, Raj); starts later today.
- `stay_home`: covers an evening block when the timetable would have put them in the pub as a customer.
- `fulfils`: must be an open commitment owned by this character, otherwise set to null.
- At most 2 plans per character per sim day. If no plans are valid, insert one `cancelled` marker row so the call is not repeated that day.

**Execution (in the tick, no model call unless noted):**

- Effective whereabouts: new `world.whereabouts(agent, now, db_path)` returns the active plan's override if one exists, otherwise `routine()`. `tick.update_routines` and `places.present` use it.
- `visit`: from `start_at` to `end_at` the character is at that place with activity "popping into the shop" / "in for a drink". Then status `done`.
- `stay_home`: stays at their home location for the block. Then `done`.
- `phone`: at `start_at`, if the other person is awake and not in a conversation, run `run_conversation(client, caller, other, turns=4, location="On the phone")`. This is a model-backed conversation and needs auto mode on. If they cannot be reached, retry once 30 sim-minutes later, then status `missed` with outcome "No answer."
- `fulfils`: when a plan with `fulfils_commitment_id` completes as `done`, mark that commitment `done` with outcome taken from the conversation summary (phone) or "Went to {place} as promised." (visit). Apply the Phase 3 kept-promise effect. A `missed` plan does not resolve the commitment; the existing due-check will ask about it later.
- Timeline: kind `action`, importance 2 (3 when it fulfils a promise), for each executed or missed plan.

**Prompt.** Add to the dialogue system prompt a section "WHAT YOU HAVE DONE AND PLAN TO DO TODAY" listing today's plan rows with status, so a character does not claim an action that did not happen.

**Player.** The player can enter the shop when it is open (already wired in Phase 2).

**Dashboard.** Replace the single "who's in the pub" line with a "Where everyone is" strip grouped by place, and show today's plans on each card.

Tests: each validation rule; an override moves the character and reverts afterwards; a phone plan runs a conversation with the fake client and resolves the linked promise; unreachable → retried once → `missed`; planning runs once per character per sim day; shop conversations happen only when two NPCs are in the shop.

---

## Phase 5 — The director

A light hand that nudges the world only when it has stalled. It never overrides characters and never contradicts established facts.

**Module `evorium/director.py`.**

`stall_report(now, db_path) -> dict` in pure Python. The world is **stalled** when all of these hold:

- No timeline row of importance ≥ 3 in the last 24 sim-hours.
- No undelivered scheduled event due in the next 24 sim-hours.
- No director event delivered in the last 24 sim-hours.

Check every 6 sim-hours in auto mode, only if the director setting is on (persisted in `world`, default on). If stalled: one model call (`max_tokens` 300, `agent_id` = the `World` row). The prompt gives a neutral summary of the last three sim days from the timeline, the cast list, and the allowed event types. Response:

```json
{"type": "letter" | "phone_call" | "small_incident" | "chance_meeting",
 "for": "<full name of a character>",
 "with": "<full name>" | null,
 "content": "<one or two sentences, second person, mundane and plausible>",
 "in_hours": 1-24,
 "rationale": "<why this would move things on>"}
```

**Validation, all required:**

- `for` (and `with`, for `chance_meeting`) are NPCs.
- `content` is at most 300 characters, contains no `£` sign and no digits followed by "k" or "thousand" (the director may not set money terms), and names no person who is not in the cast or the `npcs` table.
- `small_incident` is for everyday things only: a barrel going off, a late delivery, a burst pipe, a child off school ill.
- `letter` and `phone_call` may only come from a person or organisation already present in seed facts, seed events or the cast.
- `chance_meeting` creates two `visit` plans (Phase 4) putting both people in the same public place at the same time; both must be free then and the place open. No fact is created.
- At most one director event per sim day.

A valid event of the first three types is inserted into `scheduled_events` (add an `origin TEXT NOT NULL DEFAULT 'seed'` column; use `director`) and delivered by the existing mechanism. Record a `director` timeline entry (importance 4) including the rationale. An invalid proposal is dropped and logged; do not retry until the next 6-hour check.

**API and UI:** `POST /director {enabled: bool}`; a "Director" on/off toggle in the dashboard controls; director events tagged distinctly on the timeline.

Tests: `stall_report` true and false cases; each validation rule; the one-per-day limit; the toggle persists across a restart; a pending seed event suppresses the director.

---

## Phase 6 — Three more characters

Add to `seed.py` (characters, seed facts, relationships) and `world.py` (routines with `free` flags). Names follow the house rule: mostly British, a few others.

**Simon Ferris, 46, Asset Manager at Northgate Estates.** He is already named in both scheduled events. Lives in Hale. Polite, corporate, careful with words, evasive under pressure but not a villain; he is doing his job. Goal: get the pub's new lease and the newsagent's surrender agreed before the end of the quarter with as little fuss as possible.
- Routine: Northgate Estates office, Spinningfields, weekdays 09:00–17:30 (not free, but can take phone calls). Thursdays 14:00–14:30 he is in Patel's News (free). Otherwise at home. Never in the pub unless a plan or the director puts him there.
- Seed facts: Northgate bought the freehold of the whole terrace three months ago: the pub, the newsagent and the empty unit between them. His instructions are to bring rents up to market level and to buy out leases where that is cheaper. The proposed pub rent is £3,900 a month, up from £2,400. He offered Raj Patel £45,000 to surrender his lease and has authority to go higher but will not volunteer that. No planning application has been submitted. He does not know what the board will finally do with the block; a redevelopment has been discussed but not decided.

**Brenda Ashworth, 71, retired school dinner lady.** Chairs the tenants' association in Tommy's housing association block. Brisk, organised, kind, loves a petition and a rota. Goal: find out what is really happening to the terrace and get people organised before it is too late.
- Routine: Patel's News most mornings 09:00–09:30 (free). The pub Wednesday 19:00–21:00 and Sunday 13:00–15:00 (free). Otherwise at home, Blossom Street.
- Seed facts: She has heard nothing official about the terrace. She has run two successful petitions before, about a bus route and a zebra crossing. She has known Tommy for thirty years.

**Mohammed "Mo" Iqbal, 38, private hire driver.** Works nights. Easygoing, funny, observant; hears a lot from the back seat and is careful about repeating it. Does not drink alcohol; comes to the pub for the darts and the company. Goal: get a darts team going at the Billet and save enough for his own vehicle licence.
- Routine: Patel's News 16:00–16:20 before his shift, Monday–Saturday (free). The pub Tuesday 18:00–19:30 and Sunday 14:00–16:00 (free). Driving 19:30–04:00 (not free). Asleep 05:00–12:00.
- Seed facts: He has not driven anyone from Northgate and has heard nothing concrete about the terrace. The pub's dartboard has not had a team since before the pandemic.

**Relationships:** Brenda ↔ Tommy trust 75 / warmth 70; Brenda ↔ Dez 60 / 60; Mo ↔ Raj 65 / 65; Mo ↔ Dez 55 / 60; Simon ↔ everyone 40 / 45; all other new pairs default.

**Portraits:** the dashboard already falls back to initials when a portrait is missing. If you can generate portraits in the same style as `evorium/static/portraits/README.md` describes, add `simon.png`, `brenda.png`, `mo.png` at 256×256 and register them in the `portraits` map in `index.html`. If not, leave the initials.

Because seeding is `ON CONFLICT DO NOTHING`, these appear in the live world on the next restart. Check the dashboard still reads well with eight cards.

Tests: routines for the three (including that Mo and Brenda are free when in public places and Simon is not free at the office); seeding twice adds no duplicates; the cast list given to the note-taker includes them.

---

## Phase 7 — Housekeeping

2. **Shrink the portraits.** The five existing PNGs are about 2.2 MB each and display at avatar size. Resize in place to 256×256 and strip metadata (`convert in.png -resize 256x256 -strip out.png`; ImageMagick is installed). Keep the filenames.
4. **README.** Update the status section for everything in this brief: new endpoints, new pages, new settings, how the player, relationships, plans, timeline and director work, in a few lines each.

---

## Explicitly not in this brief

- Voice (speech in or out). The core idea document puts it after the simulation is reliable.
- Characters approaching the player unprompted, group conversations, overhearing.
- Any map, 3D view or new location beyond the pub and the shop.
- Any hosting or deployment beyond the files in Phase 7.
- Changing the model, the provider or the budget cap.

---

## Expected running cost of the new features

At real-time speed with eight characters: about 8 planning calls, at most 1 director call and 1 digest call per sim day, plus one reply call per player message. That is well under one US cent a day on top of conversations. If your implementation would exceed roughly 30 extra model calls per sim day, stop and say so in the report.

---

## Final check and report

When all phases are done:

1. `python -m pytest -q` is green. State the test count.
2. Smoke test on a **copy** of the live database on port 8001 at 600× speed for about three real minutes with auto mode on: confirm at least one planning call, one shop conversation, one timeline digest, and that nothing errors in the feed. Then one short player conversation: enter the pub, say two lines to someone, end it, and confirm the `told` facts and timeline entry. Report the estimated spend of the smoke test.
3. Restart the live server on port 8000. Confirm from `/usage` that auto mode resumed, the two seed events are still pending or correctly delivered, and the earlier conversations are intact.

Then report, in this order:

- **Done:** one line per phase.
- **Not done or partly done:** anything skipped, and why.
- **Assumptions:** every decision you made where this brief was silent.
- **Real API spend** during the build.
- **Known problems** you noticed but did not fix.
- **How to try it:** five numbered steps the owner can follow in the browser to see the player, relationships, a plan, the timeline and the director.
