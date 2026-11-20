# EVORIUM — the project in one file

> One working document: the idea, what has been built, why it looks the way it does, what is broken,
> what comes next, and the plan for taking it online. It replaces five earlier files
> (`EVORIUM_CORE_IDEA.md`, `EVORIUM_BUILD_BRIEF_M1.md`, `EVORIUM_M1_FINDINGS.md`,
> `EVORIUM_BUILD_BRIEF_M3.md`, `EVORIUM_M3_FINDINGS.md`); their full text is in git history
> (`git show 6fec17c:EVORIUM_BUILD_BRIEF_M3.md`, etc.).
> `README.md` stays the how-to-run guide. Keep this file up to date at the end of each piece of work.
>
> **Last updated:** 20 November 2026

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
Manchester; they talk, gossip, remember, make plans and take validated decisions with financial and social consequences; you
can walk in and talk to them; a dashboard, a 2D map and a desktop/phone 3D browser view show it live.

| Area | State |
|---|---|
| Characters | 8 NPCs + 1 player + 1 system ("World") row |
| Places | The Crooked Billet (pub, open 09:00–24:00 every day), Patel's News (shop, Mon–Sat 07:00–19:00) |
| Clock | Real UK time × speed multiplier (0 = paused, 1 = real, up to 600×+) |
| Conversations | 4 lines, or 6 for a pair's first meeting or fresh serious news; one at a time |
| Memory | Facts (seed / observed / told / claim) scored 1–5 for importance; only ≥3 saved or shown |
| Relationships | Directed trust, warmth, familiarity (0–100), shown as words to the model, bars on the map |
| Promises | Extracted from talk, with deadlines; kept/broken changes trust |
| Plans | Up to two visits/calls per NPC; at most one action proposal on the morning call |
| Decisions | Fixed menu; one action plus one tell per NPC/day; major decisions need evidence and twelve hours to reconsider |
| Economy | Visible/private ledger, offers and deadlines, weekly pub settlement, notices and changing routines |
| Story arcs | Python resolves Northgate; darts and flat-hunt templates can follow |
| Catch-up | Player checkpoint, significant events and gossip, cached narration or bullet fallback |
| Director | Nudges a stalled or looping world with one mundane event a day at most |
| Timeline | Permanent record + daily digest, at `/timeline-page` |
| Player | Name, enter pub/shop, chat, promises, "what you've learned" |
| Dashboard | Character cards, live feed, usage/spend, controls, **Restart server** button |
| Map tab | 2D canvas: pub, shop, empty unit, street; pixel sprites walk, idle, show speech bubbles; click for portrait + stats |
| Model | DeepSeek `deepseek-flash`, JSON mode, temperature 0.8 (0.2 for structured calls) |
| Cost | ~$0.03 for the first 70 calls; roughly 0.3–0.5 US cents per conversation including notes |
| Web 3D | `/world3d`: Shuttle Street, animated CC0 stand-ins, third-person walking/jumping, touch controls, player chat |
| Tests | 226 Python tests + 7 Node map tests + Web3D Node checks and offline Chrome integration, all fake/offline |

### Tech stack and dependencies

Python 3.11+, FastAPI + uvicorn, `sqlite3` (no ORM), `httpx` (no OpenAI SDK), pydantic, plain HTML/CSS/JS
(no framework, no build step), pytest. Node runs frontend tests and the optional Web3D asset pipeline; the game needs no Node runtime. Three.js 0.187.0 is vendored locally (MIT); glTF Transform is a build-only dependency authorized by the Web3D brief. No Docker, no Redis, no `.env`
files — the API key is hardcoded in the git-ignored `config.py` (dotenv loads the wrong file on this machine).

---

## 3. How it works

### The heartbeat (every 5 real seconds, `main._tick_loop`)

1. Read the sim clock (`world.now`).
2. Execute due plans; move everyone to their routine or plan location (`tick.update_routines`).
3. Deliver scheduled world events (letters, phone calls), create offers, notice posted signs, expire deadlines,
   settle overdue Sundays and evaluate Python-owned story outcomes. These continue during model outages.
4. Close idle player chats.
5. In auto mode ("Let them live"):
   daily digest → due-promise checks → daily plans → budgeted reactions → optional ending narration → director check →
   at most one conversation, at whichever public place has 2+ people and has waited longest.

### Decisions, knowledge and consequences (M4)

`economy.py` owns integer stats, changes, offers and notices. `actions.py` is the fixed registry: typed arguments,
Python checks, atomic effects, durable considering/done/rejected proposals, witnesses and relationship changes.
Morning planning, verbatim conversation decisions and `decide.py` reactions use the same path. Big decisions need
an actor-owned importance-4 fact, a second proposal after twelve hours and room in the daily limits. A scheduled
follow-up gives them a chance to reconsider. Reactions are at most twelve calls per day, ordinarily one per NPC
(two near expiry), and postponed when over budget. Hidden negotiation limits stay with Python and Simon.

The weekly pub calculation is deterministic: £240 profit at the old rent, £106 loss at the proposed rent, before
levers or falling-outs. Overheads are tuned to £525. Rent changes on the lease date; bankruptcy or no renewal
closes the pub. Raj's surrender closes the shop thirty days later. `arcs.py` writes outcomes and canonical facts
before attempting a single narration call; failures retain readable fallback text. A refusal may be followed by
a fresh offer within fourteen days, preserving the refusal. The next small arc starts no earlier than two days
after resolution. The flat template uses a fixed affordable viewing invitation from Simon via a director event,
and the ordinary answer-ask path; it does not simulate a housing market.

