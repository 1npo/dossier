"""Argument parsing and one module per command group."""

__all__ = ["main"]


def main() -> None:
    """Run the command line."""
    from dossier.cli.parser import build_parser

    a = build_parser().parse_args()
    a.fn(a)
