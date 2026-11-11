# After 1.0.0

Things to consider after 1.0.0, in a proposed order. Nothing here is planned yet: the author reviews the order, then each group gets a plan in `docs/plans/`. Work that the spec itself defers (cross-repository views, running the target's tests, uncommitted work, a custom Roslyn analyser) is listed in [plans/004-v1-spec.md](plans/004-v1-spec.md), section 1.

Plan documents quote commit hashes from before the repository was split out of `encamp`; those hashes no longer resolve. Use `git log --grep` on the subject instead.

## Decided against

- **The interactive graph.** M6 built it (D7 of [plans/012-m6-plan.md](plans/012-m6-plan.md)); the author reviewed it on 2026-11-10 and removed it. The component map and dependency graph cards are back to static diagrams plus tables.

## Proposed order

### 1. Make builds trustworthy (bugs found in M6)

Do these first: each one can make a build silently wrong or hide a failure.

1. **Verifier verdicts disappear.** Between two steps of the M6 run, `RW`'s build still said `verify: true` but its recorded verdicts were gone, and `render` failed with V10. Cause unknown; re-running `verify-record` fixed it. Find what clears them.
2. **`prepare` keeps a stale `extract/` after the skill changes.** Same commit and ref reuse the old extract, so an adapter fix does not show. Decide whether the skill version (or an adapter version) joins the cache key.
3. **`soft_failure` misses real scip-dotnet logs.** It only matches lines that start with `Failure:`; real logs put a timestamp and `fail:` first, so the "could not load every project" problem is never reported. The dead-code list already skips unloaded projects; decide whether the page should also name which projects did not load.
4. **Verdicts for claims without an `id`.** They are keyed by a hash of the claim text, so rewording a claim drops its verdict and its Gaps item. Give every sampled claim an id, or key by citation.

### 2. Clean up the split and the graph removal (small, mechanical)

7. **Retire the M0 fixture, `migrate` and `DOSSIER_SUBJECT_REPO`. Done (2026-11-11).** The M3 to M6 slow-suite pages and `test_check_page_slow.py` are built from `tests/fixtures/pyrepo`; `migrate`, `migrate_map.json`, the fixture line in `.gitignore`, `DOSSIER_SUBJECT_REPO`, the `golden02` test, tool and baselines are deleted (the V11 and V12 page checks still cover report 02). The local folder `tests/fixtures/encamp-m0/` is no longer used and can be removed.
8. **One test counts differently in a fresh clone** (2901 passed against 2902 in the working tree). Find which and why.


### 3. Finish v1's open acceptance item

9. **Python ground truth.** Definition-of-done item 3 is still open for Python: the author's own knowledge of a Python repository (for example `cannalerts`), scored the way the C# truth was (`tests/tools/ground_truth.py`). TS has none by decision (risk 4 of the M6 plan).

### 4. Close detection gaps (each adds missing rows; none changes existing ones)

10. **FastAPI `Depends(...)`.** Dependency injection through `Depends` is not followed and no blind-spot rule reports it. It is the one Python DI case worth a rule (spec decision 11).
11. **MSW mock handlers.** `http.get(...)` handlers are not detected as entry points (found on `BP`). Only adds missing mock routes. (P5-1, ruled in [plans/010-m4-plan.md](plans/010-m4-plan.md), "Results (Phase 5)".)
12. **Makefile and shell variables as inputs.** Dockerfile `ENV`/`ARG` and compose `environment:` are read; Makefile and script variables are not, because without a shell parser too many matches are false.
13. **`.cake` build scripts.** Cake scripts in C# repositories are not read.
14. **Agent commits classed as human.** Commits by an agent such as Copilot carry an `Agent-Logs-Url` line but are classified as human. The classifier feeds report 02, which M6 could not change.

### 5. Freshness of reference data

15. **.NET versions from `releases.json`.** The end-of-life snapshot comes from endoflife.date, which lags runtime releases (it listed 10.0.13 as latest after 10.0.14 shipped). Microsoft's own `releases.json` is current.

### 6. Features to reconsider

16. **Tier B symbols.** Shell, Rust and other languages without a Tier A adapter get counts and a file list but no tree-sitter symbols. The `no static graph` badge says what is missing.

### 7. Ongoing, driven by the author's work

19. **Correct TS and C# against real codebases.** The 1.0.0 results come from public repositories because the author has none of their own in those languages. When the author takes over TS and C# code at work, they correct rules, entry-point kinds, what counts as an entity, and the public API as they learn (spec decisions 33 and 34).

### 8. Test tooling idea (lowest priority)

20. **Ground-truth matcher labels.** `tests/tools/ground_truth.py` drops a row's label when matching; M5 noted two cases (#86 and #87).
