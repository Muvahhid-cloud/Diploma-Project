"""Pieces shared by the generation and repair prompts.

The vocabulary section is generated from the specification enums, so the prompt can never
offer a room type, style or feature the schema (and the layout engine) does not support.
"""

import json
import re
from functools import cache
from typing import Any

from app.modules.ai.context import GenerationContext
from app.modules.ai.schemas.generation import GenerationOptions, SpecificationDraft
from app.modules.building.appearance import PALETTE
from app.modules.building.enums import RoofType
from app.modules.building.facades import FACADE_SYNONYMS
from app.modules.building.specification import (
    ArchitecturalStyle,
    FacadeMaterial,
    FacadeSide,
    FinishLevel,
    InteriorStyle,
    RoomFeature,
    SpecRoomType,
    WindowStyle,
)

PROMPT_VERSION = "building-generation@2"  # @2 (K3): design systems and design intent
OUTPUT_NAME = "building_specification_draft"
OUTPUT_DESCRIPTION = (
    "The interpreted building request: a BuildingSpecification (intent only, no geometry) "
    "or clarification questions."
)
USER_TAG = "building_request"


def _values(enum: Any) -> str:
    return ", ".join(e.value for e in enum)


def vocabulary() -> str:
    return "\n".join(
        [
            "- building_type: single_family_house (residential, 1 to 3 storeys, rectilinear).",
            f"- rooms[].type: {_values(SpecRoomType)}.",
            f"- rooms[].features (bedrooms only): {_values(RoomFeature)}.",
            "- Circulation (entrance hall, corridors, stair core) is added by the layout engine;"
            " never request it.",
            "- features.garage: attached, ground floor, 1 to 3 cars.",
            "- features.balconies: on upper floors only (level >= 1); side garden|street.",
            "- features.terrace: one ground-floor terrace on the garden side.",
            f"- style.architectural_style: {_values(ArchitecturalStyle)}.",
            f"- style.interior_style: {_values(InteriorStyle)}.",
            f"- style.roof.type: {_values(RoofType)} (pitch_deg only for pitched roofs).",
            f"- style.window_style: {_values(WindowStyle)}.",
            f"- style.facade_material: {_values(FacadeMaterial)}.",
            f"- style.interior_finish_level: {_values(FinishLevel)}.",
            "- budget: {amount: decimal string, currency: ISO-4217 code}. A constraint only.",
            "- site.region_code: only when the user names a place (e.g. KZ-ALA for Almaty,"
            " KZ-AST for Astana).",
            f"- Facades: {_values(FacadeSide)}. front = street/entrance side; rear = garden/"
            "backyard/back side; left/right as seen from the street. Map "
            + ", ".join(f'"{w}"' for w in sorted(FACADE_SYNONYMS))
            + " to these values.",
            "- design.facade_color: the exterior wall color the user asks for (display color of"
            " the facade finish, not a material change). A palette name: "
            f"{', '.join(PALETTE)}; or #rrggbb when the user gives an exact color."
            " Null when no color is requested.",
            "- design.windows: {emphasis: large|panoramic, preferred_facades: [...],"
            " excluded_facades: [...]} when the user wants large/panoramic windows on particular"
            " facades. preferred_facades get the emphasised windows; excluded_facades never get"
            " them (standard windows there). Keep style.window_style for the other facades"
            " (standard unless the user wants large windows everywhere).",
            "- rooms[].faces: front|rear when a room should face the street or the garden/"
            "backyard (left/right are not supported for rooms).",
            "- style.design_system: only an id listed in <project_context> design_systems; null"
            " when the list is empty or the user names no matching direction. With a design"
            " system, every style value must be in that system's allowed lists.",
        ]
    )


@cache
def output_schema_json() -> dict[str, Any]:
    """JSON Schema of the structured output (the SpecificationDraft envelope)."""
    return SpecificationDraft.model_json_schema(mode="validation")


SCHEMA_IN_PROMPT_VERSION = "schema-in-prompt@1"


def schema_in_prompt_block(schema: dict[str, Any]) -> str:
    """System-prompt appendix for providers whose structured outputs cannot compile the schema.

    Used only as a fallback (providers/openrouter.py): the answer is still parsed with
    `json.loads` alone and validated exactly like a structured output. Versioned separately
    (`SCHEMA_IN_PROMPT_VERSION`) because the generation/repair prompts themselves do not change.
    """
    return "\n".join(
        [
            "<response_schema>",
            json.dumps(schema, ensure_ascii=False, separators=(",", ":")),
            "</response_schema>",
            f"The response schema above is the JSON Schema of `{OUTPUT_NAME}`. Answer with"
            " exactly one JSON object that validates against it: no text before or after it,"
            " no Markdown code fences, no comments. Respect every enum, minimum, maximum and"
            " length limit in the schema and omit properties you do not need.",
        ]
    )


_TAG_RE = re.compile(rf"</?\s*{USER_TAG}\s*>", re.IGNORECASE)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def quote_user_text(text: str) -> str:
    """Wrap untrusted user text in its tag so it cannot close the tag or add control chars."""
    cleaned = _CONTROL_RE.sub("", _TAG_RE.sub("", text)).strip()
    return f"<{USER_TAG}>\n{cleaned}\n</{USER_TAG}>"


def form_fields(options: GenerationOptions | None) -> dict[str, Any]:
    """The options the AI must honour (the layout seed is not an AI concern)."""
    if options is None:
        return {}
    return options.model_dump(mode="json", exclude_none=True, exclude={"seed"})


def context_block(context: GenerationContext, options: GenerationOptions | None) -> str:
    project = {
        "region_code": context.region_code,
        "currency": context.currency,
        "rules_profile": context.rules_profile,
        "room_minimums": [m.model_dump() for m in context.room_minimums],
        "max_room_share_of_gross_floor_area": context.max_room_share_of_gfa,
        # Usable (approved) design systems; empty = style.design_system must stay null.
        "design_systems": [d.model_dump() for d in context.design_systems],
    }
    parts = [
        "<project_context>",
        json.dumps(project, ensure_ascii=False, separators=(",", ":")),
        "</project_context>",
    ]
    fields = form_fields(options)
    if fields:
        parts += [
            "<form_fields>",
            json.dumps(fields, ensure_ascii=False, separators=(",", ":")),
            "</form_fields>",
            "The form fields were set explicitly by the user. The specification must use exactly"
            " these values; if the description contradicts them, use the form value and list"
            " the contradiction in `conflicts`.",
        ]
    return "\n".join(parts)
