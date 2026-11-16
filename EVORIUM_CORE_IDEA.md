# EVORIUM — Core Project Vision

> **Working title:** Evorium (name and trademark availability not yet verified)  
> **Project type:** AI-driven, persistent single-player social simulation, with a long-term open-world game ambition  
> **Development environment:** Visual Studio Code on Ubuntu, with AI coding agents  
> **Initial AI provider:** DeepSeek API (starting credit budget: US$5)  
> **Status:** Concept and prototype planning

## 1. The core idea

Evorium is a game in which non-player characters are not merely scripted dialogue trees or fixed routines. They are autonomous AI-driven agents with individual personalities, goals, beliefs, memories, relationships and circumstances. They observe a simulated world, make decisions, interact with one another and respond to the player. Their experiences can change their future behaviour.

The defining question is:

**Given everything this character knows, wants and remembers, what would they decide to do next?**

The aim is to create a living, persistent world where interesting stories emerge from character interactions and player choices rather than being entirely prewritten. This is a design goal, not a claim that the agents are conscious or that all outcomes can be left uncontrolled.

**Long-term vision:** A convincing, explorable recreation of Manchester populated by AI characters whose lives continue beyond the player's immediate view. The initial release is single-player. Multiplayer is a possible future consideration, not part of the first build.

## 2. Start small: prove the simulation before building the city

The first deliverable is **not** a full 3D game. It is a small working experiment: five AI characters in a simple shared location, such as a Manchester pub or neighbourhood, with a browser dashboard through which a human can observe and interact.

The experiment must allow us to:

1. Create five distinct agents with different personalities, goals and backgrounds.
2. Let them act and talk to each other without the player prompting every interaction.
3. Record events, conversations, memories and changing relationships.
4. Enter the simulation as a player, speak to an agent and influence events.
5. Leave the agents running, return later and see what has changed.
6. Pause, resume and accelerate simulated time.
7. Inspect *why* a character made a decision using concise, recorded decision explanations (not hidden model reasoning).
8. Track API calls, token consumption and estimated spending.

**Proof of concept:** After simulated days of activity, the agents should demonstrate coherent, observable changes in plans, relationships and beliefs, with consequences from player interactions that persist into later encounters. They should not merely produce endless, repetitive chat.

## 3. Character model

Every agent has a persistent record containing:

- **Identity:** Unique ID, name, age (if relevant), occupation, background and current circumstances.
- **Personality:** Traits, values, temperament, communication style and preferences.
- **Goals:** Immediate needs, medium-term plans and longer-term ambitions, with priorities.
- **State:** Location, activity, mood, energy, resources, schedule and availability.
- **Relationships:** Other characters, familiarity, trust, affection, conflict and interaction history.
- **Memory:** Significant events, past conversations, commitments and personal experiences.
- **Beliefs:** What the character thinks is true, where they learned it and how confident they are; beliefs may be wrong.
- **Knowledge boundaries:** A character should not automatically know events they did not witness or hear about.

Characters may form friendships, fall out, cooperate, spread rumours, make promises, change opinions or pursue personal goals. These are possible behaviours arising from simulation rules and model decisions, not guaranteed outcomes.

## 4. How the simulation works

### The core loop

1. Advance the world clock and update deterministic state (locations, schedules, resources and pending events).
2. Identify which agents have a reason or opportunity to act.
3. Retrieve each selected agent's relevant identity, goals, memories, relationships and current observations.
4. Ask the DeepSeek model for a **structured proposed action**, short dialogue if needed, and a concise decision rationale.
5. Validate the proposal against world rules, available actions, knowledge and resources.
6. Apply valid actions to the authoritative simulation state; reject or revise invalid ones.
7. Persist the event and update affected characters' memories, relationships and goals.
8. Update the dashboard and continue according to the simulation speed and API budget.

**Critical rule:** The language model proposes; the simulation validates and decides what actually happens. The AI must not directly overwrite arbitrary game state, invent possessions, teleport characters or declare other people's private thoughts as facts.

### Avoid constant model calls

Agents should **not** each call the API every second. Ordinary movement, scheduled work, sleep and routine tasks can be simulated in Python. Call the language model when there is a meaningful decision, interaction, conflict, unexpected event or need to plan. Use event-driven scheduling, cooldowns, conversation limits and summaries to control costs.

### Time and persistence

