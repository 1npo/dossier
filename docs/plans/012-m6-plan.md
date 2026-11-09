# Plan 012: milestone M6 (Tier B, interactive graphs, `--verify`, freshness, Python API and subfolders, docs, 1.0.0)

Status: written by Opus on 2026-11-09 from `docs/prompts/plan-m6.md`. The author answered section 8's questions Q1 to Q6 on 2026-11-09 (all as the defaults, recorded there). Section 9's spec issues carry defaults that this plan follows (section 2, "Judgement calls"). Phase 1 can start.

**If you were started for Phase 6a, stop reading here.** Find the heading `## Phase 6a: Rulings on new ground-truth disagreements` and read only that section.

Written from: `plans/004-v1-spec.md` (all of it), `docs/process.md`, `docs/post-v1.md`, plan 011 in full (every "Results" and "Findings" block, sections 6 to 8, Sources), plan 010 in part (shared rules, D17, Phases 4a to 5 with their results and rulings, section 6), and the code at `51b056e` (version 0.10.0; `main`, clean, M5 merged as `59f20f8`). Two Python libraries were read from clones in `~/.cache/dossier-m6-plan/src/`. Nothing was installed, restored or built. Writing this plan changed no other file. Section 8 says what I read and what I did not.

Paths used below:

- `SKILL` = `/home/nick/dev/projects/encamp/configs/user/claude/.claude/skills/dossier`, the development copy and the repository that holds the commits.
- `INSTALLED` = `/home/nick/.local/share/encamp/configs/user/claude/.claude/skills/dossier`. `~/.claude/skills/dossier` points at it. Never edit it, never run `encamp-sync` against it, and never read it as the source of truth.
- `LIVE` = `/home/nick/dev/dossiers/cannalerts`, the author's dossier. Only section 7 touches it, and only to copy it.
- `REPO` = `/home/nick/dev/projects/cannalerts`, pinned at `5923c09`. Read-only. The **Python golden** repository. Its code languages at the pin are Python, SQL and Shell; it has one `pyproject.toml`, at the root (hatchling, with `[project.scripts]`).
- `FIX` = `SKILL/tests/fixtures/encamp-m0`, frozen and git-ignored. Never written.
- `PYFIX`, `JSFIX`, `CSFIX` = `SKILL/tests/fixtures/{pyrepo,jsrepo,csrepo}/`. `PYFIX` and `JSFIX` are not edited. `CSFIX` gains one project in M6-1 and nothing else.
- `PYLIB` = `SKILL/tests/fixtures/pylib/`, new in M6-15: original code for the Python public API.
- `TRUTH` = `/home/nick/.cache/dossier-m5-vWDO/truth/`, the **kept M5 ground truth for `RW`** (see section 2, "The truth folder").
- `RW` = `realworld-apps/aspnetcore-realworld-example-app` at `9345f18abf36b778abe2f290467ba432bf1f7e5c` (MIT). The **C#** repository of definition of done item 2, and the one with ground truth.
- `CA` = `jasontaylordev/CleanArchitecture` at `4739ae4cbd057ee142bc1e1bdc93c4fea8f0cac5` (MIT). C#, Angular and React; the largest repository here. Its `main` is now **3 commits ahead of the pin** (checked 2026-11-09), which makes it the real test of the freshness BAN.
- `BP` = `alan2207/bulletproof-react` at `9506629ed003a561c6627735480cce4994244bb4` (MIT). The **TS/React** repository of item 2 (D19).
- `GC` = `ardalis/GuardClauses` at `61dde6c9d3e1715286bd100144a9edff1ad0664c` (MIT), `ZU` = `pmndrs/zustand` at `382d29c485e67018c06e75ec7235130d0968522c` (MIT): the C# and JS libraries of M5 and M4 block Y, rerun as regressions.
- `TO` = `hukkin/tomli` at tag `2.5.0` = `a2a578949199336ebc3884eeba4aede87da41ef2` (MIT): a Python library with `__all__` and a re-exporting `__init__.py`. `MI` = `more-itertools/more-itertools` at tag `v11.2.1` = `4aeb4338ae1407d8da9723e86da99efeb446f719` (MIT): a Python library **without** `__all__` in its `__init__.py` (it star-imports two modules that each have one), with `.pyi` stubs.
- Tests run from `SKILL`: `uv run --with pytest --with pygments python -m pytest tests -q`. **Baseline at `51b056e`: 2631 passed, 274 skipped (70 s)**, measured 2026-11-09. The slow baseline is in "Results (planning)" at the end of section 5.
- Slow tests need `DOSSIER_SLOW=1`, the network, the real tools and **`--basetemp=$HOME/.cache/dossier-m6-slow`**, never `/tmp`.

---

## 1. Summary

- **Features:** "no static graph" badges for Tier B languages (D5); a freshness BAN in report 01 (D6); interactive, collapsible graphs in `components.map` and `interactions.graph`, drawn from views that code computes so every view meets V12 (D7); an opt-in verifier pass, `--verify` (D8); Python's real public API (D10) and Python projects in subfolders (D9).
- **Carry-ins from M5:** the Aspire `Sdk` attribute (required), five other C# precision fixes, `ci-trigger` for every language, Dockerfile and compose environment variables, and three Python blind-spot rules from the cross-language review (section 4 and D11, D12).
- **Docs and release:** README rewrite, a new user guide and developer guide, a test that keeps the docs in step with the CLI, a refreshed end-of-life snapshot, `VERSION` 1.0.0.
- **Exit:** the definition of done (spec section 11), checked item by item by Claude in Phases 6 to 8 on the Python golden, `RW` (re-scored against the kept truth), `BP`, `CA`, a mixed fixture and five libraries.
- **Sessions: eight Sonnet, plus one Opus only if the `RW` re-score shows a new disagreement** (D20): 1 carry-ins, Tier B and freshness; 2 Python; 3 graphs; 4 verify, rules and repository inputs; 5 docs and version; 6 golden, JS and `RW`; 6a Opus rulings (conditional); 7 React, mixed, libraries, `--verify` for real and degraded builds; 8 `CA`, skeletons, install check and merge.

---

## 2. Shared rules (every phase reads this first)

