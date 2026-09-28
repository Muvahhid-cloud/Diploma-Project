"""Integrity checks for component records (families, types, assemblies, role mappings; K2)."""

from collections import Counter
from typing import get_args

from app.modules.building.elements import ElementType
from app.modules.building.issues import Issue, pointer
from app.modules.building.primitives import EPS
from app.modules.building.types import (
    ASSEMBLY_KIND_FOR,
    TYPE_ROLES,
    DoorTypeParams,
    RailingTypeParams,
    StairTypeParams,
    WindowTypeParams,
)
from app.modules.catalog.components import DerivedFrom
from app.modules.catalog.provenance import Status
from app.modules.catalog.registry import KnowledgeRegistry

ELEMENT_TYPES = frozenset(get_args(ElementType))


def _issue(code: str, path: str, message: str) -> Issue:
    return Issue(severity="error", code=code, path=path, message=message)


def check_components(
    registry: KnowledgeRegistry, *, known_materials: frozenset[str] | None
) -> list[Issue]:
    issues: list[Issue] = []
    packs = list(registry.packs.values())
    all_ids = [
        *(f.id for p in packs for f in p.families),
        *(t.id for p in packs for t in p.types),
        *(a.id for p in packs for a in p.assemblies),
        *(m.id for p in packs for m in p.role_mappings),
    ]
    for dup, n in Counter(all_ids).items():
        if n > 1:
            issues.append(_issue("DUPLICATE_ID", pointer("components"), f"{dup} defined {n} times"))

    classes = registry.classes()
    families = registry.families()
    types = registry.component_types()
    assemblies = registry.assemblies()
    items = {e.ref: e.item for e in registry.items()}

    def materials(path: str, ids: list[str | None]) -> None:
        if known_materials is None:
            return
        for mid in ids:
            if mid is not None and mid not in known_materials:
                issues.append(_issue("UNKNOWN_MATERIAL", path, f"unknown material {mid!r}"))

    def derived(path: str, status: Status, source: DerivedFrom) -> None:
        for ref in source.knowledge:
            item = items.get(ref)
            if item is None:
                issues.append(_issue("DERIVED_KNOWLEDGE_UNKNOWN", path, f"unknown {ref}"))
            elif status == Status.APPROVED and item.status != Status.APPROVED:
                issues.append(
                    _issue(
                        "APPROVED_DERIVED_UNAPPROVED",
                        path,
                        f"approved record derived from {ref}, which is {item.status}",
                    )
                )

    for f in families.values():
        path = pointer("families", f.id)
        if f.element_type not in ELEMENT_TYPES:
            issues.append(_issue("FAMILY_ELEMENT_TYPE_UNKNOWN", path, f"no {f.element_type!r}"))
        if f.class_ref not in classes:
            issues.append(_issue("FAMILY_CLASS_UNKNOWN", path, f"unknown {f.class_ref}"))

    for a in assemblies.values():
        path = pointer("assemblies", a.id)
        total = sum(layer.thickness for layer in a.layers)
        if abs(total - a.total_thickness) > EPS:
            issues.append(
                _issue(
                    "ASSEMBLY_THICKNESS_SUM",
                    path,
                    f"layers add up to {total:.3f} m, total is {a.total_thickness} m",
                )
            )
        materials(f"{path}/layers", [layer.material_id for layer in a.layers])
        derived(path, a.status, a.derived_from)

    for t in types.values():
        path = pointer("types", t.id)
        family = families.get(t.family)
        if family is None:
            issues.append(_issue("TYPE_FAMILY_UNKNOWN", path, f"unknown {t.family}"))
        elif family.element_type != t.params.element_type:
            issues.append(
                _issue(
                    "TYPE_FAMILY_MISMATCH",
                    path,
                    f"{t.params.element_type} params in a {family.element_type} family",
                )
            )
        expected = ASSEMBLY_KIND_FOR.get(t.params.element_type)
        assembly = assemblies.get(t.assembly) if t.assembly else None
        if expected is None and t.assembly is not None:
            issues.append(_issue("TYPE_ASSEMBLY_UNEXPECTED", path, "this type has no assembly"))
        elif expected is not None and (assembly is None or assembly.kind != expected):
            issues.append(
                _issue(
                    "TYPE_ASSEMBLY_UNKNOWN",
                    path,
                    f"needs a {expected} assembly, got {t.assembly!r}",
                )
            )
        p = t.params
        if isinstance(p, DoorTypeParams | WindowTypeParams):
            materials(f"{path}/params", [p.material_id, p.frame_material_id])
        elif isinstance(p, StairTypeParams | RailingTypeParams):
            materials(f"{path}/params", [p.material_id])
        derived(path, t.status, t.derived_from)

    for m in registry.role_mappings().values():
        path = pointer("role_mappings", m.id)
        for role in sorted(set(m.roles) - set(TYPE_ROLES)):
            issues.append(_issue("MAPPING_ROLE_UNKNOWN", path, f"unknown role {role}"))
        for role in sorted(set(TYPE_ROLES) - set(m.roles)):
            issues.append(_issue("MAPPING_ROLE_MISSING", path, f"role {role} is not mapped"))
        for role, type_id in sorted(m.roles.items()):
            mapped = types.get(type_id)
            if mapped is None:
                issues.append(_issue("MAPPING_TYPE_UNKNOWN", path, f"{role}: unknown {type_id}"))
            elif role in TYPE_ROLES and TYPE_ROLES[role] != mapped.params.element_type:
                issues.append(
                    _issue(
                        "MAPPING_ROLE_TYPE_MISMATCH",
                        path,
                        f"{role} holds {TYPE_ROLES[role]} types, {type_id} is a "
                        f"{mapped.params.element_type} type",
                    )
                )
    return issues
