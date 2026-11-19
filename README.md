# Evorium — Milestone 3

Eight persistent characters in an Ancoats neighbourhood, with player chat,
memories, relationships and plans. Python 3.11+, FastAPI, SQLite and plain HTML/JavaScript.

**The whole project — idea, history, current state, known issues, next steps and the online plan — is in
[EVORIUM.md](EVORIUM.md).** This README is just how to run it.

## Run locally

From this project directory:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp -n config.example.py config.py
uvicorn evorium.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. Startup creates `evorium.sqlite3` alongside this
README and seeds eight NPCs, a player and a system row if absent. Stop with Ctrl+C;
restarting reuses the database and preserves existing character state.

Edit `config.py` locally to set `DEEPSEEK_API_KEY`. The key is hardcoded only in
that ignored file; no `.env` files are used.
Do not put credentials in frontend code, logs, or version control.

## Preparing for GitHub

Commit `config.example.py`, which contains only a placeholder. Keep your real
key in `config.py`; `.gitignore` excludes that file, local environment files,
databases, logs, backups, and virtual environments. Each person cloning the
repository must create their own local `config.py` using the setup above.

Before committing, check `git status --short` and `git diff --cached`.
`config.py` must not appear among the files being committed. Do not use
`git add -f` for ignored local files, or upload the entire working directory
through GitHub's browser uploader: that bypasses `.gitignore`.

## Status: Milestone 1 complete (2026-11-15)

All five steps of the Milestone 1 brief are done (history in `EVORIUM.md`):

1. Database schema, migrations and seeded characters.
2. DeepSeek client with JSON validation, one retry on bad JSON, per-call usage records.
3. `sim.py` conversation runner + `prompts.py`; one memory per agent per conversation.
4. Endpoints (`/agents`, `/usage`, `/conversations/latest`, `/conversations/{id}`,
   `POST /conversations/run`) and the dashboard at `evorium/static/index.html`.
5. First real call verified: a 2-turn Dez/Chloe exchange cost ~$0.0003 (711 tokens).
   State, moods and memories survive a server restart.

Model is `deepseek-flash` (thinking disabled, temperature 0.8, 300-token limit,
JSON response mode). Only validated dialogue proposals reach the simulation.

**Local spending cap:** `MAX_SPEND_USD` in `config.py` (default 4.00). Once estimated
spend reaches it, new requests are refused with a clear error in the dashboard.
This is an application-level guard, not a provider billing cap; the remaining-credit
figure assumes the initial $5 funding and is not a live balance.

## Milestone 2 (2026-11-15): five characters, structured memory, real-time world

- Five characters (Dez, Chloe, Tommy, Jess, Raj) with seeded ground-truth facts (`seed.py`).
- After every conversation a second model call extracts facts (observed / told-by / claim),
  promises (with deadlines) and new people (`memory.py`, `prompts.py`). Claims are fed back
  to the character as unverifiable and shown as RUMOUR on the dashboard.
- **The sim clock is the real UK clock** (`world.py`). A speed multiplier (0 = paused, 1 = real,
  10/60/600×) re-anchors continuously; choosing 1× snaps back to real time.
- Weekly routines decide where everyone is; only people in the pub can talk.
- A tick thread (`tick.py`, every 5 real seconds) moves people, delivers scheduled world events
  (Northgate's letter with figures on Thursday 09:00; Raj's phone call Wednesday 11:00), checks
  promises that have come due (one cheap call: did you do it?), and in auto mode starts a
  conversation every N sim-minutes when two or more people are in.
- `Let them live` runs until stopped. `Run conversation` works any time two people are in.

## Milestone 3: player, relationships, actions and history

- **You:** edit your name and about, enter the pub or shop, choose someone present
  and type a message. Send with Enter, then end the conversation to save notes.
  Others learn what you said only through attributed conversation memories.
  Silence for five real minutes, leaving, and server restarts close your chat.
- **Your promises:** mark them Done or Didn't do it. Unanswered promises more
  than 24 sim-hours overdue break automatically. What you've learned shows your
  own most recent 15 facts; nobody receives another character's private knowledge.
- **Relationships:** directed trust, warmth and familiarity persist. Kept and
  broken promises change the promisee's trust; small evidenced feelings from
  notes may also change it. Cards and prompts show descriptive bands.
- **Places and plans:** the pub keeps its existing hours; Patel's News opens
  Monday–Saturday 07:00–19:00. In auto mode, NPCs can make up to two plans per
  day after 07:00, often none. Visits and staying home must fit free time;
  phone calls retry once if unanswered. Completed plans can fulfil promises.
  Pub and shop encounters have independent cooldowns (four and two turns).
