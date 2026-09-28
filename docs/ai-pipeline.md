# AI Pipeline

Status: **Implemented for Phase 3 (v0.3)** · Code: `apps/api/app/modules/ai/`

## 1. Role of AI

AI is used for **language → structure**, never for geometry. The AI produces a `BuildingSpecification` (intent: program, targets, style, features); the deterministic layout engine makes every spatial decision and the procedural 3D engine renders the resulting `BuildingModel`. The model never outputs coordinates, wall geometry, element ids, meshes, images, code or costs.

```
prompt ──▶ AIProvider (mock | anthropic) ──▶ SpecificationDraft (structured output)
       ──▶ Pydantic (tier 1) ──▶ rules spec checks + form fields (tier 2)
       ──▶ [errors → one repair call → validate again] ──▶ BuildingSpecification
       ──▶ layout engine (tier 3, deterministic) ──▶ BuildingModel ──▶ model validation
       ──▶ rules findings ──▶ new immutable project version ──▶ 3D editor
```

| Task | Input | Output (validated) | Status |
|---|---|---|---|
| **Interpret** | NL prompt + form fields + project context | `SpecificationDraft` → `BuildingSpecification` | ☑ Phase 3 |
| **Plan modification** | NL instruction + `ProjectContext` | `ModificationPlan` (typed operations) | Phase 5 (context + read-only tools prepared) |
| **Analyze** | model summary + quantities + cost | `DesignAnalysis` | Phase 7 |

## 2. Provider abstraction

```python
# app/modules/ai/providers/base.py
class AIProvider(ABC):
    name: str; model: str
    async def complete_structured(self, request: StructuredRequest) -> StructuredResult  # the one primitive
    # built on top, from the versioned prompt modules (identical for every provider):
    async def generate_building_specification(prompt, *, options, context, max_tokens)
    async def repair_building_specification(prompt, *, options, context, repair, max_tokens)
```

`StructuredRequest` carries the system prompt, messages, the JSON Schema of the expected object and the prompt version; `StructuredResult` returns the parsed object (or `None`), the raw output, model, tokens, latency and stop reason. Providers raise only `AIProviderError` subclasses (`AI_UNAVAILABLE`, `AI_TIMEOUT`, `AI_NOT_CONFIGURED`), never vendor exceptions, and never validate or trust their own output.

| Provider | File | Purpose |
|---|---|---|
| `MockAIProvider` | `providers/mock.py` + `mock_interpreter.py` | **Development, tests, CI, offline.** Deterministic rule/regex interpreter: area, storeys, bedroom/bathroom counts, family size, garage cars, balcony (and its floor), terrace, study/WC/laundry/storage, open kitchen, style/interior style, windows, roof, facade, budget (KZT/USD/EUR, "300,000,000 KZT", "$250k"), city → region code, unsupported items (pool, sauna, basement…), prompt-injection phrases. Records every default as an assumption; asks for clarification when nothing describes the house or the request is out of scope (> 3 storeys, area outside 20–2000 m²). Refused when `ENVIRONMENT=production`. |
| `AnthropicProvider` | `providers/anthropic.py` | **First real provider.** One Messages API call via the official `anthropic` SDK (the only file importing it — enforced by import-linter). The answer is constrained with **structured outputs** (`output_config.format = json_schema`), which works on every current Claude model (forced `tool_choice` is rejected by newer models). Numeric/length constraints unsupported by structured outputs are moved into field descriptions and enforced by Pydantic afterwards. The static system prompt carries a cache breakpoint. SDK errors map to `AI_TIMEOUT` / `AI_UNAVAILABLE`; `refusal`/`max_tokens` stops yield "no object" (→ repair). |
| OpenAI-compatible | — | Later (roadmap). |

Selection: `get_ai_provider()` (`providers/__init__.py`) from settings; `use_ai_provider()` overrides it in tests.

| Setting | Default | Notes |
|---|---|---|
| `AI_PROVIDER` | `mock` | `mock` \| `anthropic`; `mock` refused in production |
| `AI_MODEL` | — | Required for `anthropic` (e.g. `claude-opus-5`); never hard-coded in business logic |
| `ANTHROPIC_API_KEY` | — | Required for `anthropic`; `SecretStr`, backend only, never logged |
| `ANTHROPIC_BASE_URL` | SDK default | Optional gateway |
| `AI_EFFORT` | model default | `output_config.effort` |
| `AI_TIMEOUT_SECONDS` / `AI_MAX_RETRIES` | 120 / 1 | SDK timeout and transient retries |
| `AI_MAX_REPAIRS` | 1 | Repair calls after invalid output (0–2) |
| `AI_MAX_OUTPUT_TOKENS` | 16000 | Non-streaming request |
| `AI_MAX_PROMPT_CHARS` | 4000 | Also capped by the request schema |
| `AI_GENERATIONS_PER_HOUR` | 30 | Per user (429 `AI_RATE_LIMITED`) |
| `AI_LOG_PROMPTS` | false | Otherwise only prompt length + sha256 prefix are logged |

