"""Argument parsing and one module per command group."""

__all__ = ["main"]


def main() -> None:
    """Run the command line. For now the whole CLI is `dossier.cli.app`; D1 splits it (plan 014, D8)."""
    from dossier.cli import app

    app.main()
