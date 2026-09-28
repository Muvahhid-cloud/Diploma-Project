"""Steps 2-5 and 10 — levels, footprint, stair core, zoning, subdivision, candidate scoring.

The plan is a double-loaded corridor on every level: a street-side band (south), a corridor
band and a garden-side band (north), stacked identically on all storeys. The stair core sits in
the south band; on the ground floor it is part of the entrance hall. Every room spans its band
from the corridor to the facade (so it is reachable and gets daylight), except small service
rooms, which may be "tucked" against the corridor inside a larger room's column; that room then
wraps around them (L-shape) on the facade side.

The search enumerates skeletons (footprint proportions, band depth, core position) and, per
seeded variant, assigns rooms to bands and orders them. Candidates are scored on area error,
proportions and adjacency; the best ones go on to be built and validated.
"""

import itertools
import math
import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from app.modules.building.enums import RoomType
from app.modules.building.specification import BuildingSpecification
from app.modules.layout.config import LayoutConfig
from app.modules.layout.constraints import flights_fit_lanes
from app.modules.layout.plan import (
    Candidate,
    Column,
    LevelLayout,
    Skeleton,
    StairDesign,
    Strip,
    StripLayout,
    rnd,
    snap,
    snap_up,
)
from app.modules.layout.program import PUBLIC, TUCKABLE, WET, Program, RoomRequest
from app.modules.rules.profile import BuildingRulesProfile

EPS = 1e-6
UPSTAIRS_OK = frozenset(
    {
        RoomType.BEDROOM,
        RoomType.BATHROOM,
        RoomType.STUDY,
        RoomType.STORAGE,
        RoomType.LAUNDRY,
        RoomType.EN_SUITE,
        RoomType.WALK_IN_CLOSET,
    }
)
# Affinity of small service rooms for the room they are tucked into.
TUCK_AFFINITY: dict[RoomType, dict[RoomType, float]] = {
    RoomType.WC: {
        RoomType.LIVING: 3,
        RoomType.DINING: 3,
        RoomType.OPEN_KITCHEN_LIVING: 3,
        RoomType.KITCHEN: 2,
        RoomType.STUDY: 2,
        RoomType.BEDROOM: 1,
    },
    RoomType.BATHROOM: {
        RoomType.BEDROOM: 3,
        RoomType.STUDY: 2,
        RoomType.LIVING: 1,
        RoomType.DINING: 1,
        RoomType.OPEN_KITCHEN_LIVING: 1,
        RoomType.KITCHEN: 0.5,
    },
    RoomType.STORAGE: {RoomType.KITCHEN: 3, RoomType.OPEN_KITCHEN_LIVING: 3},
    RoomType.LAUNDRY: {RoomType.KITCHEN: 3, RoomType.OPEN_KITCHEN_LIVING: 3},
    RoomType.UTILITY: {RoomType.KITCHEN: 3, RoomType.OPEN_KITCHEN_LIVING: 3},
}
# Pairs that like to be neighbours even when the spec does not say so.
IMPLICIT_AFFINITY: dict[frozenset[RoomType], float] = {
    frozenset({RoomType.KITCHEN, RoomType.DINING}): 1.5,
    frozenset({RoomType.DINING, RoomType.LIVING}): 1.5,
    frozenset({RoomType.KITCHEN, RoomType.LIVING}): 1.0,
}
ASPECT_LIMIT = {"habitable": 2.2, "service": 3.2}


class PlanningError(Exception):
    """No feasible plan. `reasons` explain why (tier-3 feasibility)."""

    def __init__(self, message: str, reasons: list[str]) -> None:
        super().__init__(message)
        self.reasons = reasons


# --- stair ------------------------------------------------------------------------------------


def design_stair(
    floor_to_floor: float, profile: BuildingRulesProfile, config: LayoutConfig
) -> StairDesign:
    s = profile.stairs
    risers = math.ceil(floor_to_floor / s.riser_m.max - 1e-9)
    if risers > s.max_risers_per_flight:
        raise PlanningError(
            "The storey height is too large for a straight flight",
            [
                f"{floor_to_floor} m needs {risers} risers of at most {s.riser_m.max} m; one "
                f"flight allows {s.max_risers_per_flight}"
            ],
        )
    riser = floor_to_floor / risers
    tread = round(config.stair_comfort_target - 2 * riser, 3)
    tread = min(max(tread, s.tread_m.min), s.tread_m.max)
    comfort = 2 * riser + tread
    if comfort < s.comfort_rule.min:
        tread = min(s.tread_m.max, round(s.comfort_rule.min - 2 * riser + 0.0005, 3))
    elif comfort > s.comfort_rule.max:
        tread = max(s.tread_m.min, round(s.comfort_rule.max - 2 * riser - 0.0005, 3))
    width = max(config.stair_width, s.min_width_m)
    lane = snap_up(width + 2 * config.stair_clearance + config.interior_wall_thickness, config.grid)
    return StairDesign(
        risers=risers,
        riser=riser,
        tread=tread,
        run=rnd((risers - 1) * tread),
        width=width,
        lane_width=lane,
    )


