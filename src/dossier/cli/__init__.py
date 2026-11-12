"""dossier - command line behind the /dossier skill.

  dossier.py version
  dossier.py home [DIR]
  dossier.py doctor [REPO] [--all] [--json]                   list the tools a repository needs, which are installed and how to install the rest
  dossier.py clean [REPO]                                     remove the working area (clean copy, scratch home, caches) of a repository
  dossier.py prepare [REPO] [--ref REF] [--chunk-tokens N] [--full] [--allow-missing] [--no-restore] [--allow-ref] [--submodules] [--restore yes|no] [--verify]
                                                              check tools, make a clean copy, install locked dependencies if allowed, measure the repo, write facts, a reading plan and an update plan
  dossier.py render  [REPO] [--partial] [--allow-errors] [--readers N]      validate the reports and write the HTML
  dossier.py candidates [REPO] --report ID [--open] [--catalog FILE] [--json]
                                                              list the tool findings a report must keep, merge or dismiss (--open: only the undecided ones)
  dossier.py correct [REPO] ...                               record a user correction
  dossier.py confirm [REPO] [IDS] ...                         list open items, or confirm / answer / dispute them
  dossier.py verify-sample [REPO] [--seed S] [--per-report N]   pick cited claims for the independent check and print them as JSON
  dossier.py verify-record [REPO] --results FILE               record the checker's verdicts

The parser is in `parser`, the helpers every command shares are in `common`, and each group of
commands has a module in `commands/`. Called by `scripts/dossier.py` and `python -m dossier`.
"""

__all__ = ["main"]


def main() -> None:
    """Run the command line."""
    from dossier.cli.parser import build_parser

    a = build_parser().parse_args()
    a.fn(a)
