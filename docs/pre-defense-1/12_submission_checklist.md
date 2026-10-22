# 12 — Submission Checklist (Pre-Defense 1, deadline 2026-10-24)



## 1. Assessment components (eleven)

| # | Component | Deliverable | Status | Evidence / what is missing |
|---|---|---|---|---|
| 1 | Project proposal (title, team, problem, aim, objectives, scope, status) | [01_project_proposal.md](01_project_proposal.md) | ◐ Draft ready for review | Complete draft; |
| 2 | Relevance and user evidence (3–5 discussions or client agreement) | [02_relevance_and_user_evidence.md](02_relevance_and_user_evidence.md) |  in process | Protocol, questions, log and analysis templates ready; **0 interviews held**; no client agreement |
| 3 | Literature review (≥ 12 sources, ≥ 8 scientific) | [03_literature_review.md](03_literature_review.md), [references.md](references.md) | ◐ Draft ready for review | 19 Crossref-verified peer-reviewed publications (9 from 2021–2026) + 1 book + ISO standard; synthesis written; some summaries abstract-level (LIT-03) |
| 4 | Existing system comparison (3–5 systems, 6–10 criteria) | [04_existing_system_comparison.md](04_existing_system_comparison.md) | ◐ Draft ready for review | 5 systems × 9 criteria from official pages (2026-10-20); vendor claims only, no hands-on trials |
| 5 | Technology comparison (≥ 3 decisions, alternatives, justification) | [05_technology_comparison.md](05_technology_comparison.md) | ◐ Draft ready for review | 4 decisions × 3 options each + rationale for separating the deterministic engine from the LLM; no benchmarks |
| 6 | Requirements specification (FR/NFR, IDs, priority, acceptance, verification, status) | [06_requirements_specification.md](06_requirements_specification.md) | ◐ Draft ready for review | 25 FR + 18 NFR with test references; priorities to revisit after interviews |
| 7 | Architecture and diagrams (context, use case, component) | [07_architecture_and_diagrams.md](07_architecture_and_diagrams.md), `diagrams/*.mmd/.svg/.png` | ◐ Draft ready for review | 3 diagrams with editable Mermaid source + SVG + PNG; use-case notation may need UML redraw (DIA-01) |
| 8 | UX / prototype | [08_ux_prototype.md](08_ux_prototype.md), `assets/screenshots/01–12` | ◐ Draft ready for review | 12 genuine screenshots (main, mock provider); live-LLM and K3 screenshots outstanding (C4, C6); no public deployment |
| 9 | Verification and evaluation plan | [09_verification_and_evaluation_plan.md](09_verification_and_evaluation_plan.md) | ◐ Draft ready for review | Existing evidence (tests re-run 2026-10-20) separated from planned experiments; **no eval results yet** (harness not written) |
| 10 | Project management and risks (schedule, RACI, risks, YouTrack) | [10_project_management_and_risks.md](10_project_management_and_risks.md), [youtrack-tasks.csv](youtrack-tasks.csv) | ◐ Draft ready for review | Schedule, RACI (proposed), 14 risks, dependencies, 4-day plan, import file.|
| 11 | Supervisor feedback | [11_supervisor_feedback.md](11_supervisor_feedback.md) | nice, need a bit improvment | Template only; |

## 2. Minimum repository requirements for 2026-10-24

| Requirement | Status | Evidence / action |
|---|---|---|
| One repository used throughout the diploma (same project) | ✔ Completed | Git history since 2026-09-27 (14 commits + docs commit); no branch reset or deleted; commit messages were rewritten once on 2026-10-22 to remove the AI co-author trailer, at the supervisor's request; file contents, authors and dates unchanged |
| Remote repository (GitHub/GitLab) exists | ✔ Completed | <https://github.com/Muvahhid-cloud/Diploma-Project>: `main`, `phase-3.5-k3-design-systems`, `docs/pre-defense-1` pushed 2026-10-22 |
| Access for both students, supervisor, committee | approved | Depends on the remote and account names |
| README with project title, team, description, setup, status | ◐ Draft ready | Root [README.md](../../README.md) updated in this sprint |
| Pre-defense documentation in the repository | ◐ Draft ready | `docs/pre-defense-1/` (committed on branch `docs/pre-defense-1`, pushed to GitHub) |
| Build / tests pass on the submitted commit | ✔ Completed for `main` @ `7685bf9` |  web 135 passed; API 582 passed, 2 skipped; lint and typecheck clean. Re-run on the final commit before tagging |
| CI runs on the remote | ☐ Not started | Remote exists; check the GitHub Actions run on `main` |
| No secrets or personal data committed | ✔ Completed (current history) | `.env` git-ignored and untracked; screenshots use a throwaway test account; no interview data in Git. Repeat the scan before pushing (SEC-02) |
| Contributions from each student's own account | In proccess  | All existing commits come from one identity; future commits must come from each student's own account. No further history rewriting (R-04) |
| YouTrack (or tracker) with tasks | In proccess | Import file ready; no instance or project yet |
| Pre-defense tag | In proccess| Create `pre-defense-1` only after review: `git tag -a pre-defense-1 -m "Pre-defense 1 submission"` then `git push origin pre-defense-1` |
| K3 branch status clearly stated | ✔ Completed | Documented everywhere as "committed, not merged" |

## 3. Final pre-submission checks (to run on 2026-10-24)

- [ ] ≥ 3 interviews logged and analyzed in 02; hypotheses updated
- [ ] Feedback log 11 has at least one real entry, or a clearly stated reason why not
- [ ] Remote created; all branches pushed; access granted; `main` protected
- [ ] YouTrack project created; tasks imported; link added to README
- [ ] `pnpm lint && pnpm typecheck && pnpm test` green on the commit to be tagged
- [ ] Each student committed their own share from their own account
- [ ] Links in all documents resolve (relative paths)
- [ ] Tag created and pushed after confirmation
