# Building Model

Status: **Implemented for Phase 1 (v0.3)** · Canonical code: `apps/api/app/modules/building/` · Generated: `packages/schema/`

There are **two** schemas, deliberately separated:

| | `BuildingSpecification` | `BuildingModel` |
|---|---|---|
| Represents | What the client *wants* (intent, program) | What *is* designed (resolved elements) |
| Produced by | AI (or a form) | Layout engine + MEP generator + operations |
| Size | ~1–10 KB | ~0.5–3 MB |
| Coordinates | None | Everything positioned |
| Edited by | AI / user form, then re-layout | Typed operations |
| Source of truth for | Program & requirements | **Geometry, quantities, cost, rendering** |

After first generation, the **model** is the source of truth. The spec is kept as provenance and as input for full regeneration.

---

## 1. Conventions

| Convention | Value |
|---|---|
| Units | SI. Lengths **meters**, areas m², volumes m³, angles **radians**, money `Decimal` + ISO-4217 currency |
| Coordinate system | Right-handed, **Z-up**. Plan in X (east) / Y (north). Z = elevation above level 0 finished floor |
| Origin | Building origin at south-west corner of ground floor footprint |
| Precision | Geometry rounded to **1 mm** (3 decimals) on serialization; comparisons use `EPS = 1e-4` |
| IDs | UUIDv4 strings. Stable across regenerations where semantically the same object (see §7) |
| Enums | `snake_case` strings |
| Schema version | Semver string on every root document: `"schema_version": "1.0.0"` |

Three.js conversion (Y-up) happens in exactly one place: the viewer root group (`rotation.x = -π/2`). See [3d-engine.md](3d-engine.md).

---

## 2. BuildingSpecification (intent)

```jsonc
{
  "schema_version": "1.0.0",
  "building_type": "single_family_house",          // enum; residential only in v1
  "name": "Modern two-story house",
  "targets": {
    "gross_floor_area_m2": 280,
    "storeys": 2,
    "floor_to_floor_height_m": 3.0,                 // default 3.0
    "max_footprint_m": { "width": null, "depth": null }
  },
  "site": {
    "plot_width_m": null, "plot_depth_m": null,
    "north_angle_rad": 0,
    "setbacks_m": { "front": null, "rear": null, "side": null },
    "street_side": "south"
  },
  "style": {
    "architectural_style": "modern_minimalist",     // enum
    "roof": { "type": "flat", "pitch_deg": null },  // flat | gable | hip | shed
    "facade_materials": ["white_render", "timber_cladding"],   // material library ids
    "window_style": "panoramic",                    // standard | large | panoramic
    "interior_finish_level": "standard"             // economy | standard | premium
  },
  "rooms": [
    {
      "key": "bedroom_master",                      // stable semantic key (used for ID stability)
      "type": "bedroom",                            // enum (see §2.1)
      "count": 1,
      "target_area_m2": 20, "min_area_m2": 14,
      "level": 1,                                   // preferred storey index, null = any
      "features": ["en_suite", "walk_in_closet"],
      "adjacent_to": ["bathroom_master"],
      "exterior_access": false
    },
    { "key": "kitchen_living", "type": "open_kitchen_living", "count": 1, "target_area_m2": 60, "level": 0,
      "features": ["kitchen_island"], "exterior_access": true }
    // ...
  ],
  "features": {
    "garage": { "cars": 2, "attached": true },
    "balconies": [{ "level": 1, "attached_to": "bedroom_master", "depth_m": 1.8 }],
    "terrace": null,
    "basement": false,
    "stairs": { "type": "straight" }                // straight | l_shaped | u_shaped
  },
  "services": {
    "heating": "heat_pump",                         // gas_boiler | heat_pump | electric
    "cooling": "split_ac",                          // none | split_ac | ducted
    "ventilation": "natural",                       // natural | mvhr
    "hot_water": "cylinder"
  },
  "assumptions": [                                  // everything the AI inferred, shown to user
    { "path": "/targets/floor_to_floor_height_m", "value": 3.0, "reason": "Not specified; residential default." }
  ],
  "open_questions": [                               // ambiguities the AI could not resolve
    "Should the garage connect directly to the house interior?"
  ]
}
```

