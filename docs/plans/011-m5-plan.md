# Plan 011: milestone M5 (the C# adapter, its rules and its blind-spot list)

Status: written by Opus on 2026-11-08 from `docs/prompts/plan-m5.md`. **Section 7's questions were answered by the author on 2026-11-08** (answers recorded under each question). Section 8's spec issues take the proposed wording by default, under the rule in section 2 ("Judgement calls about C# and TS"); the author may still change any of them.

**If you were started for Phase 4a, stop reading here.** Find the heading `## Phase 4a: Ground truth for the primary repository` and read only that section. It must stay independent of everything else in this file.

Written from: `plans/004-v1-spec.md` (decisions 1 to 46), `docs/process.md`, `docs/post-v1.md`, plan 010 in full (including its results, rulings and follow-up), and the code at commit `dbf9d6b` (version 0.9.0). The test repositories and scip-dotnet were read from shallow clones in `~/.cache/dossier-m5-plan/src/`. Nothing was installed, restored or built, except that the cached tree-sitter and semgrep workers were run offline on two tiny scratch files to confirm the C# grammar and rule syntax. Writing this plan changed no other file. Section 7 says what I read and what I did not.

Paths used below:

- `SKILL` = `/home/nick/dev/projects/encamp/configs/user/claude/.claude/skills/dossier`, the development copy and the repository that holds the commits.
- `INSTALLED` = `/home/nick/.local/share/encamp/configs/user/claude/.claude/skills/dossier`. `~/.claude/skills/dossier` points at it. Never edit it, and never read it as the source of truth.
- `LIVE` = `/home/nick/dev/dossiers/cannalerts`, the author's dossier. Only section 6 touches it, and only to copy it.
- `REPO` = `/home/nick/dev/projects/cannalerts`, pinned at `5923c09`. Read-only. It is the **Python golden** repository.
- `FIX` = `SKILL/tests/fixtures/encamp-m0`, frozen and git-ignored. Never written; tests copy it.
- `PYFIX` = `SKILL/tests/fixtures/pyrepo/`, `JSFIX` = `SKILL/tests/fixtures/jsrepo/`. Not edited.
- `CSFIX` = `SKILL/tests/fixtures/csrepo/`, the new C# fixture repository (M5-7). Committed as plain files; it becomes a git repository only in a temporary folder at test time.
- `RW` = `realworld-apps/aspnetcore-realworld-example-app` at `9345f18abf36b778abe2f290467ba432bf1f7e5c` (MIT), the **primary** repository. It gets the ground truth.
- `CA` = `jasontaylordev/CleanArchitecture` at `4739ae4cbd057ee142bc1e1bdc93c4fea8f0cac5` (MIT), the **breadth** repository (no ground truth). It is also the real **mixed C# and TypeScript** repository: it ships an Angular app (`src/Web/ClientApp`) and a React app (`src/Web/ClientApp-React`), each with a `package-lock.json`.
- `LIB` = `ardalis/GuardClauses` at `61dde6c9d3e1715286bd100144a9edff1ad0664c` (MIT at that commit), the **library** repository. Block Y uses it for the real public API only. It gets no dossier and no ground truth.
- `SCIPSRC` = `sourcegraph/scip-dotnet` at tag `v0.2.16` (`fadd98aebb1ede2c55801636360c002679b54112`), read for the gate.
- Tests run from `SKILL`: `uv run --with pytest --with pygments python -m pytest tests -q`. **Baseline at `dbf9d6b`: 1993 passed, 117 skipped (60 s), measured 2026-11-08.** The working tree then had uncommitted changes to `assets/dossier.css`, `assets/dossier.js`, `assets/template.html` and `scripts/render.py` that are not mine (see Phase 1, first step). The slow baseline is in "Results (planning)" at the end of section 4.
- Slow tests need `DOSSIER_SLOW=1`, the network, the real tools and **`--basetemp` outside `/tmp`**.

---

## 1. Summary

- A new adapter, `csharp`, fills all eight `extract/*.json` outputs for C#: tree-sitter and semgrep for everything that can be read from the text (projects, entry points, I/O sites, EF Core models, tests, type-use graph, public surface and the real public API), and **scip-dotnet** for references and call data. Everything except scip-dotnet works with no .NET SDK at all.
- **Phase 1 is the scip-dotnet gate** (decision 2), with written pass and fail criteria. I expect it to **pass with four mitigations** the plan already contains (D2). If it fails, M5 continues on tree-sitter and semgrep only, with `partial` badges and Gaps entries, after the author says so.
- NuGet restore is switched on (`dotnet restore --locked-mode`, per project lock file). scip-dotnet is installed from a hash-checked package with no NuGet involvement. The C# blind-spot list (V7) gets twelve patterns. The real public API is reported for packable libraries and tested on `LIB`.
- No card or schema changes. Report 02 does not change. Python and JS output must stay the same, and section 6 proves it. `VERSION` goes to 0.10.0.
- **Seven Sonnet sessions and two Opus sessions, plus one Sonnet session if Opus finds faults** (D20): 1 gate and tools; 2 text extractors; 3 scip-dotnet, API and the fixture test of record; 4 shared layer, prompts, version; 4a Opus ground truth; 5 primary build and verification; 5a Opus rulings; 5b fixes; 6 breadth, mixed and library builds, then merge.

---

## 2. Shared rules (every phase reads this first)

- **Branch.** All phases work on one branch, `feat/dossier-m5`, created from `main` in Phase 1 and merged at the end of Phase 6. One commit per task. Opus phases commit only their "Results" section.
- **Skills to load at the start of every phase:** `git-commit`, `git-workflow`, `py-projects`, `py-unit-tests`, `claude-planning-docs`. Phase 4 also loads `docs-project`, `docs-readme` and `git-release`.
- **Commit style.** Follow `git-commit`. Suggested messages match the M4 commits (`feat(dossier): ...`, `test(dossier): ...`, `docs(dossier): ...`).
- **Never touch:** `INSTALLED`, `LIVE` (copy it), `REPO`, `FIX`, `/home/nick/dev/dossiers/`, `PYFIX`, `JSFIX`, the pinned clones of `RW`, `CA` and `LIB` (they are analysed, never changed). If a step seems to need a change in `INSTALLED`, make it in `SKILL`. Nothing from `RW`, `CA` or `LIB` is ever committed: no fixture, no snippet, no saved output. `CSFIX` is original code.
- **Report 02 and card schemas.** Report 02 (its panels, CSS and JS) does not change. **No file in `prompts/schema/*.json` changes.** M5 adds no card. Where a task adds a table or a line to an existing card, it says so, and a page with no C# is byte-identical to today.
- **Python and JS behaviour must not change.** `scripts/py_*.py`, `scripts/js_*.py`, `scripts/node/`, `rules/python/`, `rules/js/`, `PYFIX` and `JSFIX` are not edited. Shared code may change only where a task says so, and then it must give the same result for Python and JS. Section 6 blocks P and JS prove it. `test_py_adapter_slow.py` and `test_js_adapter_slow.py` must pass unedited at the end of every phase.
- **Report 02 guard.** After every task that edits `render.py`, `assets/dossier.css` or `assets/dossier.js`, run section 6 block E. It must print `OK`.
- **Scratch.** Every command that renders or builds sets `DOSSIER_HOME`, `DOSSIER_CONFIG` and `DOSSIER_CACHE` to a fresh folder under `~/.cache`, never `/tmp` (a 7.5 GB tmpfs that filled up twice in M4). Unit tests use `tmp_path`. **The slow suite always runs with `--basetemp=$HOME/.cache/dossier-m5-slow`**, and that folder is removed afterwards. Nothing outside section 6 and Phase 1's M5-1 builds or restores a real repository.
- **Every child process goes through `sandbox.run`**, directly or through `ctx.run`. No sandboxing, containers or namespaces (spec decision 5). The one network call made in-process is the scip-dotnet package download (D3), which uses the standard library and checks a SHA-512.
- **No new runtime dependencies** in `scripts/dossier.py` or anything it imports (standard library plus `pygments`).
- **Tests first.** Each task starts with a test that fails on the current code. Run it, see it fail, and record the failure line in the commit body as `Fails before: ...`. The full suite passes after every task. The slow suite passes at the end of each phase, except the three known failures: `test_overlapping_paragraphs_are_reported`, `test_each_browser_mutation_makes_a_fail[chart-text-small-chart text]` and the G2 golden (`test_golden02_slow.py`).
- **Do not weaken a check to make it pass.** If a check fails on real output, the output is wrong until the author says otherwise. A slow test may be skipped only when the .NET SDK it needs is missing, and the skip reason must say so; the phase acceptance criteria require those tests to have run.
- **Measured values are never written by Claude.** Nothing is dropped silently: no `[:N]` on data that feeds a card.
- **Plain language** in everything a dossier user reads. The author is new to C#: every Gaps statement for C# says what static analysis could not see, in words a newcomer understands. Gaps statements use the fixed wording in this plan, so their ids stay stable.
- **If the code contradicts this plan, stop and report** under that phase's "Results". Do not design around it.
- **Size.** Keep each new Python module under about 300 lines. **Tree-sitter patterns stay one or two levels deep** (plan 007, M2-8); join captures in Python by line ranges instead of writing deep patterns.
- **Context.** Keep tool output short: single test files while working, long output through `tail`. Never print a whole page or a whole `extract/*.json`.
- **Ticking.** Tick each task's checkbox in the same commit as the task. Write results under the phase's "Results" heading.
- **One writer per file.** Never run two sessions at once: every phase writes this plan.
- **Judgement calls about C# and TS** (the author's rule, 2026-11-08). The author is new to C# and TS and will correct dossier from work codebases (`post-v1.md`). When a question needs C# or TS judgement (what counts as an entity, an entry point, a public API, dead code, a rule's scope), **do not stop and wait**: take the sensible default this plan gives, or the one you would recommend, record it under the phase's "Results" and under "Findings for the milestone review" with one line on why, and carry on. Still stop for anything that is not a C# or TS judgement: a failed safety or hygiene check, a contradiction between the code and this plan, a merge conflict, or a step that would install or run something the author has not accepted.

---

## 3. Spec versus code

"Absorb" means the plan can absorb it as proposed. "Decision" means the author answers first (section 7 or 8).

