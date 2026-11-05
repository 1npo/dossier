# dossier 1.0.0 specification

Status: draft for review. Amended on 2026-11-01 after the review of the M2 plan (`plans/007-m2-plan.md`, section 8); the amendments are listed in section 12 under "Settled in the M2 plan review". Amended again on 2026-11-05 after the review of the M3 plan (`plans/009-m3-plan.md`), listed under "Settled in the M3 plan review". Supersedes the middle-report design in `prompts/reports.md` (everything between "This repository" and "Risks"). The decisions in plans 001 to 003 (renames, colours, card clean-ups, Dependencies card, gatherer terminology) still apply unless this document says otherwise.

## 1. Purpose and boundaries

`dossier` builds a **map of one git repository at one pinned commit**, for an engineer who did not write it and now has to maintain it. It answers a fixed list of questions (section 3). Every card in the page exists to answer one of them.

A map is not a mental model. The map orients the reader, and the model forms when the reader traces, runs and changes the code. The dossier's job is to make that fast and to say where it cannot be trusted.

### In scope for 1.0.0

- One repository, one pinned commit, committed state only.
- Static analysis, git history, and Claude reading the code.
- Full extractor support for **Python, TypeScript/JavaScript (including React) and C#**. All other languages get Tier B support (section 6.3).
- Build, test, run and deploy documentation as read from the repository.
- A machine-readable `summary.json` for the future `portfolio` feature (section 9).
- Who approved a merged pull request, read from GitHub with `gh`, used only to work out who owns a commit (4, "Who owns a commit"). All other pull request and issue content stays out of reach.

### Permanent non-goals

- Code-quality scoring (SonarQube covers it at work).
- Security auditing and vulnerability scanning (Snyk covers it at work). The Risks report keeps listing risks it observes, such as a committed secret, but dossier does not scan for vulnerabilities and must not present itself as a security tool.

### Not in 1.0.0 (deferred)

- Cross-repository views. Handled by `portfolio`, which reads each repo's `summary.json`.
- Running the target's tests or application. Coverage and runtime behaviour are read from config and CI definitions only.
- Building a dossier from uncommitted work. Possible later by committing a snapshot object under `refs/dossier/`, which keeps the pin.
- A custom Roslyn analyser. Decided: deferred (section 12).
- Questions that need people or other systems: business purpose, lifecycle stage, performance and scaling, cost, incident history, issue tracker content. These show up in Gaps as `unknown` where relevant.

## 2. Design principles

1. **Tools find, Claude explains.** Anything that can be enumerated (entry points, routes, imports, I/O sites, models, tests) is extracted by a tool. Claude never has to remember it.
2. **Candidate, adjudicate, reconcile.** For every candidate list, each candidate gets a recorded disposition: included, merged, or dismissed with a reason. Claude may add items the tool missed, marked as such. A candidate with no disposition fails the build. The candidate lists are entry points, input/output and related sites (`io_candidates`: inputs, outputs, state, concurrency, failure handling, observability, data-store connections) and data entities. Measured outputs are not candidate lists and are never pruned by a model: the import graph, symbols, test counts, dead code (drawn by code) and blind-spot hits (which go to Gaps). Neither are the computed suggestions for components, reading order and glossary terms, since V4 already reconciles components file by file. Decision markers (`HACK`, `XXX`, workaround and bug-id comments) are a fourth candidate list, with `change.decisions` as their home card. Each kind of candidate has one home card where it is decided (6.1); a decision on any other card counts too, and a candidate kept on one card and dismissed on another is an error.
3. **Three provenance tiers**, shown on every card as a small badge:
   - **M, measured:** tool output only, no model involved.
   - **A, adjudicated:** tool candidates, with Claude classifying, pruning, adding and explaining.
   - **R, read:** Claude's reading of the code, cited. Every statement is still `confirmed`, `inferred` or `unknown`.

   Shading stays two-colour as in plan 001 (measured facts versus anything a model wrote). M cards use the facts shade. A and R cards use the model shade.
4. **A closed card schema.** Writers do not choose cards or titles. A report is a fixed ordered list of cards with fixed ids, titles, shapes and required columns. A card that does not apply is still present and says so as a `confirmed` statement with evidence (`"na": "reason", "cite": [...]`). Two repos therefore always produce the same report skeleton.
5. **Each fact lives in one place.** Other reports link to the owning card and do not restate it.
6. **Say where the analysis is blind.** Every extractor declares the dynamic patterns it cannot see (section 6.4), and the dossier searches for them and reports hits.
7. **The structure is fixed; size only changes content.** The number of reports and cards never depends on the size of the repository. A larger repository gets longer tables, more diagram detail and more entries inside a card, not more cards, and nothing is dropped to fit a limit. There are no caps on components, entities, entry points, flows or rows. Only the executive summary is bounded (3 to 5 bullets of 20 words or fewer), because it is a summary. Keeping large content readable is the page's job (sorting, filtering, collapsing, search), never omission.

## 3. Questions, and where they are answered

The list below is shipped as data (`prompts/schema/questions.json`: question id, text, and the cards that answer it) and is shown in every dossier as the card `dossier.questions` in report 01.

Tags: S static extraction, G git history, L Claude reading, X outside the repository.

