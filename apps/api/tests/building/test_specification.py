from typing import Any

import pytest
from pydantic import ValidationError

from app.modules.building.specification import BuildingSpecification
from tests.building.helpers import SPECS_DIR


def base() -> dict[str, Any]:
    return {
        "name": "House",
        "targets": {"storeys": 2},
        "rooms": [{"key": "bedroom", "type": "bedroom", "count": 2}],
    }


def test_defaults_are_applied() -> None:
    s = BuildingSpecification.model_validate(base())
    assert s.schema_version == "1.0.0"
    assert s.building_type == "single_family_house"
    assert s.targets.floor_to_floor_height_m == 3.0
    assert s.targets.gross_floor_area_m2 is None
    assert s.style.roof.type == "hip"
    assert s.features.garage is None
    assert s.rooms[0].count == 2


def test_all_reference_specs_parse() -> None:
    paths = sorted(SPECS_DIR.glob("*.spec.json"))
    assert len(paths) == 10
    for p in paths:
        BuildingSpecification.model_validate_json(p.read_text(encoding="utf-8"))


def test_room_keys_must_be_unique() -> None:
    doc = base()
    doc["rooms"].append({"key": "bedroom", "type": "study"})
    with pytest.raises(ValidationError, match="unique"):
        BuildingSpecification.model_validate(doc)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("targets", "storeys"), 4),  # v1 scope: <= 3 storeys
        (("targets", "storeys"), 0),
        (("targets", "floor_to_floor_height_m"), 9),
        (("rooms", 0, "type"), "ballroom"),  # closed vocabulary
        (("rooms", 0, "type"), "corridor"),  # circulation is the engine's job
        (("rooms", 0, "count"), 13),
        (("rooms", 0, "key"), "Bed Room"),
    ],
)
def test_out_of_scope_values_are_rejected(path: tuple[Any, ...], value: Any) -> None:
    doc = base()
    node: Any = doc
    for part in path[:-1]:
        node = node[part]
    node[path[-1]] = value
    with pytest.raises(ValidationError):
        BuildingSpecification.model_validate(doc)


@pytest.mark.parametrize(
    "extra",
    [
        {"elements": []},
        {"walls": [{"start": [0, 0], "end": [5, 0]}]},
        {"coordinates": [[0, 0], [1, 1]]},
    ],
)
def test_geometry_is_not_part_of_a_spec(extra: dict[str, Any]) -> None:
    # AI output is intent only (CLAUDE.md rule 2): unknown fields are rejected, not ignored.
    with pytest.raises(ValidationError):
        BuildingSpecification.model_validate({**base(), **extra})
    with pytest.raises(ValidationError):
        BuildingSpecification.model_validate(
            {**base(), "rooms": [{"key": "b", "type": "bedroom", "position": {"x": 0, "y": 0}}]}
        )


def test_budget_is_decimal_with_currency() -> None:
    s = BuildingSpecification.model_validate(
        {**base(), "budget": {"amount": "300000000.00", "currency": "KZT"}}
    )
    assert s.budget is not None
    assert str(s.budget.amount) == "300000000.00"
    assert s.model_dump(mode="json")["budget"]["amount"] == "300000000.00"
    with pytest.raises(ValidationError):
        BuildingSpecification.model_validate(
            {**base(), "budget": {"amount": "1", "currency": "kzt"}}
        )
