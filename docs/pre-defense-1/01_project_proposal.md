# 01 — Project Proposal

> Pre-Defense 1 package · BuildAI 3D · prepared · deadline 2026-10-24
> Status vocabulary used in every document: **Implemented (main)** = merged on `main` and covered by tests · **Committed, not merged** = on a feature branch awaiting review · **Partial** · **Planned** ·

## 1. Title

| | |
|---|---|
| **English** | Development and Implementation of an Intelligent BIM-Based 3D Platform for AI-Assisted Generative Building Design |
| **Russian** | «Разработка и внедрение интеллектуальной BIM-ориентированной 3D-платформы BuildAI 3D для генеративного проектирования зданий с применением искусственного интеллекта» |
| **Working name** | BuildAI 3D |

## 2. Team

| Role | Name |
|---|---|
| Team | SE-2406 |
| Student 1 | Турсуналиев Зайниддин Хайдаралиевич |
| Student 2 | Усманов Эсанжон Амонджонович |
| Supervisor | Танырбергенова Камила Ислямовна |



## 3. Problem statement

Early-stage residential design is iterative and needs expertise. A client or junior designer has to translate a verbal brief ("a modern two-storey house, about 280 m², four bedrooms, a two-car garage") into a spatial program, a floor layout and a 3D massing before anyone can discuss the design. Professional BIM authoring tools such as Revit [P1] are powerful but built for detailed, expert-driven modeling. Commercial generative tools are mostly aimed at site feasibility, multifamily or commercial programs [P2–P5], so the AEC literature reports a gap between language-level intent and valid, structured building models:

- Learned floor-plan generators (House-GAN, HouseDiffusion, Graph2Plan, the Tell2Design dataset) produce plausible 2D layouts. Their output is raster or vector room geometry, though, not a typed building model with walls, hosted openings, slabs and roofs [S6–S11].
- LLM-based approaches can read natural language. However, they lack reliable spatial reasoning and need external checking or a geometry executor [S18, S19]. Strict output formats can also reduce LLM reasoning quality [S15].
- Reviews of generative AI in architecture find that most work targets schematic design, with images as the dominant input and output, and that evaluation is mostly comparative or subjective [S16, S17].

**Problem:** no open, reproducible platform turns a natural-language residential brief into a **validated, structured, element-level building model** that can be shown and inspected in 3D, while keeping the AI away from geometry so that the results are deterministic and testable.

## 4. Target users

Target groups below are **hypotheses**. They still have to be checked through the interviews planned in [02](02_relevance_and_user_evidence.md):

1. Prospective homeowners and residential clients who want to explore a brief before they hire an architect.
2. Architecture and civil-engineering students learning the basics of space programming and BIM.
3. Small architectural or design-build firms that need quick concept options for client conversations.
4. Developers of small residential projects (secondary).

## 5. Aim

Design, implement and evaluate a web platform that turns a natural-language description of a residential building (≤ 3 storeys, rectilinear) into a validated, deterministic, element-level `BuildingModel` and shows it as an interactive 3D model. The AI may only produce structured intent. It never produces geometry.

## 6. Measurable objectives

