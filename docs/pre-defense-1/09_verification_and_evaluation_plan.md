# 09 — Verification and Evaluation Plan

> Part A lists **evidence that already exists** (re-run or recorded). Part B is the **plan for experiments that haven't been run yet**.

## Part A — Evidence already collected

| # | Evidence | Date / source | Value | Nature |
|---|---|---|---|---|
| A1 | Web unit/component tests (Vitest) on `main` | Re-run 2026-10-20 (this sprint) | 135 passed, 23 files | Automated |
| A2 | API tests (pytest, real PostgreSQL, mock AI) on `main` | Re-run 2026-10-20 | 582 passed, 2 skipped (live-provider tests skipped by design) | Automated |
| A3 | Lint + type checks on `main` | Re-run 2026-10-20 | ESLint, ruff, ruff format, import-linter 5/5 kept, tsc, mypy (182 files) all clean | Automated |
| A4 | Reference-spec suite: 10 specs valid, reachable, no rules findings, GFA ±3 %, golden files equal | Part of A2 | 10/10 | Automated |
| A5 | Property-based invariants (Hypothesis): random specs give no model errors, all rooms reachable, program present, reproducible | Part of A2; roadmap Phase 2 records 40 random specs | Pass | Automated |
| A6 | Determinism across two `PYTHONHASHSEED`s | Part of A2 (`layout/test_engine.py`) | Pass | Automated |
| A7 | Live OpenRouter call #1 (`anthropic/claude-opus-5.5`), main | Recorded in `docs/roadmap.md`, 2026-09-29 | Strict schema rejected ("compiled grammar is too large") → schema-in-prompt fallback; 1 call, no repair; 2 floors, 222.3 m² (asked 220), 3 bed, 2 bath, 1 WC, 2-car garage; no geometry or rules findings | **Single observation** (n = 1) |
| A8 | Live OpenRouter call #2, K3 branch | Recorded in branch commit `3fbd3c4`, 2026-09-29 | Yellow facade on all 11 exterior walls; 3 panoramic windows all on the rear; front standard only; living + dining on the rear; no findings; no repair | Single observation, **branch only** |
| A9 | Mock end-to-end generation duration | Screenshot 09, 2026-10-20 | 1.3 s | Single observation |
| A10 | Viewer scene build for the generated 280 m² house | Screenshots 05–06 status line, dev mode | 117 elements, 144 meshes, ~7k triangles, built in 39–40 ms | Single observation |
| A11 | Browser E2E walkthroughs | `docs/roadmap.md` Phases 0–3 checklists; screenshots 01–12 | Pass | Manual |

Not collected: interpretation accuracy over a prompt set, latency distributions, API cost, fps, user ratings, Docker Compose run, CI run.

## Part B — Evaluation plan

### B1. Test levels

| Level | Scope | Tooling | Runs | Exists? |
|---|---|---|---|---|
| L1 Unit | Domain functions, builders, validators, providers (fake transports) | pytest, Vitest | Every change | ✔ |
| L2 Property | Layout invariants over random specs | Hypothesis | Every change | ✔ |
| L3 Golden / regression | 10 reference specs: model hash + geometry fingerprint; web scene hash | pytest, Vitest | Every change | ✔ |
| L4 Integration / API | Auth, ownership, generation jobs, AI pipeline with mock provider, migrations | pytest + httpx + PostgreSQL | Every change | ✔ |
| L5 System / E2E | Browser walkthrough of scenarios S1–S10 ([08](08_ux_prototype.md)) | Manual now; Playwright planned | Before each defense | ◐ manual only |
| L6 Interpretation experiment | NL → spec accuracy, mock vs live LLM | Eval harness (`pnpm eval`, **to be written**, roadmap Phase 3 deferred item) | Once per pre-defense | ☐ |
| L7 Performance | End-to-end and per-call latency, viewer fps | `ai_generations` / `ai_runs` durations, browser performance panel | Once per pre-defense | ☐ |
| L8 User evaluation | Task-based usability + plausibility rating | Protocol below | Once before final defense | ☐ |

