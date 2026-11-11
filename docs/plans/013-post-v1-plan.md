# Plan 013: after 1.1.0

Source: [../post-v1.md](../post-v1.md) (the author's reviewed order), plus one new item from the author: group the 40 questions into categories and sort them in the order a person asks them when diving into a new codebase. Item 19 of `post-v1.md` (correct TS and C# against real codebases) is **not** part of this plan; it starts later from the author's work.

Status lives in the checkboxes. Results go under each phase's "Results" heading.

## Shared rules (every phase reads this first)

- **Repository.** `~/dev/projects/dossier` (`github.com/1npo/dossier`). The repository root is the skill root. Work only here; never edit `~/.claude/skills`, `~/.claude/plugins` or `~/.local/share/encamp`.
- **Skills to load.** `git-workflow`, `git-commit`, `git-release`, `claude-planning-docs`. Commit as `Claude Sonnet 5.5 <noreply@anthropic.com>` with `-c user.name=... -c user.email=...` and the `Co-Authored-By` trailer, one commit per task. Work on `<type>/<short-name>` branches; merge to `main` with `--no-ff`; push `main`; delete the branch.
- **Tests.** Default suite: `uv run --with pytest --with pygments python -m pytest tests -q`. The frozen fixture `tests/fixtures/encamp-m0` is present on the author's machine but not in CI; `test_summary_render.py` fails with it present until Phase 2 task 7. Until then add `--ignore=tests/integration/scripts/test_summary_render.py`. Slow suite: `DOSSIER_SLOW=1 ... --basetemp=$HOME/.cache/dossier-slow` (about an hour; three known failures: `test_overlapping_paragraphs_are_reported`, `chart-text-small`, golden02). Record counts in each phase's Results; a count that drops without a deleted test is a bug.
- **Release.** A bump is a release: `python3 scripts/bump_version.py {minor|patch}` on `chore/release-X.Y.Z`, commit `Bump version to X.Y.Z`, merge, push. CI tags and publishes. Never tag by hand. The release points are listed in each phase; the author's answer to "release now?" is needed at none of them unless a phase says so.
- **The spec** [004-v1-spec.md](004-v1-spec.md) is the authority. If the code contradicts it, or a task needs a spec change, record it under the phase's "Spec issues" and stop for the author; do not work around it. Report 02 stays untouched unless a task says otherwise.
- **No caps, fixed structure** (spec principle 7): a card never drops rows to fit a limit, and the number of cards never depends on repository size.
- **Fixed scratch.** Put scratch work under `~/.cache/dossier-p13-<phase>`; keep ground-truth folders; do not delete `~/.cache/dossier-m6-g4vm` or `~/.cache/dossier-m5-vWDO/truth`. The environment for the verification blocks is plan 012 section 7 (set `SKILL=~/dev/projects/dossier`).
- **Start of every phase.** Read this section, `git log --oneline -15`, the previous phase's Results, and `docs/post-v1.md` for the items named. Pick up anything an earlier phase cut.
- **Cut line.** Cut from the end of a phase, never the middle: each task is committed and tested on its own. Write what was cut under Results and add it back to `docs/post-v1.md`.

## Release points

| After | Version | Why |
|---|---|---|
| Phase 2 | 1.2.0 | graph removal and the bug fixes (a new minor makes every dossier rebuild in full) |
| Phase 4 | 1.3.0 | reordered questions, environment-variable and secrets cards |
| Phase 7 | 1.4.0 | detection gaps, Tier B symbols, reference data |

Phase 1 and the Phase 3 and 5 to 6 merges ship in the next release; they are not released alone.

---

## Phase 1: Make builds trustworthy

Post-v1 items 1 to 4. Branch `fix/trusted-builds`.

- [x] **P13-1. Verifier verdicts disappear.** Read `scripts/verify.py`, the `verify-record` and `render` code in `scripts/dossier.py`, and where `build.json` is written (`buildlog.py`). Reproduce: record verdicts, then run `prepare`, `render`, `check` and `verify-sample` in the orders a build uses, and find the call that drops them (suspects: a `prepare` that rewrites `build.json` for the same commit; a second `verify-sample`). Fix the cause and add a unit test that fails before the fix. Done-check: the new test, and a sequence script in the test that records, renders, checks and re-renders with the verdicts still present.
- [x] **P13-2. A stale `extract/` after a skill change.** `prepare` keys the extract by commit and ref. Add the skill version (`VERSION`) and a hash of `scripts/*_adapter.py`, `rules/` and `tools.json` to the key, so that a changed rule or adapter re-extracts. Decide the key in one sentence in the commit message. Done-check: a test that runs `prepare` twice on a fixture repository, edits a rule file between the two, and expects the second to re-extract; and one that expects no re-extract when nothing changed.
- [x] **P13-3. `cs_scip.soft_failure` on real logs.** Make it match scip-dotnet's real line shape (`<time> fail: <logger>[<n>] Failure: Msbuild ...`, see `cs_scip.unloaded_projects`, which already parses it). Do not mark the tool `failed`. Name the unloaded projects in the C# `Gaps` item (the build's tool notes: "scip-dotnet could not load N projects: A, B"). Done-check: unit tests using a log copied from `tests/` fixtures or written in the real shape; a page-audit or gaps test that the item names the projects.
- [x] **P13-4. Verdicts for claims without an `id`.** Give every sampled claim an id when `verify-sample` writes the sample (`<report>:<n>` from the citation), and key saved verdicts by id, falling back to the citation text. Done-check: a test where a claim's wording changes and its verdict still matches.

