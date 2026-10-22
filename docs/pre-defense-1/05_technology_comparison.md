# 05 — Technology Comparison

> The selected stack below was read from the code on 2026-10-20 (`apps/web/package.json`, `apps/api/pyproject.toml`, import-linter contracts). It is not taken from the original plan. Existing decisions are recorded as ADRs in [`docs/architecture.md`](../architecture.md) §6, and this document expands four of them with alternatives and criteria. 

Requirement anchors used as criteria (see [06](06_requirements_specification.md)): determinism (NFR-D1), one schema source for Python and TS (NFR-C1), domain purity and testability (NFR-M1), vendor neutrality (NFR-E2), browser 3D performance (NFR-P1), security (NFR-S*), and **team capacity**: two students, a fixed diploma timeline, Windows development machines.

## Decision A — Backend / API framework

| Criterion | **FastAPI** (selected) | Django + Django REST Framework | NestJS (Node/TypeScript) |
|---|---|---|---|
| Schema validation and contracts | Native Pydantic v2 models for request/response; OpenAPI generated automatically [T4, T5] | DRF serializers (separate from models); OpenAPI via add-ons | class-validator/DTOs; OpenAPI via decorators [T11] |
| Fit with the geometry/domain code | The domain (layout, validation, geometry via shapely) is Python. The same Pydantic models are the domain schema **and** the API schema | Python, but the ORM-centric style pulls domain logic toward models | Domain would need TypeScript geometry libraries or a second Python service |
| Generating TS types and Zod from one source (NFR-C1) | Pydantic → JSON Schema → TS + Zod (`pnpm schema`), already in place | Possible via OpenAPI, but serializers are a second schema layer | TS-native, but then Python geometry needs its own schema, so there are two sources |
| Async I/O for LLM calls and DB | Async-first (`async def`, async SQLAlchemy) [T4] | Async support exists; much of the ecosystem is sync | Async-first |
| Batteries (admin, auth) | Minimal, so auth (JWT + rotating refresh, argon2id) was written by hand | Rich (admin, auth, ORM, migrations) [T10] | Moderate (modules, DI, guards) |
| Operational implications | One ASGI process (uvicorn). Background jobs run in-process (ADR-010) | WSGI/ASGI; heavier framework | Node runtime. A Python sidecar would be needed for shapely-class geometry |
| Risk | Hand-written auth needs security review (NFR-S*) | More framework to learn; serializer/model duplication | Language split between domain and API |

**Selected: FastAPI.** The deciding criterion was **one canonical schema**. The building model, specification and AI output contract are Pydantic classes (`apps/api/app/modules/building/`, `ai/schemas/`) that FastAPI validates at the boundary, and the TypeScript side is generated from them, so there is no hand-kept second schema (ADR-002). Django's admin and auth would have saved effort, but the project needs neither a CMS-style admin nor ORM-centric domain objects. NestJS would split the geometry domain from the API language. Accepted cost: auth was implemented by hand and must be security-reviewed (risk R-07 in [10](10_project_management_and_risks.md)).

## Decision B — Database and data modeling

| Criterion | **PostgreSQL 16, relational metadata + JSONB model snapshot per version** (selected) | PostgreSQL, fully normalized element tables | MongoDB document store |
|---|---|---|---|
| Immutable versions (FR-16) | One row per version holding the whole model. Append-only, so a restore creates a new row | Every version copies thousands of element rows, or needs temporal tables | Natural document per version |
| Read/write pattern | The model is always loaded and saved whole (viewer, layout, validation) | Needs many joins to reassemble a model | Whole-document reads |
| Relational integrity for users, projects, jobs, generations | Full SQL constraints and FKs (`users`, `refresh_tokens`, `projects`, `project_versions`, `jobs`, `ai_generations`, `ai_runs`) | Full | Weaker. Ownership and referential checks would move into application code |
| Schema evolution of the model | `schema_version` in the document + upgrade-on-read migrations (`building/migrations`); stored rows are never rewritten (ADR-015) | Alembic migrations over element tables, rewriting history | Same as JSONB, no SQL |
| Querying inside models | JSONB operators available if needed [T6] | Best for cross-model element analytics | Good document queries |
| Operational implications | One database, one migration tool (Alembic). Embedded Postgres for local dev without Docker (`pnpm db:local`) | Same DB, much larger schema | A second database technology, or giving up SQL |

**Selected: PostgreSQL with JSONB snapshots** (ADR-003). A house model is small (the generated 280 m² house has 117 elements, see screenshot 05) and always handled whole. Immutable versions are simple appends, and relational guarantees still cover the account/project/job data. Normalized element tables only pay off for cross-model element analytics, which v1 doesn't need. MongoDB would give up FK integrity for user/project ownership, and that is security-relevant. Accepted cost: element-level SQL queries across versions are clumsy. That's acceptable until a measured need appears (CLAUDE.md rule 14).

## Decision C — 3D rendering platform (browser)

