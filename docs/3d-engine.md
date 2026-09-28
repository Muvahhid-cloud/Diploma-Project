# 3D Engine

Status: **Implemented for Phase 2 (v0.4)** · Last updated: 2026-09-28

The "3D engine" is four parts with hard boundaries:

| Part | Location | Input → Output | Status |
|---|---|---|---|
| **Layout engine** | Python `modules/layout` | Spec + RulesProfile + seed → BuildingModel | ☑ Phase 2 (§16) |
| **MEP generator** | Python `modules/mep` | Architectural model → model + MEP elements | Phase 6 |
| **Geometry engine** | TS `apps/web/src/engine` | BuildingModel + EngineConfig → `SceneGraph` (render descriptors) | ☑ Phase 1 |
| **Viewer** | TS `apps/web/src/viewer` (R3F) + `features/editor` | SceneGraph + view state → interactive scene | ☑ Phase 1 |

Positions of everything are decided by the model (the layout engine for generated versions; the hand-authored demo fixture otherwise). Generated models go through the unchanged Phase 1 geometry engine and viewer. The browser only **tessellates** what the model states. There is no hidden render-only representation: every mesh is built from, and points back to, one BuildingModel element.

### Determinism contract

> **Same BuildingModel + same EngineConfig ⇒ identical geometry** (same descriptors, same order, same buffers, same material keys).

- Builders never call `Math.random`/`Date.now` or read mutable globals.
- Elements are built in **id order**, independent of document order (tested by building a reversed document).
- Walls joins are resolved in id order; polygon orientation is normalized before triangulation.
- `EngineConfig.version` (`engine@1`) is part of every geometry cache key; bump it when builder output changes.
- Verified by Vitest: a hash over every descriptor key, material list, matrix and position/normal/uv buffer must be equal across builds (`engine/scene/build-scene.test.ts`).

---

## 1. Coordinate system

| Property | BuildingModel (backend & data) | Three.js world (viewer) |
|---|---|---|
| Handedness | Right-handed | Right-handed |
| Up axis | **+Z** | **+Y** |
| Plan axes | +X = east, +Y = north | +X = east, **−Z** = north |
| Origin | Wall-centerline corner at south-west of the ground floor; Z = 0 at ground-floor finished floor level (FFL) | Same physical point |
| Angles | Radians, counter-clockwise positive seen from above | Radians |

Element `position` is an element-local anchor defined per type ([building-model.md](building-model.md) §3.3). Absolute elevation = `level.elevation + position.z`.

## 2. Architectural units

| Quantity | Unit | Precision (enforced by Pydantic on validation) |
|---|---|---|
| Length | meter | 1 mm |
| Area | m² | 0.01 m² |
| Angle | radian | 1e-6 |

Comparisons use `EPS = 1e-4 m` (Python `primitives.EPS`, TS `engine/model/types.EPS`). The UI formats meters (`12 m`, `0.3 m`), never other units.

## 3. Model ↔ Three.js conversion (the single boundary)

`apps/web/src/engine/math/coords.ts` is the only code that knows both axis conventions:

```ts
export const MODEL_ROOT_ROTATION = [-Math.PI / 2, 0, 0]; // model +Z -> world +Y
export function modelToWorld(p) { return new Vector3(p.x, p.z, -p.y); }
export function worldToModel(v) { return { x: v.x, y: -v.z, z: v.y }; }
```

- `viewer/ModelRoot.tsx` renders **all** building meshes inside `<group rotation={MODEL_ROOT_ROTATION}>`. Descriptor matrices and geometry are in model space.
- World-space things (camera poses, sun, ground, grid, section plane) are computed in model space and converted with `modelToWorld` — camera presets (`engine/scene/camera-presets.ts`), sun direction (`viewer/SceneEnvironment.tsx`), section height (`viewer/SectionPlane.tsx`).
- A unit test asserts `modelToWorld` equals the transform of a group rotated by `MODEL_ROOT_ROTATION`.

## 4. Wall generation (`engine/builders/wall.ts`, `wall-layout.ts`)

Model: axis from `position` along `rotation.z`, `length`, `thickness`, `height`, `alignment`.

```
wall-local frame: u along the axis (0..length), v across (+v = left face = +normal), z up
alignment: center -> v in [-t/2, t/2], left -> [0, t], right -> [-t, 0]
```

