"""One-off: score facts saved before importance existed, so old trivia stops reaching characters.

    .venv/bin/python -m evorium.rescore            # preview: shows proposed scores, changes nothing
    .venv/bin/python -m evorium.rescore --apply    # backs up the database, then saves the scores

Nothing is deleted. Facts scored 1–2 stay in the database but are hidden from prompts and the dashboard.
One DeepSeek call per 40 facts (about a tenth of a cent for the current database). Stop the server first.
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from evorium.db import DEFAULT_DB_PATH, VISIBLE_IMPORTANCE, connect, init_db, system_id
from evorium.llm import DeepSeekClient, LLMError

BATCH = 40

PROMPT = """You are tidying a social simulation's memory. Score each fact below for how worth remembering it is,
using exactly this scale:
5 = harm, crime, threats, betrayal, someone getting hurt, or a big decision or deal that affects other people
4 = praise or insult, a strong show of feeling, a decision someone has made, a secret, odd or out-of-character behaviour, a ban or falling-out
3 = what someone needs, fears or is worried about; rumours and gossip about other people
2 = small talk and background detail
1 = throwaway detail
Return JSON {{"scores": [{{"id": 12, "importance": 3}}, ...]}} with one entry per fact.

FACTS:
{facts}"""


class Score(BaseModel):
    id: int
    importance: int = Field(ge=1, le=5)


class Scores(BaseModel):
    scores: list[Score] = Field(default_factory=list)


def unscored(db_path):
    """Facts from conversations that still carry the migration's default score."""
    with connect(db_path) as c:
        return [dict(r) for r in c.execute(
            """SELECT f.id, a.name, f.source, f.content FROM facts f JOIN agents a ON a.id=f.agent_id
               WHERE f.source_conversation_id IS NOT NULL AND f.importance=3 ORDER BY f.id""")]


def score(client, db_path, facts):
    with connect(db_path) as c:
        aid = system_id(c)
    result = {}
    for start in range(0, len(facts), BATCH):
        chunk = facts[start:start + BATCH]
        listing = "\n".join(f"- id {f['id']} ({f['name']}, {f['source']}): {f['content']}" for f in chunk)
        reply = client.propose(aid, [{"role": "user", "content": PROMPT.format(facts=listing)}],
                               schema=Scores, max_tokens=12 * len(chunk) + 60)
        wanted = {f["id"] for f in chunk}
        result.update({s.id: s.importance for s in reply.scores if s.id in wanted})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="back up the database and save the scores")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    args = parser.parse_args(argv)
    db_path = Path(args.db)
    init_db(db_path)
    facts = unscored(db_path)
    if not facts:
        print("Nothing to score.")
        return 0
    try:
        scores = score(DeepSeekClient(db_path), db_path, facts)
    except LLMError as exc:
        print(f"DeepSeek unavailable: {exc}")
        return 1
    hidden = 0
    for f in facts:
        s = scores.get(f["id"])
        mark = "?" if s is None else ("hide" if s < VISIBLE_IMPORTANCE else "keep")
        hidden += mark == "hide"
        print(f"[{s or '-'}] {mark:4}  {f['name'].split()[0]}: {f['content']}")
    print(f"\n{len(scores)} of {len(facts)} facts scored; {hidden} would be hidden.")
    if not args.apply:
        print("Preview only. Run again with --apply to save (a backup is made first).")
        return 0
    backup = db_path.with_name(f"{db_path.stem}-backup-{datetime.now():%Y%m%d-%H%M%S}{db_path.suffix}")
    shutil.copy2(db_path, backup)
    with connect(db_path) as c:
        c.executemany("UPDATE facts SET importance=? WHERE id=?", [(s, i) for i, s in scores.items()])
    print(f"Saved. Backup at {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