- **Timeline:** open [Timeline](http://127.0.0.1:8000/timeline-page) in the header
  for permanent conversations, promises, arrivals, rumours and world events.
  Filter by character or importance. A daily digest summarises yesterday when
  auto mode is on and at least three significant records exist; at most two
  attempts per day. Your last visit is remembered in this browser.
- **Director:** the persisted toggle defaults on, acts only in auto mode, and
  checks for a stall every six sim-hours. Recent important events or a seed
  event due within 24 hours suppress it. Validated mundane events occur at most
  once per sim day; it cannot set money terms or introduce unknown people.
- **Cast:** Simon Ferris, Brenda Ashworth and Mohammed "Mo" Iqbal join the five
  original characters. Their private seed knowledge is kept separate. New
  characters use initials; existing portraits are 256×256 PNGs.

New API routes: `GET /timeline`, `GET /player`, `POST /player/profile`,
`POST /player/enter`, `/player/leave`, `/player/say`, `/player/end`,
`POST /player/promises/{id}`, and `POST /director`. Player messages accept
`{to_agent_id, text}`; the profile accepts `{name, about}`; promises accept
`{done, note}`; director accepts `{enabled}`. Validation errors explain why an
action is unavailable. Timeline query filters: `since`, `until`, `agent_id`,
`min_importance` (timestamps `YYYY-MM-DD HH:MM`).

A non-empty value requires HTTP Basic auth for every route, with any username.
Restart after changing it. `EVORIUM_DB_PATH` optionally selects a separate world
file; use that for smoke tests. Existing saves migrate in place, never reset.
See [deploy/README.md](deploy/README.md) for the optional Linux home-LAN service.
No voice, group chat or new hosting service is included.

New model call limits: player replies 300 tokens; daily planning 300 per NPC;
director 300; digest 250; phone dialogue 300 per turn. The existing note-taking
call stays at 900 and due-promise checks at 200. The ordinary daily planning,
director and digest overhead is about ten calls for eight NPCs, excluding
conversation replies and existing promise checks. Failed daily planning is not
repeated that day; cancelled marker rows record that it was attempted.

Token-rate constants are editable in `config.py`. Verified on 2026-11-19 against
[DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/), peak rates per
million tokens: input $0.30 (cache miss) or $0.006 (cache hit), output $1.20. Each call
is priced from the cache-hit count DeepSeek returns (`prompt_cache_hit_tokens`) and is
halved outside peak hours (01–04 and 06–10 UTC, Monday–Friday). Add
`CACHED_INPUT_USD_PER_MILLION` to an older `config.py` only to change the 0.006 default.
Calls priced before 2026-11-19 used peak uncached rates and overstate. Calls without provider usage
are recorded with zero token/cost placeholders and an error indicating unavailable
usage; their actual cost is unknown. Network/HTTP failures are not retried.

## Test

```bash
python -m pytest -q
```

Tests use temporary SQLite files and never call the real API. Schema versioning
uses SQLite's `user_version`; append new entries to `MIGRATIONS` in `evorium/db.py`
for future schema changes. Each connection enforces foreign keys, commits on
success, rolls back on failure and closes when finished.


## Map view

Choose **Map** beside **Dashboard**, or open `/#map`, for a live canvas view of
The Crooked Billet, Patel's News and the empty Northgate unit. The last selected
tab is remembered in this browser. Characters walk between doors, idle at their
spots and show bubbles during running conversations. Lighting and open/closed
signs follow the simulation clock; your player appears when visiting a place.

Walking is cosmetic: the backend remains the source of truth. The map reuses
the dashboard's existing data polling, performs no writes or model calls, and
animates only while visible. At fast clock speeds, interrupted routes catch up
to the latest whereabouts. Click a sprite (or choose its name below the map)
for a portrait, stats, relationship bars and a link to its full dashboard card.

To add the remaining portraits, put `simon.png`, `brenda.png` and `mo.png` in
`evorium/static/portraits/`, then add `'Simon Ferris': 'simon'`,
`'Brenda Ashworth': 'brenda'` and `'Mohammed "Mo" Iqbal': 'mo'` to the
`portraits` map in `evorium/static/index.html`. Until then their popup shows an
enlarged procedural sprite. No image assets or dependencies are used for map
characters.

Optional frontend movement checks, using Node without installing packages:
`node tests/map_view.test.cjs`.


## What characters remember

After each conversation the note-taker scores every fact from 1 to 5: harm, crime
and big decisions affecting others are 5; praise, insults, decisions, odd behaviour
are 4; needs, worries and rumours are 3; small talk is 2 and throwaway detail 1.
Only facts scoring 3 or more are saved, at most three per person per conversation;
the conversation summary still records the gist. Characters see their most
important facts first, then the most recent.

Facts saved before this existed default to 3. To score them once (preview first,
then save with an automatic backup; stop the server before applying):

```bash
.venv/bin/python -m evorium.rescore
.venv/bin/python -m evorium.rescore --apply
```

Low scores are hidden from prompts and the dashboard, never deleted. The server
also writes a rolling log to `evorium.log` in the project folder.
