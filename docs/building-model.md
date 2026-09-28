# Building Model

Status: **Implemented for Phase 3 (v0.5)** · Canonical code: `apps/api/app/modules/building/` · Generated: `packages/schema/`

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
| IDs | UUID strings: uuid5 of the semantic key for generated/fixture elements, stable across regenerations where semantically the same object (see §7); uuid4 for rows created by the app |
| Enums | `snake_case` strings |
| Schema version | Semver string on every root document: `"schema_version": "1.0.0"` |

Three.js conversion (Y-up) happens in exactly one place: the viewer root group (`rotation.x = -π/2`). See [3d-engine.md](3d-engine.md).

---

## 2. BuildingSpecification (intent)

Implemented in `apps/api/app/modules/building/specification.py` (schema_version **1.0.0**). JSON Schema (validation shape: defaulted fields optional), TS types and a Zod validator are generated into `packages/schema` (`pnpm schema`). The spec contains **no geometry**: no coordinates, walls, element ids or levels' positions — unknown fields are rejected (`extra="forbid"`), vocabularies are closed enums. Reference specs: `data/fixtures/specs/*.spec.json`.

```jsonc
{
  "schema_version": "1.0.0",
  "building_type": "single_family_house",
  "name": "Modern family house",
  "description": "…",
  "targets": {
    "gross_floor_area_m2": 280,        // on wall centerlines, all storeys, garage/balconies/terraces excluded; null = derived
    "storeys": 2,                      // 1..3 (v1 scope)
    "floor_to_floor_height_m": 3.0,    // 2.4..4.0, default 3.0
    "max_footprint_width_m": null, "max_footprint_depth_m": null
  },
  "site": {                            // optional; the street is on the model's south side (-y)
    "plot_width_m": 20, "plot_depth_m": 30,
    "setback_front_m": 5, "setback_rear_m": 6, "setback_side_m": 1.5, "region_code": "KZ-ALA"
  },
  "style": {
    "architectural_style": "modern",   // modern|minimalist|contemporary|classic|traditional|scandinavian|industrial|mediterranean|luxury
    "interior_style": "minimalist",    // optional
    "roof": { "type": "flat", "pitch_deg": null },   // flat|gable|hip; pitch 5..45 (null = engine default 25°)
    "window_style": "large",           // standard|large|panoramic
    "facade_material": "render",       // render|brick|concrete|timber (mapped to material-library ids)
    "interior_finish_level": "standard"   // economy|standard|premium
  },
  "rooms": [                           // 1..40 requirements; keys unique
    { "key": "living", "type": "living", "name": "Living room", "target_area_m2": 45, "level": 0,
      "open_to": ["kitchen"] },        // open plan: no wall where they meet (or open onto the corridor between them)
    { "key": "kitchen", "type": "kitchen", "target_area_m2": 20, "adjacent_to": ["dining"] },
    { "key": "master_bedroom", "type": "bedroom", "target_area_m2": 22, "level": 1,
      "features": ["en_suite"] },      // en_suite | walk_in_closet: rooms reached through this bedroom
    { "key": "bedroom", "type": "bedroom", "count": 3, "min_area_m2": 12 }
  ],
  "features": {
    "garage": { "cars": 2 },           // 1..3, attached at the ground floor
    "balconies": [{ "level": 1, "attached_to": "master_bedroom", "side": "garden", "width_m": null, "depth_m": 1.5 }],
    "terrace": { "attached_to": "living", "width_m": null, "depth_m": 3.0 }   // ground floor, garden side
  },
  "budget": { "amount": "300000000.00", "currency": "KZT" },   // Decimal as string; a constraint only (nothing is costed in Phase 2)
  "assumptions": [{ "path": "/targets/floor_to_floor_height_m", "value": 3.0, "reason": "Not specified; residential default." }],
  "open_questions": ["Should the garage connect directly to the house interior?"]
}
```

Semantics:

