"""Cheap derived statistics of a BuildingModel (for version lists and generation summaries).

Derived data: always recomputable from the model, never edited directly.
"""

from shapely import LineString, unary_union
from shapely.ops import polygonize

from app.modules.building.elements import Door, Room, Wall, Window
from app.modules.building.enums import RoomType, WallKind, Zone
from app.modules.building.geometry import wall_axis
from app.modules.building.model import BuildingModel
from app.modules.building.primitives import Frozen

CIRCULATION = frozenset({RoomType.CORRIDOR, RoomType.HALL, RoomType.ENTRANCE, RoomType.STAIRCASE})


class ModelSummary(Frozen):
    storeys: int
    # Area enclosed by the exterior wall centerlines of each level, summed (garage excluded:
    # its walls stop at the house's outer face and do not close a loop).
    gross_floor_area_m2: float
    net_floor_area_m2: float  # rooms, excluding circulation, garage and outdoor rooms
    rooms: int  # rooms excluding circulation, garage and outdoor rooms
    bedrooms: int
    bathrooms: int  # bathrooms + en-suites
    wcs: int
    garage: bool
    balconies: int
    terraces: int
    walls: int
    doors: int
    windows: int
    elements: int


def summarize(model: BuildingModel) -> ModelSummary:
    gross = 0.0
    for level in model.levels:
        axes = [
            tuple((round(x, 3), round(y, 3)) for x, y in wall_axis(el))  # 1 mm: close the loops
            for el in model.elements
            if isinstance(el, Wall)
            and el.level_id == level.id
            and el.properties.wall_kind == WallKind.EXTERIOR
        ]
        if axes:
            noded = unary_union([LineString(axis) for axis in axes])  # split at crossings
            gross += sum(p.area for p in polygonize(getattr(noded, "geoms", [noded])))
    rooms = [el for el in model.elements if isinstance(el, Room)]
    types = [r.properties.room_type for r in rooms]
    main = [
        r
        for r in rooms
        if r.properties.room_type not in CIRCULATION
        and r.properties.room_type != RoomType.GARAGE
        and r.properties.zone != Zone.EXTERIOR
    ]
    return ModelSummary(
        storeys=len(model.levels),
        gross_floor_area_m2=round(gross, 1),
        net_floor_area_m2=round(sum(r.dimensions.area for r in main), 1),
        rooms=len(main),
        bedrooms=types.count(RoomType.BEDROOM),
        bathrooms=types.count(RoomType.BATHROOM) + types.count(RoomType.EN_SUITE),
        wcs=types.count(RoomType.WC),
        garage=RoomType.GARAGE in types,
        balconies=types.count(RoomType.BALCONY),
        terraces=types.count(RoomType.TERRACE),
        walls=sum(isinstance(el, Wall) for el in model.elements),
        doors=sum(isinstance(el, Door) for el in model.elements),
        windows=sum(isinstance(el, Window) for el in model.elements),
        elements=len(model.elements),
    )
