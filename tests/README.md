# Tests

| Folder | What is in it | Who runs it | Slow rule |
|---|---|---|---|
| `unit/dossier/` | one test file per module, mirroring `src/dossier/` (`unit/dossier/render/test_page.py` tests `render/page.py`); `unit/tools/` tests the scripts in `tools/` | `pytest`, always | none: fast, no network, no real tools |
| `integration/dossier/` | tests that run real tools or real git, mirroring `src/dossier/` the same way | `pytest`; files named `*_slow.py` (and three others) skip unless `DOSSIER_SLOW=1` | slow files carry a `skipif` on `DOSSIER_SLOW` and need the network |
| `content/` | tests of the repository's files rather than of a module: docs drift, prompts, rules, schemas, release metadata, the launchers, fixture repositories, this tree's layout | `pytest`, always | none |
| `support/` | scaffolding the tests import: repository builders (`repos.py`), paths (`paths.py`), fakes, shared slow-test fixtures, the page builders `m3_page.py` to `m6_page.py` and the browser probes | imported by tests; the page builders and probes also run as scripts | none |
| `fixtures/` | the fixture repositories and data files | read by tests; never edited | none |

`conftest.py` holds only fixtures; its builders live in `support/repos.py`. `support/` is on pytest's `pythonpath`, so a test imports `from repos import build_py_repo` or `from paths import SKILL_ROOT`. A test module never imports another test module, and never computes a path from `__file__`.

## Running

From the repository root:

```sh
uv run pytest -q                                   # the default suite
DOSSIER_SLOW=1 uv run pytest -q --basetemp=$HOME/.cache/dossier-slow   # the slow suite, with the network; run it alone
```

Never point `--basetemp` at `/tmp`. `tests/content/test_tests_layout.py` guards the layout described here.
