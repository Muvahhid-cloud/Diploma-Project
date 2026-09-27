# Roadmap

Status: **Draft (v0.1)** · Each phase ends with a demoable, tested increment. Phases are ordered to prove the riskiest link (spec → geometry → render) **before** investing in AI and polish.

Legend: ☐ not started · ◐ in progress · ☑ done

---

## Phase 0 — Foundations ☐
Goal: everything runs with one command; contracts in place.

- Monorepo scaffold: `apps/web` (Next.js, TS strict, Tailwind), `apps/api` (FastAPI, uv), `packages/schema`
- `docker-compose.yml`: postgres, api, web; `.env.example`; Makefile (`dev`, `test`, `lint`, `schema`, `migrate`, `seed`)
- Core API: config, DB session, error envelope, health check, logging
- Alembic baseline; users + refresh_tokens; JWT auth (register/login/refresh/logout)
- Projects CRUD + membership check
- Web: auth pages, project list, API client with Zod validation, TanStack Query setup
- CI: lint, type-check, tests, migration up/down, schema drift check
- **Exit**: sign up → create project → see empty editor, in Docker, CI green

## Phase 1 — Building model & viewer (no AI, no layout) ☐
Goal: prove the model → 3D path with a hand-authored model.

- Pydantic `BuildingSpecification` + `BuildingModel` (building-model.md), invariants validator
- Schema codegen → TS types + Zod
- Fixture `data/fixtures/simple-house.model.json` (2 levels, ~8 rooms, doors, windows, slabs, flat roof)
- TS engine: builders for wall (panel decomposition), door, window, slab, room floor, roof, stair
- Viewer: orbit, fit, selection + inspector, floor isolation, cutaway, layer toggles
- Versions table + store fixture as v1 of a project
- **Exit**: open a project → fixture renders; click any element → inspector shows UUID/type/dims/material/relationships

## Phase 2 — Layout engine (spec → model) ☐
Goal: deterministic geometry from a spec.

- Program expansion, footprint, stair core, zoning, subdivision, circulation, walls, openings, slabs, roof
- Candidate search + scoring; seeded determinism; stable semantic IDs
- Hypothesis invariant tests; golden-file tests for 10 reference specs
- Spec form in UI (manual spec entry) → generate → render
- Jobs table + polling
- **Exit**: 10 reference specs (incl. the 280 m² 2-storey 4-bed example) produce valid, plausible houses

## Phase 3 — AI interpretation ☐
Goal: natural language → validated spec.

- AIProvider protocol, MockAIProvider, one real provider adapter (+ OpenAI-compatible)
- Interpret pipeline with repair loop, assumptions, open questions
- ai_runs logging; prompt versioning; eval suite (~50 prompts)
- UI: prompt panel → spec review (assumptions highlighted) → generate
- **Exit**: example prompt → house in < 60 s; eval pass rate ≥ 90 % on chosen provider

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

## Open decisions (need product input)

| # | Question | Default until decided |
|---|---|---|
| 1 | Target market / region & currency for the first cost catalog | Demo catalog in EUR, clearly labelled "demo rates" |
| 2 | First real AI provider | Anthropic adapter first; OpenAI-compatible second |
| 3 | Building-code rule set (min room sizes, stair geometry) | Generic residential defaults, configurable |
| 4 | Imperial units in UI | Metric only in v1 (input conversion supported) |
| 5 | Hosting target | Docker Compose on a single VM |
