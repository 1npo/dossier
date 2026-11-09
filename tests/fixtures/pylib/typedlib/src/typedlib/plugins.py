"""Plugins other packages can load."""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

Alias = int


class Fast:  # @api-fast
    def run(self, value: "Any"):
        return value


def _hidden():
    return None
