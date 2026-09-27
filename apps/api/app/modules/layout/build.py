"""Steps 7-9 — build BuildingModel elements from the regions of a planned candidate.

Everything positional is decided here from the plan; nothing is random. Element ids are
uuid5(id_namespace, semantic_key) unless the caller supplies ids of a previous model for the same
semantic keys (ID stability across regeneration, docs/building-model.md §7).
"""

import math
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from shapely import Point as ShapelyPoint
from shapely import Polygon as ShapelyPolygon
from shapely import box, unary_union
from shapely.geometry.polygon import orient

from app.modules.building.elements import (
    Door,
    DoorDimensions,
    DoorProperties,
    Element,
    Railing,
    RailingDimensions,
    RailingProperties,
    Relationship,
    Roof,
    RoofDimensions,
    RoofProperties,
    Room,
    RoomDimensions,
    RoomProperties,
    Slab,
    SlabDimensions,
    SlabProperties,
    Stair,
    StairDimensions,
    StairProperties,
    Wall,
    WallDimensions,
    WallProperties,
    Window,
    WindowDimensions,
    WindowProperties,
)
from app.modules.building.enums import (
    DoorKind,
    DoorSwing,
    Layer,
    Origin,
    RailingKind,
    RelationshipKind,
    RoofType,
    RoomType,
    SlabKind,
    StairType,
    WallKind,
    WindowKind,
)
from app.modules.building.geometry import Point, segment_overlap_length
from app.modules.building.model import (
    SCHEMA_VERSION,
    BuildingInfo,
    BuildingModel,
    Level,
    ModelMetadata,
)
from app.modules.building.primitives import EPS, Rotation, Vec2, Vec3
from app.modules.building.specification import BuildingSpecification, FinishLevel, WindowStyle
from app.modules.layout.config import LayoutConfig
from app.modules.layout.furnish import furnish
from app.modules.layout.plan import Rect, Region, Segment, rnd
from app.modules.layout.program import HABITABLE, WET
from app.modules.layout.regions import (
    PlanLayout,
    derive_interior_walls,
    facade_span,
    shared_edges,
    subtract_open,
)
from app.modules.rules.profile import BuildingRulesProfile

HALF_PI = math.pi / 2
FLOORS: dict[RoomType, str] = {
    RoomType.BEDROOM: "parquet",
    RoomType.LIVING: "parquet",
    RoomType.DINING: "parquet",
    RoomType.STUDY: "parquet",
    RoomType.OPEN_KITCHEN_LIVING: "parquet",
    RoomType.WALK_IN_CLOSET: "parquet",
    RoomType.CORRIDOR: "parquet",
    RoomType.KITCHEN: "tile",
    RoomType.BATHROOM: "tile",
    RoomType.EN_SUITE: "tile",
    RoomType.WC: "tile",
    RoomType.LAUNDRY: "tile",
    RoomType.ENTRANCE: "tile",
    RoomType.GARAGE: "concrete",
    RoomType.BALCONY: "decking",
    RoomType.TERRACE: "decking",
}
TILED_WALLS = frozenset({RoomType.BATHROOM, RoomType.EN_SUITE, RoomType.WC, RoomType.LAUNDRY})
SERVICE_WINDOWS = frozenset(
    {RoomType.BATHROOM, RoomType.EN_SUITE, RoomType.WC, RoomType.LAUNDRY, RoomType.UTILITY}
)
NO_CORRIDOR_DOOR = frozenset({RoomType.CORRIDOR, RoomType.ENTRANCE, RoomType.STAIRCASE})


class BuildError(Exception):
    """The candidate cannot be turned into a model (e.g. no room for a door)."""


class Ids:
    def __init__(self, namespace: uuid.UUID, previous: Mapping[str, uuid.UUID] | None) -> None:
        self.namespace = namespace
        self.previous = dict(previous or {})

    def __call__(self, semantic_key: str) -> uuid.UUID:
        return self.previous.get(semantic_key) or uuid.uuid5(self.namespace, semantic_key)


@dataclass
class WallPlan:
    key: str
    name: str
    level: int
    start: Point
    end: Point
    kind: WallKind
    thickness: float
    material: str
    left: str
    right: str
    supports: list[str] = field(default_factory=list)
    occupied: list[tuple[float, float]] = field(default_factory=list)

    @property
    def length(self) -> float:
        return math.dist(self.start, self.end)

    @property
    def horizontal(self) -> bool:
        return abs(self.end[1] - self.start[1]) < 1e-6

    @property
    def coord(self) -> float:
        return self.start[1] if self.horizontal else self.start[0]

    def param(self, a: float) -> float:
        """Distance from the wall start of the point at plan coordinate `a` along its line."""
        s, e = (self.start[0], self.end[0]) if self.horizontal else (self.start[1], self.end[1])
        return (a - s) if e >= s else (s - a)

    def covers(self, seg: Segment) -> bool:
        if (seg.orientation == "h") != self.horizontal or abs(seg.coord - self.coord) > 1e-6:
            return False
        lo, hi = sorted((self.param(seg.a0), self.param(seg.a1)))
        return lo >= -1e-6 and hi <= self.length + 1e-6

    def place(
        self,
        seg: Segment,
        width: float,
        *,
        margin: float,
        prefer: Literal["center", "low", "high"] = "center",
        gap: float = 0.15,
    ) -> float | None:
        """Offset of an opening of `width` within `seg` (plan coordinates along the wall),
        avoiding existing openings. `low`/`high` prefer the smaller/larger plan coordinate."""
        p0, p1 = self.param(seg.a0), self.param(seg.a1)
        lo, hi = max(min(p0, p1) + margin, 0.0), min(max(p0, p1) - margin, self.length)
        if hi - lo < width - 1e-6:
            return None
        free = [(lo, hi)]
        for o0, o1 in sorted(self.occupied):
            nxt = []
            for f0, f1 in free:
                if o1 + gap <= f0 or o0 - gap >= f1:
                    nxt.append((f0, f1))
                    continue
                if o0 - gap > f0:
                    nxt.append((f0, o0 - gap))
                if o1 + gap < f1:
                    nxt.append((o1 + gap, f1))
            free = nxt
        fits = [(f0, f1) for f0, f1 in free if f1 - f0 >= width - 1e-6]
        if not fits:
            return None
        increasing = self.param(seg.a1) >= self.param(seg.a0)
        if prefer == "center":
            want = (lo + hi - width) / 2
        else:
            at_low_param = (prefer == "low") == increasing
            want = lo if at_low_param else hi - width
        best = min(
            (min(max(want, f0), f1 - width) for f0, f1 in fits),
            key=lambda s: (abs(s - want), s),
        )
        start = round(best, 3)
        self.occupied.append((start, start + width))
        return start


