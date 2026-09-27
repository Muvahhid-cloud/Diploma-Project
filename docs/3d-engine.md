# 3D Engine

Status: **Accepted (v0.2)** В· Last updated: 2026-09-27

The "3D engine" is four parts with hard boundaries:

| Part | Location | Input в†’ Output | Purity |
|---|---|---|---|
| **Layout engine** | Python `modules/layout` | Spec + RulesProfile + seed в†’ architectural BuildingModel | Pure, deterministic, seeded |
| **MEP generator** | Python `modules/mep` | Architectural model в†’ model + MEP elements | Pure, deterministic |
| **Geometry builders** | TS `apps/web/src/engine` | BuildingModel + EngineConfig в†’ `RenderDescriptor[]` | Pure functions, no React, no randomness |
| **Viewer** | TS `apps/web/src/viewer` (R3F) | RenderDescriptors + view state в†’ interactive scene | React |

Positions of everything are decided in Python (or, in Phase 1, by the hand-authored model). The browser only **tessellates** what the model already states.

### Determinism contract

> **Same BuildingModel + same EngineConfig в‡’ identical geometry** (same vertex buffers, same order, same material keys).

- Builders never call `Math.random`, `Date.now`, or read global mutable state.
- Iteration order is always by a defined sort (element `id` or explicit `order` field), never by `Map`/object insertion from network order.
- Floating-point: inputs are rounded to 1 mm; builders use only deterministic arithmetic (no GPU-side generation of base geometry).
- `EngineConfig` (`{ lod, wallLayerDetail, arcSegments, version }`) is explicit and part of memo keys.
- Verified by Vitest snapshot tests: a hash of all vertex/index buffers for each fixture model is committed; any change must be deliberate.

Randomness exists **only** in the layout engine and only via an explicit `seed` stored on the model.

---

## 1. Coordinate system

| Property | BuildingModel (backend & data) | Three.js world (viewer) |
|---|---|---|
| Handedness | Right-handed | Right-handed |
| Up axis | **+Z** | **+Y** |
| Plan axes | +X = east, +Y = north | +X = east, **в€’Z** = north |
| Origin | South-west corner of ground-floor footprint, Z = 0 at ground-floor finished floor level (FFL) | Same physical point |
| Angles | Radians, counter-clockwise positive seen from above (+Z) | Radians |

Element `position` is an element-local anchor (defined per type in [building-model.md](building-model.md) В§3.3). Absolute elevation = `level.elevation_m + position.z`.

## 2. Architectural units

| Quantity | Unit | Precision on serialization |
|---|---|---|
| Length | meter (m) | 0.001 (1 mm) |
| Area | mВІ | 0.01 |
| Volume | mВі | 0.001 |
| Angle | radian | 1e-6 |

Comparisons use `EPS = 1e-4 m`. The UI may *display* mm/cm, but data is always meters. Imperial units are never stored.

## 3. Model в†” Three.js coordinate conversion

There is **exactly one** conversion, applied by the viewer's root group:

```tsx
<group name="model-root" rotation={[-Math.PI / 2, 0, 0]}>  {/* Z-up model в†’ Y-up world */}
  ...all building content, positioned in model coordinates...
</group>
```

Mapping: model `(x, y, z)` в†’ world `(x, z, в€’y)`.

- Builders emit geometry and matrices in **model space** (Z-up). They never know about Three.js world orientation.
- Camera, lights, grid, and environment live in world space (Y-up) outside `model-root`.
- Pointer hits (`event.point`) are in world space; convert to model space with `modelRoot.worldToLocal(point.clone())` вЂ” helper `engine/math/coords.ts: worldToModel / modelToWorld`, the only functions allowed to encode the mapping.
- Sun direction is computed in model space from `site.north_angle_rad` and transformed once.

## 4. Wall generation strategy

Model: wall = axis from `position` along `rotation.z` with `length`, `thickness`, `height`, `alignment` (`center | left | right` of axis).

```
axis start S = position.xy,  direction d = (cos Оё, sin Оё),  normal n = (в€’sin Оё, cos Оё)
alignment offset: center в†’ [в€’t/2, +t/2], left в†’ [0, +t], right в†’ [в€’t, 0]  (along n)
```

Builder steps (`engine/builders/wall.ts`):

