# Report specifications

Write one file per report to `reports/<id>.json`, following `method.md`. Every report needs `headline`, `summary` and `blocks`. Aim for the smallest report that fully serves a lead engineer. A short report is fine when the topic is small.

**Executive summaries are short and plain.** Write `summary` as 3 to 5 bullets (`- ` lines), each one sentence of about 20 words or fewer, in everyday words. Lead with the answer. No filler, no restating the headline, no jargon the reader has to look up.

The page also shows measured tables from `facts.json` (languages, most changed files, manifests, file inventory, environment variables, secret scan, contributor and area tables). Do not repeat those tables. Refer to them with `[[facts:...]]` and add what only reading the code can tell.

## overview

The one-page answer to "what is this?". Summary: what the project is, who it serves, how big and mature it looks, and the three things to know first. Blocks: a list "What to know first"; a table "Technology" (language, frameworks, datastores, build, test, deploy); optional text on maturity and health. Optional `update_note`.

## capabilities

What the application can do, in user terms. One table: Capability, What it does. Group related items. Separate what is implemented from what is only stubbed, planned or dead code, and say which. Features seen only in docs, not code, are `inferred` or `unknown`.

## interfaces

Where the system meets the world: everything it offers, calls, takes in and sends out. Cover: interfaces it offers (HTTP routes, CLI commands, library exports, events, scheduled jobs, webhooks); interfaces it calls (external APIs, databases, queues, file systems); inputs (formats, validation, authentication) and outputs (responses, files, messages, logs, metrics). One table per direction, with columns such as Interface, Protocol or format, Inputs, Outputs, Authentication. Add a context diagram if there is more than one external party. Note where authentication and authorization are enforced and where they are not.

## architecture

How the system is built, in enough depth that an engineer could find where any change belongs. This is the longest report. Include everything below that applies. When something does not apply (for example a library has no deployed services), say so as `confirmed` with the evidence, rather than leaving it out.

Required diagrams (Mermaid flowcharts in C4 style, see `method.md`):

1. **Level 1, system context.** The system as one box, the people and roles who use it, and every external system it talks to. Label an arrow with what flows only when it is not obvious.
2. **Level 2, containers.** Each separately runnable or deployable part (services, web apps, workers, databases, queues, caches, CLIs, scheduled jobs). Label technology and responsibility on each box, and protocol and purpose on each arrow.
3. **Level 3, components.** One diagram for each important container (up to about four), showing its modules or components and how they depend on each other.
4. **Dynamic or deployment view, if the code shows one.** For example how containers are deployed across environments, or how a key collaboration plays out step by step.

Required tables:

- **Containers:** Name, Kind, Technology, Responsibility, Runs as.
- **Modules and components:** Name, Responsibility, Key public entry points, Depends on, Used by, Approximate size. Cover every top-level module, and go deeper for the important ones.
- **External dependencies and integrations:** Name, Kind (database, API, queue, cloud service, SaaS, library with a runtime role), Purpose, Direction, Protocol, Authentication, What happens if it is down. Include databases, caches, message brokers, third-party APIs, identity providers, cloud services and file stores. List only major libraries and frameworks separately as "Key libraries" with their role.
- **Cross-cutting concerns:** how the system handles configuration, authentication and authorization, logging and tracing, error handling, caching, concurrency, feature flags and internationalization, each with where it lives.

Also write short text on: the main design patterns and decisions you can see (each with evidence), the layering or dependency rules and any violations or cycles (these become risks), and the quality attributes the design favours (for example simplicity, throughput, extensibility). Records of decisions in the repository (ADRs, design docs) should be cited and summarised.
## data

What data the system holds and moves.

- An `erDiagram` of the main entities from schema, migrations, models or types, with key fields and relationships including cardinality. Split into several diagrams if there are more than about twelve entities, grouped by area.
- **Data flow diagrams.** Draw one diagram per major flow (for example: user input to storage, read path, background processing, authentication). Keep each to about 6 to 10 nodes: the source, the main processing steps by module or function name, any data store, and the destination. Add one failure or rejection branch where the code has one. Label an arrow only when what moves is not obvious. Put the detail (fields, formats, sensitive data, trust boundaries) in a table beside the diagram, one row per step, rather than in the boxes.
- A table of entities: Name, Purpose, Key fields, Owner module, Sensitivity.
- A table of data stores: Store, Technology, What it holds, Retention or lifecycle, Backup or migration approach.
- Text on how data is validated, transformed, migrated and deleted, and which data looks sensitive, with evidence.

