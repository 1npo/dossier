# Plan 006: milestone M1 (checkout, preflight, doctor, clean, run record, process card, V9, V10, restore hygiene, adapter interface, shared tree-sitter and semgrep layer)

Status: written by Opus on 2026-11-01. **Not yet reviewed.** It was written from `plans/004-v1-spec.md`, `docs/process.md`, `plans/005-m0-plan.md` and the code at commit `2c8a718` (version 0.5.0, M0 merged). Writing it changed no other file.

Paths used below (the planning prompt gave `~/encamp/...`, which does not exist on this machine):

- `SKILL` = `/home/nick/dev/projects/encamp/configs/user/claude/.claude/skills/dossier`
- `FIX` = `SKILL/tests/fixtures/encamp-m0`: the frozen, git-ignored M0 fixture (see plan 005). It is read-only. Never write into it.
- `REPO` = `/home/nick/dev/projects/cannalerts`: the real Python repository used for the exit criterion. It has `pyproject.toml`, `uv.lock`, 158 tracked files, 129 commits, branch `main`, and `origin/HEAD -> origin/main`.
- Run the tests from `SKILL`: `uv run --with pytest --with pygments python -m pytest tests -q`. **Baseline before M1: 227 passed.**

---

## 1. Summary

- `prepare` gains the spec's front half: pin and trusted-ref check, preflight (tools per language, pinned in a new `scripts/tools.json`), a verified clean checkout in the per-repository working area `~/.local/cache/dossier/<repo>/`, an optional lockfile-only restore, and an extract stage with the path filter. New commands `doctor` and `clean`; new flags `--allow-missing`, `--no-restore`, `--allow-ref`, `--submodules`, `--restore yes|no`.
- Every stage appends to a crash-safe run record `<home>/<repo>/build.json`. `render` adds its own records, checks V10 (every fixed step has a record or a reason, error) and V9 (path filter counts, info), and draws the `dossier.process` card from the record. Missing tools, skipped or failed stages and Tier B languages become Gaps coverage items.
- Child processes for restores and tools run through one safe runner (`scripts/sandbox.py`): empty environment plus an allowlist, scratch `HOME`, private caches, process-group timeout. A fixture repository proves each rule (spec section 11, item 4).
- The adapter interface (`scripts/adapters.py`) and the shared tree-sitter and semgrep layer (`scripts/shared_tools.py` with two locked inline worker scripts) exist and are tested with a fixture adapter. No real language adapter yet (that is M2).
- `VERSION` goes to 0.6.0.

---

## 2. Shared rules (read before any task)

- **Branch.** Work on `feat/dossier-m1`, created from `main`. One commit per task. Follow the `git-commit` skill (identity, message style) and the `git-workflow` skill (branching, merging, pushing). Commit messages below are suggestions in the style of the M0 commits (`feat(dossier): …`, `test(dossier): …`, `docs(dossier): …`, `chore(dossier): …`).
- **Skills to load at the start:** `git-commit`, `git-workflow`, `py-projects`, `py-unit-tests`, `git-release` (for M1-15), `claude-planning-docs` (for writing results back into this plan), `docs-project` and `docs-readme` (for M1-14).
- **Never touch:** report 02 (the `overview` report: `panel_git`, `panel_contributors`, `panel_dependencies`, the knowledge map, the calendar and their CSS/JS), and the M0 card schemas in `prompts/schema/*.json` (ids, titles, tiers, shapes, columns). The only schema-adjacent change in M1 is that `render.py` draws real content in the existing `dossier.process` card. `prompts/method.md` and `prompts/reports.md` are not edited (M2). `FIX` is never written. Nothing under `/home/nick/dev/dossiers/` is read or written; every command that builds or renders sets `DOSSIER_HOME`, `DOSSIER_CONFIG` and `DOSSIER_CACHE` to a scratch directory.
- **No sandboxing.** Restores run on the host with the user's privileges (spec decision 5). Do not add containers, namespaces, seccomp, `unshare` or similar. The hygiene rules in spec 5.4 are the whole of it.
- **No new runtime dependencies** in `scripts/dossier.py` (it stays standard library plus `pygments`). The two worker scripts declare their own pinned dependencies inline and are locked with `uv lock --script`.
- **Tests:** follow `py-unit-tests`. Unit tests go in `tests/unit/scripts/test_<module>.py`; tests that start real processes or real git go in `tests/integration/scripts/`. Tests that need the network are skipped unless `DOSSIER_SLOW=1` is set (`pytest.mark.skipif(os.environ.get("DOSSIER_SLOW") != "1", reason="needs the network: set DOSSIER_SLOW=1")`). The full suite must pass after every task.
- **Plain language** in every message a user of the dossier reads (CLI output, card text, Gaps statements). Full sentences, no jargon where a plain word works.
- **If the code contradicts this plan, stop and report.** Do not improvise a design. Record what you found under "Verification results".
- **Report 02 guard.** After every task that edits `scripts/render.py`, run section 6 block E. It must print `OK`.

---

## 3. Spec versus code

"Absorb" = the plan handles it as proposed. "Decision" = the human must answer first (section 7 lists these as questions; each has a default the plan uses if the answer is "go ahead").

| # | Area | Spec says | Code does today | Proposal | Class |
|---|---|---|---|---|---|
| 1 | What `prepare` does, in what order | 5.1: 1 preflight, 2 checkout, 3 restore, 4 extract, 5 path filter, 6 facts/chunks/update plan as today, 7 run record | `cmd_prepare` (`dossier.py:193`): `toplevel` → `out_dir` → `load_state` → `gather.collect(top, ref, …)` (resolves the SHA inside) → `gather.delta` → `update_plan` → write `facts.json`, `chunks.json`, `activity.json`, `knowledge.json`, `dependencies.json`, `state.json` → print JSON. No preflight, checkout, restore, extract or run record. | New order: **pin** (resolve the SHA once, trusted-ref check) → **tools** (preflight) → **copy** (checkout, then restore) → **extract** (adapters, path filter, HEAD check) → **measure** (`gather.collect` and everything after it, unchanged) → print JSON. The stage code lives in a new `scripts/stages.py`; `cmd_prepare` calls it. `gather.collect` keeps its `ref` argument (so the branch label stays right) and `cmd_prepare` checks that the SHA it returns equals the pinned SHA, and stops with "The ref moved while prepare was running. Run it again." if not. | Absorb |
| 2 | Which steps read the checkout | 5.1 step 6: git-history facts keep reading the original repository's objects | `gather.collect` never reads the working tree: it uses `git ls-tree`, `cat-file --batch`, `log`, `blame`, `check-attr --source` at the SHA. The one exception is `git status --porcelain` for the "uncommitted changes" warning when `ref == HEAD`. `deps.analyze` reads blobs through the same `Repo`. `render.Cites` reads blobs from `facts.repo.path` (the original repository). | Only restores and extractors use the checkout. `gather`, `deps`, `render.Cites`, the trusted-ref check and `update_plan`'s diffs keep reading the original repository. Nothing in `gather.py`, `deps.py` or `render.Cites` changes. | Absorb |
| 3 | Where state and outputs live | Two places: the working area `~/.local/cache/dossier/<repo>/` (checkout, scratch `HOME`, caches; regenerable) and the output folder `<home>/<repo>/` (worth keeping). Root configurable with `cache_dir` in the home config. | Only the output folder exists: `out_dir()` gives `<home>/<name>/`, or `<home>/<name>-<root6>/` when another repository already uses the name. Holds `state.json`, `facts.json`, `chunks.json`, `notes/`, `reports/`, three data files and the HTML. | Working area = `<cache root>/<basename of out_dir>/`, so the collision suffix carries over. Cache root = `DOSSIER_CACHE` env var (for tests), else `cache_dir` from the config, else `~/.local/cache/dossier`. The area holds `owner.json` (`{"repo": top, "root_commit": root}`; a mismatch is an error naming both paths), `checkout/`, `home/`, `cache/`, `logs/`. `build.json`, `build.prev.json` and `extract/` go in the output folder (D11). | Absorb |
| 4 | The home config | `cache_dir` and `registry_auth` in "the dossier home config" | The config exists: `CONFIG = $DOSSIER_CONFIG or ~/.config/dossier/config.json`, today `{"home": …}`. **`cmd_home` rewrites the whole file as `{"home": …}`**, so it would delete any other key. | New `scripts/config.py` owns the file: `load()`, `update(**keys)` (read, merge, atomic write), `home()`, `cache_root()`, `timeouts()`, `registry_auth()`. `cmd_home` uses `update(home=…)`. Keys: `home`, `cache_dir`, `registry_auth`, `timeouts`. | Absorb |
| 5 | `state.json` and the restore answer | 5.1 step 3: ask once per repository, store the answer in `state.json` | `dossier.py` owns `state.json` (`load_state` = `resolve.migrate(load(...))`, `save_state` keeps a backup when the version changes). `resolve.py` only adds keys (`history`, `corrections`, `contributor_types`, `tracked`, `resolutions`, `next_item`). `incremental.py` never reads state; `update_plan` in `dossier.py` reads `last_sha` and `pending_update`. | New key `state["restore"] = {"answer": "yes"|"no", "date": "…", "ecosystems": ["python"]}`, written only by `dossier.py`. `resolve.migrate` is not changed (absent means "not asked yet"). | Absorb |
| 6 | Asking the restore question | "Before the first restore of a repository, ask once, naming what will run" | `prepare` is run by Claude without a terminal; it cannot ask. | `prepare` stops before the restore with exit code 3 and prints `{"stopped": "restore_question", "will_run": [...]}`. Claude asks the user and runs `prepare` again with `--restore yes` or `--restore no`, which stores the answer. The checkout is kept, so the second run is quick. | **Decision** (Q2) |
| 7 | Language detection for preflight | 5.1 step 1: "Detect languages (gatherer already classifies them)" | `gather.collect` builds `languages` during its full pass (extension, file name, then `#!` line), after blame and history. Preflight must run before that. | New `toolcheck.languages_at(top, sha)`: `git ls-tree -r --name-only <sha>`, skip paths where `gather.noise_reason(p)` is set, classify with `gather.lang_of(p)` only (no blob reads, so no `#!` detection), keep languages of kind `code`. Tier A = Python, JavaScript, TypeScript, C#; everything else Tier B. A shebang-only script is missed by preflight but still counted by the gatherer; acceptable because no Tier A tool depends on shebang files. | Absorb |
| 8 | Tools per language | 6.2: host needs `git` and `uv` always, Node and npm for Python/JS/TS, .NET SDK for C#; everything else installs itself | Nothing. `check_page.py` declares `playwright` unpinned; `dossier.py` declares `pygments` unpinned. | `scripts/tools.json` (D1) lists host tools with minimum versions and install hints, and self-installing tools with pinned versions and their source URLs. Node minimum differs by language (16 for Python because of scip-python, 22 for JS/TS because of scip-typescript and dependency-cruiser). The `check_page.py` and `pygments` pins are out of scope (they are the skill's own tooling, not extractors) and stay as they are. | Absorb |
| 9 | Missing tools under `--allow-missing` | "every missing tool becomes a coverage item in Gaps and the affected cards are badged 'partial'" | Gaps items come only from claims in the reports and from `reports/gaps.json` (`render.collect_gaps`). No automatic items. No mapping from tools to cards. | M1 adds automatic coverage items from `build.json` (missing tools, Tier B languages, skipped or failed stages, submodules not analysed) through `collect_gaps(reports, extra=…)`. The "partial" badge needs a tool-to-card map that only exists once adapters exist, so it moves to **M2**. | Absorb (spec issue 8) |
| 10 | Incremental builds keyed by `(sha, extractor version)` | 5.3 | `update_plan` and `incremental.plan` decide staleness from citations, diffs and corrections; nothing about extractors. | M1 builds the store and the reuse check: each `extract/<output>.json` holds one section per adapter with its `version`, tool versions and `sha`; an adapter whose key matches is not re-run (status `reused`). M1 adds the tool versions to the key (a tool upgrade changes output). "A report is stale if its extractor output changed" needs reports that cite extractor output, so it is **M2**. "M-tier cards are always recomputed" is already true (render draws them every time). | Absorb (spec issue 24) |
| 11 | The `dossier.process` card | Tier M, written by a script from `build.json`, a numbered list of 8 to 10 steps, each with one sentence and a run record, ending with a line counting measured, adjudicated and read cards | M0 added it to `prompts/schema/dossier.json` as `computed`, writer `script`, no columns, and `build_page` draws `placeholder_body` for it (`render.py`, `rid == "dossier"` branch). | `scripts/process.py` draws it from `build.json` (D3, M1-11). The schema entry is unchanged. Without a `build.json` it keeps the placeholder and V10 reports the error. | Absorb |
| 12 | "The fixed process list" for V10 | V10: "a record for every step in the fixed process list" | — | The list is defined, in plain words only, in spec section 4 (01): ten numbered steps. It has no ids. The plan gives them ids in order: `pin`, `tools`, `copy`, `measure`, `extract`, `read`, `write`, `check`, `gaps`, `render`. The card always shows all ten (spec says "8 to 10"; spec issue 6). | Absorb |
| 13 | Who records steps 6, 7 and 9 | Step 7 (5.1): "every stage appends … subagent count, reports rewritten versus reused". "Claude never edits this file." | Reading the code, writing the reports and the Gaps entries are done by Claude between `prepare` and `render`. | `render` writes those records itself from files it can see: the reading plan and cached-note count that `prepare` stored in the `measure` record, the update plan (`stale`/`fresh`), the report files present, and the open-item counts. The number of parallel readers is the one thing no file holds; `render --readers N` lets Claude pass it, and the card says "as reported by Claude". Without the flag the card says "not recorded". | **Decision** (Q3) |
| 14 | Step 8 includes "the page was opened in a real browser" | §4, step 8 | `check_page.py` runs after `render` has written the page. | `check_page.py --record <build.json>` appends a `check`/`browser` record. The card shows the latest one with its time ("The page was last opened in a real browser at 12:04 UTC: 0 problems"), or "not run yet". SKILL.md step 7 adds one final `render` after a passing check so the shipped page shows it. | **Decision** (Q4) |
| 15 | Restore in M1 | 5.1 step 3, 5.4: `npm ci --ignore-scripts`, `uv sync --frozen`, `dotnet restore --locked-mode` | Nothing. | The restore stage is complete (lockfile detection, ask-once answer, `--no-restore`, trusted-ref gate, runner, timeout, authentication-failure reason, Gaps). Python's `uv sync --frozen` is enabled (M2's scip-python wants an installed environment). npm and NuGet entries exist in `tools.json` with `"enabled": false` and are skipped with the reason "Installing npm dependencies arrives in a later version." M4 and M5 turn them on. Only lockfiles at the repository root are detected (spec issue 20). | **Decision** (Q9) |
| 16 | Hygiene with no extractors | 5.4 applies "to every restore and to every Node and .NET extractor" | Nothing. | One reusable runner, `sandbox.run()` (D4), used by the restore stage, by the shared layer, and (from M4/M5) by Node and .NET adapters. The adapter flag `loads_repo_code` makes `run_extract` apply the trusted-ref rule to an adapter. The §11 item 4 test drives the real restore stage with a fixture repository whose `install.sh` writes out its environment (M1-7). | Absorb |
| 17 | Path filter and HEAD check | 5.1 step 5 | Nothing. | `adapters.filter_paths()` runs inside `run_extract` on every adapter's output (D6). `run_extract` checks `HEAD == sha` and a clean tracked tree before and after. | Absorb |
| 18 | Tier "1"/"2" | 5.1 step 3 says "Restore (Tier 2 only)" and "falls back to Tier 1" | Spec 6.3 defines only Tier A and Tier B. | Treated as "with installed dependencies" versus "without". A failed restore is recorded in Gaps; adapters see `ctx.restored[ecosystem] = False`. | Absorb (spec issue 2) |
| 19 | Submodules | 5.4 rule 5: off by default; `--submodules` turns them on and is recorded; when off, Gaps lists them | `gather.collect` already lists them in `facts.repo.submodules` (tree entries of type `commit`). | The checkout never inits submodules unless `--submodules` (then `git submodule update --init --recursive`). The `copy`/`checkout` record lists them; each becomes a Gaps coverage item when off. | Absorb |
| 20 | Timeouts | 5.4 rule 6: per-stage wall-clock timeout, configurable | `gather` has `BLAME_BUDGET_S = 150` and a 60 s per-file blame timeout; nothing else. | Config key `timeouts` with defaults `{"restore": 900, "extract": 1800, "tool": 600}` (seconds) in `config.py`. `gather`'s own limits stay. | Absorb |
| 21 | `registry_auth` | 5.4 rule 2: list of variables or config files per ecosystem, default empty | Nothing. | Config `registry_auth = {"python": ["UV_INDEX_MYCORP_PASSWORD"], "npm": ["NPM_TOKEN", "~/.npmrc"], "nuget": [...]}`. A bare name is an environment variable passed through. An entry starting with `~/` is a file copied into the scratch `HOME` at the same relative path (files outside your home folder are refused). For npm, a copied `~/.npmrc` replaces the empty `npm_config_userconfig`. | Absorb (spec issue 17) |
| 22 | `clean` | 5.2 "removes cached checkouts"; 5.4 rule 3 "removes the whole working area" | Nothing. | `clean [repo]` removes the whole working area of that repository and nothing else (never the output folder). | Absorb (spec issue 19) |
| 23 | Process card footer | "how many cards are measured, adjudicated and read" | Schema tiers M, A, R, M+A. | Counted over all schema cards; M+A counts as adjudicated (a model touched it). | Absorb (spec issue 21) |
| 24 | 01's "extractor list with versions" and the freshness BAN | §4 (01) | Not built. | The tool list with versions appears in the `tools` step line of the process card. The freshness BAN is not in any milestone's content list; not built in M1. | Absorb (spec issue 7) |
| 25 | V9 and V10 in `render` | V9 info, V10 error | `render.validate(reports, facts, cites, partial)` returns `(errors, warnings)`; `cmd_render` prints `warning:`/`error:` lines and exits on errors unless `--allow-errors`. There is no "info" level. | New `process.validate_build(build) -> (errors, infos)`. `cmd_render` prints infos as `info: V9: …` and adds V10 errors to the blocking errors. `render.validate`'s signature does not change. | Absorb |
| 26 | Old dossiers and the M0 fixture | — | `FIX` and every 0.5.0 dossier have no `build.json`. | V10 fails for them ("V10: there is no build.json. Run prepare first."). Block E renders `FIX` with `--allow-errors` and checks that the V10 error is the only error. | Absorb |
| 27 | Version | — | `VERSION` 0.5.0. A major.minor change forces a full rebuild in `update_plan` and backs up `state.json`. | 0.6.0 (D9). | **Decision** (Q8) |
| 28 | Tool versions | Decision 7: pin every 6.2 tool, verify names, flags, behaviour | 6.2 says "from memory". | Verified on 2026-11-01 against the registries and the docs (D1 table). Pin rule: the newest stable release published at least 14 days before 2026-11-01. TypeScript is left unpinned (spec issue 11). Each tool is re-checked at the start of the milestone that first runs it (M2, M4, M5). | **Decision** (Q7) |

