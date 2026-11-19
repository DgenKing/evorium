"""Only facts worth remembering are kept, and the important ones are what characters see first."""
from datetime import datetime, timedelta

import pytest

from evorium import director, plans, relationships, sim
from evorium.db import connect, init_db
from evorium.memory import covered_today, knowledge_for_prompt, store_extraction
from evorium.models import Extraction
from evorium.prompts import build_extraction_messages
from evorium.seed import seed_agents

NOW = datetime(2026, 11, 19, 13, 50)


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "w.sqlite3"
    init_db(p)
    seed_agents(p)
    return p


def _people(c, *ids):
    return {r["name"]: dict(r) for r in c.execute(f"select * from agents where id in ({','.join('?' * len(ids))})", ids)}


def _conversation(c, a, b, sim_at=NOW):
    return c.execute("insert into conversations(location,status,agent_a_id,agent_b_id,sim_at) values ('shop','completed',?,?,?)",
                     (a, b, sim_at.strftime("%Y-%m-%d %H:%M"))).lastrowid


def _fact(content, importance=None, source="observed", subject="shop"):
    f = {"subject": subject, "content": content, "source": source}
    if importance is not None:
        f["importance"] = importance
    return f


def test_trivia_is_dropped_and_serious_facts_kept(db):
    with connect(db) as c:
        raj = c.execute("select id,name from agents where name='Raj Patel'").fetchone()
        mo = c.execute("select id from agents where name like 'Mohammed%'").fetchone()[0]
        cid = _conversation(c, raj["id"], mo)
        ext = Extraction.model_validate({"summary": "s", "per_agent": {"Raj Patel": {"facts": [
            _fact("The bread is on the shelf behind the counter.", 1),
            _fact("Mo captained a darts team years ago.", 2),
            _fact("Mo offered to sell me crack in my own shop.", 5),
            _fact("Mo is worried about his licence.", 3),
            _fact("No score given, so it counts as ordinary.", None),
            _fact("Mo was oddly jumpy and kept looking at the door.", 4),
        ]}}})
        counts = store_extraction(c, cid, _people(c, raj["id"], mo), ext, NOW)
        kept = [r[0] for r in c.execute("select importance from facts where source_conversation_id=? order by importance desc", (cid,))]
        assert kept == [5, 4, 3]                       # top three of those worth keeping, trivia never saved
        assert counts["facts"] == 3 and counts["trivia"] == 3
        assert c.execute("select count(*) from timeline where kind='serious'").fetchone()[0] == 1


def test_importance_is_coerced_into_range():
    ext = Extraction.model_validate({"summary": "s", "per_agent": {"Raj Patel": {"facts": [
        _fact("a", 9), _fact("b", "4"), _fact("c", 0), _fact("d", "high")]}}})
    assert [f.importance for f in ext.per_agent["Raj Patel"].facts] == [5, 4, 1, 3]


def test_prompt_shows_important_before_recent_and_hides_old_trivia(db):
    with connect(db) as c:
        raj, dez = (c.execute("select * from agents where name=?", (n,)).fetchone() for n in ("Raj Patel", "Dez Whitworth"))
        c.execute("insert into facts(agent_id,subject,content,source,importance) values (?, 'x', 'Rob sells drugs.', 'observed', 5)", (raj["id"],))
        for i in range(15):   # a flood of newer, middling facts
            c.execute("insert into facts(agent_id,subject,content,source,importance) values (?, 'x', ?, 'observed', 3)", (raj["id"], f"Ordinary {i}"))
        c.execute("insert into facts(agent_id,subject,content,source,importance) values (?, 'x', 'Old trivia.', 'observed', 2)", (raj["id"],))
        k = knowledge_for_prompt(c, dict(raj), dict(dez), NOW)
        assert k["certain"][0] == "Rob sells drugs."
        assert "Old trivia." not in k["certain"]


def test_extraction_prompt_asks_for_feeling_and_importance():
    text = build_extraction_messages({"name": "A", "location": "pub"}, {"name": "B"}, [], [], [], [], "now")[0]["content"]
    assert '"feeling": {"trust_change"' in text and '"importance": 3' in text and "ALWAYS include" in text


def test_story_conversations_run_longer(db):
    with connect(db) as c:
        ids = {r["name"].split()[0]: r["id"] for r in c.execute("select id,name from agents")}
    assert sim.turns_for(ids["Simon"], ids["Raj"], db) == sim.STORY_TURNS            # never met
    with connect(db) as c:
        c.execute("insert into conversations(location,status,agent_a_id,agent_b_id,started_at) values ('pub','completed',?,?,'2026-11-19T10:00:00.000Z')",
                  (ids["Dez"], ids["Jess"]))
    assert sim.turns_for(ids["Dez"], ids["Jess"], db) == sim.USUAL_TURNS
    with connect(db) as c:
        c.execute("insert into facts(agent_id,subject,content,source,importance,created_at) values (?, 'lease', 'Rent is going to £3,900.', 'observed', 5, '2026-11-19T11:00:00.000Z')",
                  (ids["Dez"],))
    assert sim.turns_for(ids["Dez"], ids["Jess"], db) == sim.STORY_TURNS            # big news since they last spoke