@dataclass
class _Context:
    plan: PlanLayout
    spec: BuildingSpecification
    profile: BuildingRulesProfile
    config: LayoutConfig
    ids: Ids
    seed: int
    walls: list[WallPlan] = field(default_factory=list)
    elements: list[Element] = field(default_factory=list)
    level_ids: list[uuid.UUID] = field(default_factory=list)
    room_polys: dict[tuple[int, str], ShapelyPolygon] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=dict)
    swing: int = 0

    def next_name(self, prefix: str, level: int) -> str:
        key = f"{prefix}{level + 1}"
        self.counters[key] = self.counters.get(key, 0) + 1
        return f"{prefix}{level + 1}-{self.counters[key]:02d}"

    @property
    def wall_height(self) -> float:
        return rnd(self.spec.targets.floor_to_floor_height_m - self.config.floor_slab_thickness)


def region_polygon(region: Region) -> list[Point]:
    """CCW boundary of the union of a region's rectangles, starting at its lowest-left vertex."""
    shape = unary_union([box(r.x0, r.y0, r.x1, r.y1) for r in region.rects])
    if not isinstance(shape, ShapelyPolygon) or len(shape.interiors) > 0:
        raise BuildError(f"{region.name}: region is not a simple polygon")
    shape = orient(shape, sign=1.0)
    pts = [(rnd(x), rnd(y)) for x, y in list(shape.exterior.coords)[:-1]]
    # Drop collinear vertices (unions keep the rectangles' corners), then start at min (y, x).
    clean: list[Point] = []
    n = len(pts)
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        if abs((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])) > 1e-9:
            clean.append(b)
    start = min(range(len(clean)), key=lambda i: (clean[i][1], clean[i][0]))
    return clean[start:] + clean[:start]


def _rel(kind: RelationshipKind, target: uuid.UUID) -> Relationship:
    return Relationship(kind=kind, target_id=target)


# --- walls --------------------------------------------------------------------------------------


def _walls(ctx: _Context) -> None:
    sk, cfg = ctx.plan.skeleton, ctx.config
    facade = cfg.facade_materials[ctx.spec.style.facade_material]
    top = sk.storeys - 1
    for lv in range(sk.storeys):
        corners = [(0.0, 0.0), (sk.W, 0.0), (sk.W, sk.D), (0.0, sk.D)]
        supports = [f"slab:L{lv + 1}"] if lv < top else ["roof:main"]
        for i, side in enumerate("SENW"):
            ctx.walls.append(
                WallPlan(
                    key=f"wall:ext:L{lv}:{side}",
                    name=ctx.next_name("W", lv),
                    level=lv,
                    start=corners[i],
                    end=corners[(i + 1) % 4],
                    kind=WallKind.EXTERIOR,
                    thickness=cfg.exterior_wall_thickness,
                    material=facade,
                    left="interior_wall",
                    right=facade,
                    supports=list(supports),
                )
            )
        if lv == 0 and ctx.plan.garage is not None:
            g = ctx.plan.garage
            half = cfg.exterior_wall_thickness / 2
            if sk.garage_side == "west":  # ends stop at the house wall's outer face
                loop = [
                    ("S", (g.x0, 0.0), (-half, 0.0)),
                    ("N", (-half, g.y1), (g.x0, g.y1)),
                    ("W", (g.x0, g.y1), (g.x0, 0.0)),
                ]
            else:
                loop = [
                    ("S", (sk.W + half, 0.0), (g.x1, 0.0)),
                    ("E", (g.x1, 0.0), (g.x1, g.y1)),
                    ("N", (g.x1, g.y1), (sk.W + half, g.y1)),
                ]
            for side, start, end in loop:
                ctx.walls.append(
                    WallPlan(
                        key=f"wall:garage:{side}",
                        name=ctx.next_name("W", 0),
                        level=0,
                        start=(rnd(start[0]), rnd(start[1])),
                        end=(rnd(end[0]), rnd(end[1])),
                        kind=WallKind.EXTERIOR,
                        thickness=cfg.exterior_wall_thickness,
                        material=facade,
                        left="interior_wall",
                        right=facade,
                        supports=["roof:garage"],
                    )
                )
        level = ctx.plan.levels[lv]
        types = {r.key: r.room_type for r in level.regions}
        seen: dict[str, int] = {}
        for run in derive_interior_walls(level, sk.W, sk.D):
            lo_key, hi_key, _ = max(run.pieces, key=lambda p: (p[2], p[0], p[1]))
            base = f"wall:L{lv}:{lo_key}|{hi_key}"
            seen[base] = seen.get(base, 0) + 1
            key = base if seen[base] == 1 else f"{base}:{seen[base]}"

            # A face is tiled only if every room it faces along the run is a wet room.
            low_tile = all(types.get(p[0]) in TILED_WALLS for p in run.pieces)
            high_tile = all(types.get(p[1]) in TILED_WALLS for p in run.pieces)
            if run.orientation == "h":
                start, end = (run.a0, run.coord), (run.a1, run.coord)
                left_tile, right_tile = high_tile, low_tile  # left = north = high side
            else:
                start, end = (run.coord, run.a0), (run.coord, run.a1)
                left_tile, right_tile = low_tile, high_tile  # left = west = low side
            ctx.walls.append(
                WallPlan(
                    key=key,
                    name=ctx.next_name("W", lv),
                    level=lv,
                    start=(rnd(start[0]), rnd(start[1])),
                    end=(rnd(end[0]), rnd(end[1])),
                    kind=WallKind.INTERIOR,
                    thickness=cfg.interior_wall_thickness,
                    material="interior_wall",
                    left="tile" if left_tile else "interior_wall",
                    right="tile" if right_tile else "interior_wall",
                )
            )