| Criterion | **three.js + React Three Fiber + drei** (selected) | Babylon.js | Game engine exported to WebGL (e.g. Unity) |
|---|---|---|---|
| Integration with the React/Next.js UI (panels, selection, state) | Declarative React scene graph; Zustand stores shared with UI panels [T7, T8] | Imperative engine; React integration through wrappers [T9] | Separate runtime embedded in the page; UI bridge via messages |
| Procedural geometry from data | Direct `BufferGeometry` construction. BuildAI keeps it in a pure-TS `engine/` (builders → `RenderDescriptor`) with no React dependency | Equally capable mesh APIs | Possible in C#, but the model→geometry code would then live outside the TS/Python contract |
| Determinism and testability (NFR-D1) | Pure-TS builders are unit-tested in Vitest without a GPU (scene hash tests) | Possible, but the engine is more coupled | Hard to unit-test in CI |
| Bundle size and load | Lightweight core; add-ons as needed | Heavier full engine with many built-ins | Large WebGL builds; slow first load |
| Built-in tooling | Fewer built-ins (drei helpers) | Rich: inspector, physics, GUI [T9] | Very rich editor tooling |
| Skills / ecosystem | Large React ecosystem; fits the TS strict codebase | Good TS support | Needs C# and Unity skills on top of TS/Python |

**Selected: three.js with React Three Fiber.** The viewer is part of a React editor where selection, floor isolation, layers and the properties panel share state with the 3D scene, and R3F makes the scene a React tree driven by the same stores. The geometry engine is deliberately framework-free (`apps/web/src/engine`, CLAUDE.md 3D rules), so swapping the renderer later would only replace `viewer/`. Babylon.js is a strong alternative with better built-in tooling, but it would add an imperative layer between React state and the scene. A game engine export fails the testability and load-time criteria. Measured evidence so far: the generated 2-storey house renders 117 elements as 144 meshes / ~7k triangles, built in 39–40 ms (status line in screenshots 05–06, dev mode). That is one observation, not a benchmark.

## Decision D — LLM / provider integration

| Criterion | **Vendor-neutral `AIProvider` interface + structured output of a typed spec; mock / Anthropic / OpenRouter adapters** (selected) | Direct single-vendor SDK calls in business logic | Agent framework where the LLM plans and writes geometry or tool calls (cf. Text2BIM [S18]) |
|---|---|---|---|
| Geometric validity | The LLM never produces geometry. A deterministic engine creates it, and 37 constraints validate it | Same, if the contract is kept | Geometry depends on LLM-generated code or tool calls, so it needs a checker/repair loop [S18] |
| Testability / CI cost | `MockAIProvider` is deterministic and offline, so CI never calls a paid API (rule 13) | Tests must mock the SDK everywhere | Multi-call, stochastic; hard to test deterministically |
| Vendor lock-in (NFR-E2) | SDK imports confined to `ai/providers/<vendor>.py` (import-linter contract). The model name comes from config only | High | Framework lock-in plus vendor |
| Cost and latency | One call per generation, at most 1 repair (ADR-012) | Same | Many calls per design |
| Robustness to provider differences | Strict JSON-Schema mode, with a **schema-in-prompt fallback** when a provider rejects a large schema (observed live with OpenRouter: "compiled grammar is too large") [T2, T3] | Breaks when the vendor changes | Depends on framework support |
| Reasoning quality | Format restriction may reduce reasoning [S15]. Mitigation: measure strict vs fallback modes in the evaluation | Same | Free-form reasoning possible, but output is less controlled |

**Selected: vendor-neutral provider interface with structured outputs.** OpenRouter (OpenAI-compatible HTTP via `httpx`, model e.g. `anthropic/claude-opus-5.5`) is the provider that has been live-tested, once. `AnthropicProvider` (official SDK) is implemented and unit-tested but has never been called live. Keeping vendors behind one interface turned out to matter: the first live OpenRouter call rejected the strict schema, and the fallback could be added inside the adapter without touching business logic (`docs/roadmap.md`, Phase 3).

## Why the deterministic geometry engine is separated from the LLM

1. **Validity by construction.** Learned and LLM approaches don't guarantee hard spatial constraints [S11, S19], and LLM-written geometry needs iterative checking [S18]. In BuildAI every coordinate comes from code that shares its placement arithmetic with the validator (`building/hosting.py`), and every generated model is validated before it is saved.
2. **Reproducibility.** `generate_layout(spec, profile, seed)` is a pure function of its inputs plus `ENGINE_VERSION`. The same inputs give a byte-identical model, tested across two `PYTHONHASHSEED`s and with golden files. An LLM can't promise that.
3. **Testability and cost.** The engine runs in milliseconds-to-seconds offline, so the whole pipeline is tested in CI with the mock provider at zero API cost.
4. **Small, checkable AI output.** A `BuildingSpecification` has a few dozen closed-vocabulary fields that Pydantic, the rules profile and the form can check. The user can also edit it in the specification form (ADR-001).
5. **Safety.** A prompt injection can at worst produce a wrong but *valid* specification. It can't produce malformed geometry or code.
6. **Separation of evaluation.** Interpretation accuracy (LLM) and layout quality (engine) can be measured independently, which is what [09](09_verification_and_evaluation_plan.md) plans.

Trade-off acknowledged: the engine supports only what its rules encode (one plan scheme, rectilinear, ≤ 3 storeys). Expressiveness grows only through engineering work, not prompting.
