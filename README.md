# Evorium — Milestone 1

Two persistent characters in a Manchester pub. Built with Python 3.11+,
FastAPI, SQLite and (in step 4) plain HTML/JavaScript.

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
README and seeds Dez Whitworth and Chloe Barlow if absent. Stop with Ctrl+C;
restarting reuses the database and preserves existing character state.

Edit `config.py` locally to set `DEEPSEEK_API_KEY`. The key is hardcoded only in
that ignored file; no `.env` files are used.
Do not put credentials in frontend code, logs, or version control.

## Status: Milestone 1 complete (2026-11-15)

All five steps of `EVORIUM_BUILD_BRIEF_M1.md` are done:

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

Next: Milestone 3 — the player walks into the pub.

Token-rate constants are editable in `config.py`. Verified on 2026-11-15 against
[DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/): peak uncached
input $0.30 and output $1.20 per million tokens. Estimates use these conservative
rates; cache hits and off-peak calls can cost less. Calls without provider usage
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