| # | Question | Tags | Report / card |
|---|---|---|---|
| 1.1 | What do the domain terms mean? | L | 03 `reading.glossary` |
| 1.2 | What technologies and idioms must I know, and which are probably new to me? | S, L | 03 `reading.technologies` |
| 2.1 | Where is execution entered? | S, L | 04 `entry.catalog` |
| 2.2 | What happens from entry to ready? | L | 04 `entry.startup` |
| 2.3 | What are the main components? | S, L | 05 `components.map`, `components.catalog` |
| 2.4 | What does each do and how does it work, including cross-cutting concerns? | L | 05 `components.detail`, `components.cross-cutting` |
| 2.5 | How do components interact? | S, L | 06 `interactions.graph`, `interactions.flows` |
| 2.6 | What are all the inputs and outputs? | S, L | 07 `io.inputs`, `io.outputs` |
| 2.7 | In what order should I read the code, and where do config, tests, build and docs live? | S, L | 03 `reading.order`, `reading.map` |
| 2.8 | Where does state live, and who writes and reads it? | S, L | 06 `interactions.state` |
| 2.9 | What is the concurrency model? | S, L | 06 `interactions.concurrency` |
| 2.10 | Where are the layer boundaries and who breaks them? | S | 06 `interactions.violations` |
| 2.11 | What extension points exist? | L | 05 `components.extension-points` |
| 2.12 | How do I write code that fits here? | L | 11 `conventions.*` |
| 3.1 | What contracts do I owe other systems, and who consumes them? | S, L, X | 07 `io.contracts` |
| 3.2 | What third-party code does each part rely on? | S | 02 Dependencies card (unchanged) |
| 4.1 | What are the data structures and schema? | S | 08 `data.entities`, `data.relationships` |
| 4.2 | What is the source of truth, what is derived, and which stores hold it? | A, L | 08 `data.truth`, `data.stores` |
| 4.3 | What is the data lifecycle, and where are the sensitive fields? | S, L | 08 `data.lifecycle` |
| 5.1 | What are the business rules and invariants? | L | 09 `behavior.rules` |
| 5.2 | What do the tests cover, and can I trust a green run? | S, G | 09 `behavior.tests` |
| 5.3 | How does it fail, and how would I notice in production? | S, L | 09 `behavior.failures`, `behavior.observability` |
| 6.1 | What changes most, and what never does? | G | 10 `change.hotspots` |
| 6.2 | What changes together without a code link? | G | 10 `change.cochange` |
| 6.3 | What breaks if I change X? | S | 10 `change.blast-radius` |
| 6.4 | Which refactors or migrations are half-finished? | L, G | 10 `change.unfinished` |
| 6.5 | Why is it this way? Which decisions and oddities need explaining? | L, G | 10 `change.decisions` |
| 6.6 | Does the documentation match the code? | L | 10 `change.docs-drift` |
| 6.7 | Is there dead code, or are there stale flags and unused endpoints? | S | 10 `change.dead-code` |
| 6.8 | What is the upgrade burden (end-of-life runtimes, lagging frameworks)? | S | 10 `change.upgrade-burden` |
| 6.9 | What work is in flight? | G, X | 10 `change.in-flight` (branches only; tracker content is `unknown`) |
| 7.1 | How do I build, test, run, release, roll back and deploy? | S, L | 12 `ops.*` |
| 7.2 | What do the CI gates guarantee? | S, L | 12 `ops.ci` |
| 7.3 | What do I need locally? | S, L | 12 `ops.local` |
| 8.1 | Who owns and knows what, and what is the bus factor? | G | 02 Contributors, knowledge map and calendar cards (unchanged); 13 `contributors.*` |
| 8.2 | What are the team's branching, commit and PR conventions? | G | 13 `contributors.workflow` |
| 10.1 | What was not analysed, and what could not be resolved? | S | 15 Gaps, and each card's footer |
| 10.2 | Where might the extractors be wrong? | S | 15 Gaps (blind-spot items) |
| 10.3 | How fresh is the dossier relative to HEAD? | S | 01 This dossier |
| 10.4 | How was this dossier produced, step by step, and what did a model do versus a tool? | S | 01 `dossier.process` |

Removed by decision: business purpose and lifecycle stage, dependence on externally operated services, performance and scaling and cost, incident history. Deferred: all of group 9.

## 4. Report structure

Report numbers continue the existing scheme. Reports 01, 02, 14, 15 and 16 are unchanged from the current design apart from plans 001 to 003. Every report except Gaps and Corrections has Executive summary, Contents (first) and References (last), as in `docs/scratch/000-fixed-cards.md`. These are not listed per report below. Priority: **P0** is required for 1.0.0, **P1** is the cut line if the schedule slips.

Each report shows its question under the title. Cards show their fixed title only.

### 01 This dossier, 02 This repository
Unchanged apart from the additions below. Report 02 keeps every card it renders today, including the Contributors, knowledge map, commit calendar and Dependencies cards. None of them moves. 01 gains the `freshness` BAN (pinned commit versus current HEAD of the ref) and the extractor list with versions (see 6.2).

Their existing cards are part of the schema and of 1.0.0, with their content unchanged. They are treated like every other card: fixed id and title, tier badge, and the shade that goes with the tier (M cards facts shade, A and R cards model shade). The one visible change is that "Reports in this dossier" (tier M) moves to the facts shade. The cards in the table below are drawn by code, not written by Claude (`computed` shape):

| Card id | Title | Tier | Content today | P |
|---|---|---|---|---|
| `dossier.about` | About this dossier | M | Build facts and statistics tiles | P0 |
| `dossier.reports` | Reports in this dossier | M | One row per report, with its one-sentence headline and counts of confirmed, inferred and unknown statements | P0 |
| `dossier.changelog` | Dossier changelog | M | One row per build | P0 |
| `overview.repository` | Overview | M | Repository and project facts, releases, languages | P0 |
| `overview.contributors` | Contributors | M | Contributor tiles, commit calendar, share-of-code bar, knowledge map, contributor table, and Owner and Author buttons (below) | P0 |
| `overview.dependencies` | Dependencies | M | The interactive dependencies card | P0 |

**Owner and Author buttons.** The Contributors card has a button group, Owner and Author. Author is selected when the page opens and shows the card as it has always been. Owner shows the tiles, the share-of-code bar and the contributor table by who owns each commit ("Who owns a commit", under report 13). The commit calendar and the knowledge map always show authors, and the Owner view says so. The buttons appear only when the build holds ownership data.

The order of report 01 is: `dossier.about`, `dossier.process`, `dossier.questions`, `dossier.reports`, `dossier.changelog`.

New cards in 01:

| Card id | Title | Tier | Shape | Source | P |
|---|---|---|---|---|---|
| `dossier.process` | How this dossier was made | M | A short numbered list of 8 to 10 steps in plain language. Each step has one sentence on what was done and a small run record: counts, tools used, and "skipped: reason" where a step did not run. Ends with one line: how many cards are measured, adjudicated and read | Written by a script from `build.json` (section 5.1), using fixed wording per step. **Claude does not write this card**, because a model's account of its own process drifts from what actually happened |
| `dossier.questions` | Questions this dossier answers | M | Table: No., Question, Answered in. One row for every question in section 3, in order. "Answered in" lists each card that answers it, as a link to that card (card title and report number), plus any panel outside the schema (for example the report 02 Dependencies card, or the report 01 freshness BAN). A question with no answering card is shown as "not answered in this version". Deferred and removed questions are not listed | Written by a script from `questions.json` and the card schemas. **Claude does not write this card.** A check fails the build if a question names a card id that does not exist, or a schema card answers no question and is not marked `informational` in the schema | P0 |

The fixed steps, in plain words:

1. Pinned the repository to one commit, so everything below describes that exact state.
2. Checked that the needed tools were installed (or listed which were missing and carried on in reduced mode).
3. Made a clean copy of the code at that commit, and installed its locked dependencies if allowed.
4. Measured the repository: files, languages, history, ownership, co-change.
5. Ran the extractors to find entry points, imports, inputs and outputs, data structures and tests.
6. Read the code: how much (single read or N chunks), with how many parallel readers, and what was reused from the last build.
7. Wrote the reports: for each list a tool found, decided what to keep, merge or drop, and explained how the parts work.
8. Checked the work: citations resolve, every tool-found item is accounted for, diagrams match real dependencies, the report layout matches the standard, and the page was opened in a real browser.
9. Recorded the open questions in Gaps, and anything the dossier could not see.
10. Rendered the page and the machine-readable summary.