# --- levels -----------------------------------------------------------------------------------


def _capacities(
    floor_area: float, storeys: int, stair: StairDesign | None, config: LayoutConfig
) -> list[float]:
    """Room area available per level (footprint minus corridor, core and entrance hall)."""
    width = math.sqrt(floor_area * 1.3)
    depth_south = 5.0
    corridor = config.corridor_width * width
    core = (storeys - 1) * (stair.lane_width if stair else 0) * depth_south
    hall = config.entrance_hall_width * depth_south
    return [
        max(1.0, floor_area - corridor - core - (hall if level == 0 else 0))
        for level in range(storeys)
    ]


def assign_levels(
    program: Program,
    storeys: int,
    floor_area: float,
    stair: StairDesign | None,
    config: LayoutConfig,
) -> dict[str, int]:
    rooms = program.by_key()
    levels: dict[str, int] = {}
    if storeys == 1:
        return dict.fromkeys(rooms, 0)
    capacity = _capacities(floor_area, storeys, stair, config)
    upper = list(range(1, storeys))

    def load(level: int) -> float:
        return sum(rooms[k].target_area for k, lv in levels.items() if lv == level)

    primaries = [r for r in program.rooms if r.serves is None]
    for r in primaries:
        if r.level is not None:
            levels[r.key] = r.level
    # Bedrooms upstairs, largest first, each to the upper level with the most free capacity.
    bedrooms = sorted(
        (r for r in primaries if r.type == RoomType.BEDROOM and r.key not in levels),
        key=lambda r: (-r.target_area, r.key),
    )
    for r in bedrooms:
        levels[r.key] = max(upper, key=lambda lv: (capacity[lv] - load(lv), -lv))
    # One bathroom per level that has bedrooms, then the ground floor, then upstairs again.
    bathrooms = sorted(
        (r for r in primaries if r.type == RoomType.BATHROOM and r.key not in levels),
        key=lambda r: r.key,
    )
    bedroom_levels = sorted(
        {levels[r.key] for r in primaries if r.type == RoomType.BEDROOM}, reverse=True
    )
    wanted = [lv for lv in bedroom_levels if lv > 0] + [0]
    for i, r in enumerate(bathrooms):
        levels[r.key] = wanted[i] if i < len(wanted) else max(upper, key=load)
    for r in primaries:
        if r.key not in levels:
            levels[r.key] = 0

    def sync_attached() -> None:
        for r in program.rooms:
            if r.serves is not None:
                levels[r.key] = levels[r.serves]

    sync_attached()

    def unit_area(r: RoomRequest) -> float:
        return r.target_area + sum(rooms[a].target_area for a in r.attached)

    def movable(r: RoomRequest, to: int) -> bool:
        if r.level is not None or r.serves is not None:
            return False
        if to > 0 and r.type not in UPSTAIRS_OK:
            return False
        if r.type == RoomType.BATHROOM:  # keep a bathroom on every level with bedrooms
            here = levels[r.key]
            baths_here = [
                b for b in primaries if b.type == RoomType.BATHROOM and levels[b.key] == here
            ]
            has_bedroom = any(
                b.type == RoomType.BEDROOM and levels[b.key] == here for b in primaries
            )
            if has_bedroom and len(baths_here) <= 1:
                return False
        return True

    for _ in range(60):
        ratios = [load(lv) / capacity[lv] for lv in range(storeys)]
        spread = sum((x - 1) ** 2 for x in ratios)
        best: tuple[float, str, int] | None = None
        for r in sorted(primaries, key=lambda r: r.key):
            src = levels[r.key]
            for dst in range(storeys):
                if dst == src or not movable(r, dst):
                    continue
                a = unit_area(r)
                new = list(ratios)
                new[src] = (load(src) - a) / capacity[src]
                new[dst] = (load(dst) + a) / capacity[dst]
                # Never empty an upper level.
                if src > 0 and not any(levels[o.key] == src for o in primaries if o.key != r.key):
                    continue
                score = sum((x - 1) ** 2 for x in new)
                if score < spread - 0.005 and (best is None or score < best[0]):
                    best = (score, r.key, dst)
        if best is None:
            break
        levels[best[1]] = best[2]
        sync_attached()

    for lv in upper:
        if not any(levels[r.key] == lv for r in primaries):
            raise PlanningError(
                "An upper floor would have no rooms",
                [f"No room can be placed on floor {lv + 1}; add rooms or reduce the storeys"],
            )
    return levels


# --- units --------------------------------------------------------------------------------------


