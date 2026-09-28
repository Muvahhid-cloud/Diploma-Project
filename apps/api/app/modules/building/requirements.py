"""Key requirements of a specification, and how a generated model compares against them.

Pure derived data (spec + ModelSummary), shown after generation so deviations between the
request and the result are never hidden, and used to detect when an AI repair changed the
user's program.
"""

from app.modules.building.primitives import Frozen
from app.modules.building.specification import BuildingSpecification, RoomFeature, SpecRoomType
from app.modules.building.summary import ModelSummary


class SpecFacts(Frozen):
    storeys: int
    gross_floor_area_m2: float | None
    bedrooms: int
    bathrooms: int  # bathrooms + en-suites
    wcs: int
    garage_cars: int | None
    balconies: int
    terrace: bool


def spec_facts(spec: BuildingSpecification) -> SpecFacts:
    def count(room_type: SpecRoomType) -> int:
        return sum(r.count for r in spec.rooms if r.type == room_type)

    en_suites = sum(r.count for r in spec.rooms if RoomFeature.EN_SUITE in r.features)
    garage = spec.features.garage
    return SpecFacts(
        storeys=spec.targets.storeys,
        gross_floor_area_m2=spec.targets.gross_floor_area_m2,
        bedrooms=count(SpecRoomType.BEDROOM),
        bathrooms=count(SpecRoomType.BATHROOM) + en_suites,
        wcs=count(SpecRoomType.WC),
        garage_cars=garage.cars if garage else None,
        balconies=len(spec.features.balconies),
        terrace=spec.features.terrace is not None,
    )


FACT_LABELS = {
    "storeys": "Floors",
    "gross_floor_area_m2": "Floor area (m²)",
    "bedrooms": "Bedrooms",
    "bathrooms": "Bathrooms",
    "wcs": "WCs",
    "garage_cars": "Garage (cars)",
    "balconies": "Balconies",
    "terrace": "Terrace",
}


def changed_facts(before: SpecFacts, after: SpecFacts) -> list[tuple[str, object, object]]:
    """(label, before, after) for every key requirement that differs."""
    old, new = before.model_dump(), after.model_dump()
    return [(FACT_LABELS[k], old[k], new[k]) for k in FACT_LABELS if old[k] != new[k]]


class RequirementCheck(Frozen):
    key: str
    label: str
    requested: str
    delivered: str
    met: bool


def requirement_checks(
    spec: BuildingSpecification, summary: ModelSummary, *, area_tolerance: float
) -> list[RequirementCheck]:
    """Requested vs delivered for the requirements a user states most often.

    `area_tolerance` is the relative gross-floor-area deviation still reported as met (the
    layout engine's own warning threshold)."""
    facts = spec_facts(spec)
    checks = [
        RequirementCheck(
            key="storeys",
            label="Floors",
            requested=str(facts.storeys),
            delivered=str(summary.storeys),
            met=facts.storeys == summary.storeys,
        )
    ]
    if facts.gross_floor_area_m2 is not None:
        target = facts.gross_floor_area_m2
        checks.append(
            RequirementCheck(
                key="gross_floor_area_m2",
                label="Floor area",
                requested=f"{target:g} m²",
                delivered=f"{summary.gross_floor_area_m2:g} m²",
                met=abs(summary.gross_floor_area_m2 - target) <= area_tolerance * target,
            )
        )
    for key, label, requested, delivered in (
        ("bedrooms", "Bedrooms", facts.bedrooms, summary.bedrooms),
        ("bathrooms", "Bathrooms", facts.bathrooms, summary.bathrooms),
        ("wcs", "WCs", facts.wcs, summary.wcs),
        ("balconies", "Balconies", facts.balconies, summary.balconies),
    ):
        if requested:
            checks.append(
                RequirementCheck(
                    key=key,
                    label=label,
                    requested=str(requested),
                    delivered=str(delivered),
                    met=requested == delivered,
                )
            )
    if facts.garage_cars is not None:
        checks.append(
            RequirementCheck(
                key="garage",
                label="Garage",
                requested=f"{facts.garage_cars} car{'s' if facts.garage_cars > 1 else ''}",
                delivered="built" if summary.garage else "missing",
                met=summary.garage,
            )
        )
    if facts.terrace:
        checks.append(
            RequirementCheck(
                key="terrace",
                label="Terrace",
                requested="yes",
                delivered="built" if summary.terraces else "missing",
                met=summary.terraces > 0,
            )
        )
    return checks