Simulated time is separate from real time. The user can pause or accelerate it. When the app is closed, the initial prototype may pause and resume from saved state; continuous 24/7 hosting is **not** required. A later version may run continuously on a server.

## 5. Player interaction

The player is an external participant in the simulation, not an all-knowing controller of every NPC.

In the first prototype, the player types messages to an individual agent or joins a shared conversation. The agent responds using its personality, relevant memories and knowledge. The player can introduce information, ask questions, make promises, offer opportunities and influence relationships. Other characters only learn about these events if present, told later or informed through a world event.

**Natural voice conversation** is a long-term goal. For the first version, text chat comes first; speech-to-text and text-to-speech are added only after the underlying simulation is reliable.

## 6. Emergent stories and the AI director

Evorium should create conditions for stories rather than depend on a fixed mission script. A character may need work, misunderstand a friend, seek help or make a decision that affects someone else. Such events can produce further consequences.

A future **AI director** monitors the world for stalled activity, emerging tensions, interesting relationships and opportunities. It can propose plausible events, but a rules engine must validate them. The director must not force every character into drama, break continuity or erase player agency.

The director is **not required for milestone one**. First establish autonomous agents, memory, relationships and a stable world state.

## 7. Proposed technical architecture

The simulation and intelligence are **engine-independent**. We can later attach a browser-based 3D world or Unreal Engine 5 without rebuilding the entire AI logic.

| Layer | Initial technology | Responsibility |
|---|---|---|
| Development | VS Code + AI coding agents | Build, test and maintain the project |
| Backend | Python | World simulation, scheduling and rules |
| API | FastAPI | Connect browser UI to simulation |
| Database | SQLite | Persist agents, events, memories and relationships |
| AI | DeepSeek API | Generate decisions, plans and dialogue |
| Frontend | Simple browser UI (HTML/CSS/JavaScript) | Observe, control and join the simulation |
| Testing | pytest | Validate rules, persistence, memory and costs |

A simple web UI can use server-sent events or WebSockets for live updates. Start with the simplest maintainable implementation.

### Suggested modules

- `world/`: clock, places, events, actions and state validation.
- `agents/`: agent profiles, goals, scheduling and decision orchestration.
- `memory/`: event recording, retrieval, summarisation and beliefs.
- `relationships/`: trust, familiarity, conflict and social changes.
- `llm/`: DeepSeek client, prompt templates, structured output validation, retries and usage tracking.
- `api/`: endpoints and real-time dashboard updates.
- `ui/`: agent cards, timeline, conversation panel and controls.
- `tests/`: automated tests and reproducible simulation scenarios.

This is a proposed organisation, not a requirement to create every directory before the first working slice.

## 8. DeepSeek API and budget

Use **one DeepSeek API account and API key for all five agents**. Separate characters through their own database records and the context supplied with each request. They do not need separate accounts or permanently running model instances.

The initial API credit budget is **US$5**. Prices and usage limits can change; check the current DeepSeek pricing before implementation. Build these safeguards into the first version:

- Keep the API key in a local environment variable or `.env` file that is never committed to Git.
- Track input/output tokens and estimated cost per call and per character.
- Configure a **local $5 maximum estimated spend**, with a safety margin and a hard stop on new requests when reached.
- Limit simultaneous requests, conversation turns and automated decision frequency.
- Use timeouts, bounded retries and graceful handling of API errors.
- Save progress so a stopped or exhausted run can resume.
- Make it possible to swap the model provider later.

A local usage cap is an application-level safeguard, **not a guaranteed provider billing cap**. Costs may differ slightly from estimates, especially with retries or delayed billing information.

## 9. Prototype dashboard

The initial browser dashboard should show:

- Five agent cards with current location, activity, mood and goal.
- A chronological event feed of conversations, decisions and world changes.
- A selected character's profile, relevant memories and relationships.
- A text input to talk to a selected character.
- Start, pause, resume, single-step and simulation-speed controls.
- API request count, tokens, estimated cost and remaining local budget.
- Clear errors and logs when the model or simulation fails.

A visual map is optional. A readable, reliable dashboard is more valuable than attractive 3D graphics during the first experiment.

## 10. Development milestones

### Milestone 1 — Smallest working interaction

Create two agents, one location and one DeepSeek integration. Each agent has a persistent identity and can exchange a short, relevant conversation. Store the exchange in SQLite and display it in the browser.

**Done when:** Restarting the app preserves both agents and their conversation.

### Milestone 2 — Five autonomous agents

