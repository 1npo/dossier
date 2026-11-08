# Report specifications

Write one file per report to `reports/<id>.json`, following `method.md`: `headline`, `summary` and `cards`. Each report below lists its cards in schema order. Write every card marked as written by you, in that order, and leave out the cards that code draws.

Before each report, run `DOSSIER candidates <repo> --report <id>`. It lists the tool findings that feed the report, grouped by the card they belong to. After the report, run it again with `--open`; it must print nothing.

**Write the reports in this order:** `entry`, `components`, `interactions`, `io`, `data`, `behavior`, `conventions`, `ops`, `change`, `contributors` (it needs the component catalog), then `reading` (it needs the entry points and components), then `overview`, `risks` (last of the three, so it can use the measured findings and `change`) and `gaps`.

A report is as long as its content. Never merge items to shorten a table; the page sorts, filters and collapses long tables.

**Executive summaries are short and plain.** Write `summary` as 3 to 5 bullets (`- ` lines or list items), each one sentence of about 20 words or fewer, in everyday words. Lead with the answer. No filler, no restating the headline, no jargon the reader has to look up.

The page also shows measured tables from `facts.json` (languages, environment variables, secret scan, code ownership). Do not repeat those tables. Refer to them with `[[facts:...]]` and add what only reading the code can tell.

**Repositories with more than one language.** The cards are the same as for any other repository, and the rows cover every language. Say which language a row belongs to only where it matters, for example in an entry point or a component that exists in both.

## entry

Report 04: Entry points. Question: *Where does execution start?*

### Entry points (`entry.catalog`)

Every way execution can start. Decide about each finding: console scripts, `__main__` modules, CLI commands (one row per command, and mark `added: true` when no tool found it), HTTP routes (one row per route group), scheduled jobs, queue consumers, container commands, CI schedules, Makefile targets, systemd units, shebang scripts. `Starts at` names the function or file.

In JavaScript and TypeScript repositories the findings also include package bins, package scripts, `main` entries, Nx targets and UI routes. Write a route's full path: add any prefix that a `route-mount` finding shows, so a router mounted under `/api` is `GET /api/tags` and not `GET /tags`. Keep one row per entry point. Package scripts are entry points. A script that only wraps another one may be merged with it only when both have the same `path` and `name`; otherwise dismiss it with a reason.

Shape: a table with columns Kind, Name, Triggered by, Starts at, Notes.

Tool findings that arrive here (home card): entry points. Decide about each (see "Tool findings" in `method.md`).

### Startup sequence (`entry.startup`)

One sequence diagram of the main entry point: configuration load, wiring, readiness. Name each participant after a real module. Follow it with a text block of numbered notes.

Shape: diagram blocks (at most 1), each followed by one text block of numbered lines (`1. ...`, `2. ...`) or one list block, with at least two steps.

## components

Report 05: Components. Question: *What are the main parts, what does each do, and how does it work?*

### Component map (`components.map`)

Drawn by code from the tool findings. **Do not write this card:** leave it out of the file.

### Component catalog (`components.catalog`)

One row per component, drafted from the component candidates (see "Components" in `method.md`). `Paths` lists the component's folders, files or globs in backticks. `Depends on`, `Used by` and `Size` are measured and drawn by code: write `-` in those three cells. List files that belong to no component in the entry's `unassigned` list. A repository of several apps gets one component per folder with a clear job; do not merge apps into one component. `Public surface` names what the component offers to other packages, or says that it is internal.

Shape: a table with columns Component, Paths, Responsibility, Public surface, Depends on, Used by, Size.

### Component details (`components.detail`)

One entry for every row of the catalog, with the component's name as the `component` key. A repository with more than 12 components gives this card to one subagent per area.

Shape: `entries`, keyed by `component`, each with the fields: `purpose` (Purpose), `how_it_works` (How it works), `public_surface` (Public surface), `state_owned` (State owned), `key_files` (Key files), `gotchas` (Gotchas).

### Cross-cutting concerns (`components.cross-cutting`)

How the code handles each concern, and where. Keep every fixed row; write that it does not apply as `confirmed`, with evidence, when it does not.

Shape: a table with columns Concern, Approach, Where.

Fixed rows (column Concern): configuration; authentication/authorisation; logging; error handling; caching; validation; i18n; feature flags.

### Extension points (`components.extension-points`)

Where and how a developer plugs something in (registries, base classes, hooks, plugin folders), with an example from the repository. Use `na` with evidence if there is no such mechanism.

Shape: a table with columns Point, How to extend, Example.

## interactions

Report 06: Interactions. Question: *How do the parts talk to each other, and where does state live?*

