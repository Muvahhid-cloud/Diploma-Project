"""Plain data structures shared by the planner (abstract plan) and the builder (elements).

Plan coordinates are level-plan meters on wall centerlines: x east, y north, street on the south
(y = 0). The house footprint is the rectangle [0, W] x [0, D]; an attached garage sits outside it
on the ground floor, balconies and terraces outside it on the garden or street side.
"""

import math
from dataclasses import dataclass, field
from typing import Literal

from app.modules.building.enums import RoomType, Zone
from app.modules.layout.program import RoomRequest

EPS = 1e-6


def rnd(v: float) -> float:
    """Round to 1 mm (all plan coordinates)."""
    return round(v, 3) + 0.0


def snap(v: float, grid: float) -> float:
    return rnd(round(v / grid) * grid)


def snap_up(v: float, grid: float) -> float:
    return rnd(math.ceil(v / grid - 1e-9) * grid)


def snap_down(v: float, grid: float) -> float:
    return rnd(math.floor(v / grid + 1e-9) * grid)


@dataclass(frozen=True)
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def w(self) -> float:
        return self.x1 - self.x0

    @property
    def h(self) -> float:
        return self.y1 - self.y0

    @property
    def area(self) -> float:
        return self.w * self.h

    def contains(self, x: float, y: float) -> bool:
        return self.x0 - EPS <= x <= self.x1 + EPS and self.y0 - EPS <= y <= self.y1 + EPS

    def strictly_contains(self, x: float, y: float) -> bool:
        return self.x0 + EPS < x < self.x1 - EPS and self.y0 + EPS < y < self.y1 - EPS


@dataclass(frozen=True)
class StairDesign:
    risers: int
    riser: float
    tread: float
    run: float
    width: float
    lane_width: float  # centerline width of one stair lane in the core


@dataclass(frozen=True)
class Skeleton:
    """Global dimensions shared by every level of a candidate."""

    W: float
    D: float
    Ds: float  # south (street) band depth
    C: float  # corridor band depth
    storeys: int
    core_x0: float  # stair core [core_x0, core_x0 + lanes * lane_width]
    lanes: int
    lane_width: float
    hall_x0: float  # ground-floor entrance hall part (without the core)
    hall_x1: float
    hall_side: Literal["west", "east"]  # side of the hall part relative to the core
    garage_side: Literal["west", "east"] | None

    @property
    def Dn(self) -> float:  # noqa: N802 - plan dimension name
        return rnd(self.D - self.Ds - self.C)

    @property
    def core_x1(self) -> float:
        return rnd(self.core_x0 + self.lanes * self.lane_width)

    @property
    def group_x0(self) -> float:  # hall part + core
        return min(self.core_x0, self.hall_x0)

    @property
    def group_x1(self) -> float:
        return max(self.core_x1, self.hall_x1)

    def lane(self, flight: int) -> tuple[float, float]:
        """Centerline x-range of the lane used by `flight` (0 = ground -> first floor).

        Flight 0 takes the lane farthest from the hall part so its open side faces the hall.
        """
        order = list(range(self.lanes))
        slot = order.index(flight)
        if self.hall_side == "west":  # hall | lane k-1 ... lane 0 | (east)
            slot = self.lanes - 1 - slot
        x0 = rnd(self.core_x0 + slot * self.lane_width)
        return x0, rnd(x0 + self.lane_width)


Side = Literal["north", "south"]


@dataclass(frozen=True)
class Strip:
    name: Literal["N", "SL", "SR"]
    x0: float
    x1: float
    y0: float
    y1: float
    side: Side  # facade side of the strip

    @property
    def length(self) -> float:
        return rnd(self.x1 - self.x0)

    @property
    def depth(self) -> float:
        return rnd(self.y1 - self.y0)


ColumnKind = Literal["main", "tuck", "full"]


@dataclass
class Column:
    kind: ColumnKind
    room: RoomRequest
    width: float
    depth: float  # tucks: depth from the corridor edge; others: the strip depth
    owner: RoomRequest | None = None  # tucks: the room that takes the facade-side remainder


@dataclass
class StripLayout:
    strip: Strip
    columns: list[Column]


@dataclass
class LevelLayout:
    index: int
    strips: list[StripLayout]
    merged_strips: list[Strip] = field(default_factory=list)  # empty strips given to circulation


@dataclass
class Candidate:
    order: int
    skeleton: Skeleton
    levels: list[LevelLayout]
    score: float
    areas: dict[str, float]  # room key -> area


RegionKind = Literal["room", "void"]


@dataclass
class Region:
    key: str  # semantic suffix: the room element's semantic key is f"room:{key}"
    kind: RegionKind
    rects: list[Rect]
    level: int
    name: str
    room_type: RoomType | None = None
    zone: Zone | None = None
    request: RoomRequest | None = None
    inside: bool = True  # inside the house footprint (interior walls are derived for these)

    @property
    def area(self) -> float:
        return sum(r.area for r in self.rects)

    def contains(self, x: float, y: float) -> bool:
        return any(r.contains(x, y) for r in self.rects)

    def strictly_contains(self, x: float, y: float) -> bool:
        return any(r.strictly_contains(x, y) for r in self.rects)


@dataclass(frozen=True)
class Segment:
    """Axis-aligned plan segment: horizontal (y = const) or vertical (x = const)."""

    orientation: Literal["h", "v"]
    coord: float
    a0: float
    a1: float

    @property
    def length(self) -> float:
        return self.a1 - self.a0

    def covers(self, other: "Segment") -> bool:
        return (
            self.orientation == other.orientation
            and abs(self.coord - other.coord) < 1e-4
            and self.a0 - 1e-4 <= other.a0
            and other.a1 <= self.a1 + 1e-4
        )
