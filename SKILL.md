---
name: dossier
description: "Build a cited, commit-pinned HTML dossier that explains a git repository: a codebase intelligence report generator that combines measured repository facts, tool findings (entry points, imports, inputs and outputs, data models, tests) and confidence-labeled analysis. Reports cover a reading guide, entry points, components, interactions, inputs and outputs, data model, behaviour and tests, conventions, build and run, and risks. Use for /dossier home, /dossier doctor, /dossier check, /dossier clean, /dossier build, /dossier version, /dossier correct, /dossier confirm."
argument-hint: home [dir] | doctor [repo] | check [repo] | clean [repo] | build [repo-path] [--ref branch-or-sha] [--full] [--allow-missing] [--no-restore] [--allow-ref] [--submodules] | version | correct ... | confirm [ids] [--answer|--wrong|--note ...]
disable-model-invocation: true
allowed-tools: Bash(uv run *), Read, Grep, Glob, Write, Agent
---

# dossier

Builds a codebase intelligence dossier: a single self-contained HTML file of short, cited reports that give a lead engineer a working mental model of a repository at one pinned commit.

Python does the counting and the drawing. You do the reading and the writing. Never count what `facts.json` already counts, and never write HTML.

Arguments the user typed: `$ARGUMENTS`

The CLI is `uv run ${CLAUDE_SKILL_DIR}/scripts/dossier.py`. Call it `DOSSIER` below.

## Commands

### `/dossier version`
Run `DOSSIER version` and show the output.

### `/dossier home [dir]`
Run `DOSSIER home [dir]`. With no directory it shows the current home. Dossiers are saved under `<home>/<repo-name>/`.

### `/dossier doctor [repo]`
Run `DOSSIER doctor <repo>` and show the output. It lists the tools this repository needs, which are installed, and how to install the missing ones. It installs nothing.

Show the output as it is printed, in a code block, line for line. Do not summarize, reword or reorder it, and do not drop a line. The last line, `skill: <commit> (clean|dirty|UNMERGED ...)`, says which version of this skill ran and whether it has uncommitted changes. It is the line the user most needs, so always include it. After the block you may add one sentence, for example to say what `dirty` means (uncommitted changes under the skill folder) or to tell the user to run `/dossier build`. Before replying, check that your reply contains a line starting `skill:`.

### `/dossier check [repo]`
Run `DOSSIER check <repo>` after `render`. It checks the written page: V11 (every row, column and entry of the reports is drawn) and V12 (a real browser, both themes, 1500 and 400 px wide: diagrams draw and are readable, no sideways scroll or overlapping text, numbered notes under flows, a table where the layout has one, the code viewer and search work). It prints one `FAIL` line per problem and `problems: N`, and exits 1 when N is not 0. It takes a few minutes.

### `/dossier clean [repo]`
Run `DOSSIER clean <repo>`. It deletes the working copy, the scratch home folder and the package caches dossier keeps for this repository under `~/.local/cache/dossier/`. The dossier itself is not touched.

### `/dossier build [repo-path] [--ref <branch-or-sha>] [--full] [--allow-missing] [--no-restore] [--allow-ref] [--submodules]`
`prepare` checks the tools, makes a clean copy of the code at the pinned commit in a working area, and records each step in `build.json`. Pass `--allow-missing` (carry on without missing tools), `--no-restore` (never install dependencies), `--allow-ref` (install dependencies even when the ref is not a tag or on the default branch) and `--submodules` through to `prepare`. Two results stop it early, and you must act on them:
- Exit code 2, `"stopped": "missing_tools"`: show the user the `text`, and offer to run `prepare` again with `--allow-missing` once they have installed the tools or chosen to go without.
- Exit code 3, `"stopped": "restore_question"`: installing the repository's locked dependencies can run the project's own build code on this machine, with the user's rights. Tell the user in plain words what `will_run` lists (the command and where it runs), including the `note`, and ask whether to install. Run `prepare` again with `--restore yes` or `--restore no`. The answer is stored for this repository.

The repository defaults to the current directory. The ref defaults to the checked-out commit. `--full` rebuilds every report. Without it, a build of a repository that already has a dossier only redoes the reports whose cited code changed. Follow these steps in order.

