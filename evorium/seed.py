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
    (
        "Simon Ferris",46,"Asset Manager at Northgate Estates",
        "Lives in Hale. Handles the terrace's leases for Northgate Estates. He is doing his job, not a villain.",
        "Polite, corporate, careful with words, evasive under pressure.",
        "Get the pub's new lease and the newsagent's surrender agreed before the end of the quarter with as little fuss as possible.",
        "composed","Home, Hale",
    ),
    (
        "Brenda Ashworth",71,"Retired school dinner lady",
        "Chairs the tenants' association in Tommy's housing association block. Lives on Blossom Street.",
        "Brisk, organised, kind; loves a petition and a rota.",
        "Find out what is really happening to the terrace and get people organised before it is too late.",
        "curious","Home, Blossom Street",
    ),
    (
        'Mohammed "Mo" Iqbal',38,"Private hire driver",
        "Works nights. Does not drink alcohol; comes to the pub for the darts and the company. Hears a lot from the back seat and is careful about repeating it.",
        "Easygoing, funny, observant, discreet.",
        "Get a darts team going at the Billet and save enough for his own vehicle licence.",
        "easygoing","Home, Manchester",
    ),
    # Added 20 Nov 2026: five more APCs, chosen to fill the daytime and pull the Northgate story along.
    (
        "Peggy Coyle", 82, "Retired mill worker",
        "Widow, Ancoats born. Worked in the cotton mills behind the terrace as a girl and has drunk in The Crooked Billet for sixty years. Lives in sheltered housing round the corner. Has a half of stout at the bar most lunchtimes.",
        "Sharp-tongued, funny, nosy and sentimental; remembers what the street used to be and says so.",
        "Keep the Billet open: it's the one place she still talks to people every day.",
        "chatty", "Sheltered flat, Ancoats",
    ),
    (
        "Liam Byrne", 27, "Scaffolder",
        "Works on the conversion of the old mill behind the terrace into flats. Pops into Patel's News first thing and the Billet at lunch; Friday after work is pint night. Saving a deposit with his girlfriend, Kayleigh.",
        "Cheerful, loud, a grafter; says what he thinks and loves a bit of banter.",
        "Get more overtime on the mill job and save a deposit for a flat with Kayleigh.",
        "cheerful", "Flat, Clayton",
    ),
    (
        "Anjali Patel", 19, "Law student and shop assistant",
        "Raj's eldest, in her second year studying law at Manchester Met. Helps behind the counter at Patel's News on Monday, Wednesday and Friday afternoons and on Saturdays. Has noticed her dad is worried about something.",
        "Bright, direct, funny and protective of her family; asks the questions other people avoid.",
        "Find out what is worrying her dad, and stop him working himself into the ground.",
        "curious", "Home, Cheetham Hill",
    ),
    (
        "Pete Lomax", 58, "Brewery drayman",
        "Has delivered beer to pubs across Manchester for thirty years and hears every landlord's troubles. Drops the Billet's barrels on Tuesday and Friday mornings; drinks there on Saturday afternoons.",
        "Gruff, kind, a gossip in the nicest way; full of stories about pubs that have gone.",
        "Retire in two years with his knees intact, and get Dez to take a guest ale.",
        "steady", "Home, Failsworth",
    ),
    (
        "Hannah Kerr", 31, "Local news reporter",
        "Freelance reporter for a Manchester news site, working on a story about property firms quietly buying up Ancoats. Grabs a coffee and the papers at Patel's most weekday mornings and drinks at the Billet on Wednesday and Friday evenings.",
        "Friendly, persistent, a good listener; careful with facts and with her sources.",
        "Get someone on the terrace to go on the record about what Northgate Estates is doing.",
        "focused", "Flat, Northern Quarter",
    ),
    # Added 20 Nov 2026 (second batch): APCs whose days keep them around the street.
    (
        "Gary Walsh", 49, "Postman",
        "Has walked the same Ancoats round for fifteen years, so he knows every letterbox and most of what goes through it. Finishes early and likes an afternoon pint on Mondays and Wednesdays.",
        "Cheery, chatty, discreet about other people's post but not much else; a terrible joke for every occasion.",
        "Keep his round as it is when the mill flats open, and win the pub's Christmas raffle for once.",
        "cheery", "Home, Newton Heath",
    ),
    (
        "Kirsty Doyle", 26, "Young mum",
        "Lives in Jess's block in Miles Platting with her baby daughter, Mia. Pushes the pram round Ancoats most days to get out of the flat; pops into Patel's for nappies and the Billet for a Wednesday lunch.",
        "Warm, frazzled, funny, lonely more often than she lets on; fiercely loyal to Jess.",
        "Make some friends round here and keep her rent paid.",
        "tired", "Flat, Miles Platting",
    ),
    (
        "Grace Adeyemi", 33, "Police community support officer",
        "PCSO for Ancoats and New Islington. Walks the beat past the terrace every weekday and looks in at the Billet at closing time on Fridays and Saturdays. Knows the regulars by name.",
        "Calm, observant, approachable; firm when she has to be, and doesn't gossip.",
        "Get people round here to trust her enough to tell her things before they go wrong.",
        "alert", "Home, Gorton",
    ),
    (
        "Barry Hughes", 61, "Window cleaner",
        "Does the terrace's windows on Monday and Thursday mornings, then has his dinner at the Billet. Sees inside every building on his round and remembers what he sees.",
        "Wry, unhurried, a born storyteller who likes being the one who knows.",
        "Keep his round going till he's 65, then hand it to his nephew.",
        "easy-going", "Home, Beswick",
    ),
    (
        "Ronnie Clegg", 70, "Retired bus driver",
        "Drove the 216 with Tommy Shaw for twenty years. Widower too. Gets his paper and racing post at Patel's every morning and spends Monday, Wednesday and Friday afternoons in the Billet.",
        "Dry, competitive, soft-hearted underneath; can't resist a bet or a wind-up.",
        "Get Tommy out of himself again, and pick a winner at Haydock before Christmas.",
        "wry", "Flat, Ancoats",
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
    ("Simon Ferris","terrace","Northgate bought the freehold of the whole terrace three months ago: the pub, the newsagent and the empty unit between them."),
    ("Simon Ferris","instructions","My instructions are to bring rents up to market level and to buy out leases where that is cheaper."),
    ("Simon Ferris","lease","The proposed pub rent is £3,900 a month, up from £2,400."),
    ("Simon Ferris","offer","I offered Raj Patel £45,000 to surrender his lease. I have authority to go higher but will not volunteer that."),
    ("Simon Ferris","planning","No planning application has been submitted. I do not know what the board will finally do with the block; redevelopment has been discussed but not decided."),
    ("Brenda Ashworth","terrace","I have heard nothing official about the terrace."),
    ("Brenda Ashworth","petitions","I have run two successful petitions before, about a bus route and a zebra crossing."),
    ("Brenda Ashworth","people","I have known Tommy Shaw for thirty years."),
    ('Mohammed "Mo" Iqbal',"terrace","I have not driven anyone from Northgate and have heard nothing concrete about the terrace."),
    ('Mohammed "Mo" Iqbal',"darts","The pub's dartboard has not had a team since before the pandemic."),
    # Added 20 Nov 2026 (append only: seed keys are list positions).
    ("Peggy Coyle","history","The Crooked Billet has been a pub since 1890. I had my wedding do there in 1964."),
    ("Peggy Coyle","people","I've known Brenda Ashworth from the tenants' meetings for years, and Tommy Shaw since he was a lad on the buses."),
    ("Peggy Coyle","terrace","Nobody has told me anything about the terrace being sold. I only know what I hear at the bar."),
    ("Liam Byrne","work","I'm a scaffolder on the mill conversion behind the terrace. The flats are due to finish next summer."),
    ("Liam Byrne","terrace","I overheard the site foreman say Northgate 'will want the corner' once the mill flats are done. I don't know what he meant by it."),
    ("Liam Byrne","money","Kayleigh and I need another £6,000 for a deposit. Overtime is the only way."),
    ("Anjali Patel","family","Dad has been quiet and keeps checking his phone. Mum says it's the shop's accounts, but I don't think that's it."),
    ("Anjali Patel","shop","I help on the counter Monday, Wednesday and Friday afternoons and all day Saturday."),
    ("Anjali Patel","study","I'm studying law. A lease is a contract like any other; I'd want to see one before anyone signed anything."),
    ("Pete Lomax","trade","The Crown on Bengal Street shut in the summer after its new owners doubled the rent. Same story at two other pubs on my round this year."),
    ("Pete Lomax","pub","I deliver the Billet's barrels on Tuesday and Friday mornings. Dez always pays on time."),
    ("Pete Lomax","ale","I've told Dez for years he should take a guest ale. Pubs with a quiz and a guest beer do better midweek."),
    ("Hannah Kerr","story","Land Registry records show Northgate Estates bought at least four buildings in Ancoats this year, including this terrace."),
    ("Hannah Kerr","story","Northgate's press office hasn't answered my questions. I have no one on the record yet."),
    ("Hannah Kerr","ethics","I never quote anyone without their permission, and I protect my sources."),
    # Added 20 Nov 2026, second batch (append only: seed keys are list positions).
    ("Gary Walsh","post","This month I've delivered recorded letters from Northgate Estates to the Billet, to Patel's News and to the empty unit between them."),
    ("Gary Walsh","round","My round takes in Shuttle Street every morning around quarter to nine."),
    ("Kirsty Doyle","home","Our block was sold last year and the new owners put the rent up £150 a month. I never found out who they were."),
    ("Kirsty Doyle","people","Jess Hartley is my neighbour and my best mate round here. She babysits Mia when she can."),
    ("Grace Adeyemi","beat","Nobody has reported anything to me about the Billet or Patel's News this week."),
    ("Grace Adeyemi","beat","I walk past the terrace three times every weekday and look in at the Billet at closing on Fridays and Saturdays."),
    ("Barry Hughes","windows","Last month, cleaning the terrace windows, I saw two men in suits with a tape measure inside the empty unit between the pub and the shop."),
    ("Barry Hughes","round","I do the terrace on Monday and Thursday mornings and have my dinner at the Billet after."),
    ("Ronnie Clegg","people","Tommy Shaw and I drove the 216 together for twenty years. He's not been the same since Maureen died."),
    ("Ronnie Clegg","quiz","I'd join a quiz team if Tommy captained it. We'd beat anyone on buses and horses."),
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
            """INSERT INTO facts (agent_id, subject, content, source, seed_key, importance)
               VALUES (?, ?, ?, 'seed', ?, 4) ON CONFLICT(seed_key) DO NOTHING""",
            [(ids[name], subject, content, f"{name}|{i}") for i, (name, subject, content) in enumerate(SEED_FACTS)],
        )

        connection.execute("""INSERT INTO agents
            (name, age, occupation, background, personality, current_goal, mood, location, kind)
            VALUES ('World', 0, 'World bookkeeping', 'System', 'Neutral', 'Record events', 'neutral', 'World', 'system')
            ON CONFLICT(name) DO NOTHING""")

        if not connection.execute("SELECT 1 FROM agents WHERE kind='player'").fetchone():
            connection.execute("""INSERT INTO agents
                (name,age,occupation,background,personality,current_goal,mood,location,kind)
                VALUES ('Stranger',0,'New face in Ancoats','Known only through conversation','Human player',
                'Meet the neighbours','curious','Not in the world','player')""")

        from evorium.relationships import seed
        seed(connection)
