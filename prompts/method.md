# Method: how to write dossier content

You are building a dossier for one repository at one pinned commit. Python has already counted and classified things (`facts.json`) and planned how to read the code (`chunks.json`). Your job is to read the code, understand it, and write complete reports: every item a tool found or you found gets its own row, and size never limits content. Python then checks your citations and draws the page.

Never count things yourself when `facts.json` has the number. Never re-list what the tools found: decide about it (see "Tool findings: keep, merge, dismiss"). Never write HTML. Only write the JSON files described here.

## Writing style

- Plain language. Write as you would explain the system to a smart colleague on their first day.
- No terse fragments ("Auth: JWT. Stores: PG."). No padding either. Full, short sentences.
- Define a term the first time you use it if a newcomer would not know it.
- Executive summaries are 3 to 5 bullets of about 20 words or fewer each, in plain everyday language. A lead engineer should grasp the report from the summary alone.
- Prefer a table or list when the reader will scan. Prefer a sentence when explaining why.

## Evidence rules

Every statement has a basis, set in `conf`:

- `confirmed`: the code, config, docs or git history says it directly. Needs at least one citation.
- `inferred`: you reasoned to it from context (naming, structure, conventions, what is missing). Needs citations to the evidence, and a `note` saying what would confirm it.
- `unknown`: you looked and could not find or infer it. Say what is missing in the text, and give a `note` saying where the answer probably lives. Citations are optional.

Do not present an inference as confirmed. Do not leave a gap unstated. If a topic does not apply (a library has no database), say so as `confirmed` and cite the evidence you used (for example `facts:manifests`).

### Citation forms

Write citations inline as `[[path]]`, `[[path:12]]` or `[[path:12-30]]`, or list them in a `cite` array. Other forms:

- `commit:<sha>` for a commit in this history.
- `facts:<key>` for a measured figure. Keys: `git`, `languages`, `hot_files`, `manifests`, `env_vars`, `secret_signals`, `contributors`, `ownership`, `areas`, `file_activity`, `knowledge`, `dependencies`, `chunks`, `history`.

Rules:

- Paths are relative to the repository root, exactly as git lists them. Line numbers refer to the pinned commit.
- A sentence that depends on a file ends with its citation, `[[path:12-30]]`. The page shows it as a numbered marker. Do not start the citation with "See": the marker is the pointer. A source cited inline is never repeated by the page, so also listing it in `cite` is harmless.
- When a sentence is *about* one specific file (a reading order, an entry point, "the bootstrap is install.sh"), name the file in the sentence with the labelled form `[[path:12-30|name]]`. The page shows `name` in code style followed by the numbered marker. Use `|name` for the file the sentence is about, and the plain form for evidence at the end of a sentence. Never write a bare or backticked path for a tracked file.
- A citation is evidence, never a name. Do not start a sentence with `[[path]]`, and do not put one where a file name belongs ("sets no strict mode" after a bare citation, or "defined in" followed by one). Wrong: `[[install.sh:33-84]] sets no strict mode.` Right: `[[install.sh:33-84|install.sh]] sets no strict mode.` or `The bootstrap sets no strict mode [[install.sh:33-84]].` The page adds the path as a label when it finds a bare citation in a name position, but write the label yourself.
- Cite each source once per statement. Do not write the same citation inline and again as a trailing "See ...".
- In a table cell that holds only a file, directory or glob (a Name column, for example), write it in backticks: `scripts/lib`, `scripts/targets/*.sh`. The page also does this for any such cell that exists at the pinned commit.
- Cite the complete block that supports the claim: the whole function body or config stanza, not only the line that names it. A reader clicks a citation to read that code in a side panel, so a range that stops short of the evidence is a defect. Do not cite a whole large file when the block is thirty lines. If the evidence is in several places, use several citations.
- A citation to a directory, a commit or a `facts:` key does not open the code panel, so prefer a file range wherever one proves the point.
- Cite the code that supports a statement, never a tool finding or its id. The link to a finding is the `cand` list (see "Tool findings: keep, merge, dismiss").
- `render` fails if a citation does not resolve. Check line numbers before you write them.

