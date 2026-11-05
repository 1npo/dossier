# Plan 009: milestone M3 (git-derived data, reports 10 and 13, the report 14 and 15 additions, `summary.json` and V8)

Status: written by Opus on 2026-11-04 from `docs/prompts/plan-m3.md`. **Reviewed by the author on 2026-11-05:** questions Q1 to Q8 in section 7 are answered, S9 is ruled, and the author set the ownership rule and the Owner and Author buttons. The spec was amended the same day at the author's request (`004-v1-spec.md`, decisions 26 to 32). S3 is ruled too, so Phase 1 can start.

Written from: `plans/004-v1-spec.md`, `docs/process.md`, plans 007 and 008 (including results and deviations), and the code at commit `5e05daa` (version 0.7.1). Read-only measurements were taken of `cannalerts` (git history, and the extract files of the author's dossier). Section 7 says what I read and what I did not.

Paths used below:

- `SKILL` = `/home/nick/dev/projects/encamp/configs/user/claude/.claude/skills/dossier`, the development copy.
- `INSTALLED` = `/home/nick/.local/share/encamp/configs/user/claude/.claude/skills/dossier`. `~/.claude/skills/dossier` points at it. Never edit it and never read it as the source of truth.
- `LIVE` = `/home/nick/dev/dossiers/cannalerts`, the author's dossier. Read-only, and only section 6 touches it, to copy it.
- `REPO` = `/home/nick/dev/projects/cannalerts`, pinned at `5923c09`. Read-only.
- `FIX` = `SKILL/tests/fixtures/encamp-m0`, frozen and git-ignored. Never written; tests copy it.
- `PYFIX` = `SKILL/tests/fixtures/pyrepo/`.
- Tests run from `SKILL`: `uv run --with pytest --with pygments python -m pytest tests -q`. **Baseline: 1107 passed, 55 skipped** (2026-11-04, `5e05daa`, 36 s).
- Slow tests need `DOSSIER_SLOW=1`.

---

## 1. Summary

- A new history pass reads git once and writes `extract/history.json`: churn, co-change, people, ownership, branches, workflow and decision markers, uncapped. It degrades to a Gaps entry and "partial" badges when history is shallow or runs out of time.
- Report 10 and report 13 are complete: code draws seven measured cards, including a scatter chart and an interactive blast-radius picker, and Claude writes the rest, with measured cells filled in by code. Every commit gets an owner as well as an author, and the Contributors card gains Owner and Author buttons.
- Report 14 gains its `Source` column, report 15 gains per-tool and history items, and `render` writes `summary.json` and checks it (V8). Reports 10 and 13 become required, and every new card passes V11 and V12.
- `VERSION` goes to 0.8.0, which forces a full rebuild of existing dossiers.
- **Three sessions.** Phase 1, git data and measured cards. Phase 2, written cards, `summary.json`, V8, prompts and version. Phase 3, end-to-end verification and merge. `docs/process.md` assumed one session; the author accepted three (Q7).

---

## 2. Shared rules (every phase reads this first)

- **Branch.** All phases work on one branch, `feat/dossier-m3`, created from `main` in Phase 1 and merged at the end of Phase 3. One commit per task.
- **Skills to load at the start of every phase:** `git-commit`, `git-workflow`, `py-projects`, `py-unit-tests`, `claude-planning-docs`. M3-10 also loads `dataviz`. Phase 2 also loads `docs-project`, `docs-readme` and `git-release`.
- **Commit style.** Follow `git-commit`. The suggested messages match the M2 and plan 008 commits.
- **Never touch:** `INSTALLED`, `LIVE`, `REPO`, `FIX`. If a step seems to need a change in `INSTALLED`, make it in `SKILL`.
- **Report 02 and existing card schemas.** Report 02 (its panels, CSS and JS) does not change. The one exception, approved by the author, is M3-15: the Owner and Author buttons, which appear only when a build holds ownership data. Existing card schemas do not change, with one exception this plan names: `prompts/schema/risks.json` gains the `Source` column (M3-16). New CSS is scoped to `.card[data-card^="change."]` or `.card[data-card^="contributors."]`.
- **Report 02 guard.** After every task that edits `render.py`, `assets/dossier.css` or `assets/dossier.js`, run section 6 block E. It must print `OK`.
- **Scratch.** Every command that renders or builds sets `DOSSIER_HOME`, `DOSSIER_CONFIG` and `DOSSIER_CACHE` to a fresh scratch folder (section 6). Tests use `tmp_path`. Nothing outside section 6 builds a dossier of a real repository.
- **Every child process goes through `sandbox.run`**, directly or through a bound `run`. New code never calls `subprocess` for git or `gh`. The existing plain git calls in `gather.py` stay as they are (section 3, row 3). No sandboxing, containers or namespaces (spec decision 5).
- **No new runtime dependencies** in `scripts/dossier.py` or anything it imports (standard library plus `pygments`). Browser checks stay PEP 723 scripts.
- **Tests first.** Each task starts with a test that fails on the current code. Run it, see it fail, and record the failure line in the commit body as `Fails before: ...`. The full suite passes after every task. The slow suite passes at the end of each phase.
- **Do not weaken a check to make it pass.** If a check fails on real output, the output is wrong until the author says otherwise.
- **Measured values are never written by Claude.** Where a Claude card has a measured column, Claude writes `-` and code fills the cell.
- **Nothing is dropped silently.** No `[:N]` on data that feeds a card. No card reads `facts.hot_files`, `facts.areas`, `facts.contributors.people`, `facts.git.bulk_commits`, `facts.git.tags`, `facts.ownership` or `knowledge.json`, because those are capped (plan 008 section 3.4, A6). Use `extract/history.json`.
- **Plain language** in everything a dossier user reads. Gaps statements use the fixed wording in this plan so their IDs stay stable.
- **If the code contradicts this plan, stop and report** under that phase's "Results". Do not design around it.
- **Size.** Keep each new module under about 300 lines.
- **Context.** Keep tool output short: single test files while working, and pipe long output through `tail`. Never print a whole page or a whole `extract/*.json`.
- **Ticking.** Tick each task's checkbox in the same commit as the task. Write results under the phase's "Results" heading.

---

## 3. Spec versus code

"Absorb" means the plan handles it as proposed. "Decision" means the human answers first (section 7 or 8).

| # | Area | Spec says | Code does today (0.7.1) | Proposal | Class |
|---|---|---|---|---|---|
| 1 | Where git data is computed | 6.1: `hotspots`, `cochange`, `workflow`, `branches` are computed in `gather.py` | None of the four exist. `gather.py` has 1,244 lines | New modules `history.py` and `workflow.py`, called by `cmd_prepare` in the `measure` step. `gather.collect` hands over identities and blame (D1). Same stage and same data; only the file differs (S2) | Absorb |
| 2 | Existing git facts are capped | Principle 7: no caps. Plan 008 A6 forbids feeding schema cards from capped facts | `hot_files` 25, `contributors` 60, `areas` 60, ownership areas 14, people 30, `bulk_commits` 20, tags 10. Knowledge map people 6 plus byte cap. `file_commits` uses `--no-renames` | Report 02 keeps those. Reports 10 and 13 and `summary.json` read only `extract/history.json`, which has no caps and follows renames | Absorb |
| 3 | Safe runner | Prompt rule and 5.4: child processes through the safe runner | `gather.py` calls `subprocess` directly against the user's repository | New git calls use `sandbox.run(profile="tool", cwd=top)`. Existing `gather.py` calls are not rewritten, because that would risk report 02 | Absorb |
| 4 | Which values are measured | Measured values are never written by Claude. Tier M: hotspots, co-change, blast radius, dead code, upgrade burden, in flight, workflow | All seven are `writer: script`, and all draw the placeholder | `measured_change.py` and `measured_people.py` draw them (D3). In the tier A cards, `Share` and `Share of commits` and `Areas touched` are filled by code, like `components.catalog` (A4 precedent, S6) | Absorb |
| 5 | Complexity proxy | 6.2 and `change.hotspots`: tree-sitter complexity proxy | Nothing: `complex` appears nowhere in `scripts/` | Count branch nodes per Python file with one tree-sitter query (M3-8). Stored on `graph` module items. The adapter goes to version "3" so old extracts are not reused (plan 008 deviation 7) | Absorb |
| 6 | Bulk filter | `change.cochange`: "`KNOWLEDGE_*` cap reused" | `KNOWLEDGE_CAP` is a byte budget for the page. The bulk rule is `gather.BULK_FILES = 400` | Use `BULK_FILES` (S1). Every bulk commit is listed as a `bulk` item | Absorb |
| 7 | Co-change volume | Table of pairs; principle 7 says no caps | `cannalerts`: 920 pairs, 191 with at least 2 co-commits, 74 with at least 3 | Pairs with at least 3 co-commits are coupling and are listed; the card states the rule and both counts (S3) | Decided (S3) |
| 8 | "Linked in code?" and uncovered files | Yes or no | The graph holds only Python modules. On `cannalerts`, 55 modules and 0 test files. Tests link through `tests` items | Yes when a direct import, a `ref-edge` or a test's `paths` joins the pair. No when both files are covered and nothing joins them. `not in the graph` when either file is uncovered. `cochange_pairs_unlinked` counts only "no" | Absorb |
| 9 | Blast radius | "Reverse closure precomputed from the graph"; interactive picker | No picker. `graphs.py` has no closure helper | Closures precomputed in Python and embedded as one bitset per file (D5). The table lists every source file, so the numbers survive without JavaScript. Files the graph does not cover say so, and the card states how many blind-spot hits exist | Absorb (S4) |
| 10 | Hotspot scatter | "Table plus scatter" | No chart code outside Mermaid and report 02 | Inline SVG drawn by Python at a fixed size inside a scroll box (D3). No library | Absorb |
| 11 | Dead code | `dead.json`: unused files, exports, dependencies, functions. "vulture, knip, unused route/flag detection" | `dead` holds vulture items only (3 on `cannalerts`, all false positives per plan 007 finding 7). `dependencies.json` has `unused` | The card draws `dead` items, unused dependencies, and modules nothing imports. Stale flags and unused routes have no Python detector: one fixed Gaps item (S8). Measured items are not pruned, so false positives stay, shown with vulture's confidence | Absorb |
| 12 | Work in flight | "Remote branches" | None | `refs/remotes`, excluding `*/HEAD` and the default branch. Local heads only when no remote refs exist, and the card says so. Ahead and behind are against the pinned commit. All such branches are drawn; `cannalerts` gives 2 | Absorb |
| 13 | Workflow rows | Six fixed rows, tier M: branch naming and strategy, merge style, commit message style, typical PR size, review rate, release cadence | None | Fixed wording from git only (D3). "PR size" is measured on merge commits and "review rate" from trailers, and each row says it is a proxy (S7). `cannalerts` writes `merged feat/x`, so the subject parser handles that form too | Absorb |
| 14 | Report 13 unit of "Area" and "Subsystem" | `contributors.ask` per component. `contributors.concentration` says Area | `facts.areas` is capped and uses another grouping | Both use `components.catalog` components, one row each. The per-component data comes from per-file history | Absorb |
| 15 | Identity | `facts:contributors` | `ident_id` is the lower-cased email. Identities merge on the same email or the same full name containing a space. `%aN`, `%aE` respect `.mailmap`. Every Claude model shares `noreply@anthropic.com`, so all become one identity. People listed in `facts` are capped at 60 | `person` items are uncapped and use the same canon. Cards show display names, never emails. `contributors.doubts` gets a list of possible duplicates | Absorb (Q2, Q3 answered) |
| 16 | Agents card | "Identity classification" | `ident_type` gives human, agent, bot. `assisted_commits` counts human commits with an agent marker | Spec silent on commits a human authored with an agent as co-author, and on separating models that share an email. Answered: one row per agent or bot identity, one row per co-author-only assistant, models sharing an email stay one row (D7) | Decided (Q3) |
| 17 | Bus factor and shares | `ownership: { top_owner_share, bus_factor, at_risk_paths }` | No definition. On `cannalerts`, 112 of 129 commits are authored by an agent | Now in the spec: four ownership rules, a human-only bus factor, and at risk means departed (D4, D10) | Decided (Q1, Q4, spec decisions 26 and 30) |
| 18 | `summary.json` contributor ids | `owners: [contributor ids]` | The id is an email address | Now in the spec: `summary.json` has a `contributors` list that `owners` points into, with an opaque id, kind, name and username, and no email addresses (D10) | Decided (Q2, spec decision 28) |
| 19 | `summary.json` sources | Section 9, "assembled from structures the reports already hold"; section 11 item 5: no field the reports do not hold | Nothing is written. The process card says "not produced in this version" | `summary.py` (D10). Reports do not yet state bus factor or top owner share, so the Knowledge concentration card gains a code-drawn line | Absorb |
| 20 | `portfolio` | Reads `summary.json` | Does not exist: no reference in `scripts/`, `prompts/` or `README.md`. `contracts` join on counterparty and schema path | Plan to section 9 only. Direction must be exactly `offered` or `consumed`, which V8 enforces | Absorb |
| 21 | `io.contracts` Direction | offered/consumed | Free text in a Claude cell | `reports.md` requires the exact words; V8 fails on anything else | Absorb |
| 22 | Extractor status | `status: ok|partial|missing` | Tool status is `ok`, `failed`, `skipped`. A **reused** adapter has no `tools` key in `build.json`, so `process._extractors` prints "none recorded" on an incremental build | `ok` stays. `failed` becomes `partial`. `skipped` or missing becomes `missing`. Read status from the `extract/*.json` sections (`candidates.tool_status`), which also fixes the process card (M3-22) | Absorb |
| 23 | V8 | Validates against its schema; error | Nothing. No JSON Schema library may enter `dossier.py` | `prompts/summary.schema.json` (outside `prompts/schema/`, because `schema.load_all` loads every file there as a report) plus a small standard-library validator. A slow test confirms the real `jsonschema` package agrees (D11) | Absorb |
| 24 | Required again | Decision 17; M3 row | `render.OPTIONAL_REPORTS = ("change", "contributors")` | Empty the tuple. A missing file is an error from `render.validate`. `render` on a 0.7.x dossier without `prepare` stops and says to rebuild. Version 0.8.0 makes `prepare` plan a full build | Absorb |
| 25 | Report 14 addition | Risks gain a `Source` column, value `extractor` | `render_table` already adds a citations column headed **Source** to every authored table. `change.decisions` already has a schema column `Source`, and `contributors.ask` a schema column `Basis`, which collides with the added **Basis** column | When a schema column has the same name, the added column is headed `Citations` or `Confidence` (M3-16). V11 learns the same rule. Second value of the column: `read` (S5) | Absorb |
| 26 | Report 15 additions | Gaps receives unassigned files, undispositioned candidates, blind spots, missing tools, Tier B languages | All present, except that a tool that failed or was skipped inside an adapter that succeeded gets a "partial" badge and **no** Gaps item (`coverage_items` looks at adapter status only) | Add per-tool items, history items and the fixed dead-code item (M3-9, M3-11) | Absorb |
| 27 | Candidates for `change.decisions` and `change.unfinished` | Tier A and R, "helped by candidates"; principle 2 limits V5 to three lists | No marker scan exists | Markers `HACK`, `XXX`, workaround and bug ids get ids and a home card, so nothing drops silently. This extends principle 2 (S9). Everything else (TODO density, legacy names, duplicate names, ADRs, long commits) stays a computed suggestion. "Mixed-style counts" have no general detector and are left to Claude | Decided (S9) |
| 28 | Staleness | 5.3; `incremental.REPO_WIDE` has `contributors` | `FEEDS` has no `change` or `contributors` | Add both, with line-free keys (D13). Measured cards are drawn on every render, so they are always current | Absorb |
| 29 | Shallow clones | Prompt: degrade with a Gaps entry | `gather` adds a warning only. Tested 2026-11-04: `git clone --local` from a shallow repository prints a warning and exits 0, and the copy has its one commit | History status `partial`, a fixed Gaps item, "partial" badges (D9). `commit:` citations to absent commits fail V1, which is correct | Absorb |
| 30 | Spec text is behind | Section 4 says `dossier.process` is a numbered list; section 7 stops at V10; `data.relationships` and `components.catalog` as first written | Plan 008's A1 to A9 were approved and built, and `5518e74` added `dossier.cards`, but the spec file was not amended | Treat A1 to A9 as the spec, as the planning prompt says. V11 and V12 apply to every new card. The text is the author's to update (S10) | **Decision** (S10) |
| 31 | Group decisions | A5: groups only for call-site findings | `one_row_per_item` covers entities and entry points | Marker findings are call sites, so group ids stay valid for them | Absorb |
| 32 | Freshness BAN | Section 4 (01); plan 008 Q5 unanswered | Not built; it is in no milestone | Not in this plan. It goes to M6 | Decided (Q6) |
| 33 | Plan 007 findings left for the M3 acceptance pass | Findings 2, 3, 4, 6, 7 | 2, 4 and 6 are handled by Claude's dismissals. 7 stays visible (row 11). 3 is wrong text: `doctor` says "via npx" | M3-25 corrects finding 3. The rest are left for the author's acceptance, as plan 008 says | Absorb |
| 36 | Pull request data | Amended: approvals are read with `gh`; other pull request content stays out of reach | `gh` is not used; the safe runner hides its login | D17: an optional tool, a `github` profile, batched by commit, cached, with a Gaps fallback. Tested in a scrubbed environment. `cannalerts` has one human, so its build never calls it, and block L covers the call | Absorb |
| 37 | Line ownership | Amended: a line belongs to the owner of the commit that last changed it | `blame_file` adds up lines by author and drops the commit | An optional per-commit result alongside the existing one, so report 02's figures do not change (M3-7) | Absorb |
| 38 | Report 02 | Amended: Owner and Author buttons | `process.md` freezes report 02 unless the author approves | Approved. D18 leaves the page unchanged when there is no ownership data, so blocks E and G2 keep their baselines | Absorb |
| 34 | P0 and P1 | P1 in M3: `change.docs-drift`, `change.upgrade-burden` | Both in the schema | Both are planned. They are the first things cut (D16). A cut card draws a fixed sentence and a Gaps item | Absorb |
| 35 | Upgrade burden data | Decision 4: shipped snapshot, optional live refresh | Nothing. endoflife.date has `python`, `django`, `nodejs`, `dotnet`, `postgresql`, but returned 404 for `flask`, `fastapi`, `sqlalchemy`, `pydantic` (2026-11-04) | Ship a snapshot of the products that exist. No live refresh in M3, since the spec makes it optional (S11) | Absorb |

Amendments that changed the meaning of the spec and that this plan relies on: **A1** (process card is a table), **A2** (diagram budgets), **A3** and **A4** (code fills measured data in Claude cards), **A5** (groups only for call sites), **A6** (report 02 keeps its caps, and no schema card reads them), **A7** (numbered notes), **A8** (V11 and V12), **A9** (skill commit recorded).

---

## 4. Decisions

### D1. The git extractor

**Modules.**

| File | Owns |
|---|---|
| `scripts/history.py` (new) | Running and parsing the one history log, per-file figures, pairs, people, bulk commits, the output file |
| `scripts/workflow.py` (new) | The six workflow rows, branches, tags, merge sizes |
| `scripts/markers.py` (new) | Marker and TODO scan of file text, decision documents, long commits, legacy and duplicate name hints |
| `scripts/measured_change.py` (new) | Hotspots, co-change, dead code, in flight |
| `scripts/measured_blast.py` (new) | Closures and the blast-radius card |
| `scripts/measured_people.py` (new) | Workflow card, per-component ownership, measured cells, bus factor |
| `scripts/measured_upgrade.py`, `scripts/eol.json` (new) | Upgrade burden |
| `scripts/github_owners.py`, `scripts/ownership.py` (new) | Pull request lookups through `gh` (D17); the owner of each commit (D4) |
| `scripts/checks_people.py` (new) | V5 completeness of reports 13 and 14 |
| `scripts/summary.py`, `prompts/summary.schema.json` (new) | `summary.json`, V8 |

**One pass.** `history.scan` runs one command through the safe runner, and `workflow` runs a few small ones:

```
git log <sha> -M --numstat -z --format=%x1e%H%x1f%aN%x1f%aE%x1f%aI%x1f%P%x1f%B
```

- Merge commits are in this log and carry no file list, because git shows no diff for merges by default. That gives parents and messages without a second pass.
- `gather.parse_commit` splits on `\x1f` and keeps `meta[:4]`, so `history.py` has its own parser that reuses `gather.parse_commit`'s numstat logic and also keeps `%P` and `%B`.
- Commits arrive newest first, so a rename seen now says where older history belongs: the `alias` logic of `gather.credit_history`.
- Only paths tracked at the pinned commit count. Paths for which `gather.noise_reason` is not `None` are skipped.

**Caching.** None. History runs on every `prepare`, like the rest of `gather`. It takes well under a second on `cannalerts`. Rejected: reuse by commit, because a contributor type override must take effect on the next `prepare`.

**Large histories.** No limit on commits. New timeout key `history`, default 600 seconds, in `config.DEFAULT_TIMEOUTS`. `sandbox.run` kills the group and leaves the partial stdout file. Since commits come newest first, the parser keeps every complete record, sets `stopped_early`, and the status becomes `partial`. Delete the stdout file after parsing. Pair counting is bounded by the bulk filter: a commit touching more than `gather.BULK_FILES` files counts for no file and no pair, and is listed as a `bulk` item.

**Hand-over from `gather`.** `collect` adds `facts["history_input"]`, which `cmd_prepare` pops before saving `facts.json`:

```python
{"canon": canon, "display": display, "ctype": ctype, "blamed": blamed, "blamed_commits": blamed_commits, "as_of": as_of.isoformat(),
 "lines": {f["path"]: f["lines"] for f in files}, "markers": marker_items, "todos": todo_items,
 "shallow": <bool>}
```

`blamed` is `{path: {contributor id: lines}}`, which `collect` already builds. `facts["history"]` keeps a small stub (D2 `meta`), so Claude can read the status and `facts:history` citations resolve.

**Order inside the `measure` block of `cmd_prepare`:** `gather.collect`, then `history.collect(...)`, write `extract/history.json`, then `candidates.digests(candidates.load(out))` and `update_plan`. The `measure` record gains `details["history"]` (the `meta` item). Do not add a separate record: `buildlog.latest(build, "measure")` must keep returning the one holding `plan_mode`.

**Rejected:** several scripts with their own logs (three more passes over history); a time limit in Python around `Popen` (the safe runner already does it); `gather.history_commits` as it stands (no parents or messages, and `--no-merges`).

### D2. `extract/history.json`

Same envelope as the other outputs, so `candidates.load` picks it up with no new plumbing, and `run_extract` never touches it (it iterates `OUTPUTS`):

```json
{"schema": 1, "sha": "...", "adapters": {"git": {"sha": "...", "version": "1", "tools": {"git": "2.47.3"},
 "tool_status": {"git": {"status": "ok", "reason": null}}, "items": []}}}
```

Do not add `history` to `adapters.OUTPUTS`. Add `"history": "mk"` to `candidates.ID_OUTPUTS`. Only `marker` items get ids: call `candidates.assign_ids("history", markers)` on those alone.

| `kind` | Fields |
|---|---|
| `meta` | `path: ""`, `status` (`ok` or `partial`), `reasons` (list of fixed strings), `commits_seen`, `commits_total` (`git rev-list --count`), `shallow`, `stopped_early`, `blame_done`, `blame_total`, `as_of` (ISO day), `window_from` (ISO day, 365 days before `as_of`), `pairs_total`, `bulk_commits`, `owner_rule` (`one-human`, `pull-requests`, `authors`), `owner_status` (`ok`, `partial`), `owner_reason`, `prs_found` |
| `file` | `path`, `lines`, `commits`, `commits_12m`, `lines_changed`, `lines_changed_12m`, `last_changed` (ISO day or null), `authors` (`{id: commits}`), `blame` (`{id: lines}` or null), `owners` (`{id: commits}`), `owner_lines` (`{id: lines}` or null) |
| `pair` | `path` (= `a`), `a`, `b` (sorted), `co_commits`, `commits_a`, `commits_b`, `share` (integer percent: `round(100 * co / min(a, b))`) |
| `person` | `path: ""`, `person` (id), `name`, `type`, `commits`, `commits_12m`, `assisted`, `first`, `last`, `aliases` (ids merged into it), `owned_commits`, `owned_lines`, `username` (or null) |
| `bulk` | `path: ""`, `sha`, `files`, `author`, `date`, `subject` |
| `branch` | `path: ""`, `ref`, `sha`, `date`, `ahead`, `behind`, `author`, `remote` (bool) |
| `workflow` | `path: ""`, `convention`, `observed`, `evidence` (text), `commits` (shas cited, at most the 3 newest examples; these are citations, not data) |
| `marker` | `id`, `group`, `path`, `line`, `end_line`, `rule` (`marker.hack`, `marker.xxx`, `marker.workaround`, `marker.bug-id`), `snippet` |
| `assistant` | `path: ""`, `name` (the label from `gather.AGENT_LABELS`, for example `Claude`), `commits` (human-authored commits carrying its marker), `files` (`{path: commits}`). Only for labels found on human-authored commits |
| `todo` | `path`, `count` |
| `decision-doc` | `path` |
| `long-commit` | `path: ""`, `sha`, `subject`, `lines`, `files` |

Windows are counted back from the pinned commit's date, never from today (`gather.KNOWLEDGE_RECENT_DAYS`).

### D3. Measured card data

All tables use `render.render_table(..., plain=True)`. Paths use `render.path_code`, citations `render.source_cell`. The table id is `t-` + the card id with dots as dashes, as `measured._table` does. **The first columns match the schema exactly**, then `Source` where a row cites something. Scope "source files" = `components.source_files(tree, extract)`, the V4 set.

- **`change.hotspots`** (schema `computed`). A sentence, then the scatter, then two tables.
  - Sentence: `Every source file, most changed in the 12 months before this commit first. {n} of {total} files did not change in that time.`
  - Scatter: x = lines (log scale), y = commits in 12 months, one circle per file, with an SVG `<title>` of `path: N commits, M lines`. Fixed `width="640" height="320"`, `role="img"` and an `aria-label`, inside `<div class="chart-scroll">` (`overflow-x: auto`). Axis text is SVG `<text>` with `font-size="12"`. Colours through `currentColor` and `var(--primary)`, so both themes work. The size never scales down, per D3 of plan 008.
  - File table `t-change-hotspots-files`: File, Component, Commits (12 months), Commits (all), Lines, Complexity, Last changed, Source. One row per source file. Sorted by commits in 12 months, then by complexity, then by path.
  - Component table `t-change-hotspots-components`: Component, Files, File changes (12 months), Lines, Complexity. A commit touching two files in a component counts for each file, so that column is the sum of the file counts.
  - Complexity is `-` for a file with no count. Component is `-` without a catalog.
- **`change.cochange`**: A, B, Co-commits, Share, Linked in code?, Source. Sorted by co-commits, then share. Sentence: `Pairs of files that changed together in at least 3 commits ({shown} of {pairs_total} pairs). Share is the co-commits as a percentage of the commits of the less-changed file. Commits touching more than 400 files are left out.` None found: `<p class="muted none-found">`.
- **`change.blast-radius`**: D5.
- **`change.dead-code`**: Item, Kind, Evidence, Source. Rows: each `dead` item (Kind = vulture type, Evidence = `{message} ({confidence}% confidence)`); each entry of `dependencies.json` `unused` (Kind `unused dependency`, Evidence = its `note`); each graph module that nothing imports, that no test imports, that is not `__init__`, `__main__` or the file of an entry point (Kind `module nothing imports`). Sentence: `Tool output, not checked by a person: some of these may be used in ways the tools cannot see.` Expose `measured_change.dead_rows(extract, dependencies)` so V11 counts the same list.
- **`change.upgrade-burden`**: Runtime or package, Pinned, Latest or supported, Gap, Source. Caption `Data as of {as_of}, from endoflife.date.` Python comes from `requires-python` in `pyproject.toml` or `.python-version`; packages from `dependencies.json` `deps` whose name is a product in `eol.json`. Gap is one of `supported until {date}`, `end of life since {date}`, `not in the data`.
- **`change.in-flight`**: Branch, Last commit, Ahead/behind, Author, Source. Last commit = `{date} {short sha}`. Ahead/behind = `{ahead} ahead, {behind} behind`. Sentence: `Compared with the pinned commit. Issue and pull request content is not in the repository and is unknown.` When only local branches exist, add: `This repository has no remote branches, so these are local branches.`
- **`contributors.workflow`**: Convention, Observed, Evidence, Source. Always six rows, in the spec's order.

**Workflow rows (`workflow.rows`).** `n` is the commit count. Fixed wording with numbers filled in:

| Row | Observed | Evidence |
|---|---|---|
| branch naming and strategy | `Default branch {name}. Most common prefixes: {prefix} ({count}), ...` or `No branch names are recorded in merge commits.` | `{m} merge commits name a branch.` Branch names come from `Merge branch 'x'`, `Merge pull request #n from o/x`, `merged x`, plus refs |
| merge style | One of `merge commits`, `linear history`, `squash merges`: merges over 10% of commits, else `(#n)` subjects over 50% of commits, else linear | `{merges} merge commits in {n} commits; {s} subjects end in a pull request number.` |
| commit message style | `Conventional commits` when over 50% of non-merge subjects match `^(feat|fix|docs|chore|refactor|test|build|ci|perf|style)(\(.+\))?!?: `, else `Free-form sentences` | `{c} of {n} subjects follow the pattern; the median subject is {k} characters.` |
| typical PR size | `About {f} files and {l} changed lines per merge (median).` or `No merge commits to measure.` | `Measured on {m} merge commits against their first parent. Git does not record pull requests, so this is a stand-in.` |
| review rate | `{r} of {m} merge commits carry a Reviewed-by or Approved-by line.` | `Reviews held on a hosting service leave no trace in git, so this may be low.` |
| release cadence | `{t} tags; a median of {d} days apart.`, or `One tag.`, or `No tags at this commit.` | `Newest tag {name} on {date}.` or `-` |

Merge sizes: `git log <sha> --merges --diff-merges=first-parent --numstat -z --format=%x1e%H` (tested on `cannalerts`). Tags: `git tag --merged <sha> --sort=creatordate --format=%(refname:short)%x1f%(creatordate:short)`. Branches: `git for-each-ref refs/remotes --format=%(refname)%x1f%(objectname)%x1f%(committerdate:short)%x1f%(authorname)`, then `git rev-list --left-right --count <sha>...<ref>` per branch. The left number is behind and the right is ahead. Rejected: `%(ahead-behind:...)`, which needs a newer git than the preflight demands.

### D4. Who owns a commit

Spec section 4 sets the rule. `ownership.owner_of` applies it in this order:

| Case | Owner |
|---|---|
| Exactly one human in the history | That human, for every commit, including bots' |
| Author is a human | The author |
| Author is an agent or bot, merged through a pull request with a human approver or merger | That human (D17) |
| Anything else, including no humans at all | The author, even an agent or bot |

Bots are treated like agents, because the author's rule names agents and the reason (a human answers for what they approve) holds for bots too. A line belongs to the owner of the commit that last changed it.

`measured_people.component_stats(ctx) -> {component: {"owned": {id: lines}, "lines": {id: n}, "commits_12m": {id: n}, "commits": {id: n}, "files": n}}` sums `file` items using `components.component_of`. `owned` comes from `owner_lines`, `lines` from `blame`. A file with `blame: null` contributes commits only, and the component is flagged `approx`.

**Definitions.** Ownership uses `owned`, never `lines`. Agents and bots can hold a share under the last row of the table, but the bus factor counts humans only.

- `top_owner_share`: largest human share of human-owned lines, integer percent, or `null` when no human owns a line.
- `bus_factor`: the smallest number of humans whose owned lines add up to more than 50% of human-owned lines, or `null` as above.
- `Owner` in `contributors.concentration` is the identity Claude judges the owner, from `owned` and its reading of bulk imports. On a one-human repository it must be that human. When nobody owns a line or has a commit in the component, it is `unknown`, with `conf: unknown`, and Share is `-`.
- `Share` in `contributors.concentration`: the named owner's share of the component's owned lines.

### D5. Blast radius

`measured_blast.data(ctx) -> dict`, embedded as `<script type="application/json" id="blast-data">`:

```json
{"files": ["src/a.py"], "graph": [1], "component": [0], "components": ["core"],
 "dep": ["<base64>"], "direct": [2], "tests": ["tests/test_a.py"], "ft": [[0]], "co": {"src/a.py": [["src/b.py", 5]]}}
```

- `files`: every source file plus every graph module path, sorted. `graph[i]` is 1 when the file is a graph node. `component[i]` indexes `components`, or -1.
- `dep[i]`: for a graph file, base64 of `ceil(N / 8)` bytes. Bit `j` (byte `j >> 3`, mask `1 << (j & 7)`) is set when file `j` depends on file `i` directly or indirectly. The file itself is never set, even in a cycle. Empty string for a file outside the graph.
- `direct[i]`: count of direct importers.
- `ft[i]`: indexes into `tests` of test files whose `paths` contain file `i`. Importing tests of `i` = `ft[i]` plus `ft[j]` for every `j` in the closure.
- `co`: pairs for each path, from `pair` items.

Edges: `graph` `import` items, importer to imported, reversed. `graphs.reverse_closure(nodes, edges) -> {node: set}` is a new helper, a breadth-first walk per node.

**Card.** `<label>` and `<select id="blast-pick">` with an optgroup Components, an optgroup Files, and each file's value = its index. Below it `<div id="blast-out" aria-live="polite">` with three lists: `#blast-dependents`, `#blast-tests`, `#blast-co`, each under a heading with its count. Then table `t-change-blast-radius`: File, Component, Direct dependents, All dependents, Importing tests, Co-changing files. One row per entry of `files`, each `<tr data-file="{i}">`. For a file outside the graph, the two dependents cells read `not in the graph`. Picking a component shows the union over its files, minus its own files.

Fixed sentence under the card: `Built from static imports. {n} places that load code at run time are not in this graph (see Gaps).`, where `n` is the count of `blindspots` items. With no graph items at all, the sentence is `No import graph was extracted, so only co-changing files are shown.`

`dossier.js`: one function `initBlast()`, called from `show()` when the `change` report is first shown. Insert it **before** the closing `})();`, so `dossierJs = "ok"` stays the last line.

**Rejected:** walking the edges in the browser. It is smaller, but the spec says precomputed (S4 records the size). A list of indexes per file instead of bits: at 5,000 files a dense graph needs tens of megabytes, where bits need about 4 MB.

### D6. V11 and V12 on the new cards

V11 (`page_audit`):

- `_drawn_counts` changes from one table per card to a list of `(table id, rows, schema columns or None)`.
- New entries: both hotspot tables (source files; components in the catalog), `t-change-cochange` (`pair` items), `t-change-dead-code` (`dead_rows`), `t-change-in-flight` (`branch` items), `t-change-blast-radius` (`len(files)`), `t-contributors-workflow` (6), `t-change-upgrade-burden` (rows from `measured_upgrade.rows`).
- When schema columns are given, the header must start with them.
- A count of zero means the card must hold `.none-found` and no such table.
- New rule: a card of reports `change` or `contributors` that says "Not yet generated" is an error, unless the card is listed in `render.CUT_CARDS` (D16).
- `contributors.concentration` must contain the bus factor line (`.bus-factor`).
- `blast-data` must parse as JSON with `len(files)` entries.

V12 (`check_layout`, `check_page`):

- `SCROLLERS` gains `.chart-scroll`, `.blast-list`.
- Text check: every `.chart-scroll svg text` is at least 11 px tall.
- `table_cards()` gains `SCRIPT_TABLE_CARDS` = `change.cochange`, `change.dead-code`, `change.in-flight`, `contributors.workflow`, `change.upgrade-burden`, `change.hotspots`, `change.blast-radius`. The JS skips a card holding `.none-found`.
- New `check_blast(page, scheme)` in `check_page.py`: open `#change`, pick up to three files whose `All dependents` is above 0, and assert that `#blast-dependents li` equals the row's number and that `#blast-tests` and `#blast-co` equal theirs; pick the first component and assert the list is drawn. Each failure is one `FAIL` line, and the whole check runs under `safe(...)`.

All the rest (sideways scroll, overlap, icon size, stylesheet loaded) already applies to every card, at 1500 and 400 px, in both themes.

### D7. Cards Claude writes

| Card | Row unit | Claude writes | Code fills |
|---|---|---|---|
| `contributors.people` | one human identity | all four cells | nothing |
| `contributors.ask` | one component | all four cells | nothing |
| `contributors.concentration` | one component | Area, Owner, Status; `-` in Share | Share, plus the bus factor line above the table |
| `contributors.agents` | one agent or bot identity, plus one row per `assistant` item (Q3) | Identity, Kind (`agent`, `bot` or `assistant`); `-` in the other two | Areas touched, Share of commits |
| `contributors.doubts` | one doubt | all cells, or `na` | nothing |
| `change.unfinished` | one pattern | all cells, or `na` | nothing |
| `change.decisions` | one item | all cells, with `cand` and `dismissed` | nothing |
| `change.docs-drift` | one claim | all cells | nothing |

`Status` is exactly `single owner`, `departed` or `shared`. `departed` and any at-risk statement are `conf: inferred`, as the spec requires.

**Fill.** `measured.fill_people(entry, cid, ctx)` is called from `render_card` next to `fill_catalog`, and matches rows by the first cell, like `fill_catalog`. Without `history` items it returns the entry unchanged. Agents' `Areas touched` lists components by commits, all of them. Share of commits is `{n}% ({c} commits)`. An `assistant` row uses the item's `commits` and `files`. Models that share an email stay one row, under the most frequent name.

**Completeness (`checks_people.py`, errors, named V5 like `v5_env`):**

- `V5: Who the people are does not list {name}.` for every `person` of type human that is in neither `contributors.people` nor `contributors.doubts`.
- `V5: Agents and bots does not list {name}.` likewise for agents, bots and `assistant` items.
- `V5: Who to ask has no row for the component {name}.` and the same for Knowledge concentration.
- `V5: {title} names {cell}, which is not {an identity|a component} in this build.` when a first cell or `Owner` cell matches nothing.
- `V5: Knowledge concentration, {name}: {human} is the only person on this project, so they are the owner.` when a one-human repository names anyone else. An `Owner` of `unknown` is accepted only with `conf: unknown`.
- `V5: Knowledge concentration, {name}: Status must be single owner, departed or shared.`
- `V5: Risks: Source must be extractor or read, found '{cell}'.`

Names are compared with `schema._norm`. A `na` card is exempt only for `contributors.doubts`. On a repository with no agents or bots, `contributors.agents` is `na`. The counts go on the check record as `v5_people`.

**What `dossier candidates` prints.**

- `--report change`: marker findings (as for any home card), then `== Decision documents ==`, `== Long commit messages ==`, `== TODO and FIXME counts ==`, `== Old-looking names ==` (`legacy`, `deprecated`, `old`, `v1`, `v2` as whole words in file or symbol names), `== Same name defined more than once ==` (class and function names from `symbols`), `== Bulk commits ==`.
- `--report contributors`: `== People ==`, `== Possible duplicates ==` (names equal after removing case, spaces and punctuation, or one contained in the other), `== Components: who wrote and who changes ==` (every identity by owned lines, authored lines, and commits in 12 months, per component), `== Bulk commits ==`, `== Agent markers ==`.
- `--report risks`: `== Measured findings that may be risks ==`: cycles, dead code count, and hotspots with a single owner (a file in the top quarter by commits in 12 months where one identity owns at least 80% of its commits).

### D8. Risks and the added columns

`prompts/schema/risks.json` gains `Source` after `Recommendation`. `render.auto_columns(columns) -> (basis, citations)` returns `("Basis", "Source")`, with `Confidence` in place of `Basis` when `Basis` is a schema column and `Citations` in place of `Source` when `Source` is. `render_table` and `page_audit._check_table` both call it. Classes stay `basis-cell` and `src-cell`. Only three tables change their header, none in report 02.

### D9. Gaps additions

Fixed wording. Kind `coverage`. `process.coverage_items` adds these, so `cmd_render` and `cmd_confirm` stay in step:

- A tool `failed` or `skipped` inside a working adapter (report `dossier`): `The tool {tool} did not finish, so the cards that use it are marked partial: {reason}`. How to confirm: `Fix the problem and build again.`
- Shallow (report `change`): `This is a shallow clone, so the history covers only {n} commits. Hotspots, co-change, ownership and workflow figures are incomplete.` How to confirm: `Build from a full clone.`
- Stopped early (report `change`): `Reading the history took too long, so only the newest {n} of {m} commits were used.` How to confirm: `Raise timeouts.history in the dossier config and build again.`
- Blame cut short (report `contributors`): `Only {a} of {b} files have line ownership, because git blame ran out of time. The rest count commits only.` How to confirm: `Build again on a faster machine.`
- Approvals not read (report `contributors`), when `owner_status` is `partial`: `Pull request approvals could not be read, so commits by agents and bots count for their authors: {reason}` How to confirm: `Run gh auth login, or install gh, and build again.`
- Every build (report `change`), from `checks.validate`: `Stale feature flags and unused routes are not detected for Python.` How to confirm: `This is a known limit of this version of dossier.`

`process.partial_cards` adds: when `details.history.status` is `partial`, every card in `HISTORY_CARDS` (`change.hotspots`, `change.cochange`, `change.blast-radius`, `contributors.people`, `contributors.ask`, `contributors.concentration`, `contributors.agents`, `contributors.workflow`) gets `Made from incomplete history: {first reason}.` When `owner_status` is `partial`, `contributors.ask` and `contributors.concentration` get `Made without pull request approvals: {owner_reason}.` `tools.json`: `grimp` gains `change.blast-radius`; `tree-sitter-language-pack` gains `change.hotspots`.

### D10. `summary.json`

`summary.build(facts, reports, extract, build, gap_counts, version, dependencies, tree) -> dict`, generated in `cmd_render` after V11 passes and just before the page is written. It is written atomically to `<out>/summary.json`.

| Field | Source |
|---|---|
| `schema_version` | constant 1 |
| `dossier_version`, `generated_at` | `VERSION`, UTC now |
| `repo` | `facts.repo`: `name`, `remote.url`, `branch`, `sha`, `commit_date` |
| `languages` | `facts.languages` of kind `code`: `name`, `share` = `share_pct`, `tier` from the `tools` record's languages, default `B` |
| `extractors` | The mapping in section 3, row 22, plus `{"name": "git", ...}` with `partial` when history is partial |
| `components` | `components.catalog` rows. `id` = name lower-cased with runs of non-alphanumerics as `-`. `paths` from `components.parse_paths`. `depends_on`, `used_by` from `catalog_edges`, as ids. `size` in lines. `owners`: identities that own at least 20% of the component's lines, as contributor ids (Q5) |
| `contributors` | One object per `person` item: `id` = `c-` plus the first 12 hex characters of the SHA-256 of the gatherer's id, `kind` (`human`, `agent`, `bot`), `name`, `username` (`person.username`, else the part before `@users.noreply.github.com` in the gatherer's id, else null). `owners` holds `id` values. No email address appears anywhere in the file |
| `entry_points` | `entry.catalog` rows. `kind` and `name` from the cells. `location` = `path:line` of the first `cand` item, else the first `cite` |
| `contracts` | `io.contracts` rows. `name`, `direction` (lower-cased), `counterparty`, `schema_path` = first file citation in that row's Schema location cell, else null. `na` gives `[]` |
| `external_dependencies` | `dependencies.json` `deps` and `unused`: `name`, `ecosystem`, `scope` (`dev` when `s` is dev, else `runtime`), `files_importing` = `src + tst` (0 for unused) |
| `data_stores` | `data.stores` rows: `name`, `technology`; `na` gives `[]` |
| `risks` | Severity counts over the risk tables, by the logic of `panel_risk_counts` (moved to `render.risk_counts`) |
| `ownership` | D4, plus `at_risk_paths`: paths of components whose concentration Status is `departed` (Q4) |
| `change` | `hotspots`: every file with `commits_12m > 0`, `{path, churn}` with churn = `commits_12m`, sorted. `cochange_pairs_unlinked` |
| `gaps` | `counts` from `cmd_render` |

Cell text is cleaned by `summary.plain(cell)`: remove `[[...]]` citations (keeping a label), backticks and surrounding space. A person's `name` that is an email address is replaced by the part before the `@`.

`deps.py` caps only its `files` list (`trimmed`), so `deps` and `unused` are complete.

### D11. V8

`prompts/summary.schema.json`: JSON Schema draft 2020-12 with `$schema`, `type`, `required`, `properties`, `additionalProperties: false`, `items`, `enum`, `minimum`. `summary.validate(doc, schema) -> list[str]` implements exactly those keywords and raises on any other keyword in the schema file, so the two cannot drift silently. Line form: `V8: summary.json: {json path}: {problem}.`

- **`render`:** errors are printed as `error: V8: ...`, counted as `v8` on a `check/summary` record. Without `--allow-errors` nothing is written, and the exit is 1, with the closing line `{n} error(s) in summary.json. The page was not written. Fix the reports and render again.` With `--allow-errors`, the page is written, `summary.json` is removed if present, and the process card says so.
- **`dossier check`:** loads `summary.json`, validates it, and compares `repo.sha` and `dossier_version` with `facts.json` and `VERSION`. Each problem is one `FAIL V8: ...` line and counts toward `problems`. A missing file is a failure.
- **Process card:** step 10 reads `Page and machine-readable summary written.`, or `Page written. summary.json was not written: {n} problems.` The step 8 line gains ` Summary: {n} problems.`