### 2.1 Room types (v1)

`bedroom, bathroom, wc, en_suite, kitchen, living, dining, open_kitchen_living, study, laundry, utility, storage, walk_in_closet, hall, corridor, entrance, staircase, garage, plant_room`

Each type has defaults in `building/defaults.py` (min area, min width, needs window, wet room, privacy zone, typical finish).

### 2.2 Spec validation (three tiers)

| Tier | Where | Examples | Result |
|---|---|---|---|
| 1. Structural | Pydantic | types, enums, ranges (`0 < storeys ≤ 3`), required fields | hard error |
| 2. Semantic | `building/validation/spec_rules.py` | Σ room target areas ≤ 0.85 × GFA (circulation/walls allowance); ≥1 bathroom; garage on level 0; balcony level < storeys; `adjacent_to` keys exist; bedrooms need exterior wall | error or warning |
| 3. Feasibility | layout engine | footprint fits plot/setbacks; rooms fit minimum widths | error with suggestion |

Every issue: `{ severity, code, path (JSON pointer), message, suggestion? }`. Errors are fed back to the AI for repair (see [ai-pipeline.md](ai-pipeline.md)).

---

## 3. BuildingModel (resolved)

Implemented in `apps/api/app/modules/building/{primitives,enums,elements,model}.py` (schema_version **1.0.0**). JSON Schema, TS types and the Zod validator in `packages/schema` are generated from these classes (`pnpm schema`).

```jsonc
{
  "schema_version": "1.0.0",
  "id": "uuid",                       // the "building" object id
  "building": { "name": "Demo family house", "building_type": "single_family_house", "description": "…" },
  "units": "m",
  "engine_version": "fixture@1",      // layout@x.y.z once generated (Phase 2)
  "seed": null,                       // layout seed (Phase 2)
  "levels": [ Level, ... ],           // the "floor" objects
  "elements": [ Element, ... ],       // discriminated union on "type"
  "metadata": { "source": "fixture" | "layout" | "operations", "generator": "…" }
}
```

`spec_hash` and `systems` (MEP) are added as minor schema versions in Phases 2 and 6.

### 3.1 Level ("floor")

```jsonc
{ "id": "uuid", "name": "Floor 1", "index": 0, "elevation": 0.0, "height": 3.0, "semantic_key": "level:L0" }
```

`elevation` = finished floor level above level 0; `height` = floor-to-floor. All lengths are meters (no `_m` suffixes in the model).

### 3.2 Element base (every object)

```jsonc
{
  "id": "uuid",                        // stable: uuid5(namespace, semantic_key) for fixtures
  "type": "wall",                      // discriminator
  "name": "W-G01",
  "layer": "structure",                // architecture | structure | furniture | plumbing | electrical | hvac | fire_safety | landscaping
  "level_id": "uuid",
  "position": { "x": 0, "y": 0, "z": 0 },   // element-local anchor, meaning per type (below)
  "rotation": { "x": 0, "y": 0, "z": 0 },   // radians, XYZ Euler; most elements use z (yaw)
  "dimensions": { ... },               // typed per element type
  "material_id": "brick" | null,       // id in data/materials/library.json
  "properties": { ... },               // typed per element type (no free-form bag)
  "relationships": [ { "kind": "bounds", "target_id": "uuid" } ],
  "origin": "generated" | "user",
  "locked": false,
  "semantic_key": "wall:G-S"
}
```

Absolute elevation = `level.elevation + position.z`. Polygon properties (room boundary, slab/roof outline) are relative to `position`, rotated by `rotation.z`. All models are `extra="forbid"`; lengths are rounded to 1 mm, areas to 0.01 m², angles to 1e-6 rad on validation.

### 3.3 Element types (implemented in schema 1.0.0)

