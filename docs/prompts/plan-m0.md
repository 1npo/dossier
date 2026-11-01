# Prompt: plan milestone M0 (paste into a fresh Opus session)

You are planning, not building. Write an implementation plan for **milestone M0** of the `dossier` 1.0.0 specification. A different, less capable model (Sonnet) will carry out your plan one task at a time, so the plan must be explicit enough to follow without design judgment. Do not modify any file except the plan you write. Do not run `/dossier build` against any repository.

## Where things are

- The skill: `~/encamp/configs/user/claude/.claude/skills/dossier` (call it `SKILL`).
- The specification, which is the authority on what to build: `SKILL/docs/plans/004-v1-spec.md`.
- How the work is organised: `SKILL/docs/process.md`.
- Earlier plans and notes that still apply: `SKILL/docs/plans/001-improvements.md`, `002-add-new-dependencies-card.md`, `003-update-profiler-language.md`, and `SKILL/docs/scratch/000-fixed-cards.md`.
- Today's behaviour: `SKILL/SKILL.md`, `SKILL/prompts/reports.md`, `SKILL/prompts/method.md`, `SKILL/README.md` (parts are stale, so trust the code over it), and the code under `SKILL/scripts/` (especially `render.py`, `dossier.py`, `incremental.py`, `resolve.py`, `check_page.py`), `SKILL/assets/` (`dossier.js`, `dossier.css`, `template.html`) and `SKILL/tests/`.
- An example of the current output: `/home/nick/dossier-encamp.html` (about 8 MB). Do not read it whole. Extract the structure you need with a script, for example the headings of each report section. Its source report files (`reports/*.json`) may not exist on this machine, so check and plan accordingly.

## Read first, in this order

1. The spec, completely. Pay particular attention to sections 2 (principles), 4 (reports and cards), 7 (checks V1 to V10), 8 (card schema) and 10 and 11 (milestones, definition of done).
2. `docs/process.md`.
3. The code and prompts listed above. Read `render.py` and `dossier.py` in full. Search the rest for what you need.

## M0 as the spec defines it

Content: card schema files, schema validation (V6), `render.py` drawing fixed titles, tier badges and question lines, and mapping the existing content onto the new skeleton. Report 02 and its Contributors, knowledge map, calendar and Dependencies cards are left untouched.

Exit criterion: the existing encamp dossier re-renders with the new skeleton and passes V6, and report 02's content is unchanged.

Not in M0: checkout, preflight, extractors, `build.json`, the `dossier.process` card, new prompts for the new cards, any language support. Where a card in the new skeleton has no content yet, M0 renders it as a clearly marked placeholder ("not yet generated"), and the "not applicable with evidence" form from section 8 must also work.

## First deliverable: a reconciliation

I wrote the spec without reading the renderer. Before the task list, give a section called **Spec versus code** that lists every place where the spec and the code disagree, or where the spec assumes something the code does not do. For each, say what you propose, and mark each as either "plan can absorb it" or "needs a decision from the human". Known areas to check, and look for others:

- The report list and order (`REPORTS`, `NAV_GROUPS`, the expected report set in `dossier.py`) versus the spec's reports 01 to 16, including the retired reports.
- Anything keyed on report ids: incremental staleness (`incremental.py`), open-item IDs and user decisions in `state.json` (`resolve.py`), the Gaps and Corrections reports, `check_page.py`, the tests.
- How blocks and headings are written and rendered today versus the spec's closed card schema (fixed ids, titles, shapes, required columns, no limits on rows or entries).
- Where the Contributors card, knowledge map, calendar and Dependencies card are attached today, and how to guarantee they do not change.
- The standard cards (Executive summary, Contents, References) and the two-shade scheme from plans 001 and `000-fixed-cards.md`, versus the three tier badges (M, A, R) in the spec.
- Existing dossiers: a skill version bump forces a full rebuild, and decisions saved in `state.json` must survive. Say what M0 must do about the version number and about old report files.
- The spec's claim that report 02 stays "unchanged": define a concrete, scriptable way to test it.

## Decisions the plan must make

State each decision, the alternatives you rejected and why. At least:

1. Where the schema files live and their format (the spec says `prompts/schema/<report>.json`), including how repeated entries, "not applicable" cards and placeholders are expressed.
2. How existing report JSON (free-form blocks with headings) is mapped onto schema cards: a one-off migration script, a compatibility layer in `render.py`, or something else. Say what happens to content that fits no card.
3. How V6 reports problems (error versus warning) and where it runs.
4. How tier badges and the question line are drawn, and how this fits the existing CSS and the shade key.
5. How the new report list replaces the old one in navigation and in the summary index, and what happens to the retired reports.

## Format of the plan

Write it to `SKILL/docs/plans/005-m0-plan.md`. Sections, in order:

1. **Summary**: what M0 delivers, in five lines or fewer.
2. **Spec versus code**: the reconciliation above.
3. **Decisions**: as above.
4. **Tasks**: an ordered list. Every task has: an id (M0-1, M0-2, ...), a goal, the exact files to touch, the interface or data shape it must satisfy, step-by-step instructions, a done-check that can be run (a command and its expected result), a suggested commit message, and a checkbox. Order tasks so that each can be finished and committed on its own and the test suite passes after every one. Say which tasks are independent. Prefer small tasks; none should need design judgment from the implementer.
5. **Verification**: how the exit criterion is checked end to end, including the report 02 comparison and running `check_page.py` (see `SKILL/SKILL.md` step 7) and the unit tests (`uv run --with pytest --with pygments python -m pytest tests`, run from `SKILL`).
6. **Risks and open questions**: things the human must answer before Sonnet starts.
7. **Spec issues**: anything in the spec that looks wrong or incomplete. Do not work around these in the plan.

## Rules

- The spec wins over your preferences. If you think it is wrong, say so under "Spec issues" and plan to the spec anyway unless the problem blocks the work.
- No limits on the number of rows, components or entries in any card: card structure is fixed, content grows with the repository.
- Plain language for anything a user of the dossier will read.
- Do not invent facts about the code. If you did not read it, say so.
- When you finish, reply with: the path of the plan, the five most important risks, and the questions the human must answer.
