"""AnthropicProvider against a fake SDK client (no network, no API key)."""

import json
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest

from app.modules.ai.errors import AITimeoutError, AIUnavailableError
from app.modules.ai.prompts.generation import build_generation_request
from app.modules.ai.prompts.shared import output_schema_json
from app.modules.ai.providers.anthropic import AnthropicProvider, structured_output_schema
from tests.ai.helpers import DEMO_PROMPT, context, valid_draft


class FakeMessages:
    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def response(text: str, stop_reason: str = "end_turn") -> Any:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        model="claude-opus-5",
        usage=SimpleNamespace(
            input_tokens=1200,
            output_tokens=800,
            cache_read_input_tokens=3000,
            cache_creation_input_tokens=0,
        ),
    )


def provider(outcome: Any, effort: str | None = None) -> tuple[AnthropicProvider, FakeMessages]:
    messages = FakeMessages(outcome)
    client = SimpleNamespace(messages=messages)
    return (
        AnthropicProvider(api_key="unused", model="claude-opus-5", effort=effort, client=client),
        messages,
    )


def request() -> Any:
    return build_generation_request(DEMO_PROMPT, options=None, context=context(), max_tokens=16000)


async def test_structured_output_request_shape() -> None:
    p, messages = provider(response(json.dumps(valid_draft())), effort="medium")
    await p.complete_structured(request())
    call = messages.calls[0]
    assert call["model"] == "claude-opus-5" and call["max_tokens"] == 16000
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert call["messages"][0]["role"] == "user"
    assert DEMO_PROMPT in call["messages"][0]["content"]
    fmt = call["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    assert call["output_config"]["effort"] == "medium"
    assert "tools" not in call and "tool_choice" not in call and "temperature" not in call


async def test_parses_the_json_answer_and_usage() -> None:
    draft = valid_draft()
    p, _ = provider(response(json.dumps(draft)))
    result = await p.complete_structured(request())
    assert result.data == draft
    assert result.model == "claude-opus-5"
    assert result.input_tokens == 4200 and result.output_tokens == 800
    assert result.metadata["cache_read_input_tokens"] == 3000


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
async def test_refusal_or_truncation_yields_no_data(stop_reason: str) -> None:
    p, _ = provider(response('{"outcome": "specifi', stop_reason))
    result = await p.complete_structured(request())
    assert result.data is None and result.stop_reason == stop_reason


async def test_non_object_json_yields_no_data() -> None:
    p, _ = provider(response("[1, 2]"))
    assert (await p.complete_structured(request())).data is None


def _http_error(cls: type[anthropic.APIStatusError], status: int) -> anthropic.APIStatusError:
    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("boom", response=httpx2.Response(status, request=req), body=None)


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (anthropic.APITimeoutError(request=httpx2.Request("POST", "https://x")), AITimeoutError),
        (
            anthropic.APIConnectionError(request=httpx2.Request("POST", "https://x")),
            AIUnavailableError,
        ),
    ],
)
async def test_transport_errors_are_mapped(exc: Exception, expected: type[Exception]) -> None:
    p, _ = provider(exc)
    with pytest.raises(expected):
        await p.complete_structured(request())


@pytest.mark.parametrize(
    ("cls", "status"),
    [
        (anthropic.AuthenticationError, 401),
        (anthropic.RateLimitError, 429),
        (anthropic.InternalServerError, 500),
        (anthropic.BadRequestError, 400),
    ],
)
async def test_http_errors_are_mapped(cls: type[anthropic.APIStatusError], status: int) -> None:
    p, _ = provider(_http_error(cls, status))
    with pytest.raises(AIUnavailableError) as info:
        await p.complete_structured(request())
    assert "unused" not in info.value.detail  # the key never appears in errors


def test_structured_output_schema_drops_unsupported_constraints() -> None:
    original = output_schema_json()
    schema = structured_output_schema(original)
    text = json.dumps(schema)
    for keyword in ('"minimum"', '"maximum"', '"minLength"', '"maxLength"', '"maxItems"'):
        assert keyword not in text
    # Constraints survive as text for the model; Pydantic still enforces them.
    targets = schema["$defs"]["Targets"]["properties"]["storeys"]
    assert "minimum 1" in targets["description"] and "maximum 3" in targets["description"]
    assert schema["$defs"]["BuildingSpecification"]["additionalProperties"] is False
    assert original["$defs"]["Targets"]["properties"]["storeys"]["maximum"] == 3  # not mutated


def test_property_named_like_a_keyword_is_kept() -> None:
    schema = {
        "type": "object",
        "properties": {"pattern": {"type": "string", "maxLength": 3}},
        "additionalProperties": False,
    }
    out = structured_output_schema(schema)
    assert out["properties"]["pattern"] == {"type": "string", "description": "(max length 3)"}
