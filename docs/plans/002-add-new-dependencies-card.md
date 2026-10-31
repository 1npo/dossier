Add a "Dependencies" card to the dossier report. A working reference implementation is at reference/dependency-card.html (self-contained HTML with mock data). It is the source of truth for look and behaviour. Port it into the dossier generator, replacing the mock data with real analysis output. Do not redesign it. If something here conflicts with the dossier's existing conventions, tell me before deviating.

## Context
The dossier is produced by a Claude Code skill and rendered as one self-contained HTML file styled with Basecoat UI. Each report is made of cards. Every card is built from cited facts or inferences from the repository. First read how an existing card (for example the contributor familiarity card) is built and wired in, and follow those conventions for the file layout, how data is embedded, theming and card registration. Use Basecoat classes for controls, tables and buttons where an equivalent exists, and keep the card's own visuals otherwise.

## Card anatomy, top to bottom
1. Title "Dependencies" (h2). No subtitle and no annotation on the right.
2. Five stat tiles. In each, an uppercase title is above the number and an optional lowercase subtitle is below it.
   - Declared: the total, with the runtime and dev counts as larger secondary numbers (titles above them) and a thin proportion bar.
   - Packages installed (subtitle "incl. transitive").
   - Declared, never imported (warn colour).
   - Imported, never declared (critical colour).
   - Runtime, used only in tests (warn colour).
3. A sortable findings table with columns Package, Finding, Scope and Detail. It has one row per package from the three finding types above and sits above the controls.
4. Controls, as segmented button groups with small uppercase labels above them:
   - View: By file (default, first), Ranked list, Module matrix, Treemap, Reliance plot, Module graph.
   - Rank by: Breadth (default), Spread, Depth.
   - Scope: All, Runtime, Dev.
   - Only in the By file view: Zoom (Top level, Modules, Folders [default], All files), Show (All paths [default], Only paths it touches) and Dependency (a searchable picker, described below).
5. The selected view.
6. A footer legend with swatches for source files (solid) and test files (hatched). Each view adds its own category-colour legend where relevant.

## Views
- **Ranked list**
  - Columns: Dependency (category swatch, name, version) | Scope pill | Pulls in | Source | Test | Breadth | Spread | Depth.
  - Breadth is a bar split into solid source and hatched test, scaled to the max file count in the current scope, with the total file count to the right of the bar. Spread is a bar of modules used, with "n/M" to the right. Depth is a bar of distinct symbols, with the count to the right.
  - Every column is sortable (click again to reverse). The default sort is the Rank by measure, descending, and changing Rank by resets any manual sort.
  - Show the top 12 with a "Show N more" row. Under 760px, hide Pulls in, Source, Test, Spread and Depth.
- **Module matrix**
  - Rows are modules and columns are the top 12 dependencies by the Rank by measure, grouped by the module that uses each most.
  - The cell number is the count of files importing it. Cell colour is the share of that module's files, as a mix of the sequential blue and the card surface. Use white text above about 50% mix.
- **Treemap**
  - Squarified, grouped by category, with area equal to the Rank by measure. Hide labels in cells that are too small. Tooltips carry the details.
- **Reliance plot**
  - x is files importing it, y is distinct symbols used, and circle area is the packages pulled in. Colour is by category. Label the top 8 with collision avoidance, and caption the corners "Deep, local", "Load-bearing" and "Wide, shallow".
- **Module graph**
  - Bipartite: modules on the left and the top 10 dependencies on the right.
  - Edge width is 1.5 + sqrt(files) × 1.1, coloured by the dependency's category. Hovering a node or edge highlights its edges.
- **By file**
  - A collapsible repository tree with three columns: Path | Imports by category | Top dependency.
    - The middle column is a 10px stacked bar of import pairs by category, with the import count beside it.
    - The third column shows the top dependency for a folder ("name n / N"), or up to two names plus "+n" for a file.
  - Zoom opens folders with depth < zoom − 1 (Top level=1, Modules=2, Folders=3, All files=99), and manual expand and collapse still works.
  - The Dependency picker is a searchable combobox (role="combobox" with a listbox, filter as you type, arrow keys, Enter and Escape). The first option, "All dependencies", is the default and clears the focus. When one dependency is chosen:
    - Bars become a single-colour share of the files in each path that import it, with a percentage.
    - The header reads "Share of files importing <name>", the third column becomes "Files importing n / N", and paths with none are dimmed.
    - The minimap shows the same.
  - Show = "Only paths it touches" hides every path with zero imports of the focused dependency.
    - It always needs a focused dependency, so the "All dependencies" option is removed and a default is chosen (the dependency with the most files).
    - Choosing another dependency re-applies the Zoom depth.
  - Minimap:
    - A canvas rail 68px wide (44px on phones) to the right of the tree, with one mini-bar per visible row.
    - Bars are indented by depth and stacked by category, or by intensity of the focused dependency.
    - It has a translucent viewport box, and click or drag scrolls the tree.
    - Redraw on scroll, resize, expand or collapse, focus change and theme change. Re-read the CSS variables on each draw and handle devicePixelRatio.
  - Keyboard: rows are role="treeitem" with aria-level and aria-expanded and a roving tabindex. Up and Down move, Right expands or moves to the first child, Left collapses or moves to the parent, Enter and Space toggle, and Home and End jump.
