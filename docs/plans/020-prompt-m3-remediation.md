# Prompt: plan the M3 remediation (paste into a fresh Opus session)

You are planning, not building. Write an implementation plan that finds and fixes **every regression and spec violation in the output of milestones M0 to M3** of the `dossier` 1.0.0 specification. A less capable model (Sonnet) will carry out your plan one task at a time, across several sessions, so the plan must be explicit enough to follow without design judgment and must be cut into phases at committed, tested boundaries. Do not modify any file except the plan you write (`SKILL/docs/plans/008-m3-remediation-plan.md`). Do not run `/dossier build` against any repository, do not install tools, and do not run restores. Reading files, running `render` on existing data, opening the rendered page in a browser, and web searches are fine.

## Why this exists

The author ran user acceptance testing on the rendered M3 dossier for the `cannalerts` repository and rejected it. The author is not going to itemise the problems, because there are too many. Your first job is to find them. The examples below are only the ones the author happened to write down; treat them as a sample of failure classes, not as the list.

Author's notes, verbatim:

- The "How this dossier was made" table is ugly. It must be a table, a diagram, or both.
- The Dependencies and Contributors cards are both a visual mess: icons the size of the page, overlapping or squashed unformatted text and tables.
- The "Components and what they import" diagram is unreadable and useless.
- The component detail table is not rendered as a table, just a pile of text.
- "Imports between components / dependency graph" is likewise unreadable and useless.
- Key Flows covers the `run` command and shows a diagram of onboarding a new site, but gives no outlined description of the process, unlike the diagram above it.
- The tables in the Relationships card are missing many fields. The author's explicit instruction was that cards be comprehensive, with no caps or limits.
- The Recipes table is not rendered as a table, just a pile of justified text.

Failure classes to look for beyond these: tables that render as text; broken CSS or oversized SVG/icons; unreadable diagrams (size, label overlap, no grouping); diagrams without the notes the spec requires; silently dropped rows, columns or fields (any cap, slice, `[:N]`, `top N`, truncation, or "first N" in code or prompts); schema columns missing from rendered tables; cards in the wrong shade or without a tier badge; report 02 content that is no longer identical to before M0; content that is wrong rather than badly formatted; and checks that should have caught all of this but did not.

Accept that the same process failed several times: M2 and M3 each passed their own exit criteria and the browser check, yet the page is visibly broken. Treat "why did our verification pass this?" as a first-class finding, not an afterthought.

## Where things are

