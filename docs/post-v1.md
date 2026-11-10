# After 1.0.0

Things to consider once dossier 1.0.0 is done. Nothing here is planned yet. Each entry says what it is, why it was left out, and where it was decided. Work that the spec itself defers (cross-repository views, running the target's tests, uncommitted work, a custom Roslyn analyser) is listed in [plans/004-v1-spec.md](plans/004-v1-spec.md), section 1.

## Cards to consider re-adding

- **Environment variables.** The measured panel "Environment variables read by the code" (anchor `facts-env_vars`, drawn by `panel_env` in `render.py`) listed the variables the gatherer found by pattern matching. It was removed in M0 because the 1.0.0 card set has no place for it: `ops.config-secrets` and `io.inputs` hold the written account of configuration instead. It also capped its rows, which goes against the spec's "no caps" principle. Citations of `facts:env_vars` now link to the repository overview card. Decided in [plans/005-m0-plan.md](plans/005-m0-plan.md), question Q4.
- **Secrets.** The measured panel "Secret scan" (anchor `facts-secret_signals`, drawn by `panel_secrets`) listed files and lines that looked like committed secrets. It was removed in M0 for the same reasons. Citations of `facts:secret_signals` now link to the repository overview card. If it returns, it must still not present dossier as a security scanner (spec section 1, permanent non-goals). Decided in [plans/005-m0-plan.md](plans/005-m0-plan.md), question Q4.

## Correct TS and C# against real codebases

The TS and C# results in 1.0.0 are measured on public repositories, because the author has none of their own and is new to both languages. When the author takes over TS and C# codebases at work, they will learn them and correct dossier as they go: rules, entry-point kinds, what counts as an entity, and the public API. Decided in the M4 plan review (spec decisions 33 and 34).

## Findings deferred from the M4 review

- **P5-1, MSW part.** MSW mock handlers (`http.get(...)`) are not detected as entry points (found on `BP`; the `BP` reports list them by hand). Deferred because it only adds missing mock routes; the Axios false entry points were fixed in the M4 follow-up.

Ruled on 2026-11-08 in [plans/010-m4-plan.md](plans/010-m4-plan.md), "Results (Phase 5)". P4-3 (names of Nx targets and package scripts) was found fixed in M6 and removed.

## Left out of 1.0.0

Each was considered during M6 and left out. Decided in [plans/012-m6-plan.md](plans/012-m6-plan.md).

- **Tier B symbols.** Languages without a Tier A adapter (Shell, Rust and the rest) get counts and a file list but no tree-sitter symbols. Left out because the spec's cut line puts "Tier B polish" second, and the `no static graph` badge already says what is missing (section 3, row 5).
- **Makefile and shell variables as inputs.** Dockerfile `ENV` and `ARG` and compose `environment:` are read; variables in Makefiles and scripts are not. Left out because without a shell parser too many matches are false (finding 2 of M5, Phase 5).
- **`.cake` build scripts.** Cake scripts in C# repositories are not read. Found on a public C# repository in M5, Phase 2.
- **FastAPI `Depends(...)`.** Dependency injection through `Depends` is not followed, and no blind-spot rule reports it. Decision 11 of the spec leaves Python DI alone; `Depends` is the one case worth a rule.
- **.NET versions from Microsoft's `releases.json`.** The end-of-life snapshot comes from endoflife.date, which lags the runtime releases (it listed 10.0.13 as latest when 10.0.14 had shipped). Microsoft's own `releases.json` would be current. Found in M5, Phase 5, finding 5.
- **Agent detection from `Agent-Logs-Url`.** Commits by an agent such as Copilot are classed as human although their messages carry an `Agent-Logs-Url` line. The classifier feeds report 02, which M6 may not change (M5, Phase 5, finding 10).
- **Ground-truth matcher labels.** `tests/tools/ground_truth.py` drops a row's label when matching; M5, Phase 5a, noted two cases (#86 and #87). A test-tool idea only.
- **Verifier verdicts for claims without an `id`.** A saved verdict is keyed by the claim's id, or by a hash of its text when it has none. If a later build rewords such a claim, the verdict stops matching and its Gaps item disappears at the next render. Give every sampled claim an id, or key verdicts by citation. Found in M6, Phase 4.
