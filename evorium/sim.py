"""Conversation runner. Python owns the state; the model proposes lines, then takes notes."""

import logging
import random
from pathlib import Path

from evorium import world
from evorium.db import DEFAULT_DB_PATH, connect
from evorium.events import emit
from evorium.llm import InvalidProposal, LLMError
from evorium.memory import DUE_FMT, knowledge_for_prompt, open_commitments, store_extraction
from evorium.models import Extraction
from evorium.prompts import build_extraction_messages, build_messages

logger = logging.getLogger(__name__)
EXTRACTION_MAX_TOKENS = 900


def _agent(connection, agent_id: int) -> dict:
    row = connection.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if row is None:
        raise ValueError(f"No agent with id {agent_id}")
    return dict(row)


def get_conversation(conversation_id: int, db_path: str | Path = DEFAULT_DB_PATH) -> dict | None:
    with connect(db_path) as connection:
        conv = connection.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        if conv is None:
            return None
        messages = connection.execute(
            """SELECT m.id, m.speaker_id, a.name AS speaker_name, m.text, m.rationale, m.sim_time, m.created_at
               FROM messages m JOIN agents a ON a.id = m.speaker_id
               WHERE m.conversation_id = ? ORDER BY m.id""",
            (conversation_id,),
        ).fetchall()
    return {**dict(conv), "messages": [dict(m) for m in messages]}


def latest_conversation_id(db_path: str | Path = DEFAULT_DB_PATH) -> int | None:
    with connect(db_path) as connection:
        row = connection.execute("SELECT id FROM conversations ORDER BY id DESC LIMIT 1").fetchone()
    return row["id"] if row else None


def mark_interrupted(db_path: str | Path = DEFAULT_DB_PATH) -> int:
    """On startup: any conversation still 'running' was cut off by a crash or restart."""
    with connect(db_path) as connection:
        cur = connection.execute(
            """UPDATE conversations SET status='failed', summary=COALESCE(summary, 'Interrupted — notes unavailable.'),
               ended_at=COALESCE(ended_at, strftime('%Y-%m-%dT%H:%M:%fZ','now')) WHERE status='running'""")
    return cur.rowcount


def _set_status(db_path, conversation_id, status, summary=None):
    with connect(db_path) as connection:
        connection.execute(
            "UPDATE conversations SET status=?, summary=COALESCE(?, summary), "
            "ended_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
            (status, summary, conversation_id),
        )


def _take_notes(client, db_path, conversation_id, a, b, transcript, sim_label):
    """Second model call: extract facts, commitments, people. Falls back to a plain summary."""
    with connect(db_path) as connection:
        cast = [r["name"] for r in connection.execute("SELECT name FROM agents WHERE kind!='system'")]
        known = [f"{r['name']}: {r['content']}" for r in connection.execute(
            """SELECT ag.name, f.content FROM facts f JOIN agents ag ON ag.id=f.agent_id
               WHERE f.agent_id IN (?, ?) AND f.source IN ('seed','observed') ORDER BY f.id""", (a["id"], b["id"]))]
        opens = [{"id": c["id"], "owner": who["name"], "content": c["content"]}
                 for who in (a, b) for c in open_commitments(connection, who["id"])]
    messages = build_extraction_messages(a, b, transcript, known, opens, cast, sim_label)
    try:
        extraction = client.propose(a["id"], messages, schema=Extraction, max_tokens=EXTRACTION_MAX_TOKENS)
    except (InvalidProposal, LLMError) as exc:
        emit(f"Note-taking failed ({exc}); saving a plain summary instead.", "error")
        last_a = next((t["text"] for t in reversed(transcript) if t["speaker_name"] == a["name"]), "")
        last_b = next((t["text"] for t in reversed(transcript) if t["speaker_name"] == b["name"]), "")
        extraction = Extraction(summary=f'{a["name"]} and {b["name"]} talked. {a["name"]}: "{last_a[:120]}" {b["name"]}: "{last_b[:120]}"')
    with connect(db_path) as connection:
        counts = store_extraction(connection, conversation_id, {a["name"]: a, b["name"]: b}, extraction, world.now(db_path))
        for who in (a, b):
            connection.execute(
                "INSERT INTO memories (agent_id, content, importance, source_conversation_id) VALUES (?, ?, 5, ?)",
                (who["id"], f"{sim_label}: {extraction.summary}", conversation_id))
    emit(f"Notes: {counts['facts']} facts, {counts['commitments']} promises, {counts['people']} new people, "
         f"{counts['resolved']} promises resolved, {counts['updated']} updated. Summary: {extraction.summary}")
    return extraction.summary


