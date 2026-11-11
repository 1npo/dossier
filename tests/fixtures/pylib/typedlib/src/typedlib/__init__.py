"""A small typed library."""
from ._core import parse, Config  # @api-reexport

__all__ = ["parse", "Config", "VERSION"]

VERSION = "1"


def _helper():
    return None
