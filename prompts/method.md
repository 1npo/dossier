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

Do not present an inference as confirmed. Do not leave a gap unstated. If a topic does not apply (a library has no database), say so as `confirmed` and cite the evidence you used (for example `facts:manifests`).

### Citation forms

Write citations inline as `[[path]]`, `[[path:12]]` or `[[path:12-30]]`, or list them in a `cite` array. Other forms:

- `commit:<sha>` for a commit in this history.
- `facts:<key>` for a measured figure. Keys: `git`, `languages`, `hot_files`, `manifests`, `env_vars`, `secret_signals`, `contributors`, `ownership`, `areas`, `chunks`.

Rules:

- Paths are relative to the repository root, exactly as git lists them. Line numbers refer to the pinned commit.
- A sentence that depends on a file ends with its citation, `[[path:12-30]]`. The page shows it as a numbered marker. Do not start the citation with "See": the marker is the pointer. A source cited inline is never repeated by the page, so also listing it in `cite` is harmless.
- When a sentence is *about* one specific file (a reading order, an entry point, "the bootstrap is install.sh"), name the file in the sentence with the labelled form `[[path:12-30|name]]`. The page shows `name` in code style followed by the numbered marker. Use `|name` for the file the sentence is about, and the plain form for evidence at the end of a sentence. Never write a bare or backticked path for a tracked file.
- A citation is evidence, never a name. Do not start a sentence with `[[path]]`, and do not put one where a file name belongs ("sets no strict mode" after a bare citation, or "defined in" followed by one). Wrong: `[[install.sh:33-84]] sets no strict mode.` Right: `[[install.sh:33-84|install.sh]] sets no strict mode.` or `The bootstrap sets no strict mode [[install.sh:33-84]].` The page adds the path as a label when it finds a bare citation in a name position, but write the label yourself.
- Cite each source once per statement. Do not write the same citation inline and again as a trailing "See ...".
- In a table cell that holds only a file, directory or glob (a Name column, for example), write it in backticks: `scripts/lib`, `scripts/targets/*.sh`. The page also does this for any such cell that exists at the pinned commit.
- Cite the complete block that supports the claim: the whole function body or config stanza, not only the line that names it. A reader clicks a citation to read that code in a side panel, so a range that stops short of the evidence is a defect. Do not cite a whole large file when the block is thirty lines. If the evidence is in several places, use several citations.
- A citation to a directory, a commit or a `facts:` key does not open the code panel, so prefer a file range wherever one proves the point.
- `render` fails if a citation does not resolve. Check line numbers before you write them.

## Report file shape

One JSON file per report in `reports/`. All have `headline` (one sentence), `summary` (the executive summary) and `blocks`. Block types:

```json
{"type": "text", "heading": "required", "text": "paragraphs, - bullets, `code`, **bold**, [[path:1-9]]", "conf": "confirmed", "cite": [], "note": ""}
{"type": "list", "heading": "required", "items": [{"text": "...", "conf": "confirmed", "cite": ["path:3"], "note": ""}]}
{"type": "table", "heading": "required", "caption": "optional", "columns": ["A", "B"],
 "rows": [{"cells": ["a1", "b1"], "conf": "confirmed", "cite": ["path:3"], "note": ""}]}
{"type": "diagram", "heading": "required", "title": "what it shows", "mermaid": "flowchart LR\n ...", "conf": "confirmed", "cite": ["path:3"], "note": ""}
```

Every block is shown as a card, and the page lists the cards by name in a contents list under the executive summary. So every block needs a short `heading` (2 to 6 words) that says what the card holds. A block without one gets a name made up by the page, which reads worse.

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
 "interfaces": [{"what": "HTTP route, CLI command, exported API, message topic", "direction": "in|out|both", "cite": "path:10-30"}],
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

- Read `state.json` first. Every entry in `corrections` is a fact supplied by the user. It overrides anything you or the profiler inferred. Apply it everywhere it matters and never contradict it.
- `user_decisions` (also in `state.json` under `resolutions`) lists items the user confirmed, answered or disputed. When you rewrite or update a report, keep each of those statements, in wording as close as you can to the original so the page can match it. Do not argue with a decision. For `answer`, write the statement as `confirmed` using the user's answer. For `wrong`, rewrite the statement using the user's text and mark it `confirmed`. For `confirm`, you may leave it `inferred`; the page shows it as confirmed by the user.
- **Updating.** `prepare` prints an `update_plan`. When its `mode` is `incremental`, rewrite only the reports in `stale` and leave every other report file untouched: do not open, re-save or reword them. Each stale report comes with reasons (a cited file changed, was deleted, gained a neighbour, a correction is pending). Start from the existing report: read it and the files in `update_plan.read`, keep every statement that still holds, change what the code now contradicts, add what is new, and fix citations. Do not re-read parts of the repository that no stale report touches. `prepare` already moved the line numbers of fresh reports; it never edits a stale one.
- A stale `overview` and `contributors` only need their statements about the repository as a whole refreshed (size, activity, people, what changed). Set `update_note` in `overview.json`. A stale `gaps` needs its items rebuilt from the other reports' current unknowns, inferences and assumptions.
- If an update leaves a fresh report wrong (a change elsewhere made it untrue), rewrite that report too and say so to the user. `--full` rebuilds everything.
- Chunk notes are only for full builds of chunked repositories. Chunks with cached notes need no re-reading.
- In `overview.json` you may set `update_note`: one plain sentence on what changed in the analysis this time. It appears in the history table.
