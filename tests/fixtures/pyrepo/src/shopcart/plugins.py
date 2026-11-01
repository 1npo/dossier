import importlib

REGISTRY = {}  # @state-registry


def load(name):
    return importlib.import_module(name)  # @bs-import


def call(obj, name):
    return getattr(obj, name)()  # @bs-getattr


def register(fn):
    return fn


@register  # @bs-registry
def handler():
    return 1
