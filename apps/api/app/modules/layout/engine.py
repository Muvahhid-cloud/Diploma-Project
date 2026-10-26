"""Layout engine entry point: BuildingSpecification + rules profile + seed -> BuildingModel.

Pure and deterministic (CLAUDE.md rule 5): same spec, profile, seed, config and id namespace
give a byte-identical model. No I/O, no clock, no global randomness — the only randomness is a
`random.Random` seeded from `seed` inside the candidate search.

Pipeline (docs/3d-engine.md §16): program -> opening fit (K2.5) -> levels -> skeletons
(footprint, bands, core) -> geometric skeleton constraints -> per-level zoning and subdivision
(seeded variants) -> scoring -> build the best candidates -> validate (model invariants incl.
geometric checks and reachability) -> first valid candidate wins.
"""

import math
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from app.modules.building.design import (
    DesignSystemSnapshot,
    effective_design,
    resolve_facade_preferences,
)
from app.modules.building.elements import Room
from app.modules.building.issues import Issue, pointer
from app.modules.building.model import BuildingModel
from app.modules.building.primitives import EPS
from app.modules.building.specification import BuildingSpecification, FacadeSide
from app.modules.building.types import TypeSet
from app.modules.building.validation import errors, validate_model
from app.modules.layout.build import BuildError, build_model
from app.modules.layout.config import DEFAULT_CONFIG, LayoutConfig
from app.modules.layout.constraints import opening_fit_issues
from app.modules.layout.plan import Candidate, StairDesign, snap
from app.modules.layout.planner import (
    PlanningError,
    SearchInput,
    assign_levels,
    design_stair,
    search,
    unmet_pairs,
)
from app.modules.layout.program import Program, expand_program
from app.modules.layout.regions import build_regions
from app.modules.layout.types import TypeSetError, config_with_types
from app.modules.rules.profile import BuildingRulesProfile

AREA_WARNING_THRESHOLD = 0.15  # explicit room targets
GFA_WARNING_THRESHOLD = 0.05
# Plan bands of the double-loaded layout that reach a facade (street = south, garden = north).
BAND_OF_FACADE = {FacadeSide.FRONT: "south", FacadeSide.REAR: "north"}


class LayoutError(Exception):
    """Generation failed. `code` is LAYOUT_INFEASIBLE (the spec cannot be laid out: tier-3
    feasibility, user-fixable) or LAYOUT_INVALID (an engine bug: no candidate validated)."""

    def __init__(self, code: str, message: str, issues: list[Issue]) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.issues = issues


@dataclass(frozen=True)
class LayoutMetrics:
    engine_version: str
    seed: int
    candidates_evaluated: int
    candidates_built: int
    score: float
    footprint_width_m: float
    footprint_depth_m: float
    gross_floor_area_m2: float
    target_gross_floor_area_m2: float


@dataclass(frozen=True)
class LayoutResult:
    model: BuildingModel
    warnings: list[Issue]
    notes: list[str] = field(default_factory=list)
    metrics: LayoutMetrics | None = None


def _circulation(
    gfa: float, storeys: int, stair: StairDesign | None, config: LayoutConfig
) -> float:
    """Estimated circulation area (corridors, stair core, entrance hall) for a house of `gfa`."""
    width = math.sqrt(gfa / storeys * 1.1)
    area = storeys * config.corridor_width * width + config.entrance_hall_width * 5.0
    if stair is not None:
        area += storeys * (storeys - 1) * stair.lane_width * 5.0
    return area


def _scale_default_areas(program: Program, capacity: float) -> float:
    """Scale rooms without an explicit target so the program fills the requested area.

    Service rooms (bathrooms, storage, ...) change size only a little; living spaces and
    bedrooms take the rest. Returns the factor applied to the living spaces.
    """
    explicit = sum(r.target_area for r in program.rooms if r.explicit_target)
    defaulted = [r for r in program.rooms if not r.explicit_target]
    total = sum(r.target_area for r in defaulted)
    if total <= 0:
        return 1.0
    overall = (capacity - explicit) / total
    service = [r for r in defaulted if r.tuckable]
    living = [r for r in defaulted if not r.tuckable]
    service_factor = min(1.3, max(0.75, overall))
    rest = capacity - explicit - service_factor * sum(r.target_area for r in service)
    living_total = sum(r.target_area for r in living)
    factor = min(2.0, max(0.75, rest / living_total)) if living_total > 0 else service_factor
    for r in service:
        r.target_area = max(r.min_area, r.target_area * service_factor)
    for r in living:
        r.target_area = max(r.min_area, r.target_area * factor)
    factors = ([factor] if living else []) + ([service_factor] if service else [])
    return max(factors, key=lambda f: abs(f - 1)) if factors else 1.0