`catchup.py` collects significant history, ledger changes and gossip since the player's checkpoint, caching a
250-token paragraph by checkpoint/latest timeline id. Calls are limited to once per sim day and real ten minutes.
Dismiss updates the checkpoint. The map adds no polls. Provider failures share one process-wide exponential pause
(1/2/4/8/15 real minutes), reset by a successful call; empty failed conversations are retained but hidden.

### A conversation (`sim.run_conversation`)

1. Each turn, the speaker gets a system prompt: identity, mood, place and time, then sections for
   what they know for certain, what they've been told (with who told them), their own unverifiable claims,
   promises both ways, how they feel about the listener, broken promises, today's plans, people they know of,
   the last conversation with this person, recent conversations, and **topics already gone over today**.
2. The model returns `{"say", "rationale", "mood"}`, validated by pydantic.
3. After the last line, one **note-taking** call extracts per speaker: facts (with source and importance),
   promises (with deadlines), a **feeling** about the other person, and new named people; plus a summary and
   any promises now done.
4. Notes may also identify one decision per speaker, with at least six verbatim words from that speaker.
   Python validates it against the action menu. Python stores facts: facts scored below 3 are dropped (max 3 kept per person per conversation); feelings are
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

The browser client at `/world3d` vendors Three.js 0.187.0, loads high/low glTF and
baked lighting, builds an octree from separate simple collision hulls, and animates a
third-person capsule/player plus NPC actors. `tools/web3d/` rebuilds assets without a
runtime build step. It polls `/world/scene` every 1.5 seconds (5 seconds after errors),
uses a collision-verified A* graph for cosmetic movement, and uses `/player/*`,
`/catchup` and `/catchup/seen` for actual player interactions. It renders no rationale
or private NPC facts. `?test=1` fixes poses/camera/time and exposes offline QA reports.

The Unreal client polls `GET /world/scene`, which reads a consistent SQLite snapshot through a read-only
connection. It exposes public presence/dialogue only and adds no model calls. Spot assignments live in Python;
Unreal handles cosmetic walking, bubbles, lighting and doors.

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

### Session of 20 November 2026 — Web3D browser implementation

- Re-ran `CODEX_PROMPT_WEB3D.md` §0.2: Blender 5.3.0, official npm registry,
  unlocked kit and both Standard archives pass. Snap Blender and networking need
  approved access outside this session's sandbox. Both supplied licences confirm CC0.
- Built `/world3d` and a dashboard **3D** link, using plain ES modules and locally
  vendored Three.js 0.187.0. The official release has no minified build; the requested
  module filename contains the unmodified module and its required core sibling.
- Added a reproducible, ignored-intermediate asset pipeline in `tools/web3d/`.
  Only the active Street scene exports; source scenes, kit cast and live state remain
  untouched. Fifteen marker coordinates match exactly; floor and doorway ray checks
  pass. The graph has 746 nodes and 4,697 verified three-ray waist-clear edges; every
  waypoint and upstairs is reachable from both street ends. Converted font signage
  to low-tessellation meshes after visual review caught missing lettering.
- The Standard pack contains Superhero bodies rather than Regular bodies. Used its
  male/female universal-rig stand-ins with clothing colour masks and per-cast scale;
  repaired one missing texture filename alias using the included PNG. Bone names
  match the library. Ten clips ship, without the library's unused mannequin mesh.
- Cycles CPU baked indirect lighting at 128 samples, secondary UVs, 2048/1024 atlases;
  the atlas is shared, with limited detail on small props. No separate night atlas;
  night dims the bake and uses emissive glass/runtime lights. Named pub/shop interior,
  window and sign groups survive optimization. Low geometry is simplified; textures
  use WebP and assets use Meshopt. Generated asset budgets: low **3.40 MB / 124,232
  triangles**, high **5.15 MB / 173,338 triangles**, counting one male and female body.
  Low texture allocation estimate is **45.44 MB**, including mipmaps and lightmap;
  this excludes renderer/JS/octree memory. Vendor modules add about 2.4 MB before HTTP
  compression. In-view geometry/shadow statistics come from browser reports.
- Implemented capsule/octree walking, running, step-up, jump and wall blocking,
  follow-camera wall collision, closed doors, desktop/touch controls, remembered
  settings, quality presets and FPS downgrade. NPCs use the verified graph, slot
  offsets, sitting/talking clips, public name cards, bubbles and server polling.
  Chat/catch-up use existing APIs and render spoken text with DOM text nodes.
- The smoke server now defaults to a `/tmp` database copy (override with
  `EVORIUM_SMOKE_DB`) and exposes a fake-only clock fixture. Browser automation refuses
  player writes without its fake status. Targeted physical tests reach both interiors
  and return, with pub/leave/shop/leave calls, ≤0.13 m final error and no penetration;
  jump 1.03 m, wall stop x −8.60 m, camera stop 0.77 m, shut-door stop z 0.60 m.
  Fake chat and a 60× routine refresh pass. Python: **226 passed**, map: **7 passed**;
  Web3D graph/animation/quality/slot/cast checks pass. All 20 desktop/phone low/high
  captures pass error, visible-triangle, blank-image, NPC-ID and avatar alignment
  checks. Visible geometry ranges from 76,750–139,238 triangles on low and
  145,715–216,268 on high; total draw calls range 43–90 low and 134–181 high,
  including shadows. SwiftShader measures about 4–11 fps low and 2 fps high, not
  hardware performance. Reviewed exteriors/signs, pub seating/bar, shop stock/till,
  cast gestures/bubbles and Rob at the door. Corrected the blocked shop test camera
  and test avatar/capsule alignment. See `tools/web3d/VERIFICATION.md`.
