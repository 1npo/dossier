"""The portfolio page: one HTML file, `<home>/index.html`, that lists every dossier under the dossier home.

It is a homepage, not a report. It reads only what each dossier already wrote (`summary.json`, `state.json`,
`facts.json`, and the name of its `dossier-<name>.html`), draws one card per dossier with the same theme as the
dossiers, and links each card to that dossier's page by a relative path. The file is self-contained (CSS and the
few lines of script are inline) and is rewritten whole every time, so it never goes stale: `render` calls
`write()` after each dossier it writes, and `dossier portfolio` calls it on demand.
"""
from __future__ import annotations

import html
import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

import render

FILE = "index.html"
E = html.escape
SEVERITIES = ("critical", "high", "medium", "low")
LANG_COLORS = ("var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)")


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def entry(d: Path, version: str, now: datetime) -> dict | None:
    """What one dossier folder contributes to the portfolio, or None when it is not a built dossier."""
    pages = sorted(d.glob("dossier-*.html"))
    if not pages:
        return None
    summary = _load(d / "summary.json") or {}
    state = _load(d / "state.json") or {}
    repo = summary.get("repo") or {}
    history = state.get("history") or []
    last = history[-1] if history else {}
    desc = ""
    facts = _load(d / "facts.json")
    if facts:
        try:
            desc = render.masthead(facts, {}).get("description") or ""
        except Exception:          # a description is a nicety: never let it stop the portfolio
            desc = ""
    built = summary.get("generated_at") or last.get("date") or datetime.fromtimestamp(pages[0].stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        age = (now - datetime.strptime(built, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).days
    except ValueError:
        age = None
    gaps = summary.get("gaps") or last.get("gaps") or {}
    return {
        "name": repo.get("name") or d.name, "folder": d.name, "page": f"{d.name}/{pages[0].name}",
        "description": re.sub(r"\s+", " ", desc).strip(), "branch": repo.get("branch") or last.get("branch") or "",
        "sha": (repo.get("sha") or last.get("sha") or "")[:10], "commit_date": repo.get("commit_date") or "",
        "built": built, "age_days": age, "remote": repo.get("remote") or "",
        "languages": (summary.get("languages") or [])[:5], "components": len(summary.get("components") or []),
        "entry_points": len(summary.get("entry_points") or []), "risks": summary.get("risks") or {},
        "open_inferences": gaps.get("inference", 0), "open_unknowns": gaps.get("unknown", 0),
        "builds": len(history), "change": (last.get("summary") or "").strip(),
        "outdated": bool(summary.get("dossier_version") or last.get("skill_version")) and
                    (summary.get("dossier_version") or last.get("skill_version")) != version,
        "has_summary": bool(summary),
    }


def collect(home: Path, version: str, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    items = [e for d in sorted(home.iterdir()) if d.is_dir() and not d.name.startswith(".")
             for e in [entry(d, version, now)] if e]
    return sorted(items, key=lambda e: e["built"], reverse=True)


def ago(days) -> str:
    if days is None:
        return "built at an unknown time"
    if days <= 0:
        return "built today"
    if days == 1:
        return "built yesterday"
    if days < 60:
        return f"built {days} days ago"
    return f"built {days // 30} months ago"


def lang_bar(langs) -> str:
    if not langs:
        return ""
    segs = "".join(f'<i style="flex:{max(l.get("share", 0), 1.5)};background:{LANG_COLORS[i % 5]}" title="{E(l["name"])} {l.get("share", 0)}%"></i>'
                   for i, l in enumerate(langs))
    names = " · ".join(f'{E(l["name"])} {l.get("share", 0):g}%' for l in langs[:3])
    return f'<div class="langs"><div class="bar" aria-hidden="true">{segs}</div><span class="muted">{names}</span></div>'


def risk_pills(risks: dict) -> str:
    out = "".join(f'<span class="badge risk-{s}" data-variant="outline">{risks[s]} {s}</span>' for s in SEVERITIES if risks.get(s))
    return out or '<span class="badge basis-confirmed" data-variant="outline">no risks above info</span>'


def card(e: dict) -> str:
    open_n = e["open_inferences"] + e["open_unknowns"]
    stale = '<span class="badge" data-variant="secondary" title="Built by an older version of the skill. Build again to refresh it.">older skill</span>' if e["outdated"] else ""
    commit = f'<div class="chips"><span class="badge" data-variant="outline">{E(e["branch"])}</span><span class="badge" data-variant="outline">{E(e["sha"])}</span></div>' if e["sha"] else ""
    change = f'<p class="muted change">{E(e["change"])}</p>' if e["change"] and e["builds"] > 1 else ""
    stats = (f'<dl class="stats"><div><dt>Components</dt><dd>{e["components"]}</dd></div>'
             f'<div><dt>Entry points</dt><dd>{e["entry_points"]}</dd></div>'
             f'<div><dt>Open items</dt><dd>{open_n}</dd></div></dl>') if e["has_summary"] else ""
    builds = f" · {e['builds']} builds" if e["builds"] > 1 else ""
    key = E(" ".join([e["name"], e["description"], e["branch"]] + [l["name"] for l in e["languages"]]).lower())
    return (f'<a class="card dcard" href="{E(e["page"])}" data-key="{key}" data-built="{E(e["built"])}" data-name="{E(e["name"].lower())}">'
            f'<div class="bar"><span class="muted">{ago(e["age_days"])}{builds}</span>{stale}</div>'
            f'<header><h2>{E(e["name"])}</h2>{commit}'
            f'<p>{E(e["description"][:200]) or "No description found in the repository."}</p></header>'
            f'<section>{stats}{lang_bar(e["languages"])}<div class="chips">{risk_pills(e["risks"])}</div></section>{change}</a>')


EXTRA_CSS = """
body { min-height: 100vh; }
.wrap { max-width: 72rem; margin: 0 auto; padding: 0 2rem 4rem; }
.top { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 1.25rem 0; border-bottom: 1px solid var(--border); }
.top .lead { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
.hero { padding: 2rem 0 1rem; } .hero h1 { font-size: 1.75rem; }
.summary { display: flex; flex-wrap: wrap; gap: .75rem; margin-top: 1rem; }
.summary div { display: flex; flex-direction: column; padding: .6rem 1rem; border: 1px solid var(--border); border-radius: var(--radius); background: var(--card); } .summary b { font-size: 1.5rem; font-variant-numeric: tabular-nums; line-height: 1.2; }
.summary span { font-size: .75rem; text-transform: uppercase; letter-spacing: .1em; color: var(--muted-foreground); }
.tools { display: flex; flex-wrap: wrap; gap: .75rem; align-items: center; margin: 1.5rem 0 1rem; }
.tools select { font: inherit; padding: .4rem .6rem; border: 1px solid var(--border); border-radius: var(--radius); background: var(--card); color: var(--foreground); }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(21rem, 1fr)); gap: 1rem; }
a.dcard { display: flex; flex-direction: column; text-decoration: none; color: inherit; transition: border-color .15s, transform .15s; }
a.dcard:hover, a.dcard:focus-visible { border-color: var(--foreground); transform: translateY(-1px); outline: none; }
.dcard header { display: grid; gap: .25rem; } .dcard h2 { font-size: 1.125rem; } .dcard header p { margin: 0; color: var(--muted-foreground); font-size: .875rem; }
.dcard .bar { display: flex; justify-content: space-between; align-items: center; gap: .5rem; margin-top: -1rem; padding: .6rem 1rem; border-bottom: 1px solid var(--border); background: var(--muted); font-size: .8125rem; }
.dcard { position: relative; } .dcard section { display: grid; gap: .85rem; flex: 1; }
.dcard .change { margin: 0; padding: 0 1.5rem 1rem; font-size: .8125rem; }
.langs .bar { display: flex; height: .45rem; border-radius: 99px; overflow: hidden; gap: 2px; margin-bottom: .35rem; } .langs .bar i { display: block; min-width: 4px; }
.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: .5rem; margin: 0; }
.stats > div { padding: .5rem .75rem; border: 1px solid var(--border); border-radius: var(--radius); background: var(--muted); }
.tools .search { position: relative; margin: 0; flex: 1 1 16rem; max-width: 24rem; } .tools .search .input { width: 100%; padding-left: 2.1rem; padding-right: 2.2rem; }
.stats dt { font-size: .6875rem; text-transform: uppercase; letter-spacing: .08em; color: var(--muted-foreground); } .stats dd { margin: 0; font-size: 1.25rem; font-weight: 600; font-variant-numeric: tabular-nums; }
.badge.risk-critical, .badge.risk-high { color: var(--destructive); border-color: var(--destructive); }
.badge.risk-medium { background: var(--warn-bg); color: var(--warn); border-color: var(--warn); }
.empty { padding: 3rem 1rem; text-align: center; color: var(--muted-foreground); } .empty[hidden] { display: none; }
.foot { margin-top: 3rem; text-align: center; }
@media (max-width: 40rem) { .wrap { padding: 0 1rem 3rem; } .grid { grid-template-columns: 1fr; } }
"""

SCRIPT = """
(function () {
  var root = document.documentElement, theme = null;
  try { theme = localStorage.getItem("dossier-theme"); } catch (e) {}
  if (!theme) theme = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  var tg = document.getElementById("theme-toggle");
  function apply() { root.classList.toggle("dark", theme === "dark"); tg.setAttribute("aria-checked", String(theme === "dark")); }
  tg.addEventListener("click", function () { theme = theme === "dark" ? "light" : "dark"; try { localStorage.setItem("dossier-theme", theme); } catch (e) {} apply(); });
  apply();
  var grid = document.getElementById("grid"), cards = [].slice.call(grid.children), q = document.getElementById("q"), sort = document.getElementById("sort"), none = document.getElementById("none");
  function run() {
    var t = q.value.trim().toLowerCase(), shown = 0;
    cards.sort(function (a, b) { return sort.value === "name" ? a.dataset.name.localeCompare(b.dataset.name) : b.dataset.built.localeCompare(a.dataset.built); });
    cards.forEach(function (c) { var ok = !t || c.dataset.key.indexOf(t) >= 0; c.hidden = !ok; if (ok) shown++; grid.appendChild(c); });
    none.hidden = shown > 0;
  }
  q.addEventListener("input", run); sort.addEventListener("change", run);
  var hint = document.getElementById("search-hint");
  if (hint) { q.addEventListener("focus", function () { hint.hidden = true; }); q.addEventListener("blur", function () { hint.hidden = false; }); }
  document.addEventListener("keydown", function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    if (e.key === "/" && document.activeElement !== q) { e.preventDefault(); q.focus(); }
    else if (e.key === "t" && !typing) tg.click();
  });
})();
"""


def page(items: list[dict], version: str, home: Path) -> str:
    n_risk = sum(i["risks"].get(s, 0) for i in items for s in ("critical", "high"))
    newest = items[0]["built"][:10] if items else ""
    summary = (f'<div class="summary"><div><b>{len(items)}</b><span>dossier{"" if len(items) == 1 else "s"}</span></div>'
               f'<div><b>{n_risk}</b><span>critical or high risks</span></div>'
               f'<div><b>{sum(i["components"] for i in items)}</b><span>components mapped</span></div></div>')
    built = f'<span class="chips"><span class="badge" data-variant="outline">Last built {E(newest)}</span></span>' if items else ""
    brand_text = f'<div class="brand-text"><span class="brand-name">Dossier</span><span class="brand-ver">v{E(version)}</span></div>'
    brand = ('<svg class="brand-icon" xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
             'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="11"/><g transform="translate(12 12) scale(0.625) translate(-12 -12)" stroke-width="3.2">'
             '<path d="M12 22V12"/><path d="M21 10.498V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.729l7 4a2 2 0 0 0 2 .001l.98-.559"/>'
             '<path d="M3.29 7 12 12l8.71-5"/><path d="m7.5 4.27 8.997 5.148"/><circle cx="18.5" cy="16.5" r="2.5"/></g></svg>')
    toggle = ('<button id="theme-toggle" class="theme-switch" type="button" role="switch" aria-checked="false" aria-label="Dark mode">'
              '<svg class="sun" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>'
              '<svg class="moon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>'
              '<span class="thumb"></span></button>')
    if items:
        body = (f'<div class="tools"><div class="search"><svg class="search-icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>'
                f'<input id="q" class="input" type="text" placeholder="Filter dossiers" aria-label="Filter dossiers" autocomplete="off" spellcheck="false"><kbd id="search-hint">/</kbd></div>'
                f'<select id="sort" aria-label="Sort"><option value="built">Most recently built</option><option value="name">Name</option></select></div>'
                f'<div class="grid" id="grid">{"".join(card(i) for i in items)}</div><p class="empty" id="none" hidden>No dossier matches that filter.</p>')
    else:
        body = '<p class="empty">No dossiers yet. Run <code>/dossier build</code> in a repository to make the first one.</p><div id="grid"></div><input id="q"><select id="sort"></select><p id="none"></p>'
    css = render.load_asset(render.VENDOR / "basecoat.min.css") + "\n" + render.load_asset(render.ASSETS / "dossier.css") + EXTRA_CSS
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta name="generator" content="dossier"><title>Dossiers</title><style>{css}</style></head><body><div class="wrap">'
            f'<header class="top"><div class="lead"><div class="brand">{brand}{brand_text}</div>{built}</div>{toggle}</header>'
            f'<section class="hero"><h1>Your dossiers</h1>{summary if items else ""}</section>'
            f'{body}<footer class="foot muted">Generated by the dossier skill v{E(version)} from <code>{E(str(home))}</code>. This page is rewritten every time a dossier is built.</footer>'
            f'</div><script>{SCRIPT}</script></body></html>\n')


def write(home: Path, version: str) -> Path:
    """Rewrite `<home>/index.html` from the dossiers now under `home`. Atomic, so a viewer never sees half a page."""
    home = Path(home)
    path = home / FILE
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(page(collect(home, version), version, home), encoding="utf-8")
    os.replace(tmp, path)
    return path
