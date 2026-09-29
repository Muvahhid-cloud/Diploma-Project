# Roadmap

Status: **Accepted (v0.2)** · Each phase ends with a demoable, tested increment. Phases are ordered to prove the riskiest link (spec → geometry → render) **before** investing in AI and polish.

Legend: ☐ not started · ◐ in progress · ☑ done

---

## Phase 0 — Foundations ☑
Goal: everything runs with one command; contracts in place. No building features yet.

- Monorepo scaffold: `apps/web` (Next.js, TS strict, Tailwind), `apps/api` (FastAPI, uv), `packages/schema` (placeholder until Phase 1)
- `docker-compose.yml`: postgres, api, web; `.env.example`; root `package.json` scripts + thin Makefile (`dev`, `test`, `lint`, `typecheck`, `schema`, `migrate`, `seed`)
- Core API: config (pydantic-settings), async DB session, error envelope, health (`/health`, `/health/db`), logging, disclaimer constant
- Alembic baseline; users + refresh_tokens; JWT auth (register/login/refresh/logout)
- Projects CRUD + ownership check
- Web: auth pages, project list, API client with Zod validation, TanStack Query setup, disclaimer footer
- CI (GitHub Actions): lint, type-check, tests, migration up/down against Postgres service, build

**Phase 0 verification checklist** (all must be green before Phase 1):

| Check | How | Result (2026-09-27, Windows dev machine) |
|---|---|---|
| Frontend setup | `pnpm build:web` succeeds; dev server serves `/` | ☑ Next.js 16.3 build OK; pages served |
| Backend setup | API starts; `GET /health` → 200 | ☑ |
| PostgreSQL connection | `GET /health/db` → 200; Alembic `upgrade head` / `downgrade base` succeed | ☑ PostgreSQL 16.2 (embedded via `pnpm db:local`); migration round-trip + model/migration drift tests pass |
| Docker Compose | `docker compose up --build` → db healthy, api healthy, web reachable | ☐ **Not verified** — Docker is not installed on the dev machine. Files written; CI `docker` job builds images |
| Environment configuration | `.env.example` complete; API fails fast with clear error on missing/unsafe vars | ☑ (tests cover async-driver URL, secret length, production guards) |
| Project structure | Matches `docs/architecture.md` §3–§5 | ☑ (domain modules stubbed as packages) |
| Lint / type check | `pnpm lint`, `pnpm typecheck` clean | ☑ ruff, ruff format, import-linter (2 contracts kept), mypy strict, ESLint, tsc |
| Basic tests | `pnpm test` | ☑ API 29 passed · web 13 passed |
| Manual E2E | register → project list → create → editor shell → reload keeps session → sign out → guarded redirect → login returns to `next` | ☑ in browser against local API + DB |
| CI-ready | `.github/workflows/ci.yml` | ☑ written (api / web / docker jobs); ☐ not yet run — no remote configured |
- **Exit**: sign up → create project → see empty editor, in Docker, CI green

## Phase 1 — Hand-authored model → procedural 3D (no AI, no layout) ☑
Goal: prove the highest-risk dependency — BuildingModel → deterministic procedural 3D → interactive viewer — completely independent of AI. **Done 2026-09-27.**

Delivered:

- Canonical Pydantic `BuildingModel` 1.0.0 (`apps/api/app/modules/building`) + invariant validator (`validation.py`) + `GET /api/v1/demo/building-model` (validates before serving)
- Codegen: `pnpm schema` → `packages/schema` (JSON Schema, generated TS types, runtime Zod validator via `z.fromJSONSchema`)
- Demo fixture `data/fixtures/demo-house.model.json` (`pnpm fixtures`): 2 floors, 12 × 10 m, 15 rooms (entrance, staircase, storage, bathroom, kitchen, corridor, living room, dining area; bedrooms 1–3, bathroom, corridor, study, balcony), 21 walls, 13 doors, 21 windows, 3 slabs (incl. stair void and balcony), straight stair, hip roof, 4 railings, 37 furniture items; stable uuid5 ids
- Shared material library `data/materials/library.json`
- TS geometry engine (`apps/web/src/engine`): MeshBuilder, wall joins + panel decomposition, builders for walls, doors, windows, room floors, slabs, stair, roof (flat/gable/hip), railings, furniture placeholders; scene graph with content-keyed geometry reuse; visibility rules; camera presets; selection mapping
- Viewer + editor at `/`: orbit/zoom/pan, 7 camera presets + reset, perspective/orthographic, selection with highlight, model-driven properties panel, floor isolation, layer manager, inspection toggles, section cut, room list