- No commits, real model calls, live-server restart, live-database writes, config,
  website, Unreal-project or source-kit changes. The older blocked preflight below
  records the earlier attempt, not the current state.

### Session of 20 November 2026 — Web3D prerequisite check

- Read `CODEX_PROMPT_WEB3D.md` in full and checked §0.2 before implementation.
  Stage 1 has not started: `blender --version` returns command not found, and
  `~/Downloads/evorium-characters/` does not exist, so the required Quaternius packs
  could not be inspected or their CC0 licences confirmed.
- The read-only kit path exists at `/run/media/user/Data Storage/Evorium/AncoatsKit/Ancoats_Blender_Kit/`.
  npm 11.4.2 is available, but connectivity checks against both the configured
  `registry.npmmirror.com` and official `registry.npmjs.org` failed with `EAI_AGAIN`
  DNS errors in this session. Network access remains unverified outside the sandbox.
- Stopped as required by §0.2. Next: install Blender 4.3+, supply both Standard
  character-pack zips, and make npm registry access available, then repeat preflight.
  No client code, assets, screenshots or budget measurements were produced. The live
  database, config, website and Unreal project were untouched; no commits were made.

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
- **Conversation count** (evening check):
  - The old world (15–16 Nov, before the database was restarted) had 16 conversations; they're kept in
    `evorium-backup-20261116.sqlite3`.
  - The current world has 48 conversation rows and none are missing: 25 real (10 with the player, 15 between
    NPCs) and 23 empty failures.
  - All 23 failures came within 5 minutes (19 Nov, 16:00–16:05). DeepSeek was failing and auto mode retried
    every tick.
- **Best conversations so far:**
  - #10, Dez rings Simon about the £3,900 rent;
  - #11–12, Simon and Raj, where Raj learns Northgate owns the whole terrace;
  - #41, Jess holds Dez to account and asks for quiz-night hours.
  - They are good dialogue that never turns into action, which is what M4 addresses.
- **Cost estimates fixed:**
  - `llm.py` now reads `prompt_cache_hit_tokens` from each reply and prices cached input at $0.006/M instead
    of $0.30/M (`CACHED_INPUT_USD_PER_MILLION`).
  - It halves the cost outside DeepSeek's peak hours (01–04 and 06–10 UTC, Mon–Fri).
  - Before this, estimates were about 3× the real bill. The DeepSeek dashboard showed $0.07 for 441 requests,
    about $0.00016 a call, while a typical reply is now estimated at about $0.00014.
  - Two tiny live calls confirmed the field (384 of 596 tokens cached on the repeat).
  - 136 tests pass.
- **Git:** a VS Code commit hung for hours waiting for the `COMMIT_EDITMSG` tab to close, and had the 26 MB
  Unreal zip staged.
  - The stuck commit was stopped and the zip unstaged; `.gitignore` now has `*.zip`.
  - The earlier commit, which had only caught the doc deletions, was amended to include the restart button and
    EVORIUM.md (`02e1875`).
- **M4 brief written:** [CODEX_PROMPT_M4.md](CODEX_PROMPT_M4.md), "decisions and consequences", for Codex to
  build. It covers:
  - failure backoff;
  - a money ledger with a weekly pub settlement;
  - an action menu of about 25 actions, checked by Python, with Simon's hidden limits;
  - routines, notices and noticing;
  - three moments to decide (morning plan, in conversation, reacting to news), with sleep-on-it and evidence
    rules for big decisions;
  - Northgate endings and follow-on story arcs;
  - a "While you were away" catch-up.
- **Docs rule added:** `AGENTS.md` and `CLAUDE.md` tell every AI to keep this file and the README current (§12
  rule 11).

### M4 build — 19 November 2026

- **First playable 3D build (late 19 Nov):** after the SM5 fix, the Unreal project opens and the owner can run around
  Shuttle Street in third person. The owner's verdict: early and rough, but the graphics are "not that bad". The
  playable area is very small, because the kit is one street frontage with a mill backdrop.
