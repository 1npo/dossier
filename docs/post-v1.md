# After 1.0.0

Things to consider once dossier 1.0.0 is done. Nothing here is planned yet. Each entry says what it is, why it was left out, and where it was decided. Work that the spec itself defers (cross-repository views, running the target's tests, uncommitted work, a custom Roslyn analyser) is listed in [plans/004-v1-spec.md](plans/004-v1-spec.md), section 1.

## Cards to consider re-adding

- **Environment variables.** The measured panel "Environment variables read by the code" (anchor `facts-env_vars`, drawn by `panel_env` in `render.py`) listed the variables the gatherer found by pattern matching. It was removed in M0 because the 1.0.0 card set has no place for it: `ops.config-secrets` and `io.inputs` hold the written account of configuration instead. It also capped its rows, which goes against the spec's "no caps" principle. Citations of `facts:env_vars` now link to the repository overview card. Decided in [plans/005-m0-plan.md](plans/005-m0-plan.md), question Q4.
- **Secrets.** The measured panel "Secret scan" (anchor `facts-secret_signals`, drawn by `panel_secrets`) listed files and lines that looked like committed secrets. It was removed in M0 for the same reasons. Citations of `facts:secret_signals` now link to the repository overview card. If it returns, it must still not present dossier as a security scanner (spec section 1, permanent non-goals). Decided in [plans/005-m0-plan.md](plans/005-m0-plan.md), question Q4.