def _wall_on(ctx: _Context, level: int, seg: Segment) -> WallPlan:
    for w in ctx.walls:
        if w.level == level and w.covers(seg):
            return w
    raise BuildError(f"No wall along {seg} on floor {level + 1}")


def _facade_wall(ctx: _Context, level: int, side: str) -> WallPlan:
    return next(w for w in ctx.walls if w.key == f"wall:ext:L{level}:{side}")


# --- openings -----------------------------------------------------------------------------------


@dataclass
class _Door:
    key: str
    wall: WallPlan
    offset: float
    width: float
    height: float
    kind: DoorKind
    swing: DoorSwing
    material: str


@dataclass
class _Window:
    key: str
    wall: WallPlan
    offset: float
    width: float
    height: float
    sill: float
    kind: WindowKind
    mullions: int


def _openings(ctx: _Context) -> tuple[list[_Door], list[_Window]]:
    sk, cfg, rules = ctx.plan.skeleton, ctx.config, ctx.profile
    doors: list[_Door] = []
    windows: list[_Window] = []

    def door(
        key: str,
        level: int,
        seg: Segment,
        size: tuple[float, float],
        kind: DoorKind,
        swing: DoorSwing | None,
        material: str,
        *,
        min_width: float,
        prefer: Literal["center", "low", "high"] = "center",
        margin: float | None = None,
    ) -> None:
        wall = _wall_on(ctx, level, seg)
        margin = cfg.door_margin if margin is None else margin
        width = size[0]
        offset = wall.place(seg, width, margin=margin, prefer=prefer)
        if offset is None and min_width < width:
            width = min_width
            offset = wall.place(seg, width, margin=margin, prefer=prefer)
        if offset is None:
            raise BuildError(f"No room for door {key}")
        if swing is None:
            ctx.swing += 1
            swing = DoorSwing.LEFT if ctx.swing % 2 else DoorSwing.RIGHT
        doors.append(_Door(key, wall, offset, width, size[1], kind, swing, material))

    entrance = (
        max(cfg.entrance_door[0], rules.doors.entrance.min_width_m),
        max(cfg.entrance_door[1], rules.doors.entrance.min_height_m),
    )
    interior = (
        max(cfg.interior_door[0], rules.doors.interior.min_width_m),
        max(cfg.interior_door[1], rules.doors.interior.min_height_m),
    )
    wet = (
        max(cfg.wet_room_door[0], rules.doors.bathroom.min_width_m),
        max(cfg.wet_room_door[1], rules.doors.bathroom.min_height_m),
    )
    core_mid = (sk.group_x0 + sk.group_x1) / 2

    # Front door, in the hall part (not in front of the stair lanes).
    door(
        "door:front",
        0,
        Segment("h", 0.0, sk.hall_x0, sk.hall_x1),
        entrance,
        DoorKind.ENTRANCE,
        DoorSwing.LEFT,
        "wood_dark",
        min_width=rules.doors.entrance.min_width_m,
        margin=0.25,
    )

    for level in ctx.plan.levels:
        lv = level.index
        corridor = level.get(f"corridor_{lv}")
        if corridor is None:
            raise BuildError(f"Floor {lv + 1} has no corridor")
        for region in level.regions:
            if (
                region.kind != "room"
                or not region.inside
                or region.request is None
                or region.room_type in NO_CORRIDOR_DOOR
            ):
                continue
            req = region.request
            target = corridor
            if req.serves is not None:
                owner = level.get(req.serves)
                if owner is not None:
                    target = owner
            edges, open_length = subtract_open(shared_edges(region, target), level.open_edges)
            if open_length >= 0.9:
                continue  # open to the corridor (open plan): no door needed
            if not edges and target is corridor and lv == 0:
                hall = level.get("hall_0")
                target = hall if hall is not None else corridor
                edges, _ = subtract_open(shared_edges(region, target), level.open_edges)
            if not edges:
                raise BuildError(f"{region.name} cannot be reached from the corridor")
            seg = max(edges, key=lambda e: (e.length, -e.a0))
            is_wet = region.room_type in WET
            # Doors sit at the end of the wall nearer the stair core (shorter walks, and the
            # rest of the wall stays free for furniture); side doors (en-suites) are centered.
            prefer: Literal["center", "low", "high"] = (
                "low" if (seg.a0 + seg.a1) / 2 > core_mid else "high"
            )
            if seg.orientation == "v":
                prefer = "center"
            door(
                f"door:{region.key}",
                lv,
                seg,
                wet if is_wet else interior,
                DoorKind.INTERIOR,
                None,
                "wood",
                min_width=rules.doors.bathroom.min_width_m
                if is_wet
                else rules.doors.interior.min_width_m,
                prefer=prefer,
            )

    if ctx.plan.garage is not None:
        g = ctx.plan.garage
        x = 0.0 if sk.garage_side == "west" else sk.W
        door(
            "door:garage_house",
            0,
            Segment("v", x, sk.Ds, rnd(sk.Ds + sk.C)),
            interior,
            DoorKind.INTERIOR,
            None,
            "wood",
            min_width=rules.doors.interior.min_width_m,
            margin=0.15,
        )
        cars = ctx.spec.features.garage.cars if ctx.spec.features.garage else 1
        per_car = max(cfg.garage_door_width_per_car, rules.doors.garage.min_width_per_car_m)
        width = min(cars * per_car, g.w - 0.3 - 2 * 0.3)
        front = next(w for w in ctx.walls if w.key == "wall:garage:S")
        xs = sorted((front.start[0], front.end[0]))
        door(
            "door:garage",
            0,
            Segment("h", 0.0, xs[0], xs[1]),
            (rnd(width), max(cfg.garage_door_height, rules.doors.garage.min_height_m)),
            DoorKind.GARAGE,
            DoorSwing.SLIDING,
            "metal",
            min_width=rnd(width),
            margin=0.3,
        )

    sliding = cfg.sliding_door
    for att in ctx.plan.attachments:
        host = ctx.plan.levels[att.level].get(att.host)
        span = facade_span(host, att.side, sk) if host is not None else None
        if span is None:
            raise BuildError(f"The {att.kind} has no host room on the facade")
        lo, hi = max(span.x0, att.rect.x0), min(span.x1, att.rect.x1)
        y = sk.D if att.side == "north" else 0.0
        width = min(sliding[0], hi - lo - 0.5)
        door(
            f"door:{att.kind}_{att.index}",
            att.level,
            Segment("h", y, lo, hi),
            (rnd(width), sliding[1]),
            DoorKind.SLIDING,
            DoorSwing.SLIDING,
            "glass",
            min_width=min(1.6, rnd(width)),
            margin=0.25,
        )
    # Garden door from the main living space when there is no terrace.
    if not any(a.kind == "terrace" for a in ctx.plan.attachments):
        level0 = ctx.plan.levels[0]
        for rtype in (RoomType.LIVING, RoomType.OPEN_KITCHEN_LIVING, RoomType.DINING):
            spans = [
                s
                for r in level0.regions
                if r.room_type == rtype
                for s in [facade_span(r, "north", sk)]
                if s is not None
            ]
            if not spans:
                continue
            span = spans[0]
            if span.w >= 3.0:
                door(
                    "door:garden",
                    0,
                    Segment("h", sk.D, span.x0, span.x1),
                    (min(sliding[0], rnd(span.w - 0.6)), sliding[1]),
                    DoorKind.SLIDING,
                    DoorSwing.SLIDING,
                    "glass",
                    min_width=1.6,
                    margin=0.25,
                )
            break

    _windows(ctx, doors, windows)
    return doors, windows


