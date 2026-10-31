#!/usr/bin/env python3
"""Dependency analysis for the Dependencies card: which packages a repository declares, which of them its files
import, and where. Everything is read from git objects at the pinned commit.

One adapter per ecosystem reads the manifests (what is declared), the lockfile (versions and transitive packages) and
the source files (what is imported), and resolves each import to a declared package. To add an ecosystem (Rust, Zig,
C), write an Adapter subclass and add it to ADAPTERS. The result is the data contract that dossier.js embeds.
"""
from __future__ import annotations

import ast
import json
import re
import sys
import warnings
from collections import defaultdict, deque
from pathlib import PurePosixPath

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None

MAX_SOURCE = 1_000_000        # bytes; larger source files are not scanned
TEXT_CACHE = 150_000_000      # bytes of source text kept in memory between the two passes
MAX_FILES = 8000              # files embedded in the page; the rest are counted in the module totals only
MAX_MODULES = 16
VENDOR_SEG = {"node_modules", "vendor", "third_party", "third-party", "thirdparty", "bower_components", "Pods", "site-packages", ".yarn", "dist", "build", "target", ".venv", "venv"}
TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|specs?|e2e|cypress|playwright|testing)/|(^|/)[\w.\-]*(Tests?|Specs?)/|(^|/)(test_[^/]*|conftest)\.py$|_test\.(go|py|rb|exs?|c|cc|cpp|zig|rs|sh)$|\.(test|spec)\.[cm]?[jt]sx?$|Tests?\.(java|kt|cs)$|(^|/)test[-_][^/]*\.sh$|(^|/)[^/]*\.test\.sh$")
DEV_GROUP = re.compile(r"dev|test|lint|doc|build|\bci\b|typing|types?\b|check|bench|format|mypy|cov|tool|quality|style|e2e|spec", re.I)

CATEGORIES = ("Framework", "Data", "Tooling", "Testing", "Utilities")
_LOOKUP = {
    "Framework": """react react-dom next nuxt vue svelte angular express fastify koa hapi remix astro solid-js preact gatsby electron redux react-redux
        react-router react-router-dom vue-router pinia vuex mobx zustand django flask fastapi starlette tornado aiohttp sanic pyramid bottle falcon litestar quart
        textual streamlit gradio dash kivy pyqt5 pyqt6 pyside2 pyside6 nicegui flet blazor avalonia swashbuckle.aspnetcore hono trpc tauri expo react-native
        discord.py python-telegram-bot slack-bolt slack-sdk""",
    "Data": """sqlalchemy psycopg psycopg2 psycopg2-binary asyncpg pymysql mysqlclient mysql-connector-python sqlite-utils redis aioredis pymongo motor peewee
        tortoise-orm alembic pandas numpy scipy polars pyarrow duckdb sqlmodel elasticsearch boto3 botocore aiobotocore s3fs pg mysql mysql2 sqlite3
        better-sqlite3 mongodb mongoose ioredis knex typeorm sequelize prisma drizzle-orm bullmq kysely pg-promise neo4j neo4j-driver bull dexie lowdb
        dapper npgsql mongodb.driver mongodb.bson stackexchange.redis nhibernate elasticsearch.net system.data.sqlclient microsoft.data.sqlclient
        microsoft.data.sqlite sqlite-net-pcl supabase firebase firebase-admin firebase_admin pymssql cx-oracle oracledb clickhouse-driver apache-airflow
        pyspark dask""",
    "Tooling": """eslint prettier typescript webpack vite rollup esbuild parcel swc ts-node tsx nodemon concurrently husky lint-staged commander yargs
        chalk ora inquirer minimist cross-env rimraf turbo nx lerna babel-loader postcss tailwindcss autoprefixer sass less sass-loader css-loader
        style-loader terser ruff black flake8 mypy pyright isort pylint bandit pre-commit tox nox setuptools wheel hatchling hatch poetry-core poetry
        flit-core pdm-backend build twine pip uv click typer rich colorama tqdm invoke fabric watchdog docutils mkdocs mkdocs-material sphinx
        commitizen bump2version bumpversion pip-tools pipx virtualenv cython cffi pybind11 setuptools-scm hatch-vcs maturin
        coverlet.collector coverlet.msbuild minver nerdbank.gitversioning commandlineparser spectre.console cocona gulp grunt browserify
        nodemon-webpack-plugin semantic-release release-it standard-version npm-run-all dotenv-cli wrangler vercel netlify-cli serve http-server
        live-server browser-sync""",
    "Testing": """pytest coverage pytest-cov hypothesis mock responses factory-boy factory_boy faker freezegun selenium playwright cypress jest vitest mocha chai
        sinon supertest msw enzyme ava karma jasmine nock testcontainers moq nsubstitute fluentassertions bogus autofixture shouldly wiremock.net
        specflow microsoft.net.test.sdk xunit nunit mstest.testframework mstest.testadapter beautifulsoup4-test tox-uv pytest-asyncio pytest-mock
        respx vcrpy betamax docker-compose-test puppeteer webdriverio jsdom happy-dom ts-jest babel-jest c8 nyc istanbul""",
    "Utilities": """requests httpx urllib3 aiofiles pydantic pydantic-settings attrs cattrs dataclasses-json marshmallow python-dateutil dateutil pytz tzdata arrow
        pendulum pyyaml ruamel.yaml toml tomli tomli-w tomlkit jinja2 markupsafe orjson ujson simplejson lxml beautifulsoup4 bs4 pillow markdown mistune
        markdown-it-py pygments cachetools tenacity retrying backoff more-itertools toolz sortedcontainers six typing-extensions packaging platformdirs
        appdirs filelock psutil python-dotenv structlog loguru lodash lodash-es underscore ramda date-fns dayjs moment luxon axios node-fetch got
        cross-fetch ky superagent zod yup joi ajv uuid nanoid clsx classnames pino winston debug semver glob minimatch chokidar fs-extra immer
        rxjs core-js tslib dompurify marked highlight.js newtonsoft.json system.text.json automapper polly mediatr fluentvalidation humanizer
        csvhelper restsharp nlog serilog bouncycastle.cryptography sharpziplib nodatime protobuf grpcio grpcio-tools pycryptodome cryptography
        bcrypt passlib pyjwt jsonschema openpyxl xlrd xlsxwriter python-docx reportlab pypdf pypdf2 tabulate prettytable unidecode regex
        validators email-validator phonenumbers""",
}
CATEGORY_OF = {n: c for c, names in _LOOKUP.items() for n in names.split()}
CATEGORY_PREFIX = (
    ("pytest-", "Testing"), ("pytest_", "Testing"), ("@testing-library/", "Testing"), ("@playwright/", "Testing"), ("@vitest/", "Testing"), ("@jest/", "Testing"),
    ("@faker-js/", "Testing"), ("xunit", "Testing"), ("nunit", "Testing"), ("mstest", "Testing"), ("coverlet", "Testing"), ("verify.", "Testing"),
    ("@types/", "Tooling"), ("types-", "Tooling"), ("@babel/", "Tooling"), ("eslint-", "Tooling"), ("@eslint/", "Tooling"), ("@typescript-eslint/", "Tooling"),
    ("@vitejs/", "Tooling"), ("@storybook/", "Tooling"), ("@swc/", "Tooling"), ("stylecop", "Tooling"), ("sonaranalyzer", "Tooling"),
    ("microsoft.sourcelink", "Tooling"), ("mkdocs", "Tooling"), ("sphinx", "Tooling"), ("prettier-", "Tooling"), ("postcss-", "Tooling"),
    ("@angular/", "Framework"), ("@nestjs/", "Framework"), ("@sveltejs/", "Framework"), ("@radix-ui/", "Framework"), ("@tanstack/", "Framework"),
    ("@mui/", "Framework"), ("@emotion/", "Framework"), ("@reduxjs/", "Framework"), ("@remix-run/", "Framework"), ("@vue/", "Framework"),
    ("django-", "Framework"), ("djangorestframework", "Framework"), ("flask-", "Framework"), ("microsoft.aspnetcore", "Framework"),
    ("@aws-sdk/", "Data"), ("google-cloud-", "Data"), ("awssdk.", "Data"), ("azure.", "Data"), ("@azure/", "Data"), ("@prisma/", "Data"), ("sqlalchemy-", "Data"),
    ("microsoft.entityframeworkcore", "Data"), ("microsoft.extensions.", "Utilities"), ("serilog", "Utilities"), ("@sentry/", "Utilities"),
)


