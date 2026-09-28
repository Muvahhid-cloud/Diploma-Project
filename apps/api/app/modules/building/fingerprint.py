"""Geometry fingerprint of a BuildingModel (docs/building-model.md §8.1).

`geometry_sha256` hashes the levels and elements with all type metadata removed (`type_ref`,
`ceiling_assembly_ref`, the model's `types` / `assemblies`) and without document-level fields
(id, schema and engine versions, metadata). Two models with the same fingerprint have the same
geometry, materials, properties and relationships — the golden files use it to prove that
schema upgrades and type assignment never change what is built or rendered.
"""

import hashlib
import json
from typing import Any

from app.modules.building.model import BuildingModel

TYPE_METADATA_FIELDS = frozenset({"type_ref", "ceiling_assembly_ref"})


def _strip(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _strip(v) for k, v in node.items() if k not in TYPE_METADATA_FIELDS}
    if isinstance(node, list):
        return [_strip(v) for v in node]
    return node


def geometry_document(model: BuildingModel) -> dict[str, Any]:
    doc = model.model_dump(mode="json", include={"levels", "elements"})
    stripped: dict[str, Any] = _strip(doc)
    return stripped


def geometry_sha256(model: BuildingModel) -> str:
    text = json.dumps(geometry_document(model), separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
