# Method: how to write dossier content

You are building a dossier for one repository at one pinned commit. Python has already counted and classified things (`facts.json`) and planned how to read the code (`chunks.json`). Your job is to read the code, understand it, and write short reports. Python then checks your citations and draws the page.

Never count things yourself when `facts.json` has the number. Never write HTML. Only write the JSON files described here.

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

Do not present an inference as confirmed. Do not leave a gap unstated. If a topic does not apply (a library has no database), say so as `confirmed` and cite the evidence you used (for example `facts:inventory`).

### Citation forms

Write citations inline as `[[path]]`, `[[path:12]]` or `[[path:12-30]]`, or list them in a `cite` array. Other forms:

- `commit:<sha>` for a commit in this history.
- `facts:<key>` for a measured figure. Keys: `git`, `languages`, `hot_files`, `manifests`, `inventory`, `env_vars`, `secret_signals`, `contributors`, `areas`, `chunks`.

Rules:

- Paths are relative to the repository root, exactly as git lists them. Line numbers refer to the pinned commit.
- Every mention of a file or directory in prose must be a citation. Do not write bare paths or backticked paths.
- Cite the narrowest range that proves the point. Do not cite a whole large file when ten lines will do.
- `render` fails if a citation does not resolve. Check line numbers before you write them.

## Report file shape

One JSON file per report in `reports/`. All have `headline` (one sentence), `summary` (the executive summary) and `blocks`. Block types:

```json
{"type": "text", "heading": "optional", "text": "paragraphs, - bullets, `code`, **bold**, [[path:1-9]]", "conf": "confirmed", "cite": [], "note": ""}
{"type": "list", "heading": "optional", "items": [{"text": "...", "conf": "confirmed", "cite": ["path:3"], "note": ""}]}
{"type": "table", "heading": "optional", "caption": "optional", "columns": ["A", "B"],
 "rows": [{"cells": ["a1", "b1"], "conf": "confirmed", "cite": ["path:3"], "note": ""}]}
{"type": "diagram", "heading": "optional", "title": "what it shows", "mermaid": "flowchart LR\n ...", "conf": "confirmed", "cite": ["path:3"], "note": ""}
```

Table rows must have exactly as many `cells` as `columns`. The page adds Basis and Sources columns itself. Do not add a "Where", "Where defined" or "Where read" column: the Sources column is the only place table citations are linked. Inline `[[...]]` citations inside cells also count.

## Diagrams (Mermaid)

- Keep fills pastel and text dark. When you use `classDef`, always set an explicit dark `color` (for example `classDef ext fill:#fde8c8,stroke:#b7791f,color:#111`), because the page can be in light or dark mode.
- Use `flowchart` for context, container, component and data-flow views, `sequenceDiagram` for execution paths, `erDiagram` for entities, `classDiagram` or `stateDiagram-v2` where they fit.
- C4 style: use a flowchart. Label each box `Name<br/>[kind]<br/>short purpose`. Use `subgraph` for boundaries. Use `classDef person|system|container|ext` so kinds look different.
- Keep each diagram to about 6 to 10 nodes. Each node is a real module, function, table or service name plus at most one short line (a few words). Put detail in the table next to the diagram, not in the boxes.
- Show the main path and at most one or two failure or alternative branches. If more is needed, draw a second diagram.
- Label an arrow only when what moves is not obvious, in two or three words.
- Always put label text in double quotes when it contains brackets, parentheses, colons, slashes or commas: `a["handler (HTTP)"]`.
- Do not use `end` as a node id. Avoid `%` and `#` inside labels. Use `<br/>` for line breaks, not `\n`, inside labels.
- Each diagram must be backed by citations in `cite`, and must not show components you did not see in the code. Mark guessed parts by setting `conf` to `inferred`.

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
 "interfaces": [{"what": "HTTP route, CLI command, exported API, message topic", "direction": "in|out|both", "cite": "path:10-30"}],
 "data": [{"what": "entity, table, schema, file format, message", "fields": "key fields", "cite": "path:10-30"}],
 "flows": [{"what": "how a main operation moves through the code, in order of files and functions", "cite": "path:10-80"}],
 "external": [{"what": "database, API, queue, service, library with a role", "cite": "path:5"}],
 "config_and_secrets": [{"what": "setting or secret and how it is supplied", "cite": "path:5"}],
 "risks": [{"what": "...", "conf": "confirmed|inferred", "cite": "path:5"}],
 "unclear": ["things you could not work out and why"]}
```

Large repositories are read with Sonnet subagents (1M context window) on chunks of the default size. No model switch is needed.

## Corrections and updates

- Read `state.json` first. Every entry in `corrections` is a fact supplied by the user. It overrides anything you or the profiler inferred. Apply it everywhere it matters and never contradict it.
- `user_decisions` (also in `state.json` under `resolutions`) lists items the user confirmed, answered or disputed. When you rewrite or update a report, keep each of those statements, in wording as close as you can to the original so the page can match it. Do not argue with a decision. For `answer`, write the statement as `confirmed` using the user's answer. For `wrong`, rewrite the statement using the user's text and mark it `confirmed`. For `confirm`, you may leave it `inferred`; the page shows it as confirmed by the user.
- If `existing_reports` is not empty and `previous_build` shows the commit changed, update the existing reports instead of rewriting from scratch. Use `facts.json` `delta.changed` to find what moved. Re-read changed areas, keep what still holds, and update citations, because line numbers drift. Chunks with cached notes need no re-reading.
- In `overview.json` you may set `update_note`: one plain sentence on what changed in the analysis this time. It appears in the history table.