---

## 4. Decisions

### D1. Tool list and pinned versions

**Decision.** One data file, `scripts/tools.json`, read by a new module `scripts/toolcheck.py`. `doctor` and the preflight stage both call `toolcheck.preflight(langs)`.

- **Host tools** (`host`): `id`, `scope` (list of `all`, `python`, `js`, `csharp`), `command` (argv that prints the version), `pattern` (regex whose group 1 is the version), `min` (a version string, or a map scope → version), `install` (`{"linux": "...", "darwin": "..."}`), `source` (URL). Presence: `shutil.which(command[0], path=PATH)`. Version: run `command` with a 15-second timeout, search stdout+stderr with `pattern` (for `dotnet --list-sdks`, take the highest match over all lines). Comparison: dotted integers, missing parts are 0. A tool is `ok`, `old` (found but below the minimum for a scope in use; reported as missing, with "found X, needs Y") or `missing`. The install text printed is `install[sys.platform startswith "darwin" ? "darwin" : "linux"]`.
- **Self-installing tools** (`tools`): `id`, `scope`, `via` (`uv`, `npx`, `dotnet-tool`, `sdk`, `repo-config`), `package` (registry name), `version` (pin, or `null` with `open` text), `published` (date of that release), `gives`, `source` (docs URL), `first_used` (milestone). Their host requirement follows `via`: `uv` → uv; `npx` → node and npm; `dotnet-tool`/`sdk` → dotnet; `repo-config` → none. Preflight never installs anything; it reports such a tool as "installs on first use" when its host tools are ok, else as missing "(needs node)".
- **Restore commands** (`restore`): `ecosystem`, `lockfile` (at the repository root), `command`, `enabled`, `source`.
- **`python`**: the interpreter every Python tool runs on (`"3.13"`, which this machine has, so nothing is downloaded).
- **`languages`**: gatherer language name → scope (`Python` → `python`, `JavaScript` and `TypeScript` → `js`, `C#` → `csharp`). Any other code language is Tier B.

Verified values (2026-11-01). "Pin" is the newest stable release at least 14 days old; "latest" is the newest at all, for the record.

| Tool | via | Pin (published) | Latest | Verified names, flags and behaviour | Source |
|---|---|---|---|---|---|
| git | host | min 2.30 (host has 2.47.3) | — | `git clone --local --no-checkout`, `git checkout --detach`, `git tag --points-at`, `git merge-base --is-ancestor` (local `git clone -h`, `git checkout -h`). The 2.30 floor is conservative and not tested; every flag used is much older. | https://git-scm.com/docs/git-clone |
| uv | host | min 0.6.0 (host has 0.11.19) | — | `uv sync --frozen` = "Sync without updating the `uv.lock` file" (`--locked` instead fails if the lock is stale); `uv lock --script`, `uv run --locked --script`, `uvx --from` (local `--help`); `UV_CACHE_DIR`. The 0.6.0 floor is not verified; script locking exists on 0.11.19. | https://docs.astral.sh/uv/reference/cli/ |
| node | host | min 16 for Python, 22 for JS/TS (host has 20.19.2) | — | scip-python: "requires Node v16 or newer"; scip-typescript: "Node v22 and Node v24 are supported"; dependency-cruiser engines `^22‖^24‖>=26`; knip engines `^20.19.0‖>=22.12.0` | READMEs below |
| npm | host | min 7.0 (host has 9.2.0) | — | `npm ci --ignore-scripts` (local `npm ci --help`); `npx --yes pkg@version` | https://docs.npmjs.com/cli/v10/commands/npm-ci |
| .NET SDK | host | min 8.0.100 (not installed here) | — | `dotnet restore --locked-mode` = "Don't allow updating project lock file"; `--packages`; `NUGET_PACKAGES` | https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-restore |
| tree-sitter-language-pack | uv | **1.22.1** (2026-10-12) | 1.22.1 | Python ≥3.10. **Grammars are downloaded on first use** and cached (default under `~/.cache/tree-sitter-language-pack/v<version>/libs/`). `get_language("python")` returns a native `Language`; the 0.13 docs also name `get_parser`; the 1.x README shows a `process()` API. The exact 1.22.1 Python API is **not verified** (Q10); M1-9 checks it first. | https://github.com/xberg-io/tree-sitter-language-pack |
| semgrep | uv | **1.181.0** (2026-10-14) | 1.183.0 | `semgrep scan --config <dir of .yml/.yaml> --json --metrics=off --disable-version-check --oss-only --timeout <s>`; `--include`/`--exclude`; respects `.gitignore` by default (`--no-git-ignore` to turn off). Login is needed only for registry configs such as `--config auto` (inferred; the docs do not say it outright). | https://docs.semgrep.dev/cli-reference |
| grimp (M2) | uv | **3.17** (2026-09-04) | 3.18 | `grimp.build_graph(package_name, include_external_packages=False, exclude_type_checking_imports=False, cache_dir=".grimp_cache")`; the package must be importable; `cache_dir` defaults to a folder in the current directory (pass `None` or a path in the working area). Cycles: `nominate_cycle_breakers`. | https://grimp.readthedocs.io/en/stable/usage.html |
| vulture (M2) | uv | **2.16** (2026-03-25) | 2.16 | `vulture <paths> --min-confidence N --exclude … --ignore-names …`; text output only (`path:line: message (N% confidence)`); exit 3 = dead code found; parses with `ast`, does not import. | https://github.com/jendrikseipp/vulture |
| import-linter (M2) | repo-config | **2.15** (2026-09-04), read only | 2.15 | Config `[importlinter]` with `root_package`, contracts `[importlinter:contract:<id>]`; types forbidden, protected, layers, independence, acyclic siblings. Only the `.importlinter` INI form is shown on the docs index; the `pyproject.toml` form is not verified. | https://import-linter.readthedocs.io/en/stable/ |
| scip-python (M2) | npx | **@sourcegraph/scip-python 0.6.6** (2025-09-05) | 0.6.8 | `scip-python index . --project-name=<name>`; `--target-only`, `--environment`; no documented `--output`. Python 3.10+. | https://github.com/sourcegraph/scip-python |
| dependency-cruiser (M4) | npx | **18.6.0** (2026-10-11) | 18.7.0 | Binary `dependency-cruiser` (also `depcruise`); `-T json`; `--no-config`; picks up `.dependency-cruiser.js` automatically (loaded as a Node module, so it runs repository code). | https://github.com/sverweij/dependency-cruiser/blob/main/doc/cli.md |
| knip (M4) | npx | **6.42.0** (2026-10-18) | 6.44.1 | Loads configs through jiti (runs repository code); `--reporter json`. | https://knip.dev/reference/cli |
| scip-typescript (M4) | npx | **@sourcegraph/scip-typescript 0.4.0** (2025-10-02) | 0.6.0 | `scip-typescript index` (`--infer-tsconfig` for JS, `--yarn-workspaces`, `--pnpm-workspaces`); needs dependencies installed first. | https://github.com/sourcegraph/scip-typescript |
| TypeScript compiler API (M4) | npm | **not pinned** | 7.0.2 | 7.x is the native port; 5.9.3 (2025-09-30) and 6.0.3 (2026-04-16) are the last JS-API lines. Left open (spec issue 11). | https://www.npmjs.com/package/typescript |
| scip-dotnet (M5) | dotnet-tool | **0.2.14** (2026-05-05) | 0.2.16 | `dotnet tool install --global scip-dotnet`; `scip-dotnet index` from the project root; README asks for .NET 8. | https://github.com/sourcegraph/scip-dotnet |
| dotnet package list (M5) | sdk | SDK command | — | `.NET 10` renamed `dotnet list package` to `dotnet package list` and runs a restore automatically unless `--no-restore`; `--include-transitive --format json`. | https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-package-list |

**How Python tools run.** Each Python tool runs as a small worker script in `scripts/` that declares its pinned dependency inline (PEP 723, the way `check_page.py` does) and is locked with `uv lock --script`, which writes `scripts/<worker>.py.lock` pinning every transitive dependency. The runner starts it as `uv run --locked --python 3.13 --script scripts/<worker>.py`. `semgrep` is started by its worker from the worker's own environment (`Path(sys.executable).parent / "semgrep"`), so the CLI, too, is fully locked.

**Rejected.** (a) Versions in Python constants: the M2 to M5 adapters and `doctor` both need the list, and data diffs are easier to review. (b) `uvx --from semgrep==X` without a lock: transitive dependencies would float, which breaks spec 5.4 rule 7. (c) Installing tools during preflight: the spec says preflight only checks, and `doctor` must be safe to run. (d) Pinning the latest release: four of them are under two weeks old.

### D2. Module layout

New modules, each small enough to edit safely (target under 300 lines):

