# codebase-dossier

A Claude Code skill that reads a git repository and builds a single-file HTML dossier: short, cited reports on what the code does, how it's built, and where the risks are.

## Usage

Inside Claude Code:

```
/dossier home ~/dev/dossiers        # set where dossiers are saved (once)
/dossier build ~/dev/projects/foo   # build a dossier for a repo
/dossier confirm                    # list open questions, then answer them
/dossier correct                    # record something the dossier got wrong
/dossier version
```

`build` pins the dossier to a commit, writes twelve reports (overview, capabilities, interfaces, architecture, domain logic, data, code tour, failures, delivery, risks, contributors, gaps), and renders them to `<home>/<repo-name>/` as one self-contained HTML page.

Every claim is marked confirmed, inferred, or unknown, and cites the files it came from. Your confirmations and corrections survive rebuilds.

## Reading the code behind a citation

Hover a source marker `[n]` to see what it points to. Click it to open the cited code in a panel on the right, with the cited lines marked and the code syntax-highlighted (by Pygments, at build time; the colors meet a 4.5:1 contrast ratio in both themes). The code is embedded in the page, so the panel works offline and without the repository.

| Key | Action |
|---|---|
| `v` | Show or hide the panel |
| `p` | Pin the panel: it stays open and the page makes room for it. The choice is remembered in the browser |
| `[` `]` | Previous or next source in the report's reference list |
| `Esc` | Collapse an unpinned panel (a click outside it does the same) |

The panel also has a row of the statement's other sources and a "Go to reference" button. Citations of directories and commits, and of files that are binary, minified or may hold secrets, do not open the panel; the click jumps to the reference list as before. A click on a "profiler facts" marker opens a short explanation of what the measurement is, with a button that shows the profiler code that made it in the same panel. A file longer than 1,500 lines is embedded as the 1,500-line window that holds the most cited ranges, and the panel says which lines it shows.

**Sharing.** The page now contains the source of every file it cites, up to 3 MB of text in total. Treat it like the repository: do not share it more widely than the code. Files that match secret patterns or are flagged by the profiler are never embedded.

## Calendars

The commit calendars (on Overview and Contributors) open on days and zoom to months or to the last twelve months as month calendars. Each week is boxed. Hover a cell to see who committed that day or month, how many commits, and the lines added (green) and deleted (red). Calendar data older than this version has no line counts until you run `prepare` again.

## Install

Requires Claude Code and [uv](https://docs.astral.sh/uv/), which installs Pygments for `dossier.py` on demand. Without Pygments the code is shown without colors, and `build` prints a warning. The page check in `build` uses Playwright, which `uv` installs on demand; the first run also needs `uv run --with playwright python -m playwright install chromium`.

```sh
git clone git@github-1npo:1npo/codebase-dossier.git
cp -r codebase-dossier/dossier ~/.claude/skills/dossier
```

The skill is user-invoked only (`/dossier ...`); Claude won't trigger it on its own.

## License

No license for the skill itself yet. Bundled third-party libraries in `dossier/vendor/` keep their own licenses (`LICENSE.md`, `LICENSE-mermaid`).

## Development

Run the unit tests from this directory:

```sh
uv run --with pytest --with pygments python -m pytest tests
```
