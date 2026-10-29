# codebase-dossier

A Claude Code skill that reads a git repository and builds a single-file HTML dossier: short, cited reports on what the code does, how it's built, and where the risks are.

## Usage

Inside Claude Code:

```
/dossier home ~/dev/dossiers        # set where dossiers are saved (once)
/dossier build ~/dev/projects/foo   # build a dossier for a repo
/dossier confirm                    # list open questions, then answer them
/dossier correct                    # record something the dossier got wrong
/dossier version
```

`build` pins the dossier to a commit, writes eleven reports (overview, capabilities, interfaces, architecture, data, code tour, failures, delivery, risks, contributors, gaps), and renders them to `<home>/<repo-name>/` as one self-contained HTML page.

Every claim is marked confirmed, inferred, or unknown, and cites the files it came from. Your confirmations and corrections survive rebuilds.

## Install

Requires Claude Code and [uv](https://docs.astral.sh/uv/).

```sh
git clone git@github-1npo:1npo/codebase-dossier.git
cp -r codebase-dossier/dossier ~/.claude/skills/dossier
```

The skill is user-invoked only (`/dossier ...`); Claude won't trigger it on its own.

## License

No license for the skill itself yet. Bundled third-party libraries in `dossier/vendor/` keep their own licenses (`LICENSE.md`, `LICENSE-mermaid`).