def test_repeated_topics_are_flagged_and_loops_count_as_stalls(db):
    with connect(db) as c:
        dez, jess = (c.execute("select id from agents where name like ?", (n,)).fetchone()[0] for n in ("Dez%", "Jess%"))
        for i in range(3):
            cid = _conversation(c, dez, jess, NOW - timedelta(hours=2) + timedelta(minutes=20 * i))
            c.execute("insert into facts(agent_id,subject,content,source,source_conversation_id) values (?, 'lease', ?, 'told', ?)",
                      (dez, f"Lease point {i}", cid))
        assert covered_today(c, dez, NOW) == ["lease (talked about in 3 conversations today)"]
        assert covered_today(c, jess, NOW) == []
    report = director.stall_report(NOW, db)
    assert report["looping_on"] == "lease" and report["stalled"]


def test_planner_is_told_about_serious_news(db):
    with connect(db) as c:
        raj = c.execute("select id from agents where name='Raj Patel'").fetchone()[0]
        c.execute("insert into facts(agent_id,subject,content,source,importance) values (?, 'offer', '£45,000 to surrender the lease.', 'observed', 5)", (raj,))
    prompts = {}

    class Recorder:
        def propose(self, aid, messages, schema=None, max_tokens=0):
            prompts[aid] = messages[0]["content"]
            return plans.DailyPlans(plans=[])

    plans.daily(Recorder(), NOW, db)
    assert "Serious news on your mind" in prompts[raj] and "45,000" in prompts[raj]
    assert all("Serious news" not in p for aid, p in prompts.items() if aid != raj)


def test_migration_scores_existing_facts(tmp_path):
    p = tmp_path / "old.sqlite3"
    init_db(p)
    seed_agents(p)
    with connect(p) as c:
        assert c.execute("select min(importance) from facts where source='seed'").fetchone()[0] == 4


def test_rescore_previews_without_writing_and_applies_with_backup(db, monkeypatch, capsys):
    from evorium import rescore
    with connect(db) as c:
        raj, rob = c.execute("select id from agents where name='Raj Patel'").fetchone()[0], c.execute("select id from agents where kind='npc' and id!=5 limit 1").fetchone()[0]
        cid = _conversation(c, raj, rob)
        bread = c.execute("insert into facts(agent_id,subject,content,source,source_conversation_id) values (?, 'shop', 'Bread is behind you.', 'told', ?)", (raj, cid)).lastrowid
        drugs = c.execute("insert into facts(agent_id,subject,content,source,source_conversation_id) values (?, 'rob', 'Rob sells drugs.', 'told', ?)", (raj, cid)).lastrowid

    class Fake:
        def __init__(self, *a): pass
        def propose(self, aid, messages, schema=None, max_tokens=0):
            return rescore.Scores(scores=[{"id": bread, "importance": 1}, {"id": drugs, "importance": 5}])

    monkeypatch.setattr(rescore, "DeepSeekClient", Fake)
    assert rescore.main(["--db", str(db)]) == 0
    with connect(db) as c:
        assert c.execute("select importance from facts where id=?", (bread,)).fetchone()[0] == 3   # preview changed nothing
    assert rescore.main(["--db", str(db), "--apply"]) == 0
    with connect(db) as c:
        assert [c.execute("select importance from facts where id=?", (i,)).fetchone()[0] for i in (bread, drugs)] == [1, 5]
    assert list(db.parent.glob("w-backup-*.sqlite3"))
    assert "1 would be hidden" in capsys.readouterr().out


def test_extraction_example_shows_a_filled_in_promise():
    # An empty "commitments": [] in the example made the note-taker record no promises at all (0 in 62 conversations).
    from evorium.prompts import build_extraction_messages
    from evorium.memory import EXAMPLE_COMMITMENT
    a = {"name": "Dez Whitworth", "location": "pub"}; b = {"name": "Tommy Shaw", "location": "pub"}
    text = build_extraction_messages(a, b, [{"speaker_name": "Dez Whitworth", "text": "hi"}], [], [], [], "now")[0]["content"]
    assert '"commitments": [{"content": "Ring the brewery about the late delivery"' in text
    assert EXAMPLE_COMMITMENT == "ring the brewery about the late delivery"
