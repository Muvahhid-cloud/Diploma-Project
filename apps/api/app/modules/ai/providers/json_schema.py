"""Vendor-neutral JSON Schema preparation for structured outputs.

Claude's structured outputs (direct or through a gateway such as OpenRouter) do not accept
numeric/length constraints, so they are moved into field descriptions here and enforced by
Pydantic afterwards — the interpreter never trusts the output either way.
"""

from typing import Any

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