Incremental builds show the same list with "reused from the previous build" on the steps that were skipped.

### 03 Reading guide
Question: *How do I approach this code?*

| Card id | Title | Tier | Shape | Source | P |
|---|---|---|---|---|---|
| `reading.order` | Reading order | A | Table: Phase, Step, Read, What you learn. Steps are grouped into phases (for example orientation, core, periphery); there is no step limit | Order from entry points outward, ranked by graph centrality (PageRank on the import graph), tests included as documentation. Claude writes the sentence per step | P0 |
| `reading.glossary` | Glossary | A | Table: Term, Meaning, Where it lives | Candidates: frequent identifiers in class, type and table names. Claude defines the domain ones | P0 |
| `reading.technologies` | Technologies and idioms | A | Table: Technology, Role here, Idiom to know | Manifests and imports. Claude adds the non-obvious idioms (DI container, ORM style, state management) | P0 |
| `reading.map` | Where things live | M | Table: Concern, Location | Detected locations: config, tests, build files, docs, migrations, CI | P0 |

### 04 Entry points
Question: *Where does execution start?*

| Card id | Title | Tier | Shape | Source | P |
|---|---|---|---|---|---|
| `entry.catalog` | Entry points | A | Table: Kind, Name, Triggered by, Starts at, Notes | Extracted (6.1): package scripts and bins, `__main__`, `Main`/`Program.cs`, CLI frameworks, HTTP routes (grouped), scheduled jobs, CI/cron, container `CMD`/`ENTRYPOINT`, queue consumers, shebang scripts, Makefile targets, systemd units | P0 |
| `entry.startup` | Startup sequence | R | Sequence diagram plus numbered notes | Claude, from the main entry point: configuration load, wiring, readiness | P0 |

### 05 Components
Question: *What are the main parts, what does each do, and how does it work?*

| Card id | Title | Tier | Shape | Source | P |
|---|---|---|---|---|---|
| `components.map` | Component map | M+A | Interactive hierarchical graph of every component, grouped by area. Groups collapse and expand, so any number of components stays readable. Until M6 delivers the interactive graph, the card shows a component diagram grouped by area plus a table of every component and its edges | Candidates from package and folder boundaries plus import-graph community detection. Claude names, merges and splits them (through `components.catalog`). The layout is computed, not drawn by Claude | P0 |
| `components.catalog` | Component catalog | A | Table: Component, Paths, Responsibility, Public surface, Depends on, Used by, Size | Paths, edges and size are measured. Responsibility is read | P0 |
| `components.detail` | Component details | R | One card holding one entry for every component in the catalog, each with the same fixed template: Purpose, How it works, Public surface, State owned, Key files, Gotchas. Entries are collapsible and searchable | Claude, with one subagent per group of components. V4 requires an entry for every component | P0 |
| `components.cross-cutting` | Cross-cutting concerns | R | Table: Concern, Approach, Where. Fixed rows: configuration, authentication/authorisation, logging, error handling, caching, validation, i18n, feature flags | Claude | P0 |
| `components.extension-points` | Extension points | R | Table: Point, How to extend, Example | Claude | P1 |

Invariant (V4): every tracked, non-excluded source file belongs to exactly one component or appears in an explicit "unassigned" list. When paths of several components match a file, the most specific path wins (a file beats a glob, a glob beats a directory, a deeper directory beats a shallower one), so a component and its sub-component can both be described by path. Only a tie between two different components is an error.

### 06 Interactions
Question: *How do the parts talk to each other, and where does state live?*

| Card id | Title | Tier | Shape | Source | P |
|---|---|---|---|---|---|
| `interactions.graph` | Dependency graph | M | Interactive module graph, edges weighted by import count. Until M6 delivers the interactive graph, the card shows a component-level diagram plus a sortable, filterable table of every module import | grimp, dependency-cruiser, Roslyn/SCIP | P0 |
| `interactions.violations` | Cycles and layer violations | M | Table: Kind, From, To, Evidence | Cycles from the graph. Layer rules taken from the repo's own config if present (import-linter contracts, dependency-cruiser rules, folder conventions). Otherwise only cycles | P0 |
| `interactions.flows` | Key flows | A | Sequence diagrams, one entry per flow, each followed by notes. At least one flow per kind of entry point; Claude adds more wherever a flow teaches something the others do not | Claude chooses flows from the entry points. V3 checks every arrow against a graph or call edge | P0 |
| `interactions.state` | State ownership | A | Table: State, Held in, Written by, Read by, Lifetime | Candidates: DB access sites, caches, globals, module-level mutables, files. Claude adjudicates | P0 |
| `interactions.concurrency` | Concurrency model | A | Table: Mechanism, Where, Shared state, Notes | Candidates: threads, async, process pools, workers, queues, locks | P0 |

### 07 Inputs and outputs
Question: *What goes in and what comes out?*

| Card id | Title | Tier | Shape | Source | P |
|---|---|---|---|---|---|
| `io.inputs` | Inputs | A | Table: Category, Input, Format, Validation, Where read. Fixed categories: CLI arguments, environment variables, config files, files read, stdin, network requests (grouped by route), messages consumed, database reads, scheduled triggers | Candidates from rule queries (6.1) plus `facts:env_vars`. Every candidate dispositioned (V5) | P0 |
| `io.outputs` | Outputs | A | Same shape. Categories: stdout/stderr, files written, network responses, outbound calls, messages produced, database writes, logs, metrics, exit codes, error responses | Same | P0 |
| `io.contracts` | Contracts | A | Table: Contract, Direction (offered/consumed), Counterparty, Schema location, Versioning | OpenAPI/proto/GraphQL/JSON-schema files, public exports, route tables, client SDK usage. Consumers outside the repo are `unknown` unless declared | P0 |

The error catalog, the configuration table and the secrets table from the old Failures and Delivery reports are absorbed here (exit codes and error responses in `io.outputs`, config in `io.inputs`) and in 12.

### 08 Data model
Question: *What data exists, and what is true about it?*

| Card id | Title | Tier | Shape | Source | P |
|---|---|---|---|---|---|
| `data.entities` | Entities and types | M+A | Table: Name, Kind, Fields, Defined in, Owner component | Extracted: classes, dataclasses/Pydantic, TS types and interfaces, EF entities, ORM models, SQL DDL, protobuf. Claude adds purpose | P0 |
| `data.relationships` | Relationships | M+A | ER diagram, split by component beyond 12 entities | Foreign keys, ORM relations, type references | P0 |
| `data.stores` | Data stores | A | Table: Store, Technology, Holds, Migration approach | Config, connection sites, migration folders | P0 |
| `data.truth` | Source of truth | R | Table: Data, Source of truth, Derived copies | Claude | P0 |
| `data.lifecycle` | Lifecycle and sensitive fields | A | Table: Data, Created, Changed, Retained, Deleted, Sensitive? | Migrations, delete paths, field-name rules for likely-sensitive fields. Identification only, not an audit | P0 |