| type | usual layer | position = | dimensions | properties |
|---|---|---|---|---|
| `wall` | structure (load-bearing exterior) / architecture | axis start; `rotation.z` = axis direction | `length, thickness, height` | `wall_kind` (exterior/interior/partition), `alignment` (center/left/right), `load_bearing`, `finish_left_id`, `finish_right_id` (left = +normal side; exterior walls are authored CCW so left = interior) |
| `door` | architecture | host-wall-local: x = offset of the start edge, z = 0 | `width, height, thickness` | `door_kind` (entrance/interior/sliding/garage), `swing` (left/right/double/sliding), `frame_material_id` |
| `window` | architecture | host-wall-local: x = offset, z = sill height | `width, height` | `window_kind` (fixed/casement/sliding/panoramic), `frame_material_id`, `mullions` |
| `room` | architecture | boundary origin | `area, perimeter, height` (validated against the boundary) | `room_type`, `zone`, `boundary` (CCW, rectilinear, wall centerlines), `floor_material_id` |
| `slab` | structure | outline origin; **top face** at `position.z` | `thickness, area` (outline − holes) | `slab_kind` (ground/floor/balcony), `outline`, `holes` |
| `stair` | structure | bottom corner at the first riser; flight along local +x, width along local +y | `width, run_length, rise_total` | `stair_type` (straight), `risers`, `riser_height`, `tread_depth`, `from_level_id`, `to_level_id` |
| `roof` | architecture | outline origin; `position.z` = top of covering at the eaves | `thickness, overhang` | `roof_type` (flat/gable/hip), `outline` (eaves, rectangle for pitched), `pitch_deg`, `ridge_axis`, `parapet_height` |
| `railing` | architecture | start of the base line; runs along local +x | `length, height` | `railing_kind` (glass/bars), `rise` (0 = level, > 0 = sloped/stair), `post_spacing` |
| `furniture` | furniture | base center on the floor; front faces local −y | `width, depth, height` | `furniture_kind` (18 kinds: sofa, armchair, coffee_table, tv_unit, dining_table, chair, bed, nightstand, wardrobe, bookshelf, desk, kitchen_counter, kitchen_island, fridge, toilet, basin, bathtub, shower), `asset_id` (GLB/glTF catalog id, null = procedural) |

Planned types (later phases): `column`, `beam` (structure); `pipe_segment`, `fixture`, `equipment` (plumbing); `conduit_run` (electrical); `duct_segment`, `terminal` (HVAC); `system` objects for MEP networks.

Wall derived geometry (not stored): `start = position`, `end = position + length·(cos θ, sin θ)`, `θ = rotation.z`.

### 3.4 Relationships

Directed, typed edges stored on the source element; targets must exist (API validator + web index).

| kind | from → to | meaning |
|---|---|---|
| `hosted_by` | door/window → wall | the opening lives in that wall (exactly one) |
| `bounds` | wall → room | the wall's axis runs along the room's boundary |
| `adjacent_to` | room → room | the rooms share a boundary edge (with or without a wall) |
| `connects` | door → room | rooms joined by the door (2, or 1 for exterior doors) |
| `supports` | wall → slab/roof | load path (ground facades carry the floor slab, upper facades the roof) |
| `located_in` | furniture/stair/railing → room | placement |
| `serves`, `connected_to`, `part_of_system` | MEP (Phase 6) | reserved |

Level membership is `level_id` (not a relationship).

---

## 4. Invariants (enforced by `building/validation.py`)

Errors (model rejected):

1. Unique ids across model, levels and elements; unique semantic keys; level indices 0..n-1.
2. Every `level_id` and relationship target exists.
3. Every material id (element, finishes, frames, floor finishes) exists in the material library (when the library is supplied).
4. Doors/windows: exactly one `hosted_by` wall on the same level; fully inside the wall (`0 ≤ x`, `x + width ≤ length`, `z + height ≤ wall height`); no overlaps on the same wall.
5. Wall height ≤ level height.
6. Room boundaries: CCW, rectilinear, simple; `area`/`perimeter` match the boundary; rooms on a level do not overlap.
7. Slabs: CCW simple outline, holes inside, `area` = outline − holes. Pitched roofs need a rectangular outline.
8. Stairs: `risers × riser_height ≈ rise_total` and `(risers − 1) × tread_depth ≈ run_length` (±0.5 mm rounding per riser); start on `from_level`, reach the next level; `rise_total` = level difference.
9. Railings no steeper than 45°. Pydantic: all dimensions finite and > 0 (area/overhang ≥ 0).