### Dependency graph (`interactions.graph`)

Drawn by code from the tool findings. **Do not write this card:** leave it out of the file. In a React repository the card also lists the React components, with what each renders and which hooks and context it uses; use that list when you write the flows. How context values reach their consumers, and what a custom hook wires up, are not worked out: Gaps says so.

### Cycles and layer violations (`interactions.violations`)

Drawn by code from the tool findings. **Do not write this card:** leave it out of the file.

### Key flows (`interactions.flows`)

One sequence diagram for each kind of entry point, each followed by numbered notes (one per step of the diagram), and more wherever a flow teaches something the others do not. Name each participant after a real module or component. `render` checks that every arrow has an import or a call behind it (V3).

Shape: diagram blocks, each followed by one text block of numbered lines (`1. ...`, `2. ...`) or one list block, with at least two steps.

### State ownership (`interactions.state`)

Where state lives: databases, caches, files, module-level variables and globals. Decide about each finding. `Lifetime` says how long it lives (process, request, forever).

Shape: a table with columns State, Held in, Written by, Read by, Lifetime.

Tool findings that arrive here (home card): db-access, global-state, cache. Decide about each (see "Tool findings" in `method.md`).

### Concurrency model (`interactions.concurrency`)

Threads, async code, process pools, workers, queues and locks, and the shared state they touch. Use `na` with evidence if the code is single-threaded and synchronous.

Shape: a table with columns Mechanism, Where, Shared state, Notes.

Tool findings that arrive here (home card): thread, async, process-pool, lock, queue. Decide about each (see "Tool findings" in `method.md`).

## io

Report 07: Inputs and outputs. Question: *What goes in and what comes out?*

### Inputs (`io.inputs`)

Everything the program takes in. Decide about every finding. One row per CLI command's arguments and one row per environment variable. The fixed categories stay as rows; a category that does not apply is a row whose input is `none`, with evidence. Network routes are one row per route group.

Shape: a table with columns Category, Input, Format, Validation, Where read.

Fixed rows (column Category): CLI arguments; environment variables; config files; files read; stdin; network requests; messages consumed; database reads; scheduled triggers.

Tool findings that arrive here (home card): cli-args, env-var, config-file, file-read, stdin, message-consume. Decide about each (see "Tool findings" in `method.md`).

### Outputs (`io.outputs`)

Everything the program puts out, including exit codes and error responses (the error catalog lives here). Decide about every finding. Keep the fixed categories.

Shape: a table with columns Category, Output, Format, Validation, Where written.

Fixed rows (column Category): stdout/stderr; files written; network responses; outbound calls; messages produced; database writes; logs; metrics; exit codes; error responses.

Tool findings that arrive here (home card): stdout, file-write, outbound-call, message-produce, exit-code, error-response. Decide about each (see "Tool findings" in `method.md`).

### Contracts (`io.contracts`)

Written agreements with other systems: OpenAPI, protobuf, GraphQL and JSON-schema files, public exports, route tables, client SDK use. Consumers outside the repository are `unknown` unless declared.

Shape: a table with columns Contract, Direction, Counterparty, Schema location, Versioning. One row per contract and direction. The page draws a table of the real public API of each package below your rows (what other packages can import); never copy it. Write one row per package that has such an API, as `offered`. `Direction` is exactly `offered` (this repository publishes it) or `consumed` (this repository relies on it); `summary.json` joins repositories on that word, and `render` fails on anything else.

## data

Report 08: Data model. Question: *What data exists, and what is true about it?*

### Entities and types (`data.entities`)

Every entity the code defines: dataclasses, Pydantic and ORM models, SQL tables, typed dictionaries, enums, and in TypeScript interfaces, object types, enums, Prisma models and ORM classes (the tool leaves out `Props` types). Decide about each finding (migrations are not entities). One row per entity: `Fields` lists every field by name, and `Owner component` names a catalog component.

Shape: a table with columns Name, Kind, Fields, Defined in, Owner component.

Tool findings that arrive here (home card): data models. Decide about each (see "Tool findings" in `method.md`).

### Relationships (`data.relationships`)

Drawn by code from the tool findings. **Do not write this card:** leave it out of the file.

### Data stores (`data.stores`)

Each database, cache or file store, its technology, what it holds, and how its schema is changed. Decide about each connection finding.

Shape: a table with columns Store, Technology, Holds, Migration approach.

Tool findings that arrive here (home card): db-connect. Decide about each (see "Tool findings" in `method.md`).

### Source of truth (`data.truth`)

For each kind of data, which store is the source of truth and which copies are derived.

