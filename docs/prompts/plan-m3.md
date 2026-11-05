# Prompt: plan milestone M3 (paste into a fresh Opus session)

You are planning, not building. Write an implementation plan for **milestone M3** of the `dossier` 1.0.0 specification. A different, less capable model (Sonnet) will carry out your plan one task at a time, in **one session unless you propose a cut**, so the plan must be explicit enough to follow without design judgment. Do not modify any file except the plan you write. Do not run `/dossier build` against any repository, and do not install tools or run restores. Reading files and web searches are fine.

## Where things are

- The skill: `/home/nick/dev/projects/encamp/configs/user/claude/.claude/skills/dossier` (call it `SKILL`). This is the development copy and the repository that holds the commits. `~/.claude/skills/dossier` points at a separate installed clone (`~/.local/share/encamp/...`); never read it as the source of truth and never edit it.
- The specification, which is the authority on what to build: `SKILL/docs/plans/004-v1-spec.md`.
- How the work is organised: `SKILL/docs/process.md`.
- The finished plans, including their "Results", "Verification results", "Risks", "Spec issues" and "Deviations": `005-m0-plan.md`, `006-m1-plan.md`, `007-m2-plan.md`, and `008-m3-remediation-plan.md` (all in `SKILL/docs/plans/`). Use 007 as the model for format and level of detail.
- Backlog of things deliberately left out: `SKILL/docs/post-v1.md`.
- Today's behaviour: `SKILL/SKILL.md`, `SKILL/prompts/method.md`, `SKILL/prompts/reports.md`, `SKILL/prompts/schema/*.json`, the code under `SKILL/scripts/`, `SKILL/rules/`, and `SKILL/tests/`. Trust the code over the README.
- Run `git log --oneline` first. M2 and the remediation plan 008 are merged (version 0.7.1).

## What happened since M2 (read before anything else)

The process file says the user's acceptance pause comes after M3. In practice the user ran acceptance testing on the **M2** output of the `cannalerts` repository, and rejected it. The remediation plan 008 was written and carried out to fix that. Its findings are the history you must not repeat:

- A broken installed copy put merge-conflict markers into the page's CSS.
- The checks passed a page the author found unusable, because they tested almost nothing the author looks at. Plan 008 redesigned verification (a static page audit, browser layout and readability checks, a visual golden for report 02, a `dossier check` command). **Every new card or report M3 adds must pass those checks, and the plan must say how.**
- Nothing was dropped silently: plan 008 added per-item dispositions and completeness checks. M3's extractors and cards must follow the same rules.

Read plan 008 sections 1, 3, 4 (spec amendments A1 to A9 and which the author approved), 9 and its "Results", then `git log` since `2ed850b`. Where an amendment or deviation changed the spec's meaning, the plan says so under "Spec versus code". M3 was **not** part of plan 008 (its section 9 lists what was left for M3).

## M3 as the spec defines it

Content (spec section 10): report 10 (git-derived cards, blast radius); report 13 (all six cards: people, ask, concentration, agents, doubts, workflow); the report 14 and 15 additions; `summary.json` (spec section 9) and V8. Reports 10 and 13 become required again (they are optional since M2; spec decision 17 and issue 12).

Exit criterion: a golden-set run on the Python repository meets spec section 11.

Not in M3: TS/JS (M4), C# (M5), Tier B badges, interactive graphs, `--verify`, the README rewrite and the 1.0.0 version (M6). Report 02 and existing card schemas must not change unless the spec requires it and you flag it under "Spec issues".

M3 is followed by the user's **acceptance pause**: they build a dossier of a Python repository they know well and judge it against spec section 11, item 3. Plan so that this pause can start the moment M3 merges (what they run, what they need installed, and what the build prints), and do not plan any work beyond it.

## Read first, in this order

1. Spec sections 2, 3, 4 (every row that mentions reports 10, 13, 14 or 15, and the card tables), 5, 6 (what the adapters and git extractors provide), 7 (V8 and how V1 to V10 fit together), 8 (card schema), 9 (`summary.json`), 10, 11 and 12.
2. `docs/process.md`.
3. Plans 007 and 008: the parts on how reports are fed from extractor JSON, dispositions, staleness, "partial" badges, the verification checks, and anything that says "M3".
4. `render.py`, `stages.py`, `buildlog.py`, `gather.py`, `check_page.py`, the card schemas for reports 10 and 13 (they exist as placeholders: look at what the "Not yet generated" cards are), and `tests/`.
5. `prompts/method.md` and `prompts/reports.md`: M3 changes how Claude is told to write reports 10, 13, 14 and 15.

## First deliverable: a reconciliation

Before the task list, a section called **Spec versus code** listing every place where the spec and the code disagree, or where the spec assumes something the code does not do (including everything plan 008 changed). For each, say what you propose and mark it "plan can absorb it" or "needs a decision from the human". Areas to check, and look for others:

- What git data exists today (the Contributors card, commit calendar, change data in `reports/change.json` and `contributors.json`) versus what reports 10 and 13 need: churn, ownership, co-change, bus factor, blast radius, and the people, ask, concentration, agents, doubts and workflow cards. Which are computed by a script from git and which are written by Claude from that script's output. The spec's rule is that measured values are never written by Claude.
- How blast radius uses the import graph and symbols from the M2 extractors, and what happens for code the graph does not cover.
- What `summary.json` needs (spec section 9, including `contracts`) versus what the reports already hold, and what `portfolio` expects.
- What V8 checks, how it is wired into `dossier check` and the build, and what a failure looks like.
- Privacy and identity: how authors are named, merged (aliases, bots) and shown, and what the "agents" card means for AI-authored commits. Do not guess; if the spec is silent, list it as an open question.
- How reports 10 and 13 become required again: which check, which error, and what happens to dossiers built at 0.7.x.
- The report 14 and 15 additions: exactly which cards or fields, from the spec.
- Anything the spec marks as P1 versus P0 (the cut line).

## Decisions to make and justify

Number them D1, D2, and so on. At least: the extractor design for git-derived data (one script or several, caching, shallow-clone behaviour, large-history limits, timing budget); the card data shapes; the order of report writing; how blast radius is computed and capped; how V8 works; the `summary.json` generation point in the build; how staleness and incremental rebuilds treat the new reports; the version `VERSION` bumps to and what that does to existing dossiers; and, if you propose more than one session, where it is cut, at committed, tested boundaries.

## Format of the plan

Write it to `SKILL/docs/plans/009-m3-plan.md`, following the project's planning-docs rules (the `claude-planning-docs` skill). The human starts each session with one line, such as "Start phase 1 as outlined in docs/plans/009-m3-plan.md", and that line must be enough. Do not write a copy-and-paste prompt for Sonnet. The plan has:

1. **Summary**: what M3 delivers, in five lines or fewer, and any phase cuts.
2. **Shared rules**: skills to load (`git-commit`, `git-workflow`, `py-projects`, `py-unit-tests`, `claude-planning-docs`, and the docs and release skills where relevant), branch name, commit style, what must never be touched (the installed clone, `/home/nick/dev/dossiers/`, the frozen fixture, the pinned repository), scratch-directory and environment-variable discipline (`DOSSIER_HOME`, `DOSSIER_CONFIG`, `DOSSIER_CACHE` set to a fresh folder), tests first with the failing line recorded, do not weaken a check to make it pass, stop and report if the code contradicts the plan, and tick the checkbox in the same commit as the task. Say that report 02 and existing card schemas are not to change except where the plan says so.
3. **Spec versus code**: the reconciliation above.
4. **Decisions**.
5. **Phases**, each a heading `## Phase <n>: <title>`, used identically everywhere. Each is self-contained and holds: what to read first and which skills to load; a first step that checks what earlier phases recorded; an ordered list of tasks; deliverables and how each is checked; the cut line; acceptance criteria; and the branch and release steps. Every task has: an id (M3-1, M3-2, ... numbered across phases), a goal, the exact files to touch, the interface or data shape, step-by-step instructions, a done-check that can be run (a command and its expected result), a suggested commit message, and a checkbox. Each task can be finished and committed on its own and the suite passes after every one. No task needs design judgment. The cut line must never drop extractor fixture tests, V8, or the checks from plan 008 applied to the new cards. Each phase says to write its results back into the plan under "Results".
6. **Verification**: the exit criterion checked end to end on a real Python repository on this machine (use `cannalerts` at its pinned commit, copying any existing dossier to scratch first): `doctor`, a full build, reports 10 and 13 written and rendered, V8, `summary.json` validity, the plan 008 browser and static audits reporting no problems on every new card at desktop and phone width in light and dark themes, an incremental rebuild, a build with git history unavailable (shallow clone) degrading with a Gaps entry, and the full test run. Say how Sonnet records results.
7. **Risks and open questions**: things the human must answer before Sonnet starts.
8. **Spec issues**: anything in the spec that looks wrong or incomplete. Do not work around these in the plan.

## Rules

- The spec wins over your preferences. If you think it is wrong, say so under "Spec issues" and plan to the spec anyway unless the problem blocks the work. Spec amendments the author approved in plan 008 are part of the spec now.
- Any external tool, flag, version or output format must be re-checked against current documentation (web search), not memory. Record the source URL for each. If you cannot verify one, list it as an open question.
- Every child process goes through the safe runner. Do not add sandboxing (spec decision 5).
- Never plan anything that reads or writes `/home/nick/dev/dossiers/` or builds a dossier of a real repository, except in Verification, and there only into a scratch directory.
- Plain language for anything a user of the dossier will read.
- Do not invent facts about the code. If you did not read it, say so.
- When you finish, reply with: the path of the plan, the five most important risks, the questions the human must answer, and the exact one-line instruction to type to start Phase 1.