def _facade_segments(ctx: _Context, region: Region) -> list[tuple[str, Segment]]:
    sk = ctx.plan.skeleton
    garage = ctx.plan.garage
    out: dict[str, list[tuple[float, float]]] = {"S": [], "N": [], "W": [], "E": []}
    if not region.inside:
        return []
    for r in region.rects:
        if abs(r.y0) < 1e-6:
            out["S"].append((r.x0, r.x1))
        if abs(r.y1 - sk.D) < 1e-6:
            out["N"].append((r.x0, r.x1))
        for side, x in (("W", r.x0), ("E", r.x1)):
            limit = 0.0 if side == "W" else sk.W
            if abs(x - limit) > 1e-6:
                continue
            lo, hi = r.y0, r.y1
            blocked = (
                region.level == 0
                and garage is not None
                and sk.garage_side == ("west" if side == "W" else "east")
            )
            if blocked and garage is not None:
                lo = max(lo, garage.y1)
            if hi - lo > 1e-6:
                out[side].append((lo, hi))
    result: list[tuple[str, Segment]] = []
    coords = {"S": 0.0, "N": sk.D, "W": 0.0, "E": sk.W}
    for side, spans in out.items():
        merged: list[list[float]] = []
        for a, b in sorted(spans):
            if merged and abs(merged[-1][1] - a) < 1e-6:
                merged[-1][1] = b
            else:
                merged.append([a, b])
        for a, b in merged:
            result.append((side, Segment("h" if side in "SN" else "v", coords[side], a, b)))
    return result