Warnings (reported, model accepted): room not fully supported by a slab; habitable room (living, dining, kitchen, bedroom, study) without a window or glazed door on its own boundary; furniture outside every room.

Planned (Phase 2, with Hypothesis properties over generated models): reachability of every room from the entrance, stair headroom, wet-room fixture placement.

---

## 5. Operations (the only way to change a model)

```jsonc
// discriminated union on "op"
{ "op": "add_element",     "element": Element }
{ "op": "remove_element",  "id": "uuid", "cascade": true }           // removes hosted openings
{ "op": "update_element",  "id": "uuid", "set": { "material_id": "oak_parquet", "properties.finishes.floor": "oak_parquet" } }
{ "op": "move_element",    "id": "uuid", "delta": { "x": 0.5, "y": 0, "z": 0 } }
{ "op": "resize_room",     "id": "uuid", "edge": "east", "delta_m": 2.0 }   // moves bounding wall, shifts neighbours
{ "op": "set_room_type",   "id": "uuid", "room_type": "study" }
{ "op": "add_opening",     "host_wall_id": "uuid", "kind": "window", "offset_m": 1.2, "width_m": 2.4, "height_m": 2.2, "sill_m": 0.3 }
{ "op": "change_spec",     "patch": [JSON Patch ops] }                      // requires relayout
```

Pipeline for applying a batch:

```
validate ops (refs exist, params in range)
 → apply (pure: model, ops → model')
 → regenerate derived: rebuild room boundaries/walls where affected, rehost openings, recompute slab outlines, rerun MEP for affected levels (locked elements kept)
 → validate model' invariants
 → diff(model, model')
```

Each operation also records its **inverse** for undo within a draft. Batches that contain `change_spec` trigger a full relayout that **preserves locked elements and IDs by semantic key**; the UI warns which unlocked manual edits may be lost.

---

## 6. Discipline layers & materials

- Layers: `architecture, structure, furniture, plumbing, electrical, hvac, fire_safety, landscaping`. Exactly one per element. Phase 1 populates the first three; the viewer's layer manager lists the rest as planned.
- Materials are referenced by id into the shared **material library** `data/materials/library.json` (JSON so both Python and TypeScript read it without extra dependencies). The API validates ids against it; the web renderer builds one shared THREE material per id from it.

```json
{ "id": "brick", "name": "Brick", "category": "masonry", "color": "#9a5038", "roughness": 0.88, "metalness": 0 }
```

Required presets: concrete, brick, glass, wood, roof, floor, interior_wall, exterior_wall (plus tile, parquet, decking, window_frame, wood_dark, metal, fabric, fabric_light, ceramic, countertop, cabinet, screen). Costing fields (`item_code`, `unit`, `waste_factor`) are added in Phase 4; prices never live here (they live in cost catalogs).

---

## 7. ID stability across regeneration

Each generated element gets a `semantic_key` (e.g. `room:bedroom_master:0`, `wall:ext:L1:N:2`, `window:room:bedroom_master:N:0`). On regeneration the engine looks up the previous model's `semantic_key → id` map and reuses IDs. This keeps selection, locks, comments and diffs meaningful.

---

## 8. Schema evolution

- `schema_version` follows semver. Additive optional fields → minor. Anything else → major with a migration function in `building/migrations/` (`v1_to_v2(doc: dict) -> dict`).
- Stored documents are upgraded on read; tests keep one fixture per historical version.
- After changing Pydantic models: `pnpm schema` regenerates `packages/schema` (JSON Schema → TS types via json-schema-to-typescript; the Zod validator is built at runtime from the same JSON Schema with `z.fromJSONSchema`). After changing the demo fixture script: `pnpm fixtures`. Pytest fails if the committed JSON Schema or fixture is stale; CI fails if the generated TS is stale.

## 9. IFC alignment (future)