## Report file shape: cards

One JSON file per report in `reports/`. Each report has a fixed list of cards, named in `prompts/schema/<report>.json`; `prompts/schema/README.md` explains the schema, and `reports.md` says what goes in each card. A report file has:

- `headline`: one sentence.
- `summary`: the executive summary, a list of 3 to 5 short bullets.
- `cards`: one entry per card that **you** write, in the same order as the schema, each named by its id: `{"card": "components.catalog", ...}`. Never write a title. The page takes the title and the layout from the schema.

A card entry is exactly one of:

- `blocks`: for cards whose schema shape is `blocks` or `flows`. Table columns must match the schema exactly, and a table needs at least one row.
- `entries`: for cards whose shape is `entries`. Each entry has the key the schema names (for example `component`), a `fields` object holding **every** field id as non-empty text, and `conf`, `cite`, `note` like any statement.
- `na`: a plain-text reason the card does not apply, with a non-empty `cite` list pointing at the evidence. Use it instead of an empty table.

Every card of the reports you write must be filled. `pending` is not allowed. Do **not** write cards the schema marks as drawn by a script (`writer: script`, tier M): leave them out of the file, because the page draws them from the tool findings. The cards of `change` (report 10) and `contributors` (report 13) that a script draws are left out. Where a card you write has a measured column (`Share`, `Areas touched`, `Share of commits`), write `-` in it: the page fills it from the history, and a figure you write is replaced.

Blocks inside a card are:

```text
{"type": "text", "text": "paragraphs, - bullets, `code`, **bold**, [[path:1-9]]", "conf": "confirmed", "cite": [], "note": ""}
{"type": "list", "items": [{"text": "...", "conf": "confirmed", "cite": ["path:3"], "note": ""}]}
{"type": "table", "columns": ["A", "B"], "rows": [{"cells": ["a1", "b1"], "conf": "confirmed", "cite": ["path:3"], "note": ""}]}
{"type": "diagram", "title": "what it shows", "mermaid": "flowchart LR\n ...", "conf": "confirmed", "cite": ["path:3"], "note": ""}
```

A `flows` card is one or more diagram blocks, each optionally followed by one `text` or `list` block that explains it. Table rows must have exactly as many `cells` as `columns`. The page adds the Basis and Sources columns itself, so do not add a "Where" column of your own for citations: a short cell (a file name, a symbol) takes its `[[...]]` citation and the page moves it to the Source column; citations stay inline only inside long free text.

Here is a complete report file with a table card, an `entries` card, a second table card and an `na` card. It is the `components` report; the measured `components.map` card is left out because a script draws it. A row of the catalog may point at several folders in its `Paths` cell (see "Components" below).

