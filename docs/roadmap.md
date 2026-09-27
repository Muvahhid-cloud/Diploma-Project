# Roadmap

Status: **Accepted (v0.2)** · Each phase ends with a demoable, tested increment. Phases are ordered to prove the riskiest link (spec → geometry → render) **before** investing in AI and polish.

Legend: ☐ not started · ◐ in progress · ☑ done

---

## Phase 0 — Foundations ◐
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

## Phase 1 — Hand-authored model → procedural 3D (no AI, no layout) ☐
Goal: prove the highest-risk dependency — BuildingModel → deterministic procedural 3D → interactive viewer — completely independent of AI.

- Pydantic `BuildingModel` (building-model.md) + invariants validator; `BuildingSpecification` schema (unused until Phase 2)
- Schema codegen → TS types + Zod in `packages/schema`
- **Demo fixture** `data/fixtures/demo-house.model.json`, hand-authored:
  - 2 floors (ground + upper), several rooms (entrance/hall, open kitchen-living, WC, garage/storage on ground; 2–3 bedrooms, bathroom, landing on upper)
  - exterior + interior walls, doors, windows (incl. one panoramic), ground + upper floor slabs (with stair hole)
  - straight stair connecting the floors, flat roof with parapet
  - basic furniture (beds, sofa, dining table + chairs, kitchen counter/island, wardrobe, bathroom fixtures)
- TS engine: builders for wall (panel decomposition + corner joins), door, window, slab, room floor, roof, stair, railing, furniture primitives; determinism snapshot tests
- Viewer: **rotate, zoom, pan**, fit; **select objects**; **isolate floors**; **inspector** with all element fields; **hide/show layers** (architecture, structure, furniture); cutaway
- Store the fixture as v1 of a demo project (versions table)
- **Exit**: open demo project → house renders; every interaction above works; clicking any element shows UUID/type/dims/position/rotation/material/properties/relationships; same model ⇒ identical geometry hash

No AI work of any kind happens before Phase 1 exits.
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

## Decisions log

| # | Question | Decision (2026-09-27) |
|---|---|---|
| 1 | Target region & currency | **Kazakhstan, KZT.** Costing is currency-agnostic (KZT/USD/EUR/… via catalogs). Seed catalog `kz-almaty-demo` is illustrative, flagged demo |
| 2 | First real AI provider | **Anthropic.** MockAIProvider for dev/tests; OpenAI-compatible adapter later |
| 3 | Building rules | **Generic configurable `BuildingRulesProfile`** (`generic-residential@1`); conceptual only; regional profiles (e.g. KZ) later. Not a code-compliance check |
| 4 | Phase order | 0 foundations → 1 hand-authored model → 3D → 2 spec → layout → 3 NL → AI. 3D pipeline must work without AI first |
| 5 | Units | Metric only (input conversion supported later) |
| 6 | Task runner | Root `package.json` scripts (Windows-friendly) + thin Makefile |

## Open decisions

| # | Question | Default until decided |
|---|---|---|
| 1 | Hosting target | Docker Compose on a single VM |
| 2 | UI language(s) (EN / RU / KZ) | English first; strings kept i18n-ready |