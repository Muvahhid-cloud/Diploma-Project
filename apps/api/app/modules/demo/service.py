"""Loads and validates the demo BuildingModel fixture and the material library."""

import json
from functools import lru_cache
from pathlib import Path

from fastapi import status

from app.core.errors import AppError
from app.modules.building.model import BuildingModel
from app.modules.building.validation import errors, validate_model

DEMO_MODEL_PATH = Path("fixtures") / "demo-house.model.json"
MATERIAL_LIBRARY_PATH = Path("materials") / "library.json"


class ModelInvalidError(AppError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "MODEL_INVALID"


@lru_cache
def material_ids(data_dir: Path) -> frozenset[str]:
    library = json.loads((data_dir / MATERIAL_LIBRARY_PATH).read_text(encoding="utf-8"))
    return frozenset(m["id"] for m in library["materials"])


@lru_cache
def demo_building_model(data_dir: Path) -> BuildingModel:
    """The demo house, validated against the schema and all model invariants.

    An invalid fixture is a server bug: it is reported loudly instead of being served.
    """
    raw = (data_dir / DEMO_MODEL_PATH).read_text(encoding="utf-8")
    model = BuildingModel.model_validate_json(raw)
    problems = errors(validate_model(model, material_ids=material_ids(data_dir)))
    if problems:
        raise ModelInvalidError(
            "The demo building model violates model invariants",
            details=[{"path": p.path, "message": p.message, "code": p.code} for p in problems],
        )
    return model