1. Compute the **wall-local frame**: u along d (0 вЂ¦ length), v along n (thickness), w up (0 вЂ¦ height).
2. Collect hosted openings (В§5), sorted by `offset` then `id`; clamp to wall bounds (invalid ones are reported, not rendered).
3. **Panel decomposition** (no CSG): walk along u; for each gap between openings emit a full-height box; for each opening emit a *sill panel* (0 в†’ sill) and a *lintel panel* (sill+height в†’ wall height) where non-zero.
4. **Corner joins**: at L/T junctions (detected from a precomputed junction map in `BuildContext`, built from wall endpoints within EPS), exterior walls are extended by half the joining wall's thickness so corners close without overlaps; interior walls stop at the face of the wall they meet. Join resolution is deterministic (sorted by wall id).
5. High LOD: when `build_up` layers exist, each panel is split along v into layer slabs with their own material keys (render/insulation/block/plaster). Low LOD: one box per panel with the finish material outside and plaster inside via two material groups.
6. UVs are world-scaled (1 UV unit = 1 m) so textures tile consistently.

## 5. Opening generation strategy

Doors and windows live in **host-wall-local coordinates**: `position.x` = offset from wall start along the axis, `position.z` = sill height (0 for doors), `dimensions.width/height`.

- The wall builder cuts the void (via panel decomposition, В§4); the opening builder fills it.
- **Window** (`engine/builders/window.ts`): frame = 4 boxes (profile 60вЂ“80 mm), glazing panes per `window_kind` (fixed: 1, casement: 1вЂ“2, sliding: 2, panoramic: n panes with mullions every в‰¤ 1.5 m), sill board outside. Glass в†’ shared glass material.
- **Door**: frame (3 boxes, no bottom), leaf (box, 40 mm) rotated per `swing` to a fixed "closed" state; `opens_into` decides which wall face the leaf sits on. Garage door: sectional panel box.
- Opening transform = wall transform Г— translate(offset, center of thickness, sill). Moving/rotating a wall moves its openings automatically.
- Validation before build: opening fully inside wall, no overlap with siblings. Invalid в†’ skipped + reported to dev overlay.

## 6. Room geometry generation

A room is a **space**, not a solid. Model: `properties.boundary` = closed CCW polygon (rectilinear in v1) in level coordinates, typically wall *centerlines*.

- **Floor finish**: boundary inset to the inner wall faces (`shapely`-equivalent offset in TS via rectilinear inset helper) в†’ `ShapeGeometry` at `z = +0.002` (avoids z-fighting with slab) with the room's floor finish material.
- **Pick volume**: invisible box/extruded prism of the room at 0.05 m height used for selecting a room by clicking its floor.
- **Label**: room name + area as a screen-space `Html`/sprite at the polygon centroid (label anchor precomputed, deterministic).
- **Ceiling** (optional, high LOD): same inset polygon at `level.height в€’ slab thickness`, hidden in cutaway.
- Area/perimeter shown in the inspector come from the model (computed in Python), never from the mesh.

## 7. Floor (slab) generation

Model: `slab` with `outline` (+ `holes`, e.g. stairwell), `thickness`, `slab_kind`.

- `THREE.Shape(outline)` + `holes` в†’ `ExtrudeGeometry({ depth: thickness, bevelEnabled: false })`, positioned so the **top face is at the level's FFL** (slab extends downward).
- Ground slab sits on a simple foundation strip (optional box ring under exterior walls, structure layer).
- Balcony slabs: `slab_kind = balcony`, cantilevered, with a railing element.
- Triangulation uses Three's earcut; outlines are normalized (CCW, first vertex = lowest x then y) before building to keep triangulation deterministic.

## 8. Roof generation

Model: `roof` with `roof_type`, `outline`, `pitch`, `overhang`, `thickness`, `ridge_axis`.

| Type | Algorithm |
|---|---|
| `flat` | Outline offset by overhang в†’ extruded slab (thickness) + parapet boxes along perimeter (height from properties, default 0.3 m) |
| `shed` | Plane rising along `ridge_axis` at `pitch`; closed with gable-end triangles |
| `gable` | Rectangle only in v1: ridge along `ridge_axis` at `h = (span/2)В·tan(pitch)`; two sloped planes + two gable triangles; thickness by offsetting along the plane normal |
| `hip` | Rectangle only in v1: closed-form straight skeleton (ridge length = long side в€’ short side), four sloped faces |

Non-rectangular outlines with pitched roofs are rejected by validation in v1 (flat allowed for any rectilinear outline). The roof sits on top of the highest level's walls (`elevation + height`).

## 9. Other element builders