If there is no persistent data, say so and describe the in-memory or message shapes instead, still with a detailed flow diagram of how values move through the code.
## code-tour

How to read the code. Required: a numbered reading order (which module first and why; name each file with its filename and extension, such as `app.py`, and put its citations at the end of the line, not in the middle), a table of entry points, and one sequence or flow diagram per main execution path (for example a request, a job run, a CLI command), each listing the modules it passes through in order. Put the notes for a path in a text block headed "Notes on path N" directly after that path's diagram; the page folds it into the diagram's card. Include where to find configuration, tests and the build. Pick paths that teach the most, usually three or fewer. Point out the hardest-to-read or most-changed areas.


## failures

How the system fails and what it says when it does. This report owns every failure output: error responses, exceptions, error codes, exit codes and failure messages. Cover:

- **Error handling strategy:** where errors are caught, wrapped, logged and reported, and whether the code fails fast or tries to continue.
- **Error catalog:** one table of every error type, exception class, error code, HTTP status or exit code that the code defines or returns. Columns: `Code or type`, `Meaning`, `Seen by` (caller, user, operator), `Handling`. Include messages shown to users when they are fixed text. If there are many, group them and cover them all.
- **Failure modes:** one table of ways the system can fail. Columns: `ID` (F1, F2), `Failure`, `Trigger`, `Detection` (how anyone finds out), `Effect`, `Recovery`. Include dependency outages, bad input, timeouts, resource exhaustion, partial writes, concurrency conflicts, misconfiguration, expired credentials or certificates, and data corruption, where the code gives evidence.
- **Resilience mechanisms:** retries, backoff, timeouts, circuit breakers, idempotency, transactions, queues with dead-letter handling, health checks, graceful shutdown.
- **Observability of failure:** logging, metrics, alerts, tracing, error reporting services, and what an operator would see.
- A diagram (flowchart or state diagram) of the most important failure and recovery path, if there is one.

Things the code does not handle, such as no timeout on an outbound call, belong here as `inferred` or `confirmed` rows and also in `risks`.
## delivery

How the application is built, packaged, released, deployed and configured, and how secrets are handled. Cover: build tooling; packaging (container image, package, binary, static bundle); CI and CD steps; environments and how config differs between them; infrastructure as code; how secrets are supplied, stored and rotated (never print a secret value); what the secret scan in `facts.json` found and whether each hit is real, a test fixture, or a false match. Anything you cannot see (for example cloud settings outside the repo) is `unknown`.

## risks

A register of everything risky or doubtful. Use one or more tables with exactly these columns: `ID`, `Risk`, `Category`, `Severity`, `Impact`, `Recommendation`. IDs are R1, R2, and so on. Severity is Critical, High, Medium, Low or Info. Categories include security, reliability, data, performance, maintainability, testing, dependencies, delivery, knowledge concentration, compliance.

Rules: every row has citations. A row based on inference is `inferred` with a note, and still goes in the register. Order by severity. Include risks from the scan in `facts.json` (secrets, unpinned or abandoned dependencies, no tests for important areas, single-person areas from `facts:areas`, very large or very hot files). Do not pad with generic advice. Summary: the top three risks in plain words and the overall picture.

## contributors

Who knows what. The page already shows contributor and area tables. Write interpretation: who the key people are by area, where knowledge is concentrated or has left (people with no recent commits), how much work comes from agents and bots and in which areas, and who to ask about which subsystem. Name areas by what they do, not just by directory. Discuss classification doubts (a person who looks like a bot, shared accounts, unmerged identities). Use `facts:contributors` and `facts:areas` as citations. If the user has given overrides, they appear in `state.json`.

## gaps

Items not already listed by the page. The page already collects every `inferred` and `unknown` statement from all reports automatically. This report adds the rest in `items`:

```json
{"items": [{"kind": "assumption|unknown|inference|coverage", "statement": "...", "how_to_confirm": "...", "report": "overview", "cite": []}]}
```

- `coverage`: what you did not read or only sampled, and why. Always disclose excluded files (see `facts.files.excluded`), large files read only in part, and chunks you could not finish.
- `assumption`: something you took as true to proceed (for example that the default branch is the released state).
- `unknown` or `inference`: only for items that did not fit in another report's rows.

The `summary` should say how complete the dossier is and which gaps matter most. `blocks` may be empty.

## corrections

Not written by you. It is built from `state.json`. When the user corrects you, record it with the CLI (see SKILL.md), update the affected reports, then mark the correction applied.