### 09 Behavior and tests
Question: *What does it guarantee, how is that checked, and how does it fail?*

| Card id | Title | Tier | Shape | Source | P |
|---|---|---|---|---|---|
| `behavior.rules` | Business rules and invariants | R | Table: Rule, What it does, Where decided, Edge cases | Claude. If the repo has no real domain logic, one `confirmed` statement says so | P0 |
| `behavior.tests` | Test landscape | A | Measured: test counts by kind and area, framework, skipped/xfail counts, mock density, test-to-source mapping, coverage config and thresholds, CI test commands. Read: what is untested that matters, whether green can be trusted | Tree-sitter plus config parsing. No test is executed | P0 |
| `behavior.failures` | Failure modes | A | Table: ID, Failure, Trigger, Detection, Effect, Recovery. Plus retries, timeouts, idempotency | Candidates: retry decorators, timeout params, catch-all handlers, transactions | P0 |
| `behavior.observability` | Observability | A | Table: Signal, Library, Where emitted, Where it goes | Logging, metrics and tracing imports and call sites | P0 |

### 10 Change and history
Question: *Where is it safe to change, and how did it get here?*

| Card id | Title | Tier | Shape | Source | P |
|---|---|---|---|---|---|
| `change.hotspots` | Hotspots | M | Table plus scatter: churn (commits, 12 months) versus size/complexity, by file and by component | git log, tree-sitter complexity proxy | P0 |
| `change.cochange` | Co-change coupling | M | Table: A, B, Co-commits, Share, Linked in code? (yes/no) | git log with bulk-commit filter (`gather.BULK_FILES`). Lists pairs with at least 3 co-commits and states how many pairs that leaves out. Flags pairs with no import link | P0 |
| `change.blast-radius` | Blast radius | M | Interactive picker: choose a file or component, see its transitive dependents, importing tests and co-changing files | Reverse closure precomputed from the graph | P0 |
| `change.unfinished` | Unfinished migrations | R | Table: Pattern, Old way, New way, Progress, Evidence | Claude, helped by candidates: duplicate abstractions, `legacy`/`v1`/`v2`/`deprecated`/`old` names, TODO density, mixed-style counts | P0 |
| `change.decisions` | Decisions and oddities | A | Table: Item, Why (as far as known), Evidence, Source | ADRs, design docs, `HACK`/`XXX`/`workaround`/bug-ID comments, long commit messages on the file. Unknown reasons stay `unknown` | P0 |
| `change.dead-code` | Dead code and stale flags | M | Table: Item, Kind, Evidence | vulture, knip, unused route/flag detection | P0 |
| `change.docs-drift` | Docs versus code | R | Table: Claim, Document, What the code shows, Verdict | Claude samples the claims in README and docs (install steps, architecture statements, endpoint lists) and checks them | P1 |
| `change.upgrade-burden` | Upgrade burden | M | Table: Runtime or package, Pinned, Latest or supported, Gap | Lockfile versions against an end-of-life dataset. Needs a data source, see open decisions | P1 |
| `change.in-flight` | Work in flight | M | Table: Branch, Last commit, Ahead/behind, Author | Remote branches. Issue and PR content is out of reach and is listed as `unknown` | P0 |

### 11 Conventions
Question: *How do I write code that fits in here?*

| Card id | Title | Tier | Shape | Source | P |
|---|---|---|---|---|---|
| `conventions.style` | Code conventions | A | Table: Area, Convention, Evidence. Areas: naming, error handling, logging, dependency injection, async, validation, tests | Claude, with measured consistency from the extractors (for example 94% of handlers use the same pattern) | P0 |
| `conventions.recipes` | Recipes | R | Numbered recipes, each listing files to touch in order, with a worked example found in the repo. Fixed set where applicable: add an endpoint or command, add a field, add a migration, add a test, add a dependency, add a config setting | Claude, each recipe grounded in an existing commit that did the same thing | P0 |
| `conventions.tooling` | Formatting and tooling | M | Table: Tool, Config file, Enforced where | Formatter and linter configs, pre-commit hooks, CI steps. Listed, not graded | P0 |

### 12 Build, run and ship
Question: *How do I get it running and into production?*

| Card id | Title | Tier | Shape | Source | P |
|---|---|---|---|---|---|
| `ops.local` | Local setup | A | Ordered steps and a prerequisites table: runtimes and versions, services, data, secret names | README, Dockerfiles, compose files, `.tool-versions`, `global.json`, `.nvmrc`, `pyproject` | P0 |
| `ops.build` | Build and packaging | A | Table: Artifact, Command, Output | Build files and scripts | P0 |
| `ops.test` | Running tests | A | Table: Scope, Command, Notes | Test config and CI | P0 |
| `ops.run` | Running it | A | Table: Mode, Command, Needs | Entry points plus config | P0 |
| `ops.ci` | CI gates | A | Table: Pipeline, Trigger, Steps, Blocks merge?, Publishes | Workflow definitions. States what the gates do and do not guarantee | P0 |
| `ops.release` | Release, deploy and rollback | A | Table: Environment, How released, How rolled back, Versioning | Deploy workflows, IaC, release scripts. Anything outside the repo is `unknown` | P0 |
| `ops.config-secrets` | Configuration and secrets | A | Two tables: settings (Setting, Default, Overridden by) and secrets by name only (Secret, Unlocks, Supplied how). Never values | `facts:env_vars`, `facts:secret_signals`, config loaders | P0 |

### 13 Contributors
In the code today, the Contributors card, the contributor knowledge map and the commit calendar render inside report 02 (`panel_contributors`, attached to the overview in `render.py`). They stay in 02, together with the Dependencies card, unchanged apart from the Owner and Author buttons. Report 13 holds only the written interpretation, which currently has free-form headings. It moves to a fixed card set:

| Card id | Title | Tier | Shape | Source | P |
|---|---|---|---|---|---|
| `contributors.people` | Who the people are | A | Table: Person, Role in the project, Areas, Active? | `facts:contributors`, `facts:areas`, with Claude naming areas by what they do | P0 |
| `contributors.ask` | Who to ask | A | Table: Subsystem, Ask first, Then, Basis | Ownership and recent commits per component. Claude resolves differences between ownership and commit share | P0 |
| `contributors.concentration` | Knowledge concentration | A | Table: Area, Owner, Share, Status (single owner, departed, shared) | Measured shares plus Claude's reading of bulk imports and reformats. "Departed" and "at risk" remain `inferred` | P0 |
| `contributors.agents` | Agents and bots | A | Table: Identity, Kind, Areas touched, Share of commits | Identity classification from `facts:contributors` | P0 |
| `contributors.doubts` | Classification doubts | R | Table: Identity, Doubt, What would settle it | Claude. Shared accounts, unmerged identities, ambiguous bots | P0 |
| `contributors.workflow` | Team workflow | M | Table: Convention, Observed, Evidence. Rows: branch naming and strategy, merge style, commit message style, typical PR size, review rate, release cadence | git log, merge-commit patterns | P0 |

