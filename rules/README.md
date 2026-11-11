# Semgrep rules

Semgrep rules shipped with dossier live here, one folder per scope. The `python/`, `js/` and `all/` rules exist and are used by the Python, JavaScript and repository adapters; the `csharp/` rules (C#, `languages: [csharp]`, test files are `.cs`) are used by the C# adapter. The `js/` rules cover both JavaScript and TypeScript (`languages: [js, ts]`) and their test files are `.ts`; they use `// ruleid:` and `// ok:` comments, and so do the `csharp/` ones. A C# test file is parsed as one C# file, so keep type declarations at the end of it. A `// ruleid:` comment must sit on the line above the first line of the match; one line matched by two rules takes one comment with the ids separated by commas. Rule files are YAML and end in `.yml`. Rule ids are `dossier.<scope>.<family>.<name>`.

Every rule has `metadata`:

- `category`: the `io_candidates` category the rule feeds, or `entry` (an entry point, with `kind`), or `blindspot` (with `pattern`, the blind-spot id).
- `detail` (optional): a regular expression. Its first group, applied to the matched text, becomes the finding's `detail` (for example the name of an environment variable). Semgrep hides matched text and metavariables unless you are logged in, so dossier reads the match from the source file instead.

Categories: `cli-args`, `env-var`, `config-file`, `file-read`, `stdin`, `message-consume`, `db-connect`, `db-access`, `global-state`, `cache`, `thread`, `async`, `process-pool`, `lock`, `queue`, `stdout`, `file-write`, `outbound-call`, `message-produce`, `exit-code`, `error-response`, `log`, `metric`, `trace`, `retry`, `timeout`, `catch-all`, `transaction`.

Blind-spot ids (code that static analysis may miss): `dynamic-import`, `entry-point-loading`, `string-plugin`, `decorator-registry`, `getattr-dispatch`, `django-apps`, `django-signals`, `pytest-fixtures`, `computed-subcommand`, `string-route`, `route-mount`, `barrel-reexport` (Python); `dynamic-import`, `dynamic-require`, `barrel-reexport`, `react-context`, `hook-wiring`, `string-route`, `route-mount`, `module-federation`, `di-registration`, `computed-subcommand` (JavaScript and TypeScript); `conventional-route`, `di-registration`, `di-resolution`, `di-scan`, `mediator-handler`, `mvc-filter`, `partial-class`, `reflection`, `route-convention`, `route-mount`, `source-generator`, `string-route` (C#); and `codegen`, `feature-flag` (all languages).

The Python rules `string-route` (a route path that is not a literal), `route-mount` (FastAPI, Flask, Starlette and Django prefixes and includes) and `barrel-reexport` (`from x import *`) are in `python/blindspot.yml`. `barrel-reexport` is a regular expression that matches in any file, because Semgrep's test files cannot be named `__init__.py`; the Python adapter keeps only the hits in `__init__.py`.

Each rule file has a test file under `tests/fixtures/semgrep/` with the same name; run them all with `DOSSIER_SLOW=1 uv run --with pytest --with pygments python -m pytest tests/integration/scripts/test_shared_layer.py -q` from the skill folder (it runs `semgrep --test` through the worker).
