# Code viewer for the dossier

Add a side panel to the rendered HTML dossier that shows the code behind a citation. Hovering a citation `[n]` still shows the tooltip. Clicking it opens the panel on the right with the cited code. The panel works offline because the cited files are embedded in the page at build time. It does not need the local repository when the page is viewed.

To run a phase, start a new session and say: "Carry out phase 1 of the plan outlined in docs/plans/000-code-viewer-plan.md" (or phase 2). Paths in this plan are relative to the `dossier` skill directory.

## Shared context

Every phase reads this section first.

### Where things are

- `scripts/render.py`: `parse_cite`, `Cites` (resolves a citation against the pinned commit, `check`, `url`), `Refs` (numbers citations per report; `mark` emits `<sup class="cite"><a href="#ref-<rid>-<n>" data-tip=...>`, one `sup` per statement; `listing` emits `<ol class="refs">`), `render_html` (assembles the page).
- `scripts/gather.py`: the secret-prone file rules, `SENSITIVE_FILE` and `SECRET_NAME`, and the `secret_signals` facts.
- `assets/dossier.js`: tooltips (`data-tip`, `#cite-tip`), the `/` search shortcut, and the other keydown handlers. `assets/dossier.css`, `assets/template.html`.
- `scripts/check_page.py`: the Playwright page check (needs a browser, see `README.md`).
- `prompts/method.md`: how the report writers cite. `agents/` or the plugin's `dossier-verifier` definition: how the verifier reviews.
- `Repo.read("<sha>:<path>")` returns `(type, bytes)` for a blob or tree at the pinned commit.

### Decisions already made

- **Embed, don't fetch.** Cited files are read from the pinned commit at render time and embedded in the page as JSON. No server and no local checkout is needed to view them.
- **Panel on the right**, 90 characters wide by default (`width: min(90ch, 100vw)`). On a viewport narrower than that it covers the full width.
- **Single click** on `[n]` opens the panel (it no longer jumps to the reference list). **No double-click behavior.** A "Go to reference" button in the panel does the jumping.
- **Keybinds** are single keys, ignored while typing in an input, like `/` for search. `v` toggles the panel (collapse or open). `p` toggles pin. `[` and `]` go to the previous and next reference. `Esc` collapses an unpinned panel. Before using these keys, check the existing keydown handlers in `dossier.js` for conflicts, and show the keys in the panel as `<kbd>` hints.
- **Collapsed** means hidden, with a small tab on the right edge to bring it back. **Pinned** means the panel stays open when you click elsewhere or press `Esc`, and the page content shrinks to make room instead of being covered. Unpinned means the panel overlays the page and closes on `Esc` or when you click outside it. The pin state is remembered in `localStorage`.
- **One embedded blob per file, capped at 1,500 lines.** There are no other line caps and no context padding.
  - A file of 1,500 lines or fewer is embedded whole. The cited range is highlighted and scrolled into view, and the rest of the file is there to scroll through.
  - A longer file is embedded as a 1,500-line window. For a file with line-range citations, choose the window that covers the most cited ranges (ties go to the earliest), and cite ranges outside it as non-openable. A single range longer than 1,500 lines is cut to its first 1,500. For a file cited without line numbers, the window is lines 1-1,500. The panel header says "lines 2,100-3,600 of 8,412" whenever the window is not the whole file.
  - A window is also capped at 150 KB of text. If it is over, shrink the window until it fits.
- **Citations that do not open the viewer** keep today's behavior: the click follows the `#ref-` anchor, and the tooltip is unchanged except where noted. These are:
  - commit citations and `facts:` citations;
  - directory citations (the tooltip says `directory <path>/, relative to the repo root`; no absolute local path is embedded, so a shared page does not leak home directories);
  - files that are binary, minified (any line over 1,000 characters), or flagged as secret-prone (matching `SENSITIVE_FILE`, or listed in the `secret_signals` facts);
  - ranges outside the file's window, and anything dropped by the size budget.