def run_conversation(client, agent_a_id: int, agent_b_id: int, turns: int = 4,
                     db_path: str | Path = DEFAULT_DB_PATH) -> int:
    now = world.now(db_path)
    sim_label = world.describe(now)
    with connect(db_path) as connection:
        a, b = _agent(connection, agent_a_id), _agent(connection, agent_b_id)
        conversation_id = connection.execute(
            "INSERT INTO conversations (location, status, sim_time, agent_a_id, agent_b_id, sim_at) VALUES (?, 'running', ?, ?, ?, ?)",
            (a["location"], sim_label, a["id"], b["id"], now.strftime(DUE_FMT)),
        ).lastrowid

    transcript: list[dict] = []
    emit(f"[{sim_label}] Conversation #{conversation_id}: {a['name']} and {b['name']}, {turns} turns.")
    try:
        for turn in range(turns):
            speaker, listener = (a, b) if turn % 2 == 0 else (b, a)
            with connect(db_path) as connection:
                speaker.update(_agent(connection, speaker["id"]))
                knowledge = knowledge_for_prompt(connection, speaker, listener)
            messages = build_messages(speaker, listener, transcript, knowledge, sim_label)
            emit(f"Turn {turn + 1}/{turns}: {speaker['name']} (mood {speaker['mood']}; knows {len(knowledge['certain'])} facts, "
                 f"told {len(knowledge['told'])}, {len(knowledge['promises'])} open promises) — asking DeepSeek…")
            try:
                proposal = client.propose(speaker["id"], messages)
            except InvalidProposal:
                emit(f"Turn {turn + 1} skipped — {speaker['name']} gave invalid JSON twice.", "error")
                continue
            emit(f"{speaker['name']}: “{proposal.say}”")
            emit(f"   why: {proposal.rationale} · mood → {proposal.mood.lower()}")
            with connect(db_path) as connection:
                connection.execute(
                    "INSERT INTO messages (conversation_id, speaker_id, text, rationale, sim_time) VALUES (?, ?, ?, ?, ?)",
                    (conversation_id, speaker["id"], proposal.say, proposal.rationale, sim_label))
                connection.execute("UPDATE agents SET mood = ? WHERE id = ?", (proposal.mood.lower(), speaker["id"]))
            transcript.append({"speaker_name": speaker["name"], "text": proposal.say})
    except LLMError as exc:
        emit(f"Conversation #{conversation_id} FAILED: {exc}", "error")
        _set_status(db_path, conversation_id, "failed")
        raise

    summary = None
    if transcript:
        try:
            summary = _take_notes(client, db_path, conversation_id, a, b, transcript, sim_label)
        except Exception as exc:  # bookkeeping must never leave a conversation stuck as 'running'
            logger.exception("Note-taking crashed for conversation %s", conversation_id)
            emit(f"Note-taking crashed ({type(exc).__name__}); conversation saved without notes.", "error")
            summary = f"{a['name']} and {b['name']} talked (notes unavailable)."
    _set_status(db_path, conversation_id, "completed", summary)
    emit(f"Conversation #{conversation_id} completed with {len(transcript)} lines.")
    return conversation_id
