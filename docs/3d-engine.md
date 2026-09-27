# 3D Engine

Status: **Accepted (v0.1)**

The "3D engine" is three distinct parts with a hard boundary between them:

| Part | Language / location | Input → Output | Purity |
|---|---|---|---|
| **Layout engine** | Python `modules/layout` | Spec → architectural BuildingModel | Pure, deterministic, seeded |
| **MEP generator** | Python `modules/mep` | Architectural model → model + MEP elements | Pure, deterministic |
| **Geometry builders** | TS `apps/web/src/engine` | BuildingModel element → `THREE.BufferGeometry` + material key | Pure functions, no React |
| **Viewer** | TS `apps/web/src/viewer` (R3F) | Render descriptors → interactive scene | React |

Positions of everything are decided in Python. The browser only *tessellates* what the model already says.

---

## 1. Layout engine (spec → rooms, walls, openings)

Scope v1: rectilinear plans, 1–3 storeys, one rectangular (or L-shaped with garage) footprint.

### Stages

```
1. Program        – expand spec rooms (count) into RoomRequests with target/min area, min width,
                    zone (public/private/service), level assignment
2. Footprint      – per-level net area → footprint W×D (aspect 1.2–1.8, fit plot/setbacks);
                    attached garage → L-shape annex on level 0
3. Vertical core  – place stair (and wet-stack zone) at a location valid on all levels
4. Zoning         – split each level footprint into zone bands (public towards street/garden,
                    private away, service near core/garage)
5. Subdivision    – within each zone: slicing-tree / squarified-treemap partition to hit target areas
6. Circulation    – insert corridor/hall where rooms lack door access; ensure entrance → all rooms
7. Walls          – derive walls from room boundary edges: shared edges → interior walls,
                    perimeter → exterior walls; merge collinear segments; assign thickness/build-up
8. Openings       – doors along adjacency graph (spanning tree + required adjacencies);
                    windows on exterior walls by room type, orientation, window_style
                    (panoramic → floor-to-ceiling on living/kitchen façades)
9. Slabs & roof   – slab per level from footprint (+ stair hole, + balcony slabs); roof per spec
10. Score         – objective: area error, aspect-ratio penalties, adjacency satisfaction,
                    daylight (habitable rooms on good façades), corridor area, wet-room clustering
```

Stages 4–8 run for **N candidates** (default 32) with seeds derived from the model seed; the best-scoring valid candidate wins. Scores are returned for transparency. Everything is plain Python + `shapely` for polygon ops; no ML.

The engine is versioned (`engine_version`). A change in output for a fixed seed is a **breaking change** caught by golden-file tests.

## 2. MEP generator (schematic)

Rule-based, runs after layout, per level:

- **Plumbing**: wet rooms get fixtures from templates (bathroom: wc, basin, shower/bath). A vertical stack is placed in the wet core; drains route orthogonally in the floor zone to the stack with 1–2 % slope; cold/hot supply routes from the water heater along walls at fixed heights. Pipe diameters from fixture-unit tables (simplified).
- **Electrical**: distribution board near entrance/garage; outlets every ≤ 3.6 m of wall perimeter per habitable room + kitchen counter rules; ceiling light per room (grid for large rooms); switches beside doors (latch side). Circuits grouped by room/load; conduit polylines route along walls to the board.
- **HVAC**: by `services`: split AC → indoor unit per bedroom/living + refrigerant lines to outdoor unit; ducted → trunk duct along corridor ceiling, branches to diffusers per room, return grille in hall; heat pump/boiler equipment in plant room/garage.

Routing uses a coarse orthogonal grid (0.1 m) with A* avoiding openings; deterministic tie-breaking. Output is clearly labelled **schematic, not for construction**.

---

## 3. Geometry builders (browser)

```ts
// engine/builders/types.ts
export interface BuildContext {
  levels: Map<string, Level>;
  elementsById: Map<string, Element>;
  hostedOpenings: Map<string, Opening[]>;   // wallId → doors/windows
  lod: 'low' | 'high';
}
export interface RenderDescriptor {
  elementId: string;
  levelId: string | null;
  layer: Layer;
  geometry: THREE.BufferGeometry;           // in element-local space
  matrix: THREE.Matrix4;                    // model space (Z-up)
  materialKey: string;                      // → shared material cache
  instanceKey?: string;                     // for instancing identical fixtures
}
export type Builder<E extends Element> = (el: E, ctx: BuildContext) => RenderDescriptor[];
```

A registry maps `element.type → builder`. Builders are **pure**, unit-tested in Vitest against shared fixtures, and memoized by `(element hash, hosted openings hash, lod)`.