- The skill: `~/encamp/configs/user/claude/.claude/skills/dossier` (call it `SKILL`). Its repository root is `~/encamp`; run `git log --oneline` there first. M0 to M3 are merged.
- The specification, which is the authority: `SKILL/docs/plans/004-v1-spec.md`. Sections 2 (especially principle 7: fixed structure, no caps, nothing dropped), 4 (card tables, with each card's shape and columns), 7 (verification), 8 (card schema), 10 and 11.
- How work is organised: `SKILL/docs/process.md`.
- Earlier plans, as the record of what each milestone did and claimed to verify: `SKILL/docs/plans/005-m0-plan.md`, `006-m1-plan.md`, `007-m2-plan.md` (read their "Verification results" and "Deviations"). Plans 001 to 003 settle colours, card clean-ups and the Dependencies card.
- Code: `SKILL/scripts/` (especially `render.py`, `check_page.py`, `gather.py`, `stages.py`, `resolve.py`), `SKILL/prompts/` (`method.md`, `reports.md`, `schema/*.json`), `SKILL/tests/` (`unit/`, `integration/`, `fixtures/`).
- The artefact under test: `~/dev/dossiers/cannalerts/dossier-cannalerts.html`, built from the sibling `reports/`, `facts.json`, `dependencies.json`, `activity.json`, `build.json`, `chunks.json`, `extract/` and `notes/`. You may re-run `render` on this data into a scratch directory (never overwrite the author's copy). The source repository is `~/dev/projects/cannalerts`.
- A last known good: use `git log` and `git worktree` to render the pre-M0 skill against the same data, so you can tell regressions (it used to work) from gaps (it never did). Report 02 and its Contributors, knowledge map, commit calendar and Dependencies cards were required to stay unchanged.

## How to investigate (the plan must record the results)

1. **Look at the page.** Open the HTML in a real browser at desktop and phone widths, in light and dark themes. Screenshot every card of every report. Write an inventory: one row per card, with columns for what the spec requires, what rendered, and the defect (if any). Do not skip cards that look fine; the inventory is the proof of coverage.
2. **Classify each defect** as render bug (data is right, drawing is wrong), content bug (data or prose is wrong or missing), spec violation (code contradicts the spec), spec gap (the spec is silent or wrong), or verification gap (a check should have caught it). Find the root cause in code or prompts, with `file:line`, not just the symptom. Group defects that share a root cause.
3. **Audit for dropped data.** Grep `render.py`, the gatherers, the prompts and the schema files for anything that limits, slices, samples, truncates or summarises. For every table, compare the schema's columns with the columns rendered and with the data available in the JSON. For every list, compare counts in the source data with counts on the page.
4. **Audit the diagrams.** For each Mermaid or SVG diagram, state its node and edge counts, and whether it can be read at the size it is drawn. Say what the spec required instead (for example the interim fallback for `components.map` and `interactions.graph`: a diagram grouped by area plus a table of every component and edge).
5. **Audit the checks.** Read `check_page.py` and the V-checks. List what each actually asserts. For every defect found, say which check should have caught it and why it did not.

## What the plan must contain

Follow the format and level of detail of `006-m1-plan.md` and `007-m2-plan.md`. At minimum:

1. **Findings**: the card inventory, the defect list grouped by root cause, and the classification from step 2. Number every defect (R1, R2, ...) so tasks can cite them.
2. **Spec issues**: anywhere the spec itself caused or permitted the failure (for example, the interim fallbacks being under-specified). Propose spec amendments, but flag each for the author to approve; do not assume them.
3. **Decisions**: each design choice the executing model would otherwise have to make (table component, diagram sizing and layout engine, how wide tables scroll, how to show large tables). Decide them here.
4. **Tasks**: ordered, small, each with the files to touch, the exact change, the test to write first, and a command to verify it. Fix root causes, not symptoms. Every fix to a table, cap or diagram gets a test that fails before the fix.
5. **Verification redesign**: new or strengthened checks so this class of failure cannot pass again. At least: a render check that every `table`-shape card produces a real `<table>` with every schema column and one row per source record; a check that nothing is capped (source count equals rendered count); diagram checks (rendered size, node count against readability thresholds, and that required notes follow each flow diagram); a layout check in a real browser at two widths (no element wider than the viewport, no SVG or icon larger than a sane bound, no overlapping text boxes); and a golden-page comparison for report 02. Say how each check is tested against a deliberately broken page.
6. **Phases and sessions**: cut at committed, tested boundaries, with a stop point after each phase where the author can look at the real page. Put the changes that most affect what the author sees (broken cards, tables, dropped data) first.
7. **Acceptance**: the author's own acceptance procedure for the result: which page to open, what to look at, and what "done" means. It must cover every defect in the inventory, not only the eight above.
8. **Risks and out-of-scope**: what you could not verify, and anything you deliberately left to M4 and later (for example the interactive graphs that spec section 10 assigns to M6). Be strict: the interim fallback for those graphs is in scope and must be readable.

## Rules

- Do not weaken a spec requirement to make a fix easier. If a requirement cannot be met, say so and ask the author.
- Do not invent defects. Every item in the findings needs evidence: a screenshot, a count, or a `file:line`.
- Do not bundle new features into the plan. Fix what M0 to M3 should have delivered.
- Keep the plan under the planning-doc conventions in `claude-planning-docs` (file naming, location).
- End with a short list of questions for the author, if any. Do not stop to ask before writing the plan unless you are blocked.
