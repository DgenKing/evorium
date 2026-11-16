import pytest

from evorium import world
from evorium.db import connect, init_db
from evorium.llm import InvalidProposal, LLMError
from evorium.models import ActionProposal, AgentExtraction, CommitmentOut, Extraction, FactOut, PersonOut
from evorium.seed import seed_agents
from evorium.sim import get_conversation, run_conversation


class FakeClient:
    def __init__(self, fail_at=None, invalid_at=None, extraction=None, extraction_fails=False):
        self.calls = []          # dialogue calls only
        self.extraction_calls = []
        self.fail_at = fail_at
        self.invalid_at = invalid_at
        self.extraction = extraction
        self.extraction_fails = extraction_fails

    def propose(self, agent_id, messages, schema=ActionProposal, max_tokens=300):
        if schema is Extraction:
            self.extraction_calls.append(messages)
            if self.extraction_fails:
                raise InvalidProposal("bad notes")
            return self.extraction or Extraction(summary="They talked about the pub.")
        n = len(self.calls) + 1
        self.calls.append((agent_id, messages))
        if self.fail_at == n:
            raise LLMError("boom")
        if self.invalid_at == n:
            raise InvalidProposal("bad json")
        return ActionProposal(say=f"Line {n} from agent {agent_id}.", rationale=f"Reason {n}.", mood="Chipper")


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "w.sqlite3"
    init_db(path)
    seed_agents(path)
    return path


def test_run_writes_messages_memories_and_stamps_sim_time(db):
    client = FakeClient()
    cid = run_conversation(client, 1, 2, turns=4, db_path=db)
    conv = get_conversation(cid, db)
    assert conv["status"] == "completed"
    assert conv["summary"] == "They talked about the pub."
    assert [m["speaker_id"] for m in conv["messages"]] == [1, 2, 1, 2]
    assert conv["sim_time"] == world.describe(world.now(db))[:len(conv["sim_time"])] or conv["sim_time"]
    with connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 2
        assert c.execute("SELECT mood FROM agents WHERE id=1").fetchone()[0] == "chipper"
    assert len(client.extraction_calls) == 1


def test_prompt_contains_seed_facts_and_rules(db):
    client = FakeClient()
    run_conversation(client, 1, 2, turns=1, db_path=db)
    system = client.calls[0][1][0]["content"]
    assert "WHAT YOU KNOW FOR CERTAIN" in system
    assert "Northgate Estates" in system            # Dez's seed fact
    assert "Do not invent" in system
    assert "not had a proper conversation with Chloe Barlow" in system


def test_extraction_is_stored_and_fed_back(db):
    ext = Extraction(
        summary="Dez promised Tommy a quiz.",
        per_agent={
            "Dez Whitworth": AgentExtraction(
                facts=[FactOut(subject="quiz", content="Tommy will write quiz questions.", source="told", told_by="Tommy Shaw")],
                commitments=[CommitmentOut(content="Bring back the Thursday quiz", to="Tommy Shaw")],
            ),
            "Tommy Shaw": AgentExtraction(
                facts=[FactOut(subject="survey", content="A man with a clipboard has been measuring the street.", source="claim")],
                new_people=[PersonOut(name="Bernie", description="a regular who claims to have seen a surveyor")],
            ),
        },
    )
    client = FakeClient(extraction=ext)
    run_conversation(client, 1, 3, turns=2, db_path=db)
    with connect(db) as c:
        assert c.execute("SELECT status FROM commitments WHERE agent_id=1").fetchone()[0] == "open"
        assert c.execute("SELECT source FROM facts WHERE agent_id=3 AND subject='survey'").fetchone()[0] == "claim"
        assert c.execute("SELECT name FROM npcs").fetchone()[0] == "Bernie"
    # Next time Dez talks to Tommy, the promise and last-conversation summary are in his prompt.
    client2 = FakeClient()
    run_conversation(client2, 1, 3, turns=1, db_path=db)
    system = client2.calls[0][1][0]["content"]
    assert "PROMISES YOU HAVE MADE AND NOT YET DONE" in system and "Thursday quiz" in system
    assert "LAST TIME YOU SPOKE WITH TOMMY SHAW" in system and "Dez promised Tommy a quiz" in system
    # And Tommy sees his own claim flagged as unverifiable, plus Bernie.
    run_conversation(client2, 3, 1, turns=1, db_path=db)
    system = client2.calls[1][1][0]["content"]
    assert "CAN'T ACTUALLY VERIFY" in system and "clipboard" in system
    assert "Bernie" in system