def generate_layout(
    spec: BuildingSpecification,
    profile: BuildingRulesProfile,
    *,
    id_namespace: uuid.UUID,
    seed: int = 0,
    config: LayoutConfig = DEFAULT_CONFIG,
    previous_ids: Mapping[str, uuid.UUID] | None = None,
    material_ids: Iterable[str] | None = None,
    type_set: TypeSet | None = None,
    design_system: DesignSystemSnapshot | None = None,
) -> LayoutResult:
    """`design_system` (K3) is an approved snapshot resolved by the generation pipeline; its
    type set is passed as `type_set`. Precedence and effective values: building/design.py."""
    notes: list[str] = []
    design = effective_design(spec, design_system)
    try:
        # Types replace the matching design defaults; geometry code reads the config as before.
        config = config_with_types(config, type_set)
    except TypeSetError as exc:
        raise LayoutError("LAYOUT_INVALID", f"The type set cannot be used: {exc}", []) from exc
    program = expand_program(spec, profile, config)
    # Fixed door sizes that cannot fit the storey's walls make every candidate invalid: say so
    # up front, as a user-fixable infeasibility (K2.5, layout/constraints.py).
    misfits = opening_fit_issues(spec, program, profile, config, type_set)
    if misfits:
        raise LayoutError(
            "LAYOUT_INFEASIBLE", "The doors of this building do not fit its walls", misfits
        )
    storeys = spec.targets.storeys
    try:
        stair = (
            design_stair(spec.targets.floor_to_floor_height_m, profile, config)
            if storeys > 1
            else None
        )
    except PlanningError as exc:
        raise _infeasible(exc) from exc

    gfa = spec.targets.gross_floor_area_m2
    if gfa is None:
        rooms_area = sum(r.target_area for r in program.rooms)
        gfa = snap(
            rooms_area
            + _circulation(rooms_area / (1 - config.circulation_share), storeys, stair, config),
            5.0,
        )
        notes.append(
            f"No floor area was given; {gfa:.0f} m² was derived from the room program "
            "(rooms plus entrance hall, corridors and stairs)"
        )
    floor_area = gfa / storeys

    # Estimated room capacity of the whole house (footprint minus corridor, core, hall).
    factor = _scale_default_areas(program, gfa - _circulation(gfa, storeys, stair, config))
    if factor > 1.25:
        notes.append(
            f"Rooms without a requested size were enlarged by up to {factor - 1:.0%} to use the "
            "requested floor area"
        )
    elif factor < 0.9:
        notes.append(
            f"Rooms without a requested size were reduced by about {1 - factor:.0%} to fit the "
            "requested floor area"
        )

    site = spec.site
    max_w = spec.targets.max_footprint_width_m
    max_d = spec.targets.max_footprint_depth_m
    if site is not None and site.plot_width_m is not None:
        buildable = site.plot_width_m - 2 * site.setback_side_m
        max_w = buildable if max_w is None else min(max_w, buildable)
    if site is not None and site.plot_depth_m is not None:
        buildable = site.plot_depth_m - site.setback_front_m - site.setback_rear_m
        max_d = buildable if max_d is None else min(max_d, buildable)
    garage = spec.features.garage
    garage_w = (
        garage.cars * config.garage_width_per_car + config.garage_extra_width if garage else 0.0
    )

    # Rooms the user wants on a facade (rooms[].faces, K3) must reach it: front = the street
    # side band (south), rear = the garden side band (north). Explicit wishes come first.
    wishes: dict[str, str] = {}
    for room_key, facing in resolve_facade_preferences(spec).items():
        band = BAND_OF_FACADE.get(facing)
        if band is not None:
            for inst in program.instances(room_key):
                wishes.setdefault(inst.key, band)
    # Rooms that host a balcony or terrace must reach that facade.
    hosts: list[tuple[str | None, str]] = [
        (b.attached_to, "north" if b.side == "garden" else "south") for b in spec.features.balconies
    ]
    if spec.features.terrace is not None:
        hosts.append((spec.features.terrace.attached_to, "north"))
    for key, side in hosts:
        instances = program.instances(key) if key else []
        if instances:
            wishes.setdefault(instances[0].key, side)

    try:
        levels = assign_levels(program, storeys, floor_area, stair, config)
        candidates = search(
            SearchInput(
                spec=spec,
                program=program,
                levels=levels,
                stair=stair,
                floor_area_per_storey=floor_area,
                max_width=max_w,
                max_depth=max_d,
                garage_width=garage_w,
                garage_depth=config.garage_min_depth,
                landing_depth=profile.stairs.landing_min_depth_m,
                wishes=wishes,
            ),
            config,
            seed,
        )
    except PlanningError as exc:
        raise _infeasible(exc) from exc

    failures: list[str] = []
    built = 0
    materials = list(material_ids) if material_ids is not None else None
    for cand in candidates[: config.candidates_to_build]:
        built += 1
        try:
            plan = build_regions(cand, program, spec, stair, config)
            model = build_model(
                plan,
                spec,
                profile,
                config,
                seed=seed,
                id_namespace=id_namespace,
                previous_ids=previous_ids,
                type_set=type_set,
                design=design,
            )
        except BuildError as exc:
            failures.append(str(exc))
            continue
        issues = validate_model(model, material_ids=materials)
        blocking = errors(issues) + [i for i in issues if i.code == "ROOM_UNREACHABLE"]
        if blocking:
            failures.append("; ".join(f"{i.code}: {i.message}" for i in blocking[:3]))
            continue
        warnings = _deviations(cand, program, spec, gfa)
        warnings += _orientation(model, program, spec, cand.skeleton.D)
        warnings += [i for i in issues if i.severity == "warning"]
        return LayoutResult(
            model=model,
            warnings=warnings,
            notes=notes + plan.notes,
            metrics=LayoutMetrics(
                engine_version=config.engine_version,
                seed=seed,
                candidates_evaluated=len(candidates),
                candidates_built=built,
                score=round(cand.score, 6),
                footprint_width_m=cand.skeleton.W,
                footprint_depth_m=cand.skeleton.D,
                gross_floor_area_m2=round(cand.skeleton.W * cand.skeleton.D * storeys, 2),
                target_gross_floor_area_m2=round(gfa, 2),
            ),
        )
    raise LayoutError(
        "LAYOUT_INVALID",
        "The layout engine could not produce a valid model for this specification",
        [Issue(severity="error", code="LAYOUT_INVALID", path="", message=f) for f in failures[:5]],
    )


