"""Export the canonical BuildingModel JSON Schema (consumed by packages/schema codegen).

Usage:  python -m app.modules.building.export_schema <output.json>
"""

import json
import sys
from pathlib import Path
from typing import Any

from app.modules.building.model import SCHEMA_VERSION, BuildingModel


def _strip_property_titles(node: Any) -> Any:
    """Pydantic titles every property ("Id", "Name", ...); code generators turn each into a
    named alias type. Keep titles only on models/enums ($defs), which name real types."""
    if isinstance(node, dict):
        out = {k: _strip_property_titles(v) for k, v in node.items()}
        props = out.get("properties")
        # Only object *schemas* (not a properties map that has a field named "properties").
        if out.get("type") == "object" and isinstance(props, dict):
            out["properties"] = {
                name: {k: v for k, v in prop.items() if k != "title"}
                for name, prop in props.items()
            }
        return out
    if isinstance(node, list):
        return [_strip_property_titles(v) for v in node]
    return node


def building_model_json_schema() -> dict[str, Any]:
    # Serialization mode: exactly the shape the API emits (defaulted fields are required).
    schema = _strip_property_titles(BuildingModel.model_json_schema(mode="serialization"))
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$comment": f"GENERATED from Pydantic (schema_version {SCHEMA_VERSION}). Do not edit.",
        **schema,
    }


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m app.modules.building.export_schema <output.json>")
    text = json.dumps(building_model_json_schema(), indent=2, ensure_ascii=False) + "\n"
    Path(sys.argv[1]).write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
