# Prompt: plan milestone M1 (paste into a fresh Opus session)

You are planning, not building. Write an implementation plan for **milestone M1** of the `dossier` 1.0.0 specification. A different, less capable model (Sonnet) will carry out your plan one task at a time, so the plan must be explicit enough to follow without design judgment. Do not modify any file except the plan you write. Do not run `/dossier build` against any repository, and do not install tools or run restores.

## Where things are

- The skill: `~/encamp/configs/user/claude/.claude/skills/dossier` (call it `SKILL`).
- The specification, which is the authority on what to build: `SKILL/docs/plans/004-v1-spec.md`.
- How the work is organised: `SKILL/docs/process.md`.
- The finished M0 plan, including its "Verification results", "Risks" and "Spec issues" sections and the deviations recorded at the end: `SKILL/docs/plans/005-m0-plan.md`. Use it as the model for format and level of detail, and as the record of what M0 actually did.
- Backlog of things deliberately left out: `SKILL/docs/post-v1.md`.
- Today's behaviour: `SKILL/SKILL.md`, `SKILL/prompts/method.md`, `SKILL/README.md` (parts are stale, so trust the code over it), the code under `SKILL/scripts/` (especially `dossier.py`, `gather.py`, `incremental.py`, `render.py`, `schema.py`, `check_page.py`, `resolve.py`) and `SKILL/tests/` (`unit/`, `integration/`, `fixtures/`, `tools/`).
- Run `git log --oneline` in the repository first. M0 is merged (version 0.5.0). Anything the M0 plan says it moved to M1 is part of this milestone.

## Read first, in this order

1. Spec sections 5 (pipeline changes, all of 5.1 to 5.4), 6.2 and 6.3 (tools and language tiers), 7 (checks V1 to V10), 10 (milestones), 11 (definition of done, items 3 and 4 in particular) and 12 (decisions, including "Still to do in M1").
2. `docs/process.md`.
3. The M0 plan's verification results, risks, spec issues and deviations.
4. `dossier.py` and `gather.py` in full (that is where `prepare`, `build` and the CLI live today). Search the rest for what you need.

## M1 as the spec defines it

Content (spec section 10): checkout, preflight, `doctor`, `clean`, the path filter, the `build.json` run record, the `dossier.process` card in report 01 rendered from it, V9 and V10, restore hygiene (5.4), the adapter interface, and the shared tree-sitter and semgrep layer. Decision 7 in section 12 also falls here: pin the version of every tool in 6.2 and verify names, flags and behaviour against current documentation.

Exit criterion: `doctor` lists missing tools correctly; a Python repository gets a verified checkout; the process card renders from a real build and V10 passes; the hygiene tests in section 11 (item 4) pass.

Not in M1: the extractors themselves for Python or any other language (grimp, vulture, scip-python and so on are M2), new prompts for cards, reports 03 to 16 content, V2 to V5, V7, V8, any TS/JS or C# support. The adapter interface and the shared tree-sitter/semgrep layer must exist and be tested with a trivial or fixture adapter, but M1 does not need a real Python adapter.

## First deliverable: a reconciliation

Before the task list, give a section called **Spec versus code** that lists every place where the spec and the code disagree, or where the spec assumes something the code does not do. For each, say what you propose, and mark it either "plan can absorb it" or "needs a decision from the human". Areas to check, and look for others:

- What `prepare` does today (steps, order, where it reads the repository) versus the spec's 5.1 steps 1 to 7. Where the checkout slots in, and which steps must read the checkout and which must keep reading the original repository's git objects.
- Where state and outputs live today (`<home>/<repo>/`, `state.json`, `facts`, chunks) versus the spec's two locations: the per-repository working area `~/.local/cache/dossier/<repo>/` and the output folder. The `cache_dir` setting in the home config: does a home config exist today?
- `state.json`: the once-per-repository restore answer. Which module owns state, and how `resolve.py` and `incremental.py` use it.
- The language detection the gatherer already does versus what preflight needs (the tools each language requires, from 6.2).
- Incremental builds: 5.3 keys extractor outputs by `(sha, extractor version)`. M1 has no extractors, so say what M1 builds of this and what it leaves for M2.
- The `dossier.process` card: M0 draws a placeholder for it in report 01 (see the M0 plan's task that added it). What shape does the schema give it, and what does `build.json` have to contain for V10 to pass? The spec says "the fixed process list" for V10 but check that the list is actually defined.
- Restore (5.1 step 3) and the Node and .NET extractors are in the hygiene rules, but M1 has no extractors. Say which hygiene rules M1 implements as a reusable "run a child process safely" function, and how that function is tested with the fixture repository from section 11 item 4.
- Existing tests and fixtures: which can be reused for the fixture repository, and what the test suite looks like (`uv run --with pytest --with pygments python -m pytest tests`, run from `SKILL`).
- Every other place the spec says "tool", "version", "pinned", "timeout" or "config", and whether the code has a home for it.

## Decisions the plan must make

State each decision, the alternatives you rejected and why. At least:

1. How the tool list and the pinned versions are stored (a data file under `SKILL`, probably) and how `doctor` and preflight read it. Include how a tool's presence and version are detected, and the install command printed for each.
2. The module layout: where the checkout, preflight, safe subprocess runner, `build.json` writer and adapter interface live (new modules versus `dossier.py`), keeping each file a size Sonnet can edit safely.
3. The `build.json` format: the fixed process list (step ids), the record fields, how it is appended crash-safely, and the rule that Claude never edits it.
4. The safe subprocess runner: how the scrubbed environment, scratch `HOME`, private caches, the allowlist, the process-group timeout and the recorded variable names are implemented, and how a test proves each of them.
5. The trusted-ref check (5.4 rule 4): how "tag", "tip of the default branch" and "reachable from the default branch" are computed, including the `origin/HEAD` fallback to `main` or `master`.
6. The path filter and V9: where it runs, what "unexpected" means, and what is counted and logged.
7. The adapter interface: the methods, the data an adapter returns, and how the shared tree-sitter and semgrep layer is called from it. Keep it to what M2 needs, with no speculative generality.
8. How V9 and V10 are reported (info versus error) and plugged into the existing `render.validate` flow from M0.
9. The version number. What does M1 bump `VERSION` to, and what does a bump do to existing dossiers (M0 recorded that a bump forces a full rebuild)?

## Format of the plan

Write it to `SKILL/docs/plans/006-m1-plan.md`, following the project's planning-docs rules (the `claude-planning-docs` skill): the plan must be usable by a one-line instruction from the human such as "Start phase 1 as outlined in docs/plans/006-m1-plan.md". Never write a copy-and-paste prompt for Sonnet. M1 is one implementation session (see `process.md`), so it has one phase, but the plan must still be structured that way:

1. **Summary**: what M1 delivers, in five lines or fewer.
2. **Shared rules**: conventions and constraints that apply to every task (read the relevant skills, commit style, branch, what must never be touched). Say that Report 02 and the M0 card schemas are not to change.
3. **Spec versus code**: the reconciliation above.
4. **Decisions**: as above.
5. **Phase 1: M1 implementation**, self-contained. What to read first and the skills to load (`git-commit`, `git-workflow`, `py-projects`, `py-unit-tests`, and any other relevant); the first step, which is to check the git log and the M0 plan for work moved to M1; then an ordered list of tasks. Every task has: an id (M1-1, M1-2, ...), a goal, the exact files to touch, the interface or data shape it must satisfy, step-by-step instructions, a done-check that can be run (a command and its expected result), a suggested commit message, and a checkbox. Order tasks so that each can be finished and committed on its own and the test suite passes after every one. Say which tasks are independent. Prefer small tasks; none should need design judgment. Include the cut line (what to drop if the session runs short, never dropping the hygiene tests), the acceptance criteria, and the branch and release steps (branch, merge, version bump, per the git skills).
6. **Verification**: how the exit criterion is checked end to end: `doctor` with a tool removed from `PATH`, a verified checkout of a real Python repository (name one on this machine, or say how to pick one), a real `build.json` from a build, the process card rendered from it, V10 passing, the hygiene fixture test, `check_page.py` reporting `"problems": 0`, and the full unit test run. Say how Sonnet records results back into the plan under "Verification results".
7. **Risks and open questions**: things the human must answer before Sonnet starts.
8. **Spec issues**: anything in the spec that looks wrong or incomplete. Do not work around these in the plan.

## Rules

- The spec wins over your preferences. If you think it is wrong, say so under "Spec issues" and plan to the spec anyway unless the problem blocks the work.
- Tool names, flags and versions for 6.2 must be checked against current documentation (use web search), not memory. Record the source URL for each. If you cannot verify one, say so and list it as an open question instead of guessing.
- Restores run on the host with the user's privileges; this is an accepted, recorded risk (spec decision 5). Do not add sandboxing.
- Plain language for anything a user of the dossier will read.
- Do not invent facts about the code. If you did not read it, say so.
- When you finish, reply with: the path of the plan, the five most important risks, the questions the human must answer, and the exact one-line instruction to type to start Phase 1.
