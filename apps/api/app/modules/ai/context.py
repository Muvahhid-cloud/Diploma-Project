"""Compact, structured context for AI calls. Never the full BuildingModel (docs/ai-pipeline.md §4).

* `GenerationContext` — what the interpreter needs to write a specification for a project:
  region, currency and the rules profile's room minimums (rules are data, CLAUDE.md rule 16,
  so the prompt quotes the active profile instead of hard-coding numbers).
* `ProjectContext` — a token-efficient digest of a project's current design (summary, spec,
  rooms with short refs, the selected element). Phase 3 uses it for the read-only AI tools;
  Phase 5 (natural-language modification) sends it with the instruction.

Both are pure functions of their inputs (no I/O).
"""

import uuid

from pydantic import BaseModel, ConfigDict

from app.modules.building.elements import Room
from app.modules.building.model import BuildingModel
from app.modules.building.specification import Budget, BuildingSpecification, SpecRoomType
from app.modules.building.summary import ModelSummary, summarize
from app.modules.rules.profile import BuildingRulesProfile
from app.modules.rules.spec_checks import MAX_ROOM_SHARE_OF_GFA


class ContextModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RoomMinimum(ContextModel):
    room_type: str
    min_area_m2: float
    min_width_m: float


class GenerationContext(ContextModel):
    region_code: str
    currency: str
    rules_profile: str
    room_minimums: tuple[RoomMinimum, ...]
    # Share of the gross floor area the rooms may take (the rest is walls and circulation).
    max_room_share_of_gfa: float


def generation_context(
    *, region_code: str, currency: str, profile: BuildingRulesProfile
) -> GenerationContext:
    room_types = [t.value for t in SpecRoomType] + ["en_suite", "walk_in_closet"]
    return GenerationContext(
        region_code=region_code,
        currency=currency,
        rules_profile=profile.ref,
        room_minimums=tuple(
            RoomMinimum(
                room_type=t,
                min_area_m2=profile.room(t).min_area_m2,
                min_width_m=profile.room(t).min_width_m,
            )
            for t in room_types
        ),
        max_room_share_of_gfa=MAX_ROOM_SHARE_OF_GFA,
    )


class VersionDigest(ContextModel):
    id: uuid.UUID
    number: int
    label: str
    source: str
    engine_version: str
    seed: int | None


class RoomDigest(ContextModel):
    ref: str  # short reference ("R3") that a model can use instead of the UUID
    id: uuid.UUID
    name: str
    room_type: str
    level: int
    area_m2: float


class ElementDigest(ContextModel):
    id: uuid.UUID
    type: str
    name: str
    level: int | None
    semantic_key: str
    dimensions: dict[str, float]


class ProjectContext(ContextModel):
    project_id: uuid.UUID
    project_name: str
    region_code: str
    currency: str
    rules_profile: str
    budget: Budget | None
    version: VersionDigest | None
    summary: ModelSummary | None
    specification: BuildingSpecification | None
    rooms: tuple[RoomDigest, ...]
    selected: ElementDigest | None


def build_project_context(
    *,
    project_id: uuid.UUID,
    project_name: str,
    region_code: str,
    currency: str,
    rules_profile: str,
    version: VersionDigest | None = None,
    model: BuildingModel | None = None,
    spec: BuildingSpecification | None = None,
    selected_id: uuid.UUID | None = None,
) -> ProjectContext:
    rooms: list[RoomDigest] = []
    selected: ElementDigest | None = None
    if model is not None:
        levels = _level_indices(model)
        ordered = sorted(
            (el for el in model.elements if isinstance(el, Room)),
            key=lambda r: (levels.get(r.level_id) or 0, r.semantic_key),
        )
        rooms = [
            RoomDigest(
                ref=f"R{i + 1}",
                id=r.id,
                name=r.name,
                room_type=r.properties.room_type.value,
                level=levels.get(r.level_id) or 0,
                area_m2=r.dimensions.area,
            )
            for i, r in enumerate(ordered)
        ]
        if selected_id is not None:
            selected = element_digest(model, selected_id)
    return ProjectContext(
        project_id=project_id,
        project_name=project_name,
        region_code=region_code,
        currency=currency,
        rules_profile=rules_profile,
        budget=spec.budget if spec else None,
        version=version,
        summary=summarize(model) if model else None,
        specification=spec,
        rooms=tuple(rooms),
        selected=selected,
    )


def _level_indices(model: BuildingModel) -> dict[uuid.UUID | None, int]:
    return {lv.id: lv.index for lv in model.levels}


def element_digest(model: BuildingModel, element_id: uuid.UUID) -> ElementDigest | None:
    levels = _level_indices(model)
    for el in model.elements:
        if el.id == element_id:
            dims = el.dimensions.model_dump()
            return ElementDigest(
                id=el.id,
                type=el.type,
                name=el.name,
                level=levels.get(el.level_id),
                semantic_key=el.semantic_key,
                dimensions={k: float(v) for k, v in dims.items() if isinstance(v, int | float)},
            )
    return None