@dataclass
class Unit:
    primary: RoomRequest
    attached: list[RoomRequest] = field(default_factory=list)

    @property
    def area(self) -> float:
        return self.primary.target_area + sum(a.target_area for a in self.attached)

    @property
    def rooms(self) -> list[RoomRequest]:
        return [self.primary, *self.attached]


def form_units(level_rooms: list[RoomRequest], config: LayoutConfig) -> list[Unit]:
    """Group each small service room with the room it will be tucked into."""
    units: dict[str, Unit] = {}
    small: list[RoomRequest] = []
    for r in level_rooms:
        if r.serves is not None:
            continue
        # Would be a skinny column at full band depth (~4.2 m or more): tuck it instead.
        if r.tuckable and r.target_area < config.tuck_widths[r.type] * 4.2:
            small.append(r)
            continue
        units[r.key] = Unit(r)
    for r in level_rooms:
        if r.serves is not None and r.serves in units:
            units[r.serves].attached.append(r)
        elif r.serves is not None:  # bedroom missing on this level: stand alone
            units[r.key] = Unit(r)
    for s in sorted(small, key=lambda r: (-r.target_area, r.key)):
        table = TUCK_AFFINITY.get(s.type, {})
        hosts = [
            u for u in units.values() if u.primary.type not in TUCKABLE and len(u.attached) < 2
        ]
        if not hosts:
            units[s.key] = Unit(s)
            continue
        host = max(
            hosts,
            key=lambda u: (table.get(u.primary.type, 0.5), u.primary.target_area, u.primary.key),
        )
        host.attached.append(s)
    return sorted(units.values(), key=lambda u: u.primary.key)


# --- strips -----------------------------------------------------------------------------------


def level_strips(sk: Skeleton, level: int) -> list[Strip]:
    y_s1 = sk.Ds
    y_n0 = rnd(sk.Ds + sk.C)
    if level == 0:
        g0, g1 = sk.group_x0, sk.group_x1
    else:
        g0, g1 = (sk.core_x0, sk.core_x1) if sk.lanes > 0 else (0.0, 0.0)
    strips = [Strip("N", 0.0, sk.W, y_n0, sk.D, "north")]
    if sk.lanes == 0 and level > 0:  # (1-storey houses have no upper levels)
        return strips
    if g1 - g0 < EPS:  # no core, no hall: one south strip
        strips.append(Strip("SL", 0.0, sk.W, 0.0, y_s1, "south"))
        return strips
    strips.append(Strip("SL", 0.0, g0, 0.0, y_s1, "south"))
    strips.append(Strip("SR", g1, sk.W, 0.0, y_s1, "south"))
    return strips


def _strip_pref(unit: Unit, strip: Strip, level: int, wishes: dict[str, str]) -> float:
    """Penalty for placing `unit` in `strip` (zoning). `wishes`: room key -> facade side it
    must reach (balcony / terrace hosts)."""
    t = unit.primary.type
    wish = wishes.get(unit.primary.key)
    if wish is not None and wish != strip.side:
        return 3.0
    if strip.side == "north":
        if t in TUCKABLE:
            return 0.35
        return 0.0
    if level == 0 and t in {RoomType.LIVING, RoomType.OPEN_KITCHEN_LIVING}:
        return 1.5
    if level == 0 and t in PUBLIC:
        return 0.3
    if t == RoomType.BEDROOM:
        return 0.1
    return 0.0


def _min_len(unit: Unit, config: LayoutConfig) -> float:
    """Lower bound of a unit's width (attached rooms as narrow full-depth columns)."""
    return frontage(unit.primary, config) + sum(frontage(a, config) for a in unit.attached)


@dataclass(frozen=True)
class Zoning:
    """Placement wishes that come from the spec rather than from room types."""

    wishes: dict[str, str]  # room key -> facade side ("north"/"south") it must reach
    pairs: list[tuple[frozenset[str], frozenset[str], float]]  # room-key groups + weight

    @staticmethod
    def of(program: Program, wishes: dict[str, str]) -> "Zoning":
        pairs = [
            (
                frozenset(r.key for r in program.instances(a)),
                frozenset(r.key for r in program.instances(b)),
                weight,
            )
            for pairs_, weight in ((program.adjacency, 0.6), (program.open_plan, 1.5))
            for a, b in pairs_
        ]
        return Zoning(wishes, pairs)


