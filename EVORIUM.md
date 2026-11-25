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
> **Last updated:** 25 November 2026

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

**Our word for them: APCs, AI Player Characters** (owner, 20 Nov 2026). They aren't scripted NPCs: they have
lives, memories and ambitions of their own, don't exist to serve the player, and the player is simply another
person in their world. Use "APC" in anything public (website, README, marketing). Code and older history still
say "NPC" (`kind='npc'`); that's fine and doesn't need renaming.

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
  called for conversations, note-taking, daily plans, decisions, the director and digests; promise checks are Python only.
- **Knowledge boundaries.** Characters know only what they saw, were told, or were seeded with. Hearsay is
  labelled as hearsay; inventions are labelled as rumour.
- **Engine-independent core.** The simulation is a Python service with a JSON API. The dashboard, the 2D map
  and the 3D web game all sit on top of the same brain.

---

## 2. Where it stands today

**One sentence:** eighteen AI characters live real-time daily routines around a pub and a newsagent in Ancoats,
Manchester; they talk, gossip, remember, make plans and take validated decisions with financial and social
consequences; you can walk in and talk to them in a dashboard, a 2D map or a 3D world in the browser (desktop
and phone); it runs around the clock on the owner's HP G4 and is reachable over the internet.

| Area | State |
|---|---|
| Characters | 18 APCs + one player per account (existing owner Rob retained; friends created at first login) + 1 system ("World") row |
| Places | Billet normally 09:00–24:00; Patel's normally Mon–Sat 07:00–19:00; festive/bank-holiday hours apply (§4); street always |
| Clock | Real UK time × speed multiplier (0 = paused, 1 = real, up to 600×+) |
| Conversations | 4/6 lines; automatic pairs capped at two per game day, with quiet-APC priority and at least three hours of shared free time per normal week |
| Memory | Facts (seed / observed / told / claim) scored 1–5 for importance; only ≥3 saved or shown |
| Relationships | Directed trust, warmth, familiarity (0–100), shown as words to the model, bars on the map |
| Promises | Typed APC promises require owner-attributed database evidence; completion reports are claims, uncheckable promises lapse neutrally; human self-reporting retained (local, 23 Nov) |
| Plans | Up to two visits/calls per NPC per day, plus at most one action proposal on the morning call |
| Decisions | Fixed menu; one action plus one tell per NPC per day; big decisions need evidence and twelve hours |
| Economy | Visible/private ledger, offers and deadlines, weekly pub settlement, notices, changing routines |
| Story arcs | Python resolves Northgate; darts and flat-hunt templates can follow |
| Realism | Cached Manchester weather, fixed UK holidays/festive events/payday visits, deterministic ordinary setbacks; no extra model calls for Parts 1–4 |
| Police follow-ups | Grace opens serious reported cases, seeks subjects on her beat, approaches the correct player and records advice/warnings (local, 23 Nov) |
| Catch-up | "While you were away": significant events and gossip, cached narration or bullet fallback |
| Director | Nudges a stalled or looping world with one mundane event a day at most |
| Timeline | Permanent record + daily digest, at `/timeline-page` |
| Navigation | ☰ burger menu top right on every page: Dashboard, Map, 3D, Timeline, Guide |
| Dashboard | Character cards, live feed, usage/spend, controls, terrace card, **version** (git commit and date) and the **Restart server** button |
| Map tab | 2D canvas of the pub, shop, empty unit and street; pixel sprites, bubbles, portrait popups |
| 3D game | `/world3d`: five real Ancoats streets by default, with the original kit scene available at `?city=0`; Three.js, nine distinct MPFB models, third person, touch controls, chat, street life and night lighting |
| City pipeline | Five-street Ancoats city generated from surveyed terrain, kit materials and instanced facades; both package limits pass (§7, §10). |
| Hosting | HP G4 home server, auto-updating from GitHub, nightly backups, public via a Cloudflare Tunnel; connection details kept private (§6) |
| Model | DeepSeek `deepseek-flash`, JSON mode, temperature 0.8 (0.6 decisions, 0.2 structured calls) |
| Cost | About $0.00015 per call; about $0.40 a day for the whole world at real speed with auto mode on |
| Tests | 403 Python tests + 18 city tests + Node map/navigation/city/night tests + Web3D Node checks and offline Chrome checks, all fake/offline |

### Tech stack and dependencies

Python 3.11+, FastAPI + uvicorn, `sqlite3` (no ORM), `httpx` (no OpenAI SDK), pydantic, plain HTML/CSS/JS
(no framework, no build step), pytest. Three.js 0.187.0 is vendored locally (MIT) for the 3D game. Node runs the
frontend tests and the 3D asset pipeline only; glTF Transform is a build-only tool. Blender rebuilds the 3D
assets. No Docker, no Redis, no `.env` files: the API key is hardcoded in the git-ignored `config.py` (dotenv
loads the wrong file on this machine).

---

## 3. How it works

### Named accounts (v1)

HTTP Basic authentication accepts named logins from private `config.py`’s `ACCOUNTS` mapping.
Names are matched case-insensitively; matching named credentials select that account. The existing owner
credential still works with **any username**, including a friend’s name, and selects the original player.
With neither owner nor named credentials configured, local development remains the owner without a login.
The canonical account ID is case-folded; `owner` is reserved for the existing owner.

Middleware sets a request `ContextVar` and resets it after the request; synchronous endpoints inherit it
through FastAPI’s threadpool. The first authenticated named request creates that account’s player once,
without model calls. Migration 14 marks the lowest-ID existing player as `owner` without replacing any
history. Migration 17 renames saved place values and APC-readable text from Shuttle Street to Henry Street in
place; message transcripts and timeline entries stay historical and unchanged. It is idempotent and covers
all stored text columns outside those history tables. Player profiles avoid duplicate names/first names across
APCs and players so memory attribution
stays unambiguous; a conflicting account display name receives a distinct player name automatically.

Conversations, learned facts, directed relationships, promises, location and catch-up checkpoints belong
to each player ID/account. The owner retains `player_place` and the existing checkpoint keys; other
accounts use suffixed settings. Catch-up cache keys and narration budgets include the account (still
250 tokens maximum per narration). A live APC conversation with another player reserves that APC for
three real minutes after its latest message. Idle conversations close after five minutes, and maintenance
and startup process every player. All accounts currently retain the full owner’s dashboard/map/timeline
view and controls; this is for trusted friends, not public registration or separate admin permissions.

### The heartbeat (every 5 real seconds, `main._tick_loop`)

1. Read the sim clock (`world.now`).
2. Refresh weather if due; select/maintain deterministic daily setbacks, execute due plans and update routines.
   Weather refresh is a separate 30-real-minute HTTP budget; no model call is used.
3. Deliver once-only calendar events and scheduled world events (letters, phone calls), create offers, notice posted signs, expire deadlines,
   check due APC promises against database evidence (at most two per tick), settle overdue Sundays and evaluate
   Python-owned story outcomes. These continue during model outages and with auto mode off.
4. Close idle player chats; scan Grace’s serious reports and expire unresolved spoken-to cases.
5. In auto mode ("Let them live"): daily digest → daily plans → budgeted reactions →
   optional ending narration → director check → at most one conversation, at whichever public place has 2+
   people and has waited longest. Grace approaches a co-located player with a case before automatic APC
   chats; an available APC case pairing takes priority at its place. Automatic NPC pairs stop after two
   completed/running chats on the same game date. A capped-only opportunity stays silent; player chats
   and manual run controls remain available. Longest-unheard people take priority in ordinary picking.

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
   typed promises (with targets and deadlines), a **feeling** about the other person, new named people and at most
   one decision; plus a summary and completion **claims**, never model-certified promise closures. The example JSON in that prompt shows a filled-in promise and
   feeling on purpose: empty examples get copied, which silently broke feelings and promises before.
4. Python stores it: facts scored below 3 are dropped (at most 3 kept per person per conversation); feelings are
   capped at ±2 and applied ×2; promises get validated types, targets and game-time creation/deadlines, must be
   made to a real other person, and are **fixed once made** (restating one changes nothing); a decision needs at least six verbatim words from that
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
kept promise trust +8 / warmth +2, broken promise trust −12 / warmth −4 (false completion claim −20 / −6),
  note-taker feeling up to ±4 each,
plus the fixed effects of actions. The model only ever sees words ("you are wary of… and like them").

### Promise evidence and claims (local implementation, 23 Nov)

The world decides whether an APC kept a promise. `promise_evidence.evidence_for(connection, commitment)`
requires matching evidence attributable to that promise's owner, at game time on/after `made_at`. The shared
`memory.resolve_commitment` refuses APC completion without evidence and applies each outcome once. Human
players retain their own Done/Didn't do it controls and existing maintenance behaviour.

| Type | Evidence |
|---|---|
| `action` | Owner's `actions` row, `status='done'`, matching allowed registry key and arguments |
| `visit` | Owner's arrival at the specified public place, or completed matching visit plan, within any specified window |
| `talk` | Completed conversation with the named target and an owner message; the promise-making conversation is excluded |
| `tell` | Owner's tell action with the specific fact and recipient, or that same information as an attributed told fact in a completed conversation with an owner message |
| `make` | Quiz questions only: sum of positive `pub.quiz_questions_ready` changes linked to Tommy's own completed write actions since the promise |
| `pay` | Matching accepted offer/loan or accepted/paid loan ask, backed by the owner's matching completed settlement action |
| `conditional` | Explicit condition text, a typed database trigger with a named actor, and a typed inner promise; only evidence after the trigger fulfils the consequence |
| `vague` / legacy `kind=NULL` | No completion certification; neutral lapse at the deadline |

Invalid types, unknown people/actions/arguments, unavailable action ownership and unsupported targets become
`vague`, without guessing. Only quiz questions can currently be made; research, general making, off-ledger
payments and loan repayment have no world action/evidence. Conditions that cannot be expressed as existing
typed database events are vague. No trigger by the deadline means a conditional promise lapses without penalty.

Conversation `commitments_done` IDs create pending `promise_claims` with the owner's words, game time and source
conversation; they do not close anything. Completed plans must match the promise type/target and have actual
evidence. At the deadline, evidence means kept (+8 trust/+2 warmth). No evidence after an hour of awake/free
opportunity means broken (−12/−4). Opportunity samples routines every 30 game minutes and also checks visit
opening hours or conversation-target reachability. No opportunity sets `retry_at` once, 24 game hours after
`due_at`, leaving the original deadline unchanged; still no opportunity at retry means a neutral lapse.
Late heartbeat processing evaluates evidence at the original deadline/retry, not at its later processing time.

An unsupported completion claim on a checkable, triggered promise becomes false at the deadline, with
−20 trust/−6 warmth, a timeline entry and an observed recipient fact. Supported claims are marked supported.
Resolution facts describe world records rather than the APC's explanation. Neutral lapses produce one
recipient fact without changing trust. Existing gossip/tell and catch-up carry these outcomes.

Migration **15** only adds fields, the claim ledger and indexes: no table rebuild, status CHECK change or
foreign-key disabling. A lapse remains `status='open'` in SQLite with `lapsed_at` set; all open/current views,
planning validation and maintenance exclude it, while promise history displays **lapsed**. `made_at` is game
time, back-filled from the source conversation where available; `commitments.created_at` remains real time and
is never compared to game evidence. Older rows without a recoverable game timestamp lapse neutrally.

Dialogue, morning planning and reactions receive deadlines and actual progress (including question counts).
Promise reminders reuse the existing bounded reaction queue, menu and plans/`fulfils` mechanism; no new
scheduler, model call or dependency. The extraction JSON example includes a filled typed promise; normalization
preserves its kind/target. The previous example-specific content suppression was removed so the forty-question
promise itself is never silently discarded.

### Weather, calendar and ordinary bad days (local, 23 Nov)

All routines remain pure functions of `(name, datetime, stats)`. `world.routine_inputs` assembles ledger,
weather and daily-condition inputs outside the routine. No routine reads settings, calls the network, hashes
random choices or invokes a model. `world.shared_free_hours` counts complete shared 30-minute slots in a normal week, checking every minute against
real opening/free rules; all eighteen APCs have at least three hours of shared free time. Existing story beats
remain, with tea breaks/lunches/after-work visits for isolated people. The complete-slot audit additionally extended
Gary’s afternoon visits and Grace’s community stops, avoiding over-counted brief encounters.