- `level` is a 0-based storey index (0 = ground floor); `null` lets the engine choose.
- `count` expands one requirement into instances `bedroom_1`, `bedroom_2`, … (the instance key is the room's semantic key suffix, `room:bedroom_2`).
- Areas are per room, on wall centerlines. Rooms without `target_area_m2` get engine defaults (layout `LayoutConfig.default_areas`), scaled to fill the requested floor area (service rooms by at most ±30 %, living spaces and bedrooms up to 2×).
- `assumptions` / `open_questions` are filled by the AI interpreter (every inferred value is an assumption with its JSON pointer and reason) and shown to the user.

### 2.0 Produced by AI (Phase 3)

The schema is unchanged by Phase 3 (still 1.0.0): the AI must produce exactly this document. Models answer with a `SpecificationDraft` (`app/modules/ai/schemas/generation.py`) that wraps it with `outcome` (`specification` | `clarification`), `understanding`, `clarification_questions`, `conflicts` and `unsupported_requests`; the draft is validated like any untrusted input (tier 1 + tier 2, one repair call at most — docs/ai-pipeline.md §5). Requests the vocabulary cannot express are reported, never approximated silently; the closed vocabularies above are also what the prompt offers (generated from the enums).

`building/requirements.py` (pure) derives the key requirements of a spec (`SpecFacts`: storeys, floor area, bedrooms, bathrooms incl. en-suites, WCs, garage cars, balconies, terrace) and compares them with a generated model's `ModelSummary` (`RequirementCheck`: requested → delivered, met). It powers the "requested vs generated" summary and detects when an AI repair changed the user's program.

### 2.1 Room types (v1)

A spec may request: `bedroom, bathroom, wc, kitchen, living, dining, open_kitchen_living, study, laundry, utility, storage, plant_room` (+ `en_suite`, `walk_in_closet` via bedroom `features`). The engine adds circulation (`entrance` hall, `corridor`, `staircase`/landing), `garage`, `balcony` and `terrace` rooms from `features`. `hall` exists in the model vocabulary but is not generated yet.

### 2.2 Spec validation (three tiers)

| Tier | Where | Examples | Result |
|---|---|---|---|
| 1. Structural | Pydantic (`specification.py`); the web form runs the generated Zod validator first | types, enums, ranges (`1 ≤ storeys ≤ 3`), unique room keys, no unknown fields | 422 `VALIDATION_ERROR` with JSON-pointer paths |
| 2. Semantic | `rules/spec_checks.py` against the project's `BuildingRulesProfile` | target area ≥ rule minimum; Σ room minimums ≤ 0.85 × GFA; ≥ 1 bathroom (or en-suite); `level` < storeys; `adjacent_to`/`open_to`/`attached_to` keys exist; open plan only between living/dining/kitchen/study; features only on bedrooms; clear height ≥ `ceiling.min_clear_height_m`; storey height ≤ one straight flight; balconies need an upper floor; plot/setbacks leave enough buildable area | errors block generation (422 `SPEC_INVALID`); warnings (no kitchen, no bedroom, feature on a service room) are shown |
| 3. Feasibility | layout engine | stair fits the street-side band; rooms fit their bands at minimum widths; footprint fits the plot/max footprint; every room reachable | job fails with `LAYOUT_INFEASIBLE` and reasons |

Every issue has the same shape (`building/issues.py`): `{ severity, code, path (JSON pointer), message, suggestion?, rule_ref?, element_id? }`. `rule_ref` is e.g. `generic-residential@1:rooms.bedroom.min_area_m2`.

---

## 3. BuildingModel (resolved)

Implemented in `apps/api/app/modules/building/{primitives,enums,elements,model}.py` (schema_version **1.0.0**). JSON Schema, TS types and the Zod validator in `packages/schema` are generated from these classes (`pnpm schema`).

```jsonc
{
  "schema_version": "1.0.0",
  "id": "uuid",                       // the "building" object id
  "building": { "name": "Demo family house", "building_type": "single_family_house", "description": "…" },
  "units": "m",
  "engine_version": "layout@1.0.0",   // "fixture@1" for the hand-authored demo
  "seed": 0,                          // layout seed (null for fixtures)
  "levels": [ Level, ... ],           // the "floor" objects
  "elements": [ Element, ... ],       // discriminated union on "type"
  "metadata": { "source": "fixture" | "layout" | "operations", "generator": "layout@1.0.0 · rules generic-residential@1" }
}
```

The spec a model was generated from is stored next to it in the project version (not inside the model). Versions produced by the AI pipeline have `source = "ai_generation"`, keep the user's `prompt`, and their generation report carries `generation` provenance (generation id, `building_generation`, provider, model, prompt version). `systems` (MEP) is added as a minor schema version in Phase 6.

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

Warnings (reported, model accepted): room not fully supported by a slab; habitable room (living, dining, kitchen, bedroom, study) without a window or glazed door on its own boundary; furniture outside every room; **room not reachable from the entrance** (`ROOM_UNREACHABLE`: graph over doors — `connects` computed geometrically —, open boundaries where no wall axis runs along a shared room edge for ≥ 0.6 m, and stairs linking the room at the bottom to the room at the top landing; start = rooms with an `entrance` door, else any exterior door); no exterior door at all (`NO_ENTRANCE`).

The layout engine rejects its own candidates on any error **or** `ROOM_UNREACHABLE`, so generated models always satisfy them; Hypothesis properties over random specs check this (`tests/layout/test_invariants.py`). Not yet checked: stair headroom, wet-room fixture placement.

Rules findings (conceptual, per rules profile) are a separate evaluator, `rules/model_checks.py` (§10); they are warnings with a `rule_ref` and never invalidate a model.

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

Each generated element gets a `semantic_key` derived from what it *is*, not where it is: `level:L1`, `room:master_bedroom`, `room:bedroom_2`, `room:corridor_1`, `room:hall_0`, `wall:ext:L1:N`, `wall:garage:S`, `wall:L1:bedroom_2|corridor_1` (interior walls: the two regions of their longest stretch), `door:front`, `door:bedroom_2`, `window:bedroom_2:S:0`, `slab:L1`, `stair:flight_0`, `roof:main`, `furniture:bedroom_2:bed:1`.

Element ids are `uuid5(id_namespace, semantic_key)`. The generation service uses the **project id** as the namespace, so regenerating the same kind of element in a project yields the same id, while two projects never share ids. `generate_layout(..., previous_ids={semantic_key: id})` additionally reuses the ids of an existing model (e.g. a hand-authored fixture) for matching keys — the hook Phase 5 regeneration with locks will build on.

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

- Code: `apps/api/app/modules/rules/` (pure domain module): `profile.py` (Pydantic schema), `loader.py` (YAML files, `extends` resolved by deep merge), `spec_checks.py` (tier-2 spec validation, §2.2), `model_checks.py` (evaluation of any BuildingModel).
- Data: `data/rules-profiles/<id>.v<version>.yaml` (YAML: human-edited, commented data; PyYAML). Profiles are read from files and cached per process; the `rules_profiles` DB table is deferred until profiles become user-editable. A file is **immutable once used** — changes go into a new version file.
- Each project has a `rules_profile_id` (default `generic-residential@1`). Each version records the profile (`project_versions.rules_profile`) that validated it; rules findings are re-evaluated on read against that exact profile.
- Regional profiles (e.g. `kz-residential`) are added later as new YAML files that `extends` the generic profile and override values.

`model_checks` evaluates: room area and clear width per room type (clear width = the largest short side of an axis-aligned rectangle inside the room, i.e. the main part of an L-shaped room), corridor width, clear ceiling height (habitable vs service), glazing-to-floor ratio of rooms with `requires_window` (windows + glazed sliding doors on the room's boundary), door width/height by kind (entrance, interior, wet room, garage per car), window size, upper-floor sills below the guard height, stair riser/tread/2R+T/risers per flight/width, railing heights (balcony vs other). Not evaluated yet: headroom, accessibility (profile data present, `enabled: false`).

```yaml
id: generic-residential
version: 1
name: Generic residential (conceptual)
extends: null
disclaimer: Conceptual rules only. Not a building-code compliance check.
units: m
rooms:                      # per room type; unspecified types fall back to "default"
  default:             { min_area_m2: 4.0,  min_width_m: 1.5 }
  bedroom:             { min_area_m2: 9.0,  min_width_m: 2.7, requires_window: true }
  living:              { min_area_m2: 16.0, min_width_m: 3.6, requires_window: true }
  dining:              { min_area_m2: 8.0,  min_width_m: 2.7, requires_window: true }
  kitchen:             { min_area_m2: 6.0,  min_width_m: 2.2, requires_window: true }
  open_kitchen_living: { min_area_m2: 25.0, min_width_m: 4.0, requires_window: true }
  study:               { min_area_m2: 6.0,  min_width_m: 2.2, requires_window: true }
  bathroom:            { min_area_m2: 3.5,  min_width_m: 1.6 }
  en_suite:            { min_area_m2: 3.0,  min_width_m: 1.5 }
  wc:                  { min_area_m2: 1.2,  min_width_m: 0.9 }
  # … laundry, utility, storage, walk_in_closet, plant_room, entrance, hall, staircase
  corridor:            { min_area_m2: 0.0,  min_width_m: 1.0 }
  garage:              { min_area_m2: 18.0, min_width_m: 3.0, per_car_area_m2: 18.0 }
  balcony:             { min_area_m2: 1.5,  min_width_m: 0.9 }
  terrace:             { min_area_m2: 3.0,  min_width_m: 1.5 }
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

Rule evaluation output uses the standard issue shape `{ severity, code, path, message, rule_ref, element_id }` where `rule_ref` = `generic-residential@1:stairs.riser_m` so every warning is traceable to the exact rule. (The originally sketched `bedroom_master` entry was dropped: the model has no "master" room type, so it could not be applied reliably.)
