"""BuildingModel root document (docs/building-model.md §3)."""

import uuid
from typing import Literal

from pydantic import Field

from app.modules.building.elements import Element
from app.modules.building.primitives import Frozen, Meters, PositiveMeters

SCHEMA_VERSION = "1.0.0"


class BuildingInfo(Frozen):
    name: str = Field(min_length=1, max_length=200)
    building_type: Literal["single_family_house"]
    description: str = Field(max_length=2000)


class Level(Frozen):
    """A storey ("floor"). elevation = finished floor level (FFL) above level 0 FFL."""

    id: uuid.UUID
    name: str = Field(min_length=1, max_length=80)
    index: int = Field(ge=0, le=10)
    elevation: Meters
    height: PositiveMeters  # floor-to-floor
    semantic_key: str = Field(min_length=1, max_length=200)


class ModelMetadata(Frozen):
    source: Literal["fixture", "layout", "operations"]
    generator: str = Field(max_length=200)


class BuildingModel(Frozen):
    schema_version: Literal["1.0.0"]
    id: uuid.UUID
    building: BuildingInfo
    units: Literal["m"]
    engine_version: str
    seed: int | None
    levels: list[Level] = Field(min_length=1)
    elements: list[Element]
    metadata: ModelMetadata