def assign_strips(
    units: list[Unit],
    strips: list[Strip],
    level: int,
    rng: random.Random,
    config: LayoutConfig,
    zoning: Zoning,
) -> dict[str, list[Unit]] | None:
    live = [s for s in strips if s.length > EPS]
    if not live:
        return None
    units = [Unit(u.primary, list(u.attached)) for u in units]  # moves below may detach rooms
    cap = {s.name: s.length * s.depth for s in live}
    wishes = zoning.wishes

    def cost(assign: dict[str, list[Unit]]) -> float:
        total = 0.0
        strip_of: dict[str, str] = {}
        for s in live:
            us = assign[s.name]
            if not us:
                total += 3.0 + s.length * 0.4
                continue
            load = sum(u.area for u in us)
            total += 4 * (load / cap[s.name] - 1) ** 2
            if sum(_min_len(u, config) for u in us) > s.length + EPS:
                total += 25
            for u in us:
                if u.primary.min_width > s.depth + EPS:
                    total += 25
                total += _strip_pref(u, s, level, wishes)
                for r in u.rooms:
                    strip_of[r.key] = s.name
        for a, b, weight in zoning.pairs:  # wanted neighbours must share a band
            sa = {strip_of[k] for k in a if k in strip_of}
            sb = {strip_of[k] for k in b if k in strip_of}
            if sa and sb and not sa & sb:
                total += weight
        return total

    # Largest first, with seeded noise so variants explore different assignments.
    keyed = sorted(units, key=lambda u: u.primary.key)
    noise = {u.primary.key: rng.uniform(-4.0, 4.0) for u in keyed}
    order = sorted(keyed, key=lambda u: (-u.area + noise[u.primary.key], u.primary.key))
    assign: dict[str, list[Unit]] = {s.name: [] for s in live}
    strip_by_name: dict[str, Strip] = {s.name: s for s in live}

    def fits(n: str, u: Unit) -> bool:
        s = strip_by_name[n]
        used = sum(_min_len(x, config) for x in assign[n])
        return used + _min_len(u, config) <= s.length + EPS and u.primary.min_width <= s.depth + EPS

    for u in order:
        best_name = min(
            (s.name for s in live),
            key=lambda n: (
                not fits(n, u),
                (sum(x.area for x in assign[n]) + u.area) / cap[n]
                + _strip_pref(u, strip_by_name[n], level, wishes),
                n,
            ),
        )
        assign[best_name].append(u)

    current = cost(assign)
    names = [s.name for s in live]

    def exchange(src: str, dst: str, out: list[Unit], back: list[Unit]) -> bool:
        """Move `out` src -> dst and `back` dst -> src; keep the change if the cost drops."""
        nonlocal current
        for u in out:
            assign[src].remove(u)
            assign[dst].append(u)
        for u in back:
            assign[dst].remove(u)
            assign[src].append(u)
        c = cost(assign)
        if c < current - 1e-9:
            current = c
            return True
        for u in out:
            assign[dst].remove(u)
            assign[src].append(u)
        for u in back:
            assign[src].remove(u)
            assign[dst].append(u)
        return False

    def improve() -> bool:
        """First-improvement local search: move one, swap one for one, swap one for two."""
        for src, dst in itertools.permutations(names, 2):
            if any(exchange(src, dst, [u], []) for u in list(assign[src])):
                return True
        for a, b in itertools.combinations(names, 2):
            pairs = itertools.product(list(assign[a]), list(assign[b]))
            if any(exchange(a, b, [ua], [ub]) for ua, ub in pairs):
                return True
        for a, b in itertools.permutations(names, 2):  # e.g. bedroom + bath for two bedrooms
            for ua in list(assign[a]):
                twos = itertools.combinations(list(assign[b]), 2)
                if any(exchange(a, b, [ua], [x, y]) for x, y in twos):
                    return True
        return False

    for _ in range(40):
        if not improve():
            break

    # A street-side strip left empty can take a service room detached from its host unit
    # (e.g. a bathroom that would otherwise be tucked into a bedroom).
    for empty in live:
        if assign[empty.name]:
            continue
        best: tuple[float, Unit, RoomRequest] | None = None
        for other in live:
            for host_unit in assign[other.name]:
                for service in list(host_unit.attached):
                    if service.serves is not None or frontage(service, config) > empty.length + EPS:
                        continue
                    host_unit.attached.remove(service)
                    assign[empty.name].append(Unit(service))
                    c = cost(assign)
                    assign[empty.name].pop()
                    host_unit.attached.append(service)
                    if c < current - 1e-9 and (best is None or c < best[0]):
                        best = (c, host_unit, service)
        if best is not None:
            current, chosen_host, chosen = best
            chosen_host.attached.remove(chosen)
            assign[empty.name].append(Unit(chosen))
    for s in strips:
        assign.setdefault(s.name, [])
    return assign


def _affinity(a: Unit, b: Unit, program: Program) -> float:
    keys_a = {r.spec_key for r in a.rooms}
    keys_b = {r.spec_key for r in b.rooms}
    score = 0.0
    for x, y in program.adjacency:
        if (x in keys_a and y in keys_b) or (y in keys_a and x in keys_b):
            score += 2
    for x, y in program.open_plan:
        if (x in keys_a and y in keys_b) or (y in keys_a and x in keys_b):
            score += 4
    score += IMPLICIT_AFFINITY.get(frozenset({a.primary.type, b.primary.type}), 0)
    return score


