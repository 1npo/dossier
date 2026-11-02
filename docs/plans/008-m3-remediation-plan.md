# Plan 008: remediation of the M0 to M3 output (broken page, unreadable diagrams, dropped data, and the checks that passed it)

Status: written by Opus on 2026-11-01 from `docs/prompts/plan-m3-remediation.md`, and changed the same day at the author's request to run as **one session** (Phase 1, in three parts). **Not yet reviewed.** Before the session starts, the author answers the questions in section 10 and approves or rejects each spec amendment in section 4 (A1 to A9); the session asks once at the start for anything left open. Writing this plan changed no other file; the fixes to `sync.sh` and `SKILL.md` described under "The merge conflict" in section 3.1 were made separately, at the author's request.

Written from: `plans/004-v1-spec.md`, `docs/process.md`, plans 005, 006 and 007 (including their results and deviations), the code at commit `2ed850b` (version 0.7.0, M2 merged), the author's page `~/dev/dossiers/cannalerts/dossier-cannalerts.html` and its data, a fresh render of that data with the committed code, a render of the same data with the pre-M0 skill (`fc916d6`, the parent of `91abe8e`) in a temporary git worktree (since removed), and screenshots of every card at 1500 px and 400 px in light and dark themes (322 screenshots per page; inventory script and metrics in the planning session's scratchpad, not kept).

Paths used below:

- `SKILL` = `/home/nick/dev/projects/encamp/configs/user/claude/.claude/skills/dossier` (the development copy; the planning prompt's `~/encamp/...` is not the repository that holds the commits).
- `INSTALLED` = `/home/nick/.local/share/encamp/configs/user/claude/.claude/skills/dossier`. `~/.claude/skills/dossier` is a symlink to it, so `/dossier build` runs this copy, not `SKILL`. It is a separate clone of the same repository.
- `LIVE` = `/home/nick/dev/dossiers/cannalerts`: the author's dossier. **Read-only.** Copy it to a scratch folder before rendering.
- `REPO` = `/home/nick/dev/projects/cannalerts` (pinned commit `5923c09`).
- `FIX` = `SKILL/tests/fixtures/encamp-m0` (frozen, git-ignored; never written).
- Tests: `cd SKILL && uv run --with pytest --with pygments python -m pytest tests -q`. **Baseline: 921 passed, 36 skipped** (2026-11-01, `2ed850b`).

---

## 1. Summary

The author rejected the page for good reason, but the page they reviewed is not the page the committed code produces, and it is not M3:

1. **No M3 code exists.** `git log` ends at the M2 merge (`2ed850b`, version 0.7.0); `LIVE/build.json` says `dossier_version: 0.7.0`; reports 10 and 13 are 15 "Not yet generated" placeholders and there is no `summary.json`. The acceptance test that `docs/process.md` puts after M3 was run on M2 output.
2. **The page was built from a copy of the skill that is stuck in a git merge.** `INSTALLED` has `UU assets/dossier.css` and `stash@{0}: autostash`: a pull with autostash conflicted on the dark-theme comment colour (`c94389b`). `render` pasted the conflict markers (`<<<<<<< Updated upstream` … `>>>>>>> Stashed changes`) into the page's `<style>` at character 259,502. The browser drops every CSS rule after that point (334 rules parsed), which removes the styles for the knowledge map, the Dependencies card, the commit calendar, the code viewer, the tier badges and the component and recipe entries. Unsized Lucide icons then draw at 1092 × 1092 px (191 of them in the Contributors card). That one fault explains author notes 2, 4 and 8, and part of the "ugly" process card.
3. **The browser check never ran on that build** (`LIVE/build.json` has no `check/browser` record; the page says "Browser check: not run yet"). Run now, `check_page.py` crashes on that page with a Playwright `TimeoutError` instead of reporting. On the clean render it prints `"problems": 0`, although that page still has 4 px diagram text, 27 data entities folded into other rows and 33 of 46 database columns missing from the ER diagram. **The checks pass because they test almost nothing that the author looks at** (section 3.6).
4. With clean CSS, real defects remain: unreadable graph diagrams (author notes 3 and 5), flow notes that are prose rather than steps (note 6), an ER diagram that drops most columns (note 7), entity rows that bundle up to nine entities, CLI commands collapsed into one cell, measured columns written by Claude, numbered recipe steps run together (note 8), wide tables that scroll at desktop width, and a process card that is a list (note 1).

The plan runs in **one session** with three parts, each ending at a committed, tested checkpoint: **A** repair what the author sees on the page (asset guard, diagram sizing and splitting, entries and process card as tables, wide tables); **B** make sure nothing is dropped (extraction fixes, measured ER diagram, per-item dispositions, completeness checks, prompts); **C** redesign verification (a static page audit, browser layout and readability checks, a visual golden for report 02, a `dossier check` command), then a final run on the author's data. The author then rebuilds cannalerts with `/dossier build` and runs the acceptance procedure (section 8). Version 0.7.1. M3 itself (reports 10 and 13, `summary.json`, V8) is **not** in this plan (section 9); it gets its own plan after this one is accepted.

---

## 2. Shared rules (read before any task)

- **Branch.** One branch, `fix/dossier-m3-remediation`, created from `main` at the start of the session and merged at its end. One commit per task. Load and follow `git-commit` and `git-workflow`. Commit messages below are suggestions in the style of the M2 commits.
- **Skills to load at the start:** `git-commit`, `git-workflow`, `py-projects`, `py-unit-tests`, `claude-planning-docs`. Part C also loads `docs-project`, `docs-readme`, `docs-user-guide`, `docs-dev-guide` and `git-release`.
- **Never touch:** `LIVE` (copy it), `REPO` (read only), `FIX`, and `INSTALLED` (it is updated from `main` by `encamp-sync pull`; an edit there is what caused R1). If a step seems to need a change in `INSTALLED`, make it in `SKILL` instead.
- **Report 02.** Its HTML must stay byte-identical after normalisation (block E). From task F3-3 on, its rendered look must also match the pre-M0 golden (block G2). Part A changes CSS that report 02 uses only where a task says so, and each such task runs block E.
- **Tests first.** Every task that fixes a table, a cap, a diagram or a check starts with a test that fails on the current code. Run it, see it fail, and record the failure line in the commit message body (`Fails before: …`). Then fix.
- **Slow tests.** Browser tests need Playwright and Chromium (already installed in `~/.cache/ms-playwright`). Put them in `tests/integration/scripts/` and mark them `@pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs a browser: set DOSSIER_SLOW=1")`. The full default suite must pass after every task; the slow suite at each checkpoint.
- **Scratch.** Every command that renders or builds sets `DOSSIER_HOME`, `DOSSIER_CONFIG` and `DOSSIER_CACHE` to a fresh scratch folder (section 7). Never render into `LIVE`.
- **No new runtime dependencies** in `scripts/dossier.py` or anything it imports (standard library plus `pygments`). Browser and image tools run as PEP 723 scripts through `uv`, as `check_page.py` does.
- **If the code contradicts this plan, stop and report** under "Results" in Phase 1. Do not design around it.
- **Do not weaken a check to make it pass.** If a new check fails on real output, the output is wrong until the author says otherwise.
- **Ticking.** Tick each task's checkbox in this file in the same commit as the task. Write results under Phase 1's "Results" heading.

---

## 3. Findings

### 3.1 What was tested, and how

| Fact | Evidence |
|---|---|
| Version under test is M2, not M3 | `LIVE/build.json` `dossier_version: "0.7.0"`; `git log` ends at `2ed850b Merge branch 'feat/dossier-m2'`; no `LIVE/reports/change.json` or `contributors.json` |
| Built by the installed copy, which is mid-merge | `git -C ~/.local/share/encamp status`: `UU configs/user/claude/.claude/skills/dossier/assets/dossier.css`; `stash@{0}: autostash`; `INSTALLED/assets/dossier.css:233` `<<<<<<< Updated upstream`, `:237` `>>>>>>> Stashed changes` |
| The committed code renders without the markers | Fresh render of a copy of `LIVE` with `SKILL`: 0 conflict markers; `LIVE` page: 2 |
| Browser check not run on the author's build | No record with `step: check, part: browser` in `LIVE/build.json` (17 records); process card text "Browser check: not run yet" |
| The browser check, run now | Author's page: exit 1 with a Python traceback, `playwright._impl._errors.TimeoutError: ElementHandle.click: Timeout 30000ms exceeded` from `check_viewer` (`check_page.py:168`). Clean render: `{"diagrams_checked": 6, "problems": 0}` |
| Report 02 HTML is unchanged in code | `report_section.py … overview --digest --normalize` on `FIX` gives the M0 baseline `fe72cec4…` (248,699 characters). On cannalerts, the pre-M0 skill and the current skill produce the same report 02 section except the executive summary (pre-M0 code cannot draw a list summary; it prints the Python list) |
| M2's own sign-off accepted the dense diagrams | Plan 007, Verification results, block G: "The component map and the dependency graph draw but are dense"; findings 8 and 9 deferred to "the M3 acceptance pass" |

**The merge conflict (resolved 2026-11-01, outside this plan's tasks).** `INSTALLED` is the stow source for live config, and two things write into it: Claude sessions, through the `~/.claude/skills/*` symlinks, and `systemctl --user enable/disable`, because `~/.config/systemd` is one symlink into the clone. On 2026-10-31 a dossier build session (`f9abcdf6`) followed `SKILL.md` step 7 ("Fix every `FAIL` line (usually in … the page assets)") and ran `sed -i` on `~/.claude/skills/dossier/assets/dossier.css` (`.74` to `.82`). Later that day, `ab5b81e` changed `sync.sh` to `git pull --autostash` to carry such edits across pulls. When `c94389b` changed the same line upstream, the pull fast-forwarded, the re-applied stash conflicted, and `git pull --autostash` **exited 0** (reproduced in a scratch repository), so `encamp-sync pull` reported success and re-stowed with conflict markers in a live file. Fixed in the source repository (uncommitted until the author commits): `scripts/sync.sh` `sync_pull` stashes local edits itself, fast-forwards only, re-applies them, and when they conflict restores upstream for the conflicted files, keeps the edits in a named stash and fails loudly; it also refuses to run on a clone with unresolved conflicts (tested on four scratch scenarios). `SKILL.md` step 7 now forbids editing the skill's own files and says a failure in the page assets is a dossier bug to report. `INSTALLED` was resolved to upstream and the stash dropped. Not fixed: `systemctl` still writes enable links into the clone (question Q8).

### 3.2 Card inventory

One row per schema card (65), in page order. "Author's page" is `LIVE/dossier-cannalerts.html`; "clean" is the same data rendered with `SKILL` at `2ed850b`. Shade and tier badge were checked on every card: every card has its badge, and every M card is in the facts shade and every A, R and M+A card in the model shade, as spec principle 3 requires. The fixed cards (Executive summary, Contents, References) render on every report and are not listed. Defect ids refer to 3.3.

| # | Card | Tier | Spec requires (section 4) | Rendered | Defects |
|---|---|---|---|---|---|
| 1 | `dossier.about` | M | Build facts and statistics tiles | Author: tiles, unstyled tier badge. Clean: as required | R1 |
| 2 | `dossier.process` | M | 8 to 10 steps, each with a run record (counts, tools used, skipped reasons); tier line | Clean: an ordered list of 10 steps with grey sub-lines; tools line lists git, uv, node, npm only; "Browser check: not run yet"; author asked for a table or diagram | R1, R17, R18 |
| 3 | `dossier.questions` | M | Table No., Question, Answered in; every question | Table 3 cols, 40 rows (40 questions in `questions.json`) | none |
| 4 | `dossier.reports` | M | One row per report with counts | Table, 15 rows | none |
| 5 | `dossier.changelog` | M | One row per build | Table, 1 row | none |
| 6 | `overview.repository` | M | Unchanged from pre-M0 | Same HTML as pre-M0 | none (R1 on the author's page) |
| 7 | `overview.contributors` | M | Unchanged from pre-M0 | Author: calendar collapsed to two year labels, 191 icons at 1092 × 1092 px, knowledge-map rows as raw text, card 6,259 px tall. Clean: as pre-M0, 1,401 px | R1 |
| 8 | `overview.dependencies` | M | Unchanged from pre-M0 | Author: tree rows as stacked unstyled text (4,455 px). Clean: as pre-M0 (991 px) | R1 |
| 9 | `reading.order` | A | Table Phase, Step, Read, What you learn; no step limit | Table, 18 rows; Claude was shown only the top 30 of 55 modules | R12 |
| 10 | `reading.glossary` | A | Table Term, Meaning, Where it lives | Table, 12 rows | none found |
| 11 | `reading.technologies` | A | Table Technology, Role here, Idiom to know | Table, 7 rows | none found |
| 12 | `reading.map` | M | Table Concern, Location | Table, 8 rows | none |
| 13 | `entry.catalog` | A | Table Kind, Name, Triggered by, Starts at, Notes; every entry point including CLI commands | Table, 7 rows; the ten sub-commands are one Notes cell ("Subcommands: init, validate, …") | R10 |
| 14 | `entry.startup` | R | Sequence diagram plus numbered notes | Diagram, 6 participants; text 20 px at 1500, **6 px at 400**; numbered notes present | R4 |
| 15 | `components.map` | M+A | Until M6: a component diagram grouped by area plus a table of every component and its edges | Diagram 16 nodes, 71 labelled edges, 12 subgraphs (9 hold one node), drawn 1076 × 320 px, **text 4 px at 1500, 1 px at 400**; Area column shows file names (`cli.py`, `models.py`) | R4, R5, R6 |
| 16 | `components.catalog` | A | Table Component, Paths, Responsibility, Public surface, Depends on, Used by, Size; edges and size measured | Table, 16 rows, 1321 px wide in a 1092 px container (scrolls at desktop); Depends on and Used by written by Claude ("every other component") | R11, R16 |
| 17 | `components.detail` | R | One collapsible, searchable entry per component with Purpose, How it works, Public surface, State owned, Key files, Gotchas | Clean: 16 entries as `<dl>` grids. Author: entry boxes gone, label/value runs together ("not a table") | R1, R15 |
| 18 | `components.cross-cutting` | R | Table Concern, Approach, Where; fixed rows | Table, 8 rows | none |
| 19 | `components.extension-points` | R | Table Point, How to extend, Example | Table, 6 rows | none |
| 20 | `interactions.graph` | M | Until M6: a component-level diagram plus a sortable, filterable table of every module import | Diagram 15 nodes, 71 labelled edges, no grouping, 1076 × 485, **text 6 px at 1500, 2 px at 400**; module table 225 rows (= 225 import items), card 11,583 px tall, no component columns | R4, R6, R7 |
| 21 | `interactions.violations` | M | Table Kind, From, To, Evidence | Table, 3 rows (3 cycles in `graph.json`) | none |
| 22 | `interactions.flows` | A | One sequence diagram per kind of entry point, each followed by notes; V3 | 2 diagrams. "Run" has 8 participants (text 13 px, 4 px at 400) and 5 numbered notes. "Onboarding" (text 20 px) is followed by one prose sentence | R4, R8 |
| 23 | `interactions.state` | A | Table State, Held in, Written by, Read by, Lifetime | Table, 7 rows, 1112 px wide (scrolls) | R16 |
| 24 | `interactions.concurrency` | A | Table Mechanism, Where, Shared state, Notes, or `na` | `na` with evidence (synchronous code) | none |
| 25 | `io.inputs` | A | Table Category, Input, Format, Validation, Where read; fixed categories; every candidate | Table, 14 rows; "every `cannalerts` subcommand and flag" is one row; env var `CANNALERTS_SKIP_AYR` (in `facts.json`) absent | R10, R13 |
| 26 | `io.outputs` | A | Same shape, output categories | Table, 14 rows | none found |
| 27 | `io.contracts` | A | Table, or `na` | `na` with evidence | none |
| 28 | `data.entities` | M+A | Table Name, Kind, Fields, Defined in, Owner component; every entity | Table, **25 rows for 52 extracted entities**; rows like "Config, Settings, SmtpConfig, Watch and related"; Fields "see schema" for the four SQL tables | R9 |
| 29 | `data.relationships` | M+A | ER diagram from foreign keys, ORM relations and type references; split by component beyond 12 entities | Diagram written by Claude: 4 tables, **13 of 46 columns**, no dataclass entity | R2, R3 |
| 30 | `data.stores` | A | Table Store, Technology, Holds, Migration approach | Table, 4 rows | none found |
| 31 | `data.truth` | R | Table Data, Source of truth, Derived copies | Table, 4 rows | none found |
| 32 | `data.lifecycle` | A | Table Data, Created, Changed, Retained, Deleted, Sensitive? | Table, 4 rows | none found |
| 33 | `behavior.rules` | R | Table Rule, What it does, Where decided, Edge cases | Table, 7 rows | none found |
| 34 | `behavior.tests` | A | Measured and read tables | Two tables, 8 and 2 rows (fixed rows) | none |
| 35 | `behavior.failures` | A | Table ID, Failure, Trigger, Detection, Effect, Recovery | Table, 8 rows, 1126 px wide (scrolls) | R16 |
| 36 | `behavior.observability` | A | Table Signal, Library, Where emitted, Where it goes | Table, 7 rows | none found |
| 37 to 45 | `change.*` (9 cards) | M, R, A | Report 10 | "Not yet generated" | out of scope (M3, section 9) |
| 46 | `conventions.style` | A | Table Area, Convention, Evidence; fixed rows | Table, 7 rows | none |
| 47 | `conventions.recipes` | R | Numbered recipes: files to touch in order, worked example grounded in an existing commit | Entries; numbered steps "1. … 2. … 3. …" run together in one paragraph; all six inferred, none cites a commit; author: "pile of justified text" | R1, R14, R15 |
| 48 | `conventions.tooling` | M | Table Tool, Config file, Enforced where | Table, 2 rows | none |
| 49 to 55 | `ops.*` (7 cards) | A | Tables per spec | Tables, 1 to 5 rows each, columns match schema | none found |
| 56 to 61 | `contributors.*` (6 cards) | A, R, M | Report 13 | "Not yet generated" | out of scope (M3) |
| 62 | `risks.tracker` | A | Table ID, Risk, Category, Severity, Impact, Recommendation (+ `Source` from M3) | Table, 14 rows | none in M0 to M2 scope |
| 63 | `gaps.tracker` | A | Table of every open item | Table, 106 rows = 106 items; 1314 px wide (scrolls); 35 of the items are V2 false positives | R16, R19 |
| 64 | `corrections.tracker` | M | Recorded corrections | "No corrections" text | none |
| 65 | `corrections.decisions` | M | Always present | Present | none |

Phone width (400 px): the page never scrolls sideways (`scrollWidth` = 400 on every report). Every table wider than 320 px scrolls inside its container, which is acceptable; every diagram is unreadable (2 to 6 px text, see 3.5).

### 3.3 Defects, grouped by root cause

Classes: **render** (data right, drawing wrong), **content** (data or prose wrong or missing), **violation** (code contradicts the spec), **spec gap** (spec silent or wrong), **verification** (a check should have caught it). **Regression** = it worked before M0; **gap** = it never worked.

**Group A: the page's assets and where the build came from**

- **R1. Conflict markers in the installed stylesheet break most of the page.** Class: verification + environment; regression (pre-M0 pages were fine). `render.py:1735` reads `ASSETS/dossier.css` and pastes it into the page without any check. `INSTALLED/assets/dossier.css:233-237` holds an unresolved autostash conflict. The browser's CSS parser stops at the stray `<<<<<<<` line, so no rule after `dossier.css:233` applies (the clean page parses all rules; the author's 334). Causes: Contributors, knowledge map and calendar unstyled with page-sized icons (note 2), Dependencies tree as raw text (note 2), component detail and recipe entries without boxes (notes 4 and 8), code viewer unstyled (which is why the browser check times out), tier badges unstyled. Fix: F1-1, F1-2, Q1.
- **R25 (related to R1). No build records which skill code made it.** Class: verification; gap. `build.json` has `dossier_version` only (`buildlog.py`). `/dossier` runs `INSTALLED`, while every milestone's verification ran `uv run $SKILL/scripts/dossier.py` (plan 007 section 6), so the tested code and the shipped code can differ silently. Fix: F1-1 (skill commit, dirty and unmerged state recorded in `build.json` and shown on the process card; `doctor` reports an unmerged skill).

**Group B: diagrams**

- **R4. Mermaid shrinks every diagram to the card width.** Class: render; gap. `dossier.js:41-42` sets `useMaxWidth: true` for flowcharts, ER and sequence diagrams, and `dossier.css:103` sets `.mermaid-host svg { max-width: 100% }`. A wide diagram is scaled down until its text is unreadable: component map 4 px, dependency graph 6 px, run flow 13 px at 1500 px; at 400 px every diagram is 1 to 6 px. Fix: F1-3.
- **R5. The component graphs have no density limit and label every edge.** Class: render + spec gap; gap. `measured_graph.py:73-90` puts every component and every edge, each labelled `"N imports"`, into one flowchart; cannalerts gives 16 nodes and 71 edges. No split, no budget. The spec's interim fallback (cards 05 and 06) says "a component diagram grouped by area" but sets no readability rule (A2). Fix: F1-5.
- **R6. Components are grouped under file names, not areas.** Class: content bug; gap. `measured_graph.py:132` takes the area from `row["paths"][0]`; for a component whose first path is a file in the package root, `area_of` (`measured_graph.py:46-55`) returns the file name. Nine of twelve subgraphs hold one node, named `cli.py`, `config.py`, `models.py`, `browser.py`, `engine.py`, `onboarding.py` and so on; the Area column repeats them. Fix: F1-4.
- **R7. The dependency graph is not grouped at all, and its module table cannot be read by component.** Class: render; gap. `measured_graph.py:122` calls `_flowchart(edges, None)` (no areas). The 225-row module table (`_edge_table`, `measured_graph.py:101-108`) has From, To, Imports, Lines, with no component columns and no component-level edge table (plan 007 finding 9). Fix: F1-5.
- **R8. Flow notes are optional, so a flow can end in prose.** Class: violation (spec 06 "each followed by notes"; the author expects steps as for the first flow); gap. `prompts/reports.md:83` says "each optionally followed by one text or list block", and `schema.py:128-144` (`_check_flows`) accepts a diagram with no notes or with a paragraph. Fix: F2-8, A7.
- **R2. The ER diagram is written by Claude and drops columns and entities.** Class: violation (principle 7; card 08 source "Foreign keys, ORM relations, type references", tier M+A); gap. `prompts/schema/data.json` makes `data.relationships` a Claude-written diagram; `reports.md:145` does not ask for every column. Claude drew `runs` with 1 of 4 columns, `scrapes` 4 of 13, `products` 3 of 20, `alert_episodes` 5 of 9 (13 of 46), and none of the 48 dataclass entities (author note 7). Fix: F2-2, A3.
- **R3. SQL tables are extracted wrongly, and their foreign keys never become relations.** Class: content bug; gap (plan 007 finding 5, deferred). `repo_adapter.py:88-108` (`_columns`) splits a `CREATE TABLE` body on commas without removing `--` comments, so after `shop TEXT NOT NULL,  -- internal store key` the next column becomes a field named `--` and its real name is lost (`scrapes` loses `site` and `started_at`; `products` loses `shop` and `retrieved_at`). `REFERENCES` is read into each field's `ref`, but no item gets a `relations` list. Fix: F2-1.

**Group C: tables and dropped data**

- **R9. Entities are merged into shared rows, and their fields are summarised.** Class: violation (principle 7: "no caps on … entities … or rows"); gap. Candidates are grouped by rule and file (`candidates.py:53`), and V5 accepts a group id as a decision for every member (`candidates.py:164-168`, `checks.py:100`). `method.md:222` invites this ("put the group id to cover every finding of that rule in that file"), and `method.md:3` ("write short reports") and `reports.md:9` ("Aim for the smallest report") push toward it. Result: 52 entities, 25 rows; "Config, Settings, SmtpConfig, Watch and related"; Fields "see schema". V5 reports 0 open. Fix: F2-3, F2-9, A5.
- **R10. CLI commands are not extracted, so they collapse into one cell.** Class: violation (6.1 lists CLI commands as an entry-point kind; 11 item 3 wants recall 100%); gap. `rules/python/entry.yml` has a click/typer rule only; argparse sub-parsers (`cli.py:526-531`, registered through a helper `add(name, handler, help)`) are invisible. Claude put the ten commands in one Notes cell of `entry.catalog` and one row of `io.inputs`. Fix: F2-5, F2-9.
- **R11. Measured catalog columns are written by Claude.** Class: violation (05: "Paths, edges and size are measured. Responsibility is read"); gap. `components.catalog` cells Depends on, Used by and Size come from Claude's JSON; the `tests` row says "every other component". Fix: F2-6, A4.
- **R12. Claude is shown only the top 30 modules for the reading order.** Class: violation (principle 7; 03 "there is no step limit"); gap. `candidates.py:266` slices `[:30]` and `candidates.py:298` prints "(top 30)"; cannalerts has 55 modules. Fix: F2-7.
- **R13. An environment variable the gatherer found is missing from Inputs.** Class: content; gap. `facts.json` lists `CANNALERTS_SKIP_AYR`; `io.inputs` has no row naming it (it appears only in `behavior` and `ops`). Nothing checks that `facts:env_vars` reach `io.inputs`. Also the gatherer caps env-var hits at 60 per file (`gather.py:902`) and 300 names (`gather.py:1186`), which `io.inputs` relies on. Fix: F2-4.
- **R14. Recipes are not grounded in commits.** Class: violation (11: "each recipe grounded in an existing commit that did the same thing"); gap. All six are `inferred` with the note "Written from the code layout and developer guide, not from a specific past commit"; nothing asks for or checks a `commit:` citation. Fix: F2-9, F2-10.

**Group D: drawing of tables, entries and the process card**

- **R15. Entry fields are drawn as one line of inline text.** Class: render; gap. `render.py:894` passes each field through `inline()`, never `md()`, so "1. Add a … 2. Register … 3. Add tests …" is one run of text, and an entry is a `<dl>` grid that collapses to running text when its CSS is missing (notes 4 and 8). Fix: F1-6.
- **R16. Wide tables scroll sideways at desktop width with no sign that they do.** Class: render; gap. `dossier.css:90` gives every cell `min-width: 7.5rem`, the authored tables add Basis and Sources columns, and multi-path `<code>` cells do not break. `components.catalog` (1321 px), `gaps.tracker` (1314 px), `behavior.failures` (1126 px) and `interactions.state` (1112 px) overflow a 1092 px container at 1500 px. Fix: F1-8.
- **R17. The process card is a list the author finds hard to read.** Class: spec gap (4 says "a short numbered list"); the author asked for a table, a diagram or both (note 1). Fix: F1-7, A1.
- **R18. The process card's tools line omits the extractors and their versions.** Class: violation (01 "the extractor list with versions"); gap. `process.py:47-52` lists `rec["tools"]` of the `tools` step, which holds host tools only (git, uv, node, npm); grimp 3.17, vulture 2.16, semgrep 1.181.0, tree-sitter-language-pack 1.22.1 and scip-python 0.6.6 are in the `extract` record's adapter details and never shown. Fix: F1-7.

**Group E: the checks**

- **R19. V2 fires on file and module names, so its warnings are ignored.** Class: verification; gap. `checks.py:221-226` treats `cli.py`, `models.py`, `alerts.state` and `menus.scrape_cached` as identifiers; 35 warnings and 35 Gaps items on cannalerts, most of them false. Warnings never block, so a run with 61 warnings is normal and real problems drown. Fix: F2-11.
- **R20. `check_page.py` checks almost nothing the author looks at, and has no tests.** Class: verification; gap. Section 3.6 lists what it asserts. It has no check for table structure, row counts, element width, icon size, text size in diagrams, flow notes, overlapping text, or whether the stylesheet loaded. It crashes rather than reporting when a step fails (`check_page.py:168`). There is no test file for it. Fix: F1-2, F3-2.
- **R21. Nothing compares the rendered page with its sources.** Class: verification; gap. V6 (`schema.validate`) checks the report JSON's columns and order; script-drawn cards, entries and the final HTML are never checked against the schema or against row counts. Fix: F3-1.
- **R22. The report 02 guard covers its HTML only.** Class: verification; gap. `tests/tools/report_section.py` digests the `<section id="overview">` text. The CSS and JS that draw it are outside the digest, and the guard runs on `FIX`, never on the built page. R1 broke report 02 completely and the guard would still print `OK`. Fix: F3-3.
- **R23. The browser check is optional in practice.** Class: verification; gap. `SKILL.md:51` (build step 7) asks for it in prose; `render` neither runs it nor marks the page as unchecked beyond one grey sentence. Fix: F3-4.
- **R24. Human review of screenshots was done by the implementer, against no threshold.** Class: verification (process); gap. Plan 007 block G told the implementing model to "look at" the screenshots; it saw "dense" diagrams and passed them, and moved its own findings 8 and 9 to the next milestone. Fix: thresholds become checks (F3-2); the final look is the author's (section 8), with a full build.

### 3.4 Dropped-data audit

Every limit, slice, sample or summary found by grepping `scripts/`, `prompts/` and `prompts/schema/` (`[:N]`, `top N`, `_CAP`, `MAX_`, `trimmed`, "at most", "short", "merge", "group"). Display truncation of ids and hashes (`sha[:7]`, `hexdigest()[:8]`) and error-message previews (`checks.py:175`, `process.py:303`) are omitted: they drop no data.

| Where | What it limits | Affects | Verdict |
|---|---|---|---|
| `candidates.py:266`, `:298` | Modules shown to Claude for the reading order: top 30 by PageRank | `reading.order` | **Remove** (R12, F2-7) |
| `candidates.py:53` + `checks.py:100` | A group id decides every finding of a rule in a file | `data.entities`, `entry.catalog` (and every V5 card) | **Restrict** to call-site findings (R9, F2-3, A5) |
| `method.md:3` "write short reports"; `reports.md:9` "Aim for the smallest report" | Report size | every written card | **Reword** (F2-9) |
| `method.md:222` merge by group | Rows per finding | every V5 card | **Restrict** (F2-9) |
| `method.md:408` "Keep each diagram to about 6 to 10 nodes" | Nodes per Claude diagram | `entry.startup`, `interactions.flows` | **Reword**: split into more diagrams, never drop (F2-9) |
| `reports.md:31`, schema `entry.startup.max_diagrams: 1` | One startup diagram | `entry.startup` | Keep: the spec card is "Sequence diagram" (one); not a cap on content |
| `gather.py:902` `[:60]` env-var hits per file; `gather.py:1186` `[:300]` names | Env vars fed to `io.inputs` | `io.inputs` | **Remove** (F2-4); report 02 does not draw env vars (removed in 0.5.0), so its HTML is unaffected |
| `gather.py:355` `[:300]` dependencies per manifest | Manifest dependencies | report 02 (Overview, Dependencies) | Keep: report 02 must stay unchanged (spec issue A6) |
| `gather.py:1087` `ranked[:60]`, `:1089` `[:30]`, `render.py:1354` `[:40]` | Contributors listed, calendar people, contributor table rows | report 02 | Keep (A6); cannalerts has 2 contributors, nothing dropped |
| `gather.py:1125` `[:10]` tags; `render.py:1025` `tags[:10]` | Releases listed | report 02 | Keep (A6); cannalerts has 0 tags |
| `gather.py:531`, `:535`, `:1108`, `:1114` area slices (`[:4]`, `[:14]`, `[:60]`, `[:5]`) | Areas and their top people | report 02 (areas no longer drawn), M3's report 13 | Keep for 02; M3's plan must not feed report 13 from these slices (section 9) |
| `gather.py:548` `ACTIVITY_CAP`, `:610` `KNOWLEDGE_CAP`, `deps` `trimmed` | Bytes of per-file data embedded for the report 02 views | report 02 | Keep (A6); the page says when it trims; cannalerts trimmed 0 |
| `gather.py:1175` `bulk[:20]`, `:1188` `sensitive[:50]`, `:1235-1237` `[:2000]`, `[:50]` | Bulk commits, sensitive files, delta lists | facts only | Keep; not drawn; flag for M3 (`change.*` must not read `bulk_commits` as complete) |
| `viewer.py:23-24` `MAX_LINES`, `MAX_BYTES` | Lines embedded in the code viewer | viewer only | Keep; the page links the full file at the pinned commit |
| `render.py:1733` `description[:300]` | Masthead lede | masthead | Keep (pre-M0, full text in `title`) |

Counts, source against page (cannalerts, clean render):

| List | Source | Page | Lost |
|---|---|---|---|
| Data entities (`models`, non-migration) | 52 | 25 rows | 27 folded into other rows; fields summarised |
| SQL columns | 46 (`schema.sql`) | 13 in the ER diagram | 33 |
| Dataclass entities in the ER diagram | 48 | 0 | 48 |
| CLI sub-commands | 10 (`cli.py` `add(…)` calls) | 0 rows (one Notes cell) | 10 |
| Env vars in `facts.json` | 4 | 3 in `io.inputs` | 1 |
| Modules shown for the reading order | 55 | 30 | 25 |
| Module imports | 225 | 225 rows | 0 |
| Components | 16 | 16 rows | 0 |
| Gaps items | 106 | 106 rows | 0 |
| Questions | 40 | 40 rows | 0 |

### 3.5 Diagram audit

Text height is the rendered height of the first label in the SVG; budgets are the ones D3 sets.

| Diagram | Kind | Nodes / edges | Drawn at 1500 (400) | Text at 1500 (400) | Readable? | Spec requires instead |
|---|---|---|---|---|---|---|
| `entry.startup` | sequence | 6 participants, 8 messages | 1059 × 653 (304 × 187) | 20 px (6 px) | Desktop yes, phone no | Readable at drawn size (A2) |
| `components.map` | flowchart | 16 / 71, 12 subgraphs | 1076 × 320 (304 × 91) | 4 px (1 px) | No | Diagram grouped by area plus a table of every component and edge (05, until M6) |
| `interactions.graph` | flowchart | 15 / 71, no grouping | 1076 × 485 (304 × 137) | 6 px (2 px) | No | Component-level diagram plus a sortable, filterable table of every module import (06, until M6) |
| `interactions.flows` #1 run | sequence | 8 participants, 10 messages | 1076 × 457 (304 × 129) | 13 px (4 px) | Barely; phone no | Diagram followed by notes |
| `interactions.flows` #2 onboarding | sequence | 5 participants, 8 messages | 1076 × 666 (304 × 188) | 20 px (5 px) | Desktop yes; notes are prose | Diagram followed by notes (A7: numbered) |
| `data.relationships` | ER | 4 entities, 2 relations | 410 × 814 (304 × 603) | 21 px (16 px) | Yes, but 33 columns and all dataclasses missing | ER from foreign keys, ORM relations, type references; split by component beyond 12 entities |

### 3.6 Check audit: what each check asserts, and what it missed

| Check | What it asserts (code) | Should have caught | Why it did not |
|---|---|---|---|
| V1 (`render.validate`) | Every citation resolves at the pinned commit | — | Works; 0 unresolved |
| V2 (`checks.v2`) | Backticked names appear in the cited lines | — | Fires on file and module names (R19); warnings only, ignored |
| V3 (`checks_v3`) | Each arrow in a flow diagram has an import or call behind it | — | Works as specified; says nothing about notes or size |
| V4 (`checks.v4`) | Every source file is in exactly one component; every component has a detail entry | R11 (partly) | Checks membership, not that Depends on, Used by and Size equal the measured values |
| V5 (`checks.v5`) | Every candidate or its group has a disposition | R9, R10 | Accepts group ids; for entities and entry points that lets one row swallow many items |
| V6 (`schema.validate`) | Report JSON matches the schema: ids, order, titles, table columns, fixed rows, flows start with a diagram | R8, R15, R21 | Checks JSON only; notes optional; never sees the HTML or script cards |
| V7 | Blind-spot hits go to Gaps | — | Works |
| V9, V10 (`process.validate_build`) | Path filter counts; a record for every step | R25, R23 | Does not ask which skill code ran; the browser check is a record of step `check`, which `render` already supplies, so V10 passes without it |
| report 02 guard (`report_section.py`) | SHA-256 of report 02's HTML on `FIX` | R1, R22 | CSS and JS are outside the digest; never run on the built page |
| `check_page.py` | Mermaid draws without error; text in diagrams has contrast ≥ 4.5:1 and is not clipped by its own label box; table headers have sort buttons; citation and gap-id tooltips show; code viewer keys, width, token contrast; knowledge-map controls and phone width; search opens an entry | R1, R4, R5, R6, R7, R8, R15, R16, R17 | Measures contrast, not size; never checks that the stylesheet loaded, that a table card has a `<table>`, row counts, element or icon size, notes after flows, or overlap; crashes instead of failing; not run on the author's build (R23) |
| Plan 007 block G "look at the screenshots" | A model's judgement | R4, R5, R6, R7 | No threshold; the implementer judged its own work and passed "dense" (R24) |

---

## 4. Spec issues (each needs the author's approval)

Nothing below is assumed. Each item says which tasks depend on it and what happens if it is rejected.

- **A1. `dossier.process` becomes a table.** Spec 4 (01) says "a short numbered list of 8 to 10 steps". The author's note: "It must be a table, a diagram, or both." Proposal: a table with columns **No., Step, What happened, Status** (one row per fixed step, the run record in "What happened", a status badge ok / skipped / failed / reused / not run), followed by the tier line. Amend 4 (01) accordingly. Tasks: F1-7. If rejected: F1-7 keeps the list and only fixes R18 and the status badges.
- **A2. The interim graph fallback gets a readability rule.** Spec 05 and 06 say "a component diagram grouped by area plus a table" with no size rule; that permitted a 71-edge diagram at 4 px. Proposal, added to both cards and to section 7 as part of the new V12: every diagram is drawn at its natural size (never scaled below it) with text at least 11 px; a flowchart holds at most 12 nodes and 30 edges, and a larger graph is drawn as an overview of areas plus one diagram per area; the full edge set is always in a table (a component dependency matrix on `components.map`, a component edge table plus the module table on `interactions.graph`). Nothing is dropped, so principle 7 holds. Tasks: F1-3, F1-5, F3-2. If rejected: F1-3 still stops the shrinking (that is a bug); F1-5 is skipped.
- **A3. `data.relationships` is drawn by code.** Spec 08 gives it tier M+A and the source "Foreign keys, ORM relations, type references", but the M0 schema made Claude write it. Proposal: `writer: script`, shape `computed`; code draws every entity (SQL tables and Python model classes) with every field and every relation, split by owner component beyond 12 entities; Claude's part is the entity rows in `data.entities`, as with `components.map` and `components.catalog` (spec decision 13). Tasks: F2-2. If rejected: F2-2 is replaced by a completeness check that fails when Claude's ER diagram omits an entity or column (same test data).
- **A4. The measured columns of `components.catalog` are drawn by code.** Spec 05 already says "Paths, edges and size are measured", but the schema lets Claude write them. Proposal: `render` fills Depends on, Used by and Size from the measured catalog edges and line counts; Claude writes `-` in those cells. Tasks: F2-6. If rejected: F2-6 becomes a check that Claude's cells equal the measured values (error).
- **A5. Group decisions are limited to call-site findings.** Spec decision Q2 of plan 007 allowed a group id (all hits of one rule in one file) for every candidate list. Principle 7 forbids folding entities, entry points or rows. Proposal: a group id may decide `io_candidates` only (log calls, retries, timeouts and other call sites); each entry point and each data entity gets its own row (an entry-point row may hold several ids only when they are the same entry point found twice, that is the same `path` and `name`); each `data.entities` row's Fields cell lists every field. Amend principle 2 and section 7 V5. Tasks: F2-3. If rejected: F2-3 is skipped and R9 stays open; say so in acceptance.
- **A6. Report 02's caps are an accepted exception to principle 7.** Report 02 must stay unchanged (spec 4, 12 decision 1) but its code caps contributors (40 shown), tags (10), dependencies per manifest (300) and trims the knowledge map and activity data to a byte budget. Proposal: record these as an explicit exception in principle 7 ("report 02 keeps its pre-1.0 limits; it says on the page when it trims"), and forbid any schema card from reading those capped facts (M3 must take uncapped data). No task changes report 02. If rejected: the author decides whether report 02 may change, and this plan gains a phase.
- **A7. Flow and startup diagrams are followed by numbered notes.** Spec 06 says "each followed by notes"; 04 already says "numbered notes". Proposal: 06 says "each followed by numbered notes, one per step of the diagram", and V6 enforces it for both cards. Tasks: F2-8. If rejected: F2-8 enforces only that notes exist.
- **A8. Verification gets two page-level checks.** Section 7 has no check on the rendered page beyond V1. Proposal: **V11 page completeness** (static, run by `render`, error): every table-shaped card renders a real `<table>` with every schema column and one row per source record; every entries card renders one entry per source entry with every field; measured cards render every source item. **V12 page layout and readability** (browser, run by `dossier check`, error): the stylesheet and script loaded completely; no element wider than the viewport outside a scroll container; icons no larger than 48 px; diagram text at least 11 px; the A2 budgets; numbered notes after every flow; no overlapping text in a card; at 1500 and 400 px in both themes. Tasks: F3-1, F3-2, F3-4.
- **A9. A build records which skill code made it.** Proposal: 5.1 step 7 adds the skill's path, commit, and whether its working tree is dirty or unmerged; `render` refuses assets with conflict markers; `doctor` reports an unmerged skill. Tasks: F1-1.

Also noted, no amendment proposed here: spec 4 (01) asks for a **freshness BAN** that no milestone lists (plan 006, spec issue 7). It is not a regression; question Q5 asks where it goes.

---

## 5. Decisions

### D1. Scope and version

This plan fixes what M0 to M2 delivered and the checks that passed it. It does not write reports 10 and 13, `summary.json` or V8 (M3). Version **0.7.1** at the end of the session. The M3 plan is the next file in `docs/plans/` after this one.

### D2. Asset integrity and build provenance (F1-1)

- `render.load_asset(path) -> str` reads an asset and raises `SystemExit("render: <path> holds a git conflict marker at line N. Resolve the merge in <repo> and render again.")` when any line matches `^(<{7}|={7}|>{7})( |$)`. `render_html` uses it for `dossier.css`, `dossier.js`, `template.html`, the vendor files and `viewer`'s embedded assets.
- `dossier.css` ends with the line `:root { --dossier-css-end: 1; }`, and `dossier.js` ends with `document.documentElement.dataset.dossierJs = "ok";` as its last statement. A test asserts both are the last non-blank lines.
- `buildlog.skill_state() -> {"path", "commit", "dirty", "unmerged"}`: `git -C ROOT rev-parse HEAD`, `git status --porcelain -- .` (dirty when any line), unmerged when any line starts with `UU`, `AA`, `DD`, `AU`, `UA`, `DU` or `UD`. `None` values when `ROOT` is not in a git work tree. `prepare` stores it in the `tools` record's `details.skill`; `render` stores it in its `check/render` record. `doctor` prints `skill: <commit> (clean|dirty|UNMERGED: run git status in <repo>)` and exits 1 when unmerged.

### D3. Diagram sizing and budgets (F1-3, F1-5)

- **No shrinking.** `dossier.js` sets `useMaxWidth: false` for `flowchart`, `er` and `sequence`. `dossier.css` replaces `.mermaid-host svg { max-width: 100%; height: auto; }` with `.mermaid-host svg { max-width: none; height: auto; }` and gives `.mermaid-host` `overflow: auto; max-height: 80vh;`. A host whose content is wider than itself gets the class `scrolls` (set in `drawIn` after render) and shows a caption "Scroll to see the whole diagram, or use Expand." The Expand button stays.
- **Layout engine:** Mermaid's default (dagre). The vendored Mermaid is 12.2.0; ELK is a separate package and is not added.
- **Budgets** (constants in `measured_graph.py`): `MAX_NODES = 12`, `MAX_EDGES = 30` for a flowchart drawn by code. The browser check (F3-2) also enforces: sequence diagrams at most 10 participants, ER diagrams at most 12 entities, flowcharts written by Claude at most 12 nodes. Over budget for a Claude diagram is a V12 failure that the prompt (F2-9) tells Claude to avoid by splitting the flow.
- **Text:** at least 11 px rendered height for every text element in every diagram, at both widths.

### D4. The two graph cards (F1-4, F1-5)

- **Areas.** A component's area is the first folder below its package root that contains all of its paths. When its paths are files directly in a package root, the area is `"<package> (top-level modules)"`, for example `cannalerts (top-level modules)`. Paths outside any package root use their top-level folder; files at the repository root use `(repository root)`. Implemented as `measured_graph.component_area(paths, roots) -> str`.
- **Edges.** Edges are unlabelled in diagrams (`a --> b`). Weight appears in the tables.
- **One diagram or several.** If the component graph has at most `MAX_NODES` nodes and `MAX_EDGES` edges, draw one flowchart `TB` with a subgraph per area. Otherwise draw: (1) **Areas**: one node per area, one edge per pair of areas with any import; (2) **one diagram per area**, titled `<area>`: the area's components inside a subgraph, plus one node per other area that its components import or are imported by, with edges to and from those area nodes. If an area diagram still exceeds the budget, it is drawn anyway at natural size (it scrolls). Every edge appears in exactly one diagram or is represented by its area edge, and every edge appears in the matrix or table, so nothing is dropped.
- **`components.map` table:** the existing per-component table (Component, Area, Files, Lines, Depends on, Used by), plus a **dependency matrix**: a `<table class="table dsm" data-nosort>` with one row and one column per component (same order, sorted by area then name), cell = number of imports from row to column, empty for none, sticky first column. Caption: "Rows import columns. The number is the count of import statements."
- **`interactions.graph`:** the same diagrams (one function serves both cards), a **component edge table** (From component, To component, Imports, Modules) sorted by Imports descending, and the module table with two new first columns, From component and To component, sorted by From component, then From, then To.

### D5. Tables (F1-8)

- Keep `render.render_table`. No new table component.
- `.table td, .table th`: `min-width: 6rem` (was 7.5rem); the Basis column (`td.basis-cell` and its header) and the Sources column get `min-width: 0; width: 1%` with `white-space: nowrap`. `.table code { overflow-wrap: anywhere; }`.
- Horizontal scroll stays inside `.table-container`. `dossier.js` adds class `scrolls` to a container whose `scrollWidth > clientWidth + 1` (on load, on report show and on resize); CSS draws a right-edge fade and a caption "Scroll sideways for more columns" above it.
- Long tables: a table with more than 40 body rows is wrapped in `.table-container.tall` (`max-height: 70vh; overflow: auto;` sticky `thead`). All rows stay in the DOM, so search, filter, sort and the V11 row count still see them. This is collapsing, not omission (principle 7).
- Target: at 1500 px, a schema table with at most 7 schema columns does not scroll.

### D6. Entries (F1-6)

`components.detail` and `conventions.recipes` stay `entries` (spec 05: "collapsible and searchable"; 11: "numbered recipes"). Each entry's body becomes a two-column table, `<table class="table kv" data-nosort><tbody>` with one `<tr><th scope="row">Label</th><td>value</td></tr>` per schema field, so it is a real table with or without the custom CSS. Values go through `md()`, so lines that start `1.`, `2.` become an `<ol>`. Because existing reports wrote numbered steps on one line, `render.split_steps(text)` first turns `"1. a 2. b 3. c"` into one line per step when the text starts with `1.` or `1)` and contains ` 2.` or ` 2)`. Question Q3 asks whether the author wants `components.detail` as one wide table instead.

### D7. The process card (F1-7, needs A1)

Table columns **No., Step, What happened, Status**. Step = `STEP_TEXT` (unchanged wording). What happened = the `run_line` text, except the `tools` step, which lists `Host: git 2.47.3, uv 0.11.19, node 20.19.2, npm 9.2.0. Extractors: grimp 3.17, vulture 2.16, semgrep 1.181.0, tree-sitter-language-pack 1.22.1, scip-python 0.6.6.` (extractor names and versions from the latest `extract` record's adapter tool lists, de-duplicated, in the order of `tools.json`), followed by `Skill: <commit>[, uncommitted changes][, UNMERGED]`. Status = a badge: ok (secondary), reused (outline), skipped (outline, with reason in What happened), failed (destructive), no record (destructive). The `check` row gets a second badge for the browser check: "browser: N problems" (secondary when 0, destructive otherwise) or "browser: not run" (destructive). The tier line follows the table as now. Drawn with `render_table(..., plain=True, sort=False)`.

### D8. Dispositions (F2-3, needs A5)

In `checks.v5`, for findings of the outputs `entry_points` and `models` (entity kinds, not `migration`):

- A group id in a `cand` list or a `dismissed` list is an error: `V5: <card title> decides the group <gid>; decide each <entry point|entity> on its own row: <ids>.` Group ids remain valid for `io_candidates`.
- In `data.entities`, a row's `cand` holds at most one `md-` id: `V5: Entities and types puts N entities in one row (<names>); give each its own row.`
- In `entry.catalog`, a row's `cand` may hold several `ep-` ids only when they share `path` (the same entry point found twice, plan 007 finding 1).
- **Fields complete:** for a `data.entities` row with one `md-` id, every field name of that item appears in the Fields cell (case-sensitive, as a whole word). Missing names: error `V5: Entities and types, <name>: the Fields cell leaves out <a, b, c>.`

### D9. The measured ER diagram (F2-2, needs A3)

`measured_er.py` (new, under 200 lines), `DRAWN["data.relationships"]`:

- Entities: every `models` item except `migration`, de-duplicated by `(path, name)`.
- Each entity block lists **every** field: `type name` (type sanitised to `[A-Za-z0-9_]`, unknown as `any`), with `PK` for a SQL primary key column and `FK` for a column with `ref`. Mermaid erDiagram attribute types cannot contain spaces or `|`; `str | None` becomes `str_or_None`, `Mapping[str, float]` becomes `Mapping_str_float`.
- Relations: a SQL column with `ref: T` gives `T ||--o{ Table : "column"`; a model field whose `ref` names another entity gives `Owner }o--|| Ref : "field"`.
- Split: with more than 12 entities, one diagram per owner component (`components.component_of(path, catalog)`), each including any entity from another component that a relation points to (drawn with its name and no fields, marked `"(in <component>)"` in the title line of the block as a comment), plus one diagram "SQL tables" when SQL tables exist. Without a catalog, split by area (D4).
- Under the diagrams: a table **Entity, Field, Type, Key, References, Defined in** with one row per field of every entity. This is the complete record; the diagrams are the picture.

### D10. Completeness checks in `render` (F3-1, needs A8)

`page_audit.py` (new, standard library `html.parser`, under 300 lines) parses the final HTML and returns errors. `cmd_render` runs it after `render_html` and before writing; errors block the write unless `--allow-errors`, and are counted on the `check/render` record as `v11`.

| Card shape | Asserted |
|---|---|
| `blocks` with table slots | For each table block in the report JSON: a `<table>` inside `[data-card=id]`; its last header row's cells start with exactly the schema columns, in order (then Basis and Sources for authored tables); `<tbody>` row count = JSON row count |
| `entries` | One `details.entry` per JSON entry; each holds a `table.kv` with one `th` per schema field label |
| `flows` | One `.diagram.flow` per diagram block; each followed (inside the card) by `.diagram-notes ol` with ≥ 2 `li` (when A7 is approved) |
| `na` | The "Not applicable" paragraph and a citation |
| measured: `reading.map` | 8 rows; `interactions.violations` rows = cycles + broken-contract violations + unchecked contracts; `components.map` table rows = catalog rows and matrix size = catalog rows squared; `interactions.graph` module table rows = import items and component table rows = component edges; `data.relationships` field table rows = sum of fields of all entities; `conventions.tooling` rows = tools found |
| computed: `dossier.questions` | rows = questions in `questions.json`; `dossier.process` rows = `len(buildlog.STEPS)` (A1) |
| page | Every `data-card` of every schema appears once; no text "Not yet generated" outside reports 10 and 13 |

### D11. The browser check (F3-2, needs A8)

`check_page.py` gains `check_layout(page, scheme, width)` run at 1500 × 1000 and 400 × 900 in both themes, on every report. Each assertion becomes one `FAIL` line naming report, card and element:

1. **Assets loaded:** `getComputedStyle(document.documentElement).getPropertyValue('--dossier-css-end').trim() === '1'` and `document.documentElement.dataset.dossierJs === 'ok'`. If either fails, report `the page's stylesheet (or script) did not load completely` and skip the rest of that theme.
2. **No sideways page scroll:** `document.documentElement.scrollWidth <= innerWidth`, and no visible element outside `.table-container, .mermaid-host, .year-scroll, .km-scroller, pre, .code-panel` with `getBoundingClientRect().right > innerWidth + 1`.
3. **Icons:** every visible `svg` whose `viewBox` is `0 0 24 24` renders at most 48 × 48 px.
4. **Diagram text:** every text element in every `.mermaid-host svg` has a rendered height of at least 11 px.
5. **Budgets** (D3): flowchart `g.node` count ≤ 12 per diagram except script-drawn area diagrams (marked `data-budget="area"` on the host), which are exempt and only reported as info; sequence `.actor` count ≤ 20 (two boxes per participant, so ≤ 10 participants); ER `.er.entityBox` (or the entity `g` groups) ≤ 12.
6. **Flow notes:** in `[data-card="interactions.flows"]` and `[data-card="entry.startup"]`, every `.diagram.flow` contains `.diagram-notes ol li` (≥ 2).
7. **Tables are tables:** every card whose schema has a table slot contains a `<table>` that is visible (width > 0) once its report is shown (tables in hidden panes of report 02 are exempt).
8. **No overlapping text:** within each card, no two visible leaf text boxes (`td, th, dt, dd, li, p, h3, h4, .badge, summary`, excluding ancestors of each other) intersect by more than 4 px².

Every sub-check runs inside `try`/`except Exception as e`, which adds `FAIL [scheme] <check>: could not run (<type>: <message>)` and continues, so a broken page reports instead of crashing.

### D12. The report 02 visual golden (F3-3)

`tests/tools/golden02.py` (PEP 723: `playwright`, `pillow`) screenshots the three report 02 cards (`#facts-git`, `#facts-contributors`, `#facts-dependencies`) at 1500 × 1000 in both themes, after injecting `.badge.tier, .question, .tier-key { display: none !important; }` (the same things `report_section.normalize` removes), and compares each with a baseline PNG. The comparison fails if more than 0.5% of pixels differ by more than 16 in any channel, or if the sizes differ. Baselines are made once by rendering `FIX` with the pre-M0 skill (commit `fc916d6`) in a temporary worktree, stored under `tests/fixtures/golden02/` (git-ignored, like `FIX`), with a `README.md` saying how to remake them. Commands in F3-3.

### D13. CLI commands (F2-5)

New semgrep rules in `rules/python/entry.yml`, kind `cli-command`:

- `dossier.python.entry.argparse-subcommand`: `$SUB.add_parser("$NAME", ...)` with a literal name; `name` = the literal.
- `dossier.python.entry.cli-helper-command`: a call `$F("$NAME", $HANDLER, ...)` where `metavariable-regex` `$HANDLER` matches `^(cmd|command|do|handle|run)_\w+$`; `name` = the literal, `target` = `$HANDLER`. This finds cannalerts' `add('init', cmd_init, …)`.
- A blind-spot rule `dossier.python.blindspot.computed-subcommand`: `$SUB.add_parser($X, ...)` where `$X` is not a string literal. It goes to Gaps (V7) as "CLI commands registered with a computed name".

### D14. V2 false positives (F2-11)

`checks._checked_span` also skips a span that (a) matches `render.BARE_FILE` (a file name with a known extension) or (b) equals a module's dotted name in `graph.json`, or is a suffix of one at a dot boundary (`alerts.state` matches `cannalerts.alerts.state`), or (c) is `<module>.<name>` where the module part matches (b) and `<name>` appears in the cited text. V2 stays a warning.

### D15. `dossier check` (F3-4)

`dossier check [repo]` runs `page_audit` on the page and then `uv run <SKILL>/scripts/check_page.py <html> --record <out>/build.json --shots <out>/.check-shots`, prints the combined result and exits non-zero on any problem. `SKILL.md` step 7 becomes "Run `DOSSIER check <repo>`; fix every FAIL; render; run it again until it prints `problems: 0`." `cmd_render`'s final JSON gains `"browser_check": "not run" | "N problems at <time>"` read from the latest browser record for the current SHA.

---

## Phase 1: Remediation in one session

The whole plan runs in **one session**, in three parts. Each part ends at a checkpoint where everything is committed and the suites pass; there is no stop for the author until the end. The author reviews the result in section 8.

### Before you start

1. Read section 2 (shared rules), section 3.3, section 3.4 and section 5 (decisions D1 to D15). Do not read plans 005 to 007 or the spec in full: this plan quotes what you need, with file and line references. Read code only around the lines a task names.
2. Load the skills listed in section 2.
3. Check that section 10 has the author's answers, and section 4 an approval or rejection for each of A1 to A9. **If any is missing, ask the author once, at the start, in a single question listing the missing items with the plan's recommendation for each, and continue with the answers.** Do not stop again later. A rejected amendment changes its tasks as its "If rejected" line says.
4. `git -C /home/nick/dev/projects/encamp log --oneline -5`; confirm `main` is at `2ed850b` or later (the commit that adds this plan and the `sync.sh` fix may follow it) and nothing from the task list is committed yet. Confirm `git -C ~/.local/share/encamp status --short` shows no `UU` line (resolved on 2026-11-01). Run the test suite and confirm the baseline (921 passed, 36 skipped).
5. Create `fix/dossier-m3-remediation` from `main`.

### Part A: Repair what the author sees

Read first: R1, R25, R4 to R7, R15 to R18, R20 and decisions D2 to D7.

- [x] **F1-1. Asset guard, sentinels and skill provenance (R1, R25; D2; A9).**
  - Files: `scripts/render.py` (`load_asset`, used in `render_html` lines 1735-1741), `assets/dossier.css` (last line), `assets/dossier.js` (last statement), `scripts/buildlog.py` (`skill_state`), `scripts/stages.py` or wherever the `tools` record is written (find it with `grep -n '"tools"' scripts/*.py`), `scripts/dossier.py` (`cmd_doctor`, `cmd_render`).
  - Tests first, in `tests/unit/scripts/test_render.py` and `test_buildlog.py`: (a) `render.load_asset` on a temporary file containing a line `<<<<<<< Updated upstream` raises `SystemExit` whose message names the file and line; (b) on the real `assets/dossier.css` and `assets/dossier.js` it returns the text; (c) the last non-blank line of `assets/dossier.css` is `:root { --dossier-css-end: 1; }` and of `assets/dossier.js` contains `dataset.dossierJs = "ok"`; (d) `skill_state` in a temporary git repo reports `dirty` after an edit and `unmerged` when `git status --porcelain` shows `UU` (create a real conflict: two branches editing one line, `git merge` with `check=False`).
  - Verify: `uv run --with pytest --with pygments python -m pytest tests/unit/scripts/test_render.py tests/unit/scripts/test_buildlog.py -q`; then block E (report 02 HTML) prints `OK`.
  - Commit: `fix(dossier): refuse to render assets with conflict markers and record the skill commit`.
- [x] **F1-2. The browser check reports instead of crashing, and checks that the assets loaded (R20, first part; D11 items 1 and the try/except).**
  - Files: `scripts/check_page.py`; new `tests/tools/broken_pages.py`; new `tests/integration/scripts/test_check_page_slow.py`.
  - `broken_pages.py`: `mutate(html: str, name: str) -> str` with named mutations, used by every later browser test: `conflict-css` (insert the three conflict lines after the first 40% of the `<style>` text), `no-js-sentinel` (remove the sentinel statement). Later tasks add mutations.
  - Test first (slow): render the pyrepo fixture page once per session (fixture `rendered_page` in the test module: copy `tests/fixtures/pyrepo` into a temporary git repo as the existing integration tests do, run `prepare` and `render --allow-errors` into `tmp_path`; if that proves too slow, reuse `FIX` with `migrate` and `render --allow-errors` as block E does). Then `check_page.py` on `mutate(page, "conflict-css")` exits 1 and prints a line containing `stylesheet` and does **not** print `Traceback`; on the unmutated page it exits 0.
  - Implement D11 item 1 and wrap every sub-check (`check_theme` per report, `check_viewer`, `check_knowledge`, `check_search`) in `try`/`except`.
  - Verify: `DOSSIER_SLOW=1 uv run --with pytest --with pygments python -m pytest tests/integration/scripts/test_check_page_slow.py -q`.
  - Commit: `fix(dossier): make the browser check report a page whose stylesheet did not load`.
- [x] **F1-3. Draw diagrams at their natural size (R4; D3).**
  - Files: `assets/dossier.js` (`initMermaid`, `drawIn`), `assets/dossier.css` (line 103 and the new `.scrolls` caption).
  - Test first (slow, in `test_check_page_slow.py`): add mutation-free test `test_diagram_text_is_readable` that opens a page whose report holds a 9-participant sequence diagram and a 16-node flowchart (add both to the pyrepo fixture's report JSON in the test's temporary copy, or render a minimal page through `render.render_html` with hand-built reports), and asserts every text element in every `.mermaid-host svg` is ≥ 11 px tall at 1500 and at 400 px. It must fail on the current code (4 px).
  - Change `useMaxWidth` to `false` for flowchart, er and sequence; CSS per D3; in `drawIn`, after `host.innerHTML = out.svg`, toggle `host.classList.toggle("scrolls", host.scrollWidth > host.clientWidth + 1)`.
  - Verify: the slow test passes; block E prints `OK` (report 02 has no Mermaid diagram, but the CSS file is shared).
  - Commit: `fix(dossier): draw diagrams at their natural size and let wide ones scroll`.
- [x] **F1-4. Group components by their real area (R6; D4 "Areas").**
  - Files: `scripts/measured_graph.py` (`component_area`, used by `_map` at line 132 and by F1-5).
  - Test first in `tests/unit/scripts/test_measured.py`: roots `["src/cannalerts"]`; `component_area(["src/cannalerts/cli.py", "src/cannalerts/__main__.py"], roots) == "cannalerts (top-level modules)"`; `(["src/cannalerts/platforms/dutchie/"], roots) == "platforms"`; `(["src/cannalerts/platforms/__init__.py", "src/cannalerts/platforms/base.py"], roots) == "platforms"`; `(["tests/"], roots) == "tests"`; `(["setup.py"], roots) == "(repository root)"`. And `_map` on a catalog with those rows gives an Area column without any `.py` value.
  - Verify: `pytest tests/unit/scripts/test_measured.py -q`.
  - Commit: `fix(dossier): group components by folder, not by their first file`.
- [x] **F1-5. Split the component graphs under a budget and add the matrix and edge tables (R5, R7; D3, D4; needs A2).**
  - Files: `scripts/measured_graph.py` (new `diagrams(edges, area) -> list[(title, mermaid)]`, `_matrix`, `_component_edge_table`; `_edge_table` gains component columns; `_flowchart` drops edge labels and takes a direction). If the module passes 300 lines, move the tables to `scripts/measured_tables.py` and say so in Results.
  - Tests first in `test_measured.py`: build a synthetic catalog of 16 components in 6 areas and 71 edges; assert (a) `diagrams` returns more than one diagram, each with ≤ 12 nodes and ≤ 30 edges except area diagrams marked over budget; (b) every component edge appears in an area diagram or is covered by an edge between the two areas in the overview; (c) no `-->|` in any source; (d) the matrix has 16 rows and 16 columns plus the header and its non-empty cells equal the 71 edges with their counts; (e) the component edge table has 71 rows sorted by Imports descending; (f) the module table has the same number of rows as import items and its first two headers are From component, To component. With 5 components and 6 edges, `diagrams` returns exactly one diagram. Each `_diagram` host carries `data-budget="area"` for the overview and per-area diagrams.
  - Verify: `pytest tests/unit/scripts/test_measured.py -q`; render a scratch copy of `LIVE` (section 7, block R) and open `#components` and `#interactions` in the browser with `--shots`; record the diagram count and node counts in Results.
  - Commit: `fix(dossier): split the component graphs into readable diagrams and add a dependency matrix`.
- [x] **F1-6. Entries as key/value tables with real lists (R15; D6).**
  - Files: `scripts/render.py` (`entries_body`, line 889; new `split_steps`), `assets/dossier.css` (`.table.kv th { width: 12rem; }`).
  - Tests first in `tests/unit/scripts/test_render_cards.py`: (a) an entry with fields `{"files_to_touch": "1. Add a `cmd_<name>` handler in `cli.py`. 2. Register it in `build_parser`. 3. Add tests.", "worked_example": "x"}` renders a `table.kv` with 2 rows and an `<ol>` with 3 `<li>`; (b) `split_steps("Use 2.5 ml")` returns the text unchanged; (c) the entry keeps `details.entry` and its `id`; (d) `check_search` in the slow suite still opens the entry (run the existing slow test).
  - Verify: `pytest tests/unit/scripts/test_render_cards.py -q` and the slow test file.
  - Commit: `fix(dossier): draw component details and recipes as tables with numbered steps`.
- [x] **F1-7. The process card as a table, with extractor versions and the browser status (R17, R18; D7; table part needs A1).**
  - Files: `scripts/process.py` (`process_body`, `_ok_line` for `tools` and `check`), `scripts/render.py` (call site line 1609 if the signature changes).
  - Tests first in `tests/unit/scripts/test_process.py`: with a build record whose `extract` record lists adapter tools `grimp 3.17` and `scip-python 0.6.6` (follow the shape in `LIVE/build.json`), the `tools` row text contains `Extractors: grimp 3.17` and `scip-python 0.6.6`; with no browser record the `check` row shows a destructive badge "browser: not run"; (A1) the body contains one `<table>` with headers `No., Step, What happened, Status` and `len(buildlog.STEPS)` body rows; a skipped step shows the badge `skipped`.
  - Verify: `pytest tests/unit/scripts/test_process.py -q`.
  - Commit: `feat(dossier): show how the dossier was made as a table, with extractor versions`.
- [x] **F1-8. Tables fit the card at desktop width and say when they scroll (R16; D5).**
  - Files: `assets/dossier.css` (line 90 and new rules), `assets/dossier.js` (scroll marking), `scripts/render.py` (`render_table`: add `tall` class when `len(rows) > 40`).
  - Test first (slow): a page with a 7-column authored table whose cells hold long multi-path code (`` `src/a/b/c.py`, `src/a/b/d.py` ``) has `scrollWidth <= clientWidth` in its `.table-container` at 1500 px; a 9-column table at 400 px gets class `scrolls`. Unit: `render_table` with 41 rows outputs `table-container tall`.
  - **Report 02:** these CSS rules apply to its tables too. Run block E (HTML) after the change; the visual golden does not exist yet, so take before-and-after screenshots of `#facts-contributors` and `#facts-dependencies` with `check_page.py --shots` and compare by eye; if anything in report 02 moves, scope the new rules to `.findings .table` and `.card[data-card]:not([data-card^="overview."]) .table`, and record which.
  - Verify: slow test, unit test, block E `OK`.
  - Commit: `fix(dossier): keep schema tables inside their card and mark the ones that scroll`.

**Checkpoint A.** Full suite and slow suite pass; block E prints `OK`; block R (section 7) renders a scratch copy of `LIVE` with no conflict markers, `check_page.py` exits 0 without a traceback, and the F1-3 measurement gives ≥ 11 px text in every diagram on that page. Write the page path, diagram counts and text sizes under "Results". Continue to Part B.

### Part B: Nothing dropped

Read first: R2, R3, R8 to R14, R19, section 3.4 and decisions D8, D9, D13, D14.

- [x] **F2-1. SQL columns: strip comments, record relations (R3).**
  - Files: `scripts/repo_adapter.py` (`_columns` line 88, `sql_tables` line 111).
  - Test first in `tests/unit/scripts/test_repo_adapter.py`: the text of cannalerts' `scrapes` table (copy the 14 lines into the test, with the two `--` comments) gives 13 fields named `id, run_id, shop, site, store, menu, platform, status, expected_count, product_count, errors, started_at, finished_at`, no field named `--`; a table with `run_id INTEGER REFERENCES runs(id)` and a table-level `FOREIGN KEY (a) REFERENCES t(b)` gives `relations == [{"field": "run_id", "to": "runs", "kind": "fk"}, {"field": "a", "to": "t", "kind": "fk"}]`; `PRIMARY KEY (x, y)` marks fields `x` and `y` with `"pk": true`.
  - Implement: remove `--[^\n]*` and `/* … */` from the body before splitting (keep newlines so line numbers hold); read table-level `PRIMARY KEY` and `FOREIGN KEY` constraints; set `relations` on every `sql-table` item.
  - Note: changing extractor output changes ids for `repo` items whose snippet changes (it does not: the snippet is the `CREATE TABLE` line) and makes `data` stale on the next incremental build, as D10 of plan 007 intends.
  - Verify: `pytest tests/unit/scripts/test_repo_adapter.py -q`.
  - Commit: `fix(dossier): read SQL columns after comments and record foreign keys`.
- [x] **F2-2. Draw `data.relationships` from the extracted models (R2; D9; needs A3).**
  - Files: new `scripts/measured_er.py`; `scripts/measured.py` (`DRAWN`); `prompts/schema/data.json` (`data.relationships`: `writer: "script"`, `shape: "computed"`, remove `slots`); `scripts/schema.py` (a written entry for a card listed in `schema.NOW_DRAWN = {"data.relationships"}` is a **warning** "drawn by code since 0.7.1; the entry is ignored", not the V6 error of plan 007 deviation 7); `prompts/reports.md` (the card becomes "Do not write this card", as for the other script cards, which `test_prompts.py` checks).
  - Tests first in new `tests/unit/scripts/test_measured_er.py`: with the four cannalerts tables (after F2-1) and the `Product` dataclass item (copy from `LIVE/extract/models.json`), the output holds every one of the 46 + 19 fields in the field table and in the diagram source; `runs ||--o{ scrapes` and `scrapes ||--o{ products` are present; with 52 entities and a catalog, there is one diagram per owner component plus "SQL tables", each with ≤ 12 entities except over-budget ones marked; types with spaces or `|` are sanitised and Mermaid accepts the source (validate in the slow suite by rendering the card and asserting no `.failed` host).
  - Verify: unit and slow tests; `test_schema_files.py` and `test_prompts.py` pass after updating their expectations for this card only.
  - Commit: `feat(dossier): draw the relationships card from the extracted models with every field`.
- [x] **F2-3. One row per entity and per entry point, with every field (R9, R10; D8; needs A5).**
  - Files: `scripts/checks.py` (`v5`, line 48 on), `scripts/candidates.py` (helper `entity_items(extract)`), `prompts/method.md` (section "Tool findings: keep, merge, dismiss", lines 211-235, and its example).
  - Tests first in `tests/unit/scripts/test_checks_v5.py`: (a) a `data.entities` row with `cand: ["mdg-…"]` is an error naming each member; (b) a row with two `md-` ids is an error; (c) a row with one `md-` id whose Fields cell omits a field is an error listing it; (d) an `entry.catalog` row holding two `ep-` ids with the same `path` passes, with different paths fails; (e) an `io.inputs` row with an `iog-` group id still passes. Run them against `LIVE/reports/data.json` (copied) to show they now fail with 25 or more errors; record the count in the commit body.
  - Verify: `pytest tests/unit/scripts/test_checks_v5.py -q`.
  - Commit: `fix(dossier): require one row per entity and entry point, with every field`.
- [x] **F2-4. Every gathered environment variable reaches Inputs; lift the env-var caps (R13).**
  - Files: `scripts/checks.py` (new `v5_env(reports, facts)`: every name in `facts["env_vars"]` appears in a cell of `io.inputs`, else error `V5: Inputs does not list the environment variable NAME (found in [[path:line]]).`), `scripts/gather.py:902` and `:1186` (remove `[:60]` and `[:300]`).
  - Tests first: `test_checks_v5.py` with facts `CANNALERTS_SKIP_AYR` and an `io.inputs` table without it gives the error; `test_gather.py` with 70 env reads in one file returns 70 names.
  - Block E must print `OK` (report 02 does not draw env vars).
  - Commit: `fix(dossier): require every environment variable in Inputs and stop capping them`.
- [x] **F2-5. Find argparse and helper-registered CLI commands (R10; D13).**
  - Files: `rules/python/entry.yml`, `rules/python/blindspot.yml`, `tests/fixtures/semgrep/python/entry.py` and `blindspot.py` (annotated targets), `scripts/py_adapter.py` if the `cli-command` kind needs the `target` from `$HANDLER`.
  - Tests first: semgrep rule tests (`tests/unit/scripts/test_rules.py` runs `semgrep --test`, slow): `commands.add_parser("serve")` → `ruleid: dossier.python.entry.argparse-subcommand`; `add('init', cmd_init, 'write an example config file')` → `ruleid: dossier.python.entry.cli-helper-command`; `add(name, handler, help)` inside the helper → `ok`; `commands.add_parser(name, help=help)` → `ruleid: dossier.python.blindspot.computed-subcommand`. Slow integration: the Python adapter on the pyrepo fixture after adding one argparse sub-command to it finds the `cli-command` item.
  - Verify: `DOSSIER_SLOW=1 … pytest tests/unit/scripts/test_rules.py tests/integration/scripts/test_py_adapter_slow.py -q`.
  - Commit: `feat(dossier): find argparse sub-commands as entry points`.
- [x] **F2-6. Draw the measured columns of the component catalog (R11; needs A4).**
  - Files: `scripts/render.py` (`render_card`: for `components.catalog`, replace the cells of Depends on, Used by and Size in each row with the measured values from `components.catalog_edges` and `components.file_lines` before `render_table`), `prompts/reports.md` (catalog paragraph: write `-` in those three cells).
  - Tests first in `test_render_cards.py`: a catalog row whose Depends on says "every other component" renders the measured, comma-separated list; Size renders `N lines` from `file_lines`.
  - Commit: `fix(dossier): draw the measured columns of the component catalog`.
- [x] **F2-7. Show every module for the reading order (R12).**
  - Files: `scripts/candidates.py:266` (remove `[:30]`), `:298` (heading "Modules by import rank").
  - Test first in `test_candidates.py`: a graph with 40 modules gives 40 in `report_data("reading", …)["modules"]`.
  - Commit: `fix(dossier): list every module for the reading order`.
- [x] **F2-8. Numbered notes after every flow (R8; needs A7).**
  - Files: `scripts/schema.py` (`_check_flows`, line 128: every diagram must be followed by a `list` block with ≥ 2 items, or a `text` block whose non-empty lines all match `^\s*\d+[.)] ` and number ≥ 2; error `V6: <card>: diagram N needs numbered notes after it`), `prompts/reports.md:83` ("each followed by numbered notes, one per step of the diagram").
  - Tests first in `tests/unit/scripts/test_schema.py`: the onboarding blocks from `LIVE/reports/interactions.json` (a diagram then a one-paragraph text) give the error; the run flow's blocks pass; a list block passes.
  - Commit: `fix(dossier): require numbered notes after every flow diagram`.
- [x] **F2-9. Prompts: complete, not short (R9, R10, R12, R14; section 3.4).**
  - Files: `prompts/method.md`, `prompts/reports.md`.
  - Changes (exact): `method.md:3` "write short reports" → "write complete reports: every item a tool found or you found gets its own row; size never limits content"; `reports.md:9` → "A report is as long as its content. Never merge items to shorten a table; the page sorts, filters and collapses long tables."; `method.md:222` merge by group → allowed only for call-site findings (`io-` ids), with A5's wording; `method.md:408` → "A sequence diagram has at most 10 participants and a flowchart at most 12 nodes. When a flow needs more, split it into several diagrams, each with its own numbered notes; never leave a step out."; `entry.catalog` paragraph: "one row per CLI command (mark `added: true` when no tool found it)"; `io.inputs`: "one row per CLI command's arguments and one row per environment variable"; `data.entities`: "one row per entity; Fields lists every field by name"; recipes: "Files to touch: one step per line, `1. path — change`. Worked example: cite the commit that did the same thing (`[[commit:<sha>]]`), found with `git log --follow -p` or `git log -S`; when no commit did, the statement is `unknown` with a note"; flows: numbered notes (F2-8).
  - Tests: `tests/unit/scripts/test_prompts.py` gains assertions that none of "short report", "smallest report", "6 to 10 nodes" appear and that the examples in `method.md` still validate (they must now have one `md-` id per entity row and numbered flow notes).
  - Commit: `docs(dossier): ask for complete reports and one row per item`.
- [x] **F2-10. Recipes cite commits (R14).**
  - Files: `scripts/checks.py` (warning `V2: Recipes, <recipe>: the worked example cites no commit` when a recipe's `worked_example` has no `commit:` citation and its `conf` is `confirmed` or `inferred`; goes to Gaps as an `inference` item).
  - Test first in `test_checks_v2.py`.
  - Commit: `feat(dossier): flag recipes that are not grounded in a commit`.
- [x] **F2-11. V2 stops flagging file and module names (R19; D14).**
  - Files: `scripts/checks.py` (`_checked_span`, line 221; `v2` passes the module names from `extract["graph"]`).
  - Test first in `test_checks_v2.py`: spans `cli.py`, `models.py`, `alerts.state`, `menus.scrape_cached` (with `scrape_cached` in the cited text) give no warning; `FetchClient` absent from the cited text still warns. Run `checks.validate` on a scratch copy of `LIVE` and record the V2 count before (35) and after in the commit body.
  - Commit: `fix(dossier): stop V2 from flagging file and module names`.

**Checkpoint B.** Full suite and slow suite pass; block E prints `OK`. Block R with `--allow-errors` lists the new V5 and V6 errors for the old reports (at least the 27 folded entities, the missing `CANNALERTS_SKIP_AYR` and the onboarding notes), and the relationships card shows all 46 SQL columns and the dataclass entities. Record the error lines by kind and count under "Results". Continue to Part C.

### Part C: Verification that fails on these defects

Read first: R20 to R25, section 3.6 and decisions D10, D11, D12, D15. Also load `docs-project`, `docs-readme`, `docs-user-guide`, `docs-dev-guide` and `git-release` now.

- [x] **F3-1. Page completeness audit in `render` (V11; R21; D10; needs A8).**
  - Files: new `scripts/page_audit.py`; `scripts/dossier.py` (`cmd_render` after `render.render_html`: run `page_audit.audit(page, reports, extract, facts, build)`; count `v11` on the `check/render` record; errors block writing unless `--allow-errors`); `scripts/process.py` (the `check` line says `Page: N problems.`).
  - Tests first in new `tests/unit/scripts/test_page_audit.py`, each against a page built by `render.render_html` from small hand-made reports and then mutated with new `broken_pages.py` mutations: `drop-row` (remove the last `<tr>` of the first schema table's body) → error naming the card and "N rows, expected N+1"; `drop-column` (remove the second `<th>` and every second `<td>`) → error naming the missing column; `table-as-text` (replace the first schema table with its text) → "has no table"; `entry-no-kv` (replace an entry's `table.kv` with a `<dl>`) → error; `drop-entry`; `drop-er-field` (remove one row of the ER field table) → error; the unmutated page → no error.
  - Verify: `pytest tests/unit/scripts/test_page_audit.py -q`; block R on a scratch copy of `LIVE` (old reports, `--allow-errors`): record the V11 count (expected 0 for drawing errors; the content errors are V5 and V6).
  - Commit: `feat(dossier): check that the page draws every row, column and entry (V11)`.
- [x] **F3-2. Layout and readability in the browser (V12; R20; D11 items 2 to 8; needs A8).**
  - Files: `scripts/check_page.py` (`check_layout`; run at both widths); `tests/tools/broken_pages.py` (mutations `wide-element` (insert a 2000 px wide `div` in a card), `icon-unsized` (add `svg.lucide-test { width: auto !important; height: auto !important }` and an icon), `tiny-diagram` (add a 60-node flowchart to a Claude card), `flow-no-notes` (remove a `.diagram-notes`), `overlap` (absolutely position a `<p>` over a `td`), `table-hidden` (`display:none` on a schema table)); `tests/integration/scripts/test_check_page_slow.py` (one test per mutation: exit 1 and one FAIL line naming the right check; the unmutated page passes).
  - Also: the module docstring of `check_page.py` lists every check (it is what SKILL.md quotes).
  - Verify: `DOSSIER_SLOW=1 … pytest tests/integration/scripts/test_check_page_slow.py -q`; then `check_page.py` on the author's original page (copy `LIVE/dossier-cannalerts.html` to scratch) exits 1 with the stylesheet line and no traceback; record the output in Results.
  - Commit: `feat(dossier): check page layout and diagram readability in the browser (V12)`.
- [x] **F3-3. Report 02 visual golden (R22; D12).**
  - Files: new `tests/tools/golden02.py`; new `tests/fixtures/golden02/README.md`; `.gitignore` entry for `tests/fixtures/golden02/*.png`; new slow test `tests/integration/scripts/test_golden02_slow.py` (skips with a clear reason when the baselines are absent).
  - Make the baselines once: `git -C /home/nick/dev/projects/encamp worktree add --detach $SCR/wt-pre fc916d6`; copy `FIX` to `$SCR/pre/home/encamp`; in the worktree's skill folder run `DOSSIER_HOME=$SCR/pre/home python3 scripts/dossier.py render /home/nick/dev/projects/encamp --allow-errors` (the fixture is in the pre-M0 layout already, so no `migrate`); run `golden02.py --write-baseline $SCR/pre/home/encamp/dossier-encamp.html tests/fixtures/golden02/`; remove the worktree with `git worktree remove --force`. Record the commands in the README.
  - Tests: the current render of `FIX` (block E's page) matches; `mutate(page, "conflict-css")` does not; a page with one CSS rule of report 02 changed (`.km-row { height: 40px }` appended) does not.
  - Add block G2 (section 7) to every later report 02 guard.
  - Commit: `test(dossier): compare report 02 with a pre-M0 screenshot golden`.
- [x] **F3-4. `dossier check` and a browser check that cannot be skipped silently (R23; D15).**
  - Files: `scripts/dossier.py` (`cmd_check`, the `check` parser, `cmd_render`'s final JSON), `SKILL.md` (build step 7, and the commands list), `scripts/process.py` (F1-7's browser badge already shows "not run").
  - Tests: `tests/unit/scripts/test_dossier_check.py` with `check_page` stubbed (monkeypatch the subprocess call) for exit codes and the combined output; `cmd_render` JSON contains `"browser_check": "not run"` on a fresh build.
  - Commit: `feat(dossier): add dossier check, which runs the page audit and the browser check`.
- [ ] **F3-5. Docs and version 0.7.1.**
  - Files: `SKILL.md`, `README.md`, `docs/user-guide.md` and `docs/developer-guide.md` if they exist (follow the docs skills; if absent, do not create them in this plan), `VERSION` (0.7.1), the changelog if the repository keeps one (check `git-release`).
  - Document: `dossier check`, V11 and V12, the skill commit on the process card, `doctor`'s unmerged check, the measured relationships card, the one-row-per-item rules, the golden02 baselines.
  - Commit: `chore(dossier): bump to 0.7.1` and a `docs(dossier): …` commit before it.
- [ ] **F3-6. Final run on the author's data, and the hand-over.**
  - Section 7: blocks R (a fresh scratch copy of `LIVE`, rendered with `--allow-errors`), A, B, C, I, E and G2, in that order. Then run `$D check $REPO` on the block R page.
  - Record in "Verification results" below: each block's key output; the `render` error lines by kind and count (the old reports must now fail V5 and V6 for the 27 folded entities, the missing `CANNALERTS_SKIP_AYR`, the onboarding notes; V11 must report 0 drawing errors); `dossier check` output (V12: 0 layout and readability failures; content-driven failures, if any, listed); section 3.4's counts for everything code draws (relationships, both graphs, reading feed), which must show 0 lost.
  - Do **not** write the dossier's reports again: the author's acceptance build (section 8) does that with `/dossier build`, using the merged code and the rewritten prompts.

### Deliverables and checks

| Deliverable | Checked by |
|---|---|
| Conflict-marker guard, sentinels, skill state | F1-1 tests; block E |
| Browser check survives a broken page | F1-2 slow test |
| Readable diagrams, split graphs, matrix | F1-3, F1-5 tests; block R |
| Entries and process card as tables; tables fit | F1-6, F1-7, F1-8 tests |
| Correct SQL extraction; measured ER card with every field | F2-1, F2-2 tests |
| Per-item rows, complete fields, env vars, CLI commands | F2-3, F2-4, F2-5 tests; checkpoint B errors |
| Measured catalog columns, all modules, numbered notes, prompts | F2-6 to F2-9 tests |
| V11 page audit, V12 browser checks | F3-1, F3-2 tests against broken pages; the author's original page fails clearly |
| Report 02 visual golden | F3-3; block G2 |
| `dossier check`; docs; 0.7.1 | F3-4, F3-5 |

### Keeping it to one session

- **Order is priority.** Do the tasks in the order written. The first 13 (F1-1 to F2-5) fix what the author saw and what was dropped; do not start Part C before checkpoint B.
- **Context.** Keep tool output short: run single test files while working (`-q`, `--no-header`, `-x`), and the full and slow suites only at checkpoints. Pipe long command output through `tail` or `grep`. Never print a whole page, a whole `extract/*.json` or a report file; query them with `python3 -c` and print counts.
- **Browser tests** share one rendered page per test module (a module-scoped fixture) and `tests/tools/broken_pages.py` mutations; never render a page per test.
- **Cut line**, only if the session cannot finish: cut F2-10, then F2-11, then F1-8's `tall` wrapper, then F3-5's docs (keep the version bump). Never cut F1-1 to F1-7, F2-1 to F2-9, or F3-1 to F3-4. Record any cut under "Results" with the reason; it becomes the first item of the next plan.

### Acceptance criteria

- Full and slow suites pass; blocks E and G2 pass.
- Checkpoints A and B were met, and F3-6 is recorded.
- Every defect R1 to R25 is marked fixed in section 3.3 with the commit that fixed it, or listed as open with the reason (a cut, or an amendment the author rejected).
- The branch is merged (below), so the author's acceptance (section 8) can run.

### Branch and release

Commit each task on `fix/dossier-m3-remediation`. After F3-6, follow `git-workflow` to merge it into `main` with a merge commit, and push only if that skill says so. Follow `git-release` for the version. Tell the author to run `encamp-sync pull` (or however `INSTALLED` is updated) before section 8.

### Results

Session of 2026-11-01, by Sonnet 5.5, on branch `fix/dossier-m3-remediation`. The author approved A1 to A9 and chose the plan's option for Q3, Q4 and Q6.

**Checkpoint A (F1-1 to F1-8).**

- Tests: 974 passed, 43 skipped (default); 1017 passed with `DOSSIER_SLOW=1` (172 s). Block E: `OK`.
- Block R (a scratch copy of `LIVE` rendered with the branch's code): 0 conflict markers; `check_page.py` exit 0, 21 diagrams checked, 0 problems. Page: `$SCRATCH/R/home/cannalerts/dossier-cannalerts.html` (scratchpad of this session, not kept).
- Diagrams on that page: `components.map` 9 (an overview of 8 areas and one diagram per area; nodes per diagram 8, 5, 13, 6, 3, 7, 4, 4, 2), `interactions.graph` 8 (the same without the isolated nodes), `entry.startup` 1, `interactions.flows` 2, `data.relationships` 1. The smallest text in any diagram, at 1500 and at 400 px, is 19 px (was 1 to 6 px). The "cannalerts (top-level modules)" area diagram has 13 nodes and 46 edges: over the budget, drawn at natural size and scrolling, as D4 allows.
- Tables on that page: 42 schema tables; 0 scroll sideways at 1500 px (3 did before the Basis fix: the dependency matrix, `data.lifecycle`, `risks.tracker`); 40 scroll inside their card at 400 px, each with the hint line; 3 are `tall` (more than 40 rows).

**Deviations in Part A.**

1. F1-2: the module-scoped `rendered_page` fixture renders the frozen `FIX` fixture (the block E route), not pyrepo, which needs `prepare` and every extractor. The slow tests skip when `FIX` is absent.
2. F1-3 and F1-8 measure through two small PEP 723 scripts, `tests/tools/diagram_text.py` and `tests/tools/table_fit.py`, because the pytest environment has no Playwright. The plan's `check_page.py` check for diagram text size (D11 item 4) is still F3-2.
3. F1-5: the tables moved to a new `scripts/measured_tables.py` (the plan allowed it). The matrix note reads "Each number is how many imports connect the two (one per importing file and imported file)", because the counts are import items, not statements (plan 007 deviation 5). `render_table` gained a `cls` parameter.
4. F1-8: the new table rules and the script's marking apply to schema cards only (`.card[data-card]:not([data-card^="overview."])`), so report 02 is unchanged by construction rather than by comparison; no before and after screenshots were needed, and F3-3 will confirm. The Basis column is capped at 14rem and wraps (the plan said nowrap, which made note text 592 px wide).
5. F1-7: extractor names come from the `extract` record's adapter tool lists (status ok only), versions from that record's `tools` list, ordered as in `tools.json`.
6. Incident: while checking that the F1-7 tests fail on the old code I ran `git stash push` on an unmodified file and then `git stash pop`, which popped an older stash of the author's (`stash@{0}: WIP on main: fe956ae`, touching `scripts/lib/install_app.sh`) and conflicted. I restored that one file to `HEAD`; the stash entry is intact and nothing else was touched. I use `git show HEAD:` and the test failures themselves from now on.

**Checkpoint B (F2-1 to F2-11).**

- Tests: 1070 passed, 45 skipped (default); 1115 passed with `DOSSIER_SLOW=1` (176 s). Block E: `OK`.
- Block R on the author's data after `prepare --no-restore` re-extracted the scratch copy (42 s): 52 entities, the four SQL tables with 4, 13, 20 and 9 fields and 2 foreign keys, 19 entry points of which 13 are `cli-command` (9 registered through the `add(...)` helper, `watch add`, and 3 argparse commands of `scripts/capture_fixtures.py`), 1 `computed-subcommand` blind spot.
- Relationships card: 13 diagrams (12 components and "SQL tables"), 71 entities, 51 relations, and a field table of 266 rows, equal to the 266 fields extracted (46 of them SQL columns). `check_page.py` on that page: exit 0, 33 diagrams, 0 problems.
- Errors the old reports now fail with (`render --allow-errors`): 31 V5 "decides the group" (the folded entities and entry points), 1 V5 "does not list the environment variable CANNALERTS_SKIP_AYR", 1 V5 "13 tool findings for Entry points have no decision" (the new commands), 1 V6 "diagram 2 needs numbered notes after it" (onboarding); 1 V6 warning that `data.relationships` is now drawn by code. V2 name warnings: 35 before F2-11, 25 after; plus 6 new recipe warnings (none cites a commit).

**Deviations in Part B.**

7. The `repo` and `python` adapters are now version "2". Their output changed (SQL columns and relations, CLI commands), and an adapter's `version` is part of the extract cache key; without the bump `prepare` reused the old extract (2.5 s instead of 42 s) and an existing dossier would never have seen the fixes.
8. F2-2: the M0 migration rule that carried an old ER diagram into `data.relationships` was removed from `migrate_map.json`, so `migrate` reports it as not carried (the plan did not mention it; `test_shipped_map_is_consistent` requires every target to be a Claude-written card).
9. F2-8: `schema.validate` takes `strict_notes` (default true); `migrate` passes false so it still carries older flow notes as written, and `render` then asks for numbered notes.
10. F2-3 treats "the same entry point" as the same file and the same name, as A5 says (D8 says only the same file).
11. F2-4 counts the missing variables as `v5_env` on the check record.

### Verification results

(F3-6 writes here.)

---

## 6. Session and checkpoints

| Part | Fixes | Checkpoint |
|---|---|---|
| A Repair what the author sees | R1, R25, R4 to R7, R15 to R18, R20 (part) | Suites green; block R page has readable diagrams and no conflict markers |
| B Nothing dropped | R2, R3, R8 to R14, R19 | Suites green; block R lists the errors the old reports now fail with |
| C Verification | R20 to R24 | Suites green; F3-6 recorded; branch merged |
| Author | all | Section 8: a full `/dossier build` with the merged code |

---

## 7. Verification blocks

Set once per shell:

```bash
SKILL=/home/nick/dev/projects/encamp/configs/user/claude/.claude/skills/dossier
REPO=/home/nick/dev/projects/cannalerts
LIVE=/home/nick/dev/dossiers/cannalerts
FIX=$SKILL/tests/fixtures/encamp-m0
SCR=$(mktemp -d)
export DOSSIER_HOME=$SCR/home DOSSIER_CONFIG=$SCR/cfg.json DOSSIER_CACHE=$SCR/cache PYTHONDONTWRITEBYTECODE=1
BASE=fe72cec488cb211edd6919154bf4d3ed68845e4e33b667a1874716a96bb63b59
D="uv run $SKILL/scripts/dossier.py"
OUT=$DOSSIER_HOME/cannalerts
cd $SKILL
git -C $REPO status --porcelain > $SCR/repo-status-before
```

**Block R: render the author's data with the branch's code** (checkpoints A and B, and F3-6).

```bash
mkdir -p $SCR/home && cp -r $LIVE $SCR/home/cannalerts && chmod -R u+w $SCR/home/cannalerts
$D render $REPO --allow-errors > $SCR/r.log; echo "render exit $?"
grep -E '^(error|warning|info):' $SCR/r.log | sed -E 's/^(error|warning|info): (V[0-9]+).*/\1 \2/' | sort | uniq -c
grep -c '^<<<<<<<\|^>>>>>>>' $OUT/dossier-cannalerts.html   # expect 0
uv run scripts/check_page.py $OUT/dossier-cannalerts.html --shots $SCR/shots; echo "check exit $?"
```

**Block A: `doctor`.** `$D doctor $REPO; echo "exit $?"`. Expect the M2 tool list, plus `skill: <commit> (clean)`; exit 0.

**Block B: `prepare`.** `$D prepare $REPO --ref main --restore yes > $SCR/p1.json; echo "exit $?"`. Expect exit 0, adapters `python ok` and `repo ok`, the `tools` record holding `details.skill` with the branch's commit and `dirty: false`. Record the `models` count and confirm the four SQL tables have 4, 13, 20 and 9 fields and two relations.

**Block C: candidates.** `$D candidates $REPO --report entry` lists the ten CLI commands (F2-5) besides the M2 items. `$D candidates $REPO --report reading` lists 55 modules.

**Block D: write the reports.** As Claude, follow SKILL.md `/dossier build` steps 2 to 5 for `REPO` with `DOSSIER` = `$D`, writing reports 03 to 09, 11, 12, `overview`, `risks` and `gaps` into `$OUT/reports/` from the rewritten prompts. Do not write `change` or `contributors`. Then `for r in entry components interactions io data behavior conventions ops reading; do $D candidates $REPO --report $r --open; done` prints nothing.

**Block F: render and the checks.** `$D render $REPO > $SCR/r1.log; echo "render exit $?"`, then the `grep … | uniq -c` line from block R. Expect exit 0, no `error:` lines. Fix the reports and render again until clean; count the rounds.

**Block G: `dossier check`.** `$D check $REPO; echo "exit $?"`. Expect `problems: 0` and exit 0; then `$D render $REPO` once more so the process card shows the check. Open with the Read tool the screenshots of reports 01, 05, 06, 08 and 11 at both widths from `$OUT/.check-shots`.

**Block G2: report 02 visual golden.** `DOSSIER_SLOW=1 uv run --with pytest --with pygments python -m pytest tests/integration/scripts/test_golden02_slow.py -q` passes.

**Block H: counts against sources.**

```bash
python3 - "$OUT" <<'PY'
import json, re, sys, html, pathlib
out = pathlib.Path(sys.argv[1]); h = (out / "dossier-cannalerts.html").read_text()
models = [i for a in json.load(open(out / "extract/models.json"))["adapters"].values() for i in a["items"] if i.get("kind") != "migration"]
print("entities", len(models), "fields", sum(len(m.get("fields") or []) for m in models))
def rows(cid):
    m = re.search(r'data-card="%s".*?<tbody>(.*?)</tbody>' % re.escape(cid), h, re.S)
    return m.group(1).count("<tr") if m else None
for cid in ("data.entities", "entry.catalog", "io.inputs", "reading.order"):
    print(cid, rows(cid))
PY
```

Expect `data.entities` rows = entities; the relationships field table (V11 already asserts it) = fields; `entry.catalog` ≥ 16 (6 M2 items, 10 commands); `io.inputs` names every env var in `facts.json`.

**Block I: the full suite.** `uv run --with pytest --with pygments python -m pytest tests -q` and `DOSSIER_SLOW=1 …` (record counts and time).

**Block E: report 02 HTML unchanged.** As in plan 007 section 6 block E, verbatim (uses `FIX`, `migrate`, `render --allow-errors`, `report_section.py … --digest --normalize`; expect `OK`).

**Order in F3-6:** R, A, B, C, I, E, G2, then `$D check $REPO` on the block R page. Finally `diff <(git -C $REPO status --porcelain) $SCR/repo-status-before` prints nothing.

**Blocks D, F, G and H are the author's acceptance build** (section 8): `/dossier build` writes the reports, renders and runs `dossier check`. They are kept here so the author, or a later session asked to, can run them by hand.

---

## 8. Acceptance: the author's procedure

**Before:** run `encamp-sync pull` so `INSTALLED` is at the merged `main` (`git -C ~/.local/share/encamp status --short` shows no `UU` line). Then `/dossier doctor` must print `skill: <commit> (clean)` with the merge commit of this plan. (If the pull stops with "local edits … conflict with upstream", that is the new `sync.sh` protecting the live files: read the message, drop the stash it names once you have moved anything you need, and pull again.)

**Build:** `/dossier build ~/dev/projects/cannalerts` (a full build, so every report is rewritten under the new prompts). It ends with `dossier check` printing `problems: 0`.

**Open** `~/dev/dossiers/cannalerts/dossier-cannalerts.html` in your browser at full width, then at phone width (or the browser's device mode at 400 px), in light and dark.

**Look at, in order** (defect ids in brackets):

1. Report 01, *How this dossier was made*: a table of 10 steps with status badges; the tools row names grimp, vulture, semgrep, tree-sitter and scip-python with versions; the check row says "browser: 0 problems"; the skill commit is the merge commit. [R1, R25, R17, R18, R23]
2. Report 02, *Contributors* and *Dependencies*: they look exactly as before M0 (calendar grid, knowledge-map tree, dependency views, small icons). [R1, R22]
3. Report 03, *Reading order*: steps cover the modules you would read, not only the most imported 30. [R12]
4. Report 04, *Entry points*: one row per CLI command (all ten), plus the console script, `python -m`, the scripts and CI. [R10]
5. Report 05, *Component map*: an Areas diagram and one diagram per area, all with text you can read without zooming; Area column shows folders; a dependency matrix with counts. *Component catalog*: Depends on, Used by and Size are lists and counts, not prose, and the table fits the card. *Component details*: each entry is a two-column table; nothing runs together. [R4, R5, R6, R11, R15, R16]
6. Report 06, *Dependency graph*: readable diagrams; a component edge table sorted by imports; the module table has component columns. *Key flows*: every flow has numbered notes under it. [R4, R5, R7, R8]
7. Report 07, *Inputs*: one row per command's arguments and one per environment variable, including `CANNALERTS_SKIP_AYR`. [R10, R13]
8. Report 08, *Entities and types*: one row per entity (about 52), each listing every field. *Relationships*: every table with every column, the two foreign keys, and the Python entities, with a field table under the diagrams. [R2, R3, R9]
9. Report 11, *Recipes*: each recipe's files are a numbered list, one step per line, and the worked example cites a commit (or says it is unknown). [R14, R15]
10. Report 15, *Gaps*: no item about `cli.py`, `models.py` or a module path "not appearing in the code it cites". [R19]
11. At phone width: no report scrolls sideways; diagrams keep readable text and scroll inside their box; wide tables scroll inside their box and say so. [R4, R16]
12. Reports 10 and 13 still say "Not yet generated": expected, they are M3 (section 9).

**Done** means: every item above holds, `dossier check` printed `problems: 0`, `render` printed no `error:` line, and section 3.3 lists every defect as fixed or as open with your recorded decision. Anything else you find wrong or missing is a new defect: say which card, and it goes into the M3 plan's acceptance list, or back into this plan if it is in M0 to M2 scope.

---

## 9. Risks and out of scope

### Risks (most important first)

1. **The author's page changes only once `INSTALLED` is updated.** Every fix lands in `SKILL`; `/dossier` runs `INSTALLED`, which `encamp-sync pull` updates. The merge that broke it was resolved on 2026-11-01, and `sync.sh` no longer leaves conflict markers in live files (section 3.1).
2. **One session is a tight fit.** Twenty-five tasks, about half with browser tests. "Keeping it to one session" in Phase 1 sets the order, the context rules and the cut line; a cut task is recorded and becomes the next plan's first item.
3. **Browser tests are slow and can be flaky.** Playwright runs are about a minute per page; layout numbers vary by font. Thresholds (11 px, 48 px, 4 px² overlap) have margin; if a check flips on an unchanged page, record it and widen the margin only with the author's agreement.
4. **Per-item rows (A5) make reports longer and builds slower.** On cannalerts: 52 entity rows instead of 25. On a large repository, entity and entry-point counts can reach hundreds. The page handles length (filter, sort, tall tables); Claude's time is the cost, and the spec chose completeness (principle 7).
5. **The split graphs may still be dense inside one area.** An area with 20 components exceeds the budget; D4 draws it at natural size with scrolling and reports it as info, not failure. The interactive graph (M6) is the real answer.
6. **Mermaid ER types.** Sanitising field types loses detail in the diagram; the field table under it keeps the original types.
7. **The golden02 baselines depend on fonts installed on this machine.** They are local fixtures (git-ignored), like `FIX`.
8. **What I could not verify:** whether the code viewer, search and knowledge-map checks pass at 400 px in dark mode after the CSS changes (I measured the current page only); whether semgrep's `metavariable-regex` rule (D13) matches cannalerts' `add(...)` calls exactly (F2-5's test decides); the reading of the author's notes 4 and 8 ("not rendered as a table"): with clean CSS those cards are entries by design, so I assume the author saw R1's breakage plus R15 (Q3).

### Out of scope

- **M3**: reports 10 and 13, the report 14 and 15 additions (Risks `Source` column), `summary.json`, V8, emptying `render.OPTIONAL_REPORTS`. The M3 plan comes after this one; its exit criterion must include `dossier check` with 0 problems and this plan's completeness checks applied to the new cards.
- **M6**: the interactive, collapsible graphs for `components.map` and `interactions.graph`. This plan only makes the interim fallback readable and complete (A2).
- **Report 02 content.** It stays unchanged (A6). Observed, not fixed: the Dependencies card files `playwright` under "Testing", while cannalerts uses it at run time to drive a browser (category from the fixed list in `deps.py`). Recorded for the author's decision (Q6).
- **The freshness BAN** in report 01 (no milestone lists it; Q5).
- Rule precision items from plan 007's findings 1 to 7 other than 1 (duplicate entry points, handled by F2-3's same-path rule) and 5 (SQL comments, F2-1); they belong to the M3 acceptance pass as plan 007 says.

---

## 10. Questions for the author

- **Q1.** Resolved on 2026-11-01: the conflicted `dossier.css` in `~/.local/share/encamp` was restored to upstream (`.8`, as committed in `c94389b`), and the stale autostash (your `.82` edit, which a dossier session made on 2026-10-31) was dropped; its patch was saved in the planning session's scratchpad. Your two systemd changes there were left in place. Nothing more to answer.
- **Q2.** Approve or reject each of A1 to A9 (section 4).
- **Q3.** Component details: keep one collapsible entry per component, each a two-column table (D6, the spec's shape), or one wide table with a row per component and a column per field? The plan does the first.
- **Q4.** Recipes: keep them as numbered entries (spec 11) with steps as an ordered list (D6), or make the card a table Recipe, Step, File, Change? The plan does the first.
- **Q5.** The freshness BAN (spec 4, question 10.3) is in no milestone. Add it to the M3 plan?
- **Q6.** Report 02's Dependencies card calls `playwright` a testing package. Leave report 02 exactly as is (the spec's rule), or allow category fixes in `deps.py`, which would change report 02's content?
- **Q7.** M3 was never built, and the acceptance pause in `docs/process.md` happened on M2 output. After this plan, should the next step be the M3 plan (reports 10 and 13, `summary.json`, V8) followed by the full M3 acceptance, as `docs/process.md` says?
- **Q8.** `~/.config/systemd` is one symlink into `~/.local/share/encamp`, so `systemctl --user enable/disable` changes tracked files there (today: two `default.target.wants` links deleted, `timers.target.wants/` untracked). The new `sync.sh` carries such edits safely, but they keep the clone dirty. Do you want the systemd package stowed with `--no-folding` (real directories in `~/.config/systemd/user`, so enable links stay out of the repository), or to keep enable links tracked in the repository on purpose?