1. **Joins** (`computeWallJoins`, pure, per level, id-ordered):
   - *T-junction* (this end lies inside another wall's axis) → trim by half that wall's thickness.
   - *L-corner* (ends meet) → **pinwheel**: the arriving wall ("end") extends by half the other's thickness, the leaving wall ("start") trims by the same amount — corners close with no overlapping volume and no coplanar faces. Both-start/both-end corners: smaller id extends.
   - Collinear continuation → unchanged.
2. **Panel decomposition** (`wallPanels`, no CSG): the face `[u0, u1] × [0, height]` minus hosted openings = full-height panels between openings + a sill panel below and a lintel panel above each opening. Openings are clamped to the wall; overlaps merge.
3. Each panel is a box; faces get materials `±u / ±z → material_id (core)`, `+v → finish_left_id`, `−v → finish_right_id`. The opening reveals therefore show the core (brick, render).
4. All panels of a wall become **one mesh** with one geometry group per material.

Exterior walls are authored counter-clockwise, so their left face is the interior and the right face the facade.

## 5. Opening generation (`engine/builders/openings.ts`)

Doors and windows are in host-wall-local coordinates: `position.x` = offset of the opening's start edge along the axis, `position.z` = sill (0 for doors). Their frame = host wall frame · `T(x, center of thickness, z)` — moving a wall moves its openings.

- The wall leaves the void; the opening fills it. Parts: `body` (frames, leaves, handles, sills) and `glass` (separate mesh: transparent, no shadow casting, rendered after opaque parts).
- **Window**: 60 mm frame profile, `mullions` vertical bars, one glass pane, an exterior sill board on exterior walls.
- **Door**: lining the full wall depth, closed leaf (single/double) with handles on the latch side, or two offset glass panels for sliding doors.
- Builders refuse non-finite or non-positive dimensions (`InvalidElementError`); the schema and API validator reject them earlier.

## 6. Room geometry (`engine/builders/floor.ts` — `buildFloor`)

A room is a **space**. Its floor finish is the boundary (wall centerlines) inset per edge by half the thickness of the wall that `bounds` it along that edge (open-plan edges are not inset), placed 4 mm above the slab. The finish uses `floor_material_id` and is also the room's pick surface. Area/perimeter shown in the UI come from the model, never from meshes.

## 7. Floor slabs (`engine/builders/slab.ts`)

Outline + holes (e.g. the stair void) extruded **downward** from the slab's top face (= FFL) via `MeshBuilder.prism` (earcut triangulation, orientation-normalized).

## 8. Roofs (`engine/builders/roof.ts`)

`z = 0` is the top of the covering at the eaves; `thickness` is vertical.

| Type | Implementation |
|---|---|
| `flat` | Outline prism + parapet boxes along each edge (inside the outline) |
| `gable` | Rectangle; ridge along `ridge_axis` at `(span/2)·tan(pitch)`; two slopes, underside, eave + verge bands. **No gable-end wall infill yet** (see limitations) |
| `hip` | Rectangle; closed-form skeleton (ridge inset by half the span from each end), four faces, underside, fascia |

The demo uses a 25° hip roof whose underside meets the wall tops at the outer face (computed in the fixture).

## 9. Stairs, railings, furniture

| Element | Implementation |
|---|---|
| `stair` (`stair.ts`) | Side profile (n risers, n−1 treads, sloped soffit parallel to the pitch, waist = riser + 120 mm) extruded across the width |
| `railing` (`railing.ts`) | Posts at ≤ `post_spacing`, top rail following `rise` (sloped for stairs), balusters every 120 mm (`bars`) or a glass panel (`glass`, level only) |
| `furniture` (`furniture/`) | Procedural placeholders per `furniture_kind` (18 kinds) sized from the element's dimensions; shower glass is a separate glass part. `assets.ts` resolves `asset_id` → registered GLB/glTF asset; with none registered, placeholders are used |

## 10. Object UUID mapping & mesh ↔ model mapping

```ts
interface RenderDescriptor {
  key: string;           // `${elementId}#${part}` — unique and stable
  elementId: string;     // BuildingModel element UUID (1 element -> 1..2 descriptors)
  part: "body" | "glass";
  levelId: string | null;
  layer: Layer;
  geometry: BufferGeometry;  // element-local; shared between identical parts
  geometryKey: string;       // engine version + content hash
  materials: string[];       // material id per geometry group
  matrix: Matrix4;           // element-local -> model space
  castShadow: boolean;
}
```

`SceneGraph` (`engine/scene/build-scene.ts`) holds `descriptors`, `byElement: elementId → descriptors`, model-space `bounds`, `stats`, the `ModelIndex` (`elementsById`, `levelsById`, `hostedOpenings`, `hostOf`, `wallsBounding`, `elementsByLevel`) and the geometry cache.

Rules: meshes carry only `{ elementId, part }` in `userData`; the properties panel reads the element from the index. Clicking a window selects the window (not its wall); clicking a floor finish selects the room. Tests assert every element has ≥ 1 descriptor and every descriptor maps back to an existing element with the same layer/level.

## 11. Object selection flow

```
click on canvas (drag distance ≤ 4 px, so orbiting never selects)
  → R3F raycast; hidden and ghosted meshes have a no-op raycast
  → nearest hit → resolveElementId(object) (walks up userData)       engine/scene/selection.ts
  → useSelectionStore.select(id)                                      single source of selection
  → ElementMesh re-renders only for the old/new selected element: material variant "selected"
    (emissive tint) + a bounding-box outline (elementBounds)          viewer/ModelRoot.tsx
  → PropertiesPanel: describeElement(element, index) → sections      features/editor
    (dimensions with units, material, placement, typed properties, relationships, identity);
    relationship rows are clickable and select their target