def order_units(units: list[Unit], program: Program, rng: random.Random) -> list[Unit]:
    if len(units) <= 1:
        return list(units)
    pool = sorted(units, key=lambda u: u.primary.key)
    rng.shuffle(pool)
    totals = {
        u.primary.key: sum(_affinity(u, v, program) for v in pool if v is not u) for u in pool
    }
    start = max(pool, key=lambda u: totals[u.primary.key])
    chain = [start]
    pool.remove(start)
    while pool:
        best = max(
            pool,
            key=lambda u: max(_affinity(u, chain[0], program), _affinity(u, chain[-1], program)),
        )
        pool.remove(best)
        if _affinity(best, chain[0], program) > _affinity(best, chain[-1], program):
            chain.insert(0, best)
        else:
            chain.append(best)
    if rng.random() < 0.5:
        chain.reverse()
    return chain


# --- widths -----------------------------------------------------------------------------------


@dataclass
class _Part:
    column: Column
    natural: float
    minimum: float
    fixed: bool
    flex: float = 1.0  # share of surplus/deficit width it takes (service rooms stay near size)


def _grid_units(v: float, grid: float) -> int:
    return round(v / grid)


def frontage(room: RoomRequest, config: LayoutConfig) -> float:
    """Minimum width of a room's corridor side: its door plus a margin on each side."""
    door = config.wet_room_door if room.type in WET else config.interior_door
    return max(room.min_width, door[0] + 2 * config.door_margin)


def layout_strip(strip: Strip, units: list[Unit], config: LayoutConfig) -> StripLayout | None:
    """Columns with widths for `units` in order, filling the strip exactly. None = infeasible.

    Attached service rooms are tucked against the corridor where possible; if the strip is too
    short for that, they become narrow full-depth columns next to their room instead."""
    return _layout_strip(strip, units, config, allow_tucks=True) or _layout_strip(
        strip, units, config, allow_tucks=False
    )


def _layout_strip(
    strip: Strip, units: list[Unit], config: LayoutConfig, *, allow_tucks: bool
) -> StripLayout | None:
    d = strip.depth
    g = config.grid
    parts: list[_Part] = []
    for u in units:
        prim = u.primary
        if prim.min_width > d + EPS:
            return None
        tucks: list[Column] = []
        fulls: list[RoomRequest] = []
        for a in u.attached:
            width = max(config.tuck_widths.get(a.type, a.min_width), a.min_width)
            width = snap_up(width, g)
            depth = snap_up(max(a.target_area / width, a.min_width), g)
            if allow_tucks and len(tucks) < 2 and d - depth >= config.remainder_min_depth - EPS:
                tucks.append(Column("tuck", a, width, depth, owner=prim))
            else:
                fulls.append(a)
        remainder = sum(t.width * (d - t.depth) for t in tucks)
        main_natural = max((prim.target_area - remainder) / d, 0.0)
        main = _Part(
            Column("main", prim, 0.0, d),
            main_natural,
            max(frontage(prim, config), (prim.min_area - remainder) / d),  # rules minimum area
            False,
            0.2 if prim.tuckable else 1.0,
        )
        seq: list[_Part] = []
        if tucks:
            seq.append(_Part(tucks[0], tucks[0].width, tucks[0].width, True))
        seq.append(main)
        if len(tucks) > 1:
            seq.append(_Part(tucks[1], tucks[1].width, tucks[1].width, True))
        for a in fulls:
            if a.min_width > d + EPS:
                return None
            seq.append(
                _Part(
                    Column("full", a, 0.0, d),
                    a.target_area / d,
                    max(frontage(a, config), a.min_area / d),
                    False,
                    0.2,
                )
            )
        parts.extend(seq)

    total_units = _grid_units(strip.length, g)
    fixed = sum(_grid_units(p.natural, g) for p in parts if p.fixed)
    # Parts are identified by their position in the strip (never by object identity: that
    # would make tie-breaking depend on memory addresses and break determinism).
    scalable = [i for i, p in enumerate(parts) if not p.fixed]
    if not scalable:
        return None
    min_units = {i: math.ceil(parts[i].minimum / g - 1e-9) for i in scalable}
    available = total_units - fixed
    if sum(min_units.values()) > available:
        return None
    # Distribute surplus/deficit by flex weight, honouring minimums (water-filling), then round
    # to integer grid units. Natural widths are converted to grid units first.
    widths: dict[int, float] = {}
    free = list(scalable)
    budget = float(available)
    while free:
        nat = sum(parts[i].natural / g for i in free)
        weight = sum(parts[i].natural / g * parts[i].flex for i in free)
        delta = budget - nat
        trial = {
            i: (
                parts[i].natural / g + delta * (parts[i].natural / g * parts[i].flex) / weight
                if weight > EPS
                else budget / len(free)
            )
            for i in free
        }
        clamped = [i for i in free if trial[i] < min_units[i]]
        if not clamped:
            widths.update(trial)
            break
        for i in clamped:
            widths[i] = float(min_units[i])
            budget -= min_units[i]
            free.remove(i)
    ints = {i: max(min_units[i], math.floor(v + 1e-9)) for i, v in widths.items()}
    diff = available - sum(ints.values())
    ranked = sorted(scalable, key=lambda i: (-(widths[i] - math.floor(widths[i])), i))
    step = 0
    while diff > 0 and ranked:
        ints[ranked[step % len(ranked)]] += 1
        diff -= 1
        step += 1
    while diff < 0:
        i = max(scalable, key=lambda i: (ints[i] - min_units[i], -i))
        if ints[i] <= min_units[i]:
            return None
        ints[i] -= 1
        diff += 1
    columns = []
    for i, p in enumerate(parts):
        if not p.fixed:
            p.column.width = rnd(ints[i] * g)
        columns.append(p.column)
    return StripLayout(strip, columns)