**Completion checklist** (verified 2026-09-27):

| Criterion | Result |
|---|---|
| Two-floor procedural house renders | ☑ (dev + production build) |
| Building comes from BuildingModel | ☑ served by the API, validated by Pydantic + Zod + integrity checks |
| Walls / rooms / doors / windows / floors / stairs / roof / furniture | ☑ all rendered from model elements (rooms as floor finishes) |
| Orbit, zoom, pan, camera reset | ☑ |
| Object selection + highlight + properties panel | ☑ (e.g. W-G01: Exterior wall, 12 m, 2.8 m, 0.3 m, Brick, UUID) |
| Floor isolation | ☑ All / Floor 1 / Floor 2 (lower floors ghosted, camera frames the floor) |
| Layer visibility | ☑ Architecture / Structure / Furniture; future layers registered as planned |
| Interior inspection | ☑ hide roof / exterior walls / furniture, isolate floors, section cut, interior camera |
| No major console errors | ☑ none from app code (one THREE.Clock deprecation warning from R3F internals) |
| Tests / lint / typecheck / production build | ☑ API 60 tests, web 95 tests; ruff, mypy, import-linter, ESLint, tsc clean; `next build` OK |
| Browser smoke test | ☑ dev server and production server |

Known limitations: see [3d-engine.md §15](3d-engine.md). Deferred from the original Phase 1 plan: `BuildingSpecification` Pydantic schema (moved to Phase 2, where it is first used) and storing the fixture as a project version (moved to Phase 2 together with the `project_versions` table).

## Phase 2 — Layout engine (spec → model) ☑
Goal: deterministic geometry from a spec. **Done 2026-09-28.**

Delivered:

- `BuildingSpecification` 1.0.0 (Pydantic, closed vocabularies, no geometry) → generated JSON Schema, TS types and Zod validator (`pnpm schema`); tier-2 spec checks against the rules profile (`rules/spec_checks.py`)
- `BuildingRulesProfile` schema + YAML loader with `extends` (`data/rules-profiles/generic-residential.v1.yaml`) and a model evaluator (`rules/model_checks.py`) whose findings carry `rule_ref`s
- Layout engine `layout@1.0.0` (`modules/layout`): program → levels → skeletons (footprint, bands, stair core) → seeded zoning/subdivision variants → scoring → regions → walls/openings/slabs/stairs/railings/roofs/furniture → validation; stable semantic ids (uuid5 per project namespace); deviations and notes reported (docs/3d-engine.md §16)
- Model validator: reachability of every room from the entrance (doors, open boundaries, stairs)
- `project_versions` + `jobs` tables (Alembic `0002`); generation job (validate → layout in a worker thread → rules findings → new immutable version); demo fixture importable as a version; `ModelSummary`
- API: `POST /projects/{id}/spec/validate`, `POST /projects/{id}/generate` (202 job), `GET /jobs/{id}`, `GET /projects/{id}/versions[/{vid}]`, `POST /projects/{id}/versions/demo`
- Web: project editor renders the current version with the Phase 1 viewer; version selector; "New design" drawer with the spec form (reference presets, rooms, style, garage/balcony/terrace, seed, plot) → real job stages → opens the new version; generation banner; design report (deviations, notes, rules findings with element links, disclaimer)
- 10 reference specs (`data/fixtures/specs`) with golden files (`pnpm golden`); `data/fixtures/generated-house.model.json` rendered by the web engine tests

**Completion checklist** (verified 2026-09-28):

| Criterion | Result |
|---|---|
| Spec schema + tier-1/2 validation | ☑ Pydantic + rules checks; errors carry JSON pointers, suggestions, `rule_ref`s |
| Rules profile `generic-residential@1` | ☑ YAML data; engine and evaluators read every minimum from it |
| Deterministic layout, seeded | ☑ same spec + seed ⇒ identical model JSON (also across `PYTHONHASHSEED`s) |
| Stable semantic ids | ☑ uuid5(project, semantic key); `previous_ids` reuse hook |
| Hypothesis invariants | ☑ 40 random specs: no model errors, all rooms reachable, program present, rooms inside footprint, reproducible |
| 10 reference specs incl. 280 m² 2-storey 4-bed | ☑ valid, reachable, no rules findings, program + GFA ± 3 %; golden files |
| Versions + jobs + polling | ☑ immutable versions, one active job per project, interrupted jobs failed on startup |
| Spec form → generate → render | ☑ verified in the browser (dev and production build): preset → generate → v1 opens; floors, selection/properties, report; 3-storey villa as v2; version switching |
| Tests / lint / typecheck / build | ☑ API 190 tests, web 110 tests; ruff, ruff format, import-linter (2 contracts), mypy strict, ESLint, tsc clean; `next build` OK |

