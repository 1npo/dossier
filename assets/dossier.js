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
      e.preventDefault(); var sb = $(".sidebar"); if (sb && sb.open) sb.open(); setRail(false); input.focus(); input.select();
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

  // ---- code viewer: a source marker [n] opens the cited code in a panel on the right. The files are embedded in #code-data.
  var panel = $("#code-panel"), codeTab = $("#code-tab"), codeBody = $("#cp-body"), code = {}, cur = null, pinned = false, isOpen = false;
  try { code = JSON.parse($("#code-data").textContent); } catch (e) {}
  try { pinned = localStorage.getItem("dossier-code-pin") === "1"; } catch (e) {}
  function parseRef(h) { var m = /^#?ref-(.+)-(\d+)$/.exec(h || ""); return m && { rid: m[1], n: +m[2] }; }
  function refLi(rid, n) { return doc.getElementById("ref-" + rid + "-" + n); }
  function refList(rid) { return $$("#" + rid + "-refs .refs li[data-view]"); }
  function syncWidth() {   // the page makes room for a pinned panel unless that would leave it too narrow to read
    var w = isOpen && pinned && window.innerWidth - panel.offsetWidth >= 480 ? panel.offsetWidth : 0;
    root.style.setProperty("--code-w-px", w + "px");
  }
  function setOpen(on) {
    isOpen = on; panel.hidden = !on; codeTab.hidden = on || !cur;
    doc.body.classList.toggle("code-pinned", on && pinned); syncWidth();
  }
  function setPin(on) {
    pinned = on; $("#cp-pin").setAttribute("aria-pressed", String(on));
    try { localStorage.setItem("dossier-code-pin", on ? "1" : "0"); } catch (e) {}
    doc.body.classList.toggle("code-pinned", isOpen && on); syncWidth();
  }
  function showCode(li) {
    var path = li.dataset.view, f = code[path], a = +li.dataset.a || 0, b = +li.dataset.b || a;
    if (codeBody.dataset.path !== path) {
      codeBody.innerHTML = f.lines.map(function (t, i) { return '<div class="cl" data-n="' + (f.start + i) + '">' + t + "</div>"; }).join("");
      codeBody.dataset.path = path;
    }
    var rows = codeBody.children, first = null;
    for (var i = 0; i < rows.length; i++) {
      var hit = a > 0 && f.start + i >= a && f.start + i <= b;
      rows[i].classList.toggle("hit", hit);
      if (hit && !first) first = rows[i];
    }
    codeBody.scrollTop = first ? Math.max(0, first.offsetTop - codeBody.offsetTop - 3 * first.offsetHeight) : 0;
    var last = f.start + f.lines.length - 1;
    $(".cp-path", panel).textContent = path;
    $(".cp-win", panel).textContent = f.start > 1 || last < f.total ? "lines " + f.start.toLocaleString() + "-" + last.toLocaleString() + " of " + f.total.toLocaleString() : "";
  }
  function showNav() {
    var list = refList(cur.rid), i = list.indexOf(refLi(cur.rid, cur.n));
    $("#cp-count").textContent = (i + 1) + " / " + list.length;
    $("#cp-prev").disabled = i <= 0; $("#cp-next").disabled = i >= list.length - 1;
    var sup = cur.sup || $('#' + cur.rid + ' sup.cite a[href="#ref-' + cur.rid + "-" + cur.n + '"]').parentElement;
    var srcs = $$("a[data-view]", sup), row = $("#cp-sources");
    row.hidden = srcs.length < 2;
    row.innerHTML = srcs.length < 2 ? "" : "Sources for this statement: " + srcs.map(function (a) {
      var r = parseRef(a.getAttribute("href"));
      return '<button type="button" class="btn" data-variant="outline" data-size="sm" data-src="' + r.n + '"' + (r.n === cur.n ? ' aria-current="true"' : "") + ">" + esc(a.textContent + " " + a.dataset.tip) + "</button>";
    }).join("");
    cur.sup = sup;
  }
  function openRef(rid, n, sup) {
    var li = refLi(rid, n); if (!li || !code[li.dataset.view]) return;
    cur = { rid: rid, n: n, sup: sup || null };
    setOpen(true); showCode(li); showNav();
  }
  function step(d) {
    var list = refList(cur.rid), li = list[Math.max(0, Math.min(list.length - 1, list.indexOf(refLi(cur.rid, cur.n)) + d))];
    if (li) openRef(cur.rid, parseRef("#" + li.id).n, null);
  }
  function toggleCode() {
    if (isOpen) return setOpen(false);
    if (cur) return setOpen(true);
    var a = $(".report:not([hidden]) sup.cite a[data-view]"), r = a && parseRef(a.getAttribute("href"));
    if (r) openRef(r.rid, r.n, a.parentElement);
  }
  function gotoRef() {
    var id = "ref-" + cur.rid + "-" + cur.n;
    if (!pinned) setOpen(false);
    go(id);
  }
  doc.addEventListener("click", function (e) {
    var t = e.target; if (!t.closest) return;
    var a = t.closest("sup.cite a[data-view]");
    if (a && !(e.ctrlKey || e.metaKey || e.shiftKey || e.altKey || e.button)) {
      var r = parseRef(a.getAttribute("href")); e.preventDefault(); openRef(r.rid, r.n, a.parentElement); return;
    }
    var open = t.closest("[data-open]");
    if (open) { var k = open.dataset.open.lastIndexOf("-"); openRef(open.dataset.open.slice(0, k), +open.dataset.open.slice(k + 1), null); return; }
    if (t.closest("#code-tab")) return toggleCode();
    if (t.closest("#code-panel")) {
      var id = t.closest("button") && t.closest("button").id, src = t.closest("[data-src]");
      if (src) openRef(cur.rid, +src.dataset.src, cur.sup);
      else if (id === "cp-prev") step(-1); else if (id === "cp-next") step(1);
      else if (id === "cp-goto") gotoRef(); else if (id === "cp-pin") setPin(!pinned); else if (id === "cp-close") setOpen(false);
      return;
    }
    if (isOpen && !pinned) setOpen(false);
  });
  // runs before the diagram handler below, so Esc closes an expanded diagram first
  doc.addEventListener("keydown", function (e) {
    var t = e.target, typing = t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable);
    if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === "v") toggleCode();
    else if (e.key === "p") setPin(!pinned);
    else if (e.key === "[" && isOpen) step(-1);
    else if (e.key === "]" && isOpen) step(1);
    else if (e.key === "Escape" && isOpen && !pinned && !$(".diagram.expanded")) setOpen(false);
  });
  window.addEventListener("resize", syncWidth);
  $("#cp-pin").setAttribute("aria-pressed", String(pinned));

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
  // ---- sidebar: collapse to a rail of icons on wide screens
  var railBtn = $("#rail-toggle");
  function setRail(on) {
    root.classList.toggle("rail", on);
    railBtn.setAttribute("aria-expanded", String(!on));
    var label = on ? "Expand the sidebar" : "Collapse the sidebar";
    railBtn.title = label; railBtn.setAttribute("aria-label", label);
    try { localStorage.setItem("dossier-rail", on ? "1" : "0"); } catch (e) {}
  }
  var railOn = false; try { railOn = localStorage.getItem("dossier-rail") === "1"; } catch (e) {}
  setRail(railOn);
  railBtn.addEventListener("click", function () { setRail(!root.classList.contains("rail")); });
  $("#rail-search").addEventListener("click", function () { setRail(false); input.focus(); input.select(); });
  $("#rail-theme").addEventListener("click", function () { $("#theme-toggle").click(); });

  // ---- calendar zoom
  $$("[data-zoom-root]").forEach(function (box) {
    var lv = $$("[data-zoom-level]", box), name = $(".zoom-name", box), names = name.dataset.zoomNames.split("|"), at = 0;
    var out = $('[data-zoom="-1"]', box), inn = $('[data-zoom="1"]', box);
    function set(n) {
      at = Math.max(0, Math.min(lv.length - 1, n));
      lv.forEach(function (el, i) { el.hidden = i !== at; });
      name.textContent = names[at]; out.disabled = at === 0; inn.disabled = at === lv.length - 1;
    }
    out.addEventListener("click", function () { set(at - 1); }); inn.addEventListener("click", function () { set(at + 1); });
  });
  $("#menu-toggle").addEventListener("click", function () { var sb = $(".sidebar"); if (sb && sb.toggle) sb.toggle(); });

  // keep the sticky header height in sync so anchors land below it
  function syncHeader() { var h = $(".masthead"); if (h) root.style.setProperty("--header-h", (h.offsetHeight + 12) + "px"); }
  window.addEventListener("resize", syncHeader); syncHeader();
  applyTheme(); show();
})();
