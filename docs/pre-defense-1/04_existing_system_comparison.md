# 04 — Existing System Comparison

> Evidence base: official product pages opened on **2026-10-20** [P1–P5] (see [references.md](references.md) §D). These pages are vendor marketing. A "Verified" cell means *the vendor publicly states this capability*. It does not mean the team tested it. No product was installed or trialled for this comparison, so hands-on trials are an outstanding task (EVAL-07 in [10](10_project_management_and_risks.md)).

## 1. Systems selected and why

| System | Vendor | Why relevant | Availability checked |
|---|---|---|---|
| **Autodesk Revit 2027** | Autodesk | The dominant BIM authoring reference: parametric walls/doors/windows, documentation, IFC [P1] | Product page live; "Starting at $251 / month" shown on 2026-10-20 |
| **Autodesk Forma Site Design** (formerly marketed as "Autodesk Forma"; the old URL now redirects) | Autodesk | AI-assisted early-stage site and massing design with Revit hand-off [P2] | Product page live; "Starting at $59 / month", free trial |
| **TestFit** | TestFit Inc. | Generative site and building feasibility, including single-family, with pro forma [P3] | Home page live |
| **Finch** (finch3d.com) | Finch | AI floor-plan generation "grounded in your firm's standards and local codes" [P4] | Home page live; enterprise waitlist mentioned |
| **Hypar** | Hypar | Conversational space planning with Revit export [P5] | Home page live |

## 2. Criteria

Eight criteria, each tied to a BuildAI requirement area:

| C# | Criterion | What counts |
|---|---|---|
| C1 | Natural-language generation | The user describes a design in text and the system generates or changes a design |
| C2 | Structured BIM element model | Typed building elements (walls, doors, windows, slabs…) instead of meshes or images |
| C3 | Layout / program generation | Automatic generation of room or unit layouts from requirements |
| C4 | Geometric / rule validation | Automated checks against rules, codes or standards, reported to the user |
| C5 | Facade / material / appearance control | User control over appearance at concept stage |
| C6 | 3D visualization | Interactive 3D model |
| C7 | 2D documentation | Sheets, drawings, schedules |
| C8 | Quantities / cost | Takeoffs or cost / pro forma |
| C9 | Interoperability / openness | Exchange formats (IFC, Revit), APIs, open source |

## 3. Comparison matrix

Legend: **✔ V** = verified vendor statement (with short evidence) · **— NS** = not stated on the page checked (unknown, **not** "absent") · **(I)** = team inference, labelled as such.