click on empty space / Esc / × → select(null)
```

Rooms can also be selected from the room list in the left panel.

## 12. Scene regeneration strategy

- `useBuildingStore.load(json)` = validate (Zod from the generated JSON Schema) → index + integrity checks → `buildScene(index, config, previousScene)`.
- Geometry is cached by **content key** (element fields + everything that influences it: hosted openings, joins, bounding-wall insets, engine version). A rebuild adopts the previous cache, so unchanged elements reuse their `BufferGeometry` (tested: changing one sofa's material rebuilds only the sofa).
- `disposeScene(old, keep=new)` disposes only geometries the new scene no longer uses. Materials live in the shared `MaterialCache` (one instance per id × variant) and are disposed when the editor unmounts.
- React keys are descriptor keys; `ElementMesh` is memoized and receives only `(descriptor, visibility mode, selected)`, so view-state changes re-render only affected meshes. View state (camera, filters, layers, selection of still-existing ids) survives rebuilds.

## 13. Performance

Demo house (measured): 116 elements → 144 meshes, ~7k triangles; validate + index + build ≈ 22 ms in the production build, ≈ 90–120 ms in dev mode. Generated houses (Phase 2, dev mode): 280 m² family house 129 elements → 155 meshes, 13–50 ms; 360 m² three-storey villa 176 elements → 214 meshes, ~35 ms.

| Technique | Status |
|---|---|
| `frameloop="demand"` (renders only on change) + `RenderOnResize` | ☑ |
| One mesh per element part with multi-material groups (not one per face/panel) | ☑ |
| Shared geometry for identical parts (e.g. 6 dining chairs → 1 geometry) | ☑ |
| Shared materials (`MaterialCache`) | ☑ |
| Memoized meshes, granular Zustand selectors | ☑ |
| Explicit disposal of replaced geometry; meshes use `dispose={null}` | ☑ |
| PCF sun shadows (2048²), disabled while a section cut is active | ☑ |
| InstancedMesh / BatchedMesh, Web Worker builds, LOD, BVH raycasting | Deferred until a model needs it (budget: 3–5k elements) |

---

## 14. Viewer & editor (Phase 1)

```
features/editor/components/
  DemoEditor        loads GET /api/v1/demo/building-model → building store (public, "/")
  ProjectEditor     /projects/[id]: version selector, loads GET …/versions/{vid} → building store;
                    "New design" drawer (features/generation: SpecForm → validate → generate job
                    → progress by real job stage → opens the new version), design report drawer
                    (features/versions/ReportPanel), start view for projects without versions
  BuildingEditor    layout: left panel | viewport | properties; toolbar under the viewport
                    (≥1024 px three columns; narrower screens stack viewport first)
  LeftPanel         project summary · floors (All / Floor 1 / Floor 2) · layers · inspection · rooms
  PropertiesPanel   model-driven properties of the selection
  ViewerToolbar     camera presets, reset, perspective/orthographic, scene stats