def strip_areas(layout: StripLayout) -> dict[str, float]:
    areas: dict[str, float] = {}
    d = layout.strip.depth
    for c in layout.columns:
        if c.kind == "tuck" and c.owner is not None:
            areas[c.room.key] = c.width * c.depth
            areas[c.owner.key] = areas.get(c.owner.key, 0.0) + c.width * (d - c.depth)
        else:
            areas[c.room.key] = areas.get(c.room.key, 0.0) + c.width * d
    return areas


# --- scoring ----------------------------------------------------------------------------------


def _aspect_penalty(layout: StripLayout) -> float:
    d = layout.strip.depth
    penalty = 0.0
    widths: dict[str, float] = {}
    for c in layout.columns:
        if c.kind == "tuck":
            owner = c.owner.key if c.owner else c.room.key
            widths[owner] = widths.get(owner, 0.0) + c.width
            dims = (c.width, c.depth)
            limit = ASPECT_LIMIT["service"]
            penalty += max(0.0, max(dims) / min(dims) - limit)
        else:
            widths[c.room.key] = widths.get(c.room.key, 0.0) + c.width
    for c in layout.columns:
        if c.kind == "tuck":
            continue
        w = widths[c.room.key]
        ratio = max(w, d) / max(min(w, d), EPS)
        limit = ASPECT_LIMIT["service" if c.room.tuckable else "habitable"]
        penalty += max(0.0, ratio - limit)
    return penalty


CROSS_CORRIDOR_MIN = 1.5


def _neighbours(layouts: Sequence[StripLayout]) -> tuple[set[frozenset[str]], set[frozenset[str]]]:
    """Room pairs next to each other in a band, and pairs facing each other across the
    corridor (overlapping by at least CROSS_CORRIDOR_MIN)."""
    pairs: set[frozenset[str]] = set()
    spans: list[tuple[str, str, float, float]] = []  # side, key, x0, x1 (corridor-facing part)
    for lay in layouts:
        owners = [c.owner.key if c.kind == "tuck" and c.owner else c.room.key for c in lay.columns]
        keys = [c.room.key for c in lay.columns]
        for i in range(len(keys) - 1):
            pairs.add(frozenset({keys[i], keys[i + 1]}))
            pairs.add(frozenset({owners[i], owners[i + 1]}))
        x = lay.strip.x0
        for c in lay.columns:
            if c.kind != "tuck":
                spans.append((lay.strip.side, c.room.key, x, x + c.width))
            x += c.width
    across: set[frozenset[str]] = set()
    for side_a, ka, a0, a1 in spans:
        for side_b, kb, b0, b1 in spans:
            if (
                side_a == "south"
                and side_b == "north"
                and min(a1, b1) - max(a0, b0) >= (CROSS_CORRIDOR_MIN - 1e-6)
            ):
                across.add(frozenset({ka, kb}))
    return pairs, across


def unmet_pairs(levels: Sequence[LevelLayout], program: Program) -> list[tuple[str, str, str]]:
    """(kind, a, b) for wished pairs the plan does not satisfy; kind is "adjacent"/"open"."""
    pairs: set[frozenset[str]] = set()
    across: set[frozenset[str]] = set()
    for lvl in levels:
        level_pairs, level_across = _neighbours(lvl.strips)
        pairs |= level_pairs
        across |= level_across
    out = []
    for kind, wanted in (("adjacent", program.adjacency), ("open", program.open_plan)):
        ok_pairs = pairs | across if kind == "open" else pairs
        for a, b in wanted:
            if not any(
                frozenset({x.key, y.key}) in ok_pairs
                for x in program.instances(a)
                for y in program.instances(b)
            ):
                out.append((kind, a, b))
    return out


