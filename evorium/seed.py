"""Seed the two M1 characters without overwriting their saved state."""

from datetime import datetime, timedelta
from pathlib import Path

from evorium.db import DEFAULT_DB_PATH, connect

LOCATION = "The Crooked Billet, Ancoats, Manchester"

CHARACTERS = (
    (
        "Dez Whitworth", 54, "Pub landlord",
        "Landlord of The Crooked Billet in Ancoats; loyal to his regulars and worried about the pub's lease.",
        "Dry humour, loyal, practical, quietly worried; speaks plainly.",
        "Find out whether the new landlord is going to raise the rent.",
        "worried", LOCATION,
    ),
    (
        "Chloe Barlow", 29, "Junior architect",
        "Grew up in Stockport, spent six years in Leicester for university and her first job, and has just moved back to Manchester; a new regular at The Crooked Billet looking for an affordable flat.",
        "Optimistic, talkative, curious and friendly; eager to find her feet back in Manchester.",
        "Make friends in the city and find a flat she can afford.",
        "hopeful", LOCATION,
    ),
    (
        "Tommy Shaw", 67, "Retired bus driver",
        "Widower, Ancoats born and bred, drank in The Crooked Billet for forty years. Knows everyone's business and most of their secrets. Lonely since his wife Maureen died two years ago.",
        "Nosy, sentimental, blunt, generous with advice nobody asked for; tells the same stories but they're good ones.",
        "Get Dez to bring back the Thursday quiz night so there's a reason to come in midweek.",
        "content", LOCATION,
    ),
    (
        "Jess Hartley", 34, "Barmaid",
        "Works behind the bar at The Crooked Billet four nights a week and does cleaning shifts in the mornings. Single mum to Alfie, 8. Lives in a housing association flat in Miles Platting.",
        "Sharp, funny, tired, fiercely protective of her son; doesn't suffer fools but has a soft spot for the regulars.",
        "Get more hours at the pub, and find out whether the lease trouble means her job is at risk.",
        "tired", LOCATION,
    ),
    (
        "Raj Patel", 41, "Newsagent",
        "Runs Patel's News two doors down from the pub, which his dad opened in 1988. Married to Anita, two teenage kids. Last week a property developer offered to buy out his lease, and he hasn't told anyone yet.",
        "Careful, polite, shrewd, dry wit; weighs every word and listens more than he talks.",
        "Work out whether the developer is buying up the whole block before deciding on the offer — and whether to warn Dez.",
        "uneasy", LOCATION,
    ),
)


# Ground truth each character actually knows at the start. (agent name, subject, content)
# These are the ONLY facts about the lease situation; anything else is rumour or invention.
SEED_FACTS = (
    ("Dez Whitworth", "lease", "My lease on the pub runs out in March. The freehold was sold three months ago to a company called Northgate Estates."),
    ("Dez Whitworth", "lease", "I have had one letter from Northgate's agent saying renewal terms 'will follow'. No figures, no meeting, nobody has visited."),
    ("Dez Whitworth", "pub", "The Thursday quiz stopped eighteen months ago when the old quizmaster moved away. Nobody has run one since."),
    ("Dez Whitworth", "staff", "Jess works four evening shifts a week. I haven't got budget for more hours unless takings pick up."),
    ("Chloe Barlow", "work", "I work for a small practice in the Northern Quarter doing housing refurbs. Nobody has asked me to look at anything in Ancoats."),
    ("Chloe Barlow", "flat", "I've viewed two flats so far: one on Blossom Street (too dear) and one in Miles Platting (damp)."),
    ("Chloe Barlow", "planning", "Planning applications are public on the council website; a survey alone leaves no public record."),
    ("Tommy Shaw", "quiz", "I used to captain a quiz team called the Bus Pass Bandits. I'd happily write questions if a quiz came back."),
    ("Tommy Shaw", "lease", "Nobody has approached me or written to me about anything. I rent my flat from the housing association."),
    ("Tommy Shaw", "people", "I have not seen anyone surveying, measuring or taking notes on the street."),
    ("Jess Hartley", "job", "I do four evening shifts at the pub and morning cleaning at an office on Great Ancoats Street. I need more hours."),
    ("Jess Hartley", "lease", "I know Dez is worried about the lease because he mentioned a letter, but he hasn't told me any details."),
    ("Jess Hartley", "people", "I have not seen anyone surveying or measuring the pub or the street."),
    ("Raj Patel", "offer", "Last Tuesday a man from Northgate Estates came into the shop and verbally offered to buy out my lease. He gave me a card and said 'a generous figure'. No paperwork, no number yet."),
    ("Raj Patel", "offer", "I have told nobody about the offer, not even Anita."),
    ("Raj Patel", "street", "I have not seen anyone surveying or measuring on the street, and no customer has mentioned it."),
)


# Scheduled world events: (agent name, weekday Mon=0, hour, subject, content, key).
# Delivered by the tick as an 'observed' fact the first time the sim clock passes that slot.
SEED_EVENTS = (
    ("Dez Whitworth", 3, 9, "lease",
     "This morning a second letter from Northgate Estates arrived: they propose renewing the lease at £3,900 a month, up from £2,400, "
     "with a reply wanted within 28 days. There is a contact name: Simon Ferris, Asset Manager.", "northgate-figures"),
    ("Raj Patel", 2, 11, "offer",
     "The Northgate man (Simon Ferris, his card says) rang the shop this morning and put a number on it: £45,000 to surrender the lease, "
     "offer open for a month.", "raj-figure"),
)


def seed_events(db_path: str | Path = DEFAULT_DB_PATH, now: datetime | None = None) -> None:
    now = now or datetime.now()
    with connect(db_path) as connection:
        ids = {r["name"]: r["id"] for r in connection.execute("SELECT id, name FROM agents")}
        rows = []
        for name, weekday, hour, subject, content, key in SEED_EVENTS:
            days_ahead = (weekday - now.weekday()) % 7
            at = (now + timedelta(days=days_ahead)).replace(hour=hour, minute=0, second=0, microsecond=0)
            if at <= now:
                at += timedelta(days=7)
            rows.append((at.strftime("%Y-%m-%d %H:%M"), ids[name], subject, content, key))
        connection.executemany(
            """INSERT INTO scheduled_events (at, agent_id, subject, content, seed_key)
               VALUES (?, ?, ?, ?, ?) ON CONFLICT(seed_key) DO NOTHING""", rows)


def seed_agents(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    with connect(db_path) as connection:
        connection.executemany(
            """INSERT INTO agents
               (name, age, occupation, background, personality, current_goal, mood, location)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(name) DO NOTHING""",
            CHARACTERS,
        )
        ids = {r["name"]: r["id"] for r in connection.execute("SELECT id, name FROM agents")}
        connection.executemany(
            """INSERT INTO facts (agent_id, subject, content, source, seed_key)
               VALUES (?, ?, ?, 'seed', ?) ON CONFLICT(seed_key) DO NOTHING""",
            [(ids[name], subject, content, f"{name}|{i}") for i, (name, subject, content) in enumerate(SEED_FACTS)],
        )