viewer/
  BuildingViewer    <Canvas shadows="percentage" frameloop="demand">
  ModelRoot         the model->world group; ElementMesh per descriptor; selection outline
  CameraRig         drei OrbitControls (rotate / zoom / pan), perspective + orthographic cameras,
                    animated presets
  SceneEnvironment  hemisphere + ambient + shadowed sun, ground disc, infinite grid
  SectionPlane      horizontal clipping plane (renderer clipping planes)
stores/ (Zustand, one concern each)
  project-store · building-store · selection-store · viewer-store (floors, inspection,
  projection, section, camera requests) · layer-store
```

| Feature | Behaviour |
|---|---|
| Rotate / zoom / pan | Left-drag orbit, wheel zoom, right-drag pan (damped) |
| Camera presets | Exterior, Front (street/south), Rear (garden/north), Top, Floor 1, Floor 2, Interior; Reset view = exterior. Presets animate (700 ms) |
| Floor isolation | All / Floor n: levels above hidden, levels below ghosted (12 % opacity, not pickable), roof hidden; choosing a floor frames it |
| Layers | Architecture, Structure (load-bearing facades, slabs, stair), Furniture toggle independently; Plumbing, Electrical, HVAC, Fire safety, Landscaping are defined but *planned* |
| Inspection | Roof, exterior walls (with their doors/windows), furniture, section cut with height slider |
| Interior | Camera at eye height (1.6 m) in the living room with that floor isolated |
| Openings follow hosts | A door/window is hidden whenever its host wall is hidden (layer or facade toggle) |

## 15. Known limitations (Phase 1)

- Gable roofs have no gable-end wall infill (the demo uses a hip roof); shed roofs are not implemented.
- Walls are single solids with face finishes; build-up layers (insulation, block, plaster) are not modelled or rendered yet.
- Door leaves are always drawn closed; no swing arcs. Windows have one pane behind the mullions.
- No room labels, ceilings, skirting, stair nosings or stair stringers.
- Selection is single-element; no hover highlight (cursor only), no multi-select or "select parent".
- Section cut is horizontal only, global (also clips grid/ground); no section fill (hatching).
- Walk (first-person) mode, plan (2D) view and measurement tools are not implemented (Phase 8).
- Furniture is procedural placeholder geometry; the GLB asset hook exists but no assets are registered and the viewer does not load GLBs yet.
- `ResizeObserver`-driven canvas sizing: in environments that throttle rendering (hidden embedded browser panes) the canvas initialises on the first interaction; normal browser tabs are unaffected.
- `THREE.Clock` deprecation warning comes from React Three Fiber internals.

## 16. Layout engine (spec → model) — ☑ Phase 2

Code: `apps/api/app/modules/layout/` (pure domain module; no I/O, clock or global randomness). Entry point:

```python
generate_layout(spec, rules_profile, *, id_namespace, seed=0, config=DEFAULT_CONFIG,
                previous_ids=None, material_ids=None) -> LayoutResult(model, warnings, notes, metrics)
# raises LayoutError(code="LAYOUT_INFEASIBLE" | "LAYOUT_INVALID", message, issues)
```

Scope v1: rectilinear plans, 1–3 storeys, one rectangular house footprint stacked on every storey, plus an attached single-storey garage (L-shaped ground floor), cantilevered balconies and ground-floor terraces. Every minimum comes from the active `BuildingRulesProfile` ([building-model.md](building-model.md) §10); construction defaults (wall/slab thicknesses, preferred door/window sizes, default room areas, search parameters) live in `LayoutConfig` (`config.py`) and are versioned with `ENGINE_VERSION` (`layout@1.0.0`).

### 16.1 Plan scheme

Every storey is a **double-loaded corridor**: a street-side band (south, depth `Ds`), a corridor band (1.2 m) and a garden-side band (north). The **stair core** sits in the street band at the same x on all storeys; on the ground floor it is part of the **entrance hall** (open to the corridor), with the front door in the hall. Every room spans its band from the corridor to the facade, so it is reachable and gets a window — except small service rooms, which are **tucked** against the corridor inside a larger room's column; that room wraps around them on the facade side (L-/T-shaped rooms). En-suites and walk-in closets are tucked into (or placed next to) their bedroom and opened from it.

```
 y=D  +--------+-----------+--------------------+    garden (north): living, dining, kitchen /
      |  ...   |  Living   |  Kitchen & dining  |    master bedroom (+ balcony / terrace door)
      |        +---+       |                    |
 Ds+C +--------+WC +-------+--------------------+
      |               Corridor                  |
 Ds   +-----+--+---------+--------+-------------+    street (south): hall + stair core,
      | Hall|St|  Study  |Laundry | Bedroom ... |    service rooms, other rooms
      |  ⌂  |ai|         |        |             |
 y=0  +-----+rs+---------+--------+-------------+
     x=0                                      x=W      garage annex at x<0 or x>W
