# 10 — Project Management and Risks


## 1. Repository state

| Item | Observed |
|---|---|
| Remote | **None** (`git remote -v` is empty). CI (`.github/workflows/ci.yml`) has therefore never run |
| `main` | `7830248`: Phases 0–3, K1, K2, K2.5, OpenRouter provider, schema-in-prompt fallback |
| Unmerged feature branch | `phase-3.5-k3-design-systems` @ `cc59d3f` (one commit ahead of `main`; 88 files, +11,745 / −288). Awaiting review; **not merged by this sprint** |
| Other local branches | `phase-2-layout-engine`, `phase-3-ai-generation`, `phase-3-anthropic-schema-fallback`, `phase-3-openrouter-provider`, `phase-3.5-k1-knowledge`, `phase-3.5-k2-types-assemblies`, `phase-3.5-k2.5-geometry`. All are ancestors of `main` (already merged) and kept untouched |
| This sprint's branch | `docs/pre-defense-1`, created from `main`. Changes are documentation only (`docs/pre-defense-1/`, `README.md`) and **uncommitted**, left for team review |
| Commit history | 14 commits, 2026-09-27 → 2026-09-29, **all authored by one Git identity** ("Zayniddin"). Commits carry a `Co-Authored-By: Claude …` trailer, i.e. AI-assisted development |
| Secrets | `.env` exists locally and is git-ignored (`.gitignore`: `.env`, `.env.*`, `!.env.example`); `.localdb/` ignored. `git ls-files` shows no `.env` |
| Tags | None. The pre-defense tag is **not** created until the package is reviewed (§8) |

## 2. Milestone schedule

| # | Milestone | Planned / actual date | Status |
|---|---|---|---|
| M0 | Foundations (Phase 0) | 2026-09-27 (actual) | Done |
| M1 | Procedural 3D from hand-authored model (Phase 1) | 2026-09-27 (actual) | Done |
| M2 | Deterministic layout engine (Phase 2) | 2026-09-28 (actual) | Done |
| M3 | AI generation (Phase 3) + OpenRouter | 2026-09-28/29 (actual) | Done (eval suite deferred) |
| M3.5a | K1, K2, K2.5 | 2026-09-28/29 (actual) | Done (on main) |
| M3.5b | K3 design systems: review + merge decision | [TO CONFIRM] | Committed, awaiting review |
| **PD1** | **Pre-Defense 1 package submitted** | **2026-10-24** | Draft ready (this package); blocked items in [12](12_submission_checklist.md) |
| M4 | Evaluation harness + first eval run (L6) | [TO CONFIRM], after PD1 | Not started |
| M5 | Phase 4: quantities + preliminary cost | [TO CONFIRM] | Not started |
| M6 | Phase 5: NL modification + version compare | [TO CONFIRM] | Not started |
| M7 | User evaluation (L8) + thesis draft | [TO CONFIRM] | Not started |
| M8 | Final defense | [TO CONFIRM by university] | — |

## 3. Responsibility matrix (RACI, proposed)

R = Responsible, A = Accountable, C = Consulted, I = Informed. S1 = Турсуналиев З. Х., S2 = Усманов Э. А., SV = supervisor. The split below is a **proposal** to agree at the first team meeting. It doesn't describe past work.

| Work package | S1 | S2 | SV |
|---|---|---|---|
| Project proposal (01) | R/A | C | C |
| User interviews + evidence analysis (02) | C | R/A | I |
| Literature review (03) | R | R/A | C |
| Existing-system comparison (04) | C | R/A | I |
| Technology comparison (05) | R/A | C | I |
| Requirements (06) | R/A | R | C |
| Architecture + diagrams (07) | R/A | C | I |
| UX evidence / screenshots (08) | C | R/A | I |
| Verification and evaluation plan + harness (09) | R/A | R | C |
| Project management, YouTrack, remote setup (10) | C | R/A | I |
| Supervisor feedback log (11) | R | R | A |
| K3 code review and merge decision | R | R (reviewer) | C |
| Security review (auth, secrets) | C | R/A | I |

## 4. Risk register