- **Branch.** All phases work on `feat/dossier-m6`, created from `main` in Phase 1 and merged at the end of Phase 8. One commit per task. Phase 6a commits only its "Results" section.
- **Skills to load at the start of every phase:** `git-commit`, `git-workflow`, `py-projects`, `py-unit-tests`, `claude-planning-docs`. Phase 5 also loads `docs-project`, `docs-readme`, `docs-user-guide`, `docs-dev-guide` and `git-release`. Phase 8 also loads `git-release`.
- **Commit style.** Follow `git-commit`. Messages match the M5 commits (`feat(dossier): ...`, `fix(dossier): ...`, `test(dossier): ...`, `docs(dossier): ...`).
- **Never touch:** `INSTALLED`, `LIVE` (copy it), `REPO`, `FIX`, `/home/nick/dev/dossiers/`, `PYFIX`, `JSFIX`, `TRUTH` (see below), and the pinned clones of `RW`, `CA`, `BP`, `GC`, `ZU`, `TO`, `MI` (analysed, never changed). Nothing from those clones is ever committed: no fixture, no snippet, no saved output. `PYLIB` and the `CSFIX` addition are original code.
- **The truth folder.** `TRUTH` holds the M5 ground truth for `RW`: `rw.json` (sha256 `a7fc87a9dbcf454d0b7e8b2500f81ad533535cdf1e5dad327ed8c7c145a18098`), `rulings.md`, `review.md`, `review-5b.md` and `rw.before-5a.json`. It exists **only for regression use**: Phase 6 re-scores the new `RW` dossier against it. It is **never edited, never committed, and never copied into the repository** or into any scratch folder. Read `rw.json` only through `tests/tools/ground_truth.py`. You may read `review-5b.md` and the "Phase 5b rerun" part of `rulings.md` to compare lists of disagreement keys; nothing else in it. Check its hash before and after every use.
- **Report 02 and card schemas.** Report 02 (its panels, CSS and JS) does not change. **No file in `prompts/schema/*.json` changes.** M6 adds no card: the freshness BAN is a tile inside `dossier.about`, the badges sit in card headers, the graph sits inside the two existing cards, the verifier writes Gaps items and a line on the process card.
- **Report 02 guard.** After every task that edits `render.py`, `measured*.py`, `process.py`, `assets/dossier.css` or `assets/dossier.js`, run section 7 block E. It must print `OK`.
- **Adapter output changes only where a task says so.** Every such change starts with a failing test, names its reason, bumps the adapter's `version`, and is recorded under the phase's "Results" as **before and after** (counts or the changed lines). The deliberate changes to Python and JS output in M6 are listed in D18; anything else that changes is a bug. `test_py_adapter_slow.py`, `test_js_adapter_slow.py` and `test_cs_adapter_slow.py` must pass at the end of every phase, edited only where a task names the edit.
- **Scratch.** Every command that renders or builds sets `DOSSIER_HOME`, `DOSSIER_CONFIG` and `DOSSIER_CACHE` to a fresh folder under `~/.cache`, never `/tmp`. Unit tests use `tmp_path`. The slow suite always runs with `--basetemp=$HOME/.cache/dossier-m6-slow`, and that folder is removed afterwards. Nothing outside section 7 builds a dossier of a real repository.
- **Every child process goes through `sandbox.run`**, directly or through `ctx.run`. No sandboxing, containers or namespaces (spec decision 5). The one new network call is `git ls-remote` for freshness (D6), which runs through `sandbox.run`.
- **No new runtime dependencies** in `scripts/dossier.py` or anything it imports (standard library plus `pygments`).
- **Tests first.** Each task starts with a test that fails on the current code. Run it, see it fail, and record the failure line in the commit body as `Fails before: ...`. A task whose new tests pass at once (a check of existing behaviour) says so and has no such line. The full suite passes after every task. The slow suite passes at the end of each phase, except the three known failures: `test_overlapping_paragraphs_are_reported`, `test_each_browser_mutation_makes_a_fail[chart-text-small-chart text]` and the G2 golden (`test_golden02_slow.py`).
- **Do not weaken a check to make it pass.** If a check fails on real output, the output is wrong until the author says otherwise.
- **Measured values are never written by Claude.** Nothing is dropped silently: no `[:N]` on data that feeds a card. A diagram view may hide links only through D7's stated filter, and it says so on the page.
- **Plain language** in everything a dossier user reads. Gaps statements and badge texts use the fixed wording in this plan, so their ids stay stable.
- **If the code contradicts this plan, stop and report** under that phase's "Results". Do not design around it.
- **Size.** Keep each new Python module under about 300 lines; `render.py` and `dossier.py` grow only by the calls a task names. Tree-sitter patterns stay one or two levels deep.
- **Context.** Keep tool output short: single test files while working, long output through `tail`. Never print a whole page or a whole `extract/*.json`.
- **Ticking.** Tick each task's checkbox in the same commit as the task. Write results under the phase's "Results" heading.
- **One writer per file.** Never run two sessions at once: every phase writes this plan.
- **Judgement calls** (the author's rule from M5, extended to all of M6). When a question needs judgement (what counts as a library, an entry point, a Tier B language, a blind spot, a page design detail), **do not stop and wait**: take the default this plan gives, or the one you would recommend, record it under the phase's "Results" and "Findings for the milestone review" with one line on why, and carry on. Still stop for: a failed safety or hygiene check, a contradiction between the code and this plan, a merge conflict, a step that would install or run something the author has not accepted, or any change to `TRUTH`.
- **The author's time is for judgement only.** Claude runs every build, test, browser check, re-score, `--verify` run, `doctor` run, install check and screenshot reading in this plan. Section 8 lists the few things only the author can do, and why.

---

## 3. Spec versus code

"Absorb" means the plan can absorb it with the default shown. "Decision" means the default is followed and the author may overrule it (section 8 or 9).

| # | Area | Spec says | Code does today (0.10.0, `51b056e`) | Default | Class |
|---|---|---|---|---|---|
| 1 | Freshness BAN | 01 gains a `freshness` BAN (pinned commit versus current HEAD of the ref); question 10.3 | Nothing: no `freshness`, no `ls-remote` anywhere. `questions.json` question 39 (10.3) already names `dossier.about` | A tile in `dossier.about`, computed in `prepare` and kept in `build.json` (D6). No schema change; spec issue S1 | Decision (S1, Q3) |
| 2 | Graph cards | `components.map`, `interactions.graph`: until M6 "a component diagram ... plus a table"; in M6 an interactive collapsible graph | **Tables only.** `1e5712c` (post-M2 visual UAT) removed the import-graph diagrams as noise; `measured_graph.py` says so. `_diagram` survives for the ER cards | Add the interactive graph above the unchanged tables, opening on the collapsed area view (D7). Q1 asks whether the author still wants it, given the UAT | Decision (Q1, S5) |
| 3 | V12 edge budget | "a flowchart holds at most 12 nodes and 30 edges" | `check_layout.py` checks nodes (`MAX_FLOW_NODES = 12`) only; no edge count | Add `MAX_FLOW_EDGES = 30` (M6-22) | Absorb (S15) |
| 4 | Tier B badge | "The affected reports are badged 'no static graph' and Gaps lists the language" | Gaps has `{lang} has basic support only: no import or call graph is extracted for it.` per Tier B language (`process.coverage_items`). **No badge.** `doctor` prints `(Tier B: no static graph)`. Every code-kind language without a `tools.json` scope is Tier B, including `Dockerfile`, `Makefile` and `SQL`, which the `repo` adapter reads | Badges on the graph-fed cards (not report headers) for Tier B languages other than those three (D5). Gaps wording unchanged | Decision (S3) |
| 5 | Tier B content | "tree-sitter symbols and structure" for Tier B | No tree-sitter symbols are extracted for Tier B languages | Not in 1.0.0; `post-v1.md` entry (M6-39). It is "Tier B polish", second on the spec's cut line | Decision (S3) |
| 6 | HTML/CSS | 6.3 names HTML/CSS as Tier B | `gather._LANGS` classifies them `markup`, so they are never a language for preflight, Tier B or V4 | Leave: markup has no imports to graph. Spec wording S3 | Decision (S3) |
| 7 | `--verify` | Section 7, last paragraph | Nothing in this skill. The agent `dossier:dossier-verifier` named in the planning prompt belongs to a **different plugin** (`1npo/dossier` marketplace, 1.4.3, uninstalled on 2026-11-09 at the author's request (Q4), with an "init mode" this skill does not have); its verdicts are `supported / overstated / unsupported`. This skill has no `agents/` folder, and a skill cannot ship one | Do not use that agent. The skill ships `prompts/verify.md`, and `SKILL.md` tells Claude to start a general-purpose subagent with it (D8). This is a contradiction between the prompt and the code that does not block the plan | Decision (Q4, S2) |
| 8 | V10 and `--verify` | V10 needs the fixed process list | `buildlog.STEPS` is the spec's ten steps | The verifier is part `verify` of step 8 `check`; no new step (D8) | Absorb (S2) |
| 9 | Python public API | Decision 42: Python gets the TS/C# report in M6 | `public-api` items exist for JS (`js_api`) and C# (`cs_api`); `measured_tables.public_api` shows them; the no-API line appears only when a module has `language` `js` or `csharp` (Python modules carry no `language` key) | `py_api.py` (D10). Python applications show the no-API line, so the golden's `io.contracts` card gains that one line (D18) | Decision (S4) |
| 10 | Python below the root | `post-v1.md`: find `pyproject.toml`, `setup.py`, `requirements.txt` below the root | `py_packages.package_roots` looks only at `""`, `src` and configured folders; the `python` restore entry is root-only (`uv.lock`, no `nested`); `scip_tool.environment` reads `<checkout>/.venv` only | D9 | Absorb (S7) |
| 11 | `ci-trigger` | 6.1: CI definitions are entry points | `repo_adapter.wants_triggers` writes push, pull-request and manual triggers for repositories with a `.cs` file only (M5-33) | Every language (M6-32, D18) | Absorb (S10) |
| 12 | `repo` inputs | 6.1: `io_candidates` for every repository | The `repo` adapter writes no I/O items; `facts.env_vars` misses `ENV` in Dockerfiles and compose `environment:` | Dockerfile `ENV`/`ARG` and compose `environment:` and `env_file:` (M6-31); Makefiles and scripts to `post-v1.md` | Decision (S9) |
| 13 | C# unused packages | `change.dead-code`: "vulture, knip" | `measured_change.dead_rows` lists `dependencies.json` `unused` rows for every ecosystem; for NuGet all 11 on `RW` were false (M5 Phase 5 finding 1) | NuGet rows left out, one fixed Gaps item (M6-2) | Absorb (S16) |
| 14 | Aspire | D9 of plan 011: `Aspire.Hosting.AppHost` gives a `framework` note | `cs_project.frameworks_named` reads `PackageReference` only; Aspire 13 projects use `<Project Sdk="Aspire.AppHost.Sdk/...">` | Read the `Sdk` attribute and `<Sdk Name>` elements (M6-1) | Absorb |
| 15 | P4-3 | `post-v1.md`: `candidates` hides Nx target and package-script names | `candidates.text` prints `[name]` after the snippet when they differ (M4 Phase 4b fix 1, `candidates.py:332`) | Prove it with a test and remove the entry (M6-7) | Absorb |
| 16 | End-of-life data | Decision 4: snapshot shows "data as of" | `eol.json` `as_of` 2026-11-05. endoflife.date itself still says .NET 10 latest is `10.0.13` on 2026-11-09 (checked), although runtime 10.0.14 shipped | Refresh the snapshot at release (M6-40); the lag is upstream, so M5 finding 5 needs no code (`post-v1.md`: .NET from Microsoft's `releases.json`) | Absorb |
| 17 | Docs | Item 7: README, `SKILL.md` and prompts describe 1.0.0 | README calls the skill `codebase-dossier`, lists "twelve reports (overview, capabilities, interfaces, ...)", keeps a version history and says "The Contributors report has a card that shows ..." (the card is in report 02). No `docs/user-guide.md`, no `docs/developer-guide.md`, no `LICENSE` | Phase 5 (D16) | Absorb |
| 18 | Release | `git-release`: use the bump tool; CI tags | This skill has no bump tool and no CI; M4 and M5 edited `VERSION` directly on the feature branch | Same as M5 (D17); Q5 | Decision (Q5) |
| 19 | Sessions | `process.md`: M6 is 1 session | M4 took 5+2+1, M5 7+2+1 | 8 Sonnet + 1 conditional Opus (D20); the author accepted this (Q2); M6-39 updates `process.md` | Decision (Q2) |
| 20 | `summary.json` | Section 9 lists its fields; "no field the reports do not hold" | `schema_version` 1; `languages[].tier` already present | No new field: freshness depends on when you look, and verifier results are not facts about the code (D6, D8). `schema_version` stays 1 | Absorb (S13) |
| 21 | Major bump | A new minor version rebuilds | `update_plan` compares `major.minor`: `0.10` to `1.0` gives `full` | Nothing to change; M6-41 tests it | Absorb |

**How the plan 008 checks apply to what M6 adds.** M6 adds no card, so V6 is untouched.

| New thing | V5 | V11 | V12 |
|---|---|---|---|
| Tier B badge | n/a | unit test of the badge set (M6-8) | header overlap check on the M6 test page |
| Freshness tile | n/a | new count: the tile exists when `build.json` has a pin record (M6-10) | page-wide checks on the M6 test page |
| Graph views | exempt: measured | new counts: every component and module is in at least one view, every view's edges come from the edge table (M6-21) | new per-view checks: at most 12 nodes and 30 edges, text at least 11 px, both widths and themes (M6-22), with mutations (M6-23) |
| Python `public-api` rows | exempt: measured | existing count (M4-21a), now also for Python | existing |
| Verifier Gaps items and process line | n/a | existing Gaps count | existing |
| New candidates (`ci-trigger` for all, compose and Dockerfile variables, Python route findings) | per-row rule, home cards `entry.catalog` and `io.inputs` | existing | existing |

---

## 4. Triage of the M5 and M4 findings

Every finding recorded in plan 011 (Phases 1 to 6 and Phase 6's verification) and the M4 deferrals in `post-v1.md`.

| Source | Finding | Disposition |
|---|---|---|
| 011 P1 | scip-dotnet indexes `obj/**/*.cs` | No action: fixed in M5-16 (`join` drops untracked documents) |
| 011 P1 | `CA`'s Aspire projects fail in scip-dotnet without a restore | No action: the expected `msbuild` Gaps case; `CA` has no lock files |
| 011 P1 | First restore ran outside `sandbox.run` (harness) | No action: a session slip, not code |
| 011 P1 | G3 wording ("every `.cs` file has a `def`") | No action: the gate passed; the author was told |
| 011 P2 | Fixture `OrderService.cs` had no `using` | No action: fixed in Phase 3 |
| 011 P2 | Source-generated output and `.cake` scripts are blind spots | Generators: no action (Gaps says so). `.cake`: `post-v1.md` (M6-39) |
| 011 P2 | `Product` missing from the fixture | No action: added in Phase 3 |
| 011 P3 | False `ref-edge`s between top-level `Program` classes of different projects | **M6-4** |
| 011 P3 | Tracked generated file: scip edges kept | No action: D12 of plan 011 keeps incoming edges by design |
| 011 P4 | `.razor` and `.csproj` are not source files | No action, decided (D5): Razor stays outside `gather`'s languages; the `razor` Gaps note says the files were not read. `.csproj` is a manifest |
| 011 P5 #1 | 11 false "unused dependency" rows for C# | **M6-2** |
| 011 P5 #2 | `repo` adapter writes no I/O items (Dockerfile `ENV`, compose, Makefile, scripts) | **M6-31** for Dockerfile and compose; Makefile and shell variables to `post-v1.md` (too many false matches without a shell parser) |
| 011 P5 #3 | Bullseye multi-line `Target(` names missing | **M6-5** |
| 011 P5 #4 | `0 files` for test projects; empty `== Python packages ==` heading in a C#-only repository | **M6-5** |
| 011 P5 #5 | `.NET` latest `10.0.13` older than runtime `10.0.14` | No code: endoflife.date itself lags (row 16). Snapshot refreshed in **M6-40**; `post-v1.md` entry for Microsoft's `releases.json` |
| 011 P5 #6 | ER `FK` marks on collection navigations | **M6-6** |
| 011 P5 #7 | No `ambiguous-symbol` note on `RW` | No action: correct (the duplicates are merged partial migrations) |
| 011 P5 #8 | `"restore": []` with `--no-restore`; restore recorded under step `copy` | No action: the spec's step 3 is "copy and restore"; the record is right |
| 011 P5 #9 | `.check-shots` keeps one shot per diagram, not per report and width | No action in code; section 7 asks for the shots that exist |
| 011 P5 #10 | `Copilot` identity classed human despite `Agent-Logs-Url` lines | `post-v1.md`: the classifier feeds report 02, which M6 must not change |
| 011 P5 #11 | V3 warns on mediator and DI hops | No action: the expected C# blind spot |
| 011 P5a | `ground_truth.py` `where` collapse; citation matching | No action: fixed in Phase 5b. The label-dropping note (#86, #87) goes to `post-v1.md` as a test-tool idea |
| 011 P5b | `ci-trigger` only for C# | **M6-32** |
| 011 P6 #1 | No Aspire `framework` note (`Sdk` attribute) | **M6-1** (required carry-in) |
| 011 P6 #2 | `CA` has 13 projects, not 10 | No action: a plan-text error |
| 011 P6 #3 | `CA` endpoint groups found by reflection | No action: the blind spots fired as designed |
| 011 P6 #4 | `AspireExtensions` listed as dead though its extension method is called | **M6-3** |
| 011 P6 #5 | Test projects show `0 files` | **M6-5** |
| `post-v1.md` | P4-3: `candidates` hides Nx target and package-script names | **M6-7** (prove fixed, remove the entry) |
| `post-v1.md` | P5-1: MSW handlers not entry points | Stays in `post-v1.md`: mock handlers are not routes the program serves |
| `post-v1.md` | Python projects in subfolders | **M6-11 to M6-14**; entry removed in M6-39 |

---

## 5. Decisions

### D1. Where the work goes

| File | Change |
|---|---|
| `scripts/cs_project.py`, `cs_scip.py`, `cs_semgrep.py`, `candidates.py`, `measured_change.py`, `measured_er.py` | Carry-ins (M6-1 to M6-6) |
| `scripts/process.py`, `render.py`, `assets/dossier.css` | Tier B badge (D5) |
| `scripts/workarea.py` (one function), `stages.py`, `render.py` | Freshness (D6) |
| `scripts/py_project.py` (new), `py_adapter.py`, `py_packages.py`, `scip_tool.py`, `tools.json` | Python subfolders (D9) |
| `scripts/py_api.py` (new), `py_adapter.py`, `measured_tables.py` | Python public API (D10) |
| `scripts/graph_views.py` (new), `measured_graph.py`, `assets/dossier.js`, `assets/dossier.css`, `page_audit.py`, `check_layout.py`, `check_page.py`, `tests/tools/broken_pages.py`, `tests/tools/m6_page.py` (new) | Interactive graphs (D7) |
| `scripts/verify.py` (new), `dossier.py`, `checks.py` or `process.py` (Gaps, V10), `prompts/verify.md` (new), `SKILL.md` | `--verify` (D8) |
| `rules/python/blindspot.yml`, `tests/fixtures/semgrep/python/blindspot.py`, `checks_v7.py` (no new wording: ids exist) | Blind spots (D11) |
| `scripts/repo_adapter.py` | `ci-trigger` for all, compose and Dockerfile inputs (D12) |
| `README.md`, `docs/user-guide.md` (new), `docs/developer-guide.md` (new), `LICENSE` (new), `SKILL.md`, `prompts/*.md`, `rules/README.md`, `docs/post-v1.md`, `tests/unit/scripts/test_docs.py` (new) | Docs (D16) |
| `VERSION`, `scripts/eol.json` | Release (D17) |

### D2. Aspire and SDK names (M6-1)

`cs_project` reads the root element's `Sdk` attribute (it may hold several names separated by `;`, each optionally `Name/Version`) and every `<Sdk Name="X" .../>` child element. These names join the package names in `frameworks_named`. A name mapping `SDK_FRAMEWORKS = {"Aspire.AppHost.Sdk": "Aspire.Hosting.AppHost"}` reports Aspire under the same Gaps name as the package does, so the wording and the id stay the same. `CSharpAdapter.version` moves up by one. Why: Aspire 13 app hosts name no package; the SDK is the signal.

### D3. C# precision (M6-2 to M6-6)

- **Unused NuGet packages (M6-2).** `dead_rows` skips `dependencies.json` `unused` rows whose `ecosystem` is NuGet (check the exact ecosystem string in `deps.py` first; the field is set at `deps.py:912`). One fixed Gaps item, report `change`, when any C# module exists: `Unused NuGet packages are not listed: a package is often used through extension methods, analysers or build files that no import names.` How to confirm: `This is a known limit of this version of dossier.` `deps.py` is not edited (report 02). Why: NuGet ids are not namespaces; all 11 rows on `RW` were false.
- **Extension methods (M6-3).** In `cs_scip.dead_items`, a type is not listed when any member `def` inside its line range has `refs` above 0. Why: a call to `x.AddAspire()` references the method symbol, not the static class.
- **Program classes (M6-4).** After `scip_read.reduce`, drop a C# `ref-edge` whose two files belong to two different projects when neither project reaches the other through `project-reference` items (transitively). Record the count in the build log details only. Why: scip-dotnet keeps only the last namespace segment, so every top-level `Program` shares one symbol.
- **Bullseye names and project file counts (M6-5).** A `build-target` item whose `name` is empty or equals the snippet reads the first string literal after `Target(` from the file text from the start line onward (up to 5 lines). `candidates.text` counts a C# project's files as the tracked `.cs` files whose nearest project folder is that project's folder (from `cs-project` items and the `tree` argument), so test projects stop showing `0 files`; the `== Python packages ==` heading is printed only when there are Python packages or Python modules.
- **`FK` marks (M6-6).** `measured_er`: a field is `FK` when it has `ref` and is not `many`. This is page output, not adapter output; it may change the ER table of JS repositories whose relation lists are `many`. Record before and after for `JSFIX`'s Prisma models in "Results".

### D4. Candidate names (M6-7)

A unit test feeds `candidates.text` an Nx target item (`name` `api:build`, snippet `nx build`) and a package-script item, and asserts both names are printed. It is expected to pass (M4 fixed it). If it fails, fix it in the same task.

### D5. Tier B badges

- **Which languages.** A language is shown as Tier B on cards when `toolcheck.tier_of` gives `B` and it is not one of `REPO_LANGUAGES = ("Dockerfile", "Makefile", "SQL")`, which the `repo` adapter reads and which have no imports to graph. The Gaps line `{lang} has basic support only: ...` is **unchanged** for every Tier B language, including those three, so its ids stay stable.
- **Which cards.** The cards a static graph feeds: `NOGRAPH_CARDS = ("reading.order", "components.map", "components.catalog", "interactions.graph", "interactions.violations", "interactions.flows", "change.blast-radius", "change.dead-code")`. These are the `cards` of grimp and dependency-cruiser in `tools.json`, plus `change.dead-code`. The spec says "reports"; a card badge is the mechanism the page already has for partial cards and says exactly which content lacks the graph (spec issue S3).
- **What it says.** A badge `no static graph` beside the tier badge, with the tip `No import or call graph was made for {list}. Their files are in the tables but have no links.`, where `{list}` is `Shell (4 files), Rust (2 files)` in descending file count, then name. File counts come from `facts["languages"]` (check the field name in `gather.collect` before writing the test).
- **How it differs from `partial`.** `partial` means a Tier A tool did not run in this build, and goes away when the tool is installed. `no static graph` means this version of dossier has no graph tool for that language. A card can have both; the header padding rule from M4 (fix 4) is extended to two badges.
- **Code.** `process.nograph_cards(build, facts) -> {card: tip}`; `render.render_card` passes it to `schema_card`, which draws `nograph_badge(tip)` after `partial_badge`. CSS: `.badge.nograph` uses the `partial` badge's look.
- **Python golden.** It has Shell, so its eight cards gain the badge (D18).
- **Razor.** Decided: not a source language in 1.0.0 (section 4). It is neither Tier A nor Tier B; the `razor` Gaps note covers it.
- **Tier B symbols.** Not in 1.0.0 (section 3, row 5).

### D6. The freshness BAN

- **Where it is computed.** `stage_pin` calls `workarea.freshness(top, sha, ref, run, timeout=15)` and stores the result in the pin record's `details.freshness`. It never fetches and never writes to the user's repository.
- **What the ref is.** `ref` as given to `prepare` (default `HEAD`). `git rev-parse --symbolic-full-name <ref>` gives `refs/heads/X` (a branch), `refs/tags/X` (a tag), `refs/remotes/<r>/X` (a remote branch), or nothing (a commit, or a detached `HEAD`). For `HEAD`, `git symbolic-ref --quiet HEAD` names the branch when `HEAD` is attached.
- **What it compares with.** A branch: its upstream (`git rev-parse --abbrev-ref X@{upstream}`, for example `origin/main`), else `origin/X` when that exists. A remote branch: itself. A tag: the same tag on `origin`. A commit: the default branch that `workarea.trusted` already found. No remote at all: nothing.
- **Online first.** `git ls-remote --exit-code origin <refs/heads/Y or refs/tags/X>` through `sandbox.run` (profile `restricted`, cwd the user's repository, stage `freshness`, 15 s). For an annotated tag, take the `^{}` line. Exit 2 means the ref is gone from the remote. The scrubbed environment has no SSH agent and no user `~/.gitconfig`, so an SSH remote usually fails here; that is expected and falls back.
- **Offline fallback.** The local remote-tracking ref (`refs/remotes/origin/Y`), labelled "as of the last fetch", with the date of `.git/FETCH_HEAD` when it exists.
- **Counts.** When the remote commit exists locally (`git cat-file -e <sha>^{commit}`): `behind = git rev-list --count <pin>..<remote>` and `ahead = git rev-list --count <remote>..<pin>`. Otherwise both `null`, with the reason `the newer commits have not been fetched`.
- **Record.** `{"ref_kind", "compared_with", "source": "remote"|"tracking"|"none", "remote_sha", "behind", "ahead", "checked_at", "reason"}`.
- **The tile.** First tile of `dossier.about`, label `Freshness`:

| Case | Value | Note under it |
|---|---|---|
| behind 0, ahead 0 | `Up to date` | `with {compared_with}, checked {time} UTC` (or `as of the last fetch on {date}`) |
| behind n | `{n} commit(s) behind` | `{compared_with} is at {short}, checked ...` |
| ahead only | `Not on {compared_with}` | `{ahead} pinned commit(s) are not on {compared_with}` |
| tag unchanged | `Tag {X}` | `still points at this commit on origin` |
| tag moved | `Tag {X} moved` | `origin now has it at {short}` |
| not known | `Not known` | the reason, for example `The repository has no remote.` or `origin could not be reached and there is no remote-tracking branch.` |

- **`--allow-ref`.** Unaffected: freshness runs no repository code and is computed for every ref.
- **`dossier check`.** V11 (`page_audit`) gains one count: when the build has a pin record, the `dossier.about` card holds a tile labelled `Freshness`.
- **`summary.json`.** No field (section 3, row 20).
- **Incremental builds.** Report 01 is drawn by code on every render, and no written report reads freshness, so a moved remote makes nothing stale. A test asserts `candidates.digests` does not change when only freshness changes.
- **Plain words.** The README and user guide say that `prepare` asks the remote once with `git ls-remote` and falls back to the last fetch. Q3 asks whether the author wants it off by default.

### D7. Interactive graphs

**Design.** Python computes every view; the browser only switches between them. So every view can be checked by unit tests and by the browser, and the page needs no new library.

- **Hierarchy.** `components.map`: areas (`measured_graph._area_map`) → components. `interactions.graph`: areas → components → modules (module files, by `components.component_of`). Without a catalog, `interactions.graph` uses areas → modules. Files in no component sit under `unassigned`.
- **Views** (`graph_views.views(levels, edges) -> list`). One view per node that has children (the root, each area, and for `interactions.graph` each component). A view holds the focus node's children as nodes, plus one collapsed node for each other node at the parent's level that has an edge to or from those children. Edges are aggregated to the nodes shown, with weight = number of imports.
- **Node budget.** At most 12 nodes per view. When the children plus neighbours exceed 12, children are folded into **group nodes** of at most 10, in name order, labelled `{first} … {last} ({n})`; neighbours fold into one `{n} other areas` node. Each group node has a view of its own. Folding is collapsing: every child is reachable through a view, and the tables hold everything.
- **Edge budget.** At most 30 edges. When a view has more, it keeps the edges with weight at least `w`, where `w` is the smallest whole number that leaves 30 or fewer (a tie at the boundary drops the whole tie). The view's caption then says `Links with fewer than {w} imports are hidden in this view ({shown} of {total} shown). Every link is in the tables below.` This is the "filtering" that principle 7 allows.
- **Data.** Each view: `{"id", "title", "parent", "children": [view ids], "nodes": [{"id", "label", "kind": "area"|"component"|"module"|"group"|"other", "view": view id or null}], "edges": [{"from", "to", "weight"}], "hidden": {"w", "shown", "total"} or null, "src": Mermaid source}`. `src` is `flowchart LR` with one node per entry and `A -->|weight| B` per edge, node ids from `measured_graph.mermaid_id`. Written into the card as `<script type="application/json" class="igraph-data">`.
- **Markup** (in the card, above the existing tables): a toolbar (breadcrumb of view titles, an `Up` button, a `<select>` of every view by title), a `.mermaid-host` with `data-src` set to the root view, a caption line, and a list of buttons, one per node that has a view (`Open {label}`). Without JavaScript, the host shows `The interactive graph needs JavaScript. Every component and link is in the tables below.`, and the tables are complete as today.
- **Script** (`assets/dossier.js`, `initGraphs(section)`, called where `drawIn` runs): render the selected view with `mermaid.render`; after each render, attach click and Enter handlers to the SVG nodes that have a view (Mermaid's own `click` is disabled under `securityLevel: "strict"`, which the page uses); update the breadcrumb, the select, the caption and the buttons. The select keeps keyboard access complete.
- **Budget marker.** The host has no `data-budget="area"`, so the existing V12 node check applies to the shown view.
- **Report 02** does not change: the new code runs only inside `[data-card="components.map"]` and `[data-card="interactions.graph"]`.
- **Answered (Q1): build it.** The author will review the graph and may scrap it. So keep it **removable in one step**: Phase 3's graph work (M6-18 to M6-23) goes in its own commits that touch nothing outside the graph code, its tests, its mutations and the two cards' markup, so `git revert` of those commits leaves the tables and every other check passing. Phase 3 records the commit range under "Results (Phase 3)".

### D8. `--verify`

- **Flag.** `prepare --verify` (and `/dossier build --verify`, passed through by `SKILL.md`). Stored in `build.json` `options.verify`. Off by default. `per_report` comes from `verify_per_report` in the dossier config, default 5.
- **Sampling** (`verify.py`, pure). Eligible claims: `render.claims_of(rid, report)` for every authored report except `gaps`, with `conf` `confirmed` or `inferred` and at least one citation that resolves to a file range (not `facts:`, not a directory, not a commit). Sorted by (report, card, claim key), where the claim key is the existing label or, without one, the SHA-1 of the claim text. Then `random.Random(f"{seed}:{rid}").sample(eligible, min(per_report, len(eligible)))`. The **seed** is made by `verify-sample` with `secrets.token_hex(8)` after the reports are written and stored in `build.json`, so the writer cannot know or choose it, and a rerun with `--seed` gives the same sample.
- **`dossier verify-sample <repo> [--seed S] [--per-report N]`.** Prints JSON: `{"seed", "sha", "prompt": "<SKILL>/prompts/verify.md", "items": [{"id": "V01", "report", "claim", "code": [{"cite": "path:a-b", "text": "<numbered lines at the pinned commit>"}]}]}`. `claim` is the plain text with citation markers removed and no confidence label, card title or report text. It appends a `build.json` record `{"step": "check", "part": "verify-sample", "by": "verify", "status": "ok", "details": {"seed", "per_report", "items": [{"id", "report", "card", "key"}]}}`.
- **The agent.** `SKILL.md` step 7a: for each report's items, start one subagent (`subagent_type: "general-purpose"`, `model: "sonnet"`), in parallel batches of about five, whose whole prompt is the text of `prompts/verify.md` followed by that report's items as JSON. Never give it the report, the dossier folder or the repository path. It answers with a JSON array `[{"id", "verdict": "supported"|"not supported"|"cannot tell", "reason"}]`, one sentence per reason, quoting the line that decides it. Claude joins the arrays into one file in the session scratchpad.
- **`dossier verify-record <repo> --results FILE`.** Checks that every id of the latest sample appears exactly once and every verdict is one of the three words; on any error it prints the problem and exits 1 without writing. Otherwise it appends `{"step": "check", "part": "verify", "by": "verify", "status": "ok", "counts": {"sampled", "supported", "not_supported", "cannot_tell"}, "details": {"seed", "results": [{"id", "report", "key", "verdict", "reason"}]}}`. Claude never edits `build.json`; the CLI does.
- **Gaps.** For each `not supported`, kind `inference`, the claim's report, statement `A separate check could not confirm this statement from the code it cites: "{claim}"`, how to confirm `The checker said: {reason} Open the cited code, then confirm or correct the statement with /dossier confirm.` The reason sits in the "how to confirm" column so the item id (from the statement) stays stable between runs. `cannot tell` is counted on the process card only. No new Gaps kind, so `summary.json` `gaps` keeps its four keys.
- **Process card.** Step 8 gains a row `Verifier`: `{per_report} claims per report, {sampled} sampled: {supported} supported, {n} not supported, {c} cannot tell` or `not run (turn it on with --verify)`.
- **V10.** An error when a `verify-sample` record exists and no later `verify` record does: `V10: the verifier sampled claims but no results were recorded. Run dossier verify-record, or build again without --verify.` When `options.verify` is set and there is no sample yet, an `info:` line only, because the first render comes before the sample.
- **Order in `/dossier build --verify`:** render, check, `verify-sample`, the agents, `verify-record`, render. Spec issue S2.

### D9. Python projects in subfolders

- **Projects** (`py_project.projects(tree, read) -> list`, pure). A Python project folder is a tracked folder that holds `pyproject.toml`, `setup.py`, `setup.cfg` or `requirements.txt`, is not noise or a test folder (`gather.noise_reason`, `gather.TEST_RE`), and has at least one tracked non-test `.py` file below it that no deeper project folder claims. The root `""` is **always** a project, whether or not it holds a manifest. Each tracked `.py` file belongs to the deepest project folder above it. A uv workspace (`[tool.uv.workspace] members`) needs nothing special: each member has its own `pyproject.toml`, so it is its own project.
- **Root unchanged.** For a repository with no nested project folder, the result is exactly today's: one project `""` holding every file, and the adapter's output is **byte-identical** (asserted against a snapshot of `PYFIX`'s output taken before the change, and by block P).
- **Analysis per project.** The adapter's existing steps run once per project on a view of the context: `checkout = <checkout>/<folder>`, `tree` and `files` re-rooted to the folder (paths without the `folder/` prefix), and every path in the items prefixed back with `folder/` before they are joined. So package roots (`""`, `src`, configured ones) are relative to the project, module names are what Python itself would import (`app.models` for `backend/app/models.py`), grimp gets absolute roots under the project and `sys.path` from them as today, vulture gets the project's paths, and `pyproject.toml` settings (vulture, import-linter, console scripts, pytest) are read from the project's own file. Items from a nested project carry `"project": "<folder>"`; root items carry no new key.
- **scip-python.** One run per project, cwd `<checkout>/<folder>`, with `--project-name <repo>[-<folder with / as ->]` and the environment file from the nearest `.venv` at or above the project folder (`scip_tool.environment` gains a `venv` argument). Document paths are prefixed back with the folder.
- **Restore.** The `python` restore entry gains `"nested": true`, so `uv sync --frozen` runs in every folder that holds a tracked `uv.lock` (a uv workspace has one, at its root).
- **Module-name clashes.** Two projects may each have an `app` package. Graph items keep their paths, so components, blast radius and dead code (which work on paths) are right. Name-based readers (V2, V3, `candidates` module lists) may match the wrong one; `candidates` prints module names with `[folder]` for nested projects. Risk 6.
- **Version.** `PythonAdapter.version` moves up by one (with D10, once).

### D10. Python's real public API

- **Which projects.** A Python project (D9) is a **library** when it is packable (a `[build-system]` table, a `setup.py`, or a `setup.cfg` with `[metadata]`) and either has a `py.typed` file in a top-level package or declares no console or GUI scripts (`[project.scripts]`, `[project.gui-scripts]`, `[tool.poetry.scripts]`, `setup.cfg` `console_scripts`). A packable project with scripts and no `py.typed` is an **application**, as a C# `Exe` is (plan 011 D15). Why: an application's importable modules are not offered to anyone.
- **Package.** The distribution name (`[project] name`, else `[tool.poetry] name`, else `setup.cfg` `metadata.name`, else `name=` in `setup.py` read with `ast`, else the folder name).
- **Import paths.** Every module of the project's top-level packages (D9's package roots and configured packages, including configured folders without `__init__.py`, PEP 420) whose dotted path has no part starting with `_`, outside test folders. Import path = the dotted module path (`tomli`, `more_itertools.more`).
- **Names** of a module, read with `ast` from the `.py` file (from the `.pyi` file when there is no `.py`):
  1. With a module-level `__all__` that is a list or tuple of string literals (and `__all__ += [...]`, `__all__.extend([...])`): exactly those names. Audience starts `listed in __all__`.
  2. Without `__all__`: top-level `def`, `async def`, `class` and assigned names not starting with `_`; plus names imported with a relative `from .x import Y` (or `from . import y`); plus, for `from .x import *`, the names that `x` exports by these same rules. Plain `import os` and absolute imports of other distributions are not re-exports. Names bound only under `if TYPE_CHECKING:` are left out. Audience starts `public by name`.
  3. A non-literal `__all__` gives no names for that module and a `py-note` `api` (Gaps: `The public API of {package} could not be fully worked out from {module}.`, report `io`, `Read this module by hand.`).
- **Defined in.** Re-exports are followed to the defining file and line (through relative imports and star imports, at most 10 hops, cycles stopped). A name whose definition cannot be found in the project gets `path` null and `external` set to the module named.
- **Kind.** `function`, `class`, `variable`, or `module` (a re-exported submodule).
- **Audience.** `listed in __all__` or `public by name`, then `, typed` when the top-level package has `py.typed` (PEP 561: the marker covers subpackages), then `, has a stub` when a `.pyi` sits beside the `.py`.
- **Entry-point groups.** Each `[project.entry-points]` group other than console and GUI scripts (for example `pytest11`) is a contract another package can load: one row, kind `entry point ({group})`, name the entry name, import path the target's module.
- **Items.** `symbols` kind `public-api` with the JS and C# keys (`path`, `line`, `name`, `symbol_kind`, `package`, `subpath` = import path, `audience`, `external`). `measured_tables.public_api` shows them unchanged: a Python `subpath` neither starts with `.` nor is a namespace, so the existing C# branch (`importable = subpath or package`) shows it as written. Check that branch when writing M6-17's test.
- **No API.** When no project is a library and the repository has Python modules, the card shows the existing line `No package here declares a public API. What this repository offers from outside is in Entry points.` The condition grows to modules with no `language` key (Python). The golden is an application, so its `io.contracts` card gains exactly this line (D18).
- **Decision 21** (per-file public surface) is unchanged.
- **Staleness.** `FEEDS["io"]` already holds `public_api`; Python items now feed it.

### D11. The blind-spot review (6.4)

Hit counts from plan 011 ("Verification results") and plan 010; `-` means not recorded. Phase 7's block BS fills in counts for every built dossier. Every pattern in the table has fixed wording in `checks_v7.BLIND_SPOTS`; positive and negative cases live in `tests/fixtures/semgrep/<lang>/blindspot.*` with `ruleid:` and `ok:` lines (checked by `test_rules.py`).

| Pattern id | Python | TS/JS | C# | All | Seen | Ruling |
|---|---|---|---|---|---|---|
| `dynamic-import` | `importlib`, `__import__` | `import()` with a computed target | (in `reflection`: `Assembly.Load`) | | - | keep |
| `entry-point-loading` | `entry_points(...)` | n/a | n/a | | - | keep |
| `string-plugin` | plugins named by string | covered by `dynamic-require` | covered by `reflection` | | - | keep |
| `decorator-registry` | decorator tables | n/a (decorators are rare outside frameworks) | attributes are read by the extractors; filters by `mvc-filter` | | - | keep |
| `getattr-dispatch` | `getattr(obj, name)` | `obj[name]()` | covered by `reflection` | | - | JS: leave, a computed member call matches almost every file |
| `django-apps`, `django-signals` | yes | n/a | n/a | | - | keep. Event emitters in JS (`on("x")`) and C# events (`+=`): leave, too common to be a useful hit |
| `pytest-fixtures` | yes | Playwright `test.extend` | xUnit fixtures (read by the tests extractor) | | - | leave the JS gap: fixtures are test-only and the tests card counts them |
| `computed-subcommand` | yes | yes | n/a | | - | C#: leave; the `cli-command` rule reads literal names and a computed one is rare |
| `string-route` | **missing** | yes | yes | | `CA` 15 | **add for Python (M6-29)**: `@app.route(x)` and `add_url_rule(x, ...)` with a non-literal path |
| `route-mount` | **missing** | yes | yes | | `CA` 1 | **add for Python (M6-29)**: FastAPI `include_router(..., prefix=...)` and `APIRouter(prefix=...)`, Flask `Blueprint(..., url_prefix=...)` and `register_blueprint(..., url_prefix=...)`, Starlette and FastAPI `mount(...)`, Django `include(...)` |
| `barrel-reexport` | **missing** | yes | n/a | | `BP` - | **add for Python (M6-30)**: `from x import *` in an `__init__.py`. grimp links an importer to the package `__init__`, not to the module that defines the name |
| `dynamic-require` | n/a | yes | n/a | | - | keep |
| `react-context`, `hook-wiring` | n/a | yes | n/a | | `BP` - | keep |
| `module-federation` | n/a | yes | n/a | | - | keep |
| `di-registration` | none (decision 11) | yes | yes | | `CA` 8 | Python: leave (decision 11). FastAPI `Depends(...)` goes to `post-v1.md` as a candidate |
| `di-scan`, `di-resolution` | n/a | n/a | yes | | `CA` 3, 10 | keep |
| `reflection` | covered by `getattr-dispatch`, `dynamic-import` | covered by `dynamic-require` | yes | | `CA` 4 | keep |
| `route-convention`, `conventional-route`, `mvc-filter`, `mediator-handler` | n/a | n/a | yes | | `CA` mediator 30 | keep |
| `source-generator` | n/a | n/a | yes | | `RW` notes 2 | keep |
| `partial-class` | n/a | n/a | yes | | - | keep (a C# language feature) |
| `codegen` | | | own rule (`<auto-generated`) | generic header rule | - | keep |
| `feature-flag` | | | own rule | generic rule | - | keep |
| runtime config selecting implementations | | | | fixed item, no rule | every build | keep; M6-33 asserts it appears exactly once in a mixed extract |

No existing rule is weakened or removed. The three new Python rules reuse existing ids, so their Gaps wording already exists.

### D12. The `repo` adapter

- **`ci-trigger` for all (M6-32).** `wants_triggers` is removed; every repository gets push, pull-request and manual trigger rows. `RepoAdapter.version` moves up by one.
- **Container and compose inputs (M6-31).** `Dockerfile*` and `Containerfile` lines `ENV K=v ...`, `ENV K v` and `ARG K[=v]` give `env-var` items (rule `repo.dockerfile-env`, `detail` K, one per name and file). `docker-compose*.yml`, `compose*.yml` and `compose*.yaml`: each key under a service's `environment:` (list `- K=v` or map `K: v`, read line by line by indentation, as `workflow_triggers` reads YAML) gives an `env-var` item (`repo.compose-env`), and each `env_file:` value gives a `config-file` item (`repo.compose-env-file`). Values are never stored.

### D13. Docs drift test (M6-34)

`dossier.py`'s parser moves into `build_parser() -> argparse.ArgumentParser`, which `main` calls. `tests/unit/scripts/test_docs.py`:

1. Every subcommand of `build_parser()` and every option string of every subcommand (except `-h`/`--help`) appears in `docs/user-guide.md`.
2. Every user command in `SKILL.md`'s `argument-hint` has a `### \`/dossier <cmd>` section in `SKILL.md`, and every flag of `prepare` that a user may pass appears in the `build` hint.
3. None of `README.md`, `SKILL.md`, `prompts/method.md`, `prompts/reports.md`, `rules/README.md`, `docs/user-guide.md`, `docs/developer-guide.md` matches `(?i)\b(capabilities|interfaces|architecture|domain logic|code tour|failures|delivery)\s+report\b`, `(?i)twelve reports` or `(?i)the contributors report has a card`.
4. `README.md` names report 02 (This repository) as the home of the Contributors cards.

### D14. Test page (M6-24)

`tests/tools/m6_page.py`, in the style of `m5_page.py`: 60 components over 15 areas, 400 modules with 1,200 imports (enough for group nodes and the edge filter), a Shell and a Rust file (Tier B badges), a pin record with freshness (`behind` 3), 40 Python `public-api` items from two packages, and three verifier Gaps items. `dossier check` must report `problems: 0` on it at both widths and themes.

### D15. Mutations (M6-23)

`broken_pages.py` gains: `graph-data-removed` (delete the `igraph-data` script of `components.map`: the browser check must say the card has no views), `graph-view-over-budget` (add a 13-node view to the data: the per-view check must fail), `graph-buttons-dead` (rename the class the script looks for, so opening a view changes nothing: the check that clicks a button and expects a new breadcrumb must fail), `graph-node-missing` (remove one component from every view: V11 must fail), and `nograph-badge-overlap` (give the header badges a negative margin so the title runs under them: the overlap check must fail). Each joins `test_each_browser_mutation_makes_a_fail` or the V11 mutation test with the line it must produce.

### D16. Docs

- `README.md`: rewritten to the `docs-readme` order: title `dossier`, one line, a sample of the page (one screenshot from the M6 test page, saved as `docs/images/dossier.png`), usage (`/dossier home`, `build`, `confirm`, `correct`, `doctor`, `check`, `clean`), install (Claude Code, `uv`, `git`; Node 22.13 or later for JS and TS, 16 or later for Python alone, not 23 or 25; the .NET SDK per `global.json`, 8 or later otherwise; `gh` optional; Playwright's Chromium for `check`), goals and status (what it is for, non-goals from spec section 1, status `active`, maintained by the author alone), documentation links by audience, licence. No version history, no option reference.
- `docs/user-guide.md`: overview (reports 01 to 16 by number and title, tiers M/A/R, confirmed/inferred/unknown, Tier A and Tier B, badges `partial` and `no static graph`), installation, getting started (a first build), usage by task (build, update, confirm, correct, check, clean, doctor, verify, read freshness, use the graphs, the code viewer, tables, the Contributors cards in report 02 with Owner and Author), reference (every `/dossier` command and every CLI subcommand and flag, from `build_parser`; config keys `home`, `cache_dir`, `timeouts.*`, `registry_auth`, `verify_per_report`; files in the dossier folder), restore hygiene in plain words, troubleshooting (missing tools, `TOO OLD`, the restore question, untrusted refs, V4/V5 errors, `check` failures), limitations (blind spots, Tier B, provisional TS and C# figures).
- `docs/developer-guide.md`: overview, getting started (clone, the two test commands with expected counts), layout, architecture (the pipeline `prepare` → reports → `render` → `check`, adapters, schema, checks V1 to V12, staleness), recipes (add a rule, add a card field, add an adapter, add a check with a mutation), testing (fixtures, slow tests, `--basetemp`, the three known failures, the test pages), conventions, configuration, release (D17), troubleshooting, gotchas (report 02 frozen, `INSTALLED` is a clone, `/tmp` is small), LLM prompts.
- `LICENSE`: MIT, `Nick OMalley <nickpeteromalley@gmail.com>`, year 2026 (the skill's first commit is in 2026; confirm with `git log --reverse --format=%ad -- . | head -1`). The README's "No license for the skill itself yet" goes. Q6.
- `SKILL.md`: `--verify` in the build hint and steps (D8), the freshness sentence in step 1, the badges in step 8's reading notes. `prompts/method.md` and `prompts/reports.md`: the two graphs are drawn by code (never describe them in a card), Tier B files have no links (say so when a component is Tier B), Python libraries' API table (never copy it). `rules/README.md`: the three new Python rules.

### D17. Version and release

`VERSION` becomes **1.0.0** in M6-41, on the feature branch, as M4 and M5 did; the skill has no bump tool and no CI (Q5). A major bump plans a full rebuild (`update_plan` compares `major.minor`). Adapter versions move only through their tasks (python, csharp, repo; js does not move). `summary.json` `schema_version` stays **1**: M6 adds no field and removes none.

### D18. Deliberate changes to existing output

| Change | Task | Python golden | JS (`JSFIX`, `BP`) | C# (`RW`, `CA`) |
|---|---|---|---|---|
| `no static graph` badges | M6-8 | yes (Shell): 8 cards | `JSFIX`: if it has a Tier B language (record) | `RW`, `CA`: Shell (record) |
| Freshness tile | M6-10 | report 01 (not compared) | report 01 | report 01 |
| Interactive graph above the tables | M6-20 | reports 05, 06 | reports 05, 06 | reports 05, 06 |
| No-API line for Python applications | M6-17 | `io.contracts` gains one line | none | none |
| `FK` only on non-list references | M6-6 | none (no ER `many`) | ER tables (record) | ER tables |
| `ci-trigger` rows for every language | M6-32 | `repo` items if the golden has GitHub workflows (record) | `JSFIX` if it has workflows | none (already) |
| Dockerfile and compose variables | M6-31 | none (no Dockerfile) | `JSFIX` has a Dockerfile: `repo` items | `RW`, `CA` |
| Python route and barrel blind spots | M6-29, M6-30 | only if the golden has those patterns (record) | none | none |
| NuGet unused rows, extension-method types, cross-project edges, Bullseye names, Aspire | M6-1 to M6-5 | none | none | `RW`, `CA` |
| `eol.json` refresh | M6-40 | upgrade-burden "latest" values may move | same | same |

Anything that changes and is not in this table is a bug.

### D19. Test repositories for the definition of done

- **Python (item 2):** `REPO`, the author's own, through block P2 (the LIVE reports copied, new findings decided in the copy only).
- **TS/React (item 2):** `BP`. Plan 010's primary `RW` (`gothinkster`) has no licence and no React; `BP` is MIT, is React, built cleanly in M4 (`problems: 0`), and has three yarn projects. No ground truth exists for it (M4 built none for `BP`).
- **C# (item 2):** `RW`, with the kept truth.
- **Also:** `CA` (largest; C#, Angular, React; freshness with a moved HEAD), the mixed fixture of M6-14 (smallest), and the libraries `TO`, `MI`, `GC`, `ZU` (prepare only).

### D20. Sessions and cut line

| Phase | Model | Content | Why this cut |
|---|---|---|---|
| 1 | Sonnet | Carry-ins, Tier B badges, freshness | Small and independent; the required Aspire fix comes first |
| 2 | Sonnet | Python subfolders and the real public API | Both change the Python adapter; one version bump |
| 3 | Sonnet | Interactive graphs, V11 and V12 checks, mutations, the M6 test page | The largest piece of page work; needs its own context |
| 4 | Sonnet | `--verify`, Python blind spots, `repo` inputs and triggers | Each is small; the CLI work fits with the Gaps work |
| 5 | Sonnet | Docs, drift test, licence, `post-v1.md`, `eol.json`, `VERSION` | Docs describe what Phases 1 to 4 built |
| 6 | Sonnet | Golden, JS run, `RW` build and re-score, incremental, suites | A full build of `RW` needs a clean context |
| 6a | Opus | Rulings on new disagreements only. Skipped when there are none | Sonnet must not judge its own misses (decision 34) |
| 7 | Sonnet | `BP`, mixed fixture, libraries, Tier B page, `--verify` for real, freshness offline, degraded builds | All need only `RW` from Phase 6 |
| 8 | Sonnet | `CA` with freshness online, skeletons, `check` everywhere, suites, DoD table, merge, fresh-clone install check | The largest repository last, then the release |

`process.md` says one session; the author accepted nine (Q2), and Phase 5 updates that row.

**Cut, in this order, only if a phase cannot finish** (the spec's cut line: P1 cards, then Tier B polish): M6-40 (`eol.json` refresh, feeds the P1 upgrade card); M6-31 (compose and Dockerfile inputs); M6-6 (`FK` marks); the `ahead` and tag rows of D6's tile (keep behind, up to date and not known); D5's file counts in the badge tip (keep the language names). Record any cut under "Results"; it becomes the first item of `post-v1.md`.

**Never cut:** tests for anything new; V2 to V5; the plan 008 checks on anything new (M6-21 to M6-24); M6-1; the Tier B badge itself; `--verify`; the Python public API and subfolder fix; the docs drift test; `VERSION` 1.0.0; the definition-of-done verification (Phases 6 to 8).

### Results (planning)

Baselines at `51b056e` (2026-11-09, clean tree): default **2631 passed, 274 skipped (70 s)**; slow (`--basetemp=$HOME/.cache/dossier-m6-slow`, removed afterwards): **3 failed, 2901 passed, 1 skipped in 22 min 53 s**. The three failures are exactly the known ones.

---

## Phase 1: Carry-ins, Tier B badges and freshness

### Before you start (Phase 1)

Read sections 2 to 4, D2 to D6, D18 and D20. Load the skills in section 2. Then:

1. `git -C $SKILL log --oneline -3` and `git -C $SKILL status --short`. The top must be `51b056e` or a later commit that touches none of `scripts/`, `prompts/`, `rules/`, `assets/`, `tests/`. Tracked changes you did not make: stop and ask the author.
2. Read sections 8 and 9 for any answer the author added; use it where it differs from the defaults, and say so in "Results (Phase 1)".
3. Run the default suite and the slow suite (`--basetemp=$HOME/.cache/dossier-m6-slow`); record both counts. Only the three known failures may fail.
4. `git switch -c feat/dossier-m6`.

### Tasks (Phase 1)

- [x] **M6-1. Read the Aspire SDK from the project file.**
  - Goal: D2; the required carry-in.
  - Files: `scripts/cs_project.py`, `scripts/cs_adapter.py` (version), `tests/unit/scripts/test_cs_project.py`, `tests/unit/scripts/test_cs_adapter.py`, `tests/unit/scripts/test_csfixture.py`, `tests/integration/scripts/test_cs_adapter_slow.py`; new `tests/fixtures/csrepo/tools/AppHost/AppHost.csproj` and `tests/fixtures/csrepo/tools/AppHost/Program.cs`.
  - Interface: project dicts gain `"sdks": [names]` (all SDK names, version stripped); `SDK_FRAMEWORKS`; `frameworks_named` reads packages and `sdks`.
  - Steps: (1) Unit tests: `<Project Sdk="Aspire.AppHost.Sdk/13.6.4">` with no package gives `Aspire.Hosting.AppHost`; `<Project Sdk="Microsoft.NET.Sdk"><Sdk Name="Aspire.AppHost.Sdk" Version="13.0.0" />` gives it too; `Sdk="A;B/1.0"` gives both names; the existing `sdk` field is unchanged (first name). (2) Fixture: `AppHost.csproj` is `<Project Sdk="Aspire.AppHost.Sdk/13.6.4">` with `OutputType Exe` and `TargetFramework net10.0`, in no solution, with a `Program.cs` holding one top-level statement (`// @ep-apphost`). Update the expected counts in the named tests in this commit, and nothing else: C# projects 8 to 9, one more `no-lock` note, one more `framework` note (`Aspire.Hosting.AppHost`), one more `program-main` entry. (3) Implement; `CSharpAdapter.version` up by one.
  - Done-check: `uv run --with pytest --with pygments python -m pytest tests/unit/scripts/test_cs_project.py tests/unit/scripts/test_cs_adapter.py tests/unit/scripts/test_csfixture.py -q` passes; `DOSSIER_SLOW=1 ... tests/integration/scripts/test_cs_adapter_slow.py -q --basetemp=$HOME/.cache/dossier-m6-slow` passes.
  - Commit: `fix(dossier): read the Aspire SDK named in a C# project file`

- [x] **M6-2. Leave unused NuGet packages out of dead code.**
  - Goal: D3, first bullet.
  - Files: `scripts/measured_change.py`, `scripts/checks_v7.py` (the fixed item in `cs_coverage`), `tests/unit/scripts/test_measured_change.py`, `tests/unit/scripts/test_checks_v7.py`.
  - Steps: (1) Tests: a `dependencies` blob with one NuGet and one npm unused row gives only the npm row; the Gaps item appears once with a C# module and not without one; Python and JS rows unchanged (assert today's lists). (2) Implement.
  - Done-check: the two test files pass; block E prints `OK`.
  - Commit: `fix(dossier): stop listing NuGet packages as unused`

- [x] **M6-3. Keep a C# type off the dead list when one of its members is used.**
  - Goal: D3, second bullet.
  - Files: `scripts/cs_scip.py`, `tests/unit/scripts/test_cs_scip.py`.
  - Steps: test: a static class whose extension method `def` has `refs` 1 is not listed; one with all members at 0 still is. Implement.
  - Done-check: `... pytest tests/unit/scripts/test_cs_scip.py -q` passes.
  - Commit: `fix(dossier): treat a used extension method as a use of its class`

- [x] **M6-4. Drop C# reference edges between unrelated projects.**
  - Goal: D3, third bullet.
  - Files: `scripts/cs_scip.py`, `scripts/cs_adapter.py`, `tests/unit/scripts/test_cs_scip.py`, `tests/integration/scripts/test_cs_adapter_slow.py`.
  - Interface: `cs_scip.drop_unrelated(items, projects, project_of) -> (items, dropped)`.
  - Steps: (1) Tests: an edge `src/Shop.Api/Program.cs` → `tools/Legacy/Program.cs` is dropped; `src/Shop.Api` → `src/Shop.Core` (referenced) kept; a test project → the project it references kept; a transitive reference kept. Slow: the fixture's false Program edges are gone; record the dropped count. (2) Implement; record `dropped` in the adapter's details.
  - Done-check: the unit test passes; the slow test passes.
  - Commit: `fix(dossier): drop C# references between projects that do not reference each other`

- [ ] **M6-5. Bullseye names and C# project file counts.**
  - Goal: D3, fourth bullet.
  - Files: `scripts/cs_semgrep.py`, `scripts/candidates.py`, `tests/unit/scripts/test_cs_semgrep.py`, `tests/unit/scripts/test_candidates_cli.py`.
  - Steps: (1) Tests: a `Target(\n    "test",\n    ...)` hit gets name `test`; a test project with three `.cs` files prints `3 files`; a C#-only extract prints no `== Python packages ==` heading; Python and JS texts unchanged (assert today's). (2) Implement.
  - Done-check: both test files pass.
  - Commit: `fix(dossier): name multi-line Bullseye targets and count test project files`

- [ ] **M6-6. `FK` only on references that are not lists.**
  - Goal: D3, fifth bullet. Cut item 3 in D20.
  - Files: `scripts/measured_er.py`, `tests/unit/scripts/test_measured_er.py`.
  - Steps: test: a field with `ref` and `many` shows no `FK`; with `ref` alone shows `FK`; `pk` unchanged. Implement. Record before and after for `JSFIX`'s Prisma model fields (run the ER helper on its extract in the test or a one-off script; no commit of output).
  - Done-check: the test passes; block E prints `OK`.
  - Commit: `fix(dossier): mark only single references as foreign keys`

- [ ] **M6-7. Prove candidate names are shown.**
  - Goal: D4.
  - Files: `tests/unit/scripts/test_candidates_cli.py` (and `scripts/candidates.py` only if the test fails).
  - Steps: the test of D4. Record in "Results" whether it passed at once; M6-39 then removes P4-3 from `post-v1.md`.
  - Done-check: the test passes.
  - Commit: `test(dossier): check that candidates names Nx targets and package scripts`

- [ ] **M6-8. "No static graph" badges.**
  - Goal: D5.
  - Files: `scripts/process.py`, `scripts/render.py`, `assets/dossier.css`, `tests/unit/scripts/test_process.py`, `tests/unit/scripts/test_render_cards.py`; new `tests/integration/scripts/test_tierb_slow.py`.
  - Interface: `process.REPO_LANGUAGES`, `process.NOGRAPH_CARDS`, `process.nograph_cards(build, facts) -> dict`; `render.nograph_badge(tip)`; `schema_card(..., nograph=None)`.
  - Steps: (1) Unit tests: a build whose tools record lists Python (A), Shell (B) and SQL (B) badges the eight cards with a tip naming Shell only; Dockerfile, Makefile and SQL alone give no badge; the Gaps lines are exactly today's; a card with both `partial` and `no static graph` shows both badges in that order; a Python-only build gives no badge and byte-identical card HTML. (2) Slow: a `tmp_path` repository with `PYFIX`'s files, plus `native/lib.rs` and `tools/run.sh`, one commit; `prepare --no-restore` then `render --allow-errors --partial`; the page holds 8 `class="badge nograph"` and the tip names `Rust (1 file), Shell (...)`. (3) Implement. (4) Block E.
  - Done-check: the three test files pass (the slow one with `DOSSIER_SLOW=1`); block E prints `OK`.
  - Commit: `feat(dossier): badge the graph cards when a language has no static graph`

- [ ] **M6-9. Record the Tier B and Razor decisions.**
  - Goal: D5's last two bullets, so later phases do not reopen them.
  - Files: this plan ("Results (Phase 1)") and `tests/unit/scripts/test_process.py`.
  - Steps: a test that a `.razor` file gives no language row and no Tier B item (pins today's behaviour); write the two decisions under "Results".
  - Done-check: the test passes.
  - Commit: `test(dossier): pin that Razor files are not a language`

- [ ] **M6-10. The freshness BAN.**
  - Goal: D6.
  - Files: `scripts/workarea.py`, `scripts/stages.py`, `scripts/render.py` (`panel_dossier`), `scripts/page_audit.py`, `tests/unit/scripts/test_workarea.py` (create if absent), `tests/unit/scripts/test_render.py`, `tests/unit/scripts/test_page_audit.py`, `tests/unit/scripts/test_candidates.py`, `tests/integration/scripts/test_workarea.py`.
  - Interface: `workarea.freshness(top, sha, ref, run, timeout=15) -> dict` (D6's record; `run` is `sandbox.run` with `area` bound, replaced by a fake in unit tests); `render.freshness_tile(rec) -> (label, value, note)`.
  - Steps: (1) Unit tests with a fake `run` and fake git answers, one per row of D6's tile table, plus: ls-remote exit 2 (`the ref no longer exists on origin`), a timeout (falls back to tracking), no remote, an annotated tag (`^{}` line used). (2) Integration test with real git in `tmp_path`: a bare "remote" with three more commits than a clone pinned at an older commit, the clone fetched: online gives `behind 3`; with the remote URL pointing at a missing folder, tracking gives `behind 3` and `source: "tracking"`; a commit made only in the clone gives `ahead 1`. (3) `stage_pin` records it; `panel_dossier` draws it first; `page_audit` counts it. (4) A test that `candidates.digests` is the same for two builds that differ only in freshness. (5) Block E.
  - Done-check: the named test files pass; block E prints `OK`.
  - Commit: `feat(dossier): show how far the pinned commit is behind its branch`

### Deliverables and checks (Phase 1)

| Deliverable | Checked by |
|---|---|
| Aspire note | `test_cs_project.py`, `test_cs_adapter_slow.py` |
| C# precision | `test_measured_change.py`, `test_cs_scip.py`, `test_cs_semgrep.py`, `test_candidates_cli.py` |
| `FK` marks | `test_measured_er.py` |
| Tier B badges | `test_process.py`, `test_render_cards.py`, `test_tierb_slow.py` |
| Freshness | `test_workarea.py` (unit and integration), `test_render.py`, `test_page_audit.py`, `test_candidates.py` |

### Cut line (Phase 1)

M6-6 only (D20). **Never cut** M6-1, M6-8 or M6-10's behind / up to date / not known rows.

### Acceptance criteria (Phase 1)

- The full suite passes; the slow suite passes except the three known failures; `test_py_adapter_slow.py` and `test_js_adapter_slow.py` pass unedited.
- Block E printed `OK` after M6-2, M6-6, M6-8 and M6-10.

### Branch and release (Phase 1)

Commit each task on `feat/dossier-m6`. Do not merge or bump. Write "Results (Phase 1)" and commit: `docs(dossier): record phase 1 of M6 in plan 012`.

### Results (Phase 1)

---

## Phase 2: Python projects in subfolders and the real public API

### Before you start (Phase 2)

Read section 2, D9, D10, D18 and "Results (Phase 1)". Load the skills in section 2. `git switch feat/dossier-m6`. Do first any task moved here.

### Tasks (Phase 2)

- [ ] **M6-11. Snapshot today's Python output, then find Python projects.**
  - Goal: D9's project rule, with the root result frozen first.
  - Files: new `scripts/py_project.py`, `tests/unit/scripts/test_py_project.py`, `tests/integration/scripts/test_py_root_unchanged_slow.py`.
  - Interface: `projects(tree, read) -> [{"dir", "manifests": [...], "files": [...]}]`.
  - Steps: (1) **Before any adapter change**, write the slow test: it builds `PYFIX` with `build_py_repo`, runs `stage_extract`, and compares the `python` section of every output with a JSON snapshot it writes to `tests/fixtures/py_snapshot/` on first run when the folder is missing (commit the snapshot; it is generated from original fixture code). Run it once to create the snapshot, then once more to pass. (2) Unit tests for `projects`: root only; `backend/pyproject.toml` beside `frontend/`; `requirements.txt` in `tools/` with `tools/run.py`; a nested project inside the root project; a uv workspace with two members; `docs/requirements.txt` with `docs/conf.py` (a project); a manifest folder with no `.py` file (not a project); `tests/pyproject.toml` (not a project); noise folders ignored. (3) Implement.
  - Done-check: `... pytest tests/unit/scripts/test_py_project.py -q` passes; `DOSSIER_SLOW=1 ... tests/integration/scripts/test_py_root_unchanged_slow.py -q --basetemp=$HOME/.cache/dossier-m6-slow` passes.
  - Commit: `feat(dossier): find Python projects below the repository root`

- [ ] **M6-12. Run the Python adapter once per project.**
  - Goal: D9's analysis per project.
  - Files: `scripts/py_adapter.py`, `scripts/py_packages.py`, `scripts/scip_tool.py`, `tests/unit/scripts/test_py_adapter.py`, `tests/unit/scripts/test_scip_tool.py`, `tests/integration/scripts/test_py_root_unchanged_slow.py`.
  - Interface: `PythonAdapter._extract_project(ctx, folder) -> dict`; `py_packages` functions take the project folder's checkout path (they already take `checkout`); `scip_tool.environment(checkout, venv=None)`; `scip_tool.run_index(..., cwd=None, project_name=None)`.
  - Steps: (1) Unit tests on hand-made trees with fake tools: a `backend/app/` package gives modules `app` and `app.models` with paths under `backend/`, items carry `project: "backend"`; root items carry no `project` key; grimp gets roots under `<checkout>/backend`; vulture paths are under `backend/`; console scripts from `backend/pyproject.toml` have `path` `backend/pyproject.toml`; scip-python runs with cwd `<checkout>/backend` and its document paths come back prefixed; the environment file comes from `backend/.venv`, else `.venv`. (2) Implement. (3) The root snapshot test must still pass unedited.
  - Done-check: the unit tests pass; the root snapshot test passes; `test_py_adapter_slow.py` passes unedited.
  - Commit: `feat(dossier): analyse each Python project in its own folder`

- [ ] **M6-13. Restore nested uv projects.**
  - Goal: D9's restore bullet.
  - Files: `scripts/tools.json`, `tests/unit/scripts/test_restore.py`.
  - Steps: tests: `backend/uv.lock` gives a plan with `dir` `backend`; root `uv.lock` unchanged; npm, yarn, pnpm and nuget plans unchanged (asserted). Implement (`"nested": true`).
  - Done-check: `... pytest tests/unit/scripts/test_restore.py -q` passes.
  - Commit: `feat(dossier): restore Python projects that have their own uv.lock`

- [ ] **M6-14. The mixed fixture with Python in a subfolder.**
  - Goal: the test of record for D9.
  - Files: new `tests/integration/scripts/test_mixed_pysub_slow.py`; `tests/conftest.py` (a `build_mixed_pysub_repo(dest)` helper: `PYFIX` under `backend/`, `JSFIX/packages/web` under `frontend/`, one commit).
  - Steps: assert: `python` and `js` sections exist; grimp `ok` (not `No Python package was found`); module names are those of `PYFIX` built alone (same set), with paths under `backend/`; `console-script` entries cite `backend/pyproject.toml`; no `partial` card for grimp; ids unique; `candidates --report components` prints `== Python packages ==` with `[backend]`.
  - Done-check: `DOSSIER_SLOW=1 ... tests/integration/scripts/test_mixed_pysub_slow.py -q --basetemp=$HOME/.cache/dossier-m6-slow` passes.
  - Commit: `test(dossier): build a repository whose Python lives in backend`

- [ ] **M6-15. The Python library fixture.**
  - Goal: known answers for D10.
  - Files: new `tests/fixtures/pylib/**`, `tests/unit/scripts/test_pylibfixture.py`; `tests/conftest.py` (`PYLIB`, `build_pylib_repo`).
  - Content (original code, each file under 40 lines, markers `# @<name>`): `typedlib/` (src layout: `pyproject.toml` with hatchling, `[project] name = "typedlib"`, `[project.entry-points."demo.plugins"] fast = "typedlib.plugins:Fast"`; `src/typedlib/__init__.py` with `__all__ = ["parse", "Config", "VERSION"]` and `from ._core import parse, Config` (`@api-reexport`), `VERSION = "1"`, a private `_helper`; `src/typedlib/_core.py` defining `parse` (`@api-parse`) and `Config` (`@api-config`); `src/typedlib/plugins.py` (no `__all__`) with `class Fast` (`@api-fast`), `def _hidden`, `if TYPE_CHECKING: from typing import Any` and `Alias = int`; `src/typedlib/py.typed`; `src/typedlib/plugins.pyi`); `flatlib/` (flat layout: `pyproject.toml` with flit, no scripts; `flatlib/__init__.py` with `from .one import *` and `from .two import *` and no `__all__`; `one.py` with `__all__ = ["a"]` and `def a`, `def b`; `two.py` with no `__all__`, `def c`, `def _d`); `app/` (`pyproject.toml` with `[project.scripts] run = "app.main:main"`, no `py.typed`; `app/main.py`); `badlib/` (`pyproject.toml`; `badlib/__init__.py` with `__all__ = names()`).
  - Steps: (1) The marker test. (2) Write the fixture.
  - Done-check: `... pytest tests/unit/scripts/test_pylibfixture.py -q` passes.
  - Commit: `test(dossier): add the Python library fixture`

- [ ] **M6-16. Work out a Python library's public API.**
  - Goal: D10.
  - Files: new `scripts/py_api.py`, `tests/unit/scripts/test_py_api.py`.
  - Interface: `is_library(project, read) -> bool`; `distribution_name(project, read) -> str`; `items(project, roots, tree, read) -> (symbols, notes)`.
  - Steps: (1) Tests on `PYLIB`: `typedlib` rows `typedlib`: `parse`, `Config` (defined in `_core.py`), `VERSION`, audience `listed in __all__, typed`; `typedlib.plugins`: `Fast` (`public by name, typed, has a stub`), not `_hidden`, not `Any`, `Alias` present; no row for import path `typedlib._core`; one `entry point (demo.plugins)` row `fast`. `flatlib` rows `flatlib`: `a`, `c` (through the star imports), not `b`, not `_d`; plus `flatlib.one`: `a`; `flatlib.two`: `c`; audience `public by name` for `flatlib`. `app` is not a library. `badlib` gives no names and one `api` note. A re-export cycle stops. (2) Implement with `ast` only.
  - Done-check: `... pytest tests/unit/scripts/test_py_api.py -q` passes.
  - Commit: `feat(dossier): find what a Python library offers to other packages`

- [ ] **M6-17. Wire the Python API into the adapter and the card.**
  - Goal: D10's items, note and no-API line.
  - Files: `scripts/py_adapter.py` (version up by one for D9 and D10 together), `scripts/measured_tables.py`, `scripts/checks_v7.py` (the `py-note` `api` wording), `tests/unit/scripts/test_measured.py`, `tests/unit/scripts/test_checks_v7.py`, `tests/integration/scripts/test_py_root_unchanged_slow.py`.
  - Steps: (1) Tests: `public_api` shows Python rows with Import path as written; a Python application extract shows the no-API line; an extract with no modules shows nothing; JS and C# HTML byte-identical to today (assert). The root snapshot: `PYFIX` is an application (check its `pyproject.toml`; if it is a library, record its new rows as the one deliberate snapshot change, regenerate the snapshot in this commit and list the diff in "Results"). (2) Implement. (3) Block E.
  - Done-check: the test files pass; block E prints `OK`.
  - Commit: `feat(dossier): show the Python public API in the contracts card`

### Deliverables and checks (Phase 2)

| Deliverable | Checked by |
|---|---|
| Projects and per-project analysis | `test_py_project.py`, `test_py_adapter.py`, `test_scip_tool.py` |
| Root unchanged | `test_py_root_unchanged_slow.py`, `test_py_adapter_slow.py` |
| Nested restore | `test_restore.py` |
| Mixed fixture | `test_mixed_pysub_slow.py` |
| Public API | `test_pylibfixture.py`, `test_py_api.py`, `test_measured.py` |

### Cut line (Phase 2)

Nothing is cut (D20, never cut).

### Acceptance criteria (Phase 2)

- The suites pass, except the three known failures. The root snapshot is unchanged, or changed only as M6-17 records.
- `prepare --no-restore` of `build_pylib_repo` output, run once by hand, gives `public-api` items for `typedlib` and `flatlib` only. Record the counts.

### Branch and release (Phase 2)

Commit on `feat/dossier-m6`. Do not merge or bump. Write "Results (Phase 2)" and commit: `docs(dossier): record phase 2 of M6 in plan 012`.

### Results (Phase 2)

---

## Phase 3: Interactive graphs

### Before you start (Phase 3)

Read section 2, D7, D14, D15 and "Results" of Phases 1 and 2. Load the skills in section 2. `git switch feat/dossier-m6`. Read `scripts/measured_graph.py`, the `drawIn` and blast-radius parts of `assets/dossier.js`, `scripts/check_layout.py` and the M5 test page `tests/tools/m5_page.py` before writing code.

### Tasks (Phase 3)

- [ ] **M6-18. Compute the graph views.**
  - Goal: D7's views, budgets and filter, as pure Python.
  - Files: new `scripts/graph_views.py`, `tests/unit/scripts/test_graph_views.py`.
  - Interface: `views(levels, edges, title) -> list` where `levels` is `{node: parent}` with `None` for top-level nodes and `edges` is `{(a, b): weight}` at leaf level; `mermaid(view) -> str`.
  - Steps: (1) Tests: 5 areas give a root view of 5 nodes; 30 areas give a root view of 3 group nodes of 10 areas each, and each group has its own view of 10 nodes; an area with 25 components gives group nodes of 10, 10 and 5, each with its own view; neighbours fold into one `other` node past 12; every leaf is a node of at least one view; every view has at most 12 nodes and 30 edges; 47 edges with weights give the smallest threshold leaving at most 30 and the `hidden` numbers; a tie at the boundary drops the whole tie; the Mermaid source parses as `flowchart LR` with the right node and edge counts (count lines); ids are unique per view. (2) Implement.
  - Done-check: `... pytest tests/unit/scripts/test_graph_views.py -q` passes.
  - Commit: `feat(dossier): compute collapsible views of the component and module graphs`

- [ ] **M6-19. Draw the graph in the two cards.**
  - Goal: D7's markup and data.
  - Files: `scripts/measured_graph.py`, `tests/unit/scripts/test_measured.py`.
  - Steps: (1) Tests: `components.map` and `interactions.graph` hold one `igraph-data` script, a host with the root view's `data-src`, the no-JavaScript sentence, a select with one option per view, a button per node with a view; the existing tables come after, byte-identical to today's; a card with no imports keeps its `No imports between modules were found.` line and draws no graph. (2) Implement. (3) Block E.
  - Done-check: the test file passes; block E prints `OK`.
  - Commit: `feat(dossier): add the interactive graph to the component map and dependency graph`

- [ ] **M6-20. The page script for the graph.**
  - Goal: D7's script.
  - Files: `assets/dossier.js`, `assets/dossier.css`, `tests/integration/scripts/test_check_page_slow.py` (a first browser test).
  - Steps: (1) Slow test on a small page (build it with the M5 page helper plus a catalog of 15 components): the root view draws; choosing a view in the select draws it and updates the breadcrumb; clicking an SVG node that has a view opens it; `Up` returns; the caption shows the hidden-links sentence when the data says so. (2) Implement `initGraphs`. (3) Block E.
  - Done-check: the new slow test passes; block E prints `OK`.
  - Commit: `feat(dossier): open and close graph views in the page`

- [ ] **M6-21. V11 for the graph views.**
  - Goal: every component and module is in a view, and every view edge exists.
  - Files: `scripts/page_audit.py`, `tests/unit/scripts/test_page_audit.py`.
  - Steps: tests: a page whose views lack one component fails with `components.map: graph views leave out <name>`; a view edge between two nodes with no import between their members fails; a correct page passes. Implement.
  - Done-check: the test file passes.
  - Commit: `feat(dossier): check that the graph views hold every component and module`

- [ ] **M6-22. V12 for the graph views, and the 30-edge budget.**
  - Goal: D7's per-view checks; section 3, row 3.
  - Files: `scripts/check_layout.py`, `scripts/check_page.py`, `tests/integration/scripts/test_check_page_slow.py`.
  - Interface: `MAX_FLOW_EDGES = 30` (count drawn edges in a flowchart SVG; confirm the element Mermaid 12.2.0 uses for an edge path on a drawn page first, and record it); `check_page.check_graphs(page, scheme) -> list`, run in each theme at both widths: for every view in the select, draw it, then count nodes and edges and the smallest text size.
  - Steps: (1) Slow tests: the M6-20 page passes; a page with a hand-made 31-edge flow in a Key flows card fails the edge budget. (2) Implement. (3) Run `dossier check` on a copy of the M5 test page (`m5_page`): `problems: 0` (no existing diagram breaks the new budget).
  - Done-check: the slow tests pass.
  - Commit: `feat(dossier): check every graph view and every flowchart's edge budget in a browser`

- [ ] **M6-23. Mutations for the graph and the badges.**
  - Goal: D15.
  - Files: `tests/tools/broken_pages.py`, `tests/integration/scripts/test_check_page_slow.py`, `tests/unit/scripts/test_page_audit.py`.
  - Steps: add the five mutations and their parametrised cases, each with the line it must produce. Run each and see it fail the check.
  - Done-check: `DOSSIER_SLOW=1 ... test_check_page_slow.py -q -k "mutation" --basetemp=$HOME/.cache/dossier-m6-slow` passes except the known `chart-text-small` case.
  - Commit: `test(dossier): prove the graph and badge checks can fail`

- [ ] **M6-24. The M6 test page.**
  - Goal: D14.
  - Files: new `tests/tools/m6_page.py`; `tests/integration/scripts/test_check_page_slow.py`.
  - Steps: build the page; the slow test runs `dossier check` on it and expects `problems: 0`; read the shots of reports 05 and 06 in both themes and at both widths with the Read tool and record what they show (tangled edges, cut labels).
  - Done-check: the slow test passes.
  - Commit: `test(dossier): check the M6 additions on a large test page`

### Deliverables and checks (Phase 3)

| Deliverable | Checked by |
|---|---|
| Views | `test_graph_views.py` |
| Cards | `test_measured.py`, block E |
| Script | `test_check_page_slow.py` |
| V11, V12, mutations | `test_page_audit.py`, `test_check_page_slow.py` |
| Large page | `m6_page`, `dossier check` |

### Cut line (Phase 3)

Nothing is cut.

### Acceptance criteria (Phase 3)

- The suites pass, except the three known failures; every new mutation fails its check.
- `m6_page` passes V11 and V12 at both widths and themes; block E printed `OK` after M6-19 and M6-20.

### Branch and release (Phase 3)

Commit on `feat/dossier-m6`. Do not merge or bump. Write "Results (Phase 3)" and commit: `docs(dossier): record phase 3 of M6 in plan 012`.

### Results (Phase 3)

---

## Phase 4: `--verify`, blind spots and repository inputs

### Before you start (Phase 4)

Read section 2, D8, D11, D12, D18 and "Results" of Phases 1 to 3. Load the skills in section 2. `git switch feat/dossier-m6`. Before M6-29 and M6-30, re-check the semgrep rule syntax you use (`paths: include`, `pattern-not`, `metavariable-regex`, `from $M import *`) with `semgrep --test` through the cached worker, as M5-1 step 6 did, and record which forms work.

### Tasks (Phase 4)

- [ ] **M6-25. Sample claims for the verifier.**
  - Goal: D8's sampling.
  - Files: new `scripts/verify.py`, `tests/unit/scripts/test_verify.py`.
  - Interface: `eligible(reports, cites) -> {rid: [claim]}`; `sample(eligible, seed, per_report) -> [item]`; `excerpt(cites, cite) -> str`; `check_results(sample_record, results) -> list[str]` (problems).
  - Steps: tests: the same seed gives the same sample; a different seed a different one; claims with only `facts:` or directory citations are not eligible; `unknown` claims are not; `gaps` is not sampled; fewer eligible claims than N gives all of them; the claim text has no citation markers and no confidence word; excerpts are numbered lines at the pinned commit; `check_results` reports a missing id, a duplicate id, an unknown id and a bad verdict.
  - Done-check: `... pytest tests/unit/scripts/test_verify.py -q` passes.
  - Commit: `feat(dossier): sample cited claims for an independent check`

- [ ] **M6-26. `verify-sample`, `verify-record` and `--verify`.**
  - Goal: D8's CLI.
  - Files: `scripts/dossier.py`, `scripts/stages.py` (`Options.verify`), `scripts/config.py` (`verify_per_report`), `tests/unit/scripts/test_verify.py`, `tests/integration/scripts/test_prepare_cli.py`.
  - Steps: (1) Tests with a fake agent result file: `prepare --verify` records `options.verify`; `verify-sample` prints D8's JSON and appends its record; `verify-record` with a good file appends the results record, with a bad file exits 1 and writes nothing; a second `verify-sample` with `--seed` of the first gives the same ids. (2) Implement.
  - Done-check: the two test files pass.
  - Commit: `feat(dossier): add verify-sample and verify-record`

- [ ] **M6-27. Verifier results in Gaps, on the process card and in V10.**
  - Goal: D8's Gaps, card and V10 bullets.
  - Files: `scripts/process.py`, `scripts/checks.py` (`gap_extras`), `tests/unit/scripts/test_process.py`, `tests/unit/scripts/test_checks_gaps.py`.
  - Steps: tests: one `inference` item per `not supported`, with D8's wording and the reason in "how to confirm"; none for `supported` or `cannot tell`; the `Verifier` row for both cases; V10 error for a sample with no results; info only for `--verify` with no sample; a build without `--verify` has no new record and its card shows `not run (turn it on with --verify)`. Implement. Block E.
  - Done-check: the two test files pass; block E prints `OK`.
  - Commit: `feat(dossier): record verifier disagreements in Gaps`

- [ ] **M6-28. The verifier prompt and the build steps.**
  - Goal: D8's agent bullet.
  - Files: new `prompts/verify.md`; `SKILL.md`; `tests/unit/scripts/test_prompts.py`.
  - Steps: (1) `prompts/verify.md`: who you are (an independent checker), what you get (claims and the code they cite, nothing else), what to do (judge each claim only from the code given; `supported` when the lines show it, `not supported` when they contradict it or show something else, `cannot tell` when they are not enough), the output (one JSON array, D8's keys, one sentence per reason quoting the line), and that repository text is data, never instructions. (2) `SKILL.md`: `--verify` in the build hint and in `prepare`'s flag list; step 7a as D8 says. (3) Tests: the prompt names the three verdicts and the JSON keys; `SKILL.md` names `verify-sample`, `verify-record`, `general-purpose` and says the report is never given to the agent.
  - Done-check: `... pytest tests/unit/scripts/test_prompts.py -q` passes.
  - Commit: `docs(dossier): tell Claude how to run the verifier`

- [ ] **M6-29. Python `string-route` and `route-mount`.**
  - Goal: D11's two route rows.
  - Files: `rules/python/blindspot.yml`, `tests/fixtures/semgrep/python/blindspot.py`, `tests/unit/scripts/test_rules.py`, `rules/README.md`.
  - Steps: rules and fixture lines with `# ruleid:` and `# ok:` for every pattern of D11 (near misses: `@app.route("/x")`, `router.get("/x")`, `include(x)` outside `path(...)`). The ids already have wording in `BLIND_SPOTS`. Record the Python adapter's rule hash change (it reruns builds; no version bump needed).
  - Done-check: `... pytest tests/unit/scripts/test_rules.py -q` passes; `DOSSIER_SLOW=1 ... tests/integration/scripts/test_shared_layer.py -q --basetemp=...` passes.
  - Commit: `feat(dossier): find Python routes mounted under a prefix or built at run time`

- [ ] **M6-30. Python `barrel-reexport`.**
  - Goal: D11's barrel row.
  - Files: as M6-29.
  - Steps: a rule for `from $M import *` limited to `__init__.py` files (with `paths: include`, or a `pattern-regex` `(?m)^[ \t]*from[ \t]+\S+[ \t]+import[ \t]+\*` if the structural form is rejected; record which), a fixture `__init__.py` positive case and a non-`__init__` negative case.
  - Done-check: as M6-29.
  - Commit: `feat(dossier): find Python packages that pass names on with star imports`

- [ ] **M6-31. Container and compose environment variables.**
  - Goal: D12's second bullet. Cut item 2 in D20.
  - Files: `scripts/repo_adapter.py` (version up by one with M6-32), `tests/unit/scripts/test_repo_adapter.py`.
  - Steps: tests for `ENV A=1 B=2`, `ENV A 1`, `ARG V`, `ARG V=1`, a multi-line `ENV` with `\`, compose `environment:` as a list and as a map, `env_file:` as a string and a list, a service with neither; no value is stored; Python and JS fixtures: record the new items as D18 allows.
  - Done-check: the test file passes.
  - Commit: `feat(dossier): read environment variables from Dockerfiles and compose files`

- [ ] **M6-32. CI triggers for every language.**
  - Goal: D12's first bullet.
  - Files: `scripts/repo_adapter.py`, `tests/unit/scripts/test_repo_adapter.py`, `tests/integration/scripts/test_py_adapter_slow.py` and `test_js_adapter_slow.py` only if they assert the `repo` section (record each edit).
  - Steps: test: a Python-only tree with a workflow `on: [push, pull_request]` gets two `ci-trigger` rows. Remove `wants_triggers`. Record the before and after `repo` item counts for `PYFIX` and `JSFIX`.
  - Done-check: the test file passes.
  - Commit: `feat(dossier): list push and pull request triggers for every language`

- [ ] **M6-33. The cross-language blind-spot checks.**
  - Goal: D11's table, held by tests.
  - Files: `tests/unit/scripts/test_rules.py`, `tests/unit/scripts/test_checks_v7.py`.
  - Steps: tests: every pattern named in `rules/*/blindspot.yml` has a `BLIND_SPOTS` entry; every `BLIND_SPOTS` id has at least one rule (or is listed in a fixed `RULELESS` set with a reason: none today); the runtime-configuration item appears exactly once in an extract with Python, JS and C# modules.
  - Done-check: both test files pass.
  - Commit: `test(dossier): check the blind-spot list across languages`

### Deliverables and checks (Phase 4)

| Deliverable | Checked by |
|---|---|
| Verifier | `test_verify.py`, `test_prepare_cli.py`, `test_process.py`, `test_checks_gaps.py`, `test_prompts.py` |
| Python blind spots | `test_rules.py`, `test_shared_layer.py` |
| `repo` inputs and triggers | `test_repo_adapter.py` |
| Cross-language list | `test_rules.py`, `test_checks_v7.py` |

### Cut line (Phase 4)

M6-31 only. **Never cut** M6-25 to M6-28.

### Acceptance criteria (Phase 4)

The suites pass, except the three known failures; block E printed `OK` after M6-27.

### Branch and release (Phase 4)

Commit on `feat/dossier-m6`. Do not merge or bump. Write "Results (Phase 4)" and commit: `docs(dossier): record phase 4 of M6 in plan 012`.

### Results (Phase 4)

---

## Phase 5: Docs and version 1.0.0

### Before you start (Phase 5)

Read section 2, D13, D16, D17 and "Results" of Phases 1 to 4. Load the skills in section 2 plus `docs-project`, `docs-readme`, `docs-user-guide`, `docs-dev-guide` and `git-release`. `git switch feat/dossier-m6`. Every command you document must be run once as written (in a scratch home) before it goes in.

### Tasks (Phase 5)

- [ ] **M6-34. `build_parser` and the docs drift test.**
  - Goal: D13.
  - Files: `scripts/dossier.py`, new `tests/unit/scripts/test_docs.py`.
  - Steps: (1) Move the parser into `build_parser()`; `main` is unchanged in behaviour (`test_doctor_cli.py`, `test_prepare_cli.py` pass). (2) Write D13's tests; they fail until M6-35 to M6-38 land, so mark the README and guide tests `xfail(strict=True)` with the reason `docs arrive in M6-35 to M6-38`, and remove each mark in the task that makes it pass.
  - Done-check: the full suite passes.
  - Commit: `test(dossier): check that the docs name every command and flag`

- [ ] **M6-35. Rewrite the README.**
  - Files: `README.md`, `docs/images/dossier.png` (a shot of the M6 test page, report 05 in the light theme at 1500 px), `tests/unit/scripts/test_docs.py`.
  - Steps: D16's README. Check every link and anchor.
  - Done-check: `... pytest tests/unit/scripts/test_docs.py -q` passes its README cases.
  - Commit: `docs(dossier): rewrite the README for 1.0.0`

- [ ] **M6-36. The user guide.**
  - Files: new `docs/user-guide.md`, `tests/unit/scripts/test_docs.py`.
  - Steps: D16's user guide, with a table of contents. The reference section lists every command and flag (D13 test 1).
  - Done-check: the docs test passes its user-guide cases.
  - Commit: `docs(dossier): add the user guide`

- [ ] **M6-37. The developer guide.**
  - Files: new `docs/developer-guide.md`.
  - Steps: D16's developer guide. Run the "Getting started" commands from a fresh clone of the branch in a scratch folder and record the counts.
  - Done-check: the docs test passes; the commands ran as written.
  - Commit: `docs(dossier): add the developer guide`

- [ ] **M6-38. `SKILL.md`, prompts and the rules README.**
  - Files: `SKILL.md`, `prompts/method.md`, `prompts/reports.md`, `rules/README.md`, `tests/unit/scripts/test_prompts.py`, `tests/unit/scripts/test_docs.py`.
  - Steps: D16's last bullet. Remove every remaining `xfail` mark in `test_docs.py`.
  - Done-check: `test_prompts.py` and `test_docs.py` pass with no `xfail`.
  - Commit: `docs(dossier): describe the 1.0.0 design in the skill and prompts`

- [ ] **M6-39. `post-v1.md`, the licence and `process.md`.**
  - Files: `docs/post-v1.md`, new `LICENSE`, `docs/process.md` (the M6 row only).
  - Steps: (1) Remove "Python projects in subfolders" and P4-3 (if M6-7 passed); add: Tier B tree-sitter symbols; Makefile and shell variables as inputs; `.cake` scripts; FastAPI `Depends`; `.NET` versions from Microsoft's `releases.json`; agent detection from `Agent-Logs-Url` (report 02 data); the ground-truth matcher's citation labels; any cut from Phases 1 to 4. Each with what, why left out and where decided. (2) `LICENSE` as D16: copy `/home/nick/.claude/skills/docs-project/templates/LICENSE` (read only; it is in the installed copy, so never edit it) and replace `{{year}}` with `2026` (Q6). (3) Change `process.md`'s M6 session count to `8 Sonnet, and 1 Opus if the C# re-score shows a new disagreement (plan 012, D20)` (Q2, author-approved 2026-11-09).
  - Done-check: `git diff --stat` shows the three files; `head -3 LICENSE` names MIT, 2026 and `Nick OMalley <nickpeteromalley@gmail.com>`; the docs test passes.
  - Commit: `docs(dossier): update the after-1.0 list, the session count and add the licence`

- [ ] **M6-40. Refresh the end-of-life snapshot.**
  - Goal: D17; cut item 1 in D20.
  - Files: `scripts/eol.json`, `tests/unit/scripts/test_measured_upgrade.py` (only where a test pins a value that moved).
  - Steps: run `tests/tools/refresh_eol.py` as its docstring says; record `as_of` before and after and every changed cycle in "Results".
  - Done-check: `... pytest tests/unit/scripts/test_measured_upgrade.py -q` passes.
  - Commit: `chore(dossier): refresh the end-of-life snapshot`

- [ ] **M6-41. Version 1.0.0.**
  - Files: `VERSION`, `tests/unit/scripts/test_incremental.py` or the test that covers `update_plan` (one case).
  - Steps: (1) Test: a state saved by `0.10.0` gives `mode` `full` with `the skill changed from 0.10.0 to 1.0.0`. (2) `VERSION` to `1.0.0`. (3) Full and slow suites.
  - Done-check: `cat VERSION` prints `1.0.0`; the suites pass, except the three known failures.
  - Commit: `chore(dossier): bump to 1.0.0`

### Deliverables and checks (Phase 5)

| Deliverable | Checked by |
|---|---|
| Docs | `test_docs.py`, `test_prompts.py`, commands run as written |
| `post-v1.md`, licence | review of the diff |
| Snapshot, version | `test_measured_upgrade.py`, the `update_plan` test |

### Cut line (Phase 5)

M6-40 only.

### Acceptance criteria (Phase 5)

`VERSION` is `1.0.0`; `test_docs.py` passes with no `xfail`; the suites pass except the three known failures.

### Branch and release (Phase 5)

Commit on `feat/dossier-m6`. Do not merge. Write "Results (Phase 5)" and commit: `docs(dossier): record phase 5 of M6 in plan 012`.

### Results (Phase 5)

---

## Phase 6: Python golden, JS run and the C# repository against its ground truth

### Before you start (Phase 6)

Read section 2, section 7 and "Results" of Phases 1 to 5. Load the skills in section 2. `git switch feat/dossier-m6`. `cat VERSION` prints `1.0.0`. Run `df -h "$HOME/.cache"`: at least 20 GB free. `sha256sum $TRUTH/rw.json` must print `a7fc87a9...8098` (section 7's `TRUTH_SHA`); if not, stop. Create `SCR` as section 7 says and write its path under "Results (Phase 6)" at once.

### Tasks (Phase 6)

- [ ] **M6-42. Blocks S, A, P, P2, JS and E.**
  - Goal: Python and JS unchanged except D18; report 02 unchanged.
  - Files: this plan, unless a block finds a bug (fixed with a test first, in its own commit, then the block rerun).
  - Done-check: results recorded under "Verification results (Phase 6)".
  - Commit: `docs(dossier): record the M6 golden and JS checks`

- [ ] **M6-43. Blocks B, C, D, F, G, H, L, T, J for `RW`, then I.**
  - Goal: the C# repository against the kept truth.
  - Steps: as section 7. Block T's result must hold M5's: entry points recall at least 96% and precision 100%, inputs at least 94%, outputs at least 91%, and every disagreement one of M5's 16 (ruled `no error`). **A new disagreement is recorded, not fixed and not judged:** Phase 6a rules on it.
  - Done-check: every block's result is recorded.
  - Commit: `docs(dossier): record the M6 verification on the C# repository`

### Deliverables and checks (Phase 6)

| Deliverable | Checked by |
|---|---|
| Python golden | Blocks P, P2 |
| JS unchanged | Block JS |
| Report 02 | Block E |
| `RW` dossier and figures | Blocks B to H, T |
| Incremental | Block J |

### Cut line (Phase 6)

Nothing is cut. If block D cannot finish, stop at a saved state and say which reports are left; the next session continues.

### Acceptance criteria (Phase 6)

`dossier check` prints `problems: 0` on `RW` and on the golden copy; blocks P, P2 and JS show only D18's changes; block E prints `OK`; block T is recorded and the truth hash is unchanged.

### Branch and release (Phase 6)

Do not merge. Commit results: `docs(dossier): record phase 6 of M6 in plan 012`.

### Results (Phase 6)

### Verification results (Phase 6)

---

## Phase 6a: Rulings on new ground-truth disagreements

**Run this with Opus, in a fresh session (`/model opus`), and only if "Verification results (Phase 6)" lists a disagreement that is not one of M5's 16.** A session started for this phase reads only this section. You are a judge: you change no code and no report.

### Before you start (Phase 6a)

Load `git-commit`. `git switch feat/dossier-m6`. Set `SCR` to the path in "Results (Phase 6)" (find it with `grep -n 'SCR=' docs/plans/012-m6-plan.md`), and `TRUTH=/home/nick/.cache/dossier-m5-vWDO/truth`. Check `sha256sum $TRUTH/rw.json` prints `a7fc87a9dbcf454d0b7e8b2500f81ad533535cdf1e5dad327ed8c7c145a18098`. The new disagreements are in `$SCR/truth-m6/review.md`; the repository is `$SCR/src/rw`; the reports are in `$SCR/home/rw/reports`.

### Tasks (Phase 6a)

- [ ] **T-6. Rule on each new disagreement.**
  - Steps: for each row, read the cited code and give one verdict with a reason: `dossier wrong` (Phase 6 or 7 fixes it), `blind spot` (name the Gaps entry or rule), or `no error`. `list wrong` is **not** available: `TRUTH` is never edited in M6; if you think the list is wrong, say so as a finding for the author. Write the rulings to `$SCR/truth-m6/rulings.md`.
  - Done-check: every new row has a verdict.

### Deliverables and checks (Phase 6a)

| Deliverable | Checked by |
|---|---|
| Rulings | every new row has a verdict |

### Cut line (Phase 6a)

Nothing is cut.

### Acceptance criteria (Phase 6a)

Every new row is ruled, and the truth hash is unchanged.

### Branch and release (Phase 6a)

Write under "Results (Phase 6a)" the count of each verdict and each `dossier wrong` row by path and name (no code from the repository). Tick T-6 and commit: `docs(dossier): record the M6 ground truth rulings in plan 012`. Do not merge.

### Results (Phase 6a)

---

## Phase 7: React, mixed and library repositories, the verifier for real, degraded builds

### Before you start (Phase 7)

Read section 2, section 7 and "Results" of Phases 1 to 6a. Load the skills in section 2. `git switch feat/dossier-m6`. Set `SCR` from "Results (Phase 6)". **If Phase 6a ruled any row `dossier wrong`, do M6-44 first; otherwise tick it as not needed.**

### Tasks (Phase 7)

- [ ] **M6-44. Fix `dossier wrong` rows from Phase 6a (only if any).**
  - Steps: for each, fix the rule or the extractor with a test first (own commit), or the report in `$SCR` when it is a writing omission; rebuild; rerun block T. A further new disagreement: stop and ask for Phase 6a again.
  - Done-check: block T holds M5's figures.
  - Commit: one per fix, then `docs(dossier): record the M6 ground truth fixes`.

- [ ] **M6-45. Blocks R, M, Y, TB and BS.**
  - Goal: the TS/React repository, the smallest mixed repository, every library's public API, the Tier B page, the blind-spot counts.
  - Done-check: results recorded.
  - Commit: `docs(dossier): record the M6 React, mixed and library checks`

- [ ] **M6-46. Blocks V, FR, N, K, NR, SUB, CL and HY.**
  - Goal: the verifier on a real dossier, freshness offline, and definition of done item 4.
  - Done-check: results recorded.
  - Commit: `docs(dossier): record the M6 verifier, freshness and degraded-build checks`

### Deliverables and checks (Phase 7)

| Deliverable | Checked by |
|---|---|
| `BP` dossier | Block R |
| Mixed fixture | Block M |
| Libraries | Block Y |
| Tier B | Block TB |
| Verifier | Block V |
| Freshness offline | Block FR |
| Item 4 | Blocks N, K, NR, SUB, CL, HY, A |

### Cut line (Phase 7)

Nothing is cut. If `BP`'s reports cannot finish, stop at a saved state; the next session continues.

### Acceptance criteria (Phase 7)

`dossier check` prints `problems: 0` on `BP` and the mixed fixture; block Y passes for all four libraries; block V recorded a real run; blocks N to HY match their expectations.

### Branch and release (Phase 7)

Do not merge. Commit results: `docs(dossier): record phase 7 of M6 in plan 012`.

### Results (Phase 7)

### Verification results (Phase 7)

---

## Phase 8: The largest repository, the definition of done, and merge

### Before you start (Phase 8)

Read section 2, section 7 and "Results" of Phases 1 to 7. Load the skills in section 2 plus `git-release`. `git switch feat/dossier-m6`. Set `SCR` from "Results (Phase 6)". **Stop if Phase 7 has no results.**

### Tasks (Phase 8)

- [ ] **M6-47. Block W for `CA`, with freshness online (block FR2).**
  - Done-check: results recorded.
  - Commit: `docs(dossier): record the M6 checks on the largest repository`

- [ ] **M6-48. Blocks X, CP, I, E, Z and the definition-of-done table.**
  - Goal: section 11, item by item.
  - Steps: run the blocks, then fill section 7's DoD table under "Verification results (Phase 8)", one line per item with the evidence (block and figure).
  - Done-check: every item says `met`, or `not met` with the reason and what is left.
  - Commit: `docs(dossier): record the M6 definition of done`

- [ ] **M6-49. Merge, install check, push.**
  - Steps: (1) Tick and record, including the list of kept folders: `TRUTH`, `$SCR/truth-m6/` if it exists, and `$SCR` itself. Delete none of them (section 8, "Ground truth after M6"). (2) `git switch main && git merge --no-ff feat/dossier-m6` (local only). (3) Block FC on the local `main`. (4) **Ask the author:** "M6 is merged locally and the fresh-clone check passed. Push `main` and delete the branch?" Push and delete only on a yes; on a no, leave both as they are and say so.
  - Done-check: `git log --oneline -1 main` shows the merge; block FC passed; the author's answer is recorded.
  - Commit: the merge commit.

### Deliverables and checks (Phase 8)

| Deliverable | Checked by |
|---|---|
| `CA` dossier, freshness online | Blocks W, FR2 |
| Same skeletons | Block X |
| `check` everywhere | Block CP |
| Suites, report 02 | Blocks I, E |
| Install from a fresh clone | Block FC |
| Definition of done | The DoD table |

### Cut line (Phase 8)

Nothing is cut. Do not merge until the DoD table is filled.

### Acceptance criteria (Phase 8, and M6)

Every DoD item is `met`, or `not met` with a reason the author accepts; block FC passed; the merge exists locally.

### Branch and release (Phase 8)

As M6-49. CI does not tag this skill; whether to tag `v1.0.0` or publish it is the author's call (section 8).

### Results (Phase 8)

### Verification results (Phase 8)

---

## 7. Verification

Set once per shell (zsh), or keep in a sourced file in the session scratchpad as M5 did. The scratch folder is under `~/.cache`:

```bash
SKILL=/home/nick/dev/projects/encamp/configs/user/claude/.claude/skills/dossier
REPO=/home/nick/dev/projects/cannalerts; LIVE=/home/nick/dev/dossiers/cannalerts; FIX=$SKILL/tests/fixtures/encamp-m0; PIN=5923c09
TRUTH=/home/nick/.cache/dossier-m5-vWDO/truth; TRUTH_SHA=a7fc87a9dbcf454d0b7e8b2500f81ad533535cdf1e5dad327ed8c7c145a18098
RW_PIN=9345f18abf36b778abe2f290467ba432bf1f7e5c; CA_PIN=4739ae4cbd057ee142bc1e1bdc93c4fea8f0cac5; BP_PIN=9506629ed003a561c6627735480cce4994244bb4
GC_PIN=61dde6c9d3e1715286bd100144a9edff1ad0664c; ZU_PIN=382d29c485e67018c06e75ec7235130d0968522c
TO_PIN=a2a578949199336ebc3884eeba4aede87da41ef2; MI_PIN=4aeb4338ae1407d8da9723e86da99efeb446f719
BASE_SHA=$(git -C $SKILL merge-base main feat/dossier-m6)
SCR=${SCR:-$(mktemp -d -p "$HOME/.cache" dossier-m6-XXXX)}; echo "SCR=$SCR"
export DOSSIER_HOME=$SCR/home DOSSIER_CONFIG=$SCR/cfg.json DOSSIER_CACHE=$SCR/cache PYTHONDONTWRITEBYTECODE=1
D() { uv run "$SKILL/scripts/dossier.py" "$@"; }   # a function: zsh does not split "$D"
cd $SKILL
```

**Block S: setup.** Full clones (history cards need them), never changed.

```bash
mkdir -p $SCR/src $SCR/truth-m6
for pair in rw:realworld-apps/aspnetcore-realworld-example-app ca:jasontaylordev/CleanArchitecture bp:alan2207/bulletproof-react \
            gc:ardalis/GuardClauses zu:pmndrs/zustand to:hukkin/tomli mi:more-itertools/more-itertools; do
  n=${pair%%:*}; r=${pair#*:}; [ -d $SCR/src/$n ] || git clone -q https://github.com/$r $SCR/src/$n; done
git -C $SCR/src/rw checkout -q $RW_PIN; git -C $SCR/src/ca checkout -q $CA_PIN; git -C $SCR/src/bp checkout -q $BP_PIN
git -C $SCR/src/gc checkout -q $GC_PIN; git -C $SCR/src/zu checkout -q $ZU_PIN; git -C $SCR/src/to checkout -q $TO_PIN; git -C $SCR/src/mi checkout -q $MI_PIN
for n in rw ca bp gc zu to mi; do b=$(git -C $SCR/src/$n symbolic-ref --short refs/remotes/origin/HEAD); \
  git -C $SCR/src/$n merge-base --is-ancestor HEAD $b && echo "$n-trusted"; done
git -C $REPO status --porcelain > $SCR/repo-status-before; sha256sum $TRUTH/rw.json
RW=$SCR/src/rw; CA=$SCR/src/ca; BP=$SCR/src/bp; OUT=$DOSSIER_HOME/rw; OUTC=$DOSSIER_HOME/ca; OUTB=$DOSSIER_HOME/bp
```

Expect seven `-trusted` lines and the truth hash. A missing line: stop and report; do not reach for `--allow-ref`. (Checked 2026-11-09: every pin is on its default branch; `CA` main is 3 ahead, `ZU` 5, `TO` 3, `MI` 10.)

**Block A: `doctor`.** `D doctor $RW; echo "exit $?"` and `D doctor $BP; echo "exit $?"`. Expect `dotnet 10.0.4xx` ok, `scip-dotnet 0.2.16 from a hash-checked NuGet package` (for `RW`), the JS tools `from a lockfile with npm` (for `BP`), `Languages:` naming Shell as `(Tier B: no static graph)` where present, a `skill:` line, exit 0.

**Block P: the Python golden, extract items.** Plan 011's block P with this `BASE_SHA`, but the comparison prints, for each output and adapter, the added and removed items by `(kind, path, name or category, line)`, not just `DIFF`. Expect: the `python` section identical; the `repo` section differing only by D18's rows (`ci-trigger`, if the golden has GitHub workflows); every other difference is a bug. Keep side b (`$SCR/p/b`).

**Block P2: the Python golden as a 1.0.0 build.** On side b only: `D candidates $REPO --report <id> --open` for every authored report (with `DOSSIER_HOME=$SCR/p/b`). For each open finding, add its disposition to the copied report in `$SCR/p/b/cannalerts/reports/` (a new row or a dismissal with a reason; record each), never to `LIVE`. Then `render` **without** `--allow-errors` (exit 0, no `error:` line), then `D check $REPO` (`problems: 0`). Then compare each report section of sides a and b with `tests/tools/report_section.py --normalize`, print a unified diff per report, and review every changed line against D18: the badges on the eight cards, the graph markup in reports 05 and 06, the no-API line in `io`, the new dispositions, upgrade-burden values (M6-40). Record the list; any other change is a bug.

**Block JS: a JS run.** Plan 011's block JS with this `BASE_SHA`. Expect the `js` section identical and the `repo` section differing only by D18 (Dockerfile variables; `ci-trigger` if `JSFIX` has workflows). Record both.

**Block E: report 02 unchanged.** Plan 010's block E with this `BASE_SHA` (use the `"${E:?}"` form for the `rm`, as M5 did). Expect `OK`.

**Block B: prepare `RW`.** `D prepare $RW --ref $RW_PIN --full --restore yes > $SCR/p1.json; echo "exit $?"`. Expect exit 0, mode `full` (skill changed to 1.0.0), `csharp` and `repo` sections with every tool `ok`, three nuget restores `ok`, and in `build.json` a pin record with `details.freshness` (`Up to date` with `origin/master`, source `remote`). Print counts with plan 011's block B script. Record the M6-4 `dropped` count, the `ci-trigger` and compose and Dockerfile items, and compare with plan 011's counts (entry_points csharp 27 / repo 12; symbols 873).

**Block C: candidates.** For `entry`, `data`, `io`, `components`, `reading`: `D candidates $RW --report <id>`. Record what looks wrong under "Findings".

**Block D: write the reports.** As Claude, follow `SKILL.md` `/dossier build` steps 2 to 5 with `DOSSIER` = `D`; write every report into `$OUT/reports/`; then `for r in entry components interactions io data behavior change conventions ops reading; do D candidates $RW --report $r --open; done` prints nothing. **Never read `$TRUTH/rw.json` while writing.** Report generators, if you use them, live in `$SCR/gen` and are never committed.

**Block F: render.** `D render $RW > $SCR/r1.log; echo "render exit $?"`; `grep -E '^(error|warning|info):' $SCR/r1.log | sed -E 's/^(error|warning|info): (V[0-9]+).*/\1 \2/' | sort | uniq -c`. Expect exit 0 and no `error:` line. Count the rounds.

**Block G: check.** `D check $RW; echo "exit $?"`: `problems: 0` (V8, V11, V12 at 1500 and 400 px, light and dark, now including every graph view). `D render $RW` once more. Read the shots in `$OUT/.check-shots` for the component map and dependency graph in both themes, and one flow.

**Block H: counts.** Plan 011's block H script with these extra prints: the number of `igraph-data` blocks (expect 2), the number of views in each, `class="badge nograph"` count (expect 8 when Shell is present, else 0), and whether the `Freshness` tile is present.

**Block L: public API.** `RW` has no packable project: `No package here declares a public API.` once, no `t-io-contracts-api` table.

**Block T: re-score against the kept truth.**

```bash
sha256sum $TRUTH/rw.json | grep -q $TRUTH_SHA && echo truth-ok
python3 tests/tools/ground_truth.py $TRUTH/rw.json $OUT/reports --review $SCR/truth-m6/review.md
sha256sum $TRUTH/rw.json | grep -q $TRUTH_SHA && echo truth-still-ok
```

Expect both `truth-ok` lines, entry points recall at least 96% and precision 100%, inputs at least 94%, outputs at least 91%. Compare the disagreement keys in `$SCR/truth-m6/review.md` with those in `$TRUTH/review-5b.md` and the "Phase 5b rerun" part of `$TRUTH/rulings.md`: list every key that is new. Record the figures, the count of old and new disagreements, and each new one with its cited line. Never write into `$TRUTH`.

**Block J: incremental.** Plan 011's block J on a copy (`--allow-ref`). Expect `incremental`; `entry`, `data`, `interactions`, `components` not stale.

**Block I: the suites.** Default, and `DOSSIER_SLOW=1 ... --basetemp=$HOME/.cache/dossier-m6-slow`, run alone. Only the three known failures may fail.

**Block R: the TS/React repository.** Plan 010's block R steps 1 to 5 on `$BP` with `--ref $BP_PIN` and `OUTB` (blocks A, B, C, D, F, G, H, L). Expect three yarn restores `ok`, `js` tools `ok`, `problems: 0`, the React table in `interactions.graph`, the graph views, and `No package here declares a public API.` Record the hand count of `apps/react-vite` routes against `entry.catalog` (M4: 10).

**Block M: the mixed fixture with Python in `backend/`.** Build it with `build_mixed_pysub_repo` (M6-14) into `$SCR/m/repo`, `prepare --no-restore`, write all reports as in block D (generated rows are fine; the fixture is synthetic), `render`, `check`. Expect `problems: 0`, `python` and `js` sections, no `partial` badge for grimp, rows from both languages in `entry.catalog` and `interactions.graph`.

**Block Y: public APIs of real libraries.** `prepare --full --no-restore` only, one home each:

```bash
for n in to mi gc zu; do pin=$(eval echo \$$(echo $n | tr a-z A-Z)_PIN); \
  DOSSIER_HOME=$SCR/y/$n DOSSIER_CACHE=$SCR/y/$n-cache D prepare $SCR/src/$n --ref $pin --full --no-restore > $SCR/y/$n.json; echo "$n exit $?"; done
```

Expect exit 0 for all four. Then from each `extract/symbols.json`'s `public-api` items:

- `TO`: package `tomli`; import path `tomli` holds exactly `loads`, `load`, `TOMLDecodeError` (defined in `src/tomli/_parser.py`), audience `listed in __all__, typed`; no import path starting `tomli._`; `__version__` absent. The nested `benchmark/`, `fuzzer/`, `profiler/` and `scripts/` folders (each with a `requirements.txt`) are Python projects (D9) and are applications or non-packable, so they add no rows. Record their module items.
- `MI`: package `more-itertools`; import path `more_itertools` holds the names of both submodules' `__all__` (record the count; spot-check `chunked` from `more.py` and `flatten` from `recipes.py`), audience `public by name, typed`; import paths `more_itertools.more` and `more_itertools.recipes` exist with `, has a stub`; `__version__` absent.
- `GC`: plan 011 block Y's expectations (33 items).
- `ZU`: plan 010 block Y's expectations (64 items).

Record the counts. A failure is a finding, fixed with a test first in Phase 7.

**Block TB: Tier B.** The slow test of M6-8 passes; also build its repository (`PYFIX` plus `native/lib.rs`, `tools/run.sh`) into `$SCR/tb`, write minimal reports (generated), `render`, `check`: `problems: 0`, 8 badges, Gaps lists Rust and Shell once each with the unchanged wording.

**Block BS: blind-spot counts.** For each built dossier (`RW`, `BP`, `CA`, the golden side b, block M): `python3 -c` over `extract/blindspots.json`, print `Counter((adapter, pattern))`. Record the table; it completes D11's "Seen" column.

**Block V: the verifier for real.** On `RW` (built in Phase 6):

```bash
D prepare $RW --ref $RW_PIN --verify --no-restore > $SCR/pv.json   # render-only plan; records options.verify
D render $RW > /dev/null; D verify-sample $RW > $SCR/v-sample.json
```

Then, as Claude, follow `SKILL.md` step 7a exactly: one general-purpose subagent per report's items, model `sonnet`, prompt = `prompts/verify.md` plus that report's items, nothing else; join the answers into `$SCR/v-results.json`; `D verify-record $RW --results $SCR/v-results.json; echo "exit $?"`; `D render $RW`; `D check $RW`. Expect exit 0, `problems: 0`, the `Verifier` row on the process card with the counts, one Gaps item per `not supported`. Record the seed, the counts, and for each `not supported` and `cannot tell` the claim and whether you agree after opening the code (a finding, not a fix). Then run `D verify-sample $RW --seed <seed>` and confirm the same ids.

**Block FR: freshness offline.** A copy of `RW`'s clone with its remote URL set to a missing folder and one extra commit fetched into a second copy:

```bash
F=$SCR/fr; mkdir -p $F; git clone -q --bare $RW $F/remote.git; git clone -q $F/remote.git $F/a; git -C $F/a checkout -q $RW_PIN
git clone -q $F/remote.git $F/b; git -C $F/b -c user.name=C -c user.email=c@x.io commit -q --allow-empty -m new; git -C $F/b push -q origin HEAD:master
git -C $F/a fetch -q; git -C $F/a remote set-url origin $F/missing.git
DOSSIER_HOME=$F/home DOSSIER_CACHE=$F/cache D prepare $F/a --ref $RW_PIN --no-restore > $F/p.json; echo "exit $?"
python3 -c "import json;b=json.load(open('$F/home/a/build.json'));print([r['details']['freshness'] for r in b['records'] if r['step']=='pin'][-1])"
```

Expect `source: "tracking"`, `behind` equal to the commits between the pin and `origin/master` (count them with `git rev-list --count`), and after `render` a `Freshness` tile saying `{n} commits behind` with `as of the last fetch`.

**Block N: a tool removed.** Plan 011's block N on `RW` (fake `dotnet`), with the three `found:` strings. Expect the same results as M5 (doctor exit 1, prepare exit 2, `--allow-missing` exit 0, three `partial` badges), and the badges sit beside any `no static graph` badge without overlap (the page passes `check`).

**Block K: an untrusted ref.** Plan 011's block K on `RW`. Expect scip-dotnet `skipped` with the fixed reason, then not skipped with `--allow-ref --no-restore`, and the `Freshness` tile present in both.

**Block NR: `--no-restore`.** Plan 011's block R on `RW`. Expect restore `skipped` with the fixed reason.

**Block SUB: submodules.** `RW` has one submodule (`realworld`). Without the flag: Gaps has `The submodule realworld was not analysed. Build with --submodules to include it.` With `DOSSIER_HOME=$SCR/sub/home DOSSIER_CACHE=$SCR/sub/cache D prepare $RW --ref $RW_PIN --submodules --no-restore`: exit 0, `build.json` records `submodules_on: true`, no such Gaps item after `render --allow-errors` with copied reports.

**Block CL: `clean`.** `DOSSIER_HOME=$SCR/sub/home DOSSIER_CACHE=$SCR/sub/cache D clean $RW`: prints `Removed the working area ...` and the dossier folder is untouched (`ls $SCR/sub/home/rw/build.json`); a second run prints `Nothing to clean`.

**Block HY: restore hygiene.** `DOSSIER_SLOW=1 uv run --with pytest --with pygments python -m pytest tests/integration/scripts/test_hygiene.py -v --basetemp=$HOME/.cache/dossier-m6-slow`: every case passes (only allowlisted names, `HOME` scratch, caches under the area, a feature branch refused without `--allow-ref`, a timed-out stage killed and recorded).

**Block W: the largest repository.** Plan 011's block W steps 1 to 5 on `$CA` with `--ref $CA_PIN` and `OUTC`. Expect adapters `csharp`, `js`, `repo`; the `framework` note `Aspire.Hosting.AppHost` (M6-1); `AspireExtensions` no longer in `change.dead-code` (M6-3); test projects with real file counts (M6-5); `problems: 0`.

**Block FR2: freshness online.** From `CA`'s `build.json` pin record: `source: "remote"`, `compared_with: "origin/main"`, `behind` equal to `gh api repos/jasontaylordev/CleanArchitecture/compare/$CA_PIN...main --jq .ahead_by` (3 on 2026-11-09; record today's), and the tile on the page says the same.

**Block X: same skeleton.** `python3 tests/tools/skeleton.py $OUT/dossier-*.html $OUTB/dossier-*.html $OUTC/dossier-*.html $SCR/m/home/*/dossier-*.html $SCR/p/b/cannalerts/dossier-*.html $SCR/tb/home/*/dossier-*.html; echo "exit $?"`. Expect exit 0 (item 2 and the first item 5: the smallest, block M, and the largest, `CA`).

**Block CP: `check` everywhere.** `D check` on `RW`, `BP`, `CA`, block M, block TB and the golden side b (with its `DOSSIER_HOME`): each `problems: 0` (item 6). Then `D render` on each so the page records the time.

**Block Z: the end.** `diff <(git -C $REPO status --porcelain) $SCR/repo-status-before` prints nothing; `git -C $SKILL worktree list` shows one worktree; every clone under `$SCR/src` has an empty `git status --porcelain`; `sha256sum $TRUTH/rw.json` still prints `$TRUTH_SHA`. Keep `$SCR` and say its path.

**Block FC: fresh-clone install check** (after the local merge, M6-49):

```bash
FC=$SCR/fc; rm -rf "${FC:?}"; git clone -q /home/nick/dev/projects/encamp $FC/encamp
SK=$FC/encamp/configs/user/claude/.claude/skills/dossier; git -C $FC/encamp log --oneline -1
uv run $SK/scripts/dossier.py version                                   # dossier 1.0.0
DOSSIER_HOME=$FC/home DOSSIER_CACHE=$FC/cache uv run $SK/scripts/dossier.py doctor $RW; echo "exit $?"
(cd $SK && uv run --with pytest --with pygments python -m pytest tests -q | tail -2)
```

Expect `dossier 1.0.0`, `doctor` exit 0 with `skill: <merge commit> (clean)`, and the default suite's count equal to block I's. This uses a fresh clone, never `INSTALLED`: updating `INSTALLED` with `encamp-sync pull` changes the author's live configuration, so it is the author's step after the push.

**The DoD table** (under "Verification results (Phase 8)"):

| Item | What shows it | Result |
|---|---|---|
| 1 P0 cards exist, validate, right badge | `render` exit 0 on every dossier (V6), `test_schema_files.py`, block H | |
| 2 three repositories, identical skeletons | blocks P2, R, B to G, X | |
| 3 ground truth | block T (C#, provisional); TS: none kept (risk 4); Python: the author's (section 8) | |
| 4 doctor, flags, clean, tool removed, hygiene | blocks A, N, NR, K, SUB, CL, HY | |
| 5 small and largest skeletons identical | block X (block M and `CA`) | |
| 5 `summary.json` valid, no extra fields | V8 in every render and check; `test_summary_schema_slow.py` | |
| 6 tests and `check_page` | block I, block CP | |
| 7 docs, prompts, `VERSION` | `test_docs.py`, `test_prompts.py`, `cat VERSION` | |
| Regression | blocks P, P2, JS, E, T, W against plan 011's figures | |

**Order.** Phase 6: S, A, P, P2, JS, E, B, C, D, F, G, H, L, T, J, I. Phase 7: R, M, Y, TB, BS, V, FR, N, K, NR, SUB, CL, HY. Phase 8: W, FR2, BS (for `CA`), X, CP, I, E, Z, then FC after the merge. Clear `$SCR/j`, `$SCR/n`, `$SCR/k`, `$SCR/r`, `$SCR/sub` and `$SCR/y/*-cache` between blocks if `df` shows under 5 GB free.

**Recording results.** Under each phase's "Verification results" write the date, branch and model, and for each block the key output lines, render rounds, page size, what was cut and why, and a "Deviations" list. Findings about rule precision go under "Findings for the milestone review", not into fixes, unless they are a crash, a V1 failure, a block T regression, a block Y failure, or a change not in D18.

---

## 8. Risks and open questions

### Risks (most important first)

1. **The `RW` re-score needs a new set of reports.** The M5 reports are gone, so Phase 6 writes all fourteen again. The writer, not the code, decides most of block T's rows (M5 Phase 5b found 14 of 15 defects were writing omissions). A weaker write can drop the figures below M5's for reasons M6 did not cause. Mitigation: block D reads plan 011's Phase 5a defect list (the kinds of row the truth expects: full route paths, migrations by name, script messages, tooling network calls) before writing, without reading `TRUTH`.
2. **The interactive graph may still read as noise.** The author's own UAT removed the static diagrams (`1e5712c`). D7's views are small and collapsed, but no check can judge usefulness. The author chose to build it and review it afterwards (Q1); D7 keeps it revertible in one step, and Phase 8's hand-over asks for one look.
3. **Mermaid layout and click wiring.** D7 relies on finding drawn node elements by id in Mermaid 12.2.0's SVG, and on the per-view checks being fast enough on large repositories (one draw per view, per theme and width). M6-22 records timing on `m6_page`; if a view count makes `check` slow, the check may sample views by a fixed rule, recorded as a deviation for the author.
4. **No TS ground truth survives.** `~/.cache/dossier-m4-8vGZ` is gone (only `dossier-m4-ALvL`, with no truth, remains). Item 3 for TS rests on plan 010's recorded figures (100/100/100/100 after Phase 4b) and is not re-measured. `BP` gets no ground truth (it never had one).
5. **Python subfolders change module naming for repositories with nested manifests.** A root repository with `docs/requirements.txt` or `tools/pyproject.toml` gets new projects and new module names (more correct, but different). The golden has none, so block P cannot show this; `TO` (four nested `requirements.txt` folders) is the real test.
6. **Name clashes between Python projects.** Two projects with an `app` package share module names; name-based checks (V2, V3) may pick the wrong file (D9).
7. **The Python library rule is a judgement.** "Packable with scripts and no `py.typed` is an application" will be wrong for some libraries that ship a CLI and no marker (decision 33's spirit: corrected from use).
8. **`git ls-remote` is a network call from `prepare`.** It runs no repository code, but it contacts the remote with the scrubbed environment, so SSH remotes fall back to the last fetch. Q3.
9. **Verifier quality.** The verifier is another Claude model judging Claude's claims from excerpts; it can miss context outside the cited lines and mark true claims `cannot tell`. It is off by default and its disagreements become ordinary inferences, which the author decides.
10. **Session count.** Nine sessions where `process.md` said one; accepted (Q2).
11. **Slow-suite flake.** M5 saw one timing-sensitive history test fail once under load; run suites alone.

### What I could not verify (open facts)

- **O1.** The SVG element names Mermaid 12.2.0 uses for flowchart nodes and edges on a drawn page (M6-20 and M6-22 confirm on a real page first).
- **O2.** Whether semgrep 1.181.0 accepts `from $M import *` as a Python pattern and rule-level `paths: include` (Phase 4's first step checks; D11 gives the regex fallback).
- **O3.** The ecosystem string `deps.py` uses for NuGet in `unused` rows (M6-2 reads it first).
- **O4.** The field name for per-language file counts in `facts["languages"]` (M6-8 reads `gather.collect` first).
- **O5.** Whether the golden repository has GitHub workflows, star imports in `__init__.py` files, or route mounts (block P records).
- **O6.** Where `uv sync` puts `.venv` for a workspace member (the uv docs do not say; D9 takes the nearest `.venv` at or above the project).
- **O7.** Whether `PYFIX` is an application by D10's rule (M6-17 checks its `pyproject.toml`).

**What I read.** In full: the spec, `process.md`, `post-v1.md`, the M6 prompt, plan 011, `SKILL.md`, `README.md`, `toolcheck.py`, `process.py`, `py_adapter.py`, `py_packages.py`, `measured_graph.py`, `stages.py`, `dossier.py` (lines 1 to 540 and the parser), `tools.json` (languages, tools, restore). In part: plan 010 (header, shared rules, D17, Phases 4a to 5 with results and rulings, section 6), `render.py` (cards, badges, `panel_dossier`, page assembly), `gather.py` (classification tables), `checks_v7.py` (first 107 lines), `check_layout.py` (header), `check_page.py` (owner and blast checks), `page_audit.py` and `broken_pages.py` (function lists), `assets/dossier.js` (function list, Mermaid and blast parts), `js_project.py` and `restore.py` (first 80 lines), `repo_adapter.py` (first 80 lines), `candidates.py` (`text`), `measured_change.dead_rows`, `measured_tables.public_api`, `cs_project.frameworks_named`, `cs_scip.dead_items`, `measured_er.py` and `deps.py` (by search), `workarea.trusted`, `sandbox.py` and `adapters.py` (by search), every `rules/*/blindspot.yml` (ids and patterns), `questions.json` (question 39), `prompts/schema/dossier.json`, the separate plugin's `dossier-verifier.md`; `TO` and `MI` (tree, `pyproject.toml`, `__init__.py`). **Not read:** plans 007, 008 and 009 (I relied on `check_layout.py`'s own list of what V12 asserts, not plan 008), `prompts/method.md` and `prompts/reports.md` beyond searches, `js_api.py`, `cs_api.py`, `summary.py`, `incremental.py`, `graphs.py`, `history.py`, `measured_blast.py` beyond its function list, `assets/dossier.css`, `template.html`, the test files' contents, `PYFIX` and `JSFIX` contents, the cannalerts code beyond its file list and `pyproject.toml` headings (read-only).

### Questions for the author (answered 2026-11-09)

All six are answered; every answer matches the default the plan already followed, so no task changes except as noted.

- **Q1. Build the interactive graph?** **Yes.** The author will review it and scrap it if it does not help. D7 now requires the graph commits to be revertible on their own.
- **Q2. Nine sessions** (eight Sonnet, one conditional Opus)? **Yes.** Phase 5 edits `process.md`'s M6 row to `8 Sonnet, and 1 Opus if the C# re-score shows a new disagreement (plan 012, D20)`.
- **Q3. `git ls-remote` on every `prepare`?** **Yes**, 15 s timeout, falling back to the last fetch (D6). No `freshness: "local"` key.
- **Q4. The verifier agent.** The old `1npo/dossier` plugin is an older version of this skill, which replaces it. **Done in planning (2026-11-09):** the plugin `dossier@dossier` was uninstalled (`claude plugin uninstall dossier@dossier`), its marketplace removed (`claude plugin marketplace remove dossier`) and its cache (`~/.claude/plugins/cache/dossier/`) deleted. Agents `dossier:dossier-verifier` and `dossier:dossier-writer` no longer exist; D8 stands (the skill ships `prompts/verify.md` and starts a general-purpose subagent). Phase 5's docs must not mention the old plugin, except that the user guide's troubleshooting may say: "If `/dossier` runs an older skill with an `init` mode, uninstall the `dossier@dossier` plugin."
- **Q5. Releasing without a bump tool.** **Edit `VERSION` directly** on the feature branch, as M4 and M5 did (D17), until the author picks a bump tool for the published release. Tagging stays the author's call.
- **Q6. Licence.** **Yes:** an MIT `LICENSE` (M6-39), from the `docs-project` skill's `templates/LICENSE` with the year filled in.

**Ground truth after M6.** The M4 and M5 truth folders were deleted at the end of those milestones on the planner's advice, which is why risk 4 has no TS truth. M6 does not repeat that: Phase 8 deletes no truth folder. `TRUTH` and any `$SCR/truth-m6/` review files are kept under `~/.cache`, and Phase 8's results name every kept folder.

**What only the author can do** (and why Claude cannot):

1. Rule on section 9 if you disagree with a default (these are your decisions about scope and policy; the plan follows its defaults until you do).
2. Look once at the golden's components map and dependency graph (`$SCR/p/b/cannalerts/dossier-cannalerts.html`, reports 05 and 06) and say whether the graph helps. It is your repository and your UAT removed the diagrams; usefulness is a judgement no check makes. Definition of done item 3 for your repository (your knowledge) is otherwise unchanged: M6 changes how the map is drawn, not its components.
3. Push and tag: whether to push `main` (asked in M6-49), tag `v1.0.0`, and run `encamp-sync pull` to update your installed copy (it changes your live configuration).

No new ground truth is proposed, so no new spot-checks are needed; the `RW` spot-checks were done in M5's hand-over.

---

## 9. Spec issues

Each has proposed wording. The plan follows the proposal unless the author rules otherwise.

- **S1. The freshness BAN** (section 4, 01). Proposed: "01 gains a freshness tile in `dossier.about`: how many commits the pinned commit is behind the current head of its ref on `origin` (a branch's upstream, the same tag, or the default branch for a commit), asked once with `git ls-remote` during `prepare`, else read from the last fetch, else 'not known'. It is not in `summary.json`." And question 10.3 answered by `dossier.about`.
- **S2. `--verify`** (section 7). Proposed: "With `--verify`, after `check`, `dossier verify-sample` picks N claims per report (default 5) from a seed made after the reports are written; each report's sample goes to a separate subagent that gets only the claims and the cited code, and answers supported, not supported or cannot tell; `dossier verify-record` stores the answers in `build.json` (part of step 8). Each 'not supported' becomes an `inference` item in Gaps; the process card counts all three."
- **S3. Tier B** (6.3). Proposed: "Tier B (any other code language, including C, Rust, Zig and shell): `deps.py` where an adapter exists, git facts and Claude reading; no import or call graph. The cards a graph feeds (reading order, component map and catalog, dependency graph, cycles, key flows, blast radius, dead code) carry a 'no static graph' badge naming each Tier B language, and Gaps lists each language once. Dockerfiles, Makefiles and SQL are read by the `repo` adapter and get no badge. HTML and CSS are markup, not Tier B. Tree-sitter symbols for Tier B languages are after 1.0.0."
- **S4. Python's real public API** (6.1, `symbols.json`; section 4, `io.contracts`; decision 42). Proposed for 6.1: "For Python, the real public API is what another package can import from a library: a packable project that has `py.typed` or declares no scripts. Each module with no `_` part in its dotted path is an import path; its names are its literal `__all__`, else its public top-level names plus relative re-exports, followed to the defining file. `[project.entry-points]` groups other than scripts are listed too." For section 4: "For Python, TS, JS and C#, followed by a measured table ...".
- **S5. The graph cards** (section 4, `components.map`, `interactions.graph`; decision 8). Proposed: replace the "Until M6 ..." sentences with: "An interactive graph whose views code computes: the areas first, then each area's components (and, in `interactions.graph`, each component's modules). Each view keeps to the V12 budget by grouping nodes and, when needed, hiding the lightest links with a note saying so. The tables below it hold every component, module and import."
- **S6.** (Merged into S5.)
- **S7. Python projects** (6.1). Proposed: "The Python adapter treats every folder with `pyproject.toml`, `setup.py`, `setup.cfg` or `requirements.txt` and its own Python files as a project, as the JS adapter treats `package.json`; module names are relative to the project."
- **S8. Python blind spots** (6.4). Proposed: add "routes mounted under a prefix or built at run time, star re-exports in `__init__.py`" to the Python list.
- **S9. `repo` inputs** (6.1). Proposed: the `repo` adapter also gives "environment variables set in Dockerfiles and compose files, and compose `env_file` entries" as `io_candidates`.
- **S10. CI triggers** (6.1). Proposed: "CI workflows started by push, pull request or by hand" join "CI/cron" for every language.
- **S11. FastAPI `Depends`** (decision 11). No change for 1.0.0; recorded in `post-v1.md`.
- **S12.** (Covered by S2: the verifier is a subagent started with a prompt the skill ships.)
- **S13. `summary.json`** (section 9). No change; `schema_version` stays 1. Recorded so a later reader knows freshness and verifier results were left out on purpose.
- **S14. `process.md`** lists M6 as one session (Q2).
- **S15. V12** already says 30 edges; the code now checks it (M6-22). No wording change.
- **S16. `change.dead-code` for C#** (decision 45 and section 4). Proposed source text: "... internal types nothing references (C#, only when scip-dotnet ran); unused NuGet packages are not listed".

---

## Sources

Checked on 2026-11-09.

| What | Used for | Source |
|---|---|---|
| `git ls-remote` synopsis, `--exit-code` exits 2 when no ref matches, `--branches`/`--tags`, output `<oid> TAB <ref>`, `^{}` line for annotated tags | D6 | https://git-scm.com/docs/git-ls-remote |
| Mermaid `securityLevel: "strict"` (the default) disables click functionality | D7 | https://mermaid.js.org/config/usage.html |
| Vendored Mermaid is 12.2.0 | D7, O1 | `vendor/mermaid.min.js` (`version:"12.2.0"`) |
| `py.typed` is recursive; `-stubs` packages; re-export rules (`import X as X`, `from Y import X as X`, `from Y import *` takes `__all__`); `__all__` overrides; `_` names private | D10 | https://typing.python.org/en/latest/spec/distributing.html |
| `[project.scripts]`, `[project.gui-scripts]`, `[project.entry-points]` (groups one level deep; `console_scripts`/`gui_scripts` reserved); a missing `[build-system]` defaults to setuptools | D10 | https://packaging.python.org/en/latest/specifications/pyproject-toml/ |
| uv workspaces: `[tool.uv.workspace] members`/`exclude`, every member has a `pyproject.toml`, one shared `uv.lock` at the root; the page does not say where `.venv` goes | D9, O6 | https://docs.astral.sh/uv/concepts/projects/workspaces/ |
| endoflife.date API v1 `products/{name}`; `.NET` 10 latest `10.0.13`, eol 2028-11-14; 9 and 8 eol 2026-11-10 | row 16, M6-40 | `curl https://endoflife.date/api/v1/products/dotnet` (schema 1.2.1) |
| `RW`, `CA`, `BP`, `GC`, `ZU` pins on their default branches (`compare` behind 0; `CA` ahead 3, `ZU` ahead 5); licences MIT except `gothinkster` (none) | Paths, D19, block S | `gh api repos/<r>/compare/<pin>...<branch>` and `gh api repos/<r>` |
| `TO`: MIT, tag `2.5.0` = `a2a5789`, flit, src layout, `__all__ = ("loads", "load", "TOMLDecodeError")` re-exported from `._parser`, `py.typed`, nested `requirements.txt` in four folders; `MI`: MIT, tag `v11.2.1` = `4aeb433`, flit, flat layout, `__init__.py` star-imports `more` and `recipes` (each with `__all__`), `.pyi` stubs, `py.typed` | D10, block Y | `gh api repos/<r>/tags`, clones in `~/.cache/dossier-m6-plan/src/` |
| The `dossier:dossier-verifier` agent is in plugin `dossier@dossier` 1.4.3 from the `1npo/dossier` marketplace | row 7, Q4 | `~/.claude/plugins/installed_plugins.json`, `~/.claude/plugins/cache/dossier/dossier/1.4.3/agents/dossier-verifier.md` (both read during planning; the plugin and its cache were removed afterwards, Q4) |
| M4 ground truth folder gone; M5 truth folder present with the expected hash | risk 4, section 2 | `ls ~/.cache`, `sha256sum` |
| The post-M2 UAT removed the import-graph diagrams | row 2, Q1 | `git show 1e5712c` |

Not re-verified, because no new task uses them differently from M4 and M5: scip-dotnet, scip-python, dependency-cruiser, knip, scip-typescript, semgrep and tree-sitter pins (plan 011, Sources; plan 010, Sources). Semgrep rule forms for M6-29 and M6-30 are checked at the start of Phase 4 (O2).