- **Conversation review, evening of 19 Nov (#49–#62):**
  - *Better:*
    - Relationships now move on every conversation, for real reasons.
    - Raj finally told Dez (#53, #58) and Jess (#56) about the £45k offer. Dez and Raj worked out Northgate
      may be clearing the terrace, and Dez advised getting the offer in writing before the 18th.
    - M4's situation lines show up in talk: Dez quoted £3,900 rent against £3,520 takings and £6,000 in
      reserve.
    - Only serious facts score 5. No empty failed conversations since the backoff.
    - About $0.046 for 103 calls.
  - *Player test:* the owner (as Rob) insulted Jess and claimed to have a gun. Jess barred him and told Dez to
    ring the police; Dez promised to. But it only cost Rob −4 trust and warmth (the ±2 cap), so Jess is still
    "neutral" towards him, and the bar isn't enforced: Rob walked back in and talked to Dez.
  - *Bug found and fixed: promises were never recorded.* There were 0 in all 62 conversations, including
    "forty by Sunday, that's a promise" and "I'll ring them, I promise". The cause was the note-taker's example
    JSON showing `"commitments": []`, the same trap as the feelings bug.
    - The example now shows a filled-in promise, and the prompt says when to record one.
    - `memory.EXAMPLE_COMMITMENT` drops the example if the model copies it.
    - A live re-test recorded Tommy's quiz questions and Dez's police call, with no false promise on a
      conversation without one.
    - Test added; 224 pass. Takes effect after a server restart.
  - *Still weak:*
    - The quiz loops: "forty by Sunday" was restated in 4 conversations, and Dez "floated reviving the quiz" in
      #62 as if new, because no promise or action ever recorded it.
    - No decisions from conversations or plans yet, only the two `wait` reactions. Today's plans were made
      before M4 went live, so tomorrow is the first real test.
- Implemented the decisions-and-consequences brief: outage backoff, ledger/weekly finances, offers, 28 menu
  actions including job choices, shared validation and decision guards, dynamic routines/notices, reactions,
  Northgate outcomes, follow-on templates, catch-up, dashboard/API/map/timeline fields.
- Appended migrations 10 (ledger), 11 (actions/asks/reactions), 12 (arcs), 13 (player checkpoint/cache).
  Migration tests preserve a version-9 world's conversations, facts, delivered letters and all history.
- Added 78 offline rule, integration and multi-day scripted story tests; 214 Python and 7 Node tests pass. Existing schema-table assertion updated
  for the deliberately added tables. Test fixtures reset provider pause state between independent tests.
- The sandbox blocks FastAPI test-client event-loop sockets; checks run with the existing `.venv` outside that
  sandbox. No dependencies installed, no real API calls, no live database writes, no commits.
- Deliberate choices: fourteen-day reopening after refusal supports the specified smoke story; overheads £525
  hit the requested profit/loss targets; fixed affordable flat invitation uses Simon rather than inventing a
  landlord. Cash and other state always come from Python, never narration.

### M4 review (Claude) — 19 November 2026

- **The live world is already on M4.** The server was restarted on the new code at 20:37 sim time, and the
  database migrated to version 13 with nothing lost: 57 conversations, 252 messages, 157 facts, 102 timeline
  entries and 80 relationships, the same before and after on a copy.
- **Offers were created from the letters already delivered:** Dez's £3,900 renewal is due 17 Dec 09:00 (28
  days) and Raj's £45,000 surrender runs out 18 Dec 11:00 (30 days).
- **First real decisions:** Raj and Dez both chose `wait`, with in-character reasons. Raj: tempted by £45k
  against his £18k savings, but suspicious that Northgate is buying the whole block. Dez: the rent is firm, so
  he'll see what the takings look like before countering.
- **Weekly settlement checked:** +£240 a week at £2,400 rent, −£106 at £3,900, and +£133 at £3,900 with the quiz
  running and a 20p rise.
- **Fixed in review:**
  - The note-taker's prompt listed every action's argument limits, which included Simon's hidden £60,000 and
    £3,300. It now lists only the two speakers' own actions, by argument name. This also cut about 6,000
    characters from every note-taking call.
  - "What people say about you" matched the player's name inside words, so "Rob" matched "problem". It now
    matches whole words only.
  - An invalid model reply paused all DeepSeek calls as if the service were down. Now only real outages
    (network, HTTP, missing usage data) trigger the pause.
  - Rejected actions showed a multi-line pydantic dump in the live feed. They now show one readable line.
  - The morning plan's `max_tokens` went from 300 to 400, since it can now carry a decision as well.
  - Tests were writing into the real `evorium.log` (a bug from the 19 Nov persistent-log change). The log path
    can now be set with `EVORIUM_LOG_FILE`; an empty value turns the file log off, and `tests/conftest.py`
    does that.
  - 4 new tests: 218 Python and 7 Node tests pass. A smoke run of the server on a copy (port 8011) loaded every
    page and endpoint with no errors.
- **Behaviour change to know about:** Jess's bar nights moved from Mon, Tue, Thu, Fri to Thu, Fri, Sat, Sun (the
  brief's order for a shift count). Mo drives on Thursday evenings, so he never makes the quiz.

### Unreal preflight — 19 November 2026

- Read `AGENTS.md`, this document and the full five-stage `CODEX_PROMPT_UNREAL.md` brief.
- Confirmed the data-drive folder, UnrealEditor-Cmd, Build.sh, Third Person template and kit archive exist.
- Stage 1 is blocked before extraction/project creation: a temporary write probe under
  `/run/media/user/Data Storage/Evorium` failed with `OSError: [Errno 30] Read-only file system`.
  This Codex session permits writes only to the Python repository and `/tmp`. Restart with the data-drive
  folder writable using the command in the Unreal brief §6. Unreal was not launched, so GPU/editor sandbox
  compatibility has not been tested. Stages 1–5 remain unbuilt; no editor checks are available yet.
- No kit extraction, engine/project changes, server requests, database/config changes or commits were made.

### Unreal Stage 1 build — 19 November 2026

- The data-drive write probe now passes. Extracted the kit to `AncoatsKit` and created
  `EvoriumUnreal` alongside engine 5.8.4 at the paths in the brief. No live database/config changes.
- Third Person C++ template, mannequin and Enhanced Input resources copied with class redirects;
  editor target builds. Headless Python passes using `InstalledNoZenLocalFallback`. Build Accelerator
  requires `~/.epic` outside the workspace sandbox; build-command permission was granted.
- Reviewed/adapted the kit importer for 5.8 material slot access, combined sets and disabled Nanite.
  Import: zero errors, seven tangent warnings (owner must inspect shading).
- Generated ShuttleStreet with shared-origin sets, lighting, start, 15 labelled waypoint actors and nav bounds.
  Triangle collision restores missing floor queries; explicit physics preparation makes headless queries work.
  All 15 floor traces are within 5 cm; both entrance rays are clear; all five required nav paths pass.
  Level checks: `EvoriumUnreal/Saved/Logs/level_checks.json`. Owner visual checks remain outstanding.

### Ban enforcement investigation — 19 November 2026

- After Rob threatened Jess in-game, a later screenshot showed Dez greeting him warmly despite an earlier
  verbal ejection. Code review found no persistent ban/ejection state or admission checks: `player.enter`
  checks opening hours, and `player.say` checks presence/busy state. A spoken ban cannot block re-entry.
- Dialogue uses bounded memories and relationship descriptions; those influence model replies but do not
  guarantee that a threat or a verbal ban governs the next greeting. The exact cause of this reply was not
  verified: the live database and provider were not accessed.
- No behaviour changes made. Next work: explicit Python-owned ejection/ban/reinstatement actions and
  persistent admission enforcement, plus prioritising relevant serious incidents in player dialogue.

### Unreal Stage 2 cast — 19 November 2026

- Added `Cast.json`, eight tint instances, native NPC/AI classes, nearby first-name labels, speech widgets,
  `Evorium.MoveTo`, and the N-key toggle. CastPreview loads all eight meshes/animation classes;
  headless game test reports `count=8 moves=8`.
- Built Manny/kit IK rigs and a retargeter. Automatic chain mapping worked, but the kit importer did not
  persist Skeleton assets, so batch-exported animations could not bind. The explicitly permitted fallback
  is active: all eight use tinted Manny with the template's shared locomotion animation blueprint.
  Requested kit mapping remains in `Cast.json`. Kit bodies, sitting/leaning and retargeted locomotion are
  unfinished. Owner must check feet, facing, tints from five metres, names and movement visually.

### Unreal Stage 3 connection — 19 November 2026

- Added read-only `/world/scene` in `scene.py`: public scene fields, deterministic spots/slots,
  clock/daylight, notices, visible/away presence and recent public dialogue. SQLite URI mode=ro prevents
  accidental writes; no model calls. Five tests cover slots, visibility, privacy, expiry and zero conversations.
- Added Unreal connection settings, polling/spawn/movement subsystem, speech, lighting/doors/notices,
  F1 debug HUD and 30-real-second runtime comparison. Offline smoke on a database copy at port 8011 with
  fake replies passed: 20 polls, three expected/matching positioned actors, closing shop at 60x, speech logged.
  223 Python and seven Node tests pass. No live database/config edits, real model calls or commits.
- Owner reported GTX 1060 Vulkan feature-level failure. Preserved their Vulkan SM5 entry beside SM6;
  launch helpers explicitly use `-sm5`. Nanite/VSM/Lumen/ray tracing disabled. Corrected renderer settings
  placement and made the sun movable. No feature requires SM6. Visual/GPU performance checks remain.
- Build with `-NoHotReloadFromIDE` to avoid stale hot-reload libraries during automated checks.

### Unreal Stage 4 player — 19 November 2026

- Added Rob's neutral Manny from `Cast.json`, physical door triggers, entry/leave calls, nearby E-to-talk,
  code-built chat/profile/catch-up panels, keyboard/mouse focus, API error text, NPC facing and speech.
- Actual walk test passed on the fake-model 8011 server in 19.4 seconds: entered pub, confirmed `/player`,
  reached a neighbour, sent chat through the panel, received fake reply, closed chat, walked out and confirmed leave.
- Runtime walking exposed a flaw the nav-path checks alone missed: decorative triangle collision snagged a
  character on low furniture. Restored the kit's authored UCX hulls from read-only FBX data (24 pub, 17 shop,
  3 street), with floor alignment in Unreal. Render meshes unchanged. All floor/door/nav checks pass again.
  Character capsules are 30 cm radius/90 cm half-height; nav agent is 35 cm radius/180 cm height. NPCs do not
  physically block one another. Floor-level nav projection avoids picking furniture tops.