**Who owns a commit.** Every commit has an author (from git) and an owner. The rules apply in this order:

1. If the repository has exactly one human contributor, that human owns every commit, whoever authored it.
2. A commit authored by a human is owned by that human.
3. A commit authored by an AI agent or a bot and merged through a pull request is owned by the human who approved the pull request: the last approving reviewer, or, with no approval, the human who merged it.
4. Any other commit is owned by its author, even when that is an agent or a bot.

Pull request data comes from `gh` (6.2). When `gh` cannot supply it, rule 3 does not apply, rule 4 does, and Gaps says so. Rule 1 needs no `gh` call. Report 13's owners, shares and bus factor use owners, not authors. A surviving line belongs to the owner of the commit that last changed it. The bus factor counts humans only.

The old "Reading the knowledge map" text is dropped from this report. It explains a card that lives in 02, so it belongs in that card's help text.

### 14 Risks, 15 Gaps, 16 Corrections
Unchanged in content and look. Their cards are part of the schema and of 1.0.0. The three tracker cards are all titled "Tracker", but they are not the same kind of card:

- The **Risks** tracker is written by Claude, as one table with fixed columns (below). It is a finding about the code, part of the report schema like any other written card.
- The **Gaps** and **Corrections** trackers are dossier metadata, drawn by code (`computed` shape): Gaps lists the inferred and unknown statements still open, and Corrections lists the user's corrections and decisions that resolve them into confirmed statements.

The tiles above each tracker (risk counts, gap counts) are not cards; they stay as they are.

| Card id | Title | Tier | Content today | P |
|---|---|---|---|---|
| `risks.tracker` | Tracker | A | Table: ID, Risk, Category, Severity, Impact, Recommendation (one or more tables) | P0 |
| `gaps.tracker` | Tracker | A | Table of every open item (ID, Type, Report, Statement, Status, What would confirm it, Evidence) | P0 |
| `corrections.tracker` | Tracker | M | Recorded corrections, and contributor type overrides when there are any | P0 |
| `corrections.decisions` | Your confirmations and answers | M | Decisions you made about open items. Always present; when there are none it says so | P0 |

Two additions:
- Risks gain a `Source` column value `extractor` when the row comes from a measured finding (cycle, dead code, hotspot with a single owner).
- Gaps automatically receives: every unassigned file (V4), every undispositioned candidate (V5), every blind-spot hit (V7), every missing tool under `--allow-missing`, and every language run in Tier B. Because V5 is an error that stops `render`, undispositioned candidates only reach a rendered page under `render --allow-errors`.

### Retired from the old design
Capabilities (folded into `components.catalog`), Interfaces (split into 04 and 07), Architecture (05 and 06), Domain logic (`behavior.rules` and `reading.glossary`), Data (08), Code tour (03 and 04), Failures (`behavior.failures`, `io.outputs`), Delivery (12, `io.inputs`).

## 5. Pipeline changes

### 5.1 `prepare`

1. **Preflight.** Detect languages (gatherer already classifies them), compute the tools each needs, check they are present, and print the full list of anything missing with install commands. Stop unless `--allow-missing` is given. With the flag, continue; every missing tool becomes a coverage item in Gaps and the affected cards are badged "partial".
2. **Checkout.** `git clone --local --no-checkout <repo> ~/.local/cache/dossier/<repo>/checkout`, then `git checkout --detach <sha>`. Reused between builds and moved to the new SHA on incremental runs. `dossier clean` deletes it. The user's own working tree is never touched. Everything dossier needs while building but can regenerate (the checkout, the scratch `HOME`, package caches) lives in one per-repository working area, `~/.local/cache/dossier/<repo>/`, kept apart from the dossier output folder (`<home>/<repo>/`), which holds only what is worth keeping and sharing. The root is configurable with `cache_dir` in the dossier home config.
3. **Restore (Tier 2 only).** Install from lockfiles only: `npm ci --ignore-scripts`, `uv sync --frozen`, `dotnet restore --locked-mode`. These run on the host and can still execute the repository's own build code (source-package builds, MSBuild targets). Before the first restore of a repository, ask once, naming what will run. All restores follow the rules in 5.4. The answer is stored in `state.json` and applies to later builds of that repository. `--no-restore` always skips it. A failed restore falls back to Tier 1 for that language and is recorded in Gaps.
4. **Extract.** Run all extractors (section 6) into `extract/*.json`.
5. **Path filter.** Drop any extracted path not in `git ls-tree -r <sha>`. Verify `HEAD == sha` before and after extraction.
6. Existing steps (facts, chunks, update plan) continue as today. Git-history facts (blame, log, co-change) keep reading the original repository's objects.
7. **Run record.** Every stage appends to `build.json` as it runs: step, start and end time, tools and versions, counts, skipped-with-reason, reading mode, chunks, subagent count, reports rewritten versus reused. `render` turns it into the `dossier.process` card. Claude never edits this file.

### 5.2 New CLI

- `dossier doctor [repo]` runs the preflight alone and prints what is installed and missing.
- `dossier clean [repo]` removes cached checkouts.
- `build` and `prepare` gain `--allow-missing`, `--no-restore`, `--allow-ref` (build restores for a ref that is not a tag or a default-branch commit) and `--submodules`.

### 5.3 Incremental builds
Extractor outputs are keyed by `(sha, extractor version, tool versions)`, and output from a build where one of the adapter's tools failed or was skipped is never reused. A report is stale if a cited file changed, as today, or if the extractor findings it is built from changed. That comparison uses a digest of those findings without line numbers (finding ids, module and import names, test counts), so code that only moved does not make a report stale. M-tier cards are always recomputed. They are cheap, and they stay correct this way.

### 5.4 Restore hygiene

These rules reduce the damage a bad install or build script can do. They are not isolation: the code still runs on the host with your privileges. They apply to every restore and to every Node and .NET extractor, since those can load repository configuration as code.

1. **Scrubbed environment.** Child processes start from an empty environment plus an allowlist, never from a copy of yours:
   - `PATH` (system directories plus the directories of the tools dossier needs), `LANG`/`LC_ALL`, `TERM`.
   - `HOME` set to a scratch directory at `~/.local/cache/dossier/<repo>/home`, plus `TMPDIR`, `XDG_CACHE_HOME` and `XDG_CONFIG_HOME` inside it.
   - Proxy and certificate variables (`HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`, `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`, `NODE_EXTRA_CA_CERTS`).
   - Telemetry opt-outs (`DOTNET_CLI_TELEMETRY_OPTOUT`, `DOTNET_NOLOGO`).

   Everything else is absent, including `SSH_AUTH_SOCK`, `GIT_*`, cloud credentials and any token, secret or connection-string variable. `build.json` records the names (never the values) of the variables passed. One exception: `gh` alone runs with `GH_CONFIG_DIR` pointing at the user's `gh` configuration folder, so it can read its own login. No token is passed as a variable, and no repository code runs in that step.
