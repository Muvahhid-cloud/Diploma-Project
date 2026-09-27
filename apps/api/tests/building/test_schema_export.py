import json

from app.modules.building.export_schema import building_model_json_schema
from tests.building.helpers import SCHEMA_PATH


def test_committed_json_schema_is_up_to_date() -> None:
    # packages/schema is generated from Pydantic; regenerate with `pnpm schema`.
    committed = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert committed == building_model_json_schema()


def test_schema_covers_every_element_type() -> None:
    schema = building_model_json_schema()
    union = schema["properties"]["elements"]["items"]
    mapping = union["discriminator"]["mapping"]
    assert set(mapping) == {
        "wall",
        "door",
        "window",
        "room",
        "slab",
        "stair",
        "roof",
        "railing",
        "furniture",
    }


def test_every_element_requires_the_common_fields() -> None:
    schema = building_model_json_schema()
    common = {
        "id",
        "type",
        "name",
        "layer",
        "level_id",
        "position",
        "rotation",
        "dimensions",
        "material_id",
        "properties",
        "relationships",
        "origin",
        "locked",
        "semantic_key",
    }
    for name in ("Wall", "Door", "Window", "Room", "Slab", "Stair", "Roof", "Railing"):
        assert common <= set(schema["$defs"][name]["required"]), name