Types map cleanly to IFC: wall→IfcWall, room→IfcSpace, door→IfcDoor, window→IfcWindow, slab→IfcSlab, pipe_segment→IfcPipeSegment, duct_segment→IfcDuctSegment, system→IfcDistributionSystem, level→IfcBuildingStorey. We don't implement export now, but we avoid modeling choices that would prevent it.

---

## 10. BuildingRulesProfile (configurable conceptual rules)

Dimensional rules are **data, not code**. The layout engine and validators read every minimum/maximum from the active `BuildingRulesProfile`; no dimensional constant is hard-coded in business logic.

> Rules profiles support **conceptual validation only**. They are not a statement of compliance with any building code, including Kazakhstan's (SN/SP RK). BuildAI 3D does not replace licensed architectural, structural, MEP or regulatory review.

- Code: `apps/api/app/modules/rules/` (pure domain module; Pydantic schema + evaluator).
- Data: `data/rules-profiles/*.yaml`, seeded into the DB (`rules_profiles` table); immutable once used by a version.
- Each project has a `rules_profile_id` (default `generic-residential@1`). Each version records which profile + version validated it.
- Regional profiles (e.g. `kz-residential`) are added later as new YAML files that `extends` the generic profile and override values.

```yaml
id: generic-residential
version: 1
name: Generic residential (conceptual)
extends: null
disclaimer: Conceptual rules only. Not a building-code compliance check.
units: m
rooms:                      # per room type; unspecified types fall back to "default"
  default:      { min_area_m2: 4.0,  min_width_m: 1.5 }
  bedroom:      { min_area_m2: 9.0,  min_width_m: 2.7, requires_window: true }
  bedroom_master: { min_area_m2: 12.0, min_width_m: 3.0, requires_window: true }
  living:       { min_area_m2: 16.0, min_width_m: 3.6, requires_window: true }
  kitchen:      { min_area_m2: 6.0,  min_width_m: 2.2, requires_window: true }
  open_kitchen_living: { min_area_m2: 25.0, min_width_m: 4.0, requires_window: true }
  bathroom:     { min_area_m2: 3.5,  min_width_m: 1.6 }
  wc:           { min_area_m2: 1.2,  min_width_m: 0.9 }
  corridor:     { min_area_m2: 0.0,  min_width_m: 1.0 }
  garage:       { min_area_m2: 18.0, min_width_m: 3.0, per_car_area_m2: 18.0 }
ceiling:
  min_clear_height_m: 2.5           # habitable rooms
  min_clear_height_service_m: 2.2   # storage, garage, wc, corridor
corridors:
  min_width_m: 1.0
  min_width_accessible_m: 1.2
doors:
  entrance:  { min_width_m: 0.9,  min_height_m: 2.1 }
  interior:  { min_width_m: 0.8,  min_height_m: 2.0 }
  bathroom:  { min_width_m: 0.7,  min_height_m: 2.0 }
  garage:    { min_width_per_car_m: 2.5, min_height_m: 2.1 }
windows:
  min_glazing_to_floor_ratio: 0.125  # habitable rooms (1:8)
  min_sill_height_m: 0.0             # panoramic allowed
  guard_required_below_sill_m: 0.9   # upper floors: sills lower than this need a guard/railing
  min_width_m: 0.6
  min_height_m: 0.6
stairs:
  min_width_m: 0.9
  riser_m: { min: 0.15, max: 0.19 }
  tread_m: { min: 0.25, max: 0.32 }
  comfort_rule: { formula: "2R+T", min: 0.60, max: 0.65 }
  min_headroom_m: 2.0
  max_risers_per_flight: 16
  landing_min_depth_m: 0.9
railings:
  min_height_m: 0.9
  balcony_min_height_m: 1.0
accessibility:                       # basic geometry checks, reported as warnings
  step_free_entrance: warning
  turning_circle_diameter_m: 1.5     # checked in one ground-floor bathroom when enabled
  accessible_door_clear_width_m: 0.85
  enabled: false
```

Rule evaluation output uses the standard issue shape `{ severity, code, path, message, rule_ref }` where `rule_ref` = `generic-residential@1:stairs.riser_m` so every warning is traceable to the exact rule.
