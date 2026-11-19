"""Prompt templates. The model proposes bounded dialogue and, afterwards, structured notes."""

import json

SYSTEM_TEMPLATE = """You are role-playing {name}, a real person in Manchester, England. Stay in character.

Identity: {name}, {age}, {occupation}.
Background: {background}
Personality: {personality}
Current goal: {current_goal}
Current mood: {mood}
Where and when: {location}, {sim_time}.

You are talking with {other_name} ({other_occupation}).

STRICT RULES ABOUT KNOWLEDGE
- Everything you know is listed below. If something is not listed, you do not know it.
- Do not invent events, letters, visitors, sightings, phone calls or people. If you want to mention
  something you are unsure of, say you are unsure or that it is only a rumour.
- Do not claim to have done something you promised unless it is listed as done.
- You may ask questions, speculate out loud (clearly as speculation), or admit you don't know.
- Speak naturally, briefly, in British English, one or two sentences. Do not repeat a greeting
  or a question you have already covered with this person.

Respond with JSON only, exactly this shape and nothing else:
{{"say": "<one or two sentences of dialogue>", "rationale": "<one short sentence on why you said it>", "mood": "<one word>"}}"""


def _section(title: str, items: list[str]) -> str:
    if not items:
        return ""
    return f"\n\n{title}\n" + "\n".join(f"- {i}" for i in items)


def build_messages(speaker: dict, listener: dict, transcript: list[dict], knowledge: dict, sim_time: str) -> list[dict]:
    system = SYSTEM_TEMPLATE.format(
        name=speaker["name"], age=speaker["age"], occupation=speaker["occupation"],
        background=speaker["background"], personality=speaker["personality"],
        current_goal=speaker["current_goal"], mood=speaker["mood"], location=speaker["location"],
        sim_time=sim_time, other_name=listener["name"], other_occupation=listener["occupation"],
    )
    if listener.get('kind') == 'player':
        system += f"\n{listener['name']} is someone you know only from what is listed here. Do not assume anything else about them."
    system += _section("WHAT YOU KNOW FOR CERTAIN (your own experience):", knowledge["certain"])
    system += _section("WHAT OTHERS HAVE TOLD YOU (second-hand, may be wrong):", knowledge["told"])
    system += _section("THINGS YOU SAID EARLIER THAT YOU CAN'T ACTUALLY VERIFY (treat as your own guesswork):", knowledge["claims"])
    system += _section("PROMISES YOU HAVE MADE AND NOT YET DONE:", knowledge["promises"])
    system += _section(f"PROMISES {listener['name'].upper()} MADE TO YOU (not yet done):", knowledge["their_promises"])
    system += _section(f"HOW YOU FEEL ABOUT {listener['name'].upper()}:", knowledge.get('relationship',[]))
    system += _section(f"PROMISES {listener['name'].upper()} HAS BROKEN TO YOU:", knowledge.get('broken_promises',[]))
    system += _section("WHAT YOU HAVE DONE AND PLAN TO DO TODAY:",knowledge.get("plans",[]))
    system += _section("OTHER PEOPLE YOU KNOW OF:", knowledge["people"])
    if knowledge["last_with_listener"]:
        system += f"\n\nLAST TIME YOU SPOKE WITH {listener['name'].upper()}:\n- {knowledge['last_with_listener']}\nPick up from there; do not re-ask what was already answered."
    else:
        system += f"\n\nYou have not had a proper conversation with {listener['name']} before."
    system += _section("YOUR MOST RECENT CONVERSATIONS (any person):", knowledge["recent"])
    system += _section("TOPICS YOU HAVE ALREADY GONE OVER TODAY (do not rehash these unless you have genuinely new "
                       "information; talk about something else: your day, your family, the other person, local life):",
                       knowledge.get("covered_today", []))

    if transcript:
        lines = "\n".join(f'{m["speaker_name"]}: {m["text"]}' for m in transcript)
        user = f"Conversation so far:\n{lines}\n\nIt is your turn to speak, {speaker['name']}. Reply as JSON."
    else:
        user = f"You are the first to speak to {listener['name']}. Open the conversation naturally. Reply as JSON."
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


