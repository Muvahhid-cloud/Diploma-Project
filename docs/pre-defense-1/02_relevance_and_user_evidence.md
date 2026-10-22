# 02 — Relevance and User Evidence


## 1. Why the project is relevant (literature-based, not user-based)

These points come from published sources and justify the project **before** user evidence exists. They are not a substitute for that evidence.

| Claim | Source |
|---|---|
| Generative AI in architecture is concentrated in the schematic design phase, with images as the dominant input and output modality. Evaluation is mostly comparative or subjective. | Systematic review covering 2014–2024 [S16] |
| LLM adoption across AECO faces data-quality, integration and adaptability barriers. Compatibility with existing industry tools is a named research need. | Review [S17] |
| LLMs understand language but lack the spatial reasoning layout generation needs. Recent systems add rule-based checks or separate geometry executors. | [S18], [S19] |
| Text-conditioned floor-plan generation is an open research task. Designs must meet spatial and relational constraints that artistic image generation doesn't. | [S11] |
| Most learned layout generators output 2D room geometry, not a typed building model. | [S6–S10], review [S12] |

## 2. Evidence requirement and how it will be met

The assessment asks for **three to five discussions** with potential users or user representatives, **or** a substantive agreement with a real client. Plan:

- Target: **5 semi-structured interviews** (minimum 3) in the period 2026-10-21 → 2026-10-23, covering at least three of the participant categories in §3.
- Format: 20–30 minutes, in person or by video call, in Russian, Uzbek, Kazakh or English as the participant prefers.
- Each interview gets one row in the evidence log (§6), plus a short summary sheet stored **outside the public repository** if it holds personal data.

### 2.1 Ethics, consent and data handling

1. Before the interview, explain the purpose (diploma project, BuildAI 3D) and that taking part is voluntary.
2. Get verbal or written consent for (a) taking notes and (b) optional audio recording. Record only with explicit consent.
3. **Anonymize** in the repository: use participant codes `P01…P05`, a category and an experience band only. No names, phone numbers, employers or e-mail addresses go in Git. Keep raw notes and recordings in a private folder that the team and supervisor can access, not in this repository.
4. Quotations go in the repository only if the participant agreed to anonymous quoting. Mark them in the log.
5. If the supervisor or university needs a specific consent form, use it instead of the verbal script.

**Consent script (short):** "We are students of SE-2406 developing BuildAI 3D, a diploma prototype that turns a text description of a house into a 3D concept model. We'd like to ask about how you work today. It takes about 20–30 minutes, and you can skip any question or stop at any time. May we take notes? May we record audio, used only by our team and supervisor? We won't publish your name."

## 3. Participant categories (candidate pool, not actual interviewees)

| Code | Category | Why relevant | Recruitment idea |
|---|---|---|---|
| A | Practising architects | Judge whether generated concepts are plausible; know the client-briefing workflow | Supervisor or faculty contacts; local firms |
| B | Architecture / civil-engineering students | Possible learning-tool users; know current BIM tools | University departments, student groups |
| C | BIM / 3D modeling practitioners | Interoperability needs (IFC, Revit), model structure expectations | Professional groups, LinkedIn |
| D | Small architectural or design-build firms | Speed of producing concept options for clients | Direct contact |
| E | Property developers (small residential) | Feasibility and option comparison | Personal and university network |
| F | Prospective residential clients (homeowners) | Ability to express a brief; trust in AI output | Family and friends network, outside the team. Note the bias risk in §7 |

Target mix for 5 interviews: at least 1 from A or D, 1 from B, 1 from C, and 1 from E or F.

## 4. Interview protocol

1. Introduction and consent (§2.1) — 2 min.
2. Background: role, years of experience, typical projects — 3 min.
3. Core questions (§5) — 15–20 min. Ask open questions first. Do **not** demo BuildAI before Q6 so the answers aren't anchored.
4. Optional: 3-minute demo of the prototype (main branch, mock or live provider; say which one is used), then Q7–Q8.
5. Closing: anything else? May we contact you for a usability session later? — 2 min.

Interviewer rules: don't pitch, don't lead, ask "can you give an example from a recent project?", write down numbers (hours, iterations, tools) when the participant gives them, and don't fill silences with suggestions.

## 5. Interview questions (neutral)