1. **Prepare.** Run `DOSSIER prepare <repo> [--ref R]`. If it says no home is set, ask the user for a directory and run `DOSSIER home`. Pass `--full` through if the user gave it. Read the JSON it prints. Show the user one line: repo, branch, short commit, size, and the update plan in plain words (for example "updating 3 of 12 reports; 9 are unchanged" or "full build: first build").

   `update_plan.mode` decides what the rest of the steps do:
   - `full`: nothing earlier can be reused (first build, `--full`, new skill version, history rewritten). Do every step below for every report.
   - `incremental`: only the reports in `update_plan.stale` are rewritten, each with its reasons. The reports in `fresh` are left exactly as they are. Their line numbers were already moved to the new commit by `prepare` (`line_shifts`).
   - `render_only`: nothing is stale. Skip steps 2 to 5 and 7, run step 6, and finish at step 8.
2. **Size check.** Look at `reading.advice`. In `incremental` mode skip this step: only the files in `update_plan.read` get read. Otherwise, if it describes a large or very large repository, tell the user the token count and chunk count in plain words, then ask whether to continue before reading any code. Do not offer to switch models: the default model, Sonnet 5.5, already has a 1M-token context window. Keep Sonnet (pass `model: "sonnet"` to the subagents) and the default chunk size, and process the chunks with parallel subagents. For anything smaller, carry on without asking. Relay any `warnings` (shallow clone, uncommitted changes).
3. **Learn the rules.** Read `${CLAUDE_SKILL_DIR}/prompts/method.md` and `${CLAUDE_SKILL_DIR}/prompts/reports.md`. Run `DOSSIER candidates <repo> --report <id>` before writing each report: it lists the tool findings that report must keep, merge or dismiss. Read `state.json` for user corrections and for `user_decisions` (what the user has confirmed, answered or disputed; `prepare` prints them), and `facts.json` (use Read with a limit if it is large; start with `repo`, `git`, `files`, `manifests`, `ownership`, `areas`, `chunks`).
4. **Read the code.** In `incremental` mode do not read the whole repository and do not write chunk notes. Read the stale reports and the files in `update_plan.read` (the changed files they cite or sit next to), plus any other file in `facts.json` `delta.changed` that a stale report needs. Otherwise follow "Reading the repository" in `method.md`. In `single` mode, read the files yourself. In `chunked` mode, write a note for every chunk that is not cached, using subagents in parallel batches of about five when the Agent tool is available. Do not skip chunks and do not truncate files.
5. **Write the reports.** In `incremental` mode write only the reports in `update_plan.stale`, as `method.md` describes under "Updating". Otherwise write these files to `reports_dir`, in this order: `entry`, `components`, `interactions`, `io`, `data`, `behavior`, `conventions`, `ops`, then `reading` (it needs the entry points and components), then `overview`, `risks` and `gaps`. Reports 10 (`change`) and 13 (`contributors`) are not written in this version. For each report, run `DOSSIER candidates <repo> --report <id>`, write the report, then run it again with `--open`: it must print nothing. For a large repository, give each report to its own subagent with the report id, the paths to `method.md`, `reports.md`, `facts.json`, the notes and the repository, and the command `DOSSIER candidates <repo> --report <id>`. If this is an update and reports already exist, update them as `method.md` describes.
6. **Render.** Run `DOSSIER render <repo>` (add `--readers N` when subagents read the code, so the process card can say how many). If it prints errors (unresolved citations, missing columns, bad diagrams, or `V4:` and `V5:` lines about files in no component and tool findings with no decision), fix the report files and run it again until it succeeds. Fix `V4:` and `V5:` errors in the reports; never use `--allow-errors` to get past them. Warnings are worth fixing but do not block. The summary's `code_viewer` counts the citations that open the code viewer, the ones that do not, and the files left out to keep the page small.
7. **Check the page.** (Skip in `render_only` mode.) Run `DOSSIER check <repo>`. It first checks that the written page draws every row, column and entry of the reports (V11), then opens every report in a real browser, in the light and the dark theme, at 1500 and 400 px wide, and prints one `FAIL` line per problem and `problems: N` at the end. Mermaid errors, unreadable text and layout faults only show when the page is opened, so never skip this and never judge diagrams by reading their source. The result is recorded in `build.json`, so the page can say whether it was checked. `check_page.py` declares its own dependency (Playwright), so `uv` installs it for you; if it says no browser is installed, run `uv run --with playwright python -m playwright install chromium` once and retry. It fails if a diagram does not draw, if any text inside a diagram has a contrast ratio under 4.5:1 against what is painted behind it or is cut off by its label box, if diagram text is under 11 px or a diagram is over its node budget, if a flow has no numbered notes, if a table column cannot be sorted or a card that should show a table shows none, if text overlaps or the page scrolls sideways, if the citation tooltip does not show, or if the code viewer misbehaves (a highlight color under 4.5:1 contrast on the panel or on a cited line; a click on a citation must open the panel on the cited lines; the keys `]`, `p`, `v` and `Esc`, the other-sources row and "Go to reference" must work; directory, commit and secret-looking citations must not open it). Fix every `FAIL` line that comes from the reports (usually a diagram's source, a table or a flow that does not match the layout), run `DOSSIER render <repo>`, and run `DOSSIER check <repo>` again until it prints `problems: 0`. **Never edit the skill's own files** (`${CLAUDE_SKILL_DIR}`: scripts, assets, prompts): that folder is the installed copy, a git clone that is synced from the source repository, and an edit there conflicts with the next update. A `FAIL` in the page assets or the scripts is a bug in dossier: stop, tell the user which check failed and why, and leave the fix to the dossier source repository. Then open at least the components and the interactions screenshots and one flow screenshot from `<out_dir>/.check-shots` with the Read tool and look at them: the script cannot see tangled arrows. Fix those too. Once it prints `problems: 0`, run `DOSSIER render <repo>` once more so the page shows the time of the browser check.
8. **Finish.** Tell the user the path of the HTML file, that it embeds the source of the files it cites (so it should be shared no more widely than the code), and, in a few plain sentences, the headline findings: what the project is, the top risks, and the number of unknowns and inferences. Do not list every step you took.

### `/dossier confirm`
For giving the dossier your answers on its open items: inferences, unknowns, assumptions and coverage notes. Every open item has an ID (G001, G002, …) shown in the page's Gap tracker and beside the statement itself. The ID stays the same across rebuilds.

- List what is open: `DOSSIER confirm <repo>` (add `--kind unknown|inference|assumption|coverage`, `--report <id>`, `--all` to include decided ones, `--json` for machine-readable output). Show the user the list in plain words, grouped by report, when they have not named IDs.
- Confirm an inference or assumption: `DOSSIER confirm <repo> --ids G006 G007 --note "why it is right"`.
- Answer an unknown (or any item): `DOSSIER confirm <repo> --ids G003 --answer "what is true"`.
- Dispute an item: `DOSSIER confirm <repo> --ids G006 --wrong "what is true"`. This also records a correction, so follow the `/dossier correct` steps for it.
- Take a decision back: `DOSSIER confirm <repo> --undo G006`.

Then run `DOSSIER render <repo>` to refresh the page. That only redraws from the existing reports, so it takes seconds and needs no re-reading. The item then shows "confirmed by you" in green, drops out of the open counts, and the sidebar dot turns green when nothing is left open.

If the user names an item by describing it rather than by ID, list the items, match it yourself, and say which ID you chose. If a match is unclear, ask.

Decisions are saved in `state.json` next to the reports. They are never discarded: they survive rebuilds, new commits, reworded reports and skill upgrades (the old state file is also copied to `state.backup-v<old version>.json` when the skill version changes). If a statement is reworded a lot, the page still matches it by its label and wording; a decision that matches nothing stays on file and shows under Corrections.

### `/dossier correct`
When the user says the dossier is wrong or gives missing facts:

1. Record it: `DOSSIER correct <repo> --report <id|other> --said "what the dossier claimed" --text "what is true"`. To change how a person is classified: `DOSSIER correct <repo> --contributor <email> --type human|agent|bot`, then re-run `prepare`.
2. Update the affected report files so they reflect the correction. Mark the corrected statement `confirmed` and cite the user's correction by adding the correction ID to the report text, for example "(correction C001)".
3. Run `DOSSIER correct <repo> --apply C001`, then `DOSSIER render <repo>`.

Corrections always win over inference. Read them before writing any report.

## Rules that always apply

- Everything is pinned to the commit SHA that `prepare` resolved. Never read the working tree for facts; read files at that commit when they differ (`git show <sha>:<path>`).
- Every file reference is a citation. Every statement is `confirmed`, `inferred` or `unknown`. Details are in `method.md`.
- Plain language, full sentences, short summaries.
- Never edit `build.json`. It is the record of what the tools did, written only by the scripts.
- Do not print secret values found in the repository, in the dossier or in chat.