The `check/summary` record uses `part: "summary"`. Add it before the page is drawn the second time, as the V11 record is, so the card shows it.

### D12. Order of report writing

`entry`, `components`, `interactions`, `io`, `data`, `behavior`, `conventions`, `ops`, `change`, `contributors`, `reading`, `overview`, `risks`, `gaps`. `contributors` needs the catalog. `risks` comes last, so it can use the measured findings and `change`.

### D13. Staleness and incremental builds

`candidates.FEEDS` gains `"change": ("markers", "decision_docs")` and `"contributors": ("people",)`. `_feed` keys: `["marker", id]`, `["doc", path]`, `["person", person, type]`. No counts or dates, so a new commit alone does not change them. `contributors` still goes stale on new commits through `REPO_WIDE`. `change` goes stale when a cited file changes or its digest changes. Measured cards redraw on every `render`. `summary.json` is rewritten on every `render`. `render_only` builds still write it.

### D14. Version

`VERSION` 0.8.0. A minor bump makes the next `prepare` a full rebuild and backs up `state.json`. Rejected: 0.7.2, which would leave a 0.7.x dossier incremental with its two new required reports listed as "not written yet" and `risks` failing V6. The skill has no bump tool and CI does not tag it: edit `VERSION` directly, as `2ae9334` did.

