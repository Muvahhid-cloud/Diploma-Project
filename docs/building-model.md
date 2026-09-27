# Building Model

Status: **Accepted (v0.1)** · Canonical code: `apps/api/app/modules/building/` · Generated: `packages/schema/`

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

```jsonc
{
  "schema_version": "1.0.0",
  "id": "uuid",
  "engine_version": "layout@0.3.1",
  "seed": 42,
  "spec_hash": "sha256:…",           // spec this was generated from
  "units": "m",
  "levels": [ Level, ... ],
  "elements": [ Element, ... ],      // discriminated union on "type"
  "systems": [ System, ... ],        // MEP systems
  "metadata": { "created_at": "...", "generator": "layout" }
}
```

### 3.1 Level

```jsonc
{ "id": "uuid", "name": "Ground floor", "index": 0, "elevation_m": 0.0, "height_m": 3.0 }
```

### 3.2 Element base (every object)

The product requirement: *every object has UUID, type, dimensions, position, rotation, material, properties, relationships.*

```jsonc
{
  "id": "uuid",
  "type": "wall",                     // discriminator
  "name": "Exterior wall S-1",
  "layer": "architecture",            // architecture | structure | plumbing | electrical | hvac | site
  "level_id": "uuid" | null,          // null for site elements / multi-level (e.g. stair core ref)
  "position": { "x": 0, "y": 0, "z": 0 },      // local anchor; meaning defined per type (below)
  "rotation": { "x": 0, "y": 0, "z": 0 },      // radians, XYZ Euler; most elements use only z (yaw)
  "dimensions": { ... },              // type-specific, typed
  "material_id": "white_render" | null,        // primary material; layered build-ups in properties
  "properties": { ... },              // type-specific, typed (NOT a free-form bag in the schema)
  "relationships": [ { "kind": "hosted_by", "target_id": "uuid" } ],
  "origin": "generated" | "user",     // who created it
  "locked": false,                    // user-locked: regeneration must preserve
  "semantic_key": "wall:ext:L0:S:1"   // for stable IDs across regeneration
}
```

`position`/`rotation` are *element-local anchors*: absolute `z` is `level.elevation_m + position.z`. `properties` is typed per element type in Pydantic (we keep an `extra: dict` escape hatch named `custom` for user-defined data only).

### 3.3 Element types (v1)

| type | layer | position = | dimensions | key properties |
|---|---|---|---|---|
| `wall` | architecture / structure | wall axis start point | `length, thickness, height` (rotation.z = axis direction) | `wall_kind` (exterior/interior/partition), `alignment` (center/left/right), `build_up` (layers w/ material + thickness), `load_bearing` |
| `room` (space) | architecture | origin of boundary polygon | `area, perimeter, height` (derived) | `room_type, spec_key, boundary: [Vec2]` (CCW, rectilinear v1), `finishes {floor, wall, ceiling}`, `zone` (public/private/service) |
| `door` | architecture | offset along host wall axis (x), 0, 0 | `width, height, thickness` | `swing` (left/right/sliding/double), `opens_into` room id, `door_kind` (entrance/interior/garage) |
| `window` | architecture | offset along host wall axis, sill height as z | `width, height` | `window_kind` (fixed/casement/sliding/panoramic), `glazing`, `frame_material` |
| `slab` | structure | origin of outline | `thickness, area` | `outline: [Vec2]`, `holes: [[Vec2]]`, `slab_kind` (ground/floor/balcony) |
| `roof` | architecture | footprint origin | `thickness, overhang` | `roof_type, pitch, outline, ridge_axis` |
| `stair` | architecture | bottom start | `width, run_length, rise_total` | `stair_type, risers, riser_h, tread_d`, connects levels |
| `column` | structure | base center | `width, depth, height` | `section` |
| `beam` | structure | start point | `length, width, depth` | |
| `railing` | architecture | start | `length, height` | balcony/stair |
| `pipe_segment` | plumbing | start point | `length, diameter` | `start, end (Vec3)`, `pipe_kind` (cold/hot/drain/vent), `slope` |
| `duct_segment` | hvac | start point | `length, width, height` or `diameter` | `start, end`, `duct_kind` (supply/return/exhaust) |
| `conduit_run` | electrical | start | `length` | `polyline: [Vec3]`, `cable_type`, `circuit_id` |
| `fixture` | plumbing / electrical | insertion point | bounding box | `fixture_kind` (wc, basin, shower, bathtub, kitchen_sink, outlet, switch, light, …), catalog id |
| `equipment` | plumbing / electrical / hvac | insertion point | bounding box | `equipment_kind` (water_heater, heat_pump, ac_indoor, ac_outdoor, distribution_board, …) |
| `terminal` | hvac | insertion point | `width, depth` | diffuser/grille |
| `furniture` | architecture | insertion point | bounding box | optional, visual only, excluded from cost by default |

