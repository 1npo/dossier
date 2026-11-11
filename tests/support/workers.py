"""Load a locked worker script as a module, so a test can call its functions.

The workers live in dossier's package data and run in their own environments under `uv run --script`;
they are not importable by name, so this loads one by path.
"""
import importlib.util
import sys

from dossier import resources


def load(name):
    """Import `resources.data("workers", f"{name}.py")` as module `name`, once, and return it."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, resources.data("workers", f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
