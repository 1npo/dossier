# Plan 005: milestone M0 (card schema, V6, fixed titles, tier badges, question lines)

Status: reviewed, ready for implementation. Written from `plans/004-v1-spec.md`, `docs/process.md` and the code at commit `88c3d7f`. Nothing in the repository was changed to write this plan.

Note on authorship: this plan was written by Sonnet in error (it was meant to be written by Opus; an earlier version of this line wrongly said "Written by Opus"). Opus then reviewed it against the code and the encamp dossier and corrected it (2026-11-01); the corrections are listed under "Review by Opus" below.

Paths used below (the planning prompt gave `~/encamp/...`, which does not exist on this machine):

- `SKILL` = `/home/nick/dev/projects/encamp/configs/user/claude/.claude/skills/dossier`
- `FIX` = `SKILL/tests/fixtures/encamp-m0`: a frozen copy of the encamp dossier as it was on 2026-10-31 (HTML `dossier-encamp.html`, 8.4 MB; `reports/` holds 12 old-layout files; `state.json` at skill version 0.4.0). It is the M0 test fixture. Its files are read-only (its folders are not, so `rm -rf` removes it in one step). It is listed in `SKILL/.gitignore` and never committed; delete the folder once M2 no longer needs it. The live dossier in `/home/nick/dev/dossiers/encamp/` is going to be deleted (all old dossiers are rebuilt from scratch after 1.0.0), so **no command in this plan reads `/home/nick/dev/dossiers/`**. The repository it describes is `/home/nick/dev/projects/encamp`, pinned at `fc916d65b28e8891dcf01610e2b16d482bd114d0`.
- Run the tests from `SKILL`: `uv run --with pytest --with pygments python -m pytest tests -q`. Baseline before M0: 168 passed.

How to use this plan (for the implementing session): do the tasks in order, one commit per task (follow the `git-commit` and `git-workflow` skills), tick the box when the done-check passes. If the code contradicts the plan, stop and report; do not improvise. Never write into `FIX` or `/home/nick/dev/dossiers/`: every command below that renders or migrates works on a scratch copy of `FIX`.

---

## Human answers (recorded after review)

- Q1 yes: dropped content is accepted; all milestones are built before `dossier` is used again, so nothing needs to work in between. Consequence: the SKILL.md interim notice (M0-12) stays but is minimal.
- Q2 yes: overview's written blocks leave 02; Technology goes to `reading.technologies`. The aim is to trim the old dossier.
- Q3: Risks, Gaps and Corrections have no executive summary or contents (code stays as is).
- Q4: cards not called out in the spec are dropped. So the Environment variables and Secret scan panels are **removed**, not moved (task changes below).
- Q5 yes: version 0.5.0. No dossier is migrated for real: every old dossier (encamp included) is deleted and rebuilt from scratch. `migrate` exists only to produce the M0 exit-criterion page from the `FIX` fixture. Therefore carrying saved decisions across the move (old M0-8), verification block E, and the user-facing `/dossier migrate` docs are **dropped** (answered 2026-11-01).
- Q8 yes: everything between "This repository" and "Risks" is replaced as the spec says.
- Q6 and Q7: the plan's defaults are accepted (to be reviewed later). One change: no card is free-form, so `behavior.tests` gets fixed tables (below). Navigation groups as proposed. ~~Reports 01, 02, 14, 15 and 16 get no question line.~~ Changed 2026-11-01: those five reports get badges and the tier key, like every other report. All five also get a question line (the texts marked † in M0-3, accepted by the human). Gaps (15) and Corrections (16) are dossier metadata (the open inferred and unknown statements, and the user's corrections and decisions that resolve them); they keep a question line because Gaps answers questions 10.1 and 10.2. Risks is moved out of the "Tracking" navigation group, which now holds only that metadata (item 1).
- **Second change (scope):** the existing cards of reports 01, 02, 14, 15 and 16 are added to the schema as they are (content unchanged; they are treated like every other card: fixed id and title, tier badge, tier shade; the three trackers are all titled "Tracker") and are part of 1.0.0. The schema now has 65 cards in 16 files. The existing three panels of report 01, the three of report 02, the Risks table, the Gap tracker and the two Corrections cards are `dossier.about`, `dossier.reports`, `dossier.changelog`, `overview.repository`, `overview.contributors`, `overview.dependencies`, `risks.tracker`, `gaps.tracker`, `corrections.tracker`, `corrections.decisions`. Consequences are folded into the tasks below; the report 02 check becomes a *normalized* digest.

## Review by Opus (2026-11-01)

Checked against the code and the fixture: the report 02 baseline digest reproduces exactly on a fresh render; report 02's six code-viewer links all point at the gatherer's own source with fixed ranges, so removing other reports' citations cannot change 02; every rule in Appendix B matches a real encamp block whose old columns exist (19 blocks plus 3 notes blocks = 22); the card counts (65 / 42 / 23) add up. Corrections made to this plan:

1. Blocks A and B could print `OK` when nothing was rendered: from M0-6, V6 rejects the old-layout `data`, `contributors` and `risks` files, `render` exits before writing, `| tail` hid the exit code, and the digest ran on the copied old page. Both blocks now delete the page first, check the exit code, and block A uses `--allow-errors`.
2. `schema.load_all()` skips `questions.json` (it is the question list for the `dossier.questions` card, not a report schema). The `dossier.questions` card itself stays in `prompts/schema/dossier.json`.
3. M0-3 writes nine schema files, not five.
4. The 16-report order is `schema.REPORT_ORDER` (in `scripts/schema.py`), not a constant in a test file, so `render.py` can use it.
5. Old M0-8 (`relink`) and block E are removed; see Q5.
6. Component detail entries are searchable (M0-5 changes `dossier.js`; `check_page.py` tests it).
7. The migration map no longer copies the component name into the `Paths` column.
8. The env-var and secret-scan panels are recorded in `docs/post-v1.md` as candidates to re-add after 1.0.0.
9. The questions table links to existing panels by their old anchors (`PANEL_ANCHORS`, M0-10 step 4); before, its links to those cards pointed nowhere.
10. Second round, after the human's answers: the fixture moved into the skill (`tests/fixtures/encamp-m0/`, git-ignored). Reports 01, 02, 14, 15 and 16 get badges, the tier key and a question line. Risks moves out of the "Tracking" navigation group into "Operations and people", because its tracker is written by Claude and belongs to the report schema, while Gaps and Corrections are dossier metadata (spec §4 reworded to say so; spec issue 17 resolved). D4, D6, M0-1, M0-3 and M0-10 changed, and the report 02 check now also removes the question line. All three trackers are informational, which now means "not required to answer a question" rather than "answers none". Section 6's questions are marked answered (D-Q1 corrected to 88 blocks). Steps, rules, table rows and spec issues were renumbered in place.

## 1. Summary

- Adds the card schema: one `prompts/schema/<report>.json` file per report (65 cards in 16 files, fixed ids, titles, tiers, shapes, columns), loaded and checked by a new `scripts/schema.py` (check V6, an error).
- `render.py` draws every schema card from the schema (fixed title, tier badge M/A/R, question line under the report title) and shows a "Not yet generated" placeholder where a card has no content, and the "not applicable, with evidence" form.
- The report list becomes the spec's 16 reports. A one-off `dossier.py migrate` command maps the old 12-report content of the encamp fixture onto the new cards (15 of 42 written cards get content, including the Risks table; the rest are placeholders), so the exit criterion can be checked on real content.
- Report 02's content and look are unchanged. A scripted digest of its HTML section (SHA-256 `fe72cec4…`, proven reproducible on today's code), taken after removing the new card ids and tier badges, must be identical after M0.
- `VERSION` goes to 0.5.0. Old dossiers are deleted and rebuilt after 1.0.0, so nothing else is done for them.

---

## 2. Spec versus code

"Absorb" = the plan handles it with the stated proposal. "Decision" = the human must answer first (see section 6; each has a default the plan uses if the answer is "go ahead").