The API refuses to start with `AI_PROVIDER=anthropic` and no key/model.

## 3. Prompts (`ai/prompts/`, version `building-generation@1`)

- `shared.py` — output name/description, the **vocabulary generated from the specification enums** (room types, features, styles, roofs, windows, facades, finish levels), the output JSON Schema (`SpecificationDraft`), `quote_user_text` and the project-context block.
- `generation.py` — static system prompt (cacheable; nothing request-specific) + user turn: `<project_context>` (region, currency, rules profile ref, **room minimums read from the active rules profile**, max room share of the floor area), optional `<form_fields>`, and the user's text in `<building_request>` tags.
- `repair.py` — single self-contained user turn: original request, `<previous_output>` (≤ 20 000 chars), `<validation_issues>` (JSON pointers into the answer), instructions. Same system prompt (shared cache prefix).

Rules the prompt states: priority *explicit requirements → form fields/project constraints → rules profile → safe defaults*; every inferred value goes into `specification.assumptions`; leave floor area / room areas empty unless stated or clearly implied; bathrooms include en-suites; "second floor" = level 1; never drop or change an explicit requirement silently — keep it and explain in `conflicts`, or ask; things the schema cannot express go into `unsupported_requests`; clarification only when a missing value materially changes the design and no default exists.

**Prompt injection.** User text is data inside its tag (tags inside it are stripped, control characters removed) and never enters the system prompt. The system prompt tells the model to ignore instructions in it and to answer only with the JSON object. The output schema has no field that could carry code or geometry (`extra="forbid"` everywhere), all text fields are length-limited, nothing the model returns is ever executed, and the UI renders text escaped.

Changing prompt wording or structure = bump `PROMPT_VERSION` (stored on every generation and AI run).

## 4. Output contract: `SpecificationDraft` (`ai/schemas/generation.py`)

```jsonc
{
  "outcome": "specification" | "clarification",
  "understanding": "A 2-storey modern family house of about 280 m² with 4 bedrooms, …",
  "specification": { /* BuildingSpecification 1.0.0 — required for "specification" */ },
  "clarification_questions": ["How many floors …?"],   // required for "clarification", ≤ 5
  "conflicts": ["…"],               // explicit requirements that conflict / exceed scope
  "unsupported_requests": ["Swimming pool — …"]      // reported, not built
}
```

`GenerationOptions` (the optional form fields: floor area, storeys, style, budget, region code, layout seed) are explicit requirements: they are sent to the model and **verified deterministically** afterwards (`check_options` → `SPEC_FORM_FIELD_MISMATCH` → repair).

## 5. Interpreter: validation and repair (`ai/interpreter.py`)