- **Size budget.** Each page has a budget for embedded data (start at 4 MB of text before highlighting; Phase 2 sets the real number from measurements). When it is exceeded, drop files in this order: files cited only without line numbers, then files with the fewest citations, then the rest. Print a warning with how many were dropped. A dropped citation is non-openable.
- **A statement's sources travel together.** One `sup.cite` holds all the sources of one statement. Opening any of them shows a row of buttons for the statement's other sources, so the whole evidence set is one click away. Prev/next still steps through the openable citations of the whole report in reference-list order and shows "3 / 12". Citations that do not open are skipped.
- **Highlighting** (Phase 2) is done at build time with Pygments (token classes, theme colors for light and dark in `dossier.css`, 4.5:1 contrast like the diagram text). If Pygments is not importable, fall back to plain escaped text and print a warning.
- **Writers cite whole blocks.** `prompts/method.md` tells writers to cite the complete block that supports a claim (the function body or the config stanza), not only the line that names it, and to use several citations when the evidence is in several places. The verifier brief flags ranges that are visibly too tight.

### Conventions

- Match the surrounding code's style, comment density and naming. Keep `render.py` helpers small, like the existing ones.
- Load these skills: `py-projects`, `py-unit-tests`, `docs-project` (and `docs-readme` / `docs-user-guide` / `docs-dev-guide` as it points), `git-workflow`, `git-commit`, `git-release`.
- Work on a feature branch, per `git-workflow`. Never commit to `main`.
- Record results in this file under the phase's **Results** heading.

## Phase 1: Embed files, panel, keybinds, navigation

Plain text with line numbers, no syntax highlighting yet. The eligibility rules still ship in this phase, so no secret or binary file is ever embedded.

### Read first

1. The shared context above.
2. `scripts/render.py`: `Cites`, `Refs`, and how `render_html` builds each report and the page. Note whether the reports are all in the page at once or shown one at a time. The panel and the prev/next list depend on that.
3. `assets/dossier.js` in full, `assets/dossier.css`, `assets/template.html`.
4. `scripts/check_page.py`, to see how the tooltip check is written.
5. `git log` and this file's Results sections, for anything earlier work cut or moved here.

### Steps

1. **Eligibility.** Add `Cites.viewable(c)` returning `(ok, reason)`. It is false for non-file citations, directories, and unresolved citations. It is also false for binary files (a NUL byte in the first 8 KB), minified files, and secret-prone files. Reuse the `SENSITIVE_FILE` pattern from `gather.py` rather than copying it, and honor the sensitive files and hits in the facts.
2. **Windows.** Add a function that picks each viewable file's window under the 1,500-line and 150 KB rules in the shared context, and says which of the file's citations fall inside it. Dedupe by path across all reports, so a file cited from many places is embedded once.
3. **Embed.** In `render_html`, emit one `<script type="application/json" id="code-data">` holding, per path: the total line count, the window's first line, and the window's lines. Escape `</script` and `<!--` inside the JSON. Apply the size budget and drop order from the shared context.
4. **Markup.** In `Refs.mark`, give each viewable citation `data-view="<path>"`, `data-a`, `data-b`. In `Refs.listing`, do the same for the list entry. Update the directory tooltip as in the shared context.
5. **Panel.** Add the panel element to `template.html` and style it in `dossier.css`: a header (path, window note, "Go to reference" button, pin button, collapse button, prev/next with the "n / m" counter, the row of the statement's other sources), and a body with line numbers and the cited range marked. Width 90ch, full width on narrow viewports, matching the page's light and dark themes.
6. **Behavior** in `dossier.js`: click on a viewable `[n]` calls `preventDefault`, opens the panel on that citation, and scrolls to the first cited line. Add the keybinds and the collapsed tab. Add pin, with the layout change (content shrinks while pinned) and `localStorage`, wrapped in try/catch since storage can be missing. "Go to reference" scrolls to the `#ref-<rid>-<n>` entry and briefly highlights it. If the panel is unpinned, it collapses first. Prev/next builds its list from the `.refs` listing of the opened citation's report. Keep the search index unaffected (the data is in a script block).
7. **Writer guidance.** Update `prompts/method.md` and the verifier brief as in the shared context.
8. **Page check.** Extend `check_page.py`: open a report, hover (tooltip still shows), click a viewable citation (panel opens, cited lines marked, 90ch wide), press `]` (the counter advances), click another source in the statement row, press `p` then `Esc` (stays open), press `p` then `Esc` (collapses), press `v` (toggles), click "Go to reference" (the reference list entry is in view). A directory citation, a commit citation, and a secret-looking file do not open the panel. Do these in both themes.
9. **Unit tests** for `viewable`, the window choice (whole file, the 1,500-line window covering the most ranges, the 150 KB shrink, a range outside the window being non-openable), the budget drop order, and the JSON escaping, following `py-unit-tests`. Include a test that a `.env` file and a binary file are never embedded.

### Deliverables and checks

- A rendered dossier whose viewable citations open the panel, with the behavior above. Checked by the extended `check_page.py` reporting `"problems": 0`, and by opening one page's screenshot and looking at it.
- No secret-prone or binary file content appears anywhere in the rendered HTML. Checked by a unit test, and by grepping the rendered HTML for the contents of a planted `.env` fixture.
- Unit tests pass.

### Cut line

If the session runs long, cut in this order, and record it under Results: the `localStorage` memory of the pin state, then the collapsed tab (keep the keybind), then the statement-sources row. Do not cut the eligibility rules, the keybinds, prev/next, or the page check.

### Acceptance

- Everything under Deliverables and checks, plus the behavior in the shared context.
- `README.md` and the dossier user-facing docs describe the viewer and the keys. `SKILL.md` step 7 (the page check) mentions the new checks. The sharing note says the page now contains source code.
- Committed on the feature branch. No release yet.

### Results

Done on branch `feat/code-viewer`. Nothing from the cut line was cut.

- **Size** (embedded JSON, plain text, 4 MB budget never reached; page size before and after): `encamp` 92 files, 488 KB (6.5 to 7.2 MB); `cannalerts` 99 files, 1,175 KB (6.4 to 7.8 MB); `cmg-util` 20 files, 39 KB (5.9 to 6.1 MB). Phase 2 sets the real budget.
- **Layout.** The window, budget and JSON-escaping logic is in a new `scripts/viewer.py`. `Cites` gained `source`, `viewable`, `view_attrs` and `plan_view`. `render_html` builds the pages once to record which ranges are cited, plans the windows, and builds again only when some marker must lose its `data-view`.
- **Escaping.** `</` becomes `<\/` and `<!--` becomes `<\u0021--` in the JSON. The `<!--@CODE-->` template slot is safe from the later placeholder replacements because of this.
- **Reference list.** Each viewable entry has the `data-view` attributes and a "View code" button (not in the plan) so the code can be opened from the list as well as from the markers. Directory and viewable-file entries no longer link to a `file://` path, so no home directory is embedded for them. A non-viewable file cited from a repo with no remote still links to `file://`, as before.
- **Pinned panel.** The page makes room only when at least 480 px is left for it; below that a pinned panel overlays, like an unpinned one. `--code-w-px` is set from JS because `90ch` depends on the font of the element it is used on.
- **Verifier brief not updated.** The `dossier-verifier` agent is part of the separate dossier plugin, not this skill, so there is no brief here to change. Only `prompts/method.md` was updated. The plugin's verifier needs the "ranges visibly too tight" check added there.
- **Tests.** `tests/` (run with `uv run --with pytest python -m pytest tests`): 54 pass. A planted `.env`, key, binary and minified file never reach the embedded data or the markup (unit tests). An end-to-end render of a throwaway repo with a planted `.env` and binary contained none of their contents.
- **Page check.** `check_page.py` reports `"problems": 0` on the `encamp` and `cannalerts` dossiers, in both themes. Light and dark screenshots of the panel were looked at.
- **Not covered by the check:** a viewport narrower than the panel (full-width case) and the `localStorage` pin memory across reloads.

## Phase 2: Highlighting and size tuning

### Read first

1. The shared context above.
2. This file's Phase 1 Results, `git log`, and any work Phase 1 cut or moved here.
3. How the scripts are run (`uv run`, and whether `dossier.py` has script metadata for dependencies), and the theme tokens in `dossier.css`.

### Steps

1. **Pygments.** Add it as a dependency of the render path in the way the scripts already declare dependencies (script metadata for `uv run`, or whatever Phase 1 found). Highlight each embedded file once, as a whole, choosing the lexer from the file name and falling back to plain text for unknown types. A truncated window starts mid-file, so the first lines may mis-tokenize; note it in Results if it is visible.
2. **Fallback.** If Pygments is not importable, render as in Phase 1 and print one warning.
3. **Theme.** Add token classes to `dossier.css` for the light and dark themes. Every token color must reach 4.5:1 contrast against the panel background in both themes. Add that check to `check_page.py`, like the existing diagram contrast check.
4. **Size.** Measure the embedded data and the final HTML on at least two real repositories (one small, one large), with and without highlighting. Set the real per-page budget, and decide whether the 150 KB window cap and the 1,500-line cap need adjusting. Keep the highlighted markup compact: class names only, no inline styles, and short class names. If the numbers are too large, store the plain text once and highlight in the browser instead, or compress the data. Record the numbers and the decision in Results.
5. **Rendering.** Open a 1,500-line file in the panel and check that it scrolls to the cited range without lag. If it lags, render only the visible rows. Do not build that unless it is needed.
6. **Guards audit.** Add a unit test that runs the eligibility rules over a fixture tree containing each excluded kind (`.env`, a key file, a binary, a minified bundle, a directory), and checks that none is embedded. Try a dossier of a repository that has a flagged secret in an ordinary source file, and confirm the file is excluded when the facts list it.
7. **Build message.** Make `/dossier build` (the render output) say how many citations are viewable, how many are not, and how many were dropped for size.

### Deliverables and checks

- Highlighted code in the panel in both themes, contrast verified by `check_page.py` with `"problems": 0`. Look at one light and one dark screenshot with the Read tool.
- The guards test passes, and the size numbers are in Results.
- Docs updated for the dependency and the build message.

### Cut line

If the session runs long, cut the build message, then the large-repository measurement (use the small one and say so). Do not cut the contrast check or the guards audit.

### Acceptance

- Everything under Deliverables and checks.
- `VERSION` bumped and released per `git-release` (a new feature, so a minor bump). Branch merged per `git-workflow`.

### Results

Done on branch `feat/code-viewer`. Not done: the `VERSION` bump, the merge and the release (see the last bullet). Nothing from the cut line was cut.

- **Pygments.** `scripts/dossier.py` now has `uv run` script metadata (`dependencies = ["pygments"]`). `viewer.highlight` lexes each whole file once (lexer from the file name; an unknown type is escaped plain text), then the window is sliced out of the result, so a window that starts mid-file is not mis-tokenized. Tokens map to 12 short classes (`TOKEN_CLASSES`: `c k s m nf nb nt na no gd gi gh`), written as `<i class=k>`, with neighbors of one class merged. Without Pygments the lines are only escaped and one warning is printed.
- **Embedded lines are now HTML**, escaped, and `dossier.js` inserts them as they are. The JSON escaping for `</` and `<!--` still applies on top.
- **Theme.** `--tk-*` variables in `dossier.css`, one set for light and one for dark. `check_page.py` measures every class against the panel background and against a cited line's background (the translucent highlight composited over it), in both themes. Lowest ratios: 5.32:1 light, 4.52:1 dark.
- **Size** (embedded JSON, plain escaped text in Phase 1 vs highlighted now; whole page after):

  | Repo | Files | Phase 1 JSON | Highlighted JSON | Page |
  |---|---|---|---|---|
  | `cmg-util` (small) | 20 | 39 KB | 61 KB | 6.1 MB |
  | `encamp` | 92 | 488 KB | 749 KB | 7.4 MB |
  | `cannalerts` (largest) | 99 | 1,175 KB | 1,782 KB | 8.4 MB |

  Highlighting adds about 50%. Mermaid and the CSS (about 5.9 MB) dominate every page. **Decision:** keep the markup in the page (no browser-side highlighting, no compression), keep the 1,500-line and 150 KB window caps, and lower the per-page budget from 4 MB to 3 MB of plain text, which is about 4.5 MB highlighted and 2.5 times the largest real dossier. The budget is counted before highlighting.
- **Rendering.** The largest embedded file (1,500 lines of JSON) builds and scrolls in the panel in about 135 ms, so no row virtualization was built.
- **Guards audit.** `TestNeverEmbedded` covers a `.env`, a key file, a binary, a minified bundle, a directory and a source file listed in the facts, and now also counts them as not viewable. A real run of `prepare` on a throwaway repo with a fake `ghp_` token in `config.py` listed the file in `secret_signals`, and `Cites.source` refused it. The profiler only flags known token formats, so an ordinary source file with some other secret is not excluded.
- **Build message.** `render` prints `code_viewer`: `viewable`, `not_viewable` (distinct citations) and `files_dropped_for_size`. For `cannalerts`: 559, 64, 0.
- **Tests.** 66 pass (`uv run --with pytest --with pygments python -m pytest tests`; without `--with pygments` the highlight tests fail). The Phase 1 tests for escaping now expect HTML-escaped lines.
- **Page check.** `check_page.py` reports `"problems": 0` on `cannalerts`, `encamp` and `cmg-util`. Light and dark screenshots of the panel on `cannalerts` were looked at.
- **Release.** The repo has no release workflow, and `VERSION` is a plain file with no bump tool in `py-projects`, so per `git-release` the bump (0.2.0 to 0.3.0, a minor bump) is left for the owner to confirm.