def _windows(ctx: _Context, doors: list[_Door], windows: list[_Window]) -> None:
    sk, cfg, rules = ctx.plan.skeleton, ctx.config, ctx.profile
    wall_h = ctx.wall_height
    style = ctx.spec.style.window_style
    preset = cfg.window_presets[style]
    ratio = max(preset.glazing_ratio, rules.windows.min_glazing_to_floor_ratio * 1.15)

    def dims(level: int) -> tuple[float, float]:
        sill = preset.sill
        if level > 0:
            sill = max(sill, rules.windows.guard_required_below_sill_m)
        height = min(preset.height, wall_h - cfg.lintel_min - sill)
        return rnd(sill), rnd(height)

    def add(
        key: str,
        level: int,
        side: str,
        seg: Segment,
        width: float,
        height: float,
        sill: float,
        kind: WindowKind,
        mullions: int,
    ) -> float:
        wall = _facade_wall(ctx, level, side)
        width = rnd(width)
        offset = wall.place(seg, width, margin=cfg.window_margin)
        if offset is None:
            return 0.0
        windows.append(_Window(key, wall, offset, width, height, sill, kind, mullions))
        return width * height

    def glazing_of(region: Region) -> float:
        total = 0.0
        for d in doors:
            if d.kind != DoorKind.SLIDING or d.wall.level != region.level:
                continue
            mid = _point_on(d.wall, d.offset + d.width / 2)
            poly = ctx.room_polys.get((region.level, region.key))
            if poly is not None and poly.exterior.distance(ShapelyPoint(mid)) < EPS:
                total += d.width * d.height
        return total

    min_w = rules.windows.min_width_m
    for level in ctx.plan.levels:
        lv = level.index
        for region in level.regions:
            segments = _facade_segments(ctx, region)
            if not segments:
                continue
            rtype = region.room_type
            n = 0
            if region.kind == "room" and rtype in HABITABLE:
                sill, height = dims(lv)
                kind = (
                    WindowKind.PANORAMIC
                    if style == WindowStyle.PANORAMIC and lv == 0
                    else WindowKind.CASEMENT
                )
                needed = ratio * region.area - glazing_of(region)
                primary = "S" if region.rects[0].y0 < 1e-6 else "N"
                ordered = sorted(
                    segments, key=lambda s: (s[0] != primary, -s[1].length, s[0], s[1].a0)
                )
                for side, seg in ordered:
                    if needed <= 1e-6 or n >= 3:
                        break
                    available = seg.length - 2 * cfg.window_margin
                    width = min(max(needed / height, min_w), available, 4.8)
                    if width < min_w - 1e-6:
                        continue
                    width = math.floor(width / 0.05 + 1e-9) * 0.05
                    mullions = min(12, max(0, math.ceil(width / preset.mullion_spacing) - 1))
                    got = add(
                        f"window:{region.key}:{side}:{n}",
                        lv,
                        side,
                        seg,
                        width,
                        height,
                        sill,
                        kind,
                        mullions,
                    )
                    if got > 0:
                        needed -= got
                        n += 1
            elif region.kind == "room" and rtype in SERVICE_WINDOWS:
                w, h, sill = cfg.service_window
                side, seg = max(segments, key=lambda s: (s[1].length, s[0]))
                if seg.length - 2 * cfg.window_margin >= w:
                    add(
                        f"window:{region.key}:{side}:0",
                        lv,
                        side,
                        seg,
                        w,
                        h,
                        sill,
                        WindowKind.CASEMENT,
                        0,
                    )
            elif rtype in (RoomType.CORRIDOR, RoomType.STAIRCASE, RoomType.ENTRANCE) or (
                region.kind == "void"
            ):
                height, sill = cfg.stair_window
                for side, seg in sorted(segments, key=lambda s: (s[0], s[1].a0)):
                    if rtype == RoomType.CORRIDOR and side in "SN":
                        continue
                    width = min(1.0, seg.length - 2 * cfg.window_margin)
                    if width >= min_w - 1e-6:
                        add(
                            f"window:{region.key}:{side}:{n}",
                            lv,
                            side,
                            seg,
                            width,
                            height,
                            sill,
                            WindowKind.FIXED,
                            0,
                        )
                        n += 1
    # Garage side window.
    if ctx.plan.garage is not None:
        g = ctx.plan.garage
        side = "W" if sk.garage_side == "west" else "E"
        wall = next(w for w in ctx.walls if w.key == f"wall:garage:{side}")
        w, h, sill = cfg.service_window
        seg = Segment("v", g.x0 if side == "W" else g.x1, g.y0, g.y1)
        offset = wall.place(seg, w, margin=cfg.window_margin)
        if offset is not None:
            windows.append(
                _Window("window:garage:0", wall, offset, w, h, sill, WindowKind.FIXED, 0)
            )


def _point_on(wall: WallPlan, t: float) -> Point:
    (sx, sy), (ex, ey) = wall.start, wall.end
    f = t / wall.length
    return (sx + (ex - sx) * f, sy + (ey - sy) * f)


# --- assembly -----------------------------------------------------------------------------------


