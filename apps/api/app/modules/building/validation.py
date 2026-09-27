"""BuildingModel invariants (docs/building-model.md §4).

Pydantic already enforces types, enums, ranges and finiteness. This module checks the
cross-element rules. Errors make a model invalid; warnings are reported to the user.
"""

import itertools
import uuid
from collections import defaultdict
from collections.abc import Iterable
from typing import Literal

from shapely import Point as ShapelyPoint
from shapely import Polygon as ShapelyPolygon
from shapely import unary_union

from app.modules.building.elements import (
    Door,
    Furniture,
    Railing,
    Roof,
    Room,
    Slab,
    Stair,
    Wall,
    Window,
)
from app.modules.building.enums import DoorKind, RelationshipKind, RoofType, RoomType
from app.modules.building.geometry import (
    is_axis_aligned_rectangle,
    is_rectilinear,
    perimeter,
    signed_area,
    to_absolute,
    wall_axis,
)
from app.modules.building.model import BuildingModel, Level
from app.modules.building.primitives import EPS, Frozen

HABITABLE_ROOMS = frozenset(
    {
        RoomType.LIVING,
        RoomType.DINING,
        RoomType.KITCHEN,
        RoomType.OPEN_KITCHEN_LIVING,
        RoomType.BEDROOM,
        RoomType.STUDY,
    }
)
AREA_TOLERANCE = 0.01  # m², matches area rounding
OVERLAP_TOLERANCE = 1e-3  # m²


class ModelIssue(Frozen):
    severity: Literal["error", "warning"]
    code: str
    path: str  # JSON pointer into the model document
    message: str
    element_id: uuid.UUID | None


class _Checker:
    def __init__(self, model: BuildingModel, material_ids: frozenset[str] | None) -> None:
        self.model = model
        self.material_ids = material_ids
        self.issues: list[ModelIssue] = []
        self.levels: dict[uuid.UUID, Level] = {lvl.id: lvl for lvl in model.levels}
        self.index = {el.id: i for i, el in enumerate(model.elements)}
        self.by_id = {el.id: el for el in model.elements}

    def add(
        self,
        severity: Literal["error", "warning"],
        code: str,
        path: str,
        message: str,
        element_id: uuid.UUID | None = None,
    ) -> None:
        self.issues.append(
            ModelIssue(
                severity=severity, code=code, path=path, message=message, element_id=element_id
            )
        )

    def path(self, element_id: uuid.UUID, suffix: str = "") -> str:
        return f"/elements/{self.index[element_id]}{suffix}"

    # --- checks ---------------------------------------------------------------------------

    def ids(self) -> None:
        seen: set[uuid.UUID] = {self.model.id}
        for i, lvl in enumerate(self.model.levels):
            if lvl.id in seen:
                self.add("error", "DUPLICATE_ID", f"/levels/{i}/id", f"Duplicate id {lvl.id}")
            seen.add(lvl.id)
        indices = [lvl.index for lvl in self.model.levels]
        if sorted(indices) != list(range(len(indices))):
            self.add("error", "LEVEL_INDEX", "/levels", "Level indices must be 0..n-1")
        for i, el in enumerate(self.model.elements):
            if el.id in seen:
                self.add("error", "DUPLICATE_ID", f"/elements/{i}/id", f"Duplicate id {el.id}")
            seen.add(el.id)
        keys = [el.semantic_key for el in self.model.elements]
        for key in {k for k in keys if keys.count(k) > 1}:
            self.add("error", "DUPLICATE_SEMANTIC_KEY", "/elements", f"Duplicate key {key!r}")

    def references(self) -> None:
        for el in self.model.elements:
            if el.level_id is None or el.level_id not in self.levels:
                self.add(
                    "error",
                    "UNKNOWN_LEVEL",
                    self.path(el.id, "/level_id"),
                    f"{el.name}: level {el.level_id} does not exist",
                    el.id,
                )
            for j, rel in enumerate(el.relationships):
                if rel.target_id not in self.by_id:
                    self.add(
                        "error",
                        "DANGLING_RELATIONSHIP",
                        self.path(el.id, f"/relationships/{j}"),
                        f"{el.name}: {rel.kind} target {rel.target_id} does not exist",
                        el.id,
                    )

    def materials(self) -> None:
        if self.material_ids is None:
            return
        for el in self.model.elements:
            refs: list[tuple[str, str | None]] = [("/material_id", el.material_id)]
            props = el.properties.model_dump()
            refs += [
                (f"/properties/{k}", v)
                for k, v in props.items()
                if k.endswith("material_id") or k.startswith("finish_")
            ]
            for suffix, mid in refs:
                if mid is not None and mid not in self.material_ids:
                    self.add(
                        "error",
                        "UNKNOWN_MATERIAL",
                        self.path(el.id, suffix),
                        f"{el.name}: unknown material {mid!r}",
                        el.id,
                    )

    def walls_and_openings(self) -> None:
        openings: dict[uuid.UUID, list[Door | Window]] = defaultdict(list)
        for el in self.model.elements:
            if isinstance(el, Wall):
                lvl = self.levels.get(el.level_id) if el.level_id else None
                if lvl and el.dimensions.height > lvl.height + EPS:
                    self.add(
                        "error",
                        "WALL_TOO_TALL",
                        self.path(el.id, "/dimensions/height"),
                        f"{el.name} is taller than its level",
                        el.id,
                    )
            if not isinstance(el, Door | Window):
                continue
            hosts = [r for r in el.relationships if r.kind == RelationshipKind.HOSTED_BY]
            host = self.by_id.get(hosts[0].target_id) if len(hosts) == 1 else None
            if not isinstance(host, Wall):
                self.add(
                    "error",
                    "OPENING_HOST",
                    self.path(el.id, "/relationships"),
                    f"{el.name} must be hosted by exactly one wall",
                    el.id,
                )
                continue
            if host.level_id != el.level_id:
                self.add(
                    "error",
                    "OPENING_LEVEL",
                    self.path(el.id, "/level_id"),
                    f"{el.name} is not on its host wall's level",
                    el.id,
                )
            x, z = el.position.x, el.position.z
            w, h = el.dimensions.width, el.dimensions.height
            if x < -EPS or x + w > host.dimensions.length + EPS or z < -EPS:
                self.add(
                    "error",
                    "OPENING_OUTSIDE_WALL",
                    self.path(el.id, "/position"),
                    f"{el.name} extends beyond {host.name} along its length",
                    el.id,
                )
            if z + h > host.dimensions.height + EPS:
                self.add(
                    "error",
                    "OPENING_TOO_TALL",
                    self.path(el.id, "/dimensions/height"),
                    f"{el.name} is taller than {host.name}",
                    el.id,
                )
            openings[host.id].append(el)
        for wall_id, items in openings.items():
            items.sort(key=lambda o: (o.position.x, str(o.id)))
            for a, b in itertools.pairwise(items):
                if a.position.x + a.dimensions.width > b.position.x + EPS:
                    self.add(
                        "error",
                        "OPENINGS_OVERLAP",
                        self.path(b.id, "/position"),
                        f"{a.name} and {b.name} overlap in {self.by_id[wall_id].name}",
                        b.id,
                    )

    def polygons(self) -> None:
        rooms_by_level: dict[uuid.UUID, list[tuple[Room, ShapelyPolygon]]] = defaultdict(list)
        slabs_by_level: dict[uuid.UUID, list[ShapelyPolygon]] = defaultdict(list)
        for el in self.model.elements:
            if isinstance(el, Room):
                pts = to_absolute(el.properties.boundary, el.position, el.rotation)
                if not self._polygon_ok(el.id, "/properties/boundary", pts, rectilinear=True):
                    continue
                area, perim = signed_area(pts), perimeter(pts)
                if abs(area - el.dimensions.area) > AREA_TOLERANCE:
                    self.add(
                        "error",
                        "ROOM_AREA_MISMATCH",
                        self.path(el.id, "/dimensions/area"),
                        f"{el.name}: area {el.dimensions.area} != boundary area {area:.2f}",
                        el.id,
                    )
                if abs(perim - el.dimensions.perimeter) > 0.001 + EPS:
                    self.add(
                        "error",
                        "ROOM_PERIMETER_MISMATCH",
                        self.path(el.id, "/dimensions"),
                        f"{el.name}: perimeter does not match boundary",
                        el.id,
                    )
                if el.level_id:
                    rooms_by_level[el.level_id].append((el, ShapelyPolygon(pts)))
            elif isinstance(el, Slab):
                outline = to_absolute(el.properties.outline, el.position, el.rotation)
                if not self._polygon_ok(el.id, "/properties/outline", outline, rectilinear=False):
                    continue
                holes = [to_absolute(h, el.position, el.rotation) for h in el.properties.holes]
                poly = ShapelyPolygon(outline, holes)
                if not poly.is_valid:
                    self.add(
                        "error",
                        "SLAB_INVALID",
                        self.path(el.id, "/properties"),
                        f"{el.name}: holes must lie inside the outline",
                        el.id,
                    )
                    continue
                if abs(poly.area - el.dimensions.area) > AREA_TOLERANCE:
                    self.add(
                        "error",
                        "SLAB_AREA_MISMATCH",
                        self.path(el.id, "/dimensions/area"),
                        f"{el.name}: area {el.dimensions.area} != {poly.area:.2f}",
                        el.id,
                    )
                if el.level_id:
                    slabs_by_level[el.level_id].append(poly)
            elif isinstance(el, Roof):
                pts = to_absolute(el.properties.outline, el.position, el.rotation)
                pitched = el.properties.roof_type != RoofType.FLAT
                if pitched and not is_axis_aligned_rectangle(pts):
                    self.add(
                        "error",
                        "ROOF_OUTLINE",
                        self.path(el.id, "/properties/outline"),
                        f"{el.name}: pitched roofs require a rectangular outline in v1",
                        el.id,
                    )
                self._polygon_ok(el.id, "/properties/outline", pts, rectilinear=True)

        for level_id, rooms in rooms_by_level.items():
            for i, (a, pa) in enumerate(rooms):
                for b, pb in rooms[i + 1 :]:
                    if pa.intersection(pb).area > OVERLAP_TOLERANCE:
                        self.add(
                            "error",
                            "ROOMS_OVERLAP",
                            self.path(b.id, "/properties/boundary"),
                            f"{a.name} and {b.name} overlap",
                            b.id,
                        )
            covered = unary_union(slabs_by_level.get(level_id, []))
            for room, poly in rooms:
                if poly.difference(covered).area > OVERLAP_TOLERANCE:
                    self.add(
                        "warning",
                        "ROOM_NOT_ON_SLAB",
                        self.path(room.id),
                        f"{room.name} is not fully supported by a slab",
                        room.id,
                    )
        self._rooms_have_windows(rooms_by_level)
        self._furniture_in_rooms(rooms_by_level)

    def _polygon_ok(
        self, eid: uuid.UUID, suffix: str, pts: list[tuple[float, float]], *, rectilinear: bool
    ) -> bool:
        if signed_area(pts) <= EPS:
            self.add(
                "error",
                "POLYGON_ORIENTATION",
                self.path(eid, suffix),
                "Polygons must be counter-clockwise with positive area",
                eid,
            )
            return False
        if rectilinear and not is_rectilinear(pts):
            self.add(
                "error",
                "POLYGON_NOT_RECTILINEAR",
                self.path(eid, suffix),
                "Polygons must be rectilinear (axis-aligned edges) in v1",
                eid,
            )
            return False
        if not ShapelyPolygon(pts).is_valid:
            self.add("error", "POLYGON_INVALID", self.path(eid, suffix), "Self-intersecting", eid)
            return False
        return True

    def _rooms_have_windows(
        self, rooms_by_level: dict[uuid.UUID, list[tuple[Room, ShapelyPolygon]]]
    ) -> None:
        """A room is lit if a window (or glazed sliding door) sits on its own boundary."""
        lit_rooms: set[uuid.UUID] = set()
        for el in self.model.elements:
            glazed = isinstance(el, Window) or (
                isinstance(el, Door) and el.properties.door_kind == DoorKind.SLIDING
            )
            if not glazed or not isinstance(el, Window | Door):
                continue
            hosts = [r.target_id for r in el.relationships if r.kind == RelationshipKind.HOSTED_BY]
            host = self.by_id.get(hosts[0]) if hosts else None
            if not isinstance(host, Wall) or host.level_id is None:
                continue
            (sx, sy), (ex, ey) = wall_axis(host)
            t = (el.position.x + el.dimensions.width / 2) / host.dimensions.length
            mid = ShapelyPoint(sx + (ex - sx) * t, sy + (ey - sy) * t)
            lit_rooms.update(
                room.id
                for room, poly in rooms_by_level[host.level_id]
                if poly.exterior.distance(mid) < EPS
            )
        for el in self.model.elements:
            if (
                isinstance(el, Room)
                and el.properties.room_type in HABITABLE_ROOMS
                and el.id not in lit_rooms
            ):
                self.add(
                    "warning",
                    "HABITABLE_ROOM_WITHOUT_WINDOW",
                    self.path(el.id),
                    f"{el.name} has no window",
                    el.id,
                )

    def _furniture_in_rooms(
        self, rooms_by_level: dict[uuid.UUID, list[tuple[Room, ShapelyPolygon]]]
    ) -> None:
        for el in self.model.elements:
            if not isinstance(el, Furniture) or el.level_id is None:
                continue
            p = ShapelyPoint(el.position.x, el.position.y)
            if not any(poly.buffer(EPS).contains(p) for _, poly in rooms_by_level[el.level_id]):
                self.add(
                    "warning",
                    "FURNITURE_OUTSIDE_ROOMS",
                    self.path(el.id, "/position"),
                    f"{el.name} is not inside any room",
                    el.id,
                )

    def stairs(self) -> None:
        for el in self.model.elements:
            if not isinstance(el, Stair):
                continue
            p, d = el.properties, el.dimensions
            # riser_height is stored to 1 mm, so allow 0.5 mm rounding per riser.
            if abs(p.risers * p.riser_height - d.rise_total) > p.risers * 0.0005 + EPS:
                self.add(
                    "error",
                    "STAIR_RISE",
                    self.path(el.id, "/properties/riser_height"),
                    f"{el.name}: risers x riser_height != rise_total",
                    el.id,
                )
            if abs((p.risers - 1) * p.tread_depth - d.run_length) > p.risers * 0.0005 + EPS:
                self.add(
                    "error",
                    "STAIR_RUN",
                    self.path(el.id, "/properties/tread_depth"),
                    f"{el.name}: (risers - 1) x tread_depth != run_length",
                    el.id,
                )
            lo, hi = self.levels.get(p.from_level_id), self.levels.get(p.to_level_id)
            if lo is None or hi is None:
                self.add(
                    "error",
                    "STAIR_LEVELS",
                    self.path(el.id, "/properties"),
                    f"{el.name}: unknown from/to level",
                    el.id,
                )
                continue
            if el.level_id != lo.id or hi.index != lo.index + 1:
                self.add(
                    "error",
                    "STAIR_LEVELS",
                    self.path(el.id, "/properties"),
                    f"{el.name} must start on its own level and reach the next one",
                    el.id,
                )
            if abs((hi.elevation - lo.elevation) - d.rise_total) > 0.005:
                self.add(
                    "error",
                    "STAIR_RISE",
                    self.path(el.id, "/dimensions/rise_total"),
                    f"{el.name}: rise_total does not match the level difference",
                    el.id,
                )

    def railings(self) -> None:
        for el in self.model.elements:
            if isinstance(el, Railing) and abs(el.properties.rise) > el.dimensions.length:
                self.add(
                    "error",
                    "RAILING_SLOPE",
                    self.path(el.id, "/properties/rise"),
                    f"{el.name}: rise is steeper than 45 degrees",
                    el.id,
                )


def validate_model(
    model: BuildingModel, *, material_ids: Iterable[str] | None = None
) -> list[ModelIssue]:
    """Return all invariant violations. `material_ids` (if given) enables material checks."""
    checker = _Checker(model, frozenset(material_ids) if material_ids is not None else None)
    checker.ids()
    checker.references()
    checker.materials()
    checker.walls_and_openings()
    checker.polygons()
    checker.stairs()
    checker.railings()
    return checker.issues


def errors(issues: Iterable[ModelIssue]) -> list[ModelIssue]:
    return [i for i in issues if i.severity == "error"]
