# EVORIUM — Build Brief for Milestone 1 (for ChatGPT)

You are the lead developer on Evorium. Read `EVORIUM_CORE_IDEA.md` first — it is the vision. This brief tells you exactly what to build **now** and what to leave alone.

## Your job in one sentence

Build the smallest working slice: **two AI characters in one Manchester pub exchange a short conversation via the DeepSeek API, it is saved to SQLite, shown in a browser, and survives a restart.**

Nothing else. No five agents, no scheduler, no AI director, no map, no voice.

## Hard constraints

1. **Python 3.11+, FastAPI, SQLite, plain HTML/JS.** No React, no ORM beyond `sqlite3` or SQLModel, no Docker, no Redis.
2. **API key lives in `config.py`, hardcoded, and `config.py` is in `.gitignore`.** Do NOT use `python-dotenv` or `.env` files — they load the wrong file on this machine. Ship a `config.example.py` with a placeholder.
3. **Budget cap is non-negotiable.** Every DeepSeek call records input tokens, output tokens and estimated USD cost in the DB. If cumulative estimated spend reaches `MAX_SPEND_USD` (default 4.00 of the $5 credit), refuse new calls and surface the error in the UI.
4. **The model proposes; Python decides.** The LLM returns JSON only. Parse and validate it against a schema before anything touches the DB. On invalid JSON, retry once, then log and skip.
5. **One API key, one account, both agents.** Characters are separated by DB records and prompt context only.
6. **Keep it runnable at every step.** `python -m evorium` (or `uvicorn`) must start the app after each commit.

## Directory layout (create only these)

```
evorium/
  config.example.py      # DEEPSEEK_API_KEY = "sk-..." ; MAX_SPEND_USD = 4.00
  config.py              # gitignored, user fills in
  .gitignore
  requirements.txt       # fastapi, uvicorn, httpx, pydantic, pytest
  README.md              # how to run, how to set the key
  evorium/
    __init__.py
    main.py              # FastAPI app + static UI
    db.py                # schema creation, connection helper, migrations list
    models.py            # pydantic: Agent, Message, LLMCall, ActionProposal
    llm.py               # DeepSeek client, usage tracking, budget guard
    sim.py               # run_conversation(agent_a, agent_b, turns=4)
    prompts.py           # system/user prompt templates
    seed.py              # creates the two characters if absent
    static/index.html    # dashboard
  tests/
    test_db.py
    test_llm_guard.py    # budget cap + JSON validation, using a fake client
    test_sim.py
```

## Database schema (SQLite)

- `agents(id, name, age, occupation, background, personality, current_goal, mood, location, created_at)`
- `messages(id, conversation_id, speaker_id, text, rationale, sim_time, created_at)`
- `conversations(id, location, started_at, ended_at, status)`
- `llm_calls(id, agent_id, model, input_tokens, output_tokens, est_cost_usd, ok, error, created_at)`
- `memories(id, agent_id, content, importance, source_conversation_id, created_at)` — write one memory per agent at the end of each conversation summarising what happened. This is the seed for Milestone 3.

## The two seed characters

Keep them distinct and local. Suggested (change if you want, but stay in Manchester):

- **Dez Whitworth**, 54, landlord of The Crooked Billet, Ancoats. Dry, loyal, worried about the pub's lease. Goal: find out whether the new landlord is going to raise the rent.
- **Priya Kaur**, 29, junior architect, regular at the pub. Optimistic, talkative, just moved from Leicester. Goal: make friends in the city and find a flat she can afford.

## LLM contract

Model: `deepseek-chat`. Endpoint is OpenAI-compatible (`https://api.deepseek.com/chat/completions`). Use `httpx` directly — do not add the `openai` package. Temperature 0.8, `max_tokens` 300, `response_format={"type":"json_object"}`.

Each turn, the agent receives: its identity, personality, goal, mood, the location, the last N messages in this conversation, and up to 3 of its most recent memories. It must reply with:

```json
{
  "say": "one or two sentences of dialogue",
  "rationale": "one short sentence on why they said this",
  "mood": "one word"
}
```

Validate with pydantic. Store `say` as the message, `rationale` in the rationale column, update `agents.mood`.

Check current DeepSeek pricing and put the per-million-token rates in `config.py` as constants so cost estimation is easy to correct.

## Dashboard (static/index.html)

One page, no framework:

- Two agent cards: name, occupation, mood, current goal.
- A "Run conversation" button that calls `POST /conversations/run` (4 turns, alternating speakers).
- The conversation transcript, each line showing speaker, text, and a small greyed-out rationale.
- A footer strip: API calls, total tokens, estimated spend, remaining budget.
- An error area that shows the last error plainly.

Endpoints: `GET /agents`, `GET /conversations/latest`, `POST /conversations/run`, `GET /usage`. Polling every 2 seconds is fine; no WebSockets yet.

## Tests that must pass

- Schema is created on first run and idempotent on second run.
- Budget guard blocks a call when `est_cost_usd` total ≥ `MAX_SPEND_USD`.
- Malformed JSON from the model is rejected and does not write a message.
- `run_conversation` with a fake LLM client writes 4 messages and 2 memories.

Tests must never hit the real API — inject a fake client.

## Definition of done

1. `pip install -r requirements.txt`, fill in `config.py`, start the app, open the browser, click "Run conversation", see a plausible 4-turn exchange between Dez and Priya with rationales.
2. Stop the server, start it again: both agents, the transcript and the usage numbers are still there.
3. `pytest` is green.
4. Total real spend to get here is under **$0.20**.

## Work in this order, and stop after each step to show me

1. Repo skeleton, `config.example.py`, `.gitignore`, `db.py` with schema, `seed.py`. Tests for schema.
2. `llm.py` with budget guard and JSON validation, tested against a fake client. No real calls yet.
3. `sim.py` + `prompts.py`, tested with fake client.
4. FastAPI endpoints + `index.html`.
5. First real DeepSeek call. Report tokens and cost.

## Do not

- Add agents three to five, schedules, a world clock, or autonomous ticks — that is Milestone 2.
- Add player chat — Milestone 3.
- Add any paid service, vector DB, embedding model or LangChain.
- Put the API key anywhere in frontend code, logs or git.
- Invent requirements. If something is unclear, ask one concise question and propose a default.

When Milestone 1 is done and demonstrated, we will write the Milestone 2 brief together.
