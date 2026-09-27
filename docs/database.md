# Database

Status: **Accepted (v0.1)** · PostgreSQL 16 · SQLAlchemy 2.x (typed, async via `asyncpg`) · Alembic

## 1. Principles

- **Relational for entities and relationships** (users, projects, versions, jobs, catalogs).
- **JSONB for building documents** (spec, model, operations, takeoff) — validated by Pydantic on write and read. See ADR-003 in [architecture.md](architecture.md).
- **Versions are immutable.** Updates create rows; they never mutate a committed version.
- UUID primary keys (`uuid` type, generated in app). `created_at`/`updated_at` `timestamptz` everywhere.
- Soft delete (`deleted_at`) for user-facing entities (projects). Hard delete only via admin/retention jobs.
- Every migration is reversible and tested (upgrade → downgrade → upgrade in CI).

## 2. Entity overview

```
users ─┬─< refresh_tokens
       └─< project_members >── projects ─┬─< project_versions (tree via parent_version_id)
                                         │        ├─< version_quantities (1:1 cache)
                                         │        ├─< cost_estimates (per catalog)
                                         │        ├─< analyses
                                         │        └─< reports
                                         ├─< drafts (per user)
                                         ├─< jobs
                                         └─< ai_runs
cost_catalogs ─< cost_items
materials (library, seeded)
```

## 3. Tables

### users
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| email | citext unique | |
| password_hash | text | argon2id |
| display_name | text | |
| is_active | bool | |
| created_at, updated_at | timestamptz | |

### refresh_tokens
| id uuid PK | user_id FK | token_hash text unique | family_id uuid | expires_at | revoked_at null | created_at | user_agent, ip |

### projects
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| owner_id | uuid FK users | |
| name | text | |
| description | text | |
| building_type | text | `single_family_house` |
| current_version_id | uuid FK project_versions null | "head" pointer shown by default |
| region_code | text | default cost region |
| deleted_at | timestamptz null | soft delete |

### project_members
| project_id | user_id | role (`owner`/`editor`/`viewer`) | PK(project_id, user_id) |

### project_versions  ★
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| project_id | uuid FK | index |
| parent_version_id | uuid FK self null | tree → branching options |
| number | int | per-project sequence (v1, v2…), unique(project_id, number) |
| label | text | "Option B – bigger kitchen" |
| created_by | uuid FK users | |
| source | text | `generation` / `modification` / `manual` / `restore` |
| prompt | text null | NL input that led here |
| spec | jsonb | BuildingSpecification snapshot |
| model | jsonb | BuildingModel snapshot |
| operations | jsonb | ops applied relative to parent (empty for generation) |
| schema_version | text | |
| engine_version | text | |
| model_hash | text | sha256 of canonical model JSON (dedupe, cache keys) |
| summary | jsonb | cheap stats for lists: GFA, rooms, bedrooms, total cost, currency |
| created_at | timestamptz | |

No `updated_at` — immutable. `spec`/`model` are large; list queries select only `summary`.

### drafts
Per (project, user) uncommitted working state.
| id | project_id | user_id | base_version_id | model jsonb | spec jsonb | operations jsonb (+ inverse stack) | updated_at | unique(project_id, user_id) |

### jobs
| id | project_id | user_id | kind (`generate`/`modify_plan`/`analyze`/`report`) | status (`queued`/`running`/`succeeded`/`failed`/`cancelled`) | progress real | stage text | input jsonb | result jsonb | error jsonb | created_at, started_at, finished_at |

### ai_runs
| id | job_id null | project_id | user_id | task | provider | model | prompt_version | input jsonb (redacted) | raw_output text | parsed_output jsonb | issues jsonb | repair_count int | input_tokens, output_tokens int | latency_ms int | cost_usd numeric(10,5) | status | created_at |

### version_quantities
| version_id PK/FK | takeoff jsonb (lines) | computed_with text (quantities engine version) | created_at |

### cost_catalogs / cost_items
```
cost_catalogs: id, code (e.g. "DEMO-EUR-2026Q3"), name, region_code, currency (char3),
               effective_date, version int, is_active, source, created_at
cost_items:    id, catalog_id FK, item_code, description, unit, material_rate numeric(14,4),
               labor_rate numeric(14,4), equipment_rate numeric(14,4), category, notes
               unique(catalog_id, item_code)
```
Catalogs are **immutable once used**; edits create a new catalog version so historical estimates stay reproducible.

### cost_estimates
| id | version_id FK | catalog_id FK | params jsonb (overhead %, contingency %, tax %, finish level) | lines jsonb | totals jsonb | total numeric(16,2) | currency | created_at | unique(version_id, catalog_id, params_hash) |

### analyses / reports
analyses: `id, version_id, ai_run_id, findings jsonb, summary_markdown, created_at`
reports: `id, version_id, kind, status, storage_path, created_at`

### materials
Seeded from `data/materials/*.yaml` (read-only in v1): `id text PK, name, category, render jsonb, unit, waste_factor, item_code`.

## 4. Versioning model

```
v1 (generation) ── v2 (kitchen wider) ── v4 (skylight)       ← project.current_version_id
         └──────── v3 (Option B: 3 bedrooms)                  ← branch
```

- **Commit**: draft → new `project_versions` row with `parent_version_id = draft.base_version_id`; draft reset.
- **Restore**: create a new version copying an old snapshot (`source = restore`); history is never rewritten.
- **Compare(a, b)**: computed on demand in `versions/diff.py`:
  - elements: added / removed / modified (field-level diff via canonical JSON paths), keyed by UUID
  - rooms: area deltas; program changes (counts by type)
  - quantities: per item_code delta; cost: per category delta
  - result cached in memory (LRU keyed by `model_hash` pair)
- **Why full snapshots instead of op-log replay**: loading any version is O(1); the ops are still stored for audit/explanation. A house model is ≤ 3 MB and TOAST-compressed (typically ~5–10×), so 100 versions ≈ tens of MB — acceptable. Revisit (content-addressed element storage) only if measurements say so.

## 5. Indexes

- `project_versions (project_id, number desc)`, `(project_id, created_at desc)`, `(parent_version_id)`
- `jobs (project_id, created_at desc)`, partial `jobs (status) where status in ('queued','running')`
- `ai_runs (project_id, created_at desc)`, `(created_at)` for spend reports
- `refresh_tokens (user_id)`, `(family_id)`
- No GIN on model JSONB in v1 (we don't query inside models).

## 6. Access patterns

| Use case | Query |
|---|---|
| Project list | projects join current version `summary` only |
| Open editor | 1 row from `project_versions` (spec+model) + user's draft |
| History panel | versions `id, number, label, parent, summary, created_at` |
| Cost | `cost_estimates` by (version, catalog, params_hash) else compute & insert |

## 7. Migrations & seeds

- Alembic autogenerate is a starting point only — every migration is reviewed by hand.
- Seeds (`make seed`): material library, default cost catalog(s), demo user + demo project (dev only).
- JSONB document migrations (schema_version upgrades) live in code (`building/migrations`), not Alembic.