| # | Objective | Measure / target | Status (2026-10-20) |
|---|---|---|---|
| O1 | A typed building schema with element-level objects (walls, rooms, doors, windows, slabs, stairs, roofs, railings, furniture) and invariant validation | Canonical Pydantic schema; generated TS/Zod contracts; hand-authored fixture validates | Implemented (main), BuildingModel 1.1.0 |
| O2 | Deterministic procedural 3D viewer driven only by the model | Same model ⇒ same scene hash; orbit/select/floor isolation/layers work | Implemented (main) |
| O3 | Deterministic layout engine (spec → model) | Same spec + seed + engine version ⇒ byte-identical model; 10/10 reference specs valid with no rules findings; Hypothesis invariants pass | Implemented (main), `layout@1.2.0` |
| O4 | Natural-language → validated `BuildingSpecification` | Pydantic + rules + form-field validation; ≤ 1 repair; invalid output never accepted | Implemented (main) with the mock provider. Real provider: OpenRouter live-tested once (§10) |
| O5 | Geometric and opening-hosting validation | 37 cataloged geometric constraints with machine-readable findings; every generated model has 0 errors | Implemented (main), K2.5 |
| O6 | Expressive design intent (facade color, facade-specific window emphasis, room orientation, design systems) | Intent visibly changes the model; conflicts reported, never silently changed | Committed, not merged (branch `phase-3.5-k3-design-systems`) |
| O7 | Immutable versions and generation history | Each generation is a new version; history stored with provenance | Implemented (main). Compare/restore: Planned (Phase 5) |
| O8 | Empirical evaluation | Interpretation accuracy ≥ 90 % on an eval prompt set; geometry pass rate 100 %; determinism 100 %; latency and cost reported; user rating | **Not started.** Plan in [09](09_verification_and_evaluation_plan.md) |
| O9 | User-needs evidence | 3–5 documented discussions with potential users | **Not started.** Protocol ready in [02](02_relevance_and_user_evidence.md) |

## 7. Expected outcomes

- A working web prototype (Next.js + FastAPI + PostgreSQL) covering the NL → spec → layout → model → 3D pipeline.
- A documented building-model schema and geometric-constraint catalog.
- An evaluation report: interpretation accuracy, validity, determinism, latency and cost, comparing the deterministic mock baseline with a real LLM.
- A diploma thesis and a defense demo.

## 8. Scope and exclusions

**In scope (v1):** residential, rectilinear plans, 1–3 storeys. Walls, rooms, doors, windows, slabs, straight stairs, flat/gable/hip roofs, railings, placeholder furniture. Metric units. A conceptual rules profile (`generic-residential@1`). English UI.

**Out of scope or not claimed:**
- Construction-ready, permit-ready or professionally certified designs. The platform is **conceptual**, and every view shows the single-source disclaimer (`app/core/disclaimer.py`).
- Structural, MEP, energy or code-compliance analysis. Rules checks are conceptual, not a building-code check.
- Non-rectilinear geometry, basements, commercial buildings, more than 3 storeys.
- Real-time collaboration, IFC export, 2D drawing sets. These are later backlog items in `docs/roadmap.md`.

## 9. Technical complexity

- **Two-language contract system:** Pydantic models are canonical, and JSON Schema, TypeScript types and Zod validators are generated from them (`pnpm schema`). Drift fails the tests.
- **Deterministic generative engine:** a program → skeleton → seeded candidate search → scoring → element construction pipeline. Determinism is tested across two `PYTHONHASHSEED`s, plus Hypothesis property tests and golden files with geometry fingerprints.
- **Geometric reasoning:** host-relative openings, wall joins, room-boundary/wall consistency, stair/slab voids and roof supports. These are 37 constraints shared between generation and validation (`building/hosting.py`).
- **Procedural 3D in the browser:** a pure-TS geometry engine (panel decomposition instead of CSG, content-keyed geometry reuse) rendered with React Three Fiber.
- **Safe LLM integration:** structured outputs with a validation and repair loop, a vendor-neutral provider interface (mock, Anthropic, OpenRouter), prompt-injection quoting, rate limits, and a schema-in-prompt fallback when a provider rejects a large schema.
- **Architectural knowledge layer:** source-attributed knowledge packs, families/types/assemblies, and gated approval workflows.

## 10. Current project status (verified 2026-10-20)

Git: local repository with **no remote configured**. `main` = `7830248`. 14 commits from 2026-09-27 to 2026-09-29. Full detail in [10](10_project_management_and_risks.md) §1.