Deferred / changed from the original plan:

- `rules_profiles` DB table → profiles stay versioned files until they become user-editable (docs/database.md)
- "Slicing-tree / squarified treemap" subdivision → a double-loaded-corridor band scheme with tucked service rooms: always reachable, always daylit, simpler to validate; richer plan types later
- Wet-stack zoning around the core, stair headroom checks, accessibility checks: not yet
- Version compare / restore: Phase 5 as planned

## Phase 3 — AI building generation (NL → spec → layout → 3D) ☑
Goal: natural language → validated `BuildingSpecification` → Phase 2 layout engine → `BuildingModel` → Phase 1 viewer. **Done 2026-09-28.** Details: [ai-pipeline.md](ai-pipeline.md).

Delivered:

- `AIProvider` abstraction (one structured-output primitive + `generate_building_specification` / `repair_building_specification`), deterministic `MockAIProvider` (dev/tests/CI/offline, refused in production), `AnthropicProvider` (official SDK, structured outputs, cached system prompt, error mapping; the only module importing the SDK — import-linter contract)
- Versioned prompt modules (`building-generation@1`): vocabulary generated from the spec enums, rules-profile minimums in the project context, explicit priorities, assumptions/conflicts/unsupported requests, clarification policy, prompt-injection quoting
- `SpecificationDraft` output contract; interpreter with Pydantic + rules + form-field validation, **one** repair call, never accepting invalid output; repair changes to the program reported
- `POST /ai/generate-building`, `GET /ai/generations/{id}`, `GET /projects/{id}/generations`; background generation with real stages; auth, ownership, prompt limits, hourly rate limit, one active generation per project; distinct failure codes with user-safe messages
- Shared `generation.pipeline.layout_and_save` (spec-form job and AI use the same layout → validation → rules → version step); AI versions carry prompt, spec, seed, rules profile, engine version and generation provenance
- `ai_generations` + `ai_runs` tables (Alembic `0003`); structured generation log line (no secrets; prompt text only when enabled)
- `ProjectContext` builder and read-only, ownership-scoped AI tools (Phase 5 preparation)
- Generated web contracts for the AI API (`pnpm schema` → `ai-generation.schema.json`, TS types, Zod validators)
- Web: AI generator on the projects dashboard (examples, optional structured details, "Generate 3D building") → editor opens with real-stage progress → the building appears; clarification questions; failures with reasons; generation summary over the 3D view (requested vs generated, warnings, assumptions, provider); history drawer; "New design" drawer with AI / specification-form tabs; design report shows the request, assumptions and AI provenance

**Completion checklist** (verified 2026-09-28, Windows dev machine, `AI_PROVIDER=mock`):

