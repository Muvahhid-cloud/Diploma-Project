# BuildAI 3D

AI-powered residential building design. Describe a house in plain language; get an editable, procedural 3D building with material quantities and a preliminary construction cost.

> "Create a modern two-story house with 280 m², 4 bedrooms, 3 bathrooms, a large open kitchen and living room, a two-car garage, balcony, panoramic windows and minimalist design."

```
Natural language → AI → BuildingSpecification → Validation → Layout engine
  → BuildingModel (walls, rooms, windows, pipes… as typed objects)
  → Procedural 3D (Three.js / React Three Fiber) → Quantities → Cost → AI analysis
```

The AI produces **structured building data**, not images. A deterministic engine turns that data into geometry, so every wall, room, window and pipe is a real, selectable, measurable object.

Initial market: **Kazakhstan (KZT)**. Costing is currency-agnostic.

## Status

**Phase 0 — Foundations** (monorepo, API, web, auth, projects, Docker, CI). Next: **Phase 1** — hand-authored BuildingModel → procedural 3D viewer. See [docs/roadmap.md](docs/roadmap.md).

## Prerequisites

- Node.js ≥ 22 and pnpm 10 (`npm i -g pnpm` or `corepack enable`)
- Python 3.12 and [uv](https://docs.astral.sh/uv/) (`pip install --user uv` also works — scripts fall back to `python -m uv`)
- Docker Desktop (optional for local dev; required for `pnpm docker:up`)

## Quick start

### Option A — Docker Compose (full stack)

```bash
cp .env.example .env        # set JWT_SECRET
docker compose up --build   # db + api (migrates on start) + web
```

Web: http://localhost:3000 · API docs: http://localhost:8000/docs

### Option B — Local processes (no Docker needed)

```bash
pnpm install
pnpm api:install
pnpm db:local               # starts embedded PostgreSQL 16, prints DATABASE_URL
cp .env.example .env        # paste DATABASE_URL, set JWT_SECRET
pnpm migrate
pnpm dev                    # web on :3000 (proxies /api) + api on :8000
```

Stop the embedded database with `pnpm db:local --stop`. You can instead point `DATABASE_URL` at any PostgreSQL 16 (`postgresql+asyncpg://…`).

## Commands

| Command | What it does |
|---|---|
| `pnpm dev` | Web + API with reload |
| `pnpm lint` | ESLint, Ruff (lint + format check), import-linter boundaries |
| `pnpm typecheck` | `tsc --noEmit`, mypy (strict) |
| `pnpm test` | Vitest (web), pytest (API, real PostgreSQL, includes migration checks) |
| `pnpm check` | lint + typecheck + test |
| `pnpm migrate` | `alembic upgrade head` |
| `pnpm build:web` | Production Next.js build |
| `pnpm docker:up` / `docker:down` | Compose stack |

API tests use `TEST_DATABASE_URL` if set (CI); otherwise they start an embedded PostgreSQL automatically.

## Repository layout

```
apps/web/        Next.js (App Router) + React Three Fiber viewer (Phase 1)
apps/api/        FastAPI modular monolith (auth, projects; domain modules stubbed)
packages/schema/ Generated contracts from Pydantic (Phase 1)
data/            Materials, cost catalogs, rules profiles, fixtures (Phase 1+)
docs/            Architecture and design documents
infra/docker/    Dockerfiles
scripts/         Cross-platform helper scripts
```

## Documentation

| Doc | Contents |
|---|---|
| [docs/architecture.md](docs/architecture.md) | System overview, repo/frontend/backend architecture, ADRs, cost/versioning/testing |
| [docs/building-model.md](docs/building-model.md) | Specification & model schemas, invariants, operations, rules profiles |
| [docs/ai-pipeline.md](docs/ai-pipeline.md) | AIProvider abstraction, interpret/modify/analyze pipelines, evals |
| [docs/3d-engine.md](docs/3d-engine.md) | Coordinates, units, geometry generation, selection, regeneration, performance |
| [docs/database.md](docs/database.md) | PostgreSQL schema, versioning storage |
| [docs/roadmap.md](docs/roadmap.md) | Phases, verification checklists, decisions log |
| [CLAUDE.md](CLAUDE.md) | Permanent project rules for AI-assisted development |

## Disclaimer

BuildAI 3D produces conceptual designs, schematic MEP layouts and preliminary cost estimates for early-stage exploration only. Rules checks are conceptual, and seed cost catalogs contain demo/estimated rates. **It is not a replacement for licensed architectural, structural, MEP or regulatory review.**