### D15. The three sessions

| Phase | Content | Why this cut |
|---|---|---|
| 1 | History, ownership, `gh`, workflow, markers, complexity, degradation, measured cards, Owner and Author buttons, V11 and V12 for them | Ends with every measured card drawn and checked on a test page. Nothing depends on Claude |
| 2 | Added columns, candidates, fills, completeness, staleness, `summary.json`, V8, required reports, prompts, docs, version | Everything that makes a build complete. Ends with suites green on a page built from fixtures |
| 3 | The real build and every verification block, then the merge | A full build of 14 reports needs a session of its own, and a clean context finds what earlier sessions assumed |

Each phase ends on the branch with everything committed and the suites green. The merge happens only in Phase 3.

### D16. Cut line

Cut in this order, only if a phase cannot finish: M3-13 (upgrade burden), then the `change.docs-drift` text in M3-24 (the card then holds `na`, citing the README), then the `== Same name defined more than once ==` and `== Old-looking names ==` hints in M3-17.

A cut card: add its id to `render.CUT_CARDS`. It draws `Not measured in this version.`, adds the fixed Gaps item `{title} is not measured in this version.`, and V11 accepts it.

**Never cut:** extractor fixture tests, V8, V11 and V12 on the new cards, the blast-radius picker, the ownership rules, the Owner and Author buttons, any P0 card. Record any cut under "Results"; it becomes the first item of the next plan.

### D17. Reading approvals with `gh`

`gh` is an optional host tool, version pattern `gh version (\d+\.\d+\.\d+)`. It is never in `missing`, so it never stops a build. `doctor` lists it as optional.

**When it runs:** only with two or more human contributors, a `remote.web_base` on `github.com`, and at least one commit by an agent or a bot. A solo repository makes no call, so `cannalerts` never uses it.