| Criterion | Result |
|---|---|
| BuildingSpecification exists and is validated | ☑ spec 1.0.0 (unchanged) — Pydantic tier 1 + rules tier 2 + form fields |
| AIProvider abstraction / MockAIProvider | ☑ |
| AnthropicProvider with environment configuration | ☑ implemented and unit-tested against a fake SDK client; settings fail fast without key/model. ☐ **not live-tested** — no project Anthropic credentials configured (`tests/ai/test_live_anthropic.py`, `RUN_LIVE_AI_TESTS=true`) |
| OpenRouterProvider (OpenAI-compatible adapter, 2026-09-29) | ☑ `AI_PROVIDER=openrouter`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`; unit-tested against a mocked HTTP transport. ☑ **live-tested once** with `anthropic/claude-opus-5.5`: strict structured outputs rejected the full schema ("compiled grammar is too large", free 400) → schema-in-prompt fallback; 1 call, no repair, 2 floors, 222.3 m² (asked 220), 3 bedrooms, 2 bathrooms, 1 WC, 2-car garage, no geometry or rules findings |
| NL generation endpoint; schema validation; invalid output rejected/repaired | ☑ |
| Spec passes building rules → layout engine → valid BuildingModel → version | ☑ demo prompt: 2 floors, 279.7 m² (asked 280), 4 bedrooms, 3 bathrooms, 2-car garage, balcony, all checks met, no rules findings |
| Existing 3D engine displays it; rotate, zoom, select, floors, properties | ☑ verified in the browser (dev and production build) |
| Summary, warnings, assumptions displayed | ☑ summary card + design report |
| Generation history stored | ☑ `ai_generations` / `ai_runs`; history drawer |
| Authentication / ownership | ☑ 401 / 404 tests |
| Mock pipeline in CI; unit/integration tests | ☑ API 285 passed + 1 live test skipped, web 126 passed |
| Lint / type checks / import boundaries / production build | ☑ ruff, ruff format, import-linter (3 contracts), mypy strict, ESLint, tsc; `next build` OK |
| No major console errors; browser E2E | ☑ dashboard prompt → editor → v1 rendered; clarification → v2; infeasible request → failure with reasons; history; report |

Deferred / changed from the original plan:

- Spec review step before generating (form with highlighted assumptions) → replaced by the post-generation summary with assumptions and requested-vs-delivered checks; the specification form remains available for precise edits
- Eval suite (~50 prompts) and `pnpm eval` → not yet; the mock prompts are parametrized tests and the live test covers the demo prompt
- OpenAI-compatible adapter → later
- "Exit: eval pass rate ≥ 90 %" → pending the eval suite and live credentials

## Phase 3.5 — Architectural knowledge & real template system ◐
Goal: ground the AI and the deterministic engines in structured, versioned, source-attributed architectural knowledge, without changing Phase 1–3 behaviour until a step deliberately does. Details: [knowledge.md](knowledge.md). Steps keep this order; each is reviewed before the next starts.

| Step | Scope | Status |
|---|---|---|
| K1 — Knowledge Foundation | pure `modules/catalog`; provenance/source model; knowledge-item, ontology, glossary, drawing-profile and region-profile schemas; loader, registry, integrity, hash lock; `core@1` pack; Georgievsky 2004 source record and `spds-georgievsky-2004@1` pack (`spds@1` drawing profile); `generic@1` region profile | ☑ 2026-09-28 |
| K2 — Families, Types, Assemblies | family/type/assembly/role-mapping records + integrity; generic type pack (draft, migrated `LayoutConfig` defaults); gated resolver; rules checks for types; BuildingModel 1.1.0 (`type_ref`, type/assembly snapshots, ceiling ref) with upgrade-on-read; layout `TypeSet`; properties panel type section | ☑ 2026-09-28 (branch, awaiting review) |
| K2.5 — Architectural Geometry & Placement | geometric invariants (hosting, opening placement, walls, room boundaries vs walls, relationships, levels, stairs vs slabs, roofs vs supports, type fit) with a constraint catalog and machine-readable findings; derived coordination axes; constraint-aware layout (door fit before the search, stair lanes in the search, shared opening placement, validation of every candidate); layout@1.2.0 | ☑ 2026-09-29 (on main) |
| K3 — Design Systems + expressive design intent | design-system records (4 editorial drafts: modern-minimal, contemporary-warm, classic-brick, scandinavian-timber) with integrity and gated resolution; spec 1.1.0 design intent (facade color, facade-specific window emphasis, room orientation, design system); BuildingModel 1.2.0 design record, wall display colors, window size classes; deterministic precedence and facade model; layout@1.3.0 integration; design checks in validate_model; renderer color keys; form controls; prompt @2 | ◐ 2026-09-29 (branch `phase-3.5-k3-design-systems`, awaiting review) |
| K4 — Templates | real building configurations (programme, relationships, circulation, structural concept, constraints, layout hints); needs sources beyond the drafting handbook | ☐ |
| K5 — Knowledge API and Units | read-only catalog API; imperial display/input conversion over SI internals | ☐ |
| K6 — Optional Structural Elements | structural element types (foundations, columns, beams, lintels) | ☐ |

**K1 completion checklist** (verified 2026-09-28):

| Criterion | Result |
|---|---|
| Pure catalog module, import boundaries | ☑ `app.modules.catalog` in the domain-purity contract; catalog depends only on `building`; contract "no module consumes the catalog yet" |
| Provenance on every object; lifecycle | ☑ 83 book items `extracted`, 6 `needs_verification`, none reviewed/approved; `approved_items()` is empty |
| Georgievsky 2004 scoped, not global | ☑ `drawing_convention_profile` pack (`spds`); `core` may cite it only for existence; the default region does not include it |
| Integrity + hash lock | ☑ the loader refuses stale/missing locks and every integrity violation (tested per rule) |
| Phase 1–3 unchanged | ☑ golden files, fixtures and `packages/schema` regenerate byte-identically; no engine, prompt or schema change |

**K2 completion checklist** (verified 2026-09-28):

| Criterion | Result |
|---|---|
| BuildingModel 1.1.0 + validation | ☑ type/assembly snapshots, `type_ref`, `ceiling_assembly_ref`; checks for unknown/mismatched refs, fixed-parameter mismatch, assembly thickness, unused snapshots |
| Upgrade-on-read | ☑ one `load_model` path (versions, AI tools, demo); pure + idempotent; legacy rows served as 1.1.0, row and hash untouched; frozen 1.0.0 fixtures |
| Catalog components + generic pack | ☑ 7 families, 20 types, 7 assemblies, 1 mapping — all `draft`; equal to `LayoutConfig` (test) |
| Gated, deterministic resolution | ☑ approved-only; unapproved derived knowledge blocks a type; draft repository ⇒ no type set |
| Rules separate from types | ☑ types below profile minimums refused with `rule_ref`, never resized |
| Geometry preserved | ☑ geometry fingerprints of all 10 reference specs unchanged, typed and untyped; web scene hash unchanged |
| Book-derived types | ☑ none added; a GOST window type stays blocked until its K1 item is approved (tested) |

**K2.5 checklist** (verified 2026-09-29, branch):

| Criterion | Result |
|---|---|
| Geometry separate from knowledge, rules and intent | ☑ `building/constraints.py` catalog; no knowledge consumed; no dimensional requirement added; rules untouched |
| Findings: what / where / why / which constraint | ☑ `Issue.constraint`, `related_ids`, `measure` (additive); computed on read; report panel group |
| Constraint-aware generation | ☑ door fit before the search, stair-lane constraint in the search, shared placement arithmetic, every candidate validated |
| Defects found in layout@1.1.0 | ☑ fixed: stair flights cut into facade walls (reference specs 05, 06, 09); storeys < 2.6 m with sliding doors failed as LAYOUT_INVALID |
| Geometry regression | ☑ 7/10 reference fingerprints unchanged; 05/06/09 changed deliberately; typed = untyped; demo and 1.0.0 fixtures valid |
| Determinism | ☑ same input ⇒ same model; two `PYTHONHASHSEED`s; seeds of unaffected skeletons unchanged |

**K3 checklist** (verified 2026-09-29, branch `phase-3.5-k3-design-systems`):

| Criterion | Result |
|---|---|
| Design systems in the catalog | ☑ `DesignSystemRecord` + integrity (allow-lists, defaults, palette, materials, mapping, approved dependencies); 4 editorial, region-neutral systems, all **draft**; gated resolution to snapshots; nothing approved |
| Expressive intent in the spec (1.1.0, additive) | ☑ `design.facade_color`, `design.windows` (emphasis, preferred/excluded facades), `rooms[].faces`, `style.design_system`; 1.0.0 specs unchanged |
| Color vs material | ☑ display color on the wall face (`finish_right_color`), material unchanged; renderer draws the library preset in that color |
| Facade model | ☑ derived from wall normals (street = −y = front); one synonym table for prompt and mock |
| Intent changes the generated model | ☑ per-facade window size classes, preferred facades glazed first, excluded facades standard only; rooms facing front/rear; `design_checks` in `validate_model` |
| Backward compatibility | ☑ all 10 reference geometry fingerprints equal to main; 1.0.0 and frozen 1.1.0 models upgrade on read; BuildingModel 1.2.0 |
| Live OpenRouter test (Claude Opus 5.5, one call) | ☑ yellow facade on all 11 exterior walls; 3 panoramic windows, all on the rear; front: standard only; living + dining on the rear; no K2.5, design or rules findings; 1 call, no repair |

## Phase 4 — Quantities & preliminary cost ☐
- Material library (YAML → DB); item-code vocabulary
- Takeoff: walls net of openings (area/volume/blocks), slabs (concrete m³, rebar kg estimate), roof, finishes by room, doors/windows counts & areas, stairs
- Cost catalogs (seed 1 demo catalog), estimate with overhead/contingency/tax, category breakdown, unmapped-item warnings
- UI: quantities table (click line → highlight elements), cost summary + breakdown chart, cost/m²
- **Exit**: hand-verified quantities on fixture house within 1 %; estimate reproducible from stored catalog

## Phase 5 — NL modification & versioning ☐
- Operations engine (apply, inverse, derived regeneration, locks)
- ModificationPlan AI pipeline with ModelSummary refs
- Drafts, commit, restore, branch
- Compare view: element diff coloring in 3D + quantity/cost deltas
- **Exit**: "make the kitchen 2 m wider and add a window to the master bedroom" → preview diff → accept → v2 with updated cost; compare v1/v2

## Phase 6 — MEP layers ☐
- Plumbing (fixtures, stack, drain/supply routing), electrical (board, outlets, lights, switches, circuits), HVAC (split or ducted)
- Systems, discipline palette, x-ray, isolate/trace system
- MEP quantities (pipe length by diameter, cable length, duct area) and cost
- **Exit**: toggle each discipline; trace a fixture to its source; MEP lines appear in estimate

## Phase 7 — Analysis & reports ☐
- Deterministic design metrics (net/gross, WWR per façade, cost/m², room compliance)
- AI analysis (findings linked to elements)
- Report: HTML (Jinja2) → PDF (WeasyPrint) with plan snapshots, 3D views (client-captured), spec, quantities, cost, assumptions, disclaimers
- **Exit**: one-click PDF report for any version

## Phase 8 — Hardening & beta ☐
- Walk mode, plan view, measurements; performance work (BatchedMesh, worker builds)
- Rate limits/budgets, observability (structured logs, error tracking), backups
- Security review, accessibility pass, onboarding/demo project
- **Exit**: closed beta

## Later / backlog
IFC export · GLB fixture catalog · multiple cost regions & user-editable catalogs · sharing & comments · real-time collaboration · non-rectilinear walls · basements · energy estimates · worker queue (arq/Redis) when scaling

---

## Decisions log

| # | Question | Decision (2026-09-27) |
|---|---|---|
| 1 | Target region & currency | **Kazakhstan, KZT.** Costing is currency-agnostic (KZT/USD/EUR/… via catalogs). Seed catalog `kz-almaty-demo` is illustrative, flagged demo |
| 2 | First real AI provider | **Anthropic.** MockAIProvider for dev/tests; OpenAI-compatible adapter later |
| 3 | Building rules | **Generic configurable `BuildingRulesProfile`** (`generic-residential@1`); conceptual only; regional profiles (e.g. KZ) later. Not a code-compliance check |
| 4 | Phase order | 0 foundations → 1 hand-authored model → 3D → 2 spec → layout → 3 NL → AI. 3D pipeline must work without AI first |
| 5 | Units | Metric only (input conversion supported later) |
| 6 | Task runner | Root `package.json` scripts (Windows-friendly) + thin Makefile |
| 7 | Rules profile storage (2026-09-28) | Versioned YAML files `data/rules-profiles/<id>.v<n>.yaml`, immutable once used, cached per process; versions record `id@version`. DB table only when profiles become user-editable |
| 8 | Gross floor area definition (2026-09-28) | Measured on wall centerlines over all storeys; attached garage, balconies and terraces excluded |
| 9 | Layout scheme v1 (2026-09-28) | Double-loaded corridor bands with the stair core in the street band and tucked service rooms (reachable + daylit by construction); other plan types later |
| 10 | Generated element ids (2026-09-28) | `uuid5(project id, semantic key)`: stable across regenerations in a project, never shared between projects |
| 11 | Requested area vs. room program (2026-09-28) | The requested gross floor area is delivered; rooms deviate instead, and every deviation > 15 % (and unmet adjacency) is reported — never silent |
| 12 | AI output mechanism (2026-09-28) | Structured outputs (JSON Schema of `SpecificationDraft`) instead of forced tool use; ≤ 1 repair call; model name from `AI_MODEL` only |
| 14 | Phase 3.5 knowledge (2026-09-28) | Steps K1 Knowledge Foundation → K2 Families, Types, Assemblies → K3 Design Systems → K4 Templates → K5 Knowledge API and Units → K6 Optional Structural Elements. Georgievsky 2004 is one source, scoped as the SPDS/ESKD-era `spds` drawing-convention profile, never a global standard; extracted knowledge stays unreviewed until a person reviews it; only approved knowledge may be consumed; knowledge is not rules |
| 13 | Default model suggestion (2026-09-28) | `.env.example` suggests `claude-opus-5`; any model is a configuration change, never a code change |

## Open decisions

| # | Question | Default until decided |
|---|---|---|
| 1 | Hosting target | Docker Compose on a single VM |
| 2 | UI language(s) (EN / RU / KZ) | English first; strings kept i18n-ready |
