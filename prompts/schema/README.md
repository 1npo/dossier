# Card schema

One `<report>.json` file per report, listing its cards in page order. A report file written by Claude (`reports/<report>.json`) never repeats titles: each entry only names the card id (`{"card": "entry.catalog", "blocks": [...]}`), and the page takes the title, tier and shape from here. Checked by `scripts/schema.py` (check V6).

`questions.json` in this folder is the question list for the `dossier.questions` card. It is not a report schema.

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

- `tier`: `M` (measured), `A` (adjudicated), `R` (read) or `M+A`. `priority`: `P0` or `P1`.
- `writer`: `claude` or `script`. Tier `M` or shape `computed` means `script`; everything else means `claude`.
- `informational: true`: the card need not answer a question in `questions.json`.
- `shape`:
  - `blocks`: the card's blocks match `slots` in order. A slot is `{"type": "table|text|list|diagram", "columns": [...], "min": 1, "max": 1}`; `"max": null` means unlimited. A list slot with `"ordered": true` is drawn as a numbered list. Table columns must match exactly; a table with no rows is an error (use `na`).
  - `flows`: repeated `diagram` blocks, each optionally followed by one `text` or `list` block (its notes). Optional `max_diagrams`.
  - `entries`: each entry is `{<key>: "name", "fields": {<field id>: "text"}, "conf", "cite", "note"}`; all fields are required.
  - `computed`: filled by a script.
- `fixed` / `fixed2`: `{"on": "<column or entry key>", "values": [...]}`. A missing value is a warning, not an error. `fixed` applies to the first table slot, `fixed2` to the second.
- Not applicable, with evidence: `{"card": "<id>", "na": "reason", "cite": ["path:1-30"]}`.
- Not yet generated: `{"card": "<id>", "pending": true}` (accepted while `schema.ALLOW_PENDING` is true).

## Temporary tools and defaults

`scripts/migrate.py` and `scripts/migrate_map.json` exist only to convert the old encamp fixture for the M0 check. They can be deleted once M2 can write the new layout, together with the fixture folder `tests/fixtures/encamp-m0/` and its line in `.gitignore`.

Defaults the spec did not give (marked † in plan 005), open for review:

- The questions for reports 01 (`dossier`), 02 (`overview`), 13 (`contributors`), 14 (`risks`), 15 (`gaps`) and 16 (`corrections`).
- `io.outputs` columns: Category, Output, Format, Validation, Where written.
- `behavior.tests`: the second table (Question, Assessment, Evidence) and its two fixed rows.
- `conventions.recipes` fields: files to touch, worked example.
- `ops.local` prerequisites table: Prerequisite, Kind, Version or detail, Where stated.
