# AI Pipeline

Status: **Accepted (v0.1)** · Code: `apps/api/app/modules/ai/`

## 1. Role of AI

AI is used for **language ↔ structure**, never for geometry. The AI generates a `BuildingSpecification` and typed modification operations only; it never generates or manipulates meshes. The deterministic layout/geometry engine is solely responsible for geometry. AI is connected only after the spec → model → 3D pipeline works without it (roadmap Phase 3).

| Task | Input | Output (validated) |
|---|---|---|
| **Interpret** | NL prompt (+ optional current spec) | `BuildingSpecification` |
| **Plan modification** | NL instruction + compact model summary | `ModificationPlan` (typed operations) |
| **Analyze** | model summary + quantities + cost | `DesignAnalysis` (structured findings + prose) |
| **Explain / answer** (later) | question + context | text |

Deterministic engines do everything with coordinates. This is the single most important AI decision: it keeps output valid, reproducible and cheap, and lets us swap models freely.

## 2. Provider abstraction

```python
# app/modules/ai/provider.py
class AIProvider(Protocol):
    name: str

    async def generate_structured(
        self,
        *,
        task: AITask,                     # "interpret" | "modify" | "analyze"
        messages: list[AIMessage],        # system + user (+ repair turns)
        output_schema: type[BaseModel],   # Pydantic model → JSON Schema for tool/structured output
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> StructuredResult[T]: ...        # parsed object | raw text, usage, latency, provider meta

    async def generate_text(self, *, messages, temperature=0.4, max_tokens=2048) -> TextResult: ...
```

Implementations:

| Provider | Purpose |
|---|---|
| `MockAIProvider` | Default for local dev and **all automated tests**. Deterministic rule/regex parser: extracts area, storeys, bedroom/bathroom counts, garage cars, keywords (balcony, panoramic, minimalist, flat roof…), fills defaults, records assumptions. Also canned ModificationPlans for common phrases ("make X bigger", "add a window to …"). |
| `AnthropicProvider` | **First real provider (decided).** Claude via tool use / structured output |
| `OpenAICompatibleProvider` | Later. Any OpenAI-compatible endpoint (OpenAI, local models via Ollama/vLLM) |

Selection via config: `AI_PROVIDER=mock|anthropic|openai_compatible`, `AI_MODEL=...`, per-task overrides (`AI_MODEL_INTERPRET`, …). Vendor SDKs are imported **only** inside their adapter file. No other module knows which vendor is used.

## 3. Interpret pipeline (NL → spec)

```
prompt
  │
  ▼
1. Pre-process      – trim, language detect, length limit (4k chars), strip injection-y markup
  ▼
2. Build messages   – system prompt (role, rules, units, enums, defaults, examples)
                      + user prompt (+ current spec when refining)
  ▼
3. Provider call    – structured output against BuildingSpecification JSON Schema
  ▼
4. Parse            – Pydantic (tier-1)
  ▼
5. Semantic rules   – tier-2 validation
  ▼  errors?
  ├─ yes → Repair turn: send the issues list (path + message) back, ask for corrected JSON
  │        (max 2 repairs) → go to 4
  ▼
6. Normalize        – apply defaults, clamp to safe ranges, record every inferred value in `assumptions`
  ▼
7. Feasibility      – quick layout pre-check (tier-3); if infeasible, return spec + issues to user
  ▼
BuildingSpecification (+ assumptions + open_questions) → user confirms/edits → layout
```

Key rules for prompts:
- Model must **not** invent coordinates, dimensions of walls, or element IDs.
- Every value not literally stated by the user must appear in `assumptions` with a reason.
- Ambiguities go to `open_questions`; the model must not ask questions *instead of* producing a spec — it produces the best spec and lists questions.
- Units: always metric in output; the pre-processor/LLM converts ft²/ft if the user uses them (conversion recorded as assumption).

The UI shows the spec as an editable form with assumptions highlighted **before** generating geometry (can be skipped with "Generate directly").

## 4. Modification pipeline (NL → operations)

```
instruction + ModelSummary + current selection
  │
  ▼
provider.generate_structured(output_schema=ModificationPlan)
  │
  ▼
ModificationPlan {
  intent_summary: "Widen the kitchen by 2 m to the east and add a skylight over the island",
  operations: [Operation, ...],          # see building-model.md §5
  requires_relayout: bool,               # true if any change_spec op
  affected_element_ids: [...],
  questions: [...]                       # if instruction is ambiguous
}
  │
  ▼
validate ops (refs exist; params in range) → dry-run apply → model invariants → diff
  │
  ▼
UI preview: diff highlighted in 3D + quantity/cost delta → user Accepts → commit version
```

**ModelSummary** is a compact, token-efficient projection of the model the LLM can reference by ID:

```jsonc
{
  "levels": [{"id":"L0","name":"Ground floor"}],
  "rooms": [{"id":"<uuid>","ref":"R3","type":"kitchen","level":"L0","area":18.4,"bbox":[4.2,0,8.8,4.0],
             "walls":{"N":"W12","E":"W13"}, "windows":2}],
  "walls": [{"ref":"W12","id":"<uuid>","kind":"exterior","len":4.6,"orientation":"N"}],
  "selection": ["<uuid>"]
}
```

Short refs (`R3`, `W12`) reduce tokens and errors; the pipeline maps refs → UUIDs after the call. Full geometry is never sent.

Deictic references ("this wall", "the selected room") resolve through `selection`.

## 5. Analysis pipeline

Input: ModelSummary + quantity summary + cost breakdown + validation warnings.
Output `DesignAnalysis { findings: [{category, severity, message, element_ids}], summary_markdown }`.
Categories: space efficiency, daylight/orientation, circulation, cost drivers, energy hints. Deterministic metrics (net-to-gross ratio, window-to-wall ratio per façade, cost/m²) are **computed in code and passed in** — the LLM interprets numbers, it doesn't compute them.

## 6. Observability & persistence

Every call is stored in `ai_runs` ([database.md](database.md)): task, provider, model, prompt version, input (redacted), raw output, parsed output, validation issues, repair count, tokens, latency, cost, status. Used for debugging, evals and spend tracking.

Prompts are versioned files: `ai/prompts/interpret/v3.md`. `prompt_version` is stored with each run.

## 7. Safety, limits & cost

- Per-user rate limit and daily token budget (config).
- Prompt length limits; outputs always schema-validated — **untrusted until validated**.
- User text is placed in the user turn only, never concatenated into the system prompt.
- Timeouts (60 s) with one retry on transient errors; provider errors map to `AI_UNAVAILABLE`.
- No user PII is sent beyond the building description.

## 8. Evaluation

`apps/api/evals/` holds ~50 prompts with expected properties (not exact JSON), e.g.:

```yaml
- prompt: "Modern two-story house, 280 m², 4 bedrooms, 3 bathrooms, open kitchen, 2-car garage, balcony"
  expect:
    targets.storeys: 2
    targets.gross_floor_area_m2: {between: [260, 300]}
    count(rooms.type == bedroom): 4
    count(rooms.type in [bathroom, en_suite]): 3
    features.garage.cars: 2
    len(features.balconies): {gte: 1}
```

`pnpm eval PROVIDER=anthropic` scores a provider/prompt version. Required before changing default model or prompt version. Not part of normal CI (costs money); MockAIProvider covers CI.
