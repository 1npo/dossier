# Package data

Files the `dossier` package reads. Code reaches them only through `dossier.resources.data(...)`, which returns a real path under this folder.

| Path | Read by | How it is used |
|---|---|---|
| `schemas/cards/` | `core.schema`, `findings.candidates` | card schemas, one JSON file per report |
| `schemas/summary.schema.json` | `render.summary_check` | check V8 on `summary.json` |
| `rules/{all,python,js,csharp}/` | the language adapters | Semgrep rules, passed to `semgrep` by path |
| `assets/` | `render.page` | page template, CSS and JS, inlined into the page |
| `vendor/` | `render.page` | Basecoat and Mermaid bundles with their licences, inlined |
| `tools.json` | `tooling.toolcheck` | the tools dossier checks for, with versions |
| `eol.json` | `render.measured.upgrade` | end-of-life dates for the upgrade card |
| `workers/` | `tooling.shared_tools` | three locked worker scripts, run with `uv run --locked --script` |
| `node/` | `adapters.js.tools`, `adapters.python.scip` | Node helper projects, copied to the cache and installed with `npm ci` |

Never edit the vendored bundles in `vendor/`. Refresh `eol.json` with `tools/refresh_eol.py`.
The workers stay plain scripts: they run in their own environments, so each has a `.lock` file beside it and no `__init__.py`.
