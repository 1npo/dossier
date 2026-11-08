# Development process for dossier 1.0.0

How the work in [plans/004-v1-spec.md](plans/004-v1-spec.md) gets planned, built and reviewed. The spec is the authority on what to build. This file only covers how.

## Roles

| Who | Does |
|---|---|
| **Sonnet** | Writes the planning prompt for each milestone. Implements each milestone from its plan. |
| **Opus** | Writes the plan for each milestone from the spec and the code. For a public test repository, also writes the ground truth before any build, rules on every disagreement with the dossier, and checks the component map (spec decision 34). Nothing else. |
| **You** | Pastes the prompt into Opus. Reviews each plan before building and each milestone after. Runs the acceptance tests. Spot-checks ground truth for public repositories. |

## The loop, per milestone

1. **Prime.** Sonnet writes `docs/prompts/plan-mN.md`, a self-contained prompt for a fresh Opus session.
2. **Plan.** You paste it into Opus. Opus writes `docs/plans/00X-mN-plan.md`, where X counts up from 5 (M0 is 005, M1 is 006, and so on). Opus changes no other file.
3. **Review the plan.** You read it, answer its open questions and approve it. For M0 the first thing to review is the spec-versus-code reconciliation list.
4. **Implement.** Sonnet works through the plan in the number of sessions below. It ticks each task's checkbox in the plan file, commits once per task, and stops and reports if the code contradicts the plan.
5. **Review the milestone.** You review the diff, run the tests and `check_page.py`, and confirm the milestone's exit criterion from the spec (section 10).
6. **Next.** Only now does Sonnet write the next prompt, so it reflects what the last milestone changed.

## Sessions

| Milestone | Implementation sessions |
|---|---|
| M0 | 1 |
| M1 | 1 |
| M2 | 3 |
| M3 | 3, then **pause** |
| M4 | 5 Sonnet, 2 Opus, and 1 more Sonnet if Opus finds faults (plan 010, D16) |
| M5 | 7 Sonnet, 2 Opus, and 1 more Sonnet if Opus finds faults (plan 011, D20) |
| M6 | 1 |

Cut a milestone's sessions at a committed, tested boundary, for example: framework and Python adapter; reports built on the extractors; checks V2 to V5. A new session starts from the spec, the milestone plan and the git log, never from an earlier session's memory.

## Pause at M3: acceptance testing

After M3 is implemented, stop. The Python pipeline is complete end to end at that point. You build a dossier of a Python repository you know well and judge it against the targets in the spec's definition of done (section 11, item 3):

- entry points: recall 100%, precision at least 95%;
- inputs and outputs: recall at least 95%;
- components: you agree with the map after minor renaming;
- no fabricated citations;
- everything you find wrong or missing is explained by a Gaps entry or a new blind-spot rule.

The findings update the spec and the M4 to M6 plans. Work on TS/JS and C# starts only after that. A second acceptance test runs before M4 is implemented.

## Rules

- **One plan file per milestone is the source of truth.** Status lives in its checkboxes.
- **The spec changes only in the spec.** If a plan or an implementer finds the spec wrong, they record it under "Spec issues" and you decide. Nobody works around it silently.
- **One writer per file.** Do not run two sessions that edit the same file.
- **Report 02 stays untouched** (Contributors, knowledge map, calendar and Dependencies cards included), unless a plan says otherwise and you approved it.
- **Every task has a done-check** that can be run: a test, a command or an expected output.
