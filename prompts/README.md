# Prompts

Claude reads these files while it builds a dossier. `SKILL.md` names each one by path; no Python code loads them.

| File | Read at | What it holds |
|---|---|---|
| `method.md` | `SKILL.md` step 3 | how to read a repository and write a report |
| `reports.md` | `SKILL.md` step 3 | what each report contains, card by card |
| `verify.md` | `SKILL.md` step 7a | how to check a sample of claims against the code |

The card schemas that `method.md` and `reports.md` refer to are package data. They live in `src/dossier/data/schemas/cards/`, one JSON file per report.

`tests/content/test_prompts.py` checks the examples in `method.md` and `reports.md` against those schemas.