Shape: a table with columns Data, Source of truth, Derived copies.

### Lifecycle and sensitive fields (`data.lifecycle`)

When data is created, changed, retained and deleted, and which fields look sensitive (identification only, not an audit).

Shape: a table with columns Data, Created, Changed, Retained, Deleted, Sensitive?.

## behavior

Report 09: Behavior and tests. Question: *What does it guarantee, how is that checked, and how does it fail?*

### Business rules and invariants (`behavior.rules`)

The business rules and invariants that make this program this program, with where they are decided and their edge cases. If there is no real domain logic, write one `confirmed` row that says so.

Shape: a table with columns Rule, What it does, Where decided, Edge cases.

### Test landscape (`behavior.tests`)

The test landscape. The first table is measured: use the test findings for counts by kind, frameworks, skips, mocks and coverage settings, and add what only reading tells (what is untested that matters). The second table asks whether a green run can be trusted. No test is executed.

Shape: a table with columns Measure, Value, Where; then a table with columns Question, Assessment, Evidence.

Fixed rows (column Measure): test counts by kind; test counts by area; framework; skipped and xfail counts; mock density; test-to-source mapping; coverage configuration and thresholds; CI test commands.

Second table, fixed rows (column Question): What important code is untested?; Can a green run be trusted?.

### Failure modes (`behavior.failures`)

How the system fails: one row per failure mode, with trigger, detection, effect and recovery. Decide about each finding (retries, timeouts, catch-all handlers, transactions). Mention idempotency.

Shape: a table with columns ID, Failure, Trigger, Detection, Effect, Recovery; then a text.

Tool findings that arrive here (home card): retry, timeout, catch-all, transaction. Decide about each (see "Tool findings" in `method.md`).

### Observability (`behavior.observability`)

Logging, metrics and tracing: the library, where each signal is emitted and where it goes. Decide about each finding; log call sites are grouped, so one decision covers a rule in a file.

Shape: a table with columns Signal, Library, Where emitted, Where it goes.

Tool findings that arrive here (home card): log, metric, trace. Decide about each (see "Tool findings" in `method.md`).

## conventions

Report 11: Conventions. Question: *How do I write code that fits in here?*

### Code conventions (`conventions.style`)

The code conventions a newcomer must follow, with evidence and how consistent the code is. Keep the fixed areas.

Shape: a table with columns Area, Convention, Evidence.

Fixed rows (column Area): naming; error handling; logging; dependency injection; async; validation; tests.

### Recipes (`conventions.recipes`)

A numbered recipe for each fixed task. `Files to touch`: one step per line, `1. path — change`, in order. `Worked example`: cite the commit that did the same thing (`[[commit:<sha>]]`), found with `git log --follow -p` or `git log -S`; when no commit did, the statement is `unknown` with a note. A recipe that does not apply says so with evidence.

Shape: `entries`, keyed by `recipe`, each with the fields: `files_to_touch` (Files to touch, in order), `worked_example` (Worked example in this repository).

Fixed rows (column recipe): add an endpoint or command; add a field; add a migration; add a test; add a dependency; add a config setting.

### Formatting and tooling (`conventions.tooling`)

Drawn by code from the tool findings. **Do not write this card:** leave it out of the file.

## ops

Report 12: Build, run and ship. Question: *How do I get it running and into production?*

### Local setup (`ops.local`)

How to set up a machine: ordered steps, then a table of prerequisites (runtimes and versions, services, data, secret names).

Shape: a list, drawn as a numbered list, so one step per item and no numbers in the text; then a table with columns Prerequisite, Kind, Version or detail, Where stated.

### Build and packaging (`ops.build`)

What gets built, with the command and the output.

Shape: a table with columns Artifact, Command, Output.

### Running tests (`ops.test`)

How to run the tests: command and notes for each scope (all, unit, one file).

Shape: a table with columns Scope, Command, Notes.

### Running it (`ops.run`)

How to run the program: command and needs for each mode.

Shape: a table with columns Mode, Command, Needs.

### CI gates (`ops.ci`)

Each pipeline: trigger, steps, whether it blocks a merge, what it publishes. Say what the gates do and do not guarantee.

Shape: a table with columns Pipeline, Trigger, Steps, Blocks merge?, Publishes.

### Release, deploy and rollback (`ops.release`)

How each environment is released and rolled back, and how versions are set. Anything outside the repository is `unknown`.

Shape: a table with columns Environment, How released, How rolled back, Versioning.

### Configuration and secrets (`ops.config-secrets`)

Two tables: settings (default, what overrides it) and secrets by name only, never values. Start from `facts:env_vars` and `facts:secret_signals`.

