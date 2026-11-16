"""DeepSeek JSON client with persistent usage accounting and validated proposals."""

import logging
import math
import runpy
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from evorium.db import DEFAULT_DB_PATH, connect
from evorium.events import emit
from evorium.models import ActionProposal

logger = logging.getLogger(__name__)
ENDPOINT = "https://api.deepseek.com/chat/completions"
MAX_OUTPUT_TOKENS = 300


class LLMError(RuntimeError):
    """Safe error text that may be shown in the dashboard."""


class InvalidProposal(LLMError):
    pass


@dataclass(frozen=True)
class Settings:
    api_key: str
    model: str = "deepseek-flash"
    input_usd_per_million: float = 0.30
    output_usd_per_million: float = 1.20
    max_spend_usd: float = 4.00

    def __post_init__(self):
        for value in (self.input_usd_per_million, self.output_usd_per_million, self.max_spend_usd):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Token rates and spend cap must be finite positive numbers.")

    @classmethod
    def from_config(cls):
        # Load this project's exact config.py, independent of cwd and sys.path.
        path = Path(__file__).resolve().parent.parent / "config.py"
        if not path.is_file():
            raise LLMError("Copy config.example.py to config.py and set your DeepSeek API key.")
        values = runpy.run_path(str(path))
        return cls(
            api_key=values.get("DEEPSEEK_API_KEY", ""),
            model=values.get("DEEPSEEK_MODEL", "deepseek-flash"),
            input_usd_per_million=values.get("INPUT_USD_PER_MILLION", 0.30),
            output_usd_per_million=values.get("OUTPUT_USD_PER_MILLION", 1.20),
            max_spend_usd=values.get("MAX_SPEND_USD", 4.00),
        )


class _Usage(BaseModel):
    model_config = ConfigDict(strict=True)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)


def estimate_cost(input_tokens: int, output_tokens: int, settings: Settings) -> Decimal:
    return (
        Decimal(input_tokens) * Decimal(str(settings.input_usd_per_million))
        + Decimal(output_tokens) * Decimal(str(settings.output_usd_per_million))
    ) / Decimal(1_000_000)


def get_usage(db_path: str | Path = DEFAULT_DB_PATH, initial_credit_usd: float = 5.00) -> dict:
    with connect(db_path) as connection:
        rows = connection.execute(
            "SELECT input_tokens, output_tokens, est_cost_usd FROM llm_calls"
        ).fetchall()
    spend = sum((Decimal(str(row["est_cost_usd"])) for row in rows), Decimal(0))
    input_tokens = sum(row["input_tokens"] for row in rows)
    output_tokens = sum(row["output_tokens"] for row in rows)
    return {
        "api_calls": len(rows), "input_tokens": input_tokens,
        "output_tokens": output_tokens, "total_tokens": input_tokens + output_tokens,
        "estimated_spend_usd": float(spend), "initial_credit_usd": initial_credit_usd,
        "estimated_remaining_usd": float(max(Decimal(0), Decimal(str(initial_credit_usd)) - spend)),
    }


