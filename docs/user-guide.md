# dossier user guide

## Contents

- [Overview](#overview)
- [Installation](#installation)
- [Getting started](#getting-started)
- [Usage by task](#usage-by-task)
- [Reference](#reference)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Limitations](#limitations)

## Overview

dossier is a Claude Code skill. It reads a git repository at one commit and writes a single self-contained HTML page of short reports: what the code does, how it is built, who knows it and where the risks are. Python counts and draws everything that can be measured. Claude reads the code and writes the rest.

Terms used below:

| Term | Meaning |
|---|---|
| Pinned commit | The one commit the dossier describes. Every citation points at it. |
| Report | One numbered section of the page. Each holds cards. |
| Card | One block of a report: a table, a graph, a list of findings or written text. |
| Measured, Analysed, Reasoned (`M`, `A`, `R`) | The badge on a card. `M` was counted by code, `A` combines tool findings with Claude's reading, `R` is Claude's reasoning. |
| Confirmed, inferred, unknown | The label on each written statement. Confirmed: the cited code says it. Inferred: it follows from the code but the code does not say it. Unknown: the code cannot answer. |
| Tier A, Tier B | Tier A languages (Python, TypeScript, JavaScript, C#) have full import and call graphs. Tier B languages (for example Shell or Rust) are counted and listed but have no graph. |

The reports, in page order:

| # | Report | # | Report |
|---|---|---|---|
| 01 | This dossier | 09 | Behavior and tests |
| 02 | This repository | 10 | Change and history |
| 03 | Reading guide | 11 | Conventions |
| 04 | Entry points | 12 | Build, run and ship |
| 05 | Components | 13 | Contributors |
| 06 | Interactions | 14 | Risks |
| 07 | Inputs and outputs | 15 | Gaps |
| 08 | Data model | 16 | Corrections |

Two badges can appear in a card's title bar:

- `partial`: a tool that feeds the card did not run in this build. Install it (see `/dossier doctor`) and build again.
- `no static graph`: the repository has Tier B languages, and this version of dossier makes no import or call graph for them. Their files are in the tables but have no links. Hover the badge to see which languages.

## Installation

Requires Claude Code, [uv](https://docs.astral.sh/uv/) and `git`. Other tools depend on the repository's languages:

| Tool | Needed for |
|---|---|
| Node 22.13 or later | TypeScript and JavaScript repositories |
| Node 16 or later | Python repositories (a Python tool runs on Node) |
| .NET SDK | C# repositories: the version in the repository's `global.json`, or 8 or later when there is none. Without it the C# cards are built from the source text alone and marked `partial`. |
| `gh` | Optional. Reads pull request approvals, so commits by agents and bots belong to the person who approved them. |
| Playwright's Chromium | `/dossier check` and the page check in `build`. Install once with `uv run --with playwright python -m playwright install chromium`. |

Pygments (code colours) is installed by `uv` on demand. Without it the code viewer shows plain text and `build` prints a warning.

Install the skill by copying this folder into your skills folder:

```sh
cp -r dossier ~/.claude/skills/dossier
```

The skill runs only when you type `/dossier ...`. To upgrade, replace the folder. A new minor version rebuilds every report the next time you build. To uninstall, delete `~/.claude/skills/dossier`, `~/.config/dossier` and `~/.local/cache/dossier`. Your dossiers stay where you saved them.

## Getting started

1. Choose where dossiers are saved (once):

   ```
   /dossier home ~/dev/dossiers
   ```

2. Check the tools for the repository:

   ```
   /dossier doctor ~/dev/projects/foo
   ```

   The output lists the languages found, the tools needed on this machine (`ok`, `MISSING` or `TOO OLD`) and the tools dossier installs by itself. It installs nothing. The last line, `skill: <commit> (clean|dirty ...)`, says which version of the skill ran.

3. Build:

   ```
   /dossier build ~/dev/projects/foo
   ```

   Claude says what it is doing in plain words. A large repository gets a question first, because reading it takes many tokens. Locked dependencies get a question too (see [The restore question](#the-restore-question)).

4. Open the page it names: `~/dev/dossiers/foo/dossier-foo.html`. A `summary.json` sits beside it.

The first build of a medium repository takes several minutes. The page check at the end opens the page in a browser and takes a few minutes more.

## Usage by task

### Build or update a dossier

```
/dossier build [repo-path] [--ref <branch-or-sha>] [--full] [--allow-missing] [--no-restore] [--allow-ref] [--submodules] [--verify]
```

The repository defaults to the current directory and the ref to the checked-out commit. Run `build` again after the code changes. It compares the pinned commit with the last render and works out which reports cite code that changed: a cited file was edited at the cited lines, was deleted, or lost or gained a neighbour; a cited directory changed; or a correction is pending. Only those reports are re-read and rewritten. Citations whose lines did not move are renumbered to the new commit by script. If nothing is stale, `build` only re-renders. The Overview and Contributors reports are refreshed whenever the commit changes, and Gaps whenever another report is.

`--full` rebuilds every report. So does a new minor version of the skill or a rewritten history.

Your confirmations and corrections survive every rebuild.

### Read how fresh a dossier is

The first tile of the "This dossier" report, `Freshness`, compares the pinned commit with the same branch or tag on the remote:

| Tile says | Meaning |
|---|---|
| `Up to date` | The pinned commit is the remote's commit. |
| `N commits behind` | The remote has N newer commits. |
| `Not on <branch>` | The pinned commit is not on that remote branch. |
| `Tag X` or `Tag X moved` | The tag still points here, or points elsewhere now. |
| `Not known` | There is no remote, or it could not be asked. The note under the tile says why. |

`build` asks the remote once, with `git ls-remote`, and never fetches or changes your repository. If the remote cannot be reached (an SSH remote usually cannot be, because dossier runs git without your SSH agent), it uses your last fetch and the tile says "as of the last fetch". Freshness is recomputed only when you build, so it can age.

### Use the graphs

The Component map (report 05) and Interactions graph (report 06) cards open on a collapsed view of areas. Each box stands for an area, a component or a group of them, and a number on a link is how many imports it stands for.

- Click a box that has a view, or press Enter on it, or press its `Open ...` button below the graph, to open it.
- `Up` goes back one level. The breadcrumb and the `View` list jump to any view.
- A view shows at most 12 boxes and 30 links. Larger sets are grouped into boxes such as `area00 … area09 (10)`. When links are hidden, the caption says how many imports a link needs to be shown and how many links are shown. Every component and link is in the tables below the graph.

Without JavaScript the graph is replaced by a note and the tables hold everything.

### Read the code behind a citation

Hover a source marker `[n]` to see what it points to. Click it to open the cited code in a panel on the right, with the cited lines marked and the code highlighted. The code is embedded in the page, so the panel works offline and without the repository.

| Key | Action |
|---|---|
| `v` | Show or hide the panel. It opens empty, with a note, when the report has no citations to view. |
| `l` | Show or hide the legend: what the badges and the confirmed, inferred and unknown pills mean. |
| `p` | Pin the panel: it stays open and the page makes room for it. The choice is remembered in the browser. |
| `[` `]` | Previous or next source in the report's reference list. |
| `Esc` | Collapse an unpinned panel (a click outside it does the same). |
| `/` | Search the dossier. |

The Legend and Code tabs sit in each report's title bar. The panel also has a row of the statement's other sources and a "Go to reference" button. Citations of directories and commits, and of files that are binary, minified or may hold secrets, do not open the panel; the click jumps to the reference list. A click on a "measured facts" marker explains what was measured, with a button that shows the code that measured it. A file longer than 1,500 lines is embedded as the 1,500-line window with the most cited ranges, and the panel says which lines it shows.

**Sharing.** The page contains the source of every file it cites, up to 3 MB of text. Treat it like the repository: share it no more widely than the code. Files that match secret patterns are never embedded.

### Work with tables

Click a column heading to sort (a third click restores the written order). Drag the right edge of a heading to resize it; double-click the edge, or use the arrow keys on it, to undo or nudge. The **Columns** menu above a table hides and shows columns. **Reset columns** brings back every column. The filter box above a table keeps the rows that contain what you type.

### Read who knows what

Report 13 (Contributors) shows who the people are, who to ask about each component, how concentrated the knowledge is (with the bus factor), which commits came from agents and bots, and how the team works. A commit belongs to the person who wrote it. When an agent or a bot wrote it, it belongs to the person who approved its pull request, and on a project with one person, to that person. The Contributors card in report 02 has **Owner** and **Author** buttons to switch between the two views.

The knowledge map is a tree of directories and files with one bar per row, split by contributor:

- **Measure**: *Lines* (lines that survive per `git blame`) or *Commits*.
- **Show**: all paths, or only the paths the selected contributor touched.
- **Zoom**: how deep the tree is open, from *Top level* to *All files*.
- **Contributor chips**: click one to see only that person's share. Click it again to go back.

Hover a row for the numbers. The minimap on the right shows the whole tree; click or drag it to scroll. The arrow keys and Enter work in the tree.

How the figures are made:

- Lines come from the same `git blame` as code ownership. If blame runs out of time on a very large repository, the card says so and the remaining line shares are estimated from lines added minus deleted.
- Commits come from one `git log --no-merges -M` pass. A renamed file keeps its history. Commits that touch more than 400 files are credited to no file.
- Identities are merged as elsewhere (`.mailmap` is honoured). Bots are left out. The six people with the most familiarity get their own colour; everyone else is "Others".
- Files are the text files tracked at the pinned commit, without vendored, generated, lock, binary and minified files.
- "Departed" and "at risk" are inferences. A person with no commit in the 6 months before the pinned commit is hatched as no longer active. A directory is "at risk" when its top contributor has left and holds 50% or more of it.

Very large trees show only the rows near the viewport. The per-file figures are kept in `knowledge.json`, at most 1.5 MB; beyond that the smallest, least changed files are left out and the card says how many.

The commit calendars (Overview and Contributors) open on days and zoom out to months. Hover a cell to see who committed, how many commits and the lines added and deleted.

### Confirm what is unsure

Every open item (an inference, an unknown, an assumption or a coverage note) has an ID such as `G003`, shown in the Gap tracker in report 15 and beside the statement. The ID stays the same across rebuilds.

```
/dossier confirm                                 # list open items
/dossier confirm --ids G006 G007 --note "why it is right"
/dossier confirm --ids G003 --answer "what is true"
/dossier confirm --ids G006 --wrong "what is true"
/dossier confirm --undo G006
```

`/dossier confirm` also takes `--kind unknown|inference|assumption|coverage`, `--report <id>`, `--all` (include decided items) and `--json`. Run a build or `render` afterwards: the item shows "confirmed by you", drops out of the open counts, and the sidebar dot turns green when nothing is left open. Decisions are kept in `state.json` and survive rebuilds, new commits and skill upgrades. A decision that matches no statement stays on file and applies again if the statement returns.

### Correct a mistake

```
/dossier correct --report components --said "what the dossier claimed" --text "what is true"
```

Claude then updates the affected reports, marks the corrected statement confirmed and cites the correction (`C001`). To change how a person is classified: `/dossier correct --contributor <email> --type human|agent|bot`. Corrections always win over inference and are listed in report 16.

### Have a statement checked independently (`--verify`)

```
/dossier build --verify
```

After the page is written, a sample of cited claims (5 per report by default) is given, with only the code they cite, to a separate checker that has not seen the report. Each answer is `supported`, `not supported` or `cannot tell`. Every `not supported` claim becomes an item in Gaps, and the process card in report 01 shows the counts. Change the sample size with `verify_per_report` in the [configuration](#configuration). The sample is random but recorded: `dossier verify-sample --seed <seed>` repeats it. The checker is a sample, not a proof: a `supported` verdict means one reader found the cited code says it.

### Check the written page

```
/dossier check ~/dev/projects/foo
```

Checks that every row, column and entry of the reports is drawn (V11), then opens the page in a browser, in both themes, at 1500 and 400 px wide (V12): diagrams draw and are readable, nothing scrolls sideways or overlaps, and the code viewer and search work. It prints one `FAIL` line per problem and `problems: N`, and exits 1 when N is not 0. It takes a few minutes. Screenshots are kept in `.check-shots` in the dossier folder.

### Clean up

```
/dossier clean ~/dev/projects/foo
```

Deletes the working copy, the scratch home and the package caches dossier keeps for that repository under `~/.local/cache/dossier/`. The dossier itself is not touched.

### The restore question

Installing a repository's locked dependencies (so that tools can see its libraries) can run that project's own build code on your machine with your rights. `build` asks before it does, and says the command and where it runs. Your answer is stored per repository.

- Answer `no`, or build with `--no-restore`, to install nothing. The cards that need the dependencies are marked `partial`.
- A ref that is neither a tag nor on the default branch does not install dependencies unless you pass `--allow-ref`.

## Reference

### Commands in Claude Code

| Command | What it does |
|---|---|
| `/dossier version` | Prints the skill version. |
| `/dossier home [dir]` | Shows or sets the folder dossiers are saved in. Each goes under `<home>/<repo-name>/`. |
| `/dossier doctor [repo]` | Lists the tools the repository needs and which are installed. Installs nothing. |
| `/dossier build [repo-path] [options]` | Builds or updates the dossier. See [Build or update a dossier](#build-or-update-a-dossier). |
| `/dossier confirm [options]` | Lists or decides open items. |
| `/dossier correct [options]` | Records a correction. |
| `/dossier check [repo]` | Checks the written page. |
| `/dossier clean [repo]` | Deletes the working copy and caches. |

`/dossier build` options:

| Option | Default | Meaning |
|---|---|---|
| `--ref <branch-or-sha>` | the checked-out commit | What to describe. |
| `--full` | off | Rebuild every report. |
| `--allow-missing` | off | Carry on without missing tools, in reduced mode. |
| `--no-restore` | off | Install no dependencies. |
| `--allow-ref` | off | Install dependencies and run repository code even when the ref is not a tag or the default branch. |
| `--submodules` | off | Also check out and analyse submodules. |
| `--verify` | off | Have an independent checker test a sample of cited claims. |

### The `dossier.py` command line

Claude runs these; you can too: `uv run ~/.claude/skills/dossier/scripts/dossier.py <command>`. In every command that takes `repo`, it defaults to the current directory.

| Command | Options |
|---|---|
| `version` | none |
| `home [dir]` | none |
| `doctor [repo]` | `--all` (check the tools for every supported language), `--json` |
| `clean [repo]` | none |
| `prepare [repo]` | `--ref REF` (default `HEAD`), `--chunk-tokens N` (default 400000), `--full`, `--allow-missing`, `--no-restore`, `--allow-ref`, `--submodules`, `--restore yes\|no` (answer the restore question), `--verify` |
| `render [repo]` | `--readers N` (parallel readers Claude used, shown on the process card), `--partial` (allow missing reports), `--allow-errors` (write the HTML even if validation fails), `--apply-corrections` (mark pending corrections as applied) |
| `check [repo]` | none |
| `candidates [repo]` | `--report ID` (required), `--open` (only findings no report has decided), `--catalog FILE`, `--json` |
| `verify-sample [repo]` | `--seed S`, `--per-report N` |
| `verify-record [repo]` | `--results FILE` (required) |
| `migrate [repo]` | `--dry-run` |
| `confirm [repo]` | `--ids ID...`, `--note`, `--answer`, `--wrong`, `--undo ID...`, `--all`, `--report`, `--kind`, `--json` |
| `correct [repo]` | `--report`, `--said`, `--text`, `--apply ID...`, `--contributor`, `--type` |

`prepare` exits 2 with `"stopped": "missing_tools"` when a tool is missing and 3 with `"stopped": "restore_question"` when it needs your answer.

### Files in the dossier folder

`<home>/<repo-name>/` holds:

| File | What it is |
|---|---|
| `dossier-<repo>.html` | The page. Self-contained. |
| `summary.json` | The facts other tools may want: components and how they depend on each other, entry points, contracts, dependencies, risk counts, ownership and hotspots. People appear by opaque id; no email address is stored. |
| `reports/*.json` | The written reports. |
| `state.json` | Your confirmations and corrections. Back-ups `state.backup-v<version>.json` are made when the skill version changes. |
| `build.json` | The record of what each build step did. Never edit it. |
| `facts.json`, `knowledge.json`, `activity.json`, `dependencies.json`, `chunks.json`, `extract/`, `notes/` | Measured data and Claude's working notes. |
| `.check-shots/` | Screenshots from `check`. |

## Configuration

The config file is `~/.config/dossier/config.json`. `/dossier home` writes the `home` key; edit the rest by hand. Environment variables `DOSSIER_CONFIG`, `DOSSIER_HOME` and `DOSSIER_CACHE` override the file's location, `home` and `cache_dir`.

```json
{
  "home": "~/dev/dossiers",
  "cache_dir": "~/.local/cache/dossier",
  "timeouts": { "history": 1200 },
  "registry_auth": {},
  "verify_per_report": 5
}
```

| Key | Default | Meaning |
|---|---|---|
| `home` | none | Where dossiers are saved. |
| `cache_dir` | `~/.local/cache/dossier` | Working copies and package caches. |
| `timeouts.restore` | 900 | Seconds for installing locked dependencies. |
| `timeouts.extract` | 1800 | Seconds for the code extractors. |
| `timeouts.tool` | 600 | Seconds for any other tool. |
| `timeouts.history` | 600 | Seconds for reading git history. Raise it for a very long history. |
| `timeouts.github` | 300 | Seconds for reading pull request approvals with `gh`. |
| `registry_auth` | `{}` | An object mapping an ecosystem to a list of environment variable names that are passed to the restore step (private package registries). |
| `verify_per_report` | 5 | Claims per report that `--verify` checks. A whole number, 1 or more. |

A bad value stops the command with a message that names the key.

## Troubleshooting

| You see | Cause and fix |
|---|---|
| `No dossier home is set` | Run `/dossier home <dir>`. |
| `MISSING <tool>` in `doctor`, or `build` stops with `missing_tools` | Install the tool with the command shown, or build with `--allow-missing`. The cards that need it are marked `partial`. |
| `TOO OLD <tool>` | The tool is older than the minimum shown. Upgrade it. |
| `build` asks whether to install dependencies | See [The restore question](#the-restore-question). |
| A card has the `partial` badge | A tool that feeds it did not run. `/dossier doctor` shows which. Fix it and build again. |
| A card has the `no static graph` badge | Expected for Tier B languages. Not a fault. |
| The Freshness tile says `Not known` | The repository has no remote, or the remote cannot be reached and has not been fetched. Run `git fetch` and build again. |
| `render` prints `V4:` or `V5:` lines | Files in no component, or tool findings with no decision. Claude fixes the reports; never pass `--allow-errors` to skip them. |
| `check` prints `FAIL` lines | A diagram, table or layout problem. Claude fixes it from the reports. A `FAIL` in the page assets or scripts is a bug in dossier. |
| `check` says no browser is installed | Run `uv run --with playwright python -m playwright install chromium` once. |
| `V10: the verifier sampled claims but no results were recorded` | A `--verify` build stopped early. Run `dossier verify-record`, or build again without `--verify`. |
| The page looks out of date | Run `/dossier build`. The page shows the pinned commit; it does not follow the repository. |

## Limitations

- **Blind spots.** Code that is wired up at run time cannot be followed by a static tool: dynamic imports, plugins loaded by name, dependency injection containers, reflection, decorator and route registries, source generators, and routes mounted under computed prefixes. Where dossier sees a sign of one, report 15 (Gaps) says so and names the file. It does not guess the link.
- **Tier B languages** have no import or call graph and no symbols. Report 15 lists each one.
- **TypeScript and C# figures** were measured on public repositories and are provisional until corrected against real codebases.
- **Razor** files (`.razor`, `.cshtml`) are not read; Gaps says so.
- **Unused NuGet packages** are not listed. A package is often used through extension methods, analysers or build files that no import names.
- **Python.** Several Python projects in one repository are found by their `pyproject.toml`, `setup.py`, `setup.cfg` or `requirements.txt`. If two of them have a package with the same name, name-based checks may match the wrong one.
- **Not a security scanner.** Report 14 lists risks that follow from the code and history. It does not look for vulnerabilities.
- **Size.** The page embeds the cited source, up to 3 MB.