Shape: a table with columns Setting, Default, Overridden by; then a table with columns Secret, Unlocks, Supplied how.

## change

Report 10: Change and history. Question: *Where is it safe to change, and how did it get here?*

Most cards of this report are drawn from the git history and the tool findings. Run `DOSSIER candidates <repo> --report change` first: it lists the decision markers (`HACK`, `XXX`, workaround and bug-id comments) as findings to decide, then suggestions that are not findings: decision documents, long commit messages, TODO and FIXME counts per file, old-looking names, names defined in more than one file, and bulk commits.

### Hotspots (`change.hotspots`)

**Do not write this card.** The page draws it from the history: every source file with its changes in the 12 months before the pinned commit, ranked bars and a table by file or component, over the past 12 months or all time.

### Co-change coupling (`change.cochange`)

**Do not write this card.** The page draws it: pairs of files that changed together in at least 3 commits, and whether an import joins them.

### Blast radius (`change.blast-radius`)

**Do not write this card.** The page draws it from the import graph, with a picker for one file or component.

### Unfinished migrations (`change.unfinished`)

Patterns in the code where an old way and a new way live side by side. Use the hints that `candidates` prints (old-looking names, names defined more than once, TODO density) and the code itself. One row per pattern. `Progress` must be a count or a fraction you can cite, such as `14 of 20 call sites use the new client`, never a feeling. When nothing is half-finished, use `na` with the evidence you looked at.

Shape: a table with columns Pattern, Old way, New way, Progress, Evidence.

### Decisions and oddities (`change.decisions`)

Things that look odd and the reason, as far as it is known. Decide every marker the tools found (see "Tool findings" in `method.md`): keep it in a row, add the id to `dismissed` with a reason, or cover a group of markers with its group id (`mkg-...`), which is allowed here. Add decision documents (ADRs, design notes) and long commit messages that explain a choice, marked `added: true` when no marker covers them. When the reason is not written anywhere, say `unknown`; do not invent one. `Source` says where the reason comes from: a comment, a commit message, a document, or `none`.

Shape: a table with columns Item, Why (as far as known), Evidence, Source. The page adds its own Basis and Citations columns after `Source`.

### Dead code and stale flags (`change.dead-code`)

**Do not write this card.** The page draws the tool findings: unused code, unused dependencies, and modules nothing imports. Stale feature flags and unused routes are not detected, and Gaps says so.

### Docs versus code (`change.docs-drift`)

Sample the claims in the README and the documents (install steps, architecture statements, endpoint lists) and check each against the code. One row per claim. `Verdict` is one of `matches`, `outdated` or `cannot tell`. Cite the document and the code.

Shape: a table with columns Claim, Document, What the code shows, Verdict.

### Upgrade burden (`change.upgrade-burden`)

**Do not write this card.** The page draws it from the lockfile versions and a shipped end-of-life snapshot.

### Work in flight (`change.in-flight`)

**Do not write this card.** The page draws it from the remote branches.

## contributors

Report 13: Contributors. Question: *Who owns and knows what, and what is the bus factor?*

Run `DOSSIER candidates <repo> --report contributors` first. It lists every person, possible duplicate identities, and for each component who wrote it, who owns it and who changed it lately. Write display names, never email addresses. Every person, agent and component must appear: `render` fails when one is left out or when a name matches nobody in this build.

**Ownership.** A line belongs to the owner of the commit that last changed it. The owner of a commit is: the only human in the history, when there is exactly one; the author, when the author is a human; the human who approved or merged the pull request, when an agent or a bot was the author; otherwise the author. Judge `Owner` from the owned lines in the candidates output, not from the authored ones. Measured cells are written as `-` and the page fills them.

### Who the people are (`contributors.people`)

One row per human, with a plain description of their role (from commits, files and areas, not guesses about job titles) and whether they are still active. A person you think is a duplicate of another goes in `contributors.doubts` instead of here, or in both.

Shape: a table with columns Person, Role in the project, Areas, Active?.

### Who to ask (`contributors.ask`)

One row per component of the catalog. `Ask first` and `Then` name people. `Basis` is the evidence: most owned lines, most recent changes, or both.

Shape: a table with columns Subsystem, Ask first, Then, Basis. The page adds a Confidence column and a Source column after `Basis`.

### Knowledge concentration (`contributors.concentration`)

One row per component. Write `Area`, `Owner` and `Status`; write `-` in `Share`, because the page fills it from the owned lines and states the bus factor above the table. `Status` is exactly `single owner`, `departed` or `shared`. `departed` and any at-risk statement are `inferred`, with a note saying what would confirm it. On a project with one human, that human is the owner of every component. When nobody owns a line or has a commit in a component, `Owner` is `unknown` and the row is `conf: unknown`.

