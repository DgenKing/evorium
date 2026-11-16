"""Fake HTTP only: validation and accounting; local spending cap removed by user."""

import json

import httpx
import pytest
from pydantic import ValidationError

from evorium.db import connect, init_db
from evorium.llm import DeepSeekClient, InvalidProposal, LLMError, Settings, get_usage
from evorium.models import ActionProposal
from evorium.seed import seed_agents

GOOD = {"say": "Any news on the lease?", "rationale": "Dez wants reassurance.", "mood": "worried"}
MESSAGES = [{"role": "user", "content": "Return a JSON dialogue proposal."}]


@pytest.fixture
def world(tmp_path):
    path = tmp_path / "world.sqlite3"
    init_db(path)
    seed_agents(path)
    return path


def response(content, **overrides):
    body = {
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 30},
    }
    body.update(overrides)
    return httpx.Response(200, json=body)


def calls(path):
    with connect(path) as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM llm_calls ORDER BY id")]


def test_valid_response_request_contract_and_persistent_usage(world):
    def handler(request):
        assert str(request.url) == "https://api.deepseek.com/chat/completions"
        assert request.headers["authorization"] == "Bearer fake-test-key"
        payload = json.loads(request.content)
        assert payload == {
            "model": "deepseek-flash", "messages": MESSAGES, "temperature": 0.8,
            "max_tokens": 300, "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
        }
        assert len(calls(world)) == 1  # Attempt persisted before network.
        return response(json.dumps(GOOD))

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        proposal = DeepSeekClient(world, Settings("fake-test-key"), http).propose(1, MESSAGES)
    assert proposal.say == GOOD["say"]
    row, = calls(world)
    assert row["input_tokens"] == 100
    assert row["output_tokens"] == 30
    assert row["est_cost_usd"] == pytest.approx(0.000066)
    assert row["ok"] == 1
    assert row["error"] is None
    init_db(world)
    assert get_usage(world)["total_tokens"] == 130
    assert get_usage(world)["estimated_spend_usd"] == pytest.approx(0.000066)


@pytest.mark.parametrize("bad", [
    "not JSON", "{}", "[]", '"hello"',
    json.dumps({**GOOD, "mood": "very worried"}),
    json.dumps({**GOOD, "say": "  "}),
    json.dumps({**GOOD, "say": 123}),
    json.dumps({**GOOD, "move_to": "London"}),
])
def test_invalid_proposal_retried_once_and_never_changes_world(world, bad, caplog):
    with httpx.Client(transport=httpx.MockTransport(lambda request: response(bad))) as http:
        with pytest.raises(InvalidProposal, match="twice"):
            DeepSeekClient(world, Settings("fake-test-key"), http).propose(1, MESSAGES)
    rows = calls(world)
    assert len(rows) == 2
    assert all(row["ok"] == 0 and row["input_tokens"] == 100 for row in rows)
    assert get_usage(world)["total_tokens"] == 260
    with connect(world) as connection:
        assert connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0
        assert connection.execute("SELECT mood FROM agents WHERE id=1").fetchone()[0] == "worried"
    assert "skipping" in caplog.text


def test_valid_retry_records_both_calls(world):
    responses = iter([response("bad JSON"), response(json.dumps(GOOD))])
    with httpx.Client(transport=httpx.MockTransport(lambda request: next(responses))) as http:
        proposal = DeepSeekClient(world, Settings("fake-test-key"), http).propose(1, MESSAGES)
    assert proposal.mood == "worried"
    assert [row["ok"] for row in calls(world)] == [0, 1]


def test_budget_cap_blocks_new_requests(world):
    with connect(world) as connection:
        connection.execute(
            """INSERT INTO llm_calls
               (agent_id, model, input_tokens, output_tokens, est_cost_usd, ok)
               VALUES (1, 'deepseek-flash', 100, 30, 4.00, 1)"""
        )
    hit = []
    with httpx.Client(transport=httpx.MockTransport(
        lambda request: (hit.append(1), response(json.dumps(GOOD)))[1]
    )) as http:
        with pytest.raises(LLMError, match="budget cap"):
            DeepSeekClient(world, Settings("fake-test-key", max_spend_usd=4.00), http).propose(1, MESSAGES)
    assert hit == []                      # no network request was made
    assert len(calls(world)) == 1         # nothing new recorded
    assert get_usage(world)["estimated_remaining_usd"] == 1.0


@pytest.mark.parametrize("status", [401, 402, 429, 500])
def test_provider_errors_recorded_without_retries_or_secret_leaks(world, status):
    with httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(status, text="secret provider body")
    )) as http:
        with pytest.raises(LLMError) as error:
            DeepSeekClient(world, Settings("fake-test-key"), http).propose(1, MESSAGES)
    if status == 402:
        assert "balance exhausted" in str(error.value)
    row, = calls(world)
    assert row["ok"] == 0
    assert "Usage unavailable" in row["error"]
    assert "fake-test-key" not in str(row)
    assert "secret provider body" not in str(row)


def test_timeout_records_attempt_and_does_not_retry(world):
    def handler(request):
        raise httpx.ReadTimeout("sensitive upstream details", request=request)
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(LLMError, match="timed out"):
            DeepSeekClient(world, Settings("fake-test-key"), http).propose(1, MESSAGES)
    row, = calls(world)
    assert "sensitive" not in row["error"]


def test_missing_usage_rejected_and_marked_unknown(world):
    with httpx.Client(transport=httpx.MockTransport(
        lambda request: response(json.dumps(GOOD), usage={})
    )) as http:
        with pytest.raises(LLMError, match="usage"):
            DeepSeekClient(world, Settings("fake-test-key"), http).propose(1, MESSAGES)
    row, = calls(world)
    assert row["ok"] == 0
    assert "unknown" in row["error"]


def test_truncated_response_is_rejected_even_if_json_valid(world):
    def handler(request):
        result = response(json.dumps(GOOD))
        body = result.json()
        body["choices"][0]["finish_reason"] = "length"
        return httpx.Response(200, json=body)
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(InvalidProposal):
            DeepSeekClient(world, Settings("fake-test-key"), http).propose(1, MESSAGES)
    assert len(calls(world)) == 2


def test_placeholder_key_never_attempts_http(world):
    def handler(request):
        pytest.fail("Placeholder key must not cause a request")
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(LLMError, match="API_KEY"):
            DeepSeekClient(world, Settings("sk-..."), http).propose(1, MESSAGES)
    assert calls(world) == []


def test_whitespace_is_trimmed():
    assert ActionProposal(**{**GOOD, "say": " Hello. "}).say == "Hello."
    with pytest.raises(ValidationError):
        ActionProposal(**{**GOOD, "mood": " "})
