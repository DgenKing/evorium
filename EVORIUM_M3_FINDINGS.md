# Evorium Milestone 3 build report

## Done

- Phase 0: saved `evorium-backup-pre-m3.sqlite3`; added the database-path
  override, NPC/player/system kinds, a World account, and sortable sim timestamps.
- Phase 1: permanent timeline, filters, daily digests, timeline page and navigation.
- Phase 2: player profile, entering/leaving public places, replies, conversation
  notes, attributed learning, personal promises, idle and startup chat recovery.
- Phase 3: directed relationships, descriptive bands, familiarity, bounded
  feelings, promise consequences and timeline changes.
- Phase 4: public places, free-time checks, daily planning, visits, staying home,
  phone calls with one retry, promise fulfilment, per-place conversations and UI.
- Phase 5: persisted director toggle, stall detection, bounded proposals,
  validated scheduled events and chance-meeting plans.
- Phase 6: Simon Ferris, Brenda Ashworth and Mohammed "Mo" Iqbal, their routines,
  seed facts and relationships. New characters use initials.
  256×256 metadata-stripped portraits, Linux service files and updated README.

Each phase has its own local commit. Nothing has been pushed. `config.py` has
not been modified, staged or committed. Local credentials and databases remain
ignored. Scans of tracked files and historical Git blobs found no common secret
patterns. The original migrations 1–3 are unchanged.

Verification: **118 tests pass**, using fake model clients and temporary
SQLite databases. This includes a complete deterministic day with planning,
a two-NPC shop conversation, a daily digest and two player messages followed
by attributed facts and timeline records. An isolated server successfully
served the dashboard and timeline page. Both pages' JavaScript parses.
A migration-preservation test upgrades a version-3 world and retains its saved
conversation and pending event. The pre-M3 backup passes SQLite integrity checks.

## Not done or partly done

- The requested three-minute, 600× **real-API** smoke test is awaiting explicit
  approval. Automatic approval review rejected sending conversation-derived
  prompts from a copy of the live database to DeepSeek. No real API test started.
- The final live restart is also held pending that approval, because restored
  auto mode would send the new prompts to the same provider. The live server
  continues running its previous code; its database is still schema version 3.
  The new migrations will apply on the authorized restart.
- Both original seed events remain pending at their original times:
  Raj's call on 18 November 2026 at 11:00; Dez's letter on 19 November at 09:00.
  The original saved conversation remains intact. Auto mode is still saved on,
  at 1× speed with a 20-minute conversation gap.
- No browser rendering or screenshot inspection was performed. HTTP page
  serving, JavaScript syntax and interaction/API logic were checked.
- No new portraits were generated; the brief explicitly allows initials.

## Assumptions

- Planning tracks an explicit sim-day and phone retry count; real creation times
  alone cannot identify an accelerated simulation day. Empty or failed planning
  attempts leave a cancelled marker and are not retried that day.
- Plans end within their starting day and do not overlap. A missed visit does not
  retroactively happen when a tick first encounters it after its end time.
- Phone availability is checked when the plan executes. A busy or sleeping
  recipient gets one retry 30 sim-minutes later. Simon can take office calls.
- Chance meetings use the earliest valid half-hour at or after the proposed
  delay, within 24 hours, and must pass the normal visit rules for both NPCs.
- When multiple places are due, the oldest-served place gets the next global
  conversation, so an accelerated pub cannot continually starve the shop.
- Brenda's morning paper visits are Monday–Saturday because the shop is shut
  on Sundays. Simon and Brenda sleep 23:00–07:00. Mo drives each night and is
  off duty at home outside his stated sleep, shop, pub and driving periods;
  his unspecified home is labelled Manchester.
- The player's full open-promise list is shown in the UI; prompt lists retain
  their existing bounds. The 40-message limit reserves space for a whole reply.
- Director name validation is deliberately conservative: proper-name tokens
  must be established in seed material, the cast or the minor-NPC registry;
  letters/calls must identify a seeded or cast correspondent. Mundane incidents
  use the four categories specified by the brief. Additional wording checks
  reject attempted changes to lease or offer terms.
  A restart picks up configuration changes; no settings were added to the
  owner's `config.py`.
- No new dependencies, deployment, public hosting or Git push were performed.

## Real API spend

**$0.00 of build-triggered API calls.** The real smoke test was blocked before
execution. Existing activity by the already-running live server is separate.
The prepared real smoke test has a $0.20 additional estimated-spend cap, below
this brief's $0.30 limit; its result must be reported after approval and execution.
Normal planning/director/digest overhead is about ten calls per sim day; even
maximal validation retries for those overhead calls are bounded around 28.
Player replies and phone conversations incur their ordinary dialogue/notes calls.

## Known problems

- The installed Starlette/FastAPI test client emits a deprecation warning about
  its httpx integration. Tests pass; dependencies were left unchanged as required.
- The director's text checks are conservative heuristics, not a general natural
  language contradiction detector. Valid but unfamiliar wording can be dropped.
- Model-dependent quality, real-provider behaviour and accelerated live-world
  behaviour still need the requested approved smoke test.

## How to try it

After the approved live restart:

1. Open `http://127.0.0.1:8000`, edit your name/about in **You**, enter an open
   place, select someone present, send two messages and end the conversation.
2. Expand a character card's **Relationships** list. Hover a relationship to see
   its latest reason; make and resolve a player promise to see a consequence.
3. Turn on **Let them live** and advance time past 07:00; inspect **Today's plans**
   on a card. Empty days are normal. The location strip shows public encounters.
4. Follow **Timeline**, inspect recorded events and filter by character or
   importance. A digest appears after midnight for a qualifying prior day.
5. Toggle **Director** off and on. It persists across restarts and only proposes
   an event in auto mode after a genuine stall with no imminent seeded event.