def build_model(
    plan: PlanLayout,
    spec: BuildingSpecification,
    profile: BuildingRulesProfile,
    config: LayoutConfig,
    *,
    seed: int,
    id_namespace: uuid.UUID,
    previous_ids: Mapping[str, uuid.UUID] | None = None,
    furniture: bool = True,
) -> BuildingModel:
    ids = Ids(id_namespace, previous_ids)
    ctx = _Context(plan, spec, profile, config, ids, seed)
    sk = plan.skeleton
    f2f = spec.targets.floor_to_floor_height_m
    levels = [
        Level(
            id=ids(f"level:L{i}"),
            name=f"Floor {i + 1}",
            index=i,
            elevation=rnd(i * f2f),
            height=f2f,
            semantic_key=f"level:L{i}",
        )
        for i in range(sk.storeys)
    ]
    ctx.level_ids = [lvl.id for lvl in levels]

    # Rooms
    room_elements: dict[tuple[int, str], Room] = {}
    room_abs: dict[tuple[int, str], list[Point]] = {}
    for level in plan.levels:
        for region in level.regions:
            if region.kind != "room":
                continue
            pts = region_polygon(region)
            ctx.room_polys[(level.index, region.key)] = ShapelyPolygon(pts)
            room_abs[(level.index, region.key)] = pts
    _walls(ctx)
    doors, windows = _openings(ctx)

    finish = spec.style.interior_finish_level
    for level in plan.levels:
        lv = level.index
        for region in level.regions:
            if region.kind != "room":
                continue
            pts = room_abs[(lv, region.key)]
            ox, oy = min(p[0] for p in pts), min(p[1] for p in pts)
            poly = ctx.room_polys[(lv, region.key)]
            if region.room_type is None or region.zone is None:
                raise BuildError(f"{region.name}: room region without a type")
            floor = FLOORS.get(region.room_type, "floor")
            if finish == FinishLevel.ECONOMY and floor == "parquet":
                floor = "floor"
            adjacent = sorted(
                other.key
                for other in level.regions
                if other.kind == "room"
                and other.key != region.key
                and _share_edge(pts, room_abs[(lv, other.key)])
            )
            room = Room(
                id=ids(f"room:{region.key}"),
                name=region.name,
                layer=Layer.ARCHITECTURE,
                level_id=levels[lv].id,
                position=Vec3(x=ox, y=oy, z=0),
                rotation=Rotation(),
                material_id=floor,
                relationships=[
                    _rel(RelationshipKind.ADJACENT_TO, ids(f"room:{k}")) for k in adjacent
                ],
                origin=Origin.GENERATED,
                semantic_key=f"room:{region.key}",
                dimensions=RoomDimensions(
                    area=poly.area, perimeter=poly.length, height=ctx.wall_height
                ),
                properties=RoomProperties(
                    room_type=region.room_type,
                    zone=region.zone,
                    boundary=[Vec2(x=rnd(x - ox), y=rnd(y - oy)) for x, y in pts],
                    floor_material_id=floor,
                ),
            )
            room_elements[(lv, region.key)] = room

    def rooms_on(level: int, p: Point) -> list[Room]:
        pt = ShapelyPoint(p)
        return [
            room_elements[(lv, key)]
            for (lv, key), poly in ctx.room_polys.items()
            if lv == level and poly.exterior.distance(pt) < EPS
        ]

    elements: list[Element] = [room_elements[k] for k in sorted(room_elements)]

    for w in ctx.walls:
        axis = (w.start, w.end)
        bounds = sorted(
            {
                room.semantic_key
                for (lv, key), pts in room_abs.items()
                if lv == w.level
                for room in [room_elements[(lv, key)]]
                if any(
                    segment_overlap_length(axis, (pts[i], pts[(i + 1) % len(pts)])) > EPS
                    for i in range(len(pts))
                )
            }
        )
        exterior = w.kind == WallKind.EXTERIOR
        elements.append(
            Wall(
                id=ids(w.key),
                name=w.name,
                layer=Layer.STRUCTURE if exterior else Layer.ARCHITECTURE,
                level_id=levels[w.level].id,
                position=Vec3(x=w.start[0], y=w.start[1], z=0),
                rotation=Rotation(z=math.atan2(w.end[1] - w.start[1], w.end[0] - w.start[0])),
                material_id=w.material,
                relationships=[_rel(RelationshipKind.BOUNDS, ids(k)) for k in bounds]
                + [_rel(RelationshipKind.SUPPORTS, ids(k)) for k in w.supports],
                origin=Origin.GENERATED,
                semantic_key=w.key,
                dimensions=WallDimensions(
                    length=w.length, thickness=w.thickness, height=ctx.wall_height
                ),
                properties=WallProperties(
                    wall_kind=w.kind,
                    load_bearing=exterior,
                    finish_left_id=w.left,
                    finish_right_id=w.right,
                ),
            )
        )

    for d in doors:
        mid = _point_on(d.wall, d.offset + d.width / 2)
        connects = sorted(r.semantic_key for r in rooms_on(d.wall.level, mid))
        elements.append(
            Door(
                id=ids(d.key),
                name=ctx.next_name("D", d.wall.level),
                layer=Layer.ARCHITECTURE,
                level_id=levels[d.wall.level].id,
                position=Vec3(x=d.offset, y=0, z=0),
                rotation=Rotation(),
                material_id=d.material,
                relationships=[_rel(RelationshipKind.HOSTED_BY, ids(d.wall.key))]
                + [_rel(RelationshipKind.CONNECTS, ids(k)) for k in connects],
                origin=Origin.GENERATED,
                semantic_key=d.key,
                dimensions=DoorDimensions(
                    width=d.width, height=d.height, thickness=config.door_thickness
                ),
                properties=DoorProperties(
                    door_kind=d.kind, swing=d.swing, frame_material_id="window_frame"
                ),
            )
        )
    for win in windows:
        elements.append(
            Window(
                id=ids(win.key),
                name=ctx.next_name("WN", win.wall.level),
                layer=Layer.ARCHITECTURE,
                level_id=levels[win.wall.level].id,
                position=Vec3(x=win.offset, y=0, z=win.sill),
                rotation=Rotation(),
                material_id="glass",
                relationships=[_rel(RelationshipKind.HOSTED_BY, ids(win.wall.key))],
                origin=Origin.GENERATED,
                semantic_key=win.key,
                dimensions=WindowDimensions(width=win.width, height=win.height),
                properties=WindowProperties(
                    window_kind=win.kind, frame_material_id="window_frame", mullions=win.mullions
                ),
            )
        )

    elements += _slabs(ctx, levels)
    elements += _stairs_and_railings(ctx, levels, room_elements)
    elements += _roofs(ctx, levels)
    if furniture:
        elements += furnish(ctx.plan, room_elements, doors_to_spans(doors), levels, ids)

    return BuildingModel(
        schema_version=SCHEMA_VERSION,
        id=ids("model"),
        building=BuildingInfo(
            name=spec.name,
            building_type="single_family_house",
            description=spec.description
            or f"Generated by {config.engine_version} from a building specification.",
        ),
        units="m",
        engine_version=config.engine_version,
        seed=seed,
        levels=levels,
        elements=elements,
        metadata=ModelMetadata(
            source="layout", generator=f"{config.engine_version} · rules {profile.ref}"
        ),
    )


def doors_to_spans(doors: list[_Door]) -> list[tuple[int, Point, Point]]:
    """Door openings as (level, plan start, plan end) — furniture keeps them clear."""
    return [
        (d.wall.level, _point_on(d.wall, d.offset), _point_on(d.wall, d.offset + d.width))
        for d in doors
    ]


def _share_edge(a: list[Point], b: list[Point]) -> bool:
    ea = [(a[i], a[(i + 1) % len(a)]) for i in range(len(a))]
    eb = [(b[i], b[(i + 1) % len(b)]) for i in range(len(b))]
    return any(segment_overlap_length(x, y) > EPS for x in ea for y in eb)


# --- slabs, stairs, roofs -----------------------------------------------------------------------


def _polygon_rel(points: list[Point]) -> tuple[Point, list[Vec2]]:
    ox = min(p[0] for p in points)
    oy = min(p[1] for p in points)
    return (ox, oy), [Vec2(x=rnd(x - ox), y=rnd(y - oy)) for x, y in points]


def _union_outline(rects: list[Rect]) -> list[Point]:
    region = Region("outline", "room", rects, 0, "outline")
    return region_polygon(region)


def _slab(
    ctx: _Context,
    key: str,
    name: str,
    level: uuid.UUID,
    outline: list[Point],
    holes: list[list[Point]],
    thickness: float,
    kind: SlabKind,
) -> Slab:
    (ox, oy), rel = _polygon_rel(outline)
    hole_rel = [[Vec2(x=rnd(x - ox), y=rnd(y - oy)) for x, y in h] for h in holes]
    area = ShapelyPolygon(outline, holes).area
    return Slab(
        id=ctx.ids(key),
        name=name,
        layer=Layer.STRUCTURE,
        level_id=level,
        position=Vec3(x=ox, y=oy, z=0),
        rotation=Rotation(),
        material_id="concrete",
        relationships=[],
        origin=Origin.GENERATED,
        semantic_key=key,
        dimensions=SlabDimensions(thickness=thickness, area=area),
        properties=SlabProperties(slab_kind=kind, outline=rel, holes=hole_rel),
    )