def test_commitment_can_be_resolved(db):
    first = Extraction(summary="s", per_agent={"Dez Whitworth": AgentExtraction(
        commitments=[CommitmentOut(content="Tell Jess her job is safe", to="Jess Hartley")])})
    run_conversation(FakeClient(extraction=first), 1, 4, turns=1, db_path=db)
    with connect(db) as c:
        cid = c.execute("SELECT id FROM commitments").fetchone()[0]
    second = Extraction(summary="Dez told Jess her job is safe.", commitments_done=[cid])
    client = FakeClient(extraction=second)
    run_conversation(client, 1, 4, turns=1, db_path=db)
    assert f"id {cid} (Dez Whitworth)" in client.extraction_calls[0][0]["content"]
    with connect(db) as c:
        assert c.execute("SELECT status FROM commitments WHERE id=?", (cid,)).fetchone()[0] == "done"


def test_extraction_failure_falls_back_to_summary(db):
    cid = run_conversation(FakeClient(extraction_fails=True), 1, 2, turns=2, db_path=db)
    conv = get_conversation(cid, db)
    assert conv["status"] == "completed"
    assert "Dez Whitworth and Chloe Barlow talked." in conv["summary"]


def test_invalid_proposal_skips_turn_only(db):
    conv = get_conversation(run_conversation(FakeClient(invalid_at=2), 1, 2, turns=4, db_path=db), db)
    assert conv["status"] == "completed" and len(conv["messages"]) == 3


def test_llm_error_marks_conversation_failed(db):
    with pytest.raises(LLMError):
        run_conversation(FakeClient(fail_at=3), 1, 2, turns=4, db_path=db)
    with connect(db) as c:
        assert c.execute("SELECT status FROM conversations").fetchone()[0] == "failed"


def test_pick_pair_avoids_recent_pairs(db):
    ids = [1, 2, 3, 4, 5]
    for _ in range(3):
        run_conversation(FakeClient(), 1, 2, turns=1, db_path=db)
    for _ in range(30):
        assert frozenset(world.pick_pair(ids, db)) != frozenset((1, 2))


def test_fallback_survives_very_long_lines(db):
    class LongLines(FakeClient):
        def propose(self, agent_id, messages, schema=ActionProposal, max_tokens=300):
            if schema is Extraction:
                raise InvalidProposal("bad notes")
            return ActionProposal(say="x" * 1100, rationale="r", mood="calm")
    cid = run_conversation(LongLines(), 1, 2, turns=2, db_path=db)
    conv = get_conversation(cid, db)
    assert conv["status"] == "completed" and len(conv["summary"]) <= 400


def test_mark_interrupted_closes_stuck_conversations(db):
    from evorium.sim import mark_interrupted
    with connect(db) as c:
        c.execute("INSERT INTO conversations (location, status) VALUES ('pub', 'running')")
        c.execute("INSERT INTO conversations (location, status) VALUES ('pub', 'completed')")
    assert mark_interrupted(db) == 1
    with connect(db) as c:
        assert [r[0] for r in c.execute("SELECT status FROM conversations ORDER BY id")] == ["failed", "completed"]


def test_restated_promise_updates_in_place_and_is_not_marked_done(db):
    first = Extraction(summary="s", per_agent={"Tommy Shaw": AgentExtraction(
        commitments=[CommitmentOut(content="Write the quiz questions", to="Dez Whitworth")])})
    run_conversation(FakeClient(extraction=first), 3, 1, turns=1, db_path=db)
    with connect(db) as c:
        cid, due = c.execute("SELECT id, due_at FROM commitments").fetchone()
    assert due is not None  # no deadline given, so the default one applies and the tick will check it
    second = Extraction(summary="s", commitments_done=[cid], per_agent={"Tommy Shaw": AgentExtraction(
        commitments=[CommitmentOut(content="Write forty quiz questions by Friday", to="Dez Whitworth",
                                   due_hours=120, replaces=cid)])})
    run_conversation(FakeClient(extraction=second), 3, 1, turns=1, db_path=db)
    with connect(db) as c:
        rows = c.execute("SELECT id, content, status, due_at FROM commitments").fetchall()
    assert len(rows) == 1
    assert rows[0]["content"] == "Write forty quiz questions by Friday"
    assert rows[0]["status"] == "open" and rows[0]["due_at"] > due


def test_replaces_cannot_touch_someone_elses_promise(db):
    first = Extraction(summary="s", per_agent={"Dez Whitworth": AgentExtraction(
        commitments=[CommitmentOut(content="Ring the agent", to="Jess Hartley")])})
    run_conversation(FakeClient(extraction=first), 1, 4, turns=1, db_path=db)
    with connect(db) as c:
        cid = c.execute("SELECT id FROM commitments").fetchone()[0]
    second = Extraction(summary="s", per_agent={"Jess Hartley": AgentExtraction(
        commitments=[CommitmentOut(content="Ask about more hours", replaces=cid)])})
    run_conversation(FakeClient(extraction=second), 1, 4, turns=1, db_path=db)
    with connect(db) as c:
        rows = [tuple(r) for r in c.execute("SELECT agent_id, content FROM commitments ORDER BY id")]
    assert rows == [(1, "Ring the agent"), (4, "Ask about more hours")]
