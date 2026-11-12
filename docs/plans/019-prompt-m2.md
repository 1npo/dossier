# Prompt: plan milestone M2 (paste into a fresh Opus session)

You are planning, not building. Write an implementation plan for **milestone M2** of the `dossier` 1.0.0 specification. A different, less capable model (Sonnet) will carry out your plan one task at a time, across **at most three sessions**, so the plan must be explicit enough to follow without design judgment and must be cut into phases at committed, tested boundaries. Do not modify any file except the plan you write. Do not run `/dossier build` against any repository, and do not install tools or run restores. Reading files and web searches are fine.

## Where things are

- The skill: `~/encamp/configs/user/claude/.claude/skills/dossier` (call it `SKILL`).
- The specification, which is the authority on what to build: `SKILL/docs/plans/004-v1-spec.md`.
- How the work is organised: `SKILL/docs/process.md`.
- The finished M1 plan, including its "Verification results", "Risks", "Spec issues" and "Deviations": `SKILL/docs/plans/006-m1-plan.md`. Use it as the model for format and level of detail, and as the record of what M1 actually did. The M0 plan (`005-m0-plan.md`) is the record of the card schemas and renderer.
- Backlog of things deliberately left out: `SKILL/docs/post-v1.md`.
- Today's behaviour: `SKILL/SKILL.md`, `SKILL/prompts/method.md`, `SKILL/prompts/reports.md`, `SKILL/prompts/schema/*.json`, `SKILL/README.md` (parts are stale, so trust the code over it), the code under `SKILL/scripts/` (especially `adapters.py`, `shared_tools.py`, `ts_worker.py`, `semgrep_worker.py`, `stages.py`, `buildlog.py`, `toolcheck.py`, `tools.json`, `render.py`, `resolve.py`, `incremental.py`, `restore.py`, `sandbox.py`, `workarea.py`, `dossier.py`, `gather.py`, `check_page.py`), `SKILL/rules/README.md` and `SKILL/tests/` (`unit/`, `integration/`, `fixtures/`, `tools/`).
- Run `git log --oneline` in the repository first. M1 is merged (version 0.6.0). Anything the M1 plan says it moved to M2 is part of this milestone.

## Read first, in this order

1. Spec sections 2 (principles), 3 (questions), 4 (all report and card tables, but read 03 to 09, 11 and 12 closely), 5.3, 6 (all of it), 7 (V2 to V5 and V7 in particular), 8 (card schema), 10 (milestones), 11 (definition of done) and 12 (decisions).
2. `docs/process.md`.
3. The M1 plan's sections 3 (Spec versus code), 4 (Decisions D1 to D12), 8 (Spec issues), "Verification results" and "Deviations". Pay particular attention to D1 (the tool table and pins), D7 (the adapter interface), D12 (shared tool cache), and every line that says "M2".
4. `adapters.py`, `shared_tools.py`, `stages.py`, `render.py`, and the card schemas in full. Search the rest for what you need.
5. `prompts/method.md` and `prompts/reports.md`: M2 changes how Claude is told to write reports 03 to 09, 11 and 12, so you need to know exactly what they say now.

## M2 as the spec defines it

Content (spec section 10): the Python vertical slice. grimp, vulture, scip-python, the Python semgrep rules and the Python blind-spot list; reports 03 to 09, 11 and 12; V2 to V5 and V7 (Python).

Exit criterion: a Python repository builds all reports from extractors, and the extractor candidates reconcile (every candidate has a disposition, V5).

Also in M2, carried from M1 (check each against the M1 plan and the code; do not trust this list over them):

- The "partial" badge for cards affected by a missing tool (needs a tool-to-card map, spec issue 8).
- "A report is stale if its extractor output changed" (5.3), now that reports cite extractor output.
- Re-verifying the Python tools' names, flags, versions and behaviour (M1 D1 says each tool is re-checked at the start of the milestone that first runs it).
- grimp must not write `.grimp_cache` into the checkout (M1 spec issue 13).
- Running M1's verification block C on a build that has reports, so `check_page.py` can report `"problems": 0` (the M1 run had no citations to open the code viewer).
- Any existing dossier fails V10 until rebuilt; `FIX`-based checks need `--allow-errors` (M1 risk 5).

