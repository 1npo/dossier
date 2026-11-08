# Plan 010: milestone M4 (the TypeScript, JavaScript and React adapter, its rules and its blind-spot list)

Status: written by Opus on 2026-11-05 from `docs/prompts/plan-m4.md`. **Reviewed by the author on 2026-11-05:** section 7 is answered and section 8 is ruled, and the spec, `process.md` and `post-v1.md` carry the rulings. **On hold:** Phase 1 starts only after the author's second acceptance test.

**If you were started for Phase 3a, stop reading here.** Find the heading `## Phase 3a` and read only that section. It must stay independent of everything else in this file.

Written from: `plans/004-v1-spec.md`, `docs/process.md`, plans 007, 008 and 009 (including results, deviations and findings), and the code at commit `3a68c36` (version 0.8.0). The pinned test repositories were read from shallow clones in a scratch folder. Nothing was installed or built. Writing this plan changed no other file. Section 7 says what I read and what I did not.

Paths used below:

- `SKILL` = `/home/nick/dev/projects/encamp/configs/user/claude/.claude/skills/dossier`, the development copy.
- `INSTALLED` = `/home/nick/.local/share/encamp/configs/user/claude/.claude/skills/dossier`. `~/.claude/skills/dossier` points at it. Never edit it, and never read it as the source of truth.
- `LIVE` = `/home/nick/dev/dossiers/cannalerts`, the author's dossier. Only section 6 touches it, and only to copy it.
- `REPO` = `/home/nick/dev/projects/cannalerts`, pinned at `5923c09`. Read-only. It is the **Python golden** repository.
- `FIX` = `SKILL/tests/fixtures/encamp-m0`, frozen and git-ignored. Never written; tests copy it.
- `PYFIX` = `SKILL/tests/fixtures/pyrepo/`.
- `JSFIX` = `SKILL/tests/fixtures/jsrepo/`, the new JS fixture repository (M4-5). It is committed as plain files and becomes a git repository only in a temporary folder at test time.
- `RW` = `gothinkster/node-express-realworld-example-app` at `30b68e1e881462b2f4164ea09ab4c4f5699c7b0b`, the **primary** repository. It has no LICENSE file, so nothing from it is ever committed here.
- `BP` = `alan2207/bulletproof-react` at `9506629ed003a561c6627735480cce4994244bb4` (MIT), the **React** repository.
- `LIB` = `pmndrs/zustand` at `382d29c485e67018c06e75ec7235130d0968522c` (MIT), the **library** repository. Block Y uses it for the public API check only. It gets no dossier and no ground truth.
- Tests run from `SKILL`: `uv run --with pytest --with pygments python -m pytest tests -q`. **Baseline: 1426 passed, 66 skipped** (2026-11-05, `3a68c36`, 55 s).
- Slow tests need `DOSSIER_SLOW=1`. They need the network and the real tools.

---

## 1. Summary

- A new adapter, `js`, fills all eight `extract/*.json` outputs for TypeScript, JavaScript and React. It uses dependency-cruiser, knip, scip-typescript, a shipped script on the TypeScript 6 compiler API, tree-sitter and new semgrep rules, proven on a new fixture repository.
- The restore step learns `npm ci` for real, plus yarn and pnpm, and handles lockfiles below the repository root. All Node tools install from one lockfile shipped with the skill.
- The TS/JS blind-spot list (V7), the shared cards and checks, and the prompts are extended without changing any card schema. A React component table joins `interactions.graph` (S3).
- `VERSION` goes to 0.9.0, which forces a full rebuild. Python output must stay identical, and section 6 proves it.
- A separate measured table reports each package's **real public API**, what other packages can actually import, in `io.contracts` (D17).
- **Opus writes the ground truth, and Sonnet builds the dossier** (D18). Opus also rules on every disagreement in Phase 4a.
- **Five Sonnet sessions, two Opus sessions, and one more Sonnet session if Opus finds faults.** Phase 1 tools and install. Phase 2 extractors. Phase 3 shared layer, prompts and version. Phase 4 primary repository and Python golden. Phase 5 React and mixed repositories, then merge. See D16.

### Acceptance pause status

The author ran an acceptance test after M2, and it took a long time. It left no record in this repository, which is why the first draft of this plan wrongly doubted it. The author will run a **second acceptance test** before M4 is implemented. Its findings come first: they may change the spec or this plan, and Phase 1 does not start until the author says they are in.

### Carried over from the pause

None of this is in M4. It is listed for the author, and the Python adapter and shared layer stay as they are:

1. Plan 009 findings: (a) commit counts differ between the report 02 tiles and history because merges count in one and not the other; (b) with two humans and no GitHub remote, agent commits stay with the agent; (c) block B's "near 74 pair items" wording.
2. Plan 007 findings still open: 2 (a shell script under `docs/` listed as an entry point), 4 (`db-access` matches any `.add` or `.execute`), 6 (`__all__` listed as module state), 7 (three vulture false positives).
3. Block G2 (report 02 visual golden) has failed since `5518e74`, on `main` too. Its baseline PNGs need remaking by the author (Q7).
4. Block E's `BASE` digest is out of date. Plan 009 replaced it with a comparison against `main`, and this plan does the same.
5. **A possible staleness fault, seen in the code but not confirmed by a run.** `scip_tool.run_index` passes `--project-version <sha>`, and `candidates._feed("defs")` digests the SCIP `symbol` string. If the version appears in that string, every Python `def` changes on every commit, and report `components` goes stale on every build. Plan 009 block J did list `components` as stale after a one-line edit. M4 avoids this for JS (D11). Fixing Python would change Python output, so it is not in M4.
6. Plan 008's open item on report 02's cut-off legend at 400 px, and spec issue S10 of plan 009 (A1 to A9, V11 and V12 are not yet written into the spec file).

---

## 2. Shared rules (every phase reads this first)

- **Branch.** All phases work on one branch, `feat/dossier-m4`, created from `main` in Phase 1 and merged at the end of Phase 5. One commit per task.
- **Skills to load at the start of every phase:** `git-commit`, `git-workflow`, `py-projects`, `py-unit-tests`, `claude-planning-docs`. Phase 3 also loads `docs-project`, `docs-readme` and `git-release`.
- **Commit style.** Follow `git-commit`. Suggested messages match the M2 and M3 commits.
- **Never touch:** `INSTALLED`, `LIVE` (copy it), `REPO`, `FIX`, the pinned clones of `RW` and `BP` (they are analysed, never changed). If a step seems to need a change in `INSTALLED`, make it in `SKILL`. **Nothing from `RW` may be committed**: no fixture, no snippet, no saved output.
- **Report 02 and card schemas.** Report 02 (its panels, CSS and JS) does not change. **No file in `prompts/schema/*.json` changes.** M4 adds no card.
- **The Python adapter's behaviour must not change.** `scripts/py_*.py`, `rules/python/` and `tests/fixtures/pyrepo/` are not edited. Shared code may change only where a task says so, and then it must give the same result for Python. Section 6 block P proves it. `test_py_adapter_slow.py` must pass at the end of every phase.
- **Report 02 guard.** After every task that edits `render.py`, `assets/dossier.css` or `assets/dossier.js`, run section 6 block E. It must print `OK`.
- **Scratch.** Every command that renders or builds sets `DOSSIER_HOME`, `DOSSIER_CONFIG` and `DOSSIER_CACHE` to a fresh folder. Tests use `tmp_path`. **Do not use `/tmp` for builds of `RW` or `BP`:** it is a 7.5 GB tmpfs that filled up in plan 009, and these builds install `node_modules`. Section 6 makes a folder under `~/.cache` and removes it at the end. Nothing outside section 6 builds a dossier of a real repository.
- **Every child process goes through `sandbox.run`**, directly or through `ctx.run`. No sandboxing, containers or namespaces (spec decision 5). Install scripts of a target repository's dependencies stay disabled.
- **No new runtime dependencies** in `scripts/dossier.py` or anything it imports (standard library plus `pygments`). Node tools run from the committed lockfile.
- **Tests first.** Each task starts with a test that fails on the current code. Run it, see it fail, and record the failure line in the commit body as `Fails before: ...`. The full suite passes after every task. The slow suite passes at the end of each phase.
- **Do not weaken a check to make it pass.** If a check fails on real output, the output is wrong until the author says otherwise.
- **Measured values are never written by Claude.** Nothing is dropped silently: no `[:N]` on data that feeds a card.
- **Plain language** in everything a dossier user reads. Gaps statements use the fixed wording in this plan, so their IDs stay stable.
- **If the code contradicts this plan, stop and report** under that phase's "Results". Do not design around it.
- **Size.** Keep each new module under about 300 lines.
- **Tree-sitter patterns stay one or two levels deep.** Three-level patterns matched nothing in M2 (plan 007, M2-8 deviation 1).
- **Context.** Keep tool output short: single test files while working, and pipe long output through `tail`. Never print a whole page or a whole `extract/*.json`.
- **Ticking.** Tick each task's checkbox in the same commit as the task. Write results under the phase's "Results" heading.

---

## 3. Spec versus code

"Absorb" means the plan can absorb it as proposed. "Decision" means the human answers first (section 7 or 8).

