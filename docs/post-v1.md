# After 1.4.0

What is left after [plans/013-post-v1-plan.md](plans/013-post-v1-plan.md): items that were cut, skipped or newly found. Everything else from the old list shipped in 1.2.0 to 1.4.0; see the Results of that plan. Work that the spec itself defers (cross-repository views, running the target's tests, uncommitted work, a custom Roslyn analyser) is listed in [plans/004-v1-spec.md](plans/004-v1-spec.md), section 1.

Plan documents quote commit hashes from before the repository was split out of `encamp`; those hashes no longer resolve. Use `git log --grep` on the subject instead.

## Decided against

- **The interactive graph.** M6 built it (D7 of [plans/012-m6-plan.md](plans/012-m6-plan.md)); the author reviewed it on 2026-11-10 and removed it. The component map and dependency graph cards are back to static diagrams plus tables.
- **Python ground truth (was item 9, Phase 7).** Skipped on 2026-11-11: the author does not know the current `cannalerts`, so no independent truth exists. Definition of done 3 is therefore not measured for Python. Revisit when the author has a Python repository they know.

## Open

1. **The upgrade-burden card is not a pure function of the commit.** It reads Microsoft's `releases-index.json` at render time; two renders can differ (Phase 6 Results). Decide whether to pin the fetch date in the build.

## Done since 1.4.0

- **C# configuration binding as inputs** (was item 1). Keys read through `IConfiguration` are a new input kind, `config-key`, drawn as a separate **Configuration keys** group under the Inputs card; see the user guide. Names only, never values. Not done: keys that appear only in `appsettings.json` (the file is still a `config-file` row) and keys built at run time.