```json
{
 "headline": "The code is split into a command-line layer, an alerts engine and a store.",
 "summary": [
  "The `cli` package parses commands and calls the alerts engine.",
  "The `alerts` package decides what to send and the `store` package keeps the results.",
  "Only the `store` package talks to the database."
 ],
 "cards": [
  {
   "card": "components.catalog",
   "blocks": [
    {
     "type": "table",
     "columns": [
      "Component",
      "Paths",
      "Responsibility",
      "Public surface",
      "Depends on",
      "Used by",
      "Size"
     ],
     "rows": [
      {
       "cells": [
        "cli",
        "`src/shop/cli.py`",
        "Reads the command line and starts the right action.",
        "`main`",
        "alerts",
        "nothing (it is the entry point)",
        "120 lines"
       ],
       "conf": "confirmed",
       "cite": [
        "src/shop/cli.py:1-40"
       ]
      },
      {
       "cells": [
        "alerts",
        "`src/shop/alerts/`",
        "Decides which alerts to send.",
        "`send_alerts`",
        "store",
        "cli",
        "340 lines"
       ],
       "conf": "confirmed",
       "cite": [
        "src/shop/alerts/__init__.py:1-30"
       ]
      },
      {
       "cells": [
        "store",
        "`src/shop/store.py`, `db/*.sql`",
        "Keeps alerts and prices in the database.",
        "`Store`",
        "nothing",
        "alerts",
        "210 lines"
       ],
       "conf": "inferred",
       "note": "Check whether the scripts in db/ are applied by the store or by hand.",
       "cite": [
        "src/shop/store.py:1-25"
       ]
      }
     ]
    }
   ],
   "unassigned": [
    {
     "paths": "docs/, LICENSE",
     "reason": "Documentation, not code."
    }
   ]
  },
  {
   "card": "components.detail",
   "entries": [
    {
     "component": "store",
     "fields": {
      "purpose": "Keeps alerts and prices in the database.",
      "how_it_works": "A `Store` object wraps one connection and runs one query per method [[src/shop/store.py:10-60|store.py]].",
      "public_surface": "`Store`, `Store.save_alert`.",
      "state_owned": "The `alerts` table.",
      "key_files": "[[src/shop/store.py:1-80|store.py]]",
      "gotchas": "The connection is opened when the module is imported."
     },
     "conf": "confirmed",
     "cite": [
      "src/shop/store.py:10-60"
     ]
    }
   ]
  },
  {
   "card": "components.cross-cutting",
   "blocks": [
    {
     "type": "table",
     "columns": [
      "Concern",
      "Approach",
      "Where"
     ],
     "rows": [
      {
       "cells": [
        "configuration",
        "Read from environment variables once, at start.",
        "[[src/shop/config.py:1-20|config.py]]"
       ],
       "conf": "confirmed",
       "cite": [
        "src/shop/config.py:1-20"
       ]
      }
     ]
    }
   ]
  },
  {
   "card": "components.extension-points",
   "na": "The code has no plugin or registry mechanism; new features are added by editing the modules above.",
   "cite": [
    "src/shop/alerts/__init__.py:1-30"
   ]
  }
 ]
}
```

## Tool findings: keep, merge, dismiss

Before the code is read, tools (grimp, vulture, scip-python for Python; dependency-cruiser, knip, scip-typescript and a script on the TypeScript compiler for JavaScript and TypeScript; semgrep, tree-sitter, and a scan of Dockerfiles, Makefiles, CI files and systemd units) have already listed what they found: entry points, inputs and outputs, data models, tests, imports and unused code. Run

```
DOSSIER candidates <repo> --report <id>
```

before you write each report. It lists the findings that feed that report, grouped under the card they belong to. Each finding has an id such as `io-3fa91c02`, and findings of one rule in one file share a group id such as `iog-7c1d0e55`. For every finding in the cards you write, decide one of these and record it:

- **Keep.** Put the id in the `cand` list of the row (or entry) that covers it: `"cand": ["io-3fa91c02"]`.
- **Merge.** For call-site findings only (the `io-` ids: log calls, retries, timeouts and the like), put several ids in one row's `cand` list when one row covers them all, or put the group id to cover every finding of that rule in that file: `"cand": ["io-5b10aa7e", "io-8c2d4e19"]` or `"cand": ["iog-7c1d0e55"]`. **Never merge entities (`md-`) or entry points (`ep-`).** Each gets its own row, and a group id (`mdg-…`, `epg-…`) in `cand` or `dismissed` is an error. An entry-point row may hold several `ep-` ids only when they are the same entry point found twice (the same file and name).
- **Dismiss.** Put the ids in the card's `dismissed` list with a short plain-text reason (no citations): `"dismissed": [{"cand": ["io-0b2c4d61"], "reason": "Test helpers, not part of the application."}]`.
- **Add.** When you found something the tools missed, write the row as usual and mark it `"added": true`. A row has either `cand` or `added`, never both.

Rules:

- Never invent an id. An id the build does not know is an error.
- Cite the code, never a finding. The citation on a row still points at `path:lines`; `cand` is the link to the tool finding.
- A finding is decided once: it cannot be kept in one card and dismissed in another.
- One row per entity, with every field of it named in the `Fields` cell, and one row per entry point (every CLI command included). A long table is fine: the page sorts, filters and collapses it.
- A row with neither `cand` nor `added` gets a warning, except a "none" row in the fixed rows of inputs and outputs.
- When you are done with a report, run `DOSSIER candidates <repo> --report <id> --open`. It prints only the findings that still have no decision, so it must print nothing.
- Only findings are listed for you to decide. The imports, the unused code and the test list are given to you as data: use them as evidence, and do not copy them into a table by hand.

Example: the `io` report. The first row keeps one finding, the second merges two, the third covers a whole group, the fourth was added by hand, and the card's `dismissed` list dismisses two more.

```json
{
 "headline": "The program reads a settings file and the environment, and writes alerts to the console and a log.",
 "summary": [
  "Settings come from one environment variable and one file.",
  "Alerts go to standard output; the log goes to a file.",
  "Nothing is read from standard input."
 ],
 "cards": [
  {
   "card": "io.inputs",
   "blocks": [
    {
     "type": "table",
     "columns": [
      "Category",
      "Input",
      "Format",
      "Validation",
      "Where read"
     ],
     "rows": [
      {
       "cells": [
        "environment variables",
        "`SHOP_DB`",
        "path",
        "none",
        "[[src/shop/config.py:12-14|config.py]]"
       ],
       "conf": "confirmed",
       "cite": [
        "src/shop/config.py:12-14"
       ],
       "cand": [
        "io-3fa91c02"
       ]
      },
      {
       "cells": [
        "environment variables",
        "`SHOP_MODE` and `SHOP_LOG`",
        "text",
        "checked against a short list",
        "[[src/shop/config.py:15-30|config.py]]"
       ],
       "conf": "confirmed",
       "cite": [
        "src/shop/config.py:15-30"
       ],
       "cand": [
        "io-5b10aa7e",
        "io-8c2d4e19"
       ]
      },
      {
       "cells": [
        "CLI arguments",
        "every subcommand flag",
        "text",
        "argparse types",
        "[[src/shop/cli.py:20-88|cli.py]]"
       ],
       "conf": "confirmed",
       "cite": [
        "src/shop/cli.py:20-88"
       ],
       "cand": [
        "iog-7c1d0e55"
       ]
      },
      {
       "cells": [
        "stdin",
        "none",
        "-",
        "-",
        "-"
       ],
       "conf": "confirmed",
       "cite": [
        "facts:languages"
       ],
       "added": true
      }
     ]
    }
   ],
   "dismissed": [
    {
     "cand": [
      "io-0b2c4d61",
      "iog-11aa22bb"
     ],
     "reason": "Test helpers, not part of the application."
    }
   ]
  },
  {
   "card": "io.outputs",
   "blocks": [
    {
     "type": "table",
     "columns": [
      "Category",
      "Output",
      "Format",
      "Validation",
      "Where written"
     ],
     "rows": [
      {
       "cells": [
        "stdout/stderr",
        "alert lines",
        "text",
        "none",
        "[[src/shop/cli.py:90-110|cli.py]]"
       ],
       "conf": "confirmed",
       "cite": [
        "src/shop/cli.py:90-110"
       ],
       "cand": [
        "iog-9d3e6a21"
       ]
      }
     ]
    }
   ]
  },
  {
   "card": "io.contracts",
   "na": "The program exposes no network interface and calls no other service, so it has no contracts.",
   "cite": [
    "src/shop/cli.py:1-40"
   ]
  }
 ]
}
```

## Components

The report `components` is written around a catalog of components, and `render` checks that every tracked source file belongs to exactly one of them.

1. Run `DOSSIER candidates <repo> --report components`. It lists the folders that hold source files, the Python packages or JavaScript projects, and groups of modules that import each other a lot (communities), with their sizes.
2. Draft the catalog from those candidates. Merge small folders, split a large one, and give each component a plain name. Fill the `Paths` cell with the component's folders, files or globs in backticks, separated by commas (`src/app/alerts/`, `scripts/*.sh`). The most specific pattern wins when two overlap; a file matched equally well by two components is an error.
3. Check what you drafted: write it to `reports/components.json`, then run `DOSSIER candidates <repo> --report components --catalog reports/components.json`. It prints the size of each component, the imports between your components (use them for `Depends on` and `Used by`) and every source file that is in no component.
4. A file that really belongs to no component (documentation, a licence, a generated folder) goes in the catalog entry's `unassigned` list, each with a reason: `"unassigned": [{"paths": "docs/, LICENSE", "reason": "Documentation, not code."}]`.
5. Write one `components.detail` entry for every row of the catalog, with the component's name as the `component` key. A missing entry is an error.

## What render checks

`DOSSIER render` runs these checks and prints what it finds. Errors stop the build; warnings are worth fixing and also appear in Gaps.

- **V1, citations (error).** Every citation resolves to a real path and line range at the pinned commit.
- **V2, names (warning).** A name in backticks in a statement should appear in the code the statement cites. Check the line range, or the name.
- **V3, diagram arrows (warning).** Every arrow in a flow diagram of `entry.startup` and `interactions.flows` should have an import or a call behind it. An arrow with none is listed under the diagram as inferred.
- **V4, components (error).** Every tracked source file belongs to one component or is listed as unassigned, and every component has a detail entry.
- **V5, tool findings (error).** Every finding is kept, merged or dismissed, ids exist, none is both kept and dismissed, and every dismissal has a reason. A row with no `cand` and no `added` is a warning.
- **V5, people and components (error).** Report 13 names every person, agent and component, nobody who is not in the build, and an owner of the only human on a one-human project. `Status` is one of three words. Each Risks row has a `Source` of `extractor` or `read`.
- **V6, card layout (error).** Cards, columns, fields, `na` reasons and the rules above. Pending cards are not allowed.
- **V8, `summary.json` (error).** `render` writes the machine-readable summary and checks it against its schema. A contract's Direction must be exactly `offered` or `consumed`.
- **V7, blind spots (never fails).** Places where static analysis may miss something (dynamic imports, registries, generated code, feature flags) are listed in Gaps. Read the code there before you rely on a report.

Do not use `--allow-errors` to get past a V4 or V5 error: fix the reports.

## Diagrams (Mermaid)

- Keep fills pastel and text dark. When you use `classDef`, always set an explicit dark `color` (for example `classDef ext fill:#fde8c8,stroke:#b7791f,color:#111`), because the page can be in light or dark mode.
- Use `flowchart` for context, container, component and data-flow views, `sequenceDiagram` for execution paths, `erDiagram` for entities, `classDiagram` or `stateDiagram-v2` where they fit.
- C4 style: use a flowchart. Label each box `Name<br/>[kind]<br/>short purpose`. Use `subgraph` for boundaries. Use `classDef person|system|container|ext` so kinds look different.
- A sequence diagram has at most 10 participants and a flowchart at most 12 nodes. When a flow needs more, split it into several diagrams, each with its own numbered notes; never leave a step out. Each node is a real module, function, table or service name plus at most one short line (a few words). Put detail in the table next to the diagram, not in the boxes.
- In `entry.startup` and `interactions.flows`, name each box or participant after a real module, file or component (`cannalerts.cli`, `src/cannalerts/store.py`, a component from the catalog), so `render` can check that each arrow has an import or a call behind it. Boxes for users and outside services are not checked.
- Show the main path and at most one or two failure or alternative branches. If more is needed, draw a second diagram.
- Label an arrow only when what moves is not obvious, in two or three words.
- Always put label text in double quotes when it contains brackets, parentheses, colons, slashes or commas: `a["handler (HTTP)"]`.
- Do not use `end` as a node id. Avoid `%` and `#` inside labels. Use `<br/>` for line breaks, not `\n`, inside labels.
- Each diagram must be backed by citations in `cite`, and must not show components you did not see in the code. Mark guessed parts by setting `conf` to `inferred`.

- **Colour and legibility are checked by a browser, not by eye.** The page draws diagrams in light and dark themes; text over an arrow sits on a light chip and must stay dark. Never set `linkStyle`, `edgeLabelBackground`, `color` on edges, or theme variables in a diagram: leave edge and subgraph styling to the page. Run `check_page.py` (see SKILL.md) after every render.

## Reading the repository: fitting inside your context window

`chunks.json` splits every analyzable file into chunks that each fit in a context window. Nothing is skipped and files are never truncated. Very large files are split by line range, and a chunk entry with `start` and `end` means read only those lines.

**When `reading.mode` is `single`:** read everything yourself, then write the reports.

**When it is `chunked`:**

1. Read each chunk in turn (or give each to a subagent, a few at a time in parallel). For each chunk whose `cached` flag is false, read all of its files and write `notes/<fingerprint>.json` using the chunk-note shape below. Skip chunks that are already cached.
2. Keep each note under about 1,500 words. It is a compressed, cited record of what the chunk contains, not a summary of the whole repo.
3. If all notes together are too large to read at once (about 60,000 tokens), first write roll-up notes per top-level area from the chunk notes, then write reports from the roll-ups. Keep citations through each step.
4. Write reports from `facts.json` plus the notes. Go back to the source files whenever you need exact lines to cite or a note is unclear. Reading source again is always allowed.
5. Anything you could not read or confirm goes into the gaps report as a `coverage` item.

Chunk note shape (`notes/<fingerprint>.json`):

```json
{"fingerprint": "...", "label": "...",
 "purpose": "what this part of the code is for",
 "entry_points": [{"what": "...", "cite": "path:10"}],
 "inputs_outputs": [{"what": "HTTP route, CLI command, exported API, message topic", "direction": "in|out|both", "cite": "path:10-30"}],
 "data": [{"what": "entity, table, schema, file format, message", "fields": "key fields", "cite": "path:10-30"}],
 "flows": [{"what": "how a main operation moves through the code, in order of files and functions", "cite": "path:10-80"}],
 "external": [{"what": "database, API, queue, service, library with a role", "cite": "path:5"}],
 "config": [{"what": "setting, its default and how it is changed", "cite": "path:5"}],
 "secrets": [{"what": "credential or key the code needs and how it is supplied (never the value)", "cite": "path:5"}],
 "risks": [{"what": "...", "conf": "confirmed|inferred", "cite": "path:5"}],
 "unclear": ["things you could not work out and why"]}
```

Large repositories are read with Sonnet subagents (1M context window) on chunks of the default size. No model switch is needed.

## Corrections and updates

- Read `state.json` first. Every entry in `corrections` is a fact supplied by the user. It overrides anything you or the gatherer inferred. Apply it everywhere it matters and never contradict it.
- `user_decisions` (also in `state.json` under `resolutions`) lists items the user confirmed, answered or disputed. When you rewrite or update a report, keep each of those statements, in wording as close as you can to the original so the page can match it. Do not argue with a decision. For `answer`, write the statement as `confirmed` using the user's answer. For `wrong`, rewrite the statement using the user's text and mark it `confirmed`. For `confirm`, you may leave it `inferred`; the page shows it as confirmed by the user.
- **Updating.** `prepare` prints an `update_plan`. When its `mode` is `incremental`, rewrite only the reports in `stale` and leave every other report file untouched: do not open, re-save or reword them. Each stale report comes with reasons (a cited file changed, was deleted, gained a neighbour, a correction is pending, or the tool findings it is built from changed). When the reason is the tool findings, run `DOSSIER candidates <repo> --report <id> --open` first: it shows what is new. Start from the existing report: read it and the files in `update_plan.read`, keep every statement that still holds, change what the code now contradicts, add what is new, and fix citations. Do not re-read parts of the repository that no stale report touches. `prepare` already moved the line numbers of fresh reports; it never edits a stale one.
- A stale `overview` only needs its `headline` and `summary` refreshed (size, activity, what changed). Set `update_note` in `overview.json`; it has no cards to write. A stale `gaps` needs its items rebuilt from the other reports' current unknowns, inferences and assumptions.
- If an update leaves a fresh report wrong (a change elsewhere made it untrue), rewrite that report too and say so to the user. `--full` rebuilds everything.
- Chunk notes are only for full builds of chunked repositories. Chunks with cached notes need no re-reading.
- In `overview.json` you may set `update_note`: one plain sentence on what changed in the analysis this time. It appears in the history table.