| # | Area | Spec says | Code does today (0.9.0, `dbf9d6b`) | Proposal | Class |
|---|---|---|---|---|---|
| 1 | What exists for C# | 6.1 to 6.4: a C# adapter | `tools.json` maps `C#` to scope `csharp`, has a `dotnet` host entry (`dotnet --list-sdks`, min 8.0.100, "SDK 8 or later" hint), `scip-dotnet` 0.2.14 `via: dotnet-tool` with `cards: []`, and `dotnet-package-list` `via: sdk` with `cards: []`. `toolcheck.HOST_FOR_VIA` maps `dotnet-tool` and `sdk` to `dotnet`. `sandbox` sets `NUGET_PACKAGES`, `DOTNET_CLI_HOME`, `DOTNET_CLI_TELEMETRY_OPTOUT`, `DOTNET_NOLOGO`. The `nuget` restore entry is `enabled: false`, root only. `deps.CSharpAdapter` (report 02 only) reads `*.csproj`, `Directory.Packages.props`, `packages.config` and `packages.lock.json` **as text**; it never calls `dotnet`. No adapter, rules or fixture | Build the adapter (D1). Leave `deps.py` as it is | Absorb |
| 2 | scip-dotnet maturity | Decision 2: revisit at the start of M5 | Pinned 0.2.14 (2026-05-05) | Gate in Phase 1 (D2). New pin **0.2.16** (2026-10-21, NuGet), the newest stable at least 14 days old. It targets `net10.0`, `net9.0` and `net8.0`, reads `.sln`, `.slnx` (merged 2026-05-27) and project files, uses Roslyn's `MSBuildWorkspace` | Absorb |
| 3 | scip-dotnet restores by itself | 5.1, 5.4: restores are lockfile-only and asked once | - | Its `index` command runs a plain `dotnet restore` (not locked, no hygiene, a timeout that only warns) unless given `--skip-dotnet-restore` (read in `ScipProjectIndexer.cs`). **Always pass `--skip-dotnet-restore`**; dossier's own restore stage does the restore (D5) | Absorb |
| 4 | scip-dotnet failure signal | "a failed tool gives partial cards" | - | It **exits 0 even when MSBuild cannot load a project**, logging `Failure:` lines, and writes an index with no documents when nothing loads (read in `IndexCommandHandler.cs`). Exit 1 only when no solution or project file is found. The client decides failure from the log and the document count (D11) | Absorb |
| 5 | Generated code in SCIP | 6.4: source generators are a blind spot | - | scip-dotnet indexes `project.Documents` only, which excludes source-generated documents. Generators still run inside it (Roslyn builds the compilation). So edges into generated code are lost; this is the `source-generator` blind spot (D10) | Absorb |
| 6 | SCIP symbol strings | Staleness (5.3) must not change on every commit | Plan 010 noted that scip-python's `--project-version` puts the sha in symbols | scip-dotnet writes `scip-dotnet nuget . . <Namespace>/<Type>#<Member>().` for in-repo symbols (no version) unless `--allow-global-symbol-definitions` is given, which dossier never passes. **No staleness fault.** But it keeps only the **last segment of a namespace** (open issue #85, and `CreateScipSymbol` in `ScipDocumentIndexer.cs`), so `A.Models.Item` and `B.Models.Item` share one symbol, and parameters (`Greet().(name)`) and type parameters are separate definitions. D11 handles both | Absorb |
| 7 | Tool install and pin | 6.2: "`dotnet tool`"; 5.4 rule 7: pinned | `via: dotnet-tool`, nothing installs it | Download `scip-dotnet.0.2.16.nupkg` once from nuget.org, check its SHA-512 against `tools.json` (the value nuget.org publishes, which I matched on the downloaded file), unzip it into the tool cache, and run `dotnet <dir>/tools/net<N>.0/any/scip-dotnet.dll`. No `dotnet tool install`, no manifest, no NuGet feed at run time (D3, spec issue S8) | Decision (S8) |
| 8 | `dotnet list package` | 6.2: `dotnet list package --include-transitive` | `tools.json` says `dotnet package list` | Both are right: .NET 10 introduced the noun-first form `dotnet package list` and the docs say SDK 9 and earlier use `dotnet list package`. Its output (transitive packages) is already in `packages.lock.json`, which `deps.py` reads, and report 02 must not change, so **nothing would read its output**. Not run in M5; the `tools.json` entry stays with `cards: []` and a note (D4, spec issue S6) | Decision (S6) |
| 9 | .NET SDK on this machine | 6.2: ".NET SDK for any C# repo" | **This machine has the .NET runtime 10.0.14 only, no SDK** (`dotnet --list-sdks` prints nothing; installed by `6e5669c` from Microsoft's apt feed). `RW` and `CA` pin SDK `10.0.403` with `rollForward: latestFeature` | The author installs SDK **10.0.403** before Phase 1 (Q1). The adapter reads each `global.json` and checks the SDKs the host has, with the documented roll-forward rules (D6). A mismatch is a missing tool for preflight, like an old Node | Decision (Q1) |
| 10 | Restore | 5.1: `dotnet restore --locked-mode`, lockfile only, project folders | `nuget` entry disabled, root only | Enable it with `nested: true` and a `{project}` token (D5). Add `-p:NuGetAudit=false` so a vulnerability warning cannot fail a restore in a repository that treats warnings as errors (`RW` does), and because dossier is not a security tool | Absorb |
| 11 | No lock file | 5.1: lockfile only | `decide` skips with a reason when there are no plans | `CA` and `LIB` have **no** `packages.lock.json`. Following the spec, they get no restore, and Gaps says so per project. scip-dotnet then runs without packages (D5). Spec issue S7 asks whether exact central versions may count as a lock | Decision (S7, Q4) |
| 12 | What runs during restore and indexing | Decision 5 accepts host execution, reduced by hygiene | - | Restore evaluates the repository's MSBuild files (`Directory.Build.*`, project files, any targets hooked to restore), which can run code; NuGet packages have no install scripts. scip-dotnet's design-time build also imports the `build/` targets of restored packages and runs the repository's and packages' **source generators** in its own process; analyzers do not run. Both run under the `restricted` profile and only on a trusted ref (D5, D11). Without a restore, package targets and package generators are not loaded, so less code runs, and scip-dotnet still indexes (gate G9 measures how much) | Decision (Q2) |
| 13 | Workloads, `NuGet.config`, private feeds | 5.4 rules 2 and 3 | `registry_auth` exists per ecosystem; `AUTH_FAILURE` already matches `NU1301` | The repository's `NuGet.config` is honoured (sources). Private feeds need `registry_auth.nuget`. Workloads are never installed: a project that needs one fails to restore with `NETSDK1147`, recorded with a fixed reason (D5) | Absorb |
| 14 | Environment allowlist | 5.4 rule 1 lists `DOTNET_CLI_TELEMETRY_OPTOUT`, `DOTNET_NOLOGO` | Those two, plus `NUGET_PACKAGES`, `DOTNET_CLI_HOME` | Add `DOTNET_ROOT` (passed through when set, needed when the SDK is installed by script), `MSBUILDDISABLENODEREUSE=1` (no MSBuild node outlives the stage), `DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE=1`, `DOTNET_GENERATE_ASPNET_CERTIFICATE=false`, `DOTNET_ADD_GLOBAL_TOOLS_TO_PATH=false`, `DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1`. M5-1 confirms each name; any that the SDK does not document is dropped (D5, spec issue S11) | Decision (S11) |
| 15 | Projects below the root | Prompt item 4 | `deps.py` finds `*.csproj` anywhere; nothing else knows projects | `cs_project` finds `.sln`, `.slnx` and `.csproj` at any depth (D7). Python stays root-only (`post-v1.md`) | Absorb |
| 16 | `graph` shape | 6.1: nodes (modules, files), edges (import, call), cycles | Python and JS edges are imports | C# has no file imports (`using` names a namespace). Graph edges are **type-use edges**: file A uses a type declared in file B, resolved with namespaces, `using` and project references, from tree-sitter (D8). They exist without the SDK. SCIP adds `ref-edge` call data. Cycles are computed between **namespaces** inside a project, because files that use each other are normal in C# (D8, spec issues S12, S14) | Decision (S12, S14) |
| 17 | Projects as nodes | - | - | New `cs-project` and `project-reference` graph items, read by `candidates` text and by a new staleness feed (D8, D16) | Absorb |
| 18 | Test files | grimp has none in its graph | `gather.TEST_RE` matches only `*Tests.cs`/`*Test.cs` for C# | Test files are every `.cs` file in a **test project** (by SDK, `IsTestProject` or test package), plus `TEST_RE`. `TEST_RE` itself is not changed (it feeds report 02). Test files are not `module` items; their edges feed `tests.paths` (D9) | Absorb |
| 19 | Generated files | - | `gather.GENERATED_NAME` matches `.designer.cs` in lower case only, so EF's `*.Designer.cs` counts as source; `obj/` and `bin/` are not noise segments | Not changed in `gather` (report 02). The adapter marks a file `generated` when its name ends `.Designer.cs`, `.g.cs` or `.g.i.cs` (any case) or its first 10 lines hold `<auto-generated`. `**/bin/**`, `**/obj/**` and `artifacts/**` are expected untracked (D12) | Absorb |
| 20 | Entry-point kinds for C# | 6.1: "`Main`/`Program.cs` for C#" only | Kind names exist for Python and JS | Ten new kinds (D9, spec issue S3) | Decision (S3) |
| 21 | Route prefixes | - | JS: `route-mount` blind spot plus prompt text | `RW` sets its `/api` prefix with an MVC convention read from configuration. New `route-convention` blind spot, and `MapGroup` reuses `route-mount`. `reports.md` tells Claude to write full paths (D9, D10) | Absorb |
| 22 | Data entities | 4: "EF entities, ORM models, SQL DDL"; decision 43 filters TS | `measured_er` keys on `(family, name)` | C# entities are only what a data store holds: EF Core entity types, Dapper row types, `[Table]` classes, and enums used by their fields. DTOs, records, envelopes, view models and options classes are left out (D13, spec issue S4) | Decision (S4) |
| 23 | Migrations | "migrations" in `models.json` | `repo_adapter.sql_tables` gives `migration` items for `.sql` | EF migration classes and model snapshots give `migration` items (D13) | Absorb |
| 24 | Tests | Tree-sitter plus config parsing | Python and JS only. `repo_adapter.TEST_COMMAND` has no `dotnet test` | `cs_queries.tests` (D14). `TEST_COMMAND` gains `dotnet test`, and `repo` goes to version 4 | Absorb |
| 25 | DI | 6.2: semgrep finds DI "where the language has a common container: C# and TS"; decision 35 made TS DI a blind spot | No category, no home card | Same rule for C#: `di-registration` (existing id), `di-scan` and `di-resolution` blind spots, hits to Gaps (D10, spec issue S5) | Decision (S5) |
| 26 | V7 for C# | 6.4 list | Python, JS and All | Twelve patterns (D10) | Absorb |
| 27 | Public surface per file | 6.1 states it for Python and TS only | `scip_read._public` is Python's rule | C# rule from accessibility modifiers (D15, spec issue S1) | Decision (S1) |
| 28 | Real public API | Decision 42: M5 proposes the C# equivalent | `js_api`, `public-api` items and `measured_tables.public_api` exist | Public and protected members of public types in packable library projects, from tree-sitter and project files; no SDK needed (D15, spec issue S2) | Decision (S2) |
| 29 | Dead code | `change.dead-code`: "vulture, knip" | `dead_rows` lists Python modules nothing imports and `dependencies.json` unused packages | For C#: internal types that nothing references, only when scip-dotnet ran, plus the existing unused-package rows (D17, spec issue S10, Q8) | Decision (S10, Q8) |
| 30 | Git-derived cards | Language-independent | Checked by reading: `markers.py` treats `//` as a comment (C# is the same); blast radius, co-change and ownership work on paths and on `graph` items; `dead_rows` skips modules that have a `language` key | Need C# complexity (D14) and type-use edges (D8) to be useful. `.razor` and `.cshtml` files have no language in `gather`, so they are not source files for V4 or hotspots; Gaps says so (D10). M5-29 tests blast radius and dead-code rows for C# modules | Absorb |
| 31 | Mixed repositories | 11 item 2: same skeleton | `run_extract` keeps one section per adapter; `candidates.load` joins them in adapter-name order | `csharp` sorts before `js`, so Python-only and JS-only repositories are unchanged. `CA` is the real mixed test (D18) | Absorb |
| 32 | Preflight and `doctor` | 5.1, 5.2 | `dotnet` host line with min 8.0.100 | Keeps the minimum, adds the repository's `global.json` need, and prints scip-dotnet as "from a hash-checked NuGet package" (D6) | Absorb |
| 33 | Upgrade burden | P1, runtimes and major frameworks | Python and Node rows; `eol.json` already has `dotnet` (as of 2026-11-05: 10 until 2028-11-14, 9 and 8 until 2026-11-10) | One `.NET` row per target framework of a non-test project (D19). First to cut | Absorb |
| 34 | Partial badges | 5.1 | `process.partial_cards` reads `tools.json` `cards` | Fill `cards` for scip-dotnet (D4) | Absorb |
| 35 | Staleness | 5.3 | `FEEDS`, `_feed` | New `projects` feed; C# symbols carry no version (D16) | Absorb |
| 36 | Razor and Blazor | Not mentioned | Not classified | `@page` directives in `.cshtml` and `.razor` give routes (pure Python). scip-dotnet does not index them (open PR #117) and semgrep's C# rules read `.cs` only (`lang.json`), so Gaps lists them (D9, D10) | Absorb |
| 37 | Submodules | 5.4 rule 5 | Gaps lists them | `RW` has one (`realworld`, the API spec). Default off; Gaps entry expected | Absorb |
| 38 | P0 versus P1 | Cut line | P1 cards in play: `change.upgrade-burden` | M5-26 is the only cut that touches a card | Absorb |
| 39 | Session count | `process.md`: M5 is one session | M4 took 5 + 2 + 1 | Seven Sonnet, two Opus, one conditional (D20). The `process.md` change is Q3; this plan does not edit it | Decision (Q3) |
| 40 | Working tree at `dbf9d6b` | - | Uncommitted edits to `assets/*` and `render.py` exist that are not part of any plan | Phase 1 stops if they are still there (first step) | Absorb |

**How the plan 008 checks apply to what M5 adds.** M5 adds no card, so V6 is untouched.

| New thing | V5 | V11 | V12 |
|---|---|---|---|
| New entry kinds, entity kinds | Per-row rule (A5), Fields complete | Existing row counts | Existing |
| C# rows in the public API table (`io.contracts`) | Exempt: measured | Existing count (M4-21a), extended to C# items | Existing page-wide checks, on the M5 test page at both widths |
| InternalsVisibleTo line under that table | Exempt | New count (M5-24) | Same |
| C# rows in `change.dead-code` | Exempt: measured | `dead_rows` is the shared source | Existing |
| `.NET` rows in `change.upgrade-burden` | Exempt | `rows()` is the shared source | Existing |
| New rows in `reading.map`, `conventions.tooling` | Exempt | Existing counts | Existing |

---

## 4. Decisions

### D1. Adapter structure

One class, `CSharpAdapter` in `scripts/cs_adapter.py`: `name = "csharp"`, `version = "1"`, `rules = (RULES,)` with `RULES = SKILL/rules/csharp`, `languages = ("C#",)`, `tools = ("scip-dotnet", "semgrep", "tree-sitter-language-pack")`, `expected_untracked = ("**/bin/**", "**/obj/**", "artifacts/**")`, `loads_repo_code = False`. It shares `ctx.semgrep` and `ctx.treesitter`. scip-dotnet is gated on its own (trust and SDK), as the JS adapter gates its Node tools, so semgrep and tree-sitter always run (decision 39).

| File | Owns |
|---|---|
| `scripts/cs_project.py` (new) | Pure: solutions, projects, project references, `Directory.Build.props`, `global.json`, which file belongs to which project, source roots, test projects, packable libraries |
| `scripts/cs_sdk.py` (new) | Pure plus one `dotnet --list-sdks`/`--list-runtimes` call: SDK roll-forward rules, the SDK gate |
| `scripts/cs_queries.py` (new) | Tree-sitter queries and the Python joins: declarations, usings, attributes, complexity, static state, tests |
| `scripts/cs_graph.py` (new) | Pure: type-use edges, namespace cycles, project items, module items |
| `scripts/cs_entries.py` (new) | Pure: entry points from declarations (controllers, `Main`, top-level statements, hosted services, functions, consumers, jobs), and `@page` routes |
| `scripts/cs_models.py` (new) | Pure: EF Core entities, Dapper and `[Table]` types, migrations |
| `scripts/cs_api.py` (new) | Pure: public surface flags and the real public API (D15) |
| `scripts/cs_scip.py` (new) | scip-dotnet install (D3), run, failure rules, disambiguation and symbol finishing (D11) |
| `scripts/cs_semgrep.py` (new) | Pure: semgrep results to items (as `js_semgrep.py`) |
| `scripts/cs_adapter.py` (new) | `CSharpAdapter`: the steps in order, with per-tool status |
| `scripts/measured_cs.py` (new) | `reading.map` and `conventions.tooling` additions (as `measured_js.py`) |
| `rules/csharp/*.yml`, `tests/fixtures/semgrep/csharp/*.cs` (new) | Semgrep rules and their tests |
| `tests/fixtures/csrepo/` (new) | The fixture repository |
| `tests/tools/m5_page.py` (new) | The M5 test page for V11 and V12 |

`adapters._registered()` returns `(CSharpAdapter, JsAdapter, PythonAdapter, RepoAdapter)`.

Rejected: one class per framework (only rules differ); `loads_repo_code = True` (it would stop semgrep and tree-sitter on an untrusted ref); a custom Roslyn tool (deferred by decision 2 unless the gate fails and the author chooses it).

### D2. The scip-dotnet gate (Phase 1, M5-1)

Run on a **tiny throwaway solution** written in the session's scratch folder (the fixture does not exist yet), on `RW` and on `CA`, after the author has installed SDK 10.0.403 (Q1) and accepted Q2. Each criterion has a command and a value to record.

| Id | Criterion | How checked | Pass when |
|---|---|---|---|
| G1 | Release and date | NuGet registration for `scip-dotnet` | 0.2.16 is listed, published 2026-10-21, not deprecated; the downloaded `.nupkg` SHA-512 (base64) is `UUaPQCnqIWFYGXaKtgjieBP0WR0uH8L55pwqhtOJH/3El+zCF5/cXXX30oYXrfKYZibDjun2knU8r1212i+eWw==` |
| G2 | Runs on the pinned SDK | `dotnet <dir>/tools/net10.0/any/scip-dotnet.dll --version`, with `dotnet --list-sdks` showing 10.0.403 | exit 0 |
| G3 | Reads `.slnx`, central package management and several projects | The tiny solution: `T.slnx` listing `Lib/Lib.csproj` and `App/App.csproj` (App references Lib), `Directory.Packages.props` with `ManagePackageVersionsCentrally` and no packages, `global.json` pinning 10.0.403 with `latestFeature`. `App` uses a `Lib` class and calls one of its methods. Restore through `sandbox.run` with `dotnet restore T.slnx --locked-mode` after creating empty lock files with `--use-lock-file` once. Index with `--skip-dotnet-restore` | exit 0; `scip_read.decode` and `scip_read.reduce` read the index **unchanged**; every `.cs` file has at least one `def`; one `ref-edge` from `App/` to `Lib/` |
| G4 | Real repository, restored | `RW`: `dotnet restore Conduit.slnx --locked-mode -p:NuGetAudit=false` through `sandbox.run` in a scratch area, then index `Conduit.slnx` with `--skip-dotnet-restore` | exit 0; documents for at least 95% of the tracked `.cs` files of the three projects; zero `Failure:` lines; wall time at most 600 s |
| G5 | Cross-project references | `RW` index after `reduce` | at least one `ref-edge` from `tests/Conduit.IntegrationTests/` to `src/Conduit/` |
| G6 | No version in symbols | `RW` index | every in-repo definition symbol starts with `scip-dotnet nuget . . ` |
| G7 | Shared symbols | `RW` index | Record: how many global symbols are defined in more than one document, and how many of those are `partial` types (by reading the files). No pass or fail |
| G8 | Source-generator output | Tiny solution: add `[GeneratedRegex("a+")] private static partial Regex R();` in `Lib` (the generator ships in the SDK, so no package is needed) | Record: whether the index has a document for generated code (expected no) and whether the call site's occurrence names `R` (expected yes). No pass or fail |
| G9 | Without a restore | A fresh copy of `RW` with no `obj/` folders, indexed with `--skip-dotnet-restore`; and `CA` (no lock files, so no restore) the same way | Record: exit code, document count, `Failure:` lines (first three), time. Pass when exit 0 and the index decodes |
| G10 | How it fails | Index an empty folder; index a project file with a syntax error in its XML | Record exit codes and whether an index file is written (expected: exit 1 and no index; exit 0 with `Failure:` and an empty or partial index) |
| G11 | Writes into the checkout | `git status --porcelain --ignored` in each copy before and after | Record the untracked paths it created. Pass when no tracked file changed |
| G12 | Writes outside the area | Modification times of `~/.nuget`, `~/.dotnet/tools`, `~/.local/share/NuGet` before and after | Pass when none changed |

**Gate result.** It **passes** when G1 to G6, G9, G11 and G12 pass. G7, G8 and G10 only feed D11.

**What I expect: pass.** scip-dotnet 0.2.16 is recent (October 2026, with a security fix release cadence through 2026), targets the .NET 10 runtime, has `.slnx` support since May 2026, and uses `MSBuildWorkspace`, so project references come from MSBuild itself. Its weak points are known from its source and are handled without a custom tool: the restore it runs on its own (always skipped), exit 0 on failure (D11 reads the log), the shortened namespaces (D11 disambiguates), and generated code (a blind spot). The least certain criteria are G4's time and G9's behaviour without packages.

**On a fail.** The author chose (a) in advance (Q9), so Phase 1 does **not** stop: record the failure, tell the author in the phase's hand-over message, and carry on with (a). The two options were:

- **(a) Fallback, the default, inside decision 2.** M5 continues with tree-sitter and semgrep only. M5-2 still pins nothing new for scip-dotnet; its `tools.json` entry keeps 0.2.16 with `"gate": "failed"`. In M5-17 the adapter records scip-dotnet as `skipped` with the reason `scip-dotnet did not pass the M5 check, so references were not indexed.`, `symbols` gets tree-sitter `def` items (D11), and `components.catalog`, `interactions.flows` and `interactions.graph` carry `partial` badges with the existing "Made without scip-dotnet" Gaps item. Every other task is unchanged, because the graph comes from type-use edges in either case (D8). Section 6 drops blocks Q's scip part and G5's measurement.
- **(b) A custom Roslyn tool.** This is a new plan, not part of M5 as written. Stop.

**After the golden run.** Decision 2 also says to revisit after the C# golden run if DI wiring is missed. Phase 5a records every miss caused by DI and says whether a Roslyn tool would have found it. The author decides at the milestone review.

### D3. Installing scip-dotnet

`tools.json` entry:

```json
{"id": "scip-dotnet", "scope": ["csharp"], "via": "dotnet-tool", "package": "scip-dotnet", "version": "0.2.16", "published": "2026-10-21",
 "nupkg": {"url": "https://api.nuget.org/v3-flatcontainer/scip-dotnet/0.2.16/scip-dotnet.0.2.16.nupkg",
           "sha512": "UUaPQCnqIWFYGXaKtgjieBP0WR0uH8L55pwqhtOJH/3El+zCF5/cXXX30oYXrfKYZibDjun2knU8r1212i+eWw==", "size": 56673777},
 "gives": "C# symbols and references", "source": "https://github.com/sourcegraph/scip-dotnet", "first_used": "M5", "verified": "<M5-1 date>",
 "cards": ["components.catalog", "interactions.flows", "interactions.graph"]}
```

`cs_scip.ensure_installed(cache_root, tool, timeout) -> Path`:

1. Folder `<cache_root>/.dossier-tools/dotnet/scip-dotnet-0.2.16/`. If its `.installed` marker holds the `sha512` and `tools/net10.0/any/scip-dotnet.dll` exists, return the folder.
2. Otherwise download the `url` with `urllib.request` (standard library, timeout from the argument) to `scip-dotnet.0.2.16.nupkg.part`, compute the SHA-512, base64-encode it, and compare with `sha512`. On a mismatch delete the file and raise `ToolError("The scip-dotnet package did not match its pinned checksum, so it was not used.")`.
3. Unzip with `zipfile`, refusing any member whose path is absolute or contains `..`. Write the marker last.

This is the one in-process network call. It runs no code from the package. The package carries all its own assemblies (it has no dependencies in its nuspec), so no NuGet feed is used at run time. Its `DotnetToolSettings.xml` names `Runner="dotnet"` and `EntryPoint="scip-dotnet.dll"`, so running the DLL with `dotnet` is what `dotnet tool` itself does.

**Which framework folder.** `cs_sdk.runtime_majors(run)` reads `dotnet --list-runtimes` (`Microsoft.NETCore.App <version>`). Use `tools/net<M>.0/any/` for the highest `M` in `(10, 9, 8)` that is installed. None gives the skip reason `scip-dotnet needs the .NET 8, 9 or 10 runtime, and none is installed.`

**Version in report 01.** From `tools.json`, by the existing path. The index's own `ToolInfo.version` is the literal `0.1.0-SNAPSHOT` and is ignored.

**`doctor`.** `toolcheck.format_text` prints `from a hash-checked NuGet package` for a tool with `nupkg` (next to `from a lockfile with npm`). `preflight`'s self-installing entry gains `"checked": bool(t.get("nupkg"))`.

Rejected: `dotnet tool install --tool-path` (needs a feed at run time, and no hash check: tool manifests hold versions only, and `dotnet tool restore` checks nothing); shipping a `dotnet-tools.json` (same reason).

### D4. Tools, pins and what is not run

| Tool | Pin | Where confirmed |
|---|---|---|
| scip-dotnet | 0.2.16 (2026-10-21) | NuGet registration and flat container; tag `v0.2.16` = `fadd98a`, whose `ScipDotnet.csproj` says `Version 0.2.16`, `TargetFrameworks net10.0;net9.0;net8.0`, Roslyn 5.3.0 |
| .NET SDK (host) | 10.0.403 for `RW` and `CA` (their `global.json`); minimum 8.0.100 for others | `releases.json` for .NET 10: 10.0.403 shipped 2026-10-25 with runtime 10.0.14 |
| tree-sitter-language-pack | unchanged 1.22.1; grammar name `csharp` | Run offline in planning: `csharp` parses, and the node names `file_scoped_namespace_declaration`, `class_declaration`, `record_declaration`, `attribute`, `modifier`, `if_statement`, `switch_expression_arm`, `binary_expression` with `operator:` are accepted. M5-1 confirms the rest of D14's list |
| semgrep | unchanged 1.181.0; C# is **generally available** (`lang.json` maturity `ga`, extension `.cs` only) | Run offline in planning: a `languages: [csharp]` rule with `$S.AddScoped<$T>(...)` and an attribute-on-method pattern matched, and `semgrep --test` passed with `// ruleid:` and `// ok:` in a `.cs` target |
| `dotnet package list` | not run (S6) | docs page for `dotnet package list` |

`tools.json` changes: the `scip-dotnet` entry as D3; `dotnet-package-list` gets `"open": "Not run: packages.lock.json already lists the indirect packages, and nothing reads this output (plan 011, S6)."`; the `dotnet` host entry keeps `min` 8.0.100 and its install text becomes `Install the .NET SDK (8 or later, or the version a repository's global.json asks for): https://learn.microsoft.com/dotnet/core/install/linux-scripted-manual`. The `nuget` restore entry as D5.

### D5. Restore

```json
{"ecosystem": "nuget", "lockfile": "packages.lock.json", "nested": true, "enabled": true,
 "command": ["dotnet", "restore", "{project}", "--locked-mode", "-p:NuGetAudit=false", "--disable-build-servers", "-v", "minimal"],
 "source": "https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-restore"}
```

- One plan per folder holding a tracked `packages.lock.json`, which is where NuGet writes it (beside the project file). `restore.run` expands `{project}` to the one `*.csproj` (or `*.fsproj`, `*.vbproj`) tracked in that folder. With none or several, the plan fails with `The lock file {lockfile} is not beside exactly one project file, so it was not used.` A project's restore also restores its project references, so a repeated restore of a referenced project is harmless.
- cwd is the project folder, so the `dotnet` host finds the repository's `global.json` by searching upward (documented).
- **SDK gate first.** Before running nuget plans, `restore.run` calls `cs_sdk.problem(...)` (D6) once. With a problem, every nuget plan is `skipped` with that reason, and no `dotnet` command runs.
- Restored packages go to `NUGET_PACKAGES=<area>/cache/nuget`, already set. The scratch `HOME` gets NuGet's default user config, so only `nuget.org` plus the repository's own `NuGet.config` sources are used.
- A project that needs a workload fails with `NETSDK1147` in its log. The reason becomes `Restoring {project} needs a .NET workload, and dossier does not install workloads.{where}`.
- **No lock file.** `restore.decide` is unchanged: no plan, no restore. The adapter adds one `cs-note` per C# project without a lock file (D10), so Gaps says `The packages of {project} were not installed, because it has no packages.lock.json and dossier installs only from lock files.`
- `restored["nuget"]` is true only when every nuget plan succeeded (existing `restore.restored`).
- **Environment** (5.4 rule 1). `sandbox.ALLOWED_NAMES` gains `DOTNET_ROOT`, `MSBUILDDISABLENODEREUSE`, `DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE`, `DOTNET_GENERATE_ASPNET_CERTIFICATE`, `DOTNET_ADD_GLOBAL_TOOLS_TO_PATH`, `DOTNET_SKIP_FIRST_TIME_EXPERIENCE`. `build_env` sets the last five to `1`, `1`, `false`, `false`, `1`, and passes `DOTNET_ROOT` through from the parent when set. M5-1 step 2 confirms each name in the SDK documentation; an undocumented one is dropped, and "Results (Phase 1)" says which.
- **What runs, under decision 5:** see section 3 row 12. The restore question already says "Installing can run the project's own build code on this machine". It needs no change.

### D6. SDK version policy

`cs_sdk.py`:

- `parse_global_json(text) -> dict | None`: the `sdk` object (`version`, `rollForward`, `allowPrerelease`), tolerating comments (the docs allow `//` and `/* */`). An invalid file gives `None`.
- `pick(installed: list[str], want: dict | None) -> str | None`: implements the documented table for `patch` (the default when a version is given without `rollForward`), `feature`, `minor`, `major`, `latestPatch`, `latestFeature`, `latestMinor`, `latestMajor` and `disable`, with versions read as `x.y.znn` (`z` the feature band, `nn` the patch). No `global.json` or no version gives the highest installed. Prerelease SDKs are skipped unless `allowPrerelease` is true.
- `requirements(tree, read) -> list[{"path", "version", "rollForward"}]`: every tracked, non-noise `global.json` with an `sdk.version`.
- `problem(run, tree, read) -> str | None`: runs `dotnet --list-sdks` (profile `tool`, 15 s). Missing `dotnet` or no SDK gives `The .NET SDK is not installed.`. Otherwise, for the first requirement no installed SDK satisfies: `The repository asks for .NET SDK {version} ({rollForward}) in {path}, and this machine has {installed or "none"}.`
- **Preflight.** `stages.stage_tools`, when `C#` is among the languages, calls `cs_sdk.requirements` and `cs_sdk.pick` with the SDKs `toolcheck` already read. An unmet requirement marks the `dotnet` host entry `old` with `needs` set to `{version} ({rollForward}) for {path}`, so `doctor` prints `TOO OLD` and `prepare` stops with exit 2 unless `--allow-missing`. With the flag, the existing host Gaps item appears, and every `dotnet` step is skipped with D6's reason. Python and JS repositories never reach this code.

Roll-forward is never forced: dossier does not edit `global.json`, set `DOTNET_ROLL_FORWARD`, or pass an SDK version. The NuGet docs warn that a different SDK can change implicit package versions and make a locked restore fail; that failure is recorded like any other.

### D7. Solutions, projects and scope

`cs_project.projects(tree, read) -> dict` returns:

```python
{"solutions": [{"path": "Conduit.slnx", "projects": ["build/build.csproj", "src/Conduit/Conduit.csproj", ...]}],
 "projects": [{"path": "src/Conduit/Conduit.csproj", "dir": "src/Conduit", "name": "Conduit", "sdk": "Microsoft.NET.Sdk.Web",
               "output_type": "Exe", "frameworks": ["net10.0"], "test": False, "packable": False, "package_id": None,
               "assembly": "Conduit", "root_namespace": "Conduit", "references": ["..."], "packages": ["Serilog", ...],
               "friends": [], "lock": True, "files": ["src/Conduit/Program.cs", ...]}],
 "loose_files": ["..."], "targets": ["Conduit.slnx", "tools/Legacy/Legacy.csproj"]}
```

Rules, in order:

1. A **project** is a tracked, non-noise `*.csproj`. `.fsproj` and `.vbproj` are listed with `"language": "F#"` or `"Visual Basic"` and get no C# files.
2. Project XML is read with `xml.etree.ElementTree` after stripping a BOM. Properties are read from unconditioned `PropertyGroup`s of the project, then of every `Directory.Build.props` from the project folder up to the root, nearest first; the project wins. Conditions are not evaluated: a property inside a conditioned group is ignored. Unparseable XML gives a project with `"error": "<first line>"` and is still listed.
3. `output_type`: `OutputType`, else `Exe` for `Microsoft.NET.Sdk.Web` and `Microsoft.NET.Sdk.Worker`, else `Library`. `frameworks`: `TargetFrameworks` split on `;`, else `TargetFramework`.
4. `test`: `IsTestProject` is `true`, or the SDK is `MSTest.Sdk`, or a `PackageReference` is `Microsoft.NET.Test.Sdk`, `xunit`, `xunit.v3`, `NUnit`, `MSTest.TestFramework`, `MSTest` or `TUnit`.
5. `packable`: false when `IsPackable` is `false`, when `test`, when `output_type` is `Exe` or `WinExe` and `PackAsTool` is not `true`, or when the SDK is `Microsoft.NET.Sdk.Web` or `Microsoft.NET.Sdk.Worker`; else true.
6. `references`: `ProjectReference Include`, with `\` turned into `/`, resolved against the project folder, kept when tracked.
7. `friends`: `InternalsVisibleTo Include` items, plus `[assembly: InternalsVisibleTo("X")]` found by M5-9's attribute query.
8. **Files.** Every tracked `.cs` file belongs to the project in the nearest folder at or above it (SDK projects include `**/*.cs` below their folder, minus nested project folders). Files under no project are `loose_files`.
9. **Solutions** at any depth: `.sln` by the regular expression `^Project\("\{[^}]+\}"\)\s*=\s*"[^"]*",\s*"([^"]+\.csproj)"` (multiline), `.slnx` by `Project Path=` in XML. Paths are relative to the solution's folder.
10. **Targets for scip-dotnet**: every solution, then every C# project in no solution. When two solutions share projects, both run; documents are joined by path, first seen wins (D11).

`source_roots(projects, tree)`: with one project, `root` is that project's folder; with several, the parent folder of each project folder, and a project at the repository root gets none. Items `{"kind": "source-root", "path": <csproj>, "root": <folder>}`. For `RW` this gives `src` and `tests` (and none for `build/`).

### D8. `graph` items for C#

| Kind | Fields |
|---|---|
| `module` | `path`, `module` (the path without `.cs`), `short` (the file's stem), `namespaces` (declared in the file), `project` (csproj path or null), `language: "csharp"`, `generated` (D12), `complexity` |
| `import` | `path`, `paths: [used file]`, `from`, `to` (module names), `lines` (first line of a use), `via: "type-use"`, `type_only: false`, `dynamic: false`, `names` (the type names used, sorted) |
| `cycle` | `modules` = namespace names, `level: "namespace"`, `project` |
| `cs-project` | `path` (csproj), `name`, `sdk`, `output_type`, `frameworks`, `test`, `packable`, `references` |
| `project-reference` | `path` (csproj), `paths: [referenced csproj]`, `from`, `to` (project names) |
| `source-root` | D7 |
| `cs-note` | D10's fixed Gaps items: `path`, `note`, `name` |

**Type-use edges** (`cs_graph.type_uses(decls, projects) -> list`). From M5-9's declarations:

1. Each type declaration gives a key (full namespace, simple name) and its file. Nested types give `Outer.Inner` under the outer type's namespace and also the simple name `Inner` with the outer type as the containing scope.
2. In file A, a name `N` is visible from: A's own namespaces and every parent namespace; each `using X;` and `global using X;` in A; each `global using` in any file of the same project; and `using static` and alias usings by their target. A dotted name `X.Y.N` is matched as written.
3. The candidates are the declarations of `N` in visible namespaces, in A's project or a project A's project references (transitively). An edge goes from A to every file declaring `N` when all candidates are parts of one `partial` type; when the candidates are different types, no edge is made and the miss is counted in `cs-note` `ambiguous-name` (D10).
4. Identifiers in A are taken from `identifier` nodes in M5-9's query whose text starts with a capital letter, plus generic names (`List<Order>` gives `Order`). An edge needs at least one use outside A's own declarations.
5. Edges from test files go to `tests.paths` (D14), not to `import` items. Self-edges and edges to files outside the tree are dropped.

This is a measured approximation: extension methods, `var`-typed uses and anything reached through reflection or DI are invisible to it. Gaps carries the fixed item `C# file links come from type names in the text; uses through extension methods, var, reflection or dependency injection are not linked.`

**Cycles.** Collapse edges to (namespace of A, namespace of B) inside one project and call `graphs.cycles` on that namespace graph. Python and JS cycles are unchanged.

### D9. Entry points

| Kind | Source | `name` | Trigger |
|---|---|---|---|
| `program-main` (new) | a `static` method named `Main` in a non-test project, or a `Program.cs` holding top-level statements (`global_statement`) | the project name | ``starting `{name}` (for example with `dotnet run`)`` |
| `http-route` | controllers (below) and minimal APIs (semgrep) | `GET /articles/{slug}` | ``a web request to `{name}` `` |
| `ui-route` | `@page "/x"` in a tracked `.razor` file | the route | ``opening `{name}` in the browser`` |
| `http-route` | `@page` in a tracked `.cshtml` file (Razor Pages) | `GET {route}` (the folder path when `@page` has no route) | as above |
| `hosted-service` (new) | a class whose base list names `BackgroundService` or `IHostedService`, and `AddHostedService<T>()` | the class name | `when the host starts` |
| `grpc-service` (new) | `MapGrpcService<T>()` | `T` | ``a gRPC call to `{name}` `` |
| `signalr-hub` (new) | `MapHub<T>("/path")` | the path | ``a SignalR connection to `{name}` `` |
| `function` (new) | a method with `[Function("N")]` or `[FunctionName("N")]` | `N` | from its trigger attribute: `HttpTrigger` a web request, `TimerTrigger` a schedule, `QueueTrigger`/`ServiceBusTrigger`/`EventHubTrigger`/`BlobTrigger`/`CosmosDBTrigger` a message or a change; otherwise `when Azure Functions calls {name}` |
| `scheduled-job` | Hangfire `RecurringJob.AddOrUpdate("id", ...)`, Quartz classes implementing `IJob`, `[TimerTrigger]` functions | the job id or class | `a schedule` |
| `queue-consumer` | classes implementing `IConsumer<T>` (MassTransit), `IHandleMessages<T>` (NServiceBus), `ServiceBusProcessor`, `EventingBasicConsumer`/`AsyncEventingBasicConsumer` (RabbitMQ), `IConsumer<,>.Consume(` (Kafka) | the class or the call | `a message for the task {name}` |
| `cli-command` | System.CommandLine `new Command("x")`, Spectre `AddCommand<T>("x")`, CommandLineParser `[Verb("x")]`, McMaster `[Command("x")]` | the command | ``the `{name}` command`` |
| `build-target` (new) | Bullseye `Target("x", ...)`, Cake `Task("x")`, in a project whose `packages` hold `Bullseye` or `Cake.Frosting`, or in `build.cake` | the target | ``running `dotnet run --project {project} -- {name}` `` |

Container `ENTRYPOINT`/`CMD`, Makefile targets, CI schedules, shebang scripts (`build.sh`) and systemd units come from the `repo` adapter, unchanged.

**Controllers** (`cs_entries.controller_routes(decls)`): a class is a controller when it is not abstract and its name ends `Controller`, or its base list names `Controller` or `ControllerBase`, or it has `[ApiController]` or `[Controller]`, and it has no `[NonController]`. Its prefix is the first `[Route("...")]` on the class (empty if none). Each public method with `[HttpGet]`, `[HttpPost]`, `[HttpPut]`, `[HttpPatch]`, `[HttpDelete]`, `[HttpHead]`, `[HttpOptions]` (with or without a template) or `[AcceptVerbs("GET", ...)]`, or with `[Route("...")]` and no verb (method `ANY`), gives one row per verb. The path is the prefix joined with the method template by `/`, except that a template starting with `/` or `~/` replaces the prefix. `[controller]` becomes the class name without `Controller`, `[action]` the method name, `[area]` stays as written. Names are written as the code writes them (case kept) with one leading `/`. A controller with no attribute route at all gives no rows; the `conventional-route` blind spot covers it. `rule` is `cs.controller-route`, `snippet` is `{METHOD} {path}`.

**Minimal APIs** (semgrep, `rules/csharp/entry.yml`): `$R.MapGet("...", ...)`, `MapPost`, `MapPut`, `MapDelete`, `MapPatch`, `MapMethods("...", ...)`, `Map("...", ...)`, `MapFallback(...)`, `MapFallbackToFile(...)`. `metadata.detail` captures the method and path in one group (`Map(Get|Post|Put|Delete|Patch|Methods|Fallback)?\(\s*"([^"]*)`), and `cs_semgrep.route_name` splits it as `js_reduce.route_parts` does. A call whose first argument is not a string literal is the `string-route` blind spot; `MapGroup("...")` is `route-mount`. Routes are named as written, without group prefixes; `reports.md` tells Claude to add them.

**Frameworks supported in M5.** ASP.NET Core MVC and Web API controllers, minimal APIs, Razor Pages, Blazor `@page`, SignalR, gRPC, hosted and worker services, Azure Functions (isolated and in-process), Hangfire, Quartz, MassTransit, NServiceBus, RabbitMQ.Client, Confluent.Kafka, Azure Service Bus, System.CommandLine, Spectre.Console.Cli, CommandLineParser, McMaster, Bullseye, Cake. **Sent to Gaps**, one fixed item each when a project references the package: `FastEndpoints`, `Carter` (its modules use `MapGet` and are partly found), `ServiceStack`, `Nancy`, `Wolverine`, `Microsoft.Orleans.Server`, `Dapr.AspNetCore`, `Akka`, and `Aspire.Hosting.AppHost` (the app host is a `program-main`; what it starts is not detected).

### D10. Blind spots (V7) and fixed Gaps items

Rules are `languages: [csharp]`, `severity: INFO`, ids `dossier.csharp.blindspot.<name>`, with `metadata: {category: blindspot, pattern: <id>}`. `checks_v7.BLIND_SPOTS` gains the new ids; existing wording does not change.

| Pattern id | How detected | What the dossier says it may miss | Report |
|---|---|---|---|
| `di-registration` (existing) | `$S.AddScoped<...>(...)`, `AddTransient`, `AddSingleton`, `TryAddScoped`, `TryAddTransient`, `TryAddSingleton`, `AddKeyedScoped`, `AddKeyedTransient`, `AddKeyedSingleton`, and the same without type arguments | objects built and passed in by a dependency injection container | `interactions` |
| `di-scan` (new) | `Scan(...)`, `RegisterAssemblyTypes(...)`, `AddValidatorsFromAssembly(...)`, `AddValidatorsFromAssemblyContaining<...>()`, `RegisterServicesFromAssembly(...)`, `AddMediator(...)`, `AddAutoMapper(...)` | services registered by scanning assemblies, so which classes are used is decided at run time | `interactions` |
| `di-resolution` (new) | `GetService<...>()`, `GetRequiredService<...>()`, `GetKeyedService<...>(...)`, `GetRequiredKeyedService<...>(...)`, `ActivatorUtilities.CreateInstance(...)`, `[FromServices]`, `[FromKeyedServices(...)]` | objects fetched from the dependency injection container by type while the program runs | `interactions` |
| `reflection` (new) | `Activator.CreateInstance(...)`, `Type.GetType(...)`, `$A.GetTypes()`, `$A.GetExportedTypes()`, `$T.GetMethod(...)`, `$M.Invoke(...)` after `GetMethod`, `Assembly.Load(...)`, `Assembly.LoadFrom(...)`, `$T.GetProperty(...)` | code found or called through reflection | `interactions` |
| `route-convention` (new) | `$O.Conventions.Add(...)`, base lists naming `IApplicationModelConvention`, `IControllerModelConvention`, `IActionModelConvention`, `IRouteTemplateProvider` (regex on the class line) | routes changed by MVC conventions, so their full path may differ from the attributes beside them | `entry` |
| `conventional-route` (new) | `MapControllerRoute(...)`, `MapDefaultControllerRoute()`, `MapAreaControllerRoute(...)` | controller actions reached through a route template, which have no path of their own in the code | `entry` |
| `mvc-filter` (new) | `$O.Filters.Add<...>(...)`, `$O.Filters.Add(...)`, `[ServiceFilter(...)]`, `[TypeFilter(...)]`, `AddEndpointFilter(...)`, base lists naming `IActionFilter`, `IAsyncActionFilter`, `IResultFilter`, `IExceptionFilter`, `IAuthorizationFilter`, `IEndpointFilter`, `ActionFilterAttribute` | filters that run before or after requests, attached by attribute or registration | `interactions` |
| `mediator-handler` (new) | base lists naming `IRequestHandler<`, `INotificationHandler<`, `IPipelineBehavior<`, `IStreamRequestHandler<`, `ICommandHandler<`, `IQueryHandler<`; calls `$M.Send(...)` and `$M.Publish(...)` with `$M` matching `(?i).*(mediator|sender|publisher)$` | requests passed to their handlers by a mediator library, so the call does not name the code that runs | `interactions` |
| `source-generator` (new) | `[Mapper]`, `[LoggerMessage(...)]`, `[GeneratedRegex(...)]`, `[JsonSerializable(...)]`, `[GeneratedComInterface]`, `[LibraryImport(...)]`, and partial methods without a body; plus one `cs-note` `generator` per project referencing `Riok.Mapperly`, `Mediator.SourceGenerator`, `CommunityToolkit.Mvvm`, `Refit`, `StronglyTypedId`, `Vogen` or any `PackageReference` whose `IncludeAssets` names `analyzers` | code generated at build time, which is not in the repository and was not read | `components` |
| `partial-class` (new) | `pattern-regex: (?m)^[ \t]*(?:\w+[ \t]+)*partial[ \t]+(?:class|record|struct|interface)\b` | a type split across several files with `partial`, so one file shows only part of it | `components` |
| `codegen` (existing id) | `pattern-regex: <auto-generated` in `rules/csharp/blindspot.yml` (the shared rule does not match EF's `// <auto-generated />`) | unchanged | unchanged |
| `feature-flag` (existing id) | `IFeatureManager`, `IVariantFeatureManager`, `[FeatureGate(...)]`, `IsEnabledAsync(...)` on a receiver matching `(?i).*feature.*` | unchanged | unchanged |
| `string-route`, `route-mount` (existing ids) | D9 | unchanged | `entry` |

Wording for the new ids is the text in the table. The multi-line regex rules use `^[ \t]*`, not `^\s*` (plan 010, M4-17 finding 3).

**Fixed coverage items** (`checks_v7.cs_coverage(extract) -> list`, called from `checks.validate` beside `js_coverage`):

- Report `change`, when any `module` has `language: "csharp"`: `Stale feature flags and unused routes are not detected for C#.` How to confirm: `This is a known limit of this version of dossier.` The Python and JS items are unchanged (the Python one appears only for modules with no `language` key, so it is not added for C# modules).
- Report `interactions`, the same condition: D8's type-use sentence. How to confirm: `This is a known limit of this version of dossier.`
- From `cs-note` items (`note`, `name`, statement, report, how to confirm):
  - `framework`: `Routes and handlers written for {name} are not detected, so check the entry points by hand.` (`entry`, known limit)
  - `no-lock`: D5's sentence with `{project}` = `name` (`dossier`, known limit)
  - `sdk`: `The C# tools that need the .NET SDK did not run: {name}` (`dossier`, `Install the SDK named here and build again.`)
  - `razor`: `{name} Razor or Blazor file(s) were not read by the reference index or the pattern rules; only their @page routes were found.` (`dossier`, `Read these files by hand.`)
  - `generator`: `Code generated at build time by {package} in {project} is not in the repository, and static analysis did not read it.` with `name` = `{package}|{project}` (`components`, known limit)
  - `ambiguous-name`: `{name} type name(s) are declared more than once in visible namespaces, so uses of them were not linked between files.` (`interactions`, known limit)
  - `ambiguous-symbol`: `{name} name(s) were given the same identity by scip-dotnet, so references to them were not counted.` (`interactions`, known limit)
  - `unindexed`: `{name} C# file(s) are not in the scip-dotnet index, so references from and to them were not counted.` (`interactions`, `Read these files by hand.`)
  - `msbuild`: `scip-dotnet could not load every project: {name}` (`dossier`, `Build the solution once with dotnet build and read the errors.`)
  - `api`: as D15.
  - `dead`: D17's sentence (`change`, known limit).

### D11. `symbols`: running and reading scip-dotnet

`cs_scip.ScipDotnet(run, dll, timeout).index(checkout, target, area, n) -> Path`:

`dotnet <dll> index <target> --working-directory <checkout> --output <area>/scip/cs-<n>.scip --skip-dotnet-restore`, profile `restricted`, cwd the checkout, timeout `config.timeouts()["tool"]`. Document paths in the index are relative to the working directory (`Path.GetRelativePath` in `ScipProjectIndexer.cs`), so they match the tree.

**Failure rules** (D2 G10): exit not 0, timeout, no index file, or an index with no documents is `failed` with the first `Failure:` line or the last stderr line. Exit 0 with `Failure:` lines in stdout or stderr keeps the documents, sets the tool `failed` with reason `scip-dotnet could not load every project: {first Failure line}`, and adds a `cs-note` `msbuild`. One failing target does not stop the others; the status recorded is the worst seen.

**Gates, in order:** `ctx.trusted` false gives `skipped` with `The ref is not trusted, so scip-dotnet did not run. Use --allow-ref to run it.`; `cs_sdk.problem(...)` gives `skipped` with that reason; no runtime gives D3's reason; an install error gives `failed`.

**Reading.** For each index: `scip_read.decode`, then `cs_scip.disambiguate(index) -> (index, count)`, then join all documents (first seen path wins), then **one** `scip_read.reduce` call, then `cs_scip.finish_symbols(items, decls) -> list`. `scip_read.py` is not edited.

- `disambiguate`: a global symbol with definition occurrences in two or more documents is a `partial` type when every defining document declares a `partial` type of that name (from M5-9); then it is kept, and `reduce` gives its references to the first document. Otherwise every occurrence of it is rewritten to `local ambiguous-<n>`, which `reduce` skips. `count` goes into a `cs-note` `ambiguous-symbol` when above 0.
- `finish_symbols`: drops `def` items whose symbol ends with a parameter or type-parameter descriptor (a final `)` not followed by `.`, or a final `]`); sets `public` from D15's per-file rule by matching the def's path and line to a declaration; drops defs in `generated` files.
- **Files missing from the index.** Tracked C# files of indexed projects with no document go into a `cs-note` `unindexed` with their count.
- **Without scip-dotnet** (skipped or failed, or the gate fallback): `symbols` gets one `def` per declaration from M5-9, with `symbol` = `cs <namespace>/<Type>#<member>`, `type` from the declaration kind, `public` from D15, `refs: 0`, `via: "tree-sitter"`, and no `ref-edge`. These keys are line-free, so the digest is stable between such builds.

### D12. Generated code

| Output | `obj/`, `bin/`, `artifacts/` (untracked) | Tracked generated file (D12 rule) |
|---|---|---|
| `graph` | not present (filtered as expected untracked) | `module` with `generated: true`, `complexity: 0`; no outgoing type-use edges; incoming edges kept |
| `symbols` | none | defs dropped (D11); not in the public API (D15) |
| `io_candidates`, `entry_points` | none | not scanned by semgrep's I/O and entry rules |
| `blindspots` | none | `codegen` hit (one per file, so Gaps has one row per generated file) |
| `models` | none | migration classes and snapshots are read (D13) |
| `tests` | none | not test files |
| `dead` | none | never listed |

The rule: name ends `.Designer.cs`, `.g.cs` or `.g.i.cs` (any case), or one of the first 10 lines contains `<auto-generated`.

### D13. Models

Kinds: `ef-entity`, `ef-owned`, `dapper-row`, `table-class`, `cs-enum`, and `migration` (not an entity).

- **DbContexts:** classes whose base list names `DbContext`, `IdentityDbContext` (any type arguments) or another DbContext class in the repository. Each `DbSet<T>` property, each `modelBuilder.Entity<T>(...)` call and each class implementing `IEntityTypeConfiguration<T>` names an entity type `T`.
- **Entity rows.** `T` must be declared in the repository (by simple name in a visible namespace, D8's lookup). One item per declaration: `{"kind": "ef-entity", "path", "line", "end_line", "name", "fields": [{"name", "type", "line", "ref", "pk", "many"}], "relations": [{"field", "to", "kind": "ef"}], "rule": "cs.ef-entity", "snippet"}`. Fields are the public properties with a getter (including those declared in base classes in the repository, attached to the entity's path). `ref` is set when the property type, with `?` removed and the element type taken from `ICollection<>`, `IList<>`, `List<>`, `IEnumerable<>`, `HashSet<>` or `ISet<>`, is another entity or entity enum; `many` is true for those collections. `pk` is true for `[Key]`, `Id`, or `{TypeName}Id`.
- **Owned types** (`OwnsOne<T>`, `OwnsMany<T>`, `[Owned]`): `ef-owned`.
- **Dapper:** `$C.Query<T>(...)`, `QueryAsync<T>`, `QueryFirst<T>`, `QueryFirstOrDefault<T>`, `QuerySingle<T>` (and `Async`) with `T` declared in the repository: `dapper-row`. **`[Table("x")]` classes:** `table-class`.
- **Enums** used as a field type by any of the above: `cs-enum`, fields = members.
- **Not entities:** every other class, record, struct or interface, including DTOs, request and response envelopes, view models, options classes and records used as messages (S4).
- **Migrations:** classes deriving `Migration` with `[Migration("id")]` give `{"kind": "migration", "tool": "ef-core", "name": id, "path", "line"}`; classes deriving `ModelSnapshot` give the same with `"snapshot": true`. `.sql` files keep coming from the `repo` adapter.
- `measured_er.family`: `ef-entity`, `ef-owned`, `cs-enum` give `"ef"`; `dapper-row` and `table-class` give `"other"`. Python and JS results are unchanged (asserted).
- I/O items from the same pass: `UseSqlServer(`, `UseSqlite(`, `UseNpgsql(`, `UseMySql(`, `UseInMemoryDatabase(`, `UseCosmos(` are `db-connect` (semgrep, D14 rules); `GetConnectionString("X")` is `config-file` with `detail` X.

### D14. Tree-sitter queries, tests and the semgrep rules

Grammar `csharp` for `.cs`. Queries stay one or two levels deep and are joined by line ranges in Python. **Node names M5-1 must confirm** (planning confirmed the ones marked ✓): `compilation_unit`, `namespace_declaration`, `file_scoped_namespace_declaration` ✓, `using_directive`, `class_declaration` ✓, `record_declaration` ✓, `struct_declaration`, `interface_declaration`, `enum_declaration`, `enum_member_declaration`, `delegate_declaration`, `method_declaration`, `constructor_declaration`, `property_declaration`, `field_declaration`, `event_field_declaration`, `variable_declarator`, `attribute_list`, `attribute` ✓, `attribute_argument_list`, `base_list`, `modifier` ✓, `global_statement`, `parameter`, `identifier`, `generic_name`, `qualified_name`, `invocation_expression`, `object_creation_expression`, `if_statement` ✓, `for_statement`, `foreach_statement`, `while_statement`, `do_statement`, `switch_section`, `switch_expression_arm` ✓, `catch_clause`, `conditional_expression`, `binary_expression` with `operator: ["&&" "||" "??"]` ✓.

`cs_queries.declarations(ts, files) -> dict[path, dict]`: per file, `namespaces` (name, start, end; a file-scoped one spans the file), `usings` (`{"name", "global", "static", "alias"}`), `types` (`{"name", "kind", "modifiers", "line", "end_line", "attributes": [{"name", "args", "line"}], "bases": [...], "partial", "outer", "namespace", "members": [{"name", "kind", "modifiers", "line", "end_line", "attributes", "type", "static", "params"}]}`), `top_level` (true when a `global_statement` exists), `idents` (capitalised identifier texts with their first line). Attributes belong to the declaration whose range holds them and whose name comes after them.

**Complexity** (`COMPLEXITY_Q`): `if_statement`, `for_statement`, `foreach_statement`, `while_statement`, `do_statement`, `switch_section`, `switch_expression_arm`, `catch_clause`, `conditional_expression`, and `binary_expression` with `operator: ["&&" "||" "??"]`. On `module` items.

**Static state** (`module_state`): a `static` field that is not `readonly` or `const`, or a `static readonly` field initialised with `new Dictionary`, `new List`, `new ConcurrentDictionary`, `new HashSet` or `[]`. Rule `dossier.csharp.state.static-mutable`, category `global-state`.

**Tests** (`cs_queries.tests(decls, projects) -> list`). Test files are D7's test-project files plus `TEST_RE` matches. One `test-file` item per file, Python's shape:

- `framework`: from the project's packages: `xunit`, `xunit.v3` give `xunit`; `NUnit` gives `nunit`; `MSTest.TestFramework`, `MSTest` or `MSTest.Sdk` give `mstest`; `TUnit` gives `tunit`; else `unknown`.
- `tests`: methods with `[Fact]`, `[Theory]`, `[Test]`, `[TestCase]`, `[TestCaseSource]`, `[TestMethod]`, `[DataTestMethod]` (counted once per method). `classes`: classes holding such a method, or with `[TestFixture]` or `[TestClass]`. `skips`: test methods with `Skip =` in `[Fact]`/`[Theory]` arguments, or `[Ignore]`, or `[Explicit]`. `xfails`: always 0.
- `mocks`: count of `new Mock<`, `Mock.Of<`, `Substitute.For<`, `A.Fake<`, `MockRepository(` in the file's text.
- `fixtures`: base lists naming `IClassFixture<`, `ICollectionFixture<`, `IAsyncLifetime`, `WebApplicationFactory<`; methods with `[SetUp]`, `[OneTimeSetUp]`, `[TearDown]`, `[TestInitialize]`, `[ClassInitialize]`.
- `test_kind`: `e2e` when the project references `Microsoft.Playwright`, `Selenium.WebDriver` or `Reqnroll*`, or its name contains `Acceptance` or `E2E`; `integration` when it references `Microsoft.AspNetCore.Mvc.Testing`, `Testcontainers*`, `Aspire.Hosting.Testing` or `Respawn`, or its name contains `Integration` or `Functional`; else `unit`.
- `paths` and `imports` from D8's test-file edges.
- `config` items: `*.runsettings`, `xunit.runner.json`, `coverlet.runsettings`, and `<Threshold>` in a test project (coverlet's MSBuild property) as `coverage_threshold`.

**Semgrep rule files** (`rules/csharp/`). Receiver tests use `metavariable-regex`, anchored at the start, so infix matches are written `.*(...)`. `detail` is a regular expression over the matched text, never a metavariable (semgrep hides metavariables without a login).

| File | Rule (category or kind): what it matches |
|---|---|
| `entry.yml` | `minimal-route` (http-route), `map-hub` (signalr-hub), `map-grpc` (grpc-service), `add-hosted` (hosted-service), `hangfire` (scheduled-job), `cli-command` (cli-command), `bullseye-target` (build-target): as D9 |
| `inputs.yml` | `env-var`: `Environment.GetEnvironmentVariable("...")`; `config-file`: `$C["..."]` with `$C` matching `(?i).*config.*`, `$C.GetValue<$T>("...")`, `$C.GetSection("...")`, `$C.GetConnectionString("...")`, `Configure<$T>(...)`, `BindConfiguration("...")`, `AddJsonFile("...")`, `AddEnvironmentVariables(...)`, `AddUserSecrets<$T>()`, `AddAzureKeyVault(...)`; `cli-args`: `Environment.GetCommandLineArgs()`, `CreateBuilder(args)`, `args[$N]`; `file-read`: `File.ReadAllText(...)`, `ReadAllTextAsync`, `ReadAllLines`, `ReadAllLinesAsync`, `ReadAllBytes`, `ReadAllBytesAsync`, `OpenRead`, `OpenText`, `new StreamReader(...)`, `UseStaticFiles(...)`; `stdin`: `Console.ReadLine()`, `Console.ReadKey(...)`, `Console.In`; `request-header`: `$R.Headers["..."]`, `[FromHeader(...)]` (one row per header name, as JS) |
| `outputs.yml` | `stdout`: `Console.WriteLine(...)`, `Console.Write(...)`, `Console.Error.WriteLine(...)`; `file-write`: `File.WriteAllText(...)` and its `Async`, `AppendAllText`, `WriteAllBytes`, `File.Create(...)`, `new StreamWriter(...)`; `outbound-call`: `new HttpClient(...)`, `AddHttpClient(...)`, `$F.CreateClient(...)`, `$H.GetAsync/PostAsync/PutAsync/DeleteAsync/SendAsync/GetFromJsonAsync/PostAsJsonAsync/PutAsJsonAsync/GetStringAsync(...)` with `$H` matching `(?i).*(http|client).*`, `new SmtpClient(...)`, `new BlobServiceClient(...)`, `new AmazonS3Client(...)`; `message-produce`: `$B.Publish(...)`, `$B.Send(...)` with `$B` matching `(?i).*(bus|endpoint|producer|publisher)$`, `$P.ProduceAsync(...)`, `$C.BasicPublish(...)`, `$S.SendMessageAsync(...)`; `exit-code`: `Environment.Exit(...)`, `Environment.ExitCode = $X`; `error-response`: `BadRequest(...)`, `NotFound(...)`, `Unauthorized(...)`, `Forbid(...)`, `Conflict(...)`, `UnprocessableEntity(...)`, `Problem(...)`, `ValidationProblem(...)`, `StatusCode($N, ...)` with `$N` of 400 or more, `Results.$M(...)` and `TypedResults.$M(...)` with those names, `$C.Response.StatusCode = $N`, `throw new $E(...)` with `$E` matching `.*(Http|Api|Rest)Exception$` or `^(NotFound|BadRequest|Unauthorized|Forbidden|Conflict|Validation).*Exception$` |
| `state.yml` | `db-connect`: `UseSqlServer`, `UseSqlite`, `UseNpgsql`, `UseMySql`, `UseInMemoryDatabase`, `UseCosmos`, `AddDbContext<$T>(...)`, `AddDbContextPool<$T>(...)`, `new SqlConnection(...)`, `new NpgsqlConnection(...)`, `new SqliteConnection(...)`, `new MongoClient(...)`, `ConnectionMultiplexer.Connect(...)`, `AddStackExchangeRedisCache(...)`; `db-access`: `$X.SaveChanges()`, `$X.SaveChangesAsync(...)`, `$X.Set<$T>()`, `FromSqlRaw`, `FromSqlInterpolated`, `ExecuteSqlRaw`, `ExecuteSqlInterpolated`, `SqlQuery<$T>`, `ExecuteUpdate`, `ExecuteDelete` (and `Async`), Dapper `Query`, `QueryAsync`, `Execute`, `ExecuteAsync` on `$C` matching `(?i).*(conn|connection|db).*`, and `$D.$S.$M(...)` with `$D` matching `(?i).*(context|db)$` and `$M` one of `Add`, `AddAsync`, `AddRange`, `Remove`, `RemoveRange`, `Update`, `Attach`, `Find`, `FindAsync`; `cache`: `AddMemoryCache(...)`, `$C.GetOrCreate(...)`, `GetOrCreateAsync`, `$C.Set(...)` with `$C` matching `(?i).*cache.*`, `SetStringAsync`, `AddOutputCache(...)`, `[ResponseCache(...)]`, `AddHybridCache(...)` |
| `concurrency.yml` | `thread`: `new Thread(...)`, `ThreadPool.QueueUserWorkItem(...)`; `async`: `Task.Run(...)`, `Task.WhenAll(...)`, `Task.WhenAny(...)`, `Parallel.For(...)`, `Parallel.ForEach(...)`, `Parallel.ForEachAsync(...)`, `new PeriodicTimer(...)`, `new Timer(...)`; `lock`: `lock ($X) { ... }`, `new SemaphoreSlim(...)`, `new Mutex(...)`, `new ReaderWriterLockSlim(...)`, `Interlocked.$M(...)`; `queue`: `Channel.CreateBounded<$T>(...)`, `Channel.CreateUnbounded<$T>(...)`, `new BlockingCollection<$T>(...)`, `new ConcurrentQueue<$T>(...)`; `process-pool`: `Process.Start(...)` |
| `resilience.yml` | `retry`: `AddPolicyHandler(...)`, `Policy.Handle<$E>()`, `$P.WaitAndRetry(...)`, `WaitAndRetryAsync`, `RetryAsync`, `AddResilienceHandler(...)`, `AddStandardResilienceHandler(...)`, `new ResiliencePipelineBuilder(...)`, `$B.AddRetry(...)`, `EnableRetryOnFailure(...)`; `timeout`: `$X.Timeout = $T`, `CancelAfter(...)`, `$B.AddTimeout(...)`, `CommandTimeout(...)`, `[RequestTimeout(...)]`; `catch-all`: `catch (Exception $E) { ... }`, `catch { ... }`, `UseExceptionHandler(...)`, base lists naming `IExceptionHandler`, `AppDomain.CurrentDomain.UnhandledException += $H`; `transaction`: `BeginTransaction(...)`, `BeginTransactionAsync(...)`, `new TransactionScope(...)` |
| `observability.yml` | `log`: `$L.LogInformation/LogWarning/LogError/LogDebug/LogTrace/LogCritical/Log(...)` with `$L` matching `(?i).*log.*`, `Log.Information/Warning/Error/Debug/Fatal/Verbose(...)`, `new LoggerConfiguration()`, `AddSerilog(...)`, `UseSerilog(...)`, `[LoggerMessage(...)]`; `metric`: `new Meter(...)`, `$M.CreateCounter<$T>(...)`, `CreateHistogram`, `CreateUpDownCounter`, `CreateObservableGauge`; `trace`: `new ActivitySource(...)`, `$S.StartActivity(...)`, `AddOpenTelemetry(...)`, `AddApplicationInsightsTelemetry(...)`, `SentrySdk.Init(...)`, `UseSentry(...)` |
| `blindspot.yml` | D10 |

Pure-Python inputs: every tracked `appsettings*.json` and `Properties/launchSettings.json` is a `config-file` item (rule `cs.appsettings`, `detail` = the file name). An environment variable named in a `launchSettings.json` profile is an `env-var` item (rule `cs.launch-env`). `gather.ENV_RE` already matches `Environment.GetEnvironmentVariable("X")`, so `v5_env` needs no change.

No new I/O category: every category above is already in `candidates.CATEGORY_CARD`.

### D15. Public surface and the real public API

**Per-file public surface** (the `public` flag on `def` items; spec issue S1). A declaration is public when its own accessibility is `public`, `protected` or `protected internal`, and every type that contains it is public by the same rule. A member of an interface with no modifier, and every enum member, takes its type's accessibility. A type with no modifier is `internal`; a member with no modifier is `private`. `private protected`, `internal`, `private` and `file` are not public. A `partial` type is public when any of its parts says `public` (the C# rule: the parts must agree or omit it).

**Real public API** (`cs_api.items(projects, decls) -> (symbols, notes)`; spec issue S2). What another assembly or a NuGet consumer can use:

- **Which projects:** `packable` projects (D7 rule 5). Web, worker, executable and test projects have none, so `RW` has none, and `CA`'s `Domain`, `Application`, `Infrastructure` and `Shared` libraries have one (they are libraries that other projects reference).
- **Which names:** each public type (D15's rule, top-level or nested) and each of its public or protected members, in the project's non-generated files. Members of a `sealed` or `static` class count `protected` as not public (it cannot be reached). One row per (type, member name): overloads are one row with Kind `method (N overloads)`. Extension methods (first parameter has `this`) have Kind `extension method`. Constructors are `constructor`. Records' positional parameters are properties.
- **Audience:** `packable` or `marked not packable` is not used (non-packable projects are left out); the column says `packable`, plus `, hidden from editors` for `[EditorBrowsable(EditorBrowsableState.Never)]` and `, obsolete` for `[Obsolete]`.
- **Not in the API:** `internal` types (so `internal` polyfills such as `CallerArgumentExpressionAttribute` are out), anything in a generated file, anything in a test project.
- **Items:** `symbols` kind `public-api`: `{"kind", "path", "line", "name": "Type" or "Type.Member", "symbol_kind", "package": PackageId or AssemblyName or project name, "subpath": namespace, "audience"}`. These are the same keys the JS items use, so `measured_tables.public_api` shows them unchanged: Package, Import path (the namespace), Name, Kind, Defined in, Audience.
- **InternalsVisibleTo:** one line per (project, friend) under the table: `{project} lets {friend} use its internal names (InternalsVisibleTo).` Measured, from D7 rule 7. It needs one small addition to `measured_tables.public_api` and a V11 count (M5-24).
- **No API:** when no C# project is packable and the repository has C# modules, the card shows the existing line `No package here declares a public API. What this repository offers from outside is in Entry points.` (the condition grows from `language: "js"` to `js` or `csharp`).
- **Gaps:** a packable project whose files could not all be parsed gives a `cs-note` `api`, and Gaps says `The public API of {project} could not be fully worked out.` (`io`, `Read this project's public types by hand.`).

### D16. Candidates, staleness and incremental builds

- No new candidate kind or category. New `entry_points` kinds and entity `models` kinds flow through `assign_ids`, `home_card`, V5, A5 and `dossier candidates` unchanged. `tests`, `dead`, `graph` and `symbols` stay measured; `blindspots` go to Gaps.
- `candidates.text` gains a `== C# projects ==` section when `cs-project` items exist: one line per project with its path, SDK, output type, test flag and file count. The Python and JS sections are printed as today.
- `FEEDS["components"]` gains `"projects"`, with `_feed` keys `["project", path, sorted(references)]`. Python and JS give no keys, so their digests do not change (asserted).
- The `csharp` section keys by `sha`, version, its three tools and the `rules` hash, as every adapter does. A section with a tool not `ok` is not reused, so a build without the SDK reruns once it is installed.
- scip-dotnet symbols hold no version (D2 G6), and the tree-sitter fallback symbols are line-free, so a comment-only commit leaves `components`, `interactions` and `entry` fresh. Block J checks it.
- Known limit, unchanged from M4: the reuse key does not include whether a restore ran.

### D17. Dead code (spec issue S10, Q8)

Only when scip-dotnet is `ok`: a `dead` item for each non-public (D15) class, record or struct in a non-test, non-generated file when (a) its definition symbol has `refs` 0 after D11, (b) it is not an entry point (D9) or an entity (D13), (c) its file has no `di-registration`, `di-scan`, `mediator-handler`, `mvc-filter`, `route-convention` or `reflection` hit, and (d) its base list names no interface or class from outside the repository. Fields: `rule: "scip-dotnet.unused-type"`, `type: "dead code without references"`, `name`, `confidence: null`, `snippet` (the author's wording, Q8: the row only says nothing references the type; whether to remove it is the reader's decision). Plus the fixed Gaps item `C# dead code is listed only for internal types that nothing references; a class found by reflection or registered by scanning can be listed wrongly, so check before removing anything.` (`change`). Unused packages keep coming from `dependencies.json` through `dead_rows`.

### D18. Mixed-language repositories

Each adapter writes its own section. `candidates.load` joins them in name order (`csharp`, `js`, `python`, `repo`), so a Python-only or JS-only repository is unchanged. Ids hash the path, and module names cannot clash between languages (C# names are paths, Python names are dotted). Preflight unions the host needs (Node for JS, the SDK for C#), which `toolcheck` already does per scope. The restore question lists both ecosystems. `reports.md`'s "Repositories with more than one language" paragraph needs only C# added to its examples. `dossier check` and the card skeleton depend on the schema alone. `CA` (Angular, React and C#) is the real test; block M is the fixture test.

### D19. Upgrade burden (P1)

`measured_upgrade.rows` gains, after the Node row, one `.NET` row per distinct target framework of non-test projects, read through `cs_project` from the tree: `net<M>.0` (with an optional `-platform` suffix) gives cycle `M` in the `dotnet` product; `netstandard*`, `netcoreapp*` below 3.1 and `net4*` give no row. Pinned: `TargetFramework net10.0`; source: the project or `Directory.Build.props` that sets it. `PACKAGE_PRODUCTS` is unchanged. `eol.json` is not refreshed (its `dotnet` data is from 2026-11-05). The Python and Node rows are unchanged (asserted).

### D20. Version, sessions and cut line

`VERSION` becomes **0.10.0**. A minor bump plans a full rebuild, which M5 needs. `repo` goes to version `4` (`TEST_COMMAND`). `js` and `python` versions do not move. The skill has no bump tool; edit `VERSION` directly, as M4 did.

| Phase | Model | Content | Why this cut |
|---|---|---|---|
| 1 | Sonnet | Gate, pins and install, SDK policy, environment, projects, restore, fixture, adapter frame | The gate decides the rest; everything later stands on a verified install |
| 2 | Sonnet | Tree-sitter declarations, type-use graph, entry points, models, tests, semgrep rules, V7 | Everything that needs no SDK; ends with real `extract/*.json` from text alone |
| 3 | Sonnet | scip-dotnet client and reading, public surface and API, dead code, `repo` test command, the fixture test of record | Needs the SDK and Phase 2's declarations |
| 4 | Sonnet | Shared readers, tables, upgrade, partial and staleness, test page, mixed fixture, prompts, docs, version | Everything that makes a build complete |
| 4a | Opus | Ground truth for `RW` | Must exist before any build, written apart (decision 34) |
| 5 | Sonnet | Ground-truth tool, the `RW` build, every verification block, the Python golden and the JS run | A full build is the exit criterion and needs a clean context |
| 5a | Opus | Rulings on block T, the component check, the DI question of decision 2 | Sonnet must not judge its own misses |
| 5b | Sonnet | Fixes from Phase 5a. Skipped if it found nothing and block T met its targets | Fixes need rulings first |
| 6 | Sonnet | `CA` build (breadth and mixed), block M, the library, skeletons, suites, merge | About the size of `RW` again, plus Node tools |

`process.md` says one session (Q3). Phase 4a needs nothing from Phases 1 to 4 and may run any time before Phase 5, but never at the same time as another phase (one writer per file).

**Cut, in this order, only if a phase cannot finish:** M5-26 (upgrade burden, P1); the `function` kind and the Azure Functions trigger mapping; the consumers other than MassTransit; D17 (dead code; then `change.dead-code` keeps only package rows and the Gaps item); Razor Pages and Blazor routes (then the `razor` Gaps item says no routes were read). Record any cut under "Results"; it becomes the first item of the next plan.

**Never cut:** extractor fixture tests, V7 for C# (every D10 rule with its test), the plan 008 checks on anything new (M5-24, M5-25), the Python golden and the JS run, the `RW` ground truth, Phase 5a, the real public API and block Y, any P0 card.

### Results (planning)

Slow-suite baseline at `dbf9d6b` (planning session, 2026-11-08, `--basetemp` under `~/.cache`, working tree dirty as noted above): **2106 passed, 1 skipped, 3 failed in 16 min 47 s.** The three failures are exactly the known ones: `test_overlapping_paragraphs_are_reported`, `test_each_browser_mutation_makes_a_fail[chart-text-small-chart text]` and the G2 golden.

---

## Phase 1: Gate, tools and projects

### Before you start (Phase 1)

Read section 2, section 3, D1 to D7, D20 and sections 7 and 8. Load the skills in section 2. Then:

1. `git -C $SKILL log --oneline -5` and `git -C $SKILL status --short`. The top should be `dbf9d6b` or a later commit that touches none of `scripts/`, `prompts/`, `rules/`, `tests/`. **If `git status` shows tracked changes you did not make (planning saw uncommitted edits to `assets/dossier.css`, `assets/dossier.js`, `assets/template.html` and `scripts/render.py`), stop and ask the author to commit or discard them.** If a later commit touches those folders, read it and stop if it contradicts this plan.
2. Section 7's answers are in (2026-11-08). Use them where they differ from the defaults, and say so in "Results (Phase 1)".
3. `dotnet --list-sdks` must list `10.0.403` or a later 10.0.4xx (installed from Microsoft's apt feed by `encamp`'s `install_dotnet_sdk`, Q1). `dotnet --list-runtimes` must list `Microsoft.NETCore.App 10.0.x`. `node --version` must print 22.13.0 or later with a major of 22, 24 or 26 and up (needed for block M and `CA`). If not, stop: Q1 is not done.
4. Run the default suite and record the count. Run the slow suite once with `--basetemp=$HOME/.cache/dossier-m5-slow`, and record the count; only the three known failures may fail.
5. `git switch -c feat/dossier-m5`. If a branch `docs/dossier-m5-truth` exists (Phase 4a ran first), `git merge --no-ff docs/dossier-m5-truth` and delete it.

### Tasks (Phase 1)

- [x] **M5-1. The scip-dotnet gate and the tool re-check.**
  - Goal: D2's criteria, and every fact this plan could not run, before any code depends on them.
  - Files: this plan only ("Results (Phase 1)").
  - Interface: none. Work in `S=$(mktemp -d -p "$HOME/.cache" dossier-m5-gate-XXXX)`. Commands that run `dotnet` go through `sandbox.run` with `area=$S/area`, so the environment is the real one: `python3 -c "import sys; sys.path.insert(0,'$SKILL/scripts'); import sandbox; r=sandbox.run([...], area='$S/area', cwd='...', stage='gate', timeout=900); print(r.returncode, r.seconds, r.stdout, r.stderr)"`.
  - Steps:
    1. G1: download the `.nupkg` (D3's URL) into `$S/pkg`, check the SHA-512, unzip it. Record the file list of `tools/net10.0/any/` (count) and that `DotnetToolSettings.xml` says `Runner="dotnet"`.
    2. Environment: for each name in D5's environment list, find it in the .NET SDK or MSBuild documentation (`https://learn.microsoft.com/dotnet/core/tools/dotnet-environment-variables`, the MSBuild docs for `MSBUILDDISABLENODEREUSE`). Record which are documented, with the URL. An undocumented one is dropped from D5.
    3. G2.
    4. G3 and G8 on the tiny solution of D2. Write it by hand: `T.slnx`, `Lib/Lib.csproj`, `Lib/Thing.cs`, `App/App.csproj` (`OutputType Exe`, `ProjectReference` to Lib), `App/Program.cs`, `Directory.Packages.props`, `global.json`. Restore once with `--use-lock-file` to create the lock files, then `--locked-mode`. Record the symbols of three defs and the range form used by the occurrences (field 1 or typed ranges).
    5. Tree-sitter: send D14's node names to `ts_worker.py` (`language: "csharp"`) on a small file written to hold each one. Record any name the grammar rejects and the name it uses instead. D14's patterns must stay one or two levels deep.
    6. Semgrep: one rule per D14 shape that planning did not try (`catch (Exception $E) { ... }`, `lock ($X) { ... }`, `throw new $E(...)` with a `metavariable-regex`, a base-list regex, `$C["..."]` indexing) in `$S/r/t.yml` with a `.cs` target, run through `semgrep --test` as the worker does. Record which work.
    7. G4 to G7, G9 to G12 on `RW` and `CA`, cloned into `$S/src/` at their pins (full clones, never changed; restore and index run in copies under `$S/w/`). For G9 on `RW`, copy the clone again and index it with no restore. Record every value D2 asks for.
    8. Record whether `dotnet restore` honoured `NUGET_PACKAGES` (packages under `$S/area/cache/nuget`) and wrote nothing under the real `~/.nuget` (G12).
  - Stop condition: none for a gate fail: record it and continue with D2's fallback (a), as the author chose (Q9). Stop only if G11 or G12 fails (scip-dotnet changed tracked files or wrote outside the area), because that is a hygiene failure. If step 2 finds that an environment name breaks a restore, drop it and carry on.
  - Done-check: "Results (Phase 1)" has one line per step and one per criterion with the values seen, and the words `Gate: passed` or `Gate: failed`.
  - Commit: `docs(dossier): record the scip-dotnet gate and the M5 tool re-check in plan 011`

- [x] **M5-2. Pin and install scip-dotnet.**
  - Goal: D3 and D4.
  - Files: new `scripts/cs_scip.py` (install part only), `tests/unit/scripts/test_cs_scip.py`, `tests/integration/scripts/test_cs_scip_slow.py`; edit `scripts/tools.json`, `scripts/toolcheck.py`, `tests/unit/scripts/test_toolcheck.py`.
  - Interface: `install_dir(cache_root, version) -> Path`; `ensure_installed(cache_root, tool: dict, timeout: float, fetch=None) -> Path` (`fetch` defaults to a `urllib` download and is replaced by a fake in unit tests); `tool_dll(folder, runtime_majors) -> Path | None`.
  - Steps: (1) Unit tests: a fake fetch with the right bytes installs and writes the marker; a second call does not fetch; wrong bytes raise the checksum error and leave no folder content; a zip member `../x` is refused; `tool_dll` picks `net10.0` for majors `[8, 10]`, `net8.0` for `[8]`, and `None` for `[7]`; `tools.json` holds D3's entry and the `dotnet-package-list` note; `doctor` text says `from a hash-checked NuGet package`. (2) Implement. (3) Slow test (skipped with a reason when no SDK): a real install into `tmp_path`, then `dotnet <dll> --version` through `sandbox.run` exits 0.
  - Done-check: `uv run --with pytest --with pygments python -m pytest tests/unit/scripts/test_cs_scip.py tests/unit/scripts/test_toolcheck.py -q` passes; `DOSSIER_SLOW=1 ... tests/integration/scripts/test_cs_scip_slow.py --basetemp=$HOME/.cache/dossier-m5-slow` passes; `uv run scripts/dossier.py doctor --all` prints `scip-dotnet 0.2.16 from a hash-checked NuGet package`.
  - Commit: `feat(dossier): pin scip-dotnet as a hash-checked NuGet package`

- [x] **M5-3. The .NET SDK policy.**
  - Goal: D6, in `doctor` and preflight.
  - Files: new `scripts/cs_sdk.py`, `tests/unit/scripts/test_cs_sdk.py`; edit `scripts/stages.py`, `scripts/dossier.py` (the `doctor` path), new `tests/unit/scripts/test_cs_preflight.py` (no test file covers `stage_tools` today), `tests/integration/scripts/test_doctor_cli.py`.
  - Interface: D6's functions, plus `runtime_majors(run) -> list[int]`.
  - Steps: (1) Tests for `pick`, one per roll-forward value, using the docs' own examples: `8.0.302` with `latestFeature` accepts `8.0.303` and `8.0.402` and refuses `8.0.301`; `8.0.102` with `latestPatch` accepts `8.0.199` and refuses `8.0.200`; `7.0.200` with `latestMajor` accepts `8.0.100`; `disable` needs an exact match; `patch` is the default; no file picks the highest; comments in `global.json` parse; prerelease skipped unless allowed. `RW`'s requirement (`10.0.403`, `latestFeature`) is met by `10.0.403` and `10.0.500` and not by `10.0.114`. Preflight on a fake host with SDK `10.0.114` and a C# tree with that `global.json` marks `dotnet` `old` with the `needs` text; a Python-only tree is unchanged (asserted against today's report). (2) Implement.
  - Done-check: the named test files pass; `uv run scripts/dossier.py doctor` on a `tmp_path` repository holding `RW`'s `global.json` and one `.cs` file prints the `TOO OLD` line when run with a fake `dotnet` first on `PATH` that lists only `10.0.114`.
  - Commit: `feat(dossier): check the .NET SDK a repository's global.json asks for`

- [x] **M5-4. Environment names for .NET.**
  - Goal: D5's environment list, as confirmed by M5-1 step 2.
  - Files: edit `scripts/sandbox.py`, `tests/unit/scripts/test_sandbox.py`, `tests/integration/scripts/test_hygiene.py`.
  - Steps: (1) Tests: each confirmed name is in `ALLOWED_NAMES`; `build_env` sets the fixed values; `DOTNET_ROOT` is passed only when the parent has it; nothing else changes for a Python or JS call (assert today's environment for profile `tool` and `restricted` with a fake parent). (2) Implement. (3) `test_hygiene.py` must pass unchanged in its existing cases.
  - Done-check: `... pytest tests/unit/scripts/test_sandbox.py tests/integration/scripts/test_hygiene.py -q` passes.
  - Commit: `feat(dossier): pass the .NET settings that keep restores quiet and private`

- [x] **M5-5. Find solutions and projects.**
  - Goal: D7.
  - Files: new `scripts/cs_project.py`, `tests/unit/scripts/test_cs_project.py`.
  - Interface: `projects(tree, read) -> dict`; `source_roots(result, tree) -> list`; `frameworks_named(result) -> list[str]` (D9's Gaps names, sorted); `is_generated(path, read) -> bool` (D12).
  - Steps: tests on hand-made trees, then implement. Cases: `RW`'s shape (a `.slnx` with three projects, Web SDK, a test project with `ProjectReference` using `..\..\`, central versions, `Directory.Build.props` setting `TargetFramework`); `CA`'s shape (a `.slnx`, ten projects in `src/` and `tests/`, `Directory.Build.props` with a conditioned group that must be ignored); `LIB`'s shape (a classic `.sln`, `TargetFrameworks` with three values, a packable library and a test project); a loose project in no solution; a project nested inside another's folder (files go to the nearest); a project file with bad XML; an `.fsproj`; `InternalsVisibleTo` items; `IsPackable=false`; `PackAsTool`; a `.cs` file under no project; source roots `src` and `tests` for `RW`'s shape; `is_generated` for `.Designer.cs`, `.g.cs`, `X.G.CS`, and a header line `// <auto-generated />`.
  - Done-check: `... pytest tests/unit/scripts/test_cs_project.py -q` passes.
  - Commit: `feat(dossier): find C# solutions and projects at any depth`

- [x] **M5-6. Restore NuGet packages in any project folder.**
  - Goal: D5.
  - Files: edit `scripts/tools.json`, `scripts/restore.py`, `tests/unit/scripts/test_restore.py`, `tests/integration/scripts/test_hygiene.py`.
  - Interface: `{project}` token expansion in `restore.run`; the SDK gate before nuget plans.
  - Steps: (1) Tests: `packages.lock.json` in three folders gives three plans with `dir`; `{project}` becomes the one csproj; two project files beside one lock give the failure reason; a fake `cs_sdk.problem` skips every nuget plan with its reason and runs no command; `NETSDK1147` in the log gives the workload reason; `NU1301` still gives the registry reason with `registry_auth.nuget`; Python, npm, yarn and pnpm plans and reasons are unchanged (asserted). (2) `test_hygiene.py` used `nuget` as its disabled ecosystem since M4-4; change that case to a made-up disabled entry in a test copy of `tools.json`. (3) Implement. (4) A slow hygiene test (skipped with a reason when no SDK): a `tmp_path` repository with one library project with no packages and an empty lock file, restored through `restore.run`; packages land under `<area>/cache/nuget`; only allowlisted names reach the child (the existing environment-dump method).
  - Done-check: `... pytest tests/unit/scripts/test_restore.py tests/integration/scripts/test_hygiene.py -q` passes, with `DOSSIER_SLOW=1` too.
  - Commit: `feat(dossier): restore NuGet packages from their lock files`

- [x] **M5-7. The C# fixture repository.**
  - Goal: a small repository with known answers, so every extractor, rule and V7 pattern has a positive and a negative case.
  - Files: new `tests/fixtures/csrepo/**`, `tests/unit/scripts/test_csfixture.py`; edit `tests/conftest.py`.
  - Interface: `CSFIX`, `build_cs_repo(dest)` and fixture `cs_repo(tmp_path)`, like `build_js_repo` (share `_commit_fixture`). `line_of` and `key_line` work unchanged.
  - Content. Every line a test must find carries `// @<name>` (in `.cs`), `@* @<name> *@` (in `.razor` and `.cshtml`) or `<!-- @<name> -->` (in XML); keep each file under 40 lines. It is original code, not copied from `RW`, `CA` or `LIB`. It must not need network access to be parsed; only M5-21's scip test restores, and only `Shop.Core`, which has no packages.
    - Root: `Shop.slnx` (projects `src/Shop.Api`, `src/Shop.Core`, `src/Shop.Data`, `tests/Shop.Tests`, `tests/Shop.NUnitTests`, `build/build.csproj`); `global.json` (`10.0.403`, `latestFeature`); `Directory.Build.props` (`TargetFramework net10.0`, `Nullable`); `Directory.Packages.props` (central versions for every package named below); `NuGet.config` (nuget.org only); `Dockerfile` (`ENTRYPOINT ["dotnet", "Shop.Api.dll"]`); `.github/workflows/ci.yml` with `run: dotnet test` (`# @ci-test`); `.editorconfig`; `.config/dotnet-tools.json` naming csharpier.
    - `samples/Sample.sln` (classic format) with `samples/Sample/Sample.csproj` and a top-level `Program.cs` (`@ep-sample`). `tools/Legacy/Legacy.csproj` in no solution, with `Program.cs` holding `static void Main(string[] args)` (`@ep-main`), `args[0]` (`@io-args`), `Console.ReadLine()` (`@io-stdin`), `Environment.Exit(2)` (`@io-exit`), `new Command("sync")` (`@ep-cli`), `Process.Start("git")` (`@cc-process`).
    - `src/Shop.Api/` (Web SDK; references Core and Data; packages `Serilog.AspNetCore`, `MediatR`, `Polly`, `Hangfire.Core`, `MassTransit`, `Microsoft.Azure.Functions.Worker`, `Riok.Mapperly`, `Microsoft.FeatureManagement`, `FastEndpoints`). `Program.cs` with top-level statements (`@ep-program`): `builder.Configuration["Shop:Name"]` (`@io-config`), `Environment.GetEnvironmentVariable("SHOP_KEY")` (`@io-env`), `AddScoped<IOrderService, OrderService>()` (`@bs-di`), `AddMediatR(c => c.RegisterServicesFromAssembly(typeof(Program).Assembly))` (`@bs-scan`), `AddHostedService<Cleanup>()` (`@ep-hosted-add`), `AddHttpClient()` (`@io-outbound-add`), `opt.Conventions.Add(new PrefixConvention())` (`@bs-convention`), `opt.Filters.Add<AuditFilter>()` (`@bs-filter`), `app.MapGet("/health", () => "ok")` (`@ep-min-get`), `var api = app.MapGroup("/api")` (`@bs-group`), `api.MapPost("/orders", ...)` (`@ep-min-post`), `app.MapGet(path, h)` (`@bs-route`), `app.MapControllerRoute("default", "{controller}/{action}")` (`@bs-conventional`), `app.MapHub<ChatHub>("/chat")` (`@ep-hub`), `app.MapGrpcService<Greeter>()` (`@ep-grpc`), `app.UseExceptionHandler("/error")` (`@fail-handler`), `Log.Information("up")` (`@io-log`), `Console.WriteLine("ready")` (`@io-stdout`), `cache.Get("x")` as a near miss for routes (`@not-route`).
    - `Controllers/OrdersController.cs`: `[ApiController]`, `[Route("api/[controller]")]`, `: ControllerBase`; `[HttpGet]` (`@ep-ctl-list`, `GET /api/Orders`), `[HttpGet("{id}")]` (`@ep-ctl-get`), `[HttpPost("~/submit")]` (`@ep-ctl-abs`, `POST /submit`), `return NotFound();` (`@io-error`), `[FromHeader(Name = "X-Tenant")]` (`@io-header`), `_mediator.Send(new GetOrder(id))` (`@bs-mediator-send`), `HttpContext.RequestServices.GetRequiredService<IClock>()` (`@bs-resolve`). `Controllers/HomeController.cs`: `: Controller` with no route attributes (no rows).
    - `Services/OrderService.cs`: `_http.GetAsync(url)` (`@io-outbound`), `_db.Orders.Add(o)` (`@io-db`), `await _db.SaveChangesAsync()` (`@io-db-save`), `await _db.Database.BeginTransactionAsync()` (`@fail-tx`), `catch (Exception ex)` (`@fail-catch`), `_logger.LogWarning("x")` (`@io-log2`), `Policy.Handle<HttpRequestException>().WaitAndRetryAsync(3, _ => TimeSpan.Zero)` (`@fail-retry`), `File.ReadAllText("prices.csv")` (`@io-file-read`), `File.WriteAllText("out.txt", "")` (`@io-file-write`), `lock (_gate)` (`@cc-lock`), `await Task.WhenAll(a, b)` (`@cc-async`), `static int _count;` (`@state-static`), `private static readonly string Name = "x";` (not state), `_bus.Publish(new OrderPlaced())` (`@io-produce`).
    - `Services/Cleanup.cs`: `: BackgroundService` (`@ep-hosted`), `new PeriodicTimer(...)`. `Hubs/ChatHub.cs`: `: Hub`. `Grpc/Greeter.cs`: a plain class. `Handlers/GetOrderHandler.cs`: `: IRequestHandler<GetOrder, Order>` (`@bs-handler`). `Filters/AuditFilter.cs`: `: IAsyncActionFilter` (`@bs-filter-class`). `Conventions/PrefixConvention.cs`: `: IApplicationModelConvention` (`@bs-convention-class`). `Plugins.cs`: `Activator.CreateInstance(t)` (`@bs-reflect`), `asm.GetTypes()`. `Mapping/OrderMapper.cs`: `[Mapper]` (`@bs-generator`) on `public partial class OrderMapper` (`@bs-partial`), and `[LoggerMessage(...)] static partial void LogPlaced(...)`. `Flags.cs`: `IFeatureManager` (`@bs-flag`). `Jobs.cs`: `RecurringJob.AddOrUpdate("nightly", () => Run(), Cron.Daily)` (`@ep-cron`), `class MailConsumer : IConsumer<OrderPlaced>` (`@ep-queue`). `Functions/Ping.cs`: `[Function("Ping")]` with `[HttpTrigger(...)]` (`@ep-func`) and `[Function("Tick")]` with `[TimerTrigger("0 */5 * * * *")]` (`@ep-func-timer`). `Pages/Index.cshtml` with `@page "/"` (`@ep-razor`). `Components/Pages/Counter.razor` with `@page "/counter"` (`@ep-blazor`). `appsettings.json`, `appsettings.Development.json`, `Properties/launchSettings.json` with `ASPNETCORE_ENVIRONMENT` (`"@launch-env"` as a JSON key line for `key_line`).
    - `src/Shop.Core/` (library, packable, `PackageId Shop.Core`, `InternalsVisibleTo Include="Shop.Tests"`, **an empty `packages.lock.json`**, no packages). `Order.cs` (`public class Order` with `Id`, `Status`, `CustomerId`, `Customer`; `@model-order`), `OrderStatus.cs` (`public enum`, `@model-enum`), `IOrderService.cs`, `IClock.cs` (`public interface IClock { DateTime Now { get; } }`, `@api-interface`), `Money.cs` (`public static class Money` with two `Round` overloads, `@api-method`, and `public static string Shout(this string s)`, `@api-ext`), `Secret.cs` (`internal class Secret`, `@api-internal`, also the unused internal type for D17, `@dead-type`), `Outer.cs` (`public class Outer` with `public class Inner` `@api-nested`, `protected void P()` `@api-protected`, `private void Q()`), `Hidden.cs` (`[EditorBrowsable(EditorBrowsableState.Never)] public class Hidden`, `@api-hidden`), `Polyfill.cs` (`#if NETSTANDARD2_0` `internal sealed class CallerArgumentExpressionAttribute`, `@api-polyfill`), `Totals.A.cs` (`public partial class Totals`, `@api-partial-a`) and `Totals.B.cs` (`partial class Totals` with a public method, `@api-partial-b`), `Models/Item.cs` (`namespace Shop.Core.Models; public class Item`, `@scip-collide-a`).
    - `src/Shop.Data/` (library; references Core; packages `Microsoft.EntityFrameworkCore.Sqlite`, `Dapper`). `ShopContext.cs`: `: DbContext`, `DbSet<Order> Orders`, `DbSet<Customer> Customers` (`@model-ctx`), `options.UseSqlite(config.GetConnectionString("Shop"))` (`@io-db-connect`, `@io-connstr`). `Customer.cs`: `ICollection<Order> Orders` (`@model-customer`). `OrderConfiguration.cs`: `: IEntityTypeConfiguration<Order>`. `Migrations/20260101000000_Init.cs` with `[Migration("20260101000000_Init")]` (`@model-migration`), `Migrations/20260101000000_Init.Designer.cs` starting `// <auto-generated />` (`@bs-codegen`), `Migrations/ShopContextModelSnapshot.cs`. `OrderDto.cs`: `public record OrderDto(int Id);` (`@not-entity`). `Reports.cs`: `conn.Query<Product>("select * from products")` (`@model-dapper`, `@io-dapper`). `Models/Item.cs` (`namespace Shop.Data.Models; public class Item`, `@scip-collide-b`).
    - `tests/Shop.Tests/` (packages `Microsoft.NET.Test.Sdk`, `xunit`, `Moq`, `Microsoft.AspNetCore.Mvc.Testing`; references Api). `OrdersTests.cs`: two `[Fact]`, one `[Fact(Skip = "flaky")]` (`@test-skip`), one `[Theory]` with `[InlineData]`, `new Mock<IClock>()` (`@test-mock`), `IClassFixture<WebApplicationFactory<Program>>` (`@test-fixture`). `TestHelpers.cs` (not named `*Tests.cs`; still a test file).
    - `tests/Shop.NUnitTests/` (packages `Microsoft.NET.Test.Sdk`, `NUnit`). `MathTests.cs`: `[TestFixture]`, two `[Test]`, `[Ignore("x")]` (`@test-ignore`), `[SetUp]`.
    - `build/build.csproj` (Exe, package `Bullseye`), `build/Program.cs` with `Target("default", ...)` (`@ep-target`) and `Target("test", ...)`.
  - Steps: (1) `test_csfixture.py` asserts each marker named above appears exactly once. (2) Write the fixture. Record any marker added or changed under "Results (Phase 1)".
  - Done-check: `... pytest tests/unit/scripts/test_csfixture.py -q` passes.
  - Commit: `test(dossier): add the C# fixture repository`

- [x] **M5-8. Adapter frame.**
  - Goal: a registered adapter with its gates, so later tasks only fill steps.
  - Files: new `scripts/cs_adapter.py`, `tests/unit/scripts/test_cs_adapter.py`; edit `scripts/adapters.py`.
  - Interface: D1. `extract(ctx)` runs `cs_project.projects`, writes `cs-project`, `project-reference`, `source-root` and `cs-note` (`framework`, `no-lock`, `razor`) items, and records every tool `skipped` with `Arrives in a later task.`, except that scip-dotnet takes the trust and SDK reasons first.
  - Steps: (1) Tests on `CSFIX` with fake runs: `detect(["C#"])` gives `csharp`; `detect(["Python"])` does not; the project items match D7; the `FastEndpoints` framework note appears; a `no-lock` note for every project except `Shop.Core`; one `razor` note naming 2 files; untrusted and no-SDK runs give D11's reasons for scip-dotnet; Python and JS fixtures detect the same adapters as before (`csharp` absent). (2) Implement. (3) Run the full suite.
  - Done-check: full suite passes; `... pytest tests/unit/scripts/test_cs_adapter.py -q` passes.
  - Commit: `feat(dossier): add the C# adapter frame and project items`

### Deliverables and checks (Phase 1)

| Deliverable | Checked by |
|---|---|
| Gate and tool facts | M5-1 lines in "Results (Phase 1)" |
| scip-dotnet install | `test_cs_scip.py`, `test_cs_scip_slow.py`, `doctor --all` |
| SDK policy | `test_cs_sdk.py`, `test_doctor_cli.py` |
| Environment, restore, hygiene | `test_sandbox.py`, `test_restore.py`, `test_hygiene.py` |
| Projects | `test_cs_project.py` |
| Fixture | `test_csfixture.py` |
| Frame | `test_cs_adapter.py` |

### Cut line (Phase 1)

Nothing is cut. If the gate fails, the phase ends after M5-1 by design.

### Acceptance criteria (Phase 1)

- "Results (Phase 1)" says `Gate: passed`, or says `Gate: failed` and that the fallback (a) is in use.
- The full suite passes; the slow suite passes except the three known failures; the slow tests added here ran (not skipped).
- `test_py_adapter_slow.py` and `test_js_adapter_slow.py` pass unedited.

### Branch and release (Phase 1)

Commit each task on `feat/dossier-m5`. Do not merge or bump. Write "Results (Phase 1)" and commit: `docs(dossier): record phase 1 of M5 in plan 011`.

### Results (Phase 1)

Run 2026-11-08 by Sonnet 5.5 on branch `feat/dossier-m5` (from `main` at `7e5b7f1`). Pre-flight: tree clean; SDK 10.0.403, runtime 10.0.14, Node 26.13.0. Default suite baseline: **1993 passed, 117 skipped (58.5 s)**. Slow baseline: see the "Slow baseline" line at the end of this section.

**M5-1 (scratch folder was `~/.cache/dossier-m5-gate-*`, removed at the end of the phase).**

- Step 1 (G1): `.nupkg` is 56,673,777 bytes; SHA-512 matches the pin; `tools/net10.0/any/` has 77 files; `Runner="dotnet"`. **Pass.**
- Step 2 (environment names): all seven names are in the .NET SDK docs (`dotnet-environment-variables.md`: `DOTNET_ROOT`, `DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE`, `DOTNET_GENERATE_ASPNET_CERTIFICATE`, `DOTNET_ADD_GLOBAL_TOOLS_TO_PATH`, `DOTNET_SKIP_FIRST_TIME_EXPERIENCE`) and the MSBuild wiki (`MSBUILDDISABLENODEREUSE`). **None dropped from D5.**
- Step 3 (G2): `--version` prints `0.2.16+fadd98aebb1ede2c55801636360c002679b54112`, exit 0. **Pass.**
- Step 4 (G3, G8, tiny solution): restore `--locked-mode` through `sandbox.run` exit 0; index exit 0 in 7.2 s; `scip_read.decode` and `reduce` read it unchanged; one `ref-edge` `App/Program.cs` to `Lib/Thing.cs`. Symbols look like `scip-dotnet nuget . . Lib/Thing#Add().`; occurrences use the 4-number `range` form. **G3: pass, except the clause "every `.cs` file has at least one `def`"**: `App/Program.cs` (top-level statements) has only `local 0`, which `reduce` drops, and the index also holds generated `obj/**/*.cs` files (6 on the tiny solution). I treated this as a wording problem in G3, not a gate failure, and carried on with scip-dotnet (rule in section 2). D11 must (a) drop documents under `obj/` and `bin/`, and (b) not expect a `def` from a top-level-statements file. **G8:** no document exists for the generated regex code (as expected); the call site occurrence names `R` (role 0, col 152), but `reduce` reports `refs: 0` for `R`, so call data into partial or generated members is weak.
- Step 5 (tree-sitter): all 40 node names in D14's list are valid in the `csharp` grammar and matched on a test file. **Nothing rejected.**
- Step 6 (semgrep, 5 shapes tested): `lock ($X) { ... }`, `throw new $E(...)` with `metavariable-regex`, `class $C : $B { ... }` with a regex on `$B`, and `$C["..."]` with a regex on `$C` all work. **`catch { ... }` is an invalid C# pattern** (parse error) and a lone `catch (Exception $E) { ... }` matches nothing; **`try { ... } catch (Exception $E) { ... }` works.** Phase 2 must write the catch-all rule that way. The bare `catch` form with a `try` wrapper was not tested. Two harness facts: `semgrep --test` wants the rules and the test files in different folders with the same relative name (`r/t.yml`, `t/t.cs`), and a `// ruleid:` comment must sit on the line above the match.
- Step 7 (real repositories, clones at the pins):
  - **G4 (`RW`)**: locked restore exit 0 in 8.2 s; index exit 0 in 16.3 s; 106 of 106 tracked `.cs` files have a document (100%), 112 documents in all (6 under `obj/`); 0 `Failure:` lines. **Pass.**
  - **G5**: 103 `ref-edge`s from `tests/Conduit.IntegrationTests/` to `src/Conduit/`. **Pass.**
  - **G6**: 0 of the definitions lack the `scip-dotnet nuget . . ` prefix. **Pass.**
  - **G7** (record only): 4 global symbols are defined in more than one document, all of them EF migrations written as a partial type (`X.cs` plus `X.Designer.cs`). Symbols keep only the last namespace segment (`Sqlite/InitialSchema#`, `SqlServer/InitialSchema#`).
  - **G9**: `RW` with no restore (fresh copy): exit 0, 112 documents, 0 `Failure:` lines, 15.0 s. `CA` (no lock files, no restore): exit 0, 147 documents, 108 of 110 tracked `.cs` files covered, 167 `ref-edge`s, 17.7 s, **2 `Failure:` lines**, for `src/AppHost/AppHost.csproj` and `tests/TestAppHost/TestAppHost.csproj` (the Aspire projects). **Pass.**
  - **G10**: empty folder: exit 1, no index file. A `.csproj` with broken XML: exit 0, an index file is written with 0 documents, one `Failure:` line plus a warning "no documents were indexed". This confirms section 3 row 4: D11 must read the log and the document count.
  - **G11**: no tracked file changed in any copy; the only new paths are the ignored `obj/` folders. **Pass.**
  - **G12**: **Pass, with a caveat I caused.** Before the baseline, I ran one `dotnet restore` of the tiny solution without `sandbox.run` (real `HOME`), which touched `~/.nuget`, `~/.dotnet` and `~/.local/share/NuGet` at 14:48. I took the modification times after that and compared them after the `CA` index; they were unchanged. The sandboxed restores of `RW` (about 14:50) and the sandboxed index runs also left them unchanged.
- Step 8: restore honoured `NUGET_PACKAGES`; packages are under `<area>/cache/nuget/`.

**Gate: passed.** G1 to G6 (G3 with the clause noted above), G9, G11 and G12 pass. Fallback (a) is not in use. **For the author:** the G3 wording ("every `.cs` file has at least one `def`") cannot hold for top-level-statement files; say if you want the gate treated as failed.

**Findings for the milestone review**
- scip-dotnet indexes `obj/**/*.cs`; D11 must filter those documents.
- `CA`'s Aspire projects fail to load in scip-dotnet without a restore and the package targets; this is the expected `partial` case for Gaps.
- A harness bug of mine: first tiny-solution restore ran outside `sandbox.run`; fixed for every later command.

**Slow baseline (before any M5 code):** 4 failed, 2105 passed, 1 skipped (17 min). The three known failures plus `test_history_git.py::TestDegrading::test_a_timeout_keeps_the_complete_records_and_does_not_crash`, which passes alone in 0.3 s; it is timing-sensitive and I was running other heavy work at the time. Treat it as a flake, not a fourth known failure.

**M5-2.** Pinned 0.2.16 with the `nupkg` block; `doctor --all` prints `scip-dotnet 0.2.16 from a hash-checked NuGet package`; slow install test passed (2.4 s). `verified` is 2026-11-08. Suite after: 2006 passed, 118 skipped.

**M5-3.** `cs_sdk.py` holds the roll-forward rules (all nine values, with the docs' own examples as tests). **Deviation from the plan's signatures:** `problem(installed, reqs)` and `runtime_majors(text)` take data already read instead of a `run` callable, so they stay pure; `list_sdks(path)` and `list_runtime_majors(path)` are the thin callers of `dotnet`. `apply(report, reqs, installed)` marks the `dotnet` host entry `old` with `needs` = `{version} ({rollForward}) for {path}`. Wiring: new `toolcheck.preflight_at(top, sha, path)`, used by both `doctor` and `stage_tools` (so the checks cannot drift); a Python-only tree gets exactly today's report (tested). `format_text` therefore prints `needs 10.0.403 (latestFeature) for global.json or later`, which reads a little oddly; left as the plan specifies. Suite after: 2037 passed, 118 skipped.

**M5-4.** `sandbox.ALLOWED_NAMES` gains the six names; `build_env` sets the five fixed values for every profile and passes `DOTNET_ROOT` only when the parent has it. All seven names were confirmed in the docs (M5-1 step 2). The fixed names are set on every sandboxed call, including Python and JS ones (`build_env` knows no language); they only matter to `dotnet`. `test_hygiene.py` passes unchanged.

**M5-5.** `cs_project.py` (D7). Choices a reader might not expect: `packages.lock.json` presence is read from the raw tracked list because `gather.noise_reason` treats lock files as noise; `package_id` falls back to the assembly name for a packable project; `source_roots` skips a project whose root would be the repository root (consumers ignore empty roots); `frameworks_named` uses D9's Gaps list exactly (MediatR is supported, so it is not named). 36 tests.

**M5-6.** The `nuget` restore entry is enabled, nested, with `{project}`, `-p:NuGetAudit=false`, `--disable-build-servers`. `restore.plans` adds a `projects` list to a plan only when its command has the token; `restore.run` expands it, fails a plan whose lock file is not beside exactly one project file, skips every nuget plan with the SDK reason (one check per `run`, via new `cs_sdk.problem_for(checkout, path)` which reads the checkout's `global.json` files), and maps `NETSDK1147` to the workload reason. `test_hygiene.py` now uses a made-up disabled ecosystem. The slow hygiene test ran for real (not skipped): the restore succeeded, only allowlisted names reached the child, `obj/project.assets.json` was written inside the checkout, and `~/.nuget`, `~/.dotnet` and `~/.local/share/NuGet` kept their modification times. With no packages in the project, nothing lands under `<area>/cache/nuget`, so that part of the plan's step 4 cannot be observed by this test (M5-1 saw it work with `RW`). Suite after: 2088 passed, 119 skipped (the slow hygiene test is skipped in the default run).

**M5-7.** `tests/fixtures/csrepo/` has 66 files, all original, each under 40 lines; `conftest.py` has `CSFIX`, `build_cs_repo` and the `cs_repo` fixture; `test_csfixture.py` has 96 tests (one per marker, the 40-line rule, `line_of`/`key_line`, one commit, the file count, and "only `Shop.Core` has a lock file"). Every `.cs` file parses with the tree-sitter `csharp` grammar with no error nodes. Changes from the plan's text, for later tasks to know:
- `Customer.cs` (with `@model-customer`) is in `src/Shop.Core/`, not `Shop.Data`, because `Order` in Core uses it and Core must compile alone for M5-21.
- Markers for attribute-defined entry points (`@ep-ctl-*`, `@ep-func*`, `@bs-generator`, `@test-skip`, `@test-ignore`, `@api-*`) sit on the **attribute line or the declaration line named in the plan**, as written in the file; `@ep-ctl-list` is on the `[HttpGet]` line, `@ep-func` on the method line after `[Function("Ping")]`. Tasks that compare lines read them with `line_of`, so they do not depend on this.
- `@launch-env` has no text marker (JSON cannot hold one); tests use `key_line(..., "ASPNETCORE_ENVIRONMENT")`.
- `Program.cs` in `Shop.Api` uses `WebApplication.CreateBuilder()` without `args`, so it adds no unmarked `cli-args` hit; `@ep-program` is on line 3.
- `@bs-codegen` is on the `// <auto-generated />` header line of the Designer file; `@api-internal` and `@dead-type` share one line in `Secret.cs` (the test counts each name once).
- The fixture is not compiled anywhere except `Shop.Core` (M5-21); other projects reference types that do not exist (`Order` in `Shop.Data` code, `IBus`, and so on), which is fine for tree-sitter and semgrep.

**M5-8.** `cs_adapter.CSharpAdapter` (D1) is registered first, so `csharp` sorts before `js`. `extract` writes `cs-project`, `project-reference`, `source-root` and `cs-note` items (`framework`, `no-lock`, `razor`) into the `graph` output, as the JS adapter does with `js-note`. On the fixture: 8 C# projects, 4 project references, source roots `samples`, `src`, `tests`, `tools`; one `framework` note (`FastEndpoints`); 7 `no-lock` notes (every project but `Shop.Core`); one `razor` note with count 2. Tool status: scip-dotnet takes the trust reason, then the SDK reason (from `cs_sdk.problem`), else `Arrives in a later task.`; semgrep and tree-sitter always say `Arrives in a later task.` The `rules/csharp` folder does not exist yet (Phase 2 creates it); `rules_hash` copes with a missing folder. Not run end to end on a real build yet (Phase 2 and 3 do that). Suite after: 2199 passed, 119 skipped.

**Phase 1 acceptance.** Default suite: 2199 passed, 119 skipped. Slow suite at the end (17 min): 3 failed (only the three known ones), 2314 passed, 1 skipped; the new slow tests (`test_cs_scip_slow.py`, the NuGet hygiene test) ran, and `test_py_adapter_slow.py` and `test_js_adapter_slow.py` passed unedited. Gate: passed. Scratch folders removed. Nothing merged or bumped; branch `feat/dossier-m5` holds eight task commits plus this one.

**Left for the author:** (1) the G3 wording question above; (2) an untracked `/home/nick/dev/projects/encamp/.claude/worktrees/` folder appeared in the encamp repo at 14:46, before I ran anything; it is not mine and I left it alone.


---

## Phase 2: Text extractors, rules and V7

### Before you start (Phase 2)

Read section 2, D1, D7 to D10, D12 to D14, and "Results (Phase 1)", especially M5-1's node names and rule shapes. **Where M5-1 recorded a different node name, flag or behaviour from this plan, use what it recorded, and say so in "Results (Phase 2)".** If the gate failed, the fallback (a) is in use (Q9). Load the skills in section 2. `git switch feat/dossier-m5`. Do first any task moved here.

### Tasks (Phase 2)

- [x] **M5-9. Declarations with tree-sitter.**
  - Goal: D14's `declarations`, the base of everything else.
  - Files: new `scripts/cs_queries.py`, `tests/unit/scripts/test_cs_queries.py`, `tests/integration/scripts/test_cs_queries_slow.py`.
  - Interface: `declarations(ts, files) -> dict`; `assemble(matches_by_file) -> dict` (pure, so unit tests use hand-made matches).
  - Steps: (1) Unit tests on hand-made matches: block and file-scoped namespaces; nested types named `Outer.Inner`; attributes assigned to the right method, including two attribute lists on one method; `partial` read from modifiers; base lists split on commas outside angle brackets; interface members with no modifier; record positional parameters as properties; `global using`, `using static`, alias usings; `top_level` for a `global_statement`; `[assembly: InternalsVisibleTo("X")]`. (2) Slow test on `cs_repo`: `OrdersController` has its class and method attributes with their arguments; `Totals` appears in two files with `partial`; `Program.cs` of `Shop.Api` has `top_level`. (3) Implement.
  - Done-check: both test files pass, the second with `DOSSIER_SLOW=1`.
  - Commit: `feat(dossier): read C# declarations, usings and attributes with tree-sitter`

- [x] **M5-10. Module items, type-use graph and namespace cycles.**
  - Goal: D8 and D12.
  - Files: new `scripts/cs_graph.py`, `tests/unit/scripts/test_cs_graph.py`; edit `scripts/cs_adapter.py`, `scripts/cs_queries.py` (complexity).
  - Interface: `module_items(projects, decls, complexity, generated) -> list`; `type_uses(decls, projects, test_files) -> (import items, test edges, ambiguous count)`; `namespace_cycles(import items, decls) -> list`.
  - Steps: (1) Unit tests: a use through `using` links; a use in the same namespace links; a use from a parent namespace links; a use across a missing project reference does not link; two different `Item` types visible together give no edge and count 1; a `partial` type gives edges to both parts; a generated file has no outgoing edges and complexity 0; edges from test files go to test edges; a namespace cycle `A → B → A` inside one project gives one `cycle` item with `level: "namespace"`; two files that use each other in one namespace give none. (2) Implement, and wire into the adapter (tree-sitter status `ok` or `failed`). Add the `ambiguous-name` note.
  - Done-check: `... pytest tests/unit/scripts/test_cs_graph.py tests/unit/scripts/test_cs_adapter.py -q` passes.
  - Commit: `feat(dossier): link C# files by the types they use`

- [x] **M5-11. Entry points.**
  - Goal: D9's tree-sitter and pure-Python kinds.
  - Files: new `scripts/cs_entries.py`, `tests/unit/scripts/test_cs_entries.py`; edit `scripts/cs_adapter.py`.
  - Interface: `controller_routes(decls) -> list`; `program_entries(projects, decls) -> list`; `class_entries(decls) -> list` (hosted services, Quartz jobs, consumers); `function_entries(decls) -> list`; `page_routes(tree, read) -> list`.
  - Steps: (1) Unit tests: every controller case of D9 (prefix and template join, `~/`, leading `/`, `[controller]`, `[action]`, `[AcceptVerbs]`, `[Route]` with no verb, `[NonController]`, abstract class, a class with no attribute route); `program-main` for `Main` in `Legacy` and for top-level statements, none in test projects; the Functions trigger mapping; `@page` with and without a route in `.cshtml`, and in `.razor`. (2) Implement and wire.
  - Done-check: `... pytest tests/unit/scripts/test_cs_entries.py -q` passes.
  - Commit: `feat(dossier): find C# entry points from controllers, Main and attributes`

- [x] **M5-12. Models.**
  - Goal: D13.
  - Files: new `scripts/cs_models.py`, `tests/unit/scripts/test_cs_models.py`; edit `scripts/measured_er.py`, `tests/unit/scripts/test_measured_er.py`, `scripts/cs_adapter.py`.
  - Interface: `model_items(decls, projects) -> list`; `measured_er.family` gains `ef`.
  - Steps: (1) Tests: `Order` and `Customer` from `DbSet`, with `Customer.Orders` `many`, `Order.Customer` `ref`, `Id` `pk`; `OrderStatus` as `cs-enum`; `Product` as `dapper-row`; `OrderDto` absent; the migration and the snapshot as `migration`; an entity named only by `IEntityTypeConfiguration<T>` is found; the ER card joins `Order.Customer` to the EF `Customer` even with another `Customer` type in the tree; Python and JS relations unchanged (assert today's output). (2) Implement.
  - Done-check: `... pytest tests/unit/scripts/test_cs_models.py tests/unit/scripts/test_measured_er.py -q` passes.
  - Commit: `feat(dossier): read EF Core entities, Dapper rows and migrations`

- [x] **M5-13. Tests, complexity and static state.**
  - Goal: D14's test, complexity and state parts.
  - Files: edit `scripts/cs_queries.py`, `scripts/cs_adapter.py`, `tests/unit/scripts/test_cs_queries.py`, `tests/integration/scripts/test_cs_queries_slow.py`.
  - Interface: `tests(decls, projects, texts) -> list`; `complexity(ts, files) -> dict`; `module_state(decls) -> list`; `test_configs(tree, read) -> list`.
  - Steps: (1) Unit tests on hand-made declarations for each count and framework rule. Slow on `cs_repo`: `OrdersTests.cs` has `tests: 4`, `skips: 1`, `mocks: 1`, `fixtures: 1`, framework `xunit`, kind `integration`; `TestHelpers.cs` is a test file with `tests: 0`; `MathTests.cs` is `nunit` with `tests: 2`, `skips: 1`, `fixtures: 1`; `_count` is state and `Name` is not; `OrderService.cs` complexity above 0. (2) Implement.
  - Done-check: both test files pass, the second with `DOSSIER_SLOW=1`.
  - Commit: `feat(dossier): extract C# tests, complexity and static state with tree-sitter`

- [x] **M5-14. The C# semgrep rules.**
  - Goal: D14's rule files, each proven to fire and not to fire.
  - Files: new `rules/csharp/{entry,inputs,outputs,state,concurrency,resilience,observability}.yml`, `tests/fixtures/semgrep/csharp/*.cs`, `scripts/cs_semgrep.py`, `tests/unit/scripts/test_cs_semgrep.py`; edit `tests/unit/scripts/test_rules.py`, `scripts/cs_adapter.py`, `rules/README.md`.
  - Interface: `cs_semgrep.items(results) -> dict` as `js_semgrep.items`; `route_name(detail, snippet) -> str`. The adapter scans only non-generated `.cs` files.
  - Steps: (1) Generalise `test_rules.py`: scopes `{"python", "all", "js", "csharp"}`; `target_of` also finds `.cs`. (2) Write the rules and targets, with a `// ruleid:` and a `// ok:` for every rule. Near misses: `cache.Get("x")` and `dict.Map(x)` under `minimal-route`; `items.Add(x)` under `db-access`; `logger.ToString()` under `log`; `File.ReadAllText` under `file-write`. A line matched by two rules takes one comma-separated annotation. The `ruleid:` comment sits directly above the line where the match starts. (3) Unit tests for `items` and `route_name`. (4) Wire.
  - Done-check: `... pytest tests/unit/scripts/test_rules.py tests/unit/scripts/test_cs_semgrep.py -q` passes; `DOSSIER_SLOW=1 ... tests/integration/scripts/test_shared_layer.py -q` passes.
  - Commit: `feat(dossier): add the C# semgrep rules with tests`

- [x] **M5-15. V7 for C#.**
  - Goal: D10: blind-spot rules, wording, fixed items.
  - Files: new `rules/csharp/blindspot.yml`, `tests/fixtures/semgrep/csharp/blindspot.cs`; edit `scripts/checks_v7.py`, `scripts/checks.py`, `scripts/cs_adapter.py`, `rules/README.md`, `tests/unit/scripts/test_checks_v7.py`, `tests/unit/scripts/test_checks_gaps.py`, `tests/unit/scripts/test_rules.py`.
  - Interface: `checks_v7.cs_coverage(extract) -> list`; `checks.cs_coverage` alias, called from `checks.validate` after `js_coverage`.
  - Steps: (1) Tests: one Gaps item per (pattern, file) with D10's wording and report; every D10 id is in `BLIND_SPOTS` and in `test_rules.BLIND_SPOTS`; each `cs-note` gives its sentence; the C# stale-flags item appears only with a C# module, and the Python and JS ones are unchanged in a mixed extract; a Python-only and a JS-only extract give the same Gaps items as before (asserted). (2) Implement. Existing wording and ids do not change.
  - Done-check: `... pytest tests/unit/scripts/test_checks_v7.py tests/unit/scripts/test_checks_gaps.py tests/unit/scripts/test_rules.py -q` passes, and the slow `test_shared_layer.py` passes.
  - Commit: `feat(dossier): find the C# blind spots and record them in Gaps`

### Deliverables and checks (Phase 2)

| Deliverable | Checked by |
|---|---|
| Declarations | `test_cs_queries.py`, `test_cs_queries_slow.py` |
| Graph | `test_cs_graph.py` |
| Entry points | `test_cs_entries.py` |
| Models | `test_cs_models.py`, `test_measured_er.py` |
| Tests, complexity, state | `test_cs_queries*.py` |
| Rules and V7 | `test_rules.py`, `test_cs_semgrep.py`, `test_shared_layer.py`, `test_checks_v7.py` |

### Cut line (Phase 2)

In this order, recording each: the `function` kind; consumers other than MassTransit; Razor and Blazor routes. **Never cut** M5-14's tests or M5-15.

### Acceptance criteria (Phase 2)

- `prepare` of `cs_repo` with `--no-restore`, run once by hand, gives a `csharp` section in all eight outputs except `symbols` and `dead`.
- The full suite and slow suite pass, except the three known failures.
- `test_py_adapter_slow.py` and `test_js_adapter_slow.py` pass unedited.

### Branch and release (Phase 2)

Commit each task on `feat/dossier-m5`. Do not merge or bump. Write "Results (Phase 2)" and commit: `docs(dossier): record phase 2 of M5 in plan 011`.

### Results (Phase 2)

Run 2026-11-08 by Sonnet 5.5 on `feat/dossier-m5`. Default suite before: 2199 passed, 119 skipped. After: 2352 passed, 1 skipped (default run, before the last test-only commit). Slow suite: 3 failed (only the three known ones), 2638 passed, 1 skipped (17 min 47 s). Gate was `passed` in Phase 1, so scip-dotnet still waits for Phase 3 (its status is `skipped`, "Arrives in a later task."). Scratch folders (`~/.cache/dossier-m5-*`) removed.

**What M5-1 recorded and I used:** `catch { ... }` is written `try { ... } catch { ... }` and `try { ... } catch (Exception $E) { ... }`; both worked. Test files and rule files go in separate folders (`t/csharp`, `r/csharp`); a `// ruleid:` sits directly above the match. A C# test target is parsed as one file, so type declarations must come last (a class followed by statements is a syntax error that fails every rule in that file); `rules/README.md` now says so.

**M5-9** `cs_queries.py`. The worker returns captures with no parent links, so each query captures a whole declaration and `assemble` reads its head with small scanners (strings, brackets, comments blanked with newlines kept). Namespaces: a file-scoped one is only its first line in the tree, so I give it an end of "end of file". Extra keys beyond D14: `top_level_line`, `qualified` (dotted names), `assembly_attributes`, per-parameter `attrs`, `get` on properties, `init` on fields. Attributes drop `Attribute` and any `assembly:`/`return:` target; `line` of a declaration with attributes is the **first attribute line** (the node starts there), so `@ep-ctl-list` equals the route row's line. 23 unit tests, 7 slow tests.

**M5-10** `cs_graph.py` plus `complexity` in `cs_queries.py`. Lookup tiers (a judgement call, C# scoping): types in the file's own namespace and its parents win over `using` directives; ambiguity inside one tier gives no edge and counts once per (file, name). `type_uses` takes an extra `generated=` argument (the plan's signature had no way to know). Test files are not link targets. `module` items skip test files (D9). Wiring writes `module`, `import`, `cycle` and the `ambiguous-name` note, and sets tree-sitter `ok` or `failed`.

**M5-11** `cs_entries.py`. Judgement calls: (1) a `[Function]` with `TimerTrigger` is a `scheduled-job`, not a `function` (D9 listed it under both); other triggers use D9's text. (2) A controller method with no class `[Route]` and no template (conventional routing) gives no row. (3) `MapFallback` is the route name `ANY (fallback)`. (4) Entry rows from test files are dropped in the adapter. (5) `build.cake` is not `.cs`, so Cake scripts are not scanned; Cake's `Task("x")` in a `.cs` file inside a project that references `Cake.Frosting` is. Not done: Razor `@page` inside `.razor` with `@attribute [Route]` forms.

**M5-12** `cs_models.py`; `measured_er.family` gives `ef` for the three EF kinds, `other` for Dapper rows and `[Table]` classes, and Python/JS relations are asserted unchanged. Signature has two extra arguments: `read` (the `Entity<T>()`, `OwnsOne<T>()` and Dapper `Query<T>()` calls are in method bodies, which declarations do not hold) and `generated`. A type is one kind only (first of ef-entity, ef-owned, dapper-row, table-class). A partial entity is one item at its first part, with fields from every part. Fields of a base class declared in the repository are attached to the entity's path. `Product` (Reports.cs) is **not** declared in the fixture, so no `dapper-row` comes out of the fixture; the unit tests cover it.

**M5-13** The plan's `tests`, `module_state` and `test_configs` live in the new **`cs_tests.py`**, not `cs_queries.py` (which had reached the size limit); their tests are `test_cs_tests.py`. `tests` counts skipped methods inside `tests` (OrdersTests: tests 4, skips 1, as the plan's check says), unlike the JS counts. `static readonly` with `new()` is state only when the field's type is a collection. Also `dotnet test` joins `TEST_COMMAND` and `repo` is version 4 (tests updated). Test-project package matching is case-insensitive.

**M5-14** Seven rule files, 49 rules in all with M5-15, each with a `ruleid` and an `ok`. Judgement calls: `log` receivers must start with `log`/end with `logger` (`catalog.LogInformation` is not a log; the plan's `(?i).*log.*` matched it). `db-connect` and `entry` details are single-group regexes. `string-route` only fires for `MapGet/Post/Put/Delete/Patch/Methods`, not bare `Map` (too common: `mapper.Map(x)`). `cs_semgrep.items` takes `project_of` and `build_projects`; a `Target(...)` hit counts only in a project referencing `Bullseye` or `Cake.Frosting`. Slow test `test_cs_semgrep_slow.py` runs the real rules over the fixture and checks every I/O, entry and blind-spot marker (51 checks).

**M5-15** `checks_v7.cs_coverage`, nine new wordings, all D10 notes (including `sdk`, `ambiguous-symbol`, `unindexed`, `msbuild`, `api`, `dead`, which Phases 3 and 4 will emit). `codegen` hits for generated files are made in Python from the header (generated files are not scanned, D12). Not done: the `generator` note for a `PackageReference` whose `IncludeAssets` names `analyzers` (needs raw XML that `cs_project` does not keep); the named packages are covered.

**Phase 2 acceptance.** `prepare` of the fixture with `--no-restore --allow-missing` writes a `csharp` section in `blindspots`, `entry_points`, `graph`, `io_candidates`, `models`, `tests` (counts 26, 22, 72, 35, 5, 3) and empty ones in `symbols` and `dead`. `test_py_adapter_slow.py` and `test_js_adapter_slow.py` were not edited.

**Findings for the milestone review**
- Fixture `OrderService.cs` uses `Order` with no `using Shop.Core;`, so (correctly) no link is made; nothing to fix, but a test that expects that edge would be wrong.
- Source-generated output and `.cake` scripts are blind spots semgrep cannot read; Gaps already says so for generators.
- `Product` is missing from the fixture, so Dapper rows are only unit-tested (Phase 3 may add the class if it wants a slow check).

---

## Phase 3: scip-dotnet, the public API and the fixture test of record

### Before you start (Phase 3)

Read section 2, D2, D3, D11, D15, D17 and "Results" of Phases 1 and 2. **If the gate failed (the fallback (a) is then in use, Q9), do M5-16 in its fallback form only (D11, "Without scip-dotnet") and skip the scip-dotnet parts of M5-21, saying so.** Load the skills in section 2. `git switch feat/dossier-m5`. Confirm `dotnet --list-sdks` lists 10.0.403. Do first any task moved here.

### Tasks (Phase 3)

- [x] **M5-16. Run and read scip-dotnet.**
  - Goal: D11.
  - Files: edit `scripts/cs_scip.py`, `scripts/cs_adapter.py`, `tests/unit/scripts/test_cs_scip.py`; new `tests/integration/scripts/test_scip_cs_slow.py`.
  - Interface: `ScipDotnet(run, dll, timeout).index(checkout, target, area, n) -> (Path, log_text)`; `failure(returncode, log_text, index_path) -> str | None`; `disambiguate(index, decls) -> (index, count)`; `join(indexes) -> dict`; `finish_symbols(items, decls, generated) -> list`; `fallback_defs(decls, generated) -> list`.
  - Steps: (1) Unit tests on hand-made decoded indexes: a symbol defined in two files of a `partial` type is kept; in two different types it becomes local and is counted; a parameter def `Greet().(name)` and a type-parameter def are dropped; `public` comes from D15; two targets sharing a document keep the first; each D11 failure rule (exit 1, no index, zero documents, exit 0 with `Failure:` keeps documents and fails the tool); fallback defs have line-free symbols. (2) Slow on `cs_repo` (skipped with a reason when no SDK): restore `src/Shop.Core` locked; index `Shop.slnx` with the other projects unrestored; a `ref-edge` from `src/Shop.Api/` to `src/Shop.Core/`; the two `Item` classes are counted as ambiguous; no `.scip` is written in the checkout. (3) Implement and wire, last in the adapter's order.
  - Done-check: `... pytest tests/unit/scripts/test_cs_scip.py -q` passes; `DOSSIER_SLOW=1 ... tests/integration/scripts/test_scip_cs_slow.py -q --basetemp=$HOME/.cache/dossier-m5-slow` passes.
  - Commit: `feat(dossier): index C# with scip-dotnet and read its references`

- [x] **M5-17. Public surface and the real public API.**
  - Goal: D15.
  - Files: new `scripts/cs_api.py`, `tests/unit/scripts/test_cs_api.py`; edit `scripts/cs_adapter.py`.
  - Interface: `is_public(decl, outers, partial_parts) -> bool`; `items(projects, decls, generated) -> (symbols, notes, friends)`.
  - Steps: (1) Tests on `CSFIX`'s declarations: `Shop.Core` lists `Order`, `IClock` and `IClock.Now`, `Money.Round` as `method (2 overloads)`, `Money.Shout` as `extension method`, `Outer`, `Outer.Inner`, `Outer.P`, `Hidden` with audience `packable, hidden from editors`, `Totals` and its method (public through one part); it does not list `Secret`, `Outer.Q`, `CallerArgumentExpressionAttribute` or anything in `Shop.Api`, `Shop.Data`'s generated files, or the test projects; `Shop.Data` (packable library) has its own rows; `Shop.Api` has none; the friend line for `Shop.Tests`; a sealed class's protected member is not listed; the per-file `public` flag for each case. (2) Implement and wire. The `def` `public` flag uses `is_public`.
  - Done-check: `... pytest tests/unit/scripts/test_cs_api.py -q` passes.
  - Commit: `feat(dossier): find what each C# library offers to other assemblies`

- [x] **M5-18. Dead code for C#.**
  - Goal: D17. Cut item 4 in D20.
  - Files: edit `scripts/cs_adapter.py`, `scripts/cs_scip.py`, `tests/unit/scripts/test_cs_scip.py`.
  - Interface: `cs_scip.dead_items(symbols, decls, entries, models, blindspots, generated, test_files) -> list`.
  - Steps: tests: `Secret` is listed when its refs are 0; not listed when it has a `di-registration` hit in its file, when it is an entity, an entry point, generated, in a test file, or public; nothing is listed when scip-dotnet did not run. Implement and add the fixed Gaps note.
  - Done-check: `... pytest tests/unit/scripts/test_cs_scip.py -q` passes.
  - Commit: `feat(dossier): list C# internal types that nothing references`

- [x] **M5-19. Repository adapter: `dotnet test`.**
  - Goal: D14's CI command.
  - Files: edit `scripts/repo_adapter.py`, `tests/unit/scripts/test_repo_adapter.py`.
  - Interface: `TEST_COMMAND` gains `|\bdotnet test\b`. `RepoAdapter.version` becomes `"4"`.
  - Steps: tests for `dotnet test`, `dotnet test --no-build`, and that `dotnet build` and `dotnet run` do not match, and every existing case still matches as before. Implement.
  - Done-check: `... pytest tests/unit/scripts/test_repo_adapter.py -q` passes.
  - Commit: `feat(dossier): recognise dotnet test in CI files`

- [x] **M5-20. Prepare the adapter for an end-to-end run.**
  - Goal: the adapter writes every output, with each tool's status, in D1's order.
  - Files: edit `scripts/cs_adapter.py`, `tests/unit/scripts/test_cs_adapter.py`.
  - Steps: tests with fake tools: the order is pure Python, tree-sitter, semgrep, scip-dotnet; a tree-sitter failure leaves semgrep's items and marks graph-dependent steps empty with tree-sitter `failed`; a scip-dotnet failure leaves the fallback defs (D11); `extract` sorts items with `candidates.sort_items`. Implement whatever is still missing from earlier tasks.
  - Done-check: full suite passes.
  - Commit: `feat(dossier): run every C# step in order with its own status`

- [x] **M5-21. The fixture test of record.**
  - Goal: prove all eight outputs on `CSFIX`, end to end.
  - Files: new `tests/integration/scripts/test_cs_adapter_slow.py`.
  - Interface: runs `stages.stage_copy` and `stages.stage_extract` on `cs_repo`, with `DOSSIER_*` under `tmp_path`, `--restore yes` (only `Shop.Core` has a lock file, so only it restores, offline), then asserts on `extract/*.json`.
  - Steps: assert:
    - `entry_points`: exactly the list given by M5-7's `@ep-*` markers, by kind, name and line, built in the test; nothing at `@not-route`; no rows for `HomeController`.
    - `graph`: `cs-project` items for the six solution projects plus `Legacy` and `Sample`; `project-reference` items; `source-root` items `src`, `tests` (and none for `build`); module items with `generated: true` for the Designer file; type-use edges `OrderService.cs → Order.cs` and `ShopContext.cs → Customer.cs`; no edge between the two `Item` files; the `ambiguous-name` note.
    - `symbols`: scip `def` items, a cross-project `ref-edge`, `public` correct for `Secret` and `Order`, the `public-api` items of M5-17.
    - `io_candidates`: each `@io-*`, `@fail-*`, `@cc-*` and `@state-*` marker with its category, the appsettings files, the launch profile variable.
    - `models`: `Order`, `Customer`, `OrderStatus`, `Product`, the migration and snapshot; no `OrderDto`.
    - `tests`: four test files, the `ci-command`, the counts of M5-13.
    - `dead`: `Secret`.
    - `blindspots`: every `@bs-*` marker with its pattern.
    - Every candidate has `id` and `group`; a second run is `reused`; every tool is `ok`; `git status --porcelain` in the checkout prints nothing tracked.
    - With `trusted` false: scip-dotnet `skipped` with the fixed reason, and `entry_points` unchanged.
    - With a fake `dotnet` first on `PATH` that prints no SDK: scip-dotnet and the restore `skipped` with D6's reason; all tree-sitter and semgrep items still present.
  - Done-check: `DOSSIER_SLOW=1 ... tests/integration/scripts/test_cs_adapter_slow.py -v --basetemp=$HOME/.cache/dossier-m5-slow` passes.
  - Commit: `test(dossier): check every C# extractor on the fixture repository`

### Deliverables and checks (Phase 3)

| Deliverable | Checked by |
|---|---|
| scip-dotnet | `test_cs_scip.py`, `test_scip_cs_slow.py` |
| Public API | `test_cs_api.py` |
| Dead code | `test_cs_scip.py` |
| CI command | `test_repo_adapter.py` |
| All outputs | `test_cs_adapter_slow.py` (the fixture test of record) |

### Cut line (Phase 3)

M5-18 only (D20 cut 4). **Never cut** M5-17 or M5-21.

### Acceptance criteria (Phase 3)

- `test_cs_adapter_slow.py` passes with exactly the expected entry points and every other expected item.
- The full suite and slow suite pass, except the three known failures.
- `test_py_adapter_slow.py` and `test_js_adapter_slow.py` pass unedited.

### Branch and release (Phase 3)

Commit each task on `feat/dossier-m5`. Do not merge or bump. Write "Results (Phase 3)" and commit: `docs(dossier): record phase 3 of M5 in plan 011`.

### Results (Phase 3)

Run 2026-11-08 by Sonnet 5.5 on `feat/dossier-m5`. SDK 10.0.403. Default run (slow tests skipped): **2557 passed, 266 skipped**. Slow suite (18 min 49 s): **3 failed (only the three known ones), 2819 passed, 1 skipped**. `test_py_adapter_slow.py` and `test_js_adapter_slow.py` passed unedited. Scratch folders removed. Nothing merged or bumped.

**Order and deviations**
- M5-17 was done **before** M5-16, because the `public` flag on scip `def` items (D11) needs `cs_api.is_public`.
- M5-19 was already done in Phase 2 (under M5-13: `dotnet test` regex, `RepoAdapter.version` "4", tests); only ticked.
- `ScipDotnet.index` returns `(path, exit code, log)`, not `(path, log)`, so `failure()` can see the exit code. `soft_failure(log)` is new (the `Failure:` lines with exit 0). Zero documents is checked in the adapter after `join`.
- `disambiguate` runs on the **joined** index, so duplicates across targets are found too (plan: per index, before joining). `join(indexes, tree)` drops documents for files not tracked (`obj/`, `bin/`, as Phase 1 found).
- `disambiguate`/`finish_symbols` take `decls` as `{path: declarations}`. `cs_api.items` returns the friends too, but the adapter puts them on `cs-project` items (`friends`), as M5-24 expects.
- **A Phase 2 gap, fixed here:** D14's file-based inputs were never written. `cs_semgrep.config_inputs` now gives a `config-file` item (`cs.appsettings`) per `appsettings*.json` and an `env-var` item (`cs.launch-env`) per variable in `Properties/launchSettings.json`.
- Notes `ambiguous-symbol` and `unindexed` need a tracked path or the stage drops them; the first uses the first scip target.
- Dead code (D17): `refs` counts only references from other files, so I also keep a type off the list when its name appears elsewhere in its own file (from `idents`). A type with no definition in the index is not listed. The `dead` note is added when at least one row is listed.
- Fixture changes (CSFIX is original code), needed by M5-21 as written: `using Shop.Core;` in `OrderService.cs` and `ShopContext.cs` (the edges the plan expects need it), a `Product` class in `Reports.cs` (Dapper row), and `public Item Pick()` with both `Item` namespaces imported (`@name-ambiguous`, gives the `ambiguous-name` note). Phase 2 had flagged the first two.
- M5-21 differences from the plan text: the build project's own `Main` and the second Bullseye target are real entry points with no `@ep` marker, so they are listed as two named extras; there are **three** test files, not four; `[Function]` entries sit on the attribute line, one above their marker; `ci-command` is in the `repo` adapter's section.
- Cross-project `ref-edge` (Shop.Api to Shop.Core): with no `using`, none appeared and I first added a strict xfail; after the fixture change scip-dotnet resolves it even though Shop.Api is **not restored**, so the xfail was removed and the assertion is a plain test.

**Findings for the milestone review**
- scip-dotnet symbols carry no project or namespace prefix beyond the last segment. A top-level-statements `Program` (no `def`) in one project references `Program#` of another project (`Legacy`), giving **false `ref-edge`s** (`src/Shop.Api/Program.cs` to `tools/Legacy/Program.cs`, tests to Legacy) and inflated `refs`. Not fixed. A filter that drops edges between projects with no project-reference path would fix it; I did not add it.
- Unrestored projects index fine here (0 `Failure:` lines), but `CA`-style Aspire projects fail (Phase 1).
- A tracked generated file is still indexed by scip; its defs are dropped, its edges are kept.

---

## Phase 4: Shared layer, prompts and version

### Before you start (Phase 4)

Read section 2, D8, D15 to D19, and "Results" of Phases 1 to 3. Load the skills in section 2, plus `docs-project`, `docs-readme` and `git-release`. `git switch feat/dossier-m5`. Do first any task moved here. Block E's comparison base is `BASE_SHA=$(git merge-base main feat/dossier-m5)`.

### Tasks (Phase 4)

- [x] **M5-22. Readers: names, components and candidates text.**
  - Goal: D8's readers, D16's text section and feed.
  - Files: edit `scripts/checks.py`, `scripts/candidates.py`, `tests/unit/scripts/test_checks_v2.py`, `tests/unit/scripts/test_checks_v3.py`, `tests/unit/scripts/test_candidates_cli.py`, `tests/unit/scripts/test_candidates.py`.
  - Interface: `checks.CS_WORDS = {"var", "string", "int", "bool", "void", "async", "await", "Task", "new", "this", "null", "public", "private", "protected", "internal", "static", "class", "record", "interface", "namespace", "using"}`, skipped by V2 only when a `module` item has `language: "csharp"`. `checks_v3.Resolver` already reads `short`. `candidates.text` gains `== C# projects ==`. `FEEDS["components"]` gains `"projects"`.
  - Steps: (1) Tests: a diagram node `OrderService` resolves through `short`; V2 treats C# `short` names as module names; the section prints one line per project; a Python and a JS extract print exactly today's text; the `components` digest of a Python and a JS extract is unchanged; adding a project reference changes the C# `components` digest; moving a line does not. (2) Implement. (3) Run block E.
  - Done-check: the named test files pass; block E prints `OK`.
  - Commit: `feat(dossier): handle C# names and projects in checks and candidates`

- [x] **M5-23. Where things live, and tooling.**
  - Goal: section 3 row 30's measured cards for C#.
  - Files: new `scripts/measured_cs.py`; edit `scripts/measured.py`, `tests/unit/scripts/test_measured.py`.
  - Interface: `measured_cs.is_config(p)`: `appsettings*.json`, `launchSettings.json`, `global.json`, `NuGet.config` (any case), `Directory.Build.props`, `Directory.Build.targets`, `Directory.Packages.props`, `*.runsettings`, `.config/dotnet-tools.json`. `is_build(p)`: `*.sln`, `*.slnx`, `*.csproj`, `build.cake`. `TOOLS` additions: `csharpier` (`.csharpierrc`, `.csharpierrc.json`, `.csharpierrc.yaml`, or a `csharpier` entry in `.config/dotnet-tools.json`), `dotnet-format` (`.editorconfig` with `EnforceCodeStyleInBuild` true in a props or project file), `StyleCop` (`stylecop.json` or a `StyleCop.Analyzers` package), `.globalconfig`. Migration folders need no change: `_reading_map` already takes them from `migration` model items (`measured.py:94`), which D13 now produces for C#; a test asserts the EF `Migrations/` folder appears.
  - Steps: tests on tree lists for each; `REPO`'s kind of tree and a JS tree give today's rows (asserted). Implement.
  - Done-check: `... pytest tests/unit/scripts/test_measured.py -q` passes; block E prints `OK`.
  - Commit: `feat(dossier): find C# config, build and tooling files`

- [ ] **M5-24. The public API table for C#.**
  - Goal: D15's card changes, with V11.
  - Files: edit `scripts/measured_tables.py`, `scripts/page_audit.py`, `tests/unit/scripts/test_measured.py`, `tests/unit/scripts/test_page_audit.py`.
  - Interface: `public_api` shows C# rows unchanged in shape; appends the friend lines (from `cs-project` items and a new `friends` field on them, set in M5-17) as `<p class="muted">` lines after the table; the "No package here declares a public API" condition includes `csharp` modules. V11 counts the friend lines.
  - Steps: (1) Tests: C# rows in D15's order; the friend line; the no-API line for a C# repository with no packable project; a repository with no JS or C# has byte-identical HTML; V11 fails when a row or a friend line is missing. (2) Implement. (3) Block E.
  - Done-check: the two test files pass; block E prints `OK`.
  - Commit: `feat(dossier): show the C# public API in the contracts card`

- [ ] **M5-25. Partial badges, Gaps and staleness.**
  - Goal: section 3 rows 34 and 35, D16.
  - Files: edit `tests/unit/scripts/test_process.py`, `tests/unit/scripts/test_candidates.py`; `scripts/process.py` only if a test proves it must change (then stop and report first).
  - Steps: tests: with scip-dotnet skipped, the three cards are partial with the `Made without scip-dotnet:` reason, and the Gaps item is written once; in a mixed C# and JS build, a missing SDK badges only the C# tool's cards; `dotnet` missing gives the existing host Gaps item; a moved line in a C# file changes no digest.
  - Done-check: `... pytest tests/unit/scripts/test_process.py tests/unit/scripts/test_candidates.py -q` passes.
  - Commit: `test(dossier): cover partial badges and staleness for the C# tools`

- [ ] **M5-26. Upgrade burden (P1).**
  - Goal: D19. First to cut.
  - Files: edit `scripts/measured_upgrade.py`, `tests/unit/scripts/test_measured_upgrade.py`.
  - Steps: tests: `net10.0` gives a `.NET` row `supported until 2028-11-14` at a commit date before that; `net8.0` gives `end of life since 2026-11-10` at a later date; `netstandard2.0` gives no row; test projects give no row; the Python and Node rows are unchanged (asserted). Implement.
  - Done-check: `... pytest tests/unit/scripts/test_measured_upgrade.py -q` passes.
  - Commit: `feat(dossier): show the .NET target frameworks in upgrade burden`

- [ ] **M5-27. Test page, skeleton and mixed fixture.**
  - Goal: V11 and V12 on what is new, without a real repository.
  - Files: new `tests/tools/m5_page.py`, `tests/integration/scripts/test_mixed_cs_slow.py`; edit `tests/integration/scripts/test_check_page_slow.py`.
  - Interface: `m5_page.make(tmp) -> Path`, in the style of `m4_page.py`, with 80 `public-api` items from C#, three friend lines, 20 EF entities, C# dead rows and `.NET` upgrade rows.
  - Steps: (1) `test_mixed_cs_slow.py`: a `tmp_path` repository holding `CSFIX` under `backend/` and `JSFIX`'s `packages/web` under `frontend/`, one commit; `stage_extract` gives `csharp`, `js` and `repo` sections; ids are unique; `dossier candidates --report components` prints the C# and JS headings. (2) Slow check: `dossier check`'s V11 and V12 report 0 problems on `m5_page` at both widths and themes.
  - Done-check: `DOSSIER_SLOW=1 ... test_mixed_cs_slow.py test_check_page_slow.py -q --basetemp=$HOME/.cache/dossier-m5-slow` passes, except the known failure in `test_check_page_slow.py`.
  - Commit: `test(dossier): check the C# tables in a browser and build a mixed fixture`

- [ ] **M5-28. Prompts.**
  - Goal: tell Claude what the C# extractors give it, and what static analysis could not see.
  - Files: edit `prompts/method.md`, `prompts/reports.md`, `SKILL.md`, `tests/unit/scripts/test_prompts.py`.
  - Steps:
    - `method.md` line 213's tool list adds `scip-dotnet for C#` and says C# files are linked by the types they use. Line 384: "the Python packages or JavaScript projects" becomes "the Python packages, JavaScript projects or C# projects".
    - `reports.md`, `entry`: in C#, controller routes are written as the attributes say; add any prefix that a `route-convention`, `route-mount` or `conventional-route` finding shows, and say where it comes from (for example a convention reading `ApiPrefix` from configuration). One row per route. Hosted services, functions, consumers and build targets are entry points.
    - `reports.md`, `data` (line 141): add "in C#, EF Core entities, owned types, Dapper rows and the enums they use (the tool leaves out DTOs, records used as messages and view models; add one only when a store holds it)".
    - `reports.md`, `components`: in C#, a project is a natural boundary; one component may hold one project or a folder of one; never put two projects' files in one component unless one references the other.
    - `reports.md`, `io`: the public API table covers C# libraries; never copy it; one `io.contracts` row per library with an API.
    - `reports.md`, `interactions`: dependency injection, mediator handlers, filters and conventions decide what runs in C#, and the tools cannot follow them; when a flow passes through one, say so in the step's note and mark the arrow `inferred`.
    - `reports.md`, technologies (line 385): add the C# idioms to the examples: dependency injection lifetimes, EF Core `DbContext`, options binding, middleware order, mediator pipelines, source generators.
    - `reports.md`, "Repositories with more than one language": add C#.
    - `SKILL.md`: the `doctor` sentence says the .NET SDK a repository asks for is needed for C# references.
  - Done-check: `... pytest tests/unit/scripts/test_prompts.py -q` passes.
  - Commit: `docs(dossier): tell Claude how to use the C# findings`

- [ ] **M5-29. Git-derived cards for C#.**
  - Goal: the prompt's check that blast radius, ownership and dead-code candidates behave for `.cs`, `.csproj`, `.razor` and generated files.
  - Files: new tests in `tests/unit/scripts/test_measured_blast.py` and `tests/unit/scripts/test_measured_change.py`; code only if a test fails, then fixed with the test first.
  - Steps: tests on a hand-made extract: the blast radius of `Order.cs` holds the files with type-use edges to it and the test files whose `paths` hold it; a `.csproj` file has co-change rows and no graph rows; a `.razor` file appears in hotspots by path and in no graph; a generated file is never in `change.dead-code`; a C# module with no incoming edge is not listed as "module nothing imports" (that row is Python's). Record what was found under "Results (Phase 4)".
  - Done-check: the two test files pass.
  - Commit: `test(dossier): check blast radius and dead code rows for C# files`

- [ ] **M5-30. Docs and version.**
  - Goal: D20.
  - Files: edit `VERSION`, `README.md`, `rules/README.md`, `docs/process.md`, this plan.
  - Steps: (0) `docs/process.md`'s M5 row becomes `7 Sonnet, 2 Opus, and 1 more Sonnet if Opus finds faults (plan 011, D20)` (Q3). (1) `VERSION` to `0.10.0`. (2) `README.md`: one sentence that C# has full support and needs the .NET SDK its `global.json` asks for (8 or later otherwise). The full rewrite stays in M6. (3) `rules/README.md`: `csharp/` exists; its blind-spot ids. (4) Run the full and slow suites.
  - Done-check: `cat VERSION` prints `0.10.0`; the suites pass, except the three known failures.
  - Commit: `chore(dossier): bump to 0.10.0`

### Deliverables and checks (Phase 4)

| Deliverable | Checked by |
|---|---|
| Readers and candidates | `test_checks_v2.py`, `test_checks_v3.py`, `test_candidates*.py` |
| Reading map, tooling, upgrade | `test_measured.py`, `test_measured_upgrade.py` |
| Public API card with V11, V12 | `test_page_audit.py`, `test_check_page_slow.py` |
| Partial and staleness | `test_process.py`, `test_candidates.py` |
| Mixed | `test_mixed_cs_slow.py` |
| Prompts | `test_prompts.py` |
| Git-derived cards | `test_measured_blast.py`, `test_measured_change.py` |

### Cut line (Phase 4)

M5-26 only. **Never cut** M5-24, M5-25 or M5-27.

### Acceptance criteria (Phase 4)

- The suites pass, except the three known failures. Block E prints `OK` after each task that needs it.
- `m5_page` passes V11 and V12.
- `VERSION` is `0.10.0`.

### Branch and release (Phase 4)

Commit on `feat/dossier-m5`. Do not merge. Write "Results (Phase 4)" and commit: `docs(dossier): record phase 4 of M5 in plan 011`.

### Results (Phase 4)

(Empty.)

---

## Phase 4a: Ground truth for the primary repository

**Run this with Opus, in a fresh session (`/model opus`).** Read only this section. Do not read the rest of this plan, the spec, `rules/`, `scripts/` or any dossier: they hold notes on this repository, and your list must not depend on them. This phase needs nothing from the other phases and may run before them, but never at the same time as another session of this plan.

### Before you start (Phase 4a)

Load `git-commit`. Then:

```bash
SKILL=/home/nick/dev/projects/encamp/configs/user/claude/.claude/skills/dossier
RW_PIN=9345f18abf36b778abe2f290467ba432bf1f7e5c
SCR=$(mktemp -d -p "$HOME/.cache" dossier-m5-XXXX); echo "SCR=$SCR"
mkdir -p $SCR/src $SCR/truth
git clone -q https://github.com/realworld-apps/aspnetcore-realworld-example-app $SCR/src/rw
git -C $SCR/src/rw checkout -q $RW_PIN
```

Do not install anything, restore, build or run the repository's code, and do not build a dossier. Do not fetch its submodule. Nothing from the repository is ever committed.

### Tasks (Phase 4a)

- [ ] **T-1. Write the truth file.**
  - Goal: an independent list that the dossier is scored against.
  - Files: `$SCR/truth/rw.json`, which is never committed.
  - Format: `{"entry_points": [{"kind", "key", "where"}], "io": [{"direction": "input"|"output", "category", "key", "where"}]}`. `key` is a short string the matching row must contain, such as `GET /api/articles` or `Jwt__SigningKey`. `where` is `path:line`; for a test helper, add ` (test helper)` after it.
  - Steps:
    1. Read every tracked source, project and config file yourself (`git ls-files`). Do not sample. The images and the lock files' package lists may be skipped; say so.
    2. List every entry point, one per row. Kinds: `Main` methods and top-level `Program.cs` files, HTTP routes (each route with its **full** path, including any prefix however it is set, and the HTTP method), browser routes, hosted or background services, functions, queue consumers, scheduled jobs, CLI commands, build-script targets (for example targets defined in a build project run with `dotnet run`), container `ENTRYPOINT` or `CMD`, CI schedules, Makefile targets, shebang scripts and systemd units.
    3. List inputs. Categories: CLI arguments, environment variables (including those in Dockerfiles, compose files, Makefiles, launch settings and CI files, and the `__` form of configuration keys), config files, configuration keys read by the code, request headers, files read, stdin, network requests (grouped by route group), messages consumed, database reads (by entity), scheduled triggers.
    4. List outputs. Categories: stdout/stderr, files written, network responses (grouped by route group), error responses, outbound calls, messages produced, database writes (by entity), schema migrations, logs, metrics, exit codes.
    5. Write the file, and run `sha256sum $SCR/truth/rw.json`.
  - Done-check: the file parses with `python3 -m json.tool`, and every `where` names a line that exists and is not blank.
  - Commit: none for the file. See below.

### Deliverables and checks (Phase 4a)

| Deliverable | Checked by |
|---|---|
| Truth file | The done-check, and the hash below |

### Cut line (Phase 4a)

Nothing is cut. If the session cannot finish, keep the file and record how far it got.

### Acceptance criteria (Phase 4a)

Every tracked source, project and config file was read, and the hash and `SCR` path are recorded.

### Branch and release (Phase 4a)

On `feat/dossier-m5` if it exists, else on a branch `docs/dossier-m5-truth` from `main` that Phase 1 merges into `feat/dossier-m5`: write under "Results (Phase 4a)" the `SCR` path, the hash, the row counts, the date and what was not read. Record no content from the repository. Tick T-1 and commit: `docs(dossier): record the M5 ground truth hash in plan 011`. Do not merge into `main`.

### Results (Phase 4a)

(Empty.)

---

## Phase 5: Primary repository, Python golden and JS run

### Before you start (Phase 5)

Read section 2, section 6 and "Results" of Phases 1 to 4. Load the skills in section 2. `git switch feat/dossier-m5`. `cat VERSION` prints `0.10.0`. Do first any task moved here. **Stop if "Results (Phase 4a)" has no hash.** Set `SCR` to the path recorded there before section 6's setup, and never read the truth file except through `ground_truth.py`. Run `df -h "$HOME/.cache"`: at least 15 GB free.

### Tasks (Phase 5)

- [ ] **M5-31. The ground truth tool for C#.**
  - Goal: score the C# dossier with the M4 tool.
  - Files: `tests/tools/ground_truth.py` and its unit test, only if a test shows the tool cannot read C# rows (for example `where` values with spaces); otherwise none.
  - Steps: (1) Run the existing unit test. (2) Add one made-up C# case (a `GET /api/x` row, an `Jwt__Key` row) to the test, and fix the tool only if that case fails. (3) `sha256sum $SCR/truth/rw.json` must equal the hash in "Results (Phase 4a)".
  - Done-check: the test passes and the hash matches.
  - Commit: `test(dossier): score C# rows with the ground truth tool` (only if something changed)

- [ ] **M5-32. Run the blocks for `RW`, the Python golden and the JS run.**
  - Goal: the exit criterion on the primary repository.
  - Files: this plan only, unless a block finds a bug.
  - Steps: run, in order, blocks S, A, B, C, D, F, G, H, L, T, J, N, Q, R, K, P, JS, E, I, as section 6 gives them. **A failure is a finding:** fix the cause on this branch with a test first, in its own commit, then rerun the block. Fix the code, not the check. **Block T is the exception:** record its disagreements and carry on, because Phase 5a judges them. Never edit the truth file.
  - Done-check: every block's result is recorded under "Verification results (Phase 5)".
  - Commit: `docs(dossier): record the M5 verification on the primary repository`

### Deliverables and checks (Phase 5)

| Deliverable | Checked by |
|---|---|
| Ground truth | Hash matches "Results (Phase 4a)" |
| `RW` dossier | Blocks B to H |
| Recall and precision | Block T |
| Degraded builds | Blocks N, Q, R, K |
| Python and JS unchanged | Blocks P and JS |

### Cut line (Phase 5)

Nothing is cut. If block D cannot finish, stop and say which reports are left; the next session continues.

### Acceptance criteria (Phase 5)

- `dossier check` prints `problems: 0`; `render` prints no `error:` line; V1 to V12 pass.
- Block T has run, and `$SCR/truth/review.md` lists every disagreement.
- Blocks P and JS print `SAME`; block E prints `OK`.

### Branch and release (Phase 5)

Do not merge. Commit results: `docs(dossier): record phase 5 of M5 in plan 011`.

### Results (Phase 5)

(Empty.)

### Verification results (Phase 5)

(Empty.)

---

## Phase 5a: Rulings on the ground truth

**Run this with Opus, in a fresh session (`/model opus`).** Read this section and D20 only. You are a judge here: you change no code and no report.

### Before you start (Phase 5a)

Load `git-commit`. `git switch feat/dossier-m5`. Set `SCR` from "Results (Phase 4a)". Sonnet's disagreements are in `$SCR/truth/review.md`, the repository is `$SCR/src/rw`, and the reports are in `$SCR/home/rw/reports`.

### Tasks (Phase 5a)

- [ ] **T-2. Rule on every disagreement.**
  - Goal: a miss or an extra row is settled by reading the code, not by the session that built the dossier.
  - Files: `$SCR/truth/rulings.md`, and `$SCR/truth/rw.json` when the list was wrong.
  - Steps: for each row, read the cited code and give one verdict with a reason: `list wrong` (amend the truth file), `dossier wrong` (Phase 5b fixes it), `blind spot` (name the Gaps entry or blind-spot rule that explains it), or `no error`. For a dossier row that matches nothing, say whether it is a true entry point, input or output. Sonnet's notes are not evidence. Rerun `sha256sum` if the file changed.
  - Done-check: every row in `review.md` has a verdict.
  - Commit: none for the files. See below.

- [ ] **T-3. Check the component map.**
  - Goal: section 11's component check for a public repository (decision 34).
  - Files: `$SCR/truth/rulings.md`.
  - Steps: for every row of `components.catalog`, open its paths and confirm that they exist, that the files belong together, and that Responsibility says what the code does. Give each `ok` or `dossier wrong`, with a reason.
  - Done-check: every component has a verdict.

- [ ] **T-4. Decision 2's DI question.**
  - Goal: say whether dependency injection wiring was missed in a way a custom Roslyn tool would have caught.
  - Files: `$SCR/truth/rulings.md`.
  - Steps: list every disagreement and every `inferred` flow arrow whose cause is DI registration, resolution or scanning, or a mediator handler. For each, say whether a compiler-based tool could have resolved it from the code alone (for example a registration with a literal type pair) or not (for example assembly scanning). End with one line: `Roslyn tool: worth revisiting` or `Roslyn tool: not needed for this repository`, with the count behind it.
  - Done-check: the line exists.

### Deliverables and checks (Phase 5a)

| Deliverable | Checked by |
|---|---|
| Rulings | Every row, every component and the DI question have a verdict |

### Cut line (Phase 5a)

Nothing is cut.

### Acceptance criteria (Phase 5a)

The three done-checks pass, and any new hash is recorded.

### Branch and release (Phase 5a)

Write under "Results (Phase 5a)": the count of each verdict, every `list wrong` change with its reason and new hash, each `dossier wrong` row by path and name (no code from the repository), and the DI line. Tick T-2 to T-4 and commit: `docs(dossier): record the M5 ground truth rulings in plan 011`. Do not merge.

### Results (Phase 5a)

(Empty.)

---

## Phase 5b: Fixes after the rulings

Skip this phase if Phase 5a found no `dossier wrong` row **and** block T met its targets.

### Before you start (Phase 5b)

Read section 2, section 6 and "Results" of Phases 4a to 5a. Load the skills in section 2. `git switch feat/dossier-m5`. Set `SCR` from "Results (Phase 4a)".

### Tasks (Phase 5b)

- [ ] **M5-33. Fix each `dossier wrong` row.**
  - Goal: the exit criterion on the primary repository.
  - Files: whatever each fix needs, under the rules in section 2.
  - Steps: (1) For each row, fix the rule or the extractor, or add a Gaps entry where no rule can work, with a test first, in its own commit. A rule change moves the build key through the `rules` hash; an extractor change bumps `CSharpAdapter.version`. (2) Rebuild what changed. (3) Rerun blocks T, P, JS and E. (4) If block T shows a new disagreement, stop and ask the author to run Phase 5a again.
  - Done-check: block T meets the targets, with no unruled disagreement.
  - Commit: `docs(dossier): record the M5 fixes on the primary repository`, plus one commit per fix.

### Deliverables and checks (Phase 5b)

| Deliverable | Checked by |
|---|---|
| Recall and precision | Block T |
| Python and JS unchanged | Blocks P and JS |

### Cut line (Phase 5b)

Nothing is cut.

### Acceptance criteria (Phase 5b)

Entry points recall 100% and precision at least 95%; inputs and outputs recall at least 95%; every miss is explained by a Gaps entry or a new blind-spot rule. Record the figures before and after.

### Branch and release (Phase 5b)

Do not merge. Commit results: `docs(dossier): record phase 5b of M5 in plan 011`.

### Results (Phase 5b)

(Empty.)

---

## Phase 6: Breadth, mixed and library repositories, then merge

### Before you start (Phase 6)

Read section 2, section 6 and "Results" of Phases 1 to 5b. Load the skills in section 2. `git switch feat/dossier-m5`. **Stop if Phase 5a has no results, or if Phase 5b was needed and has none.** Do first any task moved here. Set `SCR` from "Results (Phase 4a)"; never set it up afresh.

### Tasks (Phase 6)

- [ ] **M5-34. Run block W for `CA`.**
  - Goal: the breadth checks and the real mixed C# and TypeScript build.
  - Files: this plan only, unless a block finds a bug.
  - Steps: block W. A failure is a finding, handled as in M5-32.
  - Done-check: results recorded under "Verification results (Phase 6)".
  - Commit: `docs(dossier): record the M5 verification on the breadth repository`

- [ ] **M5-35. Run blocks M, Y, X, I, E and Z.**
  - Goal: the fixture mixed build, the library's public API, card skeletons, the suites.
  - Files: this plan only.
  - Done-check: as those blocks say.
  - Commit: `docs(dossier): record the M5 mixed, library and skeleton checks`

- [ ] **M5-36. Merge and hand over.**
  - Goal: the milestone review can start.
  - Files: this plan.
  - Steps: (1) Tick and record. (2) Follow `git-workflow`: `git merge --no-ff feat/dossier-m5` into `main`, push `main`, delete the branch. (3) Tell the author the procedure below.
  - Done-check: `git log --oneline -1 main` shows the merge, and `git status --short` shows no tracked change.
  - Commit: the merge commit.

### Deliverables and checks (Phase 6)

| Deliverable | Checked by |
|---|---|
| `CA` dossier | Block W |
| Mixed fixture build | Block M |
| Public API on a real library | Block Y |
| Same skeletons | Block X |
| Merge | M5-36 done-check |

### Cut line (Phase 6)

Nothing in section 6 is cut. If `CA`'s reports cannot finish in one session, stop at a saved state, say which are left, and continue in a new session. Do not merge until they are done.

### Acceptance criteria (Phase 6, and M5)

- Blocks W, M, Y, X and Z are recorded, and `dossier check` prints `problems: 0` on `RW`, `CA` and the mixed fixture.
- `skeleton.py` exits 0 across the Python, mixed (JS and Python) and C# pages.
- The branch is merged.

### Branch and release (Phase 6)

Merge as M5-36 says. CI does not tag this skill. The next step is the author's milestone review.

### Hand-over to the milestone review

The author does this. **Needed on the machine:** the .NET SDK 10.0.403, Node 22.13 or later, `uv`, `git` and `gh`.

1. `encamp-sync pull`, so `INSTALLED` is at the merge. `git -C ~/.local/share/encamp status --short` must show no `UU` line.
2. `/dossier doctor <repo>` on a clone of `RW`. It must print `skill: <merge commit> (clean)` and `scip-dotnet 0.2.16 from a hash-checked NuGet package`.
3. Read `RW`'s and `CA`'s pages, kept under `$SCR`. Open them at full width and at 400 px, in light and dark.
4. **Spot-check the ground truth.** Pick ten rows of the truth file at random, open the cited code, and confirm it says what the row says. Then do the same for ten rows of `entry.catalog` and `io.inputs`. This needs no C# knowledge. Read Phase 5a's rulings, especially any `list wrong`, and its DI line (decision 2).
5. Read report 15 (Gaps) of `RW` and ask: does it say plainly what static analysis could not see? This is decision 2's requirement, and no check can judge it.
6. Rule on anything recorded under "Findings for the milestone review".
7. When content is judged, delete `$SCR`.

### Results (Phase 6)

(Empty.)

### Verification results (Phase 6)

(Empty.)

---

## 6. Verification

Set once per shell. The scratch folder is under `~/.cache`, not `/tmp`:

```bash
SKILL=/home/nick/dev/projects/encamp/configs/user/claude/.claude/skills/dossier
REPO=/home/nick/dev/projects/cannalerts
LIVE=/home/nick/dev/dossiers/cannalerts
FIX=$SKILL/tests/fixtures/encamp-m0
PIN=5923c09
RW_PIN=9345f18abf36b778abe2f290467ba432bf1f7e5c
CA_PIN=4739ae4cbd057ee142bc1e1bdc93c4fea8f0cac5
LIB_PIN=61dde6c9d3e1715286bd100144a9edff1ad0664c
BASE_SHA=$(git -C $SKILL merge-base main feat/dossier-m5)
SCR=${SCR:?set SCR from Results (Phase 4a)}; echo "SCR=$SCR"
export DOSSIER_HOME=$SCR/home DOSSIER_CONFIG=$SCR/cfg.json DOSSIER_CACHE=$SCR/cache PYTHONDONTWRITEBYTECODE=1
D() { uv run "$SKILL/scripts/dossier.py" "$@"; }   # a function, because zsh does not split "$D" (plan 010, Phase 4 deviation 3)
cd $SKILL
```

**Block S: setup.** Full clones, so history cards have data. Never change them.

```bash
mkdir -p $SCR/src $SCR/truth
[ -d $SCR/src/ca ] || git clone -q https://github.com/jasontaylordev/CleanArchitecture $SCR/src/ca
[ -d $SCR/src/lib ] || git clone -q https://github.com/ardalis/GuardClauses $SCR/src/lib
git -C $SCR/src/rw checkout -q $RW_PIN && git -C $SCR/src/ca checkout -q $CA_PIN && git -C $SCR/src/lib checkout -q $LIB_PIN
git -C $SCR/src/rw merge-base --is-ancestor $RW_PIN origin/master && echo rw-trusted
git -C $SCR/src/ca merge-base --is-ancestor $CA_PIN origin/main && echo ca-trusted
git -C $SCR/src/lib merge-base --is-ancestor $LIB_PIN origin/main && echo lib-trusted
git -C $REPO status --porcelain > $SCR/repo-status-before
RW=$SCR/src/rw; CA=$SCR/src/ca; LIB=$SCR/src/lib; OUT=$DOSSIER_HOME/rw; OUTC=$DOSSIER_HOME/ca
```

Expect all three `-trusted` lines. If one is missing, stop and report; do not reach for `--allow-ref`.

**Block A: `doctor`.** `D doctor $RW; echo "exit $?"`. Expect `dotnet 10.0.403` ok, `scip-dotnet 0.2.16 from a hash-checked NuGet package`, `git` and `uv` ok, a `skill:` line, exit 0.

**Block B: `prepare`.** `D prepare $RW --ref $RW_PIN --full --restore yes > $SCR/p1.json; echo "exit $?"`. Expect exit 0, mode `full`, adapters `csharp` and `repo` with every tool `ok`, restore `ok` for three nuget plans. Then:

```bash
python3 - "$OUT" <<'PY'
import json, sys, pathlib, collections
out = pathlib.Path(sys.argv[1])
for f in sorted((out / "extract").glob("*.json")):
    d = json.load(open(f))
    print(f.stem, {k: (len(v["items"]), {t: s["status"] for t, s in (v.get("tool_status") or {}).items()}) for k, v in d["adapters"].items()})
g = json.load(open(out / "extract/graph.json"))["adapters"]["csharp"]["items"]
print(collections.Counter(i["kind"] for i in g))
print([ (i["note"], i["name"]) for i in g if i["kind"] == "cs-note"])
e = json.load(open(out / "extract/entry_points.json"))["adapters"]
print(collections.Counter(i["kind"] for a in e.values() for i in a["items"]))
PY
```

Record the counts, the time per tool from `build.json`, and the `cs-note` items. Expect all eight outputs non-empty except `dead` (possibly empty), a `generator` note for `Mediator.SourceGenerator` and `Riok.Mapperly`, and a `ambiguous-symbol` count recorded (not judged).

**Block C: candidates.** For `entry`, `data`, `io`, `components`, `reading`: `D candidates $RW --report <id>` prints their sections. Record anything that looks wrong under "Findings for the milestone review".

**Block D: write the reports.** As Claude, follow `SKILL.md` `/dossier build` steps 2 to 5 with `DOSSIER` = `D`, in the order D12 of plan 009 gives. Write **every** report into `$OUT/reports/`. Then `for r in entry components interactions io data behavior change conventions ops reading; do D candidates $RW --report $r --open; done` prints nothing. **Do not read the truth file while writing.**

**Block F: render.** `D render $RW > $SCR/r1.log; echo "render exit $?"`, then `grep -E '^(error|warning|info):' $SCR/r1.log | sed -E 's/^(error|warning|info): (V[0-9]+).*/\1 \2/' | sort | uniq -c`. Expect exit 0 and no `error:` line (V1, V4, V5, V6, V8, V10). V2 and V3 may warn; each goes to Gaps. Count the rounds.

**Block G: `dossier check`.** `D check $RW; echo "exit $?"`. Expect `problems: 0` (V8, V11, V12 at 1500 and 400 px, light and dark). Run `D render $RW` once more. Read the shots of reports 04, 05, 06, 08 and 15 at both widths with the Read tool.

**Block H: counts against sources.** Plan 010's block H script, with `OUT` and these extra prints:

```bash
python3 - "$OUT" <<'PY'
import json, re, sys, pathlib
out = pathlib.Path(sys.argv[1]); h = next(out.glob("dossier-*.html")).read_text()
ex = lambda n: [i for a in json.load(open(out / f"extract/{n}.json"))["adapters"].values() for i in a["items"]]
print("entities", sum(i.get("kind") != "migration" for i in ex("models")), "fields", sum(len(i.get("fields") or []) for i in ex("models")))
def rows(cid):
    m = re.search(r'data-card="%s".*?<tbody>(.*?)</tbody>' % re.escape(cid), h, re.S)
    return m.group(1).count("<tr") if m else None
for c in ("data.entities", "entry.catalog", "io.inputs", "io.outputs", "change.dead-code", "change.upgrade-burden"): print(c, rows(c))
print("gaps blind spots", h.count("Static analysis may miss"))
print("partial badges", h.count('class="badge partial"'))
s = json.load(open(out / "summary.json")); print({k: len(v) for k, v in s.items() if isinstance(v, list)}, s["extractors"])
PY
```

Expect `data.entities` rows equal to entities, blind-spot count above 0 (DI, mediator handlers, conventions, generators, partial classes, codegen), 0 partial badges, `summary.json` listing scip-dotnet `ok`, and one `.NET 10` upgrade row.

**Block L: public API.** `RW` has no packable project, so `io.contracts` must show `No package here declares a public API.`, no `t-io-contracts-api` table, and no `public-api` item.

**Block T: recall and precision.** Check the hash of the truth file first. Then `python3 tests/tools/ground_truth.py $SCR/truth/rw.json $OUT/reports --review $SCR/truth/review.md`. Targets: entry points recall 100%, precision at least 95%; inputs and outputs recall at least 95%. Add to `review.md` every disagreement, with the cited line, and the Gaps entry or blind-spot rule you think explains it. **Do not decide them, and never edit the truth file:** Phase 5a rules. Record recall, precision, inputs and outputs recall, and the number of disagreements.

**Block J: incremental rebuild.** Never commit to `RW`'s clone; use a copy. The edit commit is on no default branch, so pass `--allow-ref` (plan 010, Phase 4 deviation 2).

```bash
J=$SCR/j; mkdir -p $J/home && cp -r $OUT $J/home/rw2 && git clone -q $RW $J/rw2 && git -C $J/rw2 checkout -q $RW_PIN
printf '\n// verification edit\n' >> $J/rw2/src/Conduit/Features/Tags/TagsController.cs
git -C $J/rw2 -c user.name=Check -c user.email=check@example.com commit -qam "verification edit"
DOSSIER_HOME=$J/home DOSSIER_CACHE=$J/cache D prepare $J/rw2 --allow-ref --restore yes > $SCR/p2.json; echo "exit $?"
python3 -c "import json;p=json.load(open('$SCR/p2.json'))['update_plan'];print(p['mode'],sorted(p['stale']),len(p['fresh']))"
```

Expect mode `incremental`; `entry`, `data`, `interactions` and `components` not stale (a comment changes no finding, and C# symbols hold no version). If the file named above does not exist at the pin, use any controller file, and say which.

**Block N: SDK removed.** A fake `dotnet` that lists no SDK, first on `PATH`:

```bash
N=$SCR/n; mkdir -p $N/bin $N/home; printf '#!/bin/sh\n[ "$1" = "--list-sdks" ] && exit 0\nexit 1\n' > $N/bin/dotnet; chmod +x $N/bin/dotnet
PATH=$N/bin:$PATH DOSSIER_HOME=$N/home DOSSIER_CACHE=$N/cache D doctor $RW; echo "doctor exit $?"
PATH=$N/bin:$PATH DOSSIER_HOME=$N/home DOSSIER_CACHE=$N/cache D prepare $RW --ref $RW_PIN --restore yes > $SCR/p3.json; echo "prepare exit $?"
PATH=$N/bin:$PATH DOSSIER_HOME=$N/home DOSSIER_CACHE=$N/cache D prepare $RW --ref $RW_PIN --restore yes --allow-missing > $SCR/p4.json; echo "allow exit $?"
cp -r $OUT/reports $N/home/rw/ ; DOSSIER_HOME=$N/home DOSSIER_CACHE=$N/cache D render $RW --allow-errors > $SCR/r3.log; echo "render exit $?"
H=$(ls $N/home/rw/dossier-*.html); grep -c 'class="badge partial"' $H
for s in "The tool dotnet was not installed" "Made without scip-dotnet" "The C# tools that need the .NET SDK did not run"; do grep -q "$s" $H && echo "found: $s" || echo "MISSING: $s"; done
```

Expect `doctor` to report `dotnet` missing or too old with the install text and exit 1; `prepare` to stop with exit 2; with `--allow-missing`, exit 0, restore `skipped` with D6's reason, scip-dotnet `skipped`, every tree-sitter and semgrep item still present (compare `entry_points` counts with block B), and the three `found:` lines (adjust the first to the exact existing host-item wording if it differs, and say so). Then without the fake `dotnet`, `prepare` in `$N`'s home must **not** reuse the `csharp` section.

**Block Q: scip-dotnet failing.** Corrupt a copy of the tool install: `Q=$SCR/q; cp -r $DOSSIER_CACHE $Q-cache; f=$(find $Q-cache -path '*scip-dotnet-0.2.16/tools/net10.0/any/scip-dotnet.dll'); : > $f; cp $f.bak 2>/dev/null; sed -i 's/.*/x/' $(dirname $(dirname $(dirname $(dirname $f))))/.installed`, then `DOSSIER_HOME=$Q/home DOSSIER_CACHE=$Q-cache D prepare $RW --ref $RW_PIN --no-restore > $SCR/pq.json`. Breaking the marker makes `ensure_installed` reinstall; to keep the failure, instead make the marker match and only empty the DLL (record which you did). Expect exit 0, scip-dotnet `failed` with a reason, fallback `def` items, no `ref-edge`, and after `render --allow-errors` with copied reports the three scip-dotnet cards badged `partial`.

**Block R: `--no-restore`.** `DOSSIER_HOME=$SCR/r/home DOSSIER_CACHE=$SCR/r/cache D prepare $RW --ref $RW_PIN --no-restore > $SCR/pr.json`. Expect exit 0, restore `skipped`, scip-dotnet `ok` or `failed` with `msbuild` notes; record documents indexed, `ref-edge` count and `cs-note` items next to block B's. This answers whether scip-dotnet still produces anything without packages.

**Block K: an untrusted ref.** As plan 010's block K, with `$RW`, `csharp` in place of `js`: the first run shows scip-dotnet `skipped` with the fixed reason, semgrep and tree-sitter `ok`, entry points present, no restore; the second (`--allow-ref --no-restore`) shows scip-dotnet no longer `skipped`.

**Block P: the Python golden.** Plan 010's block P, unchanged, with `BASE_SHA` the merge-base above. Expect `SAME`.

**Block JS: a JS run.** The same comparison for `JSFIX`: build the fixture repository once with `build_js_repo` into `$SCR/js/repo` (`python3 -c "import sys; sys.path.insert(0, 'tests'); import conftest; conftest.build_js_repo('$SCR/js/repo')"`), then `prepare --full --no-restore` it with the `BASE_SHA` worktree (side a) and with the branch (side b), and compare `extract/*.json` items per adapter as block P does (no page comparison: the fixture has no reports). Expect `SAME`. A new `csharp` section on side b is a failure.

**Block E: report 02 HTML unchanged.** Plan 010's block E, unchanged, with this `BASE_SHA`. Expect `OK`.

**Block I: the suites.** Default and `DOSSIER_SLOW=1 ... --basetemp=$HOME/.cache/dossier-m5-slow`, run alone, not beside a build. Record counts and time. Only the three known failures may fail.

**Block W: the breadth and mixed repository.**

1. Blocks A, B, C on `$CA` with `--ref $CA_PIN` and `OUTC`. Expect adapters `csharp`, `js` and `repo`. There are no `packages.lock.json` files, so expect no nuget restore and one `no-lock` note per project; expect the two `package-lock.json` files to restore with npm (or record why not). Record the time per tool and scip-dotnet's `msbuild` notes.
2. Confirm ten C# projects, the Aspire app host as `program-main` plus the `Aspire.Hosting.AppHost` framework note, the reflection-discovered endpoint groups reaching Gaps through `reflection` and `string-route` hits, and MediatR handlers through `mediator-handler`.
3. Confirm the public API table lists the packable libraries (`Domain`, `Application`, `Infrastructure`, `Shared`, unless their project files say otherwise; record which).
4. Block D on `$CA`, all reports. Rows from both languages appear in `entry.catalog`, `data.entities` and `interactions.graph`.
5. Blocks F, G, H. Read the shots of reports 04, 05, 06 and 07 at both widths.

No ground truth is built for `CA`. A hand count of its endpoint groups' routes against `entry.catalog` is recorded, because it is cheap.

**Block M: the fixture mixed build.** `CSFIX` under `backend/` and `JSFIX`'s `packages/web` under `frontend/`, as M5-27 builds it, but through `prepare --no-restore`, reports written as in block D (the repository is small), `render` and `dossier check`: `problems: 0`, rows from both languages, Node and .NET tools named on the process card.

**Block Y: public API on a real library.** No restore and no SDK needed. Only `prepare` runs.

```bash
D prepare $LIB --ref $LIB_PIN --full --no-restore > $SCR/pl.json; echo "exit $?"
```

Expect exit 0. Then in the `public-api` items of `extract/symbols.json`:

- every item has package `Ardalis.GuardClauses`, subpath `Ardalis.GuardClauses`, audience starting `packable`;
- it holds `Guard`, `Guard.Against`, `IGuardClause`, `NotFoundException`, `ValidatedNotNullAttribute`, and `GuardClauseExtensions.Null` as an extension method with overloads, which proves partial classes across files;
- it does not hold `CallerArgumentExpressionAttribute`, anything in namespace `JetBrains.Annotations`, the private `Guard` constructor, or anything under `test/`;
- the obsolete members of `GuardAgainstExpressionExtensionsDeprecated.cs` have audience ending `, obsolete`.

A failure is a finding. Record the item count. `LIB` is not read further, and its output is not committed.

**Block X: same skeleton.** `python3 tests/tools/skeleton.py $OUT/dossier-*.html $OUTC/dossier-*.html $SCR/m/home/*/dossier-*.html $SCR/p/b/cannalerts/dossier-*.html; echo "exit $?"`. Expect exit 0. (Block P's side b must be kept until this block; delete it after.)

**Block Z: the end.** `diff <(git -C $REPO status --porcelain) $SCR/repo-status-before` prints nothing. `git -C $SKILL worktree list` shows one worktree. `git -C $RW status --porcelain`, `git -C $CA status --porcelain` and `git -C $LIB status --porcelain` print nothing. Keep `$SCR` for the author's review; say its path.

**Order.** Phase 5: S, A, B, C, D, F, G, H, L, T, J, N, Q, R, K, P, JS, E, I. Phase 6: W, M, Y, X, I, E, Z. Clear `$SCR/j`, `$SCR/n`, `$SCR/q` and `$SCR/r` between blocks if `df` shows under 5 GB free.

**Recording results.** Under each phase's "Verification results" write the date, branch and model. For each block, the key output lines, the render rounds, tool times, the page size, what was cut and why, and a "Deviations" list. For block T, every miss with its Gaps entry or blind-spot rule. Findings about rule precision go under "Findings for the milestone review", not into fixes, unless they are a crash, a V1 failure, or a miss of block T's targets.

---

## 7. Risks and open questions

### Risks (most important first)

1. **The SDK is not installed, and its version matters.** This machine has the .NET 10.0.14 runtime and no SDK. `RW` and `CA` need SDK 10.0.403 or a later 10.0 feature band. NuGet's docs warn that a different SDK can change implicit packages and fail a locked restore. Q1 installs it from the same Microsoft apt feed as the runtime, so there is one `dotnet` in `/usr/share/dotnet`. A later apt upgrade to 10.0.404 or 10.0.5xx is fine for `global.json` (`latestFeature`) but could change implicit packages; a locked-restore failure after an upgrade is recorded, not worked around. Phase 1 step 3 checks the version.
2. **scip-dotnet has not been run.** Everything about it comes from its source at `v0.2.16` and its issue tracker. The gate (D2) goes first for this reason, and later phases trust its results over this text. G4's time and G9's behaviour without packages are the least certain.
3. **scip-dotnet runs third-party code in-process.** Its design-time build imports the repository's and the packages' MSBuild targets and runs source generators. Decision 5 accepts host execution for restores; Q2 asks the author to accept it for indexing `RW` and `CA` too.
4. **Type-use edges are an approximation.** They miss extension methods, `var` uses, reflection and DI, and they are what blast radius, components and cycles rest on when scip-dotnet does not run. Gaps says so in a fixed item, and block B compares them with SCIP's `ref-edge`s only informally. A miss of `RW`'s flows would show in V3 warnings, not in block T.
5. **Entry-point recall depends on route prefixes.** `RW`'s `/api` prefix comes from an MVC convention reading configuration. No rule can compute it; the `route-convention` blind spot and the prompt make Claude write it. If Claude does not, block T fails on every route, and Phase 5b fixes the prompt, not a rule.
6. **The `CA` breadth build gets no NuGet restore** (no lock files), so scip-dotnet runs without packages there, and `partial` badges or `msbuild` notes are likely. That is the spec working (S7 asks whether it should). It also means MediatR's licence never comes into play for `CA`.
7. **Namespace collapse in scip-dotnet symbols** (issue #85) can merge two types; D11 drops their references and counts them. On a large repository with many `Models` namespaces this could drop many references. G7 measures it on `RW`.
8. **The C# entity filter may be too narrow.** A domain model persisted through a repository pattern without EF (`[Table]` missing, no Dapper) gives no entities; Claude can add rows, but the tool will not list them (S4).
9. **Nine sessions where `process.md` says one** (Q3). Phase 6 needs Node and npm again for `CA`'s two front ends.
10. **The C# figures are provisional** (decisions 33 and 34). Both models are Claude, the author is new to C#, and `RW` is a small, clean example; corrections come from work codebases (`post-v1.md`).
11. **Baseline drift.** The working tree at `dbf9d6b` held uncommitted UI changes. If they are committed before Phase 1, the suite counts move; Phase 1 records the new baseline.
12. **Slow-suite `/tmp` exhaustion** repeated in M4. Every slow run here uses `--basetemp` under `~/.cache`.

### What I could not verify (open facts)

- **O1.** Whether `MSBUILDDISABLENODEREUSE`, `DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE`, `DOTNET_GENERATE_ASPNET_CERTIFICATE`, `DOTNET_ADD_GLOBAL_TOOLS_TO_PATH` and `DOTNET_SKIP_FIRST_TIME_EXPERIENCE` are documented and honoured by SDK 10. M5-1 step 2.
- **O2.** Whether scip-dotnet's `MSBuildWorkspace` loads projects at all when no restore ran (G9).
- **O3.** Whether every tree-sitter node name in D14 exists in the `csharp` grammar of `tree-sitter-language-pack` 1.22.1 (planning confirmed eight). M5-1 step 5.
- **O4. Answered after review:** `apt-cache policy dotnet-sdk-10.0` on this machine shows the Microsoft feed (Debian 13) carries every band from 10.0.300 to 10.0.403, with 10.0.403-1 as the candidate. So apt is enough, and the install script is not needed.
- **O5.** The licence terms of MediatR 14 for an analysis-only restore: one blog and the vendor's announcement say versions from 13 on are dual-licensed (RPL-1.5 or commercial, free under a revenue threshold), and that a missing key logs a warning at run time. I did not read the licence itself. Moot for `CA` under the default of Q4 (no restore).
- **O6.** How long scip-dotnet takes on `RW` and `CA` (G4, G9).
- **O7.** Whether `@page` routes in `.razor` files are always string literals (they are in the docs' examples).

**What I read.** In full: the spec, `process.md`, `post-v1.md`, plan 010 (all of it), `adapters.py`, `js_adapter.py`, `js_tools.py`, `js_semgrep.py`, `scip_tool.py`, `scip_read.py`, `restore.py`, `sandbox.py`, `toolcheck.py`, `shared_tools.py`, `checks_v7.py`, `measured_upgrade.py`, `tools.json`, `rules/all/blindspot.yml`; scip-dotnet's `Program.cs`, `IndexCommandHandler.cs`, `IndexCommandOptions.cs`, `ScipProjectIndexer.cs`, `ScipDotnet.csproj`, `global.json`, `readme.md`; `RW`'s project, props, solution, Docker, Make, NuGet and tool-manifest files and `Program.cs` (first 80 lines). In part: `deps.py` (its C# adapter), `gather.py` (language, noise, test and env patterns), `stages.py` (first 160 lines), `candidates.py` (categories, home cards, feeds), `repo_adapter.py` (kinds, `TEST_COMMAND`, `extract`), `measured.py` (config, build and tooling helpers), `config.py` (timeouts), `checks.py` (`validate`), `process.py` (partial cards), `test_rules.py` (first 60 lines), `ScipDocumentIndexer.cs` (symbol and occurrence code), `ScipSymbol.cs`; `CA`'s tree, props, one endpoint file and the endpoint discovery file; `LIB`'s tree, project file, polyfills and `Guard.cs`. Searched only: `prompts/method.md`, `prompts/reports.md`, the C# cases in `test_deps.py`, `test_toolcheck.py`, `test_sandbox.py`, `test_measured_upgrade.py`. **Not read:** plan 007 beyond what plan 010 quotes, `render.py`, `measured_tables.py`, `page_audit.py`, `components.py`, `graphs.py`, `incremental.py`, `js_project.py`, `py_adapter.py` beyond its rules line, `assets/`, `LIVE`.

### Questions for the author

All answered by the author on 2026-11-08.

- **Q1. Install the .NET SDK 10.0.403 before Phase 1?** **Answer: yes, through `encamp`.** `scripts/lib/install_app.sh` keeps `install_dotnet_runtime` and gains `install_dotnet_sdk`, which installs `dotnet-sdk-10.0` from Microsoft's apt feed (apt upgrades it to the newest 10.0 SDK, 10.0.403 today); both share `add_microsoft_apt_repo`. `headless-workstation.sh` runs both, the SDK step with no skip check, because the runtime already puts `dotnet` in `PATH`. The author runs `sudo apt-get update && sudo apt-get install -y dotnet-sdk-10.0` once on this machine.
- **Q2. Accept decision 5's risk for these three repositories?** The author asked for more detail; it is in the reply to the review and summarised here. Restoring `RW` downloads its locked NuGet packages and evaluates its MSBuild files; scip-dotnet then loads `RW` and `CA` the way an IDE does, which imports build targets shipped inside packages and runs source generators (Mediator, Mapperly in `RW`; the SDK's own in both) inside the scip-dotnet process, with your user rights and the scrubbed environment of 5.4. Nothing is compiled to a program and nothing of theirs is started, and `CA` gets no NuGet restore (no lock files), so only its own MSBuild files and the SDK's generators run. `CA`'s two front ends get `npm ci --ignore-scripts`. `LIB` is only read. **Answer: accepted** (2026-11-08, after reading the detail).
- **Q3. Nine sessions** (seven Sonnet, two Opus, one conditional) where `process.md` says one? **Answer: yes** ("a little excessive, but fine"). `process.md` is updated in Phase 4 (M5-30) to "7 Sonnet, 2 Opus, and 1 more Sonnet if Opus finds faults (plan 011, D20)".
- **Q4. No lock file, no restore?** **Answer: yes** (the spec's rule; S7 stays as written).
- **Q5. Not running `dotnet package list`?** **Answer: default** (not run; S6).
- **Q6. The C# entity filter** (D13, S4)? **Answer: default.** The author will correct it from work codebases. This answer also set the rule in section 2, "Judgement calls about C# and TS".
- **Q7. Ground truth by a separate Opus session** (Phase 4a)? **Answer: yes.**
- **Q8. Dead code for C#** (D17, S10)? **Answer: yes, listed as "dead code without references"**; the author decides later whether to remove anything. D17 uses that wording.
- **Q9. If the gate fails**, fallback (a) or a Roslyn tool (b)? **Answer: whichever is better, with no reliance on a remote API.** Neither option needs a remote API at run time: scip-dotnet is itself built on Roslyn (Microsoft's C# compiler, used as a local library) and runs offline after a one-time, hash-checked download; a custom Roslyn tool would be a C# program dossier would have to write, pin and maintain, and it would load the same build files. (a) is better for M5: it stays inside decision 2, and the type-use graph and every tree-sitter and semgrep output work without scip-dotnet anyway. **Chosen: (a).** A Roslyn tool is revisited only if Phase 5a's DI line says so (decision 2).

---

## 8. Spec issues

Each has proposed wording for the author to rule on. The plan follows the proposals marked as defaults in section 7, and does not work around the others.

- **S1. Per-file public surface for C#** (6.1 states Python and TS only). Proposed addition to 6.1's `symbols.json` row: "For C# a name is public when it is declared `public`, `protected` or `protected internal` and every type that contains it is too; interface and enum members take their type's accessibility; a type without a modifier is internal; a `partial` type is public when any part says so."
- **S2. The C# real public API** (decision 42). Proposed: "For C#, the **real public API** is what another assembly can use: the public types of each packable library project (not a test, web, worker or executable project, and not `IsPackable=false`), and their public members, plus protected members of types that can be inherited. `internal` names, generated files and test projects are left out. `[EditorBrowsable(Never)]` and `[Obsolete]` are shown in the Audience column. `InternalsVisibleTo` is listed under the table. It is read from the code and project files; no build is needed." Section 4's `io.contracts` row: "For TS, JS and C#, followed by a measured table ...", with "Import path" holding the namespace for C#.
- **S3. C# entry-point kinds** (6.1 names only `Main`/`Program.cs`). Proposed: add to 6.1's list "for C#: `Main` methods and top-level `Program.cs`, controller and minimal-API routes, Razor Pages and Blazor `@page` routes, hosted and background services, Azure Functions, gRPC services, SignalR hubs, message consumers, scheduled jobs, CLI commands, and build-script targets (Bullseye, Cake)". Section 4's `entry.catalog` source text likewise. Recall is measured over these kinds (decision 23).
- **S4. Which C# types are entities** (section 4, `data.entities`). Proposed: "For C#, an entity is an EF Core entity or owned type (from `DbSet<T>`, `Entity<T>()` or `IEntityTypeConfiguration<T>`), a Dapper row type, a `[Table]` class, or an enum one of them uses. DTOs, records used as messages, view models and options classes are left out." To be corrected from work codebases, like decision 43.
- **S5. DI for C#** (decision 35's rule). Proposed: "DI in C# is a blind-spot pattern, so hits reach Gaps: registrations, resolutions and assembly scanning are three patterns." And 6.2's semgrep row: "DI registration (a blind-spot pattern in C# and TS; Python has no common container)".
- **S6. `dotnet list package`** (6.2). Both spellings exist: `dotnet package list` from SDK 10, `dotnet list package` before. Its output duplicates `packages.lock.json`, which `deps.py` already reads, and report 02 must not change. Proposed: remove the row, and say in the C# row that packages come from `packages.lock.json` and project files.
- **S7. Restore without a NuGet lock file** (5.1 step 3). NuGet resolves the lowest matching version, so exact central versions are close to a lock, but transitive versions can still move when packages are published. Proposed: keep "lockfile only" (the default); the alternative wording is "or, for NuGet, when every package version is exact and set centrally".
- **S8. How scip-dotnet is installed** (6.2: "`dotnet tool`"). Proposed: "Downloaded once from nuget.org at a pinned version, checked against a SHA-512 shipped with the skill, and run with `dotnet`; it is always told not to restore by itself." 5.4 rule 7 then holds without a NuGet feed at run time.
- **S9. The C# blind-spot list** (6.4). Proposed: "**C#:** dependency injection registrations, resolutions and assembly scanning; reflection; routes changed by conventions, conventional routes and MVC filters; mediator handlers; source generators; `partial` types; Razor and Blazor files (not indexed)."
- **S10. `change.dead-code` for C#** (section 4 names vulture and knip). Proposed source text: "... knip including its unused files (JS and TS), internal types nothing references (C#, only when scip-dotnet ran) ...".
- **S11. 5.4 rule 1's allowlist** gains `DOTNET_ROOT` and the .NET quiet-mode variables M5-1 confirms.
- **S12. Cycles for C#** (section 4, `interactions.violations`: "Cycles from the graph"). Files that use each other are normal in C#. Proposed: "For C#, cycles are between namespaces inside one project."
- **S13. Preflight for C#** (6.2: "the .NET SDK for any C# repo"). Proposed: "the .NET SDK, at the version the repository's `global.json` asks for when it has one (8 or later otherwise)".
- **S14. Graph edges for C#** (6.1: "edges (import, call where SCIP gives it)"). C# imports namespaces, not files. Proposed: "For C#, file edges are type uses (a file names a type another file declares), resolved through namespaces and project references; project references are graph items too."
- **S15. `process.md`** lists M5 as one session (Q3).

---

## Sources

Checked on 2026-11-08.

| What | Used for | Source |
|---|---|---|
| scip-dotnet versions and dates (0.2.16 on 2026-10-21; 0.2.14 on 2026-05-05), package type `DotnetTool`, size, SHA-512 | D3, D4, G1 | https://api.nuget.org/v3-flatcontainer/scip-dotnet/index.json, https://api.nuget.org/v3/registration5-gz-semver2/scip-dotnet/index.json and its catalog entry; hash matched on the downloaded file |
| Package layout: `tools/net8.0`, `net9.0`, `net10.0`; `DotnetToolSettings.xml` `Runner="dotnet"`; runtimeconfig `Microsoft.NETCore.App 10.0.0`; nuspec commit `fadd98a`, no dependencies | D3 | the `.nupkg`, unzipped with Python's `zipfile` in `~/.cache/dossier-m5-plan/nupkg` |
| scip-dotnet options (`--output`, `--working-directory`, `--include`, `--exclude`, `--allow-global-symbol-definitions`, `--dotnet-restore-timeout`, `--skip-dotnet-restore`, `--nuget-config-path`) | D11 | `ScipDotnet/Program.cs` at `v0.2.16`, https://github.com/sourcegraph/scip-dotnet |
| It runs `dotnet restore` unless skipped; picks the project matching the runtime's `net<N>.0`; indexes `project.Documents`; returns 0 on MSBuild failure, 1 when no project file is found; writes an index with no documents when nothing loads | rows 3 to 5, D11 | `ScipProjectIndexer.cs` and `IndexCommandHandler.cs` at `v0.2.16` |
| Symbols use package `. .` for in-source names unless `--allow-global-symbol-definitions`; a namespace's owner is the package, so only the last segment is kept; parameters are definitions | row 6, D11 | `ScipDocumentIndexer.cs`, `ScipSymbol.cs`, snapshot `snapshots/output-net10.0/syntax-slnx/Main/Program.cs` at `v0.2.16`; issue #85 |
| `.slnx` support merged 2026-05-27 (#112); `SymbolInformation.kind` merged 2026-11-02, after 0.2.16 (#124); Razor and Blazor indexing is an open PR (#117) | rows 2, 36 | https://github.com/sourcegraph/scip-dotnet/pulls?state=all, via `gh api` |
| Releases and tags (GitHub release for 0.2.14; tags 0.2.15 and 0.2.16) | D4 | `gh api repos/sourcegraph/scip-dotnet/releases` and `/tags` |
| `Project.Documents` excludes source-generated documents; Roslyn's compilation tracker runs generators | row 5 | https://source.dot.net/Microsoft.CodeAnalysis.Workspaces/Workspace/Solution/Project.cs.html and `SolutionCompilationState.RegularCompilationTracker_Generators.cs.html` (found by search; the generator part is an inference from the tracker code) |
| `dotnet package list` is the .NET 10 noun-first form; SDK 9 and earlier use `dotnet list package`; options `--include-transitive`, `--format json`, `--no-restore`; .NET 10 restores automatically | row 8, S6 | https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-package-list |
| `dotnet restore` options (`--locked-mode`, `--configfile`, `--disable-build-servers`, `--force-evaluate`, `-v`); `.slnx` accepted; audit runs in restore and in .NET 10 audits transitive packages; `NuGetAudit` property | D5 | https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-restore |
| Lock files: `RestorePackagesWithLockFile`, `packages.lock.json` at the project root, locked mode fails on a mismatch, a different SDK can change implicit packages; lowest-version resolution | D5, D6, S7 | https://learn.microsoft.com/en-us/nuget/consume-packages/package-references-in-project-files |
| `global.json` roll-forward table, search from the working directory upward, comments allowed, `latestFeature` examples | D6 | https://learn.microsoft.com/en-us/dotnet/core/tools/global-json |
| SDK 10.0.403 released 2026-10-25 with runtime 10.0.14; .NET 10 end of support 2028-11-14 | row 9, Q1 | https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json |
| Debian 13 packages from the Microsoft feed (`dotnet-sdk-10.0`, x64 and Arm64) | Q1 | https://learn.microsoft.com/en-us/dotnet/core/install/linux-debian |
| The install script and its `--version` option | Q1 | https://learn.microsoft.com/dotnet/core/tools/dotnet-install-script (search result summary) |
| Local tool manifests hold versions only; `dotnet tool restore` | D3 rejected | https://learn.microsoft.com/en-us/dotnet/core/tools/local-tools-how-to-use |
| Semgrep C# is generally available | D4 | https://docs.semgrep.dev/supported-languages |
| Semgrep C# key `csharp`, extension `.cs`, maturity `ga` | D4, row 36 | https://raw.githubusercontent.com/semgrep/semgrep-interfaces/main/lang.json |
| Semgrep C# patterns with generics and attributes, and `// ruleid:` in `.cs` tests | D4, D14 | run offline with the cached `semgrep_worker.py` (semgrep 1.181.0) in `~/.cache/dossier-m5-plan/sg` |
| tree-sitter grammar `csharp` and eight node names | D4, D14 | run offline with the cached `ts_worker.py` (tree-sitter-language-pack 1.22.1) in `~/.cache/dossier-m5-plan/tsq` |
| Minimal API `Map{Verb}`, `MapMethods`, `MapGroup` prefixes and nesting, handler forms | D9 | https://learn.microsoft.com/en-us/aspnet/core/fundamentals/minimal-apis/route-handlers |
| MediatR 13 and later dual-licensed (RPL-1.5 or commercial, free under a revenue threshold); a licence key read from configuration | O5 | https://www.jimmybogard.com/automapper-and-mediatr-commercial-editions-launch-today/ and search summaries; the licence text itself was not read |
| `RW`, `CA`, `LIB`: exist, not archived, MIT, pins resolve and equal the default-branch tips (`compare` status `identical`) | Paths | `gh api repos/<owner>/<repo>` and `/compare/<pin>...<branch>` |
| `RW`: `global.json` 10.0.403 `latestFeature`; `Conduit.slnx` with three projects; central versions; `RestorePackagesWithLockFile`; three lock files; `TreatWarningsAsErrors`; Mediator source generator and Mapperly; a submodule `realworld`; Dockerfile `ENTRYPOINT`; prefix set by `ApiRoutePrefixConvention` from `ApiPrefix` | rows 9 to 12, 21, 37 | shallow clone at the pin |
| `CA`: `.slnx`, ten projects, no lock files, MediatR 14.2.0, Aspire 13.6, Angular and React front ends with `package-lock.json`, endpoint groups found by reflection, `ArtifactsPath` | rows 11, 31, block W | shallow clone at the pin |
| `LIB`: classic `.sln`, `TargetFrameworks net8.0;netstandard2.1;netstandard2.0`, `PackageId Ardalis.GuardClauses`, internal polyfills, partial extension classes, no lock file | D15, block Y | shallow clone at the pin |

Measured on this machine: .NET host and runtime 10.0.14 with no SDK; Node 26.13.0 (fnm); `semgrep` not on `PATH` (it runs through `uv`); default suite 1993 passed, 117 skipped at `dbf9d6b` with a dirty working tree.
