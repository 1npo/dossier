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
    $$("details, sup.cite, script, .mermaid-host svg, button" + (dropTables ? ", .badge, table, .table-container" : ""), c).forEach(function (n) { n.remove(); });
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
  // calendar cells carry a day or a month; the tooltip says who committed then, and how many lines they added and deleted
  var cal = null, calMonths = null;
  try { cal = JSON.parse($("#cal-data").textContent); } catch (e) {}
  function calTip(key) {
    var who = {}, tags = [], n = 0, add = 0, del = 0;
    Object.keys(cal.days).forEach(function (d) {
      if (d.indexOf(key) !== 0) return;
      var row = cal.days[d];
      Object.keys(row).forEach(function (id) {
        var w = who[id] || (who[id] = [0, 0, 0]);
        w[0] += row[id][0]; w[1] += row[id][1]; w[2] += row[id][2];
        n += row[id][0]; add += row[id][1]; del += row[id][2];
      });
    });
    Object.keys(cal.tags).forEach(function (d) { if (d.indexOf(key) === 0) tags = tags.concat(cal.tags[d]); });
    var num = function (v) { return v.toLocaleString(); }, plural = function (v) { return num(v) + " commit" + (v === 1 ? "" : "s"); };
    var diff = function (a, d) { return cal.lines ? '<span class="tp-add">+' + num(a) + '</span><span class="tp-del">\u2212' + num(d) + "</span>" : "<span></span><span></span>"; };
    var html = '<div class="tp-h">' + esc(key) + (n ? "" : " \u00b7 no commits") + "</div>";
    var rows = "";
    Object.keys(who).sort(function (a, b) { return who[b][0] - who[a][0]; }).forEach(function (id) {
      var p = cal.people[id] || ["Others", 8];
      rows += '<div class="tp-r"><i class="tp-dot" style="background:var(--l' + p[1] + ')"></i><span class="tp-n">' + esc(p[0]) + "</span><span class=\"tp-num\">" + num(who[id][0]) + " commit" + (who[id][0] === 1 ? "" : "s") + "</span>" + diff(who[id][1], who[id][2]) + "</div>";
    });
    if (Object.keys(who).length > 1) rows += '<div class="tp-rule"></div><div class="tp-r"><span></span><span class="tp-n">Total</span><span class="tp-num">' + num(n) + " commit" + (n === 1 ? "" : "s") + "</span>" + diff(add, del) + "</div>";
    if (rows) html += '<div class="tp-g">' + rows + "</div>";
    if (tags.length) html += '<div class="tp-t">Release tag: ' + esc(tags.join(", ")) + "</div>";
    return html;
  }
  function tipFor(a) {
    var r = a.getBoundingClientRect();
    tip.className = a.dataset.tipKind === "note" ? "note" : "";
    if (a.dataset.cal && cal) tip.innerHTML = calTip(a.dataset.cal); else tip.textContent = a.dataset.tip || a.dataset.cal;
    tip.hidden = false;
    var w = tip.offsetWidth, h = tip.offsetHeight;
    var left = Math.max(8, Math.min(r.left + r.width / 2 - w / 2, window.innerWidth - w - 8));
    var top = r.top - h - 6 < 8 ? r.bottom + 6 : r.top - h - 6;
    tip.style.left = left + "px"; tip.style.top = top + "px";
  }
  doc.addEventListener("mouseover", function (e) { var a = e.target.closest && e.target.closest("[data-tip], [data-cal]"); if (a) tipFor(a); });
  doc.addEventListener("mouseout", function (e) { if (e.target.closest && e.target.closest("[data-tip], [data-cal]")) tip.hidden = true; });
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
  // ---- "profiler facts" markers: a click explains what the measurement is and offers the profiler code that made it
  var facts = {}, pop = doc.createElement("div"), popFor = null;
  try { facts = JSON.parse($("#fact-data").textContent); } catch (e) {}
  pop.className = "fact-pop"; pop.hidden = true; pop.setAttribute("role", "dialog"); doc.body.appendChild(pop);
  function closePop() { pop.hidden = true; popFor = null; }
  function showFact(el) {
    var info = facts[el.dataset.fact]; if (!info) return false;
    var ref = (el.getAttribute("href") || "").match(/^#ref-(.+-\d+)$/) || (el.closest("li") && el.closest("li").id.match(/^ref-(.+-\d+)$/));
    var li = ref && doc.getElementById("ref-" + ref[1]);
    pop.innerHTML = "<h4>Profiler facts: " + esc(info.t) + "</h4><p>" + esc(info.x) + "</p><p>The profiler is the script that counts things in the repository before Claude writes any report, so these numbers are measured, not guessed.</p>" +
      (li && li.dataset.view ? '<div class="fp-row"><button type="button" class="btn" data-variant="outline" data-size="sm" data-open="' + ref[1] + '">View the profiler code</button></div>' : "");
    pop.hidden = false; popFor = el;
    var r = el.getBoundingClientRect(), w = pop.offsetWidth, h = pop.offsetHeight;
    pop.style.left = Math.max(8, Math.min(r.left, window.innerWidth - w - 8)) + "px";
    pop.style.top = (r.bottom + 8 + h > window.innerHeight && r.top - h - 8 > 8 ? r.top - h - 8 : r.bottom + 8) + "px";
    tip.hidden = true;
    return true;
  }
  doc.addEventListener("keydown", function (e) { if (e.key === "Escape" && !pop.hidden) closePop(); });
  window.addEventListener("resize", closePop);
  doc.addEventListener("click", function (e) {
    var t = e.target; if (!t.closest) return;
    var f = t.closest("[data-fact]");
    if (f && !(e.ctrlKey || e.metaKey || e.shiftKey || e.altKey || e.button)) {
      e.preventDefault(); if (popFor === f) closePop(); else showFact(f); return;
    }
    if (!t.closest(".fact-pop")) closePop(); else if (t.closest("[data-open]")) closePop();
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
    set(+box.dataset.zoomStart || 0);
  });
  // ---- contributor knowledge map: a tree of who knows which files, with an ownership bar per row and a minimap. Figures come from #km-data.
  (function () {
    var kmRoot = $("#km-root"), dataEl = $("#km-data"), D = null;
    if (!kmRoot || !dataEl) return;
    try { D = JSON.parse(dataEl.textContent); } catch (e) { return; }
    var RH = 28, HEAD_H = 30, OVERSCAN = 12, WINDOW_MIN = 400;   // rows are windowed only when there are more than WINDOW_MIN of them
    var people = D.contributors.slice(), nOwn = people.length;
    if (D.others) people.push(D.others);
    var K = people.length, FORMULA = {
      blend: "Familiarity blends surviving lines (50%), commits (30%) and commits in the last 12 months (20%).",
      lines: "Share of lines still attributed to each contributor by git blame.",
      commits: "Share of commits that touched each path.",
      recent: "Share of commits that touched each path in the 12 months before HEAD’s commit date. People with no commits in that window score zero." };
    var scroller = $("#km-scroller"), rowsEl = $("#km-rows"), chipsEl = $("#km-chips"), cv = $("#km-mini");
    var fmt = function (n) { return n.toLocaleString("en-US"); };
    var color = function (i) { return "var(--l" + people[i].cls + ")"; };
    var month = function (m) {
      if (!m) return "unknown";
      return new Date(Date.UTC(+m.slice(0, 4), +m.slice(5, 7) - 1, 1)).toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
    };

    // the tree, built from the flat list of files; directory totals are summed from their files
    var MAP = Object.create(null), TOP = [];
    function zeros() { var a = [], i; for (i = 0; i < K; i++) a.push(0); return a; }
    function cmp(a, b) { return a.type === b.type ? (a.name < b.name ? -1 : a.name > b.name ? 1 : 0) : (a.type === "dir" ? -1 : 1); }
    D.files.forEach(function (f) {
      var parts = f[0].split("/"), list = TOP, parent = null, path = "", i, d;
      for (i = 0; i < parts.length - 1; i++) {
        path = path ? path + "/" + parts[i] : parts[i];
        d = MAP[path];
        if (!d) {
          d = MAP[path] = { id: path, name: parts[i], path: path, depth: i + 1, type: "dir", children: [], L: zeros(), C: zeros(), R: zeros(), loc: 0, files: 0, last: "", sh: {}, parent: parent };
          list.push(d);
        }
        list = d.children; parent = d;
      }
      var n = { id: f[0], name: parts[parts.length - 1], path: f[0], depth: parts.length, type: "file", L: zeros(), C: zeros(), R: zeros(), loc: f[1], files: 1, last: f[2], sh: {}, parent: parent };
      f[3].forEach(function (t) { n.L[t[0]] = t[1]; n.C[t[0]] = t[2]; n.R[t[0]] = t[3]; });
      MAP[f[0]] = n; list.push(n);
    });
    function roll(n) {
      if (n.type === "file") return;
      n.children.forEach(function (c) {
        var i;
        roll(c);
        for (i = 0; i < K; i++) { n.L[i] += c.L[i]; n.C[i] += c.C[i]; n.R[i] += c.R[i]; }
        n.loc += c.loc; n.files += c.files;
        if (c.last > n.last) n.last = c.last;
      });
      n.children.sort(cmp);
    }
    TOP.forEach(roll); TOP.sort(cmp);

    // familiarity shares for a path under the chosen measure; a component whose total is zero is dropped and the blend renormalised
    function norm(a) {
      var t = 0, i;
      for (i = 0; i < a.length; i++) t += a[i];
      return t ? a.map(function (x) { return x / t; }) : null;
    }
    function shares(n, metric) {
      if (n.sh[metric]) return n.sh[metric];
      var r = null, parts, tw = 0;
      if (metric === "lines") r = norm(n.L);
      else if (metric === "commits") r = norm(n.C);
      else if (metric === "recent") r = norm(n.R);
      else {
        parts = [[norm(n.L), 0.5], [norm(n.C), 0.3], [norm(n.R), 0.2]].filter(function (p) { return p[0]; });
        parts.forEach(function (p) { tw += p[1]; });
        if (parts.length) { r = zeros(); parts.forEach(function (p) { p[0].forEach(function (x, i) { r[i] += x * p[1] / tw; }); }); }
      }
      n.sh[metric] = r || zeros();
      return n.sh[metric];
    }
    function topOf(sh) {
      var b = -1, s = 0;
      sh.forEach(function (x, i) { if (x > s) { s = x; b = i; } });
      return { i: b, s: s };
    }

    var state = { metric: "blend", focus: null, zoom: 2, view: "full", open: Object.create(null) };
    var VIS = [], focusId = null, win = { a: 0, b: 0 };
    function openForZoom(z) { state.open = Object.create(null); Object.keys(MAP).forEach(function (id) { if (MAP[id].type === "dir" && MAP[id].depth < z) state.open[id] = true; }); }
    function openAll() { Object.keys(MAP).forEach(function (id) { if (MAP[id].type === "dir") state.open[id] = true; }); }
    function keep(n) { return state.view !== "mine" || n.C[state.focus] > 0; }
    function visible() {
      var out = [];
      (function walk(list) {
        list.forEach(function (n) {
          if (!keep(n)) return;
          out.push(n);
          if (n.type === "dir" && state.open[n.id]) walk(n.children);
        });
      })(TOP);
      return out;
    }
    function defaultFocus() {
      var b = 0;
      D.contributors.forEach(function (p, i) { if (p.commits > D.contributors[b].commits) b = i; });
      return b;
    }

    var S = 'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"';
    var ICON = {
      chev: '<svg viewBox="0 0 16 16" width="13" height="13" ' + S + '><path d="M6 3.5 10.5 8 6 12.5"/></svg>',
      dir: '<svg class="km-ic" viewBox="0 0 16 16" ' + S + '><path d="M1.75 4.25a1 1 0 0 1 1-1h3l1.5 1.75h6a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-10.5a1 1 0 0 1-1-1z"/></svg>',
      file: '<svg class="km-ic" viewBox="0 0 16 16" ' + S + '><path d="M4 1.75h5l3.25 3.25v8.5a.75.75 0 0 1-.75.75h-7.5a.75.75 0 0 1-.75-.75v-11a.75.75 0 0 1 .75-.75z"/><path d="M9 1.75V5h3.25"/></svg>' };

    function rowHTML(n, idx) {
      var sh = shares(n, state.metric), isDir = n.type === "dir", open = isDir && state.open[n.id], f = state.focus, bar, top, dim = false, g = "", k, t, s, i;
      if (f === null) {
        bar = '<div class="km-bar">';
        for (i = 0; i < K; i++) if (sh[i] >= 0.03) bar += '<i class="' + (people[i].departed ? "g" : "") + '" style="flex:' + (sh[i] * 100).toFixed(2) + ' 1 0;background-color:' + color(i) + '"></i>';
        bar += "</div>";
        t = topOf(sh);
        if (t.i < 0) top = '<span class="km-none">' + (state.metric === "recent" ? "no recent activity" : "no activity") + "</span>";
        else {
          top = '<span class="km-dot" style="background:' + color(t.i) + '"></span><span class="km-tn">' + esc(people[t.i].short) + '</span><span class="km-pct">' + Math.round(t.s * 100) + "%</span>";
          if (isDir && people[t.i].departed && t.s >= 0.5) top += '<span class="badge basis-inferred" data-variant="outline">at risk</span>';
        }
      } else {
        s = sh[f]; dim = s < 0.03;
        bar = '<div class="km-bar fo"><b style="width:' + (s * 100).toFixed(1) + '%;background-color:' + color(f) + '"></b></div>';
        top = '<span class="km-pct strong">' + (s < 0.005 ? "–" : Math.round(s * 100) + "%") + "</span>";
      }
      for (k = 1; k < n.depth; k++) g += '<span class="km-gd"></span>';
      return '<div class="km-row' + (dim ? " dim" : "") + '" role="treeitem"' + (isDir ? ' aria-expanded="' + !!open + '"' : "") + ' aria-level="' + n.depth + '" data-id="' + esc(n.id) + '" tabindex="-1" style="top:' + idx * RH + 'px">' +
        '<div class="km-nm">' + g + '<span class="km-chev' + (open ? " o" : "") + '">' + (isDir ? ICON.chev : "") + "</span>" + (isDir ? ICON.dir : ICON.file) +
        '<span class="km-lbl">' + esc(n.name) + "</span>" + (isDir ? '<span class="km-cnt">' + n.files + "</span>" : "") + "</div>" +
        '<div class="km-bc">' + bar + '</div><div class="km-tc">' + top + "</div></div>";
    }

    // only the rows near the viewport are in the page once there are many; the minimap still draws every visible row
    function viewRange(over) {
      var n = VIS.length, st = scroller.scrollTop - HEAD_H;
      if (n <= WINDOW_MIN) return [0, n];
      return [Math.max(0, Math.floor(st / RH) - over), Math.min(n, Math.ceil((st + scroller.clientHeight) / RH) + over)];
    }
    function drawRows() {
      var had = scroller.contains(doc.activeElement), r = viewRange(OVERSCAN), h = "", i, kids, target = null;
      rowsEl.style.height = VIS.length * RH + "px";
      for (i = r[0]; i < r[1]; i++) h += rowHTML(VIS[i], i);
      rowsEl.innerHTML = h; win.a = r[0]; win.b = r[1];
      kids = rowsEl.children;
      for (i = 0; i < kids.length; i++) if (kids[i].dataset.id === focusId) target = kids[i];
      if (target) { target.tabIndex = 0; if (had) target.focus({ preventScroll: true }); }
      else if (kids.length) kids[0].tabIndex = 0;
    }
    function ensureWindow() {
      var r = viewRange(0);
      if (r[0] < win.a || r[1] > win.b) drawRows();
    }

    // minimap: one bar per visible row, stacked by person, indented by depth; the box is the part of the tree in view
    function drawMini() {
      var W = cv.clientWidth, H = cv.clientHeight, dpr = window.devicePixelRatio || 1, ctx, cs, n, rp, gap, f = state.focus, mapped, ratio, vy, vh;
      if (!W || !H) return;
      cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
      ctx = cv.getContext("2d"); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
      cs = getComputedStyle(root);
      var col = function (i) { return cs.getPropertyValue("--l" + people[i].cls).trim(); };
      n = VIS.length || 1; rp = Math.min(6, H / n); gap = rp >= 3 ? 1 : 0;
      VIS.forEach(function (r, idx) {
        var y = idx * rp, h = Math.max(1, rp - gap), ind = 4 + (r.depth - 1) * 4, avail = W - ind - 4, sh = shares(r, state.metric), x = ind, i, s;
        if (r.type === "file") avail *= 0.35 + 0.65 * Math.min(1, r.loc / 300);
        if (f === null) {
          for (i = 0; i < K; i++) { if (sh[i] < 0.02) continue; ctx.fillStyle = col(i); ctx.fillRect(x, y, avail * sh[i], h); x += avail * sh[i]; }
        } else {
          s = sh[f];
          if (s < 0.02) { ctx.globalAlpha = 0.12; ctx.fillStyle = cs.getPropertyValue("--muted-foreground").trim(); ctx.fillRect(ind, y, avail, h); ctx.globalAlpha = 1; return; }
          ctx.globalAlpha = 0.25 + 0.75 * Math.min(1, s / 0.7); ctx.fillStyle = col(f); ctx.fillRect(ind, y, avail, h); ctx.globalAlpha = 1;
        }
      });
      mapped = n * rp; ratio = mapped / Math.max(1, scroller.scrollHeight);
      vy = scroller.scrollTop * ratio; vh = Math.min(mapped, scroller.clientHeight * ratio);
      ctx.fillStyle = "rgba(128,128,128,.2)"; ctx.fillRect(0, vy, W, vh);
      ctx.strokeStyle = "rgba(128,128,128,.85)"; ctx.lineWidth = 1; ctx.strokeRect(0.5, vy + 0.5, W - 1, Math.max(2, vh - 1));
    }
    var raf = 0;
    function sched() { cancelAnimationFrame(raf); raf = requestAnimationFrame(drawMini); }
    (function () {
      var drag = false;
      function seek(e) {
        var r = cv.getBoundingClientRect(), H = cv.clientHeight, n = VIS.length || 1, mapped = n * Math.min(6, H / n);
        scroller.scrollTop = (e.clientY - r.top) * (scroller.scrollHeight / mapped) - scroller.clientHeight / 2;
      }
      cv.addEventListener("pointerdown", function (e) { drag = true; cv.setPointerCapture(e.pointerId); seek(e); });
      cv.addEventListener("pointermove", function (e) { if (drag) seek(e); });
      cv.addEventListener("pointerup", function () { drag = false; });
      cv.addEventListener("pointercancel", function () { drag = false; });
    })();
    if (window.ResizeObserver) { var ro = new ResizeObserver(function () { ensureWindow(); sched(); }); ro.observe(cv); ro.observe(scroller); }
    if (window.MutationObserver) new MutationObserver(sched).observe(root, { attributes: true, attributeFilter: ["class"] });   // the theme is the "dark" class on <html>

    // controls and chips
    function setPressed(sel, v) { $$(sel + " button", kmRoot).forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.v === String(v))); }); }
    function buildChips() {
      chipsEl.innerHTML = D.contributors.map(function (p, i) {
        return '<button type="button" class="btn km-chip' + (p.departed ? " gone" : "") + '" data-variant="outline" data-size="sm" data-i="' + i + '" aria-pressed="false" title="' + esc(p.name + (p.departed ? " (left)" : "") + ", last commit " + month(p.last)) + '">' +
          '<i class="km-sw" style="background-color:' + color(i) + '"></i>' + esc(p.short) + "<small>" + fmt(p.commits) + "</small></button>";
      }).join("");
    }
    function render() {
      VIS = visible();
      drawRows();
      drawMini();
      $("#km-th3").textContent = state.focus === null ? "Top contributor" : "Their share";
      $("#km-formula").textContent = FORMULA[state.metric];
      chipsEl.className = "km-chips" + (state.focus !== null ? " has" : "");
      $$(".km-chip", chipsEl).forEach(function (b) { b.setAttribute("aria-pressed", String(state.focus === +b.dataset.i)); });
      setPressed("#km-metric", state.metric); setPressed("#km-view", state.view); setPressed("#km-zoom", state.zoom);
    }
    function resetScroll() { focusId = null; scroller.scrollTop = 0; }
    $("#km-metric").addEventListener("click", function (e) { var b = e.target.closest("button"); if (!b) return; state.metric = b.dataset.v; render(); });
    $("#km-view").addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      state.view = b.dataset.v;
      if (state.view === "mine") { if (state.focus === null) state.focus = defaultFocus(); openAll(); } else openForZoom(state.zoom);
      resetScroll(); render();
    });
    $("#km-zoom").addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      state.zoom = +b.dataset.v;
      if (state.view === "mine") { openAll(); Object.keys(state.open).forEach(function (id) { if (MAP[id].depth >= state.zoom) delete state.open[id]; }); } else openForZoom(state.zoom);
      resetScroll(); render();
    });
    chipsEl.addEventListener("click", function (e) {
      var b = e.target.closest(".km-chip"); if (!b) return;
      var i = +b.dataset.i;
      if (state.view === "mine") { if (state.focus === i) return; state.focus = i; openAll(); scroller.scrollTop = 0; } else state.focus = state.focus === i ? null : i;
      render();
    });
    function toggle(id) { if (state.open[id]) delete state.open[id]; else state.open[id] = true; focusId = id; render(); }
    rowsEl.addEventListener("click", function (e) {
      var r = e.target.closest(".km-row"); if (!r) return;
      var n = MAP[r.dataset.id];
      if (n.type === "dir") toggle(n.id); else { focusId = n.id; r.focus(); }
    });

    // keyboard: Up and Down move, Right opens or steps into a folder, Left closes or steps out, Enter and Space toggle
    function moveTo(t) {
      var idx = VIS.indexOf(t), top = HEAD_H + idx * RH, kids, i;
      focusId = t.id;
      if (top < scroller.scrollTop + HEAD_H) scroller.scrollTop = top - HEAD_H;
      else if (top + RH > scroller.scrollTop + scroller.clientHeight) scroller.scrollTop = top + RH - scroller.clientHeight;
      drawRows();
      kids = rowsEl.children;
      for (i = 0; i < kids.length; i++) if (kids[i].dataset.id === t.id) { kids[i].focus({ preventScroll: true }); }
      sched();
    }
    scroller.addEventListener("keydown", function (e) {
      var row = e.target.closest(".km-row"); if (!row) return;
      var id = row.dataset.id, idx = VIS.indexOf(MAP[id]), n = VIS[idx], t = null;
      if (e.key === "ArrowDown") t = VIS[idx + 1];
      else if (e.key === "ArrowUp") t = VIS[idx - 1];
      else if (e.key === "ArrowRight" && n.type === "dir") {
        if (!state.open[id]) { e.preventDefault(); toggle(id); return; }
        t = VIS[idx + 1] && VIS[idx + 1].parent === n ? VIS[idx + 1] : null;
      } else if (e.key === "ArrowLeft") {
        if (n.type === "dir" && state.open[id]) { e.preventDefault(); toggle(id); return; }
        t = n.parent;
      } else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); if (n.type === "dir") toggle(id); return; }
      if (t) { e.preventDefault(); moveTo(t); }
    });
    scroller.addEventListener("scroll", function () { if (VIS.length > WINDOW_MIN) ensureWindow(); sched(); hideTip(); });

    // tooltip: follows the pointer and uses the page's shared tooltip element; not shown for touch
    function tipHTML(n) {
      var sh = shares(n, state.metric), order = [], h, i;
      for (i = 0; i < K; i++) if (sh[i] >= 0.01) order.push([sh[i], i]);
      order.sort(function (a, b) { return b[0] - a[0]; });
      h = '<div class="tp-h">' + esc(n.path) + (n.type === "dir" ? "/" : "") + '</div><div class="tp-m">' + (n.type === "dir" ? n.files + " files · " : "") + fmt(n.loc) + " lines · last change " + month(n.last) + "</div>";
      if (!order.length) return h + '<div class="tp-m">No contributor activity for this measure.</div>';
      h += '<div class="tp-g">';
      order.forEach(function (o) {
        var p = people[o[1]], name = p.name + (p.departed ? " (left)" : "") + (p.people ? " (" + p.people + " people)" : "");
        h += '<div class="tp-r"><i class="tp-dot" style="background:' + color(o[1]) + '"></i><span class="tp-n">' + esc(name) + '</span><span class="tp-num">' + fmt(n.L[o[1]]) + ' lines</span><span class="tp-num">' + fmt(n.C[o[1]]) + ' commits</span><span class="tp-num"><b>' + Math.round(o[0] * 100) + "%</b></span></div>";
      });
      return h + "</div>";
    }
    var tipId = "";
    function hideTip() { if (tipId) { tip.hidden = true; tipId = ""; } }
    rowsEl.addEventListener("pointermove", function (e) {
      var r = e.target.closest(".km-row"), w, h, x, y;
      if (!r || e.pointerType === "touch") { hideTip(); return; }
      if (tipId !== r.dataset.id || tip.hidden) { tip.className = ""; tip.innerHTML = tipHTML(MAP[r.dataset.id]); tipId = r.dataset.id; }
      tip.hidden = false;
      w = tip.offsetWidth; h = tip.offsetHeight; x = e.clientX + 16; y = e.clientY + 16;
      if (x + w > window.innerWidth - 8) x = e.clientX - w - 16;
      if (y + h > window.innerHeight - 8) y = window.innerHeight - h - 8;
      tip.style.left = Math.max(8, x) + "px"; tip.style.top = Math.max(8, y) + "px";
    });
    rowsEl.addEventListener("pointerleave", hideTip);

    buildChips(); openForZoom(state.zoom); render();
  })();

  $("#menu-toggle").addEventListener("click", function () { var sb = $(".sidebar"); if (sb && sb.toggle) sb.toggle(); });

  // keep the sticky header height in sync so anchors land below it
  function syncHeader() { var h = $(".masthead"); if (h) root.style.setProperty("--header-h", (h.offsetHeight + 12) + "px"); }
  window.addEventListener("resize", syncHeader); syncHeader();
  applyTheme(); show();
})();