- The standalone smoke server exposes its fake-client identity at `/smoke/status`; the Unreal player test
  refuses other URLs or a server without that identity. The normal app has no fake-model hook.

### Unreal Stage 5 pause / resume notes — 19 November 2026

- Owner requested stopping during Stage 5. Stages 1–4 passed; Stage 5 is partial, not complete.
- Final editor and Linux Development game builds passed. Final scene test: 30 real seconds/20 polls,
  three matching positioned actors, 60x closing-time transition and fake speech. Final player test: 21.03
  seconds, actual entry/chat/fake reply/close/exit with server confirmations. Latest full suite: 225 Python
  and seven Node tests pass (the repository also contains unrelated concurrent work).
- Added Close/Esc control restoration, longer player-request timeouts, SM5 launch/build helpers and
  headless performance recording. NullRHI means 0.576 ms street / 0.381 ms pub frame intervals, with
  startup spikes; these do not measure GTX 1060 GPU performance. The zero game-thread counter is unavailable.
- Optional packaging was started and interrupted. Nested quoting in its optional local-cache argument
  needs correction before retrying. No finished package has been verified. Check for remaining descendants
  of the interrupted cook before resuming; do not stop the owner's other editor/server.
- Detailed remaining work, commands, evidence and safeguards are in
  `/run/media/user/Data Storage/Evorium/EvoriumUnreal/REMAINING_WORK.md`. Finish packaging if desired,
  consolidate owner docs, create the final file inventory and perform visual/GPU checks. Kit retargeting
  and sitting remain unfinished under the permitted Manny fallback. No commits or live DB/config edits.