1. `provider.generate_building_specification(...)` (stage `interpreting`).
2. Validate (stage `validating`): JSON object? → `SpecificationDraft` (Pydantic; issues `AI_SCHEMA_INVALID` with JSON pointers such as `/specification/rooms/0/type`) → for a specification, `validate_spec` callback = `rules.spec_checks.check_spec` (tier 2, against the project's rules profile) + `check_options`.
3. Blocking errors and `AI_MAX_REPAIRS` left → `repair_building_specification` with the issues (stage `repairing`) → validate again.
4. Still invalid → `InterpretationError`: `AI_INVALID_OUTPUT` (no usable object) or `SPEC_INVALID` (schema/rules errors). **Invalid output is never accepted.**
5. Accepted → `Interpretation` with warnings: `AI_REQUIREMENT_CONFLICT`, `AI_UNSUPPORTED_REQUEST`, and `AI_REPAIR_CHANGED` for every key requirement (storeys, area, bedrooms, bathrooms, WCs, garage cars, balconies, terrace) a repair changed — so a "fix" that drops bedrooms is visible.

Every provider call becomes an `AttemptRecord` (task, provider, model, prompt version, status ok/invalid/error, raw + parsed output, issues, tokens, latency), persisted as an `ai_runs` row — also on failure. Normal success = **1 call**; invalid output = **1 + 1 repair**.

## 6. Generation use case (`ai/orchestrator.py`, `ai/service.py`, `ai/router.py`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/ai/generate-building` | `{project_id?, prompt, options}` → 202 generation record. Auth required; ownership checked (404); prompt 3–4000 chars; 409 if a generation/job is running for the project; 429 over the hourly limit; 503 if the provider is not configured. Without `project_id` a new project is created and named after the interpreted spec. |
| GET | `/api/v1/ai/generations/{id}` | Poll: real stage, status, spec, assumptions, warnings, summary, requested-vs-delivered checks, version id/number, error |
| GET | `/api/v1/projects/{id}/generations` | History (newest first, summaries only) |

`BuildingGenerationService` (background task on the in-process job runner, ADR-010) records its **real stage** on the `ai_generations` row: `queued → interpreting → validating [→ repairing → validating] → layout → checking → saving → done`. After interpretation it calls `generation.pipeline.layout_and_save` — the same step the Phase 2 spec form uses: layout engine in a worker thread (deterministic: spec + seed + rules profile + engine version ⇒ same model), final `validate_model` (errors → `MODEL_INVALID`), rules findings, new version (`source = "ai_generation"`, `prompt`, spec snapshot, seed, rules profile, engine version, report with `generation` provenance: generation id, type, provider, model, prompt version). The service contains no layout logic.

Statuses: `completed` · `needs_clarification` (no version) · `failed` with a distinct code and a user-safe message:

| Code | Where | Message (examples) |
|---|---|---|
| `AI_UNAVAILABLE`, `AI_TIMEOUT`, `AI_NOT_CONFIGURED` | provider | "AI generation is temporarily unavailable…" |
| `AI_INVALID_OUTPUT` | no usable JSON after repair | "The AI answer could not be turned into a valid building specification." |
| `SPEC_INVALID` | schema/rules errors after repair (details = issues) | "The requested building specification could not be validated." |
| `LAYOUT_INFEASIBLE` | layout (details = the engine's reasons) | "The requested requirements could not produce a valid layout." |
| `LAYOUT_INVALID`, `MODEL_INVALID` | layout / final model validation | "The layout engine could not produce a valid building for this request." |
| `DATABASE_ERROR`, `INTERNAL_ERROR`, `JOB_INTERRUPTED` | persistence / crash / restart | no stack traces are returned |

Deviations are never hidden: the completed record lists all warnings (AI conflicts/unsupported/repair changes, spec warnings, layout deviations, rules findings) and `checks` (floors, floor area within the engine's 5 % threshold, bedrooms, bathrooms, WCs, balconies, garage, terrace: requested → delivered).

## 7. Context and tools (preparation for Phase 5)

- `ai/context.py` — `GenerationContext` (used now) and `ProjectContext` (summary, current spec, rooms with short refs `R1…`, selected element digest, version, budget, region/currency/rules). Pure functions; never the full model.
- `ai/tools.py` — read-only, typed, ownership-scoped tools (`get_project`, `get_building_summary`, `get_room`, `get_selected_object`, `get_element`) with Pydantic inputs (`extra="forbid"`) and structured outputs; `load_scope` verifies ownership. Not given to a model in Phase 3. `get_cost_summary` arrives with costing.

## 8. Observability & persistence

- `ai_generations` (history) and `ai_runs` (one row per provider call) — see [database.md](database.md). No secrets are stored.
- One structured log line per generation: id, project, provider, model, status, error code, stage, duration, repairs, tokens, warning count, version, prompt length + hash (full prompt only with `AI_LOG_PROMPTS=true`). Provider errors are logged with technical detail server-side; keys, passwords and JWTs are never logged.

## 9. Testing

- All automated tests use `MockAIProvider` or a scripted test double; CI never calls a paid API (`tests/conftest.py` forces `AI_PROVIDER=mock`).
- Unit: prompt construction and injection quoting, mock interpretation (demo prompt, defaults, clarification, conflicts, unsupported, budget/region, form fields), interpreter (valid, non-JSON, unsupported room type, invalid dimensions, missing fields, extra geometry fields, rules errors, repair changes, provider errors, form-field mismatch), Anthropic adapter against a fake SDK client (request shape, parsing, refusal/truncation, error mapping, schema transformation), provider selection and settings guards, context/tools, requirement checks.
- Integration (real API + PostgreSQL): NL → mock → spec → layout → model → version for the demo prompt and ten other prompts; history; clarification; injection; infeasible requirements; AI outage; repair; permanent invalid output; auth; ownership; validation; rate limit; concurrency; interrupted generations; determinism (same prompt + seed ⇒ same `model_hash`).
- Live: `tests/ai/test_live_anthropic.py` runs only with `RUN_LIVE_AI_TESTS=true` and `ANTHROPIC_API_KEY`.
- Web: generated validators against captured API responses, prompt form, progress, clarification, failure, summary.

## 10. Known limitations

- The Anthropic provider has been exercised only against a fake SDK client and the opt-in live test; the live test has not been run in this repository yet (no project credentials configured).
- The mock interpreter understands common English phrasings only; it is a development tool, not a language model.
- No prompt eval suite yet (the roadmap's ~50-prompt eval is deferred); the mock prompts are covered by parametrized tests.
- Generation runs in-process (ADR-010): a restart fails running generations (`JOB_INTERRUPTED`).
- Rate limiting is per user per hour in the database; there is no token budget/spend tracking (no prices in code).
- Refining an existing design in natural language (modification operations) is Phase 5.