Not in M2: report 10 and 13 content, the report 14 and 15 additions, `summary.json` and V8 (all M3); any TS/JS or C# support (M4, M5); Tier B badges, `--verify`, README rewrite (M6). Report 02 and the M0 card schemas must not change unless the spec requires it and you flag it under "Spec issues".

## First deliverable: a reconciliation

Before the task list, give a section called **Spec versus code** listing every place where the spec and the code disagree, or where the spec assumes something the code does not do. For each, say what you propose, and mark it "plan can absorb it" or "needs a decision from the human". Areas to check, and look for others:

- The adapter interface M1 built versus what the spec's 6.1 output table needs (`entry_points`, `graph`, `symbols`, `io_candidates`, `models`, `tests`, `dead`, `blindspots`). Which outputs M2 can fill for Python and from which tool, and which stay empty or are computed from the others.
- How `prepare` runs extractors today (stage order, working directory, the checkout, the path filter, the runner and its timeouts, where `extract/*.json` lands) versus what grimp (needs an importable package), vulture, and scip-python (wants an installed environment and Node) require. Which run through `uv`, which through `npx`, and what the restore stage must have produced for each.
- The extractor output store and its `(sha, extractor version, tool versions)` key from M1 (D-numbers in the plan) versus what M2's multi-tool adapter needs. Does one adapter version cover several tools?
- How reports cite extractor output. The citation syntax and V1 today versus the citation of an extractor record, and what V2 ("identifiers named in backticks in a cited statement appear in the cited range") needs from the resolver.
- The card schemas for reports 03 to 09, 11 and 12 versus what extractors can supply: which cards are computed (tier M), which are adjudicated from candidates (tier A), which are written by reading (tier R), and the exact data each prompt will be given.
- V3 (flow-diagram arrows against graph or call edges), V4 (every tracked non-excluded source file has one component, every catalog component has a detail entry), V5 (every candidate has a disposition) and V7 (blind-spot hits recorded in Gaps): where each lives in `render.validate`, what data it needs, how a disposition is stored in the card JSON, and what "unexpected" means for each failure level.
- `prompts/method.md` and `prompts/reports.md` today versus the spec's reading model: how Claude is told to consume candidates, record dispositions and avoid inventing items; chunking and subagent use for the new reports.
- Semgrep rules: `rules/README.md` promises `rules/python/` and `rules/all/` with ids `dossier.<scope>.<category>.<name>` and `metadata.category` feeding `io_candidates`. Which categories M2 needs (routes, I/O sites, DI, retries, timeouts, flags and so on, per 6.2 and 6.1), and how rules are tested.
- The Python blind-spot list in 6.4 versus what a rule can actually detect.
- Existing tests and fixtures: what can be reused for a Python fixture repository with known entry points, imports, dead code and I/O, so each extractor has an exact expected output. The test command is `uv run --with pytest --with pygments python -m pytest tests`, run from `SKILL`.
- Every other place the spec says "extractor", "candidate", "disposition", "blind spot" or "partial", and whether the code has a home for it.

## Decisions the plan must make

State each decision, the alternatives you rejected and why. At least:

1. The Python adapter's module layout and how the tools are invoked (command lines, working directory, environment, output format, timeout), keeping each file a size Sonnet can edit safely. Include how the scip index is read (the SCIP protobuf format and which library or script decodes it) and how that library is installed and pinned.
2. The exact JSON shape of each `extract/*.json` file M2 produces, with ids that reports and dispositions can reference stably across builds.
3. How a report card cites and disposes of a candidate (the id, the disposition values, where they are written in the card JSON), and the V5 rule built on it.
4. The component model: how the component catalog is derived (from grimp's graph, directory structure, or Claude's reading), what V4 checks, and what the human reviews.
5. The Python semgrep rule set: categories, rule ids, and the test fixtures that prove each rule fires and does not fire.
6. The blind-spot rules for Python (V7), where hits go, and how Gaps shows them.
7. The tool-to-card map and the "partial" badge rule.
8. The V2, V3 and V4 implementations: inputs, severity, what is counted in Gaps.
9. How `incremental` decides a report is stale when its extractor output changed.
10. How the prompts change: which parts of `method.md` and `reports.md` are rewritten, the order of report writing (extractor-fed reports before those that depend on them), and chunking for large repositories.
11. The version number M2 bumps `VERSION` to, and what that does to existing dossiers.
12. How the three sessions are cut. Propose boundaries at committed, tested points, for example: (1) framework, Python adapter and extractors with fixtures; (2) reports 03 to 09, 11, 12 built on the extractors, prompts, "partial" badges, staleness; (3) V2 to V5 and V7, and the end-to-end verification. You may choose different cuts, but each phase must leave the test suite passing and the skill usable.