### B2. Datasets and prompts

**Eval prompt set `eval-prompts@1`** (to be created as `data/fixtures/eval/prompts.v1.json`, 40 prompts, written by the team **before** any live run and frozen with a hash):

| Category | n | Description | Expected outcome |
|---|---|---|---|
| E-C Complete briefs | 12 | Floors, area, bedrooms, bathrooms, garage/balcony given | Spec facts exactly as stated |
| E-P Partial briefs | 10 | Some facts missing (e.g. no area) | Spec with documented assumptions |
| E-V Vague / non-building | 5 | "I want a nice house", unrelated text | Clarification, no version |
| E-X Conflicting / infeasible | 5 | e.g. 6 bedrooms in 60 m², 4 storeys | Rejection or clarification with reasons; never an invalid model |
| E-I Design intent | 5 | Facade color, panoramic windows to the garden, living room to the rear | Run only against K3 (if merged); spec design fields correct |
| E-L Language variants | 3 | Russian-language briefs | Same facts as their English twins |

**Annotation:** for each prompt, both students independently write the expected spec facts (`floors`, `total_area_m2` ±10 %, room counts by type, `garage.cars`, balcony/terrace presence, style, roof, design-intent fields). They then reconcile, and inter-annotator agreement (percentage agreement per fact) is reported. The 10 existing reference specs (`data/fixtures/specs`) are the layout-level dataset.

### B3. Metrics

| Metric | Definition | Applies to |
|---|---|---|
| M1 Floor-count accuracy | share of prompts where spec `floors` = expected | E-C, E-P, E-L |
| M2 Room-count accuracy | share of (prompt, room type) pairs where count = expected (bedrooms, bathrooms, WCs) | E-C, E-P, E-L |
| M3 Area accuracy | share of prompts with spec area within ±10 % of the expected value (when stated) | E-C, E-L |
| M4 Fact-level interpretation accuracy | correct facts / annotated facts, all categories | All except E-V |
| M5 Clarification precision / recall | clarifications on E-V (recall) vs unnecessary clarifications on E-C (precision) | E-V, E-C |
| M6 Generation success rate | prompts producing a version (or a correct clarification/rejection) / prompts | All |
| M7 Geometry-validation pass rate | generated models with 0 `validate_model` errors / generated models | All generated |
| M8 Opening-hosting correctness | openings with zero `host.*` / `opening.*` findings / openings | All generated |
| M9 Determinism | regenerations (same spec, seed, profile, engine) with identical model hash / regenerations | Reference specs + all generated specs re-run |
| M10 Repair rate | generations needing a repair call / generations | Live LLM |
| M11 Latency | end-to-end seconds (`ai_generations.duration_ms`, `started_at`/`finished_at`) and per provider call (`ai_runs`): median, p95. Per-stage timing for layout/validation isn't stored yet and would need extra timing in the eval harness | Mock and live |
| M12 API cost | tokens in/out (already stored: `ai_generations.input_tokens/output_tokens`, `ai_runs`) × published price on the run date; cost per prompt | Live |
| M13 Design-intent satisfaction (K3) | intent fields realized in the model (e.g. colored exterior walls / exterior walls; preferred facade windows) | E-I, K3 only |
| M14 Usability | SUS score (0–100); task completion; time on task | User session |
| M15 Layout plausibility | participant rating 1–5 of 3 generated houses ("plausible as an early concept?") | User session |

### B4. Measurement conditions and controls

To make the mock-vs-LLM comparison fair and repeatable, each run records and fixes:

| Variable | Control |
|---|---|
| Prompt text | Frozen set `eval-prompts@1` (file hash recorded) |
| Prompt template | `PROMPT_VERSION` (`building-generation@1` on main; `@2` on K3). Never mix versions within a comparison |
| Output mode | Strict JSON-Schema vs schema-in-prompt fallback, recorded per call. Report each mode separately (tests the concern in [S15]) |
| Model | Exact provider model string (e.g. `anthropic/claude-opus-5.5`) + OpenRouter routing info from the response |
| Sampling | Provider settings as configured (`AI_EFFORT`, max tokens), recorded in the run file |
| Seed | Layout seed fixed at 0 |
| Rules profile | `generic-residential@1` |
| Engine version | `layout@1.2.0` (main). K3 results reported separately under `layout@1.3.0` |
| Repairs | `AI_MAX_REPAIRS=1` |
| Repetitions | Live LLM: each prompt run **3×** to measure variance (mock is deterministic: 1×) |
| Environment | Same machine, same date window, network noted; commit hash recorded |

**Baseline:** `MockAIProvider`, the deterministic keyword interpreter in `ai/providers/mock_interpreter.py`. It is a lower-bound, rule-based baseline: if the LLM doesn't beat it on M4 for E-P/E-L, using an LLM isn't justified. An optional second baseline is "LLM without validation/repair" (raw first answer), which isolates what the validation loop contributes.

**Budget guard:** live runs = 40 prompts × 3 repetitions ≤ 120 calls (+ repairs). Before running, estimate the cost from A7's token usage and get the supervisor's or team's approval for a spending cap `[BUDGET — TO CONFIRM]`. Live runs never go in CI (CLAUDE.md rule 13).

### B5. Acceptance thresholds (proposed, to be agreed with the supervisor)

| Metric | Threshold | Rationale |
|---|---|---|
| M7 geometry pass rate | **100 %** | Validity by construction is the core claim |
| M8 hosting correctness | **100 %** | Same |
| M9 determinism | **100 %** | Same |
| M4 fact accuracy (live LLM) | ≥ 90 % | Roadmap Phase 3 exit criterion "eval pass rate ≥ 90 %" |
| M1 floor accuracy | ≥ 95 % | Most explicit fact |
| M5 clarification recall on E-V | ≥ 80 %; unnecessary clarifications on E-C ≤ 10 % | Balance between asking and guessing |
| M6 success rate | ≥ 90 % | Usable pipeline |
| M11 latency | Mock: median < 5 s. Live: report median/p95; target median ≤ 60 s | Usability; timeout 120 s |
| M12 cost | Report only (no threshold) | Depends on pricing at run time |
| M14 SUS | ≥ 68 | Commonly used "average" SUS benchmark |
| M15 plausibility | Median ≥ 3 / 5 | Early-concept usefulness |

### B6. User evaluation protocol (L8)

3–5 participants from the interview pool ([02](02_relevance_and_user_evidence.md)), with consent. Tasks: (1) generate a house from your own description; (2) isolate floor 2 and find the master bedroom's area; (3) select a window and say which wall hosts it; (4) find one assumption the system made; (5) create a second version and switch back to v1. Measure completion, time and errors, then SUS and M15. Use anonymized IDs only.

### B7. Reporting format

1. Per-run machine-readable file `eval/results/<date>_<provider>_<mode>.csv` with columns: `prompt_id, category, repetition, provider, model, prompt_version, output_mode, seed, rules_profile, engine_version, commit, outcome, repaired, floors_ok, rooms_ok, area_ok, facts_correct, facts_total, geometry_errors, hosting_errors, model_sha256, latency_total_s, latency_ai_s, latency_layout_s, tokens_in, tokens_out, cost_usd`.
2. A summary table in the thesis:

| Provider / mode | n | M1 | M2 | M3 | M4 | M5 | M6 | M7 | M8 | M9 | M10 | M11 median / p95 | M12 / prompt |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Mock (baseline) | [TO MEASURE] | | | | | | | | | | | | — |
| OpenRouter Claude Opus 5.5, strict | [TO MEASURE] | | | | | | | | | | | | |
| OpenRouter Claude Opus 5.5, schema-in-prompt | [TO MEASURE] | | | | | | | | | | | | |

3. A failure analysis: every wrong fact categorized (misread number, missing room, hallucinated feature, clarification error).
4. Threats to validity: small prompt set, team-written prompts, single model, pricing changes, non-determinism of provider routing.