2. **Private registry credentials are opt-in.** Restores from private feeds (npm, NuGet, a Python index) need credentials, and the scrubbed `HOME` hides your normal config. A `registry_auth` list in the dossier home config names the variables or config files to pass, per ecosystem. The default is empty. A restore that fails for authentication reports that reason in Gaps, with the setting to change.
3. **Private caches.** Package caches live under `~/.local/cache/dossier/<repo>/cache/` (`UV_CACHE_DIR`, `npm_config_cache`, `NUGET_PACKAGES`, `DOTNET_CLI_HOME`, `PIP_CACHE_DIR`) and are never shared with your global caches or with other repositories. `npm_config_userconfig` points at an empty file. `dossier clean` removes the whole working area for the repository.
4. **Trusted refs only, by default.** Restores and the Node and .NET extractors run without a flag only when the pinned ref is: a tag; the tip of the default branch (the branch `origin/HEAD` points to, else `main` or `master`); or a commit reachable from that branch. Any other ref (a feature branch, a pull-request ref, a fork) needs `--allow-ref`. Without it, those stages are skipped, the Python static extractors still run, and Gaps records the skip and the reason.
5. **Submodules are off by default.** They would pull in other repositories. `--submodules` turns them on and is recorded in `build.json`. When off and the repository has submodules, Gaps lists them as not analysed.
6. **Time limits.** Each stage has a wall-clock timeout (configurable). On expiry the whole process group is killed and the stage is recorded as failed in Gaps.
7. **Extractor tools are pinned.** Versions are fixed (6.2) and recorded, so a tool cannot change under you between builds.

## 6. Extraction

### 6.1 What each extractor produces

All extractors write normalized JSON that `render.py` and the prompts consume. One adapter class per language, in the style of `deps.py` (`ADAPTERS`), implements the outputs below. One more adapter, `repo`, handles files that belong to no language and runs for every repository: Dockerfiles, Makefiles, CI definitions, systemd units, shebang scripts and SQL files.