| Element | Technique |
|---|---|
| `stair` | Treads/risers generated from `risers`, `riser_h`, `tread_d`, `width`; each tread a box; instanced; stringers as two extruded profiles; straight / L / U from `stair_type` |
| `railing` | Top rail + balusters (instanced) or glass panel |
| `column`, `beam` | Boxes |
| `furniture` | Parametric primitives in v1 (bed, sofa, table, chairs, wardrobe, kitchen counter, island, toilet, basin, shower tray, car placeholder) built from boxes/cylinders keyed by `furniture_kind`; instanced per kind+dimensions. GLB assets later via `catalog_id` |
| `pipe_segment`, `duct_segment` | Cylinder/box oriented startв†’end; joints as small spheres; instanced per (size, material) |
| `conduit_run` | `TubeGeometry` along polyline, low radial segments |
| `fixture`, `equipment`, `terminal` | Parametric primitives; GLB later |

## 10. Object UUID mapping & mesh в†” BuildingModel mapping

Every renderable thing traces back to exactly one model element:

```ts
interface RenderDescriptor {
  elementId: string;          // UUID of the BuildingModel element  (1 element в†’ 1..n descriptors)
  part: string;               // "panel:0", "sill:1", "frame", "glass", "tread:7" вЂ” stable, deterministic
  levelId: string | null;
  layer: Layer;
  geometry: THREE.BufferGeometry;   // model space
  matrix: THREE.Matrix4;            // element в†’ model space
  materialKey: string;
  instanceKey?: string;             // identical geometry+material в†’ InstancedMesh
}
```

Mapping structures (built once per model load, in `engine/scene-index.ts`):

| Map | Purpose |
|---|---|
| `elementId в†’ RenderDescriptor[]` | highlight / hide / fit-to-selection for an element |
| `mesh.userData = { elementId, part }` | raycast hit в†’ element (non-instanced) |
| `instancedMesh.userData.instanceElementIds: string[]` | `instanceId` в†’ elementId (instanced) |
| `levelId в†’ elementId[]`, `layer в†’ elementId[]` | isolation & layer toggles without scanning |
| `elementId в†’ Element` | inspector data |

Rules: meshes never hold copies of element properties; `userData` holds IDs only. Openings resolve to themselves (clicking a window selects the window, not the wall). Room pick volumes resolve to the room.

## 11. Object selection flow

```
pointerdown/up on canvas (click = moved < 4 px)
  в†’ R3F raycast (sorted by distance; hidden/ghosted/x-ray layers excluded via raycast filter)
  в†’ first hit в†’ { elementId } from userData (or instanceId lookup)
  в†’ modifiers: Shift = add/remove from selection; Alt = select parent (window в†’ host wall, element в†’ room)
  в†’ viewStore.select(ids)                       (Zustand; single source of selection)
  в†’ subscribers:
       SelectionOutline  вЂ“ outlines descriptors of selected ids (postprocessing Outline)
       Inspector panel   вЂ“ reads modelStore.elementsById.get(id): UUID, type, name, layer, level,
                            position, rotation, dimensions, material, properties, relationships
                            (relationship targets are clickable в†’ select target)
       Model tree        вЂ“ scrolls to & highlights node
  в†’ click on empty space в†’ clear selection; Esc в†’ clear
```

Selection is by UUID, so it survives scene regeneration and version switches when the element still exists (В§12). Hover highlight uses the same path with a throttled `hoveredId`.

## 12. Scene regeneration strategy

When the model changes (new version loaded, operations applied, draft updated):

1. **Diff by element**: compute a content hash per element (canonical JSON of the element + hashes of its hosted openings + EngineConfig). Compare with previous hashes.
2. **Rebuild only changed elements**: unchanged elements reuse cached descriptors (memo cache keyed by hash, LRU-bounded). Removing an element disposes its geometries if no other entry references them.
3. **Dependency invalidation**: a wall rebuilds when any hosted opening changes; neighbors rebuild when a junction changes (junction map diff); rooms rebuild when their boundary changes.
4. **React reconciliation**: `<ElementMesh key={elementId + ':' + part}>` so React updates in place; materials are shared and never recreated.
5. **View state preserved**: camera, selection (filtered to ids that still exist), isolated level, visible layers.
6. `frameloop="demand"`: invalidate once after a rebuild batch.

Whole-scene rebuild happens only on EngineConfig change (e.g. LOD switch) and still goes through the same cache.

## 13. Performance strategy

Target: 3вЂ“5k elements, geometry build < 300 ms, в‰Ґ 50 fps on a mid-range laptop (integrated GPU), memory < 500 MB.

