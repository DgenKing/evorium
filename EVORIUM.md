# EVORIUM — the project in one file

> **This is the only project document.** The idea, how it works, how to run it, the home server, the 3D game,
> what's broken, what's next, the online plan and the full history are all here. `README.md` is just a
> pointer to this file. `AGENTS.md` and `CLAUDE.md` hold the AI instructions; they must stay separate files
> because Codex and Claude look for those exact names. `evorium/static/world3d/assets/LICENSES.md` stays next
> to the files it licenses. Don't create other Markdown docs: add to this file instead.
>
> Earlier documents merged into this one are in git history: the five original briefs and findings
> (`git show 6fec17c:EVORIUM_BUILD_BRIEF_M3.md`, etc.), the old README, the home server guide, the Web3D
> pipeline, controls and verification notes, the portrait prompts, and the M4, Web3D and Unreal Codex briefs.
>
> **Last updated:** 20 November 2026

## Contents

1. [The idea](#1-the-idea)
2. [Where it stands today](#2-where-it-stands-today)
3. [How it works](#3-how-it-works)
4. [The world: cast, places, routines, story](#4-the-world-cast-places-routines-story)
5. [Running it](#5-running-it)
6. [The home server (HP G4)](#6-the-home-server-hp-g4)
7. [The 3D web game](#7-the-3d-web-game)
8. [The website](#8-the-website)
9. [Known issues and open questions](#9-known-issues-and-open-questions)
10. [Next steps](#10-next-steps)
11. [Plan: Evorium online (multiplayer)](#11-plan-evorium-online-multiplayer)
12. [Plan: levelling up](#12-plan-levelling-up)
13. [Art](#13-art)
14. [History](#14-history)
15. [Rules for anyone (or any AI) working on the code](#15-rules-for-anyone-or-any-ai-working-on-the-code)
16. [Measuring success](#16-measuring-success)
17. [References](#17-references)

---

## 1. The idea

Evorium is a game whose characters are not dialogue trees or fixed scripts. They are AI-driven agents with
their own personalities, goals, beliefs, memories, relationships and circumstances. They notice what happens,
make decisions, talk to each other and to the player, and change because of it.

The question behind every character decision:

**Given everything this character knows, wants and remembers, what would they decide to do next?**

Stories should emerge from characters and player choices rather than being prewritten. This is a design goal,
not a claim that the agents are conscious.

**North star:** *build a world where characters have reasons to act, remember what happens, and change because
of it — even when the player isn't watching.*

**Long-term vision:** a convincing, explorable Manchester populated by AI characters whose lives carry on beyond
the player's view. It started as a single-player experiment; the owner now wants an online, multiplayer version
(§11). Behaviour is the game: the characters are decent people who won't stand for abuse, so how you treat them
decides how the world treats you.

### Principles that have held since day one

- **Prove the simulation before building the city.** A readable dashboard beat 3D graphics for the first experiments.
- **The model proposes; Python decides.** The language model returns JSON proposals. Python validates them
  against world rules before anything is written. The model never edits state directly, invents possessions,
  teleports characters or declares other people's private thoughts as facts.
- **Don't call the model constantly.** Movement, routines, sleep, work and money are plain Python. The model is
  called for conversations, note-taking, daily plans, decisions, promise checks, the director and digests.
- **Knowledge boundaries.** Characters know only what they saw, were told, or were seeded with. Hearsay is
  labelled as hearsay; inventions are labelled as rumour.
- **Engine-independent core.** The simulation is a Python service with a JSON API. The dashboard, the 2D map
  and the 3D web game all sit on top of the same brain.

---

## 2. Where it stands today

**One sentence:** eight AI characters live real-time daily routines around a pub and a newsagent in Ancoats,
Manchester; they talk, gossip, remember, make plans and take validated decisions with financial and social
consequences; you can walk in and talk to them in a dashboard, a 2D map or a 3D world in the browser (desktop
and phone); it runs around the clock on the owner's HP G4 and is reachable over the internet.

| Area | State |
|---|---|
| Characters | 8 NPCs + 1 player (Rob, shared by everyone for now) + 1 system ("World") row |
| Places | The Crooked Billet (pub, 09:00–24:00 every day), Patel's News (shop, Mon–Sat 07:00–19:00) |
| Clock | Real UK time × speed multiplier (0 = paused, 1 = real, up to 600×+) |
| Conversations | 4 lines, or 6 for a pair's first meeting or fresh serious news; one at a time worldwide |
| Memory | Facts (seed / observed / told / claim) scored 1–5 for importance; only ≥3 saved or shown |
| Relationships | Directed trust, warmth, familiarity (0–100), shown as words to the model, bars on the map |
| Promises | Extracted from talk, with deadlines; kept/broken changes trust (recording fixed 19 Nov) |
| Plans | Up to two visits/calls per NPC per day, plus at most one action proposal on the morning call |
| Decisions | Fixed menu; one action plus one tell per NPC per day; big decisions need evidence and twelve hours |
| Economy | Visible/private ledger, offers and deadlines, weekly pub settlement, notices, changing routines |
| Story arcs | Python resolves Northgate; darts and flat-hunt templates can follow |
| Catch-up | "While you were away": significant events and gossip, cached narration or bullet fallback |
| Director | Nudges a stalled or looping world with one mundane event a day at most |
| Timeline | Permanent record + daily digest, at `/timeline-page` |
| Dashboard | Character cards, live feed, usage/spend, controls, terrace card, **Restart server** button |
| Map tab | 2D canvas of the pub, shop, empty unit and street; pixel sprites, bubbles, portrait popups |
| 3D game | `/world3d`: Shuttle Street in Three.js, animated characters, third person, touch controls, chat |
| Hosting | HP G4 home server, auto-updating from GitHub, nightly backups, public via ngrok (§6) |
| Model | DeepSeek `deepseek-flash`, JSON mode, temperature 0.8 (0.6 decisions, 0.2 structured calls) |
| Cost | About $0.00015 per call; about $0.40 a day for the whole world at real speed with auto mode on |
| Tests | 226 Python tests + 7 Node map tests + Web3D Node checks and offline Chrome checks, all fake/offline |

### Tech stack and dependencies

Python 3.11+, FastAPI + uvicorn, `sqlite3` (no ORM), `httpx` (no OpenAI SDK), pydantic, plain HTML/CSS/JS
(no framework, no build step), pytest. Three.js 0.187.0 is vendored locally (MIT) for the 3D game. Node runs the
frontend tests and the 3D asset pipeline only; glTF Transform is a build-only tool. Blender rebuilds the 3D
assets. No Docker, no Redis, no `.env` files: the API key is hardcoded in the git-ignored `config.py` (dotenv
loads the wrong file on this machine).

---

## 3. How it works

### The heartbeat (every 5 real seconds, `main._tick_loop`)

1. Read the sim clock (`world.now`).
2. Execute due plans; move everyone to their routine or plan location (`tick.update_routines`).
3. Deliver scheduled world events (letters, phone calls), create offers, notice posted signs, expire deadlines,
   settle overdue Sundays and evaluate Python-owned story outcomes. These continue during model outages.
4. Close idle player chats.
5. In auto mode ("Let them live"): daily digest → due-promise checks → daily plans → budgeted reactions →
   optional ending narration → director check → at most one conversation, at whichever public place has 2+
   people and has waited longest.

DeepSeek failures pause all model calls for 1, 2, 4, 8, then 15 real minutes until a call succeeds. Routines,
letters, settlement and deadlines carry on. Invalid model replies don't trigger the pause; only network, HTTP and
missing-usage failures do. Empty failed conversations stay in SQLite but are hidden from the timeline and map.
Budget or balance errors stop auto mode.

### A conversation (`sim.run_conversation`)

1. Each turn, the speaker gets a system prompt: identity, mood, place and time, their situation (money and
   offers they know about), then what they know for certain, what they've been told (and by whom), their own
   unverifiable claims, promises both ways, how they feel about the listener, broken promises, today's plans,
   people they know of, the last conversation with this person, recent conversations, and **topics already gone
   over today**.
2. The model returns `{"say", "rationale", "mood"}`, validated by pydantic.
3. After the last line, one **note-taking** call extracts per speaker: facts (with source and importance),
   promises (with deadlines), a **feeling** about the other person, new named people and at most one decision;
   plus a summary and any promises now done. The example JSON in that prompt shows a filled-in promise and
   feeling on purpose: empty examples get copied, which silently broke feelings and promises before.
4. Python stores it: facts scored below 3 are dropped (at most 3 kept per person per conversation); feelings are
   capped at ±2 and applied ×2; promises get deadlines; a decision needs at least six verbatim words from that
   speaker and must pass the action checks; both speakers get the summary as a memory; the timeline gets an
   entry.

### Knowledge model

| Source | Meaning | Shown to the character as |
|---|---|---|
| `seed` | Ground truth we wrote | What you know for certain |
| `observed` | They did or saw it | What you know for certain |
| `told` | Someone in the conversation told them | What others told you (may be wrong), attributed |
| `claim` | They asserted it with no basis | Your own guesswork; shown as RUMOUR on the dashboard |

**Importance:** 5 harm, crime, threats, betrayal, someone hurt, big decisions or deals affecting others ·
4 praise or insult, strong feeling, decisions, secrets, odd behaviour, bans · 3 needs, worries, rumours ·
2 small talk (not saved) · 1 throwaway (not saved). Prompts rank by importance, then recency. Seed facts are 4,
delivered story events 5. Low scores are hidden, never deleted. `python -m evorium.rescore` scores facts saved
before importance existed (preview first; `--apply` backs up first; stop the server before applying).

### Relationships

Directed rows (Jess→Dez ≠ Dez→Jess). Changes only come from evidence: +1 familiarity per conversation,
kept promise trust +8 / warmth +2, broken promise trust −12 / warmth −4, note-taker feeling up to ±4 each,
plus the fixed effects of actions. The model only ever sees words ("you are wary of… and like them").

### Decisions, money and consequences (M4)

- **The ledger** (`economy.py`) owns integer stats, changes, offers, asks and notices. Each stat says who can see
  it; characters only get the figures they'd know.
- **The action menu** (`actions.py`): 28 fixed actions with typed arguments, Python checks, atomic effects,
  witnesses and relationship changes. Examples:
  - Dez: change the pint price, set Jess's shifts, announce or start the quiz, ring Northgate, counter the rent,
    accept or refuse the renewal, ask for a loan;
  - Raj: accept or refuse the surrender, ask for more, warn the neighbours;
  - Simon: raise an offer, offer a rent deal, set a deadline (his hidden limits, £60,000 and £3,300, are
    enforced in Python and appear only in his own prompts);
  - Jess: ask for more hours, look for another job, accept or refuse a job offer;
  - others: write quiz questions, start or sign a petition, start or join the darts team, answer asks, tell
    someone a fact, or wait.
- **Three moments to decide:** the morning plan, a conversation (verbatim quote required) and reaction calls
  (`decide.py`) when news, an offer or a deadline arrives.
- **Guards:** one action plus one tell per character per day; big decisions need an important fact the character
  owns, and the same proposal again at least twelve sim hours later ("sleep on it"); at most two big decisions
  in the world per day; at most 12 reaction calls per day. Rejected proposals are kept with their reason.
- **The pub's week** settles every Sunday at 23:59 with no model call: about +£240 at £2,400 rent, −£106 at
  £3,900, and about +£133 at £3,900 with the quiz and a 20p rise. Overheads are tuned to £525. Rent changes only
  when the new lease starts on 25 March 2027. No renewal, or savings below −£2,000, closes the pub. Raj accepting
  closes the shop thirty days later.
- **Endings** (`arcs.py`): Python decides the Northgate outcome (renewed, closed, bust), writes the facts, then
  makes one narration call with a readable fallback. A refused offer can be reopened within fourteen days. Small
  darts and flat-hunt arcs can follow two days after an ending.
- **Catch-up** (`catchup.py`): significant events, ledger changes and gossip about the player since their
  checkpoint, as one cached 250-token paragraph (at most once per sim day and per real ten minutes) or bullets.
  "Gossip" matches the player's name as a whole word.

### The 3D web game

`/world3d` loads vendored Three.js, high or low glTF assets and baked lighting, builds a collision octree from
simple hulls, and animates the third-person player and NPCs. It polls `GET /world/scene` every 1.5 seconds
(5 seconds after errors). That endpoint reads a consistent read-only SQLite snapshot and exposes public presence
and dialogue only, with no model calls. Spot assignments live in Python; the browser handles walking (along a
collision-verified A* graph), bubbles, lighting and doors. Player actions use the existing `/player/*` and
`/catchup` endpoints. NPC rationale and private facts never appear in the player UI. Details in §7.

### Code map

| File | What it does |
|---|---|
| `evorium/main.py` | FastAPI app, tick loop, endpoints, auth middleware, log file, restart endpoint |
| `evorium/world.py` | Sim clock, pub hours, routines (read from the ledger), `whereabouts` |
| `evorium/places.py` | Pub/shop registry, opening hours, who's present, conversation opportunities |
| `evorium/tick.py` | Routine updates, event delivery, due-promise checks |
| `evorium/sim.py` | Conversation runner, note-taking, `turns_for` |
| `evorium/memory.py` | What a character knows (`knowledge_for_prompt`), storing notes, promise resolution |
| `evorium/prompts.py` | Dialogue, note-taking and promise-check prompts |
| `evorium/models.py` | Pydantic schemas and lenient clean-up of model output |
| `evorium/relationships.py` | Trust/warmth/familiarity, bands, card data |
| `evorium/plans.py` | Daily planning, validation, execution |
| `evorium/economy.py` | Ledger, offers, notices, weekly settlement, situation lines |
| `evorium/actions.py` | The action menu, checks, effects, guards |
| `evorium/decide.py` | Reaction calls |
| `evorium/arcs.py` | Story endings and follow-on arcs |
| `evorium/catchup.py` | "While you were away" |
| `evorium/backoff.py` | Shared pause when DeepSeek is failing |
| `evorium/scene.py` | Read-only `/world/scene` snapshot for the 3D game |
| `evorium/director.py` | Stall/loop detection and validated nudges |
| `evorium/timeline.py` | Permanent record and daily digest |
| `evorium/player.py` | The human player |
| `evorium/llm.py` | DeepSeek client, budget cap, usage and cost records |
| `evorium/db.py` | Schema migrations (13 so far), connection helper |
| `evorium/seed.py` | Cast, seed facts, scheduled events, starting relationships |
| `evorium/rescore.py` | One-off importance scoring of old facts |
| `evorium/static/index.html` | Dashboard + tab bar |
| `evorium/static/map.js` | Map tab |
| `evorium/static/timeline.html` | Timeline page |
| `evorium/static/world3d/` | The 3D game (ES modules, data, assets) |
| `evorium/static/vendor/three/` | Vendored Three.js 0.187.0 |
| `tools/web3d/` | 3D asset pipeline and checks (§7) |
| `tools/smoke_server.py` | Offline smoke server on a database copy with fake replies (§5) |
| `deploy/` | Home server installer, auto-updater and backup tool (§6) |
| `website/` | The marketing page (§8) |

### Endpoints

- **Read:** `GET /agents` (adds `today_action`, `considering`), `/usage` (sim time, speed, places, present,
  ledger, `boot_id`, `model_paused_until`), `/events`, `/conversations/latest`, `/conversations/{id}`,
  `/timeline` (filters `since`, `until`, `agent_id`, `min_importance`, `kind` = action/offer/arc; timestamps
  `YYYY-MM-DD HH:MM`), `/player`, `/world/ledger`, `/actions?since=`, `/catchup`, `/world/scene`.
- **Pages:** `/` (dashboard; `/#map` for the map), `/timeline-page`, `/world3d`.
- **Write:** `POST /conversations/run`, `/speed`, `/auto/start`, `/auto/stop`, `/director {enabled}`,
  `/player/profile {name, about}`, `/player/enter {place}`, `/player/leave`, `/player/say {to_agent_id, text}`,
  `/player/end`, `/player/promises/{id} {done, note}`, `/catchup/seen`, `/server/restart`.

---

## 4. The world: cast, places, routines, story

### The cast

| Character | Who | Routine (summary) |
|---|---|---|
| **Dez Whitworth**, 54 | Landlord, The Crooked Billet. Dry, loyal, worried about the lease. | Cash and carry 07–09; behind the bar whenever open (09–24); flat upstairs |
| **Jess Hartley**, 34 | Barmaid, single mum to Alfie. Sharp, tired, needs hours. | Office cleaning weekday mornings; bar shifts 17–23 on Thu, Fri, Sat, Sun (her shift count from the ledger, filled in that order, then Wed, Tue); a drink on Wed evening |
| **Tommy Shaw**, 67 | Retired bus driver. Mischievous; wants the Thursday quiz back. | Walk to shops 10–12; pub most evenings 19–22:30 (Thu from 18) |
| **Raj Patel**, 41 | Runs Patel's News (family shop since 1988). Careful, warm. | Shop Mon–Sat 07–19; quiet half Tue/Thu/Fri evening; Sunday pint |
| **Chloe Barlow**, 29 | Junior architect from Stockport. Looking for a flat. | Work weekdays 9–18; pub Tue/Wed/Fri evening, Saturday afternoon |
| **Simon Ferris**, 46 | Asset Manager, Northgate Estates. Polite, corporate, evasive. | Office weekdays; in Patel's News Thursdays 14:00–14:30 |
| **Brenda Ashworth**, 71 | Retired dinner lady, tenants' association chair. Loves a petition. | Paper at the shop 09:00–09:30; pub Wed evening and Sunday lunchtime |
| **Mo Iqbal**, 38 | Private hire driver, nights. Funny, observant, doesn't drink. | Shop 16:00–16:20; pub Tue early evening and Sunday afternoon; drives 19:30–04 (so never at the Thursday quiz) |

When the quiz runs (Thursdays 19:30–22:30), Tommy, Brenda and Chloe come in if they're free. A closed pub or shop
sends its people home. House rule: names mostly British, a few others.

### The story seed

Northgate Estates bought the freehold of the whole terrace (pub, newsagent and the empty unit between) three
months ago. Simon's instructions: bring rents to market level, buy out leases where cheaper.

- Pub renewal proposed: **£3,900 a month, up from £2,400**, from 25 March 2027 (letter Thu 19 Nov 09:00).
  **Reply due 17 Dec 09:00.**
- Raj offered **£45,000 to surrender his lease** (phone call Wed 18 Nov 11:00). **Expires 18 Dec 11:00.**
  Simon can go to £60,000 and won't volunteer it.
- No planning application yet; redevelopment discussed but not decided.
- Side threads: the Thursday quiz (quizmaster left 18 months ago; Tommy promised forty questions by Sunday),
  a darts team for Mo, Jess's shifts, Chloe's flat hunt, Brenda's petitions.

### What has actually happened

- **Mon 16 Nov evening:** six pub conversations among Dez, Jess and Tommy, going round in circles on the lease
  and the quiz. Tommy's rumour "people poking round the street" spread, correctly tagged as rumour.
- **Tue 17 / Thu 19 Nov:** the player (Rob) told Raj he sells drugs, offered him crack and used a racist slur.
  Raj refused to serve him and banned him, and remembered it across visits.
- **Thu 19 Nov:** Dez rang Simon about the £3,900 rent ("market-level assessment"); Simon visited Raj about the
  surrender. That evening Raj finally told Dez and Jess about the £45k, and Dez and Raj worked out Northgate may
  be clearing the terrace. Dez quoted the real figures to Jess (£3,900 rent against £3,520 takings, £6,000 in
  reserve). Rob insulted Jess and claimed to have a gun; Jess barred him and told Dez to ring the police. Dez
  promised to; next time Rob walked in, Jess said "You've got a nerve showing your face back in here".
- **First decisions:** Raj and Dez both chose to wait. Raj: tempted by £45k against £18k savings, but suspects
  Northgate is buying the whole block. Dez: the rent is firm, so he'll see what the takings do first.

---

## 5. Running it

### On a development machine

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp -n config.example.py config.py      # then put your DeepSeek key in config.py
uvicorn evorium.main:app --host 127.0.0.1 --port 8000
```

- Open `http://127.0.0.1:8000`. Startup creates `evorium.sqlite3` and seeds the cast if it's absent;
  restarting reuses the database. Existing saves migrate in place and are never reset.
- **Stop:** Ctrl+C, or `pkill -f "uvicorn evorium.main:app"`. **Restart after code changes:** the "Restart
  server" button, top right of the dashboard (it re-runs the same command and the page reloads itself).
- **The real world lives on the G4 now (§6).** On the main PC, only run copies: `EVORIUM_DB_PATH=/path/to/copy.sqlite3`
  and never switch on auto mode against a second copy of the real world.
  `http://<PC's LAN address>:8000`. This exposes the server and its controls to your network.

### Settings (`config.py`, git-ignored)

| Setting | Default | What it does |
|---|---|---|
| `DEEPSEEK_API_KEY` | `"sk-..."` | Your key. Hardcoded here only; never in frontend code, logs or git |
| `DEEPSEEK_MODEL` | `deepseek-flash` | Model name |
| `MAX_SPEND_USD` | 4.00 | Local cap: new calls are refused once estimated spend reaches it (not a provider cap; "remaining" assumes the original $5) |
| `INPUT_USD_PER_MILLION` / `CACHED_INPUT_USD_PER_MILLION` / `OUTPUT_USD_PER_MILLION` | 0.30 / 0.006 / 1.20 | Peak prices; off-peak is half |
| `REACTION_CALLS_PER_DAY` | 12 (max 12) | World-wide reaction budget |
| `CATCHUP_COOLDOWN_SECONDS` | 600 (min 600) | Real-time gap between catch-up narrations |

Environment variables: `EVORIUM_DB_PATH` (another world file), `EVORIUM_LOG_FILE` (another log file; empty turns
the file log off, as the tests do), `EVORIUM_SMOKE_DB` (where the smoke server copies the world).

### Model calls and cost

- **Limits:** dialogue and player replies 300 tokens; note-taking 900; promise checks 200; daily planning 400 per
  NPC; reactions 350 (at most 12 a day); director 300; digest 250; arc narration 300; catch-up 250. Planning,
  director and digest add about ten calls a day for eight NPCs. Failed daily planning isn't repeated that day.
- **Prices** (checked 19 Nov 2026, [DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/)), per
  million tokens at peak: input $0.30 on a cache miss, $0.006 on a cache hit, output $1.20. Each call is priced
  from the `prompt_cache_hit_tokens` DeepSeek returns, and halved outside peak hours (01–04 and 06–10 UTC,
  Mon–Fri). Calls priced before 19 Nov used the old peak, uncached rate and overstate.
- **Real cost:** about $0.00015 a call. A 4-line conversation with notes is about $0.0008; $1 buys about 1,000
  conversations.

### Logs

`evorium.log` in the project folder rolls at 5 MB and keeps 3. On the G4, also `journalctl -u evorium`.

### Tests

```bash
.venv/bin/python -m pytest -q        # 226 tests
node tests/map_view.test.cjs         # map
node tests/world3d.test.mjs          # 3D routes, animation states, quality, slots, cast
bash tools/web3d/run_checks.sh       # 3D: smoke server + 20 headless screenshots and movement checks
```

Tests use temporary SQLite files and never call the real API. `tests/conftest.py` turns off the file log and the
SQLite's `user_version`). Each connection enforces foreign keys, commits on success, rolls back on failure and
closes when finished.

### The smoke server (offline, fake replies)

```bash
.venv/bin/python tools/smoke_server.py
```

It copies the live world with SQLite's read-only backup to `/tmp/evorium-smoke/smoke.sqlite3`, binds only
`127.0.0.1:8011`, turns auto mode off and replaces every model client with a fake. Open
`http://127.0.0.1:8011/world3d` to try the 3D game against it. It refuses to start if 8011 is busy. Never point
automated player tests at port 8000.

### Git safety

Commit `config.example.py`, never `config.py`. Before committing, check `git status --short`. Don't use
`git add -f` for ignored files, and don't upload the working folder through GitHub's web uploader (it ignores
`.gitignore`). `*.zip`, databases, logs, backups and `website/images/src/` are ignored.

---

## 6. The home server (HP G4)

The real Evorium runs on the owner's always-on **HP ProDesk 405 G4 Mini** (Ryzen 5 PRO 2400GE, 16 GB RAM,
128 GB, Ubuntu 26.04, LAN address <server-address>), under the account **`<server-user>`**, in `<project-dir>`.

- **Public address:** **https://<tunnel-domain>** (3D game at `/world3d`). Visitors click
- **Everything comes from GitHub.** Work on the main PC and push to `main`; the G4 updates itself.
  on the G4.

### How updates work (automatic)

Every 2 minutes `evorium-update.timer` runs `deploy/auto_update.sh`. When `main` has something new, it:
1. backs up the world;
2. fast-forwards to the new code, installing packages if `requirements.txt` changed;
3. runs all the tests;
4. restarts the game if they pass, or **rolls back** and keeps the old code running if they fail. A failed commit
   is tried once; the next push gets a fresh try.

It logs to `~/evorium/updates.log` and writes failed test output to `last_update_tests.txt`. It refuses to
update if code was edited on the G4 itself, so never edit code there. Only push finished work to `main`: it goes
live within minutes.

### Services on the G4

| Service | What it does |
|---|---|
| `evorium` | The game, on 127.0.0.1:8000, restarts itself if it stops and starts at boot |
| `evorium-update.timer` | Auto-update from GitHub every 2 minutes |
| `evorium-backup.timer` | Nightly backup at 03:15 to `backups/`, keeping 14 (`deploy/backup_world.py`, SQLite backup API). A systemd timer because Ubuntu 26.04 has no cron by default |
| `evorium-ngrok` | The public tunnel: `ngrok http 8000 --url=<tunnel-domain>`. A plain systemd unit, because snap ngrok can't run `ngrok service install` |

A sudoers rule lets `<server-user>` run `systemctl restart evorium` only, for the updater.

### Everyday commands (on the G4)

| What | Command |
|---|---|
| Is it running? | `sudo systemctl status evorium` |
| Watch the live log | `sudo journalctl -u evorium -f` |
| Restart | `sudo systemctl restart evorium`, or the dashboard's Restart button |
| Watch auto-updates | `tail -f ~/evorium/updates.log` |
| Check GitHub right now | `bash ~/evorium/deploy/auto_update.sh` |
| Why did an update fail? | `cat ~/evorium/last_update_tests.txt` |
| Back up now | `cd ~/evorium && .venv/bin/python deploy/backup_world.py` |
| Restore a backup | `sudo systemctl stop evorium`, copy a file from `backups/` over `evorium.sqlite3`, `sudo systemctl start evorium` |
| ngrok status | `systemctl status evorium-ngrok`, or the ngrok dashboard |

### Setting up a server from scratch (for reference)

1. **Account:** `sudo adduser evorium` (any name), then give it admin rights from an admin account:
   `su - <admin>` → `sudo usermod -aG sudo <name>` → `exit` → `exec su - <name>`.
2. **Basics:** `sudo apt update && sudo apt install -y python3 python3-venv git openssh-server`.
3. **Code:** `cd ~ && git clone https://github.com/DgenKing/evorium.git && cd evorium` (the repo is public).
4. **World and config, from the main PC:** stop its server, then
   `scp ~/projects/evorium/config.py ~/projects/evorium/evorium.sqlite3 <name>@<address>:~/evorium/`.
   the `evorium` service, auto-update, the sudoers rule and the nightly backup, and takes a first backup. Safe to
   re-run.
6. **ngrok:** `sudo snap install ngrok`, `ngrok config add-authtoken <token>`, test with `ngrok http 8000` (the
   free plan uses the account's fixed domain), then create the `evorium-ngrok` systemd unit (User=<name>,
   `ExecStart=/snap/bin/ngrok http 8000 --url=<domain> --log=stdout`, `Restart=always`) and
   `sudo systemctl enable --now evorium-ngrok`.
7. **Stay up:** Settings → Power: automatic suspend off. BIOS (F10 on HP): After Power Loss → Power On.

### Good to know

- Everyone who logs in shares the one player (Rob) and sees the owner's god view, including characters' private
  thoughts, until accounts are built (§11).
- Home upload speed limits how fast the 3D files reach each visitor; fine for a handful of people.
- Later, with real players, the same setup moves to a VPS: it's a copy-the-world-file job.

---

## 7. The 3D web game

Open `/world3d`, or **3D** in the dashboard header. No build step or runtime Node: Three.js, the high/low assets,
ten animation clips and baked lighting are served by FastAPI. The EVORIUM wordmark returns to `/`.

### Controls

- **Desktop:** WASD/arrows walk, Shift run, Space jump, drag to look, wheel zoom, E to talk within 2 m, N name
  tags, C collision wireframe, F1 debug HUD, Escape closes chat or settings. Closing chat saves notes via
  `/player/end`.
- **Phone:** left-thumb joystick (push far to run), drag on the right to look, two-finger pinch to zoom, Jump
  button and a Talk button that appears near someone. Landscape is suggested. The chat panel stays above the
  on-screen keyboard (`visualViewport`).
- **Settings (gear):** quality, name tags, invert look, sensitivity; remembered in the browser.

### Quality

Touch or narrow screens start on **low**; desktops pick **medium** or **high** from the GPU's capabilities. Pixel
ratio caps: low 1, medium 1.5, high 2. Below 28 fps for a sustained period it steps down, at most twice (keeping
the loaded assets); choosing a preset reloads the matching asset set. Override with `?quality=low|medium|high`.

### What's in it

- The kit's Shuttle Street, Crooked Billet and Patel's News, exported from `Ancoats.blend`, with 44 collision
  hulls and 15 waypoints converted to three.js space (x, z, −y).
- Characters: CC0 Quaternius Universal Base Characters (male and female "Superhero" stand-ins, the bodies in the
  free Standard pack), tinted per character with clothing masks and scaled, using 10 clips from the Universal
  Animation Library (idle, walk, run, jump, land, sit, talk and more). The rigs match, so no retargeting.
- Baked indirect lighting (Cycles, 128 samples, 2048 high / 1024 low atlas); night dims the bake and uses
  glowing windows and runtime lights.
- Assets: **low 3.40 MB / 124,232 triangles**, **high 5.15 MB / 173,338 triangles**; vendor modules add about
  2.4 MB uncompressed. Licences in `evorium/static/world3d/assets/LICENSES.md`.
- Physics: capsule-and-octree walking with step-up, a 1.03 m jump, wall and closed-door blocking, and a camera
  that never clips through walls.
- NPCs follow `/world/scene` along a route graph (746 nodes, 4,697 verified edges; every waypoint reachable from
  both street ends), with slot offsets, sitting and talking poses, name cards and speech bubbles.

### Rebuilding the assets

Needs Blender 4.3+ (built with 5.3.0), Node 24/npm, Python with Pillow, Chrome, both Quaternius **Standard** zips
in `~/Downloads/evorium-characters/`, and the unlocked kit at
`/run/media/user/Data Storage/Evorium/AncoatsKit/Ancoats_Blender_Kit/`. Run from the repository root:

```bash
mkdir -p tools/web3d/raw/characters
python3 - <<'PY'
from pathlib import Path
from zipfile import ZipFile
for path in (Path.home() / 'Downloads/evorium-characters').glob('*.zip'):
    with ZipFile(path) as archive:
        archive.extractall('tools/web3d/raw/characters')
PY
npm ci --prefix tools/web3d --registry=https://registry.npmjs.org
(cd tools/web3d/raw && npm pack three@0.187.0 --registry=https://registry.npmjs.org && tar -xzf three-0.187.0.tgz)
node tools/web3d/vendor.mjs
blender -b '/run/media/user/Data Storage/Evorium/AncoatsKit/Ancoats_Blender_Kit/Ancoats.blend' -P tools/web3d/export_set.py -- --out tools/web3d/raw
node tools/web3d/build_characters.mjs
blender -b -P tools/web3d/bake_lighting.py
bash tools/web3d/optimise.sh
```

- The scripts never save the kit's `.blend`. Folder names containing "unreal" inside the kit and the Quaternius
  pack are the packs' own names; leave them.
- `raw/blend_inventory.txt` and `raw/characters_inventory.txt` record what was exported and checked. A broken
  `_png.png` texture name in the pack is repaired from its matching PNG.
- `data/budgets.json` fails the build above 12 MB / 150k triangles (low) or 30 MB / 400k (high).
- Three.js 0.187.0 ships no minified build: `three.module.min.js` is the unmodified module, plus its
  `three.core.js` sibling. `node_modules/` and `raw/` are git-ignored.

### Checks

`bash tools/web3d/run_checks.sh` starts its own smoke server, then drives Chrome over the DevTools protocol:
20 screenshots (street, pub, shop, cast, player × low/high × 1280×720 and 390×844) to `tools/web3d/raw/screens/`
with a contact sheet, plus a scripted walk through both doors, jump, closed doors, camera collision, fake chat
and a 60× routine change. Blank images fail. `--movement-only` and `--screens-only` run parts. Test URLs:
`/world3d?test=1&cam=street|pub|shop|cast|player&quality=low|high` (fixed camera and time; exposes
`__evoriumReady` and `__evoriumReport`). Player-writing checks refuse any server that isn't the fake one.

Headless Chrome uses software rendering (SwiftShader), so its FPS (about 4–11 low, 2 high) says nothing about
real phones or the GTX 1060. Real iOS memory, keyboard and touch need a physical phone.

---

## 8. The website

A one-page marketing site in `website/` (`index.html`, `styles.css`, local images), plain HTML/CSS, theme
"Ancoats after dark" (ink, brick, Billet green, amber; Fraunces and Inter). Pitch: "The street doesn't stop
when you leave". It describes the Three.js browser game on desktop and phone. Preview without the game:

```bash
python3 -m http.server 8080 --bind 127.0.0.1 --directory website
```

Images are generated, labelled concept art; full-size masters stay in the git-ignored `website/images/src/`.
Some image filenames keep their original names (`unreal-hero`). The waitlist still uses the placeholder
`hello@example.com`. Editing these files doesn't publish the site. Personal contact details remain deferred.

**Briefing website changes** (the old `CODEX_PROMPT_WEBSITE.md`, merged here and deleted 20 Nov): describe it as
a Three.js browser game for desktop and phone; plain HTML/CSS with at most ~30 lines of JS; no frameworks or
build step; no "Home" link; no forms collecting data; fictional characters only; images as optimised WebP/JPG
with `<picture>`, lazy loading and alt text; accessible and responsive at 375, 768 and 1440 px. Colours:
`--ink #0D0E11`, `--ink-2 #16181D`, `--brick #8E3B2C`, `--billet #1E3A32`, `--amber #E8A548`, `--cream #EFE7D6`,
`--mist #9AA0A8`. Image style: cinematic 35mm film still of Manchester at dusk, warm pub light against cool
streets, film grain, matching the game's portraits.

---

## 9. Known issues and open questions

- **One shared player.** Everyone who logs in is Rob and sees the owner's god view. Accounts are the next big job (§11).
- **Barring isn't enforced.** A character can say the player is barred, but nothing stops them walking back in,
  and a later greeting may be friendly. Needs an action (e.g. `bar_customer` for Dez and Jess) that the player
  endpoints respect. **On hold (owner, 19 Nov)** while the owner tests by provoking characters; when built,
  include a testing override (an unbar button or switch).
- **Serious incidents barely move relationships.** Feelings are capped at ±2 (×2), so threats of violence cost
  only −4. Consider down to −5 (×2 = −10) for threats and violence.
- **The quiz loops.** "Forty by Sunday" was restated in 4 conversations before promises were recorded; check it
  stops now that promises save.
- **3D polish:** stand-in bodies (bald, simple clothing masks, no hair or faces); NPC catch-up snaps rather than
  fading and departures vanish at the route end; NPCs can overlap while walking; speech bubbles near the screen
  edge get cut off; shared lightmap gives small props little detail; no separate night bake or bloom.
- **Not yet tested on a real phone**, especially iPhone memory, keyboard and touch.
- **Daytime pub is empty on weekdays:** only Dez before late afternoon. Option: Tommy after his walk, Brenda at
  lunchtime.
- **Director heuristics** are conservative word checks; since M4 it also rejects any digit and words such as set,
  pay, close and sign, so many of its ideas get dropped.
- **A failed reaction call is used up**; the "offer nearly due" reminder three days before expiry gives another
  chance.
- **M4 simplifications:** fixed two-hour reaction delay (sixteen hours to reconsider); the flat viewing and the
  outside job are small Python templates; pub income is an illustrative model, not accounting.
- **Old trivia still visible** until `python -m evorium.rescore --apply` is run once.
- **Spend recorded before 19 Nov is overstated** by about $0.09 (old pricing).
- **Security to-dos:** reset the ngrok authtoken (exposed in chat on 20 Nov) and replace the placeholder
- **Starlette test-client deprecation warning** (harmless).

---

## 10. Next steps

1. **Play and review the 3D game** on desktop and a real phone; fix whatever is worst (likely the stand-in
   bodies, bubbles at the screen edge, NPC overlap and fades).
2. **Watch the story run** on the G4 for a few days: decisions, promises now being recorded, and Northgate coming
   to a head on 17–18 Dec. Review the pacing and the settlement constants.
3. **Multiplayer accounts** (§11): each player their own character, login, reputation, catch-up and spending
   limit; players' page separate from the owner's god view; NPC reasoning hidden.
4. **Fix the scaling limits** before many players (§11 hosting notes): parallel conversations, SQLite WAL, a
   cached scene snapshot.
5. **Barring and bigger relationship swings** once the owner has finished provoking-tests.
6. **An inspector:** free Python health checks (no promises today, loops, no decisions, failure spikes, cost) plus
   one cheap daily AI review that reports, never fixes.
7. Install the friend's eight new portraits (add `simon.png`, `brenda.png`, `mo.png` and register them in the
   `portraits` map in `index.html`); decide on daytime pub visitors; run `evorium.rescore --apply` once.
8. Then a small online test with 5–10 friends, before planning for large numbers.

---

## 11. Plan: Evorium online (multiplayer)

> Status: **hosting done (§6); accounts not started.** Decisions recorded here are the owner's.

### The vision

Players create an account, set a name and picture, and join **one shared Ancoats**: the same characters,
meeting each other. The characters remember every player, gossip about them, and the world carries on when
players are offline.

### How it's paid for (owner's decision)

- **Players bring their own DeepSeek API key** and top up their own account with at least a couple of dollars.
  Their own conversations run on their key.
- **"Keep Ancoats running while I'm away" is ON by default; players can opt out.** While on, a small share of
  the world's background calls is made with their key, rotating across contributors. No money moves between
  players and the game.
- **Scale:** the shared world costs roughly $0.10–0.40 a day at real speed; split across 20 contributors that's
  about a penny a day each.
- **Player settings:** spending limit; keep-running toggle; instant pause; remove my key. Profile shows e.g.
  "$0.43 this month: $0.31 your chats, $0.12 keeping Ancoats running".
- **When nobody contributes**, the world goes quiet until someone plays, or the owner keeps a backstop key.

### ⚠️ DeepSeek's terms (checked 19 Nov 2026)

DeepSeek Open Platform Terms of Service, effective 29 Apr 2026, **section 2.2**:

> "Please keep your created API key securely, prevent any form of leakage, do not share or publicly disclose
> your API key with others, and do not expose it in browser or other client-side code. You will be solely
> responsible for any fees incurred and losses caused by sharing or leaking the API key."

Section 4.1 makes the key owner responsible for all inputs and outputs on their key. A player pasting their key
into Evorium is, strictly, sharing it; the risk sits with the player. The owner has chosen to go ahead, with:
an honest line where players add their key; keys **encrypted at rest** with a master key outside the database,
never sent back to the browser; the game enforcing each player's spending limit; per-player usage from
`llm_calls` plus a "paid by" column. Alternatives if needed: the owner's key plus credits sold via Stripe
(allowed, §1.1 and §3), or a user-paid provider such as OpenRouter's sign-in flow (not yet checked).

### Players online vs offline

- **Online:** your character is in the world; you walk into the pub or shop and talk.
- **Offline:** you're not there. NPCs keep living, and remember and gossip about you.
- **Coming back:** "While you were away": what happened, and who's been talking about you.

### Behaviour is the game

Players will swear, insult and threaten; the NPCs won't stand for it, and that's the point. Bad behaviour costs
you in the world: trust drops, gossip spreads, you get barred, nobody lends you money. Good behaviour earns the
opposite. This is "surviving in Manchester", and it ties into levelling (§12).
- **Each player's standing is their own:** one troll can't spoil the world for everyone, but their behaviour
  becomes gossip about them. Barring applies to that player only.
- **Hide NPC reasoning from players.** The dashboard chat shows each reply's private rationale; a public player
  must see only what the character says (the 3D game already hides it).
- **Moderation is still needed** for abuse aimed at real players and content the provider refuses: a light
  filter and per-player rate limits.

### Hosting notes

- The G4 (or an OVH VPS-2 later) is plenty: rendering runs on players' devices and the AI on DeepSeek.
- **The real limits are in the code. Fix before scaling:**
  1. **One conversation at a time worldwide** (`_run_lock` in `main.py`): run them in parallel, one per place.
  2. **SQLite without WAL mode:** turn on `PRAGMA journal_mode=WAL` and a busy timeout.
  3. **One player row:** accounts and per-player memory are the biggest job.
  4. **A single uvicorn process** with the tick thread and in-memory state; fine at first.
  5. **`/world/scene` polled every 1.5 s per player:** build it once per tick and serve the cached copy.
- **Bandwidth:** 3–8 MB of 3D assets per new player; put a CDN (e.g. Cloudflare) in front of static files later.
- **Cost driver:** DeepSeek, not the server.
- **Cast size:** grow slowly (12–20 well-written neighbours) rather than 100 generic NPCs.

### What has to be built

| Area | Work |
|---|---|
| Profiles | Name, picture (preset avatars first; uploads need moderation) |
| Player view vs admin view | Players see the world, their own chats, what they've learned, their standing. Owner keeps the god view; restart, speed, director and auto become admin-only |
| Multi-player conversations | Several players talking to different NPCs at once |
| Key pool | Encrypted storage, rotation, fair share, per-player caps, fallback when a key fails |
| Moderation | Rate limits, report button, account bans, upload filtering |
| Legal | Privacy policy and terms (UK GDPR: emails, keys, chat logs), age limit |

Suggested order: invite-only with friends, accounts + player view, then the key pool, then open sign-ups.

---

## 12. Plan: levelling up

> Status: **idea.** Build progression from what the sim already tracks, so what the game says about you and how
> characters treat you never disagree.

1. **Neighbourhood standing** from trust, warmth and familiarity across the cast:
   **Stranger → Newcomer → Regular → Local → Pillar of the Community.**
2. **Unlocks:** Regular — Dez knows your usual. Local — characters share secrets (Raj mentions the £45k, only if
   he trusts you). Pillar — invited into the story: Brenda's petition, running the quiz, the darts team.
3. **Per-character reputation:** the trust/warmth bars are the progress bars; milestones like "Tommy's drinking
   buddy".
4. **Promises as quests:** deliver and trust jumps; break it and everyone hears.
5. **The dark path:** behave like Rob and build **notoriety**: bans, gossip, a different storyline.
6. **Patron of Ancoats** badge for players who keep "run while away" on.

---

## 13. Art

- **Portraits** (`evorium/static/portraits/`, 256×256 PNG, fictional people): `dez`, `chloe`, `tommy`, `jess`,
  `raj`. Generated with one shared prompt: *"Use case: photorealistic-natural. Square character avatar for
  Evorium, a Manchester pub social simulation. One fictional character portrait: [who]. Natural realistic
  editorial photograph, head and shoulders, looking toward camera, centred face with room for a circular crop.
  Soft warm pub window lighting, muted dark blurred pub background, realistic skin, approachable everyday person,
  consistent series. No text, labels, collage, watermark, props or other people."* The "[who]" lines:
  - Dez Whitworth, 54, pub landlord: weathered face, short greying hair, light stubble, dark polo shirt, dry
    kindly expression.
  - Chloe Barlow, 29, junior architect from Stockport: shoulder-length light brown hair, thoughtful friendly
    expression, green knit top.
  - Tommy Shaw, 67, retired bus driver: balding silver hair, lined face, navy cardigan over checked shirt, warm
    mischievous smile.
  - Jess Hartley, 34, barmaid and single mum: dark brown hair tied back, tired but sharp friendly expression,
    dark work shirt.
  - Raj Patel, 41, British Indian newsagent: short black hair with a little grey, trimmed beard, casual shirt,
    careful warm expression.

  A friend has since made **all eight** in one style; install them (§10).
- **Place renders** from the friend: the Crooked Billet and Patel's News exterior, both interiors, a brick
  texture. Candidates for the map backdrop.
- **The art kit, `Ancoats_Blender_Unreal_Kit.zip`** (moved out of the project to `/run/media/user/Data Storage/Evorium/`; 148 MB, 102 files, second version, 19 Nov;
  over GitHub's file limit). Unpacked at `/run/media/user/Data Storage/Evorium/AncoatsKit/`:
  - **Set:** "Shuttle Street", with The Crooked Billet (dark green, oak bar, hand pumps, oxblood booths) and
    Patel's News (blue and cream, aisle, parcel counter, chillers), in front of a mill backdrop. The 3D game is
    built from `Ancoats.blend`.
  - **Waypoints:** PUB_ENTRY, PUB_HOST, PUB_BAR, PUB_BOOTH, PUB_WINDOW, PUB_DART, NEWS_ENTRY, NEWS_TILL,
    NEWS_QUEUE, NEWS_RACK, NEWS_CHILLER, NEWS_PARCELS, STREET_LINK, STREET_WAIT, CYCLE_RAIL (metres, Blender
    axes).
  - **The kit's own 8 characters** (Janine Ward, Sanjay Patel, Frank Doyle, Amina Okafor, Imran Malik, Ewa
    Kowalska, Rory Campbell, Val Mercer) have an idle pose only and aren't used; the game uses the Quaternius
    bodies. If the friend ever builds animated models of Evorium's own cast, they can replace the stand-ins.
- **Voice** (speech in and out) remains a later goal.

---

## 14. History

### Session of 20 November 2026 — Website brief corrected

- Checked `CODEX_PROMPT_WEBSITE.md`: the previous edit had updated the website, but
  left the brief's Unreal Engine 5 copy and image-style prompt unchanged. Corrected
  it to match the Three.js browser client, including the hero, §2.9 copy and caption.
- Clarified that this is maintenance of the existing static marketing page, with
  existing imagery reused and still labelled concept art. Historical `unreal-hero`
  asset names/provenance stay intact. No public game launch or embed is implied.
- Updated obsolete section references and instructions to create extra README files
  to follow the consolidated-document rules. Explicitly kept personal addresses
  deferred and the placeholder waitlist email unchanged.
- Verified the brief no longer prescribes Unreal rendering, new README files or
  regeneration of all images. No website code, game state, commits or deployment changed.


### Milestone 1 — smallest working slice (15 Nov 2026)

Two characters (Dez and Chloe) in one pub exchange a conversation via DeepSeek, saved to SQLite, shown in the
browser, surviving a restart. Budget guard, JSON-only replies validated by pydantic with one retry, every call's
tokens and cost recorded. First real call: about $0.0003.

**Free-run findings** (10 minutes, 39 auto conversations, $0.055). Information genuinely spread and characters
stayed in voice, but: commitments were forgotten (only the last 3 memories reached the prompt); every pair met
"fresh"; claims grew (the surveyor gained a suit, a clipboard and an invented regular called Bernie); and 43
"I'll…" promises were never carried out. These shaped everything after: structured note-taking, the four fact
sources, a commitments table, seeded world facts, a paced world clock and a registry of named minor NPCs.

### Milestone 2 — five characters, structured memory, real-time world (15 Nov)

Five characters with seeded facts; a note-taking call after each conversation; claims fed back as unverifiable;
the real UK clock with speed control; weekly routines; the tick thread; scheduled world events; due-promise
checks; "Let them live" auto mode.

### Milestone 3 — player, relationships, timeline, director, cast (16 Nov)

Built in eight phases from one brief: agent kinds and sim timestamps; the permanent timeline and daily digests;
the player; directed relationships; places, free time and daily plans; the director; Simon, Brenda and Mo;
old world's 16 conversations are kept in `backups/evorium-backup-20261116.sqlite3`.

### 19 November 2026

- **Map tab** (Codex): canvas scene, procedural pixel sprites, walking between doors, idling, speech bubbles,
  day/night, click popup with portrait, stats and trust/warmth bars.
- **Pub hours** 09:00–midnight every day; Dez's cash-and-carry moved to 07–09.
- **Conversation review** found relationships had never changed (feelings missing from the note-taker's example
  JSON), shop chats capped at 2 lines, trivia crowding out important facts, a topic loop, and Raj sitting on the
  offer. **Fixes:** importance scoring, capped-not-dropped feelings, longer conversations when it matters,
  "topics already gone over today", director loop detection, planner nudged by serious news, rotating log,
  `evorium.rescore`.
- **Restart server button** on the dashboard.
- **Cost estimates fixed:** priced from DeepSeek's cache-hit count and off-peak hours; estimates had been about
  3× the real bill.
- **Conversation count:** 48 rows, none missing: 25 real and 23 empty failures, all in 5 minutes while DeepSeek
  was failing (fixed by M4's backoff). Best so far: Dez ringing Simon about the rent (#10), Simon and Raj
  (#11–12), Jess holding Dez to account (#41).
- **Git:** a VS Code commit hung waiting for its message tab and had the art zip staged; `*.zip` is now ignored.
- **One project file:** five earlier docs merged into EVORIUM.md; `AGENTS.md` and `CLAUDE.md` require keeping it
  current.
- **M4 built by Codex: decisions and consequences.** Backoff, ledger and weekly settlement, offers, 28 actions,
  decision guards, routines and notices, reactions, Northgate endings and follow-on arcs, catch-up, dashboard
  terrace card, map and timeline additions. Migrations 10–13. The live world migrated with nothing lost, and
  offers were created from the already-delivered letters with the right deadlines.
- **M4 review (Claude) fixed:** Simon's hidden limits leaking into the note-taker's prompt (and 6,000 characters
  per call), gossip matching "Rob" inside "problem", invalid replies pausing the whole world, unreadable rejection
  messages, the morning plan's token limit, and tests writing to the real log.
- **Evening review (#49–#62):** relationships moving for real reasons, Raj telling Dez and Jess, money figures in
  dialogue. **Bug found and fixed: no promise had ever been recorded** in 62 conversations; the note-taker's
  example showed an empty promise list and the model copied it. The example now shows a filled-in promise, and
  `memory.EXAMPLE_COMMITMENT` drops it if copied.
- **Launch website** built by Codex (`website/`, §8).

### Unreal Engine 5 trial — dropped (19–20 November 2026)

An Unreal Engine 5 client was built and played, but it was too heavy to ship: huge installs, a GTX 1060 only just
able to run it, and no browser or phone play. On 20 Nov the owner chose the Three.js browser client and removed
Unreal from the project.

### 20 November 2026

- **The 3D web game** (Codex, from the Web3D brief): `/world3d` with the kit's street, Quaternius animated
  characters, baked lighting, desktop and touch controls, NPCs following the server, and player chat. 226 Python
  tests, map and Web3D checks, and 20 headless screenshots passed.
- **Home server on the HP G4:** installer, auto-update from GitHub with tests and rollback, nightly backups,
  ngrok as a systemd unit. The world moved from the main PC (464 KB). Public at
  https://<tunnel-domain>.
- **First auto-update rolled back, as designed:** a new 3D test failed because the G4's `config.py` sets a
- **The 3D game is live:** the G4 auto-updated and the owner played `/world3d` over the internet. Owner's
  verdict: "this is more than good enough for what we need".
- **Unreal removed**; `tools/smoke_unreal.py` renamed `tools/smoke_server.py`.
- **Website copy updated** by Codex for the browser game.
- **All docs merged into this file.** The old README, the home server guide, the Web3D pipeline, controls and
  verification notes, the portrait prompts, the old LAN service notes and the finished M4 and Web3D briefs were
  folded in and deleted (they're in git history). `README.md` now just points here.
- **Clean-up:** the website brief merged into §8 and deleted; the old `server.log` and `__pycache__` deleted; the
  two old world backups moved into `backups/`; the art kit zip moved to the Data Storage drive next to the
  unpacked kit. The project folder now holds only code, config, the dev world copy and this document.

---

## 15. Rules for anyone (or any AI) working on the code

1. **Never lose the live world.** The real `evorium.sqlite3` is on the G4. Back up before risky work; never
   delete, recreate or reseed over it. Schema changes only by **appending** to `MIGRATIONS` in `db.py`; every
   migration must apply to the live database and an empty one.
2. **Secrets:** the API key lives only in `config.py`. Never print, log or commit it. No dotenv, no `.env`.
   New settings go in `config.example.py` and are read with `getattr(config, "NAME", default)`.
3. **The model proposes; Python decides.** JSON only, validated by pydantic, checked against world rules,
   dropped and logged if invalid.
4. **Tests never hit the real API**, and never depend on the machine's own `config.py`. Use fake clients. Leave
   the suite green after every change: the G4 refuses any push whose tests fail.
5. **Fixed stack:** Python, FastAPI, `sqlite3`, `httpx`, pydantic, plain HTML/CSS/JS, vendored Three.js. No new
   runtime dependencies, frameworks, ORMs, build steps or Docker without asking.
6. **Budget:** keep `max_tokens` small and state it for any new call; smoke-test on a copy, on another port.
7. **UI:** escape every string (`esc()` or `textContent`); the EVORIUM title links to `/`; **never add a "Home"
   link**; never show NPC rationale to players.
8. **Don't invent requirements.** Pick the simplest option where unspecified and say so.
9. **Keep it runnable** after every change: tests green, server starts, dashboard and `/world3d` load.
10. **Commit only when asked; the owner pushes,** usually from VS Code. A push to `main` goes live on the G4
    within minutes, so only push finished work. GitHub account: DgenKing.
11. **This is the only project document.** After every piece of work, add a dated entry to §14 and update §2,
    §3, §5–§7, §9 and §10 as needed. Don't create other Markdown docs. If nothing needs changing, say so.

---

## 16. Measuring success

Evidence, not impressive-looking chat. After several sim days, check:

1. **Autonomy** — characters act for intelligible reasons without the player.
2. **Memory** — they recall important events accurately days later.
3. **Continuity** — they respect time, places, promises and world rules.
4. **Social change** — relationships move because of real events (working since 19 Nov).
5. **Knowledge** — they keep experience, hearsay and the unknown apart.
6. **Player impact** — what you do has a lasting consequence (Raj's ban, Jess barring Rob: ✅).
7. **Variety** — conversations don't loop (re-check now that promises are recorded).
8. **Cost** — stays within budget (so far: trivially).
9. **Reliability** — restarts, errors, API failures and bad pushes don't corrupt the world (auto-update rollback: ✅).

---

## 17. References

- Stanford Generative Agents — memory, reflection, planning in a small town: https://github.com/joonspk-research/generative_agents
- Mantella — NPC conversation, voice and memory linked to a game (check licence before reuse): https://github.com/art-from-the-machine/Mantella
- inZOI / NVIDIA ACE — AI-assisted NPC decisions; architectural inspiration only.
- DeepSeek Open Platform Terms of Service: https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html
- DeepSeek pricing: https://api-docs.deepseek.com/quick_start/pricing/
- Quaternius Universal Base Characters: https://quaternius.com/packs/universalbasecharacters.html
- Quaternius Universal Animation Library: https://quaternius.com/packs/universalanimationlibrary.html
