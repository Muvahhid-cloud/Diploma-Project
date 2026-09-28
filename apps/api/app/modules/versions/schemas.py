import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.building.issues import Issue
from app.modules.building.model import BuildingModel
from app.modules.building.specification import BuildingSpecification
from app.modules.building.summary import ModelSummary


class GenerationProvenance(BaseModel):
    """Which AI generation produced a version (absent for spec-form and fixture versions)."""

    generation_id: uuid.UUID
    generation_type: Literal["building_generation"] = "building_generation"
    provider: str
    model: str
    prompt_version: str


class GenerationReport(BaseModel):
    """What the layout engine (and, for AI versions, the interpreter) reported at generation."""

    warnings: list[Issue] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    generation: GenerationProvenance | None = None


class VersionSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    parent_version_id: uuid.UUID | None
    number: int
    label: str
    source: str
    schema_version: str
    engine_version: str
    rules_profile: str
    seed: int | None
    model_hash: str
    summary: ModelSummary
    created_at: datetime


class VersionList(BaseModel):
    items: list[VersionSummaryOut]


class VersionOut(VersionSummaryOut):
    prompt: str | None
    spec: BuildingSpecification | None
    model: BuildingModel
    report: GenerationReport | None
    # Evaluated on read against the version's rules profile + model invariants (warnings).
    issues: list[Issue]