| File | Owns |
|---|---|
| `scripts/config.py` | The home config file: load, merge-update, `home()`, `cache_root()`, `timeouts()`, `registry_auth()`. |
| `scripts/tools.json` | D1 data. |
| `scripts/toolcheck.py` | Load `tools.json`, languages at a commit, tiers, preflight, `doctor` text. |
| `scripts/buildlog.py` | `build.json`: the fixed step list, start, append, read. Standard library only (also imported by `check_page.py`). |
| `scripts/workarea.py` | The working area, checkout, verification, trusted-ref check, `clean`. |
| `scripts/sandbox.py` | The safe runner. |
| `scripts/restore.py` | The restore stage. |
| `scripts/adapters.py` | Adapter base class, extract context, `ADAPTERS`, `run_extract`, `filter_paths`. |
| `scripts/shared_tools.py` | `TreeSitter` and `Semgrep` clients. |
| `scripts/ts_worker.py`, `scripts/ts_worker.py.lock` | Locked tree-sitter worker. |
| `scripts/semgrep_worker.py`, `scripts/semgrep_worker.py.lock` | Locked semgrep worker. |
| `scripts/stages.py` | The `prepare` stages before `measure`: pin, tools, copy, extract. |
| `scripts/process.py` | The process card body, render-time records, V9, V10, coverage items. |
| `rules/README.md` | Where semgrep rules go and how they are named (no rules yet). |

`dossier.py` keeps the CLI (adds `doctor`, `clean`, flags, wiring; grows by about 120 lines). `render.py` changes in three places only (the process card call, `collect_gaps(extra=…)`, `render_html(build=…)`).

**Rejected.** Putting it all in `dossier.py` (already 510 lines, and every task would edit the same file); one `pipeline.py` for everything (over 1,000 lines).

### D3. `build.json`

Location `<out>/build.json`. One file per build: `prepare` starts a new one and first renames the old one to `build.prev.json` (kept for "reused from the previous build" and for debugging). Format:

```json
{
  "schema": 1,
  "build_id": "20261101T120304Z-5923c09",
  "dossier_version": "0.6.0",
  "repo": "cannalerts",
  "sha": "5923c09…",
  "ref": "main",
  "options": {"allow_missing": false, "no_restore": false, "allow_ref": false, "submodules": false, "full": false},
  "records": [
    {"step": "copy", "part": "restore", "by": "prepare", "status": "ok",
     "started": "2026-11-01T12:03:09Z", "ended": "2026-11-01T12:03:21Z", "seconds": 12.1,
     "reason": null,
     "tools": [{"name": "uv", "version": "0.11.19"}],
     "counts": {"ecosystems": 1},
     "details": {"ecosystems": [{"ecosystem": "python", "command": "uv sync --frozen", "status": "ok"}]},
     "env_names": ["DOTNET_CLI_HOME", "DOTNET_CLI_TELEMETRY_OPTOUT", "…"],
     "command": ["uv", "sync", "--frozen"]}
  ]
}
```

- `step` ∈ `buildlog.STEPS = ("pin", "tools", "copy", "measure", "extract", "read", "write", "check", "gaps", "render")`, the ten steps of spec §4 in that order. `part` is optional (`checkout`, `restore`, `render`, `browser`). `status` ∈ `ok`, `skipped`, `failed`, `reused`. `by` ∈ `prepare`, `render`, `check_page`. A `skipped` or `failed` record must have a non-empty `reason`. `env_names` and `command` appear only on records of stages that ran a child process.
- **Append, crash-safe:** `buildlog.append(path, record)` reads the file, appends the record, writes `build.json.tmp` in the same folder, `fsync`s it and `os.replace`s it over `build.json`. A crash leaves either the old or the new file, never a broken one. Records are never edited or removed; a reader takes the **last** record for a `(step, part)`.
- **Claude never edits it.** SKILL.md says so under "Rules that always apply". Every record carries `by`, so a hand-written record would have to lie about its writer to pass.

**Rejected.** (a) JSON Lines: crash-safe too, but the spec names `build.json` and the other files in the folder are plain JSON. (b) Records inside `state.json`: that file holds the user's decisions and is never rebuilt; a run log does not belong there. (c) One file for all builds: grows without bound, and the card needs only the current and the previous build.

### D4. The safe runner (`scripts/sandbox.py`)

```python
@dataclass
class Result:
    command: list[str]
    returncode: int | None        # None when killed by the timeout
    timed_out: bool
    seconds: float
    stdout: Path                  # <area>/logs/<stage>-<n>.out
    stderr: Path                  # <area>/logs/<stage>-<n>.err
    env_names: list[str]          # sorted names of the variables passed (never values)

def build_env(area: Path, *, profile: str = "restricted", ecosystem: str | None = None,
              parent: Mapping[str, str] | None = None) -> dict[str, str]
def run(cmd: list[str], *, area: Path, cwd: Path, stage: str, timeout: float,
        profile: str = "restricted", ecosystem: str | None = None,
        input: bytes | None = None, parent: Mapping[str, str] | None = None) -> Result
```

`build_env` starts from `{}` (never from a copy of `os.environ`; `parent` defaults to `os.environ` and is only read for the names listed here) and adds:

1. `PATH`: the directories of the host tools in `tools.json` that `shutil.which` finds on the parent `PATH` (in `tools.json` order, no duplicates), then `/usr/local/bin`, `/usr/bin`, `/bin`.
2. `LANG`, `LC_ALL`, `TERM`: copied when set in the parent.
3. `HOME = <area>/home`, `TMPDIR = <area>/home/tmp`, `XDG_CACHE_HOME = <area>/home/.cache`, `XDG_CONFIG_HOME = <area>/home/.config` (all created).
4. `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`, `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`, `NODE_EXTRA_CA_CERTS`: copied when set (exactly the spec's names; spec issue 15).
5. `DOTNET_CLI_TELEMETRY_OPTOUT=1`, `DOTNET_NOLOGO=1`.
6. Private caches. Profile `restricted` (restores, and Node/.NET adapters from M4): `UV_CACHE_DIR=<area>/cache/uv`, `npm_config_cache=<area>/cache/npm`, `NUGET_PACKAGES=<area>/cache/nuget`, `DOTNET_CLI_HOME=<area>/cache/dotnet`, `PIP_CACHE_DIR=<area>/cache/pip`, `npm_config_userconfig=<area>/home/.npmrc-empty` (an empty file). Profile `tool` (the shared tree-sitter and semgrep workers, which do not load repository code): the same variables, except `UV_CACHE_DIR=<cache root>/.dossier-tools/uv` and `UV_PYTHON_INSTALL_DIR=<cache root>/.dossier-tools/python`, shared by all repositories because they hold only the pinned tool wheels (D12).
7. Registry credentials (only with `ecosystem` given and only in profile `restricted`): for each entry of `config.registry_auth()[ecosystem]`, a bare name is copied from the parent when set; a `~/…` file is copied into `<area>/home/…` (refused, with a message, if it resolves outside the real home folder); a copied `~/.npmrc` sets `npm_config_userconfig` to the copy.

Nothing else is passed: no `SSH_AUTH_SOCK`, no `GIT_*`, no cloud credentials, no token or secret variables.

`run` writes `input` (if any) to `<area>/logs/<stage>-<n>.in` and opens it as stdin (else `/dev/null`); stdout and stderr go to files (never pipes, so a child that leaves a grandchild holding the pipe cannot hang the runner). It starts the child with `subprocess.Popen(cmd, cwd=cwd, env=env, stdin=…, stdout=…, stderr=…, start_new_session=True)`, waits up to `timeout`, and on expiry sends `SIGTERM` to the whole process group (`os.killpg(p.pid, signal.SIGTERM)`), waits 5 seconds, then `SIGKILL`s the group. After a normal exit it also sends `SIGKILL` to the group (ignoring `ProcessLookupError`), so a background child of an install script cannot outlive its stage. `<n>` counts up per stage so logs are never overwritten.

How each rule is proven (M1-6, M1-7):

| Rule | Test |
|---|---|
| Empty environment plus allowlist | The parent env holds `SSH_AUTH_SOCK`, `GIT_AUTHOR_NAME`, `AWS_SECRET_ACCESS_KEY`, `GITHUB_TOKEN`, `DATABASE_URL`, `MY_SECRET`; the fixture `install.sh` writes `env` names to a file; the test asserts the names equal `sorted(result.env_names)` and are a subset of `sandbox.ALLOWED_NAMES`, and none of the six appear. |
| Proxies and certificates pass | `HTTPS_PROXY=http://proxy.invalid:3128` in the parent appears in the child. |
| Scratch `HOME` | `install.sh` writes `$HOME`; equals `<area>/home`. |
| Private caches | `install.sh` creates a marker in each cache variable's folder; every marker path is under `<area>/cache/`. |
| Names recorded, never values | The restore record in `build.json` has `env_names` and contains no value of any parent variable. |
| Registry credentials opt-in | With `registry_auth = {"python": ["MY_INDEX_TOKEN"]}` the variable reaches the child; without it, it does not. |
| Process-group timeout | `sleeper.sh` starts `sleep 300 &`, writes both PIDs, waits; with `timeout=1` the result has `timed_out=True`, and within 3 s both PIDs are gone (`os.kill(pid, 0)` raises `ProcessLookupError`). |

**Rejected.** (a) Copying `os.environ` and deleting a denylist: one forgotten name leaks a credential; the spec says allowlist. (b) `capture_output=True`: a background grandchild that keeps the pipe open hangs the runner. (c) `p.kill()` alone: kills only the direct child.

### D5. Trusted-ref check (`workarea.trusted(top, sha)`)

Run against the **original** repository (its refs are the user's; the checkout's refs are copies):

1. **Tag:** `git -C top tag --points-at <sha>` is non-empty → trusted, why `"tag <first tag>"`.
2. **Default branch:** the first ref that exists, checked with `git show-ref --verify --quiet <ref>`, in this order: the target of `git symbolic-ref --quiet refs/remotes/origin/HEAD`; `refs/remotes/origin/main`; `refs/remotes/origin/master`; `refs/heads/main`; `refs/heads/master`. None → untrusted, why `"no default branch was found (origin/HEAD, main or master)"`.
3. **Tip:** `git rev-parse <ref>` equals `sha` → trusted, why `"tip of the default branch <short name>"`.
4. **Reachable:** `git merge-base --is-ancestor <sha> <ref>` exits 0 → trusted, why `"reachable from the default branch <short name>"`.
5. Otherwise untrusted, why `"not a tag and not on the default branch <short name>"`.

Returns `{"trusted": bool, "why": str, "default_branch": "origin/main" | null}`, stored in the `pin` record. `--allow-ref` does not change the result; it only lets the gated stages run (and the record says so).

**Rejected.** Checking reachability in the checkout: its remote-tracking refs are a copy and could be stale.

### D6. Path filter and V9

`adapters.filter_paths(outputs, tree, checkout, expected_globs) -> (kept, stats)` runs in `run_extract` on each adapter's output before it is written. Every output item must have `path` (a string) and may have `paths` (a list). Each path is normalised: an absolute path inside the checkout becomes repository-relative POSIX; an absolute path outside the checkout is dropped as **outside** (for example a library in the scratch environment). A relative path that is in `git ls-tree -r <sha>` is kept. Otherwise it is dropped and classified:

- **expected**: a segment is in `gather.VENDOR_SEG | gather.GENERATED_SEG | {".venv", "venv", ".git", ".grimp_cache"}`, or it matches one of the adapter's `expected_untracked` globs (`fnmatch`);
- **unexpected**: anything else.

An item whose `path` is dropped is dropped; an item's `paths` list loses only the dropped entries. `stats = {"paths_seen", "paths_dropped", "dropped_expected", "dropped_outside", "dropped_unexpected", "unexpected": [every unexpected path, sorted]}`, summed over adapters into the `extract` record's `counts` (the list goes into `details.unexpected`).

V9 (`process.validate_build`, **info**): `"V9: no extractor ran in this build, so the path filter had nothing to check."` when `extract` was skipped; otherwise `"V9: the path filter removed {dropped} of {seen} extracted paths ({expected} generated or installed, {outside} outside the copy, {unexpected} unexpected)."`, and when there are unexpected paths a second info line `"V9: unexpected paths: a, b, c"` listing up to 20 and then `"and N more (see build.json)"`.

### D7. Adapter interface (`scripts/adapters.py`)

```python
OUTPUTS = ("entry_points", "graph", "symbols", "io_candidates", "models", "tests", "dead", "blindspots")

class Adapter:
    name = ""                  # "python"; also the section key in extract/*.json
    version = "1"              # bump when the adapter's output or logic changes (part of the reuse key)
    languages: tuple = ()      # gatherer language names it handles
    tools: tuple = ()          # tool ids from tools.json it runs; their versions join the reuse key
    loads_repo_code = False    # True for Node and .NET adapters: trusted ref required (5.4 rule 4), restricted runner profile
    expected_untracked: tuple = ()   # globs of untracked paths it may legitimately report, e.g. (".venv/**",)
    blind_spots: tuple = ()    # filled from M2: ({"id": ..., "pattern": ..., "rule": ...}, ...)

    def extract(self, ctx: "Context") -> dict[str, list[dict]]:
        """Return {output name: [items]} for any subset of OUTPUTS. Every item has 'path'."""
        raise NotImplementedError

@dataclass
class Context:
    checkout: Path
    sha: str
    tree: frozenset[str]       # every tracked path at sha
    files: list[str]           # tracked paths in this adapter's languages, sorted
    area: Path
    restored: dict[str, bool]  # ecosystem -> dependencies installed?
    run: Callable[..., sandbox.Result]   # sandbox.run with area, cwd=checkout, timeout and profile already bound
    treesitter: shared_tools.TreeSitter
    semgrep: shared_tools.Semgrep
    tool_versions: dict[str, str]

ADAPTERS: tuple[type[Adapter], ...] = ()   # M2 adds the Python adapter

def detect(languages: list[str], adapters=ADAPTERS) -> list[Adapter]
def run_extract(*, adapters, checkout, sha, tree, area, out, trusted, allow_ref, restored,
                treesitter, semgrep, tool_versions, timeout) -> dict      # returns the 'extract' record (without step/by/times)
def filter_paths(outputs, tree, checkout, expected_globs) -> tuple[dict, dict]
```

Output files `<out>/extract/<output>.json`: `{"schema": 1, "sha": "...", "adapters": {"<name>": {"version": "1", "tools": {"semgrep": "1.181.0"}, "items": [...]}}}`, written atomically. Reuse: an adapter is skipped with status `reused` when every output file it wrote last time has its section with the same `sha`, `version` and `tools`. An adapter with `loads_repo_code` on an untrusted ref without `allow_ref` is skipped with the reason from D5 plus "Use --allow-ref to run it." An exception in `extract` marks that adapter `failed` (reason = the exception's first line) and the others still run.

`run_extract` checks, before and after the adapters run: `git -C checkout rev-parse HEAD` equals `sha` and `git -C checkout status --porcelain --untracked-files=no` is empty. A mismatch after the run marks the step `failed` with reason "The clean copy changed during extraction (HEAD or tracked files)." and writes no output.

The shared layer is reached only through `ctx.treesitter` and `ctx.semgrep`:

```python
class TreeSitter:
    def __init__(self, run): ...
    def query(self, language: str, paths: list[str], query: str) -> list[dict]
    # items: {"path", "capture", "start_line", "start_col", "end_line", "end_col", "text"}; lines are 1-based

class Semgrep:
    def __init__(self, run): ...
    def scan(self, config: Path, paths: list[str] | None = None, timeout: int = 30) -> list[dict]
    # items: {"rule", "path", "start_line", "end_line", "message", "snippet", "metadata"}
```

Each call runs its worker through `run(..., profile="tool")`, sends a JSON request on stdin, and reads JSON from the worker's stdout file. A non-zero exit raises `shared_tools.ToolError` with the last 20 lines of stderr.

**Rejected.** Methods per output (`entry_points()`, `graph()`, …): every adapter would carry eight stubs, and M2 may compute several outputs from one tool run. A plugin registry or entry points: speculative.

### D8. Reporting V9 and V10

`process.validate_build(build: dict | None, pending: list[dict] = ()) -> (errors, infos)`:

- `build is None` → error `"V10: there is no build.json. Run prepare first."`.
- **V10 (error)**, over `build["records"] + pending`: for each step id in `STEPS`, no record → `"V10: build.json has no record for step {n} '{id}' ({plain sentence})."`; a `skipped` or `failed` record without a reason → `"V10: step '{id}' was {status} without a reason."`; an unknown status → error.
- **V9 (info)**: D6.

`cmd_render` calls it after `render.validate` (so V1 and V6 run first) with the render records not yet written (D3 order, M1-11), prints `info:` lines, adds the errors to the blocking list and stops unless `--allow-errors`. Only after it passes does `cmd_render` append the pending records and write the page. `check_page.py` is not part of V10.

### D9. Version

`VERSION` 0.6.0. A minor bump makes the next `prepare` of any dossier a full rebuild (`update_plan`: major.minor changed) and backs up `state.json` as `state.backup-v0.5.0.json`. That is wanted: no 0.5.0 dossier has a `build.json`. The SKILL.md interim notice ("cannot yet write the new report layout") stays. **Rejected:** staying on 0.5.0 (`update_plan` would treat a dossier without `build.json` as incremental).

### D10. Restore flow (`scripts/restore.py`)

```python
def plans(tree: frozenset[str], tools: dict) -> list[dict]
    # one per restore entry whose lockfile is at the repository root:
    # {"ecosystem", "lockfile", "command", "enabled"}
def decide(plans, *, state, answer, no_restore, trust, allow_ref) -> dict
    # {"action": "run"|"ask"|"skip", "reason": str|None, "store": "yes"|"no"|None}
def run(plans, *, area, checkout, timeout, parent=None) -> list[dict]
    # one result per plan: {"ecosystem", "command", "status", "reason", "seconds", "env_names", "log"}
```

`decide`, first match wins: no plans → skip "There is no lockfile at the top of the repository, and dossier installs only from lockfiles."; `no_restore` → skip "Installing dependencies was turned off with --no-restore."; untrusted and not `allow_ref` → skip "{trust.why}, so dependencies were not installed. Use --allow-ref to install them anyway."; `answer` given (`--restore yes|no`) → store it, then run or skip ("You chose not to install dependencies for this repository."); stored answer `no` → skip same text plus " Run prepare with --restore yes to change this."; stored answer `yes` and every plan's ecosystem in `state["restore"]["ecosystems"]` → run; otherwise → ask.

`run`: a plan with `enabled: false` → skipped "Installing {ecosystem} dependencies arrives in a later version of dossier."; else `sandbox.run(plan["command"], area=area, cwd=checkout, stage="restore-"+ecosystem, timeout=timeout, profile="restricted", ecosystem=ecosystem)`. Exit 0 → ok. Timeout → failed "Installing {ecosystem} dependencies took longer than {timeout} seconds and was stopped." Non-zero → failed; if the stderr file matches `AUTH_FAILURE = re.compile(r"\b(401|403)\b|E401|E403|Unauthori[sz]ed|authentication (failed|required)|could not authenticate|NU1301", re.I)` the reason is "Installing {ecosystem} dependencies failed because the package registry refused the credentials. Add the variables or files it needs to registry_auth.{ecosystem} in {config path}." else "Installing {ecosystem} dependencies failed (exit {code}). See {log path}."

### D11. Where `extract/` lives

`<out>/extract/`, next to `facts.json`. Reports and `render` (V5 from M2) read it, and `clean` must not break a dossier that can still be rendered. **Rejected:** the working area (regenerable, but `clean` would then make `render` fail until the next `prepare`).

### D12. Shared tool cache

The two worker scripts' uv cache and Python installs go to `<cache root>/.dossier-tools/`, shared by all repositories. They hold only the pinned tool wheels and grammars, never a repository's dependencies, and the workers do not load repository code. `clean` does not remove it (it is not a repository's working area); deleting the folder by hand is safe. **Rejected:** a per-repository copy (about 100 MB of semgrep and grammars per repository, downloaded again for each). Note: where tree-sitter-language-pack stores downloaded grammars is not verified; with the scratch `HOME` they land under `<area>/home/.cache/` unless it honours another setting. M1-9 records where they went.

---

## Phase 1: M1 implementation

### Before you start

1. Read section 2 (shared rules), then sections 3 and 4 of this plan. Load the skills listed in section 2.
2. Run `git log --oneline -15` in the repository and read the "Verification results" and "Deviations" at the end of `docs/plans/005-m0-plan.md`. M0 moved one thing to M1: the real `dossier.process` card (M0 drew a placeholder). Nothing else was moved. If the log shows commits after `2c8a718` that touch `scripts/` or `prompts/schema/`, stop and report.
3. Check the human's answers in section 7 ("Questions for the human"). If any question is unanswered, use the stated default.
4. Create the branch: `git switch -c feat/dossier-m1`.
5. Run the full suite once; it must print `227 passed`.

Independent tasks (may be done in any order relative to each other): **M1-1, M1-2, M1-4**. M1-3 needs M1-2. M1-5 and M1-6 need M1-1. M1-7 needs M1-4, M1-5, M1-6. M1-8 needs M1-4, M1-6. M1-9 needs M1-6, M1-8. M1-10 needs M1-2 to M1-9. M1-11 needs M1-10. M1-12 needs M1-11. M1-13 needs M1-11. M1-14 needs everything before it. M1-15 and M1-16 are last.

### M1-1. Config module

- [x] **Goal.** One module owns the home config; `home` no longer erases other keys; the cache root, timeouts and registry credentials have a home.
- **Files.** New `scripts/config.py`; edit `scripts/dossier.py` (`CONFIG`, `get_home`, `cmd_home` use it); new `tests/unit/scripts/test_config.py`.
- **Interface.**
  ```python
  DEFAULT_TIMEOUTS = {"restore": 900, "extract": 1800, "tool": 600}
  def path() -> Path                       # $DOSSIER_CONFIG or ~/.config/dossier/config.json (read each call)
  def load() -> dict                       # {} when absent; SystemExit with a plain message when not valid JSON
  def update(**keys) -> dict               # merge into the file, atomic write (tmp + os.replace), return the result
  def home() -> Path | None                # $DOSSIER_HOME, else load()["home"], expanded; None when unset
  def cache_root() -> Path                 # $DOSSIER_CACHE, else load()["cache_dir"], else ~/.local/cache/dossier; expanded, not created
  def timeouts() -> dict                   # DEFAULT_TIMEOUTS updated with load().get("timeouts", {}); values must be positive numbers, else SystemExit
  def registry_auth() -> dict[str, list[str]]  # load().get("registry_auth", {}); each value a list of strings, else SystemExit
  ```
- **Steps.** (1) Write the module (standard library only). (2) In `dossier.py`: `CONFIG` stays as a name for compatibility but is computed from `config.path()`; `get_home()` calls `config.home()` and keeps today's error message when it is `None`; `cmd_home` without a directory prints the same text as today; with a directory it calls `config.update(home=str(d))`. (3) Tests: `update` keeps unrelated keys (`cache_dir` survives `home`); env vars win over the file; `cache_root` default ends with `.local/cache/dossier`; a bad `timeouts` value and a non-list `registry_auth` value exit with a message; invalid JSON exits with a message naming the path.
- **Done-check.** `uv run --with pytest --with pygments python -m pytest tests -q` passes; `DOSSIER_CONFIG=$(mktemp -d)/c.json; echo '{"cache_dir": "/x"}' > $DOSSIER_CONFIG; uv run scripts/dossier.py home /tmp/h >/dev/null; cat $DOSSIER_CONFIG` shows both `cache_dir` and `home`.
- **Commit.** `feat(dossier): add a config module and stop home from erasing other settings`

### M1-2. Tool list and preflight checks

- [x] **Goal.** `tools.json` holds every tool of spec 6.2 with the D1 values; `toolcheck.py` finds host tools and their versions and decides what a set of languages needs.
- **Files.** New `scripts/tools.json`, `scripts/toolcheck.py`, `tests/unit/scripts/test_toolcheck.py`.
- **Data.** Copy the D1 table into `tools.json` exactly (ids: `git`, `uv`, `node`, `npm`, `dotnet` under `host`; `tree-sitter-language-pack`, `semgrep`, `grimp`, `vulture`, `import-linter`, `scip-python`, `dependency-cruiser`, `knip`, `scip-typescript`, `typescript`, `scip-dotnet`, `dotnet-package-list` under `tools`; restore entries `python` (`uv.lock`, `["uv","sync","--frozen"]`, enabled), `npm` (`package-lock.json`, `["npm","ci","--ignore-scripts"]`, disabled), `nuget` (`packages.lock.json`, `["dotnet","restore","--locked-mode"]`, disabled)). Host commands and patterns: git `["git","--version"]` / `git version (\d+\.\d+(?:\.\d+)?)`; uv `["uv","--version"]` / `uv (\d+\.\d+\.\d+)`; node `["node","--version"]` / `v(\d+\.\d+\.\d+)`; npm `["npm","--version"]` / `(\d+\.\d+\.\d+)`; dotnet `["dotnet","--list-sdks"]` / `(?m)^(\d+\.\d+\.\d+)`. Scopes: git and uv `["all"]`; node and npm `["python","js"]`, node `min` = `{"python": "16.0.0", "js": "22.0.0"}`, npm `min` `"7.0.0"`; dotnet `["csharp"]`, `min` `"8.0.100"`. Install texts: git linux `sudo apt install git`, darwin `brew install git`; uv both `curl -LsSf https://astral.sh/uv/install.sh | sh`; node linux `Install Node.js (version shown above or later) from https://nodejs.org/en/download, or with your version manager`, darwin `brew install node`; npm same as node; dotnet linux `Install the .NET SDK 8 or later: https://learn.microsoft.com/dotnet/core/install/linux`, darwin `brew install --cask dotnet-sdk`. Top-level keys: `"schema": 1`, `"verified": "2026-11-01"`, `"pin_rule": "Newest stable release published at least 14 days before the verified date. Re-check at the start of the milestone that first runs the tool."`, `"python": "3.13"`, `"languages": {"Python": "python", "JavaScript": "js", "TypeScript": "js", "C#": "csharp"}`. `typescript` has `"version": null` and `"open": "TypeScript 7 is the native port; choose 5.9.x, 6.0.x or the new API in M4."`.
- **Interface.**
  ```python
  TOOLS_FILE = Path(__file__).resolve().parent / "tools.json"
  def load_tools(path=TOOLS_FILE) -> dict
  def scope_of(lang: str, tools: dict) -> str | None      # None = Tier B
  def tier_of(lang: str, tools: dict) -> str              # "A" or "B"
  def languages_at(top: str, sha: str) -> list[str]       # section 3 item 7; sorted by number of files, then name
  def parse_version(text: str) -> tuple[int, ...]
  def check_host(tool: dict, scopes: set[str], path: str | None = None) -> dict
      # {"id", "status": "ok"|"old"|"missing", "version", "path", "needs": "2.30", "for": ["Python"], "install": "..."}
  def preflight(langs: list[str], tools: dict | None = None, path: str | None = None, all_scopes: bool = False) -> dict
      # {"languages": [{"name", "tier"}], "host": [check_host results for tools whose scope is in use],
      #  "self_installing": [{"id", "version", "via", "status": "first-use"|"missing", "needs": [host ids]}],
      #  "missing": [ids of host tools not ok, then self-installing tools whose host tools are missing]}
  def format_text(report: dict) -> str                    # the doctor layout in M1-3
  ```
  Scopes in use = `{"all"}` plus `scope_of(l)` for each language (or every scope when `all_scopes`). `for` names the languages that need the tool. `needs` for node is the highest minimum over the scopes in use.
- **Steps.** (1) Write the data file and the module. (2) Tests use a temporary folder of fake executables (`#!/bin/sh` scripts that `echo` a version line) passed as `path=`: all present → `missing == []`; node removed → `node` missing and `scip-python` missing "(needs node)"; node `v20.19.2` with `["TypeScript"]` → `old`, needs `22.0.0`; with `["Python"]` → ok; dotnet multi-line `--list-sdks` picks the highest; Tier: Python A, Shell B; `languages_at` on the `git_repo` fixture from `tests/conftest.py` (its files have no extensions) returns `[]`, and on a small temporary repo with `a.py`, `b.sh`, `README.md` returns `["Python", "Shell"]` (order by file count then name). (3) A test asserts every entry in `tools` has `id`, `scope`, `via`, `version` key (may be null only with `open`), `source`, and every restore entry has `ecosystem`, `lockfile`, `command`, `enabled`.
- **Done-check.** Full suite passes; `python3 -c "import json; d=json.load(open('scripts/tools.json')); print(len(d['host']), len(d['tools']), len(d['restore']))"` prints `5 12 3`.
- **Commit.** `feat(dossier): pin the 1.0.0 tool list and add the preflight checks`

### M1-3. `doctor` command

- [x] **Goal.** `dossier.py doctor [REPO] [--all] [--json]` prints what is installed and what is missing, with install commands, and needs no dossier home.
- **Files.** Edit `scripts/dossier.py` (new `cmd_doctor`, parser entry, module docstring line); new `tests/integration/scripts/test_doctor_cli.py`.
- **Behaviour.** With `--all`: `preflight([], all_scopes=True)`. Otherwise `top = toplevel(repo)`, `sha = git rev-parse HEAD`, `langs = toolcheck.languages_at(top, sha)`. `--json` prints the report as JSON; otherwise `format_text`:
  ```
  Languages: Python (full support), Shell (Tier B: no static graph)
  Needed on this machine:
    ok       git 2.47.3      needs 2.30 or later
    ok       uv 0.11.19      needs 0.6.0 or later
    MISSING  node            needs 16.0.0 or later, for Python
             Install: <install text>
  Installed by dossier on first use (pinned):
    tree-sitter-language-pack 1.22.1 via uv
    scip-python 0.6.6 via npx (cannot install: needs node, npm)
  1 tool is missing. Install it, or build with --allow-missing to carry on without it.
  ```
  (`old` prints `TOO OLD  node 20.19.2  needs 22.0.0 or later, for TypeScript`.) The last line is `Nothing is missing.` when that is so. Exit 0 when nothing is missing, 1 otherwise. `doctor` never calls `get_home()`.
- **Steps.** (1) Implement. (2) Test with `subprocess.run([sys.executable, "scripts/dossier.py", "doctor", str(repo), "--json"], env={…PATH=fake bin + dir of git…})`: build a fake bin folder with symlinks to the real `git` and fake `uv`, without node; on a temporary repo holding `a.py` the JSON lists `node` and `npm` in `missing` and the exit code is 1; with fake `node` (v20.19.2) and `npm` it exits 0. Use `sys.executable` (the test runner's Python, which has `pygments`) so no `uv` is needed to start the script.
- **Done-check.** Full suite passes; `uv run scripts/dossier.py doctor /home/nick/dev/projects/cannalerts; echo "exit $?"` lists git, uv, node, npm as ok and prints `exit 0`.
- **Commit.** `feat(dossier): add the doctor command`

### M1-4. Run record (`buildlog.py`)

- [x] **Goal.** Start, append to and read `build.json` crash-safely.
- **Files.** New `scripts/buildlog.py` (standard library only); new `tests/unit/scripts/test_buildlog.py`.
- **Interface.**
  ```python
  FILE, PREV = "build.json", "build.prev.json"
  STEPS = ("pin", "tools", "copy", "measure", "extract", "read", "write", "check", "gaps", "render")
  STATUSES = ("ok", "skipped", "failed", "reused")
  WRITERS = ("prepare", "render", "check_page")
  def now() -> str                                   # "%Y-%m-%dT%H:%M:%SZ" UTC
  def start(out: Path, *, repo: str, sha: str, ref: str, version: str, options: dict) -> Path
      # renames out/build.json to out/build.prev.json (replacing it) if present; writes a new file; returns its path
  def load(path_or_out: Path) -> dict | None        # a folder means <folder>/build.json; None when absent
  def check_record(rec: dict) -> None               # ValueError on unknown step/status/by, or skipped/failed without reason
  def append(path: Path, rec: dict) -> dict         # fills started/ended/seconds when missing, checks, atomic write (D3), returns rec
  @contextmanager
  def step(path: Path, step: str, part: str | None = None, by: str = "prepare")
      # yields a dict to fill (status defaults to "ok"); on exit appends it with times;
      # on an exception sets status "failed" and reason = first line of the exception, appends, re-raises
  def latest(build: dict, step: str, part=...) -> dict | None   # last record for step (any part when part is omitted)
  def records(build: dict, step: str) -> list[dict]
  ```
  Build id: `datetime.now(utc).strftime("%Y%m%dT%H%M%SZ") + "-" + sha[:7]`.
- **Steps.** Implement; tests: `start` twice keeps the first as `build.prev.json`; `append` keeps earlier records and order; `check_record` rejects an unknown step, an unknown status, `skipped` without `reason`; `step` records `failed` with the reason on an exception and re-raises; a simulated crash (monkeypatch `os.replace` to raise `OSError`) leaves the previous file loadable and unchanged; `latest` returns the last of two records for the same `(step, part)`.
- **Done-check.** Full suite passes.
- **Commit.** `feat(dossier): add the build.json run record`

### M1-5. Working area, checkout, trusted ref, `clean`

- [ ] **Goal.** A verified clean copy at the pinned commit in the working area, reused between builds; the trusted-ref check; the `clean` command.
- **Files.** New `scripts/workarea.py`; edit `scripts/dossier.py` (`cmd_clean`, parser, docstring); new `tests/integration/scripts/test_workarea.py`; edit `tests/conftest.py` (new fixture `hygiene_repo`, below — also used by M1-7).
- **Interface.**
  ```python
  class CheckoutError(RuntimeError): ...
  def git(cwd, *args, check=True) -> str    # runs git with os.environ minus GIT_DIR, GIT_WORK_TREE, GIT_INDEX_FILE, GIT_OBJECT_DIRECTORY
  def area_for(name: str, top: str, root_commit: str, cache_root: Path | None = None) -> Path
      # <cache_root>/<name>; creates it and owner.json on first use; CheckoutError when owner.json names another repository
  def ensure_checkout(area: Path, top: str, sha: str, submodules: bool = False) -> dict
      # {"path", "created": bool, "head": sha, "verified": True, "submodules": [paths], "submodules_on": bool}
  def verify(checkout: Path, sha: str) -> tuple[bool, str]
  def trusted(top: str, sha: str) -> dict           # D5
  def clean(area: Path, cache_root: Path) -> bool   # True if removed; refuses (CheckoutError) unless area.parent.resolve() == cache_root.resolve() and area.name not in ("", ".", "..", ".dossier-tools")
  ```
- **`ensure_checkout` steps, exactly.** `co = area / "checkout"`. (1) If `co/.git` is missing, or `git(co, "config", "--get", "remote.origin.url")` is not `top`: remove `co` if present, then `git clone --local --no-checkout --quiet <top> <co>`. (2) Else `git(co, "fetch", "--quiet", "--no-tags", "origin", "+refs/heads/*:refs/remotes/origin/*")`. (3) If `git(co, "cat-file", "-e", sha + "^{commit}", check=False)` fails, remove `co` and clone again as in (1) (a local clone copies every object, including commits on no branch). (4) `git(co, "checkout", "--quiet", "--detach", "--force", sha)`. (5) `git(co, "clean", "-ffdq")` (removes untracked files, keeps ignored ones such as `.venv`). (6) Submodules: list the tree entries of type `commit` (`git ls-tree -r <sha>` in `top`); if `submodules` and the list is non-empty, `git(co, "submodule", "update", "--init", "--recursive", "--quiet")`. (7) `verify`: `rev-parse HEAD == sha` and `status --porcelain --untracked-files=no --ignore-submodules=all` empty; otherwise raise `CheckoutError` with the reason.
- **`cmd_clean`.** `clean [REPO]`: `top = toplevel(repo)`, `out, name, root = out_dir(top)`, `area = config.cache_root() / out.name`. If it does not exist print `Nothing to clean for <name>.`; else remove it and print `Removed the working area <path>. The dossier in <out> was not touched.`
- **`hygiene_repo` fixture** (in `tests/conftest.py`, built with the same `git()` helper style as `git_repo`): `git init -b main`; commit 1 adds `install.sh`, `sleeper.sh`, `app.py` (`print("hi")\n`) and `uv.lock` (text `version = 1\n`); tag `v1.0` on commit 1; commit 2 on main edits `app.py`; commit 3 on main edits it again (main's tip); branch `feature/x` from commit 3 with commit 4 adding `feature.py`; then `git checkout main`. Return a `types.SimpleNamespace` with `path`, `tag_sha` (commit 1), `middle_sha` (commit 2: not tagged, not a tip, on main), `main_sha` (commit 3), `feature_sha` (commit 4). `install.sh` and `sleeper.sh` are exactly:
  ```sh
  #!/bin/sh
  # install.sh: writes out what a restore can see
  mkdir -p "$HOME/report"
  env | cut -d= -f1 | sort > "$HOME/report/env-names.txt"
  printf '%s\n' "$HOME" > "$HOME/report/home.txt"
  pwd > "$HOME/report/cwd.txt"
  for v in UV_CACHE_DIR npm_config_cache NUGET_PACKAGES DOTNET_CLI_HOME PIP_CACHE_DIR; do
    eval d=\$$v
    mkdir -p "$d" && : > "$d/written-by-install" && echo "$d/written-by-install" >> "$HOME/report/cache-markers.txt"
  done
  ```
  ```sh
  #!/bin/sh
  # sleeper.sh: starts a background child and never finishes on its own
  sleep 300 &
  echo $! > "$HOME/child.pid"
  echo $$ > "$HOME/parent.pid"
  wait
  ```
  Make both executable before committing (`chmod +x`).
- **Tests.** Checkout of `main_sha`: created, verified, HEAD equals, the user's repository `git status` unchanged; second call with `feature_sha` reuses (created False) and moves; an untracked file dropped into the checkout is gone after the next call; a commit added to the source after the first clone is found after fetch; `trusted`: `tag_sha` → "tag v1.0"; `main_sha` → "tip of the default branch main"; `middle_sha` → "reachable from the default branch main"; `feature_sha` → untrusted "not a tag and not on the default branch main"; a clone of the fixture (has `origin/HEAD`) → default branch `origin/main`; `area_for` with another repository's `owner.json` raises; `clean` refuses a path outside the cache root and removes a real area.
- **Done-check.** Full suite passes; `DOSSIER_HOME=$(mktemp -d) DOSSIER_CACHE=$(mktemp -d) uv run scripts/dossier.py clean /home/nick/dev/projects/cannalerts` prints `Nothing to clean for cannalerts.`
- **Commit.** `feat(dossier): add the working area, verified checkout, trusted-ref check and clean`

### M1-6. Safe runner

- [ ] **Goal.** `sandbox.run()` as in D4, with a test per rule.
- **Files.** New `scripts/sandbox.py`; new `tests/unit/scripts/test_sandbox.py` (`build_env` only) and `tests/integration/scripts/test_sandbox_run.py` (real processes).
- **Interface.** D4, plus `ALLOWED_NAMES: frozenset[str]` = every name `build_env` can set (PATH, LANG, LC_ALL, TERM, HOME, TMPDIR, XDG_CACHE_HOME, XDG_CONFIG_HOME, the six proxy/certificate names, the two telemetry names, UV_CACHE_DIR, npm_config_cache, NUGET_PACKAGES, DOTNET_CLI_HOME, PIP_CACHE_DIR, npm_config_userconfig, UV_PYTHON_INSTALL_DIR). Registry-credential names are added per call and are reported in `env_names` but are not in `ALLOWED_NAMES`. `tools_cache(area) = area.parent / ".dossier-tools"`.
- **Steps.** (1) Implement `build_env` and `run`. (2) Unit tests of `build_env` with a fake `parent` mapping: the six forbidden names (D4 table) absent; `HTTPS_PROXY` present; `HOME`, `TMPDIR`, `XDG_*` under the area; `restricted` caches under `<area>/cache`; `tool` profile `UV_CACHE_DIR` under `.dossier-tools`; registry name passed only when listed (monkeypatch `config.registry_auth`); a registry file outside home is refused. (3) Integration tests: `run(["sh", "-c", "env | cut -d= -f1 | sort"])` output equals `sorted(result.env_names)`; timeout with `sleeper.sh` from `hygiene_repo` (D4 table); a normal run that leaves a background `sleep 300 &` behind does not leave it alive; stdout and stderr go to separate files; `input=b'{"a":1}'` reaches the child's stdin (`["sh","-c","cat"]`).
- **Done-check.** Full suite passes.
- **Commit.** `feat(dossier): add the safe runner for restores and tools`

### M1-7. Restore stage and the hygiene fixture tests

- [ ] **Goal.** The restore stage (D10) and the spec section 11, item 4 tests.
- **Files.** New `scripts/restore.py`; new `tests/unit/scripts/test_restore.py` (`plans`, `decide`); new `tests/integration/scripts/test_hygiene.py`.
- **Steps.** (1) Implement D10. (2) Unit tests of `decide`, one per rule in order, including: a stored `yes` that does not cover a new ecosystem asks again; `--restore no` is stored. (3) `test_hygiene.py` drives the real stage on `hygiene_repo`: create an area with `workarea.area_for`, a checkout with `ensure_checkout`, then call `restore.run([{"ecosystem": "python", "lockfile": "uv.lock", "command": ["sh", "install.sh"], "enabled": True}], area=…, checkout=…, timeout=30, parent=<os.environ plus the six forbidden names and HTTPS_PROXY>)`, and append the result to a `build.json` with `buildlog` the way M1-10 will (one `copy`/`restore` record with `env_names`). Assert, as spec section 11 item 4 lists:
  - only allowlisted variable names appear (`env-names.txt` ⊆ `ALLOWED_NAMES`; none of the six forbidden names);
  - `HOME` is the scratch directory (`home.txt` == `<area>/home`);
  - caches land under `<area>/cache/` (every line of `cache-markers.txt`);
  - the `build.json` record has `env_names` and no parent value anywhere in the file text;
  - a feature-branch ref is refused without `--allow-ref`: `decide(plans, state={}, answer="yes", no_restore=False, trust=workarea.trusted(path, feature_sha), allow_ref=False)` → skip with a reason containing "--allow-ref"; with `allow_ref=True` → run;
  - a timed-out stage is killed and recorded: `restore.run` with `["sh", "sleeper.sh"]` and `timeout=1` → status `failed`, reason contains "took longer than 1 seconds", both PIDs gone within 3 s, and `process.coverage_items` is not available yet, so assert the record only (M1-11 adds the Gaps assertion to this file);
  - an authentication failure (`["sh", "-c", "echo 'npm ERR! code E401' >&2; exit 1"]`) gives the `registry_auth` reason.
- **Done-check.** `uv run --with pytest --with pygments python -m pytest tests/integration/scripts/test_hygiene.py -v` passes (7 or more tests), and the full suite passes.
- **Commit.** `feat(dossier): add the restore stage and the restore hygiene tests`

### M1-8. Adapter interface, extract stage, path filter

- [ ] **Goal.** D6 and D7, tested with a fixture adapter.
- **Files.** New `scripts/adapters.py`; new `tests/unit/scripts/test_adapters.py`; new `tests/integration/scripts/test_extract.py`. `shared_tools` does not exist yet, so `Context.treesitter`/`semgrep` are typed `object` here and filled with `None` in tests; M1-9 sets the real types.
- **Steps.** (1) Implement D7 and D6. (2) Unit tests of `filter_paths`: a tracked path kept; `.venv/lib/x.py` dropped expected; an absolute path outside the checkout dropped outside; `build/gen.py` with the adapter glob `build/**` dropped expected; `weird/new.py` dropped unexpected and listed; an item's `paths` list loses only dropped entries. (3) Integration test with `class FixtureAdapter(Adapter)`: `name="fixture"`, `languages=("Python",)`, `expected_untracked=(".venv/**",)`, `extract` returns `{"entry_points": [{"path": "app.py", "kind": "script"}, {"path": ".venv/x.py"}, {"path": "ghost.py"}]}`; run on a `hygiene_repo` checkout: `extract/entry_points.json` has one kept item under `adapters.fixture`; the record counts `paths_seen 3, dropped_expected 1, dropped_unexpected 1`; a second run with the same key is `reused`; changing `FixtureAdapter.version` re-runs it; an adapter with `loads_repo_code=True` on `feature_sha` is skipped with "--allow-ref" and runs with `allow_ref=True`; an adapter whose `extract` writes a tracked file in the checkout makes the step `failed` with the "clean copy changed" reason and writes nothing; an adapter that raises is `failed` and another adapter still runs; `detect(["Shell"], (FixtureAdapter,))` is empty.
- **Done-check.** Full suite passes.
- **Commit.** `feat(dossier): add the adapter interface, extract stage and path filter`

### M1-9. Shared tree-sitter and semgrep layer

- [ ] **Goal.** Locked workers and the two clients of D7.
- **Files.** New `scripts/ts_worker.py`, `scripts/ts_worker.py.lock`, `scripts/semgrep_worker.py`, `scripts/semgrep_worker.py.lock`, `scripts/shared_tools.py`, `rules/README.md`, `tests/fixtures/rules/print-call.yml`, `tests/unit/scripts/test_shared_tools.py`, `tests/integration/scripts/test_shared_layer.py`; edit `scripts/adapters.py` (types of `Context.treesitter`/`semgrep`).
- **Step 1, first: verify the tree-sitter API.** In a scratch folder (not in `SKILL`): `uv run --python 3.13 --with tree-sitter-language-pack==1.22.1 python -c "import tree_sitter_language_pack as t, tree_sitter as ts; print(t.__all__ if hasattr(t,'__all__') else dir(t)); print(ts.__version__ if hasattr(ts,'__version__') else '')"`. Continue only if `get_parser` and `get_language` exist. Then check that `tree_sitter.Query(language, source)` and `tree_sitter.QueryCursor(query).captures(node)` exist (py-tree-sitter 0.25 and later). If either check fails, **stop and report** under "Verification results" with the output; do not design a replacement.
- **Worker contracts.** Both read one JSON object on stdin and print one JSON object on stdout; they print nothing else on stdout.
  - `ts_worker.py`, header `# /// script` / `# requires-python = ">=3.10"` / `# dependencies = ["tree-sitter-language-pack==1.22.1"]` / `# ///`. Request `{"language": "python", "paths": ["a.py"], "query": "(call function: (identifier) @fn)"}` (paths relative to the current directory). Response `{"matches": [{"path", "capture", "start_line", "start_col", "end_line", "end_col", "text"}], "errors": [{"path", "error"}]}`; lines 1-based, columns 0-based; a file that cannot be read goes to `errors`.
  - `semgrep_worker.py`, dependency `semgrep==1.181.0`. Request `{"config": "/abs/rules", "paths": null, "timeout": 30}`. Runs `[Path(sys.executable).parent / "semgrep", "scan", "--config", config, "--json", "--metrics=off", "--disable-version-check", "--oss-only", "--quiet", "--timeout", str(timeout), *(paths or [])]` in the current directory; response `{"results": [{"rule": check_id, "path", "start_line", "end_line", "message", "snippet": extra.lines, "metadata": extra.metadata}], "errors": [semgrep's errors list as given]}`. Exit non-zero only when semgrep itself exits with a code other than 0 or 1.
- **Locking.** `uv lock --script scripts/ts_worker.py` and `uv lock --script scripts/semgrep_worker.py`; commit both `.lock` files. The clients run `["uv", "run", "--locked", "--python", tools["python"], "--script", str(worker)]`.
- **Clients.** `shared_tools.TreeSitter(run).query(...)` and `Semgrep(run).scan(...)` as D7: `run(cmd, input=json.dumps(req).encode(), stage="treesitter"|"semgrep", profile="tool")`, then parse `result.stdout`; timeout or non-zero → `ToolError` (message names the tool and has the last 20 lines of stderr).
- **`rules/README.md`.** One paragraph: semgrep rules shipped with dossier live here, one folder per scope (`all/`, `python/`, `js/`, `csharp/`), YAML files ending `.yml`; rule ids are `dossier.<scope>.<category>.<name>`; `metadata.category` names the `io_candidates` category the rule feeds; M1 ships no rules, M2 adds the Python set.
- **Tests.** Unit (no network): a fake `run` returning prepared stdout files checks request JSON and response parsing for both clients, and `ToolError` on non-zero and on timeout; a test asserts the version in each worker's `dependencies` line equals `tools.json`. Integration (`DOSSIER_SLOW=1` only): on a temporary folder with `a.py` containing `print("x")\nlen([])\n`, `TreeSitter.query("python", ["a.py"], "(call function: (identifier) @fn)")` returns the two calls with texts `print` and `len`; `Semgrep.scan(tests/fixtures/rules)` with `print-call.yml` (a rule `dossier.test.io.print-call`, pattern `print(...)`, language python, severity INFO, message "print call") returns one result at line 1. After the run, record in the commit message where the grammar files were stored (`find <area> <cache root>/.dossier-tools -name '*.so' | head`).
- **Done-check.** Full suite passes (slow tests skipped); `DOSSIER_SLOW=1 uv run --with pytest --with pygments python -m pytest tests/integration/scripts/test_shared_layer.py -v` passes.
- **Commit.** `feat(dossier): add the shared tree-sitter and semgrep layer`

### M1-10. Wire the stages into `prepare`

- [ ] **Goal.** `prepare` runs pin, tools, copy (checkout and restore), extract, then measure, and records each in `build.json`; the new flags work.
- **Files.** New `scripts/stages.py`; edit `scripts/dossier.py` (`cmd_prepare`, parser); new `tests/integration/scripts/test_prepare_cli.py`.
- **Interface.**
  ```python
  @dataclass
  class Options:
      ref: str; allow_missing: bool; no_restore: bool; allow_ref: bool; submodules: bool; restore: str | None; full: bool
  class Stop(Exception):
      def __init__(self, code: int, payload: dict): ...
  def stage_pin(build, top, ref) -> dict        # {"sha", "short", "trust"}; record pin
  def stage_tools(build, top, sha, opts) -> dict    # preflight report; record tools; Stop(2) when missing and not allow_missing
  def stage_copy(build, top, sha, area, state, opts, tree, trust) -> dict
      # checkout (record copy/checkout; Stop(4) on CheckoutError), then restore (record copy/restore; Stop(3) on "ask")
  def stage_extract(build, top, sha, area, out, langs, trust, opts, restored, tools) -> dict   # record extract
  ```
- **`cmd_prepare` order.** `top`, `out`, `state` as today; `area = workarea.area_for(out.name, top, root)`; `sha = git rev-parse --verify <ref>^{commit}` in `top`; `build = buildlog.start(out, repo=name, sha=sha, ref=a.ref, version=VERSION, options=…)`; then `stage_pin`, `stage_tools`, `stage_copy`, `stage_extract`, each inside `try`; on `Stop`: `save_state(out, state)`, print `json.dumps(stop.payload, indent=1)` and `sys.exit(stop.code)`. Then today's code from `gather.collect` onwards, unchanged except: (a) after `collect`, if `facts["repo"]["sha"] != sha` die with "The ref moved while prepare was running. Run it again."; (b) wrap from `gather.collect` to the end of `update_plan` in `buildlog.step(build, "measure")` and fill `counts = {"files": facts["files"]["analyzed"], "languages": len([l for l in facts["languages"] if l["kind"] == "code"]), "commits": …, "contributors": facts["git"]["contributors"]["total"]}` and `details = {"reading_mode", "chunks", "chunks_with_current_notes", "plan_mode": plan["mode"], "stale": sorted(plan["stale"]), "fresh": plan["fresh"]}`; (c) the printed JSON gains `"build": str(build)`, `"working_area": str(area)`, `"checkout": …`, `"trust": …`, `"preflight": {"languages", "missing"}`, `"restore": [...]`, `"extract": {"status", "reason"}`.
- **Record contents.** `pin`: counts none; details `{"sha", "ref", "branch_or_ref", "trust"}`. `tools`: `tools` = host tools found with versions; details = the preflight report; status `ok` (with `--allow-missing` and missing tools, still `ok`, with `details.missing` and `details.allowed_missing = true`), or `failed` with reason "Missing: node, npm." when stopping. `copy`/`checkout`: details `{"path", "created", "verified", "submodules", "submodules_on"}`. `copy`/`restore`: one record for the stage: status `skipped` with the `decide` reason, or `ok`/`failed` summarising `restore.run` results (failed if any failed; reason = the failed ones' reasons joined), with `details.ecosystems`, `env_names` (union) and `command` (the first command run). On "ask", record `skipped` with reason "Waiting for your answer about installing dependencies." before raising `Stop(3, {"stopped": "restore_question", "will_run": [{"ecosystem", "command": "uv sync --frozen", "where": checkout, "note": "Installing can run the project's own build code on this machine, with your user rights."}], "how_to_answer": "Run prepare again with --restore yes or --restore no."})`. `extract`: what `run_extract` returns; with no adapter for the languages, `skipped` "No extractors exist for these languages in this version of dossier." (the HEAD check still runs).
- **Stop payloads.** Code 2: `{"stopped": "missing_tools", "missing": [{"id", "status", "needs", "for", "install"}], "text": format_text(report), "how_to_continue": "Install the missing tools, or run prepare again with --allow-missing."}`. Code 4: `{"stopped": "checkout_failed", "reason": "..."}`.
- **Flags.** `prepare` gains `--allow-missing`, `--no-restore`, `--allow-ref`, `--submodules`, `--restore {yes,no}`. Update the module docstring line.
- **Tests (integration, real CLI with `sys.executable`).** On `hygiene_repo` (no `.py` beyond `app.py`/`feature.py`, so Python is detected): with a fake bin lacking node → exit 2, payload lists node, `build.json` has `pin` ok and `tools` failed; with `--allow-missing` → exit 3 (the `uv.lock` triggers the question), `copy`/`restore` skipped "Waiting…"; then `--allow-missing --restore no` → exit 0, `state.json` has `restore.answer == "no"`, `build.json` has records for `pin, tools, copy, extract, measure` in that order of writing; `--ref feature/x --allow-missing --restore yes` → restore skipped with "--allow-ref" (it does not run `uv sync`); `--no-restore` → skipped "--no-restore". Use `DOSSIER_HOME`, `DOSSIER_CONFIG`, `DOSSIER_CACHE` under `tmp_path`. No test runs a real `uv sync`.
- **Done-check.** Full suite passes.
- **Commit.** `feat(dossier): run preflight, checkout, restore and extract in prepare and record each step`

### M1-11. The process card, render-time records and Gaps coverage items

- [ ] **Goal.** `render` records steps 6 to 10, draws `dossier.process` from `build.json`, and adds automatic coverage items to Gaps.
- **Files.** New `scripts/process.py`; edit `scripts/render.py` (`collect_gaps(reports, extra=())`, `render_html(..., build=None)`, the `dossier` branch of `build_page`); edit `scripts/dossier.py` (`cmd_render`: load build, records, `--readers`; `cmd_confirm`: pass coverage items); new `tests/unit/scripts/test_process.py`; edit `tests/integration/scripts/test_hygiene.py` (add the Gaps assertion for the timed-out stage).
- **Fixed wording** (`process.STEP_TEXT`, copied from spec §4, keyed by step id): pin "Pinned the repository to one commit, so everything below describes that exact state."; tools "Checked that the needed tools were installed (or listed which were missing and carried on in reduced mode)."; copy "Made a clean copy of the code at that commit, and installed its locked dependencies if allowed."; measure "Measured the repository: files, languages, history, ownership, co-change."; extract "Ran the extractors to find entry points, imports, inputs and outputs, data structures and tests."; read "Read the code: how much (single read or N chunks), with how many parallel readers, and what was reused from the last build."; write "Wrote the reports: for each list a tool found, decided what to keep, merge or drop, and explained how the parts work."; check "Checked the work: citations resolve, every tool-found item is accounted for, diagrams match real dependencies, the report layout matches the standard, and the page was opened in a real browser."; gaps "Recorded the open questions in Gaps, and anything the dossier could not see."; render "Rendered the page and the machine-readable summary."
- **Run lines** (`process.run_line(step, build)`), one `<div class="muted">` under each sentence, built from the latest record(s) of that step. A `skipped` record gives `Skipped: {reason}`; `reused` gives `Reused from the previous build.`; `failed` gives `Failed: {reason}`. For `ok`:
  - pin: `Commit {short} ({ref}). {Trusted ref: <why>. | Not a trusted ref: <why>.}`
  - tools: `Languages: {names}. Tools: {id version, …}. {Missing: a, b (carried on with --allow-missing). | Nothing missing.}`
  - copy: `Clean copy checked at {short}. Dependencies: {per ecosystem "python installed (12 s)" | the restore skip reason}. Submodules: {none | off (n not analysed) | on}.`
  - measure: `{files} files, {languages} languages, {commits} commits, {contributors} contributors.`
  - extract: `{n} extractors ran ({names}); {k} reused. The path filter removed {d} of {s} paths ({u} unexpected).`
  - read: `{Single read | N chunks}; notes reused for {k} of {N} chunks; {R parallel readers, as reported by Claude | number of parallel readers not recorded}.`
  - write: full mode `{n} reports written.`; incremental `{n} reports rewritten, {m} reused.`
  - check: `{c} citations checked, {u} unresolved; layout check: {e} errors. {Browser check at HH:MM UTC: {p} problems. | Browser check: not run yet.}`
  - gaps: `{n} open items: {unknown} unknown, {inference} inferred, {assumption} assumed, {coverage} coverage.`
  - render: `Page written. The machine-readable summary is not produced in this version.`
- **Body.** `process_body(build, pending) -> str` returns `<ol class="process">` with one `<li>` per step id in order (`<p>{sentence}</p>{run line}`), then `<p class="muted">Of the {N} cards in this dossier's layout, {m} are measured by tools, {a} adjudicated (tool candidates sorted by Claude) and {r} read by Claude.</p>` (counted over `schema.load_all()`; tier `M+A` counts as adjudicated). Steps with no record show `<div class="muted">No record.</div>` (V10 reports it). All text is escaped with `render.E`.
- **Render-time records** (`process.render_records(build, *, reports, readers, v_errors, cites_checked, cites_unresolved, gap_counts) -> list[dict]`, pure; reading mode, chunk count and reused notes come from the `measure` record's `details`): `read` and `write`: if the `measure` record's `plan_mode` is `render_only` → both `reused` ("Nothing changed since the previous build."); elif `reports` is empty → both `skipped` ("No reports were written in this build."); else `read` ok with counts `{"mode", "chunks", "notes_reused", "readers"}` (readers `None` when not given) and `write` ok with `{"written", "reused"}` (full: written = number of report files; incremental: written = number of stale reports present, reused = fresh). `check`/`render`: ok or failed (failed when `v_errors` > 0, reason "{n} errors in the reports."), counts `{"citations", "unresolved", "errors"}`. `gaps`: ok, counts = `gap_counts`. `render`/`render` is **not** in this list; `cmd_render` builds it separately (below).
- **Coverage items.** `process.coverage_items(build) -> list[dict]`, each `{"kind": "coverage", "report": "dossier", "statement": …, "how_to_confirm": …}`: one per missing tool ("The tool {id} was not installed, so this build ran without it. Install it with: {install}"); one per Tier B language ("{Lang} has basic support only: no import or call graph is extracted for it."); one per skipped or failed `copy`/`restore` ecosystem other than "no lockfile" ("Dependencies were not installed for {ecosystem}: {reason}"); one for a skipped or failed `extract` ("The extractors did not run: {reason}"); one per adapter skipped or failed; one per submodule not analysed ("The submodule {path} was not analysed. Build with --submodules to include it."); one per other `failed` record ("Step '{id}' failed: {reason}"). `how_to_confirm` is the action in plain words (for example "Install the tool and build again."). Statements are deterministic, so `resolve.sync` keeps their IDs across builds.
- **`render.py` edits.** (1) `collect_gaps(reports, extra=())`: after the `gaps.json` items, append each `extra` item exactly like a `gaps.json` item (`report` = its `report`). (2) `render_html(facts, reports, state, history, version, cites, build=None)`: `ctx["build"] = build` and `ctx["gaps"] = collect_gaps(reports, process.coverage_items(build) if build else ())`. (3) In `build_page`'s `dossier` branch replace `schema_card(cards["dossier.process"], placeholder_body(cards["dossier.process"]))` with `schema_card(cards["dossier.process"], process.process_body(ctx["build"]) if ctx.get("build") else placeholder_body(cards["dossier.process"]))`. Nothing else in `render.py` changes. `import process` sits with the other local imports; `process.py` must not import `render` at module level (import `render.E` inside functions, or take an escape function) to avoid a cycle.
- **`cmd_render` order.** Load `build = buildlog.load(out)`. When it is `None` (an old dossier, or `FIX`), no record is written anywhere below and the page is drawn with `build=None` (placeholder card, no coverage items). Run `render.validate` as today and print. If `build` exists, append the `check`/`render` record (counts from `cites`, `len(errors)`). If errors and not `--allow-errors`: exit as today. Compute gaps with `collect_gaps(reports, coverage)` for `resolve.sync`/`apply` and counts. Append the `read`, `write` and `gaps` records. Build the pending `render` record in memory (`{"step": "render", "part": "render", "by": "render", "status": "ok"}`), call `process.validate_build(buildlog.load(out), [pending])` (M1-12 adds it; until then skip this call), draw with `build=<reloaded build plus pending>`, write the page, then `buildlog.append` the pending record. New option `render --readers N` (int). `cmd_confirm` passes the same coverage items to `collect_gaps` so the IDs it shows match the page.
- **Tests.** `process_body` on a hand-built build with all ten steps has ten `<li>` in order and the tier line; a step without a record shows "No record."; `run_line` for each status; `render_records` for `render_only`, no reports, full and incremental; `coverage_items` for each kind; `collect_gaps` with `extra` keeps old behaviour when `extra` is empty (existing tests stay green) and lists the extra item; the hygiene test now also asserts that `coverage_items` of the timed-out build contains one item mentioning "took longer than".
- **Done-check.** Full suite passes; section 6 block E prints `OK`.
- **Commit.** `feat(dossier): draw the process card from build.json and add coverage items to Gaps`

### M1-12. V9 and V10

- [ ] **Goal.** `render` checks the run record (D8) and prints V9 as info.
- **Files.** Edit `scripts/process.py` (`validate_build`), `scripts/dossier.py` (`cmd_render` calls it, prints `info:` lines, adds V10 errors to the blocking errors); edit `tests/unit/scripts/test_process.py`.
- **Steps.** (1) Implement D8 and D6's V9 text. (2) In `cmd_render`, at the point M1-11 left for it: `errs, infos = process.validate_build(build, [pending])`; print each info as `info: …`; each error as `error: …`; if errors and not `--allow-errors`, print the usual "{n} error(s)…" line and exit 1 without writing the page or the `render` record. (3) Tests: no build → the "no build.json" error; a build missing `extract` → error naming step 5 and its sentence; a `skipped` record with an empty reason → error; all ten present → no errors; V9 texts for skipped extract, for a run with 0 unexpected, and for 25 unexpected (lists 20 and "and 5 more").
- **Done-check.** Full suite passes; section 6 block E prints `OK` and its render log has exactly one `error:` line, starting `error: V10: there is no build.json`.
- **Commit.** `feat(dossier): check the run record in render (V9 and V10)`

### M1-13. Browser check record

- [ ] **Goal.** `check_page.py --record BUILD_JSON` appends the `check`/`browser` record.
- **Files.** Edit `scripts/check_page.py` (`main`); new test in `tests/unit/scripts/test_buildlog.py` for the record shape it writes (call the small helper below directly; do not start a browser in tests).
- **Steps.** (1) Add `ap.add_argument("--record", help="build.json to append the result to")`. (2) Add a helper `record_result(path, problems, n)` that imports `buildlog` (the script's folder is first on `sys.path` when run as a script) and appends `{"step": "check", "part": "browser", "by": "check_page", "status": "ok" if not problems else "failed", "reason": None if not problems else f"{len(problems)} problems in the browser check.", "counts": {"problems": len(problems), "diagrams_checked": n}}`. (3) Call it in `main` after printing, before `sys.exit`, when `--record` is given.
- **Done-check.** Full suite passes; `uv run scripts/check_page.py --help` lists `--record`.
- **Commit.** `feat(dossier): let check_page record the browser check in build.json`

### M1-14. Docs

- [ ] **Goal.** SKILL.md and README describe the new commands and flags; the interim notice stays.
- **Files.** Edit `SKILL.md`, `README.md`, `scripts/dossier.py` (module docstring only, if not already done).
- **Steps.** (1) SKILL.md front matter: `description` unchanged; `argument-hint` adds `doctor [repo]`, `clean [repo]` and the build flags `[--allow-missing] [--no-restore] [--allow-ref] [--submodules]`. (2) New sections `/dossier doctor [repo]` ("Run `DOSSIER doctor <repo>` and show the output. It lists the tools this repository needs, which are installed, and how to install the missing ones. It installs nothing.") and `/dossier clean [repo]` ("Run `DOSSIER clean <repo>`. It deletes the working copy, the scratch home folder and the package caches dossier keeps for this repository under `~/.local/cache/dossier/`. The dossier itself is not touched."). (3) Under `/dossier build`, below the interim notice, a short paragraph on the flags and on the two stops: exit code 2 lists missing tools (show the list; offer `--allow-missing`); exit code 3 asks about installing dependencies (show `will_run` and the note in plain words, ask the user, then run `prepare` again with `--restore yes` or `--restore no`). (4) Step 7: the command becomes `uv run ${CLAUDE_SKILL_DIR}/scripts/check_page.py <html> --shots <dir> --record <out_dir>/build.json`, and after it prints `"problems": 0` run `DOSSIER render <repo>` once more so the page shows the browser check. Step 6: pass `--readers N` when subagents read the code. (5) "Rules that always apply": add "Never edit `build.json`. It is the record of what the tools did, written only by the scripts." (6) README: one sentence after the 0.5.0 sentence: "Version 0.6.0 adds `doctor`, `clean`, a clean working copy for every build, a run record (`build.json`) and the 'How this dossier was made' card." Follow `docs-readme` for tone; do not rewrite the README (that is M6).
- **Done-check.** `grep -n "doctor\|clean\|build.json\|--record" SKILL.md` shows the new lines; full suite passes.
- **Commit.** `docs(dossier): document doctor, clean, the build flags and the run record`

### M1-15. Version 0.6.0

- [ ] **Goal.** Bump the version as the `git-release` skill describes for this repository (encamp has no release CI for the skill; the bump is a commit).
- **Files.** `VERSION`.
- **Steps.** Follow `git-release`. `VERSION` contains `0.6.0`.
- **Done-check.** `uv run scripts/dossier.py version` prints `dossier 0.6.0`; full suite passes.
- **Commit.** `chore(dossier): bump to 0.6.0`

### M1-16. Sign-off run

- [ ] **Goal.** Prove the exit criterion and record it.
- **Files.** This plan only (tick boxes; paste outputs under "Verification results").
- **Steps.** Run every block in section 6 in order. Paste each block's output (trim long JSON to the lines named under "Expected"). List any deviation from this plan under "Deviations".
- **Done-check.** Every block prints what its "Expected" line says.
- **Commit.** `docs(dossier): record the M1 verification run in plan 006`

### Cut line

If the session runs short, drop in this order, and record what was dropped under "Verification results":

1. `render --readers` (the card then always says "number of parallel readers not recorded").
2. M1-13, the browser check record (the card says "Browser check: not run yet").
3. Registry credential **files** in `registry_auth` (keep variable names).
4. Block F (the slow shared-layer run) at sign-off; the unit tests of M1-9 stay.
5. The real `uv sync --frozen` in block B (run block B with `--restore no` instead).

Never drop: the runner (M1-6), the hygiene tests (M1-7), `doctor`, checkout and `clean`, `build.json`, the process card, V9 and V10.

### Acceptance criteria

- `doctor` on `REPO` with node removed from `PATH` lists node and npm as missing with install commands and exits 1; with node present it exits 0 (block A).
- `prepare` on `REPO` produces a verified checkout in the working area at the pinned commit and a `build.json` with records for pin, tools, copy, extract and measure (block B).
- `render` of that build draws the `dossier.process` card with ten steps from `build.json`, V10 passes, V9 prints an info line (block C).
- A build with a host tool missing under `--allow-missing` produces the matching Gaps entries (block C2).
- The hygiene tests pass (block D).
- Report 02 is unchanged (block E). `check_page.py` reports `"problems": 0` on the block C page, or only the dark-theme code-viewer contrast failure accepted in plan 005.
- The full suite passes (block G), and `clean` removes the working area and nothing else (block H).

### Branch and release

All tasks commit on `feat/dossier-m1`. After M1-16, follow `git-workflow` to merge into `main` (a merge commit, as for `feat/dossier-m0`) and push if that skill says to. The version bump is M1-15.

---

## 6. Verification

Set once per shell:

```bash
SKILL=/home/nick/dev/projects/encamp/configs/user/claude/.claude/skills/dossier
REPO=/home/nick/dev/projects/cannalerts
FIX=$SKILL/tests/fixtures/encamp-m0
SCR=$(mktemp -d)
export DOSSIER_HOME=$SCR/home DOSSIER_CONFIG=$SCR/cfg.json DOSSIER_CACHE=$SCR/cache PYTHONDONTWRITEBYTECODE=1
BASE=fe72cec488cb211edd6919154bf4d3ed68845e4e33b667a1874716a96bb63b59
cd $SKILL
```

**Block A: `doctor`, with and without node.**

```bash
uv run scripts/dossier.py doctor $REPO; echo "exit $?"
mkdir -p $SCR/bin && for t in git uv; do ln -sf "$(command -v $t)" $SCR/bin/$t; done
PATH=$SCR/bin $(command -v uv) run --python /usr/bin/python3 scripts/dossier.py doctor $REPO; echo "exit $?"
```

Expected: first run lists git, uv, node and npm as `ok`, the self-installing tools for Python, `Nothing is missing.`, `exit 0`. Second run: `MISSING  node` and `MISSING  npm`, each with an `Install:` line, scip-python "(cannot install: needs node, npm)", `exit 1`.

**Block B: verified checkout of a real Python repository** (the restore runs `uv sync --frozen` in the copy, with the scratch home and private caches; see Q1):

```bash
uv run scripts/dossier.py prepare $REPO --ref main > $SCR/p1.json; echo "exit $?"
uv run scripts/dossier.py prepare $REPO --ref main --restore yes > $SCR/p2.json; echo "exit $?"
export SCR REPO
python3 - <<'PY'
import json, os, subprocess
scr, repo = os.environ["SCR"], os.environ["REPO"]
p = json.load(open(f"{scr}/p2.json"))
co = p["checkout"]["path"]; sha = p["sha"]
head = subprocess.run(["git", "-C", co, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
dirty = subprocess.run(["git", "-C", co, "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True).stdout
b = json.load(open(p["build"]))
print("checkout", "verified" if head == sha and not dirty else "NOT VERIFIED", co)
print("trust", p["trust"])
print("steps", [(r["step"], r.get("part"), r["status"]) for r in b["records"]])
rest = [r for r in b["records"] if r.get("part") == "restore"][-1]
print("restore env names", rest.get("env_names"))
print("venv in copy", os.path.isdir(os.path.join(co, ".venv")))
print("uv cache private", os.path.isdir(f"{scr}/cache/cannalerts/cache/uv"))
print("user repo untouched", subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True, text=True).stdout == "")
PY
```

Expected: `exit 3` (the restore question; `p1.json` names `uv sync --frozen`), then `exit 0`; `checkout verified`; trust "tip of the default branch origin/main" (or "reachable from …"); steps `pin ok`, `tools ok`, `copy checkout ok`, `copy restore ok`, `extract skipped`, `measure ok`; the env names contain only allowlisted names; `venv in copy True`; `uv cache private True`; `user repo untouched True` (if cannalerts had uncommitted changes before, compare with its status before the run instead). If Q1 is answered "no", run the second command with `--restore no` and expect `copy restore skipped`.

**Block C: the process card from a real build, V10 and V9.**

```bash
uv run scripts/dossier.py render $REPO --partial > $SCR/r1.log; echo "render exit $?"
grep -E '^(error|info):' $SCR/r1.log
HTML=$DOSSIER_HOME/cannalerts/dossier-cannalerts.html
python3 - "$HTML" <<'PY'
import re, sys
html = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r'data-card="dossier.process".*?</section></div>', html, re.S)
card = m.group(0)
print("process card steps:", card.count("<li>"), "| placeholder:", "Not yet generated" in card)
PY
uv run scripts/check_page.py "$HTML" --shots $SCR/shots --record $DOSSIER_HOME/cannalerts/build.json | tail -3
uv run scripts/dossier.py render $REPO --partial > $SCR/r2.log; echo "render exit $?"
```

Expected: `render exit 0`; no `error:` line; one `info: V9: no extractor ran in this build, so the path filter had nothing to check.`; `process card steps: 10 | placeholder: False`; `check_page` last line `"problems": 0` (or only the accepted dark-theme code-viewer contrast failure from plan 005; anything else must be fixed); second render exits 0. Then open `$HTML` in a browser (or a screenshot from `$SCR/shots`) and read the card: steps 6 and 7 say "Skipped: No reports were written in this build.", step 8 shows the browser check time.

**Block C2: a build with a tool removed produces Gaps entries.**

```bash
PATH=$SCR/bin $(command -v uv) run --python /usr/bin/python3 scripts/dossier.py prepare $REPO --ref main --allow-missing --no-restore > $SCR/p3.json; echo "exit $?"
uv run scripts/dossier.py render $REPO --partial > /dev/null; echo "render exit $?"
for s in "The tool node was not installed" "The tool npm was not installed" "Dependencies were not installed for python" "The extractors did not run"; do
  grep -q "$s" $DOSSIER_HOME/cannalerts/dossier-cannalerts.html && echo "in Gaps: $s" || echo "MISSING FROM GAPS: $s"
done
```

Expected: `exit 0`, `render exit 0`, and four `in Gaps:` lines. (`confirm` cannot be used here: it needs written reports, and this build has none.)

**Block D: hygiene tests.**

```bash
uv run --with pytest --with pygments python -m pytest tests/integration/scripts/test_hygiene.py -v
```

Expected: all pass (allowlisted names only, scratch `HOME`, private caches, names recorded without values, feature branch refused without `--allow-ref`, timed-out stage killed and recorded and listed in Gaps, authentication failure reason).

**Block E: report 02 unchanged** (after every task that edits `render.py`, and at sign-off):

```bash
rm -rf $SCR/home && mkdir -p $SCR/home && cp -r $FIX $SCR/home/encamp && chmod -R u+w $SCR/home/encamp
rm $SCR/home/encamp/dossier-encamp.html
uv run scripts/dossier.py migrate /home/nick/dev/projects/encamp > /dev/null; echo "migrate exit $?"
uv run scripts/dossier.py render /home/nick/dev/projects/encamp --allow-errors > $SCR/e.log; echo "render exit $?"
grep '^error:' $SCR/e.log
python3 tests/tools/report_section.py $SCR/home/encamp/dossier-encamp.html overview --digest --normalize | grep -q "^$BASE " && echo OK || echo DIFFERENT
```

Expected: `migrate exit 0`, `render exit 0`; before M1-12 no `error:` line, from M1-12 exactly one, `error: V10: there is no build.json. Run prepare first.`; then `OK`. (This block wipes `$SCR/home`; run it last at sign-off, or re-run blocks B and C after it.)

**Block F: shared layer with the real tools** (needs the network):

```bash
DOSSIER_SLOW=1 uv run --with pytest --with pygments python -m pytest tests/integration/scripts/test_shared_layer.py -v
```

Expected: both tests pass. Record where the grammar files landed.

**Block G: full suite.**

```bash
uv run --with pytest --with pygments python -m pytest tests -q
```

Expected: all pass (227 before M1, more after).

**Block H: `clean`.**

```bash
uv run scripts/dossier.py clean $REPO; echo "exit $?"
test -d $DOSSIER_CACHE/cannalerts && echo "STILL THERE" || echo "area removed"
test -f $DOSSIER_HOME/cannalerts/build.json && echo "dossier kept" || echo "DOSSIER GONE"
```

Expected: "Removed the working area …", `exit 0`, `area removed`, `dossier kept`. (Run before block E, which replaces `$SCR/home`.)

**Order at sign-off:** A, B, C, C2, D, F, G, H, then E.

**Recording results.** Under "Verification results" at the end of this plan, write the date and branch, then for each block the commands' key output lines (as in plan 005), what was cut and why, and a "Deviations" list. Tick each task's box as its done-check passes, in the same commit as the task.

---

## 7. Risks and open questions

### Risks (most important first)

1. **Builds and the slow tests need the network.** The tree-sitter grammars download on first use, the semgrep wheel and the locked worker environments download on first run, and `uv sync --frozen` downloads the repository's packages. An offline machine fails those stages; they are recorded as failed in `build.json` and Gaps, but a build is less useful. The unit tests do not need the network.
2. **Restores run the repository's code on this machine** (spec decision 5, accepted). Block B runs `uv sync --frozen` on `REPO`, which builds the project with its build backend. The hygiene rules reduce what it can reach (no SSH agent, no tokens, scratch home, private caches); they do not isolate it.
3. **The tree-sitter-language-pack 1.22.1 Python API and grammar cache location are not verified** (the 1.x docs show `get_language()` and a `process()` API; the 0.13 docs show `get_parser`). M1-9 checks it first and stops if it differs; that would push the shared layer to a follow-up.
4. **The process-group kill does not catch a process that starts its own session** (`setsid`, double fork into a new session). Such a process would survive a timeout. Detecting it would need cgroups or a sandbox, which decision 5 rules out.
5. **V10 makes every existing dossier fail `render`** until it is rebuilt with `prepare` (including `FIX`, which block E renders with `--allow-errors`). Together with the 0.6.0 bump this is intended, but it means M2 must keep using `--allow-errors` for any `FIX`-based check.
6. **This machine's Node is 20.19.2.** That is enough for Python (scip-python needs 16), but scip-typescript and dependency-cruiser need 22 or later, so `doctor` will report JS/TS repositories as "TOO OLD" until Node is upgraded (before M4).
7. **The trusted-ref check trusts the local `main`/`master`** when there is no `origin/HEAD`, including unpushed commits. That follows the spec's wording.
8. **`git clone --local` from a linked worktree or a repository on another filesystem** was not tested; git copies instead of hardlinking across filesystems, which costs disk space for large repositories.
9. **I read** `dossier.py` and `gather.py` in full, `resolve.py` in full, and the parts of `render.py` (`validate`, schema cards, `collect_gaps`, `panel_dossier`, `build_page`, `render_html`), `incremental.py`, `deps.py`, `check_page.py` and `tests/conftest.py` that M1 touches. I did not read `viewer.py`, `migrate.py`, `dossier.js` or `deps.py` beyond its outline.

### Questions for the human

Each has a default the implementer uses if you answer "go ahead".

- **Q1.** May block B run `uv sync --frozen` on `/home/nick/dev/projects/cannalerts` (your repository; it builds the project with its own build backend, inside the copy, with the scratch home)? Default: yes. If no, block B uses `--restore no`.
- **Q2.** Restore question flow: `prepare` stops with exit code 3, Claude asks you, and `prepare` runs again with `--restore yes|no` (stored per repository in `state.json`). Default: yes.
- **Q3.** Record the number of parallel readers with `render --readers N` (a number Claude passes, labelled "as reported by Claude"), or leave it out of the card? Default: add the flag.
- **Q4.** The browser check is recorded by `check_page.py --record` and shown on the next render, and SKILL.md adds one final `render` after a passing check. Default: yes.
- **Q5.** Share the pinned tool wheels and grammars across repositories in `~/.local/cache/dossier/.dossier-tools/` (not removed by `clean`), rather than one copy per repository. Default: share.
- **Q6.** Keep `extract/` in the dossier output folder (next to `facts.json`), not in the working area. Default: output folder.
- **Q7.** Accept the pins in D1 (newest release at least 14 days old; re-checked when each tool is first used), with TypeScript left unpinned until M4. Default: accept.
- **Q8.** Version 0.6.0. Default: yes.
- **Q9.** Turn on the real Python restore (`uv sync --frozen`) in M1, with npm and NuGet restores present but off until M4 and M5. Default: yes.
- **Q10.** If M1-9's first step finds that tree-sitter-language-pack 1.22.1 has no `get_parser`/`get_language`, should the implementer stop (default), or pin the last 0.x release that has them?

---

## 8. Spec issues

Not worked around in the plan, except where stated.

1. The working-area root `~/.local/cache/dossier` is not the usual XDG cache location (`~/.cache`). The plan follows the spec; `cache_dir` can change it.
2. 5.1 step 3 says "Tier 2 only" and "falls back to Tier 1", but section 6.3 defines only Tier A and Tier B. The plan reads them as "with installed dependencies" and "without".
3. 5.1 runs extract before the facts, while the §4 step list puts "Measured the repository" (4) before "Ran the extractors" (5). Harmless: the card follows §4's numbering, `prepare` follows 5.1's order.
4. Steps 6, 7 and 9 of the process list are done by Claude, and "Claude never edits" `build.json`. The spec does not say who records them. The plan has `render` derive them from files, plus `render --readers` for the one number no file holds (Q3).
5. Step 8 includes "the page was opened in a real browser", which happens after `render` has written the page. The plan records it from `check_page.py` and shows it on the next render (Q4).
6. `dossier.process` says "8 to 10 steps", but the fixed list has exactly ten. The plan always shows ten.
7. Report 01's freshness BAN (question 10.3) and "extractor list with versions" are in §4 but not in any milestone's content in §10. The plan shows tool versions in the process card; the freshness BAN is not built.
8. "The affected cards are badged 'partial'" needs a map from tools to cards that does not exist until adapters do. Moved to M2.
9. §6.2's row "`dotnet list package --include-transitive`": since .NET 10 the command is `dotnet package list`, and it restores automatically unless `--no-restore` is passed, so it must run under the restore hygiene rules or with `--no-restore`.
10. §6.2 says Node and npm are host prerequisites but gives no version. scip-typescript supports Node 22 and 24 only, and dependency-cruiser 18 needs `^22 || ^24 || >=26`; scip-python needs 16.
11. The "shipped script on the TypeScript compiler API" depends on which TypeScript: the current release (7.x) is the native port. Choose 5.9.x, 6.0.x or the new API at the start of M4.
12. knip loads its configuration through jiti and dependency-cruiser loads `.dependency-cruiser.js` as a Node module, so both run repository code; this confirms that the Node extractors need the hygiene rules. scip-typescript also needs the dependencies installed first, which ties it to the restore.
13. grimp needs the package importable and writes `.grimp_cache` into the current folder by default. M2 must pass `cache_dir=None` or a path in the working area, or the path filter and `git clean` will keep meeting it.
14. tree-sitter-language-pack 1.x downloads grammars at first use, so "installs itself" also means network access at build time, and its cache location is a hygiene question the spec does not cover.
15. 5.4 rule 1 lists only upper-case proxy variables (`HTTP_PROXY`, …); many tools read the lower-case forms (`http_proxy`). The plan passes exactly the spec's names.
16. 5.4 rule 1's allowlist does not name the private cache variables of rule 3 (`UV_CACHE_DIR`, …), which must be passed for rule 3 to work. The plan passes them.
17. `registry_auth` "names the variables or config files to pass, per ecosystem" without a format. The plan defines one (section 3 item 21).
18. scip-dotnet's README asks for .NET 8; its behaviour on .NET 10 is not stated. Check at the start of M5 (decision 2 already says so).
19. 5.2 says `clean` "removes cached checkouts"; 5.4 rule 3 says it "removes the whole working area". The plan removes the whole working area.
20. Restores look for lockfiles at the repository root only. The spec does not say what happens in a monorepo with several lockfiles.
21. The process card's last line counts "measured, adjudicated and read" cards; the spec has a fourth tier, M+A. The plan counts M+A as adjudicated.
22. "Ask once" assumes an interactive `prepare`; it is run by Claude. The plan stops `prepare` and lets Claude ask (Q2).
23. Semgrep's docs tie login to registry configurations such as `--config auto`, but do not say outright that local rules never need it. Inferred; the M1-9 slow test confirms it in practice.
24. 5.3 keys extractor outputs by `(sha, extractor version)`, but a change in a tool's version changes the output too. The plan adds the tool versions to the key.
25. Section 11 has two items numbered 5 (already noted in plan 005).

---

## Verification results

(Filled in by the implementing session.)