---

## 6. Known issues and open questions
- **Web3D device review:** automated desktop/phone-size checks use software SwiftShader;
  FPS is not representative of phone/GTX hardware. Real iOS memory, multitouch and
  keyboard feel need physical-device checks. CC0 bodies use clothing masks, without
  bespoke hair/portraits/facial animation. A shared indirect atlas simplifies small
  props; no separate night bake or bloom. Automatic quality drops change renderer
  settings but retain loaded assets; choosing a preset reloads its asset set.
  Cosmetic NPC catch-up currently snaps rather than fading, and departures disappear
  at the route end. Speech bubbles near viewport edges can crop. The shared single
  player remains an owner prototype.

- **Spoken bans are not enforced:** there is no persisted ban/ejection state or admission check. A character
  can describe throwing Rob out, yet the UI still admits him and a later greeting may be friendly. Explicit
  ban/reinstatement actions and relevant-incident prompt priority remain to build.

- **Unreal client in progress:** Stages 1–4 automated checks pass (Manny cast fallback). Owner stopped work during Stage 5;
  packaging/final handover and visual checks remain. See the Unreal project’s `REMAINING_WORK.md`.
  Kit import reports seven tangent warnings; inspect street, shop and handpump shading.

- **Old trivia still visible** until `python -m evorium.rescore --apply` is run once (it previews first, backs
  up, hides rather than deletes).
- **Daytime pub is empty on weekdays**: it opens at 09:00 but nobody except Dez visits before late afternoon.
  Option: Tommy after his walk, Brenda at lunchtime.
- **Promises are rare**: the note-taker correctly ignores vague offers; worth watching after a few real days.
- **Director heuristics** are conservative word checks; valid but unfamiliar wording gets dropped. Since M4 it
  also rejects any digit and words such as set, pay, close and sign, so expect more of its ideas to be dropped.
- **A failed reaction call is used up.** If DeepSeek fails during a character's reaction, that reaction isn't
  retried. The "offer nearly due" reminder three days before expiry gives them another chance.
- **Real-API behaviour** of the 19 Nov fixes (importance scores, feelings, loop detection) not yet observed
  live — check `evorium.log` and the timeline after a day or two.
- **M4 simplifications:** fixed two-hour reaction delay (sixteen hours for reconsideration); flat viewing and
  outside-job offers use small Python templates. Pub income is an illustrative weekly model, not accounting.
- **Serious incidents barely move relationships:** feelings are capped at ±2 (×2), so threats of violence cost
  only −4. Consider a wider negative range for threats and violence (e.g. down to −5, ×2 = −10).
- **Being barred isn't enforced:** a character can say the player is barred, but nothing stops them walking
  back in. It needs an action (e.g. `bar_customer` for Dez and Jess) that the player endpoints respect.
  **On hold (owner, 19 Nov)** while the owner is testing by provoking characters. When built, include a
  testing override (a dashboard toggle or an unbar button) so the owner can't lock themselves out.
- **3D faces are stand-ins:** the kit's faces are baked into each body's texture, so the 2D portraits can't
  simply be put onto them. The portraits appear in the click popup and on name tags instead (§10). A true Dez
  model would have to be built from `dez.png` by the friend.
- **The dashboard is a god view**: it shows every character's private knowledge. Fine for one owner, not for
  public players (§8).
- **Starlette test-client deprecation warning** (harmless).
- **Spend recorded before 19 Nov is overstated** (old peak, uncached pricing), so the local total and the $4 cap
  count about $0.09 too much. Calls from 19 Nov onwards are priced properly.
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
5. **Web3D browser client built:** `/world3d`, with the build/check commands in
   `tools/web3d/README.md` and controls in `evorium/static/world3d/README.md`.
   Next: review on the owner's desktop and a real phone (especially iOS memory,
   keyboard, touch and visual feel); improve stand-in clothing/hair and seated poses;
   add fades/separation polish and reload low assets on automatic downgrade if needed.
   Keep the Unreal project frozen; its packaging work is superseded by the browser
   client. Python remains the source of truth; the brief is `CODEX_PROMPT_WEB3D.md`.
6. **Website:** give [CODEX_PROMPT_WEBSITE.md](CODEX_PROMPT_WEBSITE.md) to Codex: a one-page, image-heavy, plain
   HTML/CSS site in `website/`. Its theme is "Ancoats after dark": ink, brick, Billet green and amber, with
   Fraunces or Playfair and Inter. The pitch is "The street doesn't stop when you leave": a living 3D world,
   AI neighbours with personalities, real time, and your reputation is the game. Codex generates all the
   images, and the waitlist uses a placeholder email.
7. **M4 is built, reviewed and live** (migrations applied, first decisions made). Restart once more to load the
   review fixes, then watch decisions over a few sim days and play Northgate to an ending: both offers come to a
   head on 17–18 Dec. Review the pacing and the settlement constants against the story.