EXTRACTION_TEMPLATE = """You are a meticulous note-taker for a social simulation. Below is a conversation between
{a_name} and {b_name} at {location}, {sim_time}. Produce structured notes in JSON.

For EACH of the two speakers, record:
- "facts": only things worth remembering next week. Small talk, pleasantries, directions to the bread aisle,
  what someone ordered and who sat where are NOT facts: leave them out (the summary covers the gist). For each:
  - "subject": one or two words (e.g. "lease", "quiz", "offer", "survey", "flat")
  - "content": one sentence, written from that speaker's point of view ("Raj has been offered money for his lease")
  - "source": "observed" ONLY if the speaker directly did or saw it themselves and it is consistent with the
    known facts list; "told" if the other speaker told them; "claim" if the speaker asserted it with no basis
    in the known facts (an invention, exaggeration or guess).
  - "told_by": the other speaker's name when source is "told", else null.
  - "importance": integer 1–5. Only record facts scoring 3 or more:
      5 = harm, crime, threats, betrayal, someone getting hurt, or a big decision or deal that affects other
          people (selling drugs, a racist slur, a rent rise, an offer to buy someone out, being sacked or evicted)
      4 = praise or insult, a strong show of feeling, a decision someone has made, a secret, someone behaving
          oddly or out of character, a ban or falling-out
      3 = what someone needs, fears or is worried about; rumours and gossip about other people
      2 = small talk and background detail (hobbies, old stories) — do not record
      1 = throwaway detail — do not record
  ATTRIBUTION RULE: when speaker X states something not in the known facts, record it TWICE — under X as
  source "claim" (X made it up), and under the other speaker as source "told" with told_by X (they heard it).
  Never record X's own invention under the other speaker as a "claim".
  Personal opinions, tastes and plans about the speaker's own life ("I'd budget £900 a month") are "observed", not claims.
- "commitments": things that speaker promised to do AFTER this conversation and has not yet done. Write each as a
  short instruction ("Ring Northgate's agent", "Write forty quiz questions"). "to": who they promised, or null.
  Do NOT record: anything already done during the conversation (pouring or buying a drink, answering a question);
  conditional or vague intentions ("I'd come if there was a quiz", "we should do that sometime"); ordinary parts
  of their job.
  "due_hours": REQUIRED integer — how many hours from now ({sim_time}) it should be done by
  ("tonight" = 4, "first thing tomorrow" = 18, "tomorrow" = 24, "by Friday" = hours from now until Friday evening,
  no time mentioned or "keep an ear out" = 72).
  "replaces": if this is the same promise as one in the OPEN COMMITMENTS list, restated with more detail or a new
  deadline, give that id here (integer) so it is updated instead of duplicated; otherwise null. If an open
  commitment is merely mentioned again with nothing new, do not record it at all.
- "feeling": ALWAYS include this, for both speakers: {{"trust_change": 0, "warmth_change": 0, "reason": "one short sentence citing what the other person actually said or did in this conversation"}}.
  How this speaker now feels about the OTHER speaker. Integers from -2 to 2. Ordinary chat is 0. Kindness, honesty,
  help or praise earns +1 or +2; rudeness, lies, threats or crime cost -1; insults, slurs, intimidation or
  admitting to crime cost -2.
- "new_people": any named person mentioned who is NOT in this list: {cast}. Give a short description of what was said about them.

Also give:
- "summary": one or two sentences summarising what happened, naming both speakers.
- "commitments_done": ids (integers) from the OPEN COMMITMENTS list whose promised action has ACTUALLY BEEN CARRIED
  OUT, as shown or reported in this conversation (the promise was to tell someone something and they have now told
  them; the speaker says they made the call and what came of it). Agreeing to it again, discussing it, planning it,
  or being reminded of it does NOT make it done. Never list an id you also gave as "replaces". Leave empty if unsure.

KNOWN FACTS (ground truth; anything a speaker says beyond these about the world is a "claim"):
{known_facts}

OPEN COMMITMENTS BEFORE THIS CONVERSATION:
{open_commitments}

CONVERSATION:
{transcript}

Return JSON exactly like:
{{"summary": "...", "per_agent": {{"{a_name}": {{"feeling": {{"trust_change": 0, "warmth_change": 0, "reason": "..."}}, "facts": [{{"subject": "...", "content": "...", "source": "told", "told_by": "{b_name}", "importance": 3}}], "commitments": [], "new_people": []}}, "{b_name}": {{"feeling": {{...}}, "facts": [...], "commitments": [], "new_people": []}}}}, "commitments_done": []}}
Keep it tight: at most 3 facts and 3 commitments per speaker, an empty facts list is fine. Never record trivia."""


def build_extraction_messages(a: dict, b: dict, transcript: list[dict], known_facts: list[str],
                              open_commitments: list[dict], cast: list[str], sim_time: str) -> list[dict]:
    lines = "\n".join(f'{m["speaker_name"]}: {m["text"]}' for m in transcript) or "(no lines)"
    known = "\n".join(f"- {f}" for f in known_facts) or "- (none)"
    opens = "\n".join(f"- id {c['id']} ({c['owner']}): {c['content']}" for c in open_commitments) or "- (none)"
    prompt = EXTRACTION_TEMPLATE.format(
        a_name=a["name"], b_name=b["name"], location=a["location"], sim_time=sim_time,
        cast=", ".join(cast), known_facts=known, open_commitments=opens, transcript=lines,
    )
    return [{"role": "user", "content": prompt}]


PROMISE_CHECK_TEMPLATE = """You are role-playing {name}, {age}, {occupation}, in Manchester. Personality: {personality}
It is now {sim_time}. You are {activity} ({location}).

Some time ago you said you would: "{promise}"{to_clause}
It was due by roughly {due}.

Be honest and in character: did you actually do it? People like you sometimes do, sometimes put it off, sometimes
forget. Base it on your personality and mood ({mood}). If you did it, say briefly what happened and what you found
out — but do NOT invent dramatic new facts (no new letters, offers, visitors or revelations); keep any result
mundane and plausible. If you didn't, say why.

Respond with JSON only:
{{"done": true or false, "what_happened": "<one or two sentences in first person>", "mood": "<one word>"}}"""


def build_promise_check_messages(agent: dict, promise: dict, sim_time: str, location: str, activity: str) -> list[dict]:
    to_clause = f' (you promised {promise["to_name"]})' if promise.get("to_name") else ""
    prompt = PROMISE_CHECK_TEMPLATE.format(
        name=agent["name"], age=agent["age"], occupation=agent["occupation"], personality=agent["personality"],
        sim_time=sim_time, activity=activity, location=location, promise=promise["content"], to_clause=to_clause,
        due=promise.get("due_at") or "now", mood=agent["mood"])
    return [{"role": "user", "content": prompt}]


def debug_dump(messages: list[dict]) -> str:
    return json.dumps(messages, indent=2)
