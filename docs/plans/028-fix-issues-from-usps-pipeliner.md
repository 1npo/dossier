# Plan: fixes to the `dossier` skill (written against 1.11.1)

Source of this plan: a `/dossier build` of `usps-pipeliner` (Windows 11, Git Bash) with dossier 1.10.5. It
exposed two bugs and several design gaps that made the dossier silently incomplete. The skill had since moved to
1.11.1. I re-checked each defect in 1.11.1 before writing this plan (see "Verified in 1.11.1"). Anything marked
"re-verify" must be re-checked by the implementer, because the code may have moved.

Do all work in the skill's **source repository**, never in the installed copy under `~/.claude/skills/dossier`.
End with a version bump (`VERSION`, `pyproject.toml`) and a changelog entry.

Paths below are relative to `src/dossier/` unless they start with `SKILL.md`, `prompts/`, `docs/` or `tests/`.

---

## Verified in 1.11.1

| Defect | Still present? | Evidence |
|---|---|---|
| Backslash paths dropped by the path filter | Yes | `pipeline/extract.py`, inner function `check(p)` of `filter_paths`: it handles absolute paths and a leading `./`, nothing converts `\`. |
| `UnicodeEncodeError` printing `→` when stdout is piped on Windows | Yes | `cli/__init__.py` `main()` never reconfigures stdout. `grep reconfigure\|PYTHONUTF8` finds nothing in the package. 13 `subprocess` calls use `text=True` with no `encoding=`; about 37 `open`/`read_text`/`write_text` calls name no encoding (audit them). |
| Entity budget fails the page check | Yes | `checks/layout.py:25` (`MAX_ENTITIES = 12`, also `MAX_FLOW_NODES`, `MAX_PARTICIPANTS`), check at about line 93; `render/measured/er.py:21` (`MAX_ENTITIES`). |

---

## 1. Bug fix: normalize backslash paths in the extract filter

**Symptom.** On Windows, tool adapters (semgrep especially) return paths such as `pipeliner\config.py`. `filter_paths`
compares them against the git file list, which uses `/`, finds no match, and discards the finding. In the observed
build 1,761 of 3,062 findings were dropped (57%); I/O candidates survived for only 3 files and entry points for 5.
Only an `info:` line mentioned it. Earlier builds of the same repo lost 1,749 of 3,026.

**Change.**
- In `pipeline/extract.py` `check(p)`: first `p = p.replace("\\", "/")` for non-absolute paths. For absolute paths,
  resolve first (as now), then take `.as_posix()`. Also normalize `it["paths"]` entries, which go through the same
  `check`.
- Find any other place that compares adapter or tool paths to git paths without normalizing (grep for
  `in tree`, `ls-tree`, `relative_to`; check `adapters/*`, `core/scip_read.py`, `core/graphs.py`,
  `findings/components.py`, `facts/gather.py`). Re-verify.
- Add a final assertion in the adapter-output stage: every kept path must satisfy `p in tree` and contain no `\`.

**Tests.** Unit test for `filter_paths` with: `a\b\c.py`, `.\a\b.py`, `C:\repo\a\b.py` (absolute under the
checkout), a mixed list, and a path truly outside the checkout (still dropped, counted as `dropped_outside`).
Integration test: run `prepare` on a tiny fixture repo on Windows and assert `dropped_unexpected == 0`
(skip on non-Windows, or simulate by feeding backslash paths into the filter).

**Acceptance.** Re-running `prepare` on `usps-pipeliner` keeps findings for essentially all of its 116 `pipeliner/` Python
files (I/O candidates, entry points, retries, logs and so on), and `dropped_unexpected` is near zero.

---

## 2. Bug fix: UTF-8 output on Windows

**Symptom.** When output is piped (Git Bash, CI, the Claude Code Bash tool) Python on Windows uses cp1252.
`render` printed a warning containing `→` (U+2192) and crashed with `UnicodeEncodeError` before the HTML was written
(`cli/commands/render.py`, the `print(f"warning: ...")` loop). Workaround used: `PYTHONUTF8=1`.

**Change.**
- In `cli/__init__.py` `main()` and in `scripts/dossier.py` (before any output), call
  `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` and the same for `sys.stderr`; guard with
  `hasattr(..., "reconfigure")`. Do the same in `__main__.py` and in any other entry (`check_page.py` runner,
  subprocess helpers) that prints.
- Audit every `subprocess.run/Popen(..., text=True)` (13 sites) and add `encoding="utf-8", errors="replace"`. Audit
  every `open`, `read_text`, `write_text` without `encoding` (about 37 sites) and set `encoding="utf-8"`. Git output on
  Windows is UTF-8, and decoding it as cp1252 corrupts paths and author names.
- Child Python processes launched by the CLI (the page checker, extractors) should get `PYTHONUTF8=1` in their env.

**Tests.** Subprocess test that runs a command printing `→` and a non-BMP character with `PYTHONIOENCODING=cp1252`
and with stdout piped; it must exit 0. A render test whose warning text contains `→`.

**Acceptance.** `uv run scripts/dossier.py render .` works from Git Bash with no environment variable set.

---

## 3. Additional change A: make tool failures, skips and discarded output loud

**Problem.** `scip-python` was skipped because the branch was not trusted, and the filter discarded most findings.
Both were in `build.json` and an `info:` line, and neither reached the user. The user wants to be told, every time,
when a tool did not run.

**Change.**
- Define one record, built from `build.json` (extract step `details.adapters[].tools`, plus `preflight`, plus
  `trust`): `tools_not_run = [{adapter, tool, status: skipped|failed|missing, reason}]`.
- `prepare` prints it in its JSON (`tool_report`) and, on stderr, as `warning:` lines. It also prints the extract filter
  counts.
- **Fail loudly on discarded output.** If `dropped_unexpected / paths_seen` is above a threshold (suggest 2%), `prepare`
  stops with exit code 4 and `"stopped": "extract_filter"`, printing the first 20 dropped paths, unless
  `--allow-dropped` is passed. Also change the `V9` log line from `info:` to `warning:`/error.
- Empty-candidates guard: when a report's `candidates` output is empty but the repository has code for that area
  (for example the Python adapter reports zero I/O candidates for a repository with more than N Python files),
  `candidates` prints a prominent line saying the tool findings for this report are empty and why they may be.
- `render` summary JSON gets `tools_not_run` and `filtered_out`; the process card in the page lists them; `check`
  prints them at the end.
- `SKILL.md`:
  - Step 1: after `prepare`, show the user every entry of `tool_report`, in plain words, before continuing.
  - Step 8: require a "Tools that did not run" paragraph in the final message, naming each tool and the reason
    and what to do (for example "pass --allow-ref" or "install X"). If nothing was skipped, say "All tools ran".
  - Make step 1 ask the user whether to continue when the filter or a tool failed.
- Consider whether an untrusted ref should still run `scip-python`. Today it is gated on trust because Node tools run
  project code. `scip-python` is not Node. Re-verify why it is gated (`adapters/python/adapter.py`, trust logic in
  `cli/commands/prepare.py`) and, if it is safe, run it regardless.

**Tests.** Extract with a fake adapter that returns backslash paths, assert exit 4. Fixture where a tool is skipped,
assert `tool_report` and the summary field. SKILL.md lint (if the repo has one) for the new step text.

---

## 4. Additional change B: remove the diagram budgets as failures

**Problem.** The page check failed a diagram with 13 boxes against a limit of 12. The limit counts cross-component
stub boxes. Nothing was actually omitted (the card has a full "Every field" table), but a failing check implied
content was being cut. The user wants no limits like this.

**Change.**
- `checks/layout.py`: remove the entity-count failure entirely (`maxEntities`, about line 93, and the constant at
  line 25). Remove the matching `maxEntities` entry from the dict near line 149. Decide for the other two budgets
  (`MAX_FLOW_NODES` 12, `MAX_PARTICIPANTS` 10): preferred outcome is to demote them to an advisory line in the check
  output that does not count in `problems: N` and does not fail the exit code. They guard readability, and
  `prompts/method.md` already says to split a long flow and never drop a step.
- `render/measured/er.py`: keep splitting a large set per component (it is presentation), but reword the module
  docstring to say nothing is omitted and the field table is complete. Remove the `"area"` budget flag coupling
  (`_diagram(..., budget)` in `render/measured/graph.py`) if it only existed for the removed check.
- Make sure no other code path truncates rows, nodes or files to fit a size (grep for slices like `[:N]`, `top`, `limit`,
  `omitted`, `more)`). The code viewer drops files "for size" (`files_dropped_for_size` was 10); that is a page-size
  cap on embedded source, and it should be listed explicitly in the process card and in Gaps with the file names.
- `prompts/method.md` section "Diagrams": keep the guidance (split long flows) but say it is advice, not a check.
- `docs/` and `README.md`: remove mention of the budgets as failures.

**Tests.** Layout test with a 15-entity ER diagram and a 15-participant sequence diagram: `problems: 0`.

---

## 5. Additional change C: a full build must start from empty reports

**Problem.** `prepare` said `mode: full`, but the old `reports/*.json` were still in the folder. The build session
patched them instead of rewriting them, so thin narrative cards from the older build survived.

**Change.**
- In `cli/commands/prepare.py` (near where `reports/` is created, about line 148) and `pipeline/incremental.py`:
  when the plan mode is `full`, move the existing `reports/*.json` to `reports.prev/<timestamp>/` (do not delete),
  leave `reports/` empty, and print `"archived_reports": [...]` plus a plain sentence. `state.json` (corrections and
  user decisions) is untouched.
- `existing_reports` in the prepare JSON becomes `[]` for a full build; the old names go in `archived_reports`.
- `SKILL.md` step 5, "full" bullet: say the old reports were archived, must be written from scratch, and the archive
  must not be read as a source of text. Add the same line to `prompts/method.md` "Corrections and updates".
- `render` must refuse (error) to run in a full build when fewer than all authored reports exist, unless
  `--partial`. Check how `--partial` behaves today; re-verify.

**Tests.** Prepare twice on a fixture: second run with `--full` archives and empties; with incremental it does not.

---

## 6. Additional change D: coverage of the hand-written cards

**Problem.** Cards that have no tool findings (Source of truth, Key flows, Lifecycle and sensitive fields, Business
rules and invariants, Extension points) are only checked for shape. Nothing notices when a whole component is never
mentioned. In the observed dossier those cards had 0 Smartsheet mentions in three cards, with five Smartsheet
workflows in the repository, and the Source of truth card had 7 rows.

**Change.**
- New check `V13` in `checks/reports.py`. For each card in `data.truth`, `data.lifecycle`, `behavior.rules`,
  `interactions.flows`, `components.extension-points`: every catalog component must be touched by at least one row
  or diagram of the card. "Touched" means the row's citations include a file inside one of the component's `Paths`
  (the components module already maps path to component: `findings/components.py` `component_of`), or the row's
  `Owner component`/text names the component.
- Escape hatch: each of those cards may carry `"not_applicable": [{"component": "...", "reason": "..."}]`. A reason is
  required; the card prints them in a small "Not applicable" list. The schema files in `data/schemas/cards/*.json`
  need the new optional field and the writer docs (`cards/README.md`) must describe it.
- `interactions.flows`: additionally require that every component containing an entry point (from `entry.catalog`)
  appears in at least one flow or in `not_applicable`.
- Severity: error for components with more than N source lines (suggest 300 lines); warning below.
- `prompts/reports.md`: add to each of the five cards "every component must be covered or listed in
  `not_applicable`" and give one worked example for a group of similar workflows (one row per workflow when they
  differ, a shared row listing them all when they do not).
- `prompts/method.md`: add a short "Coverage" section. Chunk readers must record, per component, its integration
  targets, lookup tables and state, so the writer has them.
- Gaps report: list each `not_applicable` entry as an `assumption` so the reader sees what the writer declined to
  cover.

**Tests.** Fixture with three components and a card that misses one: V13 errors, then passes when the row or a
`not_applicable` entry is added.

---

## 7. Additional change E: non-code files the code reads become findings

**Problem.** 27 `.mjml` email templates, `pipeliner/data/mime_data.json`, CSV mappings and similar files are read by
code, but they are not code, so no extractor emits a finding. The Inputs card never asked about them and they were
missing. The templates are loaded by path (`email_templates/{type}.mjml`) and by directory.

**Change.**
- New finding source `resources` (id prefix `rs`, group `rsg`) in `findings/candidates.py` (`ID_OUTPUTS`,
  `DECIDED_OUTPUTS`, `home_card`), with home card `io.inputs`. Build it in a new module `facts/resources.py`, run
  during `prepare`, written to `extract/resources.json`.
- Detection: take tracked non-code files by extension or lang (mjml, html, jinja/j2, txt, json, csv, tsv, xlsx, xlsm,
  docx, yaml/yml, toml, ini, sql, xml, md used as templates, and any file under a directory named `data`, `resources`,
  `templates`, `fixtures` outside `tests`). Group by (directory, extension), so 27 templates become one group with
  a member list.
- Link each group to code: search all analyzed code files for (a) the file name, (b) the directory path as a string
  or `Path` fragment, (c) the extension used in a format/f-string such as `f'...{x}.mjml'`, (d) the package-resource
  call patterns (`importlib.resources`, `pkgutil.get_data`, `Path(__file__).parent / 'dir'`), and (e) the directory
  name as a bare string. Record the referencing file and line range for each group. A group with no reference is still
  listed with `referenced_by: []`.
- Each group is a finding the writer must keep, merge or dismiss, like any other (V5 applies). `candidates --report io`
  lists them under `io.inputs`, and `data` also receives them (as possible lookup tables or sources of truth) via the
  same ids, so one decision is shared (see `candidates.py` `home_card`).
- Exclude by default: the test and coverage reports of section 8, lockfiles, assets and binaries (already excluded),
  and anything under `tests/` unless it is also referenced from non-test code.
- `prompts/reports.md`: in `io.inputs` say "every `rs-` finding is a row (`files read` category) or is dismissed with
  a reason"; in `data.truth` say lookup tables, reference data and templates are candidates for rows.
- Optional: add a semgrep rule for package-resource reads in `data/rules/python/` so the I/O candidates catch them too.

**Tests.** Fixture repo with a `templates/` folder of three `.mjml` files read via an f-string path: one `rs` group, one
reference, undecided finding blocks `render` until kept or dismissed.

---

## 8. Additional change F: ignore coverage reports and test results by default, and say so

**Problem.** `TESTS.md` (about 113k tokens) and `.coverage-report.xml` (about 121k tokens) are generated by CI. They are
neither source nor input, they use a large share of the reading budget, and the reports quote their numbers, which
go stale as soon as CI reruns.

**Change.**
- `facts/gather.py` `noise_reason()` (about line 190): add a `test-report` reason. Match, case-insensitively:
  - file names: `.coverage`, `.coverage.*`, `coverage.xml`, `coverage.json`, `coverage-final.json`, `lcov.info`,
    `*.lcov`, `cobertura*.xml`, `jacoco*.xml`, `clover.xml`, `.coverage-report.*`, `*coverage*report*.(xml|json|html|md|txt)`,
    `junit*.xml`, `TEST-*.xml`, `nosetests.xml`, `test-results*.(xml|json)`, `*.trx`, `pytest*report*.(xml|json|html)`,
    `report.html` next to `pytest`/`junit` markers;
  - directories (add to `GENERATED_SEG` or a new set): `htmlcov`, `coverage` (already), `.nyc_output`, `test-results`,
    `test-reports`, `TestResults`, `allure-results`, `playwright-report`;
  - content sniffing in the `gather` loop (about line 870, next to the "DO NOT EDIT" check) on the first 2 KB: a root
    element `<coverage` with `Generated by coverage.py`, `<testsuite`/`<testsuites`, `<TestRun` (trx), or a Markdown table
    whose header row has `Stmts`, `Miss`, `Cover` (the CI-written `TESTS.md`).
- Record each ignored file in `facts.files` as a list `ignored_reports: [{path, why, tokens}]`, in addition to the
  `excluded["test-report"]` count. (Today only counts and top directories are kept, which makes it impossible to name
  the files.)
- Opt-in: `--include-test-reports` on `prepare`/`build`. Remember the choice for the repository in `state.json`.
- Tell the user, every build:
  - `prepare` prints `ignored_reports` and a plain sentence ("Ignoring 2 coverage or test-result files, about N
    tokens: ...; pass --include-test-reports to read them").
  - `SKILL.md` step 1: show that sentence with the list. Step 8: repeat it in the final message.
  - The Gaps report gets one automatic `coverage` item per ignored file, and the page's "Files analyzed / not counted"
    tile lists them by name (`render/page.py` about line 1592).
- Writing implications to document in `prompts/reports.md`, `behavior.tests`: counts of tests come from the test
  extractor and CI config, coverage thresholds from `pyproject.toml`/CI files; do not cite a generated report. Remove
  the "CI test commands" dependency on those files. A citation to an ignored file renders as unresolved, so say so in
  `method.md`.

**Tests.** Unit tests for `noise_reason` on each pattern, a content-sniff test for a coverage.py XML and a
`Stmts | Miss | Cover` Markdown table, and a negative test (a file that merely mentions "coverage" in prose is not
excluded). Integration: `prepare` output lists the ignored files; with `--include-test-reports` they are read.

---

## Order of work

1. Sections 1 and 2 (bugs) with tests; release as a patch first if desired.
2. Section 3 (loud tool reporting) so later sections are visible.
3. Section 8 (ignore reports) and section 5 (archive old reports on full builds): small and independent.
4. Section 4 (remove budgets).
5. Sections 6 and 7 (coverage check, resource findings): largest; touch schemas and prompts.
6. Update `SKILL.md`, `prompts/*.md`, `README.md`, `docs/user-guide.md`, `docs/developer-guide.md`; bump version.

## Acceptance for the whole change (rebuild of `usps-pipeliner`, run from main)

- No `UnicodeEncodeError`; no `PYTHONUTF8` needed.
- `dropped_unexpected` near zero; entry-point and I/O candidates are non-empty and cover `pipeliner/workflows/**`.
- The build output names every tool that did not run (or says all ran) and names the ignored coverage/test files.
- No page-check failure from diagram size.
- `reports/` empty at the start of a full build; `reports.prev/` holds the old ones.
- Source of truth, Key flows, Lifecycle, Business rules and Extension points each cover (or explicitly mark not
  applicable) the Smartsheet workflows, the `library/directory` lookup tables, and the other components.
- Inputs card has a decision for the `pipeliner/data/email_templates/*.mjml` group and `pipeliner/data/mime_data.json`.