8. Then a small online test with 5–10 friends using their own keys, before planning for large numbers.

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

### Behaviour is the game (owner, 19 Nov)

Players will swear, insult and threaten. The NPCs are decent people who won't stand for it, and that's the
point: bad behaviour costs you in the world itself.
- Trust drops and the gossip spreads.
- You get barred, and doors close.
- Nobody will lend you money or tip you off.

Good behaviour earns the opposite. This is the core of "surviving in Manchester", and it ties straight into
the levelling plan (§9: neighbourhood standing).

For an online version:
- **Each player's standing is their own.** NPCs remember each player separately, so one troll can't spoil the
  world for everyone. Their behaviour still becomes gossip *about them*.
- **Barring and other consequences** apply to that player only.
- **Hide NPC reasoning from players.** The player chat currently shows each reply's private rationale (e.g.
  Dez: "Hold him to my promise about the police while pressing him on the earlier threat"). That's fine in the
  owner's god view, but a public player must see only what the character says.
- **Moderation is still needed:** abuse aimed at *real* players, and content the model provider refuses.
  Every message goes to DeepSeek on the player's key, so extreme input can fail or break the provider's
  rules. Plan a light filter and per-player rate limits.

### Hosting notes (20 Nov)

- **Server:** an OVH VPS-2 (4 vCores, 8 GB) is plenty for the first test (owner plus 5–10 friends). Rendering
  runs on players' devices (Three.js) and the AI on DeepSeek, so the server is light.
- **The real limits are in the code, not the hardware. Fix them before scaling:**
  1. **One conversation at a time worldwide** (`_run_lock` in `main.py`). Conversations need to run in
     parallel, one per place.
  2. **SQLite without WAL mode.** Turn on `PRAGMA journal_mode=WAL` (and a busy timeout) before many
     concurrent writers.
  3. **One player row.** Real multiplayer needs accounts and per-player relationships and memory; this is the
     biggest job.
  4. **A single uvicorn process,** with the tick thread and in-memory state, so it can't simply run multiple
     workers. That's fine at first.
  5. **`/world/scene` polled every 1.5 s per player.** Build the snapshot once per tick and serve the cached
     copy.
- **Bandwidth:** 12–30 MB of 3D assets per new player. Put a CDN (e.g. Cloudflare free) in front for static
  files.
- **Cost driver:** DeepSeek, not the VPS (about $0.40 a day for 8 characters now). That's another reason for
  player-supplied keys.
- **Cast size:** grow slowly (12–20 well-written neighbours) rather than aiming for 100 generic NPCs. Depth
  is what makes Evorium work.

