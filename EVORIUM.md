# EVORIUM — the project in one file

> One working document: the idea, what has been built, why it looks the way it does, what is broken,
> what comes next, and the plan for taking it online. It replaces five earlier files
> (`EVORIUM_CORE_IDEA.md`, `EVORIUM_BUILD_BRIEF_M1.md`, `EVORIUM_M1_FINDINGS.md`,
> `EVORIUM_BUILD_BRIEF_M3.md`, `EVORIUM_M3_FINDINGS.md`); their full text is in git history
> (`git show 6fec17c:EVORIUM_BUILD_BRIEF_M3.md`, etc.).
> `README.md` stays the how-to-run guide. Keep this file up to date at the end of each piece of work.
>
> **Last updated:** 19 November 2026

## Contents

1. [The idea](#1-the-idea)
2. [Where it stands today](#2-where-it-stands-today)
3. [How it works](#3-how-it-works)
4. [The world: cast, places, routines, story](#4-the-world-cast-places-routines-story)
5. [History: milestones and what each taught us](#5-history-milestones-and-what-each-taught-us)
6. [Known issues and open questions](#6-known-issues-and-open-questions)
7. [Next steps](#7-next-steps)
8. [Plan: Evorium online (multiplayer server)](#8-plan-evorium-online-multiplayer-server)
9. [Plan: levelling up](#9-plan-levelling-up)
10. [Art, 3D and Unreal](#10-art-3d-and-unreal)
11. [Running it](#11-running-it)
12. [Rules for anyone (or any AI) working on the code](#12-rules-for-anyone-or-any-ai-working-on-the-code)
13. [Measuring success](#13-measuring-success)
14. [References](#14-references)

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
(see §8).

### Principles that have held since day one

- **Prove the simulation before building the city.** A readable dashboard beat 3D graphics for the first experiments.
- **The model proposes; Python decides.** The language model returns JSON proposals. Python validates them
  against world rules before anything is written. The model never edits state directly, invents possessions,
  teleports characters or declares other people's private thoughts as facts.
- **Don't call the model constantly.** Movement, routines, sleep and work are plain Python. The model is called
  for conversations, note-taking, daily plans, promise checks, the director and the daily digest.
- **Knowledge boundaries.** Characters know only what they saw, were told, or were seeded with. Hearsay is
  labelled as hearsay; inventions are labelled as rumour.
- **Engine-independent core.** The simulation is a Python service with a JSON API, so a browser map, a 3D web
  view or Unreal Engine can all sit on top of the same brain.

---

## 2. Where it stands today

**One sentence:** eight AI characters live real-time daily routines around a pub and a newsagent in Ancoats,
Manchester; they talk, gossip, remember, make plans and react to a property company buying their terrace; you
can walk in and talk to them; a dashboard and a 2D map show it all live.

| Area | State |
|---|---|
| Characters | 8 NPCs + 1 player + 1 system ("World") row |
| Places | The Crooked Billet (pub, open 09:00–24:00 every day), Patel's News (shop, Mon–Sat 07:00–19:00) |
| Clock | Real UK time × speed multiplier (0 = paused, 1 = real, up to 600×+) |
| Conversations | 4 lines, or 6 for a pair's first meeting or fresh serious news; one at a time |
| Memory | Facts (seed / observed / told / claim) scored 1–5 for importance; only ≥3 saved or shown |
| Relationships | Directed trust, warmth, familiarity (0–100), shown as words to the model, bars on the map |
| Promises | Extracted from talk, with deadlines; kept/broken changes trust |
| Plans | Up to two a day per NPC: visit, phone, stay home |
| Director | Nudges a stalled or looping world with one mundane event a day at most |
| Timeline | Permanent record + daily digest, at `/timeline-page` |
| Player | Name, enter pub/shop, chat, promises, "what you've learned" |
| Dashboard | Character cards, live feed, usage/spend, controls, **Restart server** button |
| Map tab | 2D canvas: pub, shop, empty unit, street; pixel sprites walk, idle, show speech bubbles; click for portrait + stats |
| Model | DeepSeek `deepseek-flash`, JSON mode, temperature 0.8 (0.2 for structured calls) |
| Cost | ~$0.03 for the first 70 calls; roughly 0.3–0.5 US cents per conversation including notes |
| Tests | 133 Python tests + 7 Node map tests, none hitting the real API |

### Tech stack and dependencies

Python 3.11+, FastAPI + uvicorn, `sqlite3` (no ORM), `httpx` (no OpenAI SDK), pydantic, plain HTML/CSS/JS
(no framework, no build step), pytest. Node is only used to run the map test. No Docker, no Redis, no `.env`
files — the API key is hardcoded in the git-ignored `config.py` (dotenv loads the wrong file on this machine).

---

## 3. How it works

### The heartbeat (every 5 real seconds, `main._tick_loop`)

1. Read the sim clock (`world.now`).
2. Execute due plans; move everyone to their routine or plan location (`tick.update_routines`).
3. Deliver scheduled world events (letters, phone calls) as `observed` facts.
4. Close idle player chats.
5. In auto mode ("Let them live"):
   daily digest → due-promise checks → daily plans → director check →
   at most one conversation, at whichever public place has 2+ people and has waited longest.

### A conversation (`sim.run_conversation`)

1. Each turn, the speaker gets a system prompt: identity, mood, place and time, then sections for
   what they know for certain, what they've been told (with who told them), their own unverifiable claims,
   promises both ways, how they feel about the listener, broken promises, today's plans, people they know of,
   the last conversation with this person, recent conversations, and **topics already gone over today**.
2. The model returns `{"say", "rationale", "mood"}`, validated by pydantic.
3. After the last line, one **note-taking** call extracts per speaker: facts (with source and importance),
   promises (with deadlines), a **feeling** about the other person, and new named people; plus a summary and
   any promises now done.
4. Python stores it: facts scored below 3 are dropped (max 3 kept per person per conversation); feelings are
   capped at ±2 and applied ×2; promises get deadlines; both speakers get the summary as a memory; the timeline
   gets an entry.

### Knowledge model

| Source | Meaning | Shown to the character as |
|---|---|---|
| `seed` | Ground truth we wrote | What you know for certain |
| `observed` | They did or saw it | What you know for certain |
| `told` | Someone in the conversation told them | What others told you (may be wrong), attributed |
| `claim` | They asserted it with no basis | Your own guesswork; shown as RUMOUR on the dashboard |

**Importance (added 19 Nov 2026):**
5 harm, crime, threats, betrayal, someone hurt, big decisions/deals affecting others ·
4 praise or insult, strong feeling, decisions, secrets, odd behaviour, bans ·
3 needs, worries, rumours ·
2 small talk (not saved) · 1 throwaway (not saved).
Prompts rank by importance, then recency. Seed facts are 4, delivered story events 5.

### Relationships

Directed rows (Jess→Dez ≠ Dez→Jess). Changes only come from evidence: +1 familiarity per conversation,
kept promise trust +8 / warmth +2, broken promise trust −12 / warmth −4, note-taker feeling up to ±4 each.
The model only ever sees words ("you are wary of… and like them"), never numbers.

### Code map

| File | What it does |
|---|---|
| `evorium/main.py` | FastAPI app, tick loop, endpoints, auth middleware, log file, restart endpoint |
| `evorium/world.py` | Sim clock, pub hours, routines, `whereabouts` |
| `evorium/places.py` | Pub/shop registry, opening hours, who's present, conversation opportunities |
| `evorium/tick.py` | Routine updates, event delivery, due-promise checks |
| `evorium/sim.py` | Conversation runner, note-taking, `turns_for` |
| `evorium/memory.py` | What a character knows (`knowledge_for_prompt`), storing notes, promise resolution |
| `evorium/prompts.py` | Dialogue, note-taking and promise-check prompts |
| `evorium/models.py` | Pydantic schemas and lenient clean-up of model output |
| `evorium/relationships.py` | Trust/warmth/familiarity, bands, card data |
| `evorium/plans.py` | Daily planning, validation, execution |
| `evorium/director.py` | Stall/loop detection and validated nudges |
| `evorium/timeline.py` | Permanent record and daily digest |
| `evorium/player.py` | The human player |
| `evorium/llm.py` | DeepSeek client, budget cap, usage records |
| `evorium/db.py` | Schema migrations (9 so far), connection helper |
| `evorium/seed.py` | Cast, seed facts, scheduled events, starting relationships |
| `evorium/rescore.py` | One-off importance scoring of old facts |
| `evorium/static/index.html` | Dashboard + tab bar |
| `evorium/static/map.js` | Map tab |
| `evorium/static/timeline.html` | Timeline page |

### Main endpoints

`GET /agents`, `/usage` (includes `sim_time`, `speed`, `pub_open`, `places`, `present`, `boot_id`), `/events`,
`/conversations/latest`, `/conversations/{id}`, `/timeline`, `/player` ·
`POST /conversations/run`, `/speed`, `/auto/start`, `/auto/stop`, `/director`, `/player/profile`,
`/player/enter`, `/player/leave`, `/player/say`, `/player/end`, `/player/promises/{id}`, `/server/restart`.

---

## 4. The world: cast, places, routines, story

### The cast

| Character | Who | Routine (summary) |
|---|---|---|
| **Dez Whitworth**, 54 | Landlord, The Crooked Billet. Dry, loyal, worried about the lease. | Cash and carry 07–09; behind the bar whenever open (09–24); flat upstairs |
| **Jess Hartley**, 34 | Barmaid, single mum to Alfie. Sharp, tired, needs hours. | Office cleaning weekday mornings; bar Mon/Tue/Thu/Fri 17–23; drink Wed/Sat evening |
| **Tommy Shaw**, 67 | Retired bus driver. Mischievous; wants the Thursday quiz back. | Walk to shops 10–12; pub most evenings 19–22:30 (Thu from 18) |
| **Raj Patel**, 41 | Runs Patel's News (family shop since 1988). Careful, warm. | Shop Mon–Sat 07–19; quiet half Tue/Thu/Fri evening; Sunday pint |
| **Chloe Barlow**, 29 | Junior architect from Stockport. Looking for a flat. | Work weekdays 9–18; pub Tue/Wed/Fri evening, Saturday afternoon |
| **Simon Ferris**, 46 | Asset Manager, Northgate Estates. Polite, corporate, evasive. | Office weekdays; in Patel's News Thursdays 14:00–14:30 |
| **Brenda Ashworth**, 71 | Retired dinner lady, tenants' association chair. Loves a petition. | Paper at the shop 09:00–09:30; pub Wed evening and Sunday lunchtime |
| **Mo Iqbal**, 38 | Private hire driver, nights. Funny, observant, doesn't drink. | Shop 16:00–16:20; pub Tue early evening and Sunday afternoon; drives 19:30–04 |

House rule: names mostly British, a few others. (The M1 brief's "Priya Kaur" became Chloe Barlow.)

### The story seed

Northgate Estates bought the freehold of the whole terrace (pub, newsagent and the empty unit between) three
months ago. Simon's instructions: bring rents to market level, buy out leases where cheaper.

- Pub rent proposed: **£3,900 a month, up from £2,400** (Dez's second letter, Thu 19 Nov 09:00 — delivered).
- Raj offered **£45,000 to surrender his lease**, open a month (phone call Wed 18 Nov 11:00 — delivered).
  Simon has authority to go higher and won't volunteer it.
- No planning application yet; redevelopment discussed but not decided.
- Side threads: the Thursday quiz (quizmaster left 18 months ago), a darts team for Mo, Jess's shifts,
  Chloe's flat hunt, Brenda's petitions.

### What has actually happened (as of 19 Nov)

- Mon 16 Nov evening: six pub conversations among Dez, Jess and Tommy — lease worries and the quiz, round in
  circles. Tommy's rumour "people poking round the street" spread Tommy → Jess → Dez, correctly tagged as rumour.
- Tue 17 / Thu 19 Nov: the player ("Rob") in Patel's News announced he sells drugs, offered Raj crack and used a
  racist slur. Raj refused to serve him, banned him, remembered it across visits.
- Thu 19 Nov 14:00: Dez rang Simon about the £3,900 rent (Simon: "market-level assessment"); then Simon visited
  Raj about the surrender offer — cut off after two lines (since fixed: first meetings now get six).

---

## 5. History: milestones and what each taught us

### Milestone 1 — smallest working slice (15 Nov 2026)

Two characters (Dez and Chloe) in one pub exchange a conversation via DeepSeek, saved to SQLite, shown in the
browser, surviving a restart. Budget guard (`MAX_SPEND_USD`, default $4 of the $5 credit), JSON-only replies
validated by pydantic with one retry, every call's tokens and cost recorded. First real call: ~$0.0003.

### M1 free-run findings (10 minutes, 39 auto conversations, $0.055)

What worked: information genuinely spread (Jess → Raj → Tommy → Dez about a "surveyor"); characters stayed in
voice; cost was a non-issue.

What failed, and why:

1. **Forgotten commitments** — Dez agreed to the quiz, Tommy kept asking. Only the last 3 memories reached the
   prompt, memories were just the last line said/heard, and promises weren't stored as anything.
2. **Repeated conversations** — the same 3-memory window meant every pair met "fresh".
3. **Growing claims** — the surveyor grew a suit, clipboard, laser measure and an invented regular called Bernie.
   No world-fact store and no difference between observed, told and invented, so inventions became "fact".
4. **Promises without action** — 43 "I'll…" statements, nothing executed; later talk assumed they had happened.

These shaped everything after: structured note-taking, the four fact sources, a commitments table, seeded world
facts, a world clock with pacing, and a registry of named minor NPCs.

### Milestone 2 — five characters, structured memory, real-time world (15 Nov)

Five characters with seeded facts; note-taking call after each conversation (facts with sources, promises with
deadlines, new people); claims fed back as unverifiable and shown as RUMOUR; real UK clock with speed control;
weekly routines; tick thread; scheduled world events; due-promise checks; "Let them live" auto mode.

### Milestone 3 — player, relationships, actions, timeline, director, cast (16 Nov)

Built in eight phases from one brief, each committed separately: agent kinds and sim timestamps; the permanent
timeline and daily digests; the player; directed relationships; places, free time and daily plans; the director;
118 tests at the time. The live real-API smoke test was held back pending approval to send live-world prompts to
DeepSeek; the owner later ran the live server on the new code.

### Session of 19 November 2026

- **Map tab** (built by Codex from a written brief): canvas scene, procedural pixel sprites for all eight plus the
  player, walking between doors, cosmetic idling, speech bubbles, day/night and open/closed, click popup with
  portrait, activity, goal, plans, promises, knowledge counts and trust/warmth bars, "Full card →" link.
  `relationships.for_card()` gained raw `trust_value` / `warmth_value`. Movement is cosmetic and client-side;
  the backend stays the source of truth.
- **Pub hours**: 09:00–midnight every day. Dez's cash-and-carry run moved to 07–09.
- **Conversation review** found: relationships had never changed once (feelings missing from the note-taker's
  example JSON, and out-of-range values silently discarded); shop chats capped at 2 lines; trivia crowding out
  important facts; a Monday-night topic loop; Raj sitting on the £45k offer; no persistent logs.
- **Fixes** (commit `6fec17c`): fact importance scoring and filtering, capped-not-dropped feelings, `turns_for`,
  "topics already gone over today", director loop detection (every 2 sim-hours), planner nudged by serious news,
  rotating `evorium.log`, `evorium.rescore` for old facts.
- **Restart server button** in the dashboard header (`POST /server/restart` re-execs the same command; the page
  waits for a new `boot_id` then reloads).
- **Art**: a friend produced all eight portraits in one style, photoreal place renders and an
  `Ancoats_Blender_Unreal_Kit.zip` (see §10).
- **Online plan** discussed (see §8 and §9).

---

## 6. Known issues and open questions

- **Old trivia still visible** until `python -m evorium.rescore --apply` is run once (it previews first, backs
  up, hides rather than deletes).
- **Daytime pub is empty on weekdays**: it opens at 09:00 but nobody except Dez visits before late afternoon.
  Option: Tommy after his walk, Brenda at lunchtime.
- **Promises are rare**: the note-taker correctly ignores vague offers; worth watching after a few real days.
- **Director heuristics** are conservative word checks; valid but unfamiliar wording gets dropped.
- **Real-API behaviour** of the 19 Nov fixes (importance scores, feelings, loop detection) not yet observed
  live — check `evorium.log` and the timeline after a day or two.
- **The dashboard is a god view**: it shows every character's private knowledge. Fine for one owner, not for
  public players (§8).
- **Starlette test-client deprecation warning** (harmless).
- `Ancoats_Blender_Unreal_Kit.zip` (26 MB) is in the project root, untracked — keep it out of git.

---

## 7. Next steps

Short term (single owner):

1. Restart on the new code, run `evorium.rescore` (preview, then `--apply`), let it live for a day or two at
   real speed, then review conversations, relationships and the timeline again.
2. Install the eight new portraits (separate square PNGs; `simon.png`, `brenda.png`, `mo.png` plus replacements
   for the five) and register the new three in the `portraits` map in `index.html`.
3. Use the place renders as the map backdrop or a click-through "street view".
4. Decide on daytime pub visitors.

Then: the online version (§8) and levelling (§9), and later the 3D/Unreal client (§10).

---

## 8. Plan: Evorium online (multiplayer server)

> Status: **idea, not started.** Decisions recorded here are the owner's as of 19 Nov 2026.

### The vision

Put Evorium on a public server. People create an account, set a name and picture, and join **one shared
Ancoats** — the same eight characters, meeting each other. The characters remember every player, gossip about
them, and the world carries on when players are offline.

### How it's paid for (owner's decision)

- **Players bring their own DeepSeek API key** and top up their own DeepSeek account with at least a couple of
  dollars. Their own conversations run on their key.
- **"Keep Ancoats running while I'm away" is ON by default; players can opt out.** While it's on, a small share
  of the world's background calls (NPC-to-NPC conversations, daily plans, director, digest) is made with their
  key, rotating across contributing players. No money moves between players and the game; the cost simply lands
  on their own DeepSeek balance.
- **Scale:** the whole shared world costs roughly **$0.10–0.20 a day** at real speed. Split across 20
  contributors that's under 1 cent a day each — "a penny a day keeps Ancoats alive".
- **Player settings:** spending limit (per week or month); keep-running toggle; instant pause; remove my key.
  Profile shows e.g. "$0.43 this month: $0.31 your chats, $0.12 keeping Ancoats running".
- **When nobody contributes** or everyone is at their limit, the world goes quiet until someone plays (or the
  owner keeps a backstop key for quiet hours — pennies a month).

### ⚠️ DeepSeek's terms (checked 19 Nov 2026)

DeepSeek Open Platform Terms of Service, released 22 Apr 2026, effective 29 Apr 2026, **section 2.2**:

> "Please keep your created API key securely, prevent any form of leakage, do not share or publicly disclose
> your API key with others, and do not expose it in browser or other client-side code. You will be solely
> responsible for any fees incurred and losses caused by sharing or leaking the API key."

Section 4.1 also makes the key owner responsible for all inputs and outputs on their key. So a player pasting
their key into Evorium is, strictly, sharing it — permission between player and game doesn't change that, and
the risk (suspension, losses) sits with the player. The owner has chosen to go ahead. Mitigations agreed:

- One honest line where players add their key: *"DeepSeek's terms say keys shouldn't be shared — you're adding
  yours at your own discretion."*
- Keys **encrypted at rest** with a master key kept outside the database; never sent back to the browser after
  entry; usable only server-side; instant pause and delete.
- The game enforces each player's spending limit itself (DeepSeek has no per-key caps as far as we know; the
  player's balance is the only hard stop). Per-player usage comes from the existing `llm_calls` records plus a
  "paid by" column.

Legitimate alternatives if this ever becomes a problem: the owner holds one key and **sells credits via Stripe**
(DeepSeek's terms explicitly allow building public products on your own key, §1.1 and §3); or a provider built
for user-paid access such as **OpenRouter's sign-in flow** (not yet checked).

### Players online vs offline

- **Online:** your character is in the world; you walk into the pub or shop and talk.
- **Offline:** you're simply not there — at home, not on the map. NPCs keep living, and **remember and gossip
  about you** (score-5 facts like "Rob offered me crack" travel).
- **Coming back:** a "while you were away" summary: what happened, and who's been talking about you.

### What has to be built

| Area | Work |
|---|---|
| Profiles | Name, picture (start with preset avatars or approved uploads — public uploads need moderation) |
| Player view vs admin view | Players see the map, their own chats, what they've learned, their standing. Owner keeps the god view. Restart, speed, director and auto controls become admin-only |
| Multi-player conversations | Several players chatting to different NPCs at once; NPC busy rules already exist |
| Key pool | Encrypted storage, rotation, fair share, per-player caps, fallback when a key fails |
| Moderation | Players will be abusive (proven). Rate limits, report button, ability to ban accounts, filter uploads |
| Hosting | VPS, domain, HTTPS, backups, process manager; SQLite is fine for a small player count |
| Legal | Privacy policy and terms (UK GDPR: emails, keys, chat logs), age limit |

Suggested order: invite-only with friends first (owner's key or theirs), accounts + player view, then the key
pool and settings, then open sign-ups.

---

## 9. Plan: levelling up

> Status: **idea.** Build progression from things the sim already tracks rather than bolt-on XP, so what the
> game says about you and how characters treat you can never disagree.

1. **Neighbourhood standing** (the main level), from trust, warmth and familiarity across the cast:
   **Stranger → Newcomer → Regular → Local → Pillar of the Community.** Earned by being decent, keeping your
   word and turning up.
2. **Unlocks that open the world:** Regular — Dez knows your usual. Local — characters share secrets (Raj
   mentions the £45k, but only if he trusts you). Pillar — invited into the story: Brenda's petition against
   Northgate, running the Thursday quiz, the darts team.
3. **Per-character reputation:** the map's trust/warmth bars are the progress bars; milestones like
   "Tommy's drinking buddy".
4. **Promises as quests:** promise, deliver, trust jumps; break it and everyone hears.
5. **The dark path:** behave like Rob and build **notoriety** — bans, gossip, a different storyline. Being bad is
   a different game, not just losing.
6. **Patron of Ancoats** badge (a plaque in the pub) for players who keep "run while away" on.

---

## 10. Art, 3D and Unreal

- **Portraits:** five original photoreal portraits (`evorium/static/portraits/`, 256×256, prompts in that
  folder's README). A friend has now made **all eight** in one consistent style — use the full new set.
- **Place renders:** the Crooked Billet and Patel's News exterior, the pub interior, the shop interior, a brick
  texture. Candidates for the map backdrop and a "street view".
- **`Ancoats_Blender_Unreal_Kit.zip`** (26 MB): the friend's Blender/Unreal kit, "getting ready for import of
  actual characters and places in Unreal Engine". Not yet inspected. Keep it **out of git**; unpack into its own
  folder (e.g. `~/projects/evorium-assets/`) and don't run anything inside it.
- **Unreal architecture:** Evorium stays the **brain**, Unreal becomes the **body**. Unreal reads the same API
  the map uses (`/agents`, `/usage`, `/conversations/latest`) and moves 3D characters to spots; the map's rules
  (activity → spot, door waypoints, speech bubbles, catching up at high speed) carry straight over. Decide later
  between a downloadable client and browser streaming. Recommended only once the web version has players.
- **Voice** (speech in and out) remains a later goal, after the simulation is reliable.

---

## 11. Running it

```bash
# start (from the project folder)
.venv/bin/uvicorn evorium.main:app --host 127.0.0.1 --port 8000     # 0.0.0.0 to reach it from a phone on the LAN
# stop: Ctrl+C in that terminal, or from anywhere
pkill -f "uvicorn evorium.main:app"
# restart after code changes: the "Restart server" button, top right of the dashboard
# tests
.venv/bin/python -m pytest -q && node tests/map_view.test.cjs
# score old facts once (stop the server before --apply)
.venv/bin/python -m evorium.rescore           # preview
.venv/bin/python -m evorium.rescore --apply   # save, with automatic backup
```

- Dashboard `http://127.0.0.1:8000`, map `http://127.0.0.1:8000/#map`, timeline `/timeline-page`.
- Log: `evorium.log` in the project folder (rolls at 5 MB, keeps 3).
- Smoke tests on a copy: `EVORIUM_DB_PATH=/path/to/copy.sqlite3 uvicorn evorium.main:app --port 8001`.
- Home-LAN service: `deploy/README.md` and `deploy/evorium.service` (never forward the port on the router).
- Settings in `config.py` (git-ignored): `DEEPSEEK_API_KEY`, `MAX_SPEND_USD` (default 4.00),
  $1.20 output per million tokens (peak, uncached).

---

## 12. Rules for anyone (or any AI) working on the code

1. **Never lose the live world.** `evorium.sqlite3` is a real-time run. Back it up before risky work; never
   delete, recreate or reseed over it. Schema changes only by **appending** to `MIGRATIONS` in `db.py`; every
   migration must apply to the live database and an empty one.
2. **Secrets:** the API key lives only in `config.py`. Never print, log or commit it. No dotenv, no `.env`.
   New settings go in `config.example.py` and are read with `getattr(config, "NAME", default)`.
3. **The model proposes; Python decides.** JSON only, validated by pydantic, checked against world rules,
   dropped and logged if invalid.
4. **Tests never hit the real API.** Use fake clients. Leave the suite green after every change.
5. **Fixed stack:** Python, FastAPI, `sqlite3`, `httpx`, pydantic, plain HTML/CSS/JS. No new dependencies,
   frameworks, ORMs, build steps or Docker without asking.
6. **Budget:** keep `max_tokens` small and state it for any new call; smoke-test on a copy, on another port.
7. **UI:** escape every string with `esc()`; the EVORIUM title links to `/`; **never add a "Home" link**.
8. **Don't invent requirements.** Pick the simplest option where unspecified and say so.
9. **Keep it runnable** after every change: tests green, server starts, dashboard loads.
10. **Commit locally only when asked; the owner pushes.** GitHub account: DgenKing.

---

## 13. Measuring success

Evidence, not impressive-looking chat. After several sim days, check:

1. **Autonomy** — characters act for intelligible reasons without the player.
2. **Memory** — they recall important events accurately days later.
3. **Continuity** — they respect time, places, promises and world rules.
4. **Social change** — relationships move because of real events (now actually working).
5. **Knowledge** — they keep experience, hearsay and the unknown apart.
6. **Player impact** — what you do has a traceable, lasting consequence (Raj's ban: ✅).
7. **Variety** — conversations don't loop (Monday night: ❌, fixes in place, re-check).
8. **Cost** — stays within the budget (so far: trivially).
9. **Reliability** — restarts, errors and API failures don't corrupt the world.

---

## 14. References

- Stanford Generative Agents — memory, reflection, planning in a small town: https://github.com/joonspk-research/generative_agents
- Mantella — NPC conversation, voice and memory linked to a game (check licence before reuse): https://github.com/art-from-the-machine/Mantella
- inZOI / NVIDIA ACE — AI-assisted NPC decisions; architectural inspiration only.
- DeepSeek Open Platform Terms of Service: https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html
- DeepSeek pricing: https://api-docs.deepseek.com/quick_start/pricing/