- **Tooltips** (not on touch) show:
  - Dependency rows: version, category, scope, source and test files, per-module counts, symbols, pulls in, and the relative breadth, spread and depth.
  - Tree rows: path, file and import counts, and the top 5 dependencies.

## Decisions already made. Do not reintroduce.
- No subtitle under the title and no annotation at the top right.
- No "Blend" ranking and no formula footnote.
- No Lock-in column, no Modules (squares) column and no separate Symbols column. Depth shows the symbol count.
- No dependency chips and no multi-select. The picker is a single searchable combobox.
- The By file view is always the default, first view on load. Do not persist the selected view. The Rank by and Scope choices may persist per viewer.
- Scope is only Runtime and Dev. Map the other labels as follows:
  - Build-time and test dependencies are Dev.
  - Peer, platform-provided and optional dependencies are Runtime.
  - Keep the manifest's own group name (for example `dev`, `docs` or `devDependencies`) on each dependency and show it in tooltips.
- Colour is by category (Framework, Data, Tooling, Testing, Utilities, plus a neutral grey "Other"), never one colour per dependency. Use the sequential blue only for magnitude and the matrix.
- Numbers sit to the right of the bars in the Breadth, Spread and Depth columns.

## Data contract
Replace the mock generator in the reference (mockFiles, LAYOUT, NOUNS, AFF, rngOf, shuffle and MODDIR) with real analysis output embedded as compact JSON in `<script type="application/json">`, escaping `<` as `\u003c`. Keep the tree-building code, which only needs `files`.
```json
{
  "transTotal": 412,
  "modules": [{"id": "api", "files": 108}],
  "deps": [{"n": "zod", "v": "3.23.8", "c": "Utilities", "s": "runtime", "group": "dependencies",
            "ecosystem": "npm", "src": 80, "tst": 7, "mods": {"api": 30, "web": 21},
            "sym": 9, "tr": 0}],
  "unused": [{"n": "moment", "v": "2.30.1", "s": "runtime", "note": "..."}],
  "undeclared": [{"n": "semver", "files": 4, "mods": {"cli": 3}, "via": "esbuild → semver"}],
  "files": [{"p": "apps/api/src/routes/invoice.route.ts", "t": 0, "m": "api", "d": ["fastify", "zod"]}]
}
```
`files[].d` lists the declared dependencies a file imports, and `t` is 1 for test files. The breadth, spread and depth values, the per-scope maxima, the file counts and the category mix are all computed in the page and not stored.

## Analysis requirements
- Produce this data from the repository, with an adapter per ecosystem. Support Python (pyproject.toml, requirements*.txt, Pipfile), C#, JavaScript/TypeScript/React/HTML/CSS, and shell. Design the adapter interface so Rust, Zig and C can be added later.
- Resolve imports to declared packages. This is where most of the work is: Python import names versus distribution names, C# namespaces versus NuGet package IDs, npm subpath imports. Treat workspace-internal packages and the standard library as not external dependencies.
- Decide test files by path and naming conventions, and assign each file to a module.
- Count `tr` (pulls in) as transitive packages from the lockfile if one exists. Otherwise leave it out.
- Findings logic:
  - Unused: declared and imported by no file, and not tooling that is used only through configuration (linters, bundlers, analyzers, pytest plugins). Do not flag those.
  - Undeclared: imported but not declared in a manifest, with the chain that provides it.
  - Runtime, used only in tests: scope is runtime, source files are zero and test files are more than zero.
- Category is assigned from a fixed lookup of known packages. Anything unknown goes to "Other" and should be marked as inferred if the dossier has a way to mark inferred values.

## Rendering constraints
- Self-contained HTML with no network requests at runtime. Use the dossier's fonts and theme tokens, not Google Fonts.
- Light and dark modes must follow the dossier's existing mechanism. Charts must be readable in both.
- Must work at 400px width with no horizontal page scroll (only tables and charts may scroll inside their own container). Respect prefers-reduced-motion and keep visible focus rings.

## Verify
Run the new card against this repository and one other repo you have available. Check every view and every control, the keyboard navigation in the tree, the console for errors, 400px width and dark mode. Compare screenshots of the real card against the reference rendered with its mock data, and tell me about any differences.