def score_candidate(
    levels: list[LevelLayout],
    program: Program,
    sk: Skeleton,
    target_floor_area: float,
    zoning: Zoning,
) -> tuple[float, dict[str, float]]:
    areas: dict[str, float] = {}
    penalty = 0.0
    for lvl in levels:
        for lay in lvl.strips:
            areas.update(strip_areas(lay))
            penalty += 0.4 * _aspect_penalty(lay)
            for c in lay.columns:
                if c.kind != "tuck":
                    penalty += _strip_pref(Unit(c.room), lay.strip, lvl.index, zoning.wishes)
        # Street-side strips left empty become landing/hall space: wasted area.
        penalty += sum(1.0 + 0.1 * s.length * s.depth for s in lvl.merged_strips)
    for r in program.rooms:
        actual = areas.get(r.key, 0.0)
        weight = 2.0 if r.explicit_target else 1.0
        deviation = abs(actual - r.target_area) / r.target_area
        # Quadratic term: spread unavoidable surplus over many rooms, not into one.
        penalty += weight * (deviation + 1.5 * deviation**2)
        if actual + 1e-6 < r.min_area:
            penalty += 5
    for kind, _, _ in unmet_pairs(levels, program):
        penalty += 1.5 if kind == "open" else 0.6
    aspect = sk.W / sk.D
    penalty += 0.5 * max(0.0, aspect - 2.0) + 0.8 * max(0.0, 1 / aspect - 1.1)
    gfa = sk.W * sk.D * sk.storeys
    penalty += 6 * abs(gfa - target_floor_area) / target_floor_area
    return penalty, areas


# --- search -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class SearchInput:
    spec: BuildingSpecification
    program: Program
    levels: dict[str, int]
    stair: StairDesign | None
    floor_area_per_storey: float
    max_width: float | None
    max_depth: float | None
    garage_width: float
    garage_depth: float
    landing_depth: float
    wishes: dict[str, str]  # room key -> facade side it must reach


def skeletons(inp: SearchInput, config: LayoutConfig, reasons: list[str]) -> list[Skeleton]:
    spec = inp.spec
    storeys = spec.targets.storeys
    g = config.grid
    area = inp.floor_area_per_storey
    lanes = storeys - 1
    lane_w = inp.stair.lane_width if inp.stair else 0.0
    core_w = lanes * lane_w
    hall_widths = [config.entrance_hall_width]
    if area < 90:  # small floor plates: a compact hall leaves room for a street-side room
        hall_widths.append(config.compact_hall_width)
    t_ext = config.exterior_wall_thickness
    ds_min = config.min_band_depth
    if inp.stair is not None:
        ds_min = max(
            ds_min,
            snap_up(t_ext / 2 + inp.stair.run + inp.landing_depth, g),
        )
    out: list[Skeleton] = []
    seen: set[tuple[float, ...]] = set()
    for aspect, scale in itertools.product(config.footprint_aspects, config.footprint_area_scales):
        width = snap(math.sqrt(area * scale * aspect), g)
        depth = snap(area * scale / width, g)
        if inp.max_width is not None and width + inp.garage_width > inp.max_width + EPS:
            reasons.append("footprint wider than the plot allows")
            continue
        if inp.max_depth is not None and depth > inp.max_depth + EPS:
            reasons.append("footprint deeper than the plot allows")
            continue
        corridor = config.corridor_width
        balanced = (depth - corridor) / 2
        options = sorted(
            {max(ds_min, snap(balanced + off, g)) for off in config.band_split_offsets}
        )
        for ds, hall_w in itertools.product(options, hall_widths):
            if depth - ds - corridor < config.min_band_depth - EPS:
                reasons.append("footprint too shallow for two room bands and a corridor")
                continue
            group = hall_w + core_w
            if group > width - EPS:
                reasons.append("footprint too narrow for the entrance hall and stair core")
                continue
            for frac in config.core_positions:
                sides: tuple[Literal["west", "east"], ...] = ("west", "east")
                for hall_side in sides:
                    if lanes == 0 and hall_side == "east":
                        continue
                    lane, w_eff = lane_w, width
                    gx0, hall, core_x0 = _place_group(
                        width, hall_w, lanes, lane, frac, hall_side, g
                    )
                    key = (width, depth, ds, gx0, hall_w, 0.0 if hall_side == "west" else 1.0)
                    if key in seen:
                        continue
                    seen.add(key)
                    if lanes and (core_x0 < EPS or core_x0 + lanes * lane > width - EPS):
                        # The core is on the facade, so that side of its lanes is the (thicker)
                        # exterior wall. Widen the lanes, and the footprint by as much, so every
                        # flight keeps its clearance and the rooms keep their width (K2.5). If
                        # the plot does not allow it, the skeleton stays as it is and the search
                        # rejects it (flights_fit_lanes); it is never dropped here, which would
                        # shift the seeds of the skeletons after it.
                        wide = snap_up(lane_w + (t_ext - config.interior_wall_thickness) / 2, g)
                        grown = rnd(width + lanes * (wide - lane_w))
                        if inp.max_width is None or grown + inp.garage_width <= inp.max_width + EPS:
                            lane, w_eff = wide, grown
                            gx0, hall, core_x0 = _place_group(
                                w_eff, hall_w, lanes, lane, frac, hall_side, g
                            )
                    garage_side: Literal["west", "east"] | None = None
                    if spec.features.garage is not None:
                        middle = gx0 + (hall_w + lanes * lane) / 2
                        garage_side = "west" if middle <= w_eff / 2 else "east"
                    out.append(
                        Skeleton(
                            W=w_eff,
                            D=depth,
                            Ds=ds,
                            C=corridor,
                            storeys=storeys,
                            core_x0=core_x0,
                            lanes=lanes,
                            lane_width=lane,
                            hall_x0=hall[0],
                            hall_x1=hall[1],
                            hall_side=hall_side,
                            garage_side=garage_side,
                        )
                    )
    return out


