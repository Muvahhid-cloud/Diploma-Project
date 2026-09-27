from pydantic import BaseModel, Field

from app.modules.building.issues import Issue
from app.modules.building.specification import BuildingSpecification

MAX_SEED = 2**31 - 1


class SpecValidationRequest(BaseModel):
    spec: BuildingSpecification


class SpecValidationOut(BaseModel):
    valid: bool  # no errors (warnings allowed)
    issues: list[Issue]
    rules_profile: str


class GenerateRequest(BaseModel):
    spec: BuildingSpecification
    seed: int = Field(default=0, ge=0, le=MAX_SEED)
    label: str | None = Field(default=None, min_length=1, max_length=200)