- **Decision (20 Nov): host on the owner's always-on HP ProDesk 405 G4 Mini** (Ryzen 5 PRO 2400GE, 16 GB,
  128 GB, Ubuntu 26.04, LAN <server-address>) under its own `evorium` account. It's shared on the internet through
  too hard.
  - Guide: [deploy/HOME_SERVER.md](deploy/HOME_SERVER.md). The installer `deploy/install_home_server.sh`
    sets up the venv, checks config, installs a systemd service on 127.0.0.1:8000 and a 03:15 nightly backup
    cron.
  - Backups: `deploy/backup_world.py` uses SQLite's backup API, keeps 14, and was tested on a copy.
  - Once the world is moved, the G4 holds the real world; the main PC only uses copies.
  - **Deploys come only from GitHub:** develop on the main PC and push to `main`. The G4's
    `evorium-update.timer` runs `deploy/auto_update.sh` every 2 minutes. It backs up, fast-forwards, runs pytest,
    and restarts if the tests pass, otherwise it rolls back (a failed commit is tried once). It logs to
    `updates.log`, and restarts are allowed through a sudoers rule for `systemctl restart evorium` only.
    Tested on throwaway clones: good push, broken push rolled back, and a fix applied.
  - **Only push finished work to `main`,** because it goes live within minutes.
  - **Live on the G4 (20 Nov, 12:17):** account `<server-user>`, project `<project-dir>`, the world moved
    from the main PC (464 KB), the `evorium` service running, auto-update and the nightly backup timer enabled
    (the first backup was taken). On Ubuntu 26.04 the backup uses a systemd timer, because cron isn't installed
    by default. The main PC's server is stopped.
  - **Public address:** https://<tunnel-domain> (ngrok free plan, EU region), run by
    `evorium-ngrok.service` (a systemd unit; snap ngrok can't run `ngrok service install`). Protected by
  - **First auto-update (20 Nov, 12:29) was rolled back as designed:** `tests/test_world3d_route.py` failed

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

**Current delivery is Web3D**, built from `CODEX_PROMPT_WEB3D.md` on 20 November.
The friend's set is exported read-only through Blender, with font lettering, 44
collision hulls, 15 converted metre/Y-up waypoints and a verified walking grid.
Quaternius Standard CC0 male/female Superhero bodies replace the Unreal-only
mannequin; ten universal-rig clips supply idle/walk/run/jump/land/sit/talk.
Tinted clothing masks, scales and portrait cards identify Evorium's cast.
Cycles indirect lightmaps, WebP and Meshopt keep low assets at 3.40 MB and high at
5.15 MB. Full licences are in `static/world3d/assets/LICENSES.md`; rebuilding and
verification are in `tools/web3d/README.md`. Source kit and Unreal stay unchanged.
The Unreal-era casting choices below remain historical context.

Unreal build (19 Nov): Stage 1 is built at `/run/media/user/Data Storage/Evorium/EvoriumUnreal`.
Editor compilation, headless import, 15 floor traces, entrance rays and five nav paths pass.
Stage 2 uses the permitted tinted-Manny fallback because imported kit Skeletons did not persist.
See its `README.md` and `OWNER_CHECKLIST.md`; visual checks and Stage 5 handover are pending. Work was stopped at the owner’s request;
`REMAINING_WORK.md` in the Unreal project records the exact resume state.

- **Portraits:** five original photoreal portraits (`evorium/static/portraits/`, 256×256, prompts in that
  folder's README). A friend has now made **all eight** in one consistent style — use the full new set.
- **Place renders:** the Crooked Billet and Patel's News exterior, the pub interior, the shop interior, a brick
  texture. Candidates for the map backdrop and a "street view".
- **`Ancoats_Blender_Unreal_Kit.zip`**: the friend's Blender/Unreal kit, second version (19 Nov), 148 MB and
  102 files. It replaced the 26 MB first version. Keep it **out of git**: `*.zip` is ignored, and it's over
  GitHub's 100 MB file limit anyway. Unpack it into its own folder (e.g. `~/projects/evorium-assets/`).
  - **Set:** "Shuttle Street", with The Crooked Billet (dark green, oak bar, hand pumps, oxblood booths) and
    Patel's News (blue and cream, aisle, parcel counter, chillers), in front of a mill backdrop. Three FBX set
    pieces share one origin, plus 9 prop FBXs, PBR textures and a material manifest.
  - **Import:** `unreal/Import_Ancoats.py` is an assisted import for Unreal Engine 5 (Python Editor Script
    Plugin, legacy FBX importer). It has not been tested in Unreal by the kit's author.
  - **Waypoints:** 12 interaction spots in `waypoints.json` (PUB_ENTRY, PUB_HOST, PUB_BAR, PUB_BOOTH,
    PUB_WINDOW, PUB_DART, NEWS_TILL, NEWS_QUEUE, NEWS_RACK, NEWS_CHILLER, NEWS_PARCELS, plus street spots).
    Positions are in metres in Blender axes; convert to centimetres for Unreal.
  - **Characters:** 8 rigged skeletal FBXs (a shared 20-bone FK skeleton) with 2K photo-textured bodies
    rebuilt from turnaround sheets, with an idle animation only. There's no walking, sitting or face
    animation.
  - **The kit's cast is its own, not ours:** Janine Ward (pub licensee), Sanjay Patel (newsagent), Frank Doyle
    (retired machinist), Amina Okafor (bar worker), Imran Malik (cycle courier), Ewa Kowalska (building
    surveyor), Rory Campbell (print apprentice) and Val Mercer (community walk organiser). Its schedules and
    `Schedules.csv` are for that cast; Evorium's Python routines will drive movement instead.
  - **Close matches for bodies:** Raj → Sanjay, Tommy → Frank, Jess → Amina, Mo → Imran, Chloe → Ewa,
    Brenda → Val.
  - **Decided (19 Nov), the 3D casting:**

    | Evorium | Kit body | Notes |
    |---|---|---|
    | Raj | Sanjay Patel | |
    | Tommy | Frank Doyle | |
    | Jess | Amina Okafor | |
    | Mo | Imran Malik | |
    | Chloe | Ewa Kowalska | |
    | Brenda | Val Mercer | |
    | Dez | Frank Doyle, recoloured | Grey-haired working man, the closest to `dez.png` |
    | Simon | Tommy's body (Frank), recoloured | He's rarely on the street |

  - **Telling them apart:** each character uses an Unreal material instance with its own clothing tint, plus a
    name tag. Clicking a character shows their real 2D portrait, as the Map tab does. The dashboard keeps
    initials for Simon; Tommy's photo isn't reused there.
  - **Not used:** Janine and Rory, available as background extras later.
  - **Later:** ask the friend to build Dez (and Simon) from the portraits, using the same turnaround method.
- **Unreal install (19 Nov):** Unreal Engine **5.8.4** for Linux (precompiled) at
  `/run/media/user/Data Storage/Evorium/UnrealEngine-5.8.4`.
  - It has `UnrealEditor`, `UnrealEditor-Cmd` and the Python Script plugin, so imports and level setup can be
    scripted headless (e.g. by Codex).
  - The GPU is a **GTX 1060 6 GB**, below UE5's comfortable range. The project should switch off Lumen and
    Nanite and use lower scalability settings.
  - **The GTX 1060 can't run Vulkan SM6**, which is the Third Person template's only Linux target, so the editor
    stopped with "Vulkan device could not be created at the project's supported feature levels". The fix
    (19 Nov): `EvoriumUnreal/Config/DefaultEngine.ini` `[LinuxTargetSettings]` now targets `SF_VULKAN_SM5` as
    well as SM6 (backup in `DefaultEngine.ini.bak-before-sm5`). Keep SM5 enabled while this GPU is in use.
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
11. **Keep this file and README.md up to date after every piece of work.** Add what was done to §5 under a
    dated session heading, and update §2, §3, §6 and §7 to match. Put anything about running the game in
    README.md. If nothing needs changing, say so. (Also in `AGENTS.md` for Codex and `CLAUDE.md` for Claude.)

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