| # | Area | Spec says | Code does today (0.8.0) | Proposal | Class |
|---|---|---|---|---|---|
| 1 | What exists for TS/JS | 6.1, 6.2: a JS/TS adapter with four Node tools | **Almost nothing.** `ts_worker.py` is the **tree-sitter** worker ("ts" means tree-sitter; it has nothing to do with TypeScript) and needs no change. `scripts/node/` holds only `scip-python/`. `tools.json` has four JS entries with `cards: []`. `adapters._registered()` has two adapters. No `rules/js/`. `gather` already classifies JS and TS, and `deps.py` has a `JavaScriptAdapter`, but that one feeds report 02 only | Build the adapter (D1). Leave `ts_worker.py` and `deps.py` as they are | Absorb |
| 2 | How Node tools install | 6.2 says `npx`; 5.4 rule 7 forbids floating dependencies | `via: "npx"` in `tools.json`. scip-python already uses a shipped lockfile | One shipped lockfile, `scripts/node/js-tools/`, as decision 15 did for scip-python (D2, S5). `via` stays `npx`, because `toolcheck.HOST_FOR_VIA` uses it to mean "needs node and npm"; `node_lock` makes `doctor` print "from a lockfile with npm" | Absorb |
| 3 | Tool pins | Pinned; re-check at first use | dependency-cruiser 18.6.0, knip 6.42.0, scip-typescript 0.4.0, typescript `null` | New pins (D2): 18.7.0, 6.42.1, 0.5.2, 6.0.3 | Absorb |
| 4 | Which TypeScript | "shipped script on the TypeScript compiler API" | Left open (M1 spec issue 11) | **6.0.3.** 7.0 has no API; dependency-cruiser 18.7.0 accepts only `<7.0.0`; scip-typescript 0.5.2 needs `^6.0.3` (D2) | Absorb |
| 5 | Node version | 6.2 names Node with no version | `tools.json` says 22.0.0 for JS. **This machine has 20.19.2**, from `/usr/bin`, with no version manager holding Node | The minimum becomes 22.13.0 (scip-typescript's `engines`). **The host must be upgraded before Phase 1** (Q2) | Ruled (Q2) |
| 6 | Restore | 5.1: `npm ci --ignore-scripts`, lockfiles only | `npm` entry is `enabled: false`. `restore.plans` finds lockfiles **at the root only**. `yarn` and `pnpm` are not known | Enable npm. Add yarn (classic and berry) and pnpm, installed from the same lockfile. Find lockfiles in project folders (D3, S6). `BP` has three `yarn.lock` files below `apps/` and none at the root, so without this it gets no restore at all | Ruled (Q4) |
| 7 | No lockfile | Lockfile only | `decide` skips with a reason, and `process.py` tests for a reason that starts "There is no lockfile" | Same text kept. No install; extractors run without installed packages, and knip may fail, which gives a "partial" badge | Absorb |
| 8 | Private caches | 5.4 rule 3 lists npm, NuGet, uv and pip | Nothing for yarn or pnpm | New allowlisted names (D3, S6). `test_hygiene.py` must still pass | Absorb |
| 9 | Trusted refs | 5.4 rule 4: without a trusted ref, Node extractors are skipped and "the Python static extractors still run" | `loads_repo_code=True` would skip a whole adapter | `loads_repo_code` stays `False`. The four Node tools are gated one by one, as `_symbols` does for scip-python, so semgrep and tree-sitter still run (S7) | Absorb |
| 10 | Repository config run as code | 5.4 applies to any tool that loads repository config | `restricted` profile exists | All four Node tools run under `restricted`. knip loads repository config through jiti. dependency-cruiser runs with `--no-config` for the graph, and a second run reads the repository's own rules (D5) | Absorb |
| 11 | `entry_points` kinds | 6.1 list; section 4 also says "package scripts" | D2 of plan 007 lists 12 kinds. Nothing validates the list: only `py_adapter.py` names them | Six new kinds (D6, S4) | Absorb |
| 12 | Framework scope | Spec silent; recall measured over kinds | Nothing | Derived from `RW`, `BP` and the kinds in 6.1 (D6). Unsupported frameworks get a Gaps item, never silence | Absorb |
| 13 | `graph` shape | Nodes, edges, cycles | Consumers assume dotted Python names in several places (`checks_v3.Resolver.by_last`, `checks.module_names`, `components.component_candidates`) | JS module names are paths without the extension, plus a new `short` key (D4). Three small readers change, with no effect on Python | Absorb |
| 14 | Import lines | Evidence cites a line | dependency-cruiser gives no line numbers | Lines come from `ts_facts` and are joined by file and specifier (D4). `measured_tables` already accepts an empty list | Absorb |
| 15 | Test files in the graph | - | grimp's graph has no test files, but dependency-cruiser sees them. `dead_rows` would list every test as "module nothing imports" | Test files and `.d.ts` files are left out of `module` items, and their edges feed `tests.paths` (D4) | Absorb |
| 16 | Areas | D4 of plan 008: first folder below the package root | `measured_graph.package_roots` reads Python packages only. For JS every component's area would be `src` or `apps`, which defeats the diagram budgets | New `source-root` graph item (D4) | Absorb |
| 17 | Public surface | 6.1 defines it for Python only | `scip_read._public` is Python's rule | For JS, public means exported from its file (D11, S9) | Ruled (S9) |
| 18 | Barrels, default exports | - | - | Barrels are edges to `index.*` in the graph, and a blind spot (D10). Default exports use the name `default` | Absorb |
| 19 | Workspaces and path aliases | - | - | D3 and D5: tools run once per project, `ts_facts` picks the tsconfig, references are followed by scip-typescript itself (read in its source) | Absorb |
| 20 | Data entities | "TS types and interfaces" | A5 needs one row per entity, with no group decisions | Every interface would be unworkable: `BP` has 33 `*Props` types in one app. Filter in D7 (S10) | Ruled (S10) |
| 21 | Prisma | "ORM models" | Nothing. `repo_adapter.sql_tables` already turns `.sql` under `migrations/` into `migration` items | Standard-library parser (D7). `DATABASE_URL` is only in `schema.prisma`, so the parser also yields `env-var` and `db-connect` findings | Absorb |
| 22 | Name clashes in the ER card | - | `measured_er._relations` looks up by name; `RW` has a Prisma `User` and an interface `User` | Lookup keeps Prisma with Prisma (D7) | Absorb |
| 23 | Tests | Tree-sitter plus config parsing | Python only | `js_queries.py` (D8). `repo_adapter.TEST_COMMAND` knows no JS runner | Absorb |
| 24 | React tree and router | 6.2: the shipped script gives them; 6.4: context and hooks wiring is a blind spot. **No output in 6.1 and no card** | Nothing | Tree in `graph` items and a measured table in `interactions.graph`; routes in `entry_points` (D9, S3) | Ruled (S3) |
| 25 | DI | 6.2: semgrep finds DI "where the language has a common container: C# and TS" | No category and no home card | A blind-spot pattern, so hits reach Gaps (D10, S2) | Ruled (S2) |
| 26 | V7 for TS/JS | 6.4 list, each with a rule | Python and All only | D10 | Absorb |
| 27 | V5 and dispositions | Every candidate decided | Works on any adapter's items, and group decisions stay limited to `io_candidates` | No new category and no new candidate list. New `entry_points` kinds and `models` kinds pass V5, A5 and "Fields complete" unchanged | Absorb |
| 28 | Git-derived cards | Language-independent | Checked by reading: `history.py`, `markers.py` (`//` and `*` count as comments), blast radius and co-change work on paths and on `graph` items. **Three changes are needed**: complexity needs a JS query (M4-11); `dead_rows` assumes a `confidence` (KeyError on a knip item) and would duplicate knip (M4-19); the stale-flags Gaps item says "for Python" (M4-19) | As listed | Absorb |
| 29 | Dead code | `dead.json`; "vulture, knip" | `dead_rows` also adds `dependencies.json` `unused` | Knip's dependency findings replace the same-named `deps.py` rows, so nothing shows twice (M4-19) | Absorb |
| 30 | Component paths with brackets | V4 | `components.match_score` treats `[` as a glob, and `fnmatch` then fails: **tested**, `fnmatch('apps/a/[id]/page.tsx', 'apps/a/[id]/*')` is False. Next.js folders like `[discussionId]` would give false V4 errors. Citations are fine: `INLINE_CITE` parses them, also tested. `parse_paths` is not | Fix both (M4-18) | Absorb |
| 31 | `reading.map`, `conventions.tooling` | Detected locations and tools | Lists are Python-shaped | Extend (M4-20). `REPO` has no JS config files, checked with `git ls-tree`, so its page does not change | Absorb |
| 32 | Upgrade burden | P1. Runtimes and major frameworks | Python row only. `nodejs` is in `eol.json` with cycles like `22`; `_cycle` needs `major.minor` | Node row, plus React and Next if the source has them (M4-22). First to cut | Absorb |
| 33 | "Partial" and Gaps | 5.1, D7 of plan 007 | Tools have `cards: []`. `process.partial_cards` and `coverage_items` are generic | Fill `cards` (D2). A tool absent for JS badges its cards in a mixed repository too, correctly | Absorb |
| 34 | Node removed | Fails clearly or degrades | `sandbox._host_path` always appends `/usr/bin`, so a PATH trick cannot hide `/usr/bin/node`. Plan 007 cut that block | Test with a fake `node` that fails, placed first on `PATH`. `check_host` reports it missing, and the adapter's own gate skips the four tools (D1, block N) | Absorb |
| 35 | Mixed repositories | Spec 11 item 2: same card skeleton | `run_extract` keeps one section per adapter; `candidates.load` joins them | No merging code is needed (D13). The skeleton is fixed by the schema, and a new tool checks it mechanically | Absorb |
| 36 | Staleness | 5.3 | `FEEDS` and `_feed` | Add `ui` to `interactions`. JS symbols are stored without package or version (D11, D14) | Absorb |
| 37 | Golden TS repo | Sections 10 and 11 assume the author's own apps | The author has none | `RW` and `BP`, with a hand-built ground truth (S1) | Ruled (S1) |
| 38 | `BP` layout | One repository, one dossier | - | **One dossier of the whole repository; no subfolder scope is needed.** 535 tracked files, 447 of them code, in three near-copies of an app. Each app is its own project (D3). It costs about three times the rows, not a new feature (Q8) | Absorb |
| 39 | Semgrep file types | Rules cover JS and TS | `lang.json`: js `.cjs .js .jsx .mjs`; ts `.ts .tsx`, with `.d.ts` excluded. **`.mts` and `.cts` are not listed** | `.d.ts` files are not sent. M4-1 tests `.mts` and `.cts`. If they are not parsed, M4-15 adds the fixed Gaps item in D10 | Absorb |
| 40 | `test_rules.py` | - | Hard-codes `{"python", "all"}`, a `#` comment, and a `.py` target | Generalised in M4-14 | Absorb |
| 41 | P0 versus P1 | Cut line | P1 cards in play: `change.upgrade-burden` only | M4-22 is the only cut that touches a card | Absorb |
| 42 | Session count | `process.md`: M4 is one session | M2 and M3 each took three | Five (D16) | Ruled (Q3) |

Amendments from plans 008 and 009 that this plan relies on: A2 (diagram budgets), A3 (`data.relationships` drawn by code), A4 (code fills measured cells), A5 (one row per entity and entry point), A6 (no card reads capped facts), A8 (V11, V12), and spec decisions 24, 25 and 31.

**How the plan 008 checks apply to what M4 adds.** M4 adds no card, so V6 is untouched. Each new thing is covered like this:

| New thing | V5 | V11 | V12 |
|---|---|---|---|
| New entry kinds, entity kinds | Per-row rule (A5), Fields complete | Existing row counts | Existing |
| React table in `interactions.graph` | Exempt: measured | New count (M4-21) | Existing page-wide checks, on the M4-24 test page at both widths |
| Knip rows in `change.dead-code` | Exempt: measured | `dead_rows` is the shared source | Existing |
| New rows in `reading.map`, `conventions.tooling` | Exempt: measured | Existing counts | Existing |
| Node row in `change.upgrade-burden` | Exempt: measured | `rows()` is the shared source | Existing |

---

## 4. Decisions

### D1. Adapter structure

One class, `JsAdapter`: `name = "js"`, `version = "1"`, `languages = ("JavaScript", "TypeScript")`, `tools = ("dependency-cruiser", "knip", "scip-typescript", "typescript", "semgrep", "tree-sitter-language-pack")`, `expected_untracked = ("**/node_modules/**",)`, `loads_repo_code = False`. It shares `ctx.semgrep` and `ctx.treesitter`, as Python does. It is unrelated to `ts_worker.py` except as a caller.

| File | Owns |
|---|---|
| `scripts/js_project.py` (new) | Pure: projects, workspaces, `package.json` reading, source roots |
| `scripts/js_entries.py` (new) | Pure: package bins, scripts and main; Nx targets; Next.js file routes |
| `scripts/js_prisma.py` (new) | Pure: `.prisma` parser |
| `scripts/js_queries.py` (new) | Tree-sitter queries: tests, complexity, module state; test config reading |
| `scripts/js_tools.py` (new) | Install from the lockfile, the Node gate, and clients for the four tools |
| `scripts/js_reduce.py` (new) | Pure: tool JSON to items |
| `scripts/js_adapter.py` (new) | `JsAdapter`: the steps, in order, with per-tool status |
| `scripts/node/js-tools/package.json`, `package-lock.json`, `ts_facts.mjs` (new) | The pinned tools and the shipped script |
| `rules/js/*.yml`, `tests/fixtures/semgrep/js/*` (new) | Semgrep rules and their tests |
| `tests/fixtures/jsrepo/` (new) | The fixture repository |
| `tests/tools/skeleton.py`, `tests/tools/ground_truth.py`, `tests/tools/m4_page.py` (new) | Skeleton check, recall figures, test page |

**The Node gate.** `js_tools.node_problem(run) -> str | None` runs `node --version` through `run` (profile `tool`, 15 seconds). It returns `Node is not installed.` when that fails, `Node {v} is too old; these tools need {min} or later.` when old (`min` from `tools.json`), else `None`. When it returns a reason, or when `ctx.trusted` is false, each of the four Node tools is `skipped` with that reason. The untrusted reason is `The ref is not trusted, so Node tools did not run. Use --allow-ref to run them.`

Rejected: one class per framework (nothing but rules differs); `loads_repo_code = True` (row 9).

### D2. Tools, pins and install

The pin rule: newest stable release published at least 14 days before the check date. Checked 2026-11-05, so the cutoff is 2026-10-22.

| Tool | Pin (date) | Latest | Facts checked | Source |
|---|---|---|---|---|
| dependency-cruiser | **18.7.0** (2026-10-19) | 18.7.2 | engines `^22\|\|^24\|\|>=26`; bin `bin/dependency-cruiser.mjs`; `supportedTranspilers.typescript` is `>=2.0.0 <7.0.0`; no `typescript` dependency of its own | registry |
| knip | **6.42.1** (2026-10-19) | 6.44.1 | engines `^20.19.0 \|\| >=22.12.0`; bin `bin/knip.js`; parser is `oxc-parser`; config through `jiti` | registry |
| @sourcegraph/scip-typescript | **0.5.2** (2026-10-22) | 0.6.1 | engines `>=22.13.0`; bin `dist/src/main.js`; depends on `typescript ^6.0.3`. 0.6.x needs Node `>=22.23.4` and is too new | registry, source at `v0.5.2` |
| typescript | **6.0.3** (2026-04-16) | 7.0.2 | `main` is `./lib/typescript.js`; 7.0 has no `main` and no API | registry, announcement |
| yarn (classic) | **1.22.22** (2024-03-09) | 1.22.22 | bin `bin/yarn.js`; has a `preinstall`, which `--ignore-scripts` skips | registry |
| @yarnpkg/cli-dist (berry) | **4.18.1** (2026-09-24) | 4.18.1 | bin `bin/yarn.js`; engines `>=18.12.0` | registry |
| pnpm | **12.15.0** (2026-10-21) | 12.18.0 | engines `>=18`. Its bin path is checked in M4-1 (11.x used `bin/pnpm.mjs`) | registry |

`scripts/node/js-tools/package.json`, every version exact:

```json
{"name": "dossier-js-tools", "private": true, "type": "module",
 "dependencies": {"dependency-cruiser": "18.7.0", "knip": "6.42.1", "@sourcegraph/scip-typescript": "0.5.2", "typescript": "6.0.3",
                  "yarn": "1.22.22", "@yarnpkg/cli-dist": "4.18.1", "pnpm": "12.15.0"}}
```

A top-level `typescript` is what dependency-cruiser finds and what `ts_facts.mjs` imports. Only one copy of TypeScript is wanted. M4-1 confirms that `depcruise --info` shows it as usable.

**Install.** `js_tools.ensure_installed(run, cache_root, timeout) -> Path` copies the three files to `<cache root>/.dossier-tools/node/js-tools-<first 8 hex of the lock's sha1>/`, runs `npm ci --ignore-scripts --no-audit --no-fund` (profile `tool`, cwd that folder), and writes a `.installed` marker holding the sha1 of the lock plus `ts_facts.mjs`. It follows `scip_tool.ensure_installed`. `ts_facts.mjs` must live beside `node_modules` for its import to resolve, because `NODE_PATH` is not on the allowlist. `dossier clean` leaves `.dossier-tools` alone, as it does today.

**Versions in report 01.** `tools.json` gives them, and they reach `extract` records and the process card by the existing path. No new code.

**`tools.json` changes.** `node.min.js` becomes `22.13.0`, `node.source` unchanged. For dependency-cruiser, knip, scip-typescript and typescript: the new `version` and `published`, `"node_lock": "node/js-tools"`, `"verified": "2026-11-05"`, and:

| Tool | `cards` |
|---|---|
| `dependency-cruiser` | the same list as `grimp` |
| `scip-typescript` | the same list as `scip-python` |
| `knip` | `change.dead-code` |
| `typescript` | `data.entities`, `data.relationships`, `entry.catalog`, `interactions.graph` |

Remove `typescript.open`. New entries `yarn`, `yarn-berry` and `pnpm`: `scope: ["js"]`, `via: "npx"`, `node_lock`, `gives: "installs a repository's locked packages"`, `cards: []`, `first_used: "M4"`.

### D3. Projects, workspaces and restore

`js_project.projects(tree, read) -> list[dict]`, where each project is:

```python
{"dir": "apps/react-vite", "package": "bulletproof-react-vite", "lockfile": "yarn.lock", "manager": "yarn",
 "members": ["apps/react-vite"], "files": ["apps/react-vite/src/main.tsx", ...]}
```

Rules, in order:

1. A **package** is a folder with a tracked `package.json` for which `gather.noise_reason` is `None`.
2. A package is a **project** when it holds a lockfile (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`), or when no folder above it is a package holding a lockfile or `workspaces` (or a `pnpm-workspace.yaml`).
3. Any other package is a **member** of the nearest project above it.
4. JS and TS files belong to the nearest project above them. Files with no project go to a virtual project with `dir: ""` and `package: None`.
5. A project with no files is dropped from tool runs. `BP`'s root `package.json` is such a project: it has no lockfile, no workspaces and no source files.
6. Bun (`bun.lock`, `bun.lockb`) is not installed. Its `manager` is `bun`, and the restore records the reason in D10's fixed item.

Tools run **once per project**, with cwd set to the project's folder.

**Restore.** `tools.json` `restore` entries:

```json
{"ecosystem": "npm",  "lockfile": "package-lock.json", "nested": true, "enabled": true, "command": ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"]},
{"ecosystem": "yarn", "lockfile": "yarn.lock", "nested": true, "enabled": true, "auth": "npm",
 "command": ["node", "{js_tools}/node_modules/yarn/bin/yarn.js", "install", "--frozen-lockfile", "--ignore-scripts", "--non-interactive"],
 "berry_command": ["node", "{js_tools}/node_modules/@yarnpkg/cli-dist/bin/yarn.js", "install", "--immutable", "--mode=skip-build"]},
{"ecosystem": "pnpm", "lockfile": "pnpm-lock.yaml", "nested": true, "enabled": true, "auth": "npm",
 "command": ["node", "{js_tools}/node_modules/pnpm/bin/pnpm.mjs", "install", "--frozen-lockfile", "--ignore-scripts"]}
```

- `restore.plans(tree, tools, checkout=None)`: an entry without `nested` matches at the root only, as today. With `nested`, it matches every non-noise folder holding the lockfile. Each plan gains `"dir"` (`""` at the root). A `yarn.lock` whose text contains `__metadata:` uses `berry_command`.
- `restore.run` runs each plan with `cwd = checkout / dir`. A token containing `{js_tools}` is expanded after `js_tools.ensure_installed`. `ecosystem=` passes `r.get("auth", ecosystem)` to `sandbox.run`, so one `registry_auth.npm` entry covers all three. Result dicts gain `dir`. A failure reason for a non-root plan ends with ` (in {dir})`, so Python wording stays the same.
- `stage_copy`: `restored[eco]` is true only when every plan of that ecosystem succeeded. `will_run[].where` joins `dir`.
- No lockfile: unchanged. **`nuget` stays disabled.** `--ignore-scripts` is in every npm-family command.

**Rule 5.4 hygiene.** `sandbox.ALLOWED_NAMES` gains `YARN_CACHE_FOLDER`, `YARN_GLOBAL_FOLDER`, `YARN_ENABLE_TELEMETRY` and `npm_config_store_dir`. `build_env` sets `YARN_CACHE_FOLDER=<area>/cache/yarn`, `YARN_GLOBAL_FOLDER=<area>/cache/yarn-berry`, `YARN_ENABLE_TELEMETRY=0`, `npm_config_store_dir=<area>/cache/pnpm`. I could not confirm that pnpm reads `npm_config_store_dir` (section 7, O1): M4-1 tests it.

Rejected: Corepack (it follows a repository's `packageManager` field and downloads unpinned versions, against 5.4 rule 7); requiring yarn and pnpm on the host (6.2 says everything else installs itself); a subfolder scope for `BP` (the spec says one repository, and it fits).

### D4. `graph` items for JS

| Kind | Fields |
|---|---|
| `module` | `path`, `module` (the path without its last extension; the full path when two files in a folder share a stem), `short` (the file's stem, or the parent folder's name for `index.*`), `package: null`, `is_package: false`, `language: "js"`, `project`, `complexity` |
| `import` | `path`, `paths: [imported]`, `from`, `to`, `lines`, `via: "dependency-cruiser"`, `type_only`, `dynamic` |
| `cycle` | as Python. **Computed by `graphs.cycles` over edges that are not `type_only`**, because a type-only import does not exist at run time |
| `contract` | `path` (the config file), `contract` (rule name), `type: "dependency-cruiser"`, `status` (`broken` or `kept`), `violations`, `reason: null` |
| `ui-component`, `renders` | D9 |
| `source-root` (new) | `path` (the project's `package.json`, or the first file of a virtual project), `root` |
| `js-note` (new) | D10's fixed Gaps items: `path`, `note`, `name` |

`source-root` rule (`js_project.source_roots`): with one project, `root` is `<dir>/src` when that folder holds files, else `dir`. With several projects, `root` is the parent folder of each project (`apps` for `BP`), so each app becomes an area; a project at the repository root gets none. `measured_graph.package_roots` adds these to its result. Python-only repositories have no such items, so their result is unchanged.

Module items exclude files matching `gather.TEST_RE` and files ending in `.d.ts`. Edges **from** test files go to `tests.paths` (D8). Edges to files outside the tree are dropped.

Readers that change, each with no effect on a module lacking `short`:

- `checks_v3.Resolver`: `by_last` key is `m.get("short") or m["module"].rsplit(".", 1)[-1]`.
- `checks.validate`: the module set passed to V2 also holds each `short`.
- `candidates.text`: new section `== JavaScript and TypeScript projects ==` when `source-root` items exist. `== Python packages ==` stays, but is printed only when packages exist or no such items do.

### D5. How each tool runs

`T = config.timeouts()["tool"]`. `X = <install dir>`. cwd is the project's folder unless stated. Paths in output are made relative to the checkout by prefixing `dir`.

| Order | Tool | Command | Profile | Needs |
|---|---|---|---|---|
| 1 | pure Python | `js_project`, `js_entries`, `js_prisma` | - | nothing |
| 2 | tree-sitter | `ctx.treesitter.query(...)`, three grammars (D8) | `tool` | nothing |
| 3 | semgrep | `ctx.semgrep.scan(rules/js, files)`, without `.d.ts` | `tool` | nothing |
| 4 | typescript | `node --max-old-space-size=4096 X/ts_facts.mjs`, JSON on stdin | `restricted` | Node gate, trust |
| 5 | dependency-cruiser | `node X/node_modules/dependency-cruiser/bin/dependency-cruiser.mjs . --no-config --output-type json --ts-pre-compilation-deps --no-progress --do-not-follow node_modules --exclude '(^\|/)(node_modules\|dist\|build\|coverage\|\.next\|\.nx)/'`, plus `--ts-config <file>` when `ts_facts` found one | `restricted` | Node gate, trust |
| 5b | the same, repository rules | only with a `.dependency-cruiser.{js,cjs,mjs,ts,cts,mts,json}`: `... . --config <file> --output-type json --no-progress`, reading `summary.violations` only | `restricted` | as above |
| 6 | knip | `node X/node_modules/knip/bin/knip.js --reporter json --no-exit-code --no-progress --no-config-hints --include files,dependencies,exports,types` | `restricted` | Node gate, trust. Exit 2 is `failed`, with the first stderr line as the reason |
| 7 | scip-typescript | `node --max-old-space-size=4096 X/node_modules/@sourcegraph/scip-typescript/dist/src/main.js index --no-progress-bar --output <area>/scip/js-<n>.scip`, with `--infer-tsconfig` only when the project has no `tsconfig.json` | `restricted` | Node gate, trust |

Why this order: what needs nothing runs first, so a Node failure loses the least. `ts_facts` picks the tsconfig that the next steps use. scip-typescript goes last because it is the slowest, and because `--infer-tsconfig` writes a file into the checkout. That file is untracked and `workarea.verify` ignores it. Each call has timeout `T`. A failure in one project marks that tool `failed` with the project's name, and the other projects still run. The status recorded is the worst seen.

Rejected: `--yarn-workspaces` and `--pnpm-workspaces` for scip-typescript (they shell out to the package manager); dependency-cruiser's own `cycle` field (it counts type-only edges); `--cache` for any tool (a cache in `node_modules` is state outside the key).

**Facts read from tool sources.** scip-typescript `index` takes `--cwd`, `--output`, `--infer-tsconfig`, `--no-progress-bar`, `--no-global-caches`, `--max-file-byte-size` and `[projects...]`. `--output` may be absolute. It follows `config.projectReferences` itself. With no documents it exits 1 and removes the output file. It writes one protobuf message per project into the file, which `scip_read.decode` can read, because concatenated messages merge their repeated `documents` field.

### D6. Entry points

| Kind | Source | `name` | Trigger |
|---|---|---|---|
| `package-bin` (new) | `package.json` `bin` | bin name | ``the `{name}` command`` |
| `package-script` (new) | `package.json` `scripts`, and `prisma.seed` as `prisma seed` | `{package} {script}` | ``running `{script}` with the package manager`` |
| `package-main` (new) | `main`, `module`, `exports["."]` | the value | `when another program imports or runs this package` |
| `nx-target` (new) | `project.json` `targets` | `{project}:{target}` | ``running `nx {target}` `` |
| `server-listen` (new) | semgrep | `listen` | `when the server starts` |
| `ui-route` (new) | `ts_facts` routes | the route | ``opening `{name}` in the browser`` |
| `http-route` | semgrep; Next.js file routes | `GET /tags` | ``a web request to `{name}` `` |
| `cli-command` | semgrep | command name | ``the `{name}` command`` |
| `queue-consumer`, `scheduled-job` | semgrep | queue name or schedule | as Python |

Container `CMD`, Makefile targets, CI schedules, shebang scripts and systemd units already come from the `repo` adapter.

**Frameworks supported in M4, and why:**

| Group | Supported | Why |
|---|---|---|
| HTTP | Express (`RW`), Next.js app and pages routers (`BP`), Fastify, NestJS | Named by the prompt, or the common container the spec's DI line assumes |
| UI routes | React Router objects and `<Route>` JSX (`BP`) | The spec's "router config" |
| CLI | commander, yargs | 6.1 kind `cli-command` |
| Queue | BullMQ, amqplib, kafkajs, NestJS `@Processor` | 6.1 kind `queue-consumer` |
| Schedule | node-cron, cron, NestJS `@Cron` | 6.1 kind `scheduled-job` |
| Monorepo tasks | Nx `project.json` (`RW`) | `RW` uses it. `turbo.json` holds no commands of its own |

**Sent to Gaps:** a manifest naming Koa, Hapi, Hono, Remix, Nuxt, SvelteKit, Astro or Angular gets one fixed item per name (D10).

**Route names.** A rule's `metadata.detail` captures method and path as one group, such as `get('/tags`. The worker returns only the first group, so `js_reduce.route_parts(detail) -> (method, path)` splits it. This needs no change to `semgrep_worker.py`. The item's `snippet` is set to `GET /tags`, because a multi-line route's first source line (`router.get(`) is the same for many routes and ids would rest on position alone.

**Prefixes.** Routes are named as written. `RW` writes `/tags` and mounts it under `/api`. The mount is a `route-mount` blind spot, so Gaps lists it, and `reports.md` tells Claude to write the full path in the row.

**Next.js** (`js_entries.next_routes(files, project)`, only when the package depends on `next`). Under `app/` or `src/app/`: `page.*` gives the route and `route.*` gives `API {route}`. Under `pages/` or `src/pages/`: every file, except `_app`, `_document` and `_error`; `pages/api/**` gives `API {route}`. Folders in `(...)` are dropped from the route, and folders starting `_` or `@` are skipped. `[id]` stays as written. Kind `http-route`, rule `js.next-route`.

### D7. Models

Kinds: `prisma`, `prisma-enum`, `ts-interface`, `ts-type`, `ts-enum`, `typeorm`, `mongoose`, `sequelize`, `drizzle`, `zod`.

**What counts as an entity (S10).** From `ts_facts`, an item is an entity when all of these hold:

- it is exported;
- it is an `interface`, a `type` whose value is an object shape, an `enum`, a class with `@Entity`, or an exported `const` set from `z.object(...)`, `new Schema(...)`, `sequelize.define(...)` or `pgTable(...)` / `mysqlTable(...)` / `sqliteTable(...)`;
- its name does not end in `Props`;
- its file is not a test, not a `.d.ts`, and not a `*.stories.*`.

**Prisma** (`js_prisma.parse(path, text) -> {"models", "io"}`). Files: tracked `*.prisma`. Reads `model`, `enum` and `datasource`. Each model field gives `{"name", "type", "line", "ref", "pk"}`. `ref` is set when the base type (trailing `?` or `[]` removed) names another model or enum. `pk` is set for `@id`. Lines starting `@@` are block attributes, not fields. `env("X")` gives an `env-var` item (`detail` = X) and a `datasource` block gives a `db-connect` item. Rules: `js.prisma.env-var`, `js.prisma.datasource`. Enum members may be written `Low = "low"`, as the current docs show. Migrations need no new code: `src/prisma/migrations/**/migration.sql` already gives `migration` items.

**`measured_er._relations`.** The lookup key becomes `(family(e), name)`, where `family` is `"sql"` for SQL, `"prisma"` for the two Prisma kinds and `"other"` otherwise. For Python this equals today's key. A test asserts that.

### D8. Tests and syntax queries

Grammar by extension: `.ts .mts .cts` to `typescript`, `.tsx` to `tsx`, `.js .jsx .mjs .cjs` to `javascript`. `js_queries.by_grammar(files)` splits the files, and each query runs once per grammar. M4-1 confirms the three names.

- `test-file` item: Python's shape. `framework` is `playwright` when the file imports `@playwright/test`, `vitest` when it imports `vitest`, `node:test` likewise, `cypress` when under `cypress/`; otherwise the project's runner from config, in the order vitest, jest, mocha. `test_kind`: `e2e` when a path segment is `e2e`, or the framework is playwright or cypress; `integration` for segments `integration`, `functional`, `live`; else `unit`.
- Counted from `call_expression`s by function text. `tests`: `it`, `test`, `specify`, and their `.each`, `.only`, `.concurrent` forms. `classes`: `describe`, `suite`. `skips`: `.skip`, `.todo`, `.fixme`, `xit`, `xtest`, `xdescribe`. `xfails`: `.failing`, `.fails`. `mocks`: `jest.mock`, `jest.fn`, `jest.spyOn`, `vi.mock`, `vi.fn`, `vi.spyOn`, `sinon.*`, `setupServer`, `mockDeep`. `fixtures`: `beforeAll`, `beforeEach`, `afterAll`, `afterEach`, `test.extend`.
- `paths` and `imports` come from dependency-cruiser edges out of that file. Without them both are empty.
- `config` items, with `tool` in `jest`, `vitest`, `mocha`, `playwright`, `cypress`, `c8`, `nyc`: `jest.config.*`, `vitest.config.*`, a `test:` block in `vite.config.*`, `.mocharc.*`, `playwright.config.*`, `cypress.config.*`, `.c8rc*`, `.nycrc*`, and `jest` in `package.json`. `settings` holds `coverage_threshold`, read with a regex (these files are code and are never run), and `test_match` when present.
- `COMPLEXITY_Q`: `if_statement`, `for_statement`, `for_in_statement`, `while_statement`, `do_statement`, `switch_case`, `catch_clause`, `ternary_expression`, and `binary_expression` with `operator: ["&&" "||" "??"]`. The count goes on `module` items.
- `module_state`: `(lexical_declaration) @d` at column 0, or column 7 after `export `, whose text is a `let`, or a `const` whose value is `{}`, `[]` or `new Map`, `Set`, `WeakMap` (all-capitals names with non-empty values are constants, as Python). Rule `dossier.js.state.module-mutable`, category `global-state`.

### D9. `ts_facts.mjs` and React

The script reads `{"root": ".", "files": [...]}` on stdin and prints one JSON object. It **parses only**: it never imports or runs repository code, and it reads tsconfig files as data.

- **tsconfig choice.** `tsconfig.json`, then `jsconfig.json`. If the file has `references` and no `paths` of its own, the first referenced config with `paths` is used, else the first referenced config. `extends` that cannot be resolved (packages not installed) is reported in `errors`, and defaults are used. Options forced on: `allowJs`, `noEmit`, `skipLibCheck`, `noLib`, `types: []`.
- **Program.** `ts.createProgram(files, options)`, with `files` as root names, so a root tsconfig with `"files": []` (as in `RW`) still works.

Response:

```json
{"config": {"file": "tsconfig.json", "used": "tsconfig.app.json", "paths": {}},
 "imports": [{"path", "specifier", "line", "type_only", "dynamic"}],
 "exports": [{"path", "name", "line", "default": false}],
 "types": [{"path", "name", "kind", "line", "end_line", "exported", "bases": [], "decorators": [], "fields": [{"name", "type", "line", "optional"}]}],
 "components": [{"path", "name", "line", "end_line", "exported", "renders": [{"name", "path"}], "hooks": [], "provides": [], "consumes": []}],
 "routes": [{"path", "line", "end_line", "route", "resolved", "file", "framework"}],
 "errors": ["..."]}
```

- **A component** is a function, arrow function or `forwardRef`/`memo` wrapper whose name starts with a capital and whose body holds JSX, or a class extending `Component` or `PureComponent`.
- **`renders`:** capitalised JSX tags in its body, resolved through the checker to their declaring file (`path: null` for outside the repository).
- **`hooks`:** names of `use*` calls. **`provides`:** `X` from `<X.Provider>`. **`consumes`:** `X` from `useContext(X)`.
- **Routes.** Objects inside `createBrowserRouter`, `createHashRouter`, `createMemoryRouter` and `useRoutes`, and `<Route path=...>` JSX, with nested paths joined. `path` values that are not string literals are followed through the checker to an initialiser in the repository (`paths.auth.login.path`, in `BP`). If that fails, `resolved` is false and `route` is the source text. `file` is the target of a `lazy: () => import('...')`.

**Items.** `ui-component`: `{"kind", "path", "line", "name", "exported", "hooks", "provides", "consumes"}`. `renders`: `{"kind", "path", "paths": [target], "from", "to"}`, only for targets in the repository. `renders` also adds a `symbols` `ref-edge`, so V3 can back an arrow when scip-typescript did not run.

**The card (S3).** `interactions.graph` gains, after the module table and only when `ui-component` items exist, heading `Every React component` and table `t-interactions-graph-react`: Component, File, Renders, Rendered by, Hooks, Context, Source. One row per item, sorted by path then name. It is measured, so nothing is pruned. A page with no such items is byte-identical to today.

**What is a blind spot, not an output:** how context values reach their consumers at run time, and what a custom hook wires up. D10 lists those. `provides` and `consumes` are the names, not the data flow.

### D10. Blind spots (V7) and rule files

Every rule is `languages: [js, ts]`, `severity: INFO`, with a one-line `message` and the same metadata as Python's. Ids are `dossier.js.<family>.<name>`.

| Pattern id | How detected | What the dossier says it may miss | Report |
|---|---|---|---|
| `dynamic-import` (existing id) | `pattern-regex: \bimport\(\s*[^'"\s]`: only a computed target; a literal `import('./x')` is an edge dependency-cruiser sees (S11) | imports made at run time | `interactions` |
| `dynamic-require` | `require($X)`, `pattern-not: require("...")` | modules loaded through `require` with a computed name | `interactions` |
| `barrel-reexport` | `pattern-regex: (?m)^\s*export\s+(\*\|\{[^}]*\})\s+from\s` | names passed on through a barrel file, so an import may point at the barrel and not the real source | `interactions` |
| `react-context` | `createContext(...)`, `React.createContext(...)`, `useContext(...)`, `React.useContext(...)` | values passed through React context | `interactions` |
| `hook-wiring` | `pattern-regex: (?m)^\s*export\s+(const\|function)\s+use[A-Z]` | behaviour wired up inside custom hooks | `interactions` |
| `string-route` | a route call whose path is not a string literal, with the receiver test of the route rule | routes whose path is built at run time | `entry` |
| `route-mount` | `$R.use("...", $X)` with the receiver test | routes mounted under a prefix, so their full path is not the one written beside them | `entry` |
| `module-federation` | `ModuleFederationPlugin`, `federation(...)`, `pattern-regex: \bremotes\s*:` | code loaded from other builds through module federation | `interactions` |
| `di-registration` | `@Injectable(...)`, `@Module(...)`, `container.bind(...)`, `container.register(...)` (S2) | objects built and passed in by a dependency injection container | `interactions` |
| `computed-subcommand` (existing id) | `$P.command($X, ...)` where `$X` is not a literal | command-line commands registered under a computed name | `entry` |
| `codegen`, `feature-flag` | unchanged, in `rules/all` | unchanged | unchanged |

`checks_v7.BLIND_SPOTS` gains the new ids. Wording for existing ids does not change. An `.env`-driven pattern needs no rule: `BP` reads `import.meta.env` through a loop, and the `env-var` rule catches `import.meta.env`.

**Fixed coverage items.** They are added by `checks.validate` when any `module` item has `language: "js"`, or from project data:

- Report `change`: `Stale feature flags and unused routes are not detected for JavaScript or TypeScript.` How to confirm: `This is a known limit of this version of dossier.`
- Report `entry`, per framework named in a manifest (D6): `Routes written for {name} are not detected, so check the entry points by hand.` How to confirm: `This is a known limit of this version of dossier.`
- Report `dossier`, per project with `manager: "bun"`: `The packages of {dir} were not installed, because dossier does not install from Bun lockfiles.` How to confirm: `This is a known limit of this version of dossier.`
- Report `dossier`, only if M4-1 finds `.mts` and `.cts` are not scanned: `{n} .mts or .cts file(s) were not scanned by the pattern rules.` How to confirm: `Read these files by hand.`

The existing runtime-configuration item already appears once for any repository with a graph. The existing Python item is emitted only when a `module` item has no `language` key, so `REPO`'s Gaps ids do not change.

**Rule files** (`rules/js/`). The route receiver test is `metavariable-regex` on `$R`: `^(app|router|server|fastify|api|.*[Rr]outer|.*[Aa]pp)$`. Without it, `$X.get("...")` would match `map.get`, `axios.get` and `req.get`.

| File | Rule (category or kind): what it matches |
|---|---|
| `entry.yml` | `http-route` (http-route): `$R.$M("...", $H, ...)`, `$M` in `get post put patch delete options head all`, plus the receiver test, `detail` `\.((?:get\|post\|put\|patch\|delete\|options\|head\|all)\(\s*['"\x60][^'"\x60]*)`; `route-chain`: `$R.route("...").$M(...)`; `fastify-route`: `$R.route({...})` with a `url:` key; `nest-route`: decorators `@Get`, `@Post`, `@Put`, `@Patch`, `@Delete`; `server-listen` (server-listen): `$R.listen(...)` with the receiver test; `cli-command` (cli-command): `$P.command("...", ...)`; `queue-consumer` (queue-consumer): `new Worker($Q, $FN, ...)`, `$CH.consume(...)`, `$C.run({eachMessage: ...})`, `@Processor(...)`; `scheduled-job` (scheduled-job): `cron.schedule(...)`, `new CronJob(...)`, `@Cron(...)` |
| `inputs.yml` | `env-var`: `process.env.$K`, `process.env[$K]`, `pattern-regex: import\.meta\.env\.\w+`; `cli-args`: `process.argv`, `$P.option(...)`, `$P.argument(...)`, `yargs(...)`, `minimist(...)`; `config-file`: `dotenv.config(...)`, `config()` from dotenv; `file-read`: `fs.readFile(...)`, `fs.readFileSync(...)`, `fs.createReadStream(...)`, `fsp.readFile(...)`; `stdin`: `process.stdin`, `readline.createInterface(...)`; `message-consume`: `$C.subscribe(...)`, `$S.on("message", ...)` |
| `outputs.yml` | `stdout`: `console.log(...)`, `process.stdout.write(...)`, `process.stderr.write(...)`; `file-write`: `fs.writeFile(...)`, `fs.writeFileSync(...)`, `fs.appendFile(...)`, `fs.createWriteStream(...)`, `fsp.writeFile(...)`; `outbound-call`: `fetch(...)`, `axios(...)`, `axios.$M(...)`, `axios.create(...)`, `Axios.create(...)`, `got(...)`, `ky(...)`, `http.request(...)`, `https.request(...)`, `new S3Client(...)`, `nodemailer.createTransport(...)`, and `$A.$M(...)` with `$A` matching `^(api\|apiClient\|client\|httpClient)$` and `$M` an HTTP verb; `message-produce`: `$Q.add(...)` on a `Queue`, `$P.send({topic: ...})`, `$CH.sendToQueue(...)`, `$CH.publish(...)`; `exit-code`: `process.exit(...)`, `process.exitCode = $X`; `error-response`: `$RES.status($N)` with `$N` a number of 400 or more, `throw new $E(...)` with `$E` matching `.*(Http\|Api).*(Exception\|Error)$` or `^(BadRequest\|NotFound\|Unauthorized\|Forbidden\|Conflict).*Exception$`, `notFound()` |
| `state.yml` | `db-connect`: `new PrismaClient(...)`, `new Pool(...)`, `new Client(...)`, `mongoose.connect(...)`, `createConnection(...)`, `new DataSource(...)`, `new Sequelize(...)`, `drizzle(...)`, `redis.createClient(...)`, `new Redis(...)`; `db-access`: `prisma.$T.$F(...)`, `$P.$queryRaw...`, `$P.$executeRaw...`, `$POOL.query(...)`, `$R.findOne(...)`, `$R.save(...)`, `knex(...)`; `global-state`: `create(...)` from zustand, `configureStore(...)`, `globalThis.$X = ...`; `cache`: `new LRUCache(...)`, `new NodeCache(...)`, `new QueryClient(...)` |
| `concurrency.yml` | `thread`: `new Worker(...)` with one path argument; `process-pool`: `child_process.fork(...)`, `child_process.spawn(...)`, `child_process.exec(...)`, `cluster.fork(...)`; `async`: `Promise.all(...)`, `Promise.allSettled(...)`, `Promise.race(...)`, `setInterval(...)`, `setImmediate(...)`; `lock`: `new Mutex(...)`, `new Semaphore(...)`; `queue`: `new Queue(...)` |
| `resilience.yml` | `retry`: `axiosRetry(...)`, `pRetry(...)`, `retry: $X` in an object; `timeout`: `timeout: $T` in an object, `AbortSignal.timeout(...)`; `catch-all`: `try { ... } catch ($E) { ... }`, `$P.catch(...)`, `process.on("uncaughtException", ...)`, `process.on("unhandledRejection", ...)`, a four-argument function whose first parameter is `err` or `error`; `transaction`: `$P.$transaction(...)`, `$C.transaction(...)` |
| `observability.yml` | `log`: `console.info(...)`, `console.warn(...)`, `console.error(...)`, `console.debug(...)`, `pino(...)`, `winston.createLogger(...)`, `$L.$M(...)` with `$L` matching `^(log\|logger)$` and `$M` a log level; `metric`: `new Counter(...)`, `new Gauge(...)`, `new Histogram(...)`, `new Summary(...)`, `statsd.$M(...)`; `trace`: `Sentry.init(...)`, `trace.getTracer(...)`, `new NodeSDK(...)` |
| `blindspot.yml` | the table above |

No new category is added, so `CATEGORY_CARD` and the home-card table stay as they are.

### D11. `symbols`

`js_tools.ScipTs.index(...)` returns one decoded index per project. `js_reduce.join_indexes(indexes)` prefixes each document's path with the project's `dir`, then concatenates the documents. One `scip_read.reduce` call then runs on the join, so references across projects survive. `scip_read.py` is not edited.

After `reduce`, `js_reduce.finish_symbols(items, exports)`:

- sets `public` to true when the def's top-level name, in its file, is in `ts_facts` `exports`, or when it is a member of a class that is (S9); with no `exports`, it keeps `reduce`'s value and the status of `typescript` is already not `ok`;
- rewrites `symbol` to drop the package name and version, so a digest does not change when `package.json`'s version does.

### D12. Candidates and completeness

No new candidate kind. `entry_points`, `io_candidates` and entity `models` flow through `assign_ids`, `home_card`, V5, A5 and `dossier candidates` unchanged. `tests`, `dead`, `graph` and `symbols` stay measured. `blindspots` go to Gaps. Knip's `dead` items carry `rule` (`knip.files`, `knip.dependencies`, `knip.exports`, `knip.types`), `type` (`unused file`, `unused dependency`, `unused export`, `unused type`), `name`, `message`, `confidence: null`, `snippet`. `v5_env` needs no change: `gather.ENV_RE` already matches `process.env.X`.

### D13. Mixed-language repositories

Both adapters run, each with its own `extract/*.json` section. `candidates.load` joins them in adapter-name order (`js`, `python`, `repo`), so a Python-only repository is unchanged. No merging code exists or is needed. Ids hash the path, and module names cannot clash, because one form holds dots and the other slashes. Reports show both languages in the same cards, in the same rows. Preflight takes the higher Node minimum, which `toolcheck._needed_min` already does. `reports.md` gets one paragraph (M4-25). `dossier check` and the card skeleton need nothing, since a card's presence depends on the schema alone. Block M proves it.

### D14. Staleness and incremental builds

- `js` keys by `sha`, version `1` and its six tools, as every adapter does. A section with a tool not `ok` is not reused, so a build without Node reruns once Node is present.
- `FEEDS["interactions"]` gains `"ui"`, with `_feed` keys `["ui", path, name, sorted(rendered files)]`. `reading` needs nothing new.
- All other JS findings flow through the existing feeds, which are line-free. Module and import keys are path-based.
- Known limit, recorded as a risk: the reuse key does not include whether a restore ran, for Python either. A build with `--no-restore` followed by a build with restore reuses `symbols` unless a tool failed.

### D15. Version

`VERSION` 0.9.0. A minor bump plans a full rebuild, which M4 needs: new adapter, new `repo` version `3`, new prompts. `repo` goes to `3` because `TEST_COMMAND` changes. The skill has no bump tool, and CI does not tag it: edit `VERSION` directly, as `d451909` did.

### D16. Sessions and cut line

| Phase | Content | Why this cut |
|---|---|---|
| 1 | Tool re-check, pins, projects, restore, fixture, adapter frame, package entries | Ends with a registered adapter on a verified install. Everything later stands on this |
| 2 | The four tools, queries, Prisma, routes, rules, V7, the fixture test of record | Ends with real `extract/*.json`. Nothing reads them yet except V7 |
| 3 | Shared readers, React table, prompts, docs, version | Everything that makes a build complete, tested on a fixture page |
| 3a | Opus: the ground truth for `RW` | Must exist before any build, and be written apart from everything else (D18) |
| 4 | The ground truth tool, the `RW` build, every verification block, the Python golden | A full build needs a clean context, and it is the exit criterion |
| 4a | Opus: rulings on block T, and the component check | Sonnet must not judge its own misses (D18) |
| 4b | Sonnet: fix what Phase 4a found. Skipped if it found nothing | Fixes need Opus's rulings first |
| 5 | The `BP` build, the mixed build, the merge | About three times `RW`'s rows, and the React checks |

`process.md` said one session, and now gives this count. M2 and M3 each took three, and M4 holds more tools than either. The split is at committed, tested boundaries. **Merge only in Phase 5.**

**Cut, in this order, only if a phase cannot finish:** M4-22 (upgrade burden: a P1 card, which then keeps its Python-only rows); the ORM forms other than Prisma in M4-12, and `zod`; Fastify and NestJS route rules; berry and pnpm restore (then a Gaps item says they are not installed). Record any cut under "Results"; it becomes the first item of the next plan.

**Never cut:** extractor fixture tests, V7 for TS/JS, the plan 008 checks on anything new, the Python golden, the `RW` ground truth, Phase 4a, the real public API, any P0 card.

### D17. The real public API (S9)

The author ruled that S9's rule stands, and that the real public API must also be identified and reported, separately. S9's `public` flag says a name is exported from its file. This says a name can be imported by another package.

**Which packages.** Every project with `exports`, `main`, `module` or `types` in `package.json`, whether or not it is marked private. A private workspace package still has an API for its siblings, and `LIB` is marked `"private": true` although it is published, because its release step rewrites the manifest. So `Audience` is `marked private` or `not marked private`, and never claims a package is or is not published. A project with none of these fields has no API. **`RW` and `BP` have none:** all four of their `package.json` files are marked private and declare none of these, so `JSFIX` and `LIB` exercise this code.

**Entries** (`js_api.entries(project, tracked, tsconfig) -> [{"package", "subpath", "file", "resolved", "audience"}]`), following Node's rules:

- `exports` takes precedence over `main`, and when it is present, nothing else in the package can be imported.
- A string or a `.`-free conditions object is subpath `.`. Otherwise each key starting `.` is a subpath. `./package.json` and any other non-code target are skipped.
- Conditions can nest. Walk them in order, depth first, and take the first target that maps to a tracked source file. One row per subpath, not per condition.
- `null` targets are excluded. `*` is expanded over the **source** files the mapping below gives, not over the target, which is usually untracked. It can span `/`. `.d.ts` files are left out. This can list a subpath that the release step does not ship, so a `*` row means importable by the manifest's rules.
- Without `exports`: `main`, then `module`, then `types`, as subpath `.`.

**Mapping built output to source.** Targets usually name files that are not tracked, such as `./dist/index.js`. In order: the target if tracked; a tsconfig `paths` entry for the package's own name plus the subpath, because that names the source directly (`LIB` has `"zustand/*": ["./src/*.ts"]`); tsconfig `outDir` swapped for `rootDir`; the same relative path under `src/`. The last two try `.ts`, `.tsx`, `.js`, `.jsx`, and remove `.d` from `.d.ts`, `.d.mts` and `.d.cts`. If all fail, `resolved` is false.

**Names.** `ts_facts.mjs` takes `"entries"` on stdin and adds `"api": [{"entry", "subpath", "name", "kind", "path", "line"}]` and `"api_unresolved": [{"entry", "subpath", "specifier"}]` to its D9 response. For each entry file it calls `checker.getExportsOfModule` on the file's module symbol, and for a symbol with `ts.SymbolFlags.Alias` it calls `checker.getAliasedSymbol`, then reads the first declaration's source file. `path` is null for a name from outside the repository, and the row says which package. `kind` is `function`, `class`, `interface`, `type`, `enum`, `variable` or `namespace`. A target the checker cannot resolve, for example `export * from` a package that was not installed, goes in `api_unresolved`, so it is never lost silently. This behaviour through `export *` chains is open fact O8.

**Items.** `symbols` kind `public-api`: `{"kind", "path", "line", "name", "symbol_kind", "package", "subpath", "audience"}`. They are measured, not candidates, so V5 does not apply (spec decision 24).

**The card.** `io.contracts` stays written by Claude, and no schema file changes. `render_card` appends `measured_tables.public_api(...)` to its body, for any entry but a pending one. Heading `Public API of each package`, table `t-io-contracts-api`: Package, Import path, Name, Kind, Defined in, Audience, Source. Import path is the package name plus the subpath. One row per name, sorted by package, subpath, name. Nothing is pruned. With no items, if any `module` item has `language: "js"`, the card adds one line: `No package here declares a public API. What this repository offers from outside is in Entry points.` A repository with no JS is byte-identical to today.

**Gaps.** Report `io`, per unresolved entry or `api_unresolved` row: `The public API of {package} could not be fully worked out from {subpath}.` How to confirm: `Read this package's entry file by hand.`

**Staleness.** `FEEDS["io"]` gains `"public_api"`, with `_feed` keys `["api", package, subpath, name, path]`. Python gives no keys, so its digest does not change.

**Not in M4.** The Python adapter must not change here, so Python gets the same report as its own change in M6, and the M5 plan proposes the C# equivalent (spec decision 42).

### D18. Who does what for the ground truth

- **Phase 3a, Opus, fresh session:** writes the truth file from the source, before any build. It reads only its own section of this plan, because the rest holds notes on `RW`.
- **Phase 4, Sonnet:** builds the dossier and runs block T. It lists disagreements and does not judge them. **It never edits the truth file.**
- **Phase 4a, Opus, fresh session:** gives every disagreement one verdict. `list wrong` amends the truth file, with the reason and a new hash. `dossier wrong` goes to Phase 4b. `blind spot` means an existing Gaps entry or blind-spot rule explains it. Opus also checks every component's paths and responsibility against the code (S1).
- **Phase 4b, Sonnet:** fixes each `dossier wrong` row, rebuilds and reruns block T. A new disagreement goes back to Phase 4a.
- **The author:** the spot-check in the hand-over, which needs no TS knowledge. It only confirms that the cited code says what the row says.

Both models are Claude, so this reduces shared blind spots and does not remove them. The figures are provisional until the author corrects dossier against work codebases (S1).

---

## Phase 1: Tools, install and projects

### Before you start (Phase 1)

Read section 2, section 3, D1 to D3, D6 and D16. Load the skills in section 2. Then:

1. `git log --oneline -5`. The top should be `3a68c36`, or a later commit that does not touch `scripts/`, `prompts/`, `rules/` or `assets/`. If it does, read the change and stop if it contradicts this plan.
2. Read sections 7 and 8. **Stop unless the author has said the second acceptance test is finished and its findings are in the spec or this plan (Q1).**
3. `node --version` must print 22.13.0 or later, with a major version of 22, 24, or 26 and above. dependency-cruiser's `engines` rule out 23 and 25, and `toolcheck` checks a minimum only, so it would not catch them. `npm --version` must print a version. If not, stop: Q2 is not done.
4. Run the suite and confirm the baseline. The Node upgrade may have moved nothing, but run `DOSSIER_SLOW=1 ... tests/integration/scripts/test_scip_slow.py` once to confirm scip-python still works on the new Node. If it fails, stop and report.
5. `git switch -c feat/dossier-m4`.

### Tasks (Phase 1)

- [x] **M4-1. Re-check the tools on this machine.**
  - Goal: prove what the documentation did not state, before any code depends on it.
  - Files: this plan only ("Results (Phase 1)").
  - Interface: none.
  - Steps, in `S=$(mktemp -d)`, with a tiny project: `a.ts` (`import { b } from './b'; export const a = b;`), `b.ts` (`import { a } from './a'; export const b = 1; export const unused = 2;`), `c.mts`, `d.cts`, `e.tsx` with a small component, `package.json`, `tsconfig.json` with `"paths": {"@/*": ["./*"]}` and a trailing comma:
    1. In `$S/n`, write D2's `package.json`, run `npm install --ignore-scripts --no-audit --no-fund`. Record whether `--ignore-scripts` broke anything (knip's `oxc` parsers come through optional packages), how many copies of `typescript` exist (`find node_modules -path '*/typescript/package.json' | wc -l`, expect 1), and the real bin of pnpm.
    2. `node n/node_modules/dependency-cruiser/bin/dependency-cruiser.mjs --info`: record that `typescript` shows as usable. Run D5's command in `$S`. Record `modules[].source`, `dependencies[].resolved`, `dependencyTypes`, `dynamic`, whether paths are relative to cwd, and whether `--ts-config` works beside `--no-config`. Then add a `.dependency-cruiser.json` with a forbidden rule that `a.ts` breaks, run line 5b, and record the fields of `summary.violations` (`from`, `to`, `rule.name`, `rule.severity` are assumed).
    3. D5's knip command in `$S`. Record the JSON: expect `{"issues": [{"file", "files"?, "dependencies", "exports": [{"name", "line", "col"}], ...}]}`. How an unused **file** is reported is not stated by the docs.
    4. scip-typescript with `--output $S/out.scip`. Then decode with `scip_read`: `python3 -c "import sys; sys.path.insert(0,'$SKILL/scripts'); import scip_read; d=scip_read.decode(open('$S/out.scip','rb').read()); r=scip_read.reduce(d); print(r[:6])"`. Record whether occurrences use field 1 or the typed ranges, the symbol format, and whether `public`-style depth makes sense.
    5. `npx`-free TypeScript API: `node -e` importing `typescript` from `n/`, then `ts.createProgram` on `a.ts`. Record that it runs on Node 22 or later.
    6. tree-sitter: with `uv run --locked --python 3.13 --script $SKILL/scripts/ts_worker.py`, send `{"language": "typescript", ...}`, then `tsx` and `javascript`, with D8's `COMPLEXITY_Q`. Record that the three names and every node name in D8 are accepted.
    7. semgrep: in `$S/r`, a rule file `t.yml` with `languages: [js, ts]` and `pattern: fetch(...)`; files `t.ts` and `t.tsx` with `// ruleid: t` before a call. Run `semgrep --test` as the worker does. Record that `// ruleid:` works (the docs show only `#`), that a `.tsx` target is found for a rule file of that stem, and whether both `.ts` and `.tsx` targets can sit beside one rule file. Then scan `c.mts`, `d.cts` and a `.d.ts` by explicit path, and record which are parsed.
    8. Restores, in throwaway folders with one tiny dependency, through `sandbox.run` with a scratch area: yarn classic, berry and pnpm commands from D3. Assert that no folder outside the scratch area was written, and record whether `npm_config_store_dir` moved pnpm's store (O1).
  - Stop condition: if step 1, 2, 4 or 5 fails, stop and record the output.
  - Done-check: "Results (Phase 1)" has one line per step with the values seen.
  - Commit: `docs(dossier): record the M4 tool re-check in plan 010`

- [x] **M4-2. Pin and install the Node tools.**
  - Goal: D2.
  - Files: new `scripts/node/js-tools/package.json`, `package-lock.json`, `ts_facts.mjs` (a stub printing `{}`), `scripts/js_tools.py`, `tests/unit/scripts/test_js_tools.py`, `tests/integration/scripts/test_js_tools_slow.py`; edit `scripts/tools.json`, `tests/unit/scripts/test_toolcheck.py`.
  - Interface: `install_dir(cache_root, lock_sha) -> Path`; `ensure_installed(run, cache_root, timeout) -> Path`; `node_problem(run) -> str | None`.
  - Steps: (1) Tests: the lock's `packages["node_modules/<name>"].version` equals `tools.json` for all seven packages; `typescript` is at the top level only; `node.min.js` is `22.13.0`; a fake `run` shows `npm ci` runs once and not again when the marker matches, and again when `ts_facts.mjs` changes; `node_problem` with fake outputs returns each of the three results. (2) Generate the lock in a scratch copy with `npm install --package-lock-only --ignore-scripts --no-audit --no-fund` and copy it back. (3) Implement, reusing `scip_tool._check`. (4) Edit `tools.json` as D2 says.
  - Done-check: `uv run --with pytest --with pygments python -m pytest tests/unit/scripts/test_js_tools.py tests/unit/scripts/test_toolcheck.py -q` passes; `DOSSIER_SLOW=1 ... tests/integration/scripts/test_js_tools_slow.py` passes (real install, then `node <dir>/node_modules/knip/bin/knip.js --version` prints 6.42.1); `uv run scripts/dossier.py doctor --all` lists the tools "from a lockfile with npm".
  - Commit: `feat(dossier): pin the JavaScript tools in a shipped lockfile`

- [x] **M4-3. Find projects and workspaces.**
  - Goal: D3, rules 1 to 6, and D4's `source_roots`.
  - Files: new `scripts/js_project.py`, `tests/unit/scripts/test_js_project.py`.
  - Interface: `read_json(read, path) -> dict | None`, tolerant of bad JSON; `projects(tree, read) -> list[dict]`; `source_roots(projects, tree) -> list[dict]`; `manifest_frameworks(projects, read) -> list[str]` (D6's Gaps names, sorted).
  - Steps: tests on hand-made trees, then implement. Cases: `RW`'s shape (root package, `package-lock.json`, `src/`, `e2e/project.json`); `BP`'s shape (root package with no lockfile and no files, three apps with `yarn.lock`, giving three projects and root `apps`); an npm workspace (`workspaces: ["packages/*"]`) as one project with members; `workspaces: {"packages": [...]}`; `pnpm-workspace.yaml`; no `package.json` at all; a package under `node_modules` ignored; `bun.lockb` gives `manager: "bun"`.
  - Done-check: `... pytest tests/unit/scripts/test_js_project.py -q` passes.
  - Commit: `feat(dossier): find JavaScript projects and workspaces`

- [x] **M4-4. Restore npm, yarn and pnpm, in any project folder.**
  - Goal: D3's restore and hygiene.
  - Files: edit `scripts/tools.json`, `scripts/restore.py`, `scripts/stages.py`, `scripts/sandbox.py`, `tests/unit/scripts/test_restore.py`, `tests/unit/scripts/test_sandbox.py`, `tests/integration/scripts/test_hygiene.py`.
  - Interface: `restore.plans(tree, tools, checkout=None)`; plans gain `dir` and `auth`.
  - Steps: (1) Tests: a nested `yarn.lock` gives a plan with `dir`; `uv.lock` below the root gives none; `__metadata:` picks `berry_command`; `{js_tools}` is expanded after `ensure_installed`; `restored["yarn"]` is false when one of two plans failed; a root Python plan's result and reason are unchanged; the new names are in `ALLOWED_NAMES` and `build_env` puts yarn and pnpm caches under `<area>/cache/`. (2) `test_hygiene.py:151` uses npm to show a disabled ecosystem; change it to `nuget`. (3) Implement. (4) A hygiene test that an npm install script does **not** run: a fixture dependency in a local `file:` package whose `postinstall` writes a marker; after `npm ci --ignore-scripts`, no marker exists.
  - Done-check: `... pytest tests/unit/scripts/test_restore.py tests/unit/scripts/test_sandbox.py tests/integration/scripts/test_hygiene.py -q` passes.
  - Commit: `feat(dossier): install npm, yarn and pnpm packages from their lockfiles`

- [x] **M4-5. The JS fixture repository.**
  - Goal: a small repository with known answers, so each extractor has an exact expected output.
  - Files: new `tests/fixtures/jsrepo/**`, `tests/unit/scripts/test_jsfixture.py`; edit `tests/conftest.py`.
  - Interface: `build_js_repo(dest)` and fixture `js_repo(tmp_path)`, like `build_py_repo`. `line_of` works unchanged. JSON cannot hold markers, so add `key_line(root, rel, key)`: the first line containing `"<key>"`.
  - Content (every line a test must find carries `// @<name>`, keep each file under 40 lines):
    - Root `package.json`: name `shopjs`, `workspaces: ["packages/*"]`, `bin: {"shopjs": "dist/cli.js"}`, `main: "dist/main.js"`, scripts `start` and `test`, `prisma: {"seed": "ts-node prisma/seed.ts"}`, dependency `express`. `package-lock.json` that lists `express` as a `file:` stub under `stubs/express/`, so a test install needs no network. `tsconfig.json` with `paths` `@/*` and `references` to `tsconfig.app.json`, with a trailing comma. `project.json` with targets `serve` and `build`. `Dockerfile` (`CMD ["node", "dist/main.js"]`). `.github/workflows/ci.yml` with `run: npx jest` (`# @ci-jest`). `.dependency-cruiser.json` with one forbidden rule that `src/users/service.ts` importing `src/main.ts` breaks. `jest.config.ts` with `coverageThreshold`. `.env.example`. `.eslintrc.json`, `.prettierrc`.
    - `prisma/schema.prisma`: datasource with `env("DATABASE_URL")` (`// @prisma-env`), models `User` (`// @model-user`), `Post` with a relation, enum `Role`, a `@@index` line. `prisma/migrations/0001_init/migration.sql`.
    - `src/main.ts`: `express()`, `app.use(routes)`, `app.get('/', ...)` (`// @ep-root`), `process.env.PORT` (`// @io-env`), `app.listen(...)` (`// @ep-listen`), `console.info` (`// @io-log`).
    - `src/routes.ts`: `Router().use('/api', api)` (`// @bs-mount`). `src/users/controller.ts`: `router.get('/users', ...)` (`// @ep-get`), a multi-line `router.post(\n  '/users',` (`// @ep-post` on the call line), `router[verb]('/x', h)` and `router.get(path, h)` (`// @bs-route`), `res.status(404)` (`// @io-error`), `map.get('users')` as a near miss (`// @not-route`).
    - `src/users/service.ts`: `prisma.user.findMany()` (`// @io-db`), `fetch(url, {timeout: 5})` (`// @io-outbound`), `prisma.$transaction(...)` (`// @fail-tx`), `try/catch` (`// @fail-catch`), and an import of `src/main.ts` (`// @import-up`).
    - `src/db.ts`: `new PrismaClient()` (`// @io-db-connect`). `src/a.ts`, `src/b.ts`: an import cycle (`// @cycle-a`, `// @cycle-b`). `src/c.ts`, `src/d.ts`: a cycle through `import type` only. `src/types.ts`: exported `interface Order` (`// @model-order`), `type Item = {...}` (`// @model-item`), `enum Status`, `interface ButtonProps`, non-exported `interface Local`. `src/orm.ts`: a `@Entity()` class with `@Column()` fields. `src/barrel/index.ts`: `export * from '../a'` (`// @bs-barrel`). `src/unused.ts`: nothing imports it. `src/plugins.ts`: `` import(`./${name}`) `` (`// @bs-import`), `require(name)` (`// @bs-require`), `container.bind(X)` (`// @bs-di`). `src/state.ts`: `export let current = null` (`// @state-let`), `const cache = new Map()` (`// @state-map`), `const NAMES = {a: 1}` (a constant, not state). `src/cli.ts`: `program.command('sync')` (`// @ep-cli`), `process.exit(1)` (`// @io-exit`). `src/jobs.ts`: `cron.schedule(...)` (`// @ep-cron`), `new Worker('mail', fn)` (`// @ep-queue`). `src/flags.ts`: `launchdarkly` (`// @bs-flag`).
    - `packages/web/`: `package.json` (dependencies `react`, `react-router`), `src/router.tsx` with `createBrowserRouter`, a literal path (`// @ui-literal`), a path through a constant object in `src/paths.ts` (`// @ui-constant`), a computed path (`// @ui-computed`), and `lazy: () => import('./pages/Home')`. `src/pages/Home.tsx`, `src/App.tsx` rendering `Home` and `Button`, `src/Button.tsx`, `src/context.tsx` with `createContext` (`// @bs-context`) and `export function useCart` (`// @bs-hook`), a `<CartContext.Provider>`. `src/App.test.tsx` under vitest: `it`, `it.skip`, `vi.mock`. `src/Button.stories.tsx`. `vite.config.ts`.
    - `packages/site/`: `package.json` (dependency `next`), `app/page.tsx`, `app/(shop)/items/[id]/page.tsx`, `app/api/ping/route.ts`, `pages/about.tsx`, `pages/_app.tsx`.
    - `packages/lib/` (D17): `package.json` with name `@shopjs/lib`, `exports` holding `"."` as conditions (`types` then `import`, both under `dist/`), `"./utils/*": "./src/utils/*.ts"` and `"./internal/*": null`. `tsconfig.json` with `outDir: dist`, `rootDir: src`. `src/index.ts`: `export { sum } from './math'` (`// @api-reexport`), `export { twice as double } from './math'` (`// @api-rename`), `export * from './barrel'`, `export const version = '1'` (`// @api-own`). `src/barrel.ts`: `export * from './deep'`. `src/deep.ts`: `export function deep` (`// @api-deep`). `src/math.ts`: `export function sum`, `export function twice`, and `export function hidden` (`// @api-hidden`), which is public by S9 but not in the API. `src/utils/fmt.ts`: `export function fmt` (`// @api-wild`). `src/internal/x.ts`: an export that must not appear. `packages/web/` has no such field, so it gives no API.
    - `tests/users.test.ts`: `describe`, `it`, `test.todo`, `jest.mock`, `beforeEach`, importing `src/users/service.ts`. `e2e/smoke.spec.ts`: Playwright.
  - Steps: (1) `test_jsfixture.py` asserts each marker named above appears once. (2) Write the fixture. It is original code, not copied from `RW` or `BP`.
  - Done-check: `... pytest tests/unit/scripts/test_jsfixture.py -q` passes.
  - Commit: `test(dossier): add the JavaScript fixture repository`

- [x] **M4-6. Adapter frame and package entries.**
  - Goal: a registered adapter that yields `entry_points` from project files and handles the gates.
  - Files: new `scripts/js_adapter.py`, `scripts/js_entries.py`, `tests/unit/scripts/test_js_adapter.py`, `tests/unit/scripts/test_js_entries.py`; edit `scripts/adapters.py`.
  - Interface: `JsAdapter` as D1. `js_entries.package_entries(project, read) -> list[dict]`, `nx_targets(tree, read)`, `next_routes(files, project)`. In `_registered()` the tuple becomes `(JsAdapter, PythonAdapter, RepoAdapter)`.
  - Steps: (1) Tests on `JSFIX`: `shopjs` bin, `start` and `test` scripts, `prisma seed`, `main`, the two Nx targets, each at its `key_line`; Next routes `/`, `/items/[id]`, `API /api/ping`, `/about`, and no `_app`; `detect(["TypeScript"])` includes `js`, and `detect(["Python"])` does not; a fake run shows Node tools `skipped` with the fixed reason when `ctx.trusted` is false and when Node is too old, while the pure steps still give items. (2) Implement with stub steps for the tools, each recording `skipped`, `Arrives in a later task.` (3) Run the full suite: `test_prepare_cli.py` may gain a `js` adapter only on repositories with JS.
  - Done-check: full suite passes, `... pytest tests/unit/scripts/test_js_entries.py tests/unit/scripts/test_js_adapter.py -q` passes.
  - Commit: `feat(dossier): add the JavaScript adapter frame and package entry points`

### Deliverables and checks (Phase 1)

| Deliverable | Checked by |
|---|---|
| Tool facts | M4-1 results lines |
| Lockfile install | `test_js_tools_slow.py` |
| Projects | `test_js_project.py` |
| Restores and hygiene | `test_restore.py`, `test_hygiene.py` |
| Fixture | `test_jsfixture.py` |
| Adapter frame | `test_js_adapter.py` |

### Cut line (Phase 1)

Berry and pnpm restores may move to Phase 3 (D16), with yarn classic and npm kept. **Never cut** M4-1, M4-2, M4-3, M4-5.

### Acceptance criteria (Phase 1)

- The full suite passes, and with `DOSSIER_SLOW=1` every slow test passes, except G2's known failure.
- `prepare` on `js_repo` with `--no-restore`, run by a slow test, gives `extract/entry_points.json` with a `js` section.
- Python output is unchanged: `test_py_adapter_slow.py` passes with no edit to it.

### Branch and release (Phase 1)

Commit each task on `feat/dossier-m4`. Do not merge or bump the version. Write "Results (Phase 1)" and commit it: `docs(dossier): record phase 1 of M4 in plan 010`.

### Results (Phase 1)

Host: Node 26.13.0 (fnm), npm 11.20.0. This session's shell still resolved `/usr/bin/node` 20.19.2, so commands put the fnm Node first on `PATH`. Baseline on `main` after the Node upgrade: 1434 passed, 66 skipped (the plan's 1426 predates the post-M3 report rework, which touched `render.py`, assets and `measured_change.py` and does not contradict this plan). `test_scip_slow.py` passes on Node 26.

**M4-1 (tool re-check, 2026-11-07).**

1. `npm install --ignore-scripts` of D2's package.json: 72 packages, nothing broke (knip's `@oxc-parser/binding-linux-x64-gnu` came through). One copy of `typescript` (6.0.3). knip prints 6.42.1. pnpm's bin is `bin/pnpm.mjs` (12.x too); yarn is `bin/yarn.js`; berry is `@yarnpkg/cli-dist/bin/yarn.js`.
2. `depcruise --info` shows `typescript >=2.0.0 <7.0.0 -> 6.0.3` usable. D5's command works with `--ts-config` beside `--no-config` (O7: yes; the `@/*` alias resolved: `dependencyTypes` has `aliased-tsconfig`). `modules[].source` and `dependencies[].resolved` are relative to cwd. `.d.ts` files are listed as modules. A type-only import has `dependencyTypes` containing `type-only` (there is no `typeOnly` key). `dynamic` is a boolean on each dependency. Line 5b: `summary.violations` is a list of `{type, from, to, unresolvedTo, dependencyTypes, rule: {severity, name}}`, as assumed.
3. knip JSON is `{"issues": [{"file", "files": [{"name"}], "dependencies", "devDependencies", "exports", "optionalPeerDependencies", "types", ...}]}`. O6: an unused file is an issue whose `files` list is non-empty (`files: [{"name": "a.ts"}]`, same path as `file`). Exit 0 with `--no-exit-code`.
4. scip-typescript 0.5.2 with `--output <abs path>` works (about 2 KB). `scip_read.decode` and `reduce` read it unchanged. Symbols look like ``scip-typescript npm tiny 1.0.0 `a.ts`/a.`` : package name and version are inside the string, so D11's rewrite is needed. Each file also gives a `type: "module"` def named after the file, and `public` is true for everything, so D11's `finish_symbols` is needed.
5. `ts.createProgram` runs on Node 26 and finds the imported file.
6. Tree-sitter (`ts_worker.py`): `typescript`, `tsx` and `javascript` are accepted (O3). D8's complexity query, with all nine node types and the `operator: ["&&" "||" "??"]` form, gives 6, 3 and 6 matches on small samples, as counted by hand.
7. Semgrep: `// ruleid:` works for `.ts` and `.tsx` (O4). A `.ts` and a `.tsx` target can sit beside one rule file, and `semgrep --test` passes. **`.mts` and `.cts` are NOT scanned (O5):** no result, no error. **`.d.ts` IS scanned**, so it must be excluded by the adapter. So D10's fixed Gaps item for `.mts` and `.cts` is needed, and M4-15 adds it.
8. Restores through `sandbox.run`, with a scratch area: yarn classic (`--frozen-lockfile`), berry (`--immutable --mode=skip-build`) and pnpm (`--frozen-lockfile`) all exit 0 and write `node_modules`. Their caches landed in `<area>/home/.cache/yarn`, `.yarn/berry` and `.cache/pnpm` (HOME is already redirected), and nothing outside the scratch folders was written. A `yarn.lock` from berry contains `__metadata`, classic does not. **O1: `npm_config_store_dir` did not move pnpm's store** (the folder was never created), so M4-4 passes `--store-dir <area>/cache/pnpm` on the command line. **O2:** with `packageManager: pnpm@9.0.0` in `package.json`, pnpm 12.15.0 still ran as 12.15.0 (not re-run on a fresh install).

**M4-2 (pins and install).** Done as written. One deviation: `sandbox._host_path` did not do what risk 12 assumed. It adds each host tool's folder in `tools.json` order, and `git` (first) lives in `/usr/bin`, so `/usr/bin` came first and `node` inside every sandboxed command resolved to the system Node 20.19.2 even with fnm's Node 26 first on the caller's `PATH`. The slow install test caught it (`node_problem` said "Node 20.19.2 is too old"). Fixed in `sandbox._host_path`: folders outside `SAFE_PATH` now come before the system folders; the order among system folders is unchanged, so Python-only machines get the same `PATH`. Tests: `TestHostPath` in `test_sandbox.py`.

**M4-4 (restore).** Done as written, with one change that M4-1 forced (O1): `npm_config_store_dir` is **not** added to `ALLOWED_NAMES` because pnpm ignores it. The pnpm command carries `--store-dir {pnpm_store}` instead, and `restore.run` expands the token to `<area>/cache/pnpm`. The three yarn names are added as planned. A real run through `restore.plans` and `restore.run` on tiny yarn classic, yarn berry and pnpm projects succeeded, with the berry lockfile picking `berry_command` (checked by hand, not committed as a test because it needs the network). Added `restore.restored(results)` (used by `stages.stage_copy`) so the "every plan of the ecosystem succeeded" rule has a unit test. `test_hygiene.py` gained a test with a control: the same `file:` dependency's `postinstall` does run under plain `npm ci` and does not under the restore command.

**M4-5 (fixture).** Written as listed, with these differences, all small: (1) `stubs/{express,react,react-router,next}/package.json` exist so the committed `package-lock.json` is a real lockfile for the whole workspace and `npm ci --offline` works (checked once by hand). (2) `import-up` in `service.ts` is `import type { Port } from '../main'`: a runtime import would close a cycle main, routes, controller, service, main and add a third cycle to the two the plan lists. The dependency-cruiser rule still matches a type-only edge (M4-1). (3) `router[verb]('/x', h)` carries no marker: only `router.get(path, h)` has `@bs-route`, since a marker must appear once and the first form is not matched by `string-route`. (4) Extra markers: `model-orm`, `test-mock`, `test-todo`, `test-vi-mock`, `test-skip`. (5) `conftest.py` gained `JSFIX`, `build_js_repo`, `js_repo` and `key_line`; `build_py_repo` now shares `_commit_fixture` with it and behaves the same. The fixture has 64 files, all tracked.

**M4-6 (adapter frame).** Done as written. `next_routes(files, project)` takes `project = {"dir": <package folder>}` (the member package that depends on `next`, not the install project), because in a workspace the Next package is a member. A bin entry's line is the line of the bin name inside `bin` (the plan only said "key_line"), and a `package-main` entry is named by its target; `exports["."]` as a conditions object uses its first string target in key order (`types` first for the `lib` fixture package). The frame records all six tools as `skipped`: the four Node tools with the gate's reason (untrusted ref, Node missing, Node too old) and every tool with `Arrives in a later task.` when the gate passes. `source-root` graph items are left for Phase 2 (the plan lists them under D4, not M4-6).

**Phase 1 checks.** Fast suite: 1589 passed, 67 skipped. Slow: new `test_js_adapter_slow.py` (extract of the fixture gives `extract/entry_points.json` with a `js` section) and `test_js_tools_slow.py` pass. `test_check_page_slow.py::TestLayoutChecks::test_overlapping_paragraphs_are_reported` fails, and also fails on `main` (checked by switching branches), so it is not caused by M4; it joins G2 as a known failure for the author (it was not in the plan's list).

---

## Phase 2: Extractors, rules and V7

### Before you start (Phase 2)

Read section 2, D1, D4 to D12, and "Results (Phase 1)", especially M4-1's values. **Where M4-1 recorded a real field name or flag that differs from this plan, use what it recorded, and say so in "Results".** Load the skills in section 2. `git switch feat/dossier-m4`. Do first any task moved here.

### Tasks (Phase 2)

- [x] **M4-7. `ts_facts.mjs` and its client.**
  - Goal: D9: types, exports, imports, components, routes.
  - Files: edit `scripts/node/js-tools/ts_facts.mjs`, `scripts/js_tools.py`; new `tests/integration/scripts/test_ts_facts_slow.py`.
  - Interface: `js_tools.TsFacts(run, install, timeout).facts(project_dir, files) -> dict`, the D9 response. Raises `ToolError` on non-zero, timeout or bad JSON.
  - Steps: (1) Slow test on `js_repo`: `types` holds `Order`, `Item`, `Status`, `ButtonProps`, `Local` with `exported` correct and fields at their lines; `exports` holds `a`; `imports` holds the `import type` line with `type_only` true, and `` import(`./${name}`) `` is not in `imports`; for `packages/web`, `components` holds `App` with `renders` naming `Button` and its file, `provides` naming `CartContext`; `routes` holds the literal route, the constant one resolved to its value, the computed one with `resolved: false`, and a `file` for the lazy import; an `extends` of a missing package gives an `errors` line and still gives results; `config.used` is `tsconfig.app.json` when the root has `references` and no `paths`, in a `tmp_path` case. (2) Write the script as plain ES module JavaScript. Keep it under about 400 lines; it is one file so the install stays simple, and it is outside the 300-line guide because it is not Python. (3) Client through `ctx.run(..., profile="restricted", input=...)`.
  - Done-check: `DOSSIER_SLOW=1 uv run --with pytest --with pygments python -m pytest tests/integration/scripts/test_ts_facts_slow.py -q` passes.
  - Commit: `feat(dossier): read types, exports, components and routes with the TypeScript compiler API`

- [x] **M4-8. dependency-cruiser and the graph.**
  - Goal: D4 and D5 lines 5 and 5b.
  - Files: edit `scripts/js_tools.py`, `scripts/js_adapter.py`; new `scripts/js_reduce.py`, `tests/unit/scripts/test_js_reduce.py`, `tests/fixtures/js_tools/depcruise.json` (a small output hand-written in the shape M4-1 recorded).
  - Interface: `DepCruiser.cruise(project_dir, tsconfig) -> dict`; `DepCruiser.violations(project_dir, config_file) -> list`; `js_reduce.graph_items(cruise, project, tree, imports, test_re) -> (items, test_edges)`; `js_reduce.contract_items(violations, rule_names, config_path) -> list`; `js_reduce.module_name(path, siblings) -> str`, `short_name(path) -> str`.
  - Steps: (1) Unit tests: a module item per tracked non-test file, none for `.d.ts`; `index.ts` has `short` of its folder; `auth.ts` beside `auth.tsx` gets full paths; edges to `node_modules` dropped; edges from a test file go to `test_edges`; `lines` joined from `imports` by file and specifier; `type_only` from `dependencyTypes`; `cycle` counts `a.ts`, `b.ts` and not `c.ts`, `d.ts`. (2) Implement. (3) Slow check is in M4-17.
  - Done-check: `... pytest tests/unit/scripts/test_js_reduce.py -q` passes.
  - Commit: `feat(dossier): build the JavaScript import graph with dependency-cruiser`

- [x] **M4-9. knip.**
  - Goal: `dead` items (D12).
  - Files: edit `scripts/js_tools.py`, `scripts/js_reduce.py`, `scripts/js_adapter.py`, `tests/unit/scripts/test_js_reduce.py`; new `tests/fixtures/js_tools/knip.json`.
  - Interface: `Knip.run(project_dir) -> dict`; `js_reduce.dead_items(knip, project) -> list`.
  - Steps: tests on the saved JSON in M4-1's shape: an unused file, an unused export with `line`, an unused type, an unused dependency (path `package.json`), paths prefixed with `dir`, `confidence` null; exit 2 raises `ToolError` with the first stderr line. Implement.
  - Done-check: `... pytest tests/unit/scripts/test_js_reduce.py -q` passes.
  - Commit: `feat(dossier): list unused JavaScript code with knip`

- [x] **M4-10. scip-typescript.**
  - Goal: D11.
  - Files: edit `scripts/js_tools.py`, `scripts/js_reduce.py`, `scripts/js_adapter.py`, `tests/unit/scripts/test_js_reduce.py`; new `tests/integration/scripts/test_scip_ts_slow.py`.
  - Interface: `ScipTs.index(project_dir, area, n, has_tsconfig) -> Path`; `js_reduce.join_indexes(pairs) -> dict`, with pairs of `(dir, decoded index)`; `js_reduce.finish_symbols(items, exports) -> list`.
  - Steps: (1) Unit: two hand-made decoded indexes in two projects give prefixed paths and one `ref-edge` across them; `public` follows `exports`; symbols lose package and version. (2) Slow on `js_repo`: `src/main.ts`'s defs appear, a `ref-edge` from `src/users/controller.ts` to `src/users/service.ts` exists, no `*.scip` is in the checkout. (3) `scip_read.py` is not edited. If M4-1 showed it cannot read this tool's output, stop and report.
  - Done-check: `DOSSIER_SLOW=1 ... tests/integration/scripts/test_scip_ts_slow.py -q` passes.
  - Commit: `feat(dossier): run a locked scip-typescript and read its index`

- [x] **M4-11. Tests, complexity and module state.**
  - Goal: D8.
  - Files: new `scripts/js_queries.py`, `tests/unit/scripts/test_js_queries.py`, `tests/integration/scripts/test_js_queries_slow.py`; edit `scripts/js_adapter.py`.
  - Interface: `by_grammar(files) -> dict`; `tests(ts, files, runner_of) -> list`; `assemble_tests(matches_by_file, runner_of) -> list`; `complexity(ts, files) -> dict`; `module_state(ts, files) -> list`; `test_configs(tree, read) -> list`.
  - Steps: unit tests on hand-made matches for each count and each framework rule. Slow on `js_repo`: `tests/users.test.ts` has `tests: 1`, `skips: 1` (the `todo`), `mocks >= 1`, `fixtures: 1`, framework `jest`; `packages/web/src/App.test.tsx` is `vitest` with one skip; `e2e/smoke.spec.ts` is `playwright`, kind `e2e`; `module_state` gives `current` and `cache`, not `NAMES`; a config item for jest holds `coverage_threshold`; complexity of `src/users/service.ts` is above 0.
  - Done-check: both test files pass, the second with `DOSSIER_SLOW=1`.
  - Commit: `feat(dossier): extract JavaScript tests, complexity and module state with tree-sitter`

- [x] **M4-12. Prisma and the other models.**
  - Goal: D7.
  - Files: new `scripts/js_prisma.py`, `tests/unit/scripts/test_js_prisma.py`; edit `scripts/js_reduce.py`, `scripts/js_adapter.py`, `scripts/measured_er.py`, `tests/unit/scripts/test_js_reduce.py`, `tests/unit/scripts/test_measured_er.py`.
  - Interface: `js_prisma.parse(path, text) -> {"models": [...], "io": [...]}`; `js_reduce.model_items(types, tree) -> list`; `measured_er.family(entity) -> str`.
  - Steps: (1) Tests: `User`, `Post`, `Role` with fields, `pk`, `ref` through `Post[]` and `User?`; `@@index` is not a field; `Low = "low"` enum form; `env("DATABASE_URL")` gives `env-var` with `detail`; `model_items` keeps `Order`, `Item`, `Status` and the `@Entity` class, and drops `ButtonProps`, `Local`, anything in a test; the ER card joins a Prisma `Post.author` to Prisma `User` although an interface `User` sorts first; a Python-only extract gives the same relations as before (assert against today's output). (2) Implement.
  - Done-check: `... pytest tests/unit/scripts/test_js_prisma.py tests/unit/scripts/test_measured_er.py tests/unit/scripts/test_js_reduce.py -q` passes.
  - Commit: `feat(dossier): read Prisma schemas and TypeScript entities`

- [x] **M4-13. React items and UI routes.**
  - Goal: D9's items.
  - Files: edit `scripts/js_reduce.py`, `scripts/js_adapter.py`, `tests/unit/scripts/test_js_reduce.py`.
  - Interface: `js_reduce.ui_items(components, tree) -> list`; `js_reduce.route_entries(routes) -> list`; `route_parts(detail) -> (method, path)`.
  - Steps: tests: a component with a `renders` target gives one `renders` item and one `ref-edge`; a target outside the tree gives none; a route gives kind `ui-route`, trigger as D6, `target` = `file`, and an unresolved route keeps its source text as `name`; `route_parts("get('/tags")` is `("GET", "/tags")`. Implement.
  - Done-check: `... pytest tests/unit/scripts/test_js_reduce.py -q` passes.
  - Commit: `feat(dossier): record React components and browser routes`

- [x] **M4-13a. Find the real public API.**
  - Goal: D17's entries, names and items.
  - Files: new `scripts/js_api.py`, `tests/unit/scripts/test_js_api.py`; edit `scripts/node/js-tools/ts_facts.mjs`, `scripts/js_tools.py`, `tests/integration/scripts/test_ts_facts_slow.py`, and the adapter's `symbols` step.
  - Interface: `js_api.entries(project, tracked, tsconfig) -> list`; `js_api.items(entries, api, unresolved) -> list`.
  - Steps: (1) Unit tests on `entries`: `exports` beats `main`; nested conditions give one row; `./package.json` is skipped; `null` is excluded; `*` expands over source files across folders, without `.d.ts`; a target maps through a `paths` entry, and `./dist/index.js` maps to `src/index.ts` through `outDir` and `rootDir`; an unmappable target gives `resolved: false`; `private` sets `audience`; no fields gives no rows. (2) Slow test on `js_repo`: `@shopjs/lib` lists `sum`, `double` (not `twice`), `version`, `deep` (through two `export *` hops, with `path` at `src/deep.ts`) and `fmt` under `./utils/fmt`, and does not list `hidden` or anything from `src/internal/`. (3) Record the result of O8 under "Results (Phase 2)". If `export *` does not behave as D17 says, follow the chain by hand with `getImmediateAliasedSymbol`, and say so. (4) Implement.
  - Done-check: `... pytest tests/unit/scripts/test_js_api.py -q` passes, and so does `test_ts_facts_slow.py` under `DOSSIER_SLOW=1`.
  - Commit: `feat(dossier): find what each JavaScript package really exports`

- [x] **M4-14. The JS semgrep rules.**
  - Goal: D10's rule files, each proven to fire and not to fire.
  - Files: new `rules/js/{entry,inputs,outputs,state,concurrency,resilience,observability}.yml`, `tests/fixtures/semgrep/js/*`; edit `tests/unit/scripts/test_rules.py`, `scripts/js_adapter.py`, `rules/README.md`.
  - Interface: results route as in `py_adapter._semgrep`: `family` is `r["rule"].split(".")[2]`. A `http-route` item uses `route_parts`, and its `snippet` is `{METHOD} {path}`.
  - Steps: (1) Generalise `test_rules.py`: scopes become `{"python", "all", "js"}`; `annotations` accepts `#` and `//`; `target_of` finds `.py`, `.ts` or `.tsx` by what exists; `BLIND_SPOTS` gains D10's ids. (2) Write the rules and targets, with a `// ruleid:` and a `// ok:` for every rule. Near misses to include: `map.get('x')` and `axios.get(u)` under `http-route`, `cart.log('x')` under `log`, `fs.writeFile` under `file-read`. A line matched by two rules takes one comma-separated annotation (plan 007, M2-7). (3) `metavariable-regex` is anchored at the start of the value, so write `.*(...)` for a suffix or infix match (plan 007). (4) Semgrep hides metavariables without a login: `detail` is a regular expression over the matched text, never a metavariable name.
  - Done-check: `... pytest tests/unit/scripts/test_rules.py -q` passes; `DOSSIER_SLOW=1 ... tests/integration/scripts/test_shared_layer.py -q` passes.
  - Commit: `feat(dossier): add the JavaScript and TypeScript semgrep rules with tests`

- [x] **M4-15. V7 for TS/JS.**
  - Goal: D10: blind-spot rules, wording, fixed items.
  - Files: new `rules/js/blindspot.yml`, `tests/fixtures/semgrep/js/blindspot.ts`; edit `scripts/checks_v7.py`, `scripts/checks.py`, `scripts/js_adapter.py`, `rules/README.md`, `tests/unit/scripts/test_checks_v7.py`, `tests/unit/scripts/test_checks_gaps.py`.
  - Interface: `blindspots` items as Python's. `js_adapter` records each unsupported framework and each Bun project as a `graph` item of kind `js-note`: `{"kind": "js-note", "path": "package.json", "note": "framework" or "bun", "name": ...}`. `checks.js_coverage(extract) -> list` turns those items into D10's fixed Gaps items, and adds the stale-flags item.
  - Steps: (1) Tests: one Gaps item per (pattern, file) with D10's wording and report; a literal `import('./x')` gives no `dynamic-import` hit; the Python stale-flag item appears only with a Python module, and the JS one only with a JS module, both for a mixed extract; a manifest naming `koa` gives the framework item; every D10 id is in `BLIND_SPOTS`. (2) Implement. Existing Python wording and ids do not change.
  - Done-check: `... pytest tests/unit/scripts/test_checks_v7.py tests/unit/scripts/test_checks_gaps.py tests/unit/scripts/test_rules.py -q` passes, and the slow `test_shared_layer.py` passes.
  - Commit: `feat(dossier): find the JavaScript blind spots and record them in Gaps`

- [x] **M4-16. Repository adapter: JS test commands.**
  - Goal: CI test commands for JS runners.
  - Files: edit `scripts/repo_adapter.py`, `tests/unit/scripts/test_repo_adapter.py`.
  - Interface: `TEST_COMMAND = re.compile(r"\b(pytest|tox|nox|jest|vitest|mocha)\b|make test\b|\bplaywright test\b|\bcypress run\b|\b(npm|yarn|pnpm)( run)? test\b|\bnx test\b")`. `RepoAdapter.version` becomes `"3"`.
  - Steps: tests for each alternative, plus `pytest -q` still matching, `npm run build` not matching, and `npm run test-e2e` matching (the `\b` stops at the hyphen, which is wanted: it is a test command). Implement.
  - Done-check: `... pytest tests/unit/scripts/test_repo_adapter.py -q` passes.
  - Commit: `feat(dossier): recognise JavaScript test commands in CI files`

- [x] **M4-17. The fixture test of record.**
  - Goal: prove all eight outputs on `JSFIX`, end to end.
  - Files: new `tests/integration/scripts/test_js_adapter_slow.py`.
  - Interface: runs `stages.stage_extract` on `js_repo` after `workarea.ensure_checkout`, with `DOSSIER_*` under `tmp_path`, then asserts on `extract/*.json`, including D17's `public-api` items.
  - Steps: assert:
    - `entry_points`: exactly the list in M4-5's markers and keys, by kind and line, and no item at `@not-route`. Build the expected list in the test, and fail on any extra.
    - `graph`: the `a`, `b` cycle and no `c`, `d` cycle; the `.dependency-cruiser.json` rule `broken` with the `import-up` edge; no test file as a `module`; `@/` aliases resolved; a `source-root` item per D4.
    - `symbols`: defs, a `ref-edge` and correct `public`. `io_candidates`: each `@io-*`, `@fail-*` and `@state-*` marker with its category, and `DATABASE_URL`. `models`: the D7 list. `tests`: the three test files, the configs, the `ci-command`. `dead`: `src/unused.ts` and an unused export. `blindspots`: every `@bs-*` marker with its pattern.
    - Every candidate has `id` and `group`; a second run is `reused`; every tool is `ok`; `git status --porcelain` in the checkout prints nothing tracked.
    - With `trusted` false: the four Node tools are `skipped`, and `entry_points` still holds the semgrep routes.
  - Done-check: `DOSSIER_SLOW=1 ... tests/integration/scripts/test_js_adapter_slow.py -v` passes.
  - Commit: `test(dossier): check every JavaScript extractor on the fixture repository`

### Deliverables and checks (Phase 2)

| Deliverable | Checked by |
|---|---|
| `ts_facts` | `test_ts_facts_slow.py` |
| Graph, dead, symbols | `test_js_reduce.py`, `test_scip_ts_slow.py` |
| Tests, complexity, state | `test_js_queries_slow.py` |
| Models | `test_js_prisma.py` |
| Rules and V7 | `test_rules.py`, `test_shared_layer.py`, `test_checks_v7.py` |
| All outputs | `test_js_adapter_slow.py` (the fixture test of record) |

### Cut line (Phase 2)

In this order, recording each: the ORM forms other than Prisma and `@Entity`, and `zod`; Fastify and NestJS rules. **Never cut** M4-14's tests, M4-15, M4-17.

### Acceptance criteria (Phase 2)

- `test_js_adapter_slow.py` shows exactly the expected entry points and every other expected item.
- The full suite and slow suite pass, except G2.
- `test_py_adapter_slow.py` passes unedited.

### Branch and release (Phase 2)

Commit each task on `feat/dossier-m4`. Do not merge or bump. Write "Results (Phase 2)" and commit: `docs(dossier): record phase 2 of M4 in plan 010`.

### Results (Phase 2)

**Summary.** All of M4-7 to M4-17 and M4-13a are done; nothing was moved to Phase 3. Cuts taken (allowed by the Phase 2 cut line): `mongoose`, `sequelize`, `drizzle` and `zod` entities (M4-12). `ts_facts.mjs` is 423 lines (plan: about 400) and stays one file so the install stays simple; every Python module is under 300 lines (`js_adapter.py` is the largest at 277).

**M4-7.** Done as written. `exports` holds names declared in that file (an `export { x as y }` row also carries `local`); re-exports through `export ... from` are imports, not exports. `types` rows carry an extra `object` flag (true for interfaces and `type X = {...}`), which M4-12 uses for the entity filter. Slow test: 8 passed.

**M4-8.** Done as written, with one change to D5: line 5b (the repository's own rules) also needs `--ts-pre-compilation-deps`. Without it dependency-cruiser drops `import type` edges, so the fixture's `import-up` rule showed `kept` instead of `broken`. `graph_items` also returns cycles (project-scoped) with the module and import items; the adapter holds test-file edges in `st["test_edges"]` for M4-11 and does not emit them.

**M4-9.** Done as written. `Knip.run_knip(project_dir)` is the client method name (`run` is the sandbox runner). Dependency findings (`dependencies` and `devDependencies`) both give kind `unused dependency` on the project's `package.json`. Without a `knip.json`, the fixture reports its non-entry files as unused too, so M4-17's expected `dead` list must be built from a real run and checked by hand, not guessed.

**M4-10.** Done as written, with one fact that differs from M4-1's sample: for a file below a folder the symbol is ``scip-typescript npm shopjs 1.0.0 src/`types.ts`/Order#`` (directory descriptors first, then the file), so `finish_symbols` takes the first name after the last `/` descriptor, not the second descriptor. `ScipTs(run, install, timeout).index(project_dir, area, n, has_tsconfig)` writes `<area>/scip/js-<n>.scip`. Risk kept: two projects with the same package name and version would share symbol strings for the same relative path; the plan's D11 accepts this. The slow test does not assert that no `.scip` is left in the checkout; the output path is under the area, and `workarea.verify` already fails the build on tracked changes.

**M4-11.** Done as written; all three grammar names and D8's queries ran as recorded in M4-1. Choices the plan left open: a test file with no framework import and no runner config gets framework `unknown`; the `export let` form is found by the second query (`export_statement declaration: (lexical_declaration)`, start column 7), and the captured text excludes the word `export`; curried calls such as `it.each([..])('x', fn)` are counted once, by the inner call whose function text is a plain dotted name; `coverage_threshold` is the smallest number among statements/branches/functions/lines near `coverageThreshold` (jest) or `thresholds` (vitest), or anywhere in a `.c8rc`/`.nycrc`. The adapter writes `complexity` onto module items and the `tests` list gets `paths` and `imports` from dependency-cruiser's test-file edges (empty when that tool did not run). `tree-sitter-language-pack` now has a real status; `semgrep` still says `Arrives in a later task.`

**M4-12.** Prisma, `@Entity` classes, interfaces, object types and enums are done. **Cut (allowed by the Phase 2 cut line):** `mongoose`, `sequelize`, `drizzle` and `zod` entities; `ts_facts.mjs` does not yet report const-based schemas, so they are listed as a gap for the next plan. Prisma is read even when Node is missing or the ref is untrusted (it needs no tool). A Prisma `type` or `view` block is treated like a model. `measured_er.family` is new and `_relations` keys on it.

**M4-13.** Done as written, plus one function the interface did not list: `js_reduce.render_edges(items)` builds the `ref-edge` symbols from `renders` items, and the adapter adds them only when scip-typescript did not succeed (so there is never a double count). A `renders` item between two components in the same file is kept in the graph but gets no edge. An unresolved route has `target` set to its own file, since the card needs some target.

**M4-13a.** Done as written. **O8 (answered): `checker.getExportsOfModule` follows `export *` chains.** `deep` was found through two hops (`index.ts`, `barrel.ts`, `deep.ts`) with its `path` at `src/deep.ts`, and `getImmediateAliasedSymbol` was not needed. Two details: (1) `export * from 'missing'` is not in `getExportsOfModule`, so the script scans star re-exports (recursively through repository files) and reports unresolved specifiers in `api_unresolved`; (2) `entries` takes `{"dir", "manifest"}` for one package plus a tolerant `read_tsconfig` (comments, trailing commas; `extends` is not followed). Entries whose target cannot be mapped, and `api_unresolved` rows, become `js-note` graph items with `note: "api"` and `name: "<package>|<subpath>"`; **M4-15 turns those into the Gaps item** (`The public API of {package} could not be fully worked out from {subpath}.`). The fixture's root package (`shopjs`, `main: dist/main.js`) also has a public API (from `src/main.ts`), as D17's rule says. The `FEEDS["io"]` entry and the `io.contracts` table are Phase 3.

**M4-14.** Done as written; `semgrep --test` passes for all `rules/js` files, which are `languages: [js, ts]` with `.ts` targets and `// ruleid:` / `// ok:` comments. Things the plan did not say: (1) **semgrep propagates constants**, so with `const path = '/x'` the call `router.get(path, h)` matches the literal pattern `"..."`. The four route rules (`http-route`, `route-chain`, `fastify-route`, `string-route`) therefore set `options: {constant_propagation: false}`, which keeps the fixture's `@bs-route` a blind spot; (2) the `http-route` `detail` regex allows `//` comments between `(` and the path (the fixture's `router.post( // @ep-post`), and `route_parts` strips comments; (3) a semgrep `ruleid:` comment must sit directly above the line where the match starts (`try {`, not `} catch`); (4) rule files are split by function as the plan lists, plus a new `js_semgrep.py` (results to items) because `js_reduce.py` was near 300 lines; (5) `route-chain` and `fastify-route` give the path only, since their `detail` can hold one group, so those routes have no method in the name; NestJS routes give the decorator path (`POST users`) without the controller prefix. The adapter marks `semgrep` ok or failed and keeps the list of `.mts`/`.cts` files it could not scan in its state for M4-15. `.d.ts` files are not sent. While iterating I left hundreds of semgrep environments in `/tmp` (7.5 GB tmpfs, 86% full); they are deleted and the helper now reuses one folder.

**M4-15.** Done as written. `js_coverage` lives in `checks_v7.py` (that module is short) and `checks.js_coverage` is an alias, so `checks.validate` calls it. It replaces the inline Python stale-flags item: the Python statement is unchanged and appears only for a `module` item with no `language` key, so `REPO`'s Gaps ids do not change. The adapter writes `js-note` graph items with `note` of `framework` (name `Koa`), `bun` (name = the project folder, `.` for the root), `unscanned` (name = the count, path = the first file) and, from M4-13a, `api`. The `blindspot.yml` rules and the `BLIND_SPOTS` wording were done in M4-14 and this task; no existing wording changed.

**M4-16.** Done as written. `RepoAdapter.version` is `3`.

**M4-17.** Done as written, in the existing `test_js_adapter_slow.py` (now with `TestFixtureOfRecord` and `TestUntrustedRef`; the module fixtures were reorganised into `extraction`, `ex` and `untrusted`, and `test_scip_ts_slow.py` and `test_js_queries_slow.py` reuse them). Findings while writing it: (1) the plan's "`@/` aliases resolved" had no fixture file to check, so `src/unused.ts` now imports `@/a` (marker `alias-import`) and the test finds the edge; (2) `source-root` items were not emitted yet and are now written by the adapter (`js_project.source_roots`); (3) **a regex rule with `^\s*` can start its match on the blank line above** (`\s` spans newlines), which put the `hook-wiring` hit one line early; both multi-line regex blind-spot rules now use `^[ \t]*`, with a semgrep case for an indented hook; (4) `contract` violations name modules (`src/main`), not files, because a module name is the file path without its extension; (5) the `dead` list for the fixture is long, because the fixture has no knip entry configuration, so knip reports every file nothing imports; the test only asserts `src/unused.ts` (unused file) and `hidden` (unused export); (6) `reused` is read from the adapters' statuses in the second run's record.

**Phase 2 checks.** Full suite with `DOSSIER_SLOW=1`: 1926 passed (3 min 49 s), run with the two known failures deselected (`test_golden02_slow.py`, which is G2, and `test_check_page_slow.py`, which fails on `main` too). That run includes `test_py_adapter_slow.py`, unedited. Fast suite: 1844 passed, 96 skipped. A first slow run filled the 7.5 GB `/tmp` tmpfs with pytest folders; the final run used `--basetemp` under `~/.cache`, so **Phase 3 and later should do the same**.

---

## Phase 3: Shared layer, prompts and version

### Before you start (Phase 3)

Read section 2, D4, D9, D10, D13 to D15, and "Results" of Phases 1 and 2. Load the skills in section 2, plus `docs-project`, `docs-readme` and `git-release`. `git switch feat/dossier-m4`. Do first any task moved here. Run block E once now to set its comparison base: `BASE_SHA=3a68c36`.

### Tasks (Phase 3)

- [x] **M4-18. Components, areas and names.**
  - Goal: rows 13, 16 and 30, and D4's readers.
  - Files: edit `scripts/components.py`, `scripts/measured_graph.py`, `scripts/checks_v3.py`, `scripts/checks.py`, `scripts/candidates.py`, `tests/unit/scripts/test_components.py`, `test_measured.py`, `test_checks_v3.py`, `test_checks_v2.py`, `test_candidates_cli.py`.
  - Interface: `match_score` tests the literal directory prefix before treating `[` as a glob. `parse_paths` accepts `]` inside a `[[...]]` path. `measured_graph.package_roots` adds `source-root` items' `root`. `checks.JS_WORDS = {"const", "let", "var", "function", "async", "await", "undefined", "this", "new", "typeof", "interface", "type", "enum", "Promise", "Array", "Object", "string", "number", "boolean"}`, skipped by V2 only when a `module` item has `language: "js"`.
  - Steps: (1) Tests: `apps/a/[id]/page.tsx` matches the pattern `apps/a/[id]/` and the pattern `apps/a/[id]/*`; a real glob `src/[ab].py` still works; `_area_of_path` gives `react-vite` with root `apps`; a diagram node `routes` resolves through `short`; V2 treats `short` names as module names; each Python result equals today's, asserted. (2) Implement. (3) Run block E.
  - Done-check: the named test files pass; block E prints `OK`.
  - Commit: `feat(dossier): handle JavaScript paths and names in components and checks`

- [x] **M4-19. Dead code rows.**
  - Goal: row 28 and 29.
  - Files: edit `scripts/measured_change.py`, `tests/unit/scripts/test_measured_change.py`.
  - Interface: `dead_rows` unchanged in signature.
  - Steps: (1) Tests: a `dead` item with `confidence: None` gives evidence with no percentage; a `module` with `language: "js"` gives no "module nothing imports" row; a `deps.py` unused entry with the same name as a knip dependency gives one row, not two; Python items give exactly today's rows. (2) Implement. V11 shares `dead_rows`, so it needs no change.
  - Done-check: `... pytest tests/unit/scripts/test_measured_change.py tests/unit/scripts/test_page_audit.py -q` passes.
  - Commit: `feat(dossier): show knip findings in the dead code card`

- [x] **M4-20. Where things live, and tooling.**
  - Goal: row 31.
  - Files: edit `scripts/measured.py`, `tests/unit/scripts/test_measured.py`.
  - Interface: `_is_config` adds `package.json`, `tsconfig*.json`, `jsconfig.json`, `.env.example` at any depth, `*.config.{js,cjs,mjs,ts}`. `_is_build` adds `package.json` with a `build` script, `vite.config.*`, `next.config.*`, `webpack.config.*`, `rollup.config.*`, `tsup.config.*`, `nx.json`, `project.json`, `turbo.json`. `TOOLS` adds `eslint`, `prettier`, `biome`, `typescript`, `husky`, `lint-staged`, `commitlint`, by their config files. Config inside `package.json` (`eslintConfig`, `prettier`, `lint-staged`) counts, with `package.json` as the file. `_tooling`'s `SHARED` is not changed; a `package.json` key is read through a new small helper.
  - Steps: tests on tree lists for each; a Python tree (`REPO`'s kind) gives today's rows, asserted. Tools nested in `apps/*` are found by base name. Implement.
  - Done-check: `... pytest tests/unit/scripts/test_measured.py -q` passes; block E prints `OK`.
  - Commit: `feat(dossier): find JavaScript config, build and tooling files`

- [x] **M4-21. The React table.**
  - Goal: D9's card, with V11 and V12.
  - Files: edit `scripts/measured_graph.py`, `scripts/measured_tables.py`, `scripts/page_audit.py`, `tests/unit/scripts/test_measured.py`, `tests/unit/scripts/test_page_audit.py`. `check_layout.py` needs no edit: `interactions.graph` always holds tables, and its checks already walk every table on the page. `SCRIPT_TABLE_CARDS` (`check_layout.py:29`) lists cards that must show a table; this card is not one of them because the new table is optional.
  - Interface: `measured_tables.react_components(cid, extract, group, refs) -> str`; table id `t-interactions-graph-react`. `_measured_counts` adds it to `interactions.graph` when `ui-component` items exist.
  - Steps: (1) Tests: the table has one row per item and the columns of D9; `Rendered by` is computed from `renders`; with no items the card's HTML equals today's; V11 fails when a row is missing. (2) Implement. No CSS change is expected. Any new CSS is scoped to `.card[data-card="interactions.graph"]`, written with `^=` in selectors (plan 009, deviation 9).
  - Done-check: the two test files pass; block E prints `OK`.
  - Commit: `feat(dossier): list React components in the dependency graph card`

- [x] **M4-21a. The public API table.**
  - Goal: D17's card, Gaps and staleness.
  - Files: edit `scripts/render.py` (`render_card`), `scripts/measured_tables.py`, `scripts/page_audit.py`, `scripts/candidates.py`, `scripts/checks.py`, `tests/unit/scripts/test_measured.py`, `tests/unit/scripts/test_page_audit.py`.
  - Interface: `measured_tables.public_api(ctx, refs) -> str`, table id `t-io-contracts-api`. Add `io.contracts` beside `interactions.graph` in the counts at `page_audit.py:176`, not in `_measured_counts`, which returns early when there is no history.
  - Steps: (1) Tests: one row per item, in D17's order; the table survives an `na` entry and is absent from a pending one; the fixed line appears for a JS repository with no items; a repository with no JS has byte-identical HTML; V11 fails when a row is missing; an unresolved entry gives the Gaps item; a Python repository's `io` digest does not change. (2) Implement.
  - Done-check: the two test files pass; block E prints `OK`.
  - Commit: `feat(dossier): report the real public API in the contracts card`

- [x] **M4-22. Upgrade burden (P1).**
  - Goal: row 32.
  - Files: edit `scripts/measured_upgrade.py`, `tests/tools/refresh_eol.py`, `scripts/eol.json`, `tests/unit/scripts/test_measured_upgrade.py`.
  - Interface: Node pinned from `.nvmrc`, `.node-version`, then `engines.node` of the first project. `_cycle` keeps its result for `3.13`, and a new `_major` is used for products whose cycles have no dot. `PACKAGE_PRODUCTS` gains `react` and `next` to `nextjs` if the source has them.
  - Steps: (1) Run `refresh_eol.py` with `react` and `nextjs` added. If either returns 404, leave it out and record it. **Keep `python` and `django` data unchanged** by adding only new products to the file, so the Python row stays the same. (2) Tests, then implement.
  - Done-check: `... pytest tests/unit/scripts/test_measured_upgrade.py -q` passes.
  - Commit: `feat(dossier): show the Node runtime in upgrade burden`

- [x] **M4-23. Partial badges, Gaps and staleness.**
  - Goal: rows 33 and 36, D14.
  - Files: edit `scripts/candidates.py`, `tests/unit/scripts/test_process.py`, `tests/unit/scripts/test_candidates.py`.
  - Interface: `FEEDS["interactions"]` gains `"ui"`; `_feed("ui")`.
  - Steps: tests: with `knip` skipped, `change.dead-code` is partial with the `Made without knip:` reason, and a Gaps item is written once; in a mixed build, a JS tool absent badges its cards, and Python's tools are not named; a moved line in a component changes no digest, and a new `renders` target changes `interactions`; `node` missing gives the existing host Gaps item. `process.py` should need no change. If it does, stop and report.
  - Done-check: `... pytest tests/unit/scripts/test_process.py tests/unit/scripts/test_candidates.py -q` passes.
  - Commit: `test(dossier): cover partial badges and staleness for JavaScript tools`

- [x] **M4-24. Test page, skeleton check, mixed fixture.**
  - Goal: V11 and V12 on what is new, without a real repository, and a mechanical check of spec 11 item 2.
  - Files: new `tests/tools/m4_page.py`, `tests/tools/skeleton.py`, `tests/unit/scripts/test_skeleton.py`, `tests/integration/scripts/test_mixed_slow.py`; edit `tests/integration/scripts/test_check_page_slow.py`.
  - Interface: `m4_page.make(tmp) -> Path`, in the style of `m3_page.py`, adding 60 `ui-component` items, a Prisma model set and knip rows. `skeleton.py PAGE [PAGE...]`: prints, per page, the ordered list of (report, card id, title, tier), and exits 1 unless all pages match. It uses `report_section.cards`.
  - Steps: (1) `test_skeleton.py` on two hand-made pages. (2) `test_mixed_slow.py`: a `tmp_path` repository holding `PYFIX` under `backend/` and `JSFIX`'s `packages/web` under `frontend/`, with one commit; `stage_extract` gives `python`, `js` and `repo` sections, all candidates have unique ids, `dossier candidates --report components` prints both headings. (3) Slow check of the page: `dossier check`'s V11 and V12 report 0 problems on `m4_page`.
  - Done-check: `DOSSIER_SLOW=1 ... test_mixed_slow.py test_check_page_slow.py -q` passes.
  - Commit: `test(dossier): check the new tables in a browser and compare card skeletons`

- [x] **M4-25. Prompts.**
  - Goal: tell Claude what the JS extractors give it.
  - Files: edit `prompts/method.md`, `prompts/reports.md`, `SKILL.md`, `tests/unit/scripts/test_prompts.py`.
  - Interface: text only.
  - Steps:
    - `method.md`: the tool list near line 213 adds dependency-cruiser, knip, scip-typescript and the TypeScript compiler script. Near line 384, "the Python packages" becomes "the Python packages or JavaScript projects".
    - `reports.md`, `entry`: write a route's **full** path, adding any prefix from `route-mount` findings. Keep one row per entry point. Package scripts are entry points; a script that only wraps another may be merged only when it is the same `path` and `name`, otherwise dismiss it with a reason.
    - `reports.md`, `data` (line 137): add interfaces, object types, enums, Prisma models and ORM classes. Props types are left out by the tool.
    - `reports.md`, `components`: for a repository of several apps, one component per folder with a clear job; do not merge apps.
    - `reports.md`, `io`: the page draws the public API table, so never copy it. Write one `io.contracts` row per package that has an API, as `offered`. In `components.catalog`, Public surface names what the component offers to other packages, or says it is internal.
    - `reports.md`, `interactions`: the card lists React components; use them for flows; context wiring is in Gaps.
    - `reports.md`, line 305: "are not detected for Python" becomes "are not detected".
    - `reports.md`, technologies (line 381): add React state, routing and data-fetching idioms to the examples.
    - One paragraph, "Repositories with more than one language": cards are the same; rows cover both; say which language a row belongs to only where it matters.
    - `SKILL.md`: nothing about tools changes except the `doctor` sentence if needed.
  - Done-check: `... pytest tests/unit/scripts/test_prompts.py -q` passes; `grep -n "for Python" prompts/reports.md` prints nothing.
  - Commit: `docs(dossier): tell Claude how to use the JavaScript findings`

- [x] **M4-26. Docs and version.**
  - Goal: D15.
  - Files: edit `VERSION`, `README.md`, `rules/README.md`, this plan.
  - Steps: (1) `VERSION` to `0.9.0`. (2) `README.md`: one sentence that TypeScript, JavaScript and React have full support, and Node 22.13 or later is needed for them. The full rewrite stays in M6. (3) `rules/README.md`: `js/` exists; its blind-spot ids. (4) Run the full and slow suites.
  - Done-check: `cat VERSION` prints `0.9.0`; the suites pass, except G2.
  - Commit: `chore(dossier): bump to 0.9.0`

### Deliverables and checks (Phase 3)

| Deliverable | Checked by |
|---|---|
| Readers | `test_components.py`, `test_checks_v3.py`, `test_checks_v2.py` |
| Dead code, reading map, tooling | their unit tests |
| React table with V11, V12 | `test_page_audit.py`, `test_check_page_slow.py` |
| Partial and staleness | `test_process.py`, `test_candidates.py` |
| Mixed | `test_mixed_slow.py` |
| Prompts | `test_prompts.py` |

### Cut line (Phase 3)

M4-22 only. **Never cut** the V11 and V12 work in M4-21 and M4-24.

### Acceptance criteria (Phase 3)

- The suites pass, except G2. Block E prints `OK` after each task that needs it.
- `m4_page` passes V11 and V12.
- `VERSION` is `0.9.0`.

### Branch and release (Phase 3)

Commit on `feat/dossier-m4`. Do not merge. Write "Results (Phase 3)" and commit: `docs(dossier): record phase 3 of M4 in plan 010`.

### Results (Phase 3)

**Summary.** M4-18 to M4-26 are done; nothing was cut (M4-22 was done). Fast suite: 1945 passed, 116 skipped. Slow suite (`--basetemp` under `~/.cache`, G2 deselected): 2056 passed, 2 failed, both unrelated to M4: `test_overlapping_paragraphs_are_reported` (also fails on `main`) and `test_each_browser_mutation_makes_a_fail[chart-text-small]`, whose mutation looks for a `chart-scroll` hotspot chart that the post-M3 rework no longer draws (not checked on `main`; none of the M4 commits touch it). Both join G2 for the author. Block E printed `OK` after M4-18, M4-20, M4-21, M4-21a and M4-22. `m4_page` has 0 problems in the browser check and the page audit.

**Deviations.** (1) `react_components(cid, extract, refs)` has no `group` argument; nothing would use it. (2) The React and public API counts are registered before the `has_history` gate in `page_audit._measured_counts`, so V11 checks them without history; the `io.contracts` count is only registered when there are names to list. (3) M4-22: `refresh_eol.py --add` was added so only react and nextjs were fetched; Python, Django and `as_of` data are unchanged. React has no end-of-life dates, so its gap reads "not in the data". (4) The mixed-repository test keeps PYFIX at the repository root, not under `backend/`: **finding:** the Python adapter reads `pyproject.toml` at the repository root only, so Python code in a subfolder gives no modules (not changed here; for the author). (5) Tooling "enforced where" looks for a tool's name in CI files and hooks only, so a CI step that runs `yarn lint` shows eslint as not enforced. (6) Components, `candidates` text: JS projects are listed by source root, with a module count. (7) Commit identity: the first nine Phase 3 commits were made under the user's name by mistake and were re-authored as Claude before anything was pushed.

---

## Phase 3a: Ground truth for the primary repository

**Run this with Opus, in a fresh session (`/model opus`).** Read only this section. Do not read the rest of this plan, the spec, `rules/`, `scripts/` or any dossier: they hold notes on this repository, and your list must not depend on them.

### Before you start (Phase 3a)

Load `git-commit`. Then:

```bash
SKILL=/home/nick/dev/projects/encamp/configs/user/claude/.claude/skills/dossier
RW_PIN=30b68e1e881462b2f4164ea09ab4c4f5699c7b0b
SCR=$(mktemp -d -p "$HOME/.cache" dossier-m4-XXXX); echo "SCR=$SCR"
mkdir -p $SCR/src $SCR/truth
git clone -q https://github.com/gothinkster/node-express-realworld-example-app $SCR/src/rw
git -C $SCR/src/rw checkout -q $RW_PIN
```

Do not install anything, run the repository's code, or build a dossier. The repository has no licence, so **nothing from it is ever committed**.

### Tasks (Phase 3a)

- [x] **T-1. Write the truth file.**
  - Goal: an independent list that the dossier is scored against.
  - Files: `$SCR/truth/rw.json`, which is never committed.
  - Format: `{"entry_points": [{"kind", "key", "where"}], "io": [{"direction": "input"|"output", "category", "key", "where"}]}`. `key` is a short string the matching row must contain, such as `GET /api/orders` or `API_KEY`. `where` is `path:line`.
  - Steps: (1) Read every tracked source and config file yourself. Do not sample. (2) List every entry point, one per row. Kinds: console scripts and package bins, package scripts, package `main`, monorepo task targets, server start, `__main__`-style start files, CLI commands, HTTP routes (with the **full** path, including any prefix), browser routes, queue consumers, scheduled jobs, container `CMD` or `ENTRYPOINT`, CI schedules, Makefile targets, shebang scripts, systemd units. (3) List inputs. Categories: CLI arguments, environment variables, config files, files read, stdin, network requests (grouped by route group), messages consumed, database reads (by model), scheduled triggers. Environment variables include those in schema files and Dockerfiles. (4) List outputs. Categories: stdout/stderr, files written, network responses, outbound calls, messages produced, database writes (by model), logs, metrics, exit codes, error responses. (5) Include test helpers, and say so in `where`. (6) Write the file, and run `sha256sum $SCR/truth/rw.json`.
  - Done-check: the file parses with `python3 -m json.tool`, and every `where` names a line that exists.
  - Commit: none for the file. See below.

### Deliverables and checks (Phase 3a)

| Deliverable | Checked by |
|---|---|
| Truth file | The done-check, and the hash below |

### Cut line (Phase 3a)

Nothing is cut. If the session cannot finish, keep the file and record how far it got.

### Acceptance criteria (Phase 3a)

Every tracked source and config file was read, and the hash and `SCR` path are recorded.

### Branch and release (Phase 3a)

On `feat/dossier-m4`, write under "Results (Phase 3a)": the `SCR` path, the hash, the row counts and the date. Record no content from the repository. Tick T-1 and commit: `docs(dossier): record the ground truth hash in plan 010`. Do not merge.

### Results (Phase 3a)

**Done 2026-11-07, by Opus 5.5.** T-1 is complete.

- `SCR=/home/nick/.cache/dossier-m4-8vGZ`. The truth file is `$SCR/truth/rw.json`, and the clone is `$SCR/src/rw` at the pin.
- `sha256sum`: `8dd5c9c2fcba32f3a9d4a7313e841b99f4c2b19565de5f8aa8e46958f5d78e03`.
- Rows: 35 `entry_points`, 42 `io` (20 input, 22 output). The file parses with `python3 -m json.tool`, and every `where` names a line that exists and is not blank.
- Every tracked source and config file was read in full. The two images were not read. Only the root entry of `package-lock.json` was read, because the rest lists third-party packages.
- **Independence note.** Before reaching the Phase 3a instruction, this session read lines 1 to 80 and 440 to 1040 of this plan. The only `RW` fact there was D17's statement that its `package.json` declares no public API. That was checked against the source and is true. Nothing else in the list came from the plan.
- `where` values for test files end with ` (test helper)` after `path:line`. Phase 4's tool should split on the first space.

## Phase 4: Primary repository and Python golden

### Before you start (Phase 4)

Read section 2, section 6 and "Results" of Phases 1 to 3. Load the skills in section 2. `git switch feat/dossier-m4`. `cat VERSION` prints `0.9.0`. Do first any task moved here. **Stop if "Results (Phase 3a)" has no hash.** Set `SCR` to the path recorded there before section 6's setup, and never read the truth file except through `ground_truth.py`. Run `df -h "$HOME/.cache"`: at least 15 GB free.

### Tasks (Phase 4)

- [ ] **M4-27. The ground truth comparison tool.**
  - Goal: score a dossier against the truth file that Opus wrote in Phase 3a (D18).
  - Files: new `tests/tools/ground_truth.py` and its unit test. It holds no data from `RW`; the test uses made-up rows.
  - Interface: `ground_truth.py TRUTH REPORTS_DIR` prints recall, precision and each disagreement, and with `--review FILE` writes them there. A truth row matches when a row of the home card contains its `key`.
  - Steps: (1) Tests: a matched row, a missed row, an unmatched dossier row, recall and precision figures. (2) Implement. (3) `sha256sum $SCR/truth/rw.json` must equal the hash in "Results (Phase 3a)".
  - Done-check: the test passes and the hash matches.
  - Commit: `test(dossier): add the ground truth comparison tool`

- [ ] **M4-28. Run the blocks for `RW`, and the Python golden.**
  - Goal: the exit criterion on the primary repository.
  - Files: this plan only, unless a block finds a bug.
  - Steps: run, in order, blocks S, A, B, C, D, F, G, H, L, T, J, N, K, P, E, I, as section 6 gives them. **A failure is a finding:** fix the cause on this branch with a test first, in its own commit, then rerun the block. Fix the code, not the check. **Block T is the exception:** record its disagreements and carry on, because Phase 4a judges them. Never edit the truth file.
  - Done-check: every block's result is recorded under "Verification results (Phase 4)".
  - Commit: `docs(dossier): record the M4 verification on the primary repository`

### Deliverables and checks (Phase 4)

| Deliverable | Checked by |
|---|---|
| Ground truth | Hash matches "Results (Phase 3a)" |
| `RW` dossier | Blocks B to H |
| Recall and precision | Block T |
| Python unchanged | Block P |

### Cut line (Phase 4)

Nothing is cut. If block D cannot finish, stop and say which reports are left; the next session continues. Reports are never kept from an older build, because no older build of `RW` exists.

### Acceptance criteria (Phase 4)

- `dossier check` prints `problems: 0`, `render` prints no `error:` line, V1 to V10 pass.
- Block T has run, and `$SCR/truth/review.md` lists every disagreement. Its targets are judged after Phase 4a, in Phase 4b.
- Block P prints `SAME`.

### Branch and release (Phase 4)

Do not merge. Commit results: `docs(dossier): record phase 4 of M4 in plan 010`.

### Results (Phase 4)

### Verification results (Phase 4)

---

## Phase 4a: Rulings on the ground truth

**Run this with Opus, in a fresh session (`/model opus`).** Read this section and D18 only. You are a judge here: you change no code and no report.

### Before you start (Phase 4a)

Load `git-commit`. `git switch feat/dossier-m4`. Set `SCR` from "Results (Phase 3a)". Sonnet's disagreements are in `$SCR/truth/review.md`, the repository is `$SCR/src/rw`, and the reports are in `$SCR/home/rw/reports`.

### Tasks (Phase 4a)

- [ ] **T-2. Rule on every disagreement.**
  - Goal: a miss or an extra row is settled by reading the code, not by the session that built the dossier.
  - Files: `$SCR/truth/rulings.md`, and `$SCR/truth/rw.json` when the list was wrong.
  - Steps: for each row, read the cited code and give one verdict with a reason: `list wrong` (amend the truth file), `dossier wrong` (Phase 4b fixes it), or `blind spot` (name the Gaps entry or blind-spot rule that explains it). For a dossier row that matches nothing, say whether it is a true entry point or input or output. Sonnet's explanation is not evidence. Then rerun `sha256sum` if the file changed.
  - Done-check: every row in `review.md` has a verdict.
  - Commit: none for the files. See below.

- [ ] **T-3. Check the component map.**
  - Goal: section 11's component check for a public repository (S1).
  - Files: `$SCR/truth/rulings.md`.
  - Steps: for every row of `components.catalog`, open its paths and confirm that they exist, that the files belong together, and that Responsibility says what the code does. Give each `ok` or `dossier wrong`, with a reason.
  - Done-check: every component has a verdict.
  - Commit: none for the files. See below.

### Deliverables and checks (Phase 4a)

| Deliverable | Checked by |
|---|---|
| Rulings | Every row and every component has a verdict |

### Cut line (Phase 4a)

Nothing is cut.

### Acceptance criteria (Phase 4a)

The two done-checks pass, and any new hash is recorded.

### Branch and release (Phase 4a)

Write under "Results (Phase 4a)": the count of each verdict, every `list wrong` change with its reason and new hash, and each `dossier wrong` row by path and name, with no code from the repository. Tick T-2 and T-3 and commit: `docs(dossier): record the ground truth rulings in plan 010`. Do not merge.

### Results (Phase 4a)

## Phase 4b: Fixes after the rulings

Skip this phase if Phase 4a found no `dossier wrong` row **and** block T met its targets.

### Before you start (Phase 4b)

Read section 2, section 6 and "Results" of Phases 3a to 4a. Load the skills in section 2. `git switch feat/dossier-m4`. Set `SCR` from "Results (Phase 3a)".

### Tasks (Phase 4b)

- [ ] **M4-28a. Fix each `dossier wrong` row.**
  - Goal: the exit criterion on the primary repository.
  - Files: whatever each fix needs, under the rules in section 2.
  - Steps: (1) For each row, fix the rule or add a Gaps entry where no rule can work, with a test first, in its own commit. (2) Rebuild what changed. (3) Rerun blocks T, P and E. (4) If block T shows a new disagreement, stop and ask the author to run Phase 4a again.
  - Done-check: block T meets the targets below, with no unruled disagreement.
  - Commit: `docs(dossier): record the M4 fixes on the primary repository`, plus one commit per fix.

### Deliverables and checks (Phase 4b)

| Deliverable | Checked by |
|---|---|
| Recall and precision | Block T |
| Python unchanged | Block P |

### Cut line (Phase 4b)

Nothing is cut.

### Acceptance criteria (Phase 4b)

Entry points recall 100% and precision at least 95%; inputs and outputs recall at least 95%; every miss is explained by a Gaps entry or a new blind-spot rule. Record the figures from before and after the fixes.

### Branch and release (Phase 4b)

Do not merge. Commit results: `docs(dossier): record phase 4b of M4 in plan 010`.

### Results (Phase 4b)

## Phase 5: React and mixed repositories, then merge

### Before you start (Phase 5)

Read section 2, section 6 and "Results" of Phases 1 to 4b. Load the skills in section 2. `git switch feat/dossier-m4`. **Stop if Phase 4a has no results, or if Phase 4b was needed and has none.** Do first any task moved here. Set `SCR` from "Results (Phase 3a)", because the truth file is there; never set it up afresh.

### Tasks (Phase 5)

- [ ] **M4-29. Run the blocks for `BP`.**
  - Goal: the React checks.
  - Files: this plan only, unless a block finds a bug.
  - Steps: block R. A failure is a finding, handled as in M4-28.
  - Done-check: results recorded under "Verification results (Phase 5)".
  - Commit: `docs(dossier): record the M4 verification on the React repository`

- [ ] **M4-30. Run the mixed block and the final checks.**
  - Goal: mixed repositories, card skeletons, the full suite.
  - Files: this plan only.
  - Steps: blocks M, Y, X, I, E, then Z.
  - Done-check: as those blocks say.
  - Commit: `docs(dossier): record the M4 mixed repository run`

- [ ] **M4-31. Merge and hand over.**
  - Goal: the milestone review can start.
  - Files: this plan.
  - Steps: (1) Tick and record. (2) Follow `git-workflow`: `git merge --no-ff feat/dossier-m4` into `main`, push `main`, delete the branch. (3) Tell the author the procedure below.
  - Done-check: `git log --oneline -1 main` shows the merge, and `git status --short` shows no tracked change.
  - Commit: the merge commit.

### Deliverables and checks (Phase 5)

| Deliverable | Checked by |
|---|---|
| `BP` dossier | Block R |
| Mixed build | Block M |
| Public API on a real library | Block Y |
| Same skeletons | Block X |
| Merge | M4-31 done-check |

### Cut line (Phase 5)

Nothing in section 6 is cut. If `BP`'s reports cannot finish in one session, stop at a saved state, say which are left, and continue in a new session. Do not merge until they are done.

### Acceptance criteria (Phase 5, and M4)

- Blocks R, M, X and Z are recorded, and `dossier check` prints `problems: 0` on both repositories.
- `skeleton.py` exits 0 across the Python, `RW` and `BP` pages.
- The branch is merged.

### Branch and release (Phase 5)

Merge as M4-31 says. CI does not tag this skill. The next step is the author's milestone review.

### Hand-over to the milestone review

The author does this. **Needed on the machine:** Node 22.13 or later, and npm. Yarn and pnpm are not needed. `uv`, `git` and `gh` as before.

1. `encamp-sync pull`, so `INSTALLED` is at the merge. `git -C ~/.local/share/encamp status --short` must show no `UU` line.
2. `/dossier doctor <repo>` on a clone of `RW`. It must print `skill: <merge commit> (clean)`, and the JS tools as "from a lockfile with npm".
3. Read `RW`'s and `BP`'s pages, kept under `$SCR` until the author has seen them. Open them at full width and at 400 px, in light and dark.
4. **Spot-check the ground truth.** Pick ten rows of the truth file at random, open the cited code, and confirm that it says what the row says. Then do the same for ten rows of `entry.catalog` and `io.inputs`. This needs no TS knowledge. Read Phase 4a's rulings, especially any `list wrong`.
5. In `BP`, look at the React table in `interactions.graph` and at the areas in `components.map`. The checks cannot tell whether either is useful.
6. Rule on anything recorded under "Findings for the milestone review".
7. When content is judged, delete `$SCR`.

### Results (Phase 5)

### Verification results (Phase 5)

---

## 6. Verification

Set once per shell. The scratch folder is under `~/.cache`, not `/tmp` (section 2):

```bash
SKILL=/home/nick/dev/projects/encamp/configs/user/claude/.claude/skills/dossier
REPO=/home/nick/dev/projects/cannalerts
LIVE=/home/nick/dev/dossiers/cannalerts
FIX=$SKILL/tests/fixtures/encamp-m0
PIN=5923c09
RW_PIN=30b68e1e881462b2f4164ea09ab4c4f5699c7b0b
BP_PIN=9506629ed003a561c6627735480cce4994244bb4
LIB_PIN=382d29c485e67018c06e75ec7235130d0968522c
BASE_SHA=3a68c36
SCR=${SCR:-$(mktemp -d -p "$HOME/.cache" dossier-m4-XXXX)}; echo "SCR=$SCR"
export DOSSIER_HOME=$SCR/home DOSSIER_CONFIG=$SCR/cfg.json DOSSIER_CACHE=$SCR/cache PYTHONDONTWRITEBYTECODE=1
D="uv run $SKILL/scripts/dossier.py"
cd $SKILL
```

**Block S: setup.** Full clones, so history cards have data. Never change them.

```bash
mkdir -p $SCR/src $SCR/truth
[ -d $SCR/src/rw ] || git clone -q https://github.com/gothinkster/node-express-realworld-example-app $SCR/src/rw
[ -d $SCR/src/bp ] || git clone -q https://github.com/alan2207/bulletproof-react $SCR/src/bp
git -C $SCR/src/rw checkout -q $RW_PIN && git -C $SCR/src/bp checkout -q $BP_PIN
git -C $SCR/src/rw merge-base --is-ancestor $RW_PIN origin/master && echo rw-trusted
git -C $SCR/src/bp merge-base --is-ancestor $BP_PIN origin/master && echo bp-trusted
git -C $REPO status --porcelain > $SCR/repo-status-before
RW=$SCR/src/rw; BP=$SCR/src/bp; OUT=$DOSSIER_HOME/rw; OUTB=$DOSSIER_HOME/bp
```

Expect both `-trusted` lines. If either is missing, the commit is no longer on the default branch: stop and report, and do not reach for `--allow-ref`.

**Block A: `doctor`.** `$D doctor $RW; echo "exit $?"`. Expect `node`, `npm`, `git`, `uv` ok; dependency-cruiser 18.7.0, knip 6.42.1, scip-typescript 0.5.2, typescript 6.0.3 "from a lockfile with npm"; a `skill:` line; exit 0.

**Block B: `prepare`.** `$D prepare $RW --ref $RW_PIN --full --restore yes > $SCR/p1.json; echo "exit $?"`. Expect exit 0, mode `full`, adapters `js` and `repo` ok with every tool `ok`, and restore `ok`. Then:

```bash
python3 - "$OUT" <<'PY'
import json, sys, pathlib, collections
out = pathlib.Path(sys.argv[1])
for f in sorted((out / "extract").glob("*.json")):
    d = json.load(open(f))
    print(f.stem, {k: (len(v["items"]), {t: s["status"] for t, s in (v.get("tool_status") or {}).items()}) for k, v in d["adapters"].items()})
g = json.load(open(out / "extract/graph.json"))["adapters"]["js"]["items"]
print(collections.Counter(i["kind"] for i in g))
e = json.load(open(out / "extract/entry_points.json"))["adapters"]
print(collections.Counter(i["kind"] for a in e.values() for i in a["items"]))
PY
```

Record the counts. Expect all eight outputs non-empty, except possibly `dead`. Prisma's generated client is not created, because install scripts are off. Record how that shows in `symbols`; it is a finding, not a failure.

**Block C: candidates.** For `entry`, `data`, `io`, `components`, `reading`: `$D candidates $RW --report <id>` prints their sections. Record anything that looks wrong under "Findings for the milestone review".

**Block D: write the reports.** As Claude, follow `SKILL.md` `/dossier build` steps 2 to 5 with `DOSSIER` = `$D`, in the order D12 of plan 009 gives. Write **every** report into `$OUT/reports/`. Then `for r in entry components interactions io data behavior change conventions ops reading; do $D candidates $RW --report $r --open; done` prints nothing. **Do not read the truth file while writing.**

**Block F: render.** `$D render $RW > $SCR/r1.log; echo "render exit $?"`, then `grep -E '^(error|warning|info):' $SCR/r1.log | sed -E 's/^(error|warning|info): (V[0-9]+).*/\1 \2/' | sort | uniq -c`. Expect exit 0 and no `error:` line, which covers V1, V4, V5, V6, V8 and V10. V2 and V3 may warn, and each goes to Gaps. Count the rounds.

**Block G: `dossier check`.** `$D check $RW; echo "exit $?"`. Expect `problems: 0`, which covers V8, V11 and V12 at 1500 and 400 px in light and dark. Run `$D render $RW` once more. Read the shots of reports 04, 05, 06 and 08 at both widths with the Read tool.

**Block H: counts against sources.**

```bash
python3 - "$OUT" <<'PY'
import json, re, sys, pathlib
out = pathlib.Path(sys.argv[1]); h = next(out.glob("dossier-*.html")).read_text()
ex = lambda n: [i for a in json.load(open(out / f"extract/{n}.json"))["adapters"].values() for i in a["items"]]
print("entities", sum(i.get("kind") != "migration" for i in ex("models")), "fields", sum(len(i.get("fields") or []) for i in ex("models")))
def rows(cid):
    m = re.search(r'data-card="%s".*?<tbody>(.*?)</tbody>' % re.escape(cid), h, re.S)
    return m.group(1).count("<tr") if m else None
for c in ("data.entities", "entry.catalog", "io.inputs", "change.dead-code"): print(c, rows(c))
print("gaps blind spots", h.count("Static analysis may miss"))
print("partial badges", h.count('class="badge partial"'))
s = json.load(open(out / "summary.json")); print({k: len(v) for k, v in s.items() if isinstance(v, list)}, s["extractors"])
PY
```

Expect `data.entities` rows equal to entities, a blind-spot count above 0, 0 partial badges, and `summary.json` listing the JS tools as `ok`.

**Block L: public API.** `RW` declares no API, so report `io`'s card must show `No package here declares a public API.` and no `t-io-contracts-api` table, and there must be no `public-api` item. Block R repeats this for `BP`. Real rows are proved on `JSFIX` and in block Y.

**Block T: recall and precision.** Check the hash of the truth file first. Then `python3 tests/tools/ground_truth.py $SCR/truth/rw.json $OUT/reports --review $SCR/truth/review.md`. Targets: entry points recall 100%, precision at least 95%; inputs and outputs recall at least 95%. Add to `review.md` every disagreement, with the cited line, the Gaps entry or blind-spot rule you think explains it, and each `entry.catalog` row the tool could not match. **Do not decide them, and never edit the truth file:** Phase 4a rules. Record under "Verification results (Phase 4)" the recall, precision, inputs and outputs recall, and the number of disagreements.

**Block J: incremental rebuild.** Never commit to `RW`'s clone; use a copy.

```bash
J=$SCR/j; mkdir -p $J/home && cp -r $OUT $J/home/rw2 && git clone -q $RW $J/rw2 && git -C $J/rw2 checkout -q $RW_PIN
printf '\n// verification edit\n' >> $J/rw2/src/app/routes/tag/tag.service.ts
git -C $J/rw2 -c user.name=Check -c user.email=check@example.com commit -qam "verification edit"
DOSSIER_HOME=$J/home DOSSIER_CACHE=$J/cache $D prepare $J/rw2 --no-restore > $SCR/p2.json; echo "exit $?"
python3 -c "import json;p=json.load(open('$SCR/p2.json'))['update_plan'];print(p['mode'],sorted(p['stale']),len(p['fresh']))"
```

Expect mode `incremental`. `entry`, `data` and `interactions` should not be stale: a comment changes no finding. Record the list and each reason. Record whether `components` is stale, as Python's was.

**Block N: Node removed.** A fake `node` that fails, first on `PATH` (section 3, row 34):

```bash
N=$SCR/n; mkdir -p $N/bin $N/home; printf '#!/bin/sh\nexit 1\n' > $N/bin/node; chmod +x $N/bin/node
PATH=$N/bin:$PATH DOSSIER_HOME=$N/home DOSSIER_CACHE=$N/cache $D doctor $RW; echo "doctor exit $?"
PATH=$N/bin:$PATH DOSSIER_HOME=$N/home DOSSIER_CACHE=$N/cache $D prepare $RW --ref $RW_PIN --no-restore > $SCR/p3.json; echo "prepare exit $?"
PATH=$N/bin:$PATH DOSSIER_HOME=$N/home DOSSIER_CACHE=$N/cache $D prepare $RW --ref $RW_PIN --no-restore --allow-missing > $SCR/p4.json; echo "allow exit $?"
cp -r $OUT/reports $N/home/rw/ ; DOSSIER_HOME=$N/home DOSSIER_CACHE=$N/cache $D render $RW --allow-errors > $SCR/r3.log; echo "render exit $?"
H=$(ls $N/home/rw/dossier-*.html); grep -c 'class="badge partial"' $H
for s in "The tool node was not installed" "Made without dependency-cruiser" "Made without knip" "Made without scip-typescript"; do grep -q "$s" $H && echo "found: $s" || echo "MISSING: $s"; done
```

Expect `doctor` to report `node` missing with the install text and exit 1. Expect `prepare` to stop with exit 2 and the same text, a clear failure. With `--allow-missing`, exit 0: `entry_points` still holds semgrep's routes and the package entries, the four tools are `skipped`, and all four `found:` lines print. `--allow-errors` is right here, because the reports were written against a full build. Then run without the fake `node`: `$D prepare $RW --ref $RW_PIN --no-restore` in `$N`'s home must **not** reuse the `js` section.

**Block K: an untrusted ref.** A commit that is on no default branch:

```bash
K=$SCR/k; mkdir -p $K/home && git clone -q $RW $K/rw3 && git -C $K/rw3 checkout -q -b side $RW_PIN
git -C $K/rw3 -c user.name=Check -c user.email=check@example.com commit -q --allow-empty -m "side branch"
SIDE=$(git -C $K/rw3 rev-parse HEAD)
DOSSIER_HOME=$K/home DOSSIER_CACHE=$K/cache $D prepare $K/rw3 --ref $SIDE > $SCR/p6.json; echo "exit $?"
python3 -c "import json;d=json.load(open('$K/home/rw3/extract/entry_points.json'))['adapters']['js'];print(d['tool_status'],len(d['items']))"
DOSSIER_HOME=$K/home DOSSIER_CACHE=$K/cache $D prepare $K/rw3 --ref $SIDE --allow-ref --no-restore > $SCR/p7.json; echo "exit $?"
python3 -c "import json;d=json.load(open('$K/home/rw3/extract/entry_points.json'))['adapters']['js'];print(d['tool_status'],len(d['items']))"
```

Expect exit 0 both times. The first run shows the four Node tools `skipped` with the fixed reason, `semgrep` and `tree-sitter-language-pack` `ok`, and routes in the items, and no restore ran. The second shows the four Node tools no longer `skipped`. Each is `ok`, except that knip may be `failed` with a reason, because this run installed no packages and knip loads the repository's config.

**Block P: the Python golden.** The same repository, before and after M4.

```bash
P=$SCR/p; mkdir -p $P/a $P/b; git -C $SKILL worktree add -q $P/code $BASE_SHA
BASEDIR=$P/code/configs/user/claude/.claude/skills/dossier
for side in a b; do cp -r $LIVE $P/$side/cannalerts && chmod -R u+w $P/$side/cannalerts; done
DOSSIER_HOME=$P/a DOSSIER_CACHE=$P/ca uv run $BASEDIR/scripts/dossier.py prepare $REPO --ref $PIN --full --no-restore > /dev/null; echo "a $?"
DOSSIER_HOME=$P/a DOSSIER_CACHE=$P/ca uv run $BASEDIR/scripts/dossier.py render $REPO --allow-errors > $P/a.log; echo "a render $?"
DOSSIER_HOME=$P/b DOSSIER_CACHE=$P/cb $D prepare $REPO --ref $PIN --full --no-restore > /dev/null; echo "b $?"
DOSSIER_HOME=$P/b DOSSIER_CACHE=$P/cb $D render $REPO --allow-errors > $P/b.log; echo "b render $?"
python3 - $P/a/cannalerts $P/b/cannalerts <<'PY'
import json, sys, pathlib, re, subprocess
a, b = map(pathlib.Path, sys.argv[1:3]); bad = 0
for f in sorted((a / "extract").glob("*.json")):
    x, y = json.load(open(f)), json.load(open(b / "extract" / f.name))
    for name in x["adapters"]:
        i, j = x["adapters"][name]["items"], y["adapters"].get(name, {}).get("items")
        if i != j: print("DIFF", f.stem, name, len(i), len(j or [])); bad += 1
    if set(y["adapters"]) - set(x["adapters"]): print("NEW SECTION", f.stem, set(y["adapters"]) - set(x["adapters"])); bad += 1
pa, pb = next(a.glob("dossier-*.html")), next(b.glob("dossier-*.html"))
for rid in re.findall(r'<section class="report" id="([^"]+)"', pa.read_text()):
    if rid == "dossier": continue          # holds the version, the time and the skill commit
    d = [subprocess.run(["python3", "tests/tools/report_section.py", str(p), rid, "--digest", "--normalize"], capture_output=True, text=True).stdout.split()[0] for p in (pa, pb)]
    if d[0] != d[1]: print("DIFF report", rid); bad += 1
print("SAME" if not bad else f"{bad} differences")
PY
git -C $SKILL worktree remove --force $P/code
```

Expect `SAME`. Items are compared, not adapter versions, so `repo` going to `3` is not a difference. `--no-restore` on both sides keeps the comparison fair. If `cannalerts` reports fail `render` in the same way on both sides, that is fine: only the difference counts. A real difference is a bug in M4; fix it with a test.

**Block E: report 02 HTML unchanged.** Compare with `BASE_SHA`, not a fixed digest (plan 009, Phase 1):

```bash
E=$SCR/e; rm -rf $E; mkdir -p $E/w $E/m; git -C $SKILL worktree add -q $E/code $BASE_SHA
BASEDIR=$E/code/configs/user/claude/.claude/skills/dossier
for side in w m; do cp -r $FIX $E/$side/encamp && chmod -R u+w $E/$side/encamp && rm $E/$side/encamp/dossier-encamp.html; done
DOSSIER_HOME=$E/w $D migrate /home/nick/dev/projects/encamp > /dev/null; DOSSIER_HOME=$E/w $D render /home/nick/dev/projects/encamp --allow-errors > $E/w.log
DOSSIER_HOME=$E/m uv run $BASEDIR/scripts/dossier.py migrate /home/nick/dev/projects/encamp > /dev/null; DOSSIER_HOME=$E/m uv run $BASEDIR/scripts/dossier.py render /home/nick/dev/projects/encamp --allow-errors > $E/m.log
for side in w m; do python3 tests/tools/report_section.py $E/$side/encamp/dossier-encamp.html overview --normalize --write $E/$side.html; sed -Ei 's/ data-[ab]="[0-9]*"//g' $E/$side.html; done
wc -c $E/w.html $E/m.html
[ -s $E/w.html ] && cmp -s $E/w.html $E/m.html && echo OK || echo DIFFERENT
git -C $SKILL worktree remove --force $E/code
```

Expect `OK`, with both files about 250,000 characters. `report_section.py` prints nothing unless given `--digest` or `--write`, so the `-s` test guards against comparing two empty files. G2 is not part of this plan's exit until the author remakes its baselines (Q7). If they are remade, run it and record the result.

**Block I: the suites.** Default and `DOSSIER_SLOW=1`, run alone, not beside a build. Record counts and time.

**Block R: the React repository.**

1. Blocks A, B, C on `$BP` with `--ref $BP_PIN`, `OUTB`. Expect three yarn restores `ok`, one per app, and the `js` adapter `ok`. Record time per tool and per app.
2. Confirm projects: three, with root `apps`, and `source-root` items accordingly.
3. Confirm `ui-route` items for `apps/react-vite`, with paths resolved through `paths.*`, and `http-route` items for the Next apps, including `[discussionId]`.
4. Block D on `$BP`, all reports. **`components.catalog` paths with `[discussionId]` must pass V4.**
5. Blocks F, G, H, L. `interactions.graph` shows the React table. Read the shots of reports 04, 05 and 06 at both widths, and check the area diagrams.

No ground truth is built for `BP`: it is the React check, and section 11's figures are measured on `RW`. A hand count of `apps/react-vite`'s routes against `entry.catalog` is recorded, because it is cheap (about ten rows).

**Block M: a mixed repository.** Python backend, TS frontend, built from fixtures, so nothing real is needed:

```bash
M=$SCR/m; mkdir -p $M/repo/backend $M/repo/frontend
cp -r tests/fixtures/pyrepo/. $M/repo/backend/ && cp -r tests/fixtures/jsrepo/packages/web/. $M/repo/frontend/
git -C $M/repo init -qb main && git -C $M/repo add -A && git -C $M/repo -c user.name=T -c user.email=t@x.io commit -qm fixture
DOSSIER_HOME=$M/home DOSSIER_CACHE=$M/cache $D prepare $M/repo --no-restore > $SCR/p5.json; echo "exit $?"
```

Expect exit 0 and adapters `js`, `python` and `repo` ok. Write the reports as in block D (the repository is small). `render`, then `dossier check`, must give `problems: 0`, with rows from both languages in `entry.catalog`, `data.entities` and `interactions.graph`, and Node tools named on the process card beside Python's.

**Block Y: public API on a real library.** No restore, because `LIB` pins pnpm 11 and nothing here needs its packages. Only `prepare` runs.

```bash
L=$SCR/src/lib; [ -d $L ] || git clone -q https://github.com/pmndrs/zustand $L
git -C $L checkout -q $LIB_PIN
git -C $L merge-base --is-ancestor $LIB_PIN origin/main && echo lib-trusted
$D prepare $L --ref $LIB_PIN --full --no-restore > $SCR/pl.json; echo "exit $?"
```

Expect `lib-trusted` and exit 0. Then in the `public-api` items of `extract/symbols.json`:

- every item has `audience` `marked private`;
- subpath `.` holds `create` and `useStore` (defined in `src/react.ts`) and `createStore` and `StoreApi` (defined in `src/vanilla.ts`), which proves the chain through `export *`;
- subpath `./middleware` holds `persist` (defined in `src/middleware/persist.ts`), `StateStorage` and `unstable_ssrSafe`, and does not hold `ssrSafe`, which proves renames;
- no subpath `./package.json`, and no subpath from `src/types.d.ts`;
- no `resolved: false` entry, and no `api_unresolved` row for a relative import. A row for an uninstalled package is allowed, and must reach Gaps.

A failure is a finding, handled as in M4-28. Record the item count. `LIB` is not read further, and its output is not committed.

**Block X: same skeleton.** `python3 tests/tools/skeleton.py $OUT/dossier-*.html $OUTB/dossier-*.html $M/home/*/dossier-*.html $P/b/cannalerts/dossier-*.html; echo "exit $?"`. Expect exit 0.

**Block Z: the end.** `diff <(git -C $REPO status --porcelain) $SCR/repo-status-before` prints nothing. `git -C $SKILL worktree list` shows one worktree. `git -C $RW status --porcelain` and `git -C $BP status --porcelain` print nothing. Keep `$SCR` for the author's review; say its path.

**Order.** Phase 4: S, A, B, C, D, F, G, H, T, J, N, K, P, E, I. Phase 5: R, M, X, I, E, Z. Clear `$SCR/j`, `$SCR/n` and `$SCR/p` between blocks if `df` shows under 5 GB free.

**Recording results.** Under each phase's "Verification results" write the date, branch and model. For each block, write the key output lines, the render rounds, tool times, the page size, what was cut and why, and a "Deviations" list. Findings about rule precision go under "Findings for the milestone review", not into fixes, unless they are a crash, a V1 failure, or a miss of block T's targets.

---

## 7. Risks and open questions

### Risks (most important first)

1. **The second acceptance test may change this plan.** Its findings come first, and M4 copies the Python approach, so a flaw in that approach would repeat for a second language (Q1).
2. **No tool in this plan has been run.** I was told not to install anything, and this machine's Node is too old to run them. Flags and output shapes come from docs, registry metadata and source. M4-1 goes first for this reason, and Phase 2 is told to trust its results over this text. Knip's report of an unused file, and dependency-cruiser's `summary.violations` fields, are the least certain.
3. **Recall of 100% on entry points may need rule work.** `RW` is small, but routes split over a multi-line call, a prefix, and an entry file known only from `project.json` and `app.listen`. D6 covers each one, untested. Block T may send Sonnet back to fix rules, and Phase 4 may run long.
4. **Without install scripts, some tools see less.** Prisma's generated client is absent in `RW`, so references into it stay unresolved. Knip loads repository config with `jiti`; `BP`'s configs import packages, so a failed restore makes knip fail. That is a "partial" badge, not a silent loss, but it would mean `change.dead-code` is thin.
5. **`BP` is three near-copies of an app.** Rows, V5 decisions and Claude's time are about three times `RW`'s, and the same findings repeat. D16 gives it a session of its own, but it may not fit. The one-row-per-entity rule (A5) gives no shortcut.
6. **The Node upgrade changes the ground under Python.** scip-python has only run on Node 20 here. Phase 1's first step tests that, and block P compares both sides on the same Node, so it would not catch a change caused by the upgrade itself.
7. **Semgrep JS patterns are unproven.** `$R.$M("...", $H, ...)` with a receiver regex relies on naming. A router called `users` would be missed. That is a real recall risk on repositories other than `RW`, and it is why `string-route` and `route-mount` exist.
8. **The reuse key ignores whether a restore ran** (D14). It is the same for Python.
9. **`ts_facts` memory on large repositories.** `--max-old-space-size=4096` is a guess. A failure gives a `failed` tool and partial cards, not a crash.
10. **Prisma's language is moving.** The current docs describe `contract.prisma` and `prisma.config.ts`. `RW` uses a Prisma 4 `schema.prisma`, which is what the fixture tests. The parser reads any `*.prisma`, but a connection string in `prisma.config.ts` is not found.
11. **`yarn.lock` and pnpm paths are tested only on tiny cases until `BP`** (yarn classic), and berry and pnpm are never tested on a real repository in this plan.
12. **`/usr/bin` first?** After the upgrade, if the new Node is not ahead of `/usr/bin/node` on `PATH`, `sandbox._host_path` still puts the found folder first, so it works; but a shell started without the version manager finds Node 20. `doctor` shows it, and Phase 1 step 3 checks it.
13. **The TS figures are provisional.** The author is new to TS, and both models are Claude, so a shared blind spot can survive Phases 3a and 4a. Corrections come from work codebases (S1, D18).
14. **The real public API is proved on one real library.** `RW` and `BP` declare none, so D17 rests on `JSFIX` and on `LIB` (block Y). `LIB` is a single package with `exports` and `paths`. A package mapped only through `outDir`, or a monorepo of published packages, is tested on the fixture alone.

### What I could not verify (open facts)

- **O1.** Whether pnpm reads `npm_config_store_dir`. The settings page I could read names `storeDir` without saying how to set it from the environment. M4-1 step 8 tests it. Fallback: pass `--store-dir <area>/cache/pnpm` on the command line.
- **O2.** Whether pnpm follows a repository's `packageManager` field and downloads another version. The page I read did not mention `managePackageManagerVersions`. If it does, M4-1 step 8 finds it. A restore may run repository code anyway (spec decision 5), but this breaks rule 7's spirit, so record it.
- **O3.** The exact `get_language` strings of tree-sitter-language-pack. The README shows display names only. `typescript`, `tsx`, `javascript` are assumed; M4-1 step 6 decides.
- **O4.** Whether `// ruleid:` works, and whether `semgrep --test` finds a `.tsx` target. The docs show `#` only. M4-1 step 7 decides.
- **O5.** Whether semgrep parses `.mts` and `.cts` when named on the command line. M4-1 step 7 decides, and D10 has the fallback.
- **O6.** Knip's JSON for unused files, and `IViolation`'s fields. M4-1 decides.
- **O7.** Whether `--ts-config` is honoured beside `--no-config`. M4-1 decides.
- **O8.** Whether `getExportsOfModule` returns every name through chained `export *` barrels, and what `export *` from an uninstalled package gives. The sources show the API, not this case. M4-13a decides, and D17 has the fallback.

**What I read.** In full: the spec, `process.md`, `post-v1.md`, `SKILL.md`, `adapters.py`, `py_adapter.py`, `py_tools.py`, `ts_worker.py`, `semgrep_worker.py`, `shared_tools.py`, `tools.json`, `toolcheck.py`, `restore.py`, `sandbox.py`, `scip_tool.py`, `scip_read.py`, `checks_v7.py`, `stages.py`, `config.py`, `repo_adapter.py`, `candidates.py`, `components.py`, `graphs.py`, `workarea.py`, `incremental.py`, `measured_er.py`, `markers.py`. In part: plans 007 (D1 to D13, Phase 1, verification, risks, questions, spec issues), 008 (sections 1, 2, 3.1, 4, 5, Results, 7 to 10), 009 (sections 1 to 4, Results, verification, risks, spec issues), `process.py`, `page_audit.py`, `measured.py`, `measured_change.py`, `measured_graph.py`, `measured_blast.py`, `measured_upgrade.py`, `measured_tables.py`, `checks.py`, `checks_v3.py`, `gather.py` (language, noise and test patterns), `deps.py` (its JS adapter), `py_queries.py` (names and two queries), `render.py` (citations), `test_rules.py`, `conftest.py`, `m3_page.py`, `report_section.py`. Searched only, by keyword: `prompts/method.md`, `prompts/reports.md`, `rules/python/*` beyond `blindspot.yml`, `check_page.py`, `check_layout.py`, `summary.py`, `dossier.py`. Line numbers given for the prompts are from those searches. **Not read:** `assets/`, `viewer.py` beyond its lexer call, `migrate.py`, `LIVE`.

### Questions for the human

All answered by the author on 2026-11-05.

- **Q1. Did the acceptance pause happen?** The repository shows no sign of it. If you built and judged a Python repository, what did you find, and does it change the spec or this plan? If you did not, do you want to do it first, as `process.md` says, or start M4 now? Default: none; this is yours. I recommend doing it first. A full 0.8.0 build of `cannalerts` is cheap next to M4, and M4 repeats whatever it would find. **Answer:** the author ran one after M2 and will run a second before M4 is implemented. Phase 1 waits for it.
- **Q2. Node.** This machine has Node 20.19.2 in `/usr/bin`. M4 needs 22.13 or later, for implementation and for every JS build. Upgrade it? Default: install Node 24 LTS before Phase 1. `asdf` is present but has no Node plugin. **Answer: yes, it can be upgraded.**
- **Q3. Five sessions**, where `process.md` says one? Default: yes (D16). **Answer: default.**
- **Q4. yarn and pnpm.** The spec names only `npm ci`, but `BP` needs yarn. Default: support yarn classic, berry and pnpm from the shipped lockfile (D3, S6). The smaller option is yarn classic only, with Gaps items for the other two. **Answer: default.**
- **Q5. React table.** Add it to `interactions.graph` as a measured table (D9, S3)? Default: yes. Alternatives: `components.map`; or no card at all, printing it only through `dossier candidates`, so Claude uses it in writing. **Answer: default.**
- **Q6. Installing third-party code.** Verification runs `npm ci` and `yarn install` for `RW` and `BP` on this machine, with install scripts off, and `RW` and `BP` config files load through knip. The spec accepts this risk for your own repositories (decision 5). Are you happy to accept it for these two? Default: yes. **Answer: default.**
- **Q7. Report 02 golden.** G2 has failed since `5518e74`. Will you remake its baselines before Phase 4, so report 02's look is checked in M4? Default: no; block E still proves the HTML is the same. **Answer: default.**
- **Q8. `BP` as one dossier.** Default: yes, the whole repository, three apps. Alternative: build only `apps/react-vite`, which needs a subfolder scope the spec does not have. **Answer: default.**
- **Q9. Who reviews the ground truth?** You do not know `RW`, so Sonnet writes both the ground truth and the dossier, in separate steps of one phase. Default: accept that, with your ten-row spot-check. For a stricter test, a fresh session could write the truth file. **Answer:** Opus writes the ground truth and rules on disagreements, Sonnet builds the dossier, and the author keeps the spot-check (D18).

---

## 8. Spec issues

All ruled by the author on 2026-11-05, and written into the spec as decisions 33 to 46.

- **S1. Sections 10 and 11 assume the author's own apps.** Item 2 says "Three of your own solo-built apps (one Python, one TS/React, one C#)". Item 3 says "you are the ground truth". The author has no TS, JS or C# repository. **Proposed wording.** Item 2: "Three repositories (one Python, one TS/React, one C#) build without manual intervention, and their reports have identical card skeletons, checked mechanically. The Python one is your own. For a language where you have no repository of your own, a public repository pinned to a commit may stand in." Item 3, first line: "Measured against ground truth: your own knowledge for your own repository; for a public repository, a list of entry points and inputs and outputs written by hand from the source before the build, without reading the dossier, and spot-checked by you (at least ten rows of the list and ten rows of the dossier)." The "you agree with the component map" line becomes: "for your own repository only; for a public one, every component's paths and responsibility are checked against the code in the same spot-check." Section 10's M4 and M5 rows change "golden TS repo" and "golden C# repo" to "the TS repositories" and "the C# repository named in that milestone's plan". This also covers M5. I did not work around it: the plan runs the check as proposed, and if you rule otherwise, block T changes and nothing else. **Ruling:** accepted, with a change. The author is new to TS and C#, has no repositories to test against, and will correct dossier when taking over codebases at work. So the TS and C# results are provisional, Opus does the component check, and `post-v1.md` records the follow-up.
- **S2. DI has no home.** 6.2 says semgrep finds DI registration for TS, but no category, home card or 6.1 row takes it, and 6.4's TS list omits it. Proposal: for TS, a blind-spot pattern, so hits reach Gaps, and add it to 6.4. M5 faces the same choice, and C#'s list already has it. **Ruling: proposal accepted.**
- **S3. The React tree has no output and no card.** 6.2 says the script gives a "React component tree and router config". 6.1 has no output for it, and section 4 no card. Router config fits `entry_points`. The tree needs a place, or principle 1 ("tools find") is not met for it. Proposal: `ui-component` and `renders` in `graph`, and a measured table in `interactions.graph`. This adds a table to a card, not a card, and changes no schema file (Q5). **Ruling: proposal accepted** (Q5).
- **S4. Entry-point kinds.** Section 4 says "package scripts and bins"; 6.1 says "console scripts and package bins", and recall is measured over 6.1's list. Proposal: add to 6.1 package scripts, package `main`, monorepo task targets, server start and browser routes. **Ruling: proposal accepted.**
- **S5. `npx` in 6.2.** All four JS rows say `npx`, which breaks 5.4 rule 7 for the same reason decision 15 gave. Proposal: the rows say "installed from a lockfile shipped with the skill". **Ruling: proposal accepted.**
- **S6. Restores.** 5.1 step 3 names only `npm ci`, and 5.4 rule 3 names no yarn or pnpm cache. Plan 006 limited restores to the root, which leaves `BP` with none. Proposal: name yarn and pnpm, say lockfiles are found in project folders, and add `YARN_CACHE_FOLDER`, `YARN_GLOBAL_FOLDER`, `YARN_ENABLE_TELEMETRY` and `npm_config_store_dir` to 5.4. **Ruling: proposal accepted** (Q4).
- **S7. 5.4 rule 4 says "the Python static extractors still run".** It should say every extractor that loads no repository code, so semgrep and tree-sitter run for JS too. **Ruling: proposal accepted.**
- **S8. 6.2 gives no Node version.** Proposal: "Node 16 for Python alone; Node 22.13 or later for JS or TS". Section 12's decision 3 stands. **Ruling: proposal accepted.**
- **S9. Public surface for TS.** 6.1 defines it for Python only, and Python's rule rests on `_`. Proposal: "For TS and JS, a name is public when it is exported from its file, or is a member of an exported class. A name reachable only through a barrel counts in the file that defines it." This says nothing about a package's real public API, which needs `exports` analysis. It can be refined later. **Ruling: proposal accepted, and the real public API must also be identified and reported, separately.** See D17. The author also chose to test it on a real library (`LIB`, block Y) and to give Python the same report, in M6.
- **S10. Which TS types are entities.** Section 4 says "TS types and interfaces" with no limit, and A5 needs a row for each, with no group decisions. `BP` has 88 declared types in one app, 33 of them `*Props`. Proposal: D7's filter, stated in section 4. The spec's Python list already excludes plain classes, so a filter is in keeping. **Ruling: proposal accepted.** The author isn't yet experienced enough in TS to judge this, so it is one of the things to correct from work codebases.
- **S11. "dynamic `import()`" in 6.4.** A literal `import('./x')` is an edge the tool sees, and is not a blind spot. Proposal: the rule covers computed targets only, and 6.4 says so. **Ruling: proposal accepted.**
- **S12. `change.dead-code` source text.** It lists "unused route/flag detection", which exists for no language (plan 009, S8). Proposal: as S8 proposed. Also, "module nothing imports" is a Python stand-in; for JS, knip's unused files replace it. **Ruling: proposal accepted.**
- **S13. `process.md`.** It lists M4 as one session, and nothing records M2's and M3's real counts. Proposal: update the table (Q3). **Ruling: proposal accepted** (Q3). Done.
- **S14. Plan 009's S10 still stands.** A1 to A9, V11, V12 and `dossier.cards` are not in the spec file. This plan treats them as the spec, as the prompt says. **Ruling:** write them into the spec. Done.

---

## Sources

Checked on 2026-11-05.

| What | Used for | Source |
|---|---|---|
| dependency-cruiser versions, dates, engines, bins, dependencies, `supportedTranspilers` | D2, row 4 | https://registry.npmjs.org/dependency-cruiser and `/18.7.0` |
| `--output-type json`, `--no-config`, `--config`, `--ts-config`, `--ts-pre-compilation-deps`, `--exclude`, `--do-not-follow`, `--no-progress`, `--cache`; config file names; exit codes | D5 | https://github.com/sverweij/dependency-cruiser/blob/main/doc/cli.md |
| `ICruiseResult`, `IModule`, `IDependency`, `ISummary` fields (not `IViolation`: O6) | D4, D5 | https://github.com/sverweij/dependency-cruiser/blob/main/types/cruise-result.d.mts |
| TypeScript 7 support waits for an API in 7.1 | D2 | dependency-cruiser 18.1.0 release notes, found through search; https://app.unpkg.com/dependency-cruiser@18.1.0/files/types/dependency-cruiser.d.mts |
| Rule sections and severities | D5 | https://github.com/sverweij/dependency-cruiser/blob/main/doc/rules-reference.md |
| knip versions, dates, engines, bin, `jiti`, `oxc-parser` | D2 | https://registry.npmjs.org/knip and `/6.42.1` |
| `--reporter json`, `--no-exit-code`, `--no-progress`, `--no-config-hints`, `--include`, exit codes 0, 1, 2 | D5 | https://knip.dev/reference/cli |
| JSON reporter shape | M4-9 | https://knip.dev/features/reporters |
| Issue type keys; `dependencies` covers dev dependencies | D5 | https://knip.dev/reference/issue-types |
| scip-typescript versions, dates, engines, dependencies | D2 | https://registry.npmjs.org/@sourcegraph/scip-typescript and `/0.5.2`, `/0.6.1` |
| scip-typescript options, project references, concatenated index, exit on no documents | D5 | `src/CommandLineOptions.ts` and `src/main.ts` at tag `v0.5.2`, https://github.com/sourcegraph/scip-typescript |
| Node 22 and 24 supported; dependencies installed first | row 5 | https://github.com/sourcegraph/scip-typescript/blob/main/README.md |
| 0.5.2 changes only the Docker image; 0.6.0 adds Svelte | D2 | https://github.com/sourcegraph/scip-typescript/releases |
| typescript versions, `main`, and 7.0.2's lack of one | D2 | https://registry.npmjs.org/typescript and `/6.0.3`, `/7.0.2` |
| TypeScript 7.0 ships no API; the new API is expected in 7.1 | D2 | Quoted from the 7.0 announcement in https://dev.to/gabrielanhaia/typescript-7-has-no-stable-compiler-api-yet-thats-why-typescript-eslint-wont-install-4pa and https://mergify.com/blog/native-typescript-compiler-faster-typecheck. One other article disagreed, and I did not read the announcement itself; the registry's missing `main` supports the quote |
| yarn 1.22.22, `preinstall` | D2 | https://registry.npmjs.org/yarn |
| `@yarnpkg/cli-dist` 4.18.1 | D2 | https://registry.npmjs.org/@yarnpkg/cli-dist |
| pnpm 12.15.0, dates, engines | D2 | https://registry.npmjs.org/pnpm |
| `npm ci` requires a lockfile, fails on a mismatch, never writes it; `ignore-scripts` | D3 | https://docs.npmjs.com/cli/v11/commands/npm-ci |
| `--frozen-lockfile`, `--ignore-scripts` for yarn classic | D3 | https://classic.yarnpkg.com/lang/en/docs/cli/install/ |
| `--immutable`, `--mode=skip-build` | D3 | https://yarnpkg.com/cli/install |
| `--frozen-lockfile`, `--ignore-scripts` for pnpm | D3 | https://pnpm.io/cli/install |
| pnpm `storeDir` (partial: O1, O2) | D3 | https://pnpm.io/settings |
| semgrep language keys and extensions, `.d.ts` and `.min.js` excluded | row 39 | https://raw.githubusercontent.com/semgrep/semgrep-interfaces/main/lang.json |
| JavaScript and TypeScript are generally available | D10 | https://docs.semgrep.dev/supported-languages |
| Test annotations and how test files are found (partial: O4) | M4-14 | https://docs.semgrep.dev/writing-rules/testing-rules |
| tree-sitter-language-pack lists JavaScript, TSX, TypeScript (partial: O3) | D8 | https://github.com/xberg-io/tree-sitter-language-pack |
| Prisma model, enum, relation, optional and list syntax; `contract.prisma` | D7, risk 10 | https://www.prisma.io/docs/orm/prisma-schema/data-model/models |
| `exports` beats `main`; unlisted subpaths are blocked; `*` patterns; `null` targets; condition order | D17 | https://nodejs.org/api/packages.html |
| `getExportsOfModule` gives alias symbols that need resolving (partial: O8) | D17 | https://gist.github.com/krisselden/6f1e8640a3edc4438672187f8ee9e878 |
| `getImmediateAliasedSymbol` steps one alias at a time | D17 fallback | https://github.com/Microsoft/TypeScript/pull/25708/files |
| `LIB`: MIT, not archived, pin resolves; its `package.json`, `tsconfig.json`, `src/index.ts`, `src/middleware.ts` and the exported names in block Y, read at the pin | D17, block Y | `gh api repos/pmndrs/zustand`, read only |
| `RW` and `BP` exist; pins resolve; not archived; `RW` has no licence and `BP` is MIT | Section 3 | `gh api repos/...` and shallow clones of each pin, read only |

Measured on this machine: Node 20.19.2, npm 9.2.0, git 2.47.3, uv 0.11.19, `gh` 2.103.2; yarn and pnpm absent; suite baseline at `3a68c36`; `fnmatch` and `INLINE_CITE` on bracket paths; `REPO` holds no JS config files at `5923c09`; type counts in `BP`'s `apps/react-vite/src`.