| Element | Technique |
|---|---|
| `wall` | **Panel decomposition, no CSG.** Sort hosted openings by offset; emit box panels: full-height between openings, sill panel below and lintel panel above each opening. Build-up layers → optional per-layer boxes at high LOD. |
| `door` / `window` | Frame (4 thin boxes) + leaf/glass pane; glass uses a shared `MeshPhysicalMaterial` (transmission off for perf, opacity 0.3). Panoramic = multi-pane with mullions. |
| `slab` | `THREE.Shape` from outline with holes → `ExtrudeGeometry` (depth = thickness). |
| `room` | Floor finish as thin `ShapeGeometry` inset from walls; invisible by default, pickable; label sprite at centroid. |
| `roof` | Flat: extruded outline + parapet. Gable/hip: computed from rectangular outline (straight-skeleton for rectangles is closed-form). |
| `stair` | Generated treads/risers as boxes (instanced) + stringers. |
| `pipe_segment`, `duct_segment` | Cylinder (pipe) or box (rect duct) oriented start→end; elbows as small spheres/tori at joints. Instanced per (diameter, material). |
| `conduit_run` | `TubeGeometry` along polyline, low radial segments. |
| `fixture`, `equipment`, `furniture` | Simple parametric primitives in v1; later GLB assets from a catalog (`useGLTF`), keyed by `catalog_id`, instanced. |

## 4. Viewer (React Three Fiber)

```
<Canvas shadows dpr={[1, 2]} frameloop="demand">
  <SceneLighting/>                 // hemisphere + directional sun (from site north angle), soft shadows
  <Environment preset="city"/>     // drei
  <group rotation-x={-Math.PI/2}>  // ★ the ONLY Z-up → Y-up conversion
    {levels.map(l => <LevelGroup key={l.id} level={l}/>)}   // visibility per isolation state
  </group>
  <Grid/> <ContactShadows/>
  <CameraRig/>                     // orbit | walk | top (plan) — drei CameraControls / PointerLockControls
  <SelectionOutline/>              // postprocessing Outline on selected ids
  <SectionPlane/>                  // global clipping plane (renderer.localClippingEnabled)
</Canvas>
```

`frameloop="demand"` — only re-render on change (battery + fan friendly).

### Interaction features

| Feature | Implementation |
|---|---|
| Rotate / zoom / pan | drei `CameraControls` with smooth transitions; "fit to building" / "fit to selection" |
| Object selection | R3F pointer events; `userData.elementId`; click → `viewStore.select(id)`; hover highlight; inspector shows element fields; `Esc` clears |
| Floor isolation | `viewStore.isolatedLevelId`: levels above hidden, below ghosted (opacity 0.15); camera frames level; roof hidden |
| Interior view | (a) **cutaway**: hide roof + levels above + horizontal section plane at level + 1.2 m; (b) **walk mode**: first-person at 1.65 m eye height, WASD, collision against walls (simple 2D segment test) |
| Exterior view | default orbit with roof and site |
| Plan view | orthographic top camera per level with section at 1.2 m |
| Layers | `viewStore.visibleLayers`; MEP layer on → architecture x-ray (transparent, `depthWrite=false`) |
| Diff view | compare mode colors elements by diff status (added / removed ghost / modified) |
| Measurements (later) | snap to vertices; distance/area tool |

### Performance plan

Target: 3–5k elements, ≥ 50 fps mid-range laptop, geometry build < 300 ms.

1. v1: one mesh per render descriptor, shared materials, memoized geometries, instancing for repeated fixtures/pipes/treads.
2. When needed: `THREE.BatchedMesh` per (level, layer, material) keeping per-element picking via batch ids.
3. Geometry building moves to a **Web Worker** if main-thread build exceeds budget (builders are pure → trivially movable).
4. LOD: `low` hides build-up layers, mullions, fixture detail when zoomed out.

## 5. Materials

`engine/materials/` reads the generated material library (same YAML as costing) → cached `MeshStandardMaterial` keyed by `material_id` (+ variant: ghost, xray, diff-added…). Materials are never created per element.

## 6. Coordinate conversion

Model: Z-up meters. Three.js: Y-up. Builders emit geometry in **model space**; the single root group rotates −90° about X. Consequences: model (x, y, z) → world (x, z, −y). Nothing else in the codebase converts axes. Picking results convert back with the inverse root matrix.

## 7. Infrastructure visualization

- Discipline palette (constant in `engine/materials/discipline.ts`): cold water `#2f80ed`, hot water `#eb5757`, drain `#8d6e63`, vent `#9e9e9e`, power `#f2c94c`, lighting `#f2994a`, supply air `#56ccf2`, return air `#bb6bd9`, refrigerant `#27ae60`.
- Layer panel: toggle per discipline and per system; "isolate system" highlights all `part_of_system` members and dims the rest.
- Elevation-aware rendering: pipes in floor zone drawn slightly below finished floor; section planes reveal them.
- Clicking a pipe shows system, diameter, length, connected elements; "trace" walks `connected_to` edges and highlights the path to the source.