| Stage | Technique |
|---|---|
| v1 (default) | One mesh per descriptor; shared material cache; memoized geometries; **instancing** for furniture, fixtures, treads, balusters, pipe runs; `frameloop="demand"`; shadows only from the sun, shadow map 2048, static (`autoUpdate=false`, refresh on change) |
| Draw calls | Merge static, non-selectable parts (e.g. wall build-up layers of one wall) into one geometry per element with material groups |
| When > ~1500 draw calls | `THREE.BatchedMesh` per (level, layer, material), keeping per-element picking via batch ids в†’ elementId |
| Build time | Builders are pure в†’ move to a **Web Worker** (transfer ArrayBuffers) if main-thread build exceeds budget |
| LOD | `low`: no build-up layers, no mullions, simplified furniture; chosen by camera distance / element count |
| Raycasting | `three-mesh-bvh` for accelerated raycasts on larger meshes; raycast disabled on hidden/ghosted layers |
| Monitoring | Dev overlay (r3f-perf) showing draw calls, triangles, build ms; perf budget test in CI on the fixture house (build time only) |

---

## 14. Layout engine (spec в†’ model) вЂ” Phase 2

Scope v1: rectilinear plans, 1вЂ“3 storeys, one rectangular (or L-shaped with garage) footprint. All minimums come from the active `BuildingRulesProfile` ([building-model.md](building-model.md) В§10).

```
1. Program        вЂ“ expand spec rooms into RoomRequests (target/min area, min width from rules profile,
                    zone public/private/service, level assignment)
2. Footprint      вЂ“ per-level net area в†’ WГ—D (aspect 1.2вЂ“1.8, fit plot/setbacks); garage в†’ L-annex on level 0
3. Vertical core  вЂ“ stair (+ wet stack zone) placed valid on all levels; stair geometry from rules
4. Zoning         вЂ“ split each level into zone bands (public to street/garden, private away, service near core)
5. Subdivision    вЂ“ slicing-tree / squarified treemap partition to hit target areas
6. Circulation    вЂ“ corridors (min width from rules) so entrance reaches every room
7. Walls          вЂ“ from room boundary edges: shared в†’ interior, perimeter в†’ exterior; merge collinear
8. Openings       вЂ“ doors along adjacency graph; windows on exterior walls by room type/orientation/style
9. Slabs & roof   вЂ“ per level; stair holes; balcony slabs; roof per spec
10. Score         вЂ“ area error, aspect penalties, adjacency, daylight, corridor area, wet-room clustering
```

Stages 4вЂ“8 run for N candidates (default 32) with seeds derived from the model seed; best valid candidate wins. Plain Python + `shapely`; no ML. Engine versioned; output change for a fixed seed is a breaking change caught by golden files.

## 15. MEP generator (schematic) вЂ” Phase 6

Rule-based, after layout: plumbing (fixtures from wet-room templates, vertical stack, orthogonal drain routing at 1вЂ“2 % slope, supply from water heater), electrical (board, outlets в‰¤ 3.6 m apart, lights per room, switches at door latch side, circuits), HVAC (split units or ducted trunk + branches). Orthogonal grid A* routing (0.1 m) with deterministic tie-breaking. Labelled **schematic, not for construction**.

## 16. Infrastructure visualization

- Discipline palette (`engine/materials/discipline.ts`): cold water `#2f80ed`, hot water `#eb5757`, drain `#8d6e63`, vent `#9e9e9e`, power `#f2c94c`, lighting `#f2994a`, supply air `#56ccf2`, return air `#bb6bd9`, refrigerant `#27ae60`.
- Any MEP layer on в†’ architecture switches to x-ray (transparent, `depthWrite=false`, excluded from raycast).
- "Isolate system" highlights `part_of_system` members; "trace" walks `connected_to` edges to the source.

## 17. Viewer composition & interaction

```tsx
<Canvas shadows dpr={[1, 2]} frameloop="demand">
  <SceneLighting/>            {/* hemisphere + directional sun */}
  <Environment preset="city"/>
  <group name="model-root" rotation={[-Math.PI / 2, 0, 0]}>
    {levels.map(l => <LevelGroup key={l.id} level={l}/>)}
  </group>
  <Grid/> <ContactShadows/>
  <CameraRig/>                {/* drei CameraControls: orbit/zoom/pan; fit building/selection */}
  <SelectionOutline/>
  <SectionPlane/>
</Canvas>
```

| Feature | Behavior |
|---|---|
| Rotate / zoom / pan | Left-drag orbit, wheel zoom (to cursor), right-drag / Shift-drag pan; double-click element = fit to it; `F` = fit building |
| Floor isolation | `viewStore.isolatedLevelId`: levels above hidden, levels below ghosted (opacity 0.15, no raycast), roof hidden |
| Layers | `viewStore.visibleLayers` (architecture, structure, furniture, plumbing, electrical, hvac, site) |
| Inspector | Shows every element field; relationships clickable |
| Interior (Phase 1+) | Cutaway = isolation + section plane at FFL + 1.2 m |
| Walk mode / plan view | Phase 8 |
