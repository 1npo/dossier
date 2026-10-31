Update the `dossier` skill (at ~/.claude/skills/dossier, or wherever it lives on this machine) to retire the word "profiler" and position the tool as "Codebase Intelligence". Keep the tool name `dossier`. Use targeted edits (str_replace), not file rewrites.

## Goal

The tool is a codebase intelligence report generator: it measures a git repository, then writes a cited, commit-pinned HTML dossier with every claim marked confirmed, inferred or unknown. "Profiler" undersells it and conflicts with that framing. The deterministic stage that counts things before Claude writes any report (`scripts/gather.py`, which produces `facts.json`) should be called the **fact gatherer**, and its output **measured facts**.

## Steps

1. Run `grep -rniE "profil" .` over the skill directory and use the hits as your worklist. The earlier hits were at roughly these places; verify them, don't trust the line numbers:
   - `scripts/render.py` (~49-107): `PROFILER_PATH = "dossier-profiler/gather.py"` (the name shown in the code viewer), the description strings ("counted by the profiler, not written by Claude"), the citation label built as `profiler facts: {k}`, and `profiler_source()` / `profiler_range()`.
   - `assets/dossier.js` (~324-334): the popover heading "Profiler facts:", the sentence "The profiler is the script that counts things…", and the button "View the profiler code".
   - `scripts/check_page.py` (~225-238): comments and failure messages mentioning "profiler facts" and "the profiler code button". Check that no selector or string match depends on the old label.
   - `prompts/method.md` (~108): "anything you or the profiler inferred". Also grep `prompts/reports.md` for the `profiler facts:` citation form, since that is where Claude is taught the label.
   - `README.md` (~36, ~38): two sentences about the explanation popover and about files "flagged by the profiler".
   - `scripts/dossier.py` (~10): help text "profile the repo, write facts…".
   - `docs/plans/000-code-viewer-plan.md`: historical plan note. Leave it alone.

2. Rename the product term:
   - "profiler" becomes "gatherer" (or "fact gatherer" where the first mention needs the full term).
   - "Profiler facts" becomes "Measured facts". Pick one wording and use it everywhere: the citation label, the popover heading, the check_page assertions, and the prompts.
   - `PROFILER_PATH` becomes `GATHERER_PATH = "dossier-gatherer/gather.py"`; `profiler_source` / `profiler_range` become `gatherer_source` / `gatherer_range`; update all callers.
   - Reword sentences so they still read naturally, e.g. "measured by the gatherer, not written by Claude".

3. Verb forms. `gather.profile()` and the words "profile" / "profiling" in comments and messages are a function name and a verb, not the product term. Rename `gather.profile()` to `gather.collect()` and update its callers (`scripts/dossier.py` ~195 and `tests/integration/scripts/test_knowledge_map.py` ~6). Change the warning in `gather.py` (~798) from "This profile covers the committed state only" to "This dossier covers the committed state only". Reword the comments at `gather.py` ~331, ~443, ~714 too. Warning: the line-range regexes in `render.py` (~73-75) anchor on `^def profile\(` and `# -+ main profile`. Change those patterns together with the code and comments they match, or the "view the code" ranges in the viewer will break.

4. Compatibility. The citation label is probably stored in report files of dossiers that were already built. Bump `VERSION`. SKILL.md says a new skill version forces a full rebuild, so no old label text survives. If you would rather not force rebuilds, make the citation parser in `render.py` accept both the old and the new label instead. Tell me which you chose.

5. Add the new positioning:
   - In the SKILL.md frontmatter `description`, use: "Build a cited, commit-pinned HTML dossier that explains a git repository: a codebase intelligence report generator that combines measured repository facts, architecture reconstruction, and confidence-labeled analysis (capabilities, architecture, data model, code tour, delivery, risks, contributors). Use for /dossier home, /dossier build, /dossier version, /dossier correct, /dossier confirm." Keep the existing frontmatter keys unchanged.
   - Update the first sentence of the README to describe it as a codebase intelligence report generator, and update the SKILL.md intro line if it conflicts.

## Verify

- Run `grep -rniE "profil" .` again. The only remaining hits should be the untouched plan doc. List any other remaining hits and justify them.
- Run the unit and integration tests (`uv run pytest` or whatever `tests/conftest.py` expects).
- Run `/dossier build` against a small git repo, then `uv run scripts/check_page.py <html> --shots <dir>` and confirm it prints `"problems": 0`. Open the measured-facts popover and the "View the gatherer code" button to confirm the code viewer still opens on the right line range.

Report a summary of what you changed, the compatibility choice from step 4, and anything you could not verify.