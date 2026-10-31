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

## Updating a dossier

Run `/dossier build` again after the code changes. `prepare` compares the pinned commit with the last render and works out which reports cite code that changed: a cited file was edited at the cited lines, deleted, or lost or gained a neighbour; a cited directory changed; or a correction is pending. Only those reports are re-read and rewritten, and the others are left alone. Citations whose lines did not move are renumbered to the new commit by script, with no model involved. If nothing is stale, the build just re-renders. `overview` and `contributors` are refreshed whenever the commit changes, and `gaps` whenever another report is. A new minor version of the skill, a rewritten history, or `--full` rebuilds everything.

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

## Contributor knowledge map

The Contributors report has a card that shows which parts of the repository each person knows best. It is a tree of directories and files with one row per path. Each row has a bar split by contributor, and the top contributor beside it. Four controls change what you see:

- **Measure**: *Lines* (surviving lines per `git blame`) or *Commits*.
- **Show**: all paths, or only the paths the selected contributor has touched.
- **Zoom**: how deep the tree is open, from *Top level* to *All files*. You can still open and close single folders.
- **Contributor chips**: click one to see only that person's share on every row. Click it again to go back.

Hover a row for the numbers. The minimap on the right shows the whole tree: click or drag it to scroll. The tree also works from the keyboard (arrow keys, Enter).

How the figures are made (all in `gather.py`, under "knowledge map"):

- **Lines** come from the `git blame` already run for code ownership, so they match the Contributors card. If blame runs out of time on a very large repository, the card says so, and the line shares of the remaining files are estimated from lines added minus deleted.
- **Commits** and **recent commits** come from one `git log --no-merges -M` pass. A renamed file keeps its earlier history at its current path. Commits that touch more than 400 files (imports, reformatting) are not credited to any file.
- **Who is shown**: identities are merged as elsewhere in the dossier (`.mailmap` is honoured by git). Bots are left out. The six people with the most familiarity get their own colour, the same colour they have in the other graphics, and everyone else is grouped as "Others".
- **Files**: the text files tracked at the pinned commit, without vendored, generated, lock, binary and minified files, and without files that `.gitattributes` marks `linguist-generated` or `linguist-vendored`.
- **Departed and "at risk" are inferences.** A person with no commit in the 6 months before the pinned commit (`KNOWLEDGE_DEPARTED_MONTHS`) is hatched as no longer active, and a directory is tagged "at risk" when its top contributor has left and holds 50% or more of it. The card labels both as inferred.

Very large trees show only the rows near the viewport, so the page stays responsive. The per-file figures are kept in `knowledge.json` next to `facts.json`, at most 1.5 MB (`KNOWLEDGE_CAP`); beyond that the smallest, least changed files are left out and the card says how many.

## Calendars

The commit calendars (on Overview and Contributors) open on days and zoom to months or to the last twelve months as month calendars. Each week is boxed. Hover a cell to see who committed that day or month, how many commits, and the lines added (green) and deleted (red), lined up in columns. Calendar data older than this version has no line counts until you run `prepare` again.

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