`weather.py` uses existing httpx and fixed Ancoats coordinates (53.485, −2.226). The tick reserves a refresh
attempt in world settings no more than every **30 real minutes**, including failed attempts, with a **three-second
timeout**. It stores temperature, WMO-derived condition, rain, wind and observation time. Failures retain the
prior reading; none/older than **six real hours** means unknown and no effects. Fetch only at real-aligned 1×
(within five minutes of UK real time); other clocks reuse the labelled **last reading**, without inventing
conditions. Page requests/prompts only read the cache. See [Open-Meteo documentation](https://open-meteo.com/en/docs).

Rain shelters Peggy in the pub, skips Kirsty's pram walks and shortens Liam's doorway smoke break to five
minutes. Optional street tea/chat pauses shelter too; heavy rain/thunder stops Barry's window work. Necessary
travel and outdoor duties continue. The dashboard/header, map and public scene expose the reading, including
unknown/cached status. The guide credits Open-Meteo (CC BY 4.0). `WEATHER_ENABLED=False` disables fetches.

`calendar_uk.py` holds a fixed England bank-holiday table through **2027**, verified against
[GOV.UK](https://www.gov.uk/bank-holidays). Christmas Eve/New Year's Eve/Bonfire Night and last-working-day
payday are pure date context. Calendar hours apply to all routines/plans. Payday and the following Friday may
extend an existing free evening pub visit by at most one hour, capped by normal sleep/work/closing rules.
This changes opportunities for company, not wages/bank balances. World-settings markers make the **2026**
decorations, ticket sales, raffle draw, Christmas Eve and New Year's Eve events once-only. Present APCs get
observed facts; public decorations/ticket notices inform later visitors. SHA-256 picks a raffle winner only
from APCs present at the draw; a restart on a later date records no invented winner. No extra people appear.

`bad_days.py` selects and persists one outcome per APC/date with SHA-256: **3% off sick**, **6% running late**
by 30–60 minutes, **35% hungover only among recorded post-23:00 pub attendees**, otherwise ordinary routine.
Outcomes are mutually exclusive. Late-pub eligibility uses tick-recorded actual presence or recorded chats,
never a guessed routine. Seed-story-event, open-offer expiry and open-promise due/retry days are exempt;
festive hosts' key dates are protected. New critical deadlines suppress an already-selected setback.
Sickness means home, awake and unavailable for visits. Delay shifts only the first departure; hangovers delay
it by an hour and give a rough morning. Plans cannot override a blocked visit. Jess's absence leaves the pub
open with Dez behind the bar; simultaneous sickness is suppressed for Dez when needed to cover.

Each setback creates its own observed fact and low-priority god-view timeline entry once. Only that APC gets
the short feeling context; others learn it through conversation. The god-view card shows the condition.
Temporary mood restoration never overwrites a mood changed by dialogue. Weather occupies one short prompt
line; calendar plus the APC's feeling share the second. Existing dialogue/planning calls and output budgets
are unchanged: approximately **40–70 extra input tokens** for these dedicated lines (model-tokenizer estimate),
under **$0.00003 per uncached call** at the documented peak input price, with no additional model calls.
Existing bounded memory retrieval still carries newly observed facts in the usual way.

All small state uses the existing `world` settings table; migration 17 now updates saved Henry Street place
references and APC-readable text while preserving transcripts and timeline history.
Promise evidence/resolution and seed facts are unchanged. Test weather HTTP is faked globally; the smoke
server disables refresh and uses fake dialogue on a SQLite backup copy.

### Grace follows up reports (local implementation, 23 Nov)

Migration **16** appends `cases` and a partial unique index: one unresolved case per subject agent ID.
Cases retain reporter, source fact/timeline reference, summary, opening time, open/spoken_to/closed status,
outcome and closing time, incident/spoken times and daily attempt markers. Nothing reseeds or rewrites history.
`cases.py` scans Grace's importance-5 `told` (with an identified teller) or `observed` facts. It requires a named
world person acting in an explicit threat/harm statement; claims, importance-4 and vague fears do not qualify.
The first scan back-fills existing reports, using source-conversation game time when available, then a durable
fact-ID checkpoint processes new reports without reopening old closed ones. New reports refresh incident time.

During her existing weekday 08–17 and Friday/Saturday 17–24 beat hours, Grace prioritises a free, co-located
APC subject in automatic pairing, at most once per case per day. Patrol is available for her police work;
other APCs must be free of work and chats. Her dialogue gets the attributed report gist and asks her to hear
the subject's account. No model call chooses cases or pairs. For players, `cases.approach` uses their own
account's `player_place`, reserves an ordinary player-first conversation under the shared player lock, and
makes one normal **300-token** opening dialogue call. No ongoing player chat is interrupted, including another
account's chat with Grace. Daily attempt markers survive restarts. Replies and notes use ordinary player chat.
When the subject is elsewhere, a daily missed-visit fact feeds their catch-up and a persistent **PCSO Grace
Adeyemi wants a word** notice. Case opening/timeout work with auto off; approaches and automatic chats need auto.

Only Grace, talking to that unresolved case's subject, can `give_advice(person)` or
`give_formal_warning(person)`. They use the existing conversation decision path, her own six verbatim words,
strict arguments, savepoint and daily action guard; planning/reaction calls cannot issue outcomes.
The extraction example now includes a filled spoken decision (Part 1 prerequisite); examples remain
illustrations, and copied or misattributed words fail validation. Grace chooses in character: an apology and
owning it may merit advice; denial or repetition may merit a warning. No arrests, courts or other punishments.
An unresolved conversation marks `spoken_to`; after three game days since speaking or a newer incident,
Python closes it as `no_further_action`. Each outcome records serious history, an observed subject fact,
Grace's own record and an attributed reporter fact. Dez decides for himself whether to serve someone again.

The dashboard APC cards (including Grace's case list) and case/serious timeline filters are god view.
Only the subject's own panel gets their notice and outcomes. The 3D panel polls ordinary player state and
opens incoming dialogue without replacing another chat; street walking now explicitly sets street presence.
Private rationale is omitted from player dialogue. No extra officers, dependencies, enforcement or scheduling
model calls were added.

### Decisions, money and consequences (M4)

- **The ledger** (`economy.py`) owns integer stats, changes, offers, asks and notices. Each stat says who can see
  it; characters only get the figures they'd know.
- **The action menu** (`actions.py`): 30 fixed actions with typed arguments, Python checks, atomic effects,
  witnesses and relationship changes. Examples:
  - Dez: change the pint price, set Jess's shifts, announce or start the quiz, ring Northgate, counter the rent,
    accept or refuse the renewal, ask for a loan;
  - Raj: accept or refuse the surrender, ask for more, warn the neighbours;
  - Simon: raise an offer, offer a rent deal, set a deadline (his hidden limits, £60,000 and £3,300, are
    enforced in Python and appear only in his own prompts);
  - Jess: ask for more hours, look for another job, accept or refuse a job offer;
  - Grace: words of advice or a formal warning in a case conversation;
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
simple hulls, and animates the third-person player and NPCs. Individual MPFB models load lazily with shared
retargeted clips; failed models use a logged Quaternius fallback. It polls `GET /world/scene` every 1.5 seconds
(5 seconds after errors). That endpoint reads a consistent read-only SQLite snapshot and exposes public presence
and dialogue only, with no model calls. Spot assignments live in Python; the browser handles walking (along a
collision-verified A* graph. `?city=1` joins that graph to sampled OSM road/path centerlines and uses heap-based A*), bubbles, lighting and doors. The city is static client-side geography and does not change simulation places or routines. `ambient.js` adds browser-local cosmetic street life with its own visible-tab clock, lazy animal loads and no collision in the player octree. Player actions use the existing `/player/*` and
`/catchup` endpoints. NPC rationale and private facts never appear in the player UI. Details in §7.

### Code map

| File | What it does |
|---|---|
| `evorium/main.py` | FastAPI app, tick loop, endpoints, auth middleware, log file, restart endpoint |
| `evorium/world.py` | Sim clock, pub hours, routines (read from the ledger), `whereabouts` |
| `evorium/places.py` | Pub/shop registry, opening hours, who's present, conversation opportunities |
| `evorium/tick.py` | Routine updates, event delivery, due-promise checks |
| `evorium/sim.py` | Conversation runner, note-taking, `turns_for` |
| `evorium/memory.py` | What a character knows (`knowledge_for_prompt`), storing notes, promise claims and guarded resolution |
| `evorium/weather.py` | Background weather fetch, validated WMO reading and persisted cache/fallback |
| `evorium/calendar_uk.py` | Fixed holidays, hours, payday context and once-only festive events/raffle |
| `evorium/bad_days.py` | Deterministic daily conditions, eligibility/exemptions, own facts and safe temporary moods |
| `evorium/cases.py` | Grace’s report scanning, follow-up scheduling, account-specific approaches and validated case outcomes |
| `evorium/promise_evidence.py` | Typed target validation, owner-attributed game evidence, progress and opportunity checks |
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
| `evorium/accounts.py` | Request identity, account-owned players and per-account settings |
| `evorium/player.py` | Each human player’s profile, presence, chats and promises |
| `evorium/llm.py` | DeepSeek client, budget cap, usage and cost records |
| `evorium/db.py` | Schema migrations (17 so far), connection helper |
| `evorium/seed.py` | Cast, seed facts, scheduled events, starting relationships |
| `evorium/rescore.py` | One-off importance scoring of old facts |
| `evorium/static/index.html` | Dashboard + tab bar |
| `evorium/static/map.js` | Map tab |
| `evorium/static/timeline.html` | Timeline page |
| `evorium/static/nav.js` | Shared burger menu on every page |
| `evorium/static/guide.html` | Player guide at `/guide` (behind the login) |
| `evorium/static/world3d/` | The 3D game (ES modules, data, assets) |
| `evorium/static/vendor/three/` | Vendored Three.js 0.187.0 |
| `tools/web3d/` | 3D asset pipeline and checks (§7) |
| `tools/smoke_server.py` | Offline smoke server on a database copy with fake replies (§5) |
| `deploy/` | Home server installer, auto-updater and backup tool (§6) |
| `website/` | The marketing page (§8) |

### Endpoints

- **Read:** `GET /agents` (adds `today_action`, `considering`), `/usage` (sim time, speed, places, present,
  ledger, `boot_id`, `version` {commit, date, subject, modified}, `model_paused_until`), `/events`, `/conversations/latest`, `/conversations/{id}`,
  `/timeline` (filters `since`, `until`, `agent_id`, `min_importance`, `kind` = action/offer/arc; timestamps
  `YYYY-MM-DD HH:MM`), `/me` ({account, name}), `/player`, `/world/ledger`, `/actions?since=`, `/catchup`, `/world/scene`.
- **Pages:** `/` (the public website from `website/`, no login, with `/styles.css` and `/images/…`), `/game`
  (dashboard; `/game#map` for the map), `/timeline-page`, `/world3d`, `/guide`. Everything except the website needs a login.
- **Write:** `POST /conversations/run`, `/speed`, `/auto/start`, `/auto/stop`, `/director {enabled}`,
  `/player/profile {name, about}`, `/player/enter {place}`, `/player/leave`, `/player/say {to_agent_id, text}`,
  `/player/end`, `/player/promises/{id} {done, note}`, `/catchup/seen`, `/server/restart`.

---

## 4. The world: cast, places, routines, story

Henry Street, Ancoats is the real street. The Crooked Billet and Patel's News remain fictional businesses
located on it.

Grace follows serious reports up through cases (§3), using her existing patrol and Friday/Saturday closing-time visits. No other police characters are added.

### The cast

| Character | Who | Routine (summary) |
|---|---|---|
| **Dez Whitworth**, 54 | Landlord, The Crooked Billet. Dry, loyal, worried about the lease. | Cash and carry 07–09; behind the bar when open, quiet tea 14:00–14:30 and a short pavement breather; covers Jess if sick; flat upstairs |
| **Jess Hartley**, 34 | Barmaid, single mum to Alfie. Sharp, tired, needs hours. | Office cleaning weekday mornings; bar shifts 17–23 on Thu, Fri, Sat, Sun (her shift count from the ledger, filled in that order, then Wed, Tue); Tuesday lunch 13–14 and a drink on Wed evening |
| **Tommy Shaw**, 67 | Retired bus driver. Mischievous; wants the Thursday quiz back. | Walk to shops 10–12; pub most evenings 19–22:30 (Thu from 18) |
| **Raj Patel**, 41 | Runs Patel's News (family shop since 1988). Careful, warm. | Shop Mon–Sat 07–19; quiet half Tue/Thu/Fri evening; Sunday pint |
| **Chloe Barlow**, 29 | Junior architect from Stockport. Looking for a flat. | Coffee at Patel's 08:15–08:35 weekdays; work 9–18; pub Tue–Fri 18:15–21:30, Saturday afternoon |
| **Simon Ferris**, 46 | Asset Manager, Northgate Estates. Polite, corporate, evasive. | Office weekdays; lunch at the Billet Mon/Tue/Wed/Fri 12:30–13:30; Patel's News Thursdays 14:00–14:30 |
| **Brenda Ashworth**, 71 | Retired dinner lady, tenants' association chair. Loves a petition. | Paper at the shop 09:00–09:30; pensioners' lunch at the pub Tue/Thu 12:30–14; Wed evening; Sat and Sun 13–15 |
| **Mo Iqbal**, 38 | Private hire driver, nights. Funny, observant, doesn't drink. | Shop 16:00–16:20; pub Tue/Thu/Fri 18–19:30 before his shift and Sunday afternoon; drives 19:30–04 |
| **Peggy Coyle**, 82 | Retired mill worker, widow, sixty years a regular. Sharp, funny, nosy, remembers the old street. | Paper at Patel's 09:30; half of stout at the bar Mon–Sat 12–14:30; Sunday 13–15 |
| **Liam Byrne**, 27 | Scaffolder on the mill conversion behind the terrace. Cheerful, loud, saving a deposit with Kayleigh. | Breakfast at Patel's 07:00; on site 07:30–16:30; Billet at lunch 12:30–13:15; Friday pint 17–21 |
| **Anjali Patel**, 19 | Raj's daughter, law student at Manchester Met. Bright, direct, protective; knows her dad's worried. | Lectures weekdays; behind the counter Mon/Wed/Fri 15–19 and Saturday 9–17; pub friends Tue/Thu 18–19:30 |
| **Pete Lomax**, 58 | Brewery drayman for thirty years. Gruff, kind, a gossip; knows which pubs have shut. | Delivers to the Billet Tue/Fri 10:00–10:45; on his round weekdays; Saturday afternoon pint |
| **Hannah Kerr**, 31 | Local news reporter digging into firms buying up Ancoats. Friendly, persistent, protects sources. | Papers and coffee at Patel's 08:30 weekdays; Billet Wed/Fri 17:30–19:30 |
| **Gary Walsh**, 49 | Postman, fifteen years on the round. Chatty, terrible jokes, sees everyone's post. | Post at Patel's 08:30, along the terrace 08:40–09:00; Billet Mon/Wed 14–17 |
| **Kirsty Doyle**, 26 | Young mum (baby Mia), Jess's neighbour and best mate. Warm, frazzled, a bit lonely. | Pram round the block 10:30 and 14:00 daily; Patel's 11:00; Wednesday lunch at the Billet |
| **Grace Adeyemi**, 33 | PCSO for Ancoats. Calm, observant, approachable; doesn't gossip. | Patrols past the terrace 10:00, 13:30, 16:00 weekdays, with community stops 10–11 Mon/Wed/Fri, 10–10:30 Tue/Thu and short pauses at 16:00; looks in at the Billet at closing Fri/Sat |
| **Barry Hughes**, 61 | Window cleaner who sees inside every building. Wry storyteller. | Terrace windows Mon/Thu 09–12 with a 10:30 flask break, then dinner; Friday pint 17–19 |
| **Ronnie Clegg**, 70 | Retired bus driver, Tommy's old mate from the 216. Dry, competitive, likes a bet. | Paper and racing post at Patel's 09:45; Billet Mon/Wed/Fri 13–16 and Sunday lunchtime |

When the quiz runs (Thursdays 19:30–22:30), Tommy, Brenda, Chloe, Peggy, Hannah and Liam come in if they're free, with Ronnie and Gary. A closed pub or shop
sends its people home. House rule: names mostly British, a few others.

### Calendar and opening exceptions

- Christmas Day: Billet **12:00–16:00**, Patel's **shut**.
- Boxing Day and listed bank holidays: Patel's **09:00–16:00**, including Sunday Boxing Day.
- New Year's Day: Billet **12:00–24:00**. Other pub days retain 09:00–24:00, unless the ledger closes it.
- 2026: decorations and raffle tickets **5 Dec 12:00**; raffle **20 Dec 20:00**; Christmas Eve evening
  **24 Dec 19:00**; New Year's Eve **31 Dec 20:00**. Decorations remain until 6 Jan; ticket sales stop at draw time.

Rain, closures and recorded bad days override optional activities, so a listed base routine is not a guarantee
someone will be there. Payday lengthens some evening visits without moving shifts or established story beats.

### The story seed

Northgate Estates bought the freehold of the whole terrace (pub, newsagent and the empty unit between) three
months ago. Simon's instructions: bring rents to market level, buy out leases where cheaper.

- Pub renewal proposed: **£3,900 a month, up from £2,400**, from 25 March 2027 (letter Thu 19 Nov 09:00).
  **Reply due 17 Dec 09:00.**
- Raj offered **£45,000 to surrender his lease** (phone call Wed 18 Nov 11:00). **Expires 18 Dec 11:00.**
  Simon can go to £60,000 and won't volunteer it.
- No planning application yet; redevelopment discussed but not decided.
- **New threads (20 Nov):** Liam overheard the mill site foreman say Northgate "will want the corner"; Pete knows
  pubs on his round that shut after new owners doubled the rent; Hannah has Land Registry proof Northgate bought
  four Ancoats buildings this year and wants someone on the record; Anjali (law student) can tell her dad is hiding
  something and would want to read any lease before he signs. Gary delivered recorded letters from Northgate to
  all three units, including the empty one; Barry saw two men in suits measuring the empty unit last month; Kirsty's
  block was sold and her rent went up £150; Grace hasn't had anything reported about the Billet (Dez promised Jess
  he'd ring the police about Rob).
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

- Open `http://127.0.0.1:8000/game` (the website is at `/`). Startup creates `evorium.sqlite3` and seeds the cast if it's absent;
  restarting reuses the database. Existing saves migrate in place and are never reset. Migration 17 renames
  saved street references on startup; it is covered by an old-schema temporary-database test.
- **Stop:** Ctrl+C, or `pkill -f "uvicorn evorium.main:app"`. **Restart after code changes:** the "Restart
  server" button, top right of the dashboard (it re-runs the same command and the page reloads itself).
- **The real world lives on the G4 now (§6).** On the main PC, only run copies: `EVORIUM_DB_PATH=/path/to/copy.sqlite3`
  and never switch on auto mode against a second copy of the real world.
- **Phone on the same Wi-Fi:** enable access control in the local config first, then start with `--host 0.0.0.0` and browse to
  `http://<PC's LAN address>:8000`. This exposes the server and its controls to your network.

### Optional city build (main PC only)

The city pipeline is separate from the game runtime. It uses build-only packages listed in
`tools/city/requirements.txt`; it does not change the app's `requirements.txt` or the G4. Run from the repository root:

```bash
python3 -m venv tools/city/.venv
tools/city/.venv/bin/pip install -r tools/city/requirements.txt
npm ci --prefix tools/web3d
tools/city/.venv/bin/python tools/city/build.py
```

Use `build.py --stage fetch` (or choose `heights`, `geometry`, `facades`, `props`, `export` or `navmesh`) to run
one stage. The fetch stage reuses `tools/city/raw/osm-overpass.json`. Fresh queries use current Overpass data.
The manifest records the snapshot date and SHA-256. For an isolated offline fixture build, point the config
at separate build and static output directories and use `--fixture`. The G4 updater's default pytest collection
is limited to `tests/`. Run the optional build tests with
`timeout 120 tools/city/.venv/bin/python -m pytest -q tools/city/tests`.


### Settings (`config.py`, git-ignored)

| Setting | Default | What it does |
|---|---|---|
| `DEEPSEEK_API_KEY` | `"sk-..."` | Your key. Hardcoded here only; never in frontend code, logs or git |
| `DEEPSEEK_MODEL` | `deepseek-flash` | Model name |
| `ACCOUNTS` | `{}` | Optional display-name → credential mapping, set privately in `config.py`; restart after changes. Example structure only in `config.example.py` |
| `MAX_SPEND_USD` | 4.00 | Local cap: new calls are refused once estimated spend reaches it (not a provider cap; "remaining" assumes the original $5) |
| `INPUT_USD_PER_MILLION` / `CACHED_INPUT_USD_PER_MILLION` / `OUTPUT_USD_PER_MILLION` | 0.30 / 0.006 / 1.20 | Peak prices; off-peak is half |
| `REACTION_CALLS_PER_DAY` | 12 (max 12) | World-wide reaction budget |
| `CATCHUP_COOLDOWN_SECONDS` | 600 (min 600) | Real-time gap between catch-up narrations |

Environment variables: `EVORIUM_DB_PATH` (another world file), `EVORIUM_LOG_FILE` (another log file; empty turns
the file log off, as the tests do), `EVORIUM_SMOKE_DB` (where the smoke server copies the world).

Named accounts are optional. Keep real passwords only in the server’s ignored `config.py`; never put
values in docs, tests, logs or Git. The owner’s existing authentication setting stays valid with any
username. Use distinct privately chosen credentials for each friend. The example config leaves
`ACCOUNTS` empty and shows only a placeholder. Basic authentication uses the existing HTTPS tunnel
when accessing the game remotely. `GET /me` reports the current canonical account and character name.

### Model calls and cost

- **Limits:** dialogue and player replies 300 tokens; note-taking 900; promise checks use no model tokens; daily planning 400 per
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
timeout 120 .venv/bin/python -m pytest -q -x        # 403 tests
for f in tests/*.test.cjs tests/*.test.mjs; do timeout 120 node "$f"; done
timeout 120 bash tools/web3d/run_checks.sh       # 3D: smoke server + 20 headless screenshots and movement checks
```

Tests use temporary SQLite files and never call the real API. `tests/conftest.py` turns off the file log and the
machine’s local authentication settings. Schema changes are appended to `MIGRATIONS` in `evorium/db.py` (version 17 in
SQLite's `user_version`). Each connection enforces foreign keys, commits on success, rolls back on failure and
closes when finished.

### Testing Grace in the game

After normal deployment/restart, sign in as the owner’s Rob. In the dashboard, expand Grace’s card:
her god-view case list should contain the unresolved Rob report sourced from Dez. Rob’s You panel should
say “PCSO Grace Adeyemi wants a word”. If the case is absent, inspect the back-fill before provoking anyone
again; the real G4 report has not yet been verified by this implementation session.

Keep the clock at 1× and “Let them live” on. End any current chat, then use the dashboard places list/map
to find Grace and enter her actual place. Her street visits are 10:00–11:00 Mon/Wed/Fri or 10:00–10:30 Tue/Thu, plus 13:30–13:50
and 16:00–16:20 weekdays, then the shop around 13:50–14:00; she visits the Billet Friday/Saturday 22:45–23:15.
When both are available, let the heartbeat start her conversation rather than clicking Send first.
She approaches at most once per case per game day. Reply naturally (for example, own the threat and
apologise), then press **End conversation** so ordinary notes can record her spoken decision.
Check Rob’s outcome/learned facts, Grace’s case status, the serious timeline entry and Dez’s recently learned
facts. Advice versus warning is Grace’s choice; no spoken outcome leaves `spoken_to` open until the
three-game-day no-new-report timeout. These conversations change real memories; do not manufacture a
new threat just to rerun the test. Automated fake-client cases can be rerun with
`.venv/bin/python -m pytest tests/test_cases.py -q` without changing the live world.

### Testing the realism pack offline

`.venv/bin/python -m pytest tests/test_realism_behaviour.py tests/test_weather.py tests/test_calendar_uk.py tests/test_bad_days.py -q`
runs the 35 focused checks without live state or HTTP. The full suite also includes Grace's follow-ups and the
pre-existing acquaintance/job-context changes. Use the project virtualenv; the machine's system packages have
an incompatible old TestClient. This session's sandbox hangs async HTTP tests; the virtualenv suite passes
outside it. Browser smoke uses only a copied database, disables weather refresh and uses fake model clients.
The browser test hooks exercise rain/snow/fog/unknown and festive lights as well as movement and chat.

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

The realism pack needs no new dependency, API key or service. Weather adds at most 48 short outbound HTTPS
attempts per real day to Open-Meteo; failures keep the world running. Optional `WEATHER_ENABLED=False` goes in
private `config.py` to stop requests. No server credentials, configuration or live state were changed here.

The real Evorium runs on the owner's always-on **HP ProDesk 405 G4 Mini** (Ryzen 5 PRO 2400GE, 16 GB RAM,
128 GB, Ubuntu 26.04). Deployment-specific addresses, account names and absolute server paths are kept
private. In commands below, `<server-user>`, `<server-address>`, `<project-dir>` and `<tunnel-domain>`
are placeholders to fill in privately.

City data downloads, LiDAR processing and build tools stay on the main PC. The G4 receives only finished,
budget-checked city assets in a reviewed code update. The updater’s default pytest run collects only the app tests under `tests/`.

- **Public access:** the Cloudflare address shows the public website at `/`; its Play button goes to `/game`
  (login required), and the 3D game is at `/world3d`.
  The game listens on 127.0.0.1 only; the tunnel is the only way in from outside the G4, and the firewall has no
  rule for port 8000.
- **Everything comes from GitHub.** Work on the main PC and push to `main`; the G4 updates itself.
- **Never on GitHub:** `config.py` (private configuration), `evorium.sqlite3` (the world) and `backups/` exist only
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

The local promise fix appends migration 15; the normal updater backup remains required before deployment.
Migration was checked on a version-14 copy with referenced plans and on the isolated smoke-world copy, with
foreign keys enabled and integrity checks passing. The G4 world/service was not touched during implementation.

### Add a trusted friend (accounts v1)

After deploying this version and backing up normally, edit only the G4’s ignored `config.py` to add
the friend’s display-name entry to `ACCOUNTS` with their privately chosen credential. Preserve the owner’s
existing authentication setting. Do not paste real credentials into chat or tracked files. Then run
`sudo systemctl restart evorium`. The friend logs in using their configured name (case-insensitive) and
their own credential; their new character appears on first authenticated request. Using the owner’s
credential still plays as the original owner regardless of username. Removing an entry disables that
login without deleting the player’s history. No server configuration was changed by the accounts build.

### One-time alignment after the security history cleanup (21 Nov)

GitHub history was sanitised with git-filter-repo 2.47.0; this main-PC checkout is already aligned.
Old server clones cannot fast-forward to the rewritten branch. The updater refuses safely and leaves
its running service in place. Existing trusted SSH access was unavailable from the cleanup session.
On the G4, from its existing checkout, inspect `git status --short` first. If tracked files have local
edits, preserve/review them before proceeding. Then run:

```bash
.venv/bin/python deploy/backup_world.py --keep 30 &&
git fetch origin main &&
git reset --keep origin/main
```

`--keep` refuses conflicting local edits and leaves ignored private configuration, world data and backups
in place. The next scheduled updater can then follow new commits normally. Do not merge the old history
back in. Other development clones must likewise align cleanly or be recloned without discarding private
configuration or world data. A restricted, git-ignored history bundle is retained under
`backups/security-cleanup-20261121/`; it contains pre-cleanup data and must never be uploaded.

### Services on the G4

| Service | What it does |
|---|---|
| `evorium` | The game, on 127.0.0.1:8000, restarts itself if it stops and starts at boot |
| `evorium-update.timer` | Auto-update from GitHub every 2 minutes |
| `evorium-backup.timer` | Nightly backup at 03:15 to `backups/`, keeping 14 (`deploy/backup_world.py`, SQLite backup API). A systemd timer because Ubuntu 26.04 has no cron by default |
| `cloudflared` | The public tunnel (Cloudflare Tunnel, token-based). Its public hostname → `http://localhost:8000` is set in the Cloudflare dashboard, not in a file on the G4. `cloudflared-update.timer` keeps it updated |

A sudoers rule lets the configured service account run `systemctl restart evorium` only, for the updater.

**No home-network access (25 Nov).** Root-owned systemd drop-ins stop Evorium reaching the LAN while keeping the
internet: `evorium.service.d/network.conf` and `evorium-update.service.d/network.conf` set
`IPAddressAllow=localhost` and `IPAddressDeny=10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 169.254.0.0/16 100.64.0.0/10
224.0.0.0/4 255.255.255.255/32 ::/0` (all IPv6 except `::1` too, because LAN devices can have public IPv6
addresses); `evorium-backup.service.d/network.conf` sets `PrivateNetwork=yes`. DNS works because the G4 uses the
local resolver `127.0.0.53`; if that ever changes to a LAN or VPN DNS server, Evorium's lookups will fail.
Cloudflare Tunnel, SSH, Remote Desktop, the VPN and other accounts' services are separate units and unaffected.
Check: `systemctl show evorium -p IPAddressDeny`. Undo: delete the three `.d` folders, `daemon-reload`, restart.
Still to do: replace the updater's sudo restart with a no-privilege restart and delete the sudoers rule; make the
code folder read-only to the game; further systemd hardening (see 25 Nov in §14).

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
| Tunnel status | `systemctl status cloudflared`, or the Cloudflare dashboard (Zero Trust → Networks → Tunnels) |

### Setting up a server from scratch (for reference)

1. **Account:** `sudo adduser evorium` (any name), then give it admin rights from an admin account:
   `su - <admin>` → `sudo usermod -aG sudo <name>` → `exit` → `exec su - <name>`.
2. **Basics:** `sudo apt update && sudo apt install -y python3 python3-venv git openssh-server`.
3. **Code:** `cd ~ && git clone https://github.com/DgenKing/evorium.git && cd evorium` (the repo is public).
4. **World and config, from the main PC:** stop its server, then
   `scp ~/projects/evorium/config.py ~/projects/evorium/evorium.sqlite3 <name>@<address>:~/evorium/`.
   Enable access control in the server’s private configuration.
5. **Install:** `bash deploy/install_home_server.sh`. It builds the venv, checks the private configuration, installs
   the `evorium` service, auto-update, the sudoers rule and the nightly backup, and takes a first backup. Safe to
   re-run.
6. **Cloudflare Tunnel:** needs a domain on a Cloudflare account. In the dashboard (Zero Trust → Networks →
   Tunnels) create a tunnel, run the `cloudflared service install <token>` command it shows on the server, and
   add a public hostname pointing to `http://localhost:8000`. No LAN firewall rule is needed: keep the game on
   `--host 127.0.0.1`.
7. **Stay up:** Settings → Power: automatic suspend off. BIOS (F10 on HP): After Power Loss → Power On.

### Good to know

- Each account now plays its own character; the original owner keeps Rob and his history. Everyone still
  sees the owner’s god view and controls, including private thoughts, until the separate player view (§11).
- Home upload speed limits how fast the 3D files reach each visitor; fine for a handful of people.
- Later, with real players, the same setup moves to a VPS: it's a copy-the-world-file job.

---

## 7. The 3D web game

Cached weather drives lightweight rain/snow particles, wet-surface sheen/darker daylight and fog. Low quality
uses at most 60 rain streaks or 40 snowflakes; higher quality at most 360/220. Unknown weather removes effects.
Particles are confined to the street and do not add collisions, people, assets or dependencies. The calendar
switches a small instanced festive light string; no new art pipeline is needed. Real-phone performance still
needs hardware checking; desktop headless software-renderer timings are not phone FPS measurements.

Grace can now walk up for a report follow-up: the ordinary chat panel opens with her spoken line, and a
notice/outcome appears above the street. Incoming chat never replaces an already-open chat. Walking on the
street sets `player_place=street`; entering/leaving buildings updates that presence as normal (§3).

Open `/world3d`, or **3D** in the dashboard header. No build step or runtime Node: Three.js, the high/low assets,
ten animation clips and baked lighting are served by FastAPI. The EVORIUM wordmark returns to `/`.

### Generated Ancoats city (normal map)

`/world3d` opens the generated Ancoats streets by default. `/world3d?city=0` opens the original kit scene;
test harness pages stay on the kit scene unless explicitly passed `?city=1`. City mode conditionally
loads `data/city.json`, `city.glb`, `city-collision.glb` and, when present, `city-props.glb`; it places the fictional Billet/Patel kit at the transform in `tools/city/config.yaml`, joins its street exits to the generated walk graph, and credits
OpenStreetMap and the Environment Agency in the ⚙ settings panel (not on the game screen), the guide and the
website footer, as the ODbL and OGL licences require. The local review build is available in this mode.

Night uses a phase-correct moon sprite, stars that fade in cloud, rain, snow or fog, emissive lamp heads and
ground pools for all 74 city lamps. Up to four nearby PointLights run on medium/high; low uses only the emissive
heads and instanced pools. The ambient floor and moonlight keep buildings and streets readable. The kit scene's
existing windows, festive lights and interior lights continue using the shared day/night update.

From the repo root, follow the §5 setup and run:

```bash
tools/city/.venv/bin/python tools/city/fetch.py --lidar
tools/city/.venv/bin/python tools/city/fetch.py --tree
tools/city/.venv/bin/python tools/city/build.py
```

**EA terrain and heights.** The fetch command uses the cached ZIPs if present, or downloads tiles SJ89nw
and SJ89ne from the [EA survey collections](https://environment.data.gov.uk/tiles/collections/survey).
The exact URL suffixes are `/{lidar_composite_dtm|lidar_composite_first_return_dsm}/2022/1/{SJ8095|SJ8595}`.
The script extracts the TIFFs, mosaics each product with Rasterio, and clips both to the OSM box plus 20 m
(E384595–385035, N398470–398810). The aligned 1 m EPSG:27700 GeoTIFFs use nodata −9999 and stay at
`tools/city/raw/lidar_dsm.tif` and `tools/city/raw/lidar_dtm.tif`. The build manifest records their hashes.
The first-return DSM minus DTM gives 154 of the 156 heights. Two use type defaults. Interior sample relief
guides terrace roof selection where enough samples survive the edge mask. Terrain uses the DTM in metres
relative to the flat kit-scene block, with a blend around it.

**OSM and placement.** The pinned 24 Nov snapshot has 800 elements and SHA-256
`1735fbcc98e29e23679d66d7ca998a5d315e2d9579c04f19a20763c3af6add32`. The 400 × 300 m Cutting Room Square box
contains 156 building footprints, 571 road/path features, 21 trees, 21 mapped props, 3 water features,
24 land-use features and no tagged shops. The kit follows Henry Street at [4.9, 5.48] m and 41.8° yaw.
Six overlapping footprints are removed. The generated scene has 150 buildings and 212 props.

**Materials and facades.** Put the owner's raw kit at `tools/city/raw/kit/`. The generator reads its material
manifest and embeds the selected brick, plaster, stone, slate, asphalt, setts and terrazzo maps as WebP.
Low uses 48 px colour maps. High uses 128 px colour and 64 px normal and roughness maps. Texture repeats
use metres, calibrated against the supplied FBX. Its 77 upper-glass panes measure about 0.50 × 1.38 m each.
The generated bays use shared sash and taller mill window modules. High has 12 cm recesses and segmental
mill lintels. Low uses lighter profiles. High and low share LiDAR terrain, 15 cm kerbs, generic shopfronts,
roof silhouettes, baked vertex shade in reveals and near footprint contacts, and night window glow.
The tree fetch pins the CC0 Kenney source mesh and palette. Windows and trees are instanced in the finished GLBs.

**Export and verification.** Simplification was dropping one triangle from some window panes. The city export
uses topology preserving Meshopt compression and checks that all 13,557 window instances per tier use complete
two-triangle panes. Two full rebuilds produced identical city GLBs, manifests and package reports. Low totals
**7.999 MB** and high **11.859 MB**, including the original kit scene, cast and `city.json`; both remain under the 8/12 MB limits after the plaque update. The package report is
`tools/city/build/budgets.json`. Browser triangle measurements count each submitted instance and peaked at 143,598 low and 318,849 high. The offline
The Chrome harness checks the five named walks, routes and attribution on the fake smoke server on port 8011.
Final night screenshots are under `tools/city/build/night-final/`; the retained kit-scene night view is
under `tools/city/build/night-legacy/`. The first visual pass, before fixing the moon's screen placement, is
under `tools/city/build/night-review/`. Matched day screenshots are under `tools/city/build/appearance-before/`
and `appearance-after/`. The approximate
kit reference angle is under `appearance-kit-angle/`. The headless recordings use SwiftShader and a desktop
or phone viewport. Real-phone performance still needs a hardware check.

### Controls

- **Desktop:** WASD/arrows walk, Shift run, Space jump, drag to look, wheel zoom, E to talk within 2 m, N name
  tags, C collision wireframe, F1 debug HUD, Escape closes chat or settings. Closing chat saves notes via
  `/player/end`.
- **Phone:** left-thumb joystick (push far to run), drag on the right to look, two-finger pinch to zoom, Jump
  button and a Talk button that appears near someone. Landscape is suggested. The chat panel stays above the
  on-screen keyboard (`visualViewport`).
- **Settings (gear):** quality, name tags, Street life, invert look, sensitivity; remembered in the browser.

### Quality

Touch or narrow screens start on **low**; desktops pick **medium** or **high** from the GPU's capabilities. Pixel
ratio caps: low 1, medium 1.5, high 2. Below 28 fps for a sustained period it steps down, at most twice (keeping
the loaded assets); choosing a preset reloads the matching asset set. Override with `?quality=low|medium|high`.

### What's in it

- The kit scene's Crooked Billet and Patel's News, exported from `Ancoats.blend`, with 44 collision
  hulls and 15 waypoints converted to three.js space (x, z, −y).
- Other logged-in players with a place set appear with their own names, using Rob’s player body and
  the existing waypoint walking. They have no portrait or E/touch talk prompt; player-to-player chat is
  not part of accounts v1. The 2D map likewise shows other named players, including on the street.
- Characters: nine individually built MakeHuman/MPFB models, with age/build morphs, textured faces,
  hair, beards where appropriate, and actual clothing meshes. MPFB 2.0.18 is a build-only Blender extension;
  all selected graphics are CC0. `build_cast_mpfb.py` defines the cast and exports metre/Y-up models.
  The MPFB game-engine rig uses an explicit UAL bone map and rest-pose calibration; `retarget_cast.py`
  bakes the same ten clip names. Only Rob and visible NPCs load in normal play; models are cached as they
  appear. Old Quaternius bodies and original clips load only after a model failure, listed in the debug HUD.
- Baked indirect lighting (Cycles, 128 samples, 2048 high / 1024 low atlas); night dims the bake and uses
  glowing windows and runtime lights.
- Assets including the MPFB cast and street life: **low 6.763 MB**, **high 10.962 MB**, including all nine models and
  fallback files; normal play loads a visible subset. Vendor modules add about 2.4 MB uncompressed.
  Per-character budgets are below; licences are in `evorium/static/world3d/assets/LICENSES.md`.
- Physics: capsule-and-octree walking with step-up, a 1.03 m jump, wall and closed-door blocking, and a camera
  that never clips through walls.
- NPCs follow `/world/scene` along a route graph (746 nodes, 4,697 verified edges; every waypoint reachable from
  both street ends), with slot offsets, sitting and talking poses, name cards and speech bubbles.

### Street life

Cosmetic and client-only: no simulation, `/world/scene`, player endpoint or model-call changes.
Each browser schedules independently using time spent in a visible tab. **Street life** in the
gear menu defaults on and is remembered as `evorium3d.street-life`; turning it off removes all
active events. `?ambient=off` overrides that setting and prevents ambient loading.

| Event | Timing and behaviour |
|---|---|
| Pigeons | 2–5 in daylight (`daylight >= 0.3`); procedural pecking, short walks and turns. The entire flock takes off/flaps away when Rob or an APC comes within 2.5 m, disappears after 3 s, and returns after 60–180 s. Removed at night. |
| Rubbish | One crisp packet, newspaper page or can every 120–240 s, from the windward street end. Gusts spin/skitter packets and paper; cans roll along the gutter with a quiet synthetic rattle after a user gesture. A doorway/bollard stop lasts 8–25 s, then it moves on; it fades at the route end or after 110 s of activity. |
| Cat | Every 300–600 s; walks across the street pavement and sometimes idles at the shop doorstep for 20–60 s. It never enters either interior. |
| Dog | Daylight only, every 600–900 s; trots, stops by the actual cast bollard near x=8.08 to sniff using its idle clip, then leaves. |
| Fox | Only `daylight < 0.3`, every 600–1200 s; slow walk on the outer pavement lane, looking around by the quiet street end, then leaves. The owner-approved model is a resized/recoloured wolf (§13). |

Animal motion uses the street subset of `data/routes.json`, with ground rays and extra sphere/
segment checks around props and kerbs. Separation steers or waits around Rob/APCs. Ambient
objects are never inserted into the player collision octree. Low permits **one event at a time**
(a flock counts as one event) and at most **2 pigeons**, medium two events / 4 pigeons, high five
events / 5 pigeons. Pigeons and newspaper print use instancing. Hidden tabs stop movement,
animation, timers and rendering; returning does not catch up missed events. Animal meshes load
only when needed, after the first street view and visible cast; a disabled client loads none.

Fixed screenshot URLs (on the fake server, port **8011**):
`/world3d?test=1&ambient=pigeons|rubbish|cat|dog|fox&quality=low|high`.
These select fixed close cameras, poses and day/night lighting; explicit test types override a
saved off setting. Add `&debris=paper|can` for the other rubbish forms. `ambient=fox` uses night;
the other types use day. `cam=ambient&ambient=off` gives the matching daytime performance baseline.
Normal play always uses the server's daylight. `?ambient=cat` without `test=1` does not force a spawn.

All three animal downloads total **232,548 bytes (0.233 MB)** per tier: cat 79,560 / dog 75,748 /
fox 77,240 bytes, **807 / 602 / 622 triangles**. Both tiers keep these already tiny meshes.
`data/budgets.json` records and enforces **1.2 MB low / 2.5 MB high** ambient limits plus the
existing **12 MB / 30 MB** whole-package limits. Total assets including all cast and fallbacks:
**6,759,074 bytes low / 10,957,998 bytes high**. No new runtime or build dependencies.

To rebuild just the ambient assets, retain
`~/Downloads/evorium-animals/Animal Pack Vol.2 by @Quaternius.zip`, then run:

```bash
blender -b --python-exit-code 1 -P tools/web3d/build_ambient.py
node tools/web3d/optimise_ambient.mjs
```

The builder extracts to ignored `tools/web3d/raw/animals/`, exports to `raw/ambient/`, and never
saves the supplied blends. It exports sampled Idle/Walking clips, metre scale, +Z forward and
coat vertex colours. Optimisation writes `assets/{low,high}/ambient/{cat,dog,fox}.glb` with
Meshopt, and converts any textures to WebP (128px low / 256px high); these models have none.
The full `optimise.sh` also includes ambient processing. Run the ambient builder before a full
optimisation on a fresh checkout. Source provenance is in the existing asset licence manifest.

### MPFB model budgets (measured)

| Character | Low MB | Low triangles | High MB | High triangles |
|---|---:|---:|---:|---:|
| Dez | 0.342 | 4,679 | 0.695 | 13,280 |
| Jess | 0.260 | 4,488 | 0.482 | 12,525 |
| Tommy | 0.352 | 5,237 | 0.750 | 14,607 |
| Raj | 0.313 | 4,598 | 0.618 | 12,991 |
| Chloe | 0.248 | 4,015 | 0.476 | 11,182 |
| Simon | 0.274 | 10,004 | 0.473 | 22,630 |
| Brenda | 0.272 | 6,330 | 0.453 | 14,348 |
| Mo | 0.338 | 6,714 | 0.668 | 18,973 |
| Rob | 0.277 | 4,706 | 0.514 | 12,260 |

Whole-package texture estimates including mipmaps, fallback textures and all nine models are
122.7 MB low / 504.4 MB high. These exclude
renderer buffers, geometry and JavaScript; normal-play allocation is lower because models/fallbacks
load lazily. Real iPhone memory remains unverified.

### Rebuilding the assets

Needs Blender 5.3 with MPFB 2.0.18 (verified headless), Node 24/npm, Python with Pillow, Chrome, both Quaternius **Standard** zips
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
blender -b --addons bl_ext.blender_org.mpfb --python-exit-code 1 -P tools/web3d/build_cast_mpfb.py
blender -b --python-exit-code 1 -P tools/web3d/retarget_cast.py
blender -b -P tools/web3d/bake_lighting.py
blender -b --python-exit-code 1 -P tools/web3d/build_ambient.py
bash tools/web3d/optimise.sh
```

- The scripts never save the kit's `.blend`. Folder names containing "unreal" inside the kit and the Quaternius
  pack are the packs' own names; leave them.
- `raw/blend_inventory.txt` and `raw/characters_inventory.txt` record what was exported and checked. A broken
  `_png.png` texture name in the pack is repaired from its matching PNG.
- `data/budgets.json` enforces whole-game download and per-person limits below; in-view geometry is checked by Chrome (150k low / 400k high).
- Three.js 0.187.0 ships no minified build: `three.module.min.js` is the unmodified module, plus its
  `three.core.js` sibling. `node_modules/` and `raw/` are git-ignored.

### Installing MPFB and its CC0 assets

Install through Blender's CLI, then confirm background loading:

```bash
blender --background --online-mode --command extension install mpfb --sync --enable
blender -b --addons bl_ext.blender_org.mpfb --python-expr "import bl_ext.blender_org.mpfb; print('MPFB loaded')"
```

The tested version is 2.0.18 (Blender Extensions, build 20261010, minimum Blender 4.2).
To reinstall that exact extension instead of the current repository release, download
`https://extensions.blender.org/download/sha256:c075b3e9b94b8e5556a5f03f4653602d02ea306de08126e8f55ed6dee28a2dad/add-on-mpfb-v2.0.18.zip`
and run `blender -b --command extension install-file --repo blender_org --enable /absolute/path/to/add-on-mpfb-v2.0.18.zip`.
Its SHA-256 is `c075b3e9b94b8e5556a5f03f4653602d02ea306de08126e8f55ed6dee28a2dad`.
For reproducible rebuilds retain that version; a fresh CLI install may select a later release.
Official source: https://extensions.blender.org/add-ons/mpfb/ . Download the following packs
into ignored `tools/web3d/raw/mpfb/` from the official secondary mirror (the primary was slow):

- https://files.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip
- https://files.makehumancommunity.org/asset_packs/hair01/hair01_cc0.zip
- https://files.makehumancommunity.org/asset_packs/bodyparts05/bodyparts05_cc0.zip

Install each downloaded zip using the headless operator (replace the filename):

```bash
blender -b --addons bl_ext.blender_org.mpfb --python-expr "import bpy; bpy.ops.mpfb.load_pack(filepath='/absolute/path/to/pack.zip')"
```

MPFB resolves its user data folder with `LocationService.get_user_data()`; on this machine it is
`~/.config/blender/5.3/extensions/.user/blender_org/mpfb/data/`. Keep that separate from the
extension's source `data/` folder. CC0 pack tables and individual selected assets are listed in
`evorium/static/world3d/assets/LICENSES.md`. MPFB's code is GPL, its core graphics are CC0;
the extension is not included in game downloads.

To tweak a person, edit the `CAST` dictionary at the top of `tools/web3d/build_cast_mpfb.py`:
name, age, gender macro, weight, muscle, proportions, race mix, height in metres, skin, hair,
beard and clothing. Brenda's fitted hair is rebuilt as opaque low-poly curls; Dez's beard is projected toward
the face for stubble, and Tommy's top hair is removed for his receding style. Run the cast builder, `retarget_cast.py`, then `optimise.sh` as above.
`--only dez` supports a diagnostic single-character build; run the full builder before a release
so the complete inventory and licence manifest are regenerated. Intermediates are in `raw/cast/`.
The explicit mapping is `tools/web3d/data/mpfb_to_ual_bones.json`; animation inventory is in
`raw/cast/retarget_inventory.json`. Rest translation channels are stripped except pelvis bob/sit;
the browser rebases that channel to each model's pelvis. Grounded clips use a sole-vertex correction to
avoid retargeting penetration; airborne clips keep their pose. Ten shared clip names stay unchanged.

Per-character limits: low **0.7 MB / 12k triangles / 512px textures**, high **1.6 MB / 25k / 1024px**.
The optimizer fails on those limits or total downloads above **12 MB low / 30 MB high**,
including fallback files. `budgets.json` records per-character sizes/triangles and texture estimates.

### Checks

`bash tools/web3d/run_checks.sh` starts its own smoke server, then drives Chrome over the DevTools protocol:
20 screenshots (street, pub, shop, cast, player × low/high × 1280×720 and 390×844) to `tools/web3d/raw/screens/`
with JSON reports, plus 16 ambient captures (desktop high / phone low: off, pigeons, three rubbish forms, cat, dog and night fox), plus a scripted walk through both doors, jump, closed doors, camera collision, fake chat
and a 60× routine change. Blank images fail. `--movement-only` and `--screens-only` run parts. Test URLs:
`/world3d?test=1&cam=street|pub|shop|cast|player&quality=low|high` (fixed camera and time; exposes
`__evoriumReady` and `__evoriumReport`). Player-writing checks refuse any server that isn't the fake one.
Ambient reports/captures are in `raw/screens/ambient/`; the harness checks scale, grounding, actual walk-bone changes, day/night removal, hidden-time pause, saved toggle, lazy loading, quality caps and pigeon scatter/player passage, and measures 30 rendered frames against ambient-off. `node tools/web3d/ambient_checks.mjs --one=cat` reruns one type while the fake server is running. The cast-specific captures are `--cast` (nine-person lineup and all head close-ups, desktop/phone low/high)
and `--poses` (Dez/Tommy/Brenda idle, walk, run, jump, sit and talk on desktop low). Use
`?test=1&cam=lineup`, or `cam=head|body&character=dez|jess|tommy|raj|chloe|simon|brenda|mo|player`,
with optional `pose=walk` and `frame=0.5`. These studio-only views deliberately load all nine models.

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
`hello@example.com`. The game server serves it at `/` with no login (`main.py`: `/`, `/styles.css`, `/images/`), so pushing to `main`
publishes it through the G4's auto-update. Its Play buttons (nav and hero) link to `/game`. Personal contact details remain deferred. A **"What's new"** section (nav link "What's new", before the waitlist) lists
features newest first; see rule 12 in §15. The characters
section is **"Meet the APCs"** (nav label "The APCs"), and the hero and share descriptions use "APC".

**Briefing website changes** (the old `CODEX_PROMPT_WEBSITE.md`, merged here and deleted 20 Nov): describe it as
a Three.js browser game for desktop and phone; plain HTML/CSS with at most ~30 lines of JS; no frameworks or
build step; no "Home" link; no forms collecting data; fictional characters only; images as optimised WebP/JPG
with `<picture>`, lazy loading and alt text; accessible and responsive at 375, 768 and 1440 px. Colours:
`--ink #0D0E11`, `--ink-2 #16181D`, `--brick #8E3B2C`, `--billet #1E3A32`, `--amber #E8A548`, `--cream #EFE7D6`,
`--mist #9AA0A8`. Image style: cinematic 35mm film still of Manchester at dusk, warm pub light against cool
streets, film grain, matching the game's portraits.

---

## 9. Known issues and open questions

- **Ancoats city (25 Nov):** `/world3d` now defaults to Blossom, Henry, Hood, Jersey and Murray streets;
  `?city=0` keeps the original kit scene available. Night is moonlit and stars clear with weather, with 74 city lamps
  using emissive heads and ground pools, plus two kit-scene lamps with warm heads and pools (real lights
  only on medium/high). Final desktop/phone low/high captures are in `tools/city/build/night-final/`; the legacy
  pub-open night capture is in `tools/city/build/night-legacy/`. Visible triangles stayed below 150k/400k.
  Five city walks, city route connectivity/physics/weather/chat and the daytime legacy movement check pass.
  Owner review and physical phone performance remain outstanding.

- **Ancoats review build (24 Nov):** terrain and most heights use EA LiDAR. The street is still made from
  repeating facade bays. Ground floor interiors and individually modelled storefronts belong to the original
  original kit scene. Mill windows use segmental lintels over rectangular panes. Low quality omits deep
  recesses and the full sash detail. The ambient shading is a local vertex bake. The canal edge and detailed
  side path and scheduled NPC coverage remain open. The phone FPS gate needs a physical device.

- **Realism limits (23 Nov):** the fixed holiday table ends in 2027 and festive events are for Christmas 2026.
  Weather is cached model output for Ancoats, not a street rain sensor; outages older than six hours give no
  effects. Fast/offset clocks use the labelled last real reading. Raffle draws missed until a later date have
  no invented winner. Bad-day/late-pub records begin when this version runs; earlier unrecorded visits cannot
  be reconstructed. Real-phone weather performance is unverified.

- **Police report wording (23 Nov):** Python uses conservative named-actor threat/harm patterns, so unusual
  paraphrases or pronoun-only reports can be missed. It does not decide truth or impose barring. Follow-up
  requires the normal auto mode and public routine overlap; disconnected players still retain their last
  `player_place` as in accounts v1. The local checkout predates the 20 Nov report, so historical back-fill is
  tested with a dated report fixture, not against the G4 world. The saved transcript confirms the incident.

- **`talk` promises are loose (23 Nov):** any later conversation between the two people counts as keeping a `talk`
  promise, whether or not they discussed the promised subject. Matching the subject would need the conversation
  summary or facts to be checked.

- **Web3D rebuild preflight (21 Nov):** Blender 5.3, npm registry access and both intact CC0 Standard
  character zips pass. The documented kit path is absent in this session and `/media/user` is empty;
  exporting/rebaking is blocked until the kit is mounted and visible here. Existing shipped assets remain available.
- **Repository credential audit (21 Nov):** downloaded GitHub branch/tag history (35 commits, only `main`,
  tip `e7404e6`) and scanned tracked text blobs for provider tokens, private keys, credential assignments and
  credential-bearing URLs; compared the local API key against historical blobs without displaying it. No real
  API key/private key detected or exact local-key match. The approved cleanup has been published and
  GitHub’s only branch was rewritten: 33 of 36 commits changed, with no removed connection values or
  authentication prose remaining in reachable historical documentation. GitHub reports no secret-scanning
  alerts, forks or pull requests. An old unreferenced commit was confirmed retrievable through GitHub’s
  API after the rewrite; eligible object/cache purges require GitHub Support. Downloaded copies cannot be erased remotely. No live credentials were rotated.
  The G4 was unreachable through existing trusted SSH, so its checkout alignment remains outstanding (§6).

- **Street life art limits:** the fox is the owner-approved small recoloured wolf, retaining its wolf
  silhouette and walk/idle clips. The fox uses the quiet street end rather than a separate bin area. Cat doorstep rests, dog sniffing and fox look-arounds use idle clips
  and small root turns; there is no dedicated sit/sniff animation. No windowsill jump or shop-interior
  visit. The can's quiet procedural rattle is subject to browser audio/gesture support and has not
  been checked by listening on physical speakers. Real-phone FPS and memory still need hardware.
- **Accounts v1 limits:** each named login has its own player, but every account still sees the full god
  view and can use owner controls. There is no self-service sign-up, role separation, logout/session UI
  or player-to-player chat. Passwords remain only in private config; separate player permissions and
  stronger account management are future work (§11). Presence persists until Leave or a place change;
  browser disconnects do not automatically remove a player.
- **Barring isn't enforced.** A character can say the player is barred, but nothing stops them walking back in,
  and a later greeting may be friendly. Needs an action (e.g. `bar_customer` for Dez and Jess) that the player
  endpoints respect. **On hold (owner, 19 Nov)** while the owner tests by provoking characters; when built,
  include a testing override (an unbar button or switch).
- **Serious incidents barely move relationships.** Feelings are capped at ±2 (×2), so threats of violence cost
  only −4. Consider down to −5 (×2 = −10) for threats and violence.
- **The quiz loops.** "Forty by Sunday" was restated in 4 conversations before promises were recorded; check it
  stops now that promises save.
- **3D polish:** MPFB models are stylised low-poly interpretations rather than exact portrait likenesses; some garments are the nearest CC0 shirt/jacket styles and Brenda's curls remain faceted; no facial/lip animation. NPC catch-up snaps rather than
  fading and departures vanish at the route end; NPCs can overlap while walking; speech bubbles near the screen
  edge get cut off; shared lightmap gives small props little detail; no separate night bake or bloom.
- **Not yet tested on a real phone**, especially iPhone memory, keyboard and touch. The city smoke captures use
  SwiftShader; their FPS values do not predict physical-phone performance.
- **Quiet places can now stay silent:** automatic pairs stop at two chats per game day, even if nobody else
  is around. All eighteen APCs have at least three hours of shared free time in a normal sampled week.
- **Director heuristics** are conservative word checks; since M4 it also rejects any digit and words such as set,
  pay, close and sign, so many of its ideas get dropped.
- **A failed reaction call is used up**; the "offer nearly due" reminder three days before expiry gives another
  chance.
- **M4 simplifications:** fixed two-hour reaction delay (sixteen hours to reconsider); the flat viewing and the
  outside job are small Python templates; pub income is an illustrative model, not accounting.
- **The ten new APCs have no 3D models yet:** in `/world3d` they borrow Rob's body (the cast lookup's default)
  until MPFB models are built for them. Dashboard, map and conversations are fine.
- **Some facts are stored twice** (5 in the 20 Nov copy, e.g. "Dez chose to wait" noted in two conversations).
  Harmless; a de-duplication on insert would tidy it.
- **Topic repetition can still happen:** the two-chat automatic pair cap limits loops but does not guarantee
  fresh dialogue each day. Unsupported research promises remain uncheckable.
- **Unsupported promises:** research ("I'll look up Companies House"), general making, off-ledger payments, loan
  repayment and unverifiable conditions have no deterministic evidence. The local fix makes these vague and
  lapses them neutrally; a real research/repayment action remains future work. New conversations can still
  make similar promises, so this does not by itself solve same-pair topic loops.
- **Promises the game can't check (23 Nov):** only Tommy can write quiz questions, so Dez promising to "write a few
  myself" becomes `vague` and lapses without blame. APCs can promise things the action menu doesn't let them do;
  either widen the actions or stop such promises.
- **Restated promises already extended on the G4:** before the fixed-promise rule, 13 promises were restated and
  some got later deadlines (Peggy's to Rob moved from 16:21 on 23 Nov to 26 Nov). The original deadlines weren't
  stored, so they can't be restored in general.
- **APC self-certification fixed locally (23 Nov), awaiting owner review/deployment.** Deadline checks no longer
  ask the model, extraction reports become claims, and plan fulfilment must match real evidence. Migration 15
  uses `lapsed_at`, preserving the original table, status CHECK and plan foreign keys. All active views exclude
  lapsed promises; history and catch-up describe the lapse. Legacy promises cannot be retrospectively typed
  safely, so they lapse without penalties. Watch live promise behaviour after deployment rather than assuming
  prompt compliance from offline tests; no real model calls were used for this change.
- **Spoken decisions need live observation:** filled examples, copied-example rejection and quote attribution
  are tested offline, but the latest G4 action rows could not be checked without its missing backup copy.
- **Old trivia still visible** until `python -m evorium.rescore --apply` is run once.
- **Restart button** requires authentication when access control is enabled (as configured on the G4).
- **Spend recorded before 19 Nov is overstated** by about $0.09 (old pricing).
- **Security to-dos:** review the G4 access controls.
- **Full pytest run in this sandbox timed out** at 120 seconds on 25 Nov 2026 without output; the suite normally
  completes in about nine seconds. The migration test file passes alone (2 tests). A combined targeted run of
  that file and `test_auth.py` did not return a summary. Do not retry the full run here; the owner reviewer should
  run it.

---

## 10. Next steps

- **Realism pack Parts 1–5 are locally implemented (23 Nov).** Parts 1–4 add routine overlap/fairness,
  automatic pair caps and copied-decision rejection, weather, holidays/festive events/payday and deterministic
  setbacks. Part 5 retains migration 16 and Grace's case follow-ups. Review and commit/push normally after the
  final checks; no commit or deployment was made here. After normal backup/deployment, verify the actual Dez
  report back-fills to the owner's Rob case, watch spoken actions and weather freshness, and check on a real
  phone. Existing uncommitted acquaintance/job-context changes were preserved. Money/bank accounts remain
  deferred. Extend holiday/festive tables before later seasons.

- **Promise evidence is deployed (23 Nov).** Keep watching real kept/broken/lapsed results and false claims with
  the read-only promise report; unsupported research/repayment needs real actions before it can be checked.

- **Ancoats city and night lighting are ready for owner review (25 Nov).** The five-street city is now the normal
  `/world3d` map; `?city=0` retains the original kit scene. Inspect `tools/city/build/night-final/`, then check night,
  kit-scene lighting and performance on a physical phone before deployment. Low city build is 7.999 MB of
  its 8 MB limit, including the Henry Street plaque texture.

- Align the G4 checkout with the rewritten history using §6 so automatic updates resume. Review its
  access controls. Request an eligible old-object/cache
  purge through GitHub Support; do not merge old clones back into the cleaned history. Make the kit
  visible to this session before restarting Web3D rebuild stages.

1. **Build MPFB 3D models for the ten new APCs** (Peggy, Liam, Anjali, Pete, Hannah, Gary, Kirsty, Grace, Barry,
   Ronnie) with the existing
   `build_cast_mpfb.py` pipeline, and give them waypoints and poses. Then watch whether Brenda, Chloe and Mo now
   join conversations (they had 0, 0 and 2 before the routine changes).
2. **Play and review the MPFB cast** on desktop and a real phone; refine likenesses, seated poses, bubbles at
   the screen edge, NPC overlap and fades; review street life and its quiet can rattle on real hardware.
2. **Watch the story run** on the G4 for a few days: decisions, promises now being recorded, and Northgate coming
   to a head on 17–18 Dec. Review the pacing and the settlement constants.
3. **Build on accounts v1** (§11): separate player/admin views and permissions, hide APC reasoning from
   players, add sign-up/session management and per-player spending controls. Named players, separate
   memories, relationships, promises and catch-up are implemented locally; deploy only after review.
4. **Fix the scaling limits** before many players (§11 hosting notes): parallel conversations, SQLite WAL, a
   cached scene snapshot.
5. **Barring and bigger relationship swings** once the owner has finished provoking-tests.
6. **An inspector:** free Python health checks (no promises today, loops, no decisions, failure spikes, cost) plus
   one cheap daily AI review that reports, never fixes.
7. Install the friend's eight new portraits (add `simon.png`, `brenda.png`, `mo.png` and register them in the
   `portraits` map in `index.html`); decide on daytime pub visitors; run `evorium.rescore --apply` once.
8. Then a small online test with 5–10 friends, before planning for large numbers.

### Plan: real Manchester streets (city pipeline, implementation in progress 24 Nov)

**Goal:** a walkable replica of about five real Ancoats streets, built by **Python scripts from open data**, not
modelled by hand and not invented by AI. Codex writes and fixes the scripts; the scripts make the city; the
owner looks at screenshots at each gate. Same inputs always give the same city, so areas stay fixed once built.

**Status (25 Nov):** the five-street Ancoats city is the normal `/world3d` map and uses EA LiDAR for terrain and
154 building heights, the owner's kit textures and instanced facades, and Kenney CC0 trees. Night includes
working city and kit-scene lamp pools, moonlight and weather-aware stars. Rebuild and provenance are in §7.
Package and sampled triangle targets pass. The owner visual review and real-phone performance gate remain open.

**How the work is split**

| Who | Does what |
|---|---|
| Python scripts | Download and snapshot the data, work out heights, generate every building, road and prop, export the game files, measure size and triangles |
| Codex | Writes the scripts in small parts, one part per job, with tests |
| Claude | Reviews each part before it's pushed; writes the next part's prompt |
| Owner | Picks the area, judges the screenshots at each gate, decides go/no-go |
| By hand (optional, later) | A few landmark overrides (the mills, the canal edge) |

**Decided defaults** (change before Part 1 if wanted)
- Area: about 400 × 300 m around Cutting Room Square, Ancoats (roughly Blossom St, Henry St, Hood St, Jersey St,
  Murray St). Part 1 prints a labelled preview so the owner confirms the exact box before anything is built.
- The Billet and Patel's News remain fictional businesses; they sit on the real Henry Street, Ancoats.
- Real geography, **fictional businesses**: no real shop names or signs, and no APC lives at a real house number.
- Lighting: real-time lights plus a cheap baked shadow (ambient occlusion), not one big baked lightmap, so size stays
  close to today's (target ≤ 12 MB high, ≤ 8 MB low for the whole five-street area, loaded at once; chunk
  loading only beyond ~10–15 streets).
- Build tools stay off the server: scripts and their own `tools/city/requirements.txt` (geopandas, shapely, pyproj,
  rasterio, numpy, trimesh, pygltflib, osmium or pyrosm) run on the main PC. The G4 only receives the finished
  `.glb`/`.json` files, so the app's `requirements.txt` and auto-update are untouched.

**Data (all free, licensed for this)**
- OpenStreetMap (Overpass snapshot pinned by SHA-256 and clipped to the box): roads, pavements, building
  footprints, shops, trees, water, land use. ODbL: the game must show "© OpenStreetMap contributors".
- Environment Agency LiDAR (1 m surface and terrain models, Open Government Licence): real building heights
  (surface minus ground inside each footprint) and the ground level.
- Ordnance Survey open data (OGL) as a cross-check. Textures and props: ambientCG, Poly Haven, Kenney,
  Quaternius (CC0). Never Google 3D Tiles (licence forbids it).

**Layout:** `tools/city/` (scripts, `config.yaml` with the area box, origin and seed), `tools/city/raw/` and
`tools/city/build/` (git-ignored), outputs to `evorium/static/world3d/assets/{low,high}/city*.glb` and
`evorium/static/world3d/data/city.json`. One command rebuilds everything: `python tools/city/build.py`.

**Parts** (one Codex job each; review before the next)

| Part | Script output | Check / gate |
|---|---|---|
| 1. Data snapshot | Clipped OSM + LiDAR for the box, cleaned GeoJSON in local metres (British National Grid, local origin), a manifest with dates and hashes | Labelled preview PNG of streets and buildings; counts; owner confirms the area |
| 2. Heights and types | Each building gets a height (LiDAR, else OSM levels × 3.2 m, else a type default), a type (terrace, mill/warehouse, modern flats, shop, other) and a roof type | Report of how many heights came from each source; coloured preview PNG |
| 3. Grey-box | Walkable plain-box buildings, roads, pavements with kerbs, ground, collision file; a dev-only test page behind the login | **Gate 1:** owner walks it on PC and phone; download size, triangles, frame rate reported. Go/no-go |
| 4. Facades | Per-type facade rules: floors, window bays, doors facing the road, shopfronts where OSM has a shop, sills, lintels, parapets, chimneys; shared texture sheets; windows as instances; seed from each OSM id | Screenshots per building type; size within budget |
| 5. Street dressing | Lamp posts, bins, bollards, benches, road markings, OSM trees and street trees, the canal if in the box | Screenshots day and night; triangle budget |
| 6. Lighting and speed | Ambient-occlusion bake, night window glow, compressed textures, budgets in `budgets.json`, low/high versions | **Gate 2:** phone test at 30 fps or better |
| 7. Into the game | Navigation mesh from pavements replacing the 746-node graph and its slow A*, the fictional pub and shop kit placed in the area, waypoints and collisions joined up, APCs walking real streets | All existing 3D tests pass; APCs reach every place from every street end |
| 8. Landmarks (optional) | `landmarks.yaml` overrides: exact heights, materials or a hand-made model for chosen buildings | Owner's choice, ongoing |

**Not in this plan:** the simulation. APCs stay place-based (the 3D only shows them). A separate, smaller job
should first replace the hard-coded places with a places table (id, type, position, opening hours, interior),
which the arcade also needs; travel between places in real time comes after Part 7.

**Effort:** roughly 2–3 weeks of Codex sessions for Parts 1–7, with reviews in between. Parts 1–3 (about 2–4
sessions) are the cheap test of whether it's worth going on.

**Next steps:** review the screenshots under `tools/city/build/appearance-after/` and play the city on a real phone.
Review the remaining art and detailed route coverage (§9).

---

## 11. Plan: Evorium online (multiplayer)

> Status: **hosting done (§6); accounts v1 implemented locally, awaiting owner review/deployment.**
> Named trusted logins each have a player; separate player permissions, self-service sign-up and the key
> pool are not built. Decisions recorded here are the owner’s.

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

### Only real characters

Everyone you see is an APC with a real life in the simulation: no background crowds, passers-by or non-AI
extras (owner's rule, 20 Nov). To make the world busier, add APCs and give them richer routines.

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
  3. **Accounts v1 now has one player per login.** Public-player permissions and account management remain.
  4. **A single uvicorn process** with the tick thread and in-memory state; fine at first.
  5. **`/world/scene` polled every 1.5 s per player:** build it once per tick and serve the cached copy.
- **Bandwidth:** 3–8 MB of 3D assets per new player; put a CDN (e.g. Cloudflare) in front of static files later.
- **Cost driver:** DeepSeek, not the server.
- **Cast size:** grow slowly (12–20 well-written neighbours) rather than 100 generic NPCs.

### What has to be built

| Area | Work |
|---|---|
| Accounts | v1 done: named Basic logins, original owner compatibility, one player per account, separate history/checkpoints; next: self-service sign-up, sessions and roles |
| Profiles | Name, picture (preset avatars first; uploads need moderation) |
| Player view vs admin view | Players see the world, their own chats, what they've learned, their standing. Owner keeps the god view; restart, speed, director and auto become admin-only |
| Multi-player conversations | Several players talking to different NPCs at once |
| Key pool | Encrypted storage, rotation, fair share, per-player caps, fallback when a key fails |
| Moderation | Rate limits, report button, account bans, upload filtering |
| Legal | Privacy policy and terms (UK GDPR: emails, keys, chat logs), age limit |

Suggested order: review and deploy accounts v1 for trusted friends, build the separate player view, then
the key pool and open sign-ups.

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

- **Street animals:** Quaternius's *Animal Pack Vol.2 by @Quaternius.zip*, supplied by the owner,
  CC0-1.0 according to the creator's OpenGameArt upload:
  https://opengameart.org/content/animated-animales-low-poly . Uses `Cat.blend`, `Dog.blend` and
  `Wolf.blend` with their original Idle/Walking clips. The archive has no separate licence text;
  source declaration, creator announcement and archive SHA-256 are recorded in the existing
  `assets/LICENSES.md`. On 20 November the owner explicitly approved the wolf as the fox substitute
  because the official fox file remained quota-blocked. It is 0.48 m tall, fox-orange with a white
  chest/tail tip and dark legs. Cat height is 0.40 m including its raised tail; dog height 0.56 m.
  Coat colours are per-face vertex colours. Pigeons and all three rubbish forms are original
  procedural geometry. No new external imagery, sounds or runtime dependencies.

- **Current 3D cast:** MakeHuman/MPFB 2.0.18, scripted from `tools/web3d/build_cast_mpfb.py`,
  with game-ready male1591/female1605 proxies, CC0 system skins/eyes/brows/lashes/garments,
  CC0 hair01 hairstyles and the CC0 bodyparts05 beard. Hair and clothing colours are explicit.
  Balding hair is edited in geometry; Tommy's checked shirt is generated procedurally.
  Real meshes replace runtime body tint masks (those remain only on fallback bodies).
  See §7 for installation/rebuilding and the adjacent asset licence manifest for every source.
  The portraits and website images were viewed as references; website files were not changed.


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
    Kowalska, Rory Campbell, Val Mercer) have an idle pose only and aren't used; the game now uses scripted MPFB models of Evorium's cast instead.
- **Voice** (speech in and out) remains a later goal.

---

## 14. History

### 25 November 2026 — Shuttle Street renamed Henry Street

- **What:** renamed the real street throughout the current world to Henry Street, Ancoats while keeping the
  Crooked Billet and Patel's News fictional. Migration 17 updates stored place values and APC-readable saved
  text in place, including facts, memories, goals, plans, events, relationship notes, offers and cases. Past
  conversation messages and timeline rows remain unchanged. New-world seed text and the kit street plaque now
  read Henry Street; `?city=0` remains the original kit-scene selector.
- **Why / learned:** the OSM city places the fictional kit on Henry Street, so the game should use the real
  street name without claiming its businesses are real. The visible plaque is geometry in the exported GLB; a
  small texture overlay updates it without rebuilding the kit or editing `Ancoats.blend`.
- **Checks:** migration test 2/2; all five Node files passed; one desktop/high street-sign capture is at
  `tools/web3d/raw/henry-sign-review/desktop-high-street-sign.png` and the in-view count is 139,689. The full
  full pytest run timed out at 120 seconds with no output; the combined migration/auth targeted run also did not
  return a summary, while the migration file alone passed 2/2. Per the owner's instruction the full suite was not
  retried. Low/high
  city packages are 7,998,657/11,859,465 bytes and remain within budget. No push.


### 25 November 2026 — Map credits moved off the game screen

- **What:** at the owner's request, the OpenStreetMap / Environment Agency credit no longer sits over the 3D game.
  The same credit now appears at the bottom of the ⚙ settings panel in `/world3d`, at the end of the guide, and in
  the website footer, which still meets the ODbL and OGL attribution terms. `tests/city_opt_in.test.mjs` checks all
  three and that no badge is drawn over the game. Python 401 and Node 13 tests pass.

### 25 November 2026 — Ancoats city becomes the normal map; night lighting

- **What:** made `/world3d` open the five generated Ancoats streets by default, retaining Shuttle Street at
  `?city=0` and preserving the old street for test pages unless `?city=1` is set. City lamp heads now sit atop
  their 4.3 m posts; the manifest lists all 74 head positions for emissive glow, ground pools and nearby
  medium/high PointLights. Added moon phase and weather-aware stars, brighter moonlit ambient, and updated the
  Shuttle Street's two kit lamp posts with amber heads, pools and medium/high PointLights; raised the open-pub
  window glow while the closed shop stays dark. Updated the browser title, guide, website description and dated
  What's new entry.
- **Why / learned:** the first night build had lamp heads at ground level and no sky or road light. Visual
  captures showed the city is readable at night, with window glow, lamp pools, moon and stars. The exported
  Shuttle Street mesh has two tall lamp posts but no separate lamp-head meshes; added aligned warm heads and
  pools at their measured fixture positions. The Chrome physics probe also needed to transform its old
  Shuttle Street test coordinates into the translated/rotated city scene.
- **Checks:** 401 project Python tests, 18 city tests, all Node tests (including moon phase/weather clarity and
  the 74-lamp manifest), desktop/phone low/high screenshots on Jersey, Murray and Blossom, five successful
  named-street walks, city route/physics checks, and daytime Shuttle Street movement plus night captures. Low/high
  packages remain 6.759/10.958 MB for the base assets and 7.995/11.856 MB for the city build; visible triangles remain under
  150k/400k. The owner review and real-phone performance check remain open. No push or live server change.

### 25 November 2026 — G4 hardening: Evorium cut off from the home network

- **What:** the owner hardened the G4, which also hosts business data under a separate admin account. Already
  done by the owner: Docker and spare firewall rules removed, SSH/RDP limited to the main PC, UPnP off, `newuser`
  out of the sudo group, `/home/userai` at 700. This session: reviewed the remaining sudo rule and added systemd
  network restrictions (§6) so Evorium, its updater and its backup can't reach the LAN, while internet access
  (DeepSeek, Open-Meteo, GitHub, PyPI) and Cloudflare keep working. Verified `active` after restart.
- **Sudo rule findings:** only `deploy/auto_update.sh` uses it (restart after an update and on rollback); the
  dashboard Restart button uses `os.execv` and needs no privileges. Low escalation risk (one fixed command,
  service runs as `newuser`). Safer replacement planned: the updater stops the game's main PID (owned by
  `newuser`) and systemd's `Restart=always` brings it back, then the sudoers file is deleted.
- **Next hardening, not done yet:** move the database and log to a data folder and make the code read-only to the
  game (`ProtectSystem=strict`, `ProtectHome=tmpfs`, bind mounts); standard systemd protections; memory/CPU limits;
  Cloudflare Access in front of `/game`.

### 24 November 2026 — Shuttle Street materials across Ancoats

- Rebuilt the city with 2022 EA first-return LiDAR, WebP maps from the kit, complete instanced sash panes,
  roof profiles, kerbs, vertex ambient shading and Kenney CC0 trees. Added repeatable LiDAR and tree fetch steps.
- In a reproduction with the old exporter, welding retained all 34,232 glass triangles. Enabling simplification
  reduced the count to 15,404. The new topology preserving export validates both triangles on every pane.
- Verified repeatable builds, 401 app tests, 17 city tests, Node checks and the five named city walks.
  Package sizes and matched screenshots are in §7. Hardware performance and remaining art are in §9.


### 24 November 2026 — Real Ancoats review build

- Built the pinned Cutting Room Square snapshot, placed Shuttle Street on Henry Street and excluded overlaps.
  Removed the Overpass attic date clause after it caused resource failures. The EA WCS attempt returned 404.
- Reduced road geometry, split the low render mesh into spatial cells, and kept export inputs for deterministic
  rebuilds. Joined the compact graph and city collision to the existing street scene. Kept city-only
  build tests out of the G4 updater's app test collection.
- Project Python suite passed 401 tests. City Python suite passed 16 tests. Node checks passed.
  Browser walking, asset and performance evidence is recorded in §7.

### 24 November 2026 — City pipeline implementation started

- **What:** created the `city-pipeline` branch with build schemas/config, dated OSM fetch and manifest hashing,
  OSM-based building types and LiDAR/levels/default height selection, deterministic geometry/facades/props,
  Meshopt export and size/triangle gates, navmesh/client integration under `?city=1`, and an empty
  `landmarks.yaml` override file. No simulation, app runtime dependency, live data or G4 setting changed.
- **Checks:** 23 focused Python city tests; compileall; city opt-in, Web3D, navigation and map Node checks pass.
- **Not built:** no real OSM/LiDAR snapshot or city GLBs because `pyproj`, Shapely and rasterio are absent here.
  Real counts, budget measurements on the five-street input, screenshots, Chrome in-view triangles and phone FPS
  remain outstanding. No assets were added to the website or static output.

### 24 November 2026 — Ancoats area corrected; real fetch blocked

- **What:** corrected the BNG box and local origin to cover the intended area around Cutting Room Square, updated
  the offline OSM fixture to that location, and added a second Overpass endpoint fallback. Installed the isolated
  city build environment. A live refresh failed at both endpoints (502/504); removed the stale raw snapshot and
  preview from the earlier incorrect bbox so they cannot be reused accidentally. No city assets were generated.
- **Why / learned:** the first bbox was southwest of the requested streets. Location checking identified the
  correct center; the public Overpass services were unavailable during the dated fetch attempt, so real counts and
  the real-area build remain unverified.
- **Checks:** 23 focused Python city tests passed, as did city opt-in, Web3D, navigation and map Node checks.

### 24 November 2026 — Plan: real Manchester streets built by scripts

- **What:** planned a script-driven pipeline to build about five real Ancoats streets from OpenStreetMap and
  Environment Agency LiDAR, in eight parts with two go/no-go gates (§10, "Plan: real Manchester streets").
  Discussed first: it's viable; five streets fit in one download at about today's size; procedural buildings look
  like a convincing city game, not photoreal; the simulation should stay place-based, with a places table first.
- **Nothing built yet.** No code changed.

### 23 November 2026 — Website at `/`, game at `/game`

- **What:** the existing `website/` is now served by the game server at `/` with no login (only `/`,
  `/styles.css` and `/images/…` skip the login check); the dashboard moved from `/` to `/game`. The
  website gained Play buttons (nav, mobile nav, hero) linking to `/game`, plus a "What's new" entry. The
  wordmark links on the game pages and the burger menu's Dashboard/Map now point to `/game`. No new
  dependency or server; the Cloudflare Tunnel still points to `localhost:8000`.
- **Checks:** 394 Python tests and the Node nav/map/3D tests pass. New test: the website and its assets are
  public, `/images/../` can't escape, and `/game`, `/world3d`, `/guide`, the API and `/static/` still need a
  login. Offline smoke server: all 57 website images, `/game`, `/world3d`, timeline, guide, API and a
  conversation run returned 200. The live G4 was not touched; it picks this up through auto-update.
- **Note:** old bookmarks of `/#map` or `/` now land on the website; use `/game`.

### 23 November 2026 — Public access moved from ngrok to Cloudflare Tunnel

- **What:** ngrok hit its free limit. The owner set up a token-based Cloudflare Tunnel (`cloudflared` service),
  then on the G4 removed the `evorium-ngrok` unit and the ngrok snap, deleted the temporary ufw rules that
  opened port 8000 to the two home subnets, and put the `evorium` service back on `--host 127.0.0.1`
  (verified: listening on 127.0.0.1:8000; `evorium` and `cloudflared` active, `evorium-ngrok` inactive).
- **Why:** the tunnel reaches the game through localhost, so LAN access is no longer needed; the game is
  reachable only through Cloudflare. `http://<server-address>:8000` from the home network no longer works.
- **Docs:** §2, §6 (services, everyday commands, setup step 6) and §9 updated; the install script's messages
  now point to Cloudflare. The old ngrok-token security to-do is gone with ngrok.

### 23 November 2026 — Realism pack complete: integrated review and verification

- Owner authorised proceeding through all four parts without stopping after the full brief review. All four
  are implemented alongside Part 5. Existing acquaintance/job-context edits were preserved; no commit/push.
- Tightened the week audit to check every minute of each complete 30-minute shared slot. This caught short
  encounters that an instant sample over-counted. Gary now visits Mon/Wed 14–17; Grace has longer Mon/Wed/Fri
  morning community stops and full Tuesday/Thursday half-hour pauses. Whole-slot shared hours are: Dez 3.5,
  Jess 3.5, Simon 4, Anjali 3, Grace 4, Gary 4, Barry 5; everyone else also reaches at least 3 hours.
- Final integration: optional rainy street pauses shelter, the planner displays holiday hours, Dez's sick-shift
  coverage renders behind the bar on both maps, and weather particles reduce when the performance watchdog
  lowers quality. A missing past raffle draw no longer claims there was nobody there: it records a missed
  draw without inventing past attendance. No promise-evidence, seed-list or schema changes were needed.
- **393 Python tests pass**, including **35 focused Parts 1–4 tests**, the pre-existing acquaintance-context
  test, Grace's case regressions and a new API integration check for weather/calendar/private condition data.
  Every part had full-suite/Node checks and a fake-model copied-world Chrome smoke run; all 20 final desktop/
  phone screenshots, physics/movement/chat, weather/festive-light and ambient checks passed. Final weather
  quality downgrade is additionally checked in Node and the focused browser smoke.
- Dedicated environment context is at most two lines (weather; calendar plus own condition), approximately
  40–70 extra input tokens, under $0.00003 per uncached call at the documented peak input price. Output caps
  and model-call paths are unchanged. Open-Meteo attempts are at most 48/day; tests/smoke never fetch weather.
- Limits: `backups/g4-latest.sqlite3` is absent, so only the saved export's Barry/pair counts could be verified.
  The smoke source is the older local copy, copied read-only into a temporary world. Latest live action rows,
  the real weather fetch and real-phone performance remain deployment/hardware checks. All supplied holiday
  dates match GOV.UK; fixed tables cover through 2027 and the festive event schedule is Christmas 2026.
- Suggested messages: Part 1 “Fix APC conversation opportunities, repeat caps and spoken decisions”; Part 2
  “Add cached Manchester weather and street effects”; Part 3 “Add UK holidays, festive events and payday visits”;
  Part 4 “Add deterministic APC bad days with story safeguards”. Combined: “Complete the Evorium realism pack”.

### 23 November 2026 — Realism Part 4: ordinary bad days

- Added deterministic SHA-256 daily setbacks in existing world settings: 3% off sick, 6% late by 30–60 minutes,
  and 35% hungover among those eligible through recorded late pub attendance. Outcomes are mutually exclusive;
  non-attendees never get hangovers. Actual late presence is sampled by the tick and recorded chats also count.
- Scheduled seed-event, open-offer expiry and open-promise due/retry days are exempt, as are the festive hosts'
  key dates. Recheck new deadlines while a setback is active. Sick APCs stay home awake/unavailable; delays
  affect only the first departure. Plans cannot force sick/delayed people to visit. Jess's sick shifts are
  covered by Dez, keeping the pub open; reserve Dez from simultaneous sickness when he must cover.
- Own observed fact and low-importance god-view history are recorded once. Conditions appear on god-view cards;
  others learn them in conversation. The speaker's short feeling shares the calendar line, preserving the
  two-line environment budget. Temporary moods restore only if dialogue has not changed them.
- Added eleven tests for deterministic rates, evidence eligibility, all critical exemptions, Jess/Dez coverage,
  first-activity delay (including night shifts spanning midnight), plan conflict, idempotence/privacy, safe mood
  restoration and public/god-view API data. No promise-evidence or
  commitment-resolution changes, new models/dependencies or schema migration.
- Part 3 validation: 382 Python tests and map/nav/Web3D checks passed, plus fake-model copied-world Chrome
  movement/chat/weather/festive-light smoke. Updated the Part 2 weather prompt test to require both the weather
  and newly required calendar line, rather than the old single-line environment string.

### 23 November 2026 — Realism Part 3: calendar and festive evenings

- Added the fixed, GOV.UK-verified England holiday table through 2027, holiday opening hours and pure payday,
  Friday-after-payday, Bonfire Night and Christmas countdown helpers. Pub/shop routines and plans respect
  closures; free evening visitors may stay at most an extra hour, without delaying work or sleep.
- Added once-only 2026 decorations/ticket notices, raffle draw, Christmas Eve and New Year's Eve events.
  Only present APCs observe an event; public decorations/ticket notices also inform later visitors. Raffle
  selection uses SHA-256 and present APCs only; a restart on a later date records no invented past winner.
- Calendar uses the second short environment line in dialogue/planning, with festive map/3D lights and guide/
  website updates. No payroll/bank change, model call, dependency or migration. Fixed dates need extension
  after 2027; the implemented Christmas event schedule is for 2026.
- Six calendar tests cover dates, closure boundaries, every APC's holiday routine, modest extensions,
  once-only observed events, raffle membership/determinism and the late-restart rule.
- Part 2 validation: 376 Python tests, map/navigation/Web3D Node checks and the fake-model copy-only browser
  movement/chat checks passed, including actual rain/snow/fog/unknown particle rendering.

### 23 November 2026 — Realism Part 2: real Manchester weather

- Added Open-Meteo parsing and a 30-real-minute world-settings cache, with a three-second timeout and bounded
  failed attempts. Failed/malformed HTTP retains the prior reading; readings older than six hours are unknown.
  Refresh is background-only at real-aligned 1×; other clocks reuse the labelled last reading without invention.
- Weather is supplied explicitly in routine inputs. Rain shelters Peggy, shortens Liam's doorway smoke break,
  skips Kirsty's pram walk and heavy rain stops Barry's window round. Unknown weather has no effects.
- Dialogue and existing daily planning share one short weather line. Usage/scene/header/map expose weather;
  Three.js has quality-bounded rain/snow, fog and darker wet lighting. Guide credits Open-Meteo; website updated.
- Twelve fake-HTTP/temp-DB weather tests pass. Test weather HTTP is globally faked and the offline smoke server
  disables refresh, so tests never fetch weather. No new runtime dependency/model call/schema change.
- Part 1 validation before weather: 364 Python tests, map/nav/Web3D Node checks and copy-only fake-model browser
  movement, collision and player-chat smoke passed. Existing acquaintance-context test is included in the count.

### 23 November 2026 — Realism Part 1: chances to talk and fewer loops

- Added a pure sampled-week shared-free-time audit and believable opportunities for the six APCs below
  three hours: Dez's quiet bar tea, Jess's Tuesday lunch, Simon's lunches, Anjali's after-lecture meetings,
  Grace's community pauses and Barry's flask break/Friday pint. Existing shifts, bench and quiz retained.
- Automatic pairing now caps completed/running NPC pairs at two per game date, keeps player chats exempt,
  and stops the current scheduling opportunity when its sole pair is capped. Manual run remains available.
  Pairing prioritises the longest-unheard available person before existing pair weights.
- Replaced the earlier tell illustration with a legal sign_petition payload, explicitly rejected if copied
  exactly; six-word/speaker attribution and action checks remain. Rejections retain their existing action
  record and logged reason. No promise-evidence changes, migration, model calls or dependency.
- Added six offline regression tests covering the weekly minimum, fairness over actual routine overlaps,
  caps, player/manual exemptions, copied examples and valid/wrong-speaker spoken decisions.

### 23 November 2026 — Full realism brief reviewed; plan awaiting approval

- Read the owner's supplied full four-part brief. It supersedes the provisional summary-based plan and
  explicitly requires posting a plan and waiting for the owner's OK before implementation. No Parts 1–4
  implementation code has been written. Existing acquaintance/job-context edits in memory.py, prompts.py
  and test_cast.py are separate work and will be preserved.
- Read-only findings: requested `backups/g4-latest.sqlite3` is absent. The saved 21 Nov current-world export
  confirms Barry has zero dialogue lines, and Dez–Jess and Raj–Anjali each have 16 conversations. Database
  action counts and live-data freshness cannot be verified from that export. No live database was touched.
- Pure week sampling (30-minute slots, real routine/opening/free rules, normal ledger settings) found shared
  free hours: Dez 0, Jess 2.5, Simon 1, Anjali 0, Grace 0, Barry 2; every other APC has at least 3 hours.
  Existing routines are unchanged. These six need believable opportunities without moving established beats.
- Part 1 plan: world.py/places.py/tick.py/sim.py for a pure weekly audit, routine overlap, fair picking and a
  two-per-game-day automatic pair cap. prompts.py/memory.py/actions.py/models.py as needed for a valid filled
  decision example, explicit copied-example rejection and diagnostics, preserving speaker/quote/action guards.
  Risks: preserving shifts/bench/quiz, quiet APC fairness, capped-place silence and Grace's follow-ups.
- Part 2 plan: weather.py and the existing background loop cache Open-Meteo for 30 real minutes in world settings.
  Retain last readings on failure; older than six hours is unknown. Refresh only at real-aligned 1× and reuse
  the last reading at other speeds, labelled appropriately. Pass weather explicitly through routine inputs;
  add Peggy shelter, shorter doorway smoke breaks, skipped pram walks and heavy-rain window-work cancellation.
  Wire usage/scene, header, map and vendored-Three.js rain/snow/fog/darker lighting with quality limits.
- Part 3 plan: calendar_uk.py with the requested fixed holiday table, explicit festive opening hours and pure
  payday/date helpers. All eight supplied holiday dates match GOV.UK (https://www.gov.uk/bank-holidays).
  tick/settings/timeline deliver observed festive events once, with a deterministic raffle winner from actual
  APC attendance. Modest payday/following-Friday pub extensions respect free time and closures; no new wages.
- Part 4 plan: a small bad-days module using SHA-256 name/date inputs and world settings for idempotent daily
  state. Target 3% sickness, 6% lateness (30–60 minutes), and 35% hangover only after recorded post-23:00 pub
  attendance. Exempt scheduled-event/offer/open-promise deadline days. Pass effects explicitly to routines,
  record own fact/low-priority history once, and display the condition on the god-view card. Preserve Jess's
  shift definition and pub opening; Dez covers. Do not change promise evidence or resolution logic.
- Prefer existing world settings; no schema change is expected. Migration 16 already belongs to Part 5;
  any genuinely needed new migration would be appended as 17. No new seed facts/dependencies/model calls.
  Combine weather/calendar/own condition into at most two short additional prompt lines; measure token impact.
- After each part, run the full Python/Node checks and fake-model copy-only smoke/browser checks, then update
  this document. Add guide notes and separate weather/calendar/bad-days website entries. Final report will
  include test counts, cost impact, verification limits and a suggested commit message per part. No commit/push.

### 23 November 2026 — In-game police follow-up test checklist

- Added a manual verification checklist in §5: owner identity, back-filled case and notice, normal patrol
  overlap, automatic opening, ending the chat for notes, and checking both sides’ knowledge and history.
  Clarified that sanctions are Grace’s choice and repeated live tests change memories. No code or live state
  changed; the existing temporary-world case suite is the repeatable offline option.

### 23 November 2026 — Grace follows up reports

- Implemented migration 16 and `cases.py`: attributed serious reports, incremental back-fill, one unresolved
  case per named subject, routine/availability priority, daily attempts, correct-account player openings,
  missed visits and catch-up, spoken outcomes and a three-game-day no-further-action timeout.
- Fixed the spoken-decision extraction example first; retained the six-word speaker quote, strict argument,
  transactional and daily action checks. Police outcomes additionally require Grace's current conversation
  with its subject, and cannot be issued by morning/reaction calls. No outcome is inferred from an apology.
- Outcomes record serious history and facts for subject, reporter and Grace. God-view cards/timeline show
  cases; dashboard and 3D player panels show notices and outcomes, with incoming 3D chats. Explicit 3D street
  presence fixes the previous “outside” state while walking there. Removed private rationale from the
  dashboard's player conversation. Updated guide and website (“The police follow up”).
- Confirmed the saved 20 Nov 23:00 transcript: Dez reported the jaw threat and gun mention directly to Grace.
  The available local SQLite copy is older, so a dated fact fixture tests back-fill; the live G4 is untouched.
  Conservative report grammar and persistent player presence remain limits (§9).
- Validation: **357 Python tests pass**, including 19 new temporary-world/fake-client police checks and
  migration-15→16 preservation. Map/navigation and Web3D Node checks pass, including incoming chat and panel
  isolation. The full offline browser run passed: 20 desktop/phone screenshots, movement/collision,
  fake player dialogue and all ambient checks. The system Python has incompatible HTTP test packages; the project virtualenv passes outside
  the sandbox, whose async TestClient loop otherwise hangs. No runtime dependencies, commit or deployment.

### 23 November 2026 — Grace follow-up implementation plan

- Part 5 will append migration 16 for cases, scan Grace's attributed importance-5 reports once for
  back-fill and then incrementally, prioritise APC subjects on her beat, approach the correct account's
  player without interrupting chats, and leave missed-visit notices/catch-up.
- First fix the spoken-decision extraction example (Part 1 prerequisite); preserve speaker attribution,
  six verbatim words and all action checks. Outcomes use that path only, with subject/reporter facts,
  serious history, and a three-game-day no-further-action timeout after speaking without a decision.
- Finish with god-view case cards/timeline, player notices/outcomes, guide and website copy, and offline
  temporary-database/fake-client regression coverage. Other realism-pack parts remain planned.

### 23 November 2026 — Realism pack planned; bank idea deferred

- The owner suggested a bank with accounts for everyone. Agreed it fits (money as checkable evidence, real money
  pressure, loans with teeth), but proposed balances plus a cash machine at Patel's rather than a bank branch, with
  routine income/spending in Python. Deferred by the owner as too big for now.
- Planned instead (§10): behaviour fixes, real weather, the real calendar and ordinary bad days, as one Codex
  job. Findings from the 21 Nov world copy: Barry 0 lines; Raj–Anjali and Dez–Jess 16 conversations each; the
  actions table has no conversation decisions. The owner said the ngrok token is fine as it is.

### 23 November 2026 — Promises are fixed once made, and made to real people

- Live report on the G4 (19 conversations since the update): legacy promises lapse correctly (Tommy's "ask Dez"
  at 14:50), 0 evidence problems, no claims yet. But restating had become a loophole: Peggy promised Rob to talk to
  Brenda by 16:21, repeated it to someone else, and her deadline jumped to 26 Nov (the 72-hour default when no
  deadline is said). Promises could be put off for ever, so none had come due.
- Owner's rule: **promises are tied to real people and can't be changed once set.** `memory.store_extraction` now
  ignores a restatement of an open promise entirely (deadline, recipient, wording and type stay as made, no
  `promise_updated` entry) and drops any promise not made to a real other person (no recipient, an unknown name,
  or themselves). The extraction prompt says so. This replaces the earlier made_at-reset fix for restated
  promises, which is no longer needed.
- Tests: fixed-once-made, real-recipient (three cases) and recorded-to-them tests; the older restate tests were
  updated to the new rule. 336 Python tests pass.

### 23 November 2026 — Website "What's new", promises in the guide

- New standing rule (owner's request): every player-visible feature gets a short dated entry in a new
  **"What's new"** section on the website (rule 12 in §15, and in `AGENTS.md`). First entries: evidence-checked
  promises (23 Nov), named logins and the guide (21 Nov), eighteen APCs and the street (20 Nov), the 3D game (20 Nov).
- Website copy brought up to date: "Eight" → "Eighteen" APCs (meta descriptions and the APCs intro, which notes
  eight are shown), and the "They remember what matters" step now says their word gets checked. Checked at 1440 and
  375 px.
- `/guide` has a new **Promises** section: how to get one, how they're checked (done, broken, lie, retry, lapsed)
  and the player's own Done / Didn't do it buttons.

### 23 November 2026 — Live test of promise evidence; restated-promise fix

- Live test on the G4 (version bc50ff9): the owner got Peggy to promise to "bend Brenda's ear" this afternoon. It
  was saved as a typed `talk` promise to Rob, due 16:02, so new promises are recorded with types.
- Found a bug in the live data: Raj restated an old legacy promise to Mo ("read out the darts notice names") as a
  typed `talk` promise *while talking to Mo*. A restated promise kept its old `made_at` and source conversation, so
  the restating conversation itself counted as evidence and showed "Database evidence recorded" straight away.
- Fix (`memory.store_extraction`): when a restated promise changes its type or target, `made_at` and
  `source_conversation_id` move to the restating conversation, so evidence counts only from then. A restatement with
  the same type and target (e.g. a new deadline) keeps its progress. Two regression tests in
  `tests/test_promise_evidence.py`; 333 Python tests pass.
- Peggy's promise had the same bug: the write-up matched it to her legacy promise to Dez ("bend Brenda's ear") and
  kept its 21 Nov `made_at`, so a 21 Nov Peggy–Brenda chat counted as evidence. One-off repair on the G4 (after a
  backup): open typed promises whose latest `promise_updated` timeline entry is later than `made_at` took that
  entry's time and conversation. Fixed Peggy (→ 23 Nov 12:02) and Raj (→ 23 Nov 14:45). A `talk` promise is satisfied by any later conversation with that person, not
  necessarily about the promised subject.
- The owner found APCs reluctant to promise a stranger anything. That is in character: they promise what serves
  their own goals (Peggy agreed because it helps keep the Billet open).

### 23 November 2026 — Evidence-backed APC promises (local implementation)

- Implemented the owner's approved plan and amendment: appended migration 15 with typed targets, game-time
  creation, retry/claim/lapse timestamps and `promise_claims`. Left the commitments table, its original status
  CHECK and all foreign-key references intact. Legacy rows survive and back-fill game time where possible.
- Added one evidence matcher, guarded shared resolution, pending conversation claims, exact plan matching,
  deterministic bounded deadline checks and one retry without moving `due_at`. False completion claims cost
  −20 trust/−6 warmth rather than an honest miss's −12/−4. World-derived facts and timeline entries feed gossip
  and catch-up. Conditional triggers need actual database events; unsupported/legacy promises lapse neutrally.
- Applied `lapsed_at IS NULL` to every open/current promise query, including human-view/maintenance filters
  explicitly requested by the owner; human self-resolution otherwise remains unchanged. Dashboard promise
  history labels lapses correctly. No accounts, authentication or player route changes.
- Preserved typed targets through extraction cleanup, supplied a filled typed JSON example, exposed fact IDs
  for precise tells, and added deadlines/progress to dialogue, morning planning and reactions. Existing reminder
  queues and action/plan budgets are reused. Removed the old example-content suppression: a real forty-question
  promise must not be dropped just because it matches the illustration.
- Evidence rejects the wrong owner, old/future events, different targets/arguments, incomplete or silent-owner
  conversations, and the promise-making conversation itself. Quiz progress counts actual action-linked stat
  changes. Asks use their owner's completed answer action because the table has no resolution timestamp.
- **Verification:** full `.venv/bin/python -m pytest -q`: **331 passed**, one existing Starlette deprecation
  warning. Includes **81 new promise tests**, 0/50 self-certified quiz completions on each audit path, all typed
  evidence/opportunity cases, neutral lapses, human controls, and a version-14 copy with referenced plans.
  `node tests/map_view.test.cjs` (**8 passed**), `node tests/nav.test.cjs` (**2 passed**) and
  `node tests/world3d.test.mjs` all pass. Sandboxed pytest stalled; the same offline suites passed outside the
  sandbox. No dependencies added or real API calls made.
- Existing fake smoke server started on **8011**, using only `/tmp/evorium-promise-smoke/world.sqlite3` copied
  read-only from the local development world. Dashboard, `/world3d`, APC/player views and scene returned 200;
  migration version 15, foreign-key check and integrity check passed. Server stopped cleanly. No new browser
  rendering capture was needed for this promise change; physical-phone limits remain unchanged.
- Updated §2, §3, §5, §6, §9 and §10. §7's 3D architecture is unaffected. No live-world/configuration edits,
  branches, commits or pushes. Ready for owner review and push after review; no deployment performed.

### 23 November 2026 — Promise evidence investigation and proposed implementation

- Confirmed all three self-certification paths: model deadline answers, conversation extraction and
  unmatched plan fulfilment reach the shared resolver. No implementation changes yet; the owner explicitly
  requested a plan and approval before coding. Existing local documentation edits were preserved.
- Proposed migration 15 adds typed targets, game-time creation, retry and claim timestamps plus a claims
  ledger. The existing commitments status CHECK excludes `lapsed`; migration must safely accommodate that
  outcome while preserving IDs, rows and foreign-key references, without editing earlier migrations.
- Evidence will join owner-authored actions, completed plans/conversations, attributed told facts and
  action-linked quiz stat changes using game timestamps. Asks lack a resolution timestamp, so accepted
  answers need their completed `answer_ask` action as evidence. Loans can be advanced but there is no
  repayment action; unsupported payments/research/conditions must remain uncheckable, never inferred.
- Proposed bounded deterministic deadline checks, one unchanged-deadline retry for lack of opportunity,
  neutral lapses, evidence-based resolution facts, stronger false-claim penalties for checkable promises,
  and deadline/progress context for the existing planner and reaction mechanism. Human controls stay intact.
- Validation planned: per-type evidence/opportunity tests, 50-seed false-completion assay, claim and
  migration regressions, full offline Python suite and Node tests. No tests run during this investigation;
  no live world, private configuration, branches, commits or deployment changed. Not ready to push.

### 21 November 2026 — Named accounts v1 (local implementation)

- Added optional private-config `ACCOUNTS` named Basic logins and request-scoped `ContextVar` identity,
  including `/me`. Kept the existing owner credential valid with any username and no-config local mode.
  Account names are case-insensitive; actual credentials are never written to tracked files.
- Appended migration 14: account column, original-player owner marker, unique non-null account index.
  Named players are created once at first authenticated request. Existing owner IDs, names, history,
  place settings and catch-up checkpoints remain intact; no live world was migrated during this work.
- Made profile edits, places/street auto-entry, open chats, learned facts, promises, relationships,
  catch-up checkpoints/cache/budgets and maintenance account-aware. Active APC chats refuse a second
  player for three real minutes; startup/idle maintenance handles all players and restores its context.
- Scene snapshots remain read-only and identify the caller plus other present players. The dashboard
  shows the player’s name; the map and 3D render other humans by name, using the player body, without
  treating them as APC talk targets. The fake smoke server migrates only its database copy.
- Added offline regression coverage for concurrent identities/provisioning, owner compatibility, name
  clashes, player isolation and APC attribution, busy refusals, maintenance, scene visibility, catch-up
  and preservation of every row in a copied version-13 world. Retained existing legacy migration tests.
- Verification: 249 Python tests pass (one existing Starlette test-client deprecation warning), plus
  eight map tests, two navigation tests and the Web3D Node checks. `run_checks.sh` passed on the fake
  server at 8011: 20 desktop/phone low/high world captures, collision/movement/doors, fake chat, 60×
  routines and 16 ambient captures/checks. An additional fake two-account browser run verified each
  dashboard name and the other player’s 3D model/name tag, with no browser errors or model fallback;
  four captures and `accounts-browser.json` are in ignored `tools/web3d/raw/screens/`.
- Browser review also corrected the dashboard’s street entry label (previously duplicated the shop
  wording) and ensured name-card clicks use the latest profile. All accounts deliberately retain
  god-view access for trusted friends. No runtime dependencies, commits, pushes, live-server settings
  or private credentials changed. Physical-phone checks and the separate public-player view remain future work.

### 21 November 2026 — GitHub history sanitised and published

- Published the tested current-file cleanup, then used git-filter-repo 2.47.0 in an isolated mirror
  to sanitise deployment identifiers across every historical blob and remove authentication prose
  from historical Markdown. Rewrote 33 of 36 commits and force-pushed only `main` with an exact lease.
- Verified zero removed-value matches across reachable history and zero matching prose in historical
  Markdown. The rewritten tip tree exactly matched the tested release: 236 Python tests, Web3D checks,
  seven map tests, two navigation tests and shell syntax passed. GitHub API/ref checks confirmed the
  rewritten tip. No forks, pull requests or secret-scanning alerts were reported.
- Preserved the original Git history in a restricted, ignored backup bundle; aligned the main-PC
  checkout using `reset --keep`. G4 SSH access was unavailable, so §6 contains the required server
  alignment commands. No live world, private config, service or credentials were modified.
- Verified that GitHub still serves an old, now-unreferenced commit through its API. Offered making
  the repo private to block public access; this requires an owner choice because server fetches would
  then require GitHub authentication. Reachable history cleanup cannot erase copies held by others. GitHub Support is the route for eligible server-side purges. First changed commit
  for such a request: `a71cc60f72a8c7957b9724f18e4914cf6a953ee4`; affected pull requests: zero;
  no LFS in use. Source: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository .

### 21 November 2026 — Publish approved security cleanup

- The owner explicitly authorized publishing the cleanup and removing exposed deployment details
  from GitHub history. Current changes only affect documentation, installer wording and an example
  comment; authentication and world data are unchanged.
- History removal is being prepared in an isolated mirror with a private backup. A rewritten `main`
  cannot fast-forward from old clones: the G4 updater safely refuses that transition while the running
  game continues. The server checkout will need alignment before automatic updates resume.
- Rewriting published refs cannot erase copies already downloaded or guarantee deletion of cached
  commit views. GitHub Support handles eligible cache/pull-reference purges. Actual access secrets
  must be rotated through the service/server separately.

### 21 November 2026 — Remove deployment connection details

- Removed the specific tunnel domain, LAN address, service account name and absolute server checkout
  path from current documentation, including old session entries. §6 uses generic placeholders; the
  hosting summary and audit status now reflect that connection details are kept private.
- These values are unnecessary for public setup instructions. No runtime configuration, authentication,
  tunnel, server service or world data changed. The owner shares connection details privately.
- Checked every tracked working-tree file for the removed values and checked diff formatting.
  No commit or push was made. Older Git revisions still retain the details; erasing that history would
  require a coordinated rewrite and forced update, accounting for the G4 auto-updater and other clones.

### 21 November 2026 — Remove sensitive authentication prose

- At the owner’s request, removed all references to access secrets from project documentation,
  including the previously published weak literal, configuration-name mentions and historical narrative.
  Initially retained the connection details the owner asked to identify; these were subsequently
  removed at the owner’s request (see the later cleanup entry).
- Reworded installer messages/comments and the example-config comment to describe access control.
  Required authentication identifiers and offline test fixtures remain in code so existing G4 settings
  continue to protect the service. Private configuration and live-world data were untouched.
- Earlier commits still contain the old prose; these local edits have not been committed or pushed.
  Verified documentation search, shell syntax and diff formatting; no authentication logic changed.

### 21 November 2026 — GitHub credential audit and Web3D preflight

- Audited a fresh mirror of `DgenKing/evorium`, matching local tip `e7404e6`: 35 commits,
  220 tracked files at HEAD, one published branch and no tags. No detected real API key or private key;
  the local DeepSeek key does not occur in fetched historical blobs. `config.py`, database and key files
  were not found as tracked historical paths. API-key examples and installer checks are placeholders.
- Reported sensitive authentication prose and published server connection details without reproducing
  credential values. The owner subsequently approved removing the prose from current documentation;
  no history rewrite, credential rotation, commit, push or live-server change.
- Recovered the deleted Web3D brief from `d0a5535` for §0.2. Blender 5.3 runs outside the sandbox,
  npm responds, and both Standard zips pass integrity/glTF/CC0 checks. The kit path is missing in this
  session, so the brief’s prerequisite gate blocks new exports and bakes. Prior stages are already shipped;
  do not rebuild over the later MPFB cast merely to repeat the original Quaternius implementation.
- Verification: 236 Python tests pass (one existing Starlette deprecation warning), alongside the
  existing Web3D Node checks, seven map checks and two navigation checks. Python tests complete outside
  the sandbox; sandboxed attempts produced no result. No new browser review or asset rebuild was performed.


### Session of 20 November 2026 — Cosmetic street life

- The owner supplied Animal Pack Vol.2 and approved its wolf as the fox substitute, resolving
  the previous asset preflight blocker. Inspected the archive and its original Idle/Walking
  clips; verified the creator's indexed CC0 declaration and recorded the archive SHA-256 and
  source links in the existing asset licence manifest. No Ultimate Animated Animal Pack file used.
- Added `ambient.js`: per-browser visible-time scheduling, exact public snapshot daylight rules,
  pavement/gutter subsets of the existing route graph, ground/prop checks, separation from Rob
  and APCs, lazy cached animal GLBs, instanced procedural pigeons, three procedural rubbish
  forms, gusts, stops, can rolling/rattle, day dog/night fox and quality event limits. Ambient
  objects never enter the player octree. Animals face their actual movement vector, with smooth
  turns. Idle clips support rests/sniffing/look-arounds. The saved gear toggle and `ambient=off`
  remove active street life; deterministic test types load only after the first view/visible cast.
- Added `build_ambient.py`, `optimise_ambient.mjs`, full-pipeline integration, ambient and total
  download gates, Node policy/heading/accounting tests and `ambient_checks.mjs` in `run_checks.sh`.
  Exports are vertex-coloured, animated and Meshopt-compressed; no textures or new dependencies.
  Actual on-disk sums agree with budgets: **0.233 MB ambient per tier**, whole assets **6.759 MB
  low / 10.958 MB high**, under **1.2/2.5 MB ambient** and **12/30 MB whole-game** limits.
- Visual review caught raised pigeon feet, a newspaper hovering above the paving and a can
  rolling about the wrong axis; corrected all three. Separated pavement and gutter graph
  components so animals/paper remain above the kerb and cans follow its outside line.
- **Verification passed:** `.venv/bin/python -m pytest -q` (226 tests, existing Starlette warning),
  Web3D Node checks, seven map tests and `bash tools/web3d/run_checks.sh` (exit 0). Its 20 normal
  screenshots, blank-image checks, open/closed door walking, 1.03 m jump, wall/camera collision,
  fake chat and 60× routine updates passed. The final Node run additionally checks actual movement
  heading and independent asset-directory byte sums. All server/browser checks used the fake
  smoke world on **8011**, never 8000; owned server and Chrome exited afterward.
- The additional **16 ambient captures** cover desktop high (1280×720) / phone low (390×844),
  daylight for pigeons/rubbish/cat/dog and night for fox, plus off baselines. Looked at every
  ambient image. Reports and images: `tools/web3d/raw/screens/ambient/` (ignored build artifacts).
  Automated checks verify low event/bird caps, no unwanted animal loads, saved off toggle,
  hidden-time pause, day/night removal and genuine walk-bone changes. Rob and APCs each scatter
  pigeons independently; Rob walks **3.875 m** into/through the flock and **4.8 m** past each
  rubbish/animal fixture without being blocked, on both profiles.

#### Street-life screenshot review

| Type | Desktop high and phone low review |
|---|---|
| Pigeons | Five high / two low, grey bodies, darker heads, beaks and paired feet; sensible small-bird scale beside Rob and paving. Feet meet the pavement; heads vary between upright and pecking. No wall/kerb clipping seen. Their short walking turns and wing flaps are code-driven; scatter/passage is verified by the interaction tests. |
| Cat | Small charcoal cat with light paws and raised tail, about **0.409 m** total height in the captured walking frame. Far below Rob's knee/hip scale, paws at ground level, muzzle points in the +X walking direction. The sampled walk changes its leg pose and retains ground contact; no wall or kerb overlap seen. |
| Dog | Brown medium-sized dog, about **0.601 m** total height in its walking frame, larger than the cat and below Rob's waist. Forward-facing muzzle, alternating lifted/grounded paws, no floating or wall/kerb clipping. Original walking clip is sampled faster for the trot. |
| Fox substitute | Orange body, white bib/tail tip, dark legs, about **0.513 m** tall in its walking frame; visibly smaller than the dog. Dark paws touch the outer pavement and the muzzle faces travel. The slow original wolf walk changes bone poses; no visible floating or clipping. Night windows provide context. Wolf silhouette remains an acknowledged art compromise. |
| Rubbish | Yellow/red crinkled packet, folded printed newspaper and red can with metal ends, at believable small sizes. Paper lies close to paving after correction; can lies horizontally at the gutter below the kerb, fully visible in the phone frame. No wall clipping seen. Gusts now make packets/paper flip as well as spin; the can rotates perpendicular to its travel. |

#### Measured rendering cost

Thirty rendered frames per fixed camera/pose after warm-up; draw calls include high-tier shadows.
The baseline is the same client/camera with `ambient=off`, before adding a street-life fixture.
Can uses a gutter camera and fox uses night lighting, so their FPS is not a controlled daytime
comparison. SwiftShader CPU contention/warm-up causes substantial variance: these samples do
**not** establish a real-device FPS improvement or a reliable movement-time FPS cost.

| Fixture | Phone low calls | Phone low FPS | Desktop high calls | Desktop high FPS |
|---|---:|---:|---:|---:|
| Off baseline | 103 | 6.44 | 270 | 1.39 |
| Pigeons | 110 | 6.57 | 283 | 1.40 |
| Crisp packet | 105 | 8.72 | 274 | 1.42 |
| Newspaper | 107 | 8.17 | 276 | 1.43 |
| Can | 106 | 7.17 | 276 | 1.69 |
| Cat | 104 | 6.47 | 272 | 1.69 |
| Dog | 104 | 6.74 | 272 | 1.72 |
| Fox | 104 | 7.76 | 272 | 1.72 |

Incremental draw cost is **1–7 calls low / 2–13 high** in these captures (newspaper/can cameras
have slight visibility differences). No slowdown was resolved against the off baseline in this
run; physical-phone/GTX FPS and listening to the can rattle remain unverified. Cat doorstep
rests, dog sniffing and fox pauses use Idle plus small turns; no dedicated sit/sniff clips or
windowsill leap. The fox pauses at the quiet street end rather than a separately authored bin
area. No simulation/API/model-call changes, no live database writes, no commits or publication.
README remains a pointer and needs no change. §2, §3, §7, §9, §10 and §13 updated.

### Session of 20 November 2026 — Street life asset preflight

- Read the project rules and inspected the current 3D client, quality presets, route graph,
  asset pipeline and check harness. The working tree was clean before this investigation.
- Found CC0 candidate animal sources on the creator's official site and OpenGameArt upload:
  Animal Pack Vol.2 for cat/dog, Ultimate Animated Animal Pack for fox. The expected local
  `~/Downloads/evorium-animals/` directory does not exist.
- The official fox download returned an HTML **Google Drive - Quota exceeded** page rather
  than a model; the cat/dog archive page returned HTTP 403 to automated access. Stopped at
  asset acquisition, respecting the owner's instruction to request browser downloads rather
  than proceed without the required models. Exact downloads are recorded in §7.
- Documentation only: no runtime, simulation, API, asset, dependency or budget changes;
  no tests, screenshots or FPS measurements run, and no commits. Full implementation and
  requested checks remain pending. README remains the existing pointer and needs no change.

### Session of 20 November 2026 — Scripted MPFB cast

- Installed official MPFB 2.0.18 through Blender's CLI, verified it in Blender 5.3 background
  mode, and installed the official CC0 system, hair01 and bodyparts05 packs into MPFB user data.
  The primary asset mirror was slow; the secondary completed normally. CC-BY alternatives were excluded.
- Viewed the five portraits and eight website references; scripted nine age/build/skin/hair/clothing
  configurations, game-engine rigs and low-poly proxies. Exported individual models and explicit asset
  inventories; added a rest-pose-aware UAL retarget script and bone map, keeping all ten clip names.
- Added lazy per-model loading, a logged Quaternius fallback with original clips, model-height labels,
  per-person download/geometry gates and studio lineup/head/body test cameras. The public scene API,
  simulation, player APIs, website and live G4 world are unchanged. No commits.
- First visual review caught duplicated trousers on the cardigan outfit, dark cardigan colours and missing
  iris textures; corrected those, beard colours and Tommy's checked shirt before the final capture run.
  Further review flattened Dez's beard to stubble, rebuilt Brenda's fitted hair as an opaque curly perm,
  and made Tommy's checks finer. Added a sole-vertex grounding correction after measuring 3–4 cm of
  idle/sit penetration. Airborne animation keeps its lift. Fixed a smoke-harness shutdown race by waiting
  for its owned process and failing if it exits before readiness. NPC placement now uses the actual
  pub/shop floor levels instead of marker-height or chair-back collision, keeping feet and sitting poses grounded.
- Final asset totals: **6.53 MB low / 10.73 MB high**, including all nine people and fallback files. Each
  low model is **0.248–0.352 MB / 4,015–10,004 triangles**; each high model is
  **0.453–0.750 MB / 11,182–22,630 triangles**. Vendor files add about 2.4 MB. All configured budgets pass.
- **226 Python tests**, seven map tests and the expanded Web3D Node checks pass, including lazy cache,
  model presence, fallback selection and unchanged ten-clip mapping. The final Chrome review has **78 captures**:
  20 world views, 40 lineup/head views (all nine, desktop/phone, low/high), 18 pose checks for Dez/Tommy/Brenda.
  No browser errors or model fallbacks. Grounded studio poses measure soles within 2 mm of the floor;
  airborne poses retain lift. Walk-throughs finish within 0.13 m with no final penetration, pub/leave/shop/leave
  calls, fake chat, 1.03 m jump, camera/closed-door blocking and a successful 60× routine change.
- World-view total draw calls: **88–135 low / 207–254 high**; visible geometry **75,148–137,636 low /
  139,046–209,599 high** (including only the main visible geometry, separate from shadow/transparent passes).
  Lineup/head views: **12–190 total calls**, **4,017–132,798 visible triangles**. SwiftShader world FPS is about
  **3.8–7.9 low / 1.5–1.9 high**; hardware phone/desktop performance and iOS memory remain unverified.
- Reviewed every capture via the contact sheets in ignored `tools/web3d/raw/mpfb/`: `cast-review.png`,
  `lineup-review.png`, `world-review.png`, `poses-review.png`. Individual PNGs and `mpfb-reports.json` are under
  `tools/web3d/raw/screens/`. Faces/garments are stylised approximations, not photographic replicas; no black
  textures or twisted wrists/shoulders were seen in the reviewed poses. Portrait cards still use the existing 2D art.


#### Cast appearance review

| Character | What the final screenshots show | Approximation to retain or refine |
|---|---|---|
| Dez | Stockier man, short grey hair, grey facial hair, black collared top and dark trousers | Facial hair remains fuller-looking than the portrait's light stubble; collared shirt replaces exact polo |
| Jess | Slim woman, fair skin, dark swept-back bun, dark work top and black trousers | Simple top and low-poly face |
| Tommy | Shorter older man, bald crown with silver sides, navy outer layer, checked shirt, grey trousers | Cardigan-style jacket and generic shared gait rather than a bespoke elderly animation |
| Raj | Medium build, brown skin, short black hair, neat dark beard, muted grey shirt/dark trousers | Broad MPFB phenotype and simplified facial detail |
| Chloe | Slim woman, light-brown bob, green top and dark jeans | Straighter bob and simpler top than the reference's wavy hair/knit |
| Simon | Tall/trim, neat dark hair, clean-shaven, charcoal suit | Simplified shirt/lapel detail |
| Brenda | Short/rounder older woman, irregular grey curls, lilac outer layer, dark trousers | Faceted procedural curls and jacket-style garment rather than exact cardigan |
| Mo | Solid build, short dark hair and beard, dark navy jacket/trousers | Shared CC0 hair/beard style with Raj, different skin/body/clothes |
| Rob | Average build, short brown hair, cream top and blue jeans | Intentionally plain; readable from the follow camera |

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
optional dashboard authentication, portraits and a home-LAN service. The world database was restarted on 16 Nov; the
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
  ngrok as a systemd unit. The world moved from the main PC (464 KB); the tunnel address is shared privately.
- **First auto-update rolled back, as designed:** a new 3D test failed because the G4's `config.py` sets an
  authentication setting. Tests now ignore the machine’s local authentication configuration (`tests/conftest.py`).
- **The 3D game is live:** the G4 auto-updated and the owner played `/world3d` over the internet. Owner's
  verdict: "this is more than good enough for what we need".
- **Unreal removed**; `tools/smoke_unreal.py` renamed `tools/smoke_server.py`.
- **Website copy updated** by Codex for the browser game.
- **All docs merged into this file.** The old README, the home server guide, the Web3D pipeline, controls and
  verification notes, the portrait prompts, the old LAN service notes and the finished M4 and Web3D briefs were
  folded in and deleted (they're in git history). `README.md` now just points here.
- **More active APCs, and five new ones (Claude).** Activity check on the 20 Nov world copy: Dez 26
  conversations, Jess 21, Raj 17, Tommy 16, Simon 3, Mo 2, **Brenda 0, Chloe 0**. Their routines rarely overlapped
  anyone while auto mode was on (most play was on Thursdays). Changes:
  - Routines: Brenda gets pensioners' lunches (Tue/Thu) and weekend afternoons; Chloe a morning coffee at Patel's
    and pub evenings Tue–Fri; Mo an hour before his Thu/Fri shifts; Simon a Tuesday lunch at the Billet.
  - **New APCs:** Peggy Coyle (82, the daytime regular), Liam Byrne (27, scaffolder on the mill job), Anjali Patel
    (19, Raj's daughter, law student, shop Mon/Wed/Fri and Saturday), Pete Lomax (58, drayman, Tue/Fri deliveries)
    and Hannah Kerr (31, reporter on the Northgate story). Each has seed facts (appended, since seed keys are list
    positions), starting relationships and a weekly routine. A simulated week: every APC now spends time with
    company (Brenda about 12 h, Chloe about 20 h, Mo about 10 h a week).
  - `world.pick_pair` now also favours **people** who haven't spoken lately, not just pairs, so whoever is behind
    the bar no longer dominates.
  - Tests: cast-size assertions now use `len(CHARACTERS)`; new tests for seeding the newcomers into an existing
    world without duplicating facts, the new routines, and fairer pair picking. 229 pass. Seeding a copy of the live
    world added exactly 5 APCs and 15 facts, touching no conversations. On the G4 they appear at the next restart
    (the auto-update restart does it).
- **APCs on the street, and more drop-ins (Claude).** The owner saw an empty map mid-afternoon (only Dez and
  Raj). Shuttle Street itself is now a place: `world.STREET = "Shuttle Street, Ancoats"`. `/world/scene` reports it
  as `place: street` and the 2D map draws people there. New street moments: Tommy walking to the shops, Peggy on
  the bench outside the Billet after her half, Liam's smoke breaks and walk home, Brenda chatting on the pavement
  (Mon/Wed/Fri mornings), Pete unloading the dray, Anjali walking up from the tram, Hannah asking about the terrace
  (Tue/Thu lunch) and Dez out front for a breather. More drop-ins: Tommy browses the papers at Patel's and has an
  afternoon half on weekdays; Brenda Friday afternoons at the pub; Mo buys lunch at the shop and practises darts on
  Wednesday afternoons; Chloe picks up the property pages on Saturday mornings. Test added; 233 pass.
- **Five more APCs (second batch):** Gary Walsh (postman), Kirsty Doyle (young mum, Jess's neighbour), Grace
  Adeyemi (PCSO), Barry Hughes (window cleaner) and Ronnie Clegg (Tommy's old mate from the 216), with routines on
  the street and in the pub and shop, story facts and relationships. 18 APCs in all. A simulated week now shows
  2–6 APCs about on most weekday half-hours besides Dez and Raj (Sunday stays quiet). Seeding a copy of the live
  world added exactly these APCs with no duplicates. 234 tests pass.
- **Talking on the street.** The owner pressed E on Peggy outside the Billet and got "Walk into a place before
  speaking": street APCs had arrived but street conversations hadn't. `places.REGISTRY` now includes
  `'street': world.STREET` (always open), so the player can talk to anyone on Shuttle Street (being outside counts
  as being on the street, set automatically on the first line), APCs can chat to each other on the pavement, and
  the dashboard's "Where everyone is" lists the street. You still can't talk to someone who isn't there. Test
  added; 235 pass.
- **Burger menu on every page (21 Nov).** `evorium/static/nav.js` is one shared script that adds a ☰ button to the top
  right of each page's header (beside Restart on the dashboard and beside the ⚙ in 3D) and a panel with
  **Dashboard, Map, 3D and Timeline**, the current page highlighted. Full width with big targets on phones; closes on
  Esc, a tap outside or choosing a page; releases the mouse in 3D. Loaded by `index.html`, `timeline.html` and
  `world3d/index.html`. Tests: `tests/nav.test.cjs` (the four pages, no "Home", highlighting) and
  `tests/test_nav.py`. Checked with headless-Chrome screenshots, open and closed, desktop and phone. Also fixed the
  street-talk tests, which had only passed because of the time of day: they now freeze the clock with both anchors.
  236 pass.
- **Conversation review, 21 Nov (G4 world copy: 130 conversations, 814 lines since 17 Nov).** Full readable
  export of both worlds (145 conversations) in the git-ignored `backups/evorium-conversations-2026-11-21.txt`.
  - *Working:* new APCs moved the story: Raj told Anjali (#84); Gary's recorded letters to the empty unit led Raj
    and Dez to compare notes by phone and spot coordinated pressure (#133, #135); Hannah got Dez on the record
    anonymously (#106); Dez countered Simon face to face at £3,200 (#149); Peggy is rallying Brenda (#151).
    Brenda, Chloe and Mo now talk. Rob's threats, theft and slurs spread to Anjali (police, camera), Liam, Jess,
    Dez, Raj and Grace.
  - *Problems:* (1) Anjali and Raj loop: about 12 shop conversations where she promises to check Companies House
    "tonight", because there is no research action and they are often alone together. (2) Spoken decisions aren't
    becoming actions: Dez's £3,200 counter was said but not recorded; the actions table has only `wait`.
    (3) Barry has never spoken and Pete only once. Speaking counts: Dez 49, Raj 47, Rob 38, Jess 30, Tommy 26,
    Anjali 22; Peggy, Gary, Simon, Brenda, Chloe, Hannah and Mo 3–6; Kirsty and Grace 2; Pete 1.
- **Player guide for Thomas (21 Nov).** New page `/guide` (`evorium/static/guide.html`), in the ☰ menu as "Guide". It's
  inside the game, behind the login, rather than on the public website, because it explains the owner's controls
  and the god view. It covers: what Evorium and APCs are, playing as yourself, what the god view shows (private
  thinking, secrets, money, controls), the **clock speed warning** (always 1× real time; faster speeds multiply
  the cost; choosing 1× snaps back to real time), the ☰ menu, a tour of the dashboard (header, controls row,
  terrace and APC cards, You panel, live feed, catch-up, spend), talking to APCs, the map, the 3D controls (desktop
  and phone), the timeline, and do's and don'ts (leave auto mode and the director as found, don't press Restart, don't
  spam Run conversation). No credentials in the page. Tests: nav includes Guide; the page warns about the clock.
  250 pass.
- **Owner's rule: APCs only.** No fake or background people (passers-by, crowds, non-AI extras) anywhere, on the
  map or in 3D. A cosmetic passers-by feature was written for the map and removed the same day at the owner's
  request. Busier streets come from more APCs and denser routines. Animals and blowing rubbish are fine; they
  aren't people.
- **Version on the dashboard.** The header shows the git commit the server is running and its date (e.g.
  `v ed9ac18 · 20 Nov 13:54`; hover for the commit message; "(edited)" if there are uncommitted code changes).
  `main.code_version()` reads it once at start-up, so every G4 auto-update shows its new version by itself; outside
  a git checkout it says "unknown". `/usage` returns it as `version`. Tests in `tests/test_version.py` (232 pass).
- **"APCs" (AI Player Characters)** adopted as Evorium's name for its characters: website (people section
  "Meet the APCs", nav, hero line, meta and share descriptions, amber highlight on the term) and README updated.
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
12. **Website "What's new":** every feature players would notice gets a short dated entry at the top of the
    "What's new" section of `website/index.html` (headline plus one or two sentences), and any website text it
    makes out of date is fixed. Bug fixes and internal changes don't need one.

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