## Format of the plan

Write it to `SKILL/docs/plans/007-m2-plan.md`, following the project's planning-docs rules (the `claude-planning-docs` skill). The human starts each session with one line, such as "Start phase 2 as outlined in docs/plans/007-m2-plan.md", and that line must be enough. Do not write a copy-and-paste prompt for Sonnet and do not put phase instructions in a fenced "paste this" block. The plan has:

1. **Summary**: what M2 delivers, in five lines or fewer, and the phase cuts.
2. **Shared rules**: conventions and constraints that apply to every task in every phase (skills to load, commit style, branch, what must never be touched, scratch-directory and environment-variable discipline from M1). Say that Report 02 and the M0 card schemas are not to change except where the plan says so. Every phase reads this section.
3. **Spec versus code**: the reconciliation above.
4. **Decisions**: as above.
5. **Phases**, each a heading `## Phase <n>: <title>`, used identically everywhere. Each phase is self-contained and holds: what to read first and the skills to load (`git-commit`, `git-workflow`, `py-projects`, `py-unit-tests`, and any other relevant); a first step that checks what earlier phases recorded or cut (git log, the plan's results, `CHANGELOG`) and picks up work moved to this phase; an ordered list of tasks; the deliverables and how each is checked; the cut line; the acceptance criteria; and the branch and release steps. Every task has: an id (M2-1, M2-2, ... numbered across phases), a goal, the exact files to touch, the interface or data shape it must satisfy, step-by-step instructions, a done-check that can be run (a command and its expected result), a suggested commit message, and a checkbox. Order tasks so each can be finished and committed on its own and the test suite passes after every one. Say which tasks are independent. Prefer small tasks; none should need design judgment. The cut line must never drop the fixture tests for extractors or V5. Each phase says to write its results (timings, decisions, what was cut, deviations) back into the plan under that phase's "Results".
6. **Verification**: how the exit criterion is checked end to end, on a real Python repository on this machine (name one, or say how to pick one; M1 used `cannalerts`): `doctor`, a build that runs every extractor, the extractor JSON, reports 03 to 09, 11 and 12 written and rendered, V2 to V5 and V7 behaviour, `check_page.py` reporting `"problems": 0` with citations present, an incremental rebuild that reuses unchanged extractor output, a build with a tool missing showing "partial" badges and Gaps items, and the full unit test run. Say how Sonnet records results back into the plan.
7. **Risks and open questions**: things the human must answer before Sonnet starts.
8. **Spec issues**: anything in the spec that looks wrong or incomplete. Do not work around these in the plan.

## Rules

- The spec wins over your preferences. If you think it is wrong, say so under "Spec issues" and plan to the spec anyway unless the problem blocks the work.
- Tool names, flags, versions and output formats for grimp, vulture, import-linter, scip-python, tree-sitter, semgrep and the SCIP format must be re-checked against current documentation (use web search), not memory and not just the M1 table. Record the source URL for each. If you cannot verify one, say so and list it as an open question instead of guessing.
- Restores and Node tools run on the host with the user's privileges; this is an accepted, recorded risk (spec decision 5). Do not add sandboxing. Every child process goes through the M1 safe runner.
- Never plan anything that reads or writes `/home/nick/dev/dossiers/` or builds a dossier of a real repository except in the Verification section, and there only into a scratch directory with `DOSSIER_HOME`, `DOSSIER_CONFIG` and `DOSSIER_CACHE` set.
- Plain language for anything a user of the dossier will read.
- Do not invent facts about the code. If you did not read it, say so.
- When you finish, reply with: the path of the plan, the five most important risks, the questions the human must answer, and the exact one-line instruction to type to start Phase 1.