| | Revit 2027 [P1] | Forma Site Design [P2] | TestFit [P3] | Finch [P4] | Hypar [P5] | **BuildAI 3D (main, 2026-10-20)** |
|---|---|---|---|---|---|---|
| **C1 NL generation** | — NS for generation. ✔ V an "AI-powered Autodesk Assistant, grounded in your model and documentation" in **tech preview** (Q&A/actions) | — NS (page mentions "AI-powered analyses" and "design automations") | ✔ V "Prompt your site plans with an AI assistant" via an MCP Connection add-on | — NS (AI agents are described; text input is not stated) | ✔ V "Design together at the speed of conversation" (I: conversational editing; mechanism not detailed) | ✔ Implemented: NL → validated spec → model (mock offline; OpenRouter live-tested once) |
| **C2 Structured BIM elements** | ✔ V "Place wall, doors, and windows in an open, graphical, and parameter-rich system" | — NS (massing model; "turn your proposal into a geolocated Revit project") | — NS (I: layout objects such as units and parking; BIM via Revit integration) | ✔ V delivers "BIM geometry" | — NS (I: space-planning objects; Revit export) | ✔ Typed element model (walls, rooms, doors, windows, slabs, stairs, roofs, railings, furniture) with UUIDs and relationships; **not IFC** |
| **C3 Layout generation** | — NS on overview page | ✔ V "Create your site and massing in minutes with design automations" (site/massing level) | ✔ V "generative design" for site plans; building types incl. single-family and multi-family | ✔ V "Generate buildable floor plans" | ✔ V "Start architectural programming on floor plans", "Test fit" | ✔ Deterministic residential layout engine (1–3 storeys, one plan scheme) |
| **C4 Validation** | — NS on overview page | ✔ V environmental analyses (e.g. sun hours, embodied carbon blog posts); not rule validation | ✔ V "Validate layouts against pro formas" (financial validation) | ✔ V plans "grounded in … local codes" (method not detailed) | ✔ V "Test fit against client requirements" | ✔ 37 geometric constraints + conceptual rules profile + reachability; findings with constraint IDs; **not code compliance** |
| **C5 Appearance control** | ✔ V rendering via Twinmotion for Revit | — NS | — NS | ✔ V "Encode design systems" (firm standards; I: not facade appearance specifically) | — NS | ◐ Main: style/roof/window/facade-material fields in the spec. **K3 branch (not merged):** facade color, per-facade window emphasis, design systems |
| **C6 3D visualization** | ✔ V "Design buildings and infrastructure in 3D" | ✔ V "3D modeling … massing concepts" | — NS on home page (I: likely, not verified) | — NS on home page (I: BIM geometry implies 3D) | (I) home-page image shows a 3D floor plan; not stated in text | ✔ Browser 3D (React Three Fiber): orbit, select, floors, layers, section |
| **C7 2D documentation** | ✔ V "Create project sheets and add your drawings and schedules" | ✔ V "view … Revit Sheets in Forma Board" (review, not authoring) | ✔ V exports to PDF, "Live feasibility reports" | ✔ V "detailed floor plans, area calculations" | — NS | ✘ Not implemented (design report only; plans/sheets planned for Phase 7+) |
| **C8 Quantities / cost** | ✔ V schedules (I: quantity schedules; cost estimating not stated) | — NS (carbon analysis stated) | ✔ V "Live-linked pro forma financials", "Automatic quantity takeoffs for parking and infrastructure" | ✔ V "area and feasibility metrics" | — NS | ✘ Not implemented (Phase 4 planned: quantities + preliminary KZT cost) |
| **C9 Interoperability** | ✔ V IFC, 3DM, SKP, OBJ, STEP; API, Dynamo | ✔ V Revit, Rhino, Dynamo; third-party extensions | ✔ V Revit integration; AutoCAD, SketchUp, Excel, PDF exports | — NS on home page | ✔ V "Export to Revit" | ◐ Open JSON Schemas generated from Pydantic; versioned JSON model via REST API. **No IFC/Revit export** (backlog) |
| **Pricing / access** | ✔ V from $251/month | ✔ V from $59/month; 30-day trial | — NS | ✔ V waitlist | ✔ V "No credit card required" sign-up | Research prototype; not deployed; no license chosen yet |

## 4. Interpretation

### 4.1 Verified observations
- Every competitor is a commercial, closed product aimed at **professional** users. Three of them (Forma, TestFit, Finch) target site feasibility, multifamily, commercial or enterprise workflows. TestFit lists single-family among its building types [P3].
- Revit is the BIM authoring reference with documentation and IFC [P1], and AI features there are in *tech preview* [P1].
- Conversational or AI interaction is now advertised by TestFit (via an add-on) and Hypar [P3, P5].

### 4.2 Unavailable information
- None of the pages describe **how** generated designs are validated, whether results are reproducible, or what the AI is allowed to produce. Those are the dimensions BuildAI is designed around. **Absence on a marketing page is not evidence of absence**, so these cells stay "NS".
- No independent benchmarks of these products' generation quality were found during the sprint.

### 4.3 Inferred limitations (team inference, to be checked by trials or interviews)
- (I) Professional pricing and complexity are likely a barrier for students and homeowners. Interview Q2 and Q7 in [02](02_relevance_and_user_evidence.md) test this.
- (I) Single-family residential concept design from a lay description doesn't appear to be the primary use case of the generative tools reviewed.

## 5. Positioning of BuildAI 3D

BuildAI 3D is **not** a substitute for Revit or a commercial feasibility platform. It is an open research prototype that explores one architectural question:

> *Can a natural-language residential brief be turned into an element-level, geometrically validated, reproducible building model by limiting the AI to structured intent and leaving all geometry to deterministic code?*

Why it is useful despite the alternatives:
1. **Transparency and reproducibility.** Same spec + seed + engine version ⇒ identical model. Every assumption, deviation and constraint finding is shown. The commercial tools don't document this publicly.
2. **Accessible entry point.** It targets students and prospective homeowners. Whether that segment is real is a hypothesis that the interviews must confirm.
3. **An academic contribution in architecture,** not features. It provides a measurable comparison of interpretation accuracy, validity and determinism between a deterministic baseline and a real LLM (see [09](09_verification_and_evaluation_plan.md)), plus a public schema and constraint catalog.
4. **A path to interoperability.** The typed model with stable semantic IDs is designed to map to IFC entities later [T1]. That is planned, not implemented.

Gaps compared to competitors, stated honestly: no 2D documentation, no quantities or cost, no IFC/Revit export, no site context, and a single plan scheme.
