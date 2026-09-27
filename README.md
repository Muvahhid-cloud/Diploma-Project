# BuildAI 3D

AI-powered residential building design. Describe a house in plain language; get an editable, procedural 3D building with material quantities and a preliminary construction cost.

> "Create a modern two-story house with 280 m², 4 bedrooms, 3 bathrooms, a large open kitchen and living room, a two-car garage, balcony, panoramic windows and minimalist design."

```
Natural language → AI → BuildingSpecification → Validation → Layout engine
  → BuildingModel (walls, rooms, windows, pipes… as typed objects)
  → Procedural 3D (Three.js / React Three Fiber) → Quantities → Cost → AI analysis
```

The AI produces **structured building data**, not images. A deterministic engine turns that data into geometry, so every wall, room, window and pipe is a real, selectable, measurable object.

## Status

🚧 **Architecture phase.** No application code yet. See [docs/roadmap.md](docs/roadmap.md).

## Documentation

| Doc | Contents |
|---|---|
| [docs/architecture.md](docs/architecture.md) | System overview, repo/frontend/backend architecture, ADRs, cost/versioning/testing summaries |
| [docs/building-model.md](docs/building-model.md) | BuildingSpecification and BuildingModel schemas, invariants, operations |
| [docs/ai-pipeline.md](docs/ai-pipeline.md) | AIProvider abstraction, interpret/modify/analyze pipelines, evals |
| [docs/3d-engine.md](docs/3d-engine.md) | Layout engine, MEP generator, geometry builders, viewer |
| [docs/database.md](docs/database.md) | PostgreSQL schema, versioning storage |
| [docs/roadmap.md](docs/roadmap.md) | Phased delivery plan and open decisions |
| [CLAUDE.md](CLAUDE.md) | Permanent project rules for AI-assisted development |

## Tech stack

- **Frontend**: Next.js, React, TypeScript, React Three Fiber, Three.js, drei, Zustand, TanStack Query, Tailwind CSS, Zod
- **Backend**: Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, JWT
- **Infra**: Docker, Docker Compose
- **AI**: vendor-neutral `AIProvider` abstraction with a `MockAIProvider` for local development

## Getting started

_Available after Phase 0._ Planned:

```bash
cp .env.example .env
make dev        # starts postgres, api (http://localhost:8000), web (http://localhost:3000)
make migrate && make seed
```

## Disclaimer

Designs, MEP layouts and cost estimates produced by BuildAI 3D are preliminary and schematic. They are not construction documents and must be reviewed by licensed professionals.
