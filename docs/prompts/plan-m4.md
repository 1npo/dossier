# Prompt: plan milestone M4 (paste into a fresh Opus session)

You are planning, not building. Write an implementation plan for **milestone M4** of the `dossier` 1.0.0 specification. A different, less capable model (Sonnet) will carry out your plan one task at a time, in **one session unless you propose a cut**, so the plan must be explicit enough to follow without design judgment. Do not modify any file except the plan you write. Do not run `/dossier build` against any repository, and do not install tools or run restores. Reading files and web searches are fine.

## Where things are

- The skill: `/home/nick/dev/projects/encamp/configs/user/claude/.claude/skills/dossier` (call it `SKILL`). This is the development copy and the repository that holds the commits. `~/.claude/skills/dossier` points at a separate installed clone (`~/.local/share/encamp/...`); never read it as the source of truth and never edit it.
- The specification, which is the authority on what to build: `SKILL/docs/plans/004-v1-spec.md`.
- How the work is organised: `SKILL/docs/process.md`.
- The finished plans, including their "Results", "Verification results", "Risks", "Spec issues" and "Deviations": `005-m0-plan.md`, `006-m1-plan.md`, `007-m2-plan.md`, `008-m3-remediation-plan.md` and `009-m3-plan.md` (all in `SKILL/docs/plans/`). **Use 007 as the model for how a language adapter milestone is planned** (it is the Python vertical slice that M4 repeats for TS/JS), and 009 for format, phases and level of detail.
- Backlog of things deliberately left out: `SKILL/docs/post-v1.md`.
- Today's behaviour: `SKILL/SKILL.md`, `SKILL/prompts/method.md`, `SKILL/prompts/reports.md`, `SKILL/prompts/schema/*.json`, the code under `SKILL/scripts/`, `SKILL/rules/`, and `SKILL/tests/`. Trust the code over the README.
- Run `git log --oneline` first. M3 is merged (version 0.8.0).

## What has happened since the plans were written (read before anything else)

