#!/usr/bin/env python3
"""Collect deterministic facts about a git repository at one pinned commit.

Python counts and classifies; Claude interprets. Everything here reads git
objects at a resolved SHA (never the working tree), so results are repeatable.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import math
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None

BYTES_PER_TOKEN = 3.5      # rough, deliberately conservative for code
MAX_READ = 25_000_000      # bytes; larger blobs are listed but not read here
BULK_FILES = 400           # commits touching more files are treated as bulk (imports, reformatting)
TYPES = ("human", "agent", "bot")

# --------------------------------------------------------------------------- git access


class Repo:
    """Thin git wrapper with one persistent `cat-file --batch` process."""

    def __init__(self, path):
        self.path = str(path)
        self._p = None

    def git(self, *args, check=True):
        p = subprocess.run(["git", "-C", self.path, *args], capture_output=True)
        if check and p.returncode:
            raise RuntimeError(f"git {' '.join(args)}: {p.stderr.decode('utf-8', 'replace').strip()}")
        return p.stdout.decode("utf-8", "replace")

    def read(self, spec):
        """Return (type, bytes) for an object name such as 'sha:path', or None."""
        if self._p is None:
            self._p = subprocess.Popen(["git", "-C", self.path, "cat-file", "--batch"],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL)
        self._p.stdin.write(spec.encode() + b"\n")
        self._p.stdin.flush()
        line = self._p.stdout.readline().rstrip(b"\n")
        if line.endswith(b" missing") or line.endswith(b" ambiguous") or not line:
            return None
        _, typ, size = line.rsplit(b" ", 2)
        data = self._p.stdout.read(int(size))
        self._p.stdout.read(1)
        return typ.decode(), data

    def close(self):
        if self._p:
            self._p.stdin.close()
            self._p.wait()
            self._p = None


# --------------------------------------------------------------------------- classification tables

_LANGS = {
    "Python": ("code", "py pyi pyw"), "JavaScript": ("code", "js mjs cjs jsx"),
    "TypeScript": ("code", "ts tsx mts cts"), "Go": ("code", "go"), "Rust": ("code", "rs"),
    "Java": ("code", "java"), "Kotlin": ("code", "kt kts"), "Scala": ("code", "scala sc"),
    "C#": ("code", "cs"), "F#": ("code", "fs"), "C": ("code", "c h"),
    "C++": ("code", "cc cpp cxx hpp hh hxx"), "Objective-C": ("code", "m mm"),
    "Swift": ("code", "swift"), "Ruby": ("code", "rb rake gemspec"), "PHP": ("code", "php"),
    "Perl": ("code", "pl pm"), "Lua": ("code", "lua"), "R": ("code", "r"), "Dart": ("code", "dart"),
    "Elixir": ("code", "ex exs"), "Erlang": ("code", "erl hrl"), "Haskell": ("code", "hs"),
    "Clojure": ("code", "clj cljs cljc"), "OCaml": ("code", "ml mli"), "Julia": ("code", "jl"),
    "Zig": ("code", "zig"), "Shell": ("code", "sh bash zsh fish"), "PowerShell": ("code", "ps1 psm1"),
    "Batch": ("code", "bat cmd"), "SQL": ("code", "sql"), "Terraform": ("code", "tf tfvars"),
    "Solidity": ("code", "sol"), "Vue": ("code", "vue"), "Svelte": ("code", "svelte"),
    "Groovy": ("code", "groovy gradle"), "Nix": ("code", "nix"), "CMake": ("code", "cmake"),
    "HTML": ("markup", "html htm jinja jinja2 j2 njk hbs ejs erb"),
    "CSS": ("markup", "css scss sass less"), "XML": ("markup", "xml xsd xsl"),
    "JSON": ("data", "json jsonc json5"), "YAML": ("data", "yml yaml"), "TOML": ("data", "toml"),
    "INI/Config": ("data", "ini cfg conf properties env"), "CSV": ("data", "csv tsv"),
    "Protocol Buffers": ("data", "proto"), "GraphQL": ("data", "graphql gql graphqls"),
    "Prisma": ("data", "prisma"),
    "Markdown": ("docs", "md mdx markdown"), "reStructuredText": ("docs", "rst"),
    "Text": ("docs", "txt"), "AsciiDoc": ("docs", "adoc asciidoc"),
}
EXT = {e: (n, k) for n, (k, exts) in _LANGS.items() for e in exts.split()}
NAMED = {"Dockerfile": ("Dockerfile", "code"), "Containerfile": ("Dockerfile", "code"),
         "Makefile": ("Makefile", "code"), "Jenkinsfile": ("Groovy", "code"),
         "Gemfile": ("Ruby", "code"), "Rakefile": ("Ruby", "code"), "Vagrantfile": ("Ruby", "code"),
         "CMakeLists.txt": ("CMake", "code"), "justfile": ("Makefile", "code")}
ASSET_EXT = set("""png jpg jpeg gif ico webp bmp tiff pdf zip gz tgz bz2 xz 7z rar jar war ear woff woff2 ttf otf
eot mp3 mp4 mov avi webm wav ogg wasm so dll dylib exe bin class pyc o a lib svg psd ai sketch dmg iso
parquet sqlite db pickle pkl npy onnx pt h5 keras""".split())
LOCKFILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Cargo.lock", "Gemfile.lock",
             "composer.lock", "go.sum", "uv.lock", "Pipfile.lock", "bun.lockb", "gradle.lockfile",
             "packages.lock.json", "pubspec.lock", "mix.lock", "flake.lock", "Podfile.lock"}
VENDOR_SEG = {"node_modules", "vendor", "third_party", "third-party", "thirdparty", "bower_components",
              "Pods", "site-packages", ".yarn"}
GENERATED_SEG = {"dist", "target", ".next", ".nuxt", "__pycache__", "coverage", "htmlcov", ".pytest_cache",
                 ".mypy_cache", ".gradle"}
GENERATED_NAME = re.compile(r"(\.min\.(js|css)|\.map|\.pb\.go|\.pb\.gw\.go|_pb2(_grpc)?\.py|\.generated\.|\.g\.dart|\.designer\.cs)$")
TEST_RE = re.compile(r"(^|/)(tests?|__tests__|specs?|e2e|cypress|playwright)/|(^|/)test_[^/]*\.py$|_test\.(go|py|rb|exs?)$|\.(test|spec)\.[jt]sx?$|Tests?\.(java|kt|cs)$")

_INV = {
    "entry_points": [r"(^|/)(main|app|server|index|cli|run|manage|__main__|wsgi|asgi|program|start)\.(py|js|mjs|cjs|ts|tsx|go|rs|java|kt|rb|php|cs|c|cc|cpp|swift|ex)$",
                     r"(^|/)cmd/[^/]+/main\.go$", r"(^|/)bin/[^/]+$", r"(^|/)(Program|Main|Application|Startup)\.(cs|java|kt)$"],
    "containers": [r"(^|/)(Dockerfile|Containerfile)[^/]*$", r"(^|/)(docker-)?compose[^/]*\.ya?ml$", r"\.dockerignore$"],
    "ci_cd": [r"^\.github/workflows/", r"^\.gitlab-ci\.ya?ml$", r"(^|/)Jenkinsfile", r"^\.circleci/",
              r"azure-pipelines[^/]*\.ya?ml$", r"^bitbucket-pipelines\.yml$", r"^\.travis\.yml$", r"^\.buildkite/",
              r"cloudbuild\.ya?ml$", r"^\.drone\.yml$", r"^\.github/dependabot\.ya?ml$", r"^renovate\.json5?$"],
    "infrastructure": [r"\.tf$", r"(^|/)Chart\.yaml$", r"(^|/)(k8s|kubernetes|manifests|helm|charts|infra|terraform|ansible|pulumi|cdk)/",
                       r"(^|/)serverless\.ya?ml$", r"(^|/)(skaffold|kustomization)[^/]*\.ya?ml$", r"(^|/)(Procfile|app\.yaml|fly\.toml|vercel\.json|netlify\.toml|wrangler\.toml|render\.yaml)$"],
    "data_schema": [r"(^|/)(migrations?|alembic|db/migrate)/", r"\.sql$", r"\.prisma$", r"(^|/)models?(\.py|/)",
                    r"(^|/)(entities|entity|schemas?)/", r"\.avsc$"],
    "api_contracts": [r"(^|/)(openapi|swagger|asyncapi)[^/]*\.(ya?ml|json)$", r"\.proto$", r"\.graphqls?$"],
    "config_secrets": [r"(^|/)\.env[^/]*$", r"(^|/)(config|configs|settings|conf)(\.|/)", r"\.(pem|key|p12|pfx|jks|keystore)$",
                       r"(^|/)(secrets?|credentials?)[^/]*", r"\.sops\.ya?ml$", r"(^|/)vault[^/]*", r"(^|/)\.(npmrc|pypirc)$", r"\.tfvars$"],
    "build_packaging": [r"(^|/)Makefile$", r"(^|/)(setup\.py|setup\.cfg|MANIFEST\.in|tox\.ini|noxfile\.py|justfile|Taskfile\.ya?ml)$",
                        r"(^|/)(webpack|vite|rollup|esbuild|tsup|babel|gulpfile|Gruntfile)[^/]*\.[cm]?[jt]s$",
                        r"(^|/)(CMakeLists\.txt|BUILD(\.bazel)?|WORKSPACE|meson\.build|build\.gradle(\.kts)?|settings\.gradle(\.kts)?|pom\.xml|build\.sbt|Cargo\.toml|\.goreleaser\.ya?ml|flake\.nix)$",
                        r"(^|/)debian/|\.nuspec$"],
    "tests": [TEST_RE.pattern],
    "docs": [r"(^|/)(README|CONTRIBUTING|ARCHITECTURE|DESIGN|SECURITY|CHANGELOG|CHANGES|HISTORY|LICENSE|NOTICE|CODEOWNERS)[^/]*$",
             r"^docs?/", r"(^|/)(adr|decisions)/"],
}
INVENTORY = {k: re.compile("|".join(f"(?:{p})" for p in v)) for k, v in _INV.items()}
SENSITIVE_FILE = re.compile(r"(^|/)(\.env(\.(?!example|sample|template|dist)[^/]+)?|id_rsa|id_dsa|id_ecdsa|id_ed25519|[^/]+\.(pem|key|p12|pfx|jks|keystore|kdbx)|credentials(\.json)?|\.netrc|\.npmrc|\.pypirc|[^/]+\.tfstate(\.backup)?|secrets?\.(ya?ml|json|toml|env))$")

ENV_RE = re.compile(r"""(?:os\.environ(?:\.get)?\s*[\[(]\s*["']|os\.getenv\s*\(\s*["']|process\.env\.|process\.env\[\s*["']|os\.Getenv\(\s*"|System\.getenv\(\s*"|std::env::var\(\s*"|ENV\[\s*["']|ENV\.fetch\(\s*["']|[^\w.]getenv\(\s*["']|Environment\.GetEnvironmentVariable\(\s*")([A-Z][A-Z0-9_]{2,})""")
DOTENV_RE = re.compile(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]{2,})\s*=", re.M)
SECRET_PATTERNS = [
    ("aws-access-key-id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("private-key-block", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("stripe-live-key", re.compile(r"\b[sr]k_live_[0-9A-Za-z]{20,}\b")),
    ("jwt-like", re.compile(r"\beyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}")),
]

BOT_IDENT = re.compile(r"\[bot\]|\bbot\b|-bot\b|dependabot|renovate|github-actions|greenkeeper|snyk|semantic-release|pre-commit-ci|allcontributors|imgbot|mergify|web-flow|^github <|noreply@github\.com>", re.I)
AGENT_IDENT = re.compile(r"noreply@anthropic\.com|^claude( code)?\b|copilot-swe-agent|github-copilot|cursoragent|cursor agent|devin-ai-integration|\(aider\)|openhands|all-hands\.dev|chatgpt-codex|google-labs-jules|jules\[bot\]|gemini-code-assist|sweep-ai|codegen-sh|amazon-q", re.I)
AGENT_MSG = re.compile(r"Co-authored-by:\s*[^\n]*?(claude|copilot|cursor|devin|aider|codex|gemini|openhands)[^\n]*|Generated with \[?Claude Code|🤖 Generated with|Generated by (?:GitHub )?Copilot|noreply@anthropic\.com|^aider:", re.I | re.M)
AGENT_LABELS = [("Claude", r"claude|anthropic"), ("Copilot", r"copilot"), ("Cursor", r"cursor"), ("Aider", r"aider"),
                ("Devin", r"devin"), ("Codex", r"codex|openai"), ("Gemini", r"gemini|jules"), ("OpenHands", r"openhands|all-hands")]


def tokens_for(nbytes):
    return math.ceil(nbytes / BYTES_PER_TOKEN)


def lang_of(path):
    base = path.rsplit("/", 1)[-1]
    if base in NAMED:
        return NAMED[base]
    if base.startswith("Dockerfile"):
        return NAMED["Dockerfile"]
    ext = base.rsplit(".", 1)[-1].lower() if "." in base else ""
    return EXT.get(ext)


def noise_reason(path):
    segs = path.split("/")
    base = segs[-1]
    if VENDOR_SEG.intersection(segs[:-1]):
        return "vendored"
    if base in LOCKFILES:
        return "lockfile"
    if GENERATED_SEG.intersection(segs[:-1]) or GENERATED_NAME.search(base):
        return "generated"
    ext = base.rsplit(".", 1)[-1].lower() if "." in base else ""
    if ext in ASSET_EXT:
        return "asset"
    return None


def ident_id(name, email):
    e = email.lower().strip()
    m = re.match(r"^(?:\d+\+)?(.+)@users\.noreply\.github\.com$", e)
    if m:
        e = m.group(1) + "@users.noreply.github.com"
    return e or name.lower()


def ident_type(name, email, override=None):
    if override in TYPES:
        return override
    s = f"{name} <{email}>"
    if AGENT_IDENT.search(s):
        return "agent"
    if BOT_IDENT.search(s):
        return "bot"
    return "human"


def iso_day(dt):
    return dt.strftime("%Y-%m-%d")


# --------------------------------------------------------------------------- manifests


def _dep(name, spec="", dev=False):
    return {"name": name, "spec": (spec or "").strip(), "dev": dev}


def _pep508(s):
    m = re.match(r"^\s*([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?\s*(.*)$", s)
    return _dep(m.group(1), m.group(2).split(";")[0]) if m else None


def parse_manifest(path, text):
    base = path.rsplit("/", 1)[-1]
    out = {"path": path, "ecosystem": None, "name": None, "version": None, "description": None,
           "dependencies": [], "scripts": {}, "extra": {}}
    try:
        if base == "package.json":
            j = json.loads(text)
            out.update(ecosystem="npm", name=j.get("name"), version=j.get("version"), description=j.get("description"))
            for key, dev in (("dependencies", False), ("devDependencies", True), ("peerDependencies", False), ("optionalDependencies", False)):
                out["dependencies"] += [_dep(k, v, dev) for k, v in (j.get(key) or {}).items()]
            out["scripts"] = j.get("scripts") or {}
            out["extra"] = {k: j[k] for k in ("main", "module", "bin", "workspaces", "engines", "private", "type") if k in j}
        elif base == "pyproject.toml" and tomllib:
            j = tomllib.loads(text)
            p, poetry = j.get("project", {}), j.get("tool", {}).get("poetry", {})
            out.update(ecosystem="python", name=p.get("name") or poetry.get("name"), version=p.get("version") or poetry.get("version"),
                       description=p.get("description") or poetry.get("description"))
            out["dependencies"] += [d for d in map(_pep508, p.get("dependencies", [])) if d]
            for grp, items in (p.get("optional-dependencies") or {}).items():
                out["dependencies"] += [dict(d, dev=True) for d in map(_pep508, items) if d]
            for grp, items in (j.get("dependency-groups") or {}).items():
                out["dependencies"] += [dict(d, dev=True) for d in map(_pep508, [i for i in items if isinstance(i, str)]) if d]
            for k, v in (poetry.get("dependencies") or {}).items():
                if k.lower() != "python":
                    out["dependencies"].append(_dep(k, v if isinstance(v, str) else json.dumps(v)))
            for k, v in (poetry.get("dev-dependencies") or {}).items():
                out["dependencies"].append(_dep(k, v if isinstance(v, str) else json.dumps(v), True))
            out["scripts"] = p.get("scripts") or poetry.get("scripts") or {}
            out["extra"] = {k: v for k, v in (("requires-python", p.get("requires-python")), ("build-backend", j.get("build-system", {}).get("build-backend"))) if v}
        elif re.match(r"requirements.*\.txt$", base):
            out["ecosystem"] = "python"
            out["name"] = base
            for line in text.splitlines():
                line = line.split("#")[0].strip()
                if line and not line.startswith(("-", "git+", "http")):
                    d = _pep508(line)
                    if d:
                        out["dependencies"].append(dict(d, dev="dev" in base or "test" in base))
        elif base == "go.mod":
            out["ecosystem"] = "go"
            m = re.search(r"^module\s+(\S+)", text, re.M)
            out["name"] = m.group(1) if m else None
            g = re.search(r"^go\s+(\S+)", text, re.M)
            out["extra"] = {"go": g.group(1)} if g else {}
            for m in re.finditer(r"^\s*(?:require\s+)?([\w.\-/~]+\.[\w.\-/~]+)\s+(v[\w.\-+]+)(\s*//\s*indirect)?", text, re.M):
                out["dependencies"].append(_dep(m.group(1), m.group(2), bool(m.group(3))))
        elif base == "Cargo.toml" and tomllib:
            j = tomllib.loads(text)
            p = j.get("package", {})
            out.update(ecosystem="rust", name=p.get("name"), version=p.get("version") if isinstance(p.get("version"), str) else None,
                       description=p.get("description") if isinstance(p.get("description"), str) else None)
            for key, dev in (("dependencies", False), ("build-dependencies", False), ("dev-dependencies", True)):
                for k, v in (j.get(key) or {}).items():
                    out["dependencies"].append(_dep(k, v if isinstance(v, str) else (v.get("version", "") if isinstance(v, dict) else ""), dev))
            out["extra"] = {k: v for k, v in (("workspace", j.get("workspace", {}).get("members")), ("bins", [b.get("name") for b in j.get("bin", [])] or None)) if v}
        elif base == "pom.xml":
            import xml.etree.ElementTree as ET
            root = ET.fromstring(re.sub(r'\sxmlns="[^"]+"', "", text, count=1))
            g = lambda n, tag: (n.findtext(tag) or "").strip() or None
            out.update(ecosystem="maven", name=":".join(x for x in (g(root, "groupId"), g(root, "artifactId")) if x),
                       version=g(root, "version"), description=g(root, "description"))
            for d in root.iter("dependency"):
                out["dependencies"].append(_dep(f"{g(d, 'groupId')}:{g(d, 'artifactId')}", g(d, "version") or "", g(d, "scope") in ("test", "provided")))
            out["extra"] = {"modules": [m.text for m in root.iter("module")]} if list(root.iter("module")) else {}
        elif base == "composer.json":
            j = json.loads(text)
            out.update(ecosystem="php", name=j.get("name"), version=j.get("version"), description=j.get("description"))
            out["dependencies"] += [_dep(k, v) for k, v in (j.get("require") or {}).items()]
            out["dependencies"] += [_dep(k, v, True) for k, v in (j.get("require-dev") or {}).items()]
        elif base == "Gemfile":
            out["ecosystem"] = "ruby"
            for m in re.finditer(r"^\s*gem\s+['\"]([^'\"]+)['\"](?:\s*,\s*['\"]([^'\"]+)['\"])?", text, re.M):
                out["dependencies"].append(_dep(m.group(1), m.group(2) or ""))
        elif base.endswith(".csproj"):
            out["ecosystem"] = "dotnet"
            out["name"] = base[:-7]
            for m in re.finditer(r'<PackageReference\s+Include="([^"]+)"(?:\s+Version="([^"]+)")?', text):
                out["dependencies"].append(_dep(m.group(1), m.group(2) or ""))
            tf = re.search(r"<TargetFrameworks?>([^<]+)<", text)
            out["extra"] = {"target": tf.group(1)} if tf else {}
        elif base.startswith("build.gradle"):
            out["ecosystem"] = "gradle"
            for m in re.finditer(r"\b(implementation|api|compileOnly|runtimeOnly|testImplementation|annotationProcessor|kapt)\s*[( ]\s*['\"]([^'\":]+:[^'\":]+)(?::([^'\"]+))?['\"]", text):
                out["dependencies"].append(_dep(m.group(2), m.group(3) or "", m.group(1).startswith("test")))
    except Exception as exc:  # a broken manifest must not stop profiling
        out["extra"]["parse_error"] = str(exc)[:200]
    out["dependency_count"] = len(out["dependencies"])
    out["dependencies"] = out["dependencies"][:300]
    return out if out["ecosystem"] else None


MANIFEST_NAMES = re.compile(r"(^|/)(package\.json|pyproject\.toml|requirements[^/]*\.txt|go\.mod|Cargo\.toml|pom\.xml|composer\.json|Gemfile|[^/]+\.csproj|build\.gradle(\.kts)?)$")

# --------------------------------------------------------------------------- areas


def build_split(paths, max_depth=3, share=0.35, min_files=30):
    total = len(paths) or 1
    counts = Counter()
    for p in paths:
        segs = p.split("/")[:-1]
        for i in range(1, len(segs) + 1):
            counts["/".join(segs[:i]) + "/"] += 1
    split = set()
    for _ in range(max_depth):
        changed = False
        for d, c in list(counts.items()):
            depth = d.count("/")
            if d not in split and depth <= max_depth - 1 and c >= min_files and c / total > share:
                parent_ok = depth == 1 or ("/".join(d.split("/")[:-2]) + "/") in split
                if parent_ok:
                    split.add(d)
                    changed = True
        if not changed:
            break
    return split


def make_area_of(split):
    def area_of(path):
        segs = path.split("/")
        if len(segs) == 1:
            return "(root files)"
        cur = segs[0] + "/"
        while cur in split:
            idx = cur.count("/")
            if len(segs) - 1 <= idx:
                return cur + "(files)"
            cur = cur + segs[idx] + "/"
        return cur
    return area_of


# --------------------------------------------------------------------------- chunk planning


def plan_chunks(files, budget):
    """Group files into directory-coherent chunks of at most `budget` tokens.

    Files larger than the budget are split into line ranges. Nothing is dropped.
    """
    root = {"dirs": {}, "files": [], "tokens": 0}
    for f in files:
        node = root
        node["tokens"] += f["tokens"]
        for seg in f["path"].split("/")[:-1]:
            node = node["dirs"].setdefault(seg, {"dirs": {}, "files": [], "tokens": 0})
            node["tokens"] += f["tokens"]
        node["files"].append(f)

    def segments(f):
        if f["tokens"] <= budget:
            return [dict(f, start=None, end=None)]
        per_line = max(f["tokens"] / max(f["lines"], 1), 0.01)
        step = max(1, int(budget * 0.9 / per_line))
        out, s = [], 1
        while s <= f["lines"]:
            e = min(f["lines"], s + step - 1)
            out.append(dict(f, start=s, end=e, tokens=math.ceil((e - s + 1) * per_line)))
            s = e + 1
        return out

    def units(node):
        if node["tokens"] <= budget:
            flat, stack = [], [node]
            while stack:
                n = stack.pop()
                flat += [dict(f, start=None, end=None) for f in n["files"]]
                stack += [n["dirs"][k] for k in sorted(n["dirs"], reverse=True)]
            return [sorted(flat, key=lambda s: s["path"])]
        items = [[s] for f in sorted(node["files"], key=lambda f: f["path"]) for s in segments(f)]
        for name in sorted(node["dirs"]):
            items += units(node["dirs"][name])
        merged, cur, cur_t = [], [], 0
        for it in items:
            t = sum(s["tokens"] for s in it)
            if cur and cur_t + t > budget:
                merged.append(cur)
                cur, cur_t = [], 0
            cur += it
            cur_t += t
        if cur:
            merged.append(cur)
        return merged

    chunks = []
    for i, segs in enumerate(units(root), 1):
        tops = sorted({"/".join(s["path"].split("/")[:2]) for s in segs})
        label = ", ".join(tops[:3]) + (f" (+{len(tops) - 3} more)" if len(tops) > 3 else "")
        fp = hashlib.sha1("\n".join(f"{s['path']}:{s['blob']}:{s['start']}-{s['end']}" for s in segs).encode()).hexdigest()[:12]
        chunks.append({"id": f"c{i:03d}", "fingerprint": fp, "label": label,
                       "tokens": sum(s["tokens"] for s in segs), "files": [
                           {k: s[k] for k in ("path", "lines", "tokens", "role", "start", "end")} for s in segs]})
    return chunks


# --------------------------------------------------------------------------- main profile


def profile(repo_path, ref="HEAD", chunk_tokens=400_000, contributor_types=None):
    repo = Repo(repo_path)
    top = repo.git("rev-parse", "--show-toplevel").strip()
    repo = Repo(top)
    sha = repo.git("rev-parse", "--verify", f"{ref}^{{commit}}").strip()
    as_of = datetime.fromisoformat(repo.git("show", "-s", "--format=%cI", sha).strip()).astimezone(timezone.utc)
    subject = repo.git("show", "-s", "--format=%s", sha).strip()
    branch = None
    if ref == "HEAD":
        branch = repo.git("symbolic-ref", "--short", "-q", "HEAD", check=False).strip() or "(detached HEAD)"
    elif not re.fullmatch(r"[0-9a-f]{7,40}", ref):
        branch = ref
    warnings = []
    if ref == "HEAD" and repo.git("status", "--porcelain", check=False).strip():
        warnings.append("The working tree has uncommitted changes. This profile covers the committed state only.")
    if repo.git("rev-parse", "--is-shallow-repository", check=False).strip() == "true":
        warnings.append("This is a shallow clone. History-based figures (commits, contributors, ownership) are incomplete.")

    remote_url = (repo.git("remote", "get-url", "origin", check=False).strip()
                  or (repo.git("remote", check=False).split() or [""])[0])
    remote = remote_info(remote_url)

    # ---- tree
    entries = []
    for rec in repo.git("ls-tree", "-r", "-l", "-z", sha).split("\0"):
        if not rec:
            continue
        meta, path = rec.split("\t", 1)
        mode, typ, oid, size = meta.split()
        entries.append((path, typ, oid, 0 if size == "-" else int(size)))
    tree_paths = {e[0] for e in entries if e[1] == "blob"}
    submodules = [e[0] for e in entries if e[1] == "commit"]

    # ---- per-file pass
    excluded, excluded_dirs = Counter(), Counter()
    lang_stats = defaultdict(lambda: {"kind": "", "files": 0, "lines": 0, "bytes": 0})
    files = []                       # analyzable text files, for chunk planning
    env_refs, secret_hits, manifests, sensitive = {}, [], [], []
    readme = None
    for path, typ, oid, size in entries:
        if typ != "blob":
            continue
        if SENSITIVE_FILE.search(path) and not path.endswith(".pub"):
            sensitive.append(path)
        wanted_manifest = bool(MANIFEST_NAMES.search(path)) and not VENDOR_SEG.intersection(path.split("/"))
        reason = noise_reason(path)
        if reason is None and size > MAX_READ:
            reason = "oversize"
        if reason and not (wanted_manifest and reason == "generated"):
            excluded[reason] += 1
            excluded_dirs["/".join(path.split("/")[:2]) if "/" in path else "(root)"] += 1
            continue
        got = repo.read(oid)
        if not got:
            continue
        data = got[1]
        if b"\0" in data[:8000]:
            excluded["binary"] += 1
            continue
        head = data[:400]
        if b"DO NOT EDIT" in head or b"Code generated" in head or b"@generated" in head:
            excluded["generated"] += 1
            excluded_dirs["/".join(path.split("/")[:2]) if "/" in path else "(root)"] += 1
            continue
        text = data.decode("utf-8", "replace")
        lines = data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
        nonblank = len(re.findall(rb"^[ \t]*\S", data, re.M))
        lang = lang_of(path)
        if wanted_manifest:
            m = parse_manifest(path, text)
            if m:
                manifests.append(m)
        if readme is None and re.fullmatch(r"README(\.[A-Za-z]+)?", path):
            readme = {"path": path, "title": next((l.lstrip("# ").strip() for l in text.splitlines() if l.strip()), ""),
                      "excerpt": next((p.strip().replace("\n", " ")[:600] for p in re.split(r"\n\s*\n", text)
                                       if p.strip() and not p.strip().startswith(("#", "=", "[!", "!["))), "")}
        if lang:
            ls = lang_stats[lang[0]]
            ls["kind"] = lang[1]
            ls["files"] += 1
            ls["lines"] += nonblank
            ls["bytes"] += len(data)
        role = "test" if TEST_RE.search(path) else ("doc" if lang and lang[1] == "docs" else ("config" if lang and lang[1] == "data" else "code"))
        files.append({"path": path, "blob": oid, "bytes": len(data), "lines": lines, "tokens": tokens_for(len(data)), "role": role})
        if len(data) <= 2_000_000 and (not lang or lang[1] != "docs"):
            nl = None
            for pat_name, pat in SECRET_PATTERNS:
                m = pat.search(text)
                if m and len(secret_hits) < 200:
                    nl = nl or [i for i, c in enumerate(text) if c == "\n"]
                    secret_hits.append({"path": path, "line": bisect.bisect_left(nl, m.start()) + 1, "kind": pat_name})
            for m in list(ENV_RE.finditer(text))[:60]:
                name = m.group(1)
                if name not in env_refs:
                    nl = nl or [i for i, c in enumerate(text) if c == "\n"]
                    env_refs[name] = {"name": name, "count": 0, "first": {"path": path, "line": bisect.bisect_left(nl, m.start()) + 1}}
                env_refs[name]["count"] += 1
            if re.search(r"(^|/)\.env[^/]*$", path):
                for m in DOTENV_RE.finditer(text):
                    name = m.group(1)
                    if name not in env_refs:
                        line = text.count("\n", 0, m.start()) + 1
                        env_refs[name] = {"name": name, "count": 0, "first": {"path": path, "line": line}}
                    env_refs[name]["count"] += 1

    # ---- areas
    area_paths = [p for p in tree_paths if not noise_reason(p)]
    split = build_split(area_paths)
    area_of = make_area_of(split)
    area_files = Counter(area_of(p) for p in area_paths)

    # ---- identities
    pairs = Counter()
    for line in repo.git("log", sha, "--format=%aN%x1f%aE").splitlines():
        if "\x1f" in line:
            n, e = line.split("\x1f", 1)
            pairs[(n, e)] += 1
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    id_commits, id_names, by_name = Counter(), defaultdict(Counter), defaultdict(list)
    for (n, e), c in pairs.items():
        i = ident_id(n, e)
        find(i)
        id_commits[i] += c
        id_names[i][n] += c
        if " " in n.strip() and not BOT_IDENT.search(n) and not AGENT_IDENT.search(n):
            by_name[n.strip().casefold()].append(i)
    for ids in by_name.values():
        for other in ids[1:]:
            parent[find(other)] = find(ids[0])
    groups = defaultdict(list)
    for i in list(parent):
        groups[find(i)].append(i)
    canon, display, emails = {}, {}, {}
    for members in groups.values():
        best = max(members, key=lambda i: id_commits[i])
        names = Counter()
        for i in members:
            canon[i] = best
            names.update(id_names[i])
        display[best] = names.most_common(1)[0][0]
        emails[best] = sorted(members)
    overrides = contributor_types or {}
    ctype = {cid: ident_type(display[cid], cid, overrides.get(cid)) for cid in display}

    # ---- history pass
    people = {}
    area_stat = {}
    file_commits, file_churn, file_last = Counter(), Counter(), {}
    file_who = defaultdict(Counter)
    monthly, yearly = Counter(), Counter()
    merges = total = assisted_total = 0
    assisted_by = Counter()
    bulk = []
    first_dt = last_dt = None
    cutoff = as_of - timedelta(days=365)
    fmt = "%x1e%H%x1f%P%x1f%aN%x1f%aE%x1f%aI%x1f%B%x1f"
    proc = subprocess.Popen(["git", "-C", repo.path, "log", sha, "--no-renames", "--numstat", f"--format={fmt}"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def records():
        buf = b""
        while True:
            blk = proc.stdout.read(1 << 20)
            if not blk:
                break
            buf += blk
            *recs, buf = buf.split(b"\x1e")
            for r in recs:
                if r.strip():
                    yield r.decode("utf-8", "replace")
        if buf.strip():
            yield buf.decode("utf-8", "replace")

    for rec in records():
        parts = rec.split("\x1f")
        if len(parts) < 7:
            continue
        csha, parents, an, ae, ad, msg, stat = parts[:7]
        total += 1
        merges += len(parents.split()) > 1
        dt = datetime.fromisoformat(ad.strip()).astimezone(timezone.utc)
        first_dt = dt if first_dt is None or dt < first_dt else first_dt
        last_dt = dt if last_dt is None or dt > last_dt else last_dt
        cid = canon.get(ident_id(an, ae)) or ident_id(an, ae)
        itype = ctype.get(cid, "human")
        marker = AGENT_MSG.search(msg)
        t = itype if itype != "human" else ("agent" if marker else "human")
        if marker:
            assisted_total += 1
            for label, pat in AGENT_LABELS:
                if re.search(pat, marker.group(0), re.I):
                    assisted_by[label] += 1
                    break
        monthly[dt.strftime("%Y-%m")] += 1
        yearly[dt.strftime("%Y")] += 1
        nums = []
        for line in stat.splitlines():
            f = line.split("\t")
            if len(f) == 3:
                nums.append((int(f[0]) if f[0].isdigit() else 0, int(f[1]) if f[1].isdigit() else 0, f[2]))
        p = people.setdefault(cid, {"id": cid, "name": display.get(cid, an), "type": itype, "commits": 0, "assisted": 0,
                                    "by_type": Counter(), "added": 0, "deleted": 0, "first": dt, "last": dt,
                                    "recent": 0, "months": set(), "areas": Counter()})
        p["commits"] += 1
        p["by_type"][t] += 1
        p["assisted"] += bool(marker) and itype == "human"
        p["first"], p["last"] = min(p["first"], dt), max(p["last"], dt)
        p["recent"] += dt >= cutoff
        p["months"].add(dt.strftime("%Y-%m"))
        if len(nums) > BULK_FILES:
            bulk.append({"sha": csha, "files": len(nums), "author": display.get(cid, an), "date": iso_day(dt), "subject": msg.strip().split("\n")[0][:100]})
            continue
        touched = defaultdict(int)
        for a, d, path in nums:
            if noise_reason(path):
                continue
            p["added"] += a
            p["deleted"] += d
            ar = area_of(path)
            touched[ar] += a + d
            if path in tree_paths:
                file_commits[path] += 1
                file_churn[path] += a + d
                file_last.setdefault(path, dt)
                file_who[path][cid] += 1
        for ar, lines_ in touched.items():
            s = area_stat.setdefault(ar, {"commits": 0, "lines": 0, "t": {k: [0, 0] for k in TYPES}, "who": {}, "first": dt, "last": dt, "recent": 0})
            s["commits"] += 1
            s["lines"] += lines_
            s["t"][t][0] += 1
            s["t"][t][1] += lines_
            s["first"], s["last"] = min(s["first"], dt), max(s["last"], dt)
            s["recent"] += dt >= cutoff
            w = s["who"].setdefault(cid, [0, 0, dt, 0])
            w[0] += 1
            w[1] += lines_
            w[2] = max(w[2], dt)
            w[3] += dt >= cutoff
            p["areas"][ar] += 1
    proc.wait()

    # ---- assemble contributor and area tables
    def pct(a, b):
        return round(100 * a / b, 1) if b else 0.0

    ranked = sorted(people.values(), key=lambda p: -p["commits"])
    by_type_counts = Counter(p["type"] for p in ranked)
    commits_by_type = Counter()
    for p in ranked:
        commits_by_type.update(p["by_type"])
    contributors = [{
        "id": p["id"], "name": p["name"], "type": p["type"], "commits": p["commits"], "share_pct": pct(p["commits"], total),
        "assisted_commits": p["assisted"], "commits_by_type": dict(p["by_type"]),
        "added": p["added"], "deleted": p["deleted"], "first": iso_day(p["first"]), "last": iso_day(p["last"]),
        "recent_commits_12m": p["recent"], "active_months": len(p["months"]),
        "top_areas": [{"area": a, "commits": c} for a, c in p["areas"].most_common(6)],
    } for p in ranked[:60]]

    areas = []
    for name, s in sorted(area_stat.items(), key=lambda kv: -kv[1]["commits"])[:60]:
        top_who = sorted(s["who"].items(), key=lambda kv: -kv[1][0])
        humans = [(cid, w) for cid, w in top_who if people[cid]["type"] == "human" or people[cid]["by_type"].get("human")]
        hum_total = sum(w[0] for _, w in humans)
        acc, need = 0, 0
        for _, w in humans:
            need += 1
            acc += w[0]
            if hum_total and acc / hum_total >= 0.8:
                break
        areas.append({
            "name": name, "files": area_files.get(name, 0), "exists": area_files.get(name, 0) > 0, "commits": s["commits"], "lines_changed": s["lines"],
            "by_type": {k: {"commits": v[0], "lines": v[1]} for k, v in s["t"].items()},
            "top": [{"name": people[cid]["name"], "type": people[cid]["type"], "commits": w[0], "share_pct": pct(w[0], s["commits"]),
                     "recent_12m": w[3], "last": iso_day(w[2])} for cid, w in top_who[:5]],
            "humans_for_80pct": need if hum_total else 0,
            "first_active": iso_day(s["first"]), "last_active": iso_day(s["last"]), "recent_commits_12m": s["recent"],
        })

    hot = []
    for path, c in file_commits.most_common(25):
        who = file_who[path].most_common(1)[0]
        hot.append({"path": path, "commits": c, "churn": file_churn[path], "last_changed": iso_day(file_last[path]),
                    "top_contributor": people[who[0]]["name"], "top_share_pct": pct(who[1], c)})

    tags = []
    for line in repo.git("tag", "--merged", sha, "--sort=-creatordate", "--format=%(refname:short)\x1f%(creatordate:short)", check=False).splitlines()[:10]:
        if "\x1f" in line:
            tags.append(dict(zip(("name", "date"), line.split("\x1f"))))

    # ---- languages, inventory
    code_total = sum(v["lines"] for v in lang_stats.values() if v["kind"] == "code") or 1
    all_total = sum(v["lines"] for v in lang_stats.values()) or 1
    languages = [{"name": n, "kind": v["kind"], "files": v["files"], "lines": v["lines"], "bytes": v["bytes"],
                  "share_pct": pct(v["lines"], code_total if v["kind"] == "code" else all_total)}
                 for n, v in sorted(lang_stats.items(), key=lambda kv: -kv[1]["lines"])]
    inventory = {}
    for cat, rx in INVENTORY.items():
        hits = sorted((p for p in area_paths if rx.search(p)), key=lambda p: (p.count("/"), p))
        inventory[cat] = {"count": len(hits), "paths": hits[:40]}

    # ---- chunk plan
    plan_files = [f for f in files if f["bytes"] > 0]
    chunks = plan_chunks(plan_files, chunk_tokens)
    total_tokens = sum(f["tokens"] for f in plan_files)
    advice = []
    if total_tokens <= chunk_tokens:
        mode = "single"
        advice.append("The whole repository fits in one pass. No chunking is needed.")
    else:
        mode = "chunked"
        advice.append(f"The repository is about {total_tokens:,} tokens. Review it in {len(chunks)} chunks of at most {chunk_tokens:,} tokens each.")
    if total_tokens > 400_000:
        size = "very large" if total_tokens > 1_500_000 else "large"
        advice.append(f"This is a {size} repository. Process the chunks with parallel subagents on the default model (Sonnet, 1M context window). "
                      "No model switch is needed.")

    facts = {
        "schema": 1,
        "repo": {"name": PurePosixPath(top).name, "path": top, "remote": remote, "ref": ref, "branch": branch, "sha": sha,
                 "short": sha[:10], "commit_date": iso_day(as_of), "subject": subject, "warnings": warnings,
                 "submodules": submodules},
        "git": {"commits": total, "merges": merges, "first_commit": iso_day(first_dt) if first_dt else None,
                "last_commit": iso_day(last_dt) if last_dt else None,
                "age_days": (last_dt - first_dt).days if first_dt else 0,
                "contributors": {"total": len(ranked), **{t: by_type_counts.get(t, 0) for t in TYPES}},
                "commits_by_type": {t: commits_by_type.get(t, 0) for t in TYPES},
                "agent_assisted_commits": assisted_total, "agent_assisted_by": dict(assisted_by),
                "tags": tags, "bulk_commits": bulk[:20], "bulk_commit_count": len(bulk),
                "monthly": dict(sorted(monthly.items())), "yearly": dict(sorted(yearly.items()))},
        "files": {"tracked": len(tree_paths), "analyzed": len(files), "excluded": dict(excluded),
                  "excluded_top_dirs": excluded_dirs.most_common(8), "tests": inventory["tests"]["count"],
                  "total_code_lines": sum(v["lines"] for v in lang_stats.values() if v["kind"] == "code"),
                  "total_lines": sum(v["lines"] for v in lang_stats.values())},
        "languages": languages,
        "hot_files": hot,
        "manifests": manifests,
        "readme": readme,
        "inventory": inventory,
        "env_vars": sorted(env_refs.values(), key=lambda e: (-e["count"], e["name"]))[:300],
        "secret_signals": {"note": "Pattern matches only; values are never stored. Each needs human review.",
                           "hits": secret_hits, "sensitive_files": sensitive[:50]},
        "contributors": {"people": contributors, "not_listed": max(0, len(ranked) - 60),
                         "classification_note": "Heuristic: bots and agents are recognised by name, email and commit-message markers. "
                                                "Anything else is treated as human and is unverified."},
        "areas": areas,
        "chunks": {"mode": mode, "budget": chunk_tokens, "total_tokens": total_tokens, "files": len(plan_files),
                   "chunk_count": len(chunks), "advice": advice,
                   "estimate": f"tokens are estimated as bytes / {BYTES_PER_TOKEN}"},
        "delta": None,
    }
    repo.close()
    return facts, {"budget": chunk_tokens, "total_tokens": total_tokens, "chunks": chunks}


# --------------------------------------------------------------------------- helpers


def remote_info(url):
    """Normalise a remote URL (credentials removed) and work out its web base."""
    if not url:
        return {"url": None, "web_base": None, "kind": None}
    url = re.sub(r"^(https?://)[^/@]+@", r"\1", url.strip())
    m = re.match(r"^(?:https?://|ssh://git@|git@)([^/:]+)[/:](.+?)(?:\.git)?/?$", url)
    if not m:
        return {"url": url, "web_base": None, "kind": None}
    host, path = m.groups()
    kind = "github" if "github" in host else "gitlab" if "gitlab" in host else "bitbucket" if "bitbucket" in host else None
    if kind and "." not in host:  # an ssh config alias such as github-work, not a real host name
        host = {"github": "github.com", "gitlab": "gitlab.com", "bitbucket": "bitbucket.org"}[kind]
    return {"url": url, "web_base": f"https://{host}/{path}" if kind else None, "kind": kind}


def delta(repo_path, prev_sha, sha, prev_snapshot, facts):
    """What changed since the last dossier build (used for incremental updates)."""
    repo = Repo(repo_path)
    ok = subprocess.run(["git", "-C", repo.path, "merge-base", "--is-ancestor", prev_sha, sha], capture_output=True).returncode == 0
    if not ok:
        return {"from": prev_sha, "note": "The previous build's commit is not an ancestor of this one (rebase, force-push or another branch). Treat everything as changed."}
    n = int(repo.git("rev-list", "--count", f"{prev_sha}..{sha}").strip() or 0)
    changed = [l.split("\t", 1) for l in repo.git("diff", "--name-status", "--no-renames", prev_sha, sha).splitlines() if "\t" in l]
    now_deps = {d["name"] for m in facts["manifests"] for d in m["dependencies"]}
    old_deps = set((prev_snapshot or {}).get("deps", []))
    return {"from": prev_sha, "commits_added": n, "files_changed": len(changed),
            "changed": [{"status": s, "path": p} for s, p in changed[:2000]],
            "dependencies_added": sorted(now_deps - old_deps)[:50] if prev_snapshot else None,
            "dependencies_removed": sorted(old_deps - now_deps)[:50] if prev_snapshot else None}


def snapshot(facts):
    return {"sha": facts["repo"]["sha"], "commits": facts["git"]["commits"], "code_lines": facts["files"]["total_code_lines"],
            "files": facts["files"]["tracked"], "contributors": facts["git"]["contributors"]["total"],
            "deps": sorted({d["name"] for m in facts["manifests"] for d in m["dependencies"]})}