| # | Question | What it investigates |
|---|---|---|
| Q1 | Walk me through the last time you went from a client's (or your own) first idea of a house to a first concept design. What steps did you take? | Real workflow |
| Q2 | Which tools did you use at each step (e.g. sketches, SketchUp, Revit, ArchiCAD, Excel, others)? | Current tools |
| Q3 | Roughly how much time did it take to get to a first concept that could be discussed? Which part took the longest? | Time spent, bottlenecks |
| Q4 | What goes wrong or causes rework in that early stage? Can you give an example? | Problems |
| Q5 | When a brief is described in words (e.g. "two storeys, four bedrooms, garage"), what information is usually missing or ambiguous? | Requirements, clarification needs |
| Q6 | What would an early concept model need to contain or show for you to find it useful (e.g. rooms, areas, 3D, facades, plans, costs, export format)? | Requirements, priorities |
| Q7 | *(after optional demo)* Would you use a tool like this in your work or study? In which situation, and what would stop you from using it? | Willingness to use, barriers |
| Q8 | How much would you need to trust or verify an AI-generated concept before showing it to someone else? What would make you trust it more or less? | Trust, explainability |

Optional follow-ups: "Which file formats do you need to exchange?" · "Who else is involved at that stage?" · "Have you tried any AI design tools? What happened?"

## 6. Participant / evidence log (template — fill only with real data)

Keep this table in the repository with **anonymized** entries only.

| ID | Date | Category (§3) | Experience band | Mode (in person/video) | Duration | Consent: notes / audio / anonymous quotes | Interviewer | Raw notes location (private) | Summary written? |
|---|---|---|---|---|---|---|---|---|---|
| P01 | [TO COLLECT] | | | | | | | | |
| P02 | [TO COLLECT] | | | | | | | | |
| P03 | [TO COLLECT] | | | | | | | | |
| P04 | [TO COLLECT] | | | | | | | | |
| P05 | [TO COLLECT] | | | | | | | | |

**Client agreement alternative:** if a real client (e.g. a design firm) agrees to a substantive collaboration, record the organization (with its permission), the contact role, the scope, the date and where the signed or e-mailed agreement is stored. *No such agreement exists as of 2026-10-20.*

## 7. Findings analysis (template)

### 7.1 Per-question coding table

Code each answer into short themes and count how many participants raised each one. Don't write a theme until it is grounded in a real answer.

| Theme | Question(s) | Participants mentioning (IDs) | Count / N | Example evidence (anonymous paraphrase or consented quote) | Implication for BuildAI (requirement ID) |
|---|---|---|---|---|---|
| [TO COLLECT] | | | | | |

### 7.2 Hypotheses vs evidence

These are the team's **assumptions**. Each will be marked *supported / contradicted / no evidence* after the interviews.

| H# | Assumption (not yet verified) | Related requirement | Evidence status |
|---|---|---|---|
| H1 | Turning a verbal brief into a first discussable concept takes hours to days for small residential projects. | FR-01, NFR-P2 | No evidence yet |
| H2 | Users value an element-level 3D model (rooms, walls, openings) more than a rendered image. | FR-08, FR-09 | No evidence yet |
| H3 | Briefs commonly leave out floor count, area or room counts, so clarification questions are useful. | FR-03 | No evidence yet |
| H4 | Facade appearance and window orientation matter at concept stage. | FR-14, FR-15 (K3) | No evidence yet |
| H5 | Professionals would need export (e.g. IFC) before using the output in their own tools. | Planned (backlog) | No evidence yet |
| H6 | Users need to see assumptions and deviations to trust AI output. | FR-11 | No evidence yet |
| H7 | Students would use the tool for learning space programming. | — | No evidence yet |

### 7.3 Verified findings vs assumptions (fill after interviews)

| # | Verified finding (≥ 2 participants, or 1 strong client statement) | Supporting IDs | Change to requirements / backlog |
|---|---|---|---|
| — | *None yet* | | |

## 8. Outstanding evidence (blocking for the user-evidence component)

| Item | Status | Owner | Target |
|---|---|---|---|
| Recruit 5 participants across ≥ 3 categories | Not started | [TO ASSIGN] | 2026-10-21 |
| Confirm with supervisor whether a university consent form is required | Not started | [TO ASSIGN] | 2026-10-21 |
| Conduct ≥ 3 interviews (target 5) | Not started | Both students | 2026-10-21 – 10-23 |
| Fill §6 log and §7 analysis; update requirements priorities in [06](06_requirements_specification.md) | Not started | [TO ASSIGN] | 2026-10-23 |
| (Optional) obtain written client agreement | Not started | [TO ASSIGN] | — |