Wall derived geometry (not stored, computed by helpers used by both Python & TS):
`start = position`, `end = position + length·(cos θ, sin θ)`, `θ = rotation.z`.

Openings are positioned in **host-wall-local coordinates** (`x` along axis from wall start, `z` = sill height), so moving a wall moves its openings automatically.

### 3.4 Relationships

Directed, typed edges stored on the *source* element. The validator guarantees referential integrity; an index of reverse edges is built in memory on load.

| kind | from → to | meaning |
|---|---|---|
| `contained_in` | any → level | (redundant with `level_id`, not stored; derived) |
| `hosted_by` | door/window → wall | opening lives in wall |
| `bounds` | wall → room | wall is a boundary of room (both sides: one edge per room) |
| `adjacent_to` | room → room | share a wall |
| `connects` | door → room | door connects rooms (2 edges, or 1 + exterior) |
| `supports` | column/wall/beam → slab/beam | structural load path |
| `serves` | fixture/terminal/equipment → room | located in / serves room |
| `connected_to` | MEP element → MEP element | network topology |
| `part_of_system` | MEP element → system | membership |

### 3.5 System (MEP)

```jsonc
{ "id": "uuid", "name": "Domestic cold water", "discipline": "plumbing",
  "system_kind": "domestic_cold_water",   // cold_water | hot_water | sanitary_drain | vent | lighting_circuit | power_circuit | supply_air | return_air | refrigerant
  "source_id": "uuid", "properties": { "circuit_breaker_a": 16 } }
```

---

## 4. Invariants (enforced by `building/validation/model_rules.py`)

1. All IDs unique; all relationship targets exist; all `level_id`s exist.
2. Rooms on the same level do not overlap (area of intersection < EPS).
3. Every room is reachable from the entrance via doors/stairs (graph connectivity).
4. Every opening lies fully within its host wall (`0 ≤ x`, `x + width ≤ length`, `z + height ≤ wall height`), and openings on a wall don't overlap.
5. Wall heights ≤ level height; slabs cover every room footprint.
6. Habitable rooms (bedroom, living, study, kitchen) have ≥1 window unless user-overridden.
7. Wet-room fixtures are in rooms with `wet_room=true`.
8. Stairs connect consecutive levels and have headroom (slab hole present above).
9. No NaN/Infinity; all dimensions > 0.

These are also Hypothesis properties run over thousands of random specs.

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

- Layers: `architecture, structure, plumbing, electrical, hvac, site`. Exactly one per element.
- Materials are referenced by id into the **material library** (`data/materials/*.yaml`):

```yaml
- id: white_render
  name: White silicone render
  category: facade_finish
  color: "#f2f1ec"
  roughness: 0.9
  texture: null
  unit: m2
  waste_factor: 0.05
  item_code: FIN.FACADE.RENDER
  density_kg_m3: null
```

The same library drives rendering (color/roughness/texture) and costing (`item_code`, waste factor).

---

## 7. ID stability across regeneration

Each generated element gets a `semantic_key` (e.g. `room:bedroom_master:0`, `wall:ext:L1:N:2`, `window:room:bedroom_master:N:0`). On regeneration the engine looks up the previous model's `semantic_key → id` map and reuses IDs. This keeps selection, locks, comments and diffs meaningful.

---

## 8. Schema evolution

- `schema_version` follows semver. Additive optional fields → minor. Anything else → major with a migration function in `building/migrations/` (`v1_to_v2(doc: dict) -> dict`).
- Stored documents are upgraded on read; tests keep one fixture per historical version.
- After changing Pydantic models: `make schema` regenerates `packages/schema` (JSON Schema, TS types, Zod). CI fails on drift.

## 9. IFC alignment (future)

Types map cleanly to IFC: wall→IfcWall, room→IfcSpace, door→IfcDoor, window→IfcWindow, slab→IfcSlab, pipe_segment→IfcPipeSegment, duct_segment→IfcDuctSegment, system→IfcDistributionSystem, level→IfcBuildingStorey. We don't implement export now, but we avoid modeling choices that would prevent it.