| ID | Risk | Probability | Impact | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|
| R-01 | User interviews aren't completed by 2026-10-24 | High | High (assessment component) | Recruit immediately (§7 day 1); accept 3 interviews as the minimum; use video calls | S2 [TO CONFIRM] | Open |
| R-02 | Supervisor not confirmed, so no feedback before submission | Medium | High | Contact the department on day 1; log every contact in [11](11_supervisor_feedback.md) | S1 [TO CONFIRM] | Open |
| R-03 | No Git remote: committee can't access the code; CI never run | High (current state) | High | Follow §6 on day 1 once the URL and access are decided | S2 [TO CONFIRM] | Open |
| R-04 | Contribution evidence: all commits so far come from one Git identity, so the second student's contribution isn't visible | High | High (individual assessment) | From now on each student commits from their **own** account; record pairing or reviews in PR descriptions and YouTrack; **never** rewrite or backdate history | Both | Open |
| R-05 | AI-assisted development (Claude co-authored commits) not disclosed according to university policy | Medium | High (academic integrity) | Check the university AI-use policy; disclose tool use in the thesis and to the supervisor; both students must be able to explain every module | Both | Open |
| R-06 | Unverified or misdescribed literature claims | Low (all metadata verified) | Medium | Both students read full texts (LIT-03); correct the abstract-level summaries | S2 | Open |
| R-07 | Hand-written auth has a security flaw | Low–Medium | High if deployed | Tests already cover rotation and reuse; do a security review before any deployment (SEC-01) | S2 | Open |
| R-08 | Secret leak when the remote is created (`.env` holds a real OpenRouter key) | Low | High | `.env` is git-ignored (verified); run `git ls-files | grep -i env` and a secret scan before the first push; rotate the key if it is ever exposed | S1 | Open |
| R-09 | LLM cost overrun during evaluation | Medium | Medium | Budget cap before live runs; mock baseline in CI; ≤ 120 calls planned | S1 | Open |
| R-10 | Provider/model changes or is unavailable (pricing, schema limits, deprecation) | Medium | Medium | Vendor-neutral interface; schema-in-prompt fallback; model name from config only | S1 | Mitigated (design) |
| R-11 | K3 merge introduces regressions | Low–Medium | Medium | Review; re-run `pnpm check`; geometry fingerprints must stay equal (branch claims 10/10 equal) | Both | Open |
| R-12 | Scope creep (K4, Phase 4+) before evaluation is done | Medium | High | Phase order in CLAUDE.md; this sprint starts no new features | Both | Mitigated (process) |
| R-13 | Docker Compose path not verified | Medium | Low–Medium | Verify on a machine with Docker, or document Option B as the supported path | S2 | Open |
| R-14 | Interview data privacy breach (names in repo) | Low | High | Anonymized IDs only; raw notes kept outside Git ([02](02_relevance_and_user_evidence.md) §2.1) | S2 | Open |

## 5. Dependency tracking

| Deliverable | Depends on | Blocking? |
|---|---|---|
| 02 findings, 06 priorities | Real interviews (R-01) | Yes, external |
| 11 feedback log | Supervisor identity + meeting (R-02) | Yes, external |
| Repository access for committee | Remote URL + hosting decision + accounts (R-03) | Yes, external |
| YouTrack board | YouTrack instance URL / university workspace | Yes, external |
| 09 Part B results | Eval harness (not written), budget approval | Not for PD1 (plan only) |
| 08 K3 screenshots | K3 review/merge decision or a branch run | No (optional) |
| Pre-defense tag | All of the above reviewed | Yes |

## 6. Creating and connecting the remote (steps, no URL invented)

Run these only after the team chooses the host (GitHub or GitLab, personal or university organization) and **the user provides the URL**.

