# dossier developer guide

## Contents

- [Overview](#overview)
- [Getting started](#getting-started)
- [Repository layout](#repository-layout)
- [Architecture](#architecture)
- [How to make changes](#how-to-make-changes)
- [Testing](#testing)
- [Code conventions](#code-conventions)
- [Configuration and environment](#configuration-and-environment)
- [Build, release and deploy](#build-release-and-deploy)
- [Debugging and troubleshooting](#debugging-and-troubleshooting)
- [Gotchas](#gotchas)
- [LLM prompts](#llm-prompts)

## Overview

dossier is a Claude Code skill. A Python CLI (`scripts/dossier.py`) measures a git repository at one pinned commit, runs language tools over it and renders a single HTML page; Claude reads the code and writes the cards that need judgement. The standard library plus Pygments is all the CLI imports at run time; every other tool is started through `uv` or `npm` with pinned versions.

Stack: Python 3.10+ run by `uv`, tree-sitter, Semgrep, grimp, vulture and import-linter for Python, scip-python, dependency-cruiser, knip and scip-typescript for JS and TS, scip-dotnet for C#, Mermaid in the page. Linux and macOS. The page works in current Chromium, Firefox and Safari; the page check needs Playwright's Chromium.

What to build is decided in [plans/004-v1-spec.md](plans/004-v1-spec.md). How milestones are planned and reviewed is in [process.md](process.md). What waits until after 1.0.0 is in [post-v1.md](post-v1.md). The user-visible behaviour is in the [user guide](user-guide.md).

## Getting started

Prerequisites: `git`, `uv`, Node 22.13 or later (for the JS tests), and the .NET SDK (for the C# tests). Run `uv run scripts/dossier.py doctor --all` to see what is missing.

```sh
git clone git@github-1npo:1npo/encamp.git encamp
cd encamp/configs/user/claude/.claude/skills/dossier
uv run --with pytest --with pygments python -m pytest tests -q
```

Expected: no failures. On the M6 branch the result is **2889 passed, 304 skipped** in about 70 seconds (a fresh clone of the branch gave the same, give or take a skip that depends on the tools installed). The skips are the slow tests.

The slow tests run the real tools, need the network and a browser, and take about 45 minutes:

```sh
DOSSIER_SLOW=1 uv run --with pytest --with pygments python -m pytest tests -q --basetemp=$HOME/.cache/dossier-m6-slow
```

Always set `--basetemp` to a folder under your home: `/tmp` is small and the tools fill it. Three tests fail by design today and are not regressions: `test_overlapping_paragraphs_are_reported`, `test_each_browser_mutation_makes_a_fail[chart-text-small-chart text]` and the G2 golden in `test_golden02_slow.py`.

To try the skill, copy or link the folder to `~/.claude/skills/dossier` and type `/dossier doctor` in Claude Code, or run the CLI directly:

```sh
export DOSSIER_HOME=$HOME/.cache/dossier-try DOSSIER_CONFIG=$HOME/.cache/dossier-try/config.json DOSSIER_CACHE=$HOME/.cache/dossier-try/cache
uv run scripts/dossier.py doctor .
```

## Repository layout

The skill lives in `configs/user/claude/.claude/skills/dossier/` of the encamp repository; everything below is relative to it.

```
SKILL.md              what Claude reads when the user types /dossier: the steps of a build
VERSION               the version (one line)
README.md, docs/      user-facing docs; docs/plans/ holds plans and handoffs, docs/process.md the workflow
scripts/              the CLI and everything it imports (flat folder)
  dossier.py            the CLI: build_parser() and one cmd_* function per subcommand
  stages.py             the prepare stages: pin, tools, copy, measure, extract
  gather.py             measured facts about files, languages, git history
  adapters.py           the adapter interface, the extract stage, the path filter
  py_*.py cs_*.py js_*.py repo_adapter.py   one adapter per language group
  candidates.py         the tool findings each report must keep, merge or dismiss
  render.py, measured*.py   draws the page; measured*.py draw the cards code writes
  checks*.py, page_audit.py, check_layout.py, check_page.py   the checks
  graph_views.py        the views of the interactive graph cards
  verify.py             --verify sampling and recording
  sandbox.py            every child process goes through here
  tools.json            tool versions, scopes, minimum versions, install hints
  eol.json              the end-of-life snapshot
prompts/              method.md, reports.md, verify.md; schema/*.json is one card schema per report
rules/                Semgrep rules: python/, js/, csharp/, all/
assets/               dossier.css, dossier.js (the page)
vendor/               Mermaid and Basecoat, with their licences
tests/unit/scripts/   one test file per script, mirroring scripts/
tests/integration/    tests that run real tools (the *_slow.py files need DOSSIER_SLOW=1)
tests/fixtures/       small repositories and golden files; encamp-m0 is frozen and git-ignored
tests/tools/          page builders and probes used by tests (m3_page.py ... m6_page.py)
```

## Architecture

```
/dossier build
  prepare ──> build.json, facts.json, extract/*.json, a clean checkout of the pinned commit
     │
  Claude reads and writes reports/*.json (cards that code does not draw)
     │
  render ──> dossier-<repo>.html, summary.json     (V1 to V8, V10, V11 run here)
     │
  check ──> opens the page in a browser            (V12)
     │
  [--verify] verify-sample ──> subagents ──> verify-record ──> render
```

`build.json` records ten steps in order (`buildlog.STEPS`): `pin`, `tools`, `copy`, `measure`, `extract`, `read`, `write`, `check`, `gaps`, `render`. Only the scripts write it (`buildlog.WRITERS`); Claude never edits it.

**Adapters.** An adapter turns one language's code into the standard outputs: entry points, import graph, symbols, I/O candidates, models, tests, dead code and blind spots (`adapters.OUTPUTS`). The shipped adapters are `PythonAdapter`, `JsAdapter`, `CSharpAdapter` and `RepoAdapter` (Dockerfiles, compose files, CI), registered in `adapters._registered()`. An adapter's `version` is part of the extract cache key: change what it outputs and the version goes up by one. Every repository code run is under `sandbox.run` with the `restricted` profile and a scrubbed environment.

**Candidates and cards.** `candidates.py` lists every tool finding a report must account for. A report keeps, merges or dismisses each one; `dossier candidates --report ID --open` prints what is left. `candidates.FEEDS` says which extractor outputs feed which report, and `incremental.py` uses it to decide which reports a change makes stale.

**Cards and schema.** `prompts/schema/<report>.json` defines each report's cards: id, title, tier (`M`, `A`, `R`, `M+A`), shape (`blocks`, `flows`, `entries`, `computed`) and slots. [prompts/schema/README.md](../prompts/schema/README.md) describes the format. A report file written by Claude names card ids only.

**Measured cards.** Cards with tier `M` or shape `computed` are drawn by `measured*.py` from the extract files, never written by Claude. Report 02 (this repository) and its CSS and JS are frozen: see [Gotchas](#gotchas).

**Checks.**

| Check | What it asserts | Where |
|---|---|---|
| V1 | Every citation resolves | `render.py` |
| V2 | The cited code contains the span a claim quotes (warning) | `checks.py` |
| V3 | Every flow arrow has an import or a call behind it (warning) | `checks_v3.py` |
| V4, V5 | Every file is in a component; every tool finding has a decision; people and components are not left out | `checks.py`, `checks_people.py` |
| V6 | Each report matches its card schema | `schema.py` |
| V7 | Blind-spot hits are recorded in Gaps (never fails) | `checks_v7.py` |
| V8 | `summary.json` matches `prompts/summary.schema.json` | `summary_check.py` |
| V9 | The path filter kept only expected paths (info) | `process.py` |
| V10 | Every build step has a record, and a skipped or failed one says why; a verifier sample needs recorded results | `process.py` |
| V11 | The page draws every row, column and entry of its sources | `page_audit.py` |
| V12 | A browser: diagrams draw, text is readable, nothing overlaps, the viewer works | `check_page.py`, `check_layout.py` |

**Staleness.** `incremental.update_plan` compares the pinned commit with the last render and the skill's `major.minor` with the saved one. A new major or minor version plans a full rebuild.

**Interactive graphs.** `graph_views.py` computes every view in Python (at most 12 nodes and 30 links each, folding the rest into group nodes) and `measured_graph.py` writes them into the two graph cards as JSON. `assets/dossier.js` only switches between views. Because every view is computed, every view is checked by unit tests and by the browser check.

**Freshness.** `workarea.freshness` runs `git ls-remote` through `sandbox.run`, falls back to the remote-tracking branch, and `stage_pin` stores the result in the pin record of `build.json`. `render.py` draws it as the first tile of the `dossier.about` card.

## How to make changes

Every recipe starts with a failing test. Run it, see it fail, then make it pass.

**Add a Semgrep rule.**

1. Add the rule to `rules/<scope>/<family>.yml` with an id `dossier.<scope>.<family>.<name>` and `metadata.category` (see [rules/README.md](../rules/README.md) for the categories and blind-spot ids).
2. Add `ruleid:` and `ok:` lines to the test file of the same name under `tests/fixtures/semgrep/<scope>/`.
3. Run `DOSSIER_SLOW=1 uv run --with pytest --with pygments python -m pytest tests/integration/scripts/test_shared_layer.py -q`.
4. A new blind-spot id needs fixed wording in `checks_v7.BLIND_SPOTS`: the wording is part of Gaps item ids, so never reword it.
5. Bump the adapter's `version`.

**Add or change a card field.**

1. Edit `prompts/schema/<report>.json`. Run `tests/unit/scripts/test_schema*.py`.
2. For a card code draws, change the `measured*.py` function; for a written card, change `prompts/reports.md` and the example in `prompts/method.md` (`test_prompts.py` validates the examples against the schema).
3. If the card shows measured numbers, add the V11 count to `page_audit.py` and a mutation to `tests/tools/broken_pages.py`.
4. Run the report 02 guard if you touched `render.py`, `measured*.py`, `process.py`, `assets/dossier.css` or `assets/dossier.js`: render a fixed dossier before and after and compare the report 02 section byte for byte.

**Add an adapter.**

1. Write `scripts/<lang>_adapter.py` with a class that fills the standard outputs (copy the shape of `repo_adapter.py`, the smallest). Give it a `version`.
2. Register it in `adapters._registered()`.
3. Add its tools to `scripts/tools.json` with `scope`, `min` and `install` text, so `doctor` knows them.
4. Add a fixture repository under `tests/fixtures/` and a `test_<lang>_adapter_slow.py` under `tests/integration/scripts/`.
5. Mark the language Tier A in `toolcheck` only when it has an import graph; otherwise it stays Tier B and the cards badge it `no static graph`.

**Add a CLI subcommand or flag.**

1. Add it in `build_parser()` in `scripts/dossier.py` and a `cmd_*` function.
2. Name it in `docs/user-guide.md` and, if a user passes it, in `SKILL.md`'s `argument-hint`. `tests/unit/scripts/test_docs.py` fails until you do.

**Add a check with a mutation.**

1. Write the check as a pure function that returns error lines.
2. Add a broken page to `tests/tools/broken_pages.py` that the check must reject, and list the line it must produce. A check with no mutation is not accepted.

**Update the docs.** Any change to behaviour, options, setup or architecture updates `README.md`, `docs/user-guide.md` and this guide in the same change. `test_docs.py` catches the drift it can: a missing command or flag, and report names that no longer exist.

**Change the end-of-life snapshot.** Run `tests/tools/refresh_eol.py` as its docstring says and commit `scripts/eol.json`.

## Testing

- **Unit tests** (`tests/unit/scripts/test_*.py`) are fast, use `tmp_path`, and mirror the script they test. One class per unit, `Test<Unit>`, with methods named `test_<scenario>_<expected result>`. No test touches the network or the real home folder.
- **Integration tests** (`tests/integration/scripts/`) run real tools. Those named `*_slow.py` skip unless `DOSSIER_SLOW=1`.
- **Fixtures** are small made-up repositories (`pyrepo`, `jsrepo`, `csrepo`, `pylib`) and expected outputs. `encamp-m0` is a frozen, git-ignored copy; never write to it. Never commit code from a public repository.
- **Test pages.** `tests/tools/m3_page.py` to `m6_page.py` build large synthetic dossiers for the V11 and V12 checks. `python tests/tools/m6_page.py` prints the path of a rendered page.
- **Mutation tests.** `tests/tools/broken_pages.py` damages a good page in one way per check; the check must then fail with a known line. Run them through `test_check_page_slow.py`.
- **Ground truth.** `tests/tools/ground_truth.py` scores a dossier against a hand-made truth for a public repository.
- **Before you finish,** run the whole default suite and report the result.

To test the skill by hand, build a small repository: set the three `DOSSIER_*` variables to a scratch folder, run `prepare`, write or copy reports, then `render` and `check`.

## Code conventions

- Python 3.10+, `from __future__ import annotations`, standard library only in anything `dossier.py` imports (plus Pygments).
- Modules stay under about 300 lines; split by purpose, not by size alone.
- Every child process goes through `sandbox.run` or `ctx.run`. No shell strings.
- Nothing is dropped silently: no `[:N]` on data that feeds a card. A diagram view may hide links only through the stated filter, and says so on the page.
- Gaps and badge wording is fixed so item ids stay stable. Never reword it.
- Plain language in everything a dossier user reads. Measured values are never written by Claude.
- Commits are one task each, `type(dossier): subject`, made as Claude with the `Co-Authored-By` trailer; branch, merge and push follow the user's `git-workflow` skill.

## Configuration and environment

| Variable | Meaning |
|---|---|
| `DOSSIER_HOME` | Overrides the `home` config key. |
| `DOSSIER_CONFIG` | Path of the config file (default `~/.config/dossier/config.json`). |
| `DOSSIER_CACHE` | Overrides `cache_dir` (default `~/.local/cache/dossier`). |
| `DOSSIER_SLOW` | `1` runs the slow tests. |

The config keys are in the [user guide](user-guide.md#configuration). Commands that render or build set all three variables to a fresh folder under `~/.cache`, so a test run never touches your real dossiers. Secrets: dossier never prints a secret value; files that match secret patterns are never embedded in the page.

## Build, release and deploy

The version is the one line in `VERSION`. The skill has no bump tool and no CI. A release is: finish the work on a feature branch, set `VERSION`, run both suites, merge to `main` with `git merge --no-ff`, push `main`. Nobody tags by hand; add the release workflow from the `py-projects` template if the repository ever gets CI.

A new minor or major version makes `update_plan` rebuild every dossier in full the next time it is built. `summary.json` carries its own `schema_version`, which changes only when a field is added or removed.

To install a released version, the user copies the folder to `~/.claude/skills/dossier`. In the author's setup, `~/.claude/skills/dossier` points at a clone that `encamp-sync` updates.

## Debugging and troubleshooting

| Problem | Cause and fix |
|---|---|
| `uv` cannot find a Playwright browser | The browser build must match the Playwright version `uv` picked. Run `uv run --with playwright python -m playwright install chromium`. |
| Slow tests fill `/tmp` | Run with `--basetemp=$HOME/.cache/dossier-m6-slow` and delete the folder afterwards. |
| A build step looks wrong | Open `build.json` in the dossier folder: each step has a status, counts and details. |
| A card is empty | Look in `extract/*.json` for the adapter output, then `candidates --report ID`. |
| `render` refuses to write | Read the `V*` lines; fix the reports. `--allow-errors` is for debugging only. |
| The page differs from yesterday's | Compare `build.json` with `build.prev.json`; the skill's commit is on the process card. |
| A page check fails in one theme only | Open `.check-shots/` in the dossier folder: it keeps screenshots from the last check (one per diagram, and others by page). |

Useful commands: `dossier doctor <repo> --json`, `dossier candidates <repo> --report ID --json`, `dossier migrate <repo> --dry-run`, `python tests/tools/graph_probe.py PAGE.html` (drives one graph in a browser and prints what happened).

## Gotchas

- **Report 02 is frozen.** Its panels, CSS and JS keep the layout of the pre-0.5 skill, and no file in `prompts/schema/*.json` changes casually. After any edit to `render.py`, `measured*.py`, `process.py`, `assets/dossier.css` or `assets/dossier.js`, check that report 02 is byte for byte the same.
- **`~/.claude/skills/dossier` may be a clone.** Never edit the installed copy; edit the development copy and sync.
- **`/tmp` is small.** Put every scratch folder under `~/.cache`.
- **Name clashes.** Two Python projects in one repository may each have a package with the same name. Graph items keep their paths, so the graphs are right; name-based checks (V2, V3) may match the wrong one.
- **Rule ids are in Gaps item ids.** Renaming a rule or rewording its Gaps statement changes every saved decision's id.
- **The barrel rule** (`from x import *` in an `__init__.py`) is a regex over every file; `py_adapter` keeps only the hits in `__init__.py`.
- **A verifier verdict is keyed by claim.** If a report's wording of a claim without an `id` changes, a saved verdict stops matching and its Gaps item disappears at the next render.
- **Freshness ages.** It is computed at `prepare`, not at render.

## LLM prompts

Each prompt assumes a fresh session in `configs/user/claude/.claude/skills/dossier`. Replace the part in angle brackets.

**A failing test or build.**

> Read `docs/developer-guide.md` (Testing and Gotchas) and the failing test. Run only that test file with `uv run --with pytest --with pygments python -m pytest <file> -q`. Find the cause before changing anything. Fix the code, not the test, unless the test is wrong, and say which. Run the whole default suite at the end and report the counts.

**Add a feature in the project's style.**

> Read `docs/developer-guide.md` (Architecture, How to make changes, Code conventions) and the recipe that fits. Write a failing test first and show it failing. Make the smallest change that passes. If the change alters output, bump the adapter's `version` and say what changed before and after. Update `docs/user-guide.md` and this guide if behaviour changed. Commit once per task.

**Review a change.**

> Read `docs/developer-guide.md` (Code conventions and Gotchas) and the diff of `<branch>` against `main`. Check: tests first, no data dropped silently, fixed wording not reworded, every child process through `sandbox.run`, report 02 untouched, docs updated. List findings by severity with file and line.

**Update the docs after a change.**

> Read the diff of `<branch>` and `docs/user-guide.md`, `docs/developer-guide.md` and `README.md`. List every user-visible or workflow change the diff makes, update the docs for each, and run `tests/unit/scripts/test_docs.py`. Run any command you document.

**Investigate a bug in a dossier.**

> Read `docs/developer-guide.md` (Debugging and troubleshooting). For the dossier at `<folder>`, open `build.json`, then the `extract/*.json` file for the adapter involved. Say which stage produced the wrong value before proposing a fix. Reproduce it in a test on a small fixture.
