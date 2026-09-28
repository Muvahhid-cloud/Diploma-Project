"""AnthropicProvider: Claude through the official `anthropic` SDK (the only file importing it).

One Messages API call per request. The answer is constrained with structured outputs
(`output_config.format` = JSON Schema of `SpecificationDraft`), which works on every current
Claude model (unlike forced `tool_choice`). Structured outputs do not accept numeric/length
constraints, so they are moved into field descriptions here and enforced by Pydantic
afterwards — the interpreter never trusts the output either way.

The system prompt carries a cache breakpoint: it is static per prompt version, so repeated
generations and the repair call reuse the cached prefix.
"""

import json
import time
from typing import Any

import anthropic

from app.modules.ai.errors import AITimeoutError, AIUnavailableError
from app.modules.ai.providers.base import AIProvider
from app.modules.ai.structured import StructuredRequest, StructuredResult

# JSON Schema keywords structured outputs reject; they are kept as text for the model.
_UNSUPPORTED_KEYWORDS = {
    "minimum": "minimum",
    "maximum": "maximum",
    "exclusiveMinimum": "greater than",
    "exclusiveMaximum": "less than",
    "multipleOf": "multiple of",
    "minLength": "min length",
    "maxLength": "max length",
    "pattern": "pattern",
    "minItems": "min items",
    "maxItems": "max items",
    "uniqueItems": "unique items",
}


def structured_output_schema(schema: Any) -> Any:
    """Copy of `schema` without unsupported constraints (described in `description` instead)."""
    if isinstance(schema, list):
        return [structured_output_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    out: dict[str, Any] = {}
    notes: list[str] = []
    for key, value in schema.items():
        if key in _UNSUPPORTED_KEYWORDS and not isinstance(value, dict):
            notes.append(f"{_UNSUPPORTED_KEYWORDS[key]} {value}")
        elif key == "properties" and isinstance(value, dict):
            out[key] = {name: structured_output_schema(prop) for name, prop in value.items()}
        else:
            out[key] = structured_output_schema(value)
    if notes:
        prefix = f"{out['description']} " if "description" in out else ""
        out["description"] = f"{prefix}({'; '.join(notes)})"
    return out


class AnthropicProvider(AIProvider):
    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        timeout_s: float = 120.0,
        max_retries: int = 1,
        effort: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self._effort = effort
        # `client` is injectable for unit tests (a fake with `messages.create`).
        self._client: Any = client or anthropic.AsyncAnthropic(
            api_key=api_key, base_url=base_url, timeout=timeout_s, max_retries=max_retries
        )

    async def complete_structured(self, request: StructuredRequest) -> StructuredResult:
        output_config: dict[str, Any] = {
            "format": {
                "type": "json_schema",
                "schema": structured_output_schema(request.output_schema),
            }
        }
        if self._effort:
            output_config["effort"] = self._effort
        started = time.perf_counter()
        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=request.max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": request.system,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": m.role, "content": m.content} for m in request.messages],
                output_config=output_config,
            )
        except anthropic.APITimeoutError as exc:
            raise AITimeoutError(f"anthropic: timeout ({exc})") from exc
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            raise AIUnavailableError(
                f"anthropic: credentials rejected ({exc.status_code}); check ANTHROPIC_API_KEY"
            ) from exc
        except anthropic.NotFoundError as exc:
            raise AIUnavailableError(f"anthropic: model or endpoint not found ({exc})") from exc
        except anthropic.RateLimitError as exc:
            raise AIUnavailableError(f"anthropic: rate limited ({exc.status_code})") from exc
        except anthropic.APIStatusError as exc:
            raise AIUnavailableError(f"anthropic: HTTP {exc.status_code} ({exc.message})") from exc
        except anthropic.APIConnectionError as exc:
            raise AIUnavailableError(f"anthropic: connection failed ({exc})") from exc
        latency_ms = round((time.perf_counter() - started) * 1000)

        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        data: dict[str, Any] | None = None
        # A refusal or a max_tokens cut-off may not match the schema: the interpreter treats a
        # missing/invalid object as invalid output (and may repair once).
        if response.stop_reason not in ("refusal", "max_tokens"):
            try:
                parsed = json.loads(text)
            except ValueError:
                parsed = None
            data = parsed if isinstance(parsed, dict) else None
        usage = response.usage
        return StructuredResult(
            data=data,
            raw_output=text,
            model=str(getattr(response, "model", self.model)),
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0)
            + int(getattr(usage, "cache_read_input_tokens", 0) or 0)
            + int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            latency_ms=latency_ms,
            stop_reason=response.stop_reason,
            metadata={
                "cache_read_input_tokens": int(getattr(usage, "cache_read_input_tokens", 0) or 0),
                "request_id": getattr(response, "_request_id", None),
            },
        )