```

Stair core: `lanes = storeys − 1`, one straight flight per lane (`design_stair`: risers = ⌈f2f / riser_max⌉, tread from the 2R+T comfort target, all within the rules). Flight 0 rises north and arrives at the corridor; for three storeys flight 1 rises south from the corridor in the second lane and arrives at a landing over the first flight (a switchback without a mid-landing). Upper floors get walled voids over arriving flights and slab holes cut to the inner wall faces. `Ds ≥ half exterior wall + landing_min_depth + run`.

### 16.2 Pipeline

```
1. Program     program.py   spec rooms -> RoomRequests (instances, rule minimums, zones, attached suites);
                            default target areas scaled to fill the requested area (service ±30 %)
2. Levels      planner.py   fixed levels kept; bedrooms up, public rooms down, one bathroom per
                            bedroom floor; greedy balancing of room area vs. level capacity
3. Skeletons   planner.py   footprint W x D per aspect (0.5-1.8) at the requested area, street-band
                            depth options around an even split, core position (5) x hall side (2),
                            compact hall for small floors; plot / max-footprint limits
4. Zoning      planner.py   per level and seeded variant: rooms (with tucked service rooms) assigned
                            to bands by fill ratio + zoning penalties (living to the garden, balcony
                            hosts to their facade, open-plan partners in one band), local search
                            (move / swap / one-for-two / detach a bathroom into an empty strip)
5. Subdivision planner.py   units ordered by adjacency affinity; widths by flex-weighted water filling
                            with rule minimums (width, door frontage, area) on a 5 cm grid
6. Score       planner.py   area error (explicit targets x2, quadratic), room proportions, zoning,
                            unmet adjacency/open plan, footprint aspect, wasted strips, GFA error
7. Regions     regions.py   corridor, hall, stair core (void / staircase / landing), rooms, garage,
                            balconies, terraces; open edges (hall-corridor, open plan, stair arrivals;
                            open-plan pairs across the corridor open onto it)
8. Walls       regions.py   interior walls where two regions meet (maximal runs, vertical runs split at
                            X-crossings); exterior loop per storey; garage walls end at the house face
9. Elements    build.py     doors (front, corridor doors near the core, suites from their bedroom,
                            garage, sliding balcony/garden doors), windows (glazing ratio per style,
                            upper sills >= guard height), slabs (+ stair holes, balcony, terrace),
                            stairs + railings, roofs (flat/gable/hip + flat garage roof), relationships,
                            furniture (furnish.py: per-room templates clear of door zones)
10. Validate   engine.py    model invariants + reachability; the best-scoring candidate that validates
                            wins (up to 6 are built)