def _place_group(
    width: float,
    hall_w: float,
    lanes: int,
    lane_w: float,
    frac: float,
    hall_side: Literal["west", "east"],
    grid: float,
) -> tuple[float, tuple[float, float], float]:
    """Start of the hall + core group, the hall part and the core start at one position."""
    core_w = lanes * lane_w
    gx0 = snap(frac * (width - hall_w - core_w), grid)
    if hall_side == "west":
        return gx0, (gx0, rnd(gx0 + hall_w)), rnd(gx0 + hall_w)
    return gx0, (rnd(gx0 + core_w), rnd(gx0 + core_w + hall_w)), gx0


def search(inp: SearchInput, config: LayoutConfig, seed: int) -> list[Candidate]:
    """All feasible candidates, best first (deterministic for a given seed)."""
    reasons: list[str] = []
    sks = skeletons(inp, config, reasons)
    storeys = inp.spec.targets.storeys
    by_level: list[list[RoomRequest]] = [[] for _ in range(storeys)]
    for r in inp.program.rooms:
        by_level[inp.levels[r.key]].append(r)
    units_by_level = [form_units(rooms, config) for rooms in by_level]
    target = inp.floor_area_per_storey * storeys
    zoning = Zoning.of(inp.program, inp.wishes)

    candidates: list[Candidate] = []
    order = 0
    for sk_index, sk in enumerate(sks):
        if inp.stair is not None and not flights_fit_lanes(sk, inp.stair, config):
            # Skipped here, not in skeletons(): sk_index keeps seeding the same variants.
            reasons.append("the stair core against the facade leaves no room for the flight")
            continue
        for variant in range(config.variants_per_skeleton):
            # Seeded, local PRNG: the only source of variation (determinism, not security).
            rng = random.Random(f"{seed}:{sk_index}:{variant}")  # noqa: S311
            levels: list[LevelLayout] = []
            ok = True
            for lv in range(storeys):
                strips = level_strips(sk, lv)
                assign = assign_strips(units_by_level[lv], strips, lv, rng, config, zoning)
                if assign is None:
                    ok = False
                    reasons.append(f"floor {lv + 1}: no room bands")
                    break
                layouts: list[StripLayout] = []
                merged: list[Strip] = []
                for s in strips:
                    if s.length < EPS:
                        continue
                    units = assign.get(s.name, [])
                    if not units:
                        if s.side == "north":
                            ok = False
                            reasons.append(f"floor {lv + 1}: garden-side band left empty")
                            break
                        merged.append(s)
                        continue
                    lay = layout_strip(s, order_units(units, inp.program, rng), config)
                    if lay is None:
                        ok = False
                        reasons.append(
                            f"floor {lv + 1}: rooms do not fit the "
                            f"{'garden' if s.side == 'north' else 'street'}-side band at "
                            "their minimum widths"
                        )
                        break
                    layouts.append(lay)
                if not ok:
                    break
                levels.append(LevelLayout(lv, layouts, merged))
            if not ok:
                continue
            score, areas = score_candidate(levels, inp.program, sk, target, zoning)
            candidates.append(Candidate(order, sk, levels, score, areas))
            order += 1
    if not candidates:
        summary = sorted(set(reasons), key=lambda r: (-reasons.count(r), r))[:4]
        raise PlanningError("No feasible layout for this specification", summary)
    candidates.sort(key=lambda c: (round(c.score, 9), c.order))
    return candidates
