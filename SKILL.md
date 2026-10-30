---
name: dossier
description: Build a cited HTML dossier that explains a git repository (capabilities, architecture, data model, code tour, delivery, risks, contributors). Use for /dossier home, /dossier build, /dossier version, /dossier correct, /dossier confirm.
argument-hint: home [dir] | build [repo-path] [--ref branch-or-sha] | version | correct ... | confirm [ids] [--answer|--wrong|--note ...]
disable-model-invocation: true
allowed-tools: Bash(uv run *), Read, Grep, Glob, Write, Agent
---

# dossier

Builds a codebase dossier: a single self-contained HTML file of short, cited reports that give a lead engineer a working mental model of a repository at one pinned commit.

Python does the counting and the drawing. You do the reading and the writing. Never count what `facts.json` already counts, and never write HTML.

Arguments the user typed: `$ARGUMENTS`

The CLI is `uv run ${CLAUDE_SKILL_DIR}/scripts/dossier.py`. Call it `DOSSIER` below.

## Commands

### `/dossier version`
Run `DOSSIER version` and show the output.

### `/dossier home [dir]`
Run `DOSSIER home [dir]`. With no directory it shows the current home. Dossiers are saved under `<home>/<repo-name>/`.

### `/dossier build [repo-path] [--ref <branch-or-sha>]`
The repository defaults to the current directory. The ref defaults to the checked-out commit. Follow these steps in order.

1. **Prepare.** Run `DOSSIER prepare <repo> [--ref R]`. If it says no home is set, ask the user for a directory and run `DOSSIER home`. Read the JSON it prints. Show the user one line: repo, branch, short commit, size.
2. **Size check.** Look at `reading.advice`. If it describes a large or very large repository, tell the user the token count and chunk count in plain words, then ask whether to continue before reading any code. Do not offer to switch models: the default model, Sonnet 5.5, already has a 1M-token context window. Keep Sonnet (pass `model: "sonnet"` to the subagents) and the default chunk size, and process the chunks with parallel subagents. For anything smaller, carry on without asking. Relay any `warnings` (shallow clone, uncommitted changes).
3. **Learn the rules.** Read `${CLAUDE_SKILL_DIR}/prompts/method.md` and `${CLAUDE_SKILL_DIR}/prompts/reports.md`. Read `state.json` for user corrections and for `user_decisions` (what the user has confirmed, answered or disputed; `prepare` prints them), and `facts.json` (use Read with a limit if it is large; start with `repo`, `git`, `files`, `manifests`, `ownership`, `areas`, `chunks`).
4. **Read the code.** Follow "Reading the repository" in `method.md`. In `single` mode, read the files yourself. In `chunked` mode, write a note for every chunk that is not cached, using subagents in parallel batches of about five when the Agent tool is available. Do not skip chunks and do not truncate files.
5. **Write the reports.** Write all twelve files to `reports_dir`: overview, capabilities, interfaces, architecture, domain-logic, data, code-tour, failures, delivery, risks, contributors, gaps. For a large repository, give each report to its own subagent with the report name, the paths to `method.md`, `reports.md`, `facts.json`, the notes, and the repository. If this is an update and reports already exist, update them as `method.md` describes.
6. **Render.** Run `DOSSIER render <repo>`. If it prints errors (unresolved citations, missing columns, bad diagrams), fix the report files and run it again until it succeeds. Warnings are worth fixing but do not block. The summary's `code_viewer` counts the citations that open the code viewer, the ones that do not, and the files left out to keep the page small.
7. **Check the page in a real browser.** Mermaid errors, unreadable text and layout faults only show when the page is opened, so never skip this and never judge diagrams by reading their source. `check_page.py` declares its own dependency (Playwright), so `uv` installs it for you:

   ```
   uv run ${CLAUDE_SKILL_DIR}/scripts/check_page.py <html> --shots <dir>
   ```

   If it says no browser is installed, run `uv run --with playwright python -m playwright install chromium` once and retry. It opens every report in the light and the dark theme and fails if a diagram does not draw, if any text inside a diagram has a contrast ratio under 4.5:1 against what is painted behind it or is cut off by its label box, if a table column cannot be sorted, if the citation tooltip does not show, or if the code viewer misbehaves (a highlight color under 4.5:1 contrast on the panel or on a cited line; a click on a citation must open the panel on the cited lines; the keys `]`, `p`, `v` and `Esc`, the other-sources row and "Go to reference" must work; directory, commit and secret-looking citations must not open it). Fix every `FAIL` line (usually in the diagram source or the page assets), re-render and re-run until it prints `"problems": 0`. Then open at least the architecture and one flow screenshot from `--shots` with the Read tool and look at them: the script cannot see overlapping boxes, tangled arrows or a diagram too small to read. Fix those too.
8. **Finish.** Tell the user the path of the HTML file, that it embeds the source of the files it cites (so it should be shared no more widely than the code), and, in a few plain sentences, the headline findings: what the project is, the top risks, and the number of unknowns and inferences. Do not list every step you took.

### `/dossier confirm`
For giving the dossier your answers on its open items: inferences, unknowns, assumptions and coverage notes. Every open item has an ID (G001, G002, …) shown in the page's Tracker and beside the statement itself. The ID stays the same across rebuilds.

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
- Do not print secret values found in the repository, in the dossier or in chat.