**Deliverables.** Four commits, one per task, and the suite green. **Acceptance.** Default suite passes with at least the Phase start count plus the new tests; no existing test was deleted or loosened. **Branch.** Merge to `main`, push; no release. Write "Results (Phase 1)" with the cause found for P13-1 (if the cause cannot be found in one session, say so and leave the regression test that would catch it).

### Results (Phase 1)

Done 2026-11-10 by Sonnet 5.5 on `fix/trusted-builds`. Default suite: start 2875 passed, 294 skipped; end **2887 passed, 294 skipped** (66 s; `test_summary_render.py` ignored because the frozen fixture is present). Slow suite not run (not required by this phase).

- **P13-1, cause found.** `buildlog.start` (called by every `prepare`) moves `build.json` to `build.prev.json` and writes a new one with no records, and the verifier's sample and verdicts lived only in the old file. A `prepare` after `verify-record` therefore dropped them (with `--verify` on, the build still said `verify: true`). Fix: `start` carries the `verify-sample` and `verify` records over when the new build has the same commit, and not for another commit. Three tests in `test_buildlog.py`. Limit: a second `verify-sample` after the verdicts still makes V10 error ("sampled claims but no results"), by design, because the new sample needs its own verdicts. The exact command order of the M6 run was not recorded, so the first cause I found is the `prepare` one; the second-sample path is the only other way to get that exact V10 text.
- **P13-2.** The key already held the adapter version, tool versions and a rules hash; it lacked the code. `adapters.code_hash()` hashes `scripts/*.py`, `tools.json` and `VERSION` and is part of `_key`, so any change to the skill's code re-extracts (and every saved extract re-extracts once after this change). Three tests in `test_adapters.py`. Cost: a change to any script, even one an adapter does not use, re-extracts the next `prepare`; judged acceptable because it is cheap to be right.
- **P13-3.** The plan assumed `soft_failure` should match the real line; it stays as the bare-form reader. The adapter now adds the `msbuild` note from `unloaded_projects` (the Gaps item reads "scip-dotnet could not load every project: <paths>") and the tool stays `ok`, so the dead list still runs and skips the unloaded projects (`6fa6624` in the old history). One test in `test_cs_adapter.py` with a real-shape log.
- **P13-4.** Verdict key: the claim's id, else a hash of its card and sorted citations (`c:<sha1>`), else a hash of its text when it has no citation; repeats of a key get `#2`, `#3` (`verify.keyed`). Five tests in `test_verify.py`. Verdicts saved before this change used text hashes, so they stop matching once; a new minor version rebuilds anyway.

---

## Phase 2: Clean up the split and the graph removal

Post-v1 items 5 to 8. Branch `chore/cleanup-after-split`. Read Phase 1's Results first.

- [x] **P13-5. README screenshot.** `docs/images/dossier.png` shows the removed graph. Build a dossier of a small repository (the plan 012 `RW` clone is under `~/.cache/dossier-m6-g4vm/src` and its page under `~/.cache/dossier-m6-g4vm/home`; reuse the page), take a new screenshot of the component map card with `playwright` (the `check` tooling already installs Chromium: `uv run --with playwright python -m playwright install chromium`), and replace the image. Done-check: the image shows no interactive graph toolbar; README renders it.
- [x] **P13-6. Duplicate test classes.** In `tests/integration/scripts/test_check_page_slow.py` remove the second copies of `m4`, `TestNewTablesOnTheM4Page`, `m5` and `TestNewTablesOnTheM5Page` (compare them first; if they differ, keep the more complete and say which). Done-check: `pytest --collect-only -q` shows each test id once.
- [x] **P13-7. The M0 fixture tests.** Delete `test_summary_render.py`, `tests/tools/m3_page.py`'s M0 helpers if nothing else uses them, `scripts/migrate.py`, `scripts/migrate_map.json`, the `migrate` command, the fixture line in `.gitignore`, and the `DOSSIER_SUBJECT_REPO` workaround, but only after checking with grep that nothing else needs them (`test_check_page_slow.py` and `golden02` use the fixture: if a test is the only user of the fixture and is skipped in CI, delete it too, and say which tests went and why). Done-check: the default suite passes with the fixture folder present and with it absent.
- [x] **P13-8. The test that counts differently in a fresh clone.** Run the default suite in the working tree and in a fresh clone (`git clone . $SCR/fc`) with `-rs`, diff the skip lists, and explain the one test that differs. Fix it or record why it is correct. Done-check: the two counts are equal, or the difference is explained in Results.