| Output file | Contents | Feeds |
|---|---|---|
| `entry_points.json` | Kind, name, location, trigger. Kinds: console scripts and package bins, `__main__` modules and guards, CLI commands, HTTP routes, queue consumers, scheduled jobs, container `CMD`/`ENTRYPOINT`, CI schedules, Makefile targets, shebang scripts, systemd units (and `Main`/`Program.cs` for C#). Entry-point recall (section 11) is measured over these kinds | 04 |
| `graph.json` | Nodes (modules, files), edges (import, call where SCIP gives it), cycles | 05, 06, 10 |
| `symbols.json` | Definitions and references (SCIP), public surface per module. For Python a name is public when no part of it starts with `_` and it is top-level or a class member; `__all__` is not used | 05, 07, 10 |
| `io_candidates.json` | Category, location, snippet, rule id | 07, 06 |
| `models.json` | Entities, fields, relations, migrations | 08 |
| `tests.json` | Test files, counts, skip markers, mock use, fixtures, config | 09 |
| `dead.json` | Unused files, exports, dependencies, functions | 10 |
| `blindspots.json` | Hits for the language's dynamic patterns | 15 |

Git-derived outputs (`hotspots`, `cochange`, `workflow`, `branches`) are computed in `gather.py`.

**Home cards.** Every candidate (principle 2) has exactly one home card, where `dossier candidates` lists it and where its disposition is expected. Other cards that cover the same thing hold one summary row that points to the home card (principle 5); a disposition recorded there also counts.

| Candidates | Home card |
|---|---|
| Entry points, including HTTP routes, scheduled jobs and queue consumers | `entry.catalog` |
| Environment variables, CLI arguments, config files, files read, stdin, messages consumed | `io.inputs` |
| stdout and stderr, files written, outbound calls, messages produced, exit codes, error responses | `io.outputs` |
| Logs, metrics, tracing | `behavior.observability` |
| Retries, timeouts, catch-all handlers, transactions | `behavior.failures` |
| Database connections | `data.stores` |
| Database reads and writes, global and module-level mutable state, caches | `interactions.state` |
| Threads, async, process pools, locks, queues | `interactions.concurrency` |
| Data entities | `data.entities` |

### 6.2 Tools

All tools run at pinned versions, recorded in 01 This dossier. Python tools run through `uv` with a pinned interpreter, as declared inline in the script (the way `check_page.py` already does). Names and invocations below are from memory and must be verified when implementing.

| Scope | Tool | Gives | How installed |
|---|---|---|---|
| All | tree-sitter (`tree-sitter-language-pack`) | Symbols, structure, complexity proxy, rule queries | `uv` |
| All | semgrep, with rules bundled under `rules/` | Routes, I/O sites, DI registration (where the language has a common container: C# and TS; Python has none), retries, timeouts. Feature flags are a blind-spot pattern (6.4), not an I/O category | `uv` |
| All | git | History, blame, co-change | preflight check |
| All | `gh` (optional) | Who approved a merged pull request (4, "Who owns a commit"), for GitHub repositories with more than one human contributor. Reads only; never required | preflight lists it as optional |
| Python | grimp | Import graph, cycles | `uv` |
| Python | vulture | Dead code | `uv` |
| Python | import-linter config (read only) | Declared layer rules. import-linter itself is never run: dossier evaluates `layers` and `forbidden` contracts with grimp and lists every other contract type as "not checked" | parsed from repo config |
| Python | scip-python | References and call data | Installed once from a lockfile shipped with the skill (`npm ci --ignore-scripts`) into the shared tool cache, then run with Node; bare `npx` would leave its dependencies unpinned (5.4 rule 7). Needs Node. Installed packages are passed in an environment file written from the restored `.venv`, because uv environments have no `pip` for scip-python to ask |
| JS/TS | dependency-cruiser | Import graph, cycles, rule violations | `npx`, needs Node |
| JS/TS | knip | Unused files, exports, dependencies | `npx`, needs Node |
| JS/TS | scip-typescript | References and call data | `npx`, needs Node |
| JS/TS | shipped script on the TypeScript compiler API | Types, exports, React component tree, router config | Node |
| C# | scip-dotnet (Roslyn-based) | References and call data | `dotnet tool`, needs .NET SDK |
| C# | `dotnet list package --include-transitive` | Packages (`deps.py` already adapts this) | .NET SDK |
| C# | tree-sitter plus semgrep | Controllers, minimal APIs, DI registrations, EF models and migrations | `uv` |

Preflight therefore expects on the host: `git` and `uv` always; Node and npm for any Python, JS or TS repo (scip-python and the JS tools run on Node); the .NET SDK for any C# repo. Everything else installs itself. `gh` is optional: without it, or without a login, the build carries on and Gaps says commits by agents count for their authors.

### 6.3 Language tiers

- **Tier A (Python, TS/JS/React, C#):** all extractors. A card is full unless it is badged "partial"; there is no separate "full" badge.
- **Tier B (everything else, including C, Rust, Zig, shell, HTML/CSS):** tree-sitter symbols and structure, `deps.py` where an adapter exists, git facts, and Claude reading. No call or import graph unless tree-sitter can produce one. The affected reports are badged "no static graph" and Gaps lists the language.

### 6.4 Blind spots (V7)

Each adapter ships a list of patterns that static edges miss and a rule that finds them. The hit count and locations go to Gaps. Starting set:

- **Python:** `importlib`, `__import__`, string-based plugin or entry-point loading, decorator-registered handlers, `getattr` dispatch, Django `INSTALLED_APPS` and signals, pytest fixtures resolved by name.
- **TS/JS:** dynamic `import()`, `require` with variables, barrel-file re-exports, React context and hooks wiring, string-based routes, module federation.
- **C#:** DI container registrations and resolution, reflection, attribute-based routing and filters, `MediatR`-style handlers, source generators, `partial` classes.
- **All:** codegen output, runtime config selecting implementations, feature flags. "Runtime config selecting implementations" has no rule (no pattern finds it without many false matches); every build lists it in Gaps once as a fixed coverage item instead.

## 7. Verification (run by `render`)

| Id | Check | Failure |
|---|---|---|
| V1 | Every citation resolves | error (exists today) |
| V2 | Identifiers named in backticks in a cited statement appear in the cited range | warning, counted in Gaps |
| V3 | Every arrow in a flow diagram corresponds to a graph or call edge | warning; Mermaid cannot style one arrow, so each unbacked arrow is listed under its diagram as inferred and added to Gaps as an `inference` item |
| V4 | Every tracked non-excluded source file has exactly one component (the most specific matching path wins, see 05), and every component in the catalog has an entry in `components.detail` | error if unaccounted or tied between two components; unassigned list is allowed |
| V5 | Every extractor candidate has a disposition | error |
| V6 | Report matches the card schema: ids, order, titles, columns, required cards | error |
| V7 | Blind-spot hits are recorded in Gaps | automatic |
| V8 | `summary.json` validates against its schema | error |
| V9 | Extractor path filter removed nothing unexpected (counts logged) | info |
| V10 | `build.json` has a record for every step in the fixed process list, or an explicit skip reason | error |

An optional **verifier pass** samples N claims per report. A separate agent gets only the claim and the cited code, not the report's conclusion, and returns supported / not supported / cannot tell. Disagreements are written to Gaps. This is off by default and runs with `--verify`.

## 8. Card schema

`reports/<id>.json` becomes:

```json
{
  "headline": "...", "summary": ["...", "..."],
  "cards": [
    {"card": "entry.catalog", "blocks": [ ...table block with the fixed columns... ]},
    {"card": "entry.startup", "na": "No startup sequence: the project is a library", "cite": ["pyproject.toml:1-30"]},
    {"card": "components.detail", "entries": [{"component": "gatherer", "fields": {"purpose": "...", "how_it_works": "..."}}]}
  ]
}
```

`prompts/schema/<report>.json` (new, shipped with the skill) holds, per card: id, fixed title, tier, shape, required columns or entry fields, and priority. It sets no limits on the number of rows or entries. `render.py` reads it and draws the title, the tier badge and the question line. Writers supply content only. The old free-form `heading` is ignored for schema cards.

## 9. `summary.json` for `portfolio`

Written to `<home>/<repo>/summary.json` on every build. It is a public interface of the skill: `schema_version` is bumped on any breaking change, and changes are noted in the changelog.

```
schema_version, dossier_version, generated_at
repo: { name, remote, branch, sha, commit_date }
languages: [{ name, tier, share }]
extractors: [{ name, version, status: ok|partial|missing }]
components: [{ id, name, paths, depends_on: [id], used_by: [id], size, owners: [contributor ids] }]
entry_points: [{ kind, name, location }]
contributors: [{ id, kind: human|agent|bot, name, username }]
contracts: [{ name, direction: offered|consumed, counterparty, schema_path }]
external_dependencies: [{ name, ecosystem, scope: runtime|dev, files_importing }]
data_stores: [{ name, technology }]
risks: { critical, high, medium, low, info }
ownership: { top_owner_share, bus_factor, at_risk_paths: [path] }
change: { hotspots: [{ path, churn }], cochange_pairs_unlinked: n }
gaps: { unknown, inference, assumption, coverage }
```

`contributors` lists everyone in the history, plus any human who only approved pull requests. `id` is an opaque stable value that is the same in every repository for the same person, and `owners` holds these ids. `username` is the GitHub login when it is known, else null. No email address appears in this file. `owners` are the identities that own at least 20% of the component's lines. `top_owner_share` and `bus_factor` count humans only: the share is the largest human share of human-owned lines, and the bus factor is the smallest number of humans holding more than half of those lines. `at_risk_paths` are the paths of components whose status is `departed`.

It is assembled from structures the reports already hold. `contracts` is the field that lets `portfolio` link repositories: it joins `offered` in one repo to `consumed` in another by counterparty and schema path.

## 10. Milestones

Build the pipeline end to end for one language first, so the schema and verification get exercised early.

| M | Content | Exit criterion |
|---|---|---|
| M0 | Card schema files, schema validation (V6), `render.py` draws fixed titles, tier badges and question lines, and the `dossier.questions` card (static data, so it is real in M0). Map the existing content onto the new skeleton. Report 02 and its Contributors, knowledge map, calendar and Dependencies cards are left untouched | Existing encamp dossier re-renders with the new skeleton and passes V6, and report 02 is identical in content to before (byte-identical once the schema's card ids and tier badges are removed) |
| M1 | Checkout, preflight, `doctor`, `clean`, path filter, `build.json` run record, the `dossier.process` card in report 01 rendered from it, V9 and V10, restore hygiene (5.4), adapter interface, shared tree-sitter and semgrep layer | `doctor` lists missing tools correctly; a Python repo gets a verified checkout; the process card renders from a real build and V10 passes; the hygiene tests in section 11 pass |
| M2 | Python vertical slice: grimp, vulture, scip-python, Python rules and the Python blind-spot list, the repository-wide adapter; reports 03 to 09, 11, 12; V2 to V5 and V7 (Python). Reports 10 and 13 are not written: their absence is a warning, not an error | A Python repo builds all reports from extractors; candidates reconcile |
| M3 | Report 10 (git-derived cards, blast radius), report 13 (all six cards: people, ask, concentration, agents, doubts, workflow), the report 14 and 15 additions, `summary.json` and V8. Reports 10 and 13 become required again | Golden-set run on the Python repo meets section 11 |
| M4 | TS/JS/React adapter, rules and blind-spot list (V7 for TS/JS) | Same checks on the golden TS repo |
| M5 | C# adapter, rules and blind-spot list (V7 for C#). Starts by verifying scip-dotnet (decision 2) | Same checks on the golden C# repo |
| M6 | Tier B fallback badges, review of the blind-spot lists across all languages, the interactive collapsible graphs for `components.map` and `interactions.graph`, `--verify`, docs, README rewrite (including the stale description of where the Contributors cards live), version bump | Definition of done below |

Cut line: if time runs short, drop P1 cards first, then Tier B polish. Do not drop V2 to V5, since they are what make the answers trustworthy.

## 11. Definition of done for 1.0.0

1. All P0 cards in section 4 exist, validate against the schema, and render with the correct tier badge.
2. Three of your own solo-built apps (one Python, one TS/React, one C#) build without manual intervention, and their reports have **identical card skeletons**, checked mechanically.
3. Measured against your own knowledge of those apps (you are the ground truth):
   - entry points: recall 100%, precision at least 95%, over the entry-point kinds listed in 6.1 (for a library, its public functions are not entry points);
   - inputs and outputs: recall at least 95%;
   - components: you agree with the component map after at most minor renaming;
   - zero fabricated citations (V1 and V2 failures);
   - every item you find wrong or missing in the dossier is explained either by a Gaps entry or by a blind-spot rule that is now added.
4. `doctor`, `--allow-missing`, `--no-restore`, `--allow-ref`, `--submodules` and `clean` work as specified, and a build with a tool removed produces the correct Gaps entries.
   Restore hygiene is tested with a fixture repository whose install script writes out its environment and working locations: only allowlisted variable names appear, `HOME` is the scratch directory, caches land under `~/.local/cache/dossier/<repo>/cache/`, a feature-branch ref is refused without `--allow-ref`, and a timed-out stage is killed and recorded.
5. The card skeleton of a small repository and of your largest one are identical. Only content volume differs.
5. `summary.json` validates and contains no field the reports do not already hold (`contributors.id` and `contributors.username` are identifiers, and are the one exception).
6. Unit and integration tests cover the schema validator, the path filter, the candidate reconciliation, and each adapter's fixtures. `check_page.py` reports `"problems": 0` on all three dossiers.
7. README, SKILL.md and the prompts describe the new design. No reference remains to the retired reports. `VERSION` is `1.0.0`.

## 12. Decisions

Settled:

1. **Report 13 Contributors** stays, restructured to the fixed card set above. The Contributors, knowledge map, calendar and Dependencies cards stay in report 02, as they render today.
2. **C# analysis** uses scip-dotnet, tree-sitter and semgrep. A custom Roslyn tool is deferred. Revisit at the start of M5 if scip-dotnet proves immature, or after the C# golden run if it misses dependency-injection wiring. Claude Code will be the main aid for the C# codebases, so the dossier's C# reports must be explicit about what static analysis could not see.
3. **scip-python is kept.** Node and npm are host prerequisites for Python, JS and TS repos.
4. **`change.upgrade-burden`** covers runtimes and major frameworks only, from a shipped end-of-life snapshot with an optional live refresh, and shows "data as of <date>". It stays P1.
5. **Restores** ask once per repository, remembered in `state.json`. **No isolation is required:** restores and tools that load repository configuration run on the host with the user's privileges. This is a recorded, accepted risk, reduced by lockfile-only installs, `--ignore-scripts` where the tool supports it, and the restore hygiene rules in 5.4 (scrubbed environment, private caches, trusted refs only, submodules off, time limits). Containers and other sandboxes were considered and dropped.
6. **No caps.** Card counts are fixed by the schema and never depend on repository size (principle 7).

Still to do in M1:

7. Pin the versions of every tool in 6.2, and verify the names, flags and behaviour against current documentation.

Settled in the M2 plan review (2026-11-01; the numbers are the spec issues in `plans/007-m2-plan.md`, section 8):

8. **Interactive graphs** for `components.map` and `interactions.graph` move to M6. Until then both cards show a component diagram and a full edge table (issue 1).
9. **V3 marking:** an unbacked arrow is listed under its diagram as inferred and added to Gaps (issue 2).
10. **V4 nesting:** the most specific matching path wins; only a tie between two components is an error (issue 3).
11. **DI and feature flags:** no DI rule for Python; feature flags are a blind-spot pattern (issue 6).
12. **Repository-wide adapter** `repo` for files that belong to no language (issue 7).
13. **`components.map`** keeps its M+A badge although Claude's part arrives only through `components.catalog` (issue 8).
14. **Runtime config selecting implementations** has no rule and is one fixed Gaps item per build (issue 9).
15. **scip-python** is installed from a shipped lockfile and given an environment file written from `.venv` (issue 10).
16. **Staleness** compares line-free digests of the findings each report is built from (issue 11).
17. **Reports 10 and 13** are optional in M2 and required again in M3 (issue 12).
18. **Undispositioned candidates in Gaps** appear only under `render --allow-errors`, since V5 is an error (issue 13).
19. **`behavior.tests`** stays tier A with Claude copying the measured values; no schema change (issue 14).
20. **import-linter** contracts of type `layers` and `forbidden` are evaluated with grimp; other types are listed as not checked (issue 15).
21. **Public surface** for Python: no part of the name starts with `_`, and it is top-level or a class member (issue 16).
22. **No "full" badge:** a card without "partial" is full (issue 17).
23. **Entry-point recall** is measured over the kinds listed in 6.1 (issue 18).

24. **Candidate lists** (principle 2): dispositions are required for entry points, input/output and related sites, and data entities only; measured outputs and computed suggestions are exempt (issue 4).
25. **Home cards:** each kind of candidate has one home card (6.1); a disposition anywhere counts, and kept-and-dismissed is an error (issue 5).

Settled in the M3 plan review (2026-11-05):

26. **Who owns a commit** follows the four rules under report 13. A human answers for what an agent does when they approved it, or when they are the only human on the project.
27. **Owner and Author buttons** are added to the Contributors card in report 02, the one approved change to that card's look. Author stays the opening view.
28. **`contributors`** is added to `summary.json`, with no email addresses (section 9).
29. **`gh`** is an optional host tool. It reads pull request approvals only, and is the one tool given access to a login (5.4 rule 1).
30. **`at_risk_paths`** means components whose status is `departed`.
31. **Decision markers** are a fourth candidate list (principle 2); group ids may decide them.
32. **Co-change** lists pairs with at least 3 co-commits. Fewer is chance, not coupling, so this is a definition rather than a cap (principle 7), and the card prints both counts.