def category(name):
    key = name.lower()
    if key in CATEGORY_OF:
        return CATEGORY_OF[key]
    return next((c for p, c in CATEGORY_PREFIX if key.startswith(p)), "Other")


# --------------------------------------------------------------------------- shared helpers

def canon_py(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def semver_text(spec):
    """A manifest version spec shortened for display, or ''."""
    spec = (spec or "").strip()
    return "" if spec in ("*", "latest") else spec[:24]


class Lock:
    """Versions and the dependency graph read from a lockfile. `graph` is None when the lockfile format has no graph."""

    def __init__(self, versions=None, graph=None, total=0):
        self.versions, self.graph, self.total = versions or {}, graph, total

    def merge(self, other):
        self.versions.update(other.versions)
        if other.graph is not None:
            self.graph = {**(self.graph or {}), **other.graph}
        self.total += other.total

    def reach(self, key):
        """The keys reachable from `key` (not including it), or None when there is no graph."""
        if self.graph is None or key not in self.graph:
            return None
        seen, todo = set(), deque(self.graph[key])
        while todo:
            k = todo.popleft()
            if k in seen or k == key:
                continue
            seen.add(k)
            todo.extend(self.graph.get(k, ()))
        return seen

    def chain(self, roots, target):
        """The shortest chain of keys from any of `roots` to `target`, or None."""
        if self.graph is None:
            return None
        prev, todo = {r: None for r in roots}, deque(roots)
        while todo:
            k = todo.popleft()
            if k == target:
                out = []
                while k is not None:
                    out.append(k)
                    k = prev[k]
                return out[::-1]
            for n in self.graph.get(k, ()):
                if n not in prev:
                    prev[n] = k
                    todo.append(n)
        return None


class Ctx:
    """What an adapter can see: the paths at the commit, the manifests, and a cache of source text."""

    def __init__(self, repo, entries, files, is_test):
        self.repo, self.is_test = repo, is_test
        self.oid = {p: o for p, t, o, _ in entries if t == "blob"}
        self.size = {p: s for p, t, o, s in entries if t == "blob"}
        self.paths = sorted(self.oid)
        self.files = files
        self.config_text = ""            # scripts, task runners and CI files, for "used only through configuration"
        self._cache, self._cached = {}, 0

    def vendored(self, path):
        return bool(VENDOR_SEG.intersection(path.split("/")))

    def blob(self, path):
        got = self.repo.read(self.oid[path]) if path in self.oid else None
        return got[1].decode("utf-8", "replace") if got and b"\0" not in got[1][:4000] else None

    def text(self, path):
        if path in self._cache:
            return self._cache[path]
        t = self.blob(path)
        if t is not None and self._cached + len(t) < TEXT_CACHE:
            self._cache[path] = t
            self._cached += len(t)
        return t

    def find(self, pattern):
        rx = re.compile(pattern)
        return [p for p in self.paths if not self.vendored(p) and rx.search(p)]


def decl(name, spec, scope, group, manifest, key=None, internal=False):
    return {"name": name, "key": key, "spec": spec, "scope": scope, "group": group, "manifest": manifest, "internal": internal}


# --------------------------------------------------------------------------- adapters


class Adapter:
    eco = ""
    exts = ()
    mark_undeclared = True          # whether an import that matches nothing is reported as imported but never declared

    def norm(self, name):
        return name.lower()

    def handles(self, path):
        return path.rsplit(".", 1)[-1].lower() in self.exts if "." in path.rsplit("/", 1)[-1] else False

    def index(self, path, text, ctx):
        """First pass over every source file: collect what only the whole repository can tell (inline metadata, own namespaces)."""

    def declared(self, ctx):
        raise NotImplementedError

    def lock(self, ctx):
        return Lock()

    def scan(self, path, text, ctx):
        """The imports in one file, as [(specifier, {symbols})]."""
        raise NotImplementedError

    def resolve(self, spec, ctx, keys):
        """('dep', key) for a declared package, ('skip', None) for the standard library or the repository's own code, ('undeclared', key)."""
        raise NotImplementedError

    def tooling(self, d, ctx):
        """True for a package that is used through configuration rather than imports (linters, bundlers, test plugins)."""
        return False

    def mentioned(self, name, ctx):
        n = re.escape(name.lower())
        return bool(re.search(rf"(?<![\w@/.-]){n}(?![\w-])", ctx.config_text))


# ---- Python

PY_IMPORT_TO_DIST = {
    "PIL": "pillow", "yaml": "pyyaml", "cv2": "opencv-python", "sklearn": "scikit-learn", "bs4": "beautifulsoup4", "dateutil": "python-dateutil",
    "dotenv": "python-dotenv", "jwt": "pyjwt", "git": "gitpython", "attr": "attrs", "OpenSSL": "pyopenssl", "serial": "pyserial", "magic": "python-magic",
    "MySQLdb": "mysqlclient", "psycopg2": "psycopg2-binary", "Crypto": "pycryptodome", "skimage": "scikit-image", "docx": "python-docx", "pptx": "python-pptx",
    "markdown_it": "markdown-it-py", "ruamel": "ruamel.yaml", "zmq": "pyzmq", "usb": "pyusb", "fitz": "pymupdf", "lxml": "lxml", "mx": "egenix-mx-base",
    "gi": "pygobject", "wx": "wxpython", "Xlib": "python-xlib", "pkg_resources": "setuptools", "setuptools": "setuptools", "_pytest": "pytest", "pytest": "pytest",
    "msgpack": "msgpack", "snappy": "python-snappy", "slugify": "python-slugify", "telegram": "python-telegram-bot", "discord": "discord.py", "jose": "python-jose",
    "multipart": "python-multipart", "socks": "pysocks", "ldap": "python-ldap", "nacl": "pynacl", "tomli_w": "tomli-w", "yaml_include": "pyyaml-include",
    "playwright": "playwright", "grpc": "grpcio", "google.protobuf": "protobuf", "bson": "pymongo", "gridfs": "pymongo", "jinja2": "jinja2", "flask_cors": "flask-cors",
    "googleapiclient": "google-api-python-client", "google.oauth2": "google-auth", "google.auth": "google-auth", "google.api_core": "google-api-core",
    "google.cloud.pubsub_v1": "google-cloud-pubsub", "google.cloud.pubsub": "google-cloud-pubsub", "google.genai": "google-genai", "google.generativeai": "google-generativeai",
    "google.cloud.storage": "google-cloud-storage", "google.cloud.bigquery": "google-cloud-bigquery", "google.cloud.firestore": "google-cloud-firestore",
    "google.cloud.secretmanager": "google-cloud-secret-manager", "google.api": "googleapis-common-protos", "google.rpc": "googleapis-common-protos",
    "google.type": "googleapis-common-protos", "google.longrunning": "googleapis-common-protos", "google_auth_oauthlib": "google-auth-oauthlib", "google_auth_httplib2": "google-auth-httplib2",
    "pytest_socket": "pytest-socket", "attrs": "attrs", "markdown": "markdown", "sqlalchemy": "sqlalchemy", "mpl_toolkits": "matplotlib", "pylab": "matplotlib",
    "win32api": "pywin32", "win32com": "pywin32", "pythoncom": "pywin32", "tensorflow": "tensorflow", "torch": "torch", "azure.storage.blob": "azure-storage-blob",
}
PY_TOOLING = re.compile(r"^(setuptools|wheel|hatchling|hatch-.*|poetry-core|poetry|flit-core|pdm-backend|maturin|setuptools-scm|build|twine|pip|pip-tools|uv|virtualenv|"
                        r"ruff|black|flake8.*|mypy|pyright|isort|pylint|bandit|pre-commit|tox.*|nox|coverage|pytest-.*|pytest|types-.*|.*-stubs|mkdocs.*|sphinx.*|"
                        r"gunicorn|uvicorn|hypercorn|daphne|commitizen|bump2version|bumpversion|cython|pyinstaller|cx-freeze|py2exe|check-manifest|pylint-.*|autopep8|yapf|"
                        r"sphinx-.*|flake8|codespell|vulture|radon|pydocstyle|pycodestyle|pyflakes|interrogate|pre-commit-hooks|playwright)$")
PY_NAMESPACES = {"google", "azure", "ruamel", "jaraco", "backports", "sphinxcontrib"}
INLINE_META = re.compile(r"(?m)^# /// script\s*$\n((?:^#(?: .*)?\s*$\n)+?)^# ///\s*$")


class PythonAdapter(Adapter):
    eco = "python"
    exts = ("py", "pyi", "pyw")

    def __init__(self):
        self.inline, self.roots, self.projects = [], set(), set()
        self.stdlib = set(getattr(sys, "stdlib_module_names", ())) | {"__future__"}

    def norm(self, name):
        return canon_py(name)

    def index(self, path, text, ctx):
        parts = path.split("/")
        self.roots.update(p for p in parts[:-1] if p.isidentifier())
        stem = parts[-1].rsplit(".", 1)[0]
        if stem.isidentifier() and stem != "__init__":
            self.roots.add(stem)
        if "# /// script" in text:
            m = INLINE_META.search(text)
            if m and tomllib:
                body = "\n".join(l[2:] if l.startswith("# ") else "" for l in m.group(1).splitlines())
                try:
                    for spec in tomllib.loads(body).get("dependencies", []):
                        self.inline.append((spec, path))
                except Exception:
                    pass

    @staticmethod
    def _req(spec):
        m = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9_.\-]*)(?:\[[^\]]*\])?\s*(.*)$", spec)
        return (m.group(1), m.group(2).split(";")[0].strip()) if m else (None, "")

    def declared(self, ctx):
        out = []

        def add(items, scope, group, manifest):
            for s in items:
                if isinstance(s, str):
                    n, v = self._req(s)
                    if n and n.lower() != "python":
                        out.append(decl(n, v, scope, group, manifest))

        for path in ctx.find(r"(^|/)pyproject\.toml$"):
            try:
                j = tomllib.loads(ctx.blob(path) or "") if tomllib else {}
            except Exception:
                continue
            p, tool = j.get("project", {}), j.get("tool", {})
            poetry = tool.get("poetry", {})
            for n in (p.get("name"), poetry.get("name")):
                if n:
                    self.projects.add(canon_py(n))
            add(p.get("dependencies", []), "runtime", "dependencies", path)
            for grp, items in (p.get("optional-dependencies") or {}).items():
                add(items, "dev" if DEV_GROUP.search(grp) else "runtime", grp, path)
            for grp, items in (j.get("dependency-groups") or {}).items():
                add(items, "dev", grp, path)
            add((tool.get("uv") or {}).get("dev-dependencies", []), "dev", "dev-dependencies", path)
            add((j.get("build-system") or {}).get("requires", []), "dev", "build-system", path)
            for grp, tbl, dev in [("dependencies", poetry.get("dependencies"), False), ("dev-dependencies", poetry.get("dev-dependencies"), True)] + [
                    (g, (v or {}).get("dependencies"), g != "main") for g, v in (poetry.get("group") or {}).items()]:
                for n, v in (tbl or {}).items():
                    if n.lower() != "python":
                        out.append(decl(n, v if isinstance(v, str) else (v.get("version", "") if isinstance(v, dict) else ""), "dev" if dev else "runtime", grp, path))
        for path in ctx.find(r"(^|/)requirements[^/]*\.txt$"):
            base = path.rsplit("/", 1)[-1]
            for line in (ctx.blob(path) or "").splitlines():
                line = line.split(" #")[0].split("#")[0].strip()
                if line and not line.startswith(("-", "git+", "http", ".", "/")):
                    add([line], "dev" if DEV_GROUP.search(base) else "runtime", base, path)
        for path in ctx.find(r"(^|/)Pipfile$"):
            try:
                j = tomllib.loads(ctx.blob(path) or "") if tomllib else {}
            except Exception:
                continue
            for grp, scope in (("packages", "runtime"), ("dev-packages", "dev")):
                for n, v in (j.get(grp) or {}).items():
                    out.append(decl(n, v if isinstance(v, str) else (v.get("version", "") if isinstance(v, dict) else ""), scope, grp, path))
        add([s for s, _ in self.inline], "runtime", "script", "inline script metadata")
        return out

    def lock(self, ctx):
        lock = Lock(graph={})
        found = False
        for path in ctx.find(r"(^|/)uv\.lock$|(^|/)poetry\.lock$"):
            try:
                j = tomllib.loads(ctx.blob(path) or "") if tomllib else {}
            except Exception:
                continue
            found = True
            for pkg in j.get("package", []):
                n = canon_py(pkg.get("name", ""))
                src = pkg.get("source") or {}
                if not n or "virtual" in src or "editable" in src:
                    continue
                lock.versions[n] = pkg.get("version", "")
                deps = pkg.get("dependencies", [])
                lock.graph[n] = [canon_py(d["name"]) if isinstance(d, dict) else canon_py(d) for d in (deps if isinstance(deps, list) else list(deps))]
                lock.total += 1
            # a uv workspace root lists its own dependencies under a virtual/editable entry
            for pkg in j.get("package", []):
                src = pkg.get("source") or {}
                if "virtual" in src or "editable" in src:
                    for d in pkg.get("dependencies", []):
                        lock.graph.setdefault("", []).append(canon_py(d["name"]))
        for path in ctx.find(r"(^|/)Pipfile\.lock$"):
            try:
                j = json.loads(ctx.blob(path) or "{}")
            except Exception:
                continue
            found = True
            for grp in ("default", "develop"):
                for n, v in (j.get(grp) or {}).items():
                    lock.versions[canon_py(n)] = str(v.get("version", "")).lstrip("=")
                    lock.total += 1
            lock.graph = None if not lock.graph else lock.graph
        return lock if found else Lock()

    def scan(self, path, text, ctx):
        out = []
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tree = ast.parse(text)
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            for m in re.finditer(r"^[ \t]*(?:from[ \t]+([A-Za-z_][\w.]*)[ \t]+import|import[ \t]+([A-Za-z_][\w.]*))", text, re.M):
                out.append((m.group(1) or m.group(2), {"*"}))
            return out
        aliases, used = {}, defaultdict(set)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    aliases[(a.asname or a.name.split(".")[0])] = a.name
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                if node.module.split(".")[0] in PY_NAMESPACES:      # the imported name picks the distribution: from google.cloud import storage
                    out += [(f"{node.module}.{a.name}", {a.name}) for a in node.names]
                else:
                    out.append((node.module, {a.name for a in node.names}))
            elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                used[node.value.id].add(node.attr)
        for alias, mod in aliases.items():
            out.append((mod, used.get(alias) or {mod.split(".")[0]}))
        return out

    def resolve(self, spec, ctx, keys):
        root = spec.split(".")[0]
        if root in self.stdlib or root == "__future__":
            return "skip", None
        parts = spec.split(".")
        cands = [canon_py(PY_IMPORT_TO_DIST[".".join(parts[:i])]) for i in range(len(parts), 0, -1) if ".".join(parts[:i]) in PY_IMPORT_TO_DIST][:1] + [canon_py(root)]
        cands += [canon_py("-".join(parts[:i])) for i in range(2, min(len(parts), 4) + 1)]
        for c in cands:
            if c and c in keys:
                return "dep", c
        r = canon_py(root)
        for k in keys:      # python-dotenv for dotenv, pytest-foo for pytest_foo, foo-python for foo
            if re.sub(r"^(python|py)-|-(python|py|binary|lib)$", "", k) == r:
                return "dep", k
        if root in self.roots or r in self.projects:
            return "skip", None
        return "undeclared", cands[0]

    def tooling(self, d, ctx):
        n = d["key"]
        return bool(PY_TOOLING.match(n)) or d["group"] == "build-system" or bool(re.search(rf"\[tool\.{re.escape(n)}\b", ctx.config_text)) or self.mentioned(n, ctx)


# ---- JavaScript, TypeScript, React, HTML and CSS

NODE_BUILTINS = set("""assert async_hooks buffer child_process cluster console constants crypto dgram diagnostics_channel dns domain events fs http http2 https inspector
    module net os path perf_hooks process punycode querystring readline repl stream string_decoder sys timers tls trace_events tty url util v8 vm wasi worker_threads zlib""".split())
JS_TOOLING = re.compile(r"^(@types/.*|typescript|eslint(-.*)?|@eslint/.*|@typescript-eslint/.*|prettier(-.*)?|webpack(-.*)?|.*-loader|.*-webpack-plugin|vite|vite-plugin-.*|@vitejs/.*|rollup(-.*)?|"
                        r"@rollup/.*|esbuild|parcel|@babel/.*|babel-.*|postcss(-.*)?|autoprefixer|tailwindcss|@tailwindcss/.*|sass|less|stylelint(-.*)?|ts-node|tsx|ts-jest|tsup|"
                        r"nodemon|concurrently|husky|lint-staged|cross-env|rimraf|npm-run-all|turbo|nx|lerna|jest(-.*)?|vitest|mocha|karma(-.*)?|c8|nyc|cypress|"
                        r"@playwright/test|playwright|ts-loader|tslib|core-js|regenerator-runtime|@swc/.*|semantic-release|@semantic-release/.*|release-it|commitlint|@commitlint/.*|"
                        r"wrangler|serve|http-server|live-server|browser-sync|dotenv-cli|typedoc|storybook|@storybook/.*|knip|depcheck|size-limit|@size-limit/.*)$")


class JavaScriptAdapter(Adapter):
    eco = "npm"
    exts = ("js", "jsx", "mjs", "cjs", "ts", "tsx", "mts", "cts", "vue", "svelte", "astro", "html", "htm", "css", "scss", "sass", "less")

    def __init__(self):
        self.internal, self.local = set(), set()
        self.scripts = []

    def index(self, path, text, ctx):
        parts = path.split("/")
        self.local.update(p for p in parts[:-1] if p)
        self.local.add(parts[-1].rsplit(".", 1)[0])

    def declared(self, ctx):
        out = []
        for path in ctx.find(r"(^|/)package\.json$"):
            try:
                j = json.loads(ctx.blob(path) or "")
            except Exception:
                continue
            if not isinstance(j, dict):
                continue
            if isinstance(j.get("name"), str):
                self.internal.add(j["name"].lower())
            self.scripts += [str(v) for v in (j.get("scripts") or {}).values()]
            for grp, scope in (("dependencies", "runtime"), ("devDependencies", "dev"), ("peerDependencies", "runtime"), ("optionalDependencies", "runtime")):
                for n, v in (j.get(grp) or {}).items():
                    spec = v if isinstance(v, str) else ""
                    out.append(decl(n, spec, scope, grp, path, internal=spec.startswith(("workspace:", "file:", "link:"))))
        ctx.config_text += "\n".join(self.scripts).lower()
        return out

    def lock(self, ctx):
        lock, found = Lock(graph={}), False
        for path in ctx.find(r"(^|/)package-lock\.json$"):
            try:
                j = json.loads(ctx.blob(path) or "")
            except Exception:
                continue
            found = True
            pk = j.get("packages")
            if pk:
                seen = set()
                for k, v in pk.items():
                    if not k or "node_modules/" not in k:
                        continue
                    n = k.rsplit("node_modules/", 1)[1]
                    if v.get("link"):
                        continue
                    seen.add((n, v.get("version", "")))
                    if k.count("node_modules/") == 1:
                        lock.versions[n.lower()] = v.get("version", "")
                    lock.graph.setdefault(n.lower(), [])
                    lock.graph[n.lower()] += [d.lower() for d in {**(v.get("dependencies") or {}), **(v.get("optionalDependencies") or {})}]
                lock.total += len(seen)
            else:
                def walk(deps):
                    for n, v in (deps or {}).items():
                        lock.versions.setdefault(n.lower(), v.get("version", ""))
                        lock.graph.setdefault(n.lower(), []).extend(d.lower() for d in (v.get("requires") or {}))
                        lock.total += 1
                        walk(v.get("dependencies"))
                walk(j.get("dependencies"))
        for path in ctx.find(r"(^|/)yarn\.lock$"):
            found = True
            name, ver, mode = None, "", None
            for line in (ctx.blob(path) or "").splitlines():
                if not line.strip() or line.startswith("#"):
                    continue
                if not line.startswith(" "):
                    head = line.rstrip(":").split(",")[0].strip().strip('"')
                    name = head.rsplit("@", 1)[0] if "@" in head[1:] else head
                    if name.startswith("npm:"):
                        name = None
                    mode = None
                    if name:
                        lock.total += 1
                        lock.graph.setdefault(name.lower(), [])
                elif name and re.match(r"^  version:? ", line):
                    lock.versions.setdefault(name.lower(), line.split(None, 1)[1].strip().strip('"'))
                elif name and re.match(r"^  (optionalD|d)ependencies:", line):
                    mode = "deps"
                elif name and mode == "deps" and line.startswith("    "):
                    lock.graph[name.lower()].append(line.strip().split()[0].strip('":').lower())
                else:
                    mode = None
        for path in ctx.find(r"(^|/)pnpm-lock\.yaml$"):
            found = True
            sections, section, name, mode = {}, None, None, None
            for line in (ctx.blob(path) or "").splitlines():
                m = re.match(r"^(\w+):\s*$", line)
                if m:
                    section, name = m.group(1), None
                    sections.setdefault(section, {})
                elif section not in ("packages", "snapshots"):
                    continue
                elif re.match(r"^  \S", line):
                    name = re.sub(r"\(.*$", "", line.strip().rstrip(":").strip("'\"").lstrip("/")).rsplit("@", 1)[0].lower()
                    sections[section].setdefault(name, [])
                    mode = None
                elif name and re.match(r"^    (optionalD|d)ependencies:", line):
                    mode = "deps"
                elif name and mode == "deps" and line.startswith("      "):
                    sections[section][name].append(line.strip().split(":")[0].strip("'\"").lower())
                elif name and re.match(r"^    \S", line):
                    mode = None
            for n, ds in (sections.get("snapshots") or sections.get("packages") or {}).items():
                lock.graph.setdefault(n, []).extend(ds)
            lock.total += len(sections.get("packages", {}))
        return lock if found else Lock()

    CDN = re.compile(r"(?:cdn\.jsdelivr\.net/npm/|unpkg\.com/|esm\.sh/|cdn\.skypack\.dev/)((?:@[\w.\-]+/)?[\w.\-]+)|cdnjs\.cloudflare\.com/ajax/libs/([\w.\-]+)/|node_modules/((?:@[\w.\-]+/)?[\w.\-]+)")

    def scan(self, path, text, ctx):
        ext = path.rsplit(".", 1)[-1].lower()
        out = []
        if ext in ("html", "htm"):
            for m in re.finditer(r"""<(?:script|link)\b[^>]*?\b(?:src|href)\s*=\s*["']([^"']+)["']""", text, re.I):
                c = self.CDN.search(m.group(1))
                if c:
                    out.append((next(g for g in c.groups() if g), {"*"}))
            text = "\n".join(re.findall(r"<script\b[^>]*>(.*?)</script>", text, re.S | re.I))
        elif ext in ("css", "scss", "sass", "less"):
            for m in re.finditer(r"""@(?:import|use|forward)\s+(?:url\(\s*)?["']?([^"')\s;]+)""", text):
                s = m.group(1).lstrip("~")
                if not s.startswith((".", "/", "http", "data:", "sass:")) and ":" not in s:
                    out.append((s, {"*"}))
            return out
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        text = re.sub(r"(?m)^\s*//.*$", "", text)
        for m in re.finditer(r"""\bimport\s+(?:type\s+)?([^'"();]*?)\s*from\s*['"]([^'"\n]+)['"]""", text):
            out.append((m.group(2), self._clause(m.group(1), text)))
        for m in re.finditer(r"""\bexport\s+(?:type\s+)?(\*(?:\s+as\s+[\w$]+)?|\{[^}]*\})\s*from\s*['"]([^'"\n]+)['"]""", text):
            out.append((m.group(2), self._clause(m.group(1), text)))
        for m in re.finditer(r"""\bimport\s*['"]([^'"\n]+)['"]""", text):
            out.append((m.group(1), {"*"}))
        for m in re.finditer(r"""\bimport\(\s*['"]([^'"\n]+)['"]\s*\)""", text):
            out.append((m.group(1), {"*"}))
        for m in re.finditer(r"""(?:(?:const|let|var)\s+(\{[^}]*\}|[\w$]+)\s*=\s*)?(?:await\s+)?\brequire\(\s*['"]([^'"\n]+)['"]\s*\)(\.[\w$]+)?""", text):
            lhs, spec, tail = m.groups()
            syms = {tail[1:]} if tail else self._clause(lhs, text) if lhs else {"*"}
            out.append((spec, syms))
        return out

    @staticmethod
    def _clause(clause, text):
        """The symbols an import clause brings in: named imports, plus the members used on a default or namespace alias."""
        syms = set()
        clause = (clause or "").strip()
        if clause == "*":
            return {"*"}
        for grp in re.findall(r"\{([^}]*)\}", clause):
            for part in grp.split(","):
                n = re.sub(r"^type\s+", "", part.strip()).split(" as ")[0].strip()
                if n:
                    syms.add(n)
        rest = re.sub(r"\{[^}]*\}", "", clause)
        for alias in re.findall(r"(?:\*\s+as\s+)?([A-Za-z_$][\w$]*)", rest):
            members = set(re.findall(rf"(?<![\w$.]){re.escape(alias)}\.([A-Za-z_$][\w$]*)", text))
            syms |= members or {"default" if not rest.strip().startswith("*") else "*"}
        return syms or {"*"}

    def resolve(self, spec, ctx, keys):
        if spec.startswith((".", "/", "#", "~", "$", "@/", "%")) or ":" in spec or spec.startswith(("http", "data")):
            return "skip", None
        parts = spec.split("/")
        root = "/".join(parts[:2]) if spec.startswith("@") and len(parts) > 1 else parts[0]
        k = root.lower()
        if k in NODE_BUILTINS or k in self.internal:
            return "skip", None
        if k in keys:
            return "dep", k
        if root in self.local and not spec.startswith("@"):
            return "skip", None        # a bare path through tsconfig baseUrl or a path alias
        return "undeclared", k

    def tooling(self, d, ctx):
        return bool(JS_TOOLING.match(d["key"])) or self.mentioned(d["key"], ctx)


# ---- C#

CS_FRAMEWORK = re.compile(r"^(System|Microsoft|Windows|Mono)(\.|$)")
CS_ALIAS = {"xunit": ("xunit", "xunit.core", "xunit.assert", "xunit.abstractions"), "nunit.framework": ("nunit",),
            "microsoft.visualstudio.testtools.unittesting": ("mstest.testframework", "mstest", "mstest.testadapter"),
            "newtonsoft.json": ("newtonsoft.json",), "nsubstitute": ("nsubstitute",)}
CS_TOOLING = re.compile(r"(analyzers?|stylecop|sonaranalyzer|coverlet|\.testadapter|runner\.visualstudio|sourcelink|minver|gitversioning|^microsoft\.net\.test\.sdk$|"
                        r"^microsoft\.build|\.build\.|^dotnet-|roslynator)", re.I)


class CSharpAdapter(Adapter):
    eco = "nuget"
    exts = ("cs",)

    def __init__(self):
        self.own = set()
        self.names = []

    def index(self, path, text, ctx):
        for m in re.finditer(r"(?m)^\s*namespace\s+([\w.]+)", text):
            self.own.add(m.group(1))

    def declared(self, ctx):
        out, central = [], {}
        for path in ctx.find(r"(^|/)(Directory\.Packages\.props)$"):
            for m in re.finditer(r"<PackageVersion\s+[^>]*?Include=\"([^\"]+)\"[^>]*?Version=\"([^\"]+)\"", ctx.blob(path) or ""):
                central[m.group(1).lower()] = m.group(2)
        for path in ctx.find(r"\.(cs|fs|vb)proj$"):
            text = ctx.blob(path) or ""
            stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            self.own.add(stem)
            for tag in ("RootNamespace", "AssemblyName"):
                m = re.search(rf"<{tag}>([^<]+)<", text)
                if m:
                    self.own.add(m.group(1).strip())
            test_project = "Microsoft.NET.Test.Sdk" in text or bool(re.search(r"<IsTestProject>\s*true", text, re.I)) or bool(re.search(r"\.?Tests?$", stem))
            for m in re.finditer(r"<PackageReference\b([^>]*?)(/>|>(.*?)</PackageReference>)", text, re.S):
                attrs, body = m.group(1), m.group(3) or ""
                name = re.search(r"(?:Include|Update)=\"([^\"]+)\"", attrs)
                if not name:
                    continue
                ver = re.search(r"Version=\"([^\"]+)\"", attrs) or re.search(r"<Version>([^<]+)<", body)
                ver = ver.group(1) if ver else central.get(name.group(1).lower(), "")
                priv = re.search(r"PrivateAssets=\"all\"|<PrivateAssets>\s*all", attrs + body, re.I)
                dev = test_project or bool(priv) or bool(CS_TOOLING.search(name.group(1)))
                out.append(decl(name.group(1), ver, "dev" if dev else "runtime", "PackageReference", path))
        for path in ctx.find(r"(^|/)packages\.config$"):
            for m in re.finditer(r"<package\s+id=\"([^\"]+)\"\s+version=\"([^\"]+)\"([^>]*)", ctx.blob(path) or ""):
                out.append(decl(m.group(1), m.group(2), "dev" if "developmentDependency" in m.group(3) else "runtime", "packages.config", path))
        return out

    def lock(self, ctx):
        lock, found = Lock(graph={}), False
        seen = set()
        for path in ctx.find(r"(^|/)packages\.lock\.json$"):
            try:
                j = json.loads(ctx.blob(path) or "")
            except Exception:
                continue
            found = True
            for fw in (j.get("dependencies") or {}).values():
                for n, v in fw.items():
                    if v.get("type") == "Project":
                        continue
                    k = n.lower()
                    lock.versions[k] = v.get("resolved", "")
                    lock.graph.setdefault(k, [])
                    lock.graph[k] += [d.lower() for d in (v.get("dependencies") or {})]
                    seen.add(k)
        lock.total = len(seen)
        return lock if found else Lock()

    def scan(self, path, text, ctx):
        out = []
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        for m in re.finditer(r"(?m)^\s*(?:global\s+)?using\s+(static\s+)?(?:[\w.]+\s*=\s*)?([\w.]+)\s*;", text):
            out.append((m.group(2), {m.group(2)}))
        return out

    def resolve(self, spec, ctx, keys):
        low = spec.lower()
        best = None
        for k in keys:
            if (low == k or low.startswith(k + ".")) and (best is None or len(k) > len(best)):
                best = k
        for alias, pkgs in CS_ALIAS.items():
            if low == alias or low.startswith(alias + "."):
                best = next((p for p in pkgs if p in keys), best)
        if best:
            return "dep", best
        if any(spec == o or spec.startswith(o + ".") or o.startswith(spec + ".") for o in self.own):
            return "skip", None
        if CS_FRAMEWORK.match(spec):
            return "skip", None
        return "undeclared", spec.split(".")[0] if "." in spec else spec

    def tooling(self, d, ctx):
        return bool(CS_TOOLING.search(d["name"]))


# ---- shell

SHELL_SKIP = set("""alias bg bind break builtin caller case cd command compgen complete continue declare dirs disown do done echo elif else enable esac eval exec exit export fc fg fi
    for function getopts hash help history if in jobs let local logout mapfile popd printf pushd pwd read readarray readonly return select set shift shopt source suspend test then
    time times trap type typeset ulimit umask unalias unset until wait while true false cat cp mv rm ls mkdir rmdir ln chmod chown touch head tail sort uniq wc cut tr tee
    sed awk grep egrep fgrep find xargs basename dirname readlink realpath date sleep env sudo which tar gzip gunzip bash sh zsh dash python python3 tput stat diff mktemp
    kill ps uname id whoami hostname df du paste join comm column rev seq yes nohup nice expr bc od hexdump file ping nslookup dig""".split())
SHELL_PREFIX = {"sudo", "exec", "env", "time", "nohup", "command", "then", "do", "else", "elif", "if", "while", "until", "!", "{", "(", "xargs", "builtin"}


class ShellAdapter(Adapter):
    eco = "shell"
    exts = ("sh", "bash", "zsh")
    mark_undeclared = False

    @staticmethod
    def _commands(text):
        for line in text.splitlines():
            line = re.sub(r"(^|\s)#.*$", "", line).strip()
            for seg in re.split(r"&&|\|\||[;|]|\$\(|`", line):
                words = seg.split()
                while words and (words[0] in SHELL_PREFIX or re.match(r"^[A-Za-z_]\w*=", words[0])):
                    words.pop(0)
                if words and re.match(r"^[A-Za-z][\w.+\-]*$", words[0]):
                    yield words[0], (words[1] if len(words) > 1 and re.match(r"^[a-z][\w\-]*$", words[1]) else None)

    def declared(self, ctx):
        out, seen = [], set()
        for path in ctx.find(r"(^|/)Brewfile[^/]*$"):
            for m in re.finditer(r"(?m)^\s*brew\s+[\"']([^\"']+)[\"']", ctx.blob(path) or ""):
                out.append(decl(m.group(1).rsplit("/", 1)[-1], "", "runtime", "Brewfile", path))
        for path in ctx.find(r"(^|/)(Dockerfile[^/]*|Containerfile|[^/]+\.(sh|bash))$"):
            for m in re.finditer(r"\b(?:apt-get|apt|apk|dnf|yum|brew)[ \t]+(?:-\S+[ \t]+)*(?:install|add)((?:[ \t]+(?:\\\n[ \t]*)?[^\s;&|\\$()<>\"'`]+)+)", ctx.blob(path) or ""):
                for w in m.group(1).split():
                    if w not in seen and re.match(r"^[a-z][\w.+\-]*$", w):
                        seen.add(w)
                        out.append(decl(w, "", "runtime", "system packages", path))
        return out

    def scan(self, path, text, ctx):
        out = []
        for cmd, sub in self._commands(text):
            if cmd not in SHELL_SKIP:
                out.append((cmd, {sub or cmd}))
        return out

    def resolve(self, spec, ctx, keys):
        return ("dep", spec.lower()) if spec.lower() in keys else ("skip", None)

    def tooling(self, d, ctx):
        n = d["name"]
        return n.startswith("lib") or n.endswith("-dev") or n in ("ca-certificates", "openssl", "readline", "xz", "zlib", "gnupg")


ADAPTERS = (PythonAdapter, JavaScriptAdapter, CSharpAdapter, ShellAdapter)

# --------------------------------------------------------------------------- modules

CONTAINERS = {"src", "lib", "app", "apps", "packages", "services", "libs", "modules", "crates", "projects", "cmd", "internal", "pkg", "plugins", "tools", "components", "configs"}
MANIFEST_FILE = re.compile(r"(^|/)(package\.json|pyproject\.toml|Cargo\.toml|go\.mod|[^/]+\.(cs|fs|vb)proj|build\.zig\.zon|setup\.py)$")


def module_finder(ctx):
    dirs = sorted({p.rsplit("/", 1)[0] for p in ctx.paths if "/" in p and MANIFEST_FILE.search(p) and not ctx.vendored(p)}, key=len, reverse=True)
    names = {}
    for d in dirs:
        n = d.rsplit("/", 1)[-1]
        names[d] = n
    taken = defaultdict(list)
    for d, n in names.items():
        taken[n].append(d)
    for n, ds in taken.items():
        if len(ds) > 1:      # the same folder name in two places: use the last two path segments
            for d in ds:
                names[d] = "/".join(d.split("/")[-2:])

    def find(path):
        parts = path.split("/")
        for i in range(len(parts) - 1, 0, -1):
            d = "/".join(parts[:i])
            if d in names:
                return names[d]
        if len(parts) == 1:
            return "(root)"
        if parts[0] in CONTAINERS and len(parts) > 2:
            return f"{parts[0]}/{parts[1]}"
        return parts[0]
    return find


# --------------------------------------------------------------------------- analysis


def analyze(repo, entries, files, is_test=None, max_files=MAX_FILES):
    """The data contract of the Dependencies card, or None when the repository declares and imports nothing.

    repo: gather.Repo. entries: (path, type, oid, size) for every tracked object. files: the analysed text files
    ({"path", "blob", "bytes"}), which already leave out vendored, generated and binary files."""
    ctx = Ctx(repo, entries, files, is_test or (lambda p: bool(TEST_PATH.search(p))))
    adapters = [A() for A in ADAPTERS]
    mod_of = module_finder(ctx)
    todo = []        # (path, adapter)
    for f in files:
        p = f["path"]
        if ctx.vendored(p) or f["bytes"] > MAX_SOURCE:
            continue
        a = next((a for a in adapters if a.handles(p)), None)
        if a is None and "." not in p.rsplit("/", 1)[-1] and f["bytes"] < 100_000 and p.count("/") < 6:
            head = (ctx.text(p) or "")[:80]
            if re.match(r"#!.*\b(ba|z|da)?sh\b", head):
                a = adapters[-1]
        if a:
            todo.append((p, a))
    ctx.config_text = "\n".join((ctx.blob(p) or "") for p in ctx.find(r"(^|/)(Makefile|justfile|Taskfile\.ya?ml|tox\.ini|\.pre-commit-config\.ya?ml|noxfile\.py)$|(^|/)\.github/workflows/[^/]+\.ya?ml$|(^|/)Dockerfile[^/]*$")).lower()
    for p, a in todo:
        t = ctx.text(p)
        if t is not None:
            a.index(p, t, ctx)
    ctx.config_text += "\n" + "\n".join(f"[tool.{m}" for p in ctx.find(r"(^|/)pyproject\.toml$") for m in re.findall(r"(?m)^\[tool\.([\w\-]+)", ctx.blob(p) or ""))

    # what each ecosystem declares, merged by package
    decls = {}
    for a in adapters:
        merged = {}
        for d in a.declared(ctx):
            d["key"] = a.norm(d["name"])
            m = merged.get(d["key"])
            if m is None:
                merged[d["key"]] = dict(d, groups=[d["group"]], eco=a.eco, adapter=a)
            else:
                if d["group"] not in m["groups"]:
                    m["groups"].append(d["group"])
                if d["scope"] == "runtime":
                    m["scope"] = "runtime"
                m["spec"] = m["spec"] or d["spec"]
                m["internal"] = m["internal"] and d["internal"]
        decls[a.eco] = merged
    locks = {}
    for a in adapters:
        locks[a.eco] = a.lock(ctx)
    for a in adapters:      # tooling is judged after every adapter has added to config_text
        for d in decls[a.eco].values():
            d["tooling"] = a.tooling(d, ctx)
    # dependency names must be unique across ecosystems: they key the file list
    counts = defaultdict(list)
    for eco, ds in decls.items():
        for d in ds.values():
            d["shown"] = d["name"]
            counts[d["name"].lower()].append(d)
    for ds in counts.values():
        if len(ds) > 1:
            for d in ds:
                d["shown"] = f"{d['name']} ({d['eco']})"

    mods = defaultdict(int)
    out_files, src, tst, dep_mods, syms = [], defaultdict(int), defaultdict(int), defaultdict(lambda: defaultdict(int)), defaultdict(set)
    undeclared = {}
    for p, a in todo:
        t = ctx.text(p)
        if t is None:
            continue
        m = mod_of(p)
        mods[m] += 1
        test = 1 if ctx.is_test(p) else 0
        keys = decls[a.eco]
        hit = {}
        for spec, sy in a.scan(p, t, ctx):
            kind, k = a.resolve(spec, ctx, keys)
            if kind == "dep" and not keys[k]["internal"]:
                hit.setdefault(k, set()).update(sy)
            elif kind == "undeclared" and a.mark_undeclared and k:
                u = undeclared.setdefault((a.eco, k), {"name": k, "files": set(), "mods": defaultdict(int)})
                if p not in u["files"]:
                    u["files"].add(p)
                    u["mods"][m] += 1
        names = []
        for k, sy in hit.items():
            d = keys[k]
            (tst if test else src)[(a.eco, k)] += 1
            dep_mods[(a.eco, k)][m] += 1
            syms[(a.eco, k)] |= sy
            names.append(d["shown"])
        out_files.append({"p": p, "t": test, "m": m, "d": sorted(names)})

    # lockfile figures
    trans_total = sum(l.total for l in locks.values()) or None
    deps, unused, config_only = [], [], {"runtime": 0, "dev": 0}
    for eco, ds in decls.items():
        lock = locks[eco]
        for k, d in sorted(ds.items()):
            if d["internal"]:
                continue
            key = (eco, k)
            n_files = src[key] + tst[key]
            ver = lock.versions.get(k) or semver_text(d["spec"])
            if n_files:
                row = {"n": d["shown"], "v": ver, "c": category(d["name"]), "s": d["scope"], "group": ", ".join(d["groups"]), "ecosystem": eco,
                       "src": src[key], "tst": tst[key], "mods": dict(dep_mods[key]), "sym": len(syms[key])}
                r = lock.reach(k)
                if r is not None:
                    row["tr"] = len(r)
                deps.append(row)
            elif d["tooling"]:
                config_only[d["scope"]] += 1
            else:
                unused.append({"n": d["shown"], "v": ver, "s": d["scope"], "group": ", ".join(d["groups"]),
                               "note": "No file in the repository imports it, and no script or configuration file mentions it."})
    roots_of = {eco: [k for k, d in ds.items()] for eco, ds in decls.items()}
    und = []
    for (eco, k), u in sorted(undeclared.items(), key=lambda kv: -len(kv[1]["files"])):
        chain = locks[eco].chain(roots_of[eco], k)
        und.append({"n": u["name"], "files": len(u["files"]), "mods": dict(u["mods"]),
                    "via": " → ".join(chain) if chain and len(chain) > 1 else ""})
    deps.sort(key=lambda d: (-(d["src"] + d["tst"]), d["n"]))
    if not deps and not unused and not und and not config_only["runtime"] + config_only["dev"]:
        return None
    # modules: the biggest ones keep their name, the rest are merged
    ranked = sorted(mods.items(), key=lambda kv: -kv[1])
    keep = {m for m, _ in ranked[:MAX_MODULES - 1]} if len(ranked) > MAX_MODULES else {m for m, _ in ranked}
    fold = lambda m: m if m in keep else "(other)"
    modules = defaultdict(int)
    for m, n in ranked:
        modules[fold(m)] += n
    for d in deps:
        mm = defaultdict(int)
        for m, n in d["mods"].items():
            mm[fold(m)] += n
        d["mods"] = dict(mm)
    for u in und:
        mm = defaultdict(int)
        for m, n in u["mods"].items():
            mm[fold(m)] += n
        u["mods"] = dict(mm)
    for f in out_files:
        f["m"] = fold(f["m"])
    trimmed = 0
    if len(out_files) > max_files:
        out_files.sort(key=lambda f: (not f["d"], len(f["p"])))
        trimmed = len(out_files) - max_files
        out_files = out_files[:max_files]
    out_files.sort(key=lambda f: f["p"])
    return {"transTotal": trans_total, "configOnly": config_only, "trimmed": trimmed,
            "modules": [{"id": m, "files": n} for m, n in sorted(modules.items(), key=lambda kv: (-kv[1], kv[0]))],
            "deps": deps, "unused": unused, "undeclared": und, "files": out_files}
