# Plan 007: milestone M2 (the Python vertical slice: extractors, reports 03 to 09, 11 and 12, V2 to V5 and V7)

Status: written by Opus on 2026-11-01. **Reviewed and approved by the human on 2026-11-01:** every question in section 7 is answered (all with the plan's defaults) and every spec issue in section 8 is settled; the spec was amended to match (`004-v1-spec.md` principle 2, the home-card table in 6.1, and section 12, items 8 to 25). Phase 1 can start. It was written from `plans/004-v1-spec.md`, `docs/process.md`, `plans/006-m1-plan.md` (including its results and deviations), `plans/005-m0-plan.md` for the card schemas, and the code at commit `dcd36f6` (version 0.6.0, M1 merged). Writing the plan changed no other file; the spec amendments were made afterwards, at the review.

Paths used below:

- `SKILL` = `/home/nick/dev/projects/encamp/configs/user/claude/.claude/skills/dossier`. The planning prompt gave `~/encamp/...`, which does not exist on this machine.
- `FIX` = `SKILL/tests/fixtures/encamp-m0`: the frozen, git-ignored M0 fixture. It is read-only. Never write into it.
- `PYFIX` = `SKILL/tests/fixtures/pyrepo/`: the new Python fixture repository (M2-3). It is committed, as plain files, and becomes a git repository only in a temporary folder at test time.
- `REPO` = `/home/nick/dev/projects/cannalerts`: the real Python repository for the exit criterion, as in M1. It has a `src/` layout (`src/cannalerts/`, 106 tracked `.py` files), `pyproject.toml` with `[project.scripts] cannalerts = "cannalerts.cli:main"`, hatchling, `uv.lock`, ruff and pytest configuration, and tests under `tests/`.
- Tests run from `SKILL`: `uv run --with pytest --with pygments python -m pytest tests -q`. **Baseline before M2: 405 passed, 2 skipped** (M1 result; re-check in the first step of Phase 1).
- Slow tests (they need the network and the real tools) run only with `DOSSIER_SLOW=1`.

---

## 1. Summary

- A Python adapter (grimp, vulture, scip-python, tree-sitter queries and the Python semgrep rules) and a repository-wide adapter (Dockerfiles, Makefiles, CI files, systemd units, shebang scripts, SQL) fill all eight `extract/*.json` outputs, with stable candidate ids, proven on a fixture repository.
- Reports 03 to 09, 11 and 12 are written from those outputs: the five measured cards are drawn by code, and every adjudicated card records a disposition for each candidate (kept, merged or dismissed with a reason). `render` checks V2, V3, V4, V5 and V7, puts their findings in Gaps, badges cards "partial" when a tool was missing, and `prepare` marks a report stale when its tool findings changed.
- The prompts and SKILL.md are rewritten so `/dossier build` works again for Python repositories. Reports 10 and 13 stay for M3. `VERSION` goes to 0.7.0.
- Phases: **1** framework, both adapters, rules and fixtures; **2** card data, measured cards, V4, V5, "partial", staleness; **3** V2, V3, V7, prompts, SKILL.md, version, end-to-end run.

---

## 2. Shared rules (every phase reads this first)

- **Branch.** All three phases work on one branch, `feat/dossier-m2`, created from `main` in Phase 1 and merged at the end of Phase 3. One commit per task. Follow the `git-commit` skill (identity, message style) and the `git-workflow` skill (branching, merging, pushing). Commit messages below are suggestions in the style of the M1 commits.
- **Skills to load at the start of every phase:** `git-commit`, `git-workflow`, `py-projects`, `py-unit-tests`, `claude-planning-docs` (for writing results back into this plan). Phase 3 also loads `docs-project`, `docs-readme` and `git-release`.
- **Never touch:** report 02 (the `overview` report: `panel_git`, `panel_contributors`, `panel_dependencies`, the knowledge map, the calendar, their CSS and JS). **Report 02 and the M0 card schemas in `prompts/schema/*.json` (ids, titles, tiers, shapes, slots, columns, fixed rows) do not change in M2.** The plan never edits a schema file. It edits `scripts/schema.py` (the validator) in two places only (M2-14, M2-25). `FIX` is never written. `tests/fixtures/encamp-m0/` stays.
- **Never read or write `/home/nick/dev/dossiers/`.** Every command that builds, renders or runs `prepare` sets `DOSSIER_HOME`, `DOSSIER_CONFIG` and `DOSSIER_CACHE` to a scratch directory (`mktemp -d`, or `tmp_path` in tests). Never build a dossier of a real repository except in section 6.
- **No sandboxing.** Restores and Node tools run on the host with the user's privileges (spec decision 5). No containers, namespaces or `unshare`. **Every child process goes through `sandbox.run`**, directly or through `ctx.run`. Never call `subprocess` for a tool or for repository code. (Plain `git` calls on the checkout, as `workarea.py` and `stages.py` already make, are the one exception.)
- **No new runtime dependencies** in `scripts/dossier.py` or any module it imports (standard library plus `pygments`). Tools with Python dependencies run as locked worker scripts (PEP 723 header, `uv lock --script`, run with `uv run --locked --python 3.13 --script`), as M1 did. Node tools run from a committed `package-lock.json` (D1).
- **Tests.** Follow `py-unit-tests`. Unit tests go in `tests/unit/scripts/test_<module>.py`; tests that start real processes go in `tests/integration/scripts/`. Tests that need the network or a real tool are marked `@pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")`. **The full suite must pass after every task.** Slow tests must pass at the end of each phase.
- **Plain language** in everything a dossier user reads: CLI messages, card text, Gaps statements, badge tips. Full sentences, no jargon where a plain word works. Gaps statements use fixed wording (given in this plan) so their IDs stay stable across builds.
- **If the code contradicts this plan, stop and report.** Do not improvise a design. Record what you found under that phase's "Results".
- **Report 02 guard.** After every task that edits `scripts/render.py`, run section 6 block E. It must print `OK`.
- **Size.** Keep every new module under about 300 lines. If one grows past that, split it along the lines this plan names and say so in "Results".
- **Ticking.** Tick each task's checkbox in this file in the same commit as the task.

---

## 3. Spec versus code

"Absorb" = the plan handles it as proposed. "Decision" = the human had to answer first (section 7 lists the questions and, since the review on 2026-11-01, the answers). Every "Decision" row below was answered with the plan's default.

| # | Area | Spec says | Code does today (0.6.0) | Proposal | Class |
|---|---|---|---|---|---|
| 1 | Adapter outputs | 6.1: eight outputs per language adapter: `entry_points`, `graph`, `symbols`, `io_candidates`, `models`, `tests`, `dead`, `blindspots` | `adapters.OUTPUTS` has the eight names; `ADAPTERS = ()`; an adapter returns `{output: [items]}`, every item needs `path` (D7 of plan 006). | Python fills all eight (D2): `graph` from grimp (packages) and tree-sitter imports (loose modules); `symbols` from scip-python; `io_candidates`, `blindspots` and most `entry_points` from semgrep; `models`, `tests` and module-level state from tree-sitter queries; `dead` from vulture. Nothing is left empty for Python. Hotspots, co-change and blast radius stay in M3 (`gather.py`). | Absorb |
| 2 | Language-independent entry points | 6.1 lists for `entry_points`: CI and cron, container `CMD`/`ENTRYPOINT`, Makefile targets, systemd units, shebang scripts. 6.1 also says "one adapter class per language" | None of these are extracted. `detect()` matches adapters by language name only. | A second adapter, `repo` (D1), handles the files that belong to no language. It declares `languages = ("*",)` and `detect()` treats `"*"` as "always". It also finds SQL `CREATE TABLE` statements (for `models`) and CI test commands (for `tests`). | **Decision** (Q7) |
| 3 | How the Python tools run | 6.2: Python tools through `uv` with a pinned interpreter; scip-python through `npx`, needs Node | M1 runs tree-sitter and semgrep as locked worker scripts through `sandbox.run(profile="tool")`, cwd = the checkout, timeout = `timeouts.extract` bound into `ctx.run`. | grimp and vulture share one new locked worker, `py_worker.py` (they need no restore: grimp parses source, vulture uses `ast`). scip-python is **not** run with bare `npx` (its transitive npm packages would float, against 5.4 rule 7). It is installed once with `npm ci --ignore-scripts` from a committed lockfile into the shared tool cache (D1), then run with `node` under the `restricted` profile. The ref must be trusted (5.4 rule 4 covers every Node extractor): without a trusted ref or `--allow-ref`, scip-python is skipped and the rest of the adapter still runs. Every tool call passes `timeout=config.timeouts()["tool"]`. | **Decision** (Q6) |
| 4 | What restore must have produced | scip-python "wants an installed environment"; grimp "needs an importable package" | `uv sync --frozen` puts `.venv/` in the checkout when the restore ran (`ctx.restored["python"] is True`). | grimp needs only the folders that hold the packages on `sys.path` (no install), so it never depends on the restore. scip-python works without installed packages (references into libraries are then unresolved). When `.venv` exists it gets an environment file listing the installed packages (D1), because a uv virtual environment has no `pip` for scip-python to ask. vulture never needs it. | Absorb |
| 5 | grimp's cache | M1 spec issue 13: grimp writes `.grimp_cache` into the current folder | `ALWAYS_EXPECTED_SEG` already lists `.grimp_cache` for the path filter. | `py_worker.py` always calls `grimp.build_graph(..., cache_dir=None)` (verified: "Pass `None` to disable caching"). A test asserts that no `.grimp_cache` folder exists in the checkout after extraction, and `run_extract`'s clean-tree check already fails the step if a tracked file changes. | Absorb |
| 6 | The reuse key | 5.3: outputs keyed by `(sha, extractor version)` | M1 keys each adapter's section by `sha`, adapter `version` and the versions of every tool in `adapter.tools` (M1 spec issue 24). | One adapter version covers all its tools; the key already has every tool's version. M2 adds one rule: a section whose `tool_status` shows a failed or skipped tool is never reused (otherwise a build with node missing would be reused after node is installed). `tool_status` is stored in every section. | Absorb |
| 7 | Candidate ids | 2.2: every candidate gets a recorded disposition; a candidate with no disposition fails the build | Items have no ids. | `run_extract` gives every item of `entry_points`, `io_candidates`, `models`, `dead` and `blindspots` an `id` and a `group` after the path filter (D2). Ids hash the rule, the path, the matched text and the occurrence number, not the line, so they survive line shifts elsewhere in a file. | Absorb |
| 8 | How a report cites extractor output | V1 today: `[[path:a-b]]`, `commit:`, `facts:`; nothing refers to extractor records | `render.parse_cite` knows three kinds. | No new citation kind. A statement still cites the **code** (`path:line`), which V1 checks and the code viewer opens. The link to the extractor record is the disposition (`cand`, D3), which V5 checks. V2 checks identifiers against the cited code, not against extractor records. | Absorb |
| 9 | Where dispositions live in the card JSON | 8 shows table rows as `cells` plus `conf`/`cite`/`note`; nothing for dispositions | `schema.ENTRY_KEYS = {card, title, blocks, entries, na, cite, pending}`; row keys are not restricted. | Row key `cand` (list of candidate or group ids) and `added` (true when Claude found it and no tool did); card-entry key `dismissed` (list of `{cand, reason}`); `components.catalog` entry key `unassigned` (V4). `ENTRY_KEYS` gains `dismissed` and `unassigned` (a validator change, not a schema-file change). | Absorb |
| 10 | Volume of candidates | Principle 7: no caps. Principle 2: every candidate dispositioned | — | A disposition may name a **group** id (all hits of one rule in one file) instead of each hit. That bounds the work by rules times files, not by call sites (a repository with 2,000 log calls in 80 files needs at most 80 dispositions for them). | **Decision** (Q2) |
| 11 | Which lists need dispositions | 2.2 says "every extracted list" | — | V5 covers `entry_points`, `io_candidates` and the entity items of `models`. Not covered: `graph`, `symbols`, `tests` (they are measurements, drawn or given as data), `dead` (drawn by code in M3's `change.dead-code`), `blindspots` (go to Gaps, V7), migrations in `models` (data, not entities), and the glossary and reading-order hints (computed suggestions). | **Decision** (Q3, spec issue 4) |
| 12 | Which card owns each candidate | Several cards name the same sources: `io.outputs` has "logs" and "metrics" rows, `behavior.observability` lists logging and metrics; HTTP routes appear in `entry.catalog` and `io.inputs` | — | Every candidate has exactly one **home card** (D3 table), where it must be dispositioned. A disposition on any card in reports 03 to 12 also counts (so a route can be kept in `io.inputs` too), but the home card is where `dossier candidates` shows it. | **Decision** (Q3) |
| 13 | The measured cards in 03 to 12 | `reading.map`, `interactions.graph`, `interactions.violations`, `conventions.tooling` are tier M; `components.map` is M+A with a computed layout | All five have `writer: script`; `render_card` draws `placeholder_body` for every script card. | New module `measured.py` draws them (D8) from `extract/` and `facts.json`. `build_page` asks it for a body before falling back to the placeholder. | Absorb |
| 14 | `components.map` and `interactions.graph` are "interactive" | 4 (05, 06): interactive hierarchical graph, groups collapse and expand; edges weighted by import count | The page has interactive graphs only in report 02 (`dossier.js`, not read for this plan). | M2 draws, for both, a component-level Mermaid flowchart (subgraph per area, arrow per component dependency, label = import count) plus a sortable, filterable edge table at module level. Every module and edge is in the table, so nothing is dropped (principle 7). Collapsible interactive graphs move to M6 (page polish). | **Decision** (Q1, spec issue 1) |
| 15 | The component model | 05: candidates from package and folder boundaries plus import-graph community detection; Claude names, merges, splits; V4: every tracked, non-excluded source file belongs to exactly one component or appears in an explicit unassigned list | Nothing. | D4. Candidates are computed (folders, packages, label-propagation communities) and shown by `dossier candidates --report components`. Claude writes `components.catalog` with a `Paths` cell per row. V4 matches every tracked source file against the `Paths` patterns; the most specific pattern wins. | **Decision** (Q5, spec issue 3) |
| 16 | V2 | Identifiers in backticks in a cited statement appear in the cited range; warning, counted in Gaps | `render.validate` already warns when a backticked **path** is not cited. Nothing checks identifiers. | `checks.v2` (D9). | Absorb |
| 17 | V3 | Every arrow in a flow diagram corresponds to a graph or call edge; warning, arrow marked `inferred` | Mermaid source is checked only for its first keyword. | `checks.v3` (D9) parses `sequenceDiagram` messages and `flowchart` edges in `entry.startup` and `interactions.flows`, maps participants to modules, and checks each arrow against grimp import edges and scip reference edges. Mermaid cannot style one message of a sequence diagram, so an unbacked arrow is listed under the diagram ("Arrows with no import or call behind them: …") and becomes a Gaps `inference` item. | **Decision** (Q4, spec issue 2) |
| 18 | V4, V5 failure levels | V4 error if unaccounted (an unassigned list is allowed); V5 error | `cmd_render` blocks on `render.validate` errors and on V10, unless `--allow-errors`. | `checks.validate(...)` returns errors, warnings and Gaps items; `cmd_render` blocks on its errors like the others. "Unexpected" for V4 = a file matched by no row and not unassigned, or matched equally by two rows of different components. For V5 = a candidate with no disposition, an unknown id, a candidate both kept and dismissed, or a dismissal without a reason. | Absorb |
| 19 | Gaps receives V4, V5, V7 items | 4 (14/15): every unassigned file, every undispositioned candidate, every blind-spot hit | `render.collect_gaps(reports, extra)` takes the M1 coverage items. `cmd_confirm` builds the same list. | `checks.gap_items(...)` returns the new items; `cmd_render` and `cmd_confirm` pass `process.coverage_items(build) + checks items` as `extra`, in that order, so IDs match. Undispositioned candidates only reach the page under `--allow-errors` (V5 is an error), which the spec allows (spec issue 13). | Absorb |
| 20 | V7 | Blind-spot hits recorded in Gaps, automatic | Nothing. | One Gaps `coverage` item per blind-spot group (pattern, file), with a citation to the first hit's lines (D9). | Absorb |
| 21 | "Partial" badge | 5.1 step 1: with `--allow-missing`, the affected cards are badged "partial"; M1 spec issue 8 needs a tool-to-card map | No map, no badge. | Each tool in `tools.json` gains `"cards"`; a card is partial when one of its tools was missing, failed or skipped in this build (D7). | Absorb |
| 22 | Staleness from extractor output | 5.3: a report is stale if a cited file changed, or if its extractor output changed | `incremental.plan` uses citations, diffs, corrections. | `render` stores a digest per report of the tool findings it was built from (`state["extract_digests"]`); `prepare` recomputes them after the extract stage, and `update_plan` adds the reason "the tool findings it is built from changed" (D10). | Absorb |
| 23 | Reports 10 and 13 in M2 | M2 content: 03 to 09, 11, 12; 10 and 13 are M3 | `render.validate` errors when any authored report file is missing, unless `--partial`. `schema.ALLOW_PENDING = True`. | `render.OPTIONAL_REPORTS = ("change", "contributors")` in M2: missing is a warning. Claude does not write them. M3 empties the tuple. `schema.ALLOW_PENDING` becomes `False` (every card of the reports Claude writes must be filled). | **Decision** (Q8) |
| 24 | The old 12-report prompts | `prompts/method.md` and `prompts/reports.md` describe the retired reports; SKILL.md says "cannot yet write the new report layout" | as described | Rewritten (D11, M2-25 to M2-27). Reports 01, 02 (`overview.json` keeps only `headline`, `summary`, `update_note`), 14, 15 and 16 keep their current content. | Absorb |
| 25 | Block C's `"problems": 0` | M1 block C failed with "code viewer: no citation in the page can open it" because the build had no reports | `check_page.py` unchanged. | Section 6 runs the browser check on a build with reports, so citations exist. If it still fails, that is a finding, not something to work around. | Absorb |
| 26 | V10 on old dossiers | M1 risk 5: every dossier without `build.json` fails V10 | as described | Block E keeps `--allow-errors`. From M2-25, `FIX` (migrated, all cards `pending`) also fails V6 because pending is no longer allowed; block E's expectation becomes "only V6 pending errors and the one V10 error", and its digest check is unchanged. | Absorb |
| 27 | Report writing order and chunking | 4 (05): one subagent per group of components | `method.md`: chunk notes, then reports, subagents per report for large repositories. | D11: the order is 04, 05, 06, 07, 08, 09, 11, 12, then 03, risks, gaps. Chunk notes stay. Each report subagent gets the output of `dossier candidates --report <id>`. `components.detail` is split into one subagent per area for more than 12 components. | Absorb |
| 28 | Tool versions | M1 D1: re-check at the start of the milestone that first runs each tool | Pins in `tools.json`: grimp 3.17, vulture 2.16, scip-python 0.6.6, semgrep 1.181.0, tree-sitter-language-pack 1.22.1, import-linter 2.15 (read only). | Re-checked on 2026-11-01 (D1 table): all pins still hold under the 14-day rule. M2-1 re-checks the behaviour on the fixture. | Absorb |
| 29 | Import-linter "read only" | 6.2: declared layer rules, parsed from the repository's config | Not read. | `py_packages.py` reads `.importlinter`, `setup.cfg` and `pyproject.toml` (all three verified). The worker evaluates `layers` and `forbidden` contracts with grimp's own API. `independence`, `protected`, `acyclic_siblings` and custom types are listed as "not checked by dossier" in `interactions.violations`. import-linter itself is never run. | Absorb (spec issue 15) |
| 30 | The process card | Step 8 says "every tool-found item is accounted for, diagrams match real dependencies" | `process.run_line("check")` counts citations and layout errors only. | The `check` record gains V2 to V5 counts and the line says them (M2-21). | Absorb |

---

## 4. Decisions

### D1. Modules, tools and how each tool runs

New and changed modules (each under about 300 lines):

| File | Owns |
|---|---|
| `scripts/candidates.py` (new) | Ids and groups, the category-to-card map, loading `extract/*.json`, what each report is fed, report digests, the `dossier candidates` text. |
| `scripts/py_packages.py` (new) | Pure parsing of Python project layout: package roots, console scripts, import-linter contracts, `[tool.vulture]`, test and coverage configuration. Standard library only (`tomllib`, `configparser`). |
| `scripts/py_worker.py`, `scripts/py_worker.py.lock` (new) | Locked worker with `grimp==3.17` and `vulture==2.16`. Two modes: `graph` and `dead`. |
| `scripts/py_tools.py` (new) | Clients for `py_worker.py` (`Grimp`, `Vulture`), in the style of `shared_tools.py`. |
| `scripts/py_queries.py` (new) | The tree-sitter queries for Python and the code that turns their matches into `models`, `tests`, module-level state and import items. |
| `scripts/scip_tool.py` (new) | Installing scip-python into the shared tool cache, writing the environment file, running it. |
| `scripts/scip_read.py` (new) | A standard-library decoder for the SCIP protobuf file, and the reduction to definitions and file-to-file reference edges. |
| `scripts/node/scip-python/package.json`, `package-lock.json` (new) | The pinned scip-python install. |
| `scripts/py_adapter.py` (new) | `PythonAdapter`: runs the tools above in order, records each tool's status, returns the eight outputs. |
| `scripts/repo_adapter.py` (new) | `RepoAdapter`: language-independent entry points, SQL tables, CI test commands, the `rules/all/` scan. |
| `scripts/graphs.py` (new) | Standard-library graph helpers: strongly connected components (cycles), PageRank, label-propagation communities, aggregation to components. |
| `scripts/measured.py` (new) | Bodies of the five measured cards in reports 03 to 12. |
| `scripts/checks.py` (new) | V2, V3, V4, V5, V7 and their Gaps items. |
| `rules/python/*.yml`, `rules/all/*.yml` (new) | Semgrep rules (D5). |
| `tests/fixtures/semgrep/python/*.py`, `tests/fixtures/semgrep/all/*` (new) | Semgrep rule tests (D5). |
| `tests/fixtures/pyrepo/` (new) | The fixture repository (M2-3). |
| `scripts/adapters.py` | `detect` accepts `"*"`; `Context` gains `trusted`, `repo_name`, `tool_status`; `run_extract` assigns ids, stores `tool_status`, refuses to reuse a section with a failed tool, registers the two adapters. |
| `scripts/semgrep_worker.py` | Returns metavariables; gains a `test` mode. Its lock is unchanged (same dependency). |
| `scripts/sandbox.py` | Profile `tool` sets `npm_config_cache` to the shared tool cache (D12 of plan 006 extended). |
| `scripts/tools.json` | `"cards"` per tool; `"node_lock"` for scip-python. |
| `scripts/render.py` | `build_page` asks `measured` for script cards; `schema_card` takes a partial reason; table rows show "added by Claude"; adjudicated cards get a candidate footer; `render_html` takes `extract`, `partial`, `checks`; `OPTIONAL_REPORTS`. |
| `scripts/schema.py` | `ENTRY_KEYS` gains `dismissed`, `unassigned`; `ALLOW_PENDING = False`. |
| `scripts/dossier.py` | `candidates` command; `cmd_render` and `cmd_confirm` call `checks`; `update_plan` gets digests. |
| `scripts/process.py` | The `check` run line counts V2 to V5. |

**How each tool runs** (cwd is always the checkout, through `ctx.run`; `T = config.timeouts()["tool"]`):

| Tool | Command | Profile | Output | Needs |
|---|---|---|---|---|
| grimp | `uv run --locked --python 3.13 --script scripts/py_worker.py`, stdin `{"mode": "graph", "roots": ["src"], "packages": ["cannalerts"], "contracts": [...]}` | `tool` | JSON on stdout (D2 `graph` items, before ids) | Nothing installed. The worker puts each root (absolute path inside the checkout) first on `sys.path` and calls `grimp.build_graph(*packages, include_external_packages=False, exclude_type_checking_imports=False, cache_dir=None)`. |
| vulture | same worker, stdin `{"mode": "dead", "paths": [...py files], "ignore_names": [...], "ignore_decorators": [...], "min_confidence": 60}` | `tool` | JSON on stdout | Nothing. Uses the Python API `vulture.Vulture(...)`, `.scavenge(paths)`, `.get_unused_code(min_confidence=...)`. |
| tree-sitter | `ctx.treesitter.query("python", paths, query)` (M1) | `tool` | matches | Nothing. |
| semgrep | `ctx.semgrep.scan(SKILL/rules/python, None, timeout=30)` and `scan(SKILL/rules/all, ...)` | `tool` | results with metavariables | Nothing. |
| scip-python | install once: copy `scripts/node/scip-python/{package.json,package-lock.json}` to `<cache root>/.dossier-tools/node/scip-python-0.6.6/` and run `npm ci --ignore-scripts --no-audit --no-fund` there (profile `tool`, cwd that folder). Run: `node <that folder>/node_modules/@sourcegraph/scip-python/index.js index . --project-name <repo_name> --project-version <sha> --output <area>/scip/index.scip --quiet --environment <area>/scip/env.json` | install `tool`; run `restricted` | `<area>/scip/index.scip` (outside the checkout, so no untracked file) | Node (host). A trusted ref or `--allow-ref`. The environment file lists the packages in `<checkout>/.venv` (from each `*.dist-info/RECORD`: name, version, files) when the restore ran, else `[]`. |

The scip-python flags were read from `packages/pyright-scip/src/MainCommand.ts` at tag `v0.6.6`: `--project-name` (default empty), `--project-version` (default: the git revision), `--cwd`, `--target-only`, `--output` (default `index.scip`, relative to `--cwd`), `--quiet`, `--environment` ("the environment json file (experimental)"), `--dev`, `--project-namespace`, `--show-progress-rate-limit`. The npm package's bin is `index.js` (registry metadata for 0.6.8; assumed the same for 0.6.6, checked in M2-1).

**Verified tool facts (2026-11-01).** The pin rule from plan 006 (newest stable release at least 14 days old) still gives the same pins.

| Tool | Pin | Latest (date) | What was checked | Source |
|---|---|---|---|---|
| grimp | 3.17 (2026-09-04) | 3.18 (2026-10-26, too new) | `build_graph(package_name, *additional_package_names, include_external_packages=False, exclude_type_checking_imports=False, cache_dir=...)`, `cache_dir` default `.grimp_cache`, `None` disables; `graph.modules`; `get_import_details(importer, imported)` → list of `{'line_number', 'line_contents', 'is_lazy'}` (may be empty); `find_matching_direct_imports`; `find_illegal_dependencies_for_layers(layers, containers=None)` → set of `PackageDependency`, "results are not fully deterministic"; `chain_exists`, `find_shortest_chains`. No method lists all cycles (the plan computes them). Python ≥3.10. **Not stated:** how the package must be importable (the plan puts the root on `sys.path`; M2-1 checks it). | https://grimp.readthedocs.io/en/stable/usage.html, https://pypi.org/pypi/grimp/json |
| vulture | 2.16 (2026-03-25) | 2.16 | Text output `file:line: message (N% confidence)`; exit 0 none, 1 bad input, 2 bad arguments, 3 dead code; confidence 100 for unreachable code and unused arguments, 90 imports, 60 the rest; `[tool.vulture]` keys `exclude`, `ignore_decorators`, `ignore_names`, `min_confidence`, `paths`; Python API `Vulture()`, `scavenge`, `get_unused_code()` → `Item` objects. **Not stated:** `Item` attribute names and the `Vulture(...)` constructor arguments (M2-1 checks them). No JSON output. | https://github.com/jendrikseipp/vulture |
| scip-python | 0.6.6 (2025-09-05) | 0.6.8 (2026-10-22, too new) | Node 16 or newer; Python 3.10+; flags above; by default "uses `pip` to … determine the versions and names of the packages"; `--environment` skips pip and takes a list of `{name, version, files}`. No `engines` in the npm metadata. | https://github.com/sourcegraph/scip-python, `MainCommand.ts` at v0.6.6, https://registry.npmjs.org/@sourcegraph/scip-python |
| SCIP format | — | — | `Index{metadata=1, documents=2, external_symbols=3}`; `Document{relative_path=1, occurrences=2, symbols=3, language=4}`; `Occurrence{range=1 (repeated int32, zero-based, 3 or 4 elements), symbol=2, symbol_roles=3, enclosing_range=7, single_line_range=8, multi_line_range=9}`; roles `Definition=1, Import=2, WriteAccess=4, ReadAccess=8`; `SymbolInformation{symbol=1, relationships=4, kind=5, display_name=6, enclosing_symbol=8}`. Read from the current `scip.proto`; scip-python 0.6.6 predates the typed ranges (8, 9), so the decoder reads field 1 and also accepts 8/9. | https://github.com/sourcegraph/scip/blob/main/scip.proto |
| semgrep | 1.181.0 (2026-10-14) | 1.183.0 | Unchanged from M1. Rule tests: `semgrep --test --config <rules dir> <targets dir>`, annotations `# ruleid: <id>` and `# ok: <id>` on the line before; targets mirror the rules' folder structure and share the rule file's name with the language's extension. | https://docs.semgrep.dev/writing-rules/testing-rules |
| import-linter | 2.15 (2026-09-04), read only | 2.15 | Config in `setup.cfg`, `.importlinter` (INI: `[importlinter]` `root_package`/`root_packages`, `[importlinter:contract:<id>]` with `name`, `type`, …) or `pyproject.toml` (`[tool.importlinter]`, `[[tool.importlinter.contracts]]` with `name`, `type`, optional `id`); layers: `layers` (highest first; `a | b` independent, `a : b` may import each other, `(x)` optional), `containers`, `ignore_imports`, `exhaustive`; forbidden: `source_modules`, `forbidden_modules`. | https://import-linter.readthedocs.io/en/stable/get_started/configure/, `.../contract_types/layers/` |
| tree-sitter-language-pack | 1.22.1 (2026-10-12) | 1.22.1 | Unchanged from M1 (its API was checked in M1-9). | M1 |

**SCIP decoding.** `scip_read.py` decodes the protobuf wire format with the standard library (varints, length-delimited fields, packed `int32`), reading only the fields above. **Rejected:** (a) the `protobuf` package with a generated `scip_pb2.py`: it adds a pinned runtime dependency whose generated code must match the runtime version, for a dozen fields; (b) Sourcegraph's `scip` CLI (`scip print --json`): a Go binary that neither `uv` nor `npm` installs, so the host would need another prerequisite.

**Rejected for scip-python:** `npx --yes @sourcegraph/scip-python@0.6.6`: the package is pinned but its dependencies are not, which breaks 5.4 rule 7. **Rejected for grimp/vulture:** one worker per tool (two environments to download, for no isolation gain: a failure in one mode does not affect the other call).

### D2. The `extract/*.json` items

The file layout is M1's: `{"schema": 1, "sha", "adapters": {"<name>": {"sha", "version", "tools", "tool_status", "items": [...]}}}`. New: `tool_status = {"<tool id>": {"status": "ok"|"failed"|"skipped", "reason": str|null}}`.

**Ids** (assigned by `run_extract` after the path filter, `candidates.assign_ids(output, items)`), for the outputs in `candidates.ID_OUTPUTS = {"entry_points": "ep", "io_candidates": "io", "models": "md", "dead": "dd", "blindspots": "bs"}`:

- `key = f"{item['rule']}\0{item['path']}\0{norm(item['snippet'])}"`, where `norm` collapses runs of whitespace to one space and strips. Items without a `rule` use `item["kind"]` as the rule. Items without a `snippet` use `item.get("name", "")`.
- Within one output, items with the same key are numbered 0, 1, 2 in `(path, line)` order: `n`.
- `id = prefix + "-" + sha1(f"{key}\0{n}").hexdigest()[:8]`; `group = prefix + "g-" + sha1(f"{rule}\0{path}").hexdigest()[:8]`.
- Ids are stable when lines move and when unrelated code changes. They change when the matched code changes, which also makes the citing report stale.

Every item has `path` (repository-relative, filtered) and, where it points at code, `line` and `end_line` (1-based). Item shapes per output (fields not listed are not written):

| Output | Item | Fields |
|---|---|---|
| `entry_points` | one per entry point | `id`, `group`, `path`, `line`, `end_line`, `kind` (one of `console-script`, `main-module`, `main-guard`, `cli-command`, `http-route`, `queue-consumer`, `scheduled-job`, `container`, `ci-schedule`, `make-target`, `shebang-script`, `systemd-unit`), `name`, `trigger` (plain words, for example "the `cannalerts` command"), `target` (where execution starts: `module:function`, a file, or the command), `rule`, `snippet` |
| `graph` | `kind: "module"` | `path`, `module` (dotted name), `package` (top package, or `null` for a loose module), `is_package` |
| | `kind: "import"` | `path` (importer file), `paths` (`[imported file]`), `from`, `to` (dotted), `lines` (sorted line numbers, possibly empty), `via` (`grimp` or `tree-sitter`) |
| | `kind: "cycle"` | `path` (file of the first module), `paths` (files of all members), `modules` (sorted dotted names) |
| | `kind: "contract"` | `path` (the config file), `contract` (name), `type`, `status` (`kept`, `broken`, `not-checked`), `violations` (`[{"from", "to", "path", "line"}]`), `reason` (for `not-checked`) |
| `symbols` | `kind: "def"` | `path`, `line`, `end_line`, `name`, `symbol` (SCIP symbol string), `type` (`class`, `function`, `method`, `variable`, `module`), `public` (no part of the descriptor path starts with `_`, and depth ≤ 2: a top-level name or a class member), `refs` (references from other files) |
| | `kind: "ref-edge"` | `path` (referring file), `paths` (`[defining file]`), `count` |
| `io_candidates` | one per semgrep result or tree-sitter state match | `id`, `group`, `path`, `line`, `end_line`, `category` (D3), `rule`, `snippet` (first line, at most 200 characters), `detail` (the rule's main metavariable value, for example the variable name in `os.environ["X"]`, or `null`) |
| `models` | an entity | `id`, `group`, `path`, `line`, `end_line`, `name`, `kind` (`dataclass`, `pydantic`, `sqlalchemy`, `django`, `typeddict`, `namedtuple`, `enum`, `attrs`, `sql-table`), `rule` (= `kind`), `snippet` (the class line), `bases`, `fields` (`[{"name", "type", "line", "ref"}]`; `ref` is a model name this field points at, from `ForeignKey(...)`, `relationship(...)` or a type naming another model, else `null`) |
| | `kind: "migration"` | `id`, `group`, `path`, `tool` (`alembic`, `django`, `sql`) |
| `tests` | `kind: "test-file"` | `path`, `test_kind` (`e2e` if a segment is `e2e`, `integration` if a segment is `integration`/`functional`/`live`, else `unit`), `framework` (`pytest` or `unittest`), `tests`, `classes`, `skips`, `xfails`, `mocks`, `fixtures`, `imports` (project modules), `paths` (source files of those modules) |
| | `kind: "config"` | `path`, `tool` (`pytest`, `coverage`, `tox`, `nox`), `settings` (`{"fail_under": …, "addopts": …, "testpaths": …}` where present) |
| | `kind: "ci-command"` | `path`, `line`, `command` |
| `dead` | one per vulture item | `id`, `group`, `path`, `line`, `end_line`, `name`, `type` (vulture's), `confidence`, `message`, `rule` (= `"vulture." + type`), `snippet` (= `name`) |
| `blindspots` | one per hit | `id`, `group`, `path`, `line`, `end_line`, `pattern` (the blind-spot id, D6), `rule`, `snippet` |

The ordering of items in every list is `(path, line, rule or kind, name)` so files diff cleanly.

### D3. Dispositions, home cards and V5

**Approved (Q2, Q3).** The outputs V5 covers and the home-card table below were approved as written on 2026-11-01. The spec now carries the same rules: principle 2 (which lists are candidate lists) and the home-card table in 6.1. If this table and the spec's ever disagree, stop and report.

**Home cards.** `candidates.CATEGORY_CARD` maps each `io_candidates` category (the rules' `metadata.category`) to one card; `entry_points` go to `entry.catalog`; entity `models` to `data.entities`.

| Category | Home card | Category | Home card |
|---|---|---|---|
| `cli-args` | `io.inputs` | `stdout` | `io.outputs` |
| `env-var` | `io.inputs` | `file-write` | `io.outputs` |
| `config-file` | `io.inputs` | `outbound-call` | `io.outputs` |
| `file-read` | `io.inputs` | `message-produce` | `io.outputs` |
| `stdin` | `io.inputs` | `exit-code` | `io.outputs` |
| `message-consume` | `io.inputs` | `error-response` | `io.outputs` |
| `db-connect` | `data.stores` | `log` | `behavior.observability` |
| `db-access` | `interactions.state` | `metric` | `behavior.observability` |
| `global-state` | `interactions.state` | `trace` | `behavior.observability` |
| `cache` | `interactions.state` | `retry` | `behavior.failures` |
| `thread` | `interactions.concurrency` | `timeout` | `behavior.failures` |
| `async` | `interactions.concurrency` | `catch-all` | `behavior.failures` |
| `process-pool` | `interactions.concurrency` | `transaction` | `behavior.failures` |
| `lock` | `interactions.concurrency` | `queue` | `interactions.concurrency` |

HTTP routes, scheduled jobs and queue consumers are entry points (`entry.catalog`); `io.inputs` rows for "network requests", "scheduled triggers" and "messages consumed" may cite them and may repeat their `cand` ids. A `lint` test asserts that every `metadata.category` in `rules/python/*.yml` is a key of `CATEGORY_CARD` (or a blind-spot or entry rule).

**In the card JSON** (only in table blocks of `blocks`-shaped cards, and in `entries`):

```json
{"card": "io.inputs",
 "blocks": [{"type": "table", "columns": ["Category", "Input", "Format", "Validation", "Where read"],
   "rows": [
     {"cells": ["environment variables", "`CANNALERTS_DB`", "path", "none", "[[src/cannalerts/config.py:12-14|config.py]]"],
      "conf": "confirmed", "cite": ["src/cannalerts/config.py:12-14"], "cand": ["io-3fa91c02"]},
     {"cells": ["CLI arguments", "every subcommand flag", "text", "argparse types", "[[src/cannalerts/cli.py:20-88|cli.py]]"],
      "conf": "confirmed", "cite": ["src/cannalerts/cli.py:20-88"], "cand": ["iog-7c1d0e55"]},
     {"cells": ["stdin", "none", "-", "-", "-"], "conf": "confirmed", "cite": ["facts:languages"], "added": true}]}],
 "dismissed": [{"cand": ["io-0b2c4d61", "iog-11aa22bb"], "reason": "Test helpers, not part of the application."}]}
```

- `cand`: list of candidate ids or group ids. One id = **kept**; several = **merged** into this row. A group id disposes of every candidate in that group.
- `added: true`: a row Claude found that no tool listed. Rows with both `cand` and `added` are an error.
- `dismissed`: card-level list; each entry has a non-empty `cand` list and a non-empty plain-text `reason` (no citations; it is not a statement).
- For `entries`-shaped cards, `cand` and `added` sit on the entry, beside `fields`.
- A card written as `na` may carry `dismissed` (every candidate fed to it must then be dismissed).

**V5 (`checks.v5`, errors unless noted):**

1. Every candidate in `entry_points`, `io_candidates` and entity `models` is disposed of: its id or its group id appears in some `cand` or `dismissed` in reports 03 to 12. Error text: `V5: {n} tool findings for {card title} have no decision, for example {id} ({path}:{line}, {rule}). Keep, merge or dismiss them.` (one line per home card, listing at most five ids, then "and N more").
2. Every id in a `cand` or `dismissed` list exists in this build's candidates (as an id or a group). Error: `V5: {report} card {card} names {id}, which is not a tool finding in this build.`
3. No candidate is both kept somewhere and dismissed somewhere. Error: `V5: {id} is kept in {card} and dismissed in {card}.`
4. Every `dismissed` entry has a non-empty reason. Error.
5. A row with both `cand` and `added`. Error.
6. **Warning:** in a card that has candidates fed to it, a table row or entry with neither `cand` nor `added`: `V5: {report} card {card}, row '{first cell}': say which tool findings it covers ('cand') or mark it 'added'.` Exception: rows of the fixed category rows of `io.inputs` and `io.outputs` whose `conf` is `confirmed` and whose text says none apply (cells[1] is `none`).
7. Candidates of an adapter whose tool failed are still checked (they exist); candidates of a tool that did not run do not exist, so nothing is required for them.

Gaps: with `--allow-errors`, each undisposed candidate group becomes a Gaps `coverage` item: `"A tool found {n} item(s) for {card title} in [[{path}:{line}]] ({rule}) that no report accounts for."`, `how_to_confirm` "Decide in the report whether to keep, merge or dismiss them, then build again.", `report` = the home card's report.

**Rejected.** (a) Dispositions in a separate file per report (for example `reports/io.dispositions.json`): the decision belongs next to the row it produced, and a reviewer reads them together. (b) A new citation kind `cand:<id>`: a citation must point at code the reader can open. (c) One disposition per call site with no groups: unworkable for large repositories (Q2).

### D4. The component model and V4

**Candidates** (`candidates.component_candidates(tree, graph_items, facts)`, shown by `dossier candidates --report components`, never written to a report automatically):

1. **Folders:** every directory that directly holds at least one tracked source file (gatherer language kind `code`, not noise), with its file count and line count.
2. **Packages:** every Python package and subpackage from the `graph` module items, up to two levels below the top package.
3. **Communities:** `graphs.communities(edges)`: label propagation on the undirected module import graph, nodes visited in sorted order, ties broken by the smallest label, at most 20 rounds. Each community is listed as its member folders.

**What Claude writes.** `components.catalog` has one row per component. Its `Paths` cell lists the component's paths separated by `, `: a directory (`src/cannalerts/alerts/`), a file, or a glob (`scripts/*.sh`), in backticks. `Size` is the measured line count (from `dossier candidates`), `Depends on` and `Used by` the measured component edges (computed by `candidates` once Claude has drafted the paths: `dossier candidates --report components --catalog reports/components.json` prints the edges between the drafted components). Files that belong to no component go in the catalog entry's `unassigned` list: `[{"paths": "docs/, LICENSE", "reason": "Documentation, not code."}]`.

**V4 (`checks.v4`):**

- Source files = tracked paths whose `gather.lang_of(path)` kind is `code` and `gather.noise_reason(path)` is `None`.
- A pattern matches a file when it is the file itself, a directory prefix of it (with or without a trailing `/`), or an `fnmatch` glob that matches it.
- **Most specific wins**: a literal file beats a glob, a glob beats a directory, a deeper directory beats a shallower one. A file whose best matches belong to two components is an error: `V4: {path} belongs to both {A} and {B}.`
- A file with no match and not covered by `unassigned` is an error: `V4: {n} source files belong to no component and are not listed as unassigned, for example {up to five paths}.`
- Every catalog component must have a `components.detail` entry with the same name (compared case-insensitively, backticks removed). Error: `V4: the component {name} has no entry in Component details.` A detail entry with no catalog row is a warning.
- Each `unassigned` pattern becomes one Gaps `coverage` item: `"{n} source file(s) in {paths} belong to no component: {reason}"`.
- When `components.catalog` is `na` or `pending`, V4 does not run (V6 reports pending; `na` is allowed for a repository with no source files).

**What the human reviews:** the component names and boundaries in the catalog and the map (spec 11, item 3: "you agree with the component map after at most minor renaming").

**Rejected.** (a) Components computed entirely by code (communities only): the spec makes naming, merging and splitting Claude's job. (b) "Exactly one" read literally, so nested patterns are errors: a component for `src/app/` and another for `src/app/api/` is the normal way to describe a package and a subpackage (spec issue 3).

### D5. The Python semgrep rule set

Files and ids (`dossier.<scope>.<category-or-family>.<name>`; `metadata.category` is the D3 category, or `entry` plus `metadata.kind` for entry rules, or `blindspot` plus `metadata.pattern` for blind-spot rules). Every rule is `languages: [python]` and `severity: INFO`, with a one-line `message`.

| File | Rule ids (name: what it matches) |
|---|---|
| `rules/python/entry.yml` | `dossier.python.entry.main-guard`: `if __name__ == "__main__": ...` (kind `main-guard`); `.click-command`: a function decorated `@click.command(...)`, `@click.group(...)`, `@$G.command(...)` or `@$G.group(...)` (kind `cli-command`); `.http-route`: a function decorated `@$APP.route($PATH, ...)` or `@$APP.$M($PATH, ...)` with `$M` in `get|post|put|patch|delete|websocket` (kind `http-route`, `detail` = `$PATH`); `.django-url`: `path($PATH, $VIEW, ...)` or `re_path(...)` inside `urlpatterns = [...]` (kind `http-route`); `.celery-task`: `@$APP.task(...)`, `@shared_task(...)` and bare forms (kind `queue-consumer`); `.scheduled-job`: `$S.add_job(...)`, `@$S.scheduled_job(...)`, `schedule.every(...)` (kind `scheduled-job`) |
| `rules/python/inputs.yml` | `dossier.python.input.env-var`: `os.environ[$K]`, `os.environ.get($K, ...)`, `os.getenv($K, ...)` (`detail` `$K`); `.cli-args`: `$P.add_argument(...)`, `sys.argv`, `@click.option(...)`, `@click.argument(...)`, `typer.Option(...)`, `typer.Argument(...)`; `.config-file`: `tomllib.load(...)`, `tomli.load(...)`, `configparser.ConfigParser(...)`, `yaml.safe_load(...)`, `yaml.load(...)`, `dotenv.load_dotenv(...)`, `load_dotenv(...)`; `.file-read`: `open($F)`, `open($F, $M, ...)` where `$M` is a string without `w`, `a`, `x` or `+`, `$X.read_text(...)`, `$X.read_bytes(...)`; `.stdin`: `sys.stdin`, `input(...)`; `.message-consume`: `$CH.basic_consume(...)`, `$C.subscribe(...)`, `$C.poll(...)` where the receiver was built from `KafkaConsumer(...)` or `Consumer(...)` |
| `rules/python/outputs.yml` | `dossier.python.output.stdout`: `print(...)`, `sys.stdout.write(...)`, `sys.stderr.write(...)`; `.file-write`: `open($F, $M, ...)` where `$M` holds `w`, `a`, `x` or `+`, `$X.write_text(...)`, `$X.write_bytes(...)`, `shutil.copy(...)`, `shutil.copyfile(...)`, `shutil.move(...)`; `.outbound-call`: `requests.$M(...)`, `httpx.$M(...)`, `httpx.Client(...)`, `httpx.AsyncClient(...)`, `aiohttp.ClientSession(...)`, `urllib.request.urlopen(...)`, `smtplib.SMTP(...)`, `boto3.client(...)`; `.message-produce`: `$CH.basic_publish(...)`, `$P.produce(...)`, `$C.publish(...)`; `.exit-code`: `sys.exit(...)`, `raise SystemExit(...)`; `.error-response`: `abort(...)`, `raise HTTPException(...)`, `return $R, $CODE` where `$CODE` is an integer of 400 or more (`metavariable-comparison`) |
| `rules/python/state.yml` | `dossier.python.state.db-connect`: `sqlite3.connect(...)`, `create_engine(...)`, `psycopg.connect(...)`, `psycopg2.connect(...)`, `pymongo.MongoClient(...)`, `redis.Redis(...)`, `redis.from_url(...)`; `.db-access`: `$C.execute(...)`, `$C.executemany(...)`, `$S.query(...)`, `$S.add(...)`, `$S.commit()` where `$S` is a session or connection (match any receiver, the group-level disposition keeps the volume small); `.global-state`: `global $X`; `.cache`: decorators `@functools.lru_cache`, `@lru_cache(...)`, `@functools.cache`, `@cache`, `@cached_property` |
| `rules/python/concurrency.yml` | `dossier.python.concurrency.thread`: `threading.Thread(...)`, `ThreadPoolExecutor(...)`; `.process-pool`: `ProcessPoolExecutor(...)`, `multiprocessing.Process(...)`, `multiprocessing.Pool(...)`; `.async`: `asyncio.run(...)`, `asyncio.create_task(...)`, `asyncio.gather(...)`, `$LOOP.run_until_complete(...)`; `.lock`: `threading.Lock()`, `threading.RLock()`, `asyncio.Lock()`, `asyncio.Semaphore(...)`; `.queue`: `queue.Queue(...)`, `asyncio.Queue(...)`, `multiprocessing.Queue(...)` |
| `rules/python/resilience.yml` | `dossier.python.resilience.retry`: decorators `@retry(...)`, `@tenacity.retry(...)`, `@backoff.on_exception(...)`, `@backoff.on_predicate(...)`, and `Retry(...)` (urllib3); `.timeout`: any call with a `timeout=$T` keyword; `.catch-all`: `except: ...`, `except Exception: ...`, `except BaseException: ...` (with or without `as $E`); `.transaction`: `with $X.begin(): ...`, `with transaction.atomic(): ...`, `$C.rollback()` |
| `rules/python/observability.yml` | `dossier.python.observability.log`: `logging.getLogger(...)`, `logging.basicConfig(...)`, `$L.debug|info|warning|error|exception|critical(...)` where `$L` was assigned from `logging.getLogger(...)` or is named `log`, `logger` or `LOG` (`metavariable-regex`), and `structlog.get_logger(...)`, `loguru.logger.$M(...)`; `.metric`: `prometheus_client.$C(...)` for `Counter|Gauge|Histogram|Summary`, `statsd.$M(...)`; `.trace`: `sentry_sdk.init(...)`, `opentelemetry.trace.get_tracer(...)`, `trace.get_tracer(...)` |
| `rules/python/blindspot.yml` | D6 |
| `rules/all/blindspot.yml` | D6 (`languages: [generic]`) |

The module-level mutable state candidate (`category: "global-state"`, rule `dossier.python.state.module-mutable`) comes from a tree-sitter query, not semgrep, because semgrep cannot restrict a pattern to module level reliably: a module-level `assignment` whose right side is a `dictionary`, `list` or `set` and whose name is not all capitals (all-capitals names are taken as constants).

**Tests.** For each rule file `rules/<scope>/<name>.yml` there is a target file `tests/fixtures/semgrep/<scope>/<name>.py` (for `all`, `<name>.txt` is not valid; use `tests/fixtures/semgrep/all/blindspot.py`, which `generic` rules also scan). Every rule id has at least one `# ruleid: <id>` case and at least one `# ok: <id>` case (a near miss that must not match, for example `open(path, "w")` under `file-read`, `logger.info` on a receiver named `cart` under `log`, `getattr(obj, "name")` under the dynamic-getattr blind spot). The slow test runs the worker's `test` mode (`semgrep --test --config SKILL/rules SKILL/tests/fixtures/semgrep`) and requires exit code 0. A unit test (no network) parses every rule file (simple YAML subset reader written for the test: it only needs to collect `id:` and `category:` lines) and checks: ids start with `dossier.<scope>.`, ids are unique, every `id` has a `ruleid` annotation in the matching target file, and every `metadata.category` is known (D3 or `entry`/`blindspot`).

### D6. The Python blind spots (V7)

Each blind spot has an id (`metadata.pattern`) and one rule. Spec 6.4's Python list, plus "All":

| Pattern id | Rule | Detects | What the dossier says it may miss |
|---|---|---|---|
| `dynamic-import` | `dossier.python.blindspot.dynamic-import` | `importlib.import_module(...)`, `__import__(...)` | imports made at run time |
| `entry-point-loading` | `dossier.python.blindspot.entry-point-loading` | `importlib.metadata.entry_points(...)`, `entry_points(...)`, `pkg_resources.iter_entry_points(...)`, `$EP.load()` | plugins loaded from installed packages |
| `string-plugin` | `dossier.python.blindspot.string-plugin` | `importlib.import_module($S)` or `__import__($S)` where `$S` is built from a string (`f"..."`, `"..." + $X`, `"...".format(...)`) | plugins named by a string |
| `decorator-registry` | `dossier.python.blindspot.decorator-registry` | decorators `@$R.register(...)`, `@$R.register`, `@register(...)`, `@register`, `@$R.handler(...)`, `@$R.on(...)` | handlers registered by decorator and called through a table |
| `getattr-dispatch` | `dossier.python.blindspot.getattr-dispatch` | `getattr($X, $N, ...)` where `$N` is not a string literal | methods chosen by name at run time |
| `django-apps` | `dossier.python.blindspot.django-apps` | `INSTALLED_APPS = [...]` | Django apps loaded from settings |
| `django-signals` | `dossier.python.blindspot.django-signals` | `@receiver(...)`, `$SIG.connect(...)` where `$SIG` ends in `_save`, `_delete`, `_init`, `request_started`, `request_finished` (`metavariable-regex`) | signal handlers called by Django |
| `pytest-fixtures` | `dossier.python.blindspot.pytest-fixtures` | `@pytest.fixture` and `@pytest.fixture(...)` | fixtures passed to tests by name |
| `codegen` | `dossier.all.blindspot.codegen` | `pattern-regex: (?i)(do not edit|@generated|auto-?generated by)` | generated code, whose generator was not analysed |
| `feature-flag` | `dossier.all.blindspot.feature-flag` | `pattern-regex: (?i)(feature[_-]?flag|launchdarkly|unleash|flagsmith|growthbook)` | behaviour switched by flags at run time |

"Runtime config selecting implementations" (spec 6.4, All) has no rule: no pattern finds it without many false matches. It is listed in Gaps once per build as a fixed coverage item: "Code chosen at run time by configuration (for example a class name in a settings file) is not detected by any rule." (spec issue 9).

**V7 (`checks.v7`):** for every `blindspots` group (pattern, file), one Gaps `coverage` item, `report` = the report that owns the closest card (`interactions` for imports, registries, dispatch, signals; `behavior` for fixtures; `components` for codegen and flags): statement `"Static analysis may miss {what it may miss} here: {n} place(s) in [[{path}:{line}]]."` (the first hit's line), `how_to_confirm` `"Read the code at these places and check the reports that depend on them."`. V7 never fails the build. The process card's `gaps` line already counts coverage items.

### D7. The tool-to-card map and the "partial" badge

`tools.json`: every self-installing tool and the `repo-config` tool gains `"cards"`:

| Tool | Cards |
|---|---|
| `grimp` | `reading.order`, `components.map`, `components.catalog`, `interactions.graph`, `interactions.violations`, `interactions.flows` |
| `scip-python` | `components.catalog`, `interactions.flows`, `interactions.graph` |
| `semgrep` | `entry.catalog`, `io.inputs`, `io.outputs`, `interactions.state`, `interactions.concurrency`, `data.stores`, `behavior.failures`, `behavior.observability` |
| `tree-sitter-language-pack` | `data.entities`, `data.relationships`, `behavior.tests`, `interactions.state` |
| `vulture` | `change.dead-code` |
| `import-linter` | `interactions.violations` |
| JS and C# tools | `[]` until M4 and M5 |

Host tools have no cards: a missing host tool makes its self-installing tools missing (`toolcheck.preflight` already lists them in `missing`).

`render.partial_cards(build) -> dict[card id, reason]` (in `process.py`, next to `coverage_items`): a tool is **absent** when its id is in the `tools` record's `details.missing`, or when any adapter's `tool_status[tool]` is `failed` or `skipped` in the `extract` record's `details.adapters`, or when the whole `extract` step was skipped or failed (then every tool with cards is absent). For every card of an absent tool, the reason is `"Made without {tool}: {why}."` (`why` = "it is not installed", the tool's failure reason, or the extract step's reason; several reasons are joined). Only tools whose `scope` includes a language of this build count.

`schema_card(card, body, extra="", partial=None)`: when `partial` is set, a badge `<span class="badge partial" data-variant="outline" tabindex="0" data-tip="{reason}">partial</span>` follows the tier badge. The CSS class needs no new style beyond `dossier.css`'s existing `.badge`; if it does not read well in the browser check, add one rule to `assets/dossier.css` (not report 02's rules). Spec 6.3's "full" badge is not shown: a card without "partial" is full (spec issue 17).

### D8. The measured cards (`measured.py`)

`measured.body(cid, ctx, refs) -> str | None`. `build_page` calls it for every `writer: script` card in reports 03 to 12 before `placeholder_body`; `None` keeps the placeholder (for example when the extractors did not run). `ctx` gains `extract` (the flattened items per output, `candidates.load(out)`), `facts`, and `catalog` (the `components.catalog` rows, parsed). Tables use `render.render_table(..., plain=True)`; cited paths use `render.path_cell` so they open the viewer.

- **`reading.map`** (Concern, Location). Fixed concerns in this order, each with every matching tracked path or folder (a folder when all its files match), or "none found": configuration (`pyproject.toml`, `setup.cfg`, `*.ini`, `*.toml` outside `.github`, `.env.example`, `config/`, `settings*.py`), tests (folders of `tests` test files, else `gather.TEST_RE` matches), build (`pyproject.toml` build-system, `setup.py`, `Makefile`, `Dockerfile*`, `noxfile.py`, `tox.ini`), docs (`docs/`, `*.md` at the root), migrations (the `models` migration items' folders), CI (`.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, `.circleci/`), entry points (the files of `entry_points` items, de-duplicated), scripts (`scripts/`, `bin/`).
- **`conventions.tooling`** (Tool, Config file, Enforced where). One row per tool found: ruff (`[tool.ruff]`, `ruff.toml`, `.ruff.toml`), black (`[tool.black]`), isort (`[tool.isort]`, `.isort.cfg`), flake8 (`.flake8`, `[flake8]` in `setup.cfg` or `tox.ini`), mypy (`[tool.mypy]`, `mypy.ini`, `.mypy.ini`), pyright (`pyrightconfig.json`, `[tool.pyright]`), pylint (`.pylintrc`, `[tool.pylint]`), pre-commit (`.pre-commit-config.yaml`), editorconfig (`.editorconfig`). "Enforced where": `pre-commit` when the tool's name appears in `.pre-commit-config.yaml`; each CI workflow file whose text contains the tool's name; else "not enforced in the repository". Reads blobs with `cites.repo.read` at the pinned commit. No tools → "No formatter or linter configuration was found."
- **`interactions.violations`** (Kind, From, To, Evidence). Rows: one per `cycle` item (Kind "import cycle", From/To = the members joined by " → ", Evidence = a citation to the first import line of the cycle); one per `contract` violation (Kind "breaks contract '{name}'", From, To, Evidence = `path:line`); one per `not-checked` contract (Kind "contract not checked", From = the contract name, To = "-", Evidence = the reason). No rows → "No import cycles were found{, and the repository declares no layer rules | , and every declared contract is kept}."
- **`interactions.graph`**. A Mermaid flowchart at **component** level when the catalog exists (else at top-package and folder level): one node per component, an arrow per component pair with at least one import, labelled with the import count; then a module edge table (From, To, Imports, Lines) listing every `import` item, sortable and filterable. Below 2 nodes: only the table.
- **`components.map`**. A Mermaid flowchart with one `subgraph` per area (the first path segment below the package root, or the top-level folder) holding its components, arrows from `graphs.aggregate(imports, component_of)`; then a table (Component, Area, Files, Lines, Depends on, Used by), all computed. Without a catalog: `None` (placeholder) and V6 has already reported the missing catalog.

Mermaid sources are built with `measured.mermaid_id(name)` (letters, digits and underscores only) and quoted labels, so `check_page.py` can draw them.

### D9. V2, V3 and V7 implementations

All live in `checks.py`, are called by `checks.validate(reports, extract, cites, facts) -> {"errors", "warnings", "gaps", "counts"}`, and return Gaps items with fixed wording.

**V2 (warning, counted in Gaps).** For every claim (`render.claims_of`) with at least one file citation:

- Spans: `` `([^`]+)` `` in the claim's text and cells.
- Checked spans: those matching `^[A-Za-z_][\w.]*(\(\))?$` that are not tracked paths, not Python keywords or built-in names (`keyword.kwlist`, `dir(builtins)`), not all lowercase single words of 3 characters or fewer, and not the literal words `true`, `false`, `null`, `none`.
- The cited text: for each file citation, the cited lines (or the whole file when no lines are given; directories are skipped), read at the pinned commit through `cites.repo.read`.
- A span passes when the cited text contains it, or (for a dotted name) its last part, or (for `name()`) `name`.
- Each failure: warning `V2: {report} '{claim text, 50 chars}': {span} does not appear in the code it cites ({cites}).` and one Gaps `inference` item `"A statement in {report title} names `{span}`, which does not appear in the code it cites."`, `how_to_confirm` `"Check the citation's line range, or the name."`, `cite` = the claim's file citations.

**V3 (warning; arrows listed as inferred).** For every diagram block of `entry.startup` and `interactions.flows`:

- Parse `sequenceDiagram`: `participant|actor X [as Label]` lines give aliases; messages `A->>B`, `A-->>B`, `A->B`, `A-->B`, `A-xB`, `A--xB`, `A-)B`, `A--)B` with an optional `: text`. Dashed forms (`-->>`, `-->`, `--x`, `--)`) are replies: checked as B→A.
- Parse `flowchart`/`graph`: node definitions `id[...]`, `id(...)`, `id{...}`, `id["..."]` give labels; edges `A --> B`, `A -.-> B`, `A ==> B`, `A -- text --> B`, `A -->|text| B`, chains `A --> B --> C`. `subgraph … end` lines are skipped.
- **Resolve** each node (its id, then its label with `<br/>` and anything after it removed) to a set of modules: an exact dotted module name; else a module whose last part equals it (only when unique); else a tracked file path (its module); else a catalog component name (all its modules). Nodes that resolve to nothing are external (users, services, databases) and their arrows are not checked.
- An arrow A→B between resolved nodes is **backed** when some module of A imports some module of B (`graph` imports), or some file of A references some file of B (`symbols` ref-edges), or A and B share a module. Otherwise it is unbacked.
- Each unbacked arrow: warning `V3: {card title}, diagram {n}: the arrow {A} → {B} has no import or call behind it.`; the page shows under that diagram `<p class="muted">Arrows with no import or call behind them, so treat them as inferred: A → B, …</p>`; one Gaps `inference` item per arrow: `"In {card title}, the arrow from {A} to {B} has no import or call behind it in the code."`, `how_to_confirm` `"Read the two parts and check how one reaches the other (for example through a callback or a registry)."`.
- When `graph` is empty (grimp absent or failed), V3 does not run; an info line says so and the cards are already partial.

**V7.** D6.

**Counts** (for the process card): `{"v2": warnings, "v3": unbacked arrows, "v3_checked": arrows checked, "v4": errors, "v5_candidates": n, "v5_open": undisposed}`.

### D10. Staleness from extractor output (`candidates.digest`)

`candidates.FEEDS` names what each report is built from:

| Report | Fed by |
|---|---|
| `reading` | `graph` (modules, imports), `entry_points`, `tests` (files) |
| `entry` | `entry_points` |
| `components` | `graph`, `symbols` (defs with `public`) |
| `interactions` | `graph`, `symbols` (ref-edges), `io_candidates` of the `interactions.*` home cards |
| `io` | `io_candidates` of the `io.*` home cards, `entry_points` |
| `data` | `models`, `io_candidates` of `data.stores` |
| `behavior` | `tests`, `io_candidates` of the `behavior.*` home cards |
| `conventions` | `io_candidates` (all), `graph` (modules) |
| `ops` | `entry_points`, `tests` (config and CI commands) |

`digest(rid, extract) = sha1` of the JSON of the sorted list of line-free keys of those items: candidate items by `id`; graph modules by `module`; imports by `(from, to)`; cycles by `modules`; contracts by `(contract, status, violations without lines)`; defs by `(path, symbol, public)`; ref-edges by `(path, paths[0])`; tests by `(path, tests, skips, xfails)` and configs by `(path, tool, settings)`. Line numbers never enter a digest, so moving code does not make a report stale on its own (a cited file that changed already does).

`cmd_render` stores `state["extract_digests"] = {rid: digest}` for the reports it rendered. `cmd_prepare`, after `stage_extract`, computes the new digests and passes them to `update_plan(..., digests=...)`; in the incremental branch, for every report with a stored digest that differs, it adds the reason `"the tool findings it is built from changed"` (fixed wording). A report with no stored digest gets no such reason (the 0.7.0 bump forces a full build anyway). `incremental.plan` gains a `digest_changed: set[str]` parameter so the logic stays in one place and is unit-tested there. M-tier cards are drawn on every render, as today.

### D11. The prompts

- **`prompts/method.md`** keeps "Writing style", "Evidence rules", "Citation forms", "Diagrams", "Reading the repository" and "Corrections and updates" (with report names updated). It replaces "Report file shape" with the card layout (`prompts/schema/README.md` is the reference): `headline`, `summary`, `cards`; each card entry by id, in schema order, with `blocks`, `entries` or `na` plus `cite`; titles never written; every card of reports 03 to 09, 11 and 12 written (no `pending`). It adds a new section **"Tool findings: keep, merge, dismiss"**: run `DOSSIER candidates <repo> --report <id>` before writing a report; for every finding listed under a card, either keep it (`cand: [id]` on its row), merge several into one row (`cand: [id, id]` or a group id), or dismiss it in the card's `dismissed` list with a short reason; add what the tools missed as rows with `added: true`; never invent a finding's id; cite the code, not the finding; finish with `DOSSIER candidates <repo> --report <id> --open`, which must print nothing. It adds **"Components"** (D4: draft the catalog from the candidates, check the drafted paths with `--catalog`, list unassigned files with a reason, one detail entry per component) and **"What render checks"** (V1 to V7 in one plain line each).
- **`prompts/reports.md`** is rewritten as one section per report 03 to 09, 11, 12 (each card: what to put in it, which findings feed it, the measured cards it must not repeat), plus the unchanged sections for `overview` (now: `headline`, `summary`, optional `update_note`, no blocks), `risks` (the `risks.tracker` card), `gaps` and `corrections`. The retired report sections (capabilities, interfaces, architecture, domain-logic, data, code-tour, failures, delivery, contributors) are removed; the "contributors" section moves to M3.
- **Order of writing** (SKILL.md step 5): `entry`, `components`, `interactions`, `io`, `data`, `behavior`, `conventions`, `ops`, then `reading` (it needs the entry points and components), `overview`, `risks`, `gaps` last.
- **Chunking:** unchanged for reading the code. For writing, a repository whose `reading.mode` is `chunked` gives each report to its own subagent with the paths to `method.md`, `reports.md`, the notes, `facts.json` and the command `DOSSIER candidates <repo> --report <id>`; `components` gives `components.detail` to one subagent per area when the catalog has more than 12 components, each writing its entries into a scratch file that the main session merges.
- **SKILL.md** drops the "cannot yet write the new report layout" notice, lists the reports above in step 5, adds `DOSSIER candidates` to the commands Claude uses, and says that reports 10 (`change`) and 13 (`contributors`) are not written in this version.

### D12. Version

`VERSION` 0.7.0. A minor bump makes the next `prepare` of any dossier a full rebuild (`update_plan`) and backs up `state.json` as `state.backup-v0.6.0.json`. Existing 0.6.0 dossiers have no written 03 to 12 reports, so nothing is lost. **Rejected:** 0.6.1 (a patch bump would let `update_plan` treat a 0.6.0 dossier as incremental, with reports in a layout it never produced).

### D13. The three sessions

| Phase | Content | Why this cut |
|---|---|---|
| 1 | Tool re-check, framework changes, fixture repository, both adapters, all rules and their tests, `dossier candidates` | Ends with real `extract/*.json` for a Python repository and fixture tests for every extractor. Nothing reads the outputs yet, so nothing else can break. |
| 2 | Card keys, V5, V4, the measured cards, "partial", staleness, the process card's check line | Everything `render` does with the outputs that is checked mechanically. V5 lands with the dispositions it checks. |
| 3 | V2, V3, V7, prompts, SKILL.md, README line, version, end-to-end verification | The checks that read prose and diagrams, and the instructions that make Claude write the reports; only then can the full build run. |

**Rejected:** the prompt's example cut (V2 to V5 all in Phase 3): V5 would arrive a session after the card keys it checks, and Phase 2 would leave dispositions unchecked.

---

## Phase 1: Extractors and fixtures

### Before you start (Phase 1)

1. Read section 2 (shared rules), then sections 3 and 4. Load the skills listed in section 2.
2. Run `git log --oneline -10`. The top commit should be `dcd36f6 Merge branch 'feat/dossier-m1'`. If commits after it touch `scripts/` or `prompts/`, stop and report. Read plan 006's "Verification results" and "Deviations": M1 moved to M2 the "partial" badge (M2-19 here), staleness from extractor output (M2-20), the tool re-check (M2-1), `.grimp_cache` (M2-5), block C with citations (section 6), and V10 on old dossiers (block E). Nothing else.
3. Check the human's answers in section 7. All ten were answered on 2026-11-01 with the plan's defaults, so the plan applies as written. If section 7 shows an answer that differs from the plan text, stop and report.
4. `git switch -c feat/dossier-m2`.
5. Run the full suite once. It must print `405 passed, 2 skipped` (or record the real baseline under "Results (Phase 1)" if it differs, and stop if anything fails).

Independent tasks: M2-3, M2-4, M2-6 and M2-7 need nothing but M2-2 and can be done in any order. M2-5 needs M2-3 and M2-4. M2-8 needs M2-3. M2-9 needs M2-1. M2-10 needs M2-2 and M2-7. M2-11 needs all before it. M2-12 needs M2-11.

### M2-1. Re-check the Python tools on this machine

- [x] **Goal.** Prove the D1 facts that the documentation did not state, before any code depends on them.
- **Files.** This plan only ("Results (Phase 1)").
- **Steps.** In a scratch folder outside `SKILL` (`S=$(mktemp -d)`), with a tiny package `pkg/__init__.py`, `pkg/a.py` (`from pkg import b`), `pkg/b.py` (`import pkg.a\ndef unused():\n    pass\n`):
  1. grimp: `cd $S && uv run --python 3.13 --with grimp==3.17 python -c "import sys; sys.path.insert(0, '.'); import grimp; g = grimp.build_graph('pkg', cache_dir=None); print(sorted(g.modules)); print(g.get_import_details(importer='pkg.a', imported='pkg.b')); print(g.find_illegal_dependencies_for_layers(layers=['pkg.a', 'pkg.b']))"`. Expect the three modules, one detail dict with `line_number`, and a set (possibly empty). Then `ls -a $S` must show no `.grimp_cache`.
  2. vulture: `uv run --python 3.13 --with vulture==2.16 python -c "import vulture, inspect; print(inspect.signature(vulture.Vulture)); v = vulture.Vulture(); v.scavenge(['pkg']); it = v.get_unused_code(min_confidence=60); print([(i.filename, i.first_lineno, i.last_lineno, i.typ, i.name, i.confidence, i.message) for i in it])"`. Record the constructor's parameters and the item attributes. If any of `filename`, `first_lineno`, `last_lineno`, `typ`, `name`, `confidence`, `message` is missing, record the real names; M2-5 uses what this step found.
  3. scip-python: `mkdir $S/n && cd $S/n && npm init -y >/dev/null && npm install --ignore-scripts --no-audit --no-fund @sourcegraph/scip-python@0.6.6 && ls node_modules/@sourcegraph/scip-python && node node_modules/@sourcegraph/scip-python/index.js index --help`. Then in `$S`: `echo '[]' > env.json && node n/node_modules/@sourcegraph/scip-python/index.js index . --project-name pkg --output $S/out.scip --quiet --environment env.json; echo "exit $?"; ls -l $S/out.scip`. Expect exit 0 and a non-empty file. Record whether `--ignore-scripts` broke anything (it must not: no postinstall step is expected) and the bin file name.
  4. semgrep metavariables: write `$S/r.yml` with a rule `id: t`, `pattern: os.getenv($K)`, `languages: [python]`, `message: m`, `severity: INFO`, and `$S/t.py` with `import os\nos.getenv("X")\n`; run `uvx --from semgrep==1.181.0 semgrep scan --config $S/r.yml --json --metrics=off --disable-version-check --oss-only --quiet $S/t.py | python3 -c "import json,sys; r=json.load(sys.stdin)['results'][0]; print(r['extra'].get('metavars'))"`. Expect `$K` with an `abstract_content` of `"X"`. Record what came back.
- **Stop condition.** If step 1 or 3 fails, stop and record the output: M2-5 or M2-9 cannot be built as planned.
- **Done-check.** "Results (Phase 1)" has one line per step with the observed values.
- **Commit.** `docs(dossier): record the M2 tool re-check in plan 007`

### M2-2. Adapter framework: wildcard adapters, tool status, ids, the candidates module

- [x] **Goal.** The framework changes every later task relies on (sections 3 items 2, 6, 7; D2).
- **Files.** Edit `scripts/adapters.py`; new `scripts/candidates.py` (first part); edit `tests/unit/scripts/test_adapters.py`, `tests/integration/scripts/test_extract.py`; new `tests/unit/scripts/test_candidates.py`.
- **Interface.**
  ```python
  # adapters.py
  @dataclass
  class Context:  # existing fields, plus:
      trusted: bool = True          # the ref is trusted, or --allow-ref was given
      repo_name: str = "repo"
      tool_status: dict = field(default_factory=dict)   # tool id -> {"status", "reason"}
  def detect(languages, adapters=ADAPTERS):   # an adapter with "*" in languages always matches
  # candidates.py
  ID_OUTPUTS = {"entry_points": "ep", "io_candidates": "io", "models": "md", "dead": "dd", "blindspots": "bs"}
  def norm(s: str) -> str
  def assign_ids(output: str, items: list[dict]) -> list[dict]   # D2; returns new dicts, sorted (path, line, rule|kind, name)
  def load(out: Path) -> dict[str, list[dict]]   # {output: items of every adapter, in adapter-name order}; {} for missing files
  def by_id(extract) -> dict[str, dict]           # id and group ids -> item (group -> first item)
  def group_members(extract) -> dict[str, list[str]]   # group id -> ids
  ```
- **Steps.** (1) `Context`: add the three fields with defaults (keep positional construction in `run_extract` working; switch it to keyword arguments). (2) In `run_extract`: pass `trusted=bool(trusted["trusted"] or allow_ref)` and `repo_name=Path(out).name`; after `filter_paths`, `kept = {o: (candidates.assign_ids(o, its) if o in candidates.ID_OUTPUTS else its) for o, its in kept.items()}`; store `"tool_status": ctx.tool_status` in each section written (beside `sha`, `version`, `tools`); add `"tools": ctx.tool_status` to the adapter's `res` record. (3) `_reusable`: also return `False` when any section's `tool_status` has a status other than `ok`. (4) `detect`: `"*" in a.languages or set(a.languages) & set(languages)`. (5) `candidates.py` as above. Import `candidates` in `adapters` (no cycle: `candidates` imports only the standard library).
- **Tests.** `assign_ids`: the same input in a different order gives the same ids; moving an item's line keeps its id; two identical snippets in one file get different ids (`n` = 0 and 1); a changed snippet changes the id; the group id depends only on rule and path; items are returned sorted. `detect(["Shell"], (Wild,))` with `Wild.languages = ("*",)` returns it. Integration (`test_extract.py`): a fixture adapter that sets `ctx.tool_status["x"] = {"status": "failed", "reason": "boom"}` writes `tool_status` into its section, and a second run is **not** `reused`; one with all `ok` is reused as before; a fixture adapter returning `io_candidates` items gets `id` and `group` in the written file.
- **Done-check.** Full suite passes.
- **Commit.** `feat(dossier): give extractor findings stable ids and record each tool's status`

### M2-3. The Python fixture repository

- [x] **Goal.** A small repository with known entry points, imports, a cycle, a layer violation, dead code, I/O, models, tests and blind spots, so each extractor has an exact expected output.
- **Files.** New `tests/fixtures/pyrepo/**` (below); edit `tests/conftest.py` (fixture `py_repo`, helper `line_of`).
- **Content.** Every line that a test must find carries a marker comment `# @<name>` at the end of the line. Tests never hard-code line numbers: `line_of(path, name)` returns the 1-based line holding `# @<name>`. Files (write each with exactly this behaviour; keep each under 40 lines):
  - `pyproject.toml`: `[project]` name `shopcart`, `requires-python = ">=3.11"`, `[project.scripts] shopcart = "shopcart.cli:main"` (`# @ep-script` on that line), `[build-system]` hatchling, `[tool.hatch.build.targets.wheel] packages = ["src/shopcart"]`, `[tool.ruff]` `line-length = 100`, `[tool.pytest.ini_options]` `testpaths = ["tests"]`, `[tool.coverage.report]` `fail_under = 80`, and `[tool.importlinter]` `root_package = "shopcart"` with one `layers` contract `name = "cli above core"`, `layers = ["shopcart.cli", "shopcart.core"]`, plus one `independence` contract `name = "apps apart"`, `modules = ["shopcart.plugins", "shopcart.store"]`.
  - `src/shopcart/__init__.py`: `__version__ = "1.0"`.
  - `src/shopcart/__main__.py`: `from shopcart.cli import main` and `main()` (`# @ep-main-module`).
  - `src/shopcart/cli.py`: `import argparse`, `import sys`, `from shopcart import core, store`; `def main():` builds `argparse.ArgumentParser` and `add_argument("--db")` (`# @io-cli`), calls `core.total(...)`, `print(...)` (`# @io-print`), `sys.exit(0)` (`# @io-exit`); `if __name__ == "__main__":` (`# @ep-guard`) `main()`.
  - `src/shopcart/core.py`: `from shopcart import cli` inside a function (`# @import-up`, the layer violation: core imports cli), `import logging`, `log = logging.getLogger(__name__)` (`# @io-log-get`), `CART = {}` (`# @state-module`), `def total(items):` with `log.info("total")` (`# @io-log`) and a `try`/`except Exception:` (`# @fail-catchall`), `def unused_helper():` (`# @dead-func`) returning 1.
  - `src/shopcart/a.py` and `src/shopcart/b.py`: `a` does `from shopcart import b` (`# @cycle-a`), `b` does `from shopcart import a` (`# @cycle-b`).
  - `src/shopcart/store.py`: `import os`, `import sqlite3`, `DB = os.environ.get("SHOP_DB", "shop.db")` (`# @io-env`), `def connect(): return sqlite3.connect(DB)` (`# @io-db-connect`), `def save(path, text): open(path, "w").write(text)` (`# @io-file-write`), `def load(path): return open(path).read()` (`# @io-file-read`), `def fetch(url): import requests; return requests.get(url, timeout=5)` (`# @io-outbound`, the same line also matches `timeout`).
  - `src/shopcart/api.py`: `from flask import Flask`, `app = Flask(__name__)`, `@app.route("/cart")` (`# @ep-route`) on `def cart(): return {}`, and `@app.get("/health")` (`# @ep-route2`) on `def health(): return "ok"`.
  - `src/shopcart/models.py`: `from dataclasses import dataclass`, `from enum import Enum`, `from pydantic import BaseModel`; `@dataclass` `class Item:` (`# @model-item`) with `sku: str`, `price: float`; `class Status(Enum):` (`# @model-status`) with `OPEN = 1`; `class Order(BaseModel):` (`# @model-order`) with `items: list[Item]` (`# @field-items`, a `ref` to `Item`) and `status: Status`.
  - `src/shopcart/plugins.py`: `import importlib`, `def load(name): return importlib.import_module(name)` (`# @bs-import`), `def call(obj, name): return getattr(obj, name)()` (`# @bs-getattr`), `REGISTRY = {}` (`# @state-registry`), and a decorator `register` used as `@register` (`# @bs-registry`) on one function.
  - `src/shopcart/worker.py`: `import threading`, `import asyncio`, `lock = threading.Lock()` (`# @cc-lock`), `def start(): threading.Thread(target=run).start()` (`# @cc-thread`), `async def run_async(): await asyncio.sleep(0)`, `def run(): asyncio.run(run_async())` (`# @cc-async`).
  - `tests/test_core.py`: `import pytest`, `from unittest import mock`, `from shopcart import core`; `@pytest.fixture` (`# @bs-fixture`) `def items(): return []`; `def test_total(items):` (`# @test-1`); `@pytest.mark.skip(reason="later")` `def test_skipped():` (`# @test-skip`); `def test_mocked():` with `mock.patch("shopcart.core.log")` (`# @test-mock`).
  - `scripts/seed.sh`: `#!/bin/sh` then `echo seed`, committed executable (`# @ep-shebang` on line 2 is not possible in sh before the shebang; put the marker on line 2 as `# @ep-shebang` and expect line 1).
  - `Dockerfile`: `FROM python:3.13-slim`, `COPY . /app`, `CMD ["python", "-m", "shopcart"]` with the marker on the line before as a comment `# @ep-docker` (expect the `CMD` line = marker line + 1).
  - `Makefile`: `test:` (`# @ep-make`) with a tab-indented `pytest` recipe.
  - `.github/workflows/ci.yml`: `on: push` and `schedule: - cron: "0 3 * * *"` (`# @ep-cron`), one job whose step runs `pytest -q` (`# @ci-pytest`) and one that runs `ruff check .`.
  - `.pre-commit-config.yaml`: one repo entry with hook id `ruff`.
  - `db/schema.sql`: `CREATE TABLE orders (id INTEGER PRIMARY KEY);` (`-- @model-sql`).
  - `README.md`: one line.
- **conftest.** `py_repo(tmp_path)`: copy `PYFIX` into `tmp_path / "pyrepo"`, `chmod 0o755 scripts/seed.sh`, `git init -b main`, add, commit (with the same scrubbed git environment as `hygiene_repo`), return `SimpleNamespace(path, sha)`. `line_of(root, rel, name)`: the 1-based line containing `@<name>` (a marker comment), raising if absent or repeated.
- **Done-check.** Full suite passes; a new unit test `tests/unit/scripts/test_pyfixture.py` asserts every marker named above appears exactly once and that `python3 -m py_compile` succeeds on every `.py` file in `PYFIX`.
- **Commit.** `test(dossier): add the Python fixture repository`

### M2-4. Python project layout parsing (`py_packages.py`)

- [x] **Goal.** Everything the adapter reads from configuration files, as pure functions.
- **Files.** New `scripts/py_packages.py`, `tests/unit/scripts/test_py_packages.py`.
- **Interface.**
  ```python
  def read_blob(checkout: Path, rel: str) -> str | None          # text of a tracked file in the checkout, None if absent
  def package_roots(tree: frozenset, checkout: Path) -> list[dict]
      # [{"root": "src", "package": "shopcart"}]; a package is a directory with __init__.py whose parent is "" or "src"
      # (or a folder named in [tool.hatch.build.targets.wheel].packages, [tool.setuptools].packages / package-dir,
      # [tool.poetry].packages "from"); folders matching gather.TEST_RE or gather.noise_reason are excluded
  def loose_modules(tree, roots) -> list[str]                    # tracked .py files outside every package
  def console_scripts(checkout) -> list[dict]                    # [{"name", "target", "line", "path": "pyproject.toml", "group": "scripts"|"gui-scripts"|<entry-point group>}]
  def importlinter_contracts(checkout) -> dict                   # {"path": cfg file or None, "root_packages": [...], "contracts": [{"name", "type", "path", "line", ...type keys}]}
  def vulture_config(checkout) -> dict                           # {"ignore_names": [...], "ignore_decorators": [...], "exclude": [...], "min_confidence": int}
  def test_configs(checkout, tree) -> list[dict]                 # D2 tests "config" items
  ```
- **Steps.** Use `tomllib` for TOML and `configparser` for INI. Line numbers for `console_scripts` and contracts: the first line in the file whose text contains the key's name (`shopcart =`) or the contract's `name = "…"` value. Contract keys kept: `layers`, `containers`, `source_modules`, `forbidden_modules`, `modules`, `ignore_imports`. INI list values are split on newlines and stripped (import-linter's INI form). Missing or unparsable files give empty results (never raise), and `importlinter_contracts` adds `"error": "<message>"` when a file exists but cannot be parsed.
- **Tests.** On a copy of `PYFIX` (no git needed): roots `[{"root": "src", "package": "shopcart"}]`; `tests` not a package; `console_scripts` gives `shopcart` → `shopcart.cli:main` at `line_of(..., "ep-script")`; contracts: one `layers` and one `independence`, with the layers in order; `vulture_config` defaults; `test_configs` has pytest (`testpaths`) and coverage (`fail_under` 80). Extra cases in `tmp_path`: a flat layout (`pkg/__init__.py` at the root); `.importlinter` INI with a multi-line `layers`; a broken `pyproject.toml` gives empty results plus `error`.
- **Done-check.** Full suite passes.
- **Commit.** `feat(dossier): read Python package layout, scripts and import rules from project files`

### M2-5. The grimp and vulture worker (`py_worker.py`, `py_tools.py`)

- [x] **Goal.** Locked worker plus clients producing `graph` (packages) and `dead` items.
- **Files.** New `scripts/py_worker.py`, `scripts/py_worker.py.lock`, `scripts/py_tools.py`, `tests/unit/scripts/test_py_tools.py`, `tests/integration/scripts/test_py_worker.py`; edit `tests/unit/scripts/test_shared_tools.py` (the pin test also covers `py_worker.py`).
- **Worker.** Header `# /// script` / `# requires-python = ">=3.10"` / `# dependencies = ["grimp==3.17", "vulture==2.16"]` / `# ///`. Reads one JSON request on stdin, writes one JSON object on stdout, nothing else on stdout.
  - `{"mode": "graph", "roots": [abs paths], "packages": [...], "contracts": [...]}` → `{"modules": [{"module", "path", "is_package"}], "imports": [{"from", "to", "lines": [...]}], "contracts": [{"name", "type", "status", "violations": [{"from", "to", "line"}], "reason"}], "errors": [...]}`. Module paths are computed from the name and the roots (`<root>/a/b.py` or `<root>/a/b/__init__.py`), never by importing. Imports from `graph.find_matching_direct_imports("**")` if available, else by iterating `graph.modules` with `graph.find_modules_directly_imported_by(m)`; lines from `get_import_details` (empty when none). Contracts: `layers` via `find_illegal_dependencies_for_layers(layers=..., containers=set(...) or None)` (each `PackageDependency`'s routes give `from`/`to` and the first import's line, read with `get_import_details`); `forbidden` via `chain_exists(importer=s, imported=f, as_packages=True)` for every source and forbidden module, a chain becoming a violation with its first link; any other type → `status: "not-checked"`, `reason: "dossier checks only layers and forbidden contracts."`. Results are sorted so the output is deterministic despite grimp's ordering.
  - `{"mode": "dead", "paths": [...], "ignore_names", "ignore_decorators", "min_confidence"}` → `{"items": [{"path", "line", "end_line", "name", "type", "confidence", "message"}]}` using the attribute names M2-1 recorded.
- **Clients.**
  ```python
  class Grimp:
      def __init__(self, run, timeout): ...
      def graph(self, roots: list[str], packages: list[str], contracts: list[dict]) -> dict   # worker response
  class Vulture:
      def __init__(self, run, timeout): ...
      def dead(self, paths: list[str], config: dict) -> list[dict]
  ```
  Both call the worker like `shared_tools._call` (reuse it: `shared_tools._call(run, "grimp", "py_worker.py", req)`; add a `timeout` parameter to `_call` that is passed to `run` when given).
- **Locking.** `uv lock --script scripts/py_worker.py`; commit the lock.
- **Tests.** Unit: a fake `run` returning prepared stdout files checks the request JSON and parsing for both clients, and `ToolError` on non-zero and timeout; the pin test: the `dependencies` line of `py_worker.py` names exactly the `tools.json` versions of grimp and vulture. Slow (`DOSSIER_SLOW=1`), on `py_repo`, calling the worker through `sandbox.run` with a scratch area: modules include `shopcart.core`, `shopcart.a`, `shopcart.b`; imports include `shopcart.a → shopcart.b` at `line_of("cycle-a")` and `shopcart.core → shopcart.cli` at `line_of("import-up")`; the `cli above core` contract is `broken` with a violation `shopcart.core → shopcart.cli`; `apps apart` is `not-checked`; `dead` includes `unused_helper` at `line_of("dead-func")`; afterwards `<checkout>/.grimp_cache` does not exist.
- **Done-check.** Full suite passes; `DOSSIER_SLOW=1 uv run --with pytest --with pygments python -m pytest tests/integration/scripts/test_py_worker.py -v` passes.
- **Commit.** `feat(dossier): add the locked grimp and vulture worker`

### M2-6. Graph helpers (`graphs.py`)

- [x] **Goal.** Standard-library graph code used by the adapter, the measured cards and `candidates`.
- **Files.** New `scripts/graphs.py`, `tests/unit/scripts/test_graphs.py`.
- **Interface.**
  ```python
  def cycles(edges: list[tuple[str, str]]) -> list[list[str]]        # strongly connected components of size > 1 (Tarjan, iterative), each sorted, list sorted
  def pagerank(nodes, edges, damping=0.85, rounds=50) -> dict[str, float]   # edges point from importer to imported; dangling mass spread evenly
  def communities(nodes, edges, rounds=20) -> dict[str, str]          # label propagation, undirected, sorted visiting, ties to the smallest label
  def aggregate(edges, group_of: dict[str, str]) -> dict[tuple[str, str], int]   # edge counts between groups, self-pairs dropped
  ```
- **Tests.** A 3-cycle and a 2-cycle plus a tail give exactly two cycles; a self-import is ignored; PageRank sums to 1 and ranks a hub above leaves; communities of two disconnected triangles are two labels; results are identical across two runs and with shuffled input; `aggregate` drops edges inside a group and sums the rest.
- **Done-check.** Full suite passes.
- **Commit.** `feat(dossier): add graph helpers for cycles, ranking and communities`

### M2-7. Semgrep rules, their tests, and the worker's metavariables and test mode

- [x] **Goal.** D5 and D6 rule files, each proven to fire and not to fire.
- **Files.** New `rules/python/{entry,inputs,outputs,state,concurrency,resilience,observability,blindspot}.yml`, `rules/all/blindspot.yml`, `tests/fixtures/semgrep/python/<same names>.py`, `tests/fixtures/semgrep/all/blindspot.py`; edit `scripts/semgrep_worker.py`, `scripts/shared_tools.py` (`Semgrep.test`), `rules/README.md` (list the categories); new `tests/unit/scripts/test_rules.py`; edit `tests/integration/scripts/test_shared_layer.py`.
- **Steps.** (1) Write the rules as D5/D6 describe. Each rule has `metadata: {category: ..., kind: ... (entry rules), pattern: ... (blind-spot rules), detail: <metavariable name or omitted>}`. (2) Write the target files with `# ruleid:` and `# ok:` cases for every rule. (3) Worker: each result gains `"metavars": {name: value["abstract_content"] for name, value in extra.get("metavars", {}).items()}`; a request with `"test": true` runs `[semgrep, "--test", "--config", config, targets]` and returns `{"returncode": r.returncode, "output": r.stdout + r.stderr}` without raising on a non-zero code. (4) `Semgrep.test(config, targets) -> dict`. (5) `rules/README.md`: add the list of categories and blind-spot ids, and the sentence "Each rule file has a test file under `tests/fixtures/semgrep/` with the same name; run `semgrep --test` through the worker (see `tests/integration/scripts/test_shared_layer.py`)."
- **Tests.** Unit (`test_rules.py`, no network): the D5 checks (ids, prefixes, uniqueness, a `ruleid` annotation per id, known categories, every blind-spot rule's `pattern` in the D6 list). Slow: `Semgrep(run).test(SKILL/rules, SKILL/tests/fixtures/semgrep)` returns `returncode == 0` (print `output` on failure).
- **Done-check.** Full suite passes; the slow test passes.
- **Commit.** `feat(dossier): add the Python and repository-wide semgrep rules with tests`

### M2-8. Tree-sitter queries for models, tests, state and imports (`py_queries.py`)

- [x] **Goal.** The parts of `models`, `tests`, `io_candidates` (module-level state) and `graph` (loose modules) that come from syntax trees.
- **Files.** New `scripts/py_queries.py`, `tests/unit/scripts/test_py_queries.py`, `tests/integration/scripts/test_py_queries_slow.py`.
- **Interface.**
  ```python
  CLASS_Q, FIELD_Q, DECORATOR_Q, IMPORT_Q, MODULE_ASSIGN_Q, TEST_Q   # query strings
  def models(ts, files) -> list[dict]          # D2 entity items without id/group; migrations from paths (alembic */versions/*.py, django */migrations/[0-9]*.py)
  def tests(ts, test_files, module_paths: dict[str, str]) -> list[dict]   # D2 "test-file" items
  def module_state(ts, files) -> list[dict]    # io_candidates items, category "global-state", rule "dossier.python.state.module-mutable"
  def imports(ts, files, module_paths) -> list[dict]   # graph "import" items, via "tree-sitter", for the given files
  # pure helpers, unit-tested with hand-made match lists:
  def assemble_models(class_matches, field_matches, decorator_matches) -> list[dict]
  def assemble_tests(matches_by_file, module_paths) -> list[dict]
  ```
- **Rules.** Model kinds from bases and decorators (D2): `BaseModel`/`BaseSettings` → pydantic; `@dataclass`/`@dataclasses.dataclass` → dataclass; `@attrs.define`/`@attr.s`/`@define` → attrs; base text ending in `Model` with `models.` prefix → django; a base named `Base`, `DeclarativeBase` or a class body with `__tablename__` → sqlalchemy; `TypedDict` → typeddict; `NamedTuple` → namedtuple; `Enum`/`IntEnum`/`StrEnum`/`Flag` → enum. Other classes are not models. Fields: annotated assignments in the class body (enum: plain assignments), with `ref` set when the type or value names another model in the same output (`list[Item]` → `Item`) or the value calls `ForeignKey("X")`/`relationship("X")`. Tests: `def test_*`/`async def test_*` count as tests, `class Test*` as classes, decorators containing `skip` as skips and `xfail` as xfails, `mock.`/`patch(`/`MagicMock`/`monkeypatch` in the file as mocks (count of calls), `@pytest.fixture` as fixtures; `framework` = `unittest` when a class base is `unittest.TestCase` or `TestCase`, else `pytest`.
- **Tests.** Unit: assembly from hand-made matches. Slow on `py_repo`: `models` gives exactly `Item` (dataclass, fields `sku`, `price`), `Status` (enum, field `OPEN`), `Order` (pydantic, `items` with `ref: "Item"`, `status` with `ref: "Status"`) at their marker lines; `tests` gives one file `tests/test_core.py` with `tests: 3`, `skips: 1`, `fixtures: 1`, `mocks >= 1`, `paths` containing `src/shopcart/core.py`; `module_state` gives `CART` and `REGISTRY` (not `DB`, whose value is a call, and not `__version__`).
- **Done-check.** Full suite passes; the slow test passes.
- **Commit.** `feat(dossier): extract Python models, tests and module state with tree-sitter`

### M2-9. scip-python: install, run and decode (`scip_tool.py`, `scip_read.py`)

- [x] **Goal.** `symbols` items from a pinned, locked scip-python.
- **Files.** New `scripts/node/scip-python/package.json`, `scripts/node/scip-python/package-lock.json`, `scripts/scip_tool.py`, `scripts/scip_read.py`, `tests/unit/scripts/test_scip_read.py`, `tests/unit/scripts/test_scip_tool.py`, `tests/integration/scripts/test_scip_slow.py`; edit `scripts/tools.json` (`"node_lock": "node/scip-python"` on the scip-python entry), `scripts/sandbox.py` (profile `tool` sets `npm_config_cache=<cache root>/.dossier-tools/npm`), `tests/unit/scripts/test_sandbox.py`.
- **Lockfile.** `package.json`: `{"name": "dossier-scip-python", "private": true, "dependencies": {"@sourcegraph/scip-python": "0.6.6"}}`. Generate the lock in a scratch copy with `npm install --package-lock-only --ignore-scripts --no-audit --no-fund` and copy `package-lock.json` back. A unit test asserts the lock's `packages["node_modules/@sourcegraph/scip-python"].version == tools.json` pin.
- **Interface.**
  ```python
  # scip_tool.py
  def install_dir(cache_root: Path, version: str) -> Path   # <cache root>/.dossier-tools/node/scip-python-<version>
  def ensure_installed(run, cache_root, version, timeout) -> Path   # runs npm ci once (marker file .installed with the lock's sha1); returns the index.js path
  def environment(checkout: Path) -> list[dict]             # from .venv/lib/python*/site-packages/*.dist-info (METADATA Name/Version, RECORD file list); [] without .venv
  def run_index(run, index_js, checkout, area, repo_name, sha, timeout) -> Path   # writes area/scip/env.json, runs node ... (profile "restricted"), returns area/scip/index.scip
  # scip_read.py
  def decode(data: bytes) -> dict    # {"documents": [{"path", "occurrences": [{"range": [l0, c0, l1, c1], "symbol", "roles"}], "symbols": [{"symbol", "kind", "display_name"}]}]}
  def reduce(index: dict) -> list[dict]   # D2 "def" and "ref-edge" items; local symbols ("local ...") skipped
  def descriptor_type(symbol: str) -> str  # "#" class, "()." method/function, "." variable, "/" module
  ```
- **Decoding.** Wire types 0 (varint), 1 (64-bit, skip), 2 (length-delimited), 5 (32-bit, skip). `range` (field 1) may be packed (wire type 2) or repeated varints; also read `single_line_range` (8) and `multi_line_range` (9) when present. A 3-element range means `[line, start, end]` on one line. Lines become 1-based in `reduce`. A definition is an occurrence with `roles & 1`; its `end_line` is from `enclosing_range` (7) when present, else its own range. A reference edge is counted for each non-definition occurrence whose symbol is defined in another document of the index.
- **Tests.** Unit: a tiny encoder in the test file builds an index of two documents (one defines `pkg/a.py` symbol `scip-python python pkg 1.0 pkg/a/f().` at line 3, the other references it twice); `decode` and `reduce` give one `def` (`type: "function"`, `public: true`, `refs: 2`) and one `ref-edge` with `count: 2`; unknown fields are skipped; `descriptor_type` on the four suffixes; `environment` on a hand-made `.venv` folder. `scip_tool` with a fake `run`: `ensure_installed` runs `npm ci` once and not again when the marker matches; `run_index` passes `--output` inside the area and profile `restricted`. Slow on `py_repo`: real install and run; the defs include `shopcart.core` `total` (public) and `unused_helper`; a `ref-edge` from `src/shopcart/cli.py` to `src/shopcart/core.py` exists; no `index.scip` appears in the checkout.
- **Done-check.** Full suite passes; the slow test passes.
- **Commit.** `feat(dossier): run a locked scip-python and read its index`

### M2-10. The repository-wide adapter (`repo_adapter.py`)

- [x] **Goal.** Section 3 item 2: language-independent entry points, SQL tables, CI test commands and the `rules/all` scan.
- **Files.** New `scripts/repo_adapter.py`, `tests/unit/scripts/test_repo_adapter.py`.
- **Interface.** `class RepoAdapter(Adapter)`: `name = "repo"`, `version = "1"`, `languages = ("*",)`, `tools = ("semgrep",)`. `extract(ctx)` returns `entry_points`, `models` (sql tables and sql migrations), `tests` (ci-command items) and `blindspots` (from `ctx.semgrep.scan(SKILL/rules/all)`). Pure helpers, each `(path, text) -> list[dict]`: `dockerfile_entries` (`CMD` and `ENTRYPOINT`, kind `container`, `target` = the command), `makefile_targets` (lines matching `^([A-Za-z0-9_.-]+):(?!=)` that are not special targets such as `.PHONY`, kind `make-target`), `workflow_entries` (in `.github/workflows/*.yml` and `.gitlab-ci.yml`: `cron:` lines → kind `ci-schedule`, `name` = the cron text; test commands containing `pytest`, `tox`, `nox`, `make test` on `run:` lines or `script:` items → `tests` `ci-command` items), `systemd_units` (`*.service`, `*.timer` files: `ExecStart=` line, kind `systemd-unit`), `sql_tables` (`CREATE TABLE [IF NOT EXISTS] name` → `models` kind `sql-table`; files under a `migrations/` folder → `migration` items with tool `sql`), `shebang_scripts` (tracked files with mode `100755` from `git -C <checkout> ls-tree -r <sha>` whose first line starts with `#!`, kind `shebang-script`, line 1). Each item gets `rule = "repo." + kind` and a `snippet` (the line).
- **Tests.** Each helper on small strings; `extract` with a fake context on a copy of `PYFIX` (fake `semgrep.scan` returning `[]`): entry points for the Dockerfile `CMD` (marker + 1), `test` in the Makefile, the cron line, and `scripts/seed.sh` at line 1; a `sql-table` `orders`; a `ci-command` `pytest -q`.
- **Done-check.** Full suite passes.
- **Commit.** `feat(dossier): add the repository-wide adapter for containers, make, CI, systemd and SQL`

### M2-11. The Python adapter (`py_adapter.py`) and registration

- [x] **Goal.** One adapter producing all eight outputs for Python, with per-tool status, registered with `RepoAdapter`.
- **Files.** New `scripts/py_adapter.py`, `tests/unit/scripts/test_py_adapter.py`, `tests/integration/scripts/test_py_adapter_slow.py`; edit `scripts/adapters.py` (`ADAPTERS = (PythonAdapter, RepoAdapter)`, imported at the end of the module to avoid a cycle: `from py_adapter import PythonAdapter` and `from repo_adapter import RepoAdapter` inside a function `_registered()` that `detect` uses when `adapters is ADAPTERS`; keep `ADAPTERS` a tuple for tests), `scripts/stages.py` (nothing else: `stage_extract` already calls `adapters.detect(langs)`).
- **Interface.** `class PythonAdapter(Adapter)`: `name = "python"`, `version = "1"`, `languages = ("Python",)`, `tools = ("grimp", "vulture", "scip-python", "semgrep", "tree-sitter-language-pack")`, `expected_untracked = (".venv/**",)`. `extract(ctx)` runs, each step in its own `try` that records `ctx.tool_status[tool]` (`ok`, or `failed` with the first line of the error, or `skipped` with a reason):
  1. `py_packages` reads (never fails the adapter).
  2. **grimp** (when there are packages; else `skipped`, "No Python package was found, so imports were read from the files directly."): `graph` modules, imports, contracts; cycles from `graphs.cycles` over the module import pairs.
  3. **tree-sitter**: imports of loose modules (merged into `graph`, `via: "tree-sitter"`), models, tests, module state.
  4. **semgrep** (`rules/python`): results become `entry_points` (rules in `entry.yml`, `kind` from metadata, `name` from the decorator path or function name, `trigger` from fixed text per kind, `target` = `module:function` of the decorated function where it can be found from `symbols` defs or the snippet), `io_candidates` (category from metadata, `detail` from the named metavariable), `blindspots` (rules in `blindspot.yml`).
  5. **console scripts** and `__main__.py` files → `entry_points` (kinds `console-script`, `main-module`).
  6. **vulture** → `dead` (ignore files matching `gather.TEST_RE`).
  7. **scip-python** → `symbols` (`skipped` with "The ref is not trusted, so Node tools did not run. Use --allow-ref to run them." when `not ctx.trusted`; `skipped` "Node is not installed." when `shutil.which("node")` on the sandbox `PATH` is `None`).
- **Tests.** Unit: with `ctx.run`, `ctx.treesitter` and `ctx.semgrep` faked, one tool raising `ToolError` leaves the others' outputs and marks that tool `failed`; `trusted=False` skips scip-python with the fixed reason; semgrep results are routed to the right outputs by rule file. Slow (`DOSSIER_SLOW=1`), the **fixture test of record**: run the real `stages.stage_extract` on `py_repo` (after `workarea.ensure_checkout`) with `DOSSIER_*` under `tmp_path`, then assert on `extract/*.json`:
  - `entry_points` kinds and lines: `console-script` `shopcart` (`ep-script`), `main-module` (`ep-main-module`), `main-guard` (`ep-guard`), two `http-route` (`ep-route`, `ep-route2`), `container` (`ep-docker` + 1), `make-target` (`ep-make`), `ci-schedule` (`ep-cron`), `shebang-script` (`scripts/seed.sh`, 1). **Exactly these ten**, no more.
  - `graph`: the `a ↔ b` cycle; the broken `cli above core` contract; `apps apart` not checked.
  - `io_candidates`: at least the categories `cli-args` (`io-cli`), `stdout` (`io-print`), `exit-code` (`io-exit`), `log` (`io-log-get`, `io-log`), `catch-all` (`fail-catchall`), `env-var` with `detail` `"SHOP_DB"` (`io-env`), `db-connect` (`io-db-connect`), `file-write` (`io-file-write`), `file-read` (`io-file-read`), `outbound-call` and `timeout` (`io-outbound`), `global-state` (`state-module`, `state-registry`), `lock`, `thread`, `async` (`cc-*`); and **no** `file-read` at `io-file-write`.
  - `models`: `Item`, `Status`, `Order`, `orders` (sql-table).
  - `tests`: the test file, the pytest and coverage configs, the CI command.
  - `dead`: `unused_helper`.
  - `blindspots`: `dynamic-import` (`bs-import`), `getattr-dispatch` (`bs-getattr`), `decorator-registry` (`bs-registry`), `pytest-fixtures` (`bs-fixture`).
  - `symbols`: defs and the `cli.py → core.py` ref-edge.
  - Every candidate item has `id` and `group`; a second `stage_extract` is `reused`; the record's `details.adapters` has both adapters with `tools` statuses all `ok`; the checkout has no untracked files (`git status --porcelain` empty) and no `.grimp_cache`.
- **Done-check.** Full suite passes; `DOSSIER_SLOW=1 uv run --with pytest --with pygments python -m pytest tests/integration/scripts/test_py_adapter_slow.py -v` passes.
- **Commit.** `feat(dossier): add the Python adapter and register both adapters`

### M2-12. `dossier candidates`

- [x] **Goal.** The command Claude uses to see the tool findings for a report, and what is still undecided.
- **Files.** Edit `scripts/candidates.py` (second part), `scripts/dossier.py` (subcommand, docstring line); new `tests/unit/scripts/test_candidates_cli.py`.
- **Interface.**
  ```python
  CATEGORY_CARD = {...}                         # D3
  def home_card(output: str, item: dict) -> str | None   # entry_points -> entry.catalog; io by category; entity models -> data.entities; else None
  def for_report(rid, extract) -> dict[str, list[dict]]   # home card id -> its candidate items
  def dispositions(reports) -> dict[str, list[tuple]]     # id -> [(report, card, "kept"|"dismissed")]
  def open_items(rid, extract, reports) -> list[dict]     # candidates of rid's home cards with no disposition (by id or group)
  def component_candidates(tree, extract, facts) -> dict  # D4: folders, packages, communities
  def catalog_edges(catalog_rows, extract) -> list[dict]  # D4: component edges for drafted Paths
  def text(rid, extract, reports, facts, *, only_open=False, catalog=None) -> str
  ```
  CLI: `dossier.py candidates [REPO] --report ID [--open] [--catalog FILE] [--json]`. Reads `<out>/extract/` and `<out>/reports/`. Text layout per home card: a heading line `== {card id} ({card title}): {n} findings in {g} groups ==`, then one line per group: `{group id}  {rule}  {path}  ({k} hits: lines a, b, c)` and, indented, one line per hit `{id}  {path}:{line}  {snippet}`. For `--report components`: the three candidate lists of D4 with file and line counts. For `--report reading`: the top 30 modules by PageRank with their files, the entry-point files and the test files. With `--open`: only undecided candidates, and nothing at all when none are open. With `--catalog`: the measured edges, sizes and files with no component, for the drafted `components.catalog`. With `--json`: the same as data.
- **Tests.** On a hand-made `extract` (two io groups, one entry point) and a report that keeps one id, dismisses one group: `open_items` returns the rest; `--open` text lists only them; group dispositions cover all members; `home_card` for each D3 category; `component_candidates` on a small tree; `catalog_edges` counts imports between two drafted components.
- **Done-check.** Full suite passes; `uv run scripts/dossier.py candidates --help` shows the options.
- **Commit.** `feat(dossier): add the candidates command`

### Deliverables and checks (Phase 1)

| Deliverable | Checked by |
|---|---|
| Tool facts re-checked | M2-1 results lines |
| Ids, tool status, wildcard adapters | `test_candidates.py`, `test_extract.py` |
| Fixture repository | `test_pyfixture.py` |
| grimp, vulture, scip-python, tree-sitter, semgrep outputs | the slow tests of M2-5, M2-7, M2-8, M2-9 |
| Both adapters on the fixture | `test_py_adapter_slow.py` (the fixture test of record) |
| `dossier candidates` | `test_candidates_cli.py` |

### Cut line (Phase 1)

If the session runs short, move to Phase 2, in this order, and record it under "Results (Phase 1)": (1) M2-12's `--report reading` and `--catalog` options (keep the rest of `candidates`); (2) the `forbidden` contract check (report it as `not-checked`); (3) `systemd_units` and `shebang_scripts` in M2-10. **Never cut:** M2-2, M2-3, the slow fixture tests of M2-5, M2-7, M2-8, M2-9 and M2-11. If scip-python cannot be made to work (M2-1 or M2-9 stop condition), the adapter records it as `failed` with the reason and Phase 2 starts; the cards it feeds will be partial (record this as a deviation and tell the human).

### Acceptance criteria (Phase 1)

- The full suite passes, and with `DOSSIER_SLOW=1` every new slow test passes.
- `test_py_adapter_slow.py` shows exactly the expected entry points and the other expected items on the fixture.
- Running `prepare` on `py_repo` (by the slow test) leaves the checkout clean, with no `.grimp_cache` and no `index.scip` in it.

### Branch and release (Phase 1)

Commit each task on `feat/dossier-m2`. Do not merge or bump the version. At the end, write "Results (Phase 1)" (date, the M2-1 observations, test counts with and without `DOSSIER_SLOW=1`, the slow tests' run time, anything cut, deviations) and commit it: `docs(dossier): record phase 1 of M2 in plan 007`.

### Results (Phase 1)

Started 2026-11-01 on branch `feat/dossier-m2`. Baseline: `405 passed, 2 skipped` (matches).

**M2-1 observations (2026-11-01, Node v20.19.2):**

1. grimp 3.17: modules `['pkg', 'pkg.a', 'pkg.b']`; `get_import_details` returns dicts with `importer`, `imported`, `line_number`, `line_contents`, `is_lazy`; `find_illegal_dependencies_for_layers` returns a set of `PackageDependency(importer, imported, routes)`; no `.grimp_cache` created with `cache_dir=None`. OK as planned.
2. vulture 2.16: `Vulture(verbose=False, ignore_names=None, ignore_decorators=None)`; items have `filename` (a `PosixPath`, absolute), `first_lineno`, `last_lineno`, `typ`, `name`, `confidence`, `message`. All attribute names as planned. `min_confidence` is an argument of `get_unused_code`, not of the constructor.
3. scip-python 0.6.6: `npm install --ignore-scripts` works (42 packages), bin is `index.js` (`"bin": {"scip-python": "index.js"}`). **Without `--project-version`, in a folder that is not a git repository, it crashes** (`normalizeNameOrVersion` on an undefined version) and leaves a 54-byte `out.scip` behind with exit 1. With `--project-version abc123` it exits 0 and writes a 1,075-byte index. D1's command already passes `--project-version <sha>`, so the plan holds; the adapter must always pass it and must treat a non-zero exit as `failed` even when a file exists.
4. **semgrep 1.181.0: contradicts the plan.** Without a Semgrep login, `extra.lines` and `extra.fingerprint` are the string `"requires login"` and `extra.metavars` is absent, with or without `--oss-only` and with `--dataflow-traces`. Consequences: (a) D2's `detail` cannot come from metavariables (M2-7 step 3); (b) the M1 worker's `snippet` (`extra.lines`) is `"requires login"` for every result, and D2 ids hash `snippet`, so they would depend on the ordinal only. The result does carry `start`/`end` (line, col, offset), so the real text can be read from the file.

**Item 4 decision (2026-11-01, the human): read the text from the source file.** Done in M2-7: `semgrep_worker.py` now returns `snippet` = the stripped source line where the match starts (at most 200 characters; this also fixes M1's "requires login" snippet) and `detail` = the first group of the regex in the rule's `metadata.detail` applied to the matched text (read by byte offsets), else `null`. Rules that need a detail carry `metadata.detail` as a regular expression, not a metavariable name. Semgrep's `metavariable-regex` is anchored at the start of the value, so the rules use `.*(...)` where a suffix or infix match is meant. A generic rule's own test annotation matches its pattern, so `dossier.all.blindspot.feature-flag` has `(?<!blindspot\.)` in its regex.

**M2-7 notes.** 44 rules (42 in `rules/python`, 2 in `rules/all`), all pass `semgrep --test`. Stacked `# ruleid:` comments do not work (each annotation applies to the next line); a line that two rules match carries one comma-separated annotation (`string-plugin` lines are also `dynamic-import` matches).

**M2-8 deviations.** (1) Three-level tree-sitter patterns (`module > expression_statement > assignment`) match nothing with tree-sitter-language-pack 1.22.1, while one- and two-level patterns work (probed on the fixture). The queries are therefore one or two levels deep, and `py_queries` tells module level from class level by column: a module-level name starts at column 0, a class field starts at the column of the class `body` block (`CLASS_Q` now also captures `body`). (2) D5 says all-capitals module values are constants and are skipped, but the fixture (M2-3) and the tests of record (M2-8, M2-11) expect `CART = {}` and `REGISTRY = {}` to be found. Resolved as: an all-capitals name is a constant only when its value is not empty (`{}` or `[]`); an empty container is taken as state. The ids of module-state findings use `snippet = "<name> = <first line of the value>"` because the worker returns captured nodes, not source lines.

**M2-11 notes and deviations.** (1) The plan says "exactly these ten" entry points but lists nine markers (`ep-script`, `ep-main-module`, `ep-guard`, `ep-route`, `ep-route2`, `ep-docker`, `ep-make`, `ep-cron`, `ep-shebang`); the fixture test asserts exactly those nine. (2) Semgrep's default ignore list skips `tests/`, `vendor/` and similar folders when it walks a directory, so `pytest-fixtures` in `tests/` was never found; it does scan a file named on the command line. Both adapters now pass explicit file lists (the Python adapter: every tracked, non-noise Python file; the repository adapter: every tracked, non-noise file of kind `code`), and `semgrep_worker.py` sends them in batches of 400. (3) `adapters.ADAPTERS` stays an empty tuple; `detect(languages, adapters=None)` takes the shipped adapters from `_registered()`, which imports both modules on first use (a top-level import would cycle). (4) `repo` is always registered, so `prepare` on a repository now always runs two adapters and the `extract` step is `ok` even when every tool fails: `test_prepare_cli.py` expected `skipped` (M1, no adapters) and now checks the two adapters instead. Those CLI tests add about 6 seconds each to the default suite (the fake `uv` makes every tool call fail fast). (5) Module names for files under a package root drop the root (`src/shopcart/x.py` is `shopcart.x`) when grimp gave no module list.


**M2-12 notes.** `candidates.py` passed 300 lines, so the component model (D4: `component_of`, `catalog_rows`, `catalog_edges`, `component_candidates`, `parse_paths`, `file_lines`, `source_files`) moved to a new `scripts/components.py`; `candidates` re-exports those names, so the interface in the plan is unchanged. V4 (M2-15) should import `component_of` from there: it already implements "most specific wins" and reports a tie as `(first name, [other names])`. `schema/questions.json` is a list, not a report schema; `candidates.card_titles` skips it.

**Phase 1 summary (2026-11-01).**

- Branch `feat/dossier-m2`, one commit per task (M2-1 to M2-12), not merged, version unchanged (0.6.0).
- Tests: baseline `405 passed, 2 skipped`; now `800 passed, 36 skipped` by default and `836 passed` with `DOSSIER_SLOW=1`. The slow run takes about 2 min 50 s on this machine (the first run also downloads grimp, vulture, semgrep, tree-sitter and scip-python's npm packages).
- Cut: nothing. `--report reading`, `--catalog`, the `forbidden` contract check, `systemd_units` and `shebang_scripts` are all in.
- Acceptance: the fixture test of record (`test_py_adapter_slow.py`) shows exactly nine entry points and every other expected item on the fixture; a second `stage_extract` is `reused`; the checkout is clean, with no `.grimp_cache` and no `*.scip`.
- Report 02 and the card schemas were not touched; `render.py` was not edited, so block E was not needed.

**Deviations from the plan (all described above under the task that caused them):** semgrep hides matched text and metavariables without a login, so `snippet` and `detail` are read from the source file (decided by the human); one `ruleid` annotation per line, comma-separated; three-level tree-sitter patterns match nothing, so module and class level are told apart by column; an empty all-capitals container counts as module state (the fixture needs it); the plan's "ten" entry points are nine; semgrep gets explicit file lists (its default ignore list skips `tests/`); `ADAPTERS` is registered lazily; `prepare` always runs the `repo` adapter, so M1's CLI test now expects `extract` to be `ok`; `components.py` was split out of `candidates.py`.

**Things Phase 2 should know.** (1) `scip_read` reads the typed ranges (SCIP fields 8 and 9) as packed numbers, a guess that nothing exercises: scip-python 0.6.6 never writes them. (2) The default suite is about 18 seconds slower because three `prepare` CLI tests now run both adapters against a fake `uv` (every tool call fails fast, which also proves a failing tool never stops the build). (3) `tool_status` for `grimp`, `vulture`, `scip-python`, `semgrep` and `tree-sitter-language-pack` is in `extract/*.json` and in the `extract` record at `details.adapters[*].tools`, which is what M2-18 (the "partial" badge) reads. (4) `entry_points` items for decorated functions have `line` at the decorator and `target` as `module:function`; `console-script` items point at `pyproject.toml`.

---

## Phase 2: Dispositions, measured cards, V4, V5, "partial" and staleness

### Before you start (Phase 2)

1. Read section 2, then sections 3 and 4 (D3, D4, D7, D8, D10 closely). Load the skills listed in section 2.
2. Run `git log --oneline -20` and read "Results (Phase 1)". Confirm that M2-1 to M2-12 are ticked; anything cut from Phase 1 is done first in this phase, before M2-13, as its own task with its own commit. If scip-python was recorded as not working, continue (its cards are partial) and keep that in mind for section 6.
3. Run the full suite once; record the count.

Independent tasks: M2-13 and M2-16 (measured cards) and M2-18 (partial) are independent of each other. M2-14 needs M2-13. M2-15 needs M2-14. M2-17 needs M2-16. M2-19 needs M2-12. M2-20 needs M2-14 and M2-15.

### M2-13. Card keys for dispositions and the unassigned list; how they show on the page

- [x] **Goal.** D3 and D4 keys are accepted by V6 and drawn.
- **Files.** Edit `scripts/schema.py` (`ENTRY_KEYS |= {"dismissed", "unassigned"}`; nothing else), `scripts/render.py` (`render_table` and `entries_body`: an "added by Claude" badge `badge("added by Claude", "", "outline")` in the Basis cell of a row or entry with `added: true`; `schema_cards_html` passes the card entry to a new `candidate_footer(card, entry, fed)`), `tests/unit/scripts/test_schema.py`, `tests/unit/scripts/test_render_cards.py`.
- **Footer.** `render.candidate_footer(card, entry, fed) -> str`, where `fed` is the number of candidates whose home is this card (from `ctx["fed"]`, filled by `cmd_render` via `candidates.for_report`): empty when `fed` is 0; else `<p class="muted cand-foot">Tool findings: {fed} found, {kept} kept in {rows} rows, {dismissed} dismissed{, {added} rows added by Claude}.</p>` followed by `<details><summary>Dismissed findings</summary><ul>` with one `<li>` per dismissed entry: its ids in `<code>` and the reason escaped (`render.E`), not passed through `inline`.
- **Tests.** V6 accepts a card entry with `dismissed` and a catalog with `unassigned`; still rejects other unknown keys; the badge appears for `added` rows; the footer counts on a hand-made card; a dismissed reason containing `[[x]]` is shown literally.
- **Done-check.** Full suite passes; block E prints `OK`.
- **Commit.** `feat(dossier): accept and show tool-finding decisions on cards`

### M2-14. V5 and its Gaps items (`checks.py`, first part)

- [x] **Goal.** D3's V5, wired into `render` and `confirm`.
- **Files.** New `scripts/checks.py`, `tests/unit/scripts/test_checks_v5.py`; edit `scripts/dossier.py` (`cmd_render`, `cmd_confirm`), `scripts/render.py` (`render_html(..., extract=None, checks=None)`: puts `extract`, `fed` and check results in `ctx`).
- **Interface.**
  ```python
  def validate(reports, extract, cites, facts, catalog=None) -> dict
      # {"errors": [...], "warnings": [...], "gaps": [items], "counts": {...}, "unbacked": {}}; V5 in this task, more checks added later
  def v5(reports, extract) -> tuple[list, list, list, dict]   # errors, warnings, gap items, counts
  def gap_extras(build, reports, extract, cites, facts) -> list[dict]
      # process.coverage_items(build) + validate(...)["gaps"]: the one list cmd_render and cmd_confirm both pass to collect_gaps
  ```
- **`cmd_render`.** After `render.validate`: `extract = candidates.load(out)`; `res = checks.validate(reports, extract, cites, facts)`; print its warnings and errors with the same `warning:`/`error:` prefixes; add its errors to the blocking count (before the "error(s). Fix the report files" exit). Replace `coverage = process.coverage_items(build)` with `coverage = checks.gap_extras(build, reports, extract, cites, facts)` (it calls `validate` again or reuses `res`; reuse it). Pass `extract=extract, checks=res` to `render_html`. `cmd_confirm` builds the same `coverage` the same way.
- **Tests.** Every V5 rule of D3 with a hand-made extract and reports: an undisposed candidate errors with the fixed text; a group id covers its members; an unknown id errors; kept-and-dismissed errors; a dismissal without a reason errors; `cand` plus `added` errors; a row with neither warns; the fixed-category exception; Gaps items for undisposed groups have the fixed statement and resolve as citations (`path:line`). With no `extract` at all (an old dossier), V5 reports nothing.
- **Done-check.** Full suite passes; block E prints `OK` (its log gains no V5 line: `FIX` has no `extract/`).
- **Commit.** `feat(dossier): check that every tool finding has a decision (V5)`

### M2-15. V4 (`checks.py`, second part)

- [ ] **Goal.** D4's V4 and its Gaps items.
- **Files.** Edit `scripts/checks.py` (`v4`, called from `validate`), new `tests/unit/scripts/test_checks_v4.py`.
- **Interface.** `def v4(reports, tree, facts) -> tuple[list, list, list, dict]`; `def parse_paths(cell: str) -> list[str]` (split on `,` and newlines, strip backticks, `[[...]]` citations become their path); `def best_component(path, patterns) -> tuple[str|None, list[str]]` (the winning component, or the tied ones). The tree comes from `cites.tree()[0]`.
- **Tests.** Most specific wins (`src/app/` versus `src/app/api/`); file beats glob beats directory; a tie between two components errors with the fixed text; an unmatched file errors and the message lists at most five; `unassigned` covers files and adds one Gaps item per entry; a missing detail entry errors; an extra detail entry warns; `na` and `pending` catalogs skip V4; noise files (lock files, generated) are not counted.
- **Done-check.** Full suite passes.
- **Commit.** `feat(dossier): check that every source file belongs to one component (V4)`

### M2-16. Measured cards: Where things live, Formatting and tooling, Cycles and layer violations

- [ ] **Goal.** D8 for `reading.map`, `conventions.tooling`, `interactions.violations`.
- **Files.** New `scripts/measured.py`, `tests/unit/scripts/test_measured.py`; edit `scripts/render.py` (`render_card`: for `writer == "script"`, `body = measured.body(card["id"], ctx, refs)`; when `None`, the placeholder as today; `render_card` gains a `ctx` parameter passed down from `schema_cards_html` and `build_page`).
- **Steps.** Implement the three bodies as D8 says. `build_page` must call `schema_cards_html` for every report whose schema has a card with a body (it now only does so when some card is written by Claude; reports 03 to 12 all have one, so no change is needed there; check it).
- **Tests.** On a hand-made `ctx` (tree, facts with the fixture's files, extract with one cycle, one broken contract and one not-checked contract): each body has the expected rows; empty inputs give the fixed "none found" texts; the bodies contain no unescaped `<` from repository text.
- **Done-check.** Full suite passes; block E prints `OK`.
- **Commit.** `feat(dossier): draw the measured cards for locations, tooling and import violations`

### M2-17. Measured cards: Dependency graph and Component map

- [ ] **Goal.** D8 for `interactions.graph` and `components.map`.
- **Files.** Edit `scripts/measured.py`, `tests/unit/scripts/test_measured.py`.
- **Steps.** Component of a module: `checks.best_component(module path, catalog patterns)` (reuse it). Arrows from `graphs.aggregate`. Mermaid: `flowchart LR`; `subgraph` per area with a quoted label; nodes `mermaid_id(component)["Component name"]`; arrows `A -->|"n imports"| B`; no styling (the page themes it). The edge table lists every import item (sortable, filterable; `render_table(..., plain=True)` with `filterable=True`).
- **Tests.** The Mermaid source for two areas and three components has two `subgraph` lines, three nodes and the right arrows; a module in no component is grouped under "unassigned"; ids are safe (`a-b.c` → `a_b_c`); the table has one row per import.
- **Done-check.** Full suite passes; block E prints `OK`.
- **Commit.** `feat(dossier): draw the dependency graph and component map from the import graph`

### M2-18. The "partial" badge

- [ ] **Goal.** D7.
- **Files.** Edit `scripts/tools.json` (`"cards"` on every tool), `scripts/process.py` (`partial_cards(build, tools=None) -> dict`), `scripts/render.py` (`schema_card(..., partial=None)`; `render_card` looks up `ctx["partial"].get(card["id"])`; `render_html` sets `ctx["partial"] = process.partial_cards(build) if build else {}`), `tests/unit/scripts/test_process.py`, `tests/unit/scripts/test_render_cards.py`, `tests/unit/scripts/test_toolcheck.py` (every card id in `tools.json` exists in the schemas).
- **Tests.** A build whose `tools` record lists `scip-python` missing makes `components.catalog`, `interactions.flows`, `interactions.graph` partial with "Made without scip-python: it is not installed."; a `failed` grimp in `tool_status` makes `reading.order` partial with its reason; a skipped extract makes every mapped card partial; a JS tool missing in a Python-only build makes nothing partial; the badge HTML appears after the tier badge; no build → no badges.
- **Done-check.** Full suite passes; block E prints `OK`.
- **Commit.** `feat(dossier): badge cards made without one of their tools as partial`

### M2-19. Staleness when tool findings change

- [ ] **Goal.** D10.
- **Files.** Edit `scripts/candidates.py` (`FEEDS`, `digest`, `digests`), `scripts/incremental.py` (`plan(..., digest_changed=frozenset())`: each report in it gets the fixed reason), `scripts/dossier.py` (`cmd_prepare` computes `digests = candidates.digests(candidates.load(out))` after `stage_extract` and passes them to `update_plan`; `update_plan(top, out, state, facts, prev_version, full, digests=None)` compares with `state.get("extract_digests", {})`; `cmd_render` stores `state["extract_digests"]` for the reports it rendered), `tests/unit/scripts/test_candidates.py`, `tests/unit/scripts/test_incremental.py`.
- **Tests.** The digest ignores line numbers (shift every line: same digest); a new candidate changes the digest of its home report only; a new import changes `components`, `interactions`, `reading` and `conventions` (graph modules only when a module is added); `plan` adds the reason for a changed digest and not for an equal or missing one; `gaps` follows as today.
- **Done-check.** Full suite passes.
- **Commit.** `feat(dossier): mark a report stale when the tool findings it is built from change`

### M2-20. The process card's check line

- [ ] **Goal.** Section 3 item 30.
- **Files.** Edit `scripts/process.py` (`render_records(..., check_counts=None)` puts them in the `check`/`render` record's `counts`; `_ok_line("check")` adds `Tool findings: {v5_candidates} found, {v5_open} without a decision. Components: {v4} problems.` when the counts exist), `scripts/dossier.py` (pass `res["counts"]`), `tests/unit/scripts/test_process.py`.
- **Done-check.** Full suite passes; block E prints `OK`.
- **Commit.** `feat(dossier): show the tool-finding and component checks on the process card`

### Deliverables and checks (Phase 2)

| Deliverable | Checked by |
|---|---|
| Disposition keys and page markers | `test_schema.py`, `test_render_cards.py` |
| V5 | `test_checks_v5.py` |
| V4 | `test_checks_v4.py` |
| Five measured cards | `test_measured.py`, block E |
| "Partial" badge | `test_process.py`, `test_render_cards.py` |
| Staleness from tool findings | `test_candidates.py`, `test_incremental.py` |

### Cut line (Phase 2)

Move to Phase 3, in this order, recording it under "Results (Phase 2)": (1) M2-20; (2) the module edge table in `interactions.graph` (keep the diagram); (3) the dismissed-findings `<details>` list in the footer (keep the counts). **Never cut:** M2-13, M2-14 (V5 and its tests), M2-15 (V4), M2-18, M2-19.

### Acceptance criteria (Phase 2)

- The full suite passes; with `DOSSIER_SLOW=1`, Phase 1's slow tests still pass.
- Block E prints `OK` after every `render.py` task.
- `render` of a dossier with `extract/` but no reports exits non-zero only for missing reports and V10, never because of a crash in the new code (check with the slow fixture build: prepare `py_repo` in a scratch home, then `render --partial --allow-errors`).

### Branch and release (Phase 2)

Commit each task on `feat/dossier-m2`. Do not merge or bump. Write "Results (Phase 2)" (date, test counts, anything cut, deviations) and commit: `docs(dossier): record phase 2 of M2 in plan 007`.

### Results (Phase 2)

(Filled in by the Phase 2 session.)

---

## Phase 3: V2, V3, V7, prompts, version and the end-to-end run

### Before you start (Phase 3)

1. Read section 2, then sections 3 and 4 (D6, D9, D11, D12 closely). Load the skills listed in section 2, plus `docs-project`, `docs-readme`, `git-release`.
2. Run `git log --oneline -30` and read "Results (Phase 1)" and "Results (Phase 2)". Anything cut from Phase 2 is done first, as its own task.
3. Run the full suite once; record the count.

Independent tasks: M2-21, M2-22 and M2-23 are independent of each other. M2-24 needs them. M2-25 and M2-26 need M2-24. M2-27 needs M2-26. M2-28 is last.

### M2-21. V2

- [ ] **Goal.** D9 V2.
- **Files.** Edit `scripts/checks.py` (`v2(reports, cites)`, called from `validate`), new `tests/unit/scripts/test_checks_v2.py`.
- **Tests.** Using the `git_repo`/`make_cites` fixtures from `tests/conftest.py`: a span present in the cited lines passes; one outside the range warns with the fixed text and gives one Gaps item; a dotted name passes on its last part; `name()` passes on `name`; keywords, built-ins, short lowercase words and tracked paths are skipped; a claim citing only a directory or a `facts:` key is not checked; a whole-file citation searches the whole file.
- **Done-check.** Full suite passes.
- **Commit.** `feat(dossier): check that named identifiers appear in the cited code (V2)`

### M2-22. V3

- [ ] **Goal.** D9 V3, including the note under each diagram.
- **Files.** Edit `scripts/checks.py` (`v3(reports, extract, catalog)`, the parsers `sequence_arrows(src)` and `flowchart_arrows(src)`), `scripts/render.py` (`blocks_body`: after a diagram block whose `(card id, diagram index)` is in `ctx["checks"]["unbacked"]`, append the fixed muted note listing its arrows); new `tests/unit/scripts/test_checks_v3.py`.
- **Tests.** Parsers: participants with `as` aliases; every message arrow form; reply arrows reversed; flowchart chains, labelled edges, node labels with `<br/>`; `subgraph` lines ignored. Resolution: exact module, unique last part, ambiguous last part (unresolved), file path, component name. A backed arrow passes; an unbacked arrow warns, gives a Gaps item and the note; an external participant is not checked; no graph → an info line and no warnings.
- **Done-check.** Full suite passes; block E prints `OK`.
- **Commit.** `feat(dossier): check diagram arrows against imports and calls (V3)`

### M2-23. V7

- [ ] **Goal.** D6 V7 and the fixed coverage item for runtime configuration.
- **Files.** Edit `scripts/checks.py` (`v7(extract)`, called from `validate`; `BLIND_SPOTS = {pattern id: (what it may miss, report)}` from the D6 table), new `tests/unit/scripts/test_checks_v7.py`.
- **Tests.** Two hits of one pattern in one file give one item with `2 place(s)` and the first line's citation; two files give two items; the runtime-configuration item appears once whenever a Python adapter ran; no `blindspots` output gives only that item; statements are byte-identical across two runs (stable Gaps IDs).
- **Done-check.** Full suite passes.
- **Commit.** `feat(dossier): list blind-spot hits in Gaps (V7)`

### M2-24. Reports 10 and 13 optional, pending no longer allowed

- [ ] **Goal.** Section 3 item 23.
- **Files.** Edit `scripts/render.py` (`OPTIONAL_REPORTS = ("change", "contributors")`, with a comment "M3 writes these"), `scripts/schema.py` (`ALLOW_PENDING = False`; update its comment), tests that relied on pending being allowed by default (pass `allow_pending=True` explicitly where a test is about the pending form itself; search with `grep -rn "pending" tests/unit`).
- **Done-check.** Full suite passes; block E now prints V6 "pending is not allowed" errors for `FIX` (expected, `--allow-errors`) and still `OK`. Update block E's expectation text in section 6 if the wording differs.
- **Commit.** `feat(dossier): require every card of the written reports and leave reports 10 and 13 to M3`

### M2-25. Rewrite `prompts/method.md`

- [ ] **Goal.** D11 for `method.md`.
- **Files.** `prompts/method.md`.
- **Steps.** Keep the sections D11 names, with the report names updated (the old names "architecture", "interfaces", "delivery" and so on must not appear). Replace "Report file shape" with "Report file shape: cards", including one complete example of a report file with a table card that keeps, merges, dismisses and adds, an `entries` card, and an `na` card, matching `prompts/schema/README.md`. Add "Tool findings: keep, merge, dismiss", "Components" and "What render checks" (V1 to V7, one plain line each, saying which are errors). In "Citation forms", list the `facts:` keys that still exist (`render.FACT_KEYS`; check the code) and say that the code is cited, never a finding id. In "Reading the repository", keep chunk notes as they are. Write for Claude, in plain sentences.
- **Done-check.** `grep -nE "capabilities|code-tour|domain-logic|delivery|interfaces\b|architecture\b" prompts/method.md` prints nothing; the example report in it passes `schema.validate` (add a unit test `tests/unit/scripts/test_prompts.py` that extracts the first fenced `json` block after the heading "Report file shape: cards" and validates it against the right schema with `allow_pending=False`).
- **Commit.** `docs(dossier): rewrite the method for card reports and tool findings`

### M2-26. Rewrite `prompts/reports.md`

- [ ] **Goal.** D11 for `reports.md`.
- **Files.** `prompts/reports.md`; edit `tests/unit/scripts/test_prompts.py`.
- **Steps.** One section per report in the D11 writing order (`entry`, `components`, `interactions`, `io`, `data`, `behavior`, `conventions`, `ops`, `reading`), then `overview`, `risks`, `gaps`, `corrections`. Each report section lists its cards in schema order with: what goes in it (from spec section 4's Shape and Source columns), the findings `dossier candidates` lists for it and their home card, and for measured cards "drawn by code; do not write it". Keep the fixed rows of `components.cross-cutting`, `io.inputs`, `io.outputs`, `behavior.tests`, `conventions.style` and `conventions.recipes` (from the schemas). Say that `change` and `contributors` are not written in this version. Keep the current `risks`, `gaps` and `corrections` sections, adjusting only the report names they mention.
- **Done-check.** The test asserts that every card id with `writer: claude` in the schemas of reports 03 to 09, 11 and 12 appears in `reports.md`, and that no retired report name appears as a section heading. Full suite passes.
- **Commit.** `docs(dossier): rewrite the report guide for reports 03 to 12`

### M2-27. SKILL.md, README, rules README

- [ ] **Goal.** `/dossier build` works again for Python repositories.
- **Files.** `SKILL.md`, `README.md`, `rules/README.md`, `scripts/dossier.py` (module docstring line for `candidates`, if not already there).
- **Steps.** SKILL.md: remove the interim notice; step 5 lists the D11 order and says reports 10 and 13 are not written in this version; step 3 adds "Run `DOSSIER candidates <repo> --report <id>` before writing each report"; step 6 says render errors starting `V4:` or `V5:` are fixed in the reports (never with `--allow-errors`); the `description` front matter names the new reports in plain words (entry points, components, interactions, inputs and outputs, data, behaviour and tests, conventions, build and run, risks). README: one sentence after the 0.6.0 sentence: "Version 0.7.0 extracts Python entry points, imports, inputs and outputs, data models and tests with tools, writes the reading guide, entry points, components, interactions, inputs and outputs, data model, behaviour, conventions and build reports from them, and checks that every tool finding is accounted for." (Follow `docs-readme`; no other README change, that is M6.) `rules/README.md`: say the rules now exist and point at the test command.
- **Done-check.** `grep -n "cannot yet write" SKILL.md` prints nothing; `grep -n "candidates" SKILL.md` shows the new lines; full suite passes.
- **Commit.** `docs(dossier): document building Python dossiers with tool findings`

### M2-28. Version 0.7.0 and the sign-off run

- [ ] **Goal.** D12, then prove the exit criterion and record it.
- **Files.** `VERSION`; this plan ("Verification results").
- **Steps.** (1) Follow `git-release` for this repository (as in M1: `VERSION` is a plain file, the bump is a commit; no tag, no push): `0.7.0`. Commit `chore(dossier): bump to 0.7.0`. (2) Run every block of section 6 in its stated order. Paste each block's key output under "Verification results"; list deviations. Commit `docs(dossier): record the M2 verification run in plan 007`.
- **Done-check.** `uv run scripts/dossier.py version` prints `dossier 0.7.0`; every block prints what its "Expected" line says.

### Deliverables and checks (Phase 3)

| Deliverable | Checked by |
|---|---|
| V2, V3, V7 | `test_checks_v2.py`, `test_checks_v3.py`, `test_checks_v7.py` |
| Prompts | `test_prompts.py`, the section 6 build |
| SKILL.md | M2-27 done-check, the section 6 build |
| Exit criterion | section 6 |

### Cut line (Phase 3)

In this order, recording it under "Verification results": (1) the `--catalog` help for drafting components in the prompts (Claude computes edges from the edge table instead); (2) V2's dotted-name and `name()` relaxations (strict match only); (3) block J of section 6 (the tool-missing build). **Never cut:** V3 and V7 basics, the prompt rewrites, M2-28's blocks A to I.

### Acceptance criteria (Phase 3, and M2)

- The spec's exit criterion: cannalerts builds all reports 03 to 09, 11 and 12 from extractors, and `render` reports no V5 error (every candidate has a disposition) and no V4 error (section 6, blocks C to F).
- `check_page.py` prints `"problems": 0` on that page, with citations present (block G).
- An incremental rebuild at the same commit reuses the extractor output (block H).
- A build with node removed shows "partial" badges and the Gaps items (block J).
- Report 02 is unchanged (block E). The full suite passes with and without `DOSSIER_SLOW=1` (block I).

### Branch and release (Phase 3)

After M2-28, follow `git-workflow` to merge `feat/dossier-m2` into `main` with a merge commit (as for M0 and M1) and push only if that skill says to.

---

## 6. Verification

Set once per shell:

```bash
SKILL=/home/nick/dev/projects/encamp/configs/user/claude/.claude/skills/dossier
REPO=/home/nick/dev/projects/cannalerts
FIX=$SKILL/tests/fixtures/encamp-m0
SCR=$(mktemp -d)
export DOSSIER_HOME=$SCR/home DOSSIER_CONFIG=$SCR/cfg.json DOSSIER_CACHE=$SCR/cache PYTHONDONTWRITEBYTECODE=1
BASE=fe72cec488cb211edd6919154bf4d3ed68845e4e33b667a1874716a96bb63b59
D="uv run $SKILL/scripts/dossier.py"
OUT=$DOSSIER_HOME/cannalerts
cd $SKILL
git -C $REPO status --porcelain > $SCR/repo-status-before
```

**Picking the repository.** Use cannalerts. If it has changed so much that it no longer builds (no `pyproject.toml`, no Python package), pick another Python repository under `/home/nick/dev/projects/` with a `pyproject.toml`, a package and tests, record which and why, and change `REPO` and `OUT`.

**Block A: `doctor`.** `$D doctor $REPO; echo "exit $?"`. Expected: git, uv, node, npm `ok`; grimp, vulture, scip-python, semgrep, tree-sitter-language-pack listed as installing on first use; `exit 0`.

**Block B: `prepare` runs every extractor.**

```bash
$D prepare $REPO --ref main --restore yes > $SCR/p1.json; echo "exit $?"
python3 - "$OUT" <<'PY'
import json, sys, pathlib
out = pathlib.Path(sys.argv[1])
b = json.load(open(out / "build.json"))
ex = [r for r in b["records"] if r["step"] == "extract"][-1]
print("extract", ex["status"], ex.get("reason"))
for a in ex["details"]["adapters"]:
    print(" adapter", a["name"], a["status"], {t: s["status"] for t, s in (a.get("tools") or {}).items()})
for f in sorted((out / "extract").glob("*.json")):
    d = json.load(open(f))
    print(f.stem, {k: len(v["items"]) for k, v in d["adapters"].items()})
PY
git -C $(python3 -c "import json;print(json.load(open('$SCR/p1.json'))['checkout']['path'])") status --porcelain | head
```

Expected: `exit 0` (or `exit 3` first if the restore answer is not stored yet; then re-run with `--restore yes`); `extract ok`; adapters `python ok` and `repo ok` with every tool `ok`; all eight files present with non-zero counts for `entry_points`, `graph`, `symbols`, `io_candidates`, `tests` (and `models`, `dead`, `blindspots` if cannalerts has any; record the counts); the checkout's `git status --porcelain` prints nothing.

**Block C: the extractor JSON makes sense.** `$D candidates $REPO --report entry`. Expected: the `cannalerts` console script (`pyproject.toml`), the `__main__`/main guard if present, and nothing that is not an entry point. Read `extract/graph.json` and confirm the `cannalerts.*` modules and their imports are there. Record anything wrong as a finding (a rule to fix in M3's acceptance pass), not as a failure of the block.

**Block D: write the reports.** As Claude, follow SKILL.md `/dossier build` steps 2 to 5 for `REPO` with `DOSSIER` = `$D` (the environment variables above stay set): read the code, run `$D candidates $REPO --report <id>` for each report, write reports 03 to 09, 11, 12, `overview`, `risks` and `gaps` into `$OUT/reports/`. Do not write `change` or `contributors`. Then `for r in entry components interactions io data behavior conventions ops reading; do $D candidates $REPO --report $r --open; done` prints nothing.

**Block F: render and the checks.**

```bash
$D render $REPO > $SCR/r1.log; echo "render exit $?"
grep -E '^(error|warning|info):' $SCR/r1.log | sed -E 's/^(error|warning|info): (V[0-9]+).*/\1 \2/' | sort | uniq -c
```

Expected: `render exit 0`; no `error:` lines; warnings only of kinds V2, V3 and the report-10/13 "missing" warnings; `info: V9: …`. If V5 or V4 errors appear, fix the reports (block D) and render again, recording how many rounds it took. Then check the page: `grep -c 'data-card="' $OUT/dossier-cannalerts.html` is at least the number of schema cards in reports 01 to 12, 14 to 16; the five measured cards hold no "Not yet generated" text: `python3 -c "import re,sys;h=open('$OUT/dossier-cannalerts.html').read();[print(c, 'Not yet generated' in re.search(r'data-card=\"'+c+r'\".*?</section></div>', h, re.S).group(0)) for c in ['reading.map','components.map','interactions.graph','interactions.violations','conventions.tooling']]"` prints five `False`. V7: `grep -c 'Static analysis may miss' $OUT/dossier-cannalerts.html` (record the count; 0 is fine if cannalerts has no blind-spot hits, and the runtime-configuration item must appear once).

**Block G: the browser check, with citations.**

```bash
uv run scripts/check_page.py $OUT/dossier-cannalerts.html --shots $SCR/shots --record $OUT/build.json | tail -3
$D render $REPO > $SCR/r2.log; echo "render exit $?"
```

Expected: `"problems": 0` (the M1 "no citation in the page can open it" failure must be gone, because the reports cite code). Open the Components and Interactions screenshots and one flow with the Read tool and look at them. Fix any failure in the reports or the page assets and repeat. Second render exits 0.

**Block H: incremental rebuild reuses extractor output.**

```bash
$D prepare $REPO --ref main > $SCR/p2.json; echo "exit $?"
python3 - "$OUT" "$SCR/p2.json" <<'PY'
import json, sys
b = json.load(open(sys.argv[1] + "/build.json")); p = json.load(open(sys.argv[2]))
ex = [r for r in b["records"] if r["step"] == "extract"][-1]
print("extract", ex["status"], [(a["name"], a["status"]) for a in ex["details"]["adapters"]])
print("plan", p["update_plan"]["mode"], p["update_plan"]["stale"])
PY
```

Expected: `exit 0`; `extract reused` with both adapters `reused`; plan `render_only` and no stale reports.

**Block I: the full suite.**

```bash
uv run --with pytest --with pygments python -m pytest tests -q
DOSSIER_SLOW=1 uv run --with pytest --with pygments python -m pytest tests -q
```

Expected: both pass (record the counts and the slow run's time).

**Block J: a tool missing gives "partial" badges and Gaps items.**

```bash
mkdir -p $SCR/bin && for t in git uv; do ln -sf "$(command -v $t)" $SCR/bin/$t; done
PATH=$SCR/bin $(command -v uv) run --python /usr/bin/python3 scripts/dossier.py prepare $REPO --ref main --allow-missing --no-restore > $SCR/p3.json; echo "exit $?"
$D render $REPO --allow-errors > $SCR/r3.log; echo "render exit $?"
H=$OUT/dossier-cannalerts.html
grep -c 'class="badge partial"' $H
for s in "The tool node was not installed" "Made without scip-python"; do grep -q "$s" $H && echo "found: $s" || echo "MISSING: $s"; done
```

Expected: `exit 0`; `render exit 0`; at least three partial badges (`components.catalog`, `interactions.flows`, `interactions.graph`); both `found:` lines. (`--allow-errors` because V3 may now be unable to check and the reports were written against the full build.) Then rebuild with node available (`$D prepare $REPO --ref main`) so the dossier is left in the full state: the `python` adapter must **not** be reused (its scip-python status was `skipped`), and the badges disappear after the next render.

**Block E: report 02 unchanged** (after every task that edits `render.py`, and last at sign-off; it wipes `$SCR/home`):

```bash
rm -rf $SCR/home && mkdir -p $SCR/home && cp -r $FIX $SCR/home/encamp && chmod -R u+w $SCR/home/encamp
rm $SCR/home/encamp/dossier-encamp.html
$D migrate /home/nick/dev/projects/encamp > /dev/null; echo "migrate exit $?"
$D render /home/nick/dev/projects/encamp --allow-errors > $SCR/e.log; echo "render exit $?"
grep '^error:' $SCR/e.log | sed -E 's/: card [^:]+:/: card …:/' | sort | uniq -c
python3 tests/tools/report_section.py $SCR/home/encamp/dossier-encamp.html overview --digest --normalize | grep -q "^$BASE " && echo OK || echo DIFFERENT
```

Expected: `migrate exit 0`, `render exit 0`; error lines: one `V10: there is no build.json`, and from M2-24 also the V6 "pending is not allowed" lines (and "missing" errors for reports the fixture lacks, if any); no V4 or V5 lines (the fixture has no `extract/`); then `OK`.

**Order at sign-off:** A, B, C, D, F, G, H, J (then the rebuild it describes, and render again), I, then E. Finally `diff <(git -C $REPO status --porcelain) $SCR/repo-status-before` prints nothing (the user's repository was not touched).

**Recording results.** Under "Verification results" write the date, branch and model, then for each block the commands' key output lines, the number of render rounds needed in block F, what was cut and why, and a "Deviations" list. Findings about rule precision or missed items in block C go in a list "Findings for the M3 acceptance pass", not into fixes in this milestone, unless a finding is a crash or a V1 failure.

---

## 7. Risks and open questions

### Risks (most important first)

1. **scip-python may not run as planned.** Its `--environment` option is marked experimental, a uv virtual environment has no `pip` for it to ask, and whether `npm ci --ignore-scripts` gives a working install is untested. M2-1 checks this first; if it fails, the adapter still runs and the three cards it feeds are badged partial, but V3 then checks arrows against imports only.
2. **Candidate volume on large repositories.** Logging, `print`, `timeout=` and `async` sites can run into thousands. Group dispositions keep the work to rules times files, but a large repository can still have hundreds of groups, and V5 blocks `render` until each has a decision. This may make full builds of large repositories slow and expensive in Claude time.
3. **Rule precision and recall are unproven.** The rules are new and tested only on the fixture. The spec's targets (entry points recall 100%, inputs and outputs recall 95%) are judged at M3's acceptance pause; rules will need tuning then. Wide rules (`db-access` on any `.execute`, `timeout` on any keyword) trade precision for recall on purpose.
4. **Builds and slow tests need the network** for the grimp and vulture worker environment, the npm install of scip-python and the semgrep rules' first run. Offline, these tools fail and their cards are partial.
5. **Phase 1 is large** (twelve tasks, five tools). The cut line protects the fixture tests; if Phase 1 overruns, Phase 2 starts with its leftovers and the risk moves to Phase 3's end-to-end run.
6. **V2 may warn on prose.** Backticked names that are concepts rather than code (for example `retry budget`) are excluded only when they contain spaces; single words that are not in the cited code will warn. Warnings do not block, but they add Gaps items.
7. **grimp's layer results "are not fully deterministic"** (its docs). The worker sorts its output, but which violating route is reported first may vary between runs, which can change the Evidence cell and make `interactions` stale in an incremental build.
8. **I read** in full: the spec, plans 006 (all sections), `adapters.py`, `shared_tools.py`, `stages.py`, `schema.py`, `ts_worker.py`, `semgrep_worker.py`, `prompts/method.md`, `prompts/reports.md`, `SKILL.md`, every card schema, `rules/README.md`, `docs/process.md`, `docs/post-v1.md`; in part: `render.py` (citations, validation, card drawing, Gaps, page assembly), `dossier.py` (`update_plan`, `cmd_prepare`, `cmd_render`), `incremental.py` (`assess`, `plan`), `process.py` (coverage items, V9, V10), `tools.json`, `tests/conftest.py` (`hygiene_repo`). I did not read `deps.py`, `viewer.py`, `migrate.py`, `check_page.py`, `toolcheck.py` beyond its outline, `gather.collect`, `assets/dossier.js`, `assets/dossier.css`, or the existing tests' bodies. Where the plan depends on them (`gather.lang_of`, `gather.noise_reason`, `gather.TEST_RE`, `render.render_table`, `render.path_cell`), it uses only names and signatures I saw.

### Questions for the human

Answers recorded on 2026-11-01. Every answered question took the plan's default, so the plan text above needs no change for them.

- **Q1.** `components.map` and `interactions.graph` as a component-level Mermaid diagram plus a full module edge table in M2, with collapsible interactive graphs moved to M6? **Answer: yes.** Interactivity is M6 work (spec section 10, M6 row).
- **Q2.** May a decision cover a whole group (every hit of one rule in one file), so Claude does not decide each call site one by one? **Answer: yes (default).**
- **Q3.** V5 covers entry points, inputs and outputs (and the state, concurrency, failure and observability findings) and data entities, each with one home card (D3 table); the import graph, symbols, tests, dead code and blind spots are measured or go to Gaps instead. **Answer: yes (default), including every home card in D3's table** (logs, metrics and tracing in `behavior.observability`; HTTP routes, scheduled jobs and queue consumers in `entry.catalog`; database connections in `data.stores`). Spec amended: principle 2 and the home-card table in 6.1.
- **Q4.** An arrow V3 cannot back is listed under its diagram as inferred and added to Gaps, because Mermaid cannot mark one arrow of a sequence diagram. **Answer: yes.**
- **Q5.** V4 lets the most specific path win when a component and a sub-component both match a file, and errors only on a tie between two components. **Answer: yes.**
- **Q6.** scip-python is installed once from a committed npm lockfile into the shared tool cache (not with bare `npx`), runs under the restricted profile, and only on trusted refs or with `--allow-ref`. **Answer: yes (default).**
- **Q7.** Add a repository-wide adapter (`repo`) for Dockerfiles, Makefiles, CI files, systemd units, shebang scripts and SQL, alongside the language adapters. **Answer: yes.**
- **Q8.** In M2, reports 10 (`change`) and 13 (`contributors`) are not written and their absence is a warning; cards may no longer be left `pending`. **Answer: yes.** M3 must empty `render.OPTIONAL_REPORTS` (spec section 10, M3 row).
- **Q9.** Version 0.7.0. **Answer: yes (default).**
- **Q10.** May section 6 run `uv sync --frozen` on cannalerts again and have Claude (the implementing session) write a full dossier of it into the scratch folder? **Answer: yes (default).**

---

## 8. Spec issues

Reviewed by the human on 2026-11-01. Each issue ends with its **Resolution**. "Spec amended" means `004-v1-spec.md` now says what the plan does (its section 12 lists the amendments as items 8 to 25), so a later session reading the spec and this plan finds the same answer in both.

1. Section 4 (05, 06) asks for interactive, collapsible graphs for `components.map` and `interactions.graph`, but no milestone lists the page work for them. The plan draws a component diagram plus a full edge table in M2 and suggests M6 for interactivity (Q1). **Resolution:** accepted; interactivity moves to M6. Spec amended (05 and 06 card rows, section 10 M6 row, decision 8).
2. V3 says an unbacked arrow is "marked `inferred`", but Mermaid sequence diagrams cannot style one message, and a diagram block has one `conf` for the whole diagram. The plan lists the arrows under the diagram and in Gaps (Q4). **Resolution:** accepted. Spec amended (section 7 V3 row, decision 9).
3. V4 says "exactly one component". Read literally, a component and its sub-component cannot both be described by path. The plan lets the most specific path win (Q5). **Resolution:** accepted. Spec amended (05 invariant, section 7 V4 row, decision 10).
4. Principle 2 says "for every extracted list" each candidate gets a disposition, but the glossary and reading-order suggestions, the import graph, symbols, tests and dead code are measurements, not candidate lists a model should keep or drop. The plan applies V5 to entry points, the I/O-style findings and data entities only (Q3). **Resolution:** accepted (default, Q3). Spec amended: principle 2 now names the candidate lists and the exempt outputs (decision 24).
5. Several cards list the same sources (`io.outputs` "logs"/"metrics" versus `behavior.observability`; HTTP routes in `entry.catalog` and `io.inputs`). The spec does not say where the decision is recorded. The plan gives each category one home card (D3) and accepts a decision anywhere. **Resolution:** accepted (default, Q3), with every home card in D3's table as written. Spec amended: the home-card table in 6.1, and principle 2 (decision 25).
6. 6.2 lists "DI registration" and "flags" among semgrep's outputs for all languages. Python has no common DI container to detect, so the Python set has no DI rule, and feature flags are a blind-spot heuristic, not an I/O category. **Resolution:** accepted (default). Spec amended (6.2 semgrep row, decision 11).
7. 6.1 says "one adapter class per language", but `entry_points` includes Dockerfiles, Makefiles, CI and systemd units, which belong to no language. The plan adds a repository-wide adapter (Q7). **Resolution:** accepted. Spec amended (6.1 introduction, section 10 M2 row, decision 12).
8. `components.map` is tier M+A but `writer: script` with a `computed` shape: Claude's part (names, merges) arrives only through `components.catalog`. This is consistent, but the badge "M+A" on a card Claude never writes may confuse readers. **Resolution:** accepted (default): no change; the badge stays M+A and the card schema is unchanged. Spec amended to say so (05 card row, decision 13).
9. 6.4's "All: runtime config selecting implementations" cannot be detected by a rule without heavy false matches. The plan adds one fixed Gaps item instead. **Resolution:** accepted (default). Spec amended (6.4, decision 14).
10. scip-python's `--environment` is "experimental", and by default it asks `pip`, which uv virtual environments do not contain. The spec's "scip-python wants an installed environment" does not cover this. **Resolution:** accepted (default): environment file written from `.venv`, install from a shipped lockfile (Q6). Spec amended (6.2 scip-python row, decision 15). M2-1 still checks that it works; if it does not, the stop condition there applies.
11. 5.3 keys extractor output by `(sha, extractor version)`, and says a report is stale "if its extractor output changed". Output always changes when the commit changes (line numbers). The plan compares line-free digests of what each report is fed (D10). **Resolution:** accepted (default). Spec amended (5.3, decision 16).
12. Section 10 puts reports 10 and 13 in M3, but `render` requires every authored report. The plan makes them optional for M2 (Q8). **Resolution:** accepted; M3 makes them required again. Spec amended (section 10 M2 and M3 rows, decision 17).
13. Section 4 (14/15) says Gaps receives "every undispositioned candidate", while V5 makes any such candidate an error that stops `render`. Both can hold only under `--allow-errors`. The plan does both. **Resolution:** accepted (default). Spec amended (section 4, 14/15 additions, decision 18).
14. `behavior.tests` is tier A, but most of its first table (counts, skips, mock density, configuration) is measured. Claude copies measured values into it from `dossier candidates`; a measured sub-table drawn by code would be more faithful. **Resolution:** accepted (default): no change in M2; the card schema stays as M0 made it. Recorded as spec decision 19.
15. 6.2 says import-linter configuration is "read only", but reporting violations needs the contracts evaluated. The plan evaluates `layers` and `forbidden` contracts with grimp and lists the other contract types as not checked. **Resolution:** accepted (default). Spec amended (6.2 import-linter row, decision 20).
16. 6.1's `symbols` "public surface per module" has no definition for Python. The plan calls a name public when no part of it starts with `_` and it is top-level or a class member; `__all__` is ignored. **Resolution:** accepted (default). Spec amended (6.1 `symbols` row, decision 21).
17. 6.3 says Tier A cards are badged "full". The plan shows only "partial"; a card without it is full. **Resolution:** accepted (default). Spec amended (6.3, decision 22).
18. Section 11 item 3 wants entry-point recall of 100%, but the spec does not say which entry points count for a library (every public function?). The plan counts only the kinds in D2. **Resolution:** accepted (default). Spec amended: 6.1's `entry_points` row lists the kinds, and section 11 item 3 measures recall over them (decision 23).
