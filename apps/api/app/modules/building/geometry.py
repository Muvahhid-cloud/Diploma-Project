"""Pure plan-geometry helpers used by validation (and later by layout/quantities)."""

import math
from collections.abc import Sequence

from app.modules.building.elements import Wall
from app.modules.building.primitives import EPS, Rotation, Vec2, Vec3

Point = tuple[float, float]


def to_absolute(points: Sequence[Vec2], position: Vec3, rotation: Rotation) -> list[Point]:
    """Level-plan coordinates of an element-relative polygon (rotation.z about position)."""
    c, s = math.cos(rotation.z), math.sin(rotation.z)
    return [(position.x + p.x * c - p.y * s, position.y + p.x * s + p.y * c) for p in points]


def signed_area(points: Sequence[Point]) -> float:
    """Shoelace formula; positive for counter-clockwise polygons."""
    n = len(points)
    return 0.5 * sum(
        points[i][0] * points[(i + 1) % n][1] - points[(i + 1) % n][0] * points[i][1]
        for i in range(n)
    )


def perimeter(points: Sequence[Point]) -> float:
    n = len(points)
    return sum(math.dist(points[i], points[(i + 1) % n]) for i in range(n))


def is_rectilinear(points: Sequence[Point]) -> bool:
    n = len(points)
    for i in range(n):
        (x0, y0), (x1, y1) = points[i], points[(i + 1) % n]
        if abs(x0 - x1) > EPS and abs(y0 - y1) > EPS:
            return False
    return True


def is_axis_aligned_rectangle(points: Sequence[Point]) -> bool:
    return len(points) == 4 and is_rectilinear(points)


def wall_axis(wall: Wall) -> tuple[Point, Point]:
    """Start and end of a wall's axis in level-plan coordinates."""
    start = (wall.position.x, wall.position.y)
    angle = wall.rotation.z
    end = (
        start[0] + wall.dimensions.length * math.cos(angle),
        start[1] + wall.dimensions.length * math.sin(angle),
    )
    return start, end


def segment_overlap_length(a: tuple[Point, Point], b: tuple[Point, Point]) -> float:
    """Length of the collinear overlap of two segments (0 if not collinear)."""
    (ax0, ay0), (ax1, ay1) = a
    dx, dy = ax1 - ax0, ay1 - ay0
    length = math.hypot(dx, dy)
    if length < EPS:
        return 0.0
    ux, uy = dx / length, dy / length
    for px, py in b:  # both endpoints of b must lie on a's supporting line
        if abs((px - ax0) * uy - (py - ay0) * ux) > EPS:
            return 0.0
    t0 = (b[0][0] - ax0) * ux + (b[0][1] - ay0) * uy
    t1 = (b[1][0] - ax0) * ux + (b[1][1] - ay0) * uy
    lo, hi = max(0.0, min(t0, t1)), min(length, max(t0, t1))
    return max(0.0, hi - lo)


def polygon_edges(points: Sequence[Point]) -> list[tuple[Point, Point]]:
    n = len(points)
    return [(points[i], points[(i + 1) % n]) for i in range(n)]