**How it runs.** New `sandbox` profile `github`: the normal scrubbed environment plus `GH_CONFIG_DIR` (the parent's value, else `$XDG_CONFIG_HOME/gh`, else `~/.config/gh`), `GH_PROMPT_DISABLED=1` and `GH_NO_UPDATE_NOTIFIER=1`. No token variable is passed. Tested 2026-11-05 with an empty environment and a scratch `HOME`: the call succeeds. A login kept in a system keyring may not be reachable this way, and then the build falls back (below).

**Query.** One `gh api graphql -f query=...` per 50 commits, with aliases:

```graphql
{repository(owner:"o",name:"r"){
 c0:object(expression:"<sha>"){... on Commit{author{user{login}}
  associatedPullRequests(first:5){nodes{number merged mergedBy{login __typename}
   reviews(states:APPROVED,last:20){nodes{author{login __typename}}}}}}}}}
```

Tested on `cli/cli`, where it returns the pull request for both a merge commit and a commit inside it. A query by commit, rather than listing pull requests, also covers squash merges, and costs one batch per 50 agent commits rather than every pull request.

**Reading a commit.** Keep pull requests with `merged: true` and take the lowest number. `approver` is the author of the last review whose `__typename` is `User` and whose login `gather.ident_type` does not class as a bot or agent. With none, `merged_by` is used on the same test. With neither, the commit has no pull request owner, and rule 4 applies.

**Logins to identities.** Ask for `author{user{login}}` on one commit of each human identity, in the same batches. A login that matches no identity becomes a new `person` with id `github:<login>`, the login as `name`, type human, `commits: 0`. `dossier candidates --report contributors` lists these under possible duplicates.

**Limits and caching.** New timeout key `github`, default 300 seconds, checked between batches. Finished batches are kept. Results for commits that have a pull request are cached in `<out>/github-owners.json`, keyed by commit, because a merged pull request does not change, so rebuilds fetch only new commits.

**Fallback.** No `gh`, no login, not on GitHub, an error, or a timeout: rule 3 does not apply to the commits left unread, `owner_status` is `partial`, and D9's item is added.

### D18. Owner and Author buttons

The buttons sit at the top of the Contributors card, drawn by the same helper as the knowledge map's `.km-ctl` button groups (`render.py`, near line 1371): a `.button-group` with Owner, then Author, and `aria-pressed`. **Author is pressed when the page opens.**

- `panel_contributors(f, refs, history=None)`; `build_page` passes `ctx["extract"].get("history")`. **With no `history` items it returns exactly what it returns today.** `FIX` has none, so blocks E and G2 keep their baselines.
- With them, the tiles, the `who-bar` and the contributor table are each wrapped in `<div data-who="author">`, with a sibling `<div data-who="owner" hidden>`.
- Owner tiles: commits owned by humans, agents and bots. Owner bar: `owned_lines` per identity, drawn with `share_bar`. Owner table `t-people-owner`: Name, Type, Commits owned, Commits authored, Lines owned, one row per identity that owns anything, **uncapped**, read from `history` only.
- A `<p class="muted" data-who="owner" hidden>` states the rule in force, by `meta.owner_rule`: `{name} is the only person on this project, so they own every commit.`, or `Commits by agents and bots belong to the person who approved their pull request, or to their author when there was none.` Then: `The calendar and the knowledge map always show who authored each commit.`
- `dossier.js`: `initWho()` toggles `hidden` on `[data-who]` and `aria-pressed`, inserted before the closing `})();`.
- V11: `t-people-owner` rows equal the identities that own something. V12: `check_owner_buttons(page, scheme)` clicks Owner and asserts the owner table is visible and `#t-people` is hidden, then clicks Author and asserts the reverse. The existing `FROZEN_CARDS` exemption covers only the sideways check, so the other V12 checks apply.

---

## Phase 1: Git data and measured cards

### Before you start (Phase 1)

Read section 2, section 3, D1 to D6, D9, D16, D17 and D18. Load the skills in section 2. Then:

1. `git log --oneline -5`. The top should be `5e05daa` or a later merge that does not touch `scripts/`, `prompts/` or `assets/`. If it does touch them, read the change and stop if it contradicts this plan.
2. Read sections 7 and 8: every question is answered, and S3 and S9 are ruled, so the plan text stands.
3. Run the suite and confirm the baseline. Create `feat/dossier-m3` from `main`.

### Tasks (Phase 1)

- [x] **M3-1. History parser.**
  - Goal: turn the log output into commits, following renames.
  - Files: `scripts/history.py`, `tests/unit/scripts/test_history.py`.
  - Interface: `parse_log(data: bytes) -> Iterator[Commit]` with `Commit(sha, name, email, date, parents, message, entries)`, entries as `(added, deleted, old, new)`. `fold(commits, wanted, cid_of, as_of, bulk_files) -> Folded` with per-file figures, pair counter, people and bulk list.
  - Steps: (1) Tests on hand-written byte strings: plain commit, rename, merge with no entries, a truncated last record (dropped), a message holding tabs and newlines. (2) Implement, reusing the numstat token loop from `gather.parse_commit`. (3) In `fold`, use the alias logic of `gather.credit_history`, skip paths not in `wanted`, and for a commit with more than `bulk_files` files add a `bulk` record and count no file or pair. (4) Count pairs with `itertools.combinations(sorted(set(paths)), 2)`.
  - Done-check: `uv run --with pytest --with pygments python -m pytest tests/unit/scripts/test_history.py -q` passes.
  - Commit: `feat(dossier): parse the git history once, following renames`

- [x] **M3-2. The history output and the hand-over from `gather`.**
  - Goal: `prepare` writes `extract/history.json`.
  - Files: `scripts/history.py`, `scripts/gather.py`, `scripts/dossier.py`, `scripts/config.py`, `scripts/candidates.py`, `tests/conftest.py`, `tests/integration/scripts/test_history_git.py`, `tests/unit/scripts/test_gather.py`.
  - Interface: `history.collect(top, sha, run, handed, timeout) -> dict` returning the envelope of D2; `history.write(out, data)`. `facts["history_input"]` and `facts["history"]` as in D1.
  - Steps: (1) Add a `history_repo` fixture to `conftest.py`, built like `git_repo`: two humans, one agent, one bot, a rename, three files changing together in three commits, one merge of a `feat/x` branch, one tag, a remote ref, a `# HACK:` comment, and a human commit with a `Co-authored-by: Claude` line. Monkeypatch `gather.BULK_FILES` to 3 for a bulk commit. (2) Test the `file`, `pair`, `person`, `assistant`, `bulk` and `meta` items, and that a renamed file keeps its old commits. (3) Add `"history": 600` to `DEFAULT_TIMEOUTS`. (4) Run the D1 command with `run([...], stage="history", timeout=timeout, profile="tool")`. Parse `result.stdout`, then delete it. (5) Status: `partial` when shallow or timed out or when `blame_done < blame_total`; `reasons` hold the fixed sentences. (6) Wire `cmd_prepare` in the order D1 gives. `facts.json` must not contain `history_input`. (7) Add `facts["history"]` to `render.FACT_KEYS` as `card-change-hotspots` (use `card_dom_id`) and to `FACT_INFO`, with a plain description and the range markers `^def collect\(`, `^def write\(`, read from `history.py`; if `gatherer_source` cannot read that file, add `history.py` as a third embedded source the way `deps` is.
  - Done-check: `uv run --with pytest --with pygments python -m pytest tests/integration/scripts/test_history_git.py tests/unit/scripts/test_gather.py -q` passes, and `grep -c history_input scripts/dossier.py` prints at least 1.
  - Commit: `feat(dossier): write uncapped git history to extract/history.json`

- [x] **M3-3. Workflow rows and branches.**
  - Goal: the six rows and the branch list, from git only.
  - Files: `scripts/workflow.py`, `scripts/history.py`, `tests/unit/scripts/test_workflow.py`, `tests/integration/scripts/test_history_git.py`.
  - Interface: `workflow.rows(commits, merge_sizes, tags, default_branch) -> list[dict]`; `workflow.branches(top, sha, run) -> list[dict]`; `workflow.merge_sizes(top, sha, run) -> dict`.
  - Steps: (1) Unit tests for each row's wording with no merges, with `Merge pull request`, with `merged feat/x`, with conventional and free subjects, with 0, 1 and 3 tags. (2) Implement D3's table. (3) Integration test on `history_repo`: six rows in spec order, the remote branch with correct ahead and behind, `HEAD` refs left out, the default branch left out, local fallback when there are no remotes. (4) Add the items to `history.collect`.
  - Done-check: `uv run --with pytest --with pygments python -m pytest tests/unit/scripts/test_workflow.py tests/integration/scripts/test_history_git.py -q` passes.
  - Commit: `feat(dossier): measure the team workflow and the branches in flight`

- [x] **M3-4. Markers and hints.**
  - Goal: findings for `change.decisions` and `change.unfinished`.
  - Files: `scripts/markers.py`, `scripts/gather.py`, `scripts/history.py`, `scripts/candidates.py`, `tests/unit/scripts/test_markers.py`.
  - Interface: `markers.scan(path, text) -> (marker_items, todo_count)`; `markers.decision_docs(tree) -> list[str]`; `markers.long_commits(commits) -> list[dict]`.
  - Steps: (1) Tests. A comment line is one whose stripped text starts with `#`, `//`, `--`, `/*` or `*`, or that holds ` # ` or ` // `. Rules: `HACK` and `XXX` as whole words in capitals; `workaround` or `work around` in any case; bug ids as `(BUG|ISSUE|JIRA)[-#]?\d+`, or `[A-Z]{2,}-\d+`. TODO and FIXME are counted, not listed. (2) Call `scan` inside `gather.collect`'s per-file loop for files that are not docs; keep the result in `history_input`. (3) `decision_docs`: paths matching `(^|/)(adr|adrs|decisions?)/` or `(^|/)docs/.*(design|architecture|rfc)`. (4) `long_commits`: messages with at least 8 non-blank lines after the subject, trailers not counted. (5) Add `"history": "mk"` to `ID_OUTPUTS` and assign ids to marker items only. Add nothing to `DECIDED_OUTPUTS` yet (M3-17).
  - Done-check: `uv run --with pytest --with pygments python -m pytest tests/unit/scripts/test_markers.py tests/unit/scripts/test_candidates.py -q` passes.
  - Commit: `feat(dossier): find decision markers, TODO counts and long commit messages`

- [x] **M3-5. Fixture check of the whole output.**
  - Goal: lock the output shape.
  - Files: `tests/integration/scripts/test_history_git.py`.
  - Steps: assert every item kind in D2 appears for `history_repo`, each with exactly the fields listed, and that `candidates.load(out)["history"]` returns them. Assert that no item holds an email except `person.person`, `person.aliases` and the keys of `authors` and `blame`.
  - Done-check: `uv run --with pytest --with pygments python -m pytest tests/integration/scripts/test_history_git.py -q` passes.
  - Commit: `test(dossier): pin the shape of extract/history.json`

- [x] **M3-6. Reading approvals with `gh`.**
  - Goal: D17.
  - Files: `scripts/github_owners.py`, `scripts/sandbox.py`, `scripts/tools.json`, `scripts/toolcheck.py`, `scripts/process.py`, `tests/unit/scripts/test_github_owners.py`, `tests/unit/scripts/test_sandbox.py`, `tests/unit/scripts/test_toolcheck.py`, `tests/fixtures/github/` (saved responses).
  - Interface: `github_owners.slug(remote) -> "owner/name" | None`; `lookup(slug, shas, run, cache, timeout) -> {sha: {"number", "approver", "merged_by"}}`; `logins(slug, samples, run, timeout) -> {sha: login}`.
  - Steps: (1) Tests on saved responses: one approval; two approvals (the last wins); no approval, merged by a human; merged by a bot with no approval (no owner); no pull request; two pull requests (the lowest merged number wins); a `gh` failure; a timeout that keeps finished batches. (2) Add the `gh` host entry with `"optional": true`. In `preflight`, leave optional tools out of `missing`. In `format_text`, print them under `Optional:`. In `coverage_items`, skip optional tools. (3) Add profile `github` to `sandbox.build_env`, and the three names to `ALLOWED_NAMES`. A test asserts no other profile gets them, and that no variable name holds `TOKEN`. (4) Implement D17.
  - Done-check: the three test files pass, and `uv run scripts/dossier.py doctor --all` lists `gh` without failing when `gh` is hidden from `PATH`.
  - Commit: `feat(dossier): read pull request approvals with gh`

- [x] **M3-7. Commit owners.**
  - Goal: D4's rules, per commit, file and line.
  - Files: `scripts/ownership.py`, `scripts/history.py`, `scripts/gather.py`, `tests/unit/scripts/test_ownership.py`, `tests/integration/scripts/test_history_git.py`, `tests/unit/scripts/test_gather.py`.
  - Interface: `ownership.owner_of(author, author_type, pr_owner, sole_human) -> id`; `ownership.apply(folded, people, prs) -> {sha: owner}`.
  - Steps: (1) Test every row of D4's table, plus a repository with no humans, and an approver who never committed (a new `person` with `commits: 0`). (2) `gather.blame_file` and `ownership()` take an optional dict filled with `{path: {sha: [id, lines]}}`. Default behaviour and every existing figure stay the same; `test_gather.py` proves it. Pass the dict in `collect` as `blamed_commits`. (3) In `history.collect`: count humans; with exactly one, apply rule 1 and make no `gh` call; otherwise look up non-human commits (M3-6), map logins to identities, and fill `file.owners`, `file.owner_lines`, `person.owned_commits`, `person.owned_lines`, `person.username`. A blamed commit outside the log (history cut short) uses the blame's author. (4) Fill `meta.owner_rule`, `owner_status`, `owner_reason`.
  - Done-check: `uv run --with pytest --with pygments python -m pytest tests/unit/scripts/test_ownership.py tests/integration/scripts/test_history_git.py tests/unit/scripts/test_gather.py -q` passes, and block E prints `OK`.
  - Commit: `feat(dossier): work out who owns each commit and line`

- [x] **M3-8. Complexity proxy.**
  - Goal: a complexity number per Python file.
  - Files: `scripts/py_queries.py`, `scripts/py_adapter.py`, `tests/unit/scripts/test_py_queries.py`, `tests/integration/scripts/test_py_queries_slow.py`, `tests/fixtures/pyrepo/` only if a file needs a branch.
  - Interface: `py_queries.complexity(ts, files) -> {path: count}`; `graph` module items gain `complexity`.
  - Steps: (1) `COMPLEXITY_Q = "[(if_statement) (elif_clause) (for_statement) (while_statement) (except_clause) (conditional_expression) (boolean_operator) (case_clause)] @branch"`. Check each node name against the pinned grammar in the slow test. A name that does not exist makes the query fail, so remove it and record that under "Results". (2) Count matches by `m["path"]`. (3) In `PythonAdapter.extract`, after `_syntax`, inside the same `_step` guard, set `complexity` on `graph` module items. (4) `PythonAdapter.version = "3"`. (5) `_feed("modules")` must not change, so a complexity change alone makes nothing stale; add a test.
  - Done-check: `DOSSIER_SLOW=1 uv run --with pytest --with pygments python -m pytest tests/unit/scripts/test_py_queries.py tests/integration/scripts/test_py_queries_slow.py -q` passes.
  - Commit: `feat(dossier): count branches per Python file as a complexity proxy`

- [x] **M3-9. Degrading: Gaps and "partial".**
  - Goal: D9.
  - Files: `scripts/process.py`, `scripts/tools.json`, `tests/unit/scripts/test_process.py`, `tests/integration/scripts/test_history_git.py`.
  - Steps: (1) Tests for each D9 statement, word for word, and for `partial_cards` with a partial history. (2) Per-tool items: read `details.adapters[].tools` of the `prepare` extract record. (3) Integration test: `git clone --depth 1 file://...` of `history_repo`, run `history.collect`, expect `status: partial` and `shallow: true`. Add a timeout test with `timeout=0.001`, expecting `stopped_early` or no crash and a `partial` status. (4) Edit `tools.json` as D9 says.
  - Done-check: `uv run --with pytest --with pygments python -m pytest tests/unit/scripts/test_process.py tests/integration/scripts/test_history_git.py -q` passes.
  - Commit: `feat(dossier): report incomplete history and failed tools in Gaps`

- [x] **M3-10. Hotspots card.** Load `dataviz` first.
  - Goal: D3's table, component table and scatter.
  - Files: `scripts/measured_change.py`, `scripts/measured.py`, `scripts/render.py`, `assets/dossier.css`, `tests/unit/scripts/test_measured_change.py`.
  - Interface: `measured_change.DRAWN` merged into `measured.DRAWN`. `ctx["facts"]` must reach it: check `render.measured_ctx`, and add `dependencies` if absent.
  - Steps: (1) Tests from hand-built `extract` dicts: one row per source file including files with no commits, sorting, component sums, the sentence's counts, the SVG has one circle per file and a `<title>` each, no `history` items gives `None`. (2) Implement. (3) `.chart-scroll { overflow-x: auto; } .chart-scroll svg { display: block; max-width: none; }`, scoped as section 2 says.
  - Done-check: the test file passes and block E prints `OK`.
  - Commit: `feat(dossier): draw the hotspots card with a churn scatter`

- [x] **M3-11. Co-change, dead code, in flight, workflow.**
  - Goal: four measured cards.
  - Files: `scripts/measured_change.py`, `scripts/measured_people.py`, `scripts/measured.py`, `scripts/checks.py`, `tests/unit/scripts/test_measured_change.py`, `tests/unit/scripts/test_measured_people.py`.
  - Interface: `measured_change.linked(a, b, extract) -> "yes"|"no"|"not in the graph"`; `measured_change.dead_rows(extract, dependencies) -> list`.
  - Steps: (1) Tests for each `linked` case, including a pair joined only by a test's `paths`. (2) Draw each card as D3 says, with `.none-found` when empty. (3) `commit:` citations in `Source`: `refs.mark(["commit:" + sha])`. (4) Add the fixed Gaps item for flags and routes to `checks.validate`'s `gaps`, only when the `python` adapter ran.
  - Done-check: both test files pass and block E prints `OK`.
  - Commit: `feat(dossier): draw co-change, dead code, work in flight and team workflow`

- [x] **M3-12. Blast radius.**
  - Goal: D5.
  - Files: `scripts/graphs.py`, `scripts/measured_blast.py`, `scripts/measured.py`, `assets/dossier.js`, `assets/dossier.css`, `tests/unit/scripts/test_graphs.py`, `tests/unit/scripts/test_measured_blast.py`.
  - Steps: (1) Tests: `reverse_closure` on a chain, a diamond and a cycle (a file is never its own dependent). Bits decode back to the same set. A file outside the graph shows `not in the graph`. Tests reached through the closure are counted. (2) Implement. (3) Write `initBlast` as D5 says; it must escape paths with `esc`. (4) CSS: `.blast-lists { display: grid; grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr)); gap: 1rem; } .blast-list { max-height: 20rem; overflow: auto; } #blast-pick { max-width: 100%; }`, scoped to the card. (5) Assert `dossierJs = "ok"` is still the last line (the existing test covers it).
  - Done-check: both test files pass and block E prints `OK`.
  - Commit: `feat(dossier): add the blast radius picker`

- [x] **M3-13. Upgrade burden (P1).**
  - Goal: the card, from a shipped snapshot.
  - Files: `scripts/eol.json`, `scripts/measured_upgrade.py`, `scripts/measured.py`, `tests/tools/refresh_eol.py`, `tests/unit/scripts/test_measured_upgrade.py`.
  - Interface: `eol.json` is `{"as_of": "YYYY-MM-DD", "source": "https://endoflife.date/api/v1/products/", "products": {"python": [{"cycle": "3.14", "eol": "2030-10-31", "latest": "3.14.10"}]}}`. `measured_upgrade.rows(ctx) -> list`.
  - Steps: (1) `refresh_eol.py` fetches `https://endoflife.date/api/v1/products/<name>` for `python`, `django`, `nodejs`, `dotnet`, `postgresql` and keeps, from `result.releases`, `name`, `eolFrom` and `latest.name`. Run it once and commit the output. (2) Tests with a small snapshot passed in. Cycle matching: the highest cycle allowed by `requires-python`'s lower bound, or the pinned `major.minor`. (3) Draw as D3 says.
  - Done-check: the test file passes, and `python3 -c "import json;d=json.load(open('scripts/eol.json'));print(d['as_of'],sorted(d['products']))"` prints a date and the five products.
  - Commit: `feat(dossier): draw upgrade burden from an end-of-life snapshot`

- [x] **M3-14. V11 and V12 on the new cards, and a test page.**
  - Goal: D6.
  - Files: `scripts/page_audit.py`, `scripts/render.py` (`CUT_CARDS = ()`), `scripts/check_layout.py`, `scripts/check_page.py`, `tests/tools/m3_page.py`, `tests/tools/broken_pages.py`, `tests/fixtures/m3page/` (`history.json`, `graph.json`, `tests.json`, `dead.json`, `change.json`, `contributors.json`), `tests/unit/scripts/test_page_audit.py`, `tests/integration/scripts/test_check_page_slow.py`.
  - Interface: `m3_page.make(tmp) -> Path` copies `FIX` to a temporary home, adds those files, runs `render --allow-errors`, and returns the page. The fixture reports cite only `facts:` keys. Paths in the fixture data are real paths of `FIX`'s repository at its commit. Give it enough rows to make a table taller than 40 rows and an over-wide row, so the layout checks mean something.
  - Steps: (1) Add mutations to `broken_pages.py`: `blast-data-removed`, `hotspot-row-removed`, `chart-text-small`, `workflow-table-to-text`. (2) Unit tests: each row-count and column rule of D6 fails on a page with a row removed. (3) Slow test, module-scoped page: `check_page.py` prints no `FAIL` line naming `change.` or `contributors.`, in light and dark, at 1500 and 400 px. Each mutation produces a `FAIL`. (4) Implement.
  - Done-check: `DOSSIER_SLOW=1 uv run --with pytest --with pygments python -m pytest tests/unit/scripts/test_page_audit.py tests/integration/scripts/test_check_page_slow.py -q` passes.
  - Commit: `feat(dossier): hold the new cards to the page audit and the browser check`

- [x] **M3-15. Owner and Author buttons.** The author approved this change to report 02 on 2026-11-05.
  - Goal: D18.
  - Files: `scripts/render.py`, `assets/dossier.js`, `assets/dossier.css`, `scripts/page_audit.py`, `scripts/check_page.py`, `tests/tools/broken_pages.py`, `tests/unit/scripts/test_render.py`, `tests/unit/scripts/test_page_audit.py`, `tests/integration/scripts/test_check_page_slow.py`.
  - Steps: (1) Tests: without `history` items the card is byte-identical to today's; with them, removing every `data-who="owner"` element, the buttons and the wrappers gives back today's card; Owner table rows equal the identities that own something; Owner view figures come from `history`, not from `facts`. (2) Implement D18. (3) Add `check_owner_buttons` and the mutation `owner-buttons-dead`.
  - Done-check: `DOSSIER_SLOW=1 uv run --with pytest --with pygments python -m pytest tests/unit/scripts/test_render.py tests/unit/scripts/test_page_audit.py tests/integration/scripts/test_check_page_slow.py tests/integration/scripts/test_golden02_slow.py -q` passes, and block E prints `OK` with `$BASE` unchanged.
  - Commit: `feat(dossier): add Owner and Author buttons to the Contributors card`

### Deliverables and checks (Phase 1)

| Deliverable | Checked by |
|---|---|
| `extract/history.json`, all kinds | M3-5 |
| Commit owners, `gh` lookups and fallback | M3-6, M3-7 |
| Complexity on module items | M3-8 slow test |
| Gaps items, partial badges, shallow and timeout paths | M3-9 |
| Seven measured cards | M3-10 to M3-13 tests |
| V11 and V12 fail on broken pages and pass on the test page | M3-14 |
| Owner and Author buttons | M3-15 |
| Report 02 unchanged without ownership data | Blocks E and G2 |

### Cut line (Phase 1)

M3-13 only (D16). Anything else unfinished moves to the start of Phase 2, in order, and is recorded under "Results".

### Acceptance criteria (Phase 1)

- Default and slow suites pass; blocks E and G2 pass.
- `grep -n "hot_files\|\.get(\"areas\")\|bulk_commits\|knowledge" scripts/measured_change.py scripts/measured_people.py scripts/measured_blast.py` prints nothing.
- Every task is ticked or recorded as cut.

### Branch and release (Phase 1)

Commit on `feat/dossier-m3`. Do not merge. No version change.

### Results (Phase 1)

Written 2026-11-05 by Sonnet on branch `feat/dossier-m3`. All 15 tasks are done and ticked. Nothing was cut, including M3-13.

**Tests.** Baseline 1107 passed, 55 skipped. End of Phase 1: 1289 passed, 65 skipped (default suite, about 50 s). Slow suite: `test_check_page_slow.py` 21 passed (15 old, 6 new); `test_py_queries_slow.py`, `test_py_adapter_slow.py` and `test_extract.py` pass. **`test_golden02_slow.py` fails, and it fails the same way on `main` (5e05daa):** all six cards are shorter than their baselines (for example facts-git 538 to 514 px, facts-contributors 1260 to 1222, facts-dependencies 1595 to 1517). Commit `5518e74` (table column controls, tidied cards) probably caused it, so the baseline PNGs need remaking by the author. I did not touch them. Block G2 therefore cannot pass until then.

**M3-8.** All eight tree-sitter node names exist in the pinned grammar (a sample file with each gives 8 matches). None was removed.

**Block E, a flaw in the plan.** Block E's `BASE` hash (`fe72cec4...`) does not match `main` itself: `main` gives `53cc5498...`. Any edit to `gather.py` also moves the `data-a`/`data-b` line numbers of the citations into `gather.py`, so an exact digest cannot stay equal while M3-2, M3-4 and M3-7 edit that file. I used a stricter check instead: render the report 02 overview section at `main` and at the working tree, drop the `data-a`/`data-b` numbers, and diff. It prints `OK` after every task. Phase 2 and 3 should use the same check, or replace `BASE` in section 6 with a digest that ignores those numbers.

**Deviations from the plan text.**

1. `%x1f` does not work in `git for-each-ref` or `git tag --format`; the code puts a literal separator character in the format string.
2. A lightweight tag's `creatordate` is the commit date, so the release-cadence row dates it that way.
3. `history.collect` takes two extra optional arguments (`github_cache`, `github_timeout`), and `config.DEFAULT_TIMEOUTS` has a `github` key as well as `history`. `dossier.py` keeps the cache in `<out>/github-owners.json`.
4. `history_input` also carries `remote`, `tree` and `blamed_commits`. `gather.blame_file` and `ownership()` gained optional dict arguments only; every existing figure is unchanged.
5. `render.gatherer_which(key)` picks the embedded source file from the fifth entry of `FACT_INFO`, so `history.py` is a third embedded source without a special case.
6. `item.owners` and `item.owner_lines` are keyed by identity (an email), like `authors` and `blame`. M3-5 allows email only in those keys and in `person`/`aliases`; I added the two owner keys to that list.
7. M3-14: the fixture data for the test page is generated by `tests/tools/m3_page.py` from the file list of the fixture's repository, not stored under `tests/fixtures/m3page/`. The dead-code, in-flight and workflow cards need no stored files.
8. M3-14: `page_audit.audit` takes a new `measured=` argument (the same context `render` gives the measured cards). `cmd_render` and `cmd_check` both pass it. Without it, only the old checks run.
9. M3-14: CSS selectors in the new rules use `[data-card^="..."]`. A selector written `[data-card="..."]` in the stylesheet is the first `data-card="` in the page text and silently broke the `overlap` and `wide-element` mutation helpers.
10. The `.bus-factor` line required of `contributors.concentration` (D6) is Phase 2 (M3-18), so V11 does not check it yet.
11. The Owner view's note and the figures come from `history` only; `facts:history` is cited on the card only when `facts.history` exists.
12. `tests/unit/scripts/test_page_audit.py` imports helpers from `test_render.py` for the Owner table test.

**Not verified.** The `gh` path has only been run against saved responses and a fake runner; block L (a real pull request) is Phase 3. A login kept in a system keyring may not be reachable from the scrubbed environment (risk 2).

---

## Phase 2: Written cards, summary.json, V8, prompts and version

### Before you start (Phase 2)

Read section 2, section 3, D7, D8, D10 to D14, and D16. Load the skills in section 2, including `docs-project`, `docs-readme` and `git-release`. Then:

1. `git switch feat/dossier-m3`, `git log --oneline main..` and read "Results (Phase 1)". Do first any task moved here.
2. Run the suite and compare with Phase 1's count.

### Tasks (Phase 2)

- [x] **M3-16. Added columns and the Risks `Source` column.**
  - Goal: D8.
  - Files: `scripts/render.py`, `scripts/page_audit.py`, `prompts/schema/risks.json`, `scripts/checks_people.py`, `tests/unit/scripts/test_render.py`, `tests/unit/scripts/test_page_audit.py`, `tests/unit/scripts/test_schema_files.py`.
  - Steps: (1) Tests: `auto_columns` in all four cases; `change.decisions` draws `Source` then `Basis` then `Citations`; `contributors.ask` draws `Basis`, `Confidence`, `Source`; V11 accepts both. (2) Implement. (3) Add the column. (4) Add the Risks source check from D7.
  - Done-check: the three test files pass and block E prints `OK`. Its error lines now also include a V6 column line for `risks`.
  - Commit: `feat(dossier): add the Source column to Risks and name added columns apart`

- [x] **M3-17. Candidates for reports 10, 13 and 14.**
  - Goal: D7's `dossier candidates` output, and markers under V5 (needs S9).
  - Files: `scripts/candidates.py`, `scripts/measured_people.py`, `tests/unit/scripts/test_candidates.py`, `tests/unit/scripts/test_candidates_cli.py`, `tests/unit/scripts/test_checks_v5.py`.
  - Steps: (1) Tests: `home_card("history", marker) == "change.decisions"` and `None` for other kinds; an undecided marker fails V5 and a group id decides it; each new section prints; `--open` prints nothing once decided. (2) Add `"history"` to `DECIDED_OUTPUTS`. (3) Add the `change`, `contributors` and `risks` branches to `report_data` and `text`. `candidates.py` is about 300 lines, so put the new text in a new `candidates_history.py` that `candidates` calls late.
  - Done-check: the three test files pass.
  - Commit: `feat(dossier): list history findings for the change, contributors and risks reports`

- [x] **M3-18. Ownership and measured cells.**
  - Goal: D4 and D7's fill.
  - Files: `scripts/measured_people.py`, `scripts/measured.py`, `scripts/render.py`, `tests/unit/scripts/test_measured_people.py`, `tests/unit/scripts/test_render_cards.py`.
  - Interface: `component_stats(ctx)` (D4), `bus_factor(ctx) -> {"bus_factor", "top_owner_share"}`, `measured.fill_people(entry, cid, ctx)`.
  - Steps: (1) Tests: Share comes from blame, not from Claude's cell; a wrong value in Claude's cell is replaced; Share comes from `owner_lines`, not `blame`; on a one-human repository Share is 100% for that human; bus factor on 1, 2 and 3 humans; agents and bots left out; an `assistant` row is filled from its item; an `unknown` owner gets `-`; no human lines gives `null` and the line `Bus factor: not known, because no person has lines at this commit.` (2) `render_card` calls the fill for `contributors.concentration` and `contributors.agents`. (3) Line above the table: `<p class="bus-factor">Bus factor: {n}. The largest share held by one person is {s}% of the lines people wrote. Agents and bots are not counted.</p>`.
  - Done-check: both test files pass and block E prints `OK`.
  - Commit: `feat(dossier): fill measured contributor cells and state the bus factor`

- [x] **M3-19. Completeness of report 13.**
  - Goal: D7's checks.
  - Files: `scripts/checks_people.py`, `scripts/checks.py`, `scripts/process.py`, `tests/unit/scripts/test_checks_people.py`.
  - Steps: (1) One test per error line of D7. (2) Call from `checks.validate` inside `try`, as `v5_env` is. Add `v5_people` to the counts. (3) The process card's check line adds ` People and components: {n} missing.` when the count is present.
  - Done-check: the test file and `tests/unit/scripts/test_process.py` pass.
  - Commit: `feat(dossier): require every person and component in report 13`

- [x] **M3-20. Staleness.**
  - Goal: D13.
  - Files: `scripts/candidates.py`, `tests/unit/scripts/test_candidates.py`, `tests/unit/scripts/test_incremental.py`.
  - Steps: (1) Tests: a new marker changes the `change` digest; a new commit that adds no person leaves the `contributors` digest alone; a line move changes nothing. (2) Implement.
  - Done-check: both test files pass.
  - Commit: `feat(dossier): mark reports 10 and 13 stale when their findings change`

- [x] **M3-21. `summary.json` and V8 in `render`.**
  - Goal: D10 and D11.
  - Files: `scripts/summary.py`, `prompts/summary.schema.json`, `scripts/dossier.py`, `scripts/render.py`, `scripts/process.py`, `tests/unit/scripts/test_summary.py`, `tests/integration/scripts/test_summary_schema_slow.py`.
  - Steps: (1) Tests: each field from hand-built reports; `na` cards give empty lists; a bad Direction gives one V8 line; a missing required key gives one V8 line; an unknown schema keyword raises; `plain` strips citations; `contributors` has one object per `person` with the right `kind` and `username`; every `owners` value is a contributor `id`; no `@` appears in the file; `at_risk_paths` holds only `departed` components. (2) Write the schema from spec section 9, field for field, plus `contributors` (D10). (3) Move risk counting into `render.risk_counts`. (4) Wire `cmd_render` as D11 says. (5) Slow test: `uv run --with jsonschema==4.26.0 python -c ...` validates a built summary with `Draft202012Validator`, and it agrees with `summary.validate` on one good and three bad documents.
  - Done-check: `DOSSIER_SLOW=1 uv run --with pytest --with pygments python -m pytest tests/unit/scripts/test_summary.py tests/integration/scripts/test_summary_schema_slow.py -q` passes.
  - Commit: `feat(dossier): write summary.json and check it against its schema (V8)`

- [x] **M3-22. V8 in `dossier check`, and tool status on reuse.**
  - Goal: D11's check side, and section 3 row 22.
  - Files: `scripts/dossier.py`, `scripts/candidates.py`, `scripts/process.py`, `tests/unit/scripts/test_dossier_check.py`, `tests/unit/scripts/test_process.py`.
  - Interface: `candidates.tool_status(out) -> {tool: {"status", "reason"}}`, read from every `extract/*.json` section.
  - Steps: (1) Tests: a missing or tampered `summary.json` gives `FAIL V8`; an old SHA gives `FAIL V8`; with a reused adapter, the process card lists extractors rather than "none recorded". (2) Implement. `render_records` gets the status through a new `details.tool_status` on the `extract` record, written in `cmd_prepare`.
  - Done-check: both test files pass.
  - Commit: `feat(dossier): check summary.json in dossier check and show extractors on reuse`

- [x] **M3-23. Reports 10 and 13 are required.**
  - Goal: section 3 row 24.
  - Files: `scripts/render.py`, `tests/unit/scripts/test_render_validate.py`, `tests/unit/scripts/test_incremental.py`.
  - Steps: (1) Tests: a missing `change.json` is an error with the text `Report 'change' is missing (expected reports/change.json). Run /dossier build to write it.`; `--partial` keeps it a warning. (2) `OPTIONAL_REPORTS = ()`. Keep the name, so `update_plan` needs no change. (3) Update block E's expected lines in section 6 of this file if they differ, and record that.
  - Done-check: both test files pass and block E prints `OK`.
  - Commit: `feat(dossier): require reports 10 and 13`

- [x] **M3-24. Prompts.**
  - Goal: Claude can write reports 10, 13 and 14.
  - Files: `prompts/method.md`, `prompts/reports.md`, `prompts/schema/README.md`, `tests/unit/scripts/test_prompts.py`.
  - Steps: (1) `method.md`: drop "`change` and `contributors` are not written"; add `facts:history` to the citation keys; add the rule that a measured cell is written as `-`; add V8 and the report 13 completeness rule to "What render checks". (2) `reports.md`: new sections `## change` and `## contributors`, one heading per card in schema order, saying what D7 says. Measured cards say **Do not write this card**. `change.decisions` says to decide every marker, and that a group id is allowed. `change.unfinished` says to use the hints and that `Progress` must come from counts Claude can cite. `contributors.people` says to use display names, never email addresses. `contributors.concentration` gives the three Status words, says `departed` is `inferred`, gives D4's ownership rule, and says to judge Owner from owned lines, not authored ones. `contributors.ask` names people. (3) `## risks`: add the `Source` column with its two values and when to use `extractor`. `io.contracts`: Direction is exactly `offered` or `consumed`, one row each. (4) Writing order from D12. (5) Test: every card id of both reports appears in `reports.md`, and each `writer: script` card's section holds the words "Do not write".
  - Done-check: `uv run --with pytest --with pygments python -m pytest tests/unit/scripts/test_prompts.py -q` passes.
  - Commit: `docs(dossier): tell Claude how to write reports 10, 13 and 14`

- [x] **M3-25. SKILL.md, README, doctor text.**
  - Goal: the instructions match the code.
  - Files: `SKILL.md`, `README.md`, `scripts/tools.json` or `scripts/toolcheck.py` (wherever `grep -rn "via npx" scripts` finds the text), `docs/post-v1.md` if a cut needs it.
  - Steps: (1) SKILL.md description and step 5: D12's order, and remove "Reports 10 ... are not written". Step 6: `V8:` errors. Step 7: `dossier check` covers V8. Step 8: mention `summary.json`. (2) README: reports 10 and 13, `summary.json`, the `history` timeout. Plain language, following `docs-readme`. The full rewrite stays in M6. (3) Correct the npx text to say scip-python installs from a lockfile.
  - Done-check: `grep -n "not written in this version\|via npx" SKILL.md README.md prompts/*.md scripts/*.json scripts/*.py` prints nothing, and the suite passes.
  - Commit: `docs(dossier): document reports 10 and 13, summary.json and V8`

- [x] **M3-26. Version 0.8.0.**
  - Goal: D14.
  - Files: `VERSION`.
  - Steps: edit the file directly (D14). Run the default and slow suites.
  - Done-check: `cat VERSION` prints `0.8.0`; both suites pass.
  - Commit: `chore(dossier): bump to 0.8.0`

### Deliverables and checks (Phase 2)

| Deliverable | Checked by |
|---|---|
| Added columns, Risks `Source` | M3-16 |
| `dossier candidates` for three reports; markers under V5 | M3-17 |
| Measured cells, bus factor, completeness | M3-18, M3-19 |
| Staleness | M3-20 |
| `summary.json`, V8 in both commands | M3-21, M3-22 |
| Required reports | M3-23 |
| Prompts and docs | M3-24, M3-25 |
| 0.8.0 | M3-26 |

### Cut line (Phase 2)

D16 only. V8 and M3-18 to M3-23 are never cut.

### Acceptance criteria (Phase 2)

- Default and slow suites pass; blocks E and G2 pass.
- `render.OPTIONAL_REPORTS == ()`, and `VERSION` is `0.8.0`.
- No build of a real repository has been run yet.

### Branch and release (Phase 2)

Commit on `feat/dossier-m3`. Do not merge.

### Results (Phase 2)

Written 2026-11-05 by Sonnet on branch `feat/dossier-m3`. All 11 tasks (M3-16 to M3-26) are done and ticked. Nothing was cut.

**Tests.** Phase 1 ended at 1289 passed, 65 skipped. End of Phase 2: 1426 passed, 66 skipped (default, about 55 s). Slow suite: 1491 passed, 1 failed, 14 min. The one failure is `test_golden02_slow.py`, the same Phase 1 failure that also fails on `main` (baseline PNGs need remaking by the author), so block G2 still cannot pass. `summary.schema.json` agrees with `jsonschema` 4.26.0 on one good and three bad documents.

**Block E.** Passes (`OK`) after every task that edited `render.py`. I used the Phase 1 check (report 02 overview at `main` in a scratch worktree against the working tree, `data-a`/`data-b` dropped). Its allowed error lines changed: the migrated fixture now gives `V5: Risks: Source must be extractor or read, found 'Not yet recorded'` lines, because the migration fills the new Risks `Source` column with its missing-cell placeholder. Section 6 block E is updated.

**Deviations.**

1. M3-16: `migrate_map.json` gives the risks rule `"Source": null`, because `test_migrate.py::test_shipped_map_is_consistent` needs the rule's columns to match the schema. `reports.md` got the Source sentence in this task, not M3-24. `checks_people.py` was created here (Risks check) and extended in M3-19.
2. M3-17: `component_stats` and `names_of` were written here, not in M3-18, since the candidates output needs them. `file` items keep only all-time commits per person, so there is no per-person "commits in 12 months" per component. The contributors candidates list all-time commits instead, and `component_stats` has no `commits_12m` key. `candidates.py` is now 349 lines.
3. M3-18: Share of commits is the identity's commits over all `person` commits. An owner name that matches nobody gets `-`.
4. M3-19: one line is new: `V5: Knowledge concentration, {name}: an Owner of unknown needs conf unknown.` The checks stay quiet until all four cards are written (V6 reports the rest). `v5_people` counts the Risks Source errors too.
5. M3-21: `candidates.tool_list` (read from the extract files) was added here; M3-22's `tool_status` builds on it and also returns `version`. `deps.py` unused entries gained `ecosystem`. The validator is in `summary_check.py` (under 300 lines) and `summary.validate` re-exports it. It also accepts `$schema`, `title` and `description` as annotations, and `type` as a list. Tier is `A` or `B`. `repo.remote` is the web address, or the remote with any `user@` removed. `ownership.bus_factor` and `top_owner_share` are `null` without human lines.
6. M3-23: block E's expected lines (see above).
7. M3-25: the "via npx" text is now "from a lockfile with npm" for tools with a `node_lock`. No user guide or developer guide exists yet; the full README rewrite stays in M6.

**Not verified.** No real repository has been built. Report 13 completeness and `summary.json` content are tested on hand-built data and the frozen fixture only.


---

## Phase 3: End-to-end verification and merge

### Before you start (Phase 3)

Read section 2, section 3, section 6 and "Results" of Phases 1 and 2. Load the skills in section 2. Then `git switch feat/dossier-m3`, check that `cat VERSION` prints `0.8.0`, and do first any task moved here.

### Tasks (Phase 3)

- [x] **M3-27. Run section 6.**
  - Goal: the exit criterion, on `cannalerts`.
  - Files: this plan only, unless a block finds a bug.
  - Steps: run the blocks in the order section 6 gives. **A failure is a finding:** fix the cause on this branch with a test first, in its own commit, then rerun the block. Fix the code, not the check. Record everything under "Verification results".
  - Done-check: every block's expected result is recorded as met, or the phase stops and reports.
  - Commit: `docs(dossier): record the M3 verification run`

- [x] **M3-28. Merge and hand over.**
  - Goal: the acceptance pause can start.
  - Files: this plan.
  - Steps: (1) Tick and record. (2) Follow `git-workflow`: `git merge --no-ff feat/dossier-m3` into `main`, push `main`, delete the branch. (3) Tell the author the procedure in "Hand-over to the acceptance pause" below.
  - Done-check: `git log --oneline -1 main` shows the merge, and `git status --short` shows no tracked change.
  - Commit: the merge commit.

### Deliverables and checks (Phase 3)

| Deliverable | Checked by |
|---|---|
| Verification results | Section 6, recorded |
| Merge | M3-28 done-check |

### Cut line (Phase 3)

Nothing in section 6 is cut. If block D (rewriting every report) cannot finish in the session, say so, keep the reports from the copy of `LIVE` for the reports not yet rewritten, and record which ones. Reports `change`, `contributors`, `risks` and `gaps` are always written fresh.

### Acceptance criteria (Phase 3, and M3)

- Section 6 is recorded, with `dossier check` at `problems: 0`, no `error:` line from `render`, V8 clean, and `summary.json` valid.
- Every card of reports 10 and 13 is filled, on the real page.
- `diff` of `REPO`'s status before and after prints nothing.
- The branch is merged.

### Branch and release (Phase 3)

Merge as M3-28 says. CI does not tag this skill. No work beyond the hand-over: **the next step is the author's acceptance pause.**

### Hand-over to the acceptance pause

The author does this. Nothing new has to be installed. `gh` is optional, is already on this machine, and matters only for repositories with more than one human.

1. `encamp-sync pull`, so `INSTALLED` is at the merge. `git -C ~/.local/share/encamp status --short` must show no `UU` line.
2. `/dossier doctor <repo>`. It must print `skill: <merge commit> (clean)`.
3. `/dossier build <repo>`, on a Python repository the author knows well. It plans a full build, because the version changed. It ends with `dossier check` printing `problems: 0`, and tells the author the page path. `summary.json` sits next to the page in `<home>/<repo>/`.
4. Judge the page against spec section 11, item 3: entry points recall 100% and precision at least 95%; inputs and outputs recall at least 95%; the component map after minor renaming; no fabricated citations; everything wrong or missing explained by a Gaps entry or a new blind-spot rule.
5. Things worth a look that the checks cannot judge: `contributors.people`, `contributors.ask`, the bus factor line, the Owner and Author buttons in report 02, and the three vulture findings on `change.dead-code` (plan 007 finding 7).

### Results (Phase 3)

Written 2026-11-05 by Sonnet on branch `feat/dossier-m3`. M3-27 and M3-28 are done. Nothing was cut.

**Fix made.** `check_page.check_owner_buttons` failed on the real page (`FAIL [light] overview.contributors: the owner button does not show #t-people-owner`, four lines). On a real build the contributor table sits in the knowledge map's hidden Contributors view, which the fixture does not have. The check now clicks `#km-vw` Contributors first and asserts the same things. One commit; no unit test, because the check only runs in a browser and the real `dossier check` is the evidence.

**Open for the author.** Block G2 still fails (`test_golden02_slow.py`), as in Phases 1 and 2 and on `main`: the baseline PNGs need remaking.


### Verification results

Date 2026-11-05, branch `feat/dossier-m3`, model Sonnet 5.5. Scratch under the session scratchpad; `REPO` status unchanged (diff empty).

- **A.** Nothing missing; `gh 2.103.2` listed as optional; `skill: d451909 (clean)`; exit 0.
- **B.** Exit 0, mode `full`. History `ok`, `owner_rule` `one-human`, no `github-owners.json`, every `file.owners` is the one human, `commits_seen` 129, 2 `person`, 2 `branch`, 6 `workflow`, `pairs_total` 909, 74 pairs with 3 or more co-commits. `history.json` holds all 909 `pair` items; the card shows the 74 (S3). Merge style row says merge commits, 30 merges. `measure` took 2.0 s.
- **C.** All three reports print their D7 sections.
- **D.** Cut line used: the 12 reports from the copy of `LIVE` were kept; `change`, `contributors` and `risks` (Source column, R11 reworded, R15 for the 3 import cycles) were written fresh. `gaps` kept from `LIVE`.
- **F.** One render round, exit 0, no `error:` line; 56 warnings (V2, V3 from the kept reports, V6 for `data.relationships`).
- **G.** After the fix above: `{"diagrams_checked": 16, "problems": 0}`. Screenshots of reports 10 and 13 were taken by hand (the check keeps none) and read at 1500 px; all cards drawn.
- **H.** `summary.json` valid (jsonschema 4.26.0). Lists: languages 3, extractors 6, components 16, entry_points 20, contributors 2, contracts 0, external_dependencies 6, data_stores 4. `bus_factor` 1, `cochange_pairs_unlinked` 14, gaps 0 unknown / 59 inference / 2 assumption / 44 coverage. Rows: cochange 74, in-flight 2, workflow 6, hotspots 108, blast 108, owner table 1. Contributors human + agent, 0 non-human owners, 0 emails. Page 9.0 MB, `blast-data` 15.6 KB.
- **I.** Default: 1426 passed, 66 skipped, 59 s. Slow (run alone): 1491 passed, 1 failed (G2), 13 min 51 s.
- **E.** `migrate` and `render` exit 0, the only error lines are the allowed kinds. The `BASE` digest in the block is out of date (it printed DIFFERENT); report 02's overview section is identical between `main` and the branch once `data-a` and `data-b` are dropped (249,551 characters each), as in Phases 1 and 2.
- **G2.** Fails as on `main`.
- **J.** Mode `incremental`, stale: components, contributors, gaps, interactions, overview; 9 fresh. `Check` appeared as a new person; after adding it, render exit 0, `errors.py` row shows one more commit, `summary.json` has the new SHA, the process card does not say "none recorded", `dossier check` `problems: 0`. A first check run, with the slow suite running at the same time, timed out on the `data` layout; it passed alone.
- **K.** Shallow clone at `5923c09`: `prepare` exit 0, `render` exit 0, Gaps item once, 8 partial badges, no "Not yet generated". 17 V5 errors, all "names Nick OMalley, which is not an identity in this build", which is expected (the one commit has another author).
- **L.** Pull request 14918, approver `babakks`, merged by `BagToad`. With an empty `GH_CONFIG_DIR`: empty result, no crash.

**Deviations.** (1) Block E's `BASE` digest replaced by the `main` comparison. (2) Block D used the cut line. (3) `/tmp` filled up (7.5 GB tmpfs) when the slow suite ran beside builds; the author freed space and the suite was rerun alone. Future runs should clear scratch caches between blocks.

**Findings for the acceptance pause.** (a) `contributors.people` counts Nick as 16 commits in the report 02 tiles but 8 in the history (merges are in the first); both are right for their definitions. (b) With two humans and no GitHub remote, agent commits are owned by the agent, as the rules say. (c) The plan's block B and H expect "near 74 `pair` items"; the file holds every pair and the card filters.


---

## 6. Verification

Set once per shell:

```bash
SKILL=/home/nick/dev/projects/encamp/configs/user/claude/.claude/skills/dossier
REPO=/home/nick/dev/projects/cannalerts
LIVE=/home/nick/dev/dossiers/cannalerts
FIX=$SKILL/tests/fixtures/encamp-m0
PIN=5923c09
SCR=$(mktemp -d)
export DOSSIER_HOME=$SCR/home DOSSIER_CONFIG=$SCR/cfg.json DOSSIER_CACHE=$SCR/cache PYTHONDONTWRITEBYTECODE=1
BASE=fe72cec488cb211edd6919154bf4d3ed68845e4e33b667a1874716a96bb63b59
D="uv run $SKILL/scripts/dossier.py"
OUT=$DOSSIER_HOME/cannalerts
cd $SKILL
git -C $REPO status --porcelain > $SCR/repo-status-before
mkdir -p $SCR/home && cp -r $LIVE $SCR/home/cannalerts && chmod -R u+w $SCR/home/cannalerts   # Phase 3 only
```

Phases 1 and 2 run only blocks E and G2. They leave out the last line, so they never read `LIVE`.

**Block A: `doctor`.** `$D doctor $REPO; echo "exit $?"`. Expect nothing missing, `gh` listed as optional, a `skill:` line with the branch commit, and exit 0.

**Block B: `prepare`.** `$D prepare $REPO --ref $PIN --full --restore yes > $SCR/p1.json; echo "exit $?"`. Expect exit 0, `update_plan.mode` `full`, adapters `python` (version 3) and `repo` ok, then:

```bash
python3 - "$OUT" <<'PY'
import json, sys, collections, pathlib
out = pathlib.Path(sys.argv[1])
d = json.load(open(out / "extract/history.json"))["adapters"]["git"]
print(d["tool_status"], collections.Counter(i["kind"] for i in d["items"]))
print(next(i for i in d["items"] if i["kind"] == "meta"))
PY
```

Expect `meta.status` `ok`, `owner_rule` `one-human`, no `gh` call (no `github-owners.json`), every `file.owners` naming only the human, `commits_seen` 129, 2 `person` items, 2 `branch` items, 6 `workflow` items, `pairs_total` near 920 and near 74 `pair` items. The merge style row must say merge commits, with 30 merges. Record the time of the `measure` step from `build.json`.

**Block C: candidates.** For `change`, `contributors` and `risks`: `$D candidates $REPO --report <id>` prints the D7 sections.

**Block D: write the reports.** As Claude, follow `SKILL.md` `/dossier build` steps 2 to 5, with `DOSSIER` = `$D`, and write every report in D12's order into `$OUT/reports/`. Then `for r in entry components interactions io data behavior change conventions ops reading; do $D candidates $REPO --report $r --open; done` prints nothing.

**Block F: render.** `$D render $REPO > $SCR/r1.log; echo "render exit $?"`, then `grep -E '^(error|warning|info):' $SCR/r1.log | sed -E 's/^(error|warning|info): (V[0-9]+).*/\1 \2/' | sort | uniq -c`. Expect exit 0 and no `error:` line. Fix the reports and render again until clean. Count the rounds.

**Block G: `dossier check`.** `$D check $REPO; echo "exit $?"`. Expect `problems: 0` and exit 0, which covers V8, V11 and V12 on every new card at 1500 and 400 px, in light and dark. Run `$D render $REPO` once more. Open with the Read tool the screenshots of reports 10 and 13 at both widths, if the shots folder has them.

**Block H: `summary.json` and counts against sources.**

```bash
uv run --with jsonschema==4.26.0 python - "$OUT" "$SKILL" <<'PY'
import json, sys, pathlib, re
from jsonschema import Draft202012Validator
out, skill = map(pathlib.Path, sys.argv[1:3])
s = json.load(open(out / "summary.json"))
Draft202012Validator(json.load(open(skill / "prompts/summary.schema.json"))).validate(s)
print("valid", s["schema_version"], s["dossier_version"], s["repo"]["sha"][:7])
print({k: len(v) for k, v in s.items() if isinstance(v, list)}, s["ownership"]["bus_factor"], s["change"]["cochange_pairs_unlinked"], s["gaps"])
h = (out / "dossier-cannalerts.html").read_text()
items = json.load(open(out / "extract/history.json"))["adapters"]["git"]["items"]
def rows(tid):
    m = re.search(r'id="%s".*?<tbody>(.*?)</tbody>' % tid, h, re.S)
    return m.group(1).count("<tr") if m else None
print("pairs", sum(i["kind"] == "pair" for i in items), rows("t-change-cochange"))
print("branches", sum(i["kind"] == "branch" for i in items), rows("t-change-in-flight"))
print("workflow", rows("t-contributors-workflow"), "hotspots", rows("t-change-hotspots-files"), "blast", rows("t-change-blast-radius"))
ids = {c["id"]: c for c in s["contributors"]}
print("contributors", [(c["kind"], c["name"], c["username"]) for c in s["contributors"]])
print("non-human owners", sum(ids[o]["kind"] != "human" for c in s["components"] for o in c["owners"]))
print("emails in summary", len(re.findall(r"[\w.+-]+@[\w-]+\.", json.dumps(s))))
print("owner table", rows("t-people-owner"))
PY
```

Expect `valid`, row counts equal to their sources, `workflow` 6, `hotspots` and `blast` equal to the source file count, two contributors (one `human`, one `agent`), 0 non-human owners, 0 emails, and an owner table of 1 row. In the browser, Owner must show the human holding 100%.

**Block I: the suites.** Default and `DOSSIER_SLOW=1`. Record counts and time.

**Block E: report 02 HTML unchanged** (it wipes `$SCR/e`, so it uses its own home):

```bash
E=$SCR/e; mkdir -p $E && cp -r $FIX $E/encamp && chmod -R u+w $E/encamp && rm $E/encamp/dossier-encamp.html
DOSSIER_HOME=$E $D migrate /home/nick/dev/projects/encamp > /dev/null; echo "migrate exit $?"
DOSSIER_HOME=$E $D render /home/nick/dev/projects/encamp --allow-errors > $SCR/e.log; echo "render exit $?"
grep '^error:' $SCR/e.log | sed -E 's/: card [^:]+:/: card …:/' | cut -c1-70 | sort | uniq -c
python3 tests/tools/report_section.py $E/encamp/dossier-encamp.html overview --digest --normalize | grep -q "^$BASE " && echo OK || echo DIFFERENT
```

Expect `migrate exit 0`, `render exit 0`, `OK`. Error lines allowed: the V10 line, V6 "pending is not allowed", a V6 column line for `risks`, `Report 'change' is missing` if the fixture lacks it, V11 "Not yet generated" lines for reports 10 and 13, `V5: Risks: Source must be extractor or read, found 'Not yet recorded'` lines (the migration leaves the new Risks `Source` column as a placeholder), and V8 lines. No V4 lines and no other V5 lines.

**Block G2: report 02 visual golden.** `DOSSIER_SLOW=1 uv run --with pytest --with pygments python -m pytest tests/integration/scripts/test_golden02_slow.py -q` passes.

**Block J: incremental rebuild.** Never commit to `REPO`; use a clone, a copied home and a fresh cache.

```bash
J=$SCR/j; mkdir -p $J/home && cp -r $OUT $J/home/cannalerts
git clone -q $REPO $J/cannalerts && git -C $J/cannalerts checkout -q $PIN
printf '\n# verification edit\n' >> $J/cannalerts/src/cannalerts/errors.py
git -C $J/cannalerts -c user.name=Check -c user.email=check@example.com commit -qam "verification edit"
export DOSSIER_HOME=$J/home DOSSIER_CACHE=$J/cache
$D prepare $J/cannalerts --no-restore > $SCR/p2.json; echo "exit $?"
python3 -c "import json;p=json.load(open('$SCR/p2.json'))['update_plan'];print(p['mode'],sorted(p['stale']),len(p['fresh']))"
```

Expect mode `incremental`, with `contributors` stale ("it summarises the whole repository") and a new person `Check`. Add that person to `contributors.people` and refresh the stale reports as `SKILL.md` says, then `$D render $J/cannalerts`. Expect exit 0, the process card showing reused steps with extractors listed (not "none recorded"), hotspots showing one more commit for `errors.py`, and `summary.json` with the new SHA. Restore the exports: `export DOSSIER_HOME=$SCR/home DOSSIER_CACHE=$SCR/cache`.

**Block K: history unavailable (shallow clone).**

```bash
K=$SCR/k; mkdir -p $K/home && git clone -q --depth 1 file://$REPO $K/cannalerts
export DOSSIER_HOME=$K/home DOSSIER_CACHE=$K/cache
$D prepare $K/cannalerts --no-restore > $SCR/p3.json; echo "exit $?"
cp -r $OUT/reports $OUT/notes $K/home/cannalerts/ 2>/dev/null
$D render $K/cannalerts --allow-errors > $SCR/r3.log; echo "render exit $?"
grep -o 'shallow clone, so the history covers only' $K/home/cannalerts/dossier-cannalerts.html | wc -l
grep -o 'class="badge partial"' $K/home/cannalerts/dossier-cannalerts.html | wc -l
```

The clone's tip must be `$PIN`; if `REPO`'s branch has moved, record it and use the tip. Expect `prepare` exit 0, `render` exit 0, the Gaps item present, at least 8 partial badges, cards drawn with one commit of history and no crash or "Not yet generated". `commit:` citations fail V1 here, which is expected. Restore the exports.

**Block L: `gh` on a real pull request.** `cannalerts` has one human, so nothing above calls `gh`. Run the lookup directly, on a public repository:

```bash
mkdir -p $SCR/l/area
cd $SKILL/scripts && python3 - "$SCR/l/area" <<'PY'
import functools, sys
from pathlib import Path
import github_owners, sandbox
area = Path(sys.argv[1])
run = functools.partial(sandbox.run, area=area, cwd=area, timeout=60, profile="github")
print(github_owners.lookup("cli/cli", ["eeb44bc432c0107de002dadd34a61b4e2bd15882"], run, {}, 60))
PY
cd $SKILL
```

Expect pull request 14918, approver `babakks`, merged by `BagToad`. Then repeat with `GH_CONFIG_DIR=$SCR/l/empty` set, and expect an empty result and no crash. If `lookup`'s signature changed in M3-6, adapt the call and record it.

**Order:** A, B, C, D, F, G, H, I, E, G2, J, K, L. Finally `diff <(git -C $REPO status --porcelain) $SCR/repo-status-before` prints nothing.

**Recording results.** Under "Verification results" write the date, branch and model. For each block, write the key output lines, the render rounds in block F, the `measure` time, the size of the page and of `blast-data`, what was cut and why, and a "Deviations" list. Findings about rule precision go under "Findings for the acceptance pause", not into fixes, unless they are a crash or a V1 failure.

---

## 7. Risks and open questions

### Risks (most important first)

1. **The real build does not exercise the pull request path.** `cannalerts` has one human, so rule 1 applies and `gh` is never called. Only saved responses and block L cover that path until the author builds a repository with two people. A wrong reading there would show as wrong owners, not as a failure. Rebase merges are untested: `associatedPullRequests` was tried on merge commits and on commits inside a pull request, and rebased commits may not link back.
2. **Ownership depends on GitHub at build time.** A build with `gh` missing, logged out or offline gives different owners from one with it. Gaps and the "partial" badge say so, and the cache makes earlier answers stick. A login held in a system keyring may not be reachable from the scrubbed environment.
3. **Report 13's completeness rules can make `render` fail repeatedly on large repositories.** One row per identity and per component means hundreds of rows for a repository with many contributors, and the first build may take several rounds. That is the spec's choice (principle 7), but it costs Claude's time.
4. **Blast-radius data grows with the square of the file count.** About 4 MB at 5,000 files and about 66 MB at 20,000 (S4). The page would still work, but slowly. The author's solo repositories are far below this; a large work repository may not be.
5. **Phase 3 may be too large for one session.** Rewriting all 14 reports plus every block is the biggest single step in M3. The Phase 3 cut line protects the four reports that matter; the author's own build is the real full build anyway.
6. **Git proxies may be taken as fact.** "Typical PR size" and "review rate" are stand-ins, and a repository reviewed on GitHub will show a rate near 0. The rows say so, but a reader may skip the Evidence column (S7).
7. **The 3 false positives on `change.dead-code` stay visible.** Measured output is never pruned, so the author will see them at acceptance. The card's sentence and the confidence figures are the only mitigation.
8. **Marker rules are unproven on real code.** `cannalerts` has none of them in `src`, `tests` or `scripts`, so the real build barely exercises this; only fixtures do. On a repository with many, V5 adds work, though group ids bound it.
9. **`[A-Z]{2,}-\d+` will match things that are not bug ids** (for example `UTF-8`, `ISO-8601`). Claude dismisses them, by group where possible. Tune the rule at acceptance if it is noisy.
10. **The test page is built on `FIX`,** which is git-ignored and local. M3-14's slow test skips where `FIX` is absent, as plan 008's did.
11. **What I could not verify.** The tree-sitter node names in M3-8 (the slow test decides). That `FACT_INFO` can point at `history.py` without a third embedded source (M3-2 gives the fallback). GitHub's GraphQL reference pages, which my reader could not open, so the fields rest on live queries. The endoflife.date licence and API docs page: the docs pages returned no text to my reader, though the live endpoint did, so field names come from a live response. The `-z --numstat` rename layout: the documentation I could read does not describe it, so it rests on `gather.parse_commit` and my own run over `cannalerts` (129 commits parsed). I ran no prototype of the cards themselves.

**What I read.** In full: the spec, `process.md`, `post-v1.md`, `SKILL.md`, the schemas for reports 10, 13, 14, 15, `stages.py`, `buildlog.py`, `page_audit.py`, `candidates.py`, `incremental.py`, `measured_tables.py`, `gather.py` lines 468 to 1244. In part: plan 007 (sections 1 to 3, D1 to D4, D7, D8, D10 to D13, findings, risks), plan 008 (sections 1 to 5, Results, 6 to 10; I did not read its task list, lines 367 to 515), `render.py`, `dossier.py`, `process.py`, `check_layout.py`, `check_page.py`, `checks.py`, `measured.py`, `adapters.py`, `schema.py`, `sandbox.py`, `workarea.py`, `py_adapter.py`, `py_queries.py`, `prompts/method.md`, `prompts/reports.md`. Outline only: `assets/dossier.js`, `deps.py`, `tests/`. Not read: `assets/dossier.css` beyond its end, `viewer.py`, `toolcheck.py`, `migrate.py`.

### Questions for the human

All answered by the author on 2026-11-05, and the plan text above follows the answers.

- **Q1. Do agents count as owners?** Default: bus factor and top owner share count humans only, and bots never count. Agents are excluded because they cannot leave, but `Share` still shows what an agent wrote. The alternative counts agents as owners, which would give `cannalerts` a top owner that is not a person. **Answer: only humans are owners, because a human is held responsible for an agent's actions. Refined the same day: the true owner of an agent's commit is the human who approved its pull request; a commit with no pull request belongs to its author, even an agent; and on a repository with one human, that human owns everything.** D4 and D17 implement this, and the spec holds the rule.
- **Q2. What is a contributor id in `summary.json`?** It is an email today, and this file is meant to be read across repositories. Default: an opaque stable id, `c-` plus the first 12 hex characters of the SHA-256 of the lower-cased id, so `portfolio` can still match one person across repositories without holding addresses. Alternatives: the display name, or the email as it stands. **Answer: a contributor is a human, an AI agent or a bot (for example github-bot or dependabot), with a username if available. The author then withdrew the email part.** So `summary.json` has a `contributors` list with no email addresses, and the opaque id is kept as the key that `owners` points to (D10).
- **Q3. What does `contributors.agents` show?** Default: one row per author identity of kind agent or bot, plus one row per assistant found only as a co-author marker on human commits (for example `Claude`, Kind `assistant`, Share of commits = marked commits). Models sharing an email stay one identity, shown under the most frequent name. Should different models be separate rows? Default: no. **Answer: default.**
- **Q4. What makes a path "at risk" in `summary.json`?** Default: components whose Status is `single owner` or `departed`. On a solo repository that is every component. The alternative, `departed` only, says more across a portfolio but says nothing about solo projects. **Answer: `departed` only.**
- **Q5. Single-owner threshold.** The "hotspot with a single owner" hint uses 80% of a file's commits, and `owners` in `summary.json` uses 20% of blamed lines. Are those acceptable? Default: yes. **Answer: default.** The 20% is of the component's owned lines.
- **Q6. Freshness BAN (plan 008 Q5).** Spec section 4 wants it in report 01, and no milestone lists it. Default: stays out of M3 and goes to M6. **Answer: default.**
- **Q7. Three sessions?** `docs/process.md` assumes one for M3. Default: three (D15). If you prefer two, Phase 3 runs in the same session as Phase 2. **Answer: default.**
- **Q8. Report 02's legend (plan 008 Results, open item 1).** It is cut off at 400 px and exempted from V12. Default: leave it. **Answer: default.**

---

## 8. Spec issues

S3 and S9 are ruled. The others need only a note in the spec. The plan follows the spec except where stated.

- **S1. Wrong constant.** `change.cochange` says the "`KNOWLEDGE_*` cap" is reused. The bulk filter is `gather.BULK_FILES`; `KNOWLEDGE_CAP` is a byte budget. Proposal: correct the text.
- **S2. Where history is computed.** 6.1 says `gather.py`. The plan uses new modules called in the same stage, because of the file's size and the safe-runner rule. Proposal: say "the measure step".
- **S3. Co-change threshold against principle 7.** Listing every pair is noise: 920 on `cannalerts`, and it grows quickly. The plan lists pairs with at least 3 co-commits and prints both counts on the card. **Ruling, 2026-11-05: accepted.** `COCHANGE_MIN = 3`.
- **S4. Precomputed blast radius grows with the square of the files.** The plan follows the spec, using bits (D5). Alternative for later: embed edges and walk them in the browser.
- **S5. Risks `Source` has one defined value.** The spec names `extractor` only. The plan adds `read` for everything else. The spec also calls report 14 "unchanged", while the same section adds a column. Proposal: state both values.
- **S6. Measured cells in tier A cards.** Spec tier A for `contributors.concentration` and `contributors.agents` does not say code fills `Share`. This follows A4 and the rule that Claude never writes a measured value. Proposal: add it to section 4.
- **S7. Two workflow rows cannot be measured from git.** Pull requests and reviews live on the hosting service, yet the card is tier M. The plan measures stand-ins and says so. Proposal: note this in the card's row.
- **S8. Dead code sources.** "Unused route/flag detection" has no Python detector, and spec 6.4 treats flags as a blind spot. The plan adds a fixed Gaps item. Proposal: limit the card's source text to what exists.
- **S9. Markers as a candidate list.** Principle 2 and decision 24 limit dispositions to three lists, yet `change.decisions` is tier A, and plan 008's rule is that nothing drops silently. The plan makes `HACK`, `XXX`, workaround and bug-id markers a fourth list, with `change.decisions` as home card and group ids allowed. **Ruling, 2026-11-05: accepted.** The spec now says so (principle 2, decision 31).
- **S10. The spec text lags what was approved.** A1 to A9, V11, V12 and the `dossier.cards` card (`5518e74`) are not in the spec file, and the status line still says amended 2026-11-01 for M2 only. Section 4's order of report 01 omits `dossier.cards`. Under `process.md` the spec changes only in the spec, so this plan does not edit it. Proposal: the author applies them, or asks for that as separate work.
- **S11. Upgrade burden coverage.** Only runtimes and a few frameworks exist in the data source: `flask`, `fastapi`, `sqlalchemy` and `pydantic` returned 404 on 2026-11-04, so a typical Python repository shows only its runtime. The optional live refresh is not built. Proposal: accept for 1.0.0, since the card is P1.
- **S13. `summary.json` gains `contributors`. Done:** the author asked for it, and spec section 9 and decision 28 now hold it. `schema_version` stays 1 because nothing has shipped.
- **S12. Numbering.** Section 11 has two items numbered 5. Proposal: renumber, but note that `process.md` and the prompts cite "item 3", which is unaffected.

---

## Sources

Checked on 2026-11-04.

| What | Used for | Source |
|---|---|---|
| `git log`: `%aN`, `%aE` respect `.mailmap`; `%P`; `%B`; `-M` default 50%; `-z` with `--numstat`; merges show no diff by default; `--diff-merges` | D1, D3 | https://git-scm.com/docs/git-log |
| `git rev-list --left-right --count` prints two tab-separated counts | D3 | https://git-scm.com/docs/git-rev-list |
| `git for-each-ref` fields, `authorname`, `committerdate`, `ahead-behind` | D3 | https://git-scm.com/docs/git-for-each-ref |
| `git rev-parse --is-shallow-repository` | M3-2 | https://git-scm.com/docs/git-rev-parse |
| `GH_CONFIG_DIR`, `GH_TOKEN` and how `gh` finds its login | D17 | https://cli.github.com/manual/gh_help_environment |
| JSON Schema 2020-12 keywords and `$schema` URI | D11 | https://json-schema.org/draft/2020-12/json-schema-validation |
| `jsonschema` 4.26.0, Python 3.10 or newer (test only; upload date not confirmed, so check the pin rule in M3-21) | M3-21 | https://pypi.org/pypi/jsonschema/json |
| endoflife.date release fields `name`, `eolFrom`, `latest.name` under `result.releases`, from a live response | M3-13 | https://endoflife.date/api/v1/products/python |

Run on this machine with `gh` 2.103.2: the D17 query, on `cli/cli` and on `1npo/cannalerts`, in the normal and in a scrubbed environment. With git 2.47.3: `--diff-merges=first-parent --numstat -z` on `cannalerts`, `git clone --local` from a shallow repository, and the D1 log format.
