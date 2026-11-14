# Plan: fix `npm.cmd` launching and the `scip-python` Windows crash in the dossier skill

Audience: Claude Code, run on the personal machine, asked to "follow the plan in dossier-windows-fixes-plan.md".
Skill repo: https://github.com/1npo/dossier (local clone is the skill folder, `~/.claude/skills/dossier`).
Written 2026-11-13 from a work-machine session. Nothing in this plan has been applied to the skill yet.

Ground rules for whoever follows this plan:

- Make the fixes in the dossier **source repository** (a normal clone with a branch and PR), not by hand-editing an installed copy. The skill docs say the installed folder is a synced clone, so edits there conflict with the next update.
- Use targeted edits (str_replace style), not whole-file rewrites.
- Stop and ask before pushing, opening a PR, or changing anything outside the dossier repo.
- Never print or copy tokens from `~/.npmrc` or environment variables.

## Problem 1: dossier cannot start `npm` on Windows

Symptom: every `scip-python` (and JS tool) install fails with `Could not start npm: [WinError 2] The system cannot find the file specified`, reported by `prepare` as `scip-python failed (exit 127)` or similar. Log lines are in `~/.local/cache/dossier/<repo>/logs/scip-install-N.err`.

Cause: on Windows `npm` is a script, `npm.cmd`. `subprocess.Popen(["npm", ...])` without a shell only finds `.exe` files, so it fails even when npm is on PATH.

Where it happens:

- `src/dossier/tooling/sandbox.py`, function `run()` (about line 169). It calls `subprocess.Popen(cmd, ...)` at about line 188 with `cmd[0]` unchanged. The error text is written at about line 190.
- Callers that pass the bare name `"npm"`: `src/dossier/adapters/python/scip.py` (line ~42) and `src/dossier/adapters/js/tools.py` (line ~52). `node` is a real `node.exe`, so it works.
- `sandbox.py` already does `shutil.which(t["command"][0], path=parent.get("PATH", ""))` at about line 75 for another purpose, which shows the pattern.

Fix (one place covers all callers): in `sandbox.run()`, before `Popen`, resolve the executable with the PATH of the environment the child will get:

1. Build `env` as the function already does.
2. `exe = shutil.which(cmd[0], path=env.get("PATH"))` (on Windows this honours `PATHEXT`, so it returns `C:\node\npm.CMD`).
3. If `exe` is found, use `[exe, *cmd[1:]]`; otherwise keep `cmd` so the existing error path still reports "Could not start ...".
4. Keep this a no-op on non-Windows (resolving to an absolute path is harmless there too, but do not change behaviour more than needed).

Check that `env["PATH"]` in the "tool" and "restricted" profiles still contains the Node folder (`C:\node` on the work machine). If a profile strips PATH, resolve against the parent process PATH instead.

Caveat to test: Python can run a `.cmd` through `Popen` with a full path on Windows (it goes via `cmd.exe`). Arguments with spaces or `&`/`^` can be mangled by `cmd.exe`. The npm arguments here are plain flags, so this is fine, but do not pass untrusted values this way.