**Acceptance.** Default suite green in the working tree and in a fresh clone with the same count. **Branch and release.** Merge, then release **1.2.0**.

### Results (Phase 2)

Done 2026-11-10 by Sonnet 5.5 on `chore/cleanup-after-split`. Default suite: start 2887 passed, 294 skipped (with `test_summary_render.py` ignored); end **2887 passed, 294 skipped** with no ignore flag, in the working tree and in a fresh clone (`-rs` skip lists identical).

- **P13-5.** `docs/images/dossier.png` is a new screenshot of the component map card of the `RW` clone, rendered with the current code (a copy of `~/.cache/dossier-m6-g4vm/home/rw`, re-rendered in `~/.cache/dossier-p13-2`; the original is untouched). It shows the "no static graph" badge and the table, no graph and no view selector. README alt text updated.
- **P13-6.** The second `m4`, `TestNewTablesOnTheM4Page`, `m5` and `TestNewTablesOnTheM5Page` were identical to the first (diffed); removed. `--collect-only` lists no id twice.
- **P13-7, partly done.** Deleted `test_summary_render.py` (its one test needed the fixture and `migrate`, failed where the fixture exists, and was skipped in CI). Its coverage of "render writes `summary.json`" is now only in the unit tests of `summary.py`. **Not deleted:** `migrate.py`, `migrate_map.json`, the `migrate` command, the `.gitignore` line and `DOSSIER_SUBJECT_REPO`. The grep showed `tests/tools/m3_page.make` copies the fixture and runs `migrate`, and the M4, M5 and M6 page builders and `test_check_page_slow.py` all sit on it, so deleting them breaks the slow suite (the plan said to delete only if nothing else needs them). `golden02` also still reads the fixture. Left as item 7 in `docs/post-v1.md`, reworded.
- **P13-7, finished 2026-11-11 (post-v1 item 7), on `refactor/retire-m0-fixture`.** `tests/tools/m3_page.py` and `test_check_page_slow.py` now commit `tests/fixtures/pyrepo` in a temporary folder, run `prepare`, and add 600 generated source paths and one `interactions.flows` card (a diagram with numbered notes and three citations, which two mutation tests need). Deleted: `scripts/migrate.py`, `migrate_map.json`, the `migrate` command, `test_migrate.py` (13 tests), `golden02` (`test_golden02_slow.py` with 3 tests, `tests/tools/golden02.py`, the baselines), the `.gitignore` lines and `DOSSIER_SUBJECT_REPO`. Default suite 2912 passed, 298 skipped to **2899 passed, 295 skipped** (the 13 and 3 deleted tests, no others). Two slow-suite findings: `test_check_page_slow.py` never imported `m6_page`, so `TestHeaderBadges` and `TestLargeM6Page` had always errored (import added); and the "Go to reference" check in `scripts/check_page.py` waited 700 ms for a smooth scroll, too short on the large page (now 3 s). The local folder `tests/fixtures/encamp-m0/` is unused; it is hidden in this clone's `.git/info/exclude` and left for the author to delete.
- **P13-8.** The one test that differed was `test_summary_render.py` (it ran with the fixture present and failed). With it deleted the counts are equal and the skip lists identical.

---

## Phase 3: Group and reorder the 40 questions

New item from the author. Branch `feat/question-order`. **An author decision comes first.**

**Read first.** `prompts/schema/questions.json` and its README paragraph, `scripts/schema.py` (`load_questions`), the `dossier.questions` card in `render.py`, `scripts/candidates.py` and `tests/unit/scripts/test_schema.py` (where the list is used), `prompts/reports.md` and `prompts/method.md` (any place that names a question number), and spec section 3 (the questions, and where they are answered; the card `dossier.questions` is defined in section 4).