1. **Plan 008 changed the rules.** The user rejected the M2 output at acceptance testing; plan 008 redesigned verification (a static page audit, browser layout and readability checks, a visual golden for report 02, `dossier check`) and added per-item dispositions and completeness checks. **Every new extractor, rule, card and report M4 adds or changes must pass those checks, and the plan must say how.** Read plan 008 sections 1, 3, 4 (spec amendments A1 to A9) and its "Results".
2. **Plan 009 (M3) is done**: reports 10 and 13, `summary.json`, V8, the report 14 and 15 additions. Read its "Results", "Verification results", "Deviations", "Spec issues" and "Findings for the acceptance pause".
3. **The acceptance pause.** `process.md` says work on TS/JS starts only after the user has built a dossier of a Python repository they know well, judged it against spec section 11 item 3, and updated the spec and the M4 to M6 plans from the findings. I do not know whether that has happened. **Find out from the repository** (`git log` since the merge of `feat/dossier-m3`, the spec's "Settled in..." lists in section 12, `post-v1.md`, the "Findings for the acceptance pause" in plan 009). Report what you found at the top of the plan under "Acceptance pause status". If there is no record that the pause happened, say so in "Risks and open questions" as a question the human must answer before Sonnet starts, and plan to the spec as it stands today. Anything from the pause that changes the Python adapter or the shared layer is not part of M4 unless the spec says so; list it under "Carried over from the pause" for the human.

## M4 as the spec defines it

Content (spec section 10): the **TS/JS/React adapter**, its **rules**, and its **blind-spot list (V7 for TS/JS)**. Spec sections 6.1 to 6.4 define the extractor outputs, tools and blind spots; section 4 defines which cards each report has and at which tier.

Exit criterion: the same checks that M2 and M3 met for Python, on the golden TS repository.

Not in M4: C# (M5), Tier B badges, the review of blind-spot lists across languages, interactive graphs, `--verify`, the README rewrite and the 1.0.0 version (M6). Report 02 and existing card schemas must not change unless the spec requires it and you flag it under "Spec issues". Git-derived cards (reports 10 and 13) are language-independent: M4 should need little or no change to them, but check that blast radius, ownership and dead-code candidates behave for TS/JS file types and say what you found.

M4 is followed by no formal pause in `process.md`, but the milestone review (process step 5) applies: the plan must say what the user runs to judge it and what they need installed (Node and npm are the new host requirement; the spec says what preflight expects).

## Read first, in this order

1. Spec sections 2, 3, 4 (every report row that depends on extractors, the card tables, and the tier column), 5 (pipeline, restore hygiene 5.4, especially rules on `npx`, lockfiles and install scripts), 6 (all of it), 7 (V1 to V10 and V7), 8, 9, 10, 11 and 12.
2. `docs/process.md`.
3. Plans 007 and 009: how the Python adapter was built (adapter class, `ADAPTERS`, the shared tree-sitter and semgrep layer, the repository-wide adapter, extractor JSON, candidates and dispositions, blind-spot rules, V7, "partial" badges, the verification checks), and anything that says "M4" or "TypeScript".
4. `adapters.py`, `py_adapter.py`, `py_tools.py`, `py_worker.py` (and its `.lock`), `ts_worker.py` (and its `.lock`) and `scripts/node/` (they exist already: **read what they do today and what M1 or M2 put there on purpose**), `semgrep_worker.py`, `shared_tools.py`, `tools.json`, `toolcheck.py`, `restore.py`, `sandbox.py`, `deps.py` (what it already does for npm), `repo_adapter.py`, `candidates.py`, `checks_v7.py`, `scip_tool.py`, `scip_read.py`, `graphs.py`, `components.py`, `stages.py`, `render.py`, `check_page.py`, `page_audit.py`, and `rules/` (look at how Python rules are laid out and tested) and `tests/` (fixtures, how Python adapter fixtures are built).
5. `prompts/method.md` and `prompts/reports.md`: how Claude is told about languages and about what the extractors give it. M4 may need language-aware wording.

## First deliverable: a reconciliation

Before the task list, a section called **Spec versus code** listing every place where the spec and the code disagree, or where the spec assumes something the code does not do (including everything plans 008 and 009 changed and the spec's own "Settled in..." amendments). For each, say what you propose and mark it "plan can absorb it" or "needs a decision from the human". Areas to check, and look for others:

- What exists already for TS/JS (`ts_worker.py`, `scripts/node/`, `deps.py`, any tree-sitter or semgrep TS support, `tools.json` entries) versus what spec 6.1 and 6.2 require: dependency-cruiser, knip, scip-typescript, a shipped script on the TypeScript compiler API (types, exports, React component tree, router config), semgrep rules for routes, I/O sites, DI where applicable, retries and timeouts.
- Each extractor output file for TS/JS (`entry_points`, `graph`, `symbols`, `io_candidates`, `models`, `tests`, `dead`, `blindspots`): what the Python adapter emits, what the TS/JS adapter must emit in the same shape, and where the shape cannot be the same (for example public surface rules, barrel files, default exports, monorepo workspaces, path aliases from `tsconfig`).
- **Entry-point kinds for TS/JS**: package `bin`, `main`/`exports`, scripts, HTTP routes (Express, Fastify, Next.js file routes, etc.), queue consumers, scheduled jobs, container `CMD`, and the repository-wide kinds. Spec section 11 measures recall over the kinds in 6.1; say which frameworks you propose to support, and which go to Gaps. Do not guess a list: derive it from the spec and from what the golden repository uses.
- **Data model (report 08)** for TS/JS: ORMs and schema tools (Prisma, TypeORM, Drizzle, Sequelize, Mongoose, raw SQL migrations), and what the spec requires versus what is P1.
- **Tests (report 09)** for TS/JS: runners and config (Jest, Vitest, Mocha, Playwright, Cypress), skip markers, mocks.
- **React**: component tree, router config, hooks and context wiring; what is an extractor output, what is a blind spot (the spec lists context and hooks wiring as a blind spot), and which report and card shows it.
- **Restore hygiene and install**: how `npm ci`, `pnpm`, `yarn` and workspaces are handled by the restore step, lockfile detection, `--ignore-scripts`, the allowlist of environment variables, and what happens with no lockfile. Spec 5.4 rule 7 forbids bare `npx` with unpinned dependencies: say how dependency-cruiser, knip and scip-typescript are installed from a lockfile shipped with the skill, the way scip-python was.
- **V7 for TS/JS**: the blind-spot patterns listed in spec 6.4, the semgrep or tree-sitter rule for each, the hit counts to Gaps, and the fixed coverage items.
- **Candidates and dispositions** (plan 008): which new candidate kinds appear for TS/JS, their home cards (spec 6.1 table), and how completeness is checked.
- **Mixed-language repositories**: a Python backend with a TS frontend is common. How the adapters combine, how reports show both, and how `dossier check` and the "same card skeleton" rule (spec section 11 item 2) are met.
- **Preflight and `doctor`**: Node, npm and any tool the adapter needs; what `doctor` prints when missing; `--allow-missing` behaviour and the Gaps entry.
- **Golden TS repository**: which repository on this machine is the "golden TS repo"? Look under `/home/nick/dev/projects/` (read-only; list, do not build). If none is clearly the one, list it as an open question with candidates. Also say what the fixture repository for tests is, and whether the existing frozen fixture helps.
- Anything the spec marks P1 versus P0 (the cut line).

## Decisions to make and justify

Number them D1, D2, and so on. At least: the adapter structure (one class or several; how it reuses the shared tree-sitter and semgrep layer; how it relates to `ts_worker.py` and `scripts/node/`); how Node tools are pinned and installed (lockfile shipped under the skill, tool cache location, version recording in report 01); the order tools run in and their timeouts; how monorepos and workspaces are scoped; how `tsconfig` paths and project references are handled; how SCIP data is read for TS (reuse of `scip_read.py`); the card data shapes where TS/JS differs; which frameworks get routes, models and tests support in M4; how V7 patterns are detected; how mixed-language builds merge extractor output; how staleness and incremental rebuilds treat the new extractors; the version `VERSION` bumps to; and, if you propose more than one session, where it is cut, at committed, tested boundaries.

## Format of the plan

Write it to `SKILL/docs/plans/010-m4-plan.md`, following the project's planning-docs rules (the `claude-planning-docs` skill). The human starts each session with one line, such as "Start phase 1 as outlined in docs/plans/010-m4-plan.md", and that line must be enough. Do not write a copy-and-paste prompt for Sonnet. The plan has:

1. **Summary**: what M4 delivers, in five lines or fewer, and any phase cuts. Then **Acceptance pause status** and **Carried over from the pause** as described above.
2. **Shared rules**: skills to load (`git-commit`, `git-workflow`, `py-projects`, `py-unit-tests`, `claude-planning-docs`, and the docs and release skills where relevant), branch name, commit style, what must never be touched (the installed clone, `/home/nick/dev/dossiers/`, the frozen fixture, the pinned repositories), scratch-directory and environment-variable discipline (`DOSSIER_HOME`, `DOSSIER_CONFIG`, `DOSSIER_CACHE` set to a fresh folder), tests first with the failing line recorded, do not weaken a check to make it pass, stop and report if the code contradicts the plan, and tick the checkbox in the same commit as the task. Say that report 02 and existing card schemas are not to change except where the plan says so, and that the Python adapter's behaviour must not change (the Python golden run must give the same results before and after).
3. **Spec versus code**: the reconciliation above.
4. **Decisions**.
5. **Phases**, each a heading `## Phase <n>: <title>`, used identically everywhere. Each is self-contained and holds: what to read first and which skills to load; a first step that checks what earlier phases recorded; an ordered list of tasks; deliverables and how each is checked; the cut line; acceptance criteria; and the branch and release steps. Every task has: an id (M4-1, M4-2, ... numbered across phases), a goal, the exact files to touch, the interface or data shape, step-by-step instructions, a done-check that can be run (a command and its expected result), a suggested commit message, and a checkbox. Each task can be finished and committed on its own and the suite passes after every one. No task needs design judgment. The cut line must never drop extractor fixture tests, V7 for TS/JS, or the plan 008 checks applied to anything new. Each phase says to write its results back into the plan under "Results".
6. **Verification**: the exit criterion checked end to end on the golden TS repository (copy any existing dossier to scratch first): `doctor`, a full build, every report built from extractors, candidates reconciling, V1 to V10 passing, blind-spot hits in Gaps, the plan 008 browser and static audits reporting no problems at desktop and phone width in light and dark themes, an incremental rebuild, a build with Node removed degrading correctly with a Gaps entry (or failing clearly), a mixed Python plus TS repository, **and the Python golden run unchanged**, and the full test run. Include a measured comparison against what the user knows of the repo, in the form of spec section 11 item 3 (entry-point recall and precision, inputs and outputs recall), as a checklist for the user to fill in, not for Sonnet to judge. Say how Sonnet records results.
7. **Risks and open questions**: things the human must answer before Sonnet starts.
8. **Spec issues**: anything in the spec that looks wrong or incomplete. Do not work around these in the plan.
9. **Sources**: a table of every external fact you verified, with its URL and the date.

## Rules

- The spec wins over your preferences. If you think it is wrong, say so under "Spec issues" and plan to the spec anyway unless the problem blocks the work. Spec amendments the author approved in plans 008 and 009 are part of the spec now.
- The spec's tool table says its names and invocations are "from memory and must be verified when implementing". Every external tool, flag, version, package name, config format or output format (dependency-cruiser, knip, scip-typescript, the TypeScript compiler API, semgrep's JS/TS rule syntax, tree-sitter grammars, `npm ci`, `pnpm`, `yarn`) must be re-checked against current documentation by web search, not memory. Record the source URL for each. If you cannot verify one, list it as an open question. Pin exact versions and say where each was confirmed (registry page, release page).
- Every child process goes through the safe runner. Do not add sandboxing (spec decision 5). Install scripts of the target repository's dependencies stay disabled per spec 5.4.
- Never plan anything that reads or writes `/home/nick/dev/dossiers/` or builds a dossier of a real repository, except in Verification, and there only into a scratch directory.
- Plain language for anything a user of the dossier will read.
- Do not invent facts about the code. If you did not read it, say so.
- When you finish, reply with: the path of the plan, the five most important risks, the questions the human must answer, and the exact one-line instruction to type to start Phase 1.