Tests to add (follow `py-unit-tests` conventions if that skill is installed; tests live in the dossier repo's own test folder):

- A unit test for `run()` that puts a fake `npm.cmd` (a tiny batch file that echoes and exits 0) in a temp dir on `PATH`, calls `run(["npm", "--version"], ...)`, and asserts it starts and the exit code is 0. Skip the test when not on Windows.
- A test that a command that truly does not exist still produces the "Could not start" message.

## Problem 2: `scip-python` 0.6.6 crashes at startup on Windows

Symptom: after npm works, `scip-python` exits 1 immediately. Log `~/.local/cache/dossier/<repo>/logs/scip-python-N.err` shows `SyntaxError: Invalid regular expression: /\/g: \ at end of pattern` from `PythonEnvironment.ts:4`.

Cause: upstream `@sourcegraph/scip-python` 0.6.6 has `const pathSepRegex = new RegExp(path.sep, 'g')`. On Windows `path.sep` is `\`, which is not a valid regex on its own. This is an upstream bug.

Step A (check upstream first): look at whether a newer `@sourcegraph/scip-python` fixes it (read its changelog or source for `pathSepRegex`). If a fixed version exists and its lockfile resolves cleanly, the preferred fix is to bump the pinned version in the shipped resource folder `src/dossier/data/node/scip-python/` (`package.json` and `package-lock.json`), regenerate the lockfile with `npm install --package-lock-only`, and bump the folder name/version key used by `install_dir()` in `scip.py` so the cache refreshes. Re-run the full verification below.

Step B (only if no fixed version exists): patch after install, inside `ensure_installed()` in `src/dossier/adapters/python/scip.py`, before the `.installed` marker is written:

1. Target file: `<install dir>/node_modules/@sourcegraph/scip-python/dist/scip-python.js` (the webpack bundle). The 0.6.6 bundle contains exactly one occurrence of `new RegExp(o.sep,"g")`.
2. Replace that exact text with `new RegExp(o.sep.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"),"g")` (escapes the separator before building the regex).
3. Do the replacement only on Windows, only if the exact original string occurs exactly once, and only if the file has not already been patched. If the string is not found (a different version), do nothing and let the normal run report whatever happens.
4. Keep a `.orig` copy beside the file on first patch.
5. The marker file must still hold the lockfile SHA-1 (`_lock_sha()`). Patching a file under `node_modules` does not change that, so the marker logic stays as it is.
6. Log in the build output that a Windows patch was applied, so it is visible in `build.json`/warnings, not silent.

Note: the bundle is minified, so the variable name `o` is specific to 0.6.6. Match on the full literal and fail closed.

Do not copy these exact one-liners blindly through a shell: a first attempt on the work machine lost a backslash to shell quoting and produced a broken regex. Put the patch logic in a Python function in the repo and unit test it with a string fixture.

Tests to add: a unit test for the patch function (input bundle text containing the original expression returns the patched text; text already patched is unchanged; text with the expression twice or zero times is left alone).

## Problem 3 (environment, not a dossier bug): npm registry and TLS settings

Seen on the work machine, listed here so the personal-machine run does not trip on them:

- `~/.npmrc` pointed npm at an internal Artifactory mirror whose token was rejected (HTTP 401). `npm ci` of the lockfile (which pins `registry.npmjs.org` URLs) failed. The workaround used was `npm ci --registry=https://registry.npmjs.org/ --replace-registry-host=never` in the tool cache folder. The personal machine probably does not have this; if it does, ask before overriding any registry setting.
- The work shell had `NODE_TLS_REJECT_UNAUTHORIZED=0` set (it disables certificate checking and npm prints a warning). Do not copy that setting anywhere, and do not set it in the skill.
- Optional improvement for the dossier repo: have the `scip-install` failure message include the last line of npm's stderr (for example E401) so a failure like this is visible in `prepare` output instead of just `exit 1`.

## Problem 4: the build leaves scratch files in the dossier home

Symptom (seen 2026-11-13, screenshot from the work machine): after one `/dossier build`, the dossier home (`C:\dev\_dossiers`) held, next to the expected `index.html` and `usps-pipeliner/` folder, a pile of files the build produced along the way: `prep2.json`, `prep3.json` ... `prep5.json` and matching `.err` files, `render1.out`, `render2.out` and `.err` files, and `check1.out` / `check1.err` (the last two were 0 KB because the background browser check was killed when the session ended).

Cause: these were not written by the dossier scripts. They were redirected command output (`> <home>/prepN.json 2> ...`) that the assistant ran while following SKILL.md, which never says where scratch output should go or that it must be removed. So the fix is in the skill's instructions, plus an optional safety net in the CLI.

Fix, in the dossier source repo:

1. `SKILL.md` (the build steps and "Rules that always apply"): add a rule that every temporary file made during a build (captured command output, helper scripts, merged JSON for `verify-record`, screenshots copied for viewing) goes in the session scratchpad or the OS temp folder, **never** in `<home>`, `<home>/<repo>/`, or the repository being analysed.
2. `SKILL.md` step 8 (Finish): add a cleanup step before reporting. It must (a) list what is in `<home>` and `<home>/<repo>/`, (b) delete only files the assistant itself created during this build that are not part of the expected layout, (c) never delete reports, notes, `state.json`, `build.json`, `reports.prev/`, or anything it did not create, and (d) tell the user what it removed. Define the expected layout there so the assistant can tell: in `<home>`: `index.html` and one folder per repository; in `<home>/<repo>/`: the files the CLI writes (for example `facts.json`, `chunks.json`, `build.json`, `state.json`, `reports/`, `notes/`, `extract/`, the HTML page, `summary.json`, `.check-shots/`).
3. `SKILL.md`: when a command is run in the background (for example `check`), say that its output file must be in the scratchpad, and that the assistant must wait for it or stop it before finishing, so no half-written files are left.
4. Optional CLI safety net: a `dossier tidy [repo]` command (or a final warning from `render` / `check`) that lists files in `<home>` and `<home>/<repo>/` that are not in the known layout. Default is list only; deleting needs an explicit flag. Keep the cache folder (`~/.local/cache/dossier/...`) out of this; `dossier clean` already handles that.
5. Also say in SKILL.md whether the working copy and tool cache are kept after a build (they are, until `/dossier clean`), so the user is not surprised by them.

Tests: if `dossier tidy` is added, test it with a temp home containing the expected layout plus a few stray files, and assert it lists exactly the strays and deletes nothing without the flag.

Applying it now to the work machine (not part of the skill change): the stray files from the screenshot are the assistant's own scratch output and can be deleted by name: `prep2/3/4/5.json`, `prep2/3/4/5.err`, `render1/2.out`, `render1/2.err`, `check1.out`, `check1.err` in `C:\dev\_dossiers`. Also `C:\dev\_dossiers\render*` and `prep*` were the only such files; do not touch `index.html` or `usps-pipeliner/`.

## Part B: page layout and content changes requested by the user

These come from the user's review of the first dossier (usps-pipeliner, 2026-11-13). They change the renderer, the page assets and the report-writing rules, so they belong in the dossier source repo, on the same branch or a second one.

Source locations found in the installed skill (line numbers are from that copy and may have moved):

- `src/dossier/render/page.py`: the "Tool findings: N found, N kept in N rows, N dismissed ..." line is built around line 914 (class `cand-foot`). The `<details class="not-applicable"><summary>Not applicable</summary>` block is built around lines 951-954. The "Not applicable: ..." paragraph for a card with `na` is around line 782. The `partial` badge is around line 756, and the data for it (`process.partial_cards`) is passed in around line 1877.
- `src/dossier/render/process.py`: `partial_cards()` and the code that decides a card is partial (around lines 389 and 454-457).
- `src/dossier/data/assets/dossier.js`: the text "Scroll sideways for more columns." is added at about line 64 (class `table-hint`).
- `src/dossier/render/measured/`: the cards drawn from measurements (overview, contributors, secret signals, releases, languages).
- `src/dossier/checks/page_audit.py` (about line 156) and `src/dossier/checks/layout.py` (about line 115) look for the words "Not applicable" and the `none-found` class. Update them in step with any change to those elements, or `check` will fail.
- Report-writing rules live in `prompts/method.md` and `prompts/reports.md`; schemas in `src/dossier/data/schemas/cards/`.

### Gate before any work on Part B

Before changing any code, send the user one message with itemized lists (card title and report, one line each), built by scanning the built page and the card schemas, not from memory:

1. Every card that shows the "Tool findings: ..." line (item B1).
2. Every card that has a "Not applicable" dropdown, in any report (item B3).
3. Every table where one column is much wider than the useful columns (item B4).
4. Every card with a standalone text block next to a table, diagram or other element (item B5).
5. Every measured card or table that is hidden when it has no data (items B6, B8, B9).
6. Every card with a `partial` badge, with its tooltip text (item B10).

Wait for the user's reply before starting. The user has already answered the three questions that were open (B1 is a plain row number, B3 gets no new heading, B4 is the citation column), so do not ask them again; ask only about anything new you find ambiguous.

### B1. Remove the "Tool findings" line, add an ID column

- Remove the `cand-foot` line ("Tool findings: 102 found, 31 kept in 31 rows, 71 dismissed, 29 rows added by Claude.") from every card, entirely. The user finds it confusing and misleading.
- Add a first column to each table that has tool findings: a plain row number (`#`), 1, 2, 3 ... in the order the table is drawn by default. That is all: no finding ids, no tooltips and no extra text in the cell. (The user confirmed this reading: "just a row number, essentially".)
- The column must be sortable like the others, and the page check "columns not sortable" must still pass.

### B2. Filter toggles for findings

- Add a toggle group to every card in the B1 list with four options: `All`, `Kept`, `Dismissed`, `Added by Claude`. The first is the default.
- "Kept" shows rows that cite a finding. "Added by Claude" shows rows marked `added`. "Dismissed" shows the dismissed findings, so the renderer must draw them (they exist only in the card's `dismissed` list with a reason today): show each dismissed finding as a row with its id, location, a short description of what it matched and the dismissal reason, in the same table style, hidden until that option is chosen. Include them in the page search index only when visible.
- Placement and style must match the existing toggles in other cards (for example Zoom and Show in the graph card, or the 12 months / all time switch in hotspots): same component, same position (top-right of the card, above the table), same keyboard behaviour. Reuse the existing toggle markup and CSS; do not invent a new one.

### B3. Replace the "Not applicable" dropdown

- Problem: the `<details>` dropdown sits directly under the table like plain text, with no spacing, and only a hand cursor shows it is clickable. Found in the Extension points card and the State ownership card, and likely in every card whose report has `not_applicable` (V13 cards: Extension points, Source of truth, Lifecycle and sensitive fields, Business rules, Key flows, and others). The gate message must list every one.
- Fix: do not hide the information, and do not add any heading or subheading to the card. The user has said explicitly that they do not want new headers in cards (they have found earlier headers lazy, sloppy and badly spaced). Show it as a visible alert box (the B5 box, note variant) placed under the table with normal card spacing. It holds one plain sentence saying these components are not covered by this card, followed by a compact list or two-column table of Component and Reason. No `<h*>` element, no bold pseudo-heading and no separate caption.
- Do not keep the collapsed `<details>` form. Nothing in the replacement is hidden.
- Update `checks/page_audit.py` and `checks/layout.py`, which look for the old markup.

### B4. Column widths

- Problem (confirmed by the user): in the Concurrency model card the citation column ("Sources") is very wide, while the columns the user actually needs to read are squashed. It is wider than the other five columns combined. The Inputs card has the same problem. The gate message must list every table with this.
- Fix: size columns by content role. Citation and source columns get a small fixed width and their markers wrap inside it; short label columns get a minimum width; long-text columns share the remaining space. Use CSS (`table-layout`, `col` widths or `max-width` plus wrapping) in the page stylesheet, not per-report tweaks.
- Add a check to `check_page.py`/`browser.py`: for each rendered table, fail when any single citation or source column is wider than, say, a third of the table or wider than the widest text column, and print the table id.

### B5. Alert boxes for standalone text

- Problem: text blocks that sit alone in a card around a table or diagram (for example the text after the Failure modes table) look like stray paragraphs.
- Fix: render a standalone `text` block (one that is not the main content of the card) as an alert box with an icon, a bold label and a coloured left border, in both light and dark themes, with contrast of at least 4.5:1 (the check already measures this). Pick the variant from the content: note (default), tip, important, warning. Do not guess by keyword; add an optional `variant` field to the text block in the report schema, default `note`, and document it in `reports.md` and `method.md`. The "Not applicable: ..." paragraph for a card with `na` should use the same box.
- Apply it everywhere in the dossier where such a block exists, not only Failure modes. The gate message lists them.

### B6. Overview card

- Move the languages bar and legend up, between the headline number tiles (the "BANs") and the releases table.
- Remove the titles "Recent releases" and "Languages, by share of non-blank lines".
- Never hide the releases table. With no releases, draw the table with its headers and one centered message row ("No releases"), same height as a normal empty state.

### B7. Contributors card

- Put the View and Measure toggles on the same line as the Zoom and Show toggles (one toolbar row; wrap on narrow screens).
- Remove the subtext "Which parts of the repository each person ...".

### B8. Secret signals card

- Move the "No credential-shaped strings or ..." message into the middle of the empty table (same empty-state pattern as the releases table in B6).

### B9. Empty-state rule for every table

- Anywhere in any card of the schema where a table (or chart) is hidden because there is no data, draw the table with its headers and a centered message instead. Implement one shared helper (for example `empty_table(columns, message)`) and use it for releases, secret signals and every other case found by the audit; the `.none-found` class already exists and can be the base. Add a page check that fails if a measured card with no data draws nothing.

### B10. New card: cards marked "partial"

- Add a card to "This dossier" (the process report), or to a better place if one exists, titled for example "Partial cards". One row per card that carries a `partial` pill, with columns: Card, Report, Why it is partial (the exact tooltip text), What to do to clear it.
- Fill the first three columns from the same data that draws the pills (`process.partial_cards`), so the card can never drift from the pills.
- "What to do" comes from a small table in the dossier source that maps each known reason to the action (for example a shallow clone: fetch the full history; a missing hosting-service link or access for pull-request data: say what is needed). Do not invent an action for a reason that is not in the table: show "See the reason" and add a Gaps item so the table gets completed. List every known reason string found in `history/ownership.py` and `history/scan.py` when building the table.
- When there are no partial cards, show the empty-state table from B9.

### B11. Remove "Scroll sideways for more columns."

- Delete the hint from `dossier.js` (and any CSS for `.table-hint`) so it appears in no card. Wide tables must still scroll by touch or trackpad; solve it with the width fixes in B4, not with a text hint. Add a check that the built page does not contain that phrase.

### B12. Cite every function and variable in Component details

- Problem: the `Public surface` field of Component details lists functions, classes and variables with no citation, so the reader cannot open them in the side panel.
- Content fix: rewrite the `public_surface` field of every entry in the components report so each function, class or variable name is written with a citation to its definition, using the labelled form `[[path:start-end|name]]` (complete definition block, line numbers verified). Do this for all components, not only the ones the user saw.
- Rule fix: update `prompts/reports.md` and `prompts/method.md` to require it, and add a render check (V-rule, an error) that flags any backticked identifier in a `public_surface` field with no citation next to it. The existing "mentions X without citing it" warning only covers file paths, so extend or add a sibling rule.

### Order and tests for Part B

1. Gate message (above), wait for the user.
2. B11, B1, B2, B5 (the alert box), B3 (which reuses the B5 box), B4, B6 to B9, B10 as separate commits, each with tests (render tests that build a small fixture dossier and assert the new markup, the absence of the removed text, and the empty states).
3. B12 after the check rule exists, so the check proves the report fix.
4. Update `checks/page_audit.py`, `checks/layout.py` and `checks/browser.py` for the new markup, then run `dossier check` on a real dossier at 1500 px and 400 px wide, light and dark. Open at least one screenshot of each changed card and look at it.
5. Rebuild the usps-pipeliner dossier with the new version (a full build, since the skill version changes) and compare against the first build.

## Known issue found in the first dossier: the `io` tooltip check

`dossier check` reported `io: the citation tooltip did not appear on hover` on two runs. In a separate clean browser at 1500 and 400 px, all 414 citations of the Inputs and outputs report showed their tooltip, with the check's own timing. With the code viewer panel open (it covers the right side from about 857 px at 1500 px wide), the panel intercepts the hover on every report, so the check must close it before this step; whether it does, and what is different for `io`, was not found. Investigate in `src/dossier/checks/browser.py` (the code-viewer check around lines 149-180 and the tooltip check around lines 372-389): log the state of the page before the hover, and check that the code panel is closed and the page is scrolled where the check expects.

## Verification (on the personal machine, after the fixes)

1. Clean the tool cache so the fix is exercised: delete `~/.local/cache/dossier/.dossier-tools/node/scip-python-*` (only that folder).
2. Run the dossier repo's own test suite, including the new tests.
3. Run `uv run <skill>/scripts/dossier.py doctor <some Python repo>`; it should list npm/node as present.
4. Run `uv run <skill>/scripts/dossier.py prepare <some small Python repo> --allow-ref --restore yes` (answer prompts as needed). Expected: no `scip-python failed` warning, `tool_report` is `[]`, and `<working area>/scip/index.scip` exists and is non-empty.
5. Confirm nothing changed outside the dossier repo (git status of the skill folder is clean after the update is merged and the installed copy is synced).
6. Run a full `/dossier build` on a small repo and, at the end, check that `<home>` holds only `index.html` and one folder per repository, and that the assistant's final message says what it cleaned up (or that there was nothing to clean).

## Deliverables

- A branch in the dossier repo with: the `sandbox.run()` executable resolution, the scip-python fix (version bump or post-install patch), the `SKILL.md` cleanup and scratch-location rules (Problem 4, plus `dossier tidy` if added), the Part B page and content changes (B1 to B12), the `io` tooltip check fix, and tests for each code change. Part B starts only after the user answers the gate message.
- A short PR description covering both symptoms (exact error strings above) and how they were verified.
- Report back with the test results and the `prepare` output from step 4. Do not merge or push without asking.