```

Determinism: the only randomness is `random.Random(f"{seed}:{skeleton}:{variant}")`; all ties break on stable keys (never object identity or hash order — a test runs the engine under two `PYTHONHASHSEED`s). Same spec + seed + profile + config + id namespace ⇒ byte-identical model JSON. Typical runtime: 0.05–1 s for the reference specs.

### 16.3 What the engine reports

- **Deviations** (`LayoutResult.warnings`): explicit room targets off by > 15 %, gross floor area off by > 5 %, unmet `adjacent_to`/`open_to` — never hidden; shown in the version's design report.
- **Notes**: derived floor area, rooms enlarged/reduced to fill the area, empty street-side strips turned into landing space, balconies/terraces moved to another host room.
- **Infeasibility** (`LAYOUT_INFEASIBLE`): the most frequent rejection reasons of all candidates (e.g. "footprint wider than the plot allows", "rooms do not fit the garden-side band at their minimum widths", "3.1 m needs 17 risers …").

### 16.4 Tests

`tests/layout/`: 10 reference specs (`data/fixtures/specs`, incl. the 280 m² 2-storey 4-bed example, a 3-storey villa, bungalows, a narrow plot, no area given) must validate, be fully reachable, have no rules findings, deliver the program (counts, levels, suites, garage/balcony/terrace, GFA ± 3 %) and match their **golden files** (`data/fixtures/golden/*.golden.json`: footprint, rooms + areas, counts, warnings, model sha256; update deliberately with `pnpm golden`). Hypothesis generates random in-scope specs and asserts invariants, reachability, containment and reproducibility. `data/fixtures/generated-house.model.json` is rendered by the web engine tests.

### 16.6 Component types (layout@1.1.0, Phase 3.5 K2)

`generate_layout(..., type_set: TypeSet | None = None)`. The engine never reads the catalog; the generation pipeline passes an approved, rules-checked `TypeSet` (docs/knowledge.md §3.4) or `None`.

- **Design values**: `layout/types.py: config_with_types(config, type_set)` returns the effective `LayoutConfig`: each value a type defines (wall/slab/roof thickness via assemblies, door width/height, garage door width per car, window presets, service/stair windows, stair width, railing heights and post spacing) replaces the default; roles without a type keep `LayoutConfig`. Values the config holds once (door thickness, post spacing, main and garage roof thickness) must agree across types, otherwise `LAYOUT_INVALID`. The geometry code is unchanged.
- **Roles**: every generated wall, slab, roof, stair, railing, door and window has a role (`building/types.py TYPE_ROLES`); doors and windows record theirs where the engine chooses them (e.g. `door.wet_room`, `window.service`, `window.stair`).
- **Attachment**: `build.attach_types` sets `type_ref` and the type's fixed materials, and copies the used types and their assemblies into the model (sorted); rooms and furniture stay untyped. `metadata.generator` names the type pack and mapping.
- **Determinism and geometry**: with the generic types the effective config equals `LayoutConfig` (tested), so every reference spec generates the same geometry fingerprint typed and untyped (`tests/layout/test_types.py`, also under two `PYTHONHASHSEED`s). The web geometry builders are unchanged (`engine@1`); a web test asserts type metadata never changes the scene hash.
- `ENGINE_VERSION` is `layout@1.1.0` (models are BuildingModel 1.1.0). The golden files changed only in `engine_version`, the full-model hash and the new fields; every `geometry_sha256` is identical to the pre-K2 baseline.

### 16.5 Limitations (layout@1.0.0)

- One plan type (double-loaded corridor, street on the south); no L/U-shaped houses except the garage annex, no courtyards, no sloped sites, no basements.
- Straight flights only; the 3-storey core is a conceptual switchback (the pocket under the second flight belongs to the staircase room). Storey height is limited to one flight (≤ 16 risers → ≤ 3.04 m with the generic profile).
- Rooms only span a full band or are tucked against the corridor; small houses (< ~60 m² per storey) lose a large share to hall, core and corridor.
- Windows are sized by glazing ratio per facade segment, not by view/orientation; no skylights; no guards for low upper-floor sills (sills are raised to the guard height instead).
- Furniture is basic and skipped when it does not fit (e.g. shallow balconies).
- Gable roofs inherit the Phase 1 renderer limitation (no gable-end infill).

## 17. MEP generator (schematic) — Phase 6

Rule-based after layout: plumbing (fixtures from wet-room templates, stack, orthogonal drains at 1–2 %, supplies), electrical (board, outlets ≤ 3.6 m apart, lights, switches at the latch side, circuits), HVAC (split units or ducted trunk + branches). Orthogonal A* routing on a 0.1 m grid, deterministic tie-breaking. Labelled **schematic, not for construction**.

## 18. Infrastructure visualization — Phase 6

- Discipline palette: cold water `#2f80ed`, hot water `#eb5757`, drain `#8d6e63`, vent `#9e9e9e`, power `#f2c94c`, lighting `#f2994a`, supply air `#56ccf2`, return air `#bb6bd9`, refrigerant `#27ae60`.
- Any MEP layer on → architecture switches to x-ray (transparent, `depthWrite=false`, not pickable) — the ghost material variant already provides this.
- "Isolate system" highlights `part_of_system` members; "trace" walks `connected_to` edges to the source.