**The draft grouping.** The author asked for categories, and for the questions in the order a person asks them when diving into a new codebase. This draft puts them in 12 groups (the numbers are today's ids):

| # | Category | Asks (today's ids) |
|---|---|---|
| 1 | Orient | 9 reading order, 1 domain terms, 2 technologies and idioms |
| 2 | Get it running | 34 local needs, 32 build, test, run, release, deploy, 33 CI gates |
| 3 | Shape | 5 main components, 6 what each does, 7 how they interact, 12 layer boundaries, 16 third-party code |
| 4 | Execution | 3 where execution starts, 4 entry to ready, 11 concurrency |
| 5 | Boundaries | 8 inputs and outputs, 15 contracts owed to others, 13 extension points |
| 6 | Data | 17 structures and schema, 10 where state lives, 18 source of truth, 19 lifecycle and sensitive fields |
| 7 | Behaviour | 20 business rules and invariants, 22 how it fails and how I would notice |
| 8 | Working here | 14 how to write code that fits, 36 branch, commit and PR conventions, 21 what the tests cover, 25 what breaks if I change X |
| 9 | History and change | 23 what changes most, 24 what changes together, 31 work in flight, 26 half-finished refactors, 27 why it is this way |
| 10 | Health and risk | 28 docs match the code, 29 dead code and stale flags, 30 upgrade burden |
| 11 | People | 35 owners, knowledge and bus factor |
| 12 | Trusting this dossier | 37 what was not analysed, 38 where extractors may be wrong, 39 freshness, 40 how it was produced |

Open points the author may change: whether "People" (35) moves earlier (who do I ask), whether 20 belongs under Data, whether 33 belongs under Health, and whether 36 belongs with Get it running.

- [x] **P13-9. Author review (stop here first).** Show the author the draft table above and the proposed default for the open points below, and wait for the answer. The default if the author says "go": the draft as written; **renumber** the ids to the new order, because a new minor version already makes every dossier rebuild in full, so no saved dossier keeps old numbers; the page shows the category as a heading with the numbered questions under it; each question keeps its answering cards.
- [x] **P13-10. Reorder and group the data.** Add a `category` field to every entry in `questions.json` and a top-level `categories` list (id, title, one-line "why you ask these now") in the agreed order; reorder the entries; renumber (if agreed). Update `schema.load_questions` and every consumer; update any place that quotes a question number (prompts, spec section 3, docs); the author's request authorizes changing the spec's question list and its numbering here. Done-check: a schema test that every question has a known category, categories are in the agreed order, ids are `1..40` in file order, and every question still has at least one answering card; `grep` finds no stale number in prompts or docs (list what you changed).
- [x] **P13-11. Draw the card.** `dossier.questions` shows each category as a heading with its questions in order, each linking to its cards as today. Keep V-checks green (the card's text and the page audit). Done-check: render the fixture page, read the card in the browser check's shot, and `dossier check` reports `problems: 0`.
- [x] **P13-12. Docs.** User guide: one paragraph on how the questions are grouped and why the order. Done-check: `test_docs.py`.

**Acceptance.** Default suite green; the card shows 12 groups and 40 questions; the author approved the grouping before P13-10. **Branch.** Merge, push, no release yet.

### Results (Phase 3)

- P13-9: the author approved the draft as written (thin groups People and Behaviour stay) and left the four open points at their defaults.
- P13-10: `questions.json` is now `{"categories", "questions"}`; ids `1..40` in the new order; `schema.load_categories` added, `load_questions` unchanged in shape plus `category`. Spec section 3 rewritten with the new numbering. No prompt or doc quoted a question number.
- P13-11: one headed table per category (`t-questions-<category>`), fixed column widths; V11 now checks each table's row count and the 12 groups. Rendered and read in the browser: 12 groups, 40 questions. The old single filterable table is gone (a filter over 12 small tables does not help).
- P13-12: user guide section "Read the questions card".
- Extra, by the author's request: `render.py` failed to parse before Python 3.12 (backslash and reused quotes inside f-strings, three sites). Fixed on `fix/py310-render`, with `test_py310_syntax.py` (parses every script under 3.10).
- Default suite: 2888 passed, 294 skipped (was 2887 plus the new test).
- **Python floor:** `py_packages.py` and `py_api.py` import `tomllib` (3.11+), so the 3.10 floor was false. Raised to 3.11 for the CLI and page check; the three worker scripts keep 3.10 (they run under the repository's own Python). Suite passes on 3.11 and 3.13.
- **Released 1.2.1** (author approved): the 3.10 syntax fix, the Windows sandbox fix (from `~/dossier-sandbox.patch`), `/dossier build` printing the version first, and the 3.11 floor.
- **Found, not fixed (item 7):** the `encamp` repository now has two root commits, so `out_dir` resolves the fixture to `encamp-<hash>` and every fixture-based slow test fails with "No facts.json found".

---

## Phase 4: Environment variables and secrets cards

Post-v1 items 17 and 18, which the author wants added. Branch `feat/env-and-secrets-cards`. Read Phase 3's Results first (the cards answer questions by their new ids).

**Read first.** `scripts/gather.py` around line 1205 (`env_vars`, `secret_signals`), `scripts/render.py` (`FACT_KEYS`, the removed panels, line 233), `scripts/checks.py` (the `env_vars` check), `prompts/schema/ops.json`, `prompts/schema/io.json`, `prompts/schema/README.md`, the spec decisions on cards (sections 3 and 4) and on the permanent non-goals (section 1), and `docs/plans/005-m0-plan.md` question Q4.

**Design (proposal; change it only for a reason you write down).**
- Two new script-written cards, tier `M`, priority P1: `ops.env-vars` (every environment variable the code reads: name, files and lines that read it, a default when the call has one, and whether the variable also appears in a Dockerfile, compose file or CI workflow) and `ops.secret-signals` (every tracked string or file that matches a credential pattern, by path and line and pattern name; **never the value**). They sit in report `ops`, after `ops.config-secrets`.
- No caps: every row is listed (the page sorts and filters). The panels were removed in M0 because they capped rows.
- The secrets card says in its first line that it lists pattern matches for human review and is not a security scanner (spec section 1). It never prints or stores a matched value; a test greps the built page and `extract/` for a planted fake secret and expects zero occurrences.
- Questions: `ops.env-vars` answers the input question (8) and the local-needs question (34); `ops.secret-signals` answers the sensitive-fields question (19). Use the ids from Phase 3.
- Without matches the card is drawn as an empty table with "No environment variable reads were found" (not omitted: the structure is fixed).

- [ ] **P13-13. Facts.** Make the gatherer's `env_vars` and `secret_signals` complete and per-language (Python `os.environ`, `os.getenv`; JS `process.env`, `import.meta.env`; C# `Environment.GetEnvironmentVariable`, configuration binding by name only where the name is a literal). Output with path, line, name, default when literal. Secrets: reuse the existing patterns; add none that match values the card would print. Done-check: unit tests per language on small fixtures, and the planted-secret test.
- [ ] **P13-14. Schema and render.** Add the two cards to `ops.json` (tier M, writer script, shape computed), draw them in `render.py`, add their anchors and citations, update `questions.json` answers. Update every place that counts cards (56 becomes 58: `skeleton.py` expectations, V checks, tests, docs; grep `56`). Done-check: `test_schema_files.py`, `skeleton.py` on the six pages of plan 012 block X (use the saved pages under `~/.cache/dossier-m6-g4vm` after re-rendering) reports the same 58 cards on each.
- [ ] **P13-15. Prompts and checks.** `prompts/reports.md` and `method.md`: tell the writer these two cards are drawn by code and must not be written; `ops.config-secrets` should refer to them instead of listing variables itself. Page audit (V11-style): every row's file and line must exist in the tree. Done-check: `test_prompts.py`, page-audit tests, and `dossier check` on one built page with `problems: 0`.
- [ ] **P13-16. Docs and post-v1.** User guide and the report list in README; remove items 17 and 18 from `docs/post-v1.md`. Done-check: `test_docs.py`.

**Acceptance.** Default suite green; slow suite run once at the end of the phase with the known failures only; both cards present on every page of block X; the planted-secret test passes. **Branch and release.** Merge, then release **1.3.0**. Results: card row counts on `RW`, `BP` and `CA`, and any false positives seen (list them; do not fix them by dropping rows).

### Results (Phase 4)

Done 2026-11-10 by Sonnet 5.5 on `feat/env-and-secrets-cards`. Default suite: start 2888 passed, 294 skipped; end **2912 passed, 298 skipped** (the 4 new skips are `test_env_cards_slow.py`, which passes under `DOSSIER_SLOW=1`). Slow suite once: 3173 passed, 1 skipped, 36 errors, all in `test_check_page_slow.py` (33) and `test_golden02_slow.py` (3), all "No facts.json found" from the encamp fixture (item 7); no other failure.

- **P13-13.** New `scripts/env_scan.py`: Python (`os.environ`, `os.getenv`), JS/TS (`process.env`, `import.meta.env`, `Deno.env.get`) and C# (`Environment.GetEnvironmentVariable` with a literal name), plus the older Go, Java, Rust, Ruby, C and Zig forms. Each variable keeps every site, a literal default, and the Dockerfile, compose, CI and `.env` files that name it. Names are no longer limited to 3+ uppercase characters. Secret hits are every match (no 200 cap, no one-per-pattern), no value stored. A default under a secret-like name or shaped like a credential is withheld. Not done: C# configuration binding (its keys are not environment variable names).
- **P13-14.** Two M, P1, script cards in `ops.json`; drawn by `measured_env.py`; questions 4 and 15 list `ops.env-vars`, 21 lists `ops.secret-signals`; spec updated. The skeleton is 58 cards (the plan's "56" was the skeleton count, not a number in code, so nothing else needed changing) on all six block X pages, same order, exit 0 (scratch copies of the saved pages, re-rendered with fresh facts).
- **P13-15.** Prompts updated; V11 now checks both tables' rows and that every named file and line exists. **Retired `v5_env`** (it forced `io.inputs` to list every variable, against the new card): its four tests became one, and a prompt test that required "one row per environment variable" was reworded. `dossier check`: Tier B page and `cannalerts` `problems: 0`.
- **P13-16.** User guide section and spec rows; items 17 and 18 removed from `post-v1.md`.
- **Planted secret.** `test_env_cards_slow.py` finds neither fake secret in the page or any file under the dossier folder.
- **Row counts.** `RW`: 0 variables, 0 hits, 0 sensitive files. `BP`: 12 variables (11 before; gained `CI`), 0, 0. `CA`: 8 (5 before; gained `npm_package_name`, `services__webapi__http__0`, `services__webapi__https__0`), 0 hits, 2 sensitive files.
- **False positives.** None seen on these three. Lowercase names make a stray `process.env.<property>` possible; it would be listed, not dropped.

---

## Phase 5: Close the detection gaps

Post-v1 items 10 to 14. Branch `feat/detection-gaps`. Each task adds rows or blind-spot notes; none may change an existing row, so the golden comparison (plan 012 block P, with `BASE_SHA` set to the Phase 4 merge) must differ only by the new rows.

- [x] **P13-17. FastAPI `Depends(...)`.** Add a blind-spot rule (`rules/python/blindspot.yml`, same format as its siblings) that reports `Depends(...)` injection, and, where the dependency is a name defined in the project, a `calls`/`uses` edge from the route function. Done-check: a rule test and an adapter test on a fixture with two routes and a dependency.
- [x] **P13-18. MSW handlers.** In the JS adapter detect `http.get/post/...(` and `rest.get(...)` calls from `msw` as entry points of kind `mock-route`, with the path literal and the file and line. Do not mix them with real routes (own kind). Done-check: adapter test; the `BP` clone (`~/.cache/dossier-m6-g4vm/src/bp`) lists the handlers the reports list by hand.
- [x] **P13-19. Makefile and shell variables as inputs.** Read `${VAR}`/`$VAR` uses only where the same file defines a default (`VAR ?= x`, `${VAR:-x}`) or `export VAR`; skip everything else, to avoid false matches. Done-check: tests with a Makefile and a script on both kinds; no new row for a plain `$HOME`-style use.
- [x] **P13-20. `.cake` scripts.** Treat `.cake` as a build script: list its tasks as `build-task` items in the C# repository facts. Done-check: adapter test on a small `.cake` fixture.
- [x] **P13-21. Agent commits.** Classify a commit as an agent's when its message has an `Agent-Logs-Url:` line or a `Co-authored-by:` trailer from a known agent account (`Copilot`, `copilot-swe-agent`, `claude`). **This changes report 02's facts:** the plan allows it only for this task; update the report 02 golden (block E's baseline) and say so in Results. Done-check: classifier unit tests; the golden diff is exactly the commits named by the new rule.

**Acceptance.** Default suite green; golden comparison differs only by the new rows (list them). **Branch.** Merge, push; release with Phase 6.

### Results (Phase 5)

Done 2026-11-11 by Sonnet 5.5 on `feat/detection-gaps`. Default suite: start 2899 passed, 295 skipped; end **2942 passed, 295 skipped**. Slow, run for the adapters touched: `test_shared_layer` (all 154 semgrep rule tests), `test_py_adapter_slow`, `test_py_root_unchanged_slow`, `test_js_adapter_slow`, `test_env_cards_slow` (50 passed together), `test_cs_adapter_slow` and `test_mixed_slow` (82 passed).

- **P13-17 (FastAPI `Depends`).** New blind-spot rule `dossier.python.blindspot.dependency-injection` (pattern `dependency-injection`, registered in `checks_v7.BLIND_SPOTS` and `rules/README.md`). New `scripts/py_depends.py` adds a `ref-edge` symbol (with `via: fastapi-depends`, `from` the route function, `to` the dependency name, `line`) from the file of a function that declares `Depends(name)` to the project file that defines `name`, found through the file's own imports (absolute, relative, and `from . import deps` with `deps.name`). Not added: a dependency in the same file, a lambda, a name from outside the project, and a `Depends` outside any function (a router-level `dependencies=[...]`). Python adapter version 4 to 5. Tests: the semgrep rule test, `test_py_depends.py` (10), and an adapter test on the new fixture `tests/fixtures/pyfastapi` (two routes, one dependency imported by name and one by module attribute, and a route with a lambda). I did not add files to `pyrepo`, so the Python snapshot and the M3 to M6 pages are unchanged.
- **P13-18 (msw).** New rule `dossier.js.entry.msw-handler`: `http.<method>(...)` and `rest.<method>(...)` in a file that imports from `msw` (or `msw/...`, or requires it), with a first argument that is a string or template literal. Entry kind `mock-route`, with its own trigger text. Node's own `http.get(url, cb)` is not matched. JS adapter version 5 to 6. On `BP` the rule finds 17 handlers in each of three apps (51 rows); a hand count of the `http.<method>(` lines in `nextjs-pages/src/testing/mocks` is 17. Names read `GET ${env.API_URL}/teams` (the path as written).
- **P13-19 (Makefile and shell variables).** `repo_adapter.shell_variables` lists an `env-var` input per name, only where the file itself gives a default (`VAR ?= x` in a Makefile, or `${VAR:-x}`, `${VAR-x}`, `${VAR:=x}`, `${VAR=x}` in either, also with a doubled dollar in a recipe) or exports the bare name (`export VAR`). A plain `$HOME`, `VAR=x`, `export VAR=x`, `${VAR:?}` and `${VAR:+x}` add nothing. One row per name at its first line; values are never stored. Shell files are `*.sh`, `*.bash` and executable files with a shell shebang. Repo adapter version 6 to 7.
- **P13-20 (`.cake`).** `cs_entries.cake_tasks` lists `Task("Name")` declarations (either quote, comments ignored) as `build-task` entry points (`running dotnet cake --target Name`). C# adapter version 2 to 3. Fixture `tests/fixtures/cscake`.
- **P13-21 (agent commits).** `Co-authored-by:` trailers from Claude, Copilot and `copilot-swe-agent` were already matched by `gather.AGENT_MSG`; the new part is an `Agent-Logs-Url:` line at the start of a line, labelled Copilot. Unit tests in `test_agent_commits.py` cover both and the non-trailer cases. **Block E and the report 02 golden no longer exist** (retired with the fixture in item 7, by the author's decision), so there was no baseline to update; the V11 and V12 page checks cover report 02. The `git` extract envelope's own `version` stays `"1"`: it is not part of the cache key, so an old `extract/history.json` for the same commit may be reused until it is rebuilt (`prepare --full`).
- **Golden comparison.** Block P's comparison of extract items, for `cannalerts` (pin `5923c09`) and `BP` (pin `9506629`), `--full --no-restore`, the Phase 4 merge `7e0a9c7` (side a, in a worktree) against this branch (side b). `cannalerts`: all 14 adapter outputs identical, no added or removed row (it has no `Depends`, msw, Makefile default or agent trailer). `BP`: one difference, `entry_points` of `js` 81 to 132, which is 51 added `mock-route` rows and nothing removed; every other output is identical (`history` 71,177 rows on both sides). I did not run the `RW` or `TO` clones or the HTML report digests: no extract row changed in either run, and Phase 5 touches no rendering.
- **Not done.** `Security(...)` is not matched at all. A `Depends` given a call or an instance (`Depends(Auth())`) is a blind-spot row with no edge.

---

## Phase 6: Reference data and Tier B symbols

Post-v1 items 15 and 16. Branch `feat/refdata-and-symbols`.

- [x] **P13-22. .NET versions from `releases.json`.** Replace (or front) the endoflife.date snapshot for .NET with Microsoft's `releases-index.json` (`https://dotnetcli.blob.core.windows.net/dotnet/release-metadata/releases-index.json`): latest patch and end-of-support per channel. Keep the offline snapshot as the fallback and name the source on the card. Update `scripts/eol.json` handling and its test, including the behaviour with no network. Done-check: unit tests with a saved copy of the index; a test that the fallback is used and named.
- [x] **P13-23. Tier B symbols.** For languages with a tree-sitter grammar in `tree-sitter-language-pack` but no adapter (Shell, Rust, Go, Ruby, Java and so on, whichever the pinned pack has), list top-level definitions (functions, classes or types, modules) as symbols with path, line and kind. No call graph, no imports; the `no static graph` badge stays. Add a per-language query table in `scripts/tier_b.py` (new) and keep it small and tested. Done-check: a fixture file per language in `tests/fixtures/tierb/` and a test per language; the Shell count on `RW` is no longer zero; Tier B repositories still show the badge.

**Acceptance.** Default suite green; the six-page skeleton block X identical; `doctor` unchanged. **Branch and release.** Merge, then release **1.4.0**.

### Results (Phase 6)

Done 2026-11-11 by Sonnet 5.5 on `feat/refdata-and-symbols`. Default suite: start 2942 passed, 301 skipped; end **2957 passed, 301 skipped**.

- **P13-22 (.NET versions).** `measured_upgrade.fetch_dotnet_index` reads Microsoft's `releases-index.json` (5 s timeout) each time the upgrade-burden card is drawn; `dotnet_cycles_from_index` maps channel `10.0` to cycle `10` (`3.1` stays) and `resolve_snapshot` swaps it in for the snapshot's `dotnet` list. Any network, status or JSON failure, or `DOSSIER_OFFLINE=1`, uses the snapshot. The card caption gets a second sentence only when a .NET row exists: "from Microsoft's releases-index.json, fetched now" or "from the offline snapshot of <date> (Microsoft's releases-index.json was not reachable)". `refresh_eol.py` now fills `dotnet` from the same index (`--add dotnet` was run: 11.0 is new, 10.0 is 10.0.15). `tests/conftest.py` sets `DOSSIER_OFFLINE=1`, so no test reaches the network. Tests use a saved copy of the index, `tests/fixtures/refdata/releases-index.json`. **Note:** the card is no longer a pure function of the commit: two renders can differ when Microsoft publishes a release between them.
- **P13-23 (Tier B symbols).** New `scripts/tier_b.py` with `TierBAdapter` (name `tier-b`, version 1, registered last). Languages with a query: Shell (grammar `bash`; `.sh .bash .zsh`), Rust, Go, Ruby, Java. Only top-level definitions (queries are anchored at the root): functions, structs, enums, traits, types, modules, classes, interfaces, records, Go methods; not nested functions or members. Symbols have kind `decl` (not `def`, so dead-code, duplicate-name and public-API code is unaffected), with `path`, `line`, `name`, `symbol_kind`, `language`, `via`. No imports and no call graph, so the `no static graph` badge is unchanged. Fixtures in `tests/fixtures/tierb/` (one file per language) and a slow test per language; unit tests use a fake tree-sitter. On `RW` (the `~/.cache/dossier-m6-g4vm/src/rw` clone) Shell goes from 0 to 1 symbol (`cleanup` in `scripts/run-managed-api-tests.sh`), which matches a hand count of the 4 shell files. The `pyrepo` fixture has a shell file, so its extract now has a `tier-b` section; three tests that listed the adapters were updated. Go, Ruby, Java and Rust were not run on a real repository.
- **Checks.** Slow, run for the adapters touched: `test_tier_b_slow` (6), `test_py_adapter_slow` and `test_py_root_unchanged_slow` (22), `test_mixed_slow`, `test_js_adapter_slow`, `test_cs_adapter_slow` and `test_env_cards_slow` (106 together). The six-page block X skeleton was not re-rendered: only the text of one card caption changed and no card was added.

---

## Phase 7: Python ground truth (author with Claude)

Post-v1 item 9 (definition of done 3) and item 20. Branch `test/python-ground-truth`. **The author's own knowledge is the truth, so this phase needs the author in the session.**

- [ ] **P13-24. Choose the repository.** Ask the author which Python repository to use (default: `cannalerts`, read-only at `~/dev/projects/cannalerts`). Build its dossier with 1.4.0 into `~/.cache/dossier-p13-truth`.
- [ ] **P13-25. Matcher labels.** Fix `tests/tools/ground_truth.py` so a row's label is kept when matching (cases #86 and #87 of M5, Phase 5a); keep the C# scores unchanged (rerun block T of plan 012 against `~/.cache/dossier-m5-vWDO/truth`: entry points 98%, inputs 99%, outputs 93%). Done-check: a unit test for the two cases, and the C# scores.
- [ ] **P13-26. Truth.** With the author, write the truth file the way the C# one was written (see `~/.cache/dossier-m5-vWDO/truth/` for the format): entry points, inputs, outputs, components, **without reading the dossier first**. The author states the items; Claude only writes them down and asks about anything unclear. Store it under `~/.cache/dossier-p13-truth/truth/` and keep it (never delete ground truth).
- [ ] **P13-27. Score.** Run `tests/tools/ground_truth.py` against the dossier. Targets from the spec's definition of done: entry points recall at least 96% and precision 100%, inputs at least 94%, outputs at least 91%. For each disagreement the author rules: dossier wrong, blind spot (needs a Gaps entry or a rule), or no error. Record the figures and every ruling in Results; fix what the rulings ask for only if it is a crash or a regression, otherwise add it to `docs/post-v1.md`.

**Acceptance.** The figures and rulings are recorded; the truth folder path is recorded; the default suite is green. **Branch.** Merge, push; release a patch only if a fix was needed.

### Results (Phase 7)

*(not started)*

---

## Last: wrap up

After Phase 7 move every finished item out of `docs/post-v1.md` (keep only what was cut or newly found), update `docs/developer-guide.md` if the workflow changed, and add a one-line note under each phase's Results of the release it went out in (`git ls-remote --tags origin`).