class DeepSeekClient:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH,
                 settings: Settings | None = None, client: httpx.Client | None = None):
        self.db_path = db_path
        self.settings = settings if settings is not None else Settings.from_config()
        self._client = client

    def propose(self, agent_id: int, messages: list[dict[str, str]],
                schema: type[BaseModel] = ActionProposal, max_tokens: int = MAX_OUTPUT_TOKENS):
        if not self.settings.api_key or self.settings.api_key == "sk-...":
            raise LLMError("Set DEEPSEEK_API_KEY in config.py before running a conversation.")
        spent = get_usage(self.db_path)["estimated_spend_usd"]
        if spent >= self.settings.max_spend_usd:
            raise LLMError(
                f"Local budget cap reached (${spent:.2f} of ${self.settings.max_spend_usd:.2f}). "
                "Raise MAX_SPEND_USD in config.py to continue."
            )
        # At most two requests. Only invalid dialogue JSON/schema gets a retry.
        for attempt in range(2):
            try:
                return self._attempt(agent_id, messages, schema, max_tokens)
            except InvalidProposal:
                if attempt == 1:
                    logger.warning("Agent %s: invalid dialogue after two attempts; skipping.", agent_id)
                    raise InvalidProposal("Model returned invalid dialogue twice; turn skipped.") from None
        raise AssertionError("Unreachable")

    def _start_call(self, agent_id: int) -> int:
        # Record attempts before network I/O, including interrupted requests.
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """INSERT INTO llm_calls
                (agent_id, model, input_tokens, output_tokens, est_cost_usd, ok, error)
                VALUES (?, ?, ?, ?, ?, 0, ?)""",
                (agent_id, self.settings.model, 0, 0, 0,
                 "Pending or interrupted call; usage unavailable, cost unknown."),
            )
            return cursor.lastrowid

    def _attempt(self, agent_id: int, messages: list[dict[str, str]],
                 schema: type[BaseModel] = ActionProposal, max_tokens: int = MAX_OUTPUT_TOKENS):
        payload = {
            "model": self.settings.model, "messages": messages,
            "temperature": 0.8 if schema is ActionProposal else 0.2, "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
        }
        call_id = self._start_call(agent_id)
        input_tokens, output_tokens = 0, 0
        usage_available = False
        proposal, failure = None, None
        try:
            headers = {"Authorization": f"Bearer {self.settings.api_key}"}
            if self._client is None:
                with httpx.Client(timeout=30.0) as client:
                    response = client.post(ENDPOINT, json=payload, headers=headers)
            else:
                response = self._client.post(ENDPOINT, json=payload, headers=headers, timeout=30.0)
            response.raise_for_status()
            body = response.json()
            usage = _Usage.model_validate(body["usage"])
            input_tokens, output_tokens = usage.prompt_tokens, usage.completion_tokens
            usage_available = True
            try:
                content = body["choices"][0]["message"]["content"]
                proposal = schema.model_validate_json(content)
                if body["choices"][0].get("finish_reason") != "stop":
                    raise ValueError("Incomplete response")
            except ValidationError as exc:
                first = exc.errors()[0] if exc.errors() else {}
                emit(f"Schema rejected {schema.__name__}: {'.'.join(str(p) for p in first.get('loc', ()))} — {first.get('msg', '')}"[:200], "error")
                failure = InvalidProposal("Model returned invalid or incomplete dialogue JSON.")
            except (KeyError, IndexError, TypeError, ValueError):
                failure = InvalidProposal("Model returned invalid or incomplete dialogue JSON.")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 402:
                failure = LLMError("DeepSeek account balance exhausted. Add credit to continue.")
            else:
                failure = LLMError(f"DeepSeek HTTP {exc.response.status_code}; check your key or account.")
        except httpx.RequestError:
            failure = LLMError("DeepSeek connection failed or timed out; no automatic network retry.")
        except (KeyError, IndexError, TypeError, ValueError, ValidationError):
            failure = LLMError("DeepSeek response lacks valid usage data; tokens and cost unknown.")
        error = str(failure) if failure else None
        if failure and not usage_available:
            error += " Usage unavailable; recorded token/cost zeros are placeholders."
        # Never persist provider response bodies, prompts, headers, or exception text.
        with connect(self.db_path) as connection:
            connection.execute(
                """UPDATE llm_calls SET input_tokens=?, output_tokens=?, est_cost_usd=?,
                   ok=?, error=? WHERE id=?""",
                (input_tokens, output_tokens, float(estimate_cost(input_tokens, output_tokens, self.settings)),
                 int(failure is None), error, call_id),
            )
        if failure:
            emit(f"DeepSeek call failed: {error}", "error")
            raise failure
        emit(f"DeepSeek replied: {input_tokens} in / {output_tokens} out tokens, "
             f"≈${float(estimate_cost(input_tokens, output_tokens, self.settings)):.5f}")
        return proposal
