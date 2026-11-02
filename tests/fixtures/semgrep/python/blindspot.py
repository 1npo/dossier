# ruleid: dossier.python.blindspot.dynamic-import
mod = importlib.import_module(name)
# ruleid: dossier.python.blindspot.dynamic-import
mod2 = __import__("x")
# ok: dossier.python.blindspot.dynamic-import
importlib.reload(mod)

# ruleid: dossier.python.blindspot.entry-point-loading
eps = importlib.metadata.entry_points(group="x")
# ruleid: dossier.python.blindspot.entry-point-loading
eps2 = entry_points()
# ruleid: dossier.python.blindspot.entry-point-loading
pkg_resources.iter_entry_points("x")
# ruleid: dossier.python.blindspot.entry-point-loading
plugin_ep.load()
# ok: dossier.python.blindspot.entry-point-loading
config.load()

# ruleid: dossier.python.blindspot.string-plugin, dossier.python.blindspot.dynamic-import
importlib.import_module(f"plugins.{name}")
# ruleid: dossier.python.blindspot.string-plugin, dossier.python.blindspot.dynamic-import
importlib.import_module("plugins." + name)
# ruleid: dossier.python.blindspot.string-plugin, dossier.python.blindspot.dynamic-import
importlib.import_module("plugins.{}".format(name))
# ruleid: dossier.python.blindspot.string-plugin, dossier.python.blindspot.dynamic-import
__import__("plugins." + name)
# ok: dossier.python.blindspot.string-plugin
os.path.join("plugins.", name)


# ruleid: dossier.python.blindspot.decorator-registry
@registry.register("x")
def one():
    pass


# ruleid: dossier.python.blindspot.decorator-registry
@register
def two():
    pass


# ruleid: dossier.python.blindspot.decorator-registry
@bus.on("event")
def three():
    pass


# ruleid: dossier.python.blindspot.decorator-registry
@bus.handler()
def four():
    pass


# ok: dossier.python.blindspot.decorator-registry
@staticmethod
def five():
    pass


# ruleid: dossier.python.blindspot.getattr-dispatch
getattr(obj, name)()
# ruleid: dossier.python.blindspot.getattr-dispatch
getattr(obj, name, None)
# ok: dossier.python.blindspot.getattr-dispatch
getattr(obj, "name")

# ruleid: dossier.python.blindspot.django-apps
INSTALLED_APPS = ["a", "b"]
# ok: dossier.python.blindspot.django-apps
MIDDLEWARE = ["a"]


# ruleid: dossier.python.blindspot.django-signals
@receiver(post_save)
def on_save(sender, **kw):
    pass


# ruleid: dossier.python.blindspot.django-signals
post_save.connect(on_save)
# ruleid: dossier.python.blindspot.django-signals
request_started.connect(on_save)
# ok: dossier.python.blindspot.django-signals
button.connect(on_save)


# ruleid: dossier.python.blindspot.pytest-fixtures
@pytest.fixture
def items():
    return []


# ruleid: dossier.python.blindspot.pytest-fixtures
@pytest.fixture(scope="module")
def db():
    return None


# ok: dossier.python.blindspot.pytest-fixtures
@pytest.mark.skip
def test_x():
    pass


# ruleid: dossier.python.blindspot.computed-subcommand
commands.add_parser(name, help=help)

# ok: dossier.python.blindspot.computed-subcommand
commands.add_parser("serve", help="run the server")
