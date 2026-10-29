(function () {
  var doc = document, root = doc.documentElement;
  function $(s, r) { return (r || doc).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || doc).querySelectorAll(s)); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function escRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

  function alertHtml(title, text) {
    return '<div class="alert" data-variant="destructive"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><path d="M12 16h.01"/></svg><h2>' + esc(title) + "</h2><section>" + text + "</section></div>";
  }

  // ---- theme
  var theme = null;
  try { theme = localStorage.getItem("dossier-theme"); } catch (e) {}
  if (!theme) theme = window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  function applyTheme() {
    root.classList.toggle("dark", theme === "dark");
    $("#theme-toggle").setAttribute("aria-checked", String(theme === "dark"));
    initMermaid();
  }

  // ---- diagrams
  var seq = 0, failures = window.__dossierDiagramFailures = [];
  function initMermaid() {
    if (!window.mermaid) return;
    var dark = theme === "dark";
    // Pastel node fills with dark text in both themes, so boxes stay readable whatever classDef colours the diagram sets.
    mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "base",
      themeVariables: {
        darkMode: dark, background: "transparent", fontSize: "15px",
        primaryColor: "#dbe7ff", primaryTextColor: "#111827", primaryBorderColor: "#4b6cb7",
        secondaryColor: "#e6f4ea", secondaryTextColor: "#111827", secondaryBorderColor: "#3f8f5a",
        tertiaryColor: dark ? "#1f2937" : "#f3f4f6", tertiaryTextColor: dark ? "#f3f4f6" : "#111827", tertiaryBorderColor: dark ? "#6b7280" : "#9ca3af",
        lineColor: dark ? "#cbd5e1" : "#374151", textColor: dark ? "#f3f4f6" : "#111827", titleColor: dark ? "#f3f4f6" : "#111827",
        clusterBkg: dark ? "#1f2937" : "#f3f4f6", clusterBorder: dark ? "#6b7280" : "#9ca3af",
        edgeLabelBackground: "#f3f4f6", noteBkgColor: "#fff4c2", noteTextColor: "#111827", noteBorderColor: "#b59b2f",
        actorBkg: "#dbe7ff", actorTextColor: "#111827", actorBorder: "#4b6cb7", actorLineColor: dark ? "#cbd5e1" : "#374151",
        signalColor: dark ? "#f3f4f6" : "#111827", signalTextColor: dark ? "#f3f4f6" : "#111827",
        labelBoxBkgColor: "#dbe7ff", labelTextColor: "#111827", loopTextColor: dark ? "#f3f4f6" : "#111827"
      },
      fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif", fontSize: 15, flowchart: { useMaxWidth: true, htmlLabels: true },
      er: { useMaxWidth: true }, sequence: { useMaxWidth: true } });
  }
  function drawIn(section) {
    if (!window.mermaid) return;
    $$(".mermaid-host", section).forEach(function (host) {
      if (host.dataset.done === theme) return;
      var id = "dm" + (++seq);
      mermaid.render(id, host.dataset.src).then(function (out) {
        host.innerHTML = out.svg; host.dataset.done = theme; host.classList.remove("failed");
      }).catch(function (err) {
        var stray = doc.getElementById("d" + id); if (stray) stray.remove();
        host.classList.add("failed"); host.dataset.done = theme;
        var cap = host.closest(".diagram").querySelector("h3");
        failures.push((cap && cap.textContent || "Diagram") + ": " + (err && err.message || err));
        host.innerHTML = alertHtml("Diagram could not be drawn", 'Its source is under "Diagram source" below. ' + esc(err && err.message || err));
        var b = $("#diagram-banner"); b.hidden = false; b.innerHTML = alertHtml(failures.length + " diagram(s) could not be drawn", "The source of each is still available under the diagram.");
      });
    });
  }

  // ---- navigation: one report visible at a time
  function show() {
    var firstRep = $(".report"), id = decodeURIComponent(location.hash.slice(1)) || firstRep.id;
    var target = doc.getElementById(id) || firstRep;
    var section = target.closest(".report") || target;
    $$(".report").forEach(function (s) { s.hidden = s !== section; });
    $$("[data-nav]").forEach(function (a) { if (a.dataset.nav === section.id) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
    drawIn(section);
    if (target !== section) {
      target.scrollIntoView();
      target.classList.remove("flash"); void target.offsetWidth; target.classList.add("flash");
    } else window.scrollTo(0, 0);
  }
  window.addEventListener("hashchange", show);
  function go(id) { if (location.hash === "#" + id) show(); else location.hash = id; }

  // ---- search
  var input = $("#search"), results = $("#search-results"), navGroups = $("#nav-groups"), index = null, shown = [], active = -1;
  function textOf(el, dropTables) {
    var c = el.cloneNode(true);
    $$("details, sup.cite, .mermaid-host svg, button" + (dropTables ? ", .badge, table, .table-container" : ""), c).forEach(function (n) { n.remove(); });
    return c.textContent.replace(/\s+/g, " ").trim();
  }
  function buildIndex() {
    index = []; var n = 0;
    $$(".report").forEach(function (rep) {
      var rtitle = $("h1", rep).textContent.trim();
      $$(".card", rep).forEach(function (card) {
        if (card.classList.contains("refs-card") || card.classList.contains("toc-card")) return;
        var h = $("header h2, header h3", card), title = h ? textOf(h) : rtitle;
        if (!card.id) card.id = "s-" + rep.id + "-" + (++n);
        index.push({ id: card.id, report: rtitle, section: title, text: textOf(card, true), row: false });
        $$("tbody tr", card).forEach(function (tr) {
          if (!tr.id) tr.id = "r-" + rep.id + "-" + (++n);
          var cells = $$("td", tr).map(function (td) { return textOf(td); });
          index.push({ id: tr.id, report: rtitle, section: title, label: cells.filter(Boolean).slice(0, 2).join(" · "), text: cells.join(" | "), row: true });
        });
      });
    });
    index.forEach(function (e) { e.lower = (e.section + " " + e.text).toLowerCase(); });
  }
  function highlight(text, terms) {
    var re = new RegExp("(" + terms.map(escRe).join("|") + ")", "gi");
    return text.split(re).map(function (p, i) { return i % 2 ? "<mark>" + esc(p) + "</mark>" : esc(p); }).join("");
  }
  function snippet(text, terms) {
    var low = text.toLowerCase(), at = -1;
    terms.forEach(function (t) { var i = low.indexOf(t); if (i >= 0 && (at < 0 || i < at)) at = i; });
    var start = Math.max(0, at - 40), s = text.slice(start, start + 140);
    return (start > 0 ? "…" : "") + s + (start + 140 < text.length ? "…" : "");
  }
  function runSearch() {
    var q = input.value.trim().toLowerCase();
    if (!q) { results.hidden = true; navGroups.hidden = false; shown = []; return; }
    if (!index) buildIndex();
    var terms = q.split(/\s+/);
    shown = index.filter(function (e) { return terms.every(function (t) { return e.lower.indexOf(t) >= 0; }); })
      .map(function (e, i) { return { e: e, score: (terms.every(function (t) { return e.section.toLowerCase().indexOf(t) >= 0; }) ? 2 : 0) + (e.row ? 1 : 0), i: i }; })
      .sort(function (a, b) { return b.score - a.score || a.i - b.i; }).slice(0, 15).map(function (x) { return x.e; });
    navGroups.hidden = true; results.hidden = false; active = shown.length ? 0 : -1;
    results.innerHTML = shown.length ? shown.map(function (e, i) {
      var what = e.row ? e.label : e.section;
      return '<button type="button" class="result" role="option" data-i="' + i + '" aria-selected="' + (i === active) + '"><span class="where">' + esc(e.report) + (e.row ? " › " + esc(e.section) : "") +
        '</span><span class="what">' + highlight(what, terms) + '</span><span class="snip">' + highlight(snippet(e.row ? e.text : e.text, terms), terms) + "</span></button>";
    }).join("") : '<div class="no-results">No matches for "' + esc(input.value.trim()) + '".</div>';
  }
  function select(i) {
    active = Math.max(0, Math.min(shown.length - 1, i));
    $$(".result", results).forEach(function (b, k) { b.setAttribute("aria-selected", String(k === active)); if (k === active) b.scrollIntoView({ block: "nearest" }); });
  }
  function open(i) {
    var e = shown[i]; if (!e) return;
    input.value = ""; runSearch(); input.blur(); go(e.id);
  }
  input.addEventListener("input", runSearch);
  input.addEventListener("keydown", function (e) {
    if (e.key === "ArrowDown") { e.preventDefault(); select(active + 1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); select(active - 1); }
    else if (e.key === "Enter") { e.preventDefault(); open(Math.max(active, 0)); }
    else if (e.key === "Escape") { input.value = ""; runSearch(); input.blur(); }
  });
  results.addEventListener("click", function (e) { var b = e.target.closest(".result"); if (b) open(+b.dataset.i); });
  doc.addEventListener("keydown", function (e) {
    var t = e.target, typing = t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable);
    if ((e.key === "/" && !typing && !e.ctrlKey && !e.metaKey && !e.altKey) || ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k")) {
      e.preventDefault(); var sb = $(".sidebar"); if (sb && sb.open) sb.open(); input.focus(); input.select();
    }
  });
  var hint = $("#search-hint");
  input.addEventListener("focus", function () { hint.hidden = true; }); input.addEventListener("blur", function () { hint.hidden = false; });


  // ---- tooltips: appear the moment the pointer is over a source marker [n] or a note such as a gap ID
  var tip = doc.createElement("div"); tip.id = "cite-tip"; tip.hidden = true; tip.setAttribute("role", "tooltip"); doc.body.appendChild(tip);
  function tipFor(a) {
    var r = a.getBoundingClientRect();
    tip.className = a.dataset.tipKind === "note" ? "note" : "";
    tip.textContent = a.dataset.tip; tip.hidden = false;
    var w = tip.offsetWidth, h = tip.offsetHeight;
    var left = Math.max(8, Math.min(r.left + r.width / 2 - w / 2, window.innerWidth - w - 8));
    var top = r.top - h - 6 < 8 ? r.bottom + 6 : r.top - h - 6;
    tip.style.left = left + "px"; tip.style.top = top + "px";
  }
  doc.addEventListener("mouseover", function (e) { var a = e.target.closest && e.target.closest("[data-tip]"); if (a) tipFor(a); });
  doc.addEventListener("mouseout", function (e) { if (e.target.closest && e.target.closest("[data-tip]")) tip.hidden = true; });
  doc.addEventListener("focusin", function (e) { var a = e.target.closest && e.target.closest("[data-tip]"); if (a) tipFor(a); });
  doc.addEventListener("focusout", function () { tip.hidden = true; });
  window.addEventListener("scroll", function () { tip.hidden = true; }, true);

  // ---- sortable tables: every column header sorts its table
  var SEV = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
  function sortKey(td) {
    if (td.dataset.sort !== undefined) { var d = parseFloat(td.dataset.sort); return isNaN(d) ? td.dataset.sort.toLowerCase() : d; }
    var c = td.cloneNode(true); $$("sup.cite", c).forEach(function (n) { n.remove(); });
    var t = c.textContent.replace(/\s+/g, " ").trim().toLowerCase();
    if (t in SEV) return SEV[t];
    var m = /^[+\-]?\d[\d,]*(\.\d+)?/.exec(t);
    return m && !/^\d{4}-\d{2}/.test(t) && !/^[a-z]/.test(t) ? parseFloat(m[0].replace(/,/g, "")) : t;
  }
  // numeric collation puts R2 before R10 and G002 before G010
  var collate = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });
  function sortBy(table, col, dir) {
    var body = table.tBodies[0], rows = $$("tr", body).map(function (tr) { return { tr: tr, i: +tr.dataset.row, k: dir ? sortKey(tr.cells[col] || tr.cells[0]) : 0 }; });
    rows.sort(function (a, b) {
      if (!dir) return a.i - b.i;
      var x = a.k, y = b.k, r;
      if (typeof x === "number" && typeof y === "number") r = x - y;
      else if (typeof x === "number") r = -1; else if (typeof y === "number") r = 1;
      else r = collate.compare(x, y);
      return (r * dir) || a.i - b.i;
    });
    rows.forEach(function (r) { body.appendChild(r.tr); });
  }
  function makeSortable(table) {
    if (!table.tHead || !table.tBodies[0] || table.dataset.sortable || table.hasAttribute("data-nosort")) return;
    table.dataset.sortable = "1";
    $$("tr", table.tBodies[0]).forEach(function (tr, i) { tr.dataset.row = i; });
    var hr = table.tHead.rows[table.tHead.rows.length - 1];
    var wrap = table.closest(".table-container") || table, bar = doc.createElement("div"), reset = doc.createElement("button");
    bar.className = "tbl-bar"; reset.type = "button"; reset.className = "btn"; reset.hidden = true; reset.textContent = "Reset order";
    reset.setAttribute("data-variant", "outline"); reset.setAttribute("data-size", "sm"); reset.title = "Put the rows back in the order they were written";
    var filter = wrap.previousElementSibling;
    wrap.before(bar); if (filter && filter.classList.contains("tbl-filter")) bar.appendChild(filter); bar.appendChild(reset);
    function clear() { $$("th", hr).forEach(function (o) { o.removeAttribute("aria-sort"); }); reset.hidden = true; sortBy(table, 0, 0); }
    reset.addEventListener("click", clear);
    $$("th", hr).forEach(function (th, col) {
      var b = doc.createElement("button"); b.type = "button"; b.title = "Sort by this column; a third click restores the original order";
      while (th.firstChild) b.appendChild(th.firstChild);
      th.appendChild(b); th.classList.add("sortable");
      b.addEventListener("click", function () {
        var cur = th.getAttribute("aria-sort");
        if (cur === "descending") return clear();
        var dir = cur === "ascending" ? -1 : 1;
        $$("th", hr).forEach(function (o) { o.removeAttribute("aria-sort"); });
        th.setAttribute("aria-sort", dir === 1 ? "ascending" : "descending");
        reset.hidden = false;
        sortBy(table, col, dir);
      });
    });
  }
  $$("table.table").forEach(makeSortable);

  // ---- table filter, diagram expand
  doc.addEventListener("input", function (e) {
    var t = e.target; if (!t.classList || !t.classList.contains("tbl-filter")) return;
    var q = t.value.toLowerCase();
    $$("#" + t.dataset.target + " tbody tr").forEach(function (tr) { tr.hidden = q && tr.textContent.toLowerCase().indexOf(q) < 0; });
  });
  doc.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-expand]");
    if (b) setExpanded(b.closest(".diagram"), !b.closest(".diagram").classList.contains("expanded"));
  });
  function setExpanded(fig, on) {
    var b = $("[data-expand]", fig), label = on ? "Close" : "Expand";
    fig.classList.toggle("expanded", on); b.title = label; b.setAttribute("aria-label", label + " diagram");
  }
  doc.addEventListener("keydown", function (e) {
    if (e.key === "Escape") $$(".diagram.expanded").forEach(function (f) { setExpanded(f, false); });
  });
  $("#theme-toggle").addEventListener("click", function () {
    theme = theme === "dark" ? "light" : "dark";
    try { localStorage.setItem("dossier-theme", theme); } catch (e) {}
    applyTheme(); drawIn($(".report:not([hidden])"));
  });
  $("#menu-toggle").addEventListener("click", function () { var sb = $(".sidebar"); if (sb && sb.toggle) sb.toggle(); });

  // keep the sticky header height in sync so anchors land below it
  function syncHeader() { var h = $(".masthead"); if (h) root.style.setProperty("--header-h", (h.offsetHeight + 12) + "px"); }
  window.addEventListener("resize", syncHeader); syncHeader();
  applyTheme(); show();
})();