def _infeasible(exc: PlanningError) -> LayoutError:
    return LayoutError(
        "LAYOUT_INFEASIBLE",
        str(exc),
        [
            Issue(severity="error", code="LAYOUT_INFEASIBLE", path="", message=reason)
            for reason in exc.reasons
        ]
        or [Issue(severity="error", code="LAYOUT_INFEASIBLE", path="", message=str(exc))],
    )


def _orientation(
    model: BuildingModel, program: Program, spec: BuildingSpecification, depth: float
) -> list[Issue]:
    """ROOM_FACADE_UNMET for a room that does not reach the facade it should face."""
    out: list[Issue] = []
    rooms = {el.semantic_key: el for el in model.elements if isinstance(el, Room)}
    for key, side in resolve_facade_preferences(spec).items():
        for inst in program.instances(key):
            room = rooms.get(f"room:{inst.key}")
            if room is None or side not in BAND_OF_FACADE:
                continue
            ys = [room.position.y + p.y for p in room.properties.boundary]
            reached = min(ys) < EPS if side == FacadeSide.FRONT else max(ys) > depth - EPS
            if not reached:
                out.append(
                    Issue(
                        severity="warning",
                        code="ROOM_FACADE_UNMET",
                        path=pointer("rooms", inst.spec_index, "faces"),
                        message=f"{inst.name} could not be placed on the {side.value} facade",
                    )
                )
    return out


def _deviations(
    cand: Candidate, program: Program, spec: BuildingSpecification, gfa: float
) -> list[Issue]:
    """Where the result departs from what was asked (never hidden from the user)."""
    out: list[Issue] = []
    for r in program.rooms:
        if not r.explicit_target:
            continue
        actual = cand.areas.get(r.key, 0.0)
        if abs(actual - r.target_area) / r.target_area > AREA_WARNING_THRESHOLD:
            out.append(
                Issue(
                    severity="warning",
                    code="LAYOUT_AREA_DEVIATION",
                    path=pointer("rooms", r.spec_index, "target_area_m2"),
                    message=f"{r.name}: {actual:.1f} m² instead of the requested "
                    f"{r.target_area:.1f} m²",
                )
            )
    actual_gfa = cand.skeleton.W * cand.skeleton.D * spec.targets.storeys
    if (
        spec.targets.gross_floor_area_m2 is not None
        and abs(actual_gfa - gfa) / gfa > GFA_WARNING_THRESHOLD
    ):
        out.append(
            Issue(
                severity="warning",
                code="LAYOUT_GFA_DEVIATION",
                path="/targets/gross_floor_area_m2",
                message=f"Gross floor area is {actual_gfa:.0f} m² instead of {gfa:.0f} m²",
            )
        )
    for kind, a, b in unmet_pairs(cand.levels, program):
        idx = program.instances(a)[0].spec_index if program.instances(a) else 0
        out.append(
            Issue(
                severity="warning",
                code="LAYOUT_ADJACENCY",
                path=pointer("rooms", idx),
                message=f"{a} could not be placed {'next' if kind == 'adjacent' else 'open'} "
                f"to {b}",
            )
        )
    return out
