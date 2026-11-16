# Milestone 1 — 10-minute free-run findings (2026-11-15)

Run: 39 auto conversations (43 total), 173 messages, 174 API calls, **$0.055**. Five agents, random pairs, 3–5 turns each.

## What worked
- Information genuinely spreads: Jess tells Raj about a surveyor (#4); Raj asks Tommy about "the fella with the clipboard Jess saw" (#5); by #28 Tommy is telling Dez about it.
- Characters stay in voice, pursue their own goals, and the lease thread becomes a shared storyline without any script.
- Cost is a non-issue at this scale.

## The four failures, traced to code

### 1. Forgotten commitments (Dez agrees to the quiz in #7; Tommy still asking in #20, #28, #29, #32)
**Model received it and lost it.** Dez's memory from #7 *does* contain "Quiz I can sort, Tommy" — but only because it happened to be his last line. Dez then had 7 more conversations (#10, 14, 15, 21, 23, 24, 26) and `MEMORY_LIMIT = 3` in `sim.py` means by #28 the quiz memory was long out of the prompt. Tommy's side: his memory of #7 is similarly a single final line; the *commitment* was never recorded as a thing.
- Cause A: `sim.py` memory = last line said + last line heard. Commitments mid-conversation are dropped.
- Cause B: only the 3 most recent memories reach the prompt. No relevance retrieval.
- Cause C: no `commitments` table. "I'll sort the quiz" is dialogue, not state.

### 2. Repeated conversations (Tommy asks Jess about the quiz in #20, #25, #32; Jess "You're back then" in #16 and #18)
Same root as 1: with a 3-memory window and ~8 conversations per agent per 10 minutes, each pair effectively meets fresh every few rounds. The "you've spoken before" prompt line only helps if the relevant memory is still in the window.

### 3. Growing claims (the surveyor)
Every detail was fabricated by the model and then laundered into "fact" via memory:
- #4 Jess invents "fella in a suit measuring up outside the empty unit" (nothing in her seed).
- #5 Raj adds "clipboard" (Jess never said clipboard).
- #18 Jess invents a regular called **Bernie** as the source.
- #19 "a woman taking notes"; #21 "laser tape measuring"; #30 "Tuesday morning", "folder of papers", "measuring up Dez's wall".
- #27/#28 Tommy claims they've "had the clipboard out at Raj's **and Chloe's**" — Chloe never said that.
Cause: no world-fact store and no distinction between *observed*, *told* and *invented*. Prompt says "don't invent facts" but gives the model no facts to work from, so it invents them. Memories store whatever was said, verbatim, as truth.

### 4. Promises without action
43 "I'll …" statements (ring the landlord, pin Bernie down, write the team sheet, check the planning portal). **Nothing records or executes any of them.** There is no action system at all in M1 — by design — but the model talks as if there is, and later conversations assume the action happened ("I checked again this morning", #43).

## What M2 must add (in priority order)
1. **Structured memory extraction** per conversation: ask the model (one extra call per conversation, ~$0.0003) for a JSON list of `facts_learned`, `commitments_made`, `questions_open` — store each as a row with `source` (observed / told-by-X / own-claim) and `subject` tags.
2. **Relevance retrieval**: pull memories by subject tags of the listener and the current goal, not "last 3". Cap tokens, not rows.
3. **Commitments table** with status (open / done / broken) injected into the prompt as "Things you've promised". A deterministic Python tick marks simple ones done (e.g. "put up sign-up sheet") and lets the model reference them.
4. **World facts table** seeded by us (who has had a letter, who hasn't; no surveyor has visited yet). The prompt gets "What you actually know" from this plus memories tagged *observed*. Model claims about the world that aren't in it get stored as `own-claim`, never as fact, and are shown in the dashboard as "rumour".
5. **Conversation pacing**: a world clock so pairs don't meet 8 times in 10 "minutes"; cooldown per pair.
6. **Named NPC registry**: if the model names a new person (Bernie), either reject or register them as a minor NPC so the next prompt knows Bernie exists and what's attributed to him.

## Budget note
At ~$0.0014 per conversation, $5 funds roughly 3,500 conversations. The extra extraction call in item 1 adds ~25%. Still fine.
