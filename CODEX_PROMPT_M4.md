# Evorium M4: decisions and consequences (build brief for Codex)

## 0. Read this first

Evorium is an AI social simulation of eight characters on one terrace in Ancoats, Manchester:
The Crooked Billet pub, Patel's News, and an empty unit between them. It's a Python 3.11+
FastAPI app with SQLite, plain HTML/JS and DeepSeek (`deepseek-flash`, JSON mode). Read
`EVORIUM.md` (whole project) and `README.md` before starting. Then read these files, because
you will change them: `evorium/plans.py`, `director.py`, `memory.py`, `models.py`,
`prompts.py`, `sim.py`, `tick.py`, `world.py`, `places.py`, `seed.py`, `db.py`, `timeline.py`,
`relationships.py`, `main.py`, `static/index.html`, `static/map.js`.

**Today the characters talk well, but they don't do anything.** Raj has a £45,000 offer to
give up his shop and hasn't decided. Dez has a renewal letter at £3,900 a month (up from
£2,400) and no plan. The quiz is "coming back", but nothing makes it happen. Nothing they say
changes the world.

**Goal of M4:** characters make real decisions, Python applies real consequences, the
Northgate story can end in different ways, and a returning player gets a "while you were
away" catch-up.

### The core rule, unchanged: the model proposes, Python decides

- The model only ever picks from a **fixed menu of actions**, with arguments.
- Python checks every proposal (who, where, when, money, cooldowns, evidence). If it fails,
  Python drops it and logs why with `emit(..., "error")`.
- Python applies every effect. The model never writes numbers into the world directly, and
  never decides an outcome.
