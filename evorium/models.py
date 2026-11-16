"""Validated records and the model's bounded dialogue proposal."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Agent(BaseModel):
    id: int
    name: str
    age: int
    occupation: str
    background: str
    personality: str
    current_goal: str
    mood: str
    location: str
    created_at: str


class Message(BaseModel):
    id: int
    conversation_id: int
    speaker_id: int
    text: str
    rationale: str
    sim_time: str
    created_at: str


class LLMCall(BaseModel):
    id: int
    agent_id: int
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    est_cost_usd: float = Field(ge=0)
    ok: bool
    error: str | None
    created_at: str


class ActionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    say: str = Field(min_length=1, max_length=1200)
    rationale: str = Field(min_length=1, max_length=600)
    mood: str = Field(min_length=1, max_length=40)

    @field_validator("mood")
    @classmethod
    def one_word(cls, value: str) -> str:
        if len(value.split()) != 1:
            raise ValueError("Mood must be one word.")
        return value


# --- Post-conversation extraction (second model call per conversation) ---

class FactOut(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    subject: str = Field(min_length=1, max_length=60)
    content: str = Field(min_length=1, max_length=300)
    source: Literal["observed", "told", "claim"]
    told_by: str | None = None


class CommitmentOut(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    content: str = Field(min_length=1, max_length=200)
    to: str | None = None
    due_hours: int | None = Field(default=None, ge=1, le=24 * 60)
    replaces: int | None = None  # id of an open commitment this one restates with new detail or a new deadline


class PromiseCheck(BaseModel):
    """Answer to 'did you actually do what you promised?' asked by the world tick."""
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    done: bool
    what_happened: str = Field(min_length=1, max_length=300)
    mood: str = Field(min_length=1, max_length=40)


class PersonOut(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=60)
    description: str = Field(min_length=1, max_length=200)


class Feeling(BaseModel):
    model_config = ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    trust_change: int = Field(ge=-2,le=2)
    warmth_change: int = Field(ge=-2,le=2)
    reason: str = Field(max_length=300)


class AgentExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    feeling: Feeling | None = None
    facts: list[FactOut] = Field(default_factory=list, max_length=8)
    commitments: list[CommitmentOut] = Field(default_factory=list, max_length=5)
    new_people: list[PersonOut] = Field(default_factory=list, max_length=3)


def _clip(value, n: int):
    return value[:n] if isinstance(value, str) else value


def _plain(x):
    if isinstance(x, BaseModel):
        return x.model_dump()
    if isinstance(x, dict):
        return {k: _plain(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_plain(v) for v in x]
    return x


def _normalise_extraction(data):
    """Be lenient with the note-taker: clip, coerce and drop rather than reject the whole thing."""
    if not isinstance(data, dict):
        return data
    data = _plain(dict(data))
    data["summary"] = _clip(str(data.get("summary") or "").strip(), 400) or "They talked."
    per_agent = data.get("per_agent") or {}
    if not isinstance(per_agent, dict):
        per_agent = {}
    cleaned = {}
    for name, ext in per_agent.items():
        if not isinstance(ext, dict):
            continue
        facts = []
        for f in (ext.get("facts") or [])[:8]:
            if not isinstance(f, dict) or not f.get("content"):
                continue
            source = str(f.get("source") or "claim").lower()
            if source not in ("observed", "told", "claim"):
                source = "told" if f.get("told_by") else "claim"
            facts.append({"subject": _clip(str(f.get("subject") or "general"), 60), "content": _clip(str(f["content"]), 300),
                          "source": source, "told_by": _clip(f.get("told_by"), 60) if f.get("told_by") else None})
        commitments = []
        for c in (ext.get("commitments") or [])[:5]:
            if not isinstance(c, dict) or not c.get("content"):
                continue
            try:
                due = int(c.get("due_hours")) if c.get("due_hours") is not None else None
                due = min(max(due, 1), 24 * 60) if due is not None else None
            except (TypeError, ValueError):
                due = None
            try:
                replaces = int(str(c.get("replaces")).strip().lower().removeprefix("id").strip()) if c.get("replaces") is not None else None
            except (TypeError, ValueError):
                replaces = None
            commitments.append({"content": _clip(str(c["content"]), 200),
                                "to": _clip(c.get("to"), 60) if c.get("to") else None, "due_hours": due,
                                "replaces": replaces})
        people = [{"name": _clip(str(p["name"]), 60), "description": _clip(str(p.get("description") or "mentioned in passing"), 200)}
                  for p in (ext.get("new_people") or [])[:3] if isinstance(p, dict) and p.get("name")]
        feeling = ext.get('feeling')
        if feeling is not None:
            try:
                feeling = Feeling.model_validate(feeling).model_dump()
            except ValueError:
                from evorium.events import emit
                emit('Invalid feeling proposal dropped.', 'error')
                feeling = None
        cleaned[str(name)] = {"facts": facts, "commitments": commitments, "new_people": people, "feeling": feeling}
    data["per_agent"] = cleaned
    done = []
    for x in data.get("commitments_done") or []:
        try:
            done.append(int(str(x).strip().lower().removeprefix("id").strip()))
        except (TypeError, ValueError):
            pass
    data["commitments_done"] = done
    return data


class Extraction(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    summary: str = Field(min_length=1, max_length=400)
    per_agent: dict[str, AgentExtraction] = Field(default_factory=dict)
    commitments_done: list[int] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _lenient(cls, data):
        return _normalise_extraction(data)