| # | Where | Spec says | Code does | Proposal | Class |
|---|---|---|---|---|---|
| 1 | Report list and order | 16 reports, numbered 01 to 16 (§4). Ids are never named; cards are `reading.*`, `entry.*`, … | `render.REPORTS` has 14 reports (dossier, overview, capabilities, interfaces, architecture, domain-logic, data, code-tour, failures, delivery, contributors, risks, gaps, corrections). `NAV_GROUPS` has 4 groups. Numbers on the page come from list position. | New ids = card prefixes: `reading, entry, components, interactions, io, data, behavior, change, conventions, ops, contributors`. List order = spec order. Risks, Gaps, Corrections become 14, 15, 16 automatically. Navigation groups: Orientation (dossier, overview, reading, entry), Design (components, interactions, io, data), Behaviour and change (behavior, change, conventions), Operations and people (ops, contributors, risks), Tracking (gaps, corrections). Risks sits with 12 and 13 (so the sidebar numbers stay in order) because its tracker is a finding written by Claude; "Tracking" holds only the dossier metadata (changed 2026-11-01). | Absorb |
| 2 | Ids reused with new meaning | `data` and `contributors` exist in both designs | `reports/data.json` and `reports/contributors.json` hold old-layout content | A report file is new-layout only if it has a `cards` list. A file with `blocks` and no `cards` for a schema report is a V6 error that says "run `dossier.py migrate`". | Absorb |
| 3 | Retired reports | Capabilities, Interfaces, Architecture, Domain logic, Code tour, Failures, Delivery retire | These ids appear in `REPORTS`, `OPTIONAL_REPORTS` (`domain-logic`), `PANELS_AFTER` (`delivery`), `state.json` (`tracked[].report`, `corrections[].report`) and `gaps.json` items | Remove from code. `migrate` copies the old report files to `reports.legacy-v<version>/` and removes them from `reports/`. Ids of retired reports left in `state.json` are inert (item 12). | Absorb |
| 4 | Overview's written blocks | "Report 02 keeps every card it renders today" | `overview.json` has 3 blocks (What to know first, Technology, Maturity and health). `build_page` does **not** draw them on 02: it draws them at the top of Capabilities (`moved`). | Stop drawing them. `Technology` maps to `reading.technologies`. The other two have no card and are kept only in the backup. `claims_of` ignores overview blocks, so nothing is counted that is not shown. `overview.json` is not edited. | **Decision** (D-Q2, answered) |
| 5 | Standard cards | §4: every report except Gaps and Corrections has Executive summary, Contents, References | `BARE_REPORTS = (risks, gaps, corrections)` (plan 001 removed them from Risks; `docs/scratch/000-fixed-cards.md` still lists only Gaps and Corrections) | Keep the code (Risks stays bare). | **Decision** (D-Q3, answered) |
| 6 | Shades versus badges | Two shades stay; M cards use the facts shade, A and R the model shade; three badges (§2.3) | `SHADE_KEY` is printed in every report head, including 02. `block_card` is always `llm`, measured panels are `fact`. | Do not touch `SHADE_KEY` (it is part of 02's bytes). Add a separate `TIER_KEY` line and a separate question line, printed for every report (all 16 have a schema and a question). Tier M → `fact` shade, A/R/M+A → `llm` shade. | Absorb |
| 7 | Tier "M+A" | Used on 3 cards; principle 3 defines only M, A, R | No tier concept | Badge text "M+A", model shade, own tooltip. | Absorb (spec issue 3) |
| 8 | Tier M content | M = "tool output only, no model involved" | No extractors exist in M0. Every table in the old reports was written by Claude. | Cards whose writer is a script (tier M, or shape `computed`) never receive migrated content. They render the placeholder. This keeps the M badge true. | **Decision** (D-Q8, answered) |
| 9 | Free-form blocks versus closed cards | Fixed ids, titles, shapes, columns; writers do not choose headings (§8) | A report is a flat list of blocks. Each block is its own card, titled by its free-text `heading`. `with_contents` builds the contents list by regex over the card markup. `validate` warns when a heading is missing. | New `cards` layout. A schema card is one card holding its blocks. Heading is ignored. Contents list reads card titles. The regex `CARD_HEAD` gets an optional `data-card` attribute so tests can read card ids from the page. The badge sits outside the `<h3>` so it does not leak into the contents list. | Absorb |
| 10 | Claim model | Every statement is confirmed, inferred or unknown (§2.3) | `claims_of` walks blocks only (text, diagram, list items, table rows). | New walkers: blocks inside cards (same as today), `entries` (one claim per entry; `conf`, `cite`, `note` on the entry), `na` (always `confirmed`, citation required). `pending` and script cards make no claims. | Absorb (spec issue 8) |
| 11 | Executive summary type | §8 example: `"summary": ["...", "..."]` (list) | `summary` is a string of `- ` lines; `validate` and `md()` expect a string | Accept both; a list is joined into `- ` lines by one helper. No new bounds check in M0. | Absorb (spec issue 1) |
| 12 | Open-item IDs and decisions | IDs and decisions must survive (process.md, SKILL.md) | `resolve.sync` matches an item to a tracked ID only within the **same report id**, by statement fingerprint or similarity. Moved or renamed statements get new IDs. Old decisions then match nothing. `gaps.json` items carry a `report` field (old ids). `corrections[].report` holds old ids. `cmd_correct` checks `--report` against `TITLES`. | (Answered 2026-11-01: not needed.) Every old dossier is deleted and rebuilt, so no saved decision has to survive. `migrate` remaps `gaps.json` item `report` fields only (so the Gaps tracker links to reports that exist) and leaves `state.json` alone; open-item IDs on the migrated fixture may be renumbered, which is acceptable. | Absorb |
| 13 | Incremental staleness (`incremental.py`) | §5.3 | Keyed on ids only in `REPO_WIDE = (overview, contributors)` and `AGGREGATE = gaps`; all still exist. `cites_in` uses a generic walker (`transform`) that already visits any `cite` list and any string, and skips `mermaid`. `update_plan` builds `expected` from `render.REPORTS`. | No code change. Add one test that `cites_in` finds citations inside `cards` (blocks, `na`, `entries`). | Absorb |
| 14 | Version and old dossiers | (not covered) | `VERSION` is 0.4.0. `update_plan` forces a full rebuild when major.minor changes. `save_state` copies `state.json` to `state.backup-v<old>.json` when the version changes. | Bump to 0.5.0 in M0 (not 1.0.0; that is M6). Add an interim notice to SKILL.md because the prompts cannot yet write the new layout. Old dossiers are deleted, not upgraded. | **Decision** (D-Q5, answered) |
| 15 | Report 02 "unchanged" | "byte-identical in content" (§10) | 02's HTML section includes the shared `SHADE_KEY`, the code-viewer markers (planned from all reports' citations), the contents list and references. | Test = SHA-256 of the `<section class="report" id="overview">` element after removing the added card ids, tier badges, question line and tier key (`--normalize`). Proven today: a fresh render of the current code on a copy of the encamp dossier reproduces the existing page's section exactly (248,699 characters, SHA-256 `fe72cec488cb211edd6919154bf4d3ed68845e4e33b667a1874716a96bb63b59`). | Absorb |
| 16 | Questions under report titles | Each report shows its question (§4) | Reports have a `headline` only. Questions exist in the spec for 03 to 12, not for 01, 02, 13, 14, 15, 16. | Question line for all 16 reports. 13 uses question 8.1 from §3 ("Who owns and knows what, and what is the bus factor?"). 01, 02, 14, 15 and 16 use the texts marked † in M0-3 (15 reuses question 10.1). | **Decision** (D-Q6, answered) |
| 17 | Fixed rows and categories | "Fixed rows" (cross-cutting), "Fixed categories" (inputs, outputs), fixed areas (conventions), fixed recipes | Nothing | Stored in the schema (`fixed`). V6 gives a **warning** for a missing fixed value, not an error (an error would block encamp, whose rows differ). | Absorb |
| 18 | "Not yet generated" | §10: placeholder; §8 defines only `na` | No such form | `{"card": "<id>", "pending": true}` in the report file. V6 accepts it while `schema.ALLOW_PENDING` is true (turn off in M2). A missing required card is still an error. | Absorb |
| 19 | `dossier.process` | New M-tier card in 01, written by a script from `build.json` (M1) | Report 01 is built from three panels | M0 adds only the placeholder card, from `prompts/schema/dossier.json`, after "About this dossier". | Absorb |
| 20 | (answered: drop) Measured env-var and secret-scan panels | Not mentioned. `ops.config-secrets` is a Claude-written table citing `facts:env_vars`. | `PANELS_AFTER["delivery"]` draws two measured cards (`facts-env_vars`, `facts-secret_signals`). Citations of `facts:env_vars` and `facts:secret_signals` link to those anchors. They cap rows at 40, 50 and 30. | Remove both panels (`panel_env`, `panel_secrets`, `PANELS_AFTER`). Point the fact keys `env_vars` and `secret_signals` at `facts-git` in `FACT_KEYS`, as is already done for `hot_files`, so a citation of them still resolves. Their tests, if any, go with them. Both panels are listed in `docs/post-v1.md` as candidates to re-add after 1.0.0. | Absorb (Q4) |
| 21 | "No limits" (principle 7) versus report 02 | No caps on rows | Report 02 caps: top 40 contributors, 10 release tags, calendar last 16 years; knowledge map and dependencies trim files; `gather.py` has caps I did not audit. | Report 02 is frozen by M0. Raise with the human; not planned in M0. | **Decision** (spec issue 11) |
| 22 | Tests keyed on report ids | — | `test_render.py::TestReportLayout` asserts `TITLES`/`NAV_GROUPS` for overview, risks, gaps, Tracking group (all still true except the Tracking group, which loses Risks; M0-11 step 5 changes that one assertion). `test_incremental.py` uses ids like `data`, `code-tour` only as dictionary keys. `check_page.py` finds reports with `.report` and has no id list. `dossier.js` has no id list. | No test needs changing for the id switch. New tests are added per task. | Absorb |
| 23 | Docs and prompts | `prompts/reports.md` describes the old design; README says "twelve reports" | — | Not rewritten in M0 (M2 and M6). SKILL.md gets a short interim notice (task M0-12). | Absorb |
| 24 | Existing cards of 01, 02, 14, 15, 16 enter the schema | Added by the human after review | Drawn by code with ids like `facts-git`, `tracker`, `corrections-list` | Schema entries (shape `computed`) with new ids; `card()` adds `data-card` and a badge; old DOM ids kept so citations keep working. Report 02's digest is taken after removing those additions. | Absorb |
| 25 | Look versus tier | M cards use the facts shade (§2.3) | "Reports in this dossier" is model-shaded in code | Shade follows the tier like every other card, so this card (tier M) moves to the facts shade. No other existing card changes shade (checked: all others already match their tier). | Absorb |
| 26 | Risks card title | (not stated) | `risks.json` headings vary ("Risk register" in encamp; prompts say "Tracker") | Schema title "Tracker" (plan 001). Encamp's Risks card therefore changes title. | Absorb |
| 27 | Corrections "Your confirmations and answers" | Fixed skeleton | Drawn only when decisions exist | Always drawn, with an empty message. | Absorb |

---

## 3. Decisions

### D1. Schema files: location and format