def _wall_thickness_at(ctx: _Context, level: int, x: float, y0: float, y1: float) -> float:
    """Thickness of the wall along x = const covering [y0, y1] (0 if none)."""
    for w in ctx.walls:
        if w.level == level and not w.horizontal and abs(w.coord - x) < 1e-6:
            lo, hi = sorted((w.start[1], w.end[1]))
            if lo < (y0 + y1) / 2 < hi:
                return w.thickness
    return 0.0


def _slabs(ctx: _Context, levels: list[Level]) -> list[Element]:
    sk, cfg = ctx.plan.skeleton, ctx.config
    half = cfg.exterior_wall_thickness / 2
    house = Rect(-half, -half, rnd(sk.W + half), rnd(sk.D + half))
    out: list[Element] = []
    ground = [house]
    if ctx.plan.garage is not None:
        g = ctx.plan.garage
        ground.append(Rect(rnd(g.x0 - half), -half, rnd(g.x1 + half), rnd(g.y1 + half)))
    out.append(
        _slab(
            ctx,
            "slab:ground",
            "Ground slab",
            levels[0].id,
            _union_outline(ground),
            [],
            cfg.ground_slab_thickness,
            SlabKind.GROUND,
        )
    )
    for lv in range(1, sk.storeys):
        holes = []
        void = ctx.plan.levels[lv].get(f"void_{lv}")
        if void is not None:
            r = void.rects[0]
            t_w = _wall_thickness_at(ctx, lv, r.x0, r.y0, r.y1) / 2
            t_e = _wall_thickness_at(ctx, lv, r.x1, r.y0, r.y1) / 2
            y0 = r.y0 + (half if r.y0 < 1e-6 else 0.0)  # south facade inner face
            level = ctx.plan.levels[lv]
            top_open = any(o.covers(Segment("h", r.y1, r.x0, r.x1)) for o in level.open_edges)
            y1 = r.y1 - (0.0 if top_open else cfg.interior_wall_thickness / 2)
            x0, x1 = rnd(r.x0 + t_w), rnd(r.x1 - t_e)
            holes.append([(x0, rnd(y0)), (x1, rnd(y0)), (x1, rnd(y1)), (x0, rnd(y1))])
        outline = [
            (house.x0, house.y0),
            (house.x1, house.y0),
            (house.x1, house.y1),
            (house.x0, house.y1),
        ]
        out.append(
            _slab(
                ctx,
                f"slab:L{lv}",
                f"Floor {lv + 1} slab",
                levels[lv].id,
                outline,
                holes,
                cfg.floor_slab_thickness,
                SlabKind.FLOOR,
            )
        )
    for att in ctx.plan.attachments:
        r = att.rect
        if att.kind == "balcony":
            y0, y1 = (rnd(r.y0 + half), r.y1) if att.side == "north" else (r.y0, rnd(r.y1 - half))
            thickness, kind, key, name = (
                cfg.balcony_slab_thickness,
                SlabKind.BALCONY,
                f"slab:balcony_{att.index}",
                "Balcony slab",
            )
        else:
            y0, y1 = rnd(r.y0 + half), r.y1
            thickness, kind, key, name = (
                cfg.terrace_slab_thickness,
                SlabKind.GROUND,
                "slab:terrace",
                "Terrace slab",
            )
        outline = [(r.x0, y0), (r.x1, y0), (r.x1, y1), (r.x0, y1)]
        out.append(_slab(ctx, key, name, levels[att.level].id, outline, [], thickness, kind))
    return out


def _stairs_and_railings(
    ctx: _Context, levels: list[Level], rooms: dict[tuple[int, str], Room]
) -> list[Element]:
    sk, cfg, stair = ctx.plan.skeleton, ctx.config, ctx.plan.stair
    out: list[Element] = []
    f2f = ctx.spec.targets.floor_to_floor_height_m
    rail_h = max(cfg.stair_railing_height, ctx.profile.railings.min_height_m)
    if stair is not None:
        for k in range(sk.storeys - 1):
            x0, x1 = sk.lane(k)
            xm = (x0 + x1) / 2
            w = stair.width
            if k % 2 == 0:
                pos, yaw = (rnd(xm + w / 2), rnd(sk.Ds - stair.run)), HALF_PI
            else:
                pos, yaw = (rnd(xm - w / 2), sk.Ds), -HALF_PI
            host = rooms.get((k, "hall_0" if k == 0 else f"stair_{k}"))
            rels = [_rel(RelationshipKind.LOCATED_IN, host.id)] if host else []
            out.append(
                Stair(
                    id=ctx.ids(f"stair:flight_{k}"),
                    name=f"Stair {k + 1}-{k + 2}",
                    layer=Layer.STRUCTURE,
                    level_id=levels[k].id,
                    position=Vec3(x=pos[0], y=pos[1], z=0),
                    rotation=Rotation(z=yaw),
                    material_id="wood",
                    relationships=rels,
                    origin=Origin.GENERATED,
                    semantic_key=f"stair:flight_{k}",
                    dimensions=StairDimensions(width=w, run_length=stair.run, rise_total=f2f),
                    properties=StairProperties(
                        stair_type=StairType.STRAIGHT,
                        risers=stair.risers,
                        riser_height=stair.riser,
                        tread_depth=stair.tread,
                        from_level_id=levels[k].id,
                        to_level_id=levels[k + 1].id,
                    ),
                )
            )
            if k == 0:  # open side of the first flight faces the hall
                edge_x = xm - w / 2 + 0.03 if sk.hall_side == "west" else xm + w / 2 - 0.03
                out.append(
                    _railing(
                        ctx,
                        "railing:stair_0",
                        "Stair railing",
                        levels[0].id,
                        (rnd(edge_x), rnd(sk.Ds - stair.run), rnd(stair.riser)),
                        HALF_PI,
                        stair.run,
                        rail_h,
                        rnd(f2f - stair.riser),
                        RailingKind.BARS,
                        host,
                    )
                )
    height = max(cfg.balcony_railing_height, ctx.profile.railings.balcony_min_height_m)
    half = cfg.exterior_wall_thickness / 2
    for att in ctx.plan.attachments:
        if att.kind != "balcony":
            continue
        r = att.rect
        host = rooms.get((att.level, f"balcony_{att.index}"))
        lvl = levels[att.level].id
        inset = 0.05
        depth = r.h - half - inset
        if att.side == "north":
            parts = [
                ("w", (r.x0 + inset, r.y0 + half, 0.0), HALF_PI, depth),
                ("n", (r.x0 + inset, r.y1 - inset, 0.0), 0.0, r.w - 2 * inset),
                ("e", (r.x1 - inset, r.y1 - inset, 0.0), -HALF_PI, depth),
            ]
        else:
            parts = [
                ("w", (r.x0 + inset, r.y1 - half, 0.0), -HALF_PI, depth),
                ("s", (r.x0 + inset, r.y0 + inset, 0.0), 0.0, r.w - 2 * inset),
                ("e", (r.x1 - inset, r.y0 + inset, 0.0), HALF_PI, depth),
            ]
        for tag, start, yaw, length in parts:
            out.append(
                _railing(
                    ctx,
                    f"railing:balcony_{att.index}:{tag}",
                    f"Balcony railing {tag.upper()}",
                    lvl,
                    (rnd(start[0]), rnd(start[1]), 0.0),
                    yaw,
                    rnd(length),
                    height,
                    0.0,
                    RailingKind.GLASS,
                    host,
                )
            )
    return out