1. On the hosting service, create an **empty private** repository named e.g. `buildai-3d` (no README, no .gitignore, so histories don't conflict).
2. Locally, check that nothing secret is tracked:
   ```bash
   git ls-files | grep -i -E "\.env$|secret|\.pem|\.key"
   ```
   (Expected: only `.env.example`.) Optionally run a secret scanner such as `gitleaks detect`.
3. Add the remote and push **all** branches. History stays as it is: no rebasing, squashing or author rewriting.
   ```bash
   git remote add origin <REMOTE_URL — TO BE PROVIDED>
   git push -u origin main
   git push origin --all
   ```
4. Grant access:
   - Турсуналиев З. Х. and Усманов Э. А.: *Maintainer / Write*, each with their **own** account.
   - Supervisor [SUPERVISOR NAME — TO CONFIRM]: *Read* (or *Reporter* on GitLab), or higher if they review PRs.
   - Committee members: *Read* (account names [TO CONFIRM]).
5. Protect `main`: require a pull request and one review; disallow force-push and deletion.
6. Check that the CI workflow runs on the first PR (GitHub Actions; on GitLab an equivalent `.gitlab-ci.yml` would be needed, a separate task).
7. From then on, merge feature branches (e.g. K3) through reviewed pull requests from the author's own account.

## 7. Next-step plan (four days to 2026-10-24)

| Day | Date | Tasks |
|---|---|---|
| 1 | Wed 2026-10-21 | Review this package together; confirm the supervisor and send them the package; recruit 5 interviewees; decide the Git host and create the remote (§6); create the YouTrack project and import `youtrack-tasks.csv`; agree the RACI |
| 2 | Thu 2026-10-22 | Hold 2–3 interviews; read full texts of S16–S19 and fix summaries; supervisor meeting if possible; push branches |
| 3 | Fri 2026-10-23 | Remaining interviews; fill [02](02_relevance_and_user_evidence.md) §6–§7; adjust priorities in [06](06_requirements_specification.md); log feedback in [11](11_supervisor_feedback.md); optional: capture K3 / live-LLM screenshots (C4, C6) |
| 4 | Sat 2026-10-24 | Final consistency pass; update [12](12_submission_checklist.md) statuses; commit from your own accounts; after the supervisor confirms, create the tag `pre-defense-1` and submit |

## 8. YouTrack task list (import template)

File: [`youtrack-tasks.csv`](youtrack-tasks.csv) (columns: Summary, Description, Type, Priority, Assignee, Due Date, Tags, Subsystem). Import it through YouTrack's CSV/spreadsheet import once a project exists. **None of these tasks exist in YouTrack yet.**

| ID (proposed) | Summary | Area | Assignee | Due |
|---|---|---|---|---|
| DOC-01 | Team review of the pre-defense package | documentation | Both | 2026-10-21 |
| DOC-02 | Fix the stale K2 status in `docs/roadmap.md` and mark planned stages in `docs/architecture.md` §2 (after deciding on K3 merge, to avoid conflicts) | documentation | [TO ASSIGN] | [TO CONFIRM] |
| LIT-01 | Extend the literature search with a documented Scopus/WoS query | literature | S2 | [TO CONFIRM] |
| LIT-03 | Read full texts and correct abstract-level summaries (S12, S15–S19) | literature | Both | 2026-10-22 |
| INT-01 | Recruit 5 interview participants (≥ 3 categories) | interviews | S2 | 2026-10-21 |
| INT-02 | Confirm the consent-form requirement with the supervisor | interviews | S2 | 2026-10-21 |
| INT-03 | Conduct and log interviews P01–P05 | interviews | Both | 2026-10-23 |
| INT-04 | Analyze findings; update requirement priorities | interviews / requirements | S2 | 2026-10-23 |
| REQ-01 | Re-validate requirement statuses after the K3 decision | requirements | S1 | [TO CONFIRM] |
| DIA-01 | Redraw the use-case diagram in strict UML if the template requires it | diagrams | S1 | [TO CONFIRM] |
| PRO-01 | Capture a live-LLM generation screenshot and record its cost (C4) | prototype evidence | S1 | 2026-10-23 |
| PRO-02 | Capture K3 screenshots from the branch, labelled (C6) | prototype evidence | S2 | [TO CONFIRM] |
| TST-01 | Write the eval harness (`pnpm eval`) and freeze `eval-prompts@1` | testing | S1 | [TO CONFIRM] |
| TST-02 | Run the mock baseline + live evaluation (budget-capped) | testing | Both | [TO CONFIRM] |
| TST-03 | Verify Docker Compose on a machine with Docker | testing | S2 | [TO CONFIRM] |
| SEC-01 | Security review of auth, cookies, secrets, rate limits | security | S2 | [TO CONFIRM] |
| SEC-02 | Secret scan before the first push | security | S1 | 2026-10-21 |
| REP-01 | Create the remote, push all branches, grant access, protect `main` | repository | S2 | 2026-10-21 |
| SUP-01 | Confirm the supervisor and send the package | supervisor | S1 | 2026-10-21 |
| SUP-02 | Supervisor review meeting; log feedback | supervisor | Both | 2026-10-23 |
| K3-01 | Review the K3 branch; decide on merge (`pnpm check` must pass) | development | Both | [TO CONFIRM] |