- Hidden limits (Simon's real authority, his rent floor) live only in Python and in Simon's
  own prompt. They are never shown to anyone else.

### Project rules (must follow)

- **Never lose or reseed the live `evorium.sqlite3`.** Migrations in `db.py` `MIGRATIONS`
  are append-only; the current schema is version 9, so yours start at 10. Existing saves
  must migrate in place and keep all history.
- **No new dependencies.**
- **Tests never call the real API.** Use a fake client like the existing tests do.
- **Never print, log or commit the API key.** Don't touch `config.py`; put new settings in
  `config.example.py` and read them with `getattr(config, NAME, default)`.
- **No dotenv.**
- Escape every string shown in HTML with the existing `esc()`.
- **No "Home" link in any navigation.**
- **Don't commit.** Leave the changes in the working tree; the owner commits.
- Don't touch `Ancoats_Blender_Unreal_Kit.zip`.
- Keep the existing code style: short modules, small functions, pydantic models with
  `extra='forbid'` for model output.
- All money is whole pounds (integers) unless stated. All sim times use `memory.DUE_FMT`.
- Every new emitted line and timeline entry must read well to a non-programmer.

Build in the phase order below. Run `python -m pytest -q` and `node tests/map_view.test.cjs`
after each phase; all existing tests must keep passing (update a test only where M4
deliberately changes behaviour, and say so in your summary).

---

## Phase 1: stop the failure storm (small, do first)

On 19 Nov, DeepSeek failed for 5 minutes and auto mode created 23 empty "failed"
conversations, one every tick.

- In `main._tick_loop`, after an `LLMError` that is **not** budget or balance, pause all
  model calls with backoff: 1 real minute, then 2, 4, 8, capped at 15. Reset after the first
  successful call. Non-model work (routines, events, plans without calls) keeps running.
- Emit one line when the pause starts ("DeepSeek isn't answering; trying again in 2
  minutes.") and one when it recovers. Don't emit once per tick.
- Show the pause in `/usage` as `model_paused_until` (real time), and in the dashboard
  header as a small note.
- Conversations that fail before any line was spoken: keep the row (never delete), but
  exclude them from the timeline, the conversation list and the map. Add a test.

---

## Phase 2: the world ledger (numbers that matter)

New module `evorium/economy.py`. Migration 10 adds:

```
stats(key TEXT PRIMARY KEY, value INTEGER NOT NULL, visible_to TEXT NOT NULL, updated_at TEXT NOT NULL)
stat_changes(id INTEGER PRIMARY KEY, key, old INTEGER, new INTEGER, reason TEXT, sim_at TEXT, action_id INTEGER NULL)
offers(id INTEGER PRIMARY KEY, kind TEXT CHECK(kind IN ('surrender','renewal','loan','job')),
       from_id, to_id, amount INTEGER, terms TEXT, status TEXT CHECK(status IN ('open','accepted','refused','expired','withdrawn')),
       created_at TEXT, expires_at TEXT, resolved_at TEXT NULL, source_action_id INTEGER NULL)
notices(id INTEGER PRIMARY KEY, place TEXT, text TEXT, by_id INTEGER, since TEXT, until TEXT NULL)
```

`visible_to` is `public`, `pub_regulars`, or a comma-separated list of agent names. Only
characters who could plausibly know a number get it in their prompts. Dez knows his savings;
Jess knows her shifts; everyone in the pub sees the beer price and the quiz poster.

### Starting values (as constants in `economy.py`, so they can be tuned)

| Key | Start | Visible to |
|---|---|---|
| `pub.pint_price_p` | 460 (pence) | public |
| `pub.rent_month` | 2400 | Dez, Simon |
| `pub.lease_end` | 2027-03-25 (Lady Day quarter day; store as a sim date in a text-valued twin table or as days since epoch — your choice, be consistent) | Dez, Simon, Jess |
| `pub.savings` | 6000 | Dez |
| `pub.takings_last_week` | computed | Dez, Jess |
| `pub.quiz` | 0 = none, 1 = announced, 2 = running weekly | public |
| `pub.quiz_questions_ready` | 0 (Tommy fills it) | Tommy, Dez, Jess |
| `jess.shifts` | 4 (bar nights per week) | Jess, Dez |
| `jess.job_hunting` | 0 | Jess |
| `shop.open` | 1 | public |
| `raj.savings` | 18000 | Raj |
| `terrace.petition` | 0 (signatures) | public once started |
| `mo.darts_signups` | 0 | public once started |
| `chloe.flat_found` | 0 | Chloe |

### Weekly settlement

Every sim Sunday at 23:59, settle the pub's week in pure Python (no model call). Use these
starting constants:

- **Pints sold:** base 700 a week.
  - Each 10p above 460 cuts pints by 4%; each 10p below adds 3%.
  - Quiz running adds 110 pints.
  - Fewer than 3 Jess shifts cuts pints by 8% (slow service).
  - Each regular who has a "falling out" with Dez (warmth band cold or worse) cuts 15 pints.
- **Revenue:** pints × price, plus £300 food.
- **Costs:**
  - stock at 40% of revenue
  - Jess at £12.21/hour × 6 hours × shifts
  - £450 overheads
  - `rent_month × 12 / 52`
  - Dez's own drawings, £500
- **Savings** change by revenue minus costs. Record `takings_last_week` and one
  `stat_changes` row with a plain-English reason.

**Target behaviour, which tests must check:**
- At the current rent and price, the week is a small profit (roughly +£200 to +£400).
- At £3,900 rent with nothing else changed, it is a clear loss (roughly −£100 to −£300).
- A running quiz plus a 20p rise can close most of that gap.
- Every lever costs something: a price rise annoys regulars (see Phase 4), and extra shifts
  cost wages.

Tune the constants to hit these targets, and keep them in one block at the top of
`economy.py`.

### Rent and the lease

- Rent stays £2,400 until `pub.lease_end`.
- On `lease_end`:
  - if Dez has an **accepted** renewal offer, rent becomes that offer's amount;
  - if not, the pub closes (see the endings in Phase 6).
- If `pub.savings` falls below −£2,000 at a settlement, the pub closes as "bust". Dez gets
  one warning timeline entry when savings first go below £1,000.

### Migrating the live world (important)

Write `economy.ensure(db_path, now)`, idempotent like `seed_events`, called at startup:
- Create missing stats with the starting values.
- If seed event `northgate-figures` has been **delivered** and no renewal offer exists,
  create an open `renewal` offer:
  - from Simon to Dez, £3,900
  - `terms`: "new lease from 25 March 2027"
  - `expires_at` = delivery time + 28 days (the letter says "reply within 28 days")
- If seed event `raj-figure` has been delivered and no surrender offer exists, create an open
  `surrender` offer:
  - from Simon to Raj, £45,000
  - `expires_at` = delivery time + 30 days
- If those events are not delivered yet, create the offers inside `tick.deliver_events` at
  delivery time instead.
- **Simon's hidden limits:** maximum surrender £60,000, minimum rent £3,300, as constants.
  Python rejects any of Simon's own offers beyond them. Simon's prompt shows them as "your
  authority: up to £60,000 / no lower than £3,300". Nobody else ever sees them.

Offers expire automatically in the tick: status `expired`, an importance-4 timeline entry,
and an observed fact for both parties.

---

## Phase 3: the action menu

New module `evorium/actions.py`, with a registry of actions as data plus small Python
functions. Each action defines:
- `key`
- `who`: names allowed, or `"any"`
- an args schema (a pydantic model, `extra='forbid'`)
- `check(c, actor, args, now)`, which raises `ValueError` with a readable reason
- `apply(c, actor, args, now)`, which returns a list of effects
- `importance` (1–5)
- `big` (bool)
- `cooldown_hours`
- `witnesses`: who learns of it directly — `target`, `place`, `public`, or `none`

Migration 11 adds:

```
actions(id INTEGER PRIMARY KEY, agent_id, key, args_json, reason, status TEXT CHECK(status IN ('considering','done','rejected')),
        trigger TEXT CHECK(trigger IN ('plan','conversation','reaction','player')), evidence TEXT, sim_at, conversation_id NULL, result TEXT)
```

Status `rejected` keeps the reason so the owner can see what the model tried.

### Actions to build

| Who | Action | Args | Python checks | Effects |
|---|---|---|---|---|
| Dez | `change_pint_price` | pence −30..+50, not 0 | at most once a week | stat; public notice in pub; regulars' facts on next visit |
| Dez | `set_jess_shifts` | 2..6 | not the same as now; once a week | stat; Jess's routine changes (Phase 4); Jess gets a fact; relationship change Jess→Dez |
| Dez | `announce_quiz` | — | quiz is 0 | `pub.quiz`=1; pub notice "Quiz night returns Thursday 8pm" |
| Dez | `start_quiz` | — | quiz 1 and `quiz_questions_ready` ≥ 40 | `pub.quiz`=2; Thursday routine change (Phase 4) |
| Dez | `ring_northgate` | — | Simon reachable rules as `plans` phone | schedules a phone plan with Simon within 3 hours |
| Dez | `counter_rent` | amount 2400..3899 | open renewal offer exists | creates a pending ask Simon must answer (reaction for Simon) |
| Dez | `accept_renewal` **big** | offer_id | open renewal to Dez | offer accepted; future rent set; ending flag (Phase 6) |
| Dez | `refuse_renewal` **big** | offer_id | open renewal to Dez | offer refused; Dez starts "looking for a new place" goal |
| Dez | `ask_loan` | person, amount 500..10000 | person is an NPC with ≥ amount savings stat, or any NPC if unknown | creates a `loan` offer the other must answer |
| Raj | `accept_surrender` **big** | offer_id | open surrender to Raj | offer accepted; shop closes 30 days later (`shop.open`=0, `places.is_open` false); Raj's routine changes; raj.savings += amount |
| Raj | `refuse_surrender` **big** | offer_id | open | offer refused; Simon gets a reaction |
| Raj | `ask_more` | amount 45001..90000 | open offer | pending ask; Simon reacts |
| Raj | `warn_neighbours` | — | not done before | told-facts to Dez, Brenda and Tommy ("Raj says Northgate own the whole terrace") on their next encounter, or immediately if they're in the shop or pub |
| Simon | `raise_offer` | offer_id, amount ≤ hidden max | open offer from Simon | new amount; old offer withdrawn; new offer, same expiry |
| Simon | `offer_rent_deal` | amount ≥ hidden floor, years 1..10 | open renewal | replaces the renewal offer |
| Simon | `set_deadline` | offer_id, days 3..14 | open, and doesn't extend | shorter expiry; fact for the other party |
| Jess | `ask_more_hours` | — | once a week | pending ask; Dez reacts |
| Jess | `start_job_hunt` **big** | — | not already | `jess.job_hunting`=1; after 14 sim days, if still hunting and shifts ≤ 4, Jess gets a `job` offer elsewhere (Python, not model) and must decide |
| Tommy | `write_quiz_questions` | count 5..20 | quiz announced or agreed with Dez (has a fact or commitment about it) | `quiz_questions_ready` += count (max 60) |
| Brenda | `start_petition` | text ≤120 | not already | `terrace.petition`=1; notice in the shop and the pub |
| any | `sign_petition` | — | petition exists, not signed | +1 |
| Mo | `start_darts_team` | — | not already | notice in pub; signups via `join_darts` |
| any | `join_darts` | — | darts started | +1 signup |
| any | `answer_ask` | ask_id, yes/no | ask is to them | resolves Dez's counter, Raj's ask-more, loans, Jess's hours |
| any | `tell` | person, fact_id | actor knows the fact (importance ≥3); not already told today | a `told` fact for the person, attributed |
| any | `wait` | — | — | nothing; logged with reason (a valid choice) |

Represent "pending asks" either as `offers` rows (kind and status fit) or a small `asks`
table in the same migration — your call; keep it simple. An unanswered ask expires after 72
sim hours with a fact for the asker ("Simon hasn't replied").

**Every applied action produces:**
- a timeline entry (`kind='action'`, the action's importance);
- an `observed` fact for the actor (importance 4 for big actions, 3 otherwise);
- facts for its direct witnesses;
- any relationship changes, through `relationships.adjust` with a plain reason;
- an `emit` line.

Others learn only through witnessing or conversation. Never broadcast.

### Relationship effects (deterministic)

| Action | Effect |
|---|---|
| Shifts cut | Jess→Dez trust −6, warmth −4 |
| Shifts raised | Jess→Dez trust +4, warmth +4 |
| Price up ≥20p | each regular's warmth to Dez −2, on their next visit |
| Raj warns neighbours | each neighbour's trust in Raj +5 |
| Raj accepts without warning anyone | when they find out, each neighbour→Raj trust −8 |
| Loan given | asker→lender warmth +8 |
| Loan refused | asker→lender warmth −3 |
| Quiz starts | Tommy→Dez warmth +6 |

---

## Phase 4: the world reacts (routines, notices, noticing)

- `world.py` routines read stats:
  - Jess works `jess.shifts` evening bar shifts, chosen in a fixed order: Thu, Fri, Sat, Sun,
    Wed, Tue.
  - When `pub.quiz`=2, Tommy, Mo, Brenda and Chloe are in the pub Thursday 19:30–22:30 if
    otherwise free.
  - When `shop.open`=0, Raj is at home, and `places.is_open('shop', ...)` is false.
  - Keep the functions pure apart from reading stats, and pass stats in where practical so
    tests stay simple.
- **Notices:** when a character is first present at a place after a notice was posted or a
  price changed, they get one observed fact ("The Billet's pint has gone up to £4.80",
  "There's a petition about the terrace on Patel's counter"). This is how news spreads
  without the model.
- `knowledge_for_prompt` gets a new section, `situation`: the stats and open offers this
  speaker can see, phrased in words ("Your savings: about £5,800", "Raj has an open offer of
  £45,000 from Northgate, expires 18 Dec"). Keep it to 6 lines or fewer.
- Add the situation to the dialogue prompt in `prompts.py` under a short heading. People in
  a business crisis talk about it, but the "topics already covered today" rule still applies.

---

## Phase 5: when characters decide

Three entry points, all ending in the same `actions.propose(...)` → `check` → `apply` path.

### 1. Morning plan (`plans.daily`)

- `DailyPlans` gains `actions: list` with at most 1 entry: `{"action": key, "args": {...},
  "reason": "...", "evidence": [fact ids]}`.
- The prompt lists only the actions this character could take **today**, already filtered
  through `check`, with their args described, plus the situation lines.
- "Most days, do nothing" still holds: an empty list is normal.

### 2. In conversation (`memory.store_extraction`)

- The note-taking schema gains a per-speaker `decision` (optional, at most one): `{action,
  args, quote}`.
- Python accepts it only if `quote` appears **verbatim** (case-insensitive, at least 6 words)
  in a line that **speaker** actually said in the transcript, and the action passes `check`.
  This stops the note-taker inventing decisions.
- Update the extraction prompt and the example JSON. Remember that the example JSON is what
  the model copies: last milestone, a missing key in the example silently broke feelings.

### 3. Reaction call (new: `evorium/decide.py`)

- **Triggers** (each schedules one reaction for the affected character between 1 and 36 sim
  hours later; record it in a `reactions` table in migration 11, or reuse `scheduled_events`
  with a new origin):
  - an offer or ask arrives
  - an offer is 3 sim days from expiry
  - an importance-5 fact arrives
  - a deadline is changed
  - a petition or notice that concerns them goes up
- **The call:**
  - The prompt holds the character, personality, mood, goal, situation, relevant facts
    (importance ≥4, with ids), relationships in band words, open offers and asks with ids,
    and the valid actions now.
  - It asks them to think as this person would, about money, family, loyalty, pride and
    fear, and return `{"action": key, "args": {...}, "reason": "...", "evidence": [fact
    ids], "new_goal": null | "≤120 chars"}`.
  - `max_tokens` 350, temperature 0.6.
- **`wait` is always allowed.** Waiting past an expiry is a decision with a consequence: the
  offer expires.

### Guards (all in Python)

- **One acted action per character per sim day** (any trigger), plus at most one `tell`.
- **No more than 2 big actions in the whole world per sim day.**
- **Big actions must be slept on.**
  - The first time a big action is proposed, store it as `considering` (with an emit:
    "Raj is seriously thinking about accepting Northgate's offer").
  - It can only become `done` if the same character proposes it again at least 12 sim hours
    later, through any trigger.
  - Schedule a follow-up reaction ~16 sim hours later so it gets reconsidered.
  - The `considering` state appears in that character's own prompt ("You were leaning
    towards…").
- **Big actions need evidence:** at least one fact id that belongs to the actor and has
  importance ≥4. Otherwise reject them with a reason.
- **`new_goal`** is accepted at most once per sim day per character, ≤120 chars, and stored
  on the agent row. Log the old goal in the timeline (importance 2).
- **Rejected proposals are kept** in `actions` with status `rejected` and the reason, never
  silently lost.
- **Call budget:** at most 1 reaction call per character per sim day (2 if an offer expires
  within 48 sim hours), and at most 12 reaction calls in the world per sim day. Over budget,
  the reaction is postponed to the next sim day. Respect the Phase 1 backoff.

---

## Phase 6: story arcs and endings

Migration 12 adds `arcs(id, key UNIQUE, status TEXT CHECK(status IN ('active','resolved')),
started_at, resolved_at, outcome TEXT, summary TEXT)`. `economy.ensure` creates the
`northgate` arc as active.

**Northgate is resolved by Python, at the first of these moments:**

| When | Outcome |
|---|---|
| Dez's renewal accepted, and Raj's surrender resolved (accepted, refused or expired) | `renewed` (with the rent) plus Raj's outcome |
| `lease_end` arrives without an accepted renewal | `pub_closed` |
| Savings below −£2,000 | `pub_bust` |
| Raj's surrender resolved and Dez's renewal refused or expired | Dez has 14 sim days to find an answer (`counter_rent` or a new `offer_rent_deal` from Simon). Otherwise `pub_closed` at lease end |

**On resolution:**
1. Python writes the outcome.
2. One model call (narration only, `max_tokens` 300) writes a 3–4 sentence "how it ended",
   given the facts and the outcome. It cannot change anything; Python provides a plain
   fallback if the call fails.
3. Record an importance-5 timeline entry, and give every NPC an observed fact.
4. If the pub closed: Dez's and Jess's routines become home, `world.pub_open` returns false
   (keep a stat `pub.closed`), and the map shows the pub shuttered. Nothing is deleted.

**After resolution, the director may start the next arc** after at least 2 sim days. Ship two
small arc templates as data:
- `darts_league` (Mo needs 6 signups before a league deadline);
- `chloe_flat` (Chloe has 3 weeks to find a flat she can afford, with an offer from a
  landlord the director can introduce through its existing event types).

Each template has seed facts, stats and a resolution rule. Keep the template format simple,
so the owner can add more later.

**Director changes (`director.py`):**
- `stall_report` treats an open offer, a pending reaction or a `considering` action as "not
  stalled".
- The director prompt includes the active arc and its stats.
- It still cannot set money terms or invent people, and it must never resolve an arc or
  perform an action. Test this.

---

## Phase 7: "While you were away" catch-up

- Migration 13 adds `last_seen_at` to the player's agent row.
  - `GET /catchup` returns everything since `last_seen_at`:
    - timeline entries of importance ≥3, at most 15;
    - stat changes in plain words;
    - offers opened or resolved;
    - actions done;
    - facts where an NPC's content mentions the player's name ("what people say about you",
      at most 5).
  - `POST /catchup/seen` updates `last_seen_at`.
- If there are 3 or more items, one model call (`max_tokens` 250) writes a "Previously in
  Ancoats" paragraph of 4–6 sentences. Cache it by (`last_seen_at`, latest timeline id), so
  reloading doesn't call again. At most one catch-up call per real 10 minutes; fall back to
  the bullet list.
- **Dashboard:** a dismissable panel at the top on load, when the sim gap is ≥2 sim hours and
  there are items. It shows the paragraph, then the bullets. Dismiss calls `/catchup/seen`.
  Keep the existing browser "last visit" for the Timeline page as it is.

---

## Phase 8: dashboard and map

- **A "The terrace" card on the dashboard:**
  - lease countdown (days to 25 Mar 2027);
  - open offers with amounts and expiry countdowns;
  - pint price;
  - quiz state;
  - Jess's shifts;
  - the petition and darts counts once started;
  - last week's takings;
  - Dez's savings, with a small note: "only Dez knows this".
  - The dashboard is the owner's god view, so private numbers are fine there, but say whose
    knowledge they are.
  - It shows the arc status and, once resolved, the ending text.
- **Each NPC card:**
  - "Today: …" with the action they took, if any;
  - "Thinking about: …" for a `considering` action.
  - Rejected proposals appear only in the live feed.
- **Timeline:** the new kinds (`action`, `offer`, `arc`) get filter chips.
- **Map (`map.js`):**
  - notices appear as a small sign on the pub or shop;
  - a closed shop or pub is drawn shuttered;
  - the popup shows "Today: …".
  - Keep the map read-only, with no new polling: add fields to the existing payloads.
- **New API:** `GET /world/ledger` (stats, offers, notices, arc) and `GET /actions?since=`.
  Extend `GET /agents` with `today_action` and `considering`.

---

## Phase 9: tests (fake client only)

**Add tests for at least:**
- **Settlement:** the profit at £2,400, the loss at £3,900, and the gap-closing levers.
- **`economy.ensure` on a world where both seed events were already delivered** (as in the
  live DB): the offers are created once, with the correct expiries (28 and 30 days), and it's
  idempotent.
- **Each action's `check`:** rejects wrong person, wrong place or time, out-of-range args,
  Simon beyond his hidden limits, and cooldowns.
- **Each action's `apply`:** stats, facts for the actor and witnesses, relationship deltas,
  timeline.
- **A conversation decision needs a verbatim quote from that speaker.** It is rejected when
  the quote is from the other person or invented.
- **Sleep-on-it:** a big action becomes `considering` and needs ≥12 sim hours and a second
  proposal; a big action without evidence is rejected.
- **The daily limits:** per character and world-wide big actions.
- **Reaction triggers and budget:** postponed when over budget.
- **Offer expiry:** status, facts, timeline.
- **Routines:** Jess's shifts and the quiz Thursday; the shop closed after Raj accepts.
- **Notices:** the first visit creates one fact, the second creates none.
- **Northgate endings:** each outcome path, with narration fallback when the model fails;
  the director cannot resolve arcs or act.
- **Catch-up:** items since `last_seen_at`, caching (no second call), fallback.
- **Phase 1 backoff:** no conversation rows during the pause; non-model work continues.
- **Migrations 10–13** apply cleanly to a copy of a version-9 database with existing
  conversations, facts and delivered events, and keep all rows.
- **One offline smoke test that runs a few sim days of the Northgate story with a scripted
  fake client:**
  - Raj considers, then refuses;
  - Simon raises the offer to £55,000;
  - Raj accepts;
  - Dez counters at £3,400, Simon answers with a deal at £3,500, and Dez accepts;
  - the arc resolves as `renewed`.
  - Check the facts and timeline at each step.

---

## Phase 10: documentation and summary

- **README:** add a short "Decisions and consequences" section covering what characters can
  do, how Python checks it, the sleep-on-it rule, the daily limits, the endings, and the
  catch-up. Add the new model calls and their token limits to the existing call-limits
  paragraph.
- **EVORIUM.md:** add M4 to the history; update "State today", "How it works", "Known issues"
  and "Next steps".
- `config.example.py`: any new tunables, with comments.
- **Your final message:** list the files changed, the migrations added, the tests added and
  their result, any test you changed and why, and anything you didn't finish or deliberately
  simplified. Don't commit.

### Cost guardrails (check your design against these)

- New model calls per sim day across the whole world are at most:
  - about 12 reaction calls;
  - 1 catch-up call;
  - 1 narration per arc ending.
- Plan and extraction decisions add fields to calls that already happen, not new calls.
- At about $0.00015 per call, this should add well under 1 cent per sim day.