Add three agents, individual goals, schedules, valid actions, basic relationship changes and event-driven interactions.

**Done when:** Agents initiate meaningful actions and conversations without direct player prompts.

### Milestone 3 — Player enters the world

Add player chat, knowledge boundaries, persistent memories and consequences that affect later decisions.

**Done when:** An agent can accurately refer to a prior player interaction and make a later decision influenced by it.

### Milestone 4 — Unattended simulation experiment

Run several simulated days, with speed controls and an API budget cap. Produce a timeline of significant events and relationship changes.

**Done when:** We can explain what happened, which decisions caused it, and whether the behaviour remained coherent and within budget.

### Milestone 5 — Improve realism

Address repetitive conversations, inconsistent memories, pointless actions, excessive API usage, relationship plausibility and agent inactivity. Consider reflection, long-term planning and an AI director only when the simpler system works.

**Done when:** Repeated test runs produce varied but plausible outcomes, without uncontrolled loops or contradictions.

### Later milestones — Game world

Build a neighbourhood, eventually Manchester, in a chosen graphics engine. Add 3D characters, navigation, animation, ambient life and natural voice interaction. Evaluate a browser 3D engine against Unreal Engine 5 based on visual targets, performance, development effort and distribution. Keep single-player as the initial target.

## 11. How we judge success

We need evidence, not just impressive-looking conversations. Test whether:

1. **Autonomy:** Characters initiate actions for intelligible reasons without player input.
2. **Memory:** They recall important events accurately after multiple simulated days.
3. **Continuity:** They respect time, locations, possessions, promises and world rules.
4. **Social change:** Relationships evolve from actual events, not arbitrary score changes.
5. **Knowledge:** Characters distinguish direct experience, hearsay and unknown facts.
6. **Player impact:** An intervention produces a traceable, persistent consequence.
7. **Variety:** Conversations do not repeat the same patterns endlessly.
8. **Cost:** The simulation remains within a user-configured API budget.
9. **Reliability:** Saves, restarts, errors and API failures do not corrupt the world.

Use scripted test fixtures for reproducibility, but do not script the agents' story outcomes. Record enough data to compare runs and diagnose unexpected behaviour.

## 12. Research foundations

Study these as references, not dependencies we assume can be copied directly:

- **Stanford Generative Agents:** Memory, reflection, planning and autonomous social interaction in a small simulated town. Repository: https://github.com/joonspk-research/generative_agents
- **Mantella:** Natural NPC conversation, voice, memories and a Python service linked to a game. Repository: https://github.com/art-from-the-machine/Mantella — review licensing before reusing code.
- **inZOI / NVIDIA ACE:** AI-assisted autonomous NPC decisions and small-model approaches; useful architectural inspiration, but not a drop-in system.

The exact implementation details and current capabilities of third-party projects should be verified against their latest documentation.

## 13. Explicitly out of scope for the first prototype

- Recreating all of Manchester.
- Unreal Engine integration or photorealistic graphics.
- Multiplayer and networking between human players.
- Real-time speech, voice cloning and facial animation.
- Hundreds or thousands of continuously active model-driven agents.
- Complex economics, combat, vehicles or fully simulated city infrastructure.
- Paid public hosting or commercial launch.
- Claims of genuine consciousness or unrestricted self-directed AI.

## 14. Working principles for AI coding agents

1. **Build a vertical slice first.** Two agents exchanging a persisted conversation beats a large unfinished framework.
2. **Keep the core engine independent of the UI and future graphics engine.**
3. **Use deterministic Python rules for world state and the LLM for bounded choices and dialogue.**
4. **Never trust raw model output.** Parse and validate structured responses before applying actions.
5. **Persist everything important.** Use database migrations and tests for save/load.
6. **Protect the API key and budget.** Never expose credentials in frontend code, logs or Git.
7. **Prefer simple, testable code over unnecessary frameworks.**
8. **Document assumptions and open decisions.** Do not invent confirmed requirements.
9. **Ask before adding paid services, major dependencies or scope-expanding features.**
10. **Keep the project runnable after each milestone.**

## 15. Immediate next action

Create the Python project, SQLite schema and minimal browser interface. Connect the DeepSeek API using an environment variable. Implement **two** characters who can exchange one conversation, store it and remember it after restart. Once that works, expand to five autonomous characters and begin the unattended simulation experiment.

---

**North star:** *Build a world where characters have reasons to act, remember what happens, and change because of it — even when the player isn't watching.*