Shape: a table with columns Area, Owner, Share, Status.

### Agents and bots (`contributors.agents`)

One row per identity that is an agent or a bot, and one row per assistant that only appears as a co-author of human commits (`candidates` lists them as agent markers). Models that share an email address are one identity. `Kind` is `agent`, `bot` or `assistant`. Write `-` in `Areas touched` and `Share of commits`; the page fills them. When the history has no agents, bots or assistants, use `na` with `facts:contributors`.

Shape: a table with columns Identity, Kind, Areas touched, Share of commits.

### Classification doubts (`contributors.doubts`)

Identities that might be one person, or that the tools may have classed wrongly (a human called `ci`, a bot with a human name). Use the possible duplicates that `candidates` lists. Say what would settle each one. When there are none, use `na`.

Shape: a table with columns Identity, Doubt, What would settle it.

### Team workflow (`contributors.workflow`)

**Do not write this card.** The page draws the six workflow rows from git: branch naming, merge style, commit message style, pull request size, review rate and release cadence.

## reading

Report 03: Reading guide. Question: *How do I approach this code?*

### Reading order (`reading.order`)

The order to read the code in, grouped into phases (for example orientation, core, periphery); there is no step limit. Start from the entry points and move outward; the findings list shows which modules are imported most, so read those early. Include tests where they explain behaviour. `Read` is one file, directory or glob in backticks; `What you learn` is one sentence of about 15 words.

Shape: a table with columns Phase, Step, Read, What you learn.

### Glossary (`reading.glossary`)

The domain terms a newcomer will meet in class, type and table names. Define each in one sentence and say where it lives. Skip generic programming words.

Shape: a table with columns Term, Meaning, Where it lives.

### Technologies and idioms (`reading.technologies`)

Each language, framework and library with a role in the code (from the manifests and imports), what it does here, and the idiom a newcomer needs to know (DI container, ORM style, state management; for React, the state, routing and data-fetching idioms).

Shape: a table with columns Technology, Role here, Idiom to know.

### Where things live (`reading.map`)

Drawn by code from the tool findings. **Do not write this card:** leave it out of the file.

## overview

The one-page answer to "what is this?". It has no cards to write: the page draws the repository, contributors and dependencies cards from measurements. Write `headline` and `summary` (what the project is, who it serves, how big and mature it looks, and the three things to know first), and optionally `update_note`: one plain sentence on what changed in the analysis this time. `cards` is not needed.

## risks

A register of everything risky or doubtful: the card `risks.tracker`. Use one or more tables with exactly the columns `ID`, `Risk`, `Category`, `Severity`, `Impact`, `Recommendation`, `Source`. `Source` is exactly `extractor` when a tool's output found the risk, or `read` when you found it by reading the code. IDs are R1, R2, and so on. Order by severity; the page counts Critical and High rows and highlights those tiles. Severity is Critical, High, Medium, Low or Info. Categories include security, reliability, data, performance, maintainability, testing, dependencies, delivery, knowledge concentration, compliance.

Rules: every row has citations. A row based on inference is `inferred` with a note, and still goes in the register. Include risks from the tool findings and from the scan in `facts.json` (cycles and layer violations in `interactions.violations`, unused code, secrets, unpinned or abandoned dependencies, no tests for important areas, single-person areas from `facts:areas`, very large or very hot files). Do not pad with generic advice, and do not add a "How to read this register" text block: put anything the reader needs to know in the summary. Summary: the top three risks in plain words and the overall picture.

## gaps

Items not already listed by the page. The page already collects every `inferred` and `unknown` statement from all reports automatically, and it adds the checks' own items: files in no component, tool findings with no decision, blind-spot places, names that are not in the code they cite, and diagram arrows with no import or call behind them. This report adds the rest in `items`:

```json
{"items": [{"kind": "assumption|unknown|inference|coverage", "statement": "...", "how_to_confirm": "...", "report": "overview", "cite": []}]}
```

- `coverage`: what you did not read or only sampled, and why. Always disclose excluded files (see `facts.files.excluded`), large files read only in part, and chunks you could not finish.
- `assumption`: something you took as true to proceed (for example that the default branch is the released state).
- `unknown` or `inference`: only for items that did not fit in another report's rows.

The `summary` should say how complete the dossier is and which gaps matter most. `blocks` may be empty.

## corrections

Not written by you. It is built from `state.json`. When the user corrects you, record it with the CLI (see SKILL.md), update the affected reports, then mark the correction applied.