| Milestone | Status | Evidence |
|---|---|---|
| Phase 0 — foundations (monorepo, auth, projects, CI file) | Implemented (main). Docker Compose **not verified** (no Docker on dev machine). CI **never run** (no remote) | `docs/roadmap.md` Phase 0 checklist |
| Phase 1 — hand-authored model → procedural 3D | Implemented (main) | Roadmap checklist; screenshot `assets/screenshots/01-demo-house-viewer.png` |
| Phase 2 — `BuildingSpecification` + deterministic layout engine | Implemented (main) | 10 reference specs + golden files; Hypothesis tests |
| Phase 3 — AI building generation | Implemented (main). `AnthropicProvider` unit-tested only (never called live) | Roadmap Phase 3 checklist |
| OpenRouter provider (Claude Opus 5.5) + schema-in-prompt fallback | Implemented (main). **Live-tested once** (single call, recorded in `docs/roadmap.md`) | Commits `5b18975`, `7830248` |
| Phase 3.5 K1 — knowledge foundation | Implemented (main) | `bcfb278` |
| Phase 3.5 K2 — families, types, assemblies (BuildingModel 1.1.0) | Implemented (main). Records stay `draft` pending human review | `9d94bb0` (`docs/roadmap.md` still says "branch, awaiting review" for K2, which is out of date) |
| Phase 3.5 K2.5 — geometry and placement validation (`layout@1.2.0`) | Implemented (main) | `77fea02` |
| Phase 3.5 K3 — design systems + expressive design intent (`layout@1.3.0`, spec 1.1.0, model 1.2.0) | **Committed, not merged**: branch `phase-3.5-k3-design-systems` (`cc59d3f`), awaiting review. Its tests were **not re-run** on 2026-10-20 | Commit message and branch roadmap; one live OpenRouter call recorded there |
| K4–K6, Phase 4 (quantities/cost) … Phase 8 | Not started | `docs/roadmap.md` |

**Automated checks re-run on `main` on 2026-10-20 (this sprint):** web Vitest **135 passed** (23 files). API pytest **582 passed, 2 skipped** (the two live-provider tests, skipped by design). `pnpm lint` clean (ESLint, ruff, ruff format, import-linter **5 contracts kept**). `pnpm typecheck` clean (tsc, mypy: "no issues found in 182 source files").

**Current limitations:** one plan scheme (double-loaded corridor bands); rectilinear only. Knowledge, type and design-system records are all `draft`, so the engines don't consume them yet. No eval suite. No quantities or cost. No version compare/restore. No NL modification. Not deployed. No user evidence yet.

## 11. Technologies used (from the code, not the plan)

Web: Next.js 16.3, React 19.2, TypeScript (strict), three 0.186, @react-three/fiber 9, @react-three/drei 10, Zustand 5, TanStack Query 5, Zod 4, Tailwind 4, Vitest 5. API: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic, PostgreSQL 16, argon2, shapely, Hypothesis, httpx. The `anthropic` SDK is used only in its provider adapter. Tooling: pnpm workspaces, uv, ruff, mypy (strict), import-linter, ESLint. The justification for each choice is in [05](05_technology_comparison.md).

## 12. Proposed evaluation method

Summary of [09](09_verification_and_evaluation_plan.md):
1. **Automated verification:** unit, property, golden and integration tests (already in place, re-run per release).
2. **Interpretation experiment:** a fixed set of 40 or more prompts with expected spec facts. Compare `MockAIProvider` (deterministic baseline) against a real LLM through OpenRouter on floor count, room counts, area tolerance, garage/balcony presence, and design-intent fields (K3, if merged). Hold prompt version, rules profile, engine version and seed constant.
3. **Validity and determinism:** geometry-validation pass rate, opening-hosting errors, and byte-identical regeneration.
4. **Performance and cost:** end-to-end latency by stage, and tokens/cost per generation from provider responses.
5. **User assessment:** a short task-based session with 3–5 participants from the interview pool (SUS-style questionnaire plus a layout plausibility rating). This only happens after the ethics and consent steps in [02](02_relevance_and_user_evidence.md).
