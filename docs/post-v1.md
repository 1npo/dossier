# After 1.4.0

What is left after [plans/013-post-v1-plan.md](plans/013-post-v1-plan.md): items that were cut, skipped or newly found. Everything else from the old list shipped in 1.2.0 to 1.4.0; see the Results of that plan. Work that the spec itself defers (cross-repository views, running the target's tests, uncommitted work, a custom Roslyn analyser) is listed in [plans/004-v1-spec.md](plans/004-v1-spec.md), section 1.

Plan documents quote commit hashes from before the repository was split out of `encamp`; those hashes no longer resolve. Use `git log --grep` on the subject instead.

## Decided against

- **The interactive graph.** M6 built it (D7 of [plans/012-m6-plan.md](plans/012-m6-plan.md)); the author reviewed it on 2026-11-10 and removed it. The component map and dependency graph cards are back to static diagrams plus tables.
- **Python ground truth (was item 9, Phase 7).** Skipped on 2026-11-11: the author does not know the current `cannalerts`, so no independent truth exists. Definition of done 3 is therefore not measured for Python. Revisit when the author has a Python repository they know.

## Open

1. **Correct TS and C# against real codebases (ongoing).** The 1.0.0 results come from public repositories because the author has none of their own in those languages. When the author takes over TS and C# code at work, they correct rules, entry-point kinds, what counts as an entity, and the public API as they learn (spec decisions 33 and 34).
2. **FastAPI `Security(...)` and `Depends(Auth())`.** `Security(...)` is not matched at all; a `Depends` given a call or an instance is a blind-spot row with no edge (Phase 5 Results).
3. **C# configuration binding as inputs.** Its keys are not environment variable names, so the env-vars card skips them (Phase 4 Results).
4. **Tier B symbols on real repositories.** Go, Ruby, Java and Rust were tested on fixtures only (Phase 6 Results).
5. **The upgrade-burden card is not a pure function of the commit.** It reads Microsoft's `releases-index.json` at render time; two renders can differ (Phase 6 Results). Decide whether to pin the fetch date in the build.