def _railing(
    ctx: _Context,
    key: str,
    name: str,
    level: uuid.UUID,
    start: tuple[float, float, float],
    yaw: float,
    length: float,
    height: float,
    rise: float,
    kind: RailingKind,
    room: Room | None,
) -> Railing:
    return Railing(
        id=ctx.ids(key),
        name=name,
        layer=Layer.ARCHITECTURE,
        level_id=level,
        position=Vec3(x=start[0], y=start[1], z=start[2]),
        rotation=Rotation(z=yaw),
        material_id="metal",
        relationships=[_rel(RelationshipKind.LOCATED_IN, room.id)] if room else [],
        origin=Origin.GENERATED,
        semantic_key=key,
        dimensions=RailingDimensions(length=length, height=height),
        properties=RailingProperties(
            railing_kind=kind, rise=rise, post_spacing=ctx.config.railing_post_spacing
        ),
    )


def _roofs(ctx: _Context, levels: list[Level]) -> list[Element]:
    sk, cfg = ctx.plan.skeleton, ctx.config
    half = cfg.exterior_wall_thickness / 2
    wall_h = ctx.wall_height
    roof_spec = ctx.spec.style.roof
    out: list[Element] = []
    top = levels[-1].id
    t = cfg.roof_thickness
    if roof_spec.type == RoofType.FLAT:
        outline = [
            (-half, -half),
            (sk.W + half, -half),
            (sk.W + half, sk.D + half),
            (-half, sk.D + half),
        ]
        out.append(
            _roof(
                ctx,
                "roof:main",
                "Roof",
                top,
                outline,
                rnd(wall_h + t),
                RoofType.FLAT,
                0.0,
                0.0,
                "x",
                cfg.parapet_height,
            )
        )
    else:
        pitch = roof_spec.pitch_deg or cfg.roof_pitch_deg
        over = cfg.roof_overhang
        e = half + over
        outline = [(-e, -e), (sk.W + e, -e), (sk.W + e, sk.D + e), (-e, sk.D + e)]
        eave_z = rnd(wall_h - over * math.tan(math.radians(pitch)) + t)
        out.append(
            _roof(
                ctx,
                "roof:main",
                "Roof",
                top,
                outline,
                eave_z,
                roof_spec.type,
                pitch,
                over,
                "x" if sk.W >= sk.D else "y",
                0.0,
            )
        )
    if ctx.plan.garage is not None:
        g = ctx.plan.garage
        x0, x1 = (g.x0 - half, -half) if sk.garage_side == "west" else (sk.W + half, g.x1 + half)
        outline = [(x0, -half), (x1, -half), (x1, g.y1 + half), (x0, g.y1 + half)]
        out.append(
            _roof(
                ctx,
                "roof:garage",
                "Garage roof",
                levels[0].id,
                outline,
                rnd(wall_h + t),
                RoofType.FLAT,
                0.0,
                0.0,
                "x",
                cfg.parapet_height * 0.7,
            )
        )
    return out


def _roof(
    ctx: _Context,
    key: str,
    name: str,
    level: uuid.UUID,
    outline: list[Point],
    z: float,
    roof_type: RoofType,
    pitch: float,
    overhang: float,
    ridge: Literal["x", "y"],
    parapet: float,
) -> Roof:
    pts = [(rnd(x), rnd(y)) for x, y in outline]
    (ox, oy), rel = _polygon_rel(pts)
    return Roof(
        id=ctx.ids(key),
        name=name,
        layer=Layer.ARCHITECTURE,
        level_id=level,
        position=Vec3(x=ox, y=oy, z=z),
        rotation=Rotation(),
        material_id="roof",
        relationships=[],
        origin=Origin.GENERATED,
        semantic_key=key,
        dimensions=RoofDimensions(thickness=ctx.config.roof_thickness, overhang=overhang),
        properties=RoofProperties(
            roof_type=roof_type,
            outline=rel,
            pitch_deg=pitch,
            ridge_axis=ridge,
            parapet_height=rnd(parapet),
        ),
    )
