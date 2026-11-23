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
    system += _section("YOUR SITUATION:", knowledge.get("situation", []))
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
  short instruction ("Ring Northgate's agent", "Write forty quiz questions"). "to": REQUIRED full name of the person they promised.
  A promise to nobody in particular, or to themselves, is not a promise: do not record it.
  Do NOT record: anything already done during the conversation (pouring or buying a drink, answering a question);
  ordinary parts of their job. Record conditional promises and vague promises with those explicit types.
  "due_hours": REQUIRED integer — how many hours from now ({sim_time}) it should be done by
  ("tonight" = 4, "first thing tomorrow" = 18, "tomorrow" = 24, "by Friday" = hours from now until Friday evening,
  no time mentioned or "keep an ear out" = 72).
  "replaces": if this is the same promise as one in the OPEN COMMITMENTS list (even with a new deadline or more
  detail), give that id here (integer); otherwise null. Promises are fixed once made: restating one never changes
  its deadline, recipient or wording, and no duplicate is recorded.
  "kind" and "target": REQUIRED. Use only explicit, checkable targets; never guess:
  action: {{"key":"allowed menu key","args":{{...}}}}; the owner must be allowed that action.
  visit: {{"place":"pub|shop|street"}}, optionally "start_at"/"end_at" in YYYY-MM-DD HH:MM game time.
  talk: {{"person":"full cast name"}} for a conversation, bending an ear or doing something together.
  tell: {{"person":"full cast name","fact_id":123}} for passing a specific known fact (use a listed id).
  make: {{"item":"quiz_questions","count":40}}; only Tommy and quiz questions are supported.
  pay: {{"ask_id":123}} for an existing loan request or {{"offer_id":123}} for an existing ledger settlement;
       repayment and off-ledger cash promises are vague.
  conditional: {{"condition":"explicit condition text","trigger":{{"person":"full cast name","kind":"action","target":{{"key":"announce_quiz","args":{{}}}}}},"promise":{{"kind":"visit","target":{{"place":"pub"}}}}}}.
       Use a demonstrable typed trigger and inner promise; otherwise vague. Never invent a trigger mapping.
  vague: {{}} for research, unsupported making/paying, uncertain conditions or unknown targets.
- "feeling": ALWAYS include this, for both speakers: {{"trust_change": 0, "warmth_change": 0, "reason": "one short sentence citing what the other person actually said or did in this conversation"}}.
  How this speaker now feels about the OTHER speaker. Integers from -2 to 2. Ordinary chat is 0. Kindness, honesty,
  help or praise earns +1 or +2; rudeness, lies, threats or crime cost -1; insults, slurs, intimidation or
  admitting to crime cost -2.
- "decision": null unless this speaker explicitly chooses a real action now. At most one: {{"action":"menu key","args":{{}},"quote":"at least six exact words from this speaker's own line"}}. Do not infer a decision from someone else's words or a vague intention.
- "new_people": any named person mentioned who is NOT in this list: {cast}. Give a short description of what was said about them.

Also give:
- "summary": one or two sentences summarising what happened, naming both speakers.
- "commitments_done": ids of open promises whose OWNER claims completion in this conversation.
  These are CLAIMS ONLY: the world checks database evidence. Never certify an off-screen action as an observed
  fact merely because its owner says "I did it". Store the recipient's report as told and the owner's report as
  claim. Repeating a promise or agreeing again is not a completion claim. Never list an id also in "replaces".


KNOWN FACTS (ground truth; anything a speaker says beyond these about the world is a "claim"):
{known_facts}

OPEN COMMITMENTS BEFORE THIS CONVERSATION:
{open_commitments}

CONVERSATION:
{transcript}

Return JSON exactly like:
{{"summary": "...", "per_agent": {{"{a_name}": {{"decision": {{"action":"tell","args":{{"person":"{b_name}","fact_id":123}},"quote":"I am telling you what I witnessed"}}, "feeling": {{"trust_change": 0, "warmth_change": 0, "reason": "..."}}, "facts": [{{"subject": "...", "content": "...", "source": "told", "told_by": "{b_name}", "importance": 3}}], "commitments": [{{"content": "Write forty quiz questions", "to": "{b_name}", "due_hours": 24, "replaces": null, "kind": "make", "target": {{"item": "quiz_questions", "count": 40}}}}], "new_people": []}}, "{b_name}": {{"decision": null, "feeling": {{...}}, "facts": [...], "commitments": [], "new_people": []}}}}, "commitments_done": []}}
Keep it tight: at most 3 facts and 3 commitments per speaker, an empty facts list is fine. Never record trivia.
The filled decision illustrates "I am telling you what I witnessed" with a known fact id 123; never copy it unless those exact words and that owned fact occur. Extract actual choices (including advice or a warning) using the menu and verbatim speech.
The example values are illustrations only: record a commitment whenever a speaker says they will do something (e.g. "I'll ring them", "forty by Sunday, that's a promise"), and use an empty list only when nobody promised anything."""


def build_extraction_messages(a: dict, b: dict, transcript: list[dict], known_facts: list[str],
                              open_commitments: list[dict], cast: list[str], sim_time: str, police_menu: dict | None = None) -> list[dict]:
    lines = "\n".join(f'{m["speaker_name"]}: {m["text"]}' for m in transcript) or "(no lines)"
    known = "\n".join(f"- {f}" for f in known_facts) or "- (none)"
    opens = "\n".join(f"- id {c['id']} ({c['owner']}): {c['content']}; due {c.get('due_at')}; kind {c.get('kind')}; target {c.get('target_json')}; {c.get('progress', '')}" for c in open_commitments if not c.get("lapsed_at")) or "- (none)"
    prompt = EXTRACTION_TEMPLATE.format(
        a_name=a["name"], b_name=b["name"], location=a["location"], sim_time=sim_time,
        cast=", ".join(cast), known_facts=known, open_commitments=opens, transcript=lines,
    )
    from evorium.actions import REGISTRY
    speakers = {a["name"].split()[0]: a["name"], b["name"].split()[0]: b["name"]}
    # Argument names only: ranges are checked in Python, and Simon's limits must never reach the note-taker.
    menu = {name: [{'action': x.key, 'args': list(x.args_schema.model_fields)} for x in REGISTRY.values()
                   if x.who in ('any', first) and x.key != 'wait'
                   and (x.key not in ('give_advice','give_formal_warning') or (police_menu or {}).get(name, False))] for first, name in speakers.items()}
    prompt += '\nDecision menu per speaker (use only that speaker\'s own list): ' + json.dumps(menu)
    return [{"role": "user", "content": prompt}]


PROMISE_CHECK_TEMPLATE = """You are role-playing {name}, {age}, {occupation}, in Manchester. Personality: {personality}
It is now {sim_time}. You are {activity} ({location}).

Some time ago you said you would: "{promise}"{to_clause}
It was due by roughly {due}.

Your answer is an unverified CLAIM and cannot complete the promise. Did you actually do it? People like you sometimes do, sometimes put it off, sometimes
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