**Decision.** `prompts/schema/<report>.json`, one per report that has written cards: all 16 reports. `dossier`, `overview`, `gaps` and `corrections` consist only of script cards (shape `computed`: existing panels drawn by code); `risks` has one Claude-written card with a table; `reading … contributors` as before. A card may carry `"informational": true`: it is not required to answer a question in `questions.json` (the spec's check "a schema card answers no question and is not marked `informational`" skips it). An informational card may still be named as an answer; `gaps.tracker` is, for questions 10.1 and 10.2. Informational cards: `dossier.questions`, `dossier.reports`, `dossier.changelog`, `overview.repository`, `corrections.decisions`, and the three trackers `risks.tracker`, `gaps.tracker`, `corrections.tracker` (decided by the human, 2026-11-01). A report file needs a `cards` list only if its schema has a Claude-written card; `gaps.json` keeps its top-level `items` list. A short `prompts/schema/README.md` documents the format.

```json
{
  "report": "entry",
  "title": "Entry points",
  "question": "Where does execution start?",
  "cards": [
    {"id": "entry.catalog", "title": "Entry points", "tier": "A", "priority": "P0", "writer": "claude",
     "shape": "blocks",
     "slots": [{"type": "table", "columns": ["Kind", "Name", "Triggered by", "Starts at", "Notes"]}],
     "fixed": null}
  ]
}
```

- `tier`: `M`, `A`, `R` or `M+A`. `priority`: `P0` or `P1`. `writer`: `claude` or `script`. Rule: tier `M` or shape `computed` ⇒ writer `script`; everything else ⇒ `claude`. A unit test enforces it.
- `shape` is one of:
  - `blocks`: the card's `blocks` match `slots` in order. A slot is `{"type": "table|text|list|diagram", "columns": [...] (tables), "min": 1, "max": 1}`; `min` defaults to 1, `max` to 1, `"max": null` means unlimited. A table slot's `columns` must match exactly (names and order); a table with zero rows is an error (use `na`).
  - `flows`: repeated `diagram` blocks, each optionally followed by one `text` or `list` block (its notes). Optional `"max_diagrams": 1` (used by `entry.startup`). No upper limit otherwise.
  - `entries`: the card holds `entries`, each `{<key>: "name", "fields": {<field id>: "text", …}, "conf", "cite", "note"}`. The schema has `"key": "component"` and `"fields": [{"id": "purpose", "label": "Purpose"}, …]`. All fields are required.
  - `computed`: filled by a script later (graphs, scatter plots, pickers). Writer `script`.
- Repeated entries: `entries` (no limit). Repeated rows: any number of rows. Repeated flows: any number of diagram blocks.
- "Not applicable with evidence": `{"card": "<id>", "na": "reason", "cite": ["path:1-30"]}` (spec §8). Allowed on every card whose writer is `claude`. The reason is a `confirmed` statement; `cite` must be non-empty.
- Placeholder: `{"card": "<id>", "pending": true}`.
- Script cards (writer `script`) may be absent from a report file; if present they may only be `pending`. Render fills them (M0: placeholder).
- `fixed`: `{"on": "<column or entry key>", "values": [...]}` or `null`. Warning only (see item 17). A card may also have `fixed2` (same format) for its second table slot; `fixed` applies to the first table slot, `fixed2` to the second. Only `behavior.tests` uses it.

**Rejected.** (a) One big `schema.json`: merge conflicts, and the spec says one file per report. (b) Putting titles and tiers in Python: the prompts in M2 must read them. (c) A JSON-Schema file: cannot express "column order equals the list" and "optional notes after each diagram" without more machinery than the validator itself.

### D2. Mapping existing content onto the cards

**Decision.** A one-off command `dossier.py migrate [REPO] [--dry-run]`, driven by a data file `scripts/migrate_map.json` (rules: old report, block heading or diagram type → card, with a column map). It runs the old report files through the rules and writes new-layout files.

- A table block fills a card only through an explicit column map: each new column names the old column it takes, or `null`. A `null` column is filled with the text "Not yet recorded". Rows keep their `conf`, `cite` and `note`.
- A diagram followed by a text block whose heading starts "Notes on …" becomes a diagram plus its notes (the same pairing the renderer applies today).
- If a card does not get exactly what its slots need, it stays `pending` and the blocks that were tried are listed as not carried over.
- Content that fits no card is **not shown**. It is copied unchanged into `reports.legacy-v<version>/`, and `migrate` prints the list (old report, block number, heading). It is not turned into Gaps items and not hidden in a catch-all card (that would break the closed schema).
- Cards with writer `script` get no migrated content (D-Q8).
- `headline` and `summary` of a new report are copied from one named old report (`primary` in the map) when at least one card was filled; otherwise they say "Not yet generated for this dossier."
- The old reports are backed up, retired files removed from `reports/`, `data.json` and `contributors.json` overwritten in the new layout, `gaps.json` item `report` fields remapped. `overview.json` is not touched. `risks.json` is rewritten in the card layout (its table becomes the `risks.tracker` card).

**Rejected.** (a) A compatibility layer inside `render.py` that reads old blocks directly: permanent legacy code, a hole in V6, re-maps on every render, and hides what is lost. (b) Having Claude rewrite the content: needs M2 prompts, costs tokens, and is not repeatable. (c) Only a full rebuild: the exit criterion needs the existing dossier re-rendered, and the prompts cannot yet write the new layout. (d) A catch-all "other content" card: contradicts principle 4.

The map for encamp is in Appendix B; Appendix A shows what is carried over and what is not.

### D3. How V6 reports problems and where it runs

**Decision.** `schema.validate(rid, rep, sch)` returns `(errors, warnings)`. Every message starts with "V6:". `render.validate` calls it for every report that has a schema and adds the results to its own lists, so `dossier.py render` prints them and stops on errors (unless `--allow-errors`), like V1 today. `migrate` runs the same function on what it wrote and exits non-zero on any error. Errors: wrong layout, unknown, duplicate or out-of-order card, missing required card, a title that differs from the schema, a script card with content, wrong columns, unexpected or missing block, zero-row table, `na` without a citation, bad entry fields, `pending` while `ALLOW_PENDING` is false. Warnings: a fixed row or recipe missing.

**Rejected.** (a) A separate command writers must remember to run: the spec says `render` runs it. (b) Making fixed rows an error now: blocks encamp for a rule that nothing yet teaches the writer. (c) Warning instead of error for column mismatches: the spec says error.

### D4. Tier badges and question line

**Decision.**

- Card header: `<header><h3>{title}</h3><span class="badge tier tier-a" data-variant="outline" tabindex="0" data-tip="…" data-tip-kind="note" aria-label="…">A</span></header>`. The badge is outside the `<h3>`. The tooltip uses the page's existing `data-tip` mechanism.
- Tooltips (plain words): M "Measured: produced by a tool from the repository. No model was involved." A "Adjudicated: a tool found the candidates, and Claude sorted, pruned, added and explained them." R "Read: Claude's reading of the code, with citations. Each statement is confirmed, inferred or unknown." M+A "Measured and adjudicated: tool output that Claude then named, merged or explained."
- Shade: tier M → class `fact`; A, R, M+A → class `llm`. Same CSS as today (`.card.fact`, `.card.llm`).
- Report head for every report (all 16 have a schema): `<h1>`, then `<p class="question">…</p>`, then the existing headline, then the existing `SHADE_KEY` unchanged, then a new `<p class="tier-key">` ("Badge on each card: M measured by a tool · A found by a tool, decided by Claude · R read by Claude").
- Reports 01, 02, 14, 15 and 16 are treated like the others: badges on their cards, the tier key and a question line (the texts marked † in M0-3). In report 02 the badges, card ids, question line and tier key are the only additions, and the report 02 check removes exactly them before comparing (D6).

**Rejected.** (a) Editing `SHADE_KEY`: changes 02's bytes. (b) Colour per tier: the spec keeps two colours. (c) Badge inside the `<h3>`: it would appear in the contents list.

### D5. New report list in navigation and the summary index

**Decision.** `REPORTS`, `TITLES`, `NAV_GROUPS` are redefined (item 1 above). "Reports in this dossier" and the sidebar are built from `REPORTS`, so they follow. Retired reports disappear from both. Their files are in the legacy backup; their ids stay in old `state.json` entries, where they are inert (item 12). `OPTIONAL_REPORTS` becomes empty. `--partial` still turns a missing report into a warning; a missing schema report then draws its whole skeleton as placeholders.

**Rejected.** Keeping retired ids as hidden reports: they would keep counting statements and open items that the page no longer shows.

### D6. What counts as "report 02 unchanged"

`tests/tools/report_section.py HTML overview --digest --normalize` prints the SHA-256 of the exact `<section class="report" id="overview" hidden>…</section>` text after removing the only things M0 adds to it: every ` data-card="…"` attribute, every `<span class="badge tier …">…</span>`, the `<p class="question">…</p>` line and the `<p class="tier-key">…</p>` line. Without `--normalize` the digest is of the raw text (used for the original page). It must equal the baseline above after every task that touches `render.py`, `dossier.css`, `dossier.js` or `template.html`, run against a scratch copy (commands in section 5). The baseline is valid for the frozen fixture `FIX` (the encamp dossier as it was on 2026-10-31); always render a scratch copy of `FIX`, never the live dossier. If `FIX` is ever replaced, re-derive the baseline with M0-1's tool on commit `88c3d7f`.

### D7. Overview's written blocks

`overview.json` stays byte-identical. The renderer stops drawing its `blocks`, `claims_of("overview", …)` returns nothing for them, and `validate` no longer requires `blocks` for overview. See item 4.

### D8. Version

`VERSION` = 0.5.0 (task M0-12). Not 1.0.0: the definition of done (§11.7) sets that at M6. **Rejected:** leaving 0.4.0, because the next `prepare` would call the old-layout dossier "incremental" and treat the new reports as merely unwritten.

---

## 4. Tasks

Dependency order. Independent of each other: M0-1; M0-2; M0-5 (needs nothing but the spec). M0-3 and M0-4 each need only M0-2 and are independent of each other. M0-6 needs M0-2 and M0-5. M0-7 needs M0-2, M0-3, M0-4. M0-9 needs M0-7. M0-10 needs M0-5 and M0-6. M0-11 needs M0-9 and M0-10. M0-12 needs M0-11. M0-13 needs everything. (There is no M0-8: it carried saved decisions across the migration and was dropped on 2026-11-01. The numbers of the other tasks are kept so that references stay valid.)

After **every** task: the full test suite passes. After tasks M0-5, M0-6 and M0-10 (they touch `render.py`, `dossier.js` or CSS) also run the report-02 digest check on the unmigrated scratch copy (section 5, block A); it must print `OK`.

### M0-1. Report-section tool (baseline for "report 02 unchanged")

- [ ] **Goal.** A small script that cuts one report's section out of a rendered page, prints its SHA-256, and lists the card ids of every report.
- **Files.** New `tests/tools/report_section.py`; new `tests/unit/scripts/test_report_section.py`.
- **Interface.** `section(html: str, rid: str) -> str` returns the text from `<section class="report" id="{rid}" hidden>` up to and including its closing `</section>`, found with `re.search(r'<section class="report" id="%s" hidden>.*?</section>(?=<section class="report"|\s*<footer class="foot)' % re.escape(rid), html, re.S)`; raises `SystemExit` with a message when absent. `cards(html: str) -> dict[str, list[str]]` maps each report id to its `data-card="…"` values in page order. CLI: `report_section.py HTML RID --digest` prints the 64-hex SHA-256 of `section(...)` UTF-8 bytes and the length in characters, space-separated; `--normalize` (with `--digest` or `--write`) first applies `normalize(text)`, which removes exactly what D6 lists (every ` data-card="…"` attribute including its leading space, every `<span class="badge tier …">…</span>`, every `<p class="question">…</p>`, every `<p class="tier-key">…</p>`) and nothing else; `--write FILE` saves the section; `--cards` prints `cards()` as JSON.
- **Steps.** (1) Write the module (standard library only). (2) Test with a small synthetic page of three `<section class="report" …>` elements: `section` returns exactly the middle one; digest is stable; `--normalize` removes a `data-card` attribute, a tier badge span, a question paragraph and a tier-key paragraph and nothing else (a page without them gives the same digest with and without the flag); `cards` finds `data-card` attributes per report; missing report exits. (3) Confirm the baseline (below).
- **Done-check.** `uv run --with pytest python -m pytest tests/unit/scripts/test_report_section.py -q` passes, and `python3 tests/tools/report_section.py tests/fixtures/encamp-m0/dossier-encamp.html overview --digest --normalize` prints `fe72cec488cb211edd6919154bf4d3ed68845e4e33b667a1874716a96bb63b59 248699`. Then run section 5 block A on the **unchanged** code; it must also print `OK`.
- **Commit.** `test(dossier): add a report-section digest tool for the M0 report 02 check`

### M0-2. Schema loader and V6 validator

- [ ] **Goal.** `scripts/schema.py`: load schema files, lint them, validate a report against its schema.
- **Files.** New `scripts/schema.py`; new `tests/unit/scripts/test_schema.py`. No schema files yet; tests build schemas in memory.
- **Interface.**
  - `SCHEMA_DIR = Path(__file__).resolve().parent.parent / "prompts" / "schema"`; `ALLOW_PENDING = True  # M0 only: turn off when the M2 prompts can write every card`.
  - `REPORT_ORDER = ("dossier", "overview", "reading", "entry", "components", "interactions", "io", "data", "behavior", "change", "conventions", "ops", "contributors", "risks", "gaps", "corrections")`: the 16 reports in spec order. This is the single source of the order: tests, `render.py` (M0-10, M0-11) and the end-to-end check all import it from here.
  - `QUESTIONS_FILE = "questions.json"`: the question list behind the `dossier.questions` card (M0-4). It lives in the same folder but is **not** a report schema.
  - `load(rid, schema_dir=SCHEMA_DIR) -> dict | None` (None when the file does not exist, and always None for `rid == "questions"`); `load_all(schema_dir=SCHEMA_DIR) -> dict[str, dict]`: every `*.json` in the folder **except `QUESTIONS_FILE`**, key = file stem; `load_questions(schema_dir=SCHEMA_DIR) -> list[dict]` reads `QUESTIONS_FILE` (empty list when absent).
  - `lint(sch) -> list[str]`: meta-rules. Every card id starts with `<report>.`; ids unique; `tier` in `M, A, R, M+A`; `informational`, if present, is a boolean; `priority` in `P0, P1`; `writer` in `claude, script`; tier `M` or shape `computed` ⇒ `script`, all others ⇒ `claude`; `shape` known; `blocks` shapes have non-empty `slots` with known types and (tables) non-empty `columns`; `entries` shapes have `key` and `fields`; `fixed` is null or has `on` and `values`.
  - `validate(rid, rep, sch, allow_pending=None) -> (errors, warnings)`; `allow_pending=None` means use `ALLOW_PENDING`. Messages start with `V6:` and name the report and card.
- **Algorithm for `validate`.**
  1. `rep` not a dict → one error. If the schema has no writer-`claude` card and `cards` is absent → return no messages. `cards` missing otherwise: if `blocks` is a list, error "uses the old layout ('blocks' without 'cards'). Run: dossier.py migrate"; else error "needs a 'cards' list". Return.
  2. Walk `rep["cards"]` with a position pointer into `sch["cards"]`. For each entry: not a dict or no `card` → error. Unknown id → error. Seen before → error "appears more than once". Index lower than the pointer → error "out of order". Otherwise set the pointer past it. Required cards (writer `claude`) that were skipped over, or never seen, → error "required card … is missing". Script cards are never required.
  3. Allowed keys on an entry: `card, title, blocks, entries, na, cite, pending`. Others → error. `title`, if present, must equal the schema title.
  4. Script card with anything except `pending` → error "is produced by a script and must not be written".
  5. `pending`: must be `true`, and `allow_pending` must be true, else error. It excludes every other content key.
  6. `na`: non-empty string, no `blocks`/`entries`, `cite` a non-empty list of strings; else error.
  7. Otherwise exactly one of `blocks` / `entries` as the shape requires, else error.
  8. Shape `blocks`: match the block list against `slots` (consume blocks of the slot's type up to `max`, require at least `min`; extra blocks → error "unexpected block N (type)"; table columns compared with `==` → error "table columns must be [...], found [...]"; zero rows → error "has no rows; use 'na' with a reason and a citation").
  9. Shape `flows`: sequence of `diagram` blocks, each optionally followed by one `text` or `list` block; first block must be a diagram; `max_diagrams` enforced; anything else → error.
  10. Shape `entries`: `entries` is a non-empty list of dicts; each has a non-empty string under `key`, and `fields` is a dict whose keys equal the field ids exactly; values are non-empty strings.
  11. `fixed` (first table slot) and `fixed2` (second table slot): for a table slot, collect the values of the column named in `on`; for entries, the values of `key`; compare case-insensitively after stripping spaces and backticks; each missing value → **warning** "V6: … has no row for '…'".
- **Done-check.** `uv run --with pytest python -m pytest tests/unit/scripts/test_schema.py -q` passes. Tests cover: one passing report per shape; and one failing case per numbered rule above (assert the message contains `V6` and the key word: "old layout", "unknown card", "more than once", "out of order", "missing", "script", "columns", "no rows", "cite", "unexpected block", "fields"); `na` accepted; `pending` accepted and then refused with `allow_pending=False`; a missing fixed row is a warning, not an error; `lint` flags a card id with the wrong prefix and a tier-M card with writer `claude`; `load_all` on a temporary folder holding `a.json` and `questions.json` returns only `a`.
- **Commit.** `feat(dossier): add the card schema loader and V6 validator`

### M0-3. Schema files, part 1 (reports 01 to 06, 14 to 16)

- [ ] **Goal.** Write the nine schema files for `dossier`, `overview`, `reading`, `entry`, `components`, `interactions`, `risks`, `gaps`, `corrections`, and the format README.
- **Files.** New `prompts/schema/dossier.json` (five cards, as in the table below), `reading.json`, `entry.json`, `components.json`, `interactions.json`, `overview.json`, `risks.json`, `gaps.json`, `corrections.json`, `prompts/schema/README.md`; new `tests/unit/scripts/test_schema_files.py`.
- **Interface.** The format of D1. `title` and `question` are copied from the spec (§4); the spec gives no question for reports 01, 02, 14, 15 and 16, so their questions are the texts marked † (accepted by the human), copied exactly. Cards (all `fixed: null` unless a row says otherwise; `writer` follows the rule in D1; columns are written in this exact order):

| Report (title; question) | Card id | Title | Tier | P | Shape and slots |
|---|---|---|---|---|---|
| `dossier` ("This dossier"; "How was this dossier made, and how far can I trust it?" †) | `dossier.about` | About this dossier | M | P0 | `computed`, informational false (answers 10.3) |
| | `dossier.process` | How this dossier was made | M | P0 | `computed` |
| | `dossier.questions` | Questions this dossier answers | M | P0 | `computed` (drawn from `questions.json`, see M0-4 and M0-10), informational |
| | `dossier.reports` | Reports in this dossier | M | P0 | `computed`, informational |
| | `dossier.changelog` | Dossier changelog | M | P0 | `computed`, informational |
| `overview` ("This repository"; "What is this repository, who works on it, and what does it depend on?" †) | `overview.repository` | Overview | M | P0 | `computed`, informational |
| | `overview.contributors` | Contributors | M | P0 | `computed` (answers 8.1) |
| | `overview.dependencies` | Dependencies | M | P0 | `computed` (answers 3.2) |
| `risks` ("Risks"; "What could go wrong here, and how much would it matter?" †) | `risks.tracker` | Tracker | A | P0 | `blocks`: one table slot with `"max": null`, columns [ID, Risk, Category, Severity, Impact, Recommendation]; informational |
| `gaps` ("Gaps"; "What was not analysed, and what could not be resolved?" † (question 10.1)) | `gaps.tracker` | Tracker | A | P0 | `computed` (drawn from every open item plus `items`); informational; still named as the answer to 10.1 and 10.2 |
| `corrections` ("Corrections"; "What have I corrected or decided, and has it been applied?" †) | `corrections.tracker` | Tracker | M | P0 | `computed`, informational |
| | `corrections.decisions` | Your confirmations and answers | M | P0 | `computed`, informational |
| `reading` ("Reading guide"; "How do I approach this code?") | `reading.order` | Reading order | A | P0 | `blocks`: table [Phase, Step, Read, What you learn] |
| | `reading.glossary` | Glossary | A | P0 | table [Term, Meaning, Where it lives] |
| | `reading.technologies` | Technologies and idioms | A | P0 | table [Technology, Role here, Idiom to know] |
| | `reading.map` | Where things live | M | P0 | table [Concern, Location] (writer `script`) |
| `entry` ("Entry points"; "Where does execution start?") | `entry.catalog` | Entry points | A | P0 | table [Kind, Name, Triggered by, Starts at, Notes] |
| | `entry.startup` | Startup sequence | R | P0 | `flows`, `max_diagrams` 1 |
| `components` ("Components"; "What are the main parts, what does each do, and how does it work?") | `components.map` | Component map | M+A | P0 | `computed` |
| | `components.catalog` | Component catalog | A | P0 | table [Component, Paths, Responsibility, Public surface, Depends on, Used by, Size] |
| | `components.detail` | Component details | R | P0 | `entries`, key `component`, fields purpose "Purpose", how_it_works "How it works", public_surface "Public surface", state_owned "State owned", key_files "Key files", gotchas "Gotchas" |
| | `components.cross-cutting` | Cross-cutting concerns | R | P0 | table [Concern, Approach, Where]; `fixed` on Concern: configuration, authentication/authorisation, logging, error handling, caching, validation, i18n, feature flags |
| | `components.extension-points` | Extension points | R | P1 | table [Point, How to extend, Example] |
| `interactions` ("Interactions"; "How do the parts talk to each other, and where does state live?") | `interactions.graph` | Dependency graph | M | P0 | `computed` |
| | `interactions.violations` | Cycles and layer violations | M | P0 | table [Kind, From, To, Evidence] (writer `script`) |
| | `interactions.flows` | Key flows | A | P0 | `flows` (no maximum) |
| | `interactions.state` | State ownership | A | P0 | table [State, Held in, Written by, Read by, Lifetime] |
| | `interactions.concurrency` | Concurrency model | A | P0 | table [Mechanism, Where, Shared state, Notes] |

- **Steps.** (1) Write the nine JSON files exactly as the table says (`slots` as in D1; script-writer cards still list their columns; all three trackers are informational, as D1 says). (2) `README.md`: the D1 text, trimmed, plus the rule "the report file never repeats titles", plus one sentence saying `questions.json` is the question list for the `dossier.questions` card and is not a report schema. (3) Test: every file passes `schema.lint`, its `report` equals the file stem, its `question` is a non-empty string, and (for this task) the set of file stems returned by `schema.load_all()` is exactly the nine above, each of which is in `schema.REPORT_ORDER`. M0-4 extends the set.
- **Done-check.** `uv run --with pytest python -m pytest tests -q` passes, including the new test.
- **Commit.** `feat(dossier): add card schemas for reports 01 to 06 and 14 to 16`

### M0-4. Schema files, part 2 (reports 07 to 13)

- [ ] **Goal.** Schema files for `io`, `data`, `behavior`, `change`, `conventions`, `ops`, `contributors`.
- **Files.** New `prompts/schema/io.json`, `data.json`, `behavior.json`, `change.json`, `conventions.json`, `ops.json`, `contributors.json`; edit `tests/unit/scripts/test_schema_files.py`.
- **Interface.** Same format. Defaults chosen where the spec gives no columns are marked †; see section 6 and 7.

| Report (title; question) | Card id | Title | Tier | P | Shape and slots |
|---|---|---|---|---|---|
| `io` ("Inputs and outputs"; "What goes in and what comes out?") | `io.inputs` | Inputs | A | P0 | table [Category, Input, Format, Validation, Where read]; `fixed` on Category: CLI arguments, environment variables, config files, files read, stdin, network requests, messages consumed, database reads, scheduled triggers |
| | `io.outputs` | Outputs | A | P0 | table [Category, Output, Format, Validation, Where written] †; `fixed` on Category: stdout/stderr, files written, network responses, outbound calls, messages produced, database writes, logs, metrics, exit codes, error responses |
| | `io.contracts` | Contracts | A | P0 | table [Contract, Direction, Counterparty, Schema location, Versioning] |
| `data` ("Data model"; "What data exists, and what is true about it?") | `data.entities` | Entities and types | M+A | P0 | table [Name, Kind, Fields, Defined in, Owner component] |
| | `data.relationships` | Relationships | M+A | P0 | `blocks`: diagram slot with `"max": null` |
| | `data.stores` | Data stores | A | P0 | table [Store, Technology, Holds, Migration approach] |
| | `data.truth` | Source of truth | R | P0 | table [Data, Source of truth, Derived copies] |
| | `data.lifecycle` | Lifecycle and sensitive fields | A | P0 | table [Data, Created, Changed, Retained, Deleted, Sensitive?] |
| `behavior` ("Behavior and tests"; "What does it guarantee, how is that checked, and how does it fail?") | `behavior.rules` | Business rules and invariants | R | P0 | table [Rule, What it does, Where decided, Edge cases] |
| | `behavior.tests` | Test landscape | A | P0 | `blocks`: two table slots in order: [Measure, Value, Where] with `fixed` on Measure: test counts by kind, test counts by area, framework, skipped and xfail counts, mock density, test-to-source mapping, coverage configuration and thresholds, CI test commands; then [Question, Assessment, Evidence] with fixed rows "What important code is untested?" and "Can a green run be trusted?" †. Only one `fixed` is allowed per card in the schema, so put the second fixed list under `fixed2` (same format); V6 checks both as warnings |
| | `behavior.failures` | Failure modes | A | P0 | table [ID, Failure, Trigger, Detection, Effect, Recovery], then an optional `text` slot (`min` 0) for retries, timeouts and idempotency |
| | `behavior.observability` | Observability | A | P0 | table [Signal, Library, Where emitted, Where it goes] |
| `change` ("Change and history"; "Where is it safe to change, and how did it get here?") | `change.hotspots` | Hotspots | M | P0 | `computed` |
| | `change.cochange` | Co-change coupling | M | P0 | table [A, B, Co-commits, Share, Linked in code?] (script) |
| | `change.blast-radius` | Blast radius | M | P0 | `computed` |
| | `change.unfinished` | Unfinished migrations | R | P0 | table [Pattern, Old way, New way, Progress, Evidence] |
| | `change.decisions` | Decisions and oddities | A | P0 | table [Item, Why (as far as known), Evidence, Source] |
| | `change.dead-code` | Dead code and stale flags | M | P0 | table [Item, Kind, Evidence] (script) |
| | `change.docs-drift` | Docs versus code | R | P1 | table [Claim, Document, What the code shows, Verdict] |
| | `change.upgrade-burden` | Upgrade burden | M | P1 | table [Runtime or package, Pinned, Latest or supported, Gap] (script) |
| | `change.in-flight` | Work in flight | M | P0 | table [Branch, Last commit, Ahead/behind, Author] (script) |
| `conventions` ("Conventions"; "How do I write code that fits in here?") | `conventions.style` | Code conventions | A | P0 | table [Area, Convention, Evidence]; `fixed` on Area: naming, error handling, logging, dependency injection, async, validation, tests |
| | `conventions.recipes` | Recipes | R | P0 | `entries`, key `recipe`, fields files_to_touch "Files to touch, in order", worked_example "Worked example in this repository" †; `fixed` on recipe: add an endpoint or command, add a field, add a migration, add a test, add a dependency, add a config setting |
| | `conventions.tooling` | Formatting and tooling | M | P0 | table [Tool, Config file, Enforced where] (script) |
| `ops` ("Build, run and ship"; "How do I get it running and into production?") | `ops.local` | Local setup | A | P0 | `blocks`: a `list` slot (the ordered steps), then a table [Prerequisite, Kind, Version or detail, Where stated] † |
| | `ops.build` | Build and packaging | A | P0 | table [Artifact, Command, Output] |
| | `ops.test` | Running tests | A | P0 | table [Scope, Command, Notes] |
| | `ops.run` | Running it | A | P0 | table [Mode, Command, Needs] |
| | `ops.ci` | CI gates | A | P0 | table [Pipeline, Trigger, Steps, Blocks merge?, Publishes] |
| | `ops.release` | Release, deploy and rollback | A | P0 | table [Environment, How released, How rolled back, Versioning] |
| | `ops.config-secrets` | Configuration and secrets | A | P0 | two table slots in order: [Setting, Default, Overridden by] then [Secret, Unlocks, Supplied how] |
| `contributors` ("Contributors"; "Who owns and knows what, and what is the bus factor?" †) | `contributors.people` | Who the people are | A | P0 | table [Person, Role in the project, Areas, Active?] |
| | `contributors.ask` | Who to ask | A | P0 | table [Subsystem, Ask first, Then, Basis] |
| | `contributors.concentration` | Knowledge concentration | A | P0 | table [Area, Owner, Share, Status] |
| | `contributors.agents` | Agents and bots | A | P0 | table [Identity, Kind, Areas touched, Share of commits] |
| | `contributors.doubts` | Classification doubts | R | P0 | table [Identity, Doubt, What would settle it] |
| | `contributors.workflow` | Team workflow | M | P0 | table [Convention, Observed, Evidence] (script) |

- **Also in this task: `prompts/schema/questions.json`.** Format: `[{"id": "1.1", "question": "What do the domain terms mean?", "answers": [<ref>, …]}, …]`; a ref is a card id string or `{"report": "overview", "label": "Dependencies card"}` for something outside the schema. One entry per question in spec §3, in order, text copied from the spec. Answers: 1.1 reading.glossary; 1.2 reading.technologies; 2.1 entry.catalog; 2.2 entry.startup; 2.3 components.map, components.catalog; 2.4 components.detail, components.cross-cutting; 2.5 interactions.graph, interactions.flows; 2.6 io.inputs, io.outputs; 2.7 reading.order, reading.map; 2.8 interactions.state; 2.9 interactions.concurrency; 2.10 interactions.violations; 2.11 components.extension-points; 2.12 conventions.style, conventions.recipes, conventions.tooling; 3.1 io.contracts; 3.2 overview.dependencies; 4.1 data.entities, data.relationships; 4.2 data.truth, data.stores; 4.3 data.lifecycle; 5.1 behavior.rules; 5.2 behavior.tests; 5.3 behavior.failures, behavior.observability; 6.1 change.hotspots; 6.2 change.cochange; 6.3 change.blast-radius; 6.4 change.unfinished; 6.5 change.decisions; 6.6 change.docs-drift; 6.7 change.dead-code; 6.8 change.upgrade-burden; 6.9 change.in-flight; 7.1 ops.build, ops.test, ops.run, ops.release, ops.config-secrets; 7.2 ops.ci; 7.3 ops.local; 8.1 overview.contributors, contributors.people, contributors.ask, contributors.concentration, contributors.agents, contributors.doubts; 8.2 contributors.workflow; 10.1 gaps.tracker; 10.2 gaps.tracker; 10.3 dossier.about; 10.4 dossier.process. Test: every card id in `answers` exists in the schemas; every schema card that is not `informational` is named by at least one question; question ids are unique and in spec order.
- **Steps.** Write the seven files and `questions.json`. Extend the test: `schema.load_all()` returns exactly the 16 ids of `schema.REPORT_ORDER` (so `questions` is not among them); all 16 files pass `lint`; 65 cards in total; 42 have writer `claude` and 23 `script`; every `fixed.on` (and `fixed2.on`) names a real column or entry key; `schema.load_questions()` passes the checks listed above.
- **Done-check.** `uv run --with pytest python -m pytest tests -q` passes.
- **Commit.** `feat(dossier): add card schemas for reports 07 to 13`

### M0-5. Card drawing helpers (not yet wired into the page)

- [ ] **Goal.** Pure functions in `render.py` that draw one schema card: title, badge, placeholder, "not applicable", blocks, flows, entries.
- **Files.** Edit `scripts/render.py` (add a section "schema cards" after `render_blocks`); edit `assets/dossier.css`; edit `assets/dossier.js` (search over entries, below); edit `scripts/check_page.py` (search check, below); new `tests/unit/scripts/test_render_cards.py`.
- **Interface.**
  - `TIER_INFO = {"M": ("Measured", "…tooltip text from D4…"), "A": …, "R": …, "M+A": …}`; `tier_badge(tier) -> str` as in D4 (class `tier tier-<tier lowercased, '+' as 'plus'>`).
  - `card_dom_id(cid) -> str` returns `"c-" + cid.replace(".", "-")`.
  - `schema_card(card, body, extra="") -> str`: `<div class="card block {shade}{extra}" id="{card_dom_id}" data-card="{id}"><header><h3>{title}</h3>{tier_badge}</header><section>{body}</section></div>`; `shade` is `fact` for tier M, else `llm`.
  - `placeholder_body(card) -> str`: writer `claude`: `<p class="muted"><strong>Not yet generated.</strong> This card is part of the standard layout. Nothing has been written for it in this dossier yet.</p>`; writer `script`: same first sentence plus "A tool fills this card in, not Claude. That tool is not part of this version yet."
  - `na_body(entry, refs) -> str`: `<p>Not applicable: {inline(na)}</p>` followed by `provenance({"conf": "confirmed", "cite": entry["cite"]}, refs, entry["na"])`.
  - `blocks_body(card, blocks, refs, tid) -> str`: for each block, the same inner markup the existing `render_block` builds, without its outer `<div class="card …">`: tables via `render_table(cols, rows, refs, f"{tid}-{i}")` with the optional `caption`; lists as `<ul class="claims">` (copy the existing list markup); text as `md(...)` plus `provenance(...)`; diagrams as `<div class="diagram flow">` containing `<div class="flow-bar"><h4>{title}</h4>` + the existing expand button markup (`EXPAND_ICONS`) + `</div>`, the `mermaid-host` div, the `<details>` source block, and the notes block that follows it (text or list), each with its provenance. Block `heading` is ignored.
  - `entries_body(card, entries, refs, tid) -> str`: one `<details class="entry" id="{card_dom_id(card id)}-e{n}" open>` per entry (`n` counts from 1 in entry order): `<summary>{name}</summary>`, a `<dl class="facts">` with the field labels from the schema and `inline(value, refs)`, then `provenance(entry, refs, " ".join(values))`.
  - `render_card(card, entry, refs, rid) -> str`: `entry` is the dict from the report file or `None`. `None`, `pending` or a script card → placeholder; `na` → `na_body`; `blocks`/`entries` → the matching body; anything unexpected → placeholder (V6 reports the real error).
  - `schema_cards_html(sch, rep, refs, rid) -> str`: for each schema card in order, `render_card(card, entries_by_id.get(card["id"]), …)`; joined; no wrapper.
- **Search over entries (`assets/dossier.js`).** The spec requires component detail entries to be collapsible **and searchable**. Today `textOf` removes every `<details>` element before indexing (it is meant for the "Diagram source" blocks), so entry text would never be found, and a hit inside a closed entry would land on hidden text. Make exactly these three changes:
  1. In `textOf`, change the selector `"details, sup.cite, …"` to `"details:not(.entry), sup.cite, …"` (diagram sources stay out of the index; entries stay in).
  2. In `buildIndex`, inside the per-card loop and after the `tbody tr` loop, index every entry like a table row: `$$("details.entry", card).forEach(function (d) { var s = $("summary", d); index.push({ id: d.id, report: rtitle, section: title, label: s ? textOf(s) : title, text: textOf(d), row: true }); });` (entries always have an id; see `entries_body`).
  3. In `open(i)`, before `go(e.id)`, open the target if it is a closed entry and every `<details>` that contains it: `var t = doc.getElementById(e.id); while (t) { if (t.tagName === "DETAILS") t.open = true; t = t.parentElement && t.parentElement.closest("details"); }`.
- **Search check (`scripts/check_page.py`).** Add `check_search(page, scheme)` in the style of `check_knowledge`, and call it from the same place. When the page has no `details.entry`, it returns `[]`. Otherwise, for the first entry: go to its report (`location.hash = <report id>`), close the entry (`el.open = false`), take the first word of 6 or more letters from the text of its first `dd` element (not the `dt` labels, which every entry shares), type it into `#search`, and require a `.result` whose `.what` text contains the entry's summary text; press Enter and require the entry to be `open` and visible (non-zero bounding box). Each failure is one problem, prefixed `[{scheme}] search:`.
- **CSS (append to `assets/dossier.css`).** `.tier { margin-left: .5rem; font-weight: 600; min-width: 1.6rem; justify-content: center; }` `.question { margin: .15rem 0 0; font-size: 1rem; font-style: italic; color: var(--muted-foreground); }` `.tier-key { display: flex; flex-wrap: wrap; gap: .3rem 1.25rem; font-size: .8125rem; color: var(--muted-foreground); margin: 0; }` `.diagram.flow + .diagram.flow { margin-top: 1.25rem; padding-top: 1rem; border-top: 1px solid var(--border); }` `.flow-bar { display: flex; align-items: center; justify-content: space-between; gap: .75rem; }` `.entry { border: 1px solid var(--border); border-radius: var(--radius); padding: .6rem .8rem; margin-bottom: .6rem; }` `.entry summary { cursor: pointer; font-weight: 600; }`. Adjust only if the screenshot check in M0-13 shows overlap.
- **Tests (`test_render_cards.py`, using the `make_cites` fixture and the in-memory schemas of M0-2).** Placeholder text appears for a missing, `pending` and script card; `na` shows the reason and a `[1]` marker; the tier badge is outside the `<h3>` (assert `</h3><span class="badge tier`); tier M gets `fact`, A gets `llm`; a table card keeps the schema's title even if the block has a different `heading`; a flows card with two diagrams and one notes block draws both, notes after the first; an entries card draws one `<details class="entry">` per entry, with ids `c-components-detail-e1`, `-e2`, … in entry order; `with_contents("entry", html)` lists the card titles without the letter "A" or "M".
- **Done-check.** Full test suite passes; section 5 block A prints `OK` (the helpers are not called by the page yet, so this only guards the CSS, the JavaScript and imports); `uv run scripts/check_page.py $SCR/home/encamp/dossier-encamp.html` on that page still reports `"problems": 0` (the new search check returns nothing on a page without entries; it is exercised for real in block C).
- **Commit.** `feat(dossier): draw schema cards with fixed titles, tier badges and placeholders`

### M0-6. Claims and validation for the new layout

- [ ] **Goal.** `claims_of`, `validate` and the summary helper understand `cards`; V6 runs inside `render.validate`.
- **Files.** Edit `scripts/render.py`; edit `tests/unit/scripts/test_incremental.py` (one test); new `tests/unit/scripts/test_render_validate.py`.
- **Interface and steps.**
  1. `import schema` at the top of `render.py`. Add `UNRENDERED_BLOCKS = ("overview",)  # overview.json's written blocks are no longer drawn; do not count what is not shown`.
  2. Split the current body of `claims_of` into `claims_of_blocks(rid, blocks, where=None)` (same logic; `where` overrides `b.get("heading")` when given) and make `claims_of(rid, rep)`:
     - `rid in UNRENDERED_BLOCKS` → `[]`.
     - `rep` has a `cards` list → for each card entry that is a dict: `blocks` → `claims_of_blocks(rid, entry["blocks"], where=<schema title or card id>)`; `entries` → one claim per entry with `text = f"{name} · {first field value}"`, `cells` = all field values, `node = entry`; `na` → `claim(rid, title, {"conf": "confirmed", "cite": entry.get("cite")}, entry["na"])`. Everything else → nothing. Be defensive: skip anything that is not the expected type; never raise.
     - otherwise the current behaviour on `rep.get("blocks", [])`.
  3. `summary_text(rep) -> str`: a string summary is returned as is; a list of strings becomes `"\n".join("- " + s)`. Use it wherever `render.py` reads `rep.get("summary")` (`validate`, `build_page`, `claims`: search for `"summary"`).
  4. In `validate`: for `rid` with `schema.load(rid)` not None, replace the `blocks` handling: no "needs a 'blocks' list" error; extend `errors`/`warnings` with `schema.validate(rid, rep, sch)`; run the per-block checks (type valid, table rows have as many cells as columns, diagram starts with a Mermaid keyword, list has `items`) over every block inside `cards[*].blocks`, with no heading warning. Move those per-block checks into a helper `check_block(tag, b, rid, schema_card=False)` used by both branches. For `rid == "overview"` do not require `blocks`. Remove the `capabilities` Status-column check. Keep the `risks` column check.
  5. Remove `"domain-logic"` from `OPTIONAL_REPORTS` (leave `OPTIONAL_REPORTS = ()`).
  6. Risks: `panel_risk_counts(rep)` must read the table blocks inside `cards` (add `all_blocks(rep)` returning `rep["blocks"]` or the blocks of every card; use it there and in `validate`). The risk-column check stays.
  7. `names` in `validate` still comes from `REPORTS`; the list itself changes in M0-11, so nothing else here depends on it.
- **Tests.** (`test_render_validate.py`, calling `render.validate` with the `make_cites` fixture and a schema loaded from the real `prompts/schema` files, using `entry` as the example report) a valid `entry` report with one table card, one `pending` card passes with no errors; a table with the wrong columns gives a "V6" error; a row with the wrong number of cells gives the row error; an old-layout `entry` report gives the "Run: dossier.py migrate" error; `claims_of` counts rows, an entry, and an `na`, and returns nothing for `pending`; `claims_of("overview", {"blocks": [...]})` is empty; `summary_text` handles both types. In `test_incremental.py` add: `incremental.cites_in({"cards": [{"card": "x", "na": "none", "cite": ["a.py:1"]}, {"card": "y", "entries": [{"component": "c", "fields": {"purpose": "see [[b.py:2]]"}, "cite": ["c.py"]}]}]})` returns the three paths.
- **Done-check.** Full test suite passes; section 5 block A prints `OK`.
- **Commit.** `feat(dossier): validate and count statements in card-layout reports (V6)`

### M0-7. Migration engine and map (pure functions)

- [ ] **Goal.** `scripts/migrate.py` turns old reports into new ones without touching disk; `scripts/migrate_map.json` holds the rules.
- **Files.** New `scripts/migrate.py`, `scripts/migrate_map.json` (content in Appendix B), `tests/unit/scripts/test_migrate.py`.
- **Interface.**
  - `MISSING_CELL = "Not yet recorded"`.
  - `load_map(path=MAP_PATH) -> dict` with keys `retired` (old report id → default new report id), `primary` (new report id → old report id), `rules` (list).
  - A rule: `{"from": "<old report id>", "to": "<card id>", "type": "table|diagram|text|list" (optional), "heading": "<regex, case-insensitive>" (optional), "mermaid": "<regex on the diagram source>" (optional), "columns": {"<new column>": "<old column>" | null} (tables), "notes": "following" (diagrams only)}`. A rule matches an old block when every given attribute matches. Rules are applied in file order; each old block is used by at most one rule.
  - `convert(old: dict[str, dict], mapping: dict, schemas: dict[str, dict]) -> dict` returns `{"reports": {new_id: report_dict}, "carried": [(old_id, block_index, heading, card_id)], "not_carried": [(old_id, block_index, heading, reason)]}`.
- **Algorithm for `convert`.**
  1. For each rule, in order, scan the blocks of `old[rule["from"]]` (absent report → skip). For a match: table → build a new table block `{"type": "table", "columns": <schema columns of the target slot>, "rows": [...], "caption": old caption if any}`; each row keeps `conf`, `cite`, `note` and its cells are taken through `columns` (an old column name that does not exist in the block counts as `null`). Diagram → `{"type", "title", "mermaid", "conf", "cite", "note"}`; with `"notes": "following"`, if the next old block is a text block whose heading matches `^\s*notes?\s+(on|for)\b` (the existing `render.NOTES_HEAD`), append it as a text block (without its heading) and mark it used. Text and list blocks are copied without `heading`. Drop `heading` from every converted block. Append the converted blocks to the card's pending list in rule order.
  2. For each card (writer `claude` only; script cards are skipped even if a rule targets them, and that is a map error caught by a test): build `{"card": id, "blocks": blocks}` and check it with `schema.validate` on a one-card report. If it has errors (wrong slot count, wrong columns), the card becomes `{"card": id, "pending": true}` and its blocks are listed in `not_carried` with reason "did not fit the card".
  3. For each schema, in the order of `schema["cards"]`: filled cards, then `{"card": id, "pending": true}` for every writer-`claude` card with nothing; script cards are omitted. Report `headline`/`summary` come from `old[primary[new_id]]` when at least one card is filled; otherwise `headline` "Not yet generated for this dossier." and `summary` "- Not yet generated for this dossier."
  4. `not_carried` also lists every old block no rule used (reason "no card for this content"), for every old report except `gaps`.
- **Tests.** Use a tiny hand-written old-report set (a `code-tour` with a reading-order table and two sequence diagrams each followed by "Notes on …", an `architecture` with a components table, a `delivery` with Configuration and Secrets tables, an `overview` with a Technology table). Assert: columns reordered and `null` columns filled with `MISSING_CELL`; row `conf`/`cite` preserved; flows card gets 2 diagrams + notes; `ops.config-secrets` is filled only when both tables exist (with one missing it is `pending` and the other table is in `not_carried`); headings dropped; unused blocks listed; every card of every schema is present or intentionally omitted (script); the result passes `schema.validate` for each new report; the shipped `migrate_map.json` has no rule targeting a script card or an unknown card id, and every `to` and `retired` target exists in the schemas.
- **Done-check.** Full suite passes. Then with the real map on the real encamp reports (read-only):
  `uv run python -c "import sys,json; sys.path.insert(0,'scripts'); import migrate,schema; from pathlib import Path; d=Path('tests/fixtures/encamp-m0/reports'); old={p.stem: json.load(open(p)) for p in d.glob('*.json')}; r=migrate.convert(old, migrate.load_map(), schema.load_all()); print(len(r['carried']), len(r['not_carried']), sum(1 for rep in r['reports'].values() for c in rep['cards'] if c.get('blocks')), sum(1 for rep in r['reports'].values() for c in rep['cards'] if c.get('pending')))"`
  prints `22 66 15 27`.
- **Commit.** `feat(dossier): add the old-to-new report migration engine and encamp map`

### M0-8. (dropped)

**Dropped (2026-11-01).** This task carried open-item IDs and saved decisions across the migration. Every old dossier is deleted and rebuilt, so nothing needs to survive. Do not implement it; go on to M0-9.

### M0-9. The `migrate` command

- [ ] **Goal.** `dossier.py migrate [REPO] [--dry-run]`: backup, convert, write, validate. It exists to turn the `FIX` fixture into the new layout for the exit criterion; it is not documented for users (no dossier is migrated for real).
- **Files.** Edit `scripts/dossier.py`; edit `scripts/migrate.py` (add `remap_gaps`); edit `tests/unit/scripts/test_migrate.py` (add a command-level test using a temporary dossier folder).
- **Interface.**
  - `migrate.remap_gaps(gaps_report, retired) -> dict`: returns a copy of the report with each item's `report` set to `retired.get(report, report)`.
  - `cmd_migrate(a)` in `dossier.py` (register `migrate` with `repo` and `--dry-run`). Steps:
    1. `out, name, _ = out_dir(toplevel(a.repo))`; `reports_dir = out / "reports"`. Load every `*.json` there into `old`. A dossier needs migrating when any retired id has a file, or any schema report file lacks `cards`. If none: print "Nothing to migrate." and return.
    2. `result = migrate.convert(old, migrate.load_map(), schema.load_all())`; `gaps_new = migrate.remap_gaps(old["gaps"], retired)` if there is a gaps file. Validate each new report with `schema.validate`; any error → print them and exit 1 **before writing anything**.
    3. `--dry-run`: print the summary (below) and return without writing.
    4. Backup: `shutil.copytree(reports_dir, out / f"reports.legacy-v{state_version or 'unknown'}")`; if that folder exists, `die(...)` (never overwrite a backup). `state_version` is `state.get("skill_version")`.
    5. Write each new report with the existing `save()`, write `gaps.json`, delete the retired files from `reports/`. Do not touch `overview.json` or `state.json`.
    6. Print a JSON summary: `{"backup": path, "written": [ids], "cards_filled": n, "cards_pending": n, "carried": n, "not_carried": [{"report", "block", "heading", "reason"}…]}`.
- **Test.** In a temporary folder with `DOSSIER_HOME` set and a small git repo (use the existing `git_repo` fixture): old-layout reports in, `migrate` out; assert the backup folder holds the old files, retired files are gone, `data.json` has `cards`, `overview.json` and `state.json` are byte-identical to before, a second run prints "Nothing to migrate.", `--dry-run` writes nothing, a second backup name collision stops the command.
- **Done-check.** Full suite passes. Then make a fresh scratch copy (the first two command lines of section 5, block B) and run `uv run scripts/dossier.py migrate /home/nick/dev/projects/encamp --dry-run`; it prints `"cards_filled": 15` and `"cards_pending": 27`.
- **Commit.** `feat(dossier): add the migrate command for old-layout dossiers`

### M0-10. Wire schema cards into the page

- [ ] **Goal.** `build_page` draws schema reports from the schema, adds the question line and tier key, adds the `dossier.process` placeholder to report 01, and stops drawing overview's old blocks. The report list itself is **not** switched yet, so legacy dossiers still render.
- **Files.** Edit `scripts/render.py`; edit `assets/dossier.css` (only if needed); edit `tests/unit/scripts/test_render_cards.py`.
- **Steps.**
  1. `CARD_HEAD`: change the pattern to `r'<div class="card (panel|block)([^"]*)"( id="[^"]*")?( data-card="[^"]*")?><header><h([23])>(.*?)</h\5>'`, and in `with_contents` unpack the new group and re-emit it: `f'<div class="card {kind}{extra}" id="{cid}"{dc or ""}><header><h{lvl}>{inner}</h{lvl}>'`. For markup without `data-card` the output is unchanged.
  2. New `head_html(rid, title, headline_html, sch=None) -> str` that returns the `<header class="report-head">…</header>` string exactly as `build_page` builds it today when `sch` is None, and for a schema report inserts `<p class="question">{E(question)}</p>` after the `<h1>` and `<p class="tier-key">…</p>` after `SHADE_KEY`. Use it in `build_page`. Insert the tier key, the question line and every tier badge (here and in step 6), directly against the neighbouring markup with no added spaces or newlines: the report 02 digest removes exactly those elements, so any extra whitespace around them makes it differ.
  3. In `build_page`, in the authored branch: `sch = schema.load(rid)`; if `sch`, `parts.append(f'<div class="findings">{schema_cards_html(sch, rep, refs, rid)}</div>')` and do not call `render_blocks`. For `rid == "overview"` keep the three panels and draw no blocks. Delete the `moved` variable and the `capabilities` special case.
  4. In the `dossier` branch, after `panel_dossier(...)`, add `schema_card(card, placeholder_body(card))` for `dossier.process`, then the real `dossier.questions` card: `schema_card(card, questions_body(refs))`. `questions_body(refs)` loads `questions.json` and all schemas and builds a plain table (`render_table(["No.", "Question", "Answered in"], rows, refs, "t-questions", True, True)`; no Basis or Sources columns) with one row per question. Each answering card is `<a href="#{card_anchor(id)}">Card title</a> <span class="muted">(report NN)</span>`, NN being the 2-digit position (counting from 1) of the card's report in `schema.REPORT_ORDER`. `card_anchor(cid)` returns the existing DOM id for cards drawn by the existing panels (they keep their old anchors, step 6), else `card_dom_id(cid)`. Put the table of existing anchors in `render.py` as `PANEL_ANCHORS = {"dossier.about": "dossier-build", "dossier.reports": "report-index", "dossier.changelog": "history", "overview.repository": "facts-git", "overview.contributors": "facts-contributors", "overview.dependencies": "facts-dependencies", "gaps.tracker": "tracker", "corrections.tracker": "corrections-list", "corrections.decisions": "resolutions-list"}` (check each value against the `pid` passed to `card(...)` today; stop and report if one differs). A unit test renders the page for a small fixture and asserts that every `href="#…"` in the questions table names an `id` that exists on the page. A non-card reference is plain text linking to its report anchor (`#overview`, `#dossier`, `#gaps`). No answering card gives "not answered in this version". Tier badge M.
  5. Use `summary_text(rep)` in `build_page`.
  6. Existing panels get their schema identity, with content and look unchanged: extend `card(...)` with an optional `cid` argument; when given, it takes the title and tier from the schema card (a unit test asserts each existing title string equals the schema title), adds ` data-card="<cid>"` after the `id` attribute, and puts `tier_badge(tier)` after the `</h2>` inside `<header>`. The `kind` (shade) argument is derived from the tier when `cid` is given (M → `fact`, otherwise `llm`), so the report index card changes from model shade to facts shade; all other existing cards already match. Pass `cid` at each call: `panel_dossier` → `dossier.about`; the report index → `dossier.reports`; `panel_history` → `dossier.changelog`; `panel_git` → `overview.repository`; `panel_contributors` → `overview.contributors`; `panel_dependencies` → `overview.dependencies`; `panel_gaps` → `gaps.tracker` (its title string changes from "Gap tracker" to "Tracker"; the anchor id `tracker` stays); `panel_corrections` → `corrections.tracker` and `corrections.decisions`. Keep every existing `pid` anchor.
  7. `panel_corrections`: always draw the second card. When there are no decisions it contains `<p>No confirmations or answers have been recorded yet.</p>` (today the card is absent).
  8. Order in report 01: `dossier.about`, `dossier.process`, `dossier.questions`, `dossier.reports`, `dossier.changelog`. `head_html` prints the question line and the tier key for every report (all 16 schemas have a `question`, and all reports now have badges).
  9. Risks: draw `panel_risk_counts` (unchanged) and then `schema_cards_html` for `risks.tracker` (the table card is now titled "Tracker" and carries a badge; with the question line and tier key from step 8, these are the only visible changes to report 14).
  10. Delete `panel_env`, `panel_secrets` and `PANELS_AFTER` (and its use in `build_page`); set `FACT_KEYS["env_vars"] = FACT_KEYS["secret_signals"] = "facts-git"` with the same kind of comment as `hot_files`. Keep `FACT_INFO` entries so the popovers still work. Digest check (block A) still applies; report 02 does not use these panels. (`docs/post-v1.md` already lists both panels as candidates to re-add after 1.0.0; do not edit it.)
- **Tests.** `head_html("overview", …)` equals the legacy literal string built by hand in the test; `head_html("entry", …, sch)` contains the question and the tier key and still contains `SHADE_KEY`; `head_html("overview", …, sch)` with the real overview schema, after `report_section.normalize`, equals the legacy string (the question and tier key are the only additions); `with_contents` of a page with a `data-card` card keeps the attribute and lists the title; a full `schema_cards_html` for `entry` with one filled table card and one pending card yields ids `c-entry-catalog`, `c-entry-startup` in that order.
- **Done-check.** Full suite passes; section 5 block A (unmigrated scratch copy, legacy report list) prints `OK`, and `grep -c 'data-card="dossier.process"' $SCR/home/encamp/dossier-encamp.html` prints `1`.
- **Commit.** `feat(dossier): draw schema reports with question lines and tier badges`

### M0-11. Switch to the new report list, and run the migration end to end

- [ ] **Goal.** The 16-report list is live; the encamp dossier (scratch copy) migrates, renders and passes V6.
- **Files.** Edit `scripts/render.py`; edit `scripts/dossier.py`; edit `tests/unit/scripts/test_render.py`, `tests/unit/scripts/test_schema_files.py`.
- **Steps.**
  1. `REPORTS` becomes (id, title, written by Claude?): `("dossier", "This dossier", False), ("overview", "This repository", True), ("reading", "Reading guide", True), ("entry", "Entry points", True), ("components", "Components", True), ("interactions", "Interactions", True), ("io", "Inputs and outputs", True), ("data", "Data model", True), ("behavior", "Behavior and tests", True), ("change", "Change and history", True), ("conventions", "Conventions", True), ("ops", "Build, run and ship", True), ("contributors", "Contributors", True), ("risks", "Risks", True), ("gaps", "Gaps", True), ("corrections", "Corrections", False)`.
  2. `NAV_GROUPS` = the groups in item 1, exactly: `[("Orientation", ["dossier", "overview", "reading", "entry"]), ("Design", ["components", "interactions", "io", "data"]), ("Behaviour and change", ["behavior", "change", "conventions"]), ("Operations and people", ["ops", "contributors", "risks"]), ("Tracking", ["gaps", "corrections"])]`.
  3. (Panels already removed in M0-10.)
  4. `dossier.py`: in `cmd_render`, add `"cards_filled"` and `"cards_pending"` to the printed summary, counted over schema reports as: a card entry with `blocks` or `entries` or `na` is filled, `pending` (or an absent writer-`claude` card) is pending. Put the counting in `render.card_counts(reports) -> (filled, pending)` and unit-test it.
  5. Tests: a test that `[r for r, _, _ in render.REPORTS]` equals `list(schema.REPORT_ORDER)`; that each schema file's `title` equals `render.TITLES[stem]`; that `NAV_GROUPS` contains every id in `REPORTS` exactly once; `BARE_REPORTS` unchanged. In `tests/unit/scripts/test_render.py::TestReportLayout`, change the one assertion `dict(render.NAV_GROUPS)["Tracking"] == ["risks", "gaps", "corrections"]` to `== ["gaps", "corrections"]` and add `"risks" in dict(render.NAV_GROUPS)["Operations and people"]`; every other existing assertion must still pass unchanged.
  6. End to end on a scratch copy (section 5, block B): migrate, render, then the checks in "Verification". Record the numbers in the commit message.
- **Done-check.** Full suite passes. Section 5 block B prints, in order: the migrate summary with `"cards_filled": 15`, `"cards_pending": 27`; the render summary with `"unresolved_citations": 0`, no line starting `error:`, `"cards_filled": 15`, `"cards_pending": 27`; and `OK` from the digest comparison.
- **Commit.** `feat(dossier): switch to the 16-report layout`

### M0-12. Version, interim notice, docs

- [ ] **Goal.** Bump the version and make sure a user running `/dossier build` is not led into a failure.
- **Files.** Edit `VERSION`; edit `SKILL.md`; edit `prompts/schema/README.md`; edit `README.md` (one line).
- **Steps.**
  1. `VERSION` contains `0.5.0` (single line, as now).
  2. `SKILL.md`: directly under the `/dossier build` heading add this paragraph: "**This version cannot yet write the new report layout.** `render` now needs reports in the card layout described in `prompts/schema/`. The prompts for it are not written yet. Do not start a build. Tell the user this, and offer the previous version of the skill." Do **not** document `migrate` in SKILL.md (it is a one-off tool for the M0 check, not a user command).
  3. `README.md`: after the sentence about `build`, add "Version 0.5.0 draws the new card layout; writing dossiers in that layout arrives in a later version."
  4. `prompts/schema/README.md`: add one paragraph saying that `scripts/migrate.py` and `scripts/migrate_map.json` exist only to convert the old encamp fixture for the M0 check and can be deleted once M2 can write the new layout (together with the fixture folder `tests/fixtures/encamp-m0/` and its line in `.gitignore`), and add the list of defaults marked † in M0-3 and M0-4.
- **Done-check.** `cat VERSION` prints `0.5.0`; `uv run scripts/dossier.py version` prints `dossier 0.5.0`; the full suite passes; `grep -n "cannot yet write" SKILL.md` finds the paragraph.
- **Commit.** `chore(dossier): bump to 0.5.0 and document the interim state`

### M0-13. Sign-off run

- [ ] **Goal.** Prove the exit criterion with the real tools and leave a record.
- **Files.** Edit this plan only (tick boxes, paste the output of the commands under "Verification results" at the end).
- **Steps.** Run every command in section 5 (blocks B, C, D). Open the screenshots named there and look at them. Paste the outputs. Do not run anything against `/home/nick/dev/dossiers/` or write into `FIX`.
- **Done-check.** Block B prints `OK`; block C prints `"problems": 0`; the full suite passes.
- **Commit.** `docs(dossier): record the M0 verification run in plan 005`

---

## 5. Verification

Set once per shell (a scratch directory outside the repository; any empty directory works):

```bash
SKILL=/home/nick/dev/projects/encamp/configs/user/claude/.claude/skills/dossier
FIX=$SKILL/tests/fixtures/encamp-m0
SCR=$(mktemp -d)
BASE=fe72cec488cb211edd6919154bf4d3ed68845e4e33b667a1874716a96bb63b59
export DOSSIER_HOME=$SCR/home DOSSIER_CONFIG=$SCR/cfg.json PYTHONDONTWRITEBYTECODE=1
cd $SKILL
```

`FIX`'s files are read-only, so every copy is made writable with `chmod -R u+w`. Every block deletes the copied page before rendering and checks that `render` succeeded, so a digest can never be taken of the old page by mistake.

**Block A: report 02 on the unmigrated copy** (use after M0-1, M0-5, M0-6, M0-10; the report list is still the old one, so the old reports render):

```bash
rm -rf $SCR/home && mkdir -p $SCR/home && cp -r $FIX $SCR/home/encamp && chmod -R u+w $SCR/home/encamp
rm $SCR/home/encamp/dossier-encamp.html
uv run scripts/dossier.py render /home/nick/dev/projects/encamp --allow-errors > $SCR/render.log; echo "render exit $?"
grep '^error:' $SCR/render.log | grep -v '^error: V6:' ; tail -3 $SCR/render.log
test -f $SCR/home/encamp/dossier-encamp.html && echo "page written" || echo "NO PAGE WRITTEN"
python3 tests/tools/report_section.py $SCR/home/encamp/dossier-encamp.html overview --digest --normalize | grep -q "^$BASE " && echo OK || echo DIFFERENT
```

Expected: `render exit 0`, no `error:` line other than `error: V6: …` lines, `page written`, `OK`. `--allow-errors` is needed because from M0-6 until M0-11 the old-layout `data`, `contributors` and `risks` files fail V6 (expected: those `error: V6:` lines name only those three reports and say "old layout"). On `DIFFERENT`, stop: write the section to a file with `--write`, diff it against the same call on `$FIX/dossier-encamp.html`, and fix the task that broke it.

**Block B: the exit criterion end to end** (the M0-11 and M0-13 check):

```bash
rm -rf $SCR/home && mkdir -p $SCR/home && cp -r $FIX $SCR/home/encamp && chmod -R u+w $SCR/home/encamp
rm $SCR/home/encamp/dossier-encamp.html
uv run scripts/dossier.py migrate /home/nick/dev/projects/encamp; echo "migrate exit $?"
uv run scripts/dossier.py render /home/nick/dev/projects/encamp; echo "render exit $?"
test -f $SCR/home/encamp/dossier-encamp.html && echo "page written" || echo "NO PAGE WRITTEN"
python3 tests/tools/report_section.py $SCR/home/encamp/dossier-encamp.html overview --digest --normalize | grep -q "^$BASE " && echo OK || echo DIFFERENT
export SCR
python3 - <<'PY'
import json, subprocess, sys, os
sys.path.insert(0, "scripts"); sys.path.insert(0, "tests/tools")
import report_section as rs, schema
html = open(os.environ["SCR"] + "/home/encamp/dossier-encamp.html", encoding="utf-8").read()
got = rs.cards(html)
for rid, sch in schema.load_all().items():
    want = [c["id"] for c in sch["cards"]]
    assert [c for c in got.get(rid, [])] == want, (rid, got.get(rid), want)
print("skeleton matches the schema for", len(schema.load_all()), "reports,", sum(len(v) for v in got.values()), "cards")
PY
cmp $SCR/home/encamp/reports/overview.json $FIX/reports/overview.json && echo "overview.json unchanged"
```

Expected: migrate prints `"cards_filled": 15, "cards_pending": 27`, lists 66 blocks not carried over, and `migrate exit 0`; `render exit 0`, `page written`; render prints no `error:` lines, `"unresolved_citations": 0`, `"cards_filled": 15`, `"cards_pending": 27`; then `OK`; `skeleton matches the schema for 16 reports, 65 cards` (cards drawn by code keep their content; `dossier.process` and 12 script cards are placeholders); `overview.json unchanged`.

**Block C: the page in a real browser** (SKILL.md step 7):

Encamp has no component detail entries yet, so first add one by hand to the migrated copy (it exercises the entries card and the search check; it is a test entry, not content):

```bash
python3 - <<'PY'
import json, os
p = os.environ["SCR"] + "/home/encamp/reports/components.json"
rep = json.load(open(p))
entry = {"component": "Installer", "fields": {"purpose": "Bootstraps a machine from the repository checkout.",
         "how_it_works": "Runs install steps in order.", "public_surface": "The install script.",
         "state_owned": "None.", "key_files": "README.md", "gotchas": "None recorded."},
         "conf": "confirmed", "cite": ["README.md"]}
rep["cards"] = [{"card": "components.detail", "entries": [entry]} if c.get("card") == "components.detail" else c for c in rep["cards"]]
json.dump(rep, open(p, "w"), indent=2)
PY
rm $SCR/home/encamp/dossier-encamp.html
uv run scripts/dossier.py render /home/nick/dev/projects/encamp > /dev/null; echo "render exit $?"
uv run scripts/check_page.py $SCR/home/encamp/dossier-encamp.html --shots $SCR/shots
```

Expected: `render exit 0`; last JSON line `"problems": 0` (this includes the new search check: searching for "Bootstraps" finds the Installer entry and opens it). Then open with the Read tool: `$SCR/shots/light-interactions-1.png` (the flows card: diagram, notes, expand button) and one screenshot of a report with placeholders. Look for badge overlap and for placeholders that look like content. Also open the page, go to Interactions, click the expand button on a diagram inside the Key flows card, and confirm it opens full-screen and closes with Esc (check_page does not test this).

**Block D: unit tests**

```bash
uv run --with pytest --with pygments python -m pytest tests -q
```

Expected: all pass (168 before M0, more after).

(Block E, "decisions survive", was dropped on 2026-11-01 together with M0-8.)

No real dossier is migrated. The human deletes the old dossiers in `/home/nick/dev/dossiers/` and rebuilds them once the 1.0.0 prompts exist. `FIX` stays as the M0 fixture until M2 no longer needs it.

---

## 6. Risks and open questions

### Risks (most important first)

1. **The page is mostly placeholders after M0.** For encamp, 22 of 88 written blocks (the Risks table included) are carried over; 66 are not shown (Appendix A). 15 of the 42 Claude-written cards have content, 27 are placeholders, and 12 of the 23 script cards are placeholders until M1 and later (the rest are existing panels or `dossier.questions`, drawn for real). This follows from the closed schema, which has no place for prose, C4 diagrams, capabilities, the error catalog or the "interfaces called" tables. The old content stays in the read-only fixture `FIX/reports/` (and in the scratch copy's `reports.legacy-v0.4.0/`). Nothing can refill the cards until the M2 prompts exist.
2. **`/dossier build` cannot produce a valid dossier between M0 and M2.** The prompts still describe the old layout; `render` will refuse such reports. Mitigations: the SKILL.md notice (M0-12), the version bump, and the clear "Run: dossier.py migrate" error. The user must not rely on building new dossiers until M2.
3. **Report 02 can be broken indirectly.** Shared code (`CARD_HEAD`, `SHADE_KEY`, code-viewer window planning, `with_contents`, CSS) touches 02's bytes. Guard: the normalized digest check after each render-touching task. The normalizer removes only card ids, tier badges, the question line and the tier key, so a mistake that hides a real change inside those would go unseen; the unit test for `--normalize` must stay strict. The check depends on the frozen fixture `FIX`.
4. (Removed 2026-11-01: saved decisions no longer have to survive, because no dossier is migrated for real.)
5. **The spec leaves about ten card shapes undefined** (marked † in M0-3 and M0-4, spec issues 2, 5, 8). The defaults I chose will need rework in M2 if the human prefers others. They are all in data files (`prompts/schema/*.json`), so a change is cheap now and costly after the M2 prompts are written.
6. **New markup is only partly checked by `check_page.py`.** The expand overlay for a diagram nested inside a card is not exercised by it; block C asks for a manual look. Search over collapsed entries is checked by the new `check_search` (M0-5), but only on the hand-added test entry, because encamp has no real entries yet.
7. **The version bump affects every dossier.** After 0.5.0 a `prepare` on any old dossier is a full build that cannot succeed until M2. This is accepted: the old dossiers are deleted and rebuilt after 1.0.0. I found no CI workflow or release tooling in the encamp repository (`.github` is absent at its root); I did not check whether any hook reacts to `VERSION`.
8. **I did not read** `gather.py` (1,243 lines), `deps.py`, `viewer.py`, or `dossier.js` in full, only the places that touch report ids, caps and the card markup. Item 21 (caps) is therefore incomplete.

### Questions for the human

**All answered; see "Human answers" at the top.** Nothing here is open, so the implementer does not stop for them. For the record, what was asked and what was decided:

- **D-Q1.** 66 of encamp's 88 written blocks are not shown until M2 (no holding area). Answered: accepted.
- **D-Q2.** Overview's "What to know first" and "Maturity and health" are dropped; "Technology" goes to `reading.technologies`. Answered: yes.
- **D-Q3.** Risks, Gaps and Corrections have no executive summary or contents. Answered: yes.
- **D-Q4.** The measured "Environment variables" and "Secret scan" panels. Answered: removed (listed in `docs/post-v1.md`).
- **D-Q5.** `VERSION` 0.5.0 and the SKILL.md notice. Answered: yes; no dossier is migrated for real, all are rebuilt.
- **D-Q6.** The defaults marked † in M0-3 and M0-4. Answered: accepted, to be reviewed later; `behavior.tests` gets fixed tables; reports 01, 02, 14, 15 and 16 get a question line (changed 2026-11-01).
- **D-Q7.** Navigation groups. Answered: as proposed.
- **D-Q8.** Tier-M cards get no migrated content. Answered: yes.

---

## 7. Spec issues

Not worked around in the plan, except where stated.

1. §8's example shows `"summary": ["...", "..."]` (a list); the code and prompts use a string of `- ` lines. The plan accepts both.
2. `data.entities` says "Claude adds purpose" but has no Purpose column. The old Entities table has one, so it is lost in migration.
3. Tier `M+A` appears on three cards but principle 3 defines only M, A, R and the shading rule. The plan treats it as a fourth badge with the model shade.
4. §4 says every report except Gaps and Corrections has Executive summary and Contents; the code (plan 001) also removes them from Risks.
5. Questions are given for reports 03 to 12 only; 01, 02, 13, 14, 15, 16 have none, yet "each report shows its question". The human decided all 16 reports show one. The plan uses question 8.1 for 13, question 10.1 for 15, and the texts marked † in M0-3 for 01, 02, 14 and 16. The spec should list these questions.
6. §4 (14) says Risks "gain a `Source` column value `extractor`". No `Source` column exists in the Risks table today (`RISK_COLUMNS` = ID, Risk, Category, Severity, Impact, Recommendation). The column itself must be added (M3).
7. Report ids are never named; `data` and `contributors` reuse old ids, so old and new files can be confused (handled by the `cards` key).
8. Underspecified shapes: `behavior.tests` (no columns), `change.hotspots` and `components.map` (table plus graph, no data format), `change.blast-radius`, `io.outputs` ("same shape"), the `ops.local` prerequisites table, `conventions.recipes` fields, and the confidence model of `components.detail` entries (the §8 example gives an entry no `conf` or `cite`, but every statement needs both).
9. §4 retires "Capabilities (folded into `components.catalog`)", but that card has no column for what a feature does for a user or its status (Implemented, Partial, …). Interfaces "split into 04 and 07" has no card for "interfaces called" or "network services exposed" tables. Prose-only content (C4 context and container diagrams, design patterns, quality attributes, portability caveats) has no card, and the schema has no optional notes. A per-card optional `notes` text would keep most of what M0 currently drops.
10. The measured environment-variable and secret-scan cards (today attached to Delivery) are not placed in the new design. Resolved: removed in M0 (Q4) and listed in `docs/post-v1.md` as candidates to re-add after 1.0.0.
11. Principle 7 ("no caps, nothing dropped to fit a limit") conflicts with report 02 (top 40 contributors, 10 tags, 16 calendar years, trimmed knowledge map and dependencies) and with the two panels above, but 02 is frozen "unchanged".
12. The M0 exit criterion says V6 passes for the existing dossier, but §8 defines no form for "no content yet". The plan adds `{"card": id, "pending": true}` and a switch to turn it off in M2.
13. "Byte-identical in content" for report 02 is ambiguous; the plan defines it as the SHA-256 of the report's HTML section.
14. §11 numbers two items "5." (the second should be 6, and the rest shift).
15. §12 says "Still to do in M1: 7. Pin the versions" while §10's M1 does not list it explicitly; harmless, but easy to miss.
16. `Risks gain a Source column` also means the `risks.tracker` columns change in M3; M0 uses today's six.
17. §4 (text above the table of existing cards in 01 and 02) says the three tracker cards in 14, 15 and 16 "are drawn by code, not written by Claude (`computed` shape)". That is true of the Gaps and Corrections trackers, but the Risks table is written by Claude today (`reports/risks.json`), and §4 (14) gives it fixed columns and tier A. This plan makes `risks.tracker` a Claude-written `blocks` card with one table slot (no row limit) and today's six columns. **Resolved 2026-11-01:** the human approved, and §4 of the spec now says that the Risks tracker is written by Claude and is part of the report schema, while the Gaps and Corrections trackers are dossier metadata drawn by code. Risks also moves to the "Operations and people" navigation group.

---

## Appendix A. What happens to encamp's current blocks

Old layout: 88 written blocks (`gaps.json` has items, not blocks).

**Carried over (22 blocks → 15 cards)**

| Old report › block | New card | Notes |
|---|---|---|
| code-tour › Reading order | `reading.order` | Phase = "Not yet recorded" |
| domain-logic › Domain concepts | `reading.glossary` | Where it lives = "Not yet recorded" |
| overview › Technology | `reading.technologies` | Idiom to know = "Not yet recorded" |
| code-tour › Entry points | `entry.catalog` | Triggered by, Starts at = "Not yet recorded" |
| architecture › Modules and components | `components.catalog` | Paths = "Not yet recorded" (the old table has no paths column; copying the component name there would show a wrong value as confirmed) |
| architecture › Cross-cutting concerns | `components.cross-cutting` | Where = "Not yet recorded"; fixed-row warnings expected |
| code-tour › Path 1, 2, 3 (diagram + notes each, 6 blocks), architecture › Dynamic view (diagram) | `interactions.flows` | Four flows |
| data › Entities and how they relate | `data.relationships` | |
| data › Entities | `data.entities` | Kind, Defined in = "Not yet recorded"; Purpose and Sensitivity are not carried |
| data › Data stores | `data.stores` | Retention is not carried |
| domain-logic › Rules and decisions | `behavior.rules` | Where decided = "Not yet recorded" |
| failures › Failure modes | `behavior.failures` | Same columns |
| delivery › Configuration + Secrets | `ops.config-secrets` | Needs both tables |
| contributors › Who to ask, by subsystem | `contributors.ask` | Then = "Not yet recorded" |
| risks › Risk register | `risks.tracker` | Same six columns; card is now titled "Tracker" |

**Not shown (66 blocks, all kept in the backup)**

- architecture (13): Level 1 system context, System summary, Level 2 containers, Containers, Authored code scope, Level 3 components, External dependencies and integrations, Key libraries and tools, Design patterns and decisions, Layering and dependency rules, Quality attributes, Decision records, Portability caveat.
- capabilities (3): all.
- code-tour (2): Where to find configuration, tests and build (would fill the tier-M card `reading.map`); Hard-to-read and most-changed areas.
- contributors (7): Who the people are, Ownership versus commit share, Where the shares are real and where they are not, Agents and bots, Knowledge concentration and departed people, Reading the knowledge map (belongs in the knowledge-map card's help text, per §4), Doubts about the classification.
- data (9): No persistent database, Flow 1 diagram, Data flow steps, Flow 2 diagram, Notes on flow 2, Flow 3 diagram, Validation migration and deletion, Sensitive data, Bulk vendored data.
- delivery (10): all except Configuration and Secrets.
- domain-logic (5): Scope, Workflow diagram, What each target provisions, Boundaries, Invariants assumptions and drift.
- failures (6): all except Failure modes (Error handling strategy, Error catalog, Resilience mechanisms, Observability of failure, Smaller code-level quirks, Main failure path).
- interfaces (9): all.
- overview (2): What to know first, Maturity and health (never drawn on report 02).

## Appendix B. `scripts/migrate_map.json`

```json
{
  "retired": {
    "capabilities": "components", "interfaces": "io", "architecture": "components",
    "domain-logic": "behavior", "code-tour": "reading", "failures": "behavior", "delivery": "ops",
    "data": "data", "contributors": "contributors", "overview": "overview", "risks": "risks", "gaps": "gaps"
  },
  "primary": {
    "reading": "code-tour", "entry": "code-tour", "components": "architecture", "interactions": "code-tour",
    "data": "data", "behavior": "domain-logic", "ops": "delivery", "contributors": "contributors", "risks": "risks"
  },
  "rules": [
    {"from": "code-tour", "type": "table", "heading": "^Reading order$", "to": "reading.order",
     "columns": {"Phase": null, "Step": "Step", "Read": "Read", "What you learn": "What you learn"}},
    {"from": "domain-logic", "type": "table", "heading": "^Domain concepts$", "to": "reading.glossary",
     "columns": {"Term": "Concept", "Meaning": "Meaning", "Where it lives": null}},
    {"from": "overview", "type": "table", "heading": "^Technology$", "to": "reading.technologies",
     "columns": {"Technology": "What is used", "Role here": "Area", "Idiom to know": null}},
    {"from": "code-tour", "type": "table", "heading": "^Entry points$", "to": "entry.catalog",
     "columns": {"Kind": "Kind", "Name": "Entry point", "Triggered by": null, "Starts at": null, "Notes": "What it does"}},
    {"from": "architecture", "type": "table", "heading": "^Modules and components$", "to": "components.catalog",
     "columns": {"Component": "Name", "Paths": null, "Responsibility": "Responsibility", "Public surface": "Key entry points",
                 "Depends on": "Depends on", "Used by": "Used by", "Size": "Approximate size"}},
    {"from": "architecture", "type": "table", "heading": "^Cross-cutting concerns$", "to": "components.cross-cutting",
     "columns": {"Concern": "Concern", "Approach": "How it is handled", "Where": null}},
    {"from": "code-tour", "type": "diagram", "mermaid": "^\\s*sequenceDiagram", "to": "interactions.flows", "notes": "following"},
    {"from": "architecture", "type": "diagram", "mermaid": "^\\s*sequenceDiagram", "to": "interactions.flows", "notes": "following"},
    {"from": "data", "type": "diagram", "mermaid": "^\\s*erDiagram", "to": "data.relationships"},
    {"from": "data", "type": "table", "heading": "^Entities$", "to": "data.entities",
     "columns": {"Name": "Name", "Kind": null, "Fields": "Key fields", "Defined in": null, "Owner component": "Owner module"}},
    {"from": "data", "type": "table", "heading": "^Data stores$", "to": "data.stores",
     "columns": {"Store": "Store", "Technology": "Technology", "Holds": "What it holds", "Migration approach": "Backup or migration approach"}},
    {"from": "domain-logic", "type": "table", "heading": "^Rules and decisions$", "to": "behavior.rules",
     "columns": {"Rule": "Rule or decision", "What it does": "What it does", "Where decided": null, "Edge cases": "Edge cases or caveats"}},
    {"from": "failures", "type": "table", "heading": "^Failure modes$", "to": "behavior.failures",
     "columns": {"ID": "ID", "Failure": "Failure", "Trigger": "Trigger", "Detection": "Detection", "Effect": "Effect", "Recovery": "Recovery"}},
    {"from": "delivery", "type": "table", "heading": "^Configuration$", "to": "ops.config-secrets",
     "columns": {"Setting": "Setting", "Default": "Default", "Overridden by": "How it is overridden"}},
    {"from": "delivery", "type": "table", "heading": "^Secrets$", "to": "ops.config-secrets",
     "columns": {"Secret": "Secret", "Unlocks": "What it unlocks", "Supplied how": "How it is supplied"}},
    {"from": "risks", "type": "table", "heading": "^(Risk register|Tracker)$", "to": "risks.tracker",
     "columns": {"ID": "ID", "Risk": "Risk", "Category": "Category", "Severity": "Severity", "Impact": "Impact", "Recommendation": "Recommendation"}},
    {"from": "contributors", "type": "table", "heading": "^Who to ask, by subsystem$", "to": "contributors.ask",
     "columns": {"Subsystem": "Subsystem", "Ask first": "Who", "Then": null, "Basis": "Why this is the answer"}}
  ]
}
```

A table rule's column map is keyed by the **new** column names and must list exactly the target slot's columns (a test checks this against the schema). The order of rules matters only for `interactions.flows` (code-tour paths first, then the architecture view) and `ops.config-secrets` (Configuration, then Secrets).

## Verification results

(To be pasted by the session that does M0-13.)
