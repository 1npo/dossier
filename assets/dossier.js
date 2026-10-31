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
  // ---- "measured facts" markers: a click explains what the measurement is and offers the gatherer code that made it
  var facts = {}, pop = doc.createElement("div"), popFor = null;
  try { facts = JSON.parse($("#fact-data").textContent); } catch (e) {}
  pop.className = "fact-pop"; pop.hidden = true; pop.setAttribute("role", "dialog"); doc.body.appendChild(pop);
  function closePop() { pop.hidden = true; popFor = null; }
  function showFact(el) {
    var info = facts[el.dataset.fact]; if (!info) return false;
    var ref = (el.getAttribute("href") || "").match(/^#ref-(.+-\d+)$/) || (el.closest("li") && el.closest("li").id.match(/^ref-(.+-\d+)$/));
    var li = ref && doc.getElementById("ref-" + ref[1]);
    pop.innerHTML = "<h4>Measured facts: " + esc(info.t) + "</h4><p>" + esc(info.x) + "</p><p>The gatherer is the script that counts things in the repository before Claude writes any report, so these numbers are measured, not guessed.</p>" +
      (li && li.dataset.view ? '<div class="fp-row"><button type="button" class="btn" data-variant="outline" data-size="sm" data-open="' + ref[1] + '">View the gatherer code</button></div>' : "");
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
      lines: "Share of lines still attributed to each contributor by git blame.",
      commits: "Share of commits that touched each path." };
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

    // familiarity shares for a path under the chosen measure
    function norm(a) {
      var t = 0, i;
      for (i = 0; i < a.length; i++) t += a[i];
      return t ? a.map(function (x) { return x / t; }) : null;
    }
    function shares(n, metric) {
      if (!n.sh[metric]) n.sh[metric] = norm(metric === "commits" ? n.C : n.L) || zeros();
      return n.sh[metric];
    }
    function topOf(sh) {
      var b = -1, s = 0;
      sh.forEach(function (x, i) { if (x > s) { s = x; b = i; } });
      return { i: b, s: s };
    }

    var state = { metric: "lines", focus: null, zoom: 99, view: "full", open: Object.create(null) };
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
        if (t.i < 0) top = '<span class="km-none">' + "no activity" + "</span>";
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

    // with more rows than pixels, rows are grouped into one-pixel bands and each band draws the average of its rows, instead of the last row painting over the others
    function drawBands(ctx, cs, col, rp, W) {
      var f = state.focus, bands = [], b, i, x, w, frac;
      VIS.forEach(function (r, idx) {
        var y = Math.floor(idx * rp), ind = 4 + (r.depth - 1) * 4, avail = W - ind - 4, sh = shares(r, state.metric);
        if (r.type === "file") avail *= 0.35 + 0.65 * Math.min(1, r.loc / 300);
        b = bands[y] || (bands[y] = { n: 0, ind: 0, avail: 0, seg: zeros() });
        b.n++; b.ind += ind; b.avail += avail;
        for (i = 0; i < K; i++) b.seg[i] += avail * sh[i];
      });
      bands.forEach(function (b, y) {
        var ind = b.ind / b.n, avail = b.avail / b.n;
        if (f === null) {
          x = ind;
          for (i = 0; i < K; i++) { frac = b.seg[i] / b.avail; if (frac < 0.02) continue; w = avail * frac; ctx.fillStyle = col(i); ctx.fillRect(x, y, w, 1); x += w; }
        } else {
          frac = b.seg[f] / b.avail;
          if (frac < 0.02) { ctx.globalAlpha = 0.12; ctx.fillStyle = cs.getPropertyValue("--muted-foreground").trim(); }
          else { ctx.globalAlpha = 0.25 + 0.75 * Math.min(1, frac / 0.7); ctx.fillStyle = col(f); }
          ctx.fillRect(ind, y, avail, 1); ctx.globalAlpha = 1;
        }
      });
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
      if (rp < 1) drawBands(ctx, cs, col, rp, W);
      else VIS.forEach(function (r, idx) {
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

    $("#km-vw").addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      var files = b.dataset.v === "files";
      $("#km-pane-people").hidden = files; $("#km-pane-files").hidden = !files;
      setPressed("#km-vw", b.dataset.v);
      $("#km-metric-ctl").hidden = !files;
      if (files) render();   // the minimap needs its size, which a hidden pane does not have
    });

    buildChips(); openForZoom(state.zoom); render();
  })();

  // ---- dependencies card: six views of which files import which packages. Figures come from #dp-data; breadth, spread and depth are worked out here.
  (function () {
    var rootEl = $("#dp-root"), dataEl = $("#dp-data"), D = null;
    if (!rootEl || !dataEl) return;
    try { D = JSON.parse(dataEl.textContent); } catch (e) { return; }
    var MODS = D.modules, DEPS = D.deps, FILES = D.files, STORE = "dossier-dep-card";
    var CATS = ["Framework", "Data", "Tooling", "Testing", "Utilities", "Other"];
    var MEAS = { breadth: "Breadth", spread: "Spread", depth: "Depth" };
    var HAS_TR = DEPS.some(function (d) { return d.tr != null; });
    var stage = $("#dp-stage", rootEl);
    var state = { view: "files", measure: "breadth", scope: "all", all: false, zoom: 99, show: "all", focus: null, open: Object.create(null), sel: null };
    try {
      var sv = JSON.parse(localStorage.getItem(STORE) || "{}");
      if (MEAS[sv.measure]) state.measure = sv.measure;
      if (["all", "runtime", "dev"].indexOf(sv.scope) >= 0) state.scope = sv.scope;
    } catch (e) {}
    var catVar = function (c) { return "var(--dp-" + c.toLowerCase() + ")"; };
    var pct = function (x) { return Math.round(x * 100); };
    var fmt = function (n) { return n.toLocaleString("en-US"); };
    var CAT = Object.create(null); DEPS.forEach(function (d) { CAT[d.n] = d.c; });
    var BYNAME = Object.create(null); DEPS.forEach(function (d) { BYNAME[d.n] = d; });
    var plural = function (n, w) { return n + " " + w + (n === 1 ? "" : "s"); };

    // ---- measures, for the dependencies in the chosen scope
    function list() {
      var l = DEPS.filter(function (d) { return state.scope === "all" || d.s === state.scope; });
      var mf = 1, mm = 1, ms = 1;
      l.forEach(function (d) { d.files = d.src + d.tst; d.spread = Object.keys(d.mods).length; mf = Math.max(mf, d.files); mm = Math.max(mm, d.spread); ms = Math.max(ms, d.sym); });
      l.forEach(function (d) { d.b = d.files / mf; d.sp = d.spread / mm; d.dp = d.sym / ms; });
      return l;
    }
    var val = function (d) { return state.measure === "spread" ? d.sp : state.measure === "depth" ? d.dp : d.b; };
    var ranked = function (l) { return l.slice().sort(function (a, b) { return val(b) - val(a) || b.files - a.files || (a.n < b.n ? -1 : 1); }); };
    var EMPTY = '<p class="muted">No dependencies in this scope are imported by any file.</p>';

    function catLegend() {
      var seen = {}; DEPS.forEach(function (d) { seen[d.c] = 1; });
      return CATS.filter(function (c) { return seen[c]; }).map(function (c) {
        return '<span><i class="dp-dot" style="background:' + catVar(c) + '"></i>' + c + (c === "Other" ? " (inferred)" : "") + "</span>";
      }).join("");
    }
    var legend = function (extra) { return '<div class="dp-legend">' + catLegend() + (extra ? "<span>" + extra + "</span>" : "") + "</div>"; };

    // ---- sorting (the ranked list; the findings table is sorted by the page's own table code)
    var SORTS = { name: function (d) { return d.n.toLowerCase(); }, scope: function (d) { return d.s; }, src: function (d) { return d.src; }, tst: function (d) { return d.tst; },
      breadth: function (d) { return d.files; }, spread: function (d) { return d.spread; }, depth: function (d) { return d.sym; }, tr: function (d) { return d.tr == null ? -1 : d.tr; } };
    var tsort = { key: null, dir: "desc" };
    function nextSort(key) {
      var cur = tsort.key || state.measure, curDir = tsort.key ? tsort.dir : "desc";
      tsort.dir = cur === key ? (curDir === "asc" ? "desc" : "asc") : (key === "name" || key === "scope" ? "asc" : "desc");
      tsort.key = key;
    }
    function th(label, key, cls) {
      var cur = tsort.key || state.measure, on = cur === key, dir = tsort.key ? tsort.dir : "desc";
      return '<th class="sortable ' + (cls || "") + '"' + (on ? ' aria-sort="' + (dir === "asc" ? "ascending" : "descending") + '"' : "") + '><button type="button" data-sort="' + key + '">' + label + "</button></th>";
    }

    // ---- ranked list
    function viewTable(l) {
      var cur = tsort.key || state.measure, m = (tsort.key ? tsort.dir : "desc") === "asc" ? 1 : -1, LIM = 12;
      var rows = l.slice().sort(function (a, b) { var x = SORTS[cur](a), y = SORTS[cur](b); return (x < y ? -1 : x > y ? 1 : 0) * m || (a.n < b.n ? -1 : 1); });
      var shown = state.all ? rows : rows.slice(0, LIM), maxF = Math.max.apply(null, l.map(function (d) { return d.files; })) || 1;
      var h = '<div class="table-container"><table class="table dp-rank" data-nosort aria-label="Dependencies"><thead><tr>' + th("Dependency", "name") + th("Scope", "scope") + (HAS_TR ? th("Pulls in", "tr", "r c-hide") : "") +
        th("Source", "src", "r c-hide") + th("Test", "tst", "r c-hide") + th("Breadth", "breadth") + th("Spread", "spread", "c-hide") + th("Depth", "depth", "c-hide") + "</tr></thead><tbody>";
      shown.forEach(function (d) {
        var w = function (x) { return (x / maxF * 100).toFixed(1) + "%"; };
        h += '<tr data-dep="' + esc(d.n) + '" tabindex="0"><td><div class="dp-name"><i class="dp-dot" style="background:' + catVar(d.c) + '"></i><span class="dp-nm">' + esc(d.n) + '</span><span class="dp-ver">' + esc(d.v) + "</span></div></td>" +
          "<td>" + '<span class="badge" data-variant="' + (d.s === "runtime" ? "secondary" : "outline") + '">' + d.s + "</span></td>" +
          (HAS_TR ? '<td class="r dp-num c-hide">' + (d.tr == null ? "·" : d.tr) + "</td>" : "") +
          '<td class="r dp-num c-hide">' + d.src + '</td><td class="r dp-num c-hide">' + d.tst + "</td>" +
          '<td><div class="dp-used"><div class="dp-bar">' + (d.src ? '<i style="flex:0 0 ' + w(d.src) + '"></i>' : "") + (d.tst ? '<i class="t" style="flex:0 0 ' + w(d.tst) + '"></i>' : "") + '<span style="flex:1"></span></div><span class="dp-num">' + d.files + "</span></div></td>" +
          '<td class="c-hide"><div class="dp-used"><div class="dp-bar"><i style="flex:0 0 ' + pct(d.sp) + '%"></i><span style="flex:1"></span></div><span class="dp-num">' + d.spread + "/" + MODS.length + "</span></div></td>" +
          '<td class="c-hide"><div class="dp-used"><div class="dp-bar"><i style="flex:0 0 ' + pct(d.dp) + '%"></i><span style="flex:1"></span></div><span class="dp-num">' + d.sym + "</span></div></td></tr>";
      });
      h += "</tbody></table></div>";
      if (rows.length > LIM) h += '<button type="button" class="dp-more" data-more>' + (state.all ? "Show top " + LIM : "Show " + (rows.length - LIM) + " more") + "</button>";
      return h;
    }

    // ---- module matrix: rows are modules, columns the top 12 dependencies, grouped by the module that leans on each most
    function viewMatrix(l) {
      var top = ranked(l).slice(0, 12);
      var dom = function (d) { var b = 0, bi = 0; MODS.forEach(function (m, i) { var s = (d.mods[m.id] || 0) / m.files; if (s > b) { b = s; bi = i; } }); return [bi, b]; };
      top.sort(function (a, b) { var x = dom(a), y = dom(b); return x[0] - y[0] || y[1] - x[1]; });
      var h = '<div class="dp-scroll"><table class="dp-mx" aria-label="Files per module that import each dependency"><thead><tr><th></th>' +
        top.map(function (d) { return '<th class="col" scope="col"><span>' + esc(d.n) + "</span></th>"; }).join("") + "</tr></thead><tbody>";
      MODS.forEach(function (m) {
        h += '<tr><th scope="row">' + esc(m.id) + "<small>" + plural(m.files, "file") + "</small></th>";
        top.forEach(function (d) {
          var n = d.mods[m.id] || 0, s = n / m.files, p;
          if (!n) { h += '<td class="z" data-cell="' + esc(m.id + "|" + d.n) + '">·</td>'; return; }
          p = Math.min(100, 8 + s * 130);
          h += '<td data-cell="' + esc(m.id + "|" + d.n) + '" style="background:color-mix(in oklab, var(--dp-seq) ' + p.toFixed(0) + '%, var(--card));color:' + (p > 52 ? "var(--dp-on-seq)" : "var(--foreground)") + '">' + n + "</td>";
        });
        h += "</tr>";
      });
      return h + '</tbody></table></div><div class="dp-ramp"><span>Share of the module\'s files</span><span>0%</span><i></i><span>80%+</span><span>Cell number = files importing it. Columns are grouped by the module that leans on them most.</span></div>';
    }

    // ---- treemap: squarified, grouped by category, area = the Rank by measure
    function squarify(items, x, y, w, h) {
      var total = items.reduce(function (s, i) { return s + i.value; }, 0), k = w * h / total, out = [], rest = items.map(function (i) { return { i: i, a: i.value * k }; });
      var worst = function (r, s) {
        var sum = r.reduce(function (t, c) { return t + c.a; }, 0), mx = Math.max.apply(null, r.map(function (c) { return c.a; })), mn = Math.min.apply(null, r.map(function (c) { return c.a; }));
        return Math.max(s * s * mx / (sum * sum), sum * sum / (s * s * mn));
      };
      while (rest.length) {
        var short = Math.min(w, h), row = [], wv, wr = Infinity, sum, cur, rw, rh, cy, cx;
        while (rest.length) { wv = worst(row.concat([rest[0]]), short); if (row.length && wv > wr) break; row.push(rest.shift()); wr = wv; }
        sum = row.reduce(function (t, c) { return t + c.a; }, 0);
        if (w >= h) { rw = sum / h; cy = y; row.forEach(function (c) { var ch = c.a / rw; out.push({ item: c.i, x: x, y: cy, w: rw, h: ch }); cy += ch; }); x += rw; w -= rw; }
        else { rh = sum / w; cx = x; row.forEach(function (c) { var cw = c.a / rh; out.push({ item: c.i, x: cx, y: y, w: cw, h: rh }); cx += cw; }); y += rh; h -= rh; }
      }
      return out;
    }
    function viewTree() { return '<div class="dp-tm" id="dp-tm"></div>' + legend("Area = " + MEAS[state.measure].toLowerCase()); }
    function layoutTree() {
      var el = $("#dp-tm", rootEl); if (!el || !el.clientWidth) return;
      var W = el.clientWidth, H = el.clientHeight, l = list(), h = "";
      var groups = CATS.map(function (c) {
        var ds = l.filter(function (d) { return d.c === c; }).sort(function (a, b) { return val(b) - val(a); });
        return { c: c, ds: ds, value: ds.reduce(function (s, d) { return s + Math.max(val(d), 0.01); }, 0) };
      }).filter(function (g) { return g.ds.length; }).sort(function (a, b) { return b.value - a.value; });
      if (!groups.length) { el.innerHTML = EMPTY; return; }
      squarify(groups, 0, 0, W, H).forEach(function (g) {
        var gr = g.item, gap = 3, LH = 18;
        h += '<div class="g" style="left:' + (g.x + gap) + "px;top:" + (g.y + 1) + "px;width:" + (g.w - gap * 2) + 'px"><i class="dp-dot" style="background:' + catVar(gr.c) + '"></i>' + gr.c + "</div>";
        squarify(gr.ds.map(function (d) { return { d: d, value: Math.max(val(d), 0.01) }; }), g.x + gap, g.y + LH + 1, g.w - gap * 2, g.h - LH - gap - 1).forEach(function (r) {
          var d = r.item.d, w = r.w - 3, hh = r.h - 3;
          var lab = w > 44 && hh > 22 ? "<b>" + esc(d.n) + "</b>" : "", sub = w > 60 && hh > 40 ? "<small>" + plural(d.files, "file") + (w > 110 ? " · " + d.spread + " mod" : "") + "</small>" : "";
          h += '<div class="cell" data-dep="' + esc(d.n) + '" style="left:' + r.x + "px;top:" + r.y + "px;width:" + w + "px;height:" + hh + "px;border-color:" + catVar(d.c) + ";background:color-mix(in oklab, " + catVar(d.c) + ' 22%, var(--card))">' + lab + sub + "</div>";
        });
      });
      el.innerHTML = h;
    }

    // ---- reliance plot: files importing it against distinct symbols, sized by packages pulled in
    function viewBubble(l) {
      var W = 680, H = 380, m = { l: 52, r: 20, t: 16, b: 44 }, pw = W - m.l - m.r, ph = H - m.t - m.b, i;
      var xm = Math.ceil(Math.max.apply(null, l.map(function (d) { return d.files; })) / 20) * 20 || 20, ym = Math.ceil(Math.max.apply(null, l.map(function (d) { return d.sym; })) / 5) * 5 || 5;
      var X = function (v) { return m.l + v / xm * pw; }, Y = function (v) { return m.t + ph - v / ym * ph; }, R = function (d) { return 5 + (HAS_TR ? Math.sqrt(d.tr || 0) * 2.1 : 3); };
      var s = '<svg viewBox="0 0 ' + W + " " + H + '" width="100%" style="min-width:35rem" role="img" aria-label="Reliance plot: files importing each dependency against distinct symbols used' + (HAS_TR ? ", sized by packages pulled in" : "") + '">';
      for (i = 0; i <= 4; i++) {
        var gv = xm / 4 * i, gy = ym / 4 * i;
        s += '<line class="grid" x1="' + X(gv) + '" x2="' + X(gv) + '" y1="' + m.t + '" y2="' + (m.t + ph) + '"/><line class="grid" y1="' + Y(gy) + '" y2="' + Y(gy) + '" x1="' + m.l + '" x2="' + (m.l + pw) + '"/>' +
          '<text x="' + X(gv) + '" y="' + (m.t + ph + 16) + '" text-anchor="middle">' + Math.round(gv) + '</text><text x="' + (m.l - 8) + '" y="' + (Y(gy) + 4) + '" text-anchor="end">' + Math.round(gy) + "</text>";
      }
      s += '<line class="axis" x1="' + m.l + '" x2="' + (m.l + pw) + '" y1="' + (m.t + ph) + '" y2="' + (m.t + ph) + '"/><line class="axis" x1="' + m.l + '" x2="' + m.l + '" y1="' + m.t + '" y2="' + (m.t + ph) + '"/>' +
        '<text x="' + (m.l + pw / 2) + '" y="' + (H - 6) + '" text-anchor="middle">Files importing it</text><text transform="translate(13 ' + (m.t + ph / 2) + ') rotate(-90)" text-anchor="middle">Distinct symbols used</text>' +
        '<text x="' + (m.l + 8) + '" y="' + (m.t + 14) + '">Deep, local</text><text x="' + (m.l + pw - 8) + '" y="' + (m.t + 14) + '" text-anchor="end">Load-bearing</text><text x="' + (m.l + pw - 8) + '" y="' + (m.t + ph - 8) + '" text-anchor="end">Wide, shallow</text>';
      l.slice().sort(function (a, b) { return (b.tr || 0) - (a.tr || 0) || b.files - a.files; }).forEach(function (d) {
        s += '<circle data-dep="' + esc(d.n) + '" cx="' + X(d.files) + '" cy="' + Y(d.sym) + '" r="' + R(d) + '" fill="color-mix(in oklab, ' + catVar(d.c) + ' 38%, var(--card))" stroke="' + catVar(d.c) + '" stroke-width="2"/>';
      });
      var placed = [], hit = function (a, b) { return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h; };
      var circles = l.map(function (d) { return { n: d.n, x: X(d.files) - R(d), y: Y(d.sym) - R(d), w: R(d) * 2, h: R(d) * 2 }; });
      ranked(l).slice(0, 8).forEach(function (d) {
        var x = X(d.files), y = Y(d.sym), r = R(d), w = d.n.length * 7.2;
        var cands = [[x + r + 4, y + 4, "start", x + r + 4], [x - r - 4, y + 4, "end", x - r - 4 - w], [x, y - r - 6, "middle", x - w / 2], [x, y + r + 13, "middle", x - w / 2]], pick = cands[0], k, c, box;
        for (k = 0; k < cands.length; k++) {
          c = cands[k]; box = { x: c[3], y: c[1] - 11, w: w, h: 14 };
          if (box.x < m.l || box.x + w > W - 4) continue;
          if (placed.some(function (p) { return hit(box, p); }) || circles.some(function (ci) { return ci.n !== d.n && hit(box, ci); })) continue;
          pick = c; break;
        }
        placed.push({ x: pick[3], y: pick[1] - 11, w: w, h: 14 });
        s += '<text class="strong mono" x="' + pick[0] + '" y="' + pick[1] + '" text-anchor="' + pick[2] + '" style="pointer-events:none">' + esc(d.n) + "</text>";
      });
      return '<div class="dp-scroll">' + s + "</svg></div>" + legend(HAS_TR ? "Circle size = packages pulled in" : "");
    }

    // ---- module graph: modules on the left, the top 10 dependencies on the right, edge width = files importing
    function viewGraph(l) {
      var top = ranked(l).slice(0, 10), W = 680, nh = 34, Hm = Math.max(MODS.length, top.length) * 44 + 16, x1 = 150, x2 = W - 190;
      var ly = function (i) { return 12 + i * ((Hm - 24 - nh) / Math.max(1, MODS.length - 1)); }, ry = function (i) { return 12 + i * ((Hm - 24 - nh) / Math.max(1, top.length - 1)); };
      var s = '<svg viewBox="0 0 ' + W + " " + Hm + '" width="100%" style="min-width:35rem" role="img" aria-label="Module to dependency graph; line width shows files importing">';
      MODS.forEach(function (m, i) {
        top.forEach(function (d, j) {
          var n = d.mods[m.id]; if (!n) return;
          var y1 = ly(i) + nh / 2, y2 = ry(j) + nh / 2, mx = (x1 + x2) / 2;
          s += '<path class="dp-ge" data-m="' + esc(m.id) + '" data-d="' + esc(d.n) + '" data-cell="' + esc(m.id + "|" + d.n) + '" d="M' + x1 + " " + y1 + " C" + mx + " " + y1 + " " + mx + " " + y2 + " " + x2 + " " + y2 + '" stroke="' + catVar(d.c) + '" stroke-width="' + (1.5 + Math.sqrt(n) * 1.1).toFixed(1) + '" opacity=".5"/>';
        });
      });
      MODS.forEach(function (m, i) {
        s += '<g class="dp-gn" data-mod="' + esc(m.id) + '" tabindex="0"><rect class="box" x="0" y="' + ly(i) + '" width="' + x1 + '" height="' + nh + '" rx="6"/><text class="strong" x="12" y="' + (ly(i) + 15) + '" style="font-weight:500;font-size:12px">' + esc(m.id) + '</text><text x="12" y="' + (ly(i) + 28) + '">' + plural(m.files, "file") + "</text></g>";
      });
      top.forEach(function (d, j) {
        s += '<g class="dp-gn" data-dep="' + esc(d.n) + '" tabindex="0"><rect class="box" x="' + x2 + '" y="' + ry(j) + '" width="' + (W - x2) + '" height="' + nh + '" rx="6"/><rect x="' + x2 + '" y="' + ry(j) + '" width="4" height="' + nh + '" style="fill:' + catVar(d.c) + ';stroke:none"/>' +
          '<text class="strong mono" x="' + (x2 + 14) + '" y="' + (ry(j) + 15) + '" style="font-size:12px">' + esc(d.n) + '</text><text x="' + (x2 + 14) + '" y="' + (ry(j) + 28) + '">' + plural(d.files, "file") + " · " + plural(d.spread, "module") + "</text></g>";
      });
      return '<div class="dp-scroll">' + s + "</svg></div>" + legend("Line width = files importing it · top 10 by " + MEAS[state.measure].toLowerCase());
    }

    // ---- by file: the repository tree. Directory totals are summed from their files, and rows are drawn only for the part in view.
    var RH = 28, HEAD_H = 30, OVER = 8;
    var NODE = Object.create(null), TOPS = [], VIS = [], INS = Object.create(null), focusRow = false;
    (function () {
      FILES.forEach(function (f) {
        var parts = f.p.split("/"), list = TOPS, parent = null, path = "", i, d, n;
        for (i = 0; i < parts.length - 1; i++) {
          path = path ? path + "/" + parts[i] : parts[i];
          d = NODE[path];
          if (!d) { d = NODE[path] = { id: path, name: parts[i], dir: true, depth: i, kids: [], nf: 0, parent: parent }; list.push(d); }
          list = d.kids; parent = d;
        }
        n = NODE[f.p] = { id: f.p, name: parts[parts.length - 1], dir: false, depth: parts.length - 1, file: f, nf: 1, parent: parent };
        list.push(n);
      });
      function sortKids(a) { a.sort(function (x, y) { return x.dir === y.dir ? (x.name < y.name ? -1 : x.name > y.name ? 1 : 0) : (x.dir ? -1 : 1); }); a.forEach(function (n) { if (n.dir) sortKids(n.kids); }); }
      sortKids(TOPS);
      (function count(a) { a.forEach(function (n) { if (n.dir) { count(n.kids); n.nf = n.kids.reduce(function (s, k) { return s + k.nf; }, 0); } }); })(TOPS);
    })();
    // import pairs per path, for the dependencies in scope: stat = { imp, per: {name: files}, cc: {category: pairs} }
    function computeStats() {
      INS = Object.create(null); list().forEach(function (d) { INS[d.n] = 1; });
      (function walk(a) {
        a.forEach(function (n) {
          var st = { imp: 0, per: Object.create(null), cc: Object.create(null) };
          if (n.dir) {
            walk(n.kids);
            n.kids.forEach(function (k) {
              st.imp += k.st.imp;
              Object.keys(k.st.per).forEach(function (x) { st.per[x] = (st.per[x] || 0) + k.st.per[x]; });
              Object.keys(k.st.cc).forEach(function (x) { st.cc[x] = (st.cc[x] || 0) + k.st.cc[x]; });
            });
          } else {
            n.file.d.forEach(function (x) { if (!INS[x]) return; st.imp++; st.per[x] = 1; st.cc[CAT[x]] = (st.cc[CAT[x]] || 0) + 1; });
          }
          n.st = st;
        });
      })(TOPS);
    }
    function applyZoom() { state.open = Object.create(null); Object.keys(NODE).forEach(function (id) { var n = NODE[id]; if (n.dir && n.depth < state.zoom - 1) state.open[id] = 1; }); }
    function defaultFocus() { var l = list().sort(function (a, b) { return b.files - a.files || (a.n < b.n ? -1 : 1); }); return l.length ? l[0].n : null; }
    function buildVis() {
      var fc;
      if (state.focus && !INS[state.focus]) state.focus = null;
      if (state.show === "touched" && !state.focus) state.focus = defaultFocus();
      fc = state.focus; VIS = [];
      (function walk(a) { a.forEach(function (n) { if (state.show === "touched" && !n.st.per[fc]) return; VIS.push(n); if (n.dir && state.open[n.id]) walk(n.kids); }); })(TOPS);
      if (!state.sel || !NODE[state.sel] || VIS.indexOf(NODE[state.sel]) < 0) state.sel = VIS.length ? VIS[0].id : null;
    }
    var ICON = {
      chev: '<svg class="dp-chev" viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 3l5 5-5 5"/></svg>',
      dir: '<svg class="dp-ic" viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round" aria-hidden="true"><path d="M1.5 4.5a1 1 0 011-1h3.2l1.3 1.5h6.5a1 1 0 011 1v6a1 1 0 01-1 1h-11a1 1 0 01-1-1z"/></svg>',
      file: '<svg class="dp-ic" viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round" aria-hidden="true"><path d="M4 1.5h5l3.5 3.5v9a.5.5 0 01-.5.5H4a.5.5 0 01-.5-.5v-12a.5.5 0 01.5-.5zM9 1.5V5h3.5"/></svg>' };
    var scroller = null, rowsEl = null, cv = null;
    function viewFiles(l) {
      if (!l.length) return EMPTY;
      return '<div class="dp-tree"><div class="dp-scroller" id="dp-scroller" role="tree" aria-label="Repository files"><div class="dp-thead" role="presentation"><span>Path</span><span id="dp-th2"></span><span id="dp-th3"></span></div>' +
        '<div class="dp-rows" id="dp-rows"></div></div><div class="dp-mini" id="dp-mini-wrap" title="Minimap: click or drag to scroll"><canvas id="dp-mini" aria-hidden="true"></canvas></div></div>' +
        legend("Bar = share of imports by category · number = imports in that path");
    }
    function rowHTML(n, i) {
      var st = n.st, fc = state.focus, has = fc ? (st.per[fc] || 0) : st.imp, p = fc ? (st.per[fc] || 0) / n.nf : 0, bar, tail, top, open = !!state.open[n.id];
      if (fc) {
        bar = '<div class="dp-bar track">' + (p > 0 ? '<i style="flex:0 0 ' + (p * 100).toFixed(1) + "%;background:" + catVar(CAT[fc]) + '"></i>' : "") + '<span style="flex:1"></span></div><span class="dp-pc">' + pct(p) + "%</span>";
        tail = '<span class="dp-nm">' + (st.per[fc] || 0) + '</span><span class="dp-cnt">/ ' + plural(n.nf, "file") + "</span>";
      } else {
        bar = st.imp ? '<div class="dp-bar">' + CATS.filter(function (c) { return st.cc[c]; }).map(function (c) { return '<i style="flex:' + st.cc[c] + ";background:" + catVar(c) + '"></i>'; }).join("") + "</div>" : '<div class="dp-bar track"></div>';
        bar += '<span class="dp-pc">' + st.imp + "</span>";
        top = Object.keys(st.per).sort(function (a, b) { return st.per[b] - st.per[a] || (a < b ? -1 : 1); });
        tail = !top.length ? '<span class="dp-cnt">none</span>' : n.dir ? '<span class="dp-nm">' + esc(top[0]) + '</span><span class="dp-cnt">' + st.per[top[0]] + " / " + n.nf + "</span>" :
          '<span class="dp-nm">' + esc(top.slice(0, 2).join(", ")) + "</span>" + (top.length > 2 ? '<span class="dp-cnt">+' + (top.length - 2) + "</span>" : "");
      }
      return '<div class="dp-row' + (fc && !has ? " dim" : "") + '" role="treeitem" aria-level="' + (n.depth + 1) + '"' + (n.dir ? ' aria-expanded="' + open + '"' : "") + ' aria-setsize="' + VIS.length + '" aria-posinset="' + (i + 1) + '" tabindex="' + (n.id === state.sel ? 0 : -1) + '" data-path="' + esc(n.id) + '" style="top:' + i * RH + 'px">' +
        '<div class="dp-p" style="padding-left:' + n.depth * 14 + 'px">' + (n.dir ? ICON.chev : '<span style="width:12px;flex:none"></span>') + (n.dir ? ICON.dir : ICON.file) + '<span class="dp-nm">' + esc(n.name) + "</span>" + (n.dir ? '<span class="dp-cnt">' + n.nf + "</span>" : "") + "</div>" +
        '<div class="dp-mix">' + bar + '</div><div class="dp-top">' + tail + "</div></div>";
    }
    function drawRows() {
      if (!rowsEl) return;
      var n = VIS.length, a = Math.max(0, Math.floor((scroller.scrollTop - HEAD_H) / RH) - OVER), b = Math.min(n, Math.ceil((scroller.scrollTop + scroller.clientHeight - HEAD_H) / RH) + OVER), i, h = "", had = rowsEl.contains(doc.activeElement);
      rowsEl.style.height = n * RH + "px";
      for (i = a; i < b; i++) h += rowHTML(VIS[i], i);
      rowsEl.innerHTML = h;
      if (!$('.dp-row[tabindex="0"]', rowsEl)) { var first = $(".dp-row", rowsEl); if (first) first.tabIndex = 0; }
      if (had || focusRow) { var cur = $('.dp-row[data-path="' + cssEsc(state.sel) + '"]', rowsEl); if (cur) cur.focus({ preventScroll: true }); focusRow = false; }
    }
    var cssEsc = function (s) { return window.CSS && CSS.escape ? CSS.escape(s) : String(s).replace(/["\\]/g, "\\$&"); };
    function renderFiles(keepScroll) {
      scroller = $("#dp-scroller", rootEl); rowsEl = $("#dp-rows", rootEl); cv = $("#dp-mini", rootEl);
      if (!scroller) return;
      buildVis();
      var fc = state.focus;
      $("#dp-th2", rootEl).textContent = fc ? "Share of files importing " + fc : "Imports by category";
      $("#dp-th3", rootEl).textContent = fc ? "Files importing" : "Top dependency";
      if (!keepScroll) scroller.scrollTop = 0;
      drawRows(); drawMini();
    }
    // minimap: one bar per visible row, stacked by category (or by the focused dependency's share); rows beyond the pixel height are averaged into bands
    function drawMini() {
      if (!cv || state.view !== "files") return;
      var W = cv.clientWidth, H = cv.clientHeight, dpr = window.devicePixelRatio || 1, ctx, cs, n = VIS.length, fc = state.focus, rp, bands = {}, i, mapped, top, bx, css;
      if (!W || !H || !n) return;
      cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
      ctx = cv.getContext("2d"); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
      cs = getComputedStyle(rootEl); css = function (k) { return cs.getPropertyValue(k).trim(); };
      rp = Math.min(6, H / n);
      VIS.forEach(function (nd, idx) {
        var y = Math.floor(idx * rp), ind = 3 + nd.depth * 4, av = Math.max(6, W - ind - 4) * (nd.dir ? 1 : 0.7), b = bands[y] || (bands[y] = { n: 0, ind: 0, av: 0, seg: {}, none: 0 }), st = nd.st;
        b.n++; b.ind += ind; b.av += av;
        if (fc) { b.seg[fc] = (b.seg[fc] || 0) + av * ((st.per[fc] || 0) / nd.nf); }
        else if (!st.imp) b.none += av;
        else CATS.forEach(function (c) { if (st.cc[c]) b.seg[c] = (b.seg[c] || 0) + av * st.cc[c] / st.imp; });
      });
      Object.keys(bands).forEach(function (k) {
        var b = bands[k], y = +k, ind = b.ind / b.n, av = b.av / b.n, bh = Math.max(1, rp - 1.5), x = ind;
        if (fc) {
          var frac = (b.seg[fc] || 0) / b.av;
          ctx.fillStyle = css("--border"); ctx.fillRect(ind, y, av, bh);
          if (frac > 0.005) { ctx.fillStyle = css("--dp-" + CAT[fc].toLowerCase()); ctx.fillRect(ind, y, Math.max(2, av * frac), bh); }
        } else {
          var tot = 0; CATS.forEach(function (c) { tot += b.seg[c] || 0; });
          ctx.fillStyle = css("--border"); ctx.fillRect(ind, y, av * (1 - Math.min(1, tot / b.av)) + 0.01, bh);
          x = ind;
          CATS.forEach(function (c) { var w = (b.seg[c] || 0) / b.n; if (!w) return; ctx.fillStyle = css("--dp-" + c.toLowerCase()); ctx.fillRect(x, y, Math.max(0.5, w - 0.5), bh); x += w; });
        }
      });
      mapped = n * rp; top = scroller.scrollTop / scroller.scrollHeight * mapped; bx = Math.min(mapped, scroller.clientHeight / scroller.scrollHeight * mapped);
      ctx.fillStyle = css("--foreground"); ctx.globalAlpha = 0.1; ctx.fillRect(0, top, W, bx);
      ctx.globalAlpha = 0.7; ctx.strokeStyle = css("--foreground"); ctx.lineWidth = 1; ctx.strokeRect(0.5, top + 0.5, W - 1, Math.max(2, bx - 1)); ctx.globalAlpha = 1;
    }
    var miniRaf = 0, sched = function () { cancelAnimationFrame(miniRaf); miniRaf = requestAnimationFrame(drawMini); };
    function seek(e) {
      var r = cv.getBoundingClientRect(), n = VIS.length || 1, mapped = n * Math.min(6, cv.clientHeight / n);
      scroller.scrollTop = (e.clientY - r.top) / mapped * scroller.scrollHeight - scroller.clientHeight / 2;
    }
    var dragging = false;
    stage.addEventListener("pointerdown", function (e) { if (e.target !== cv) return; dragging = true; cv.setPointerCapture(e.pointerId); seek(e); });
    stage.addEventListener("pointermove", function (e) { if (dragging && cv) seek(e); });
    stage.addEventListener("pointerup", function () { dragging = false; });
    stage.addEventListener("pointercancel", function () { dragging = false; });
    stage.addEventListener("scroll", function (e) { if (e.target === scroller) { drawRows(); sched(); hideTip(); } }, true);
    if (window.ResizeObserver) new ResizeObserver(function () { if (state.view === "tree") layoutTree(); else if (state.view === "files") { drawRows(); sched(); } }).observe(stage);
    if (window.MutationObserver) new MutationObserver(sched).observe(root, { attributes: true, attributeFilter: ["class"] });   // the theme is the "dark" class on <html>

    // ---- tree keyboard: Up and Down move, Right opens or enters, Left closes or leaves, Enter and Space toggle, Home and End jump
    function toggle(n, open) { if (open) state.open[n.id] = 1; else delete state.open[n.id]; state.sel = n.id; focusRow = true; renderFiles(true); }
    function moveTo(j) {
      if (j < 0 || j >= VIS.length) return;
      state.sel = VIS[j].id;
      var y = HEAD_H + j * RH;
      if (y < scroller.scrollTop + HEAD_H) scroller.scrollTop = y - HEAD_H; else if (y + RH > scroller.scrollTop + scroller.clientHeight) scroller.scrollTop = y + RH - scroller.clientHeight;
      focusRow = true; drawRows(); sched();
    }
    stage.addEventListener("keydown", function (e) {
      var row = e.target.closest && e.target.closest(".dp-row"); if (!row) return;
      var n = NODE[row.dataset.path], i = VIS.indexOf(n), j;
      if (e.key === "ArrowDown") { e.preventDefault(); moveTo(i + 1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); moveTo(i - 1); }
      else if (e.key === "ArrowRight") { e.preventDefault(); if (n.dir && !state.open[n.id]) toggle(n, true); else if (n.dir) moveTo(i + 1); }
      else if (e.key === "ArrowLeft") {
        e.preventDefault();
        if (n.dir && state.open[n.id]) toggle(n, false);
        else if (n.parent) moveTo(VIS.indexOf(n.parent));
      }
      else if ((e.key === "Enter" || e.key === " ") && n.dir) { e.preventDefault(); toggle(n, !state.open[n.id]); }
      else if (e.key === "Home") { e.preventDefault(); moveTo(0); }
      else if (e.key === "End") { e.preventDefault(); moveTo(VIS.length - 1); }
    });

    // ---- the dependency picker: a searchable combobox. "All dependencies" clears the focus, and is not offered while Show is "Only paths it touches".
    var combo = { open: false, q: "", idx: 0, items: [] }, depInp = $("#dp-depsel", rootEl), depList = $("#dp-deplist", rootEl);
    function depItems() {
      var q = combo.q.trim().toLowerCase();
      var items = list().sort(function (a, b) { return a.n.toLowerCase() < b.n.toLowerCase() ? -1 : 1; }).filter(function (d) { return !q || d.n.toLowerCase().indexOf(q) >= 0; });
      if (!q && state.show !== "touched") items.unshift({ all: true });
      return items;
    }
    function drawCombo() {
      depList.hidden = !combo.open; depInp.setAttribute("aria-expanded", String(combo.open));
      if (!combo.open) { depInp.removeAttribute("aria-activedescendant"); return; }
      combo.items = depItems(); combo.idx = Math.max(0, Math.min(combo.idx, combo.items.length - 1));
      depList.innerHTML = combo.items.length ? combo.items.map(function (d, i) {
        return d.all ? '<li id="dp-opt' + i + '" role="option" data-v="" aria-selected="' + (i === combo.idx) + '"><span>All dependencies</span></li>' :
          '<li id="dp-opt' + i + '" role="option" data-v="' + esc(d.n) + '" aria-selected="' + (i === combo.idx) + '" class="' + (d.n === state.focus ? "cur" : "") + '"><i class="dp-dot" style="background:' + catVar(d.c) + ';margin:0"></i><span class="dp-nm">' + esc(d.n) + '</span><span class="dp-cnt">' + plural(d.files, "file") + "</span></li>";
      }).join("") : '<li class="none" role="option" aria-disabled="true">No dependency matches</li>';
      if (combo.items.length) {
        depInp.setAttribute("aria-activedescendant", "dp-opt" + combo.idx);
        var li = depList.children[combo.idx];
        if (li) { if (li.offsetTop < depList.scrollTop) depList.scrollTop = li.offsetTop - 4; else if (li.offsetTop + li.offsetHeight > depList.scrollTop + depList.clientHeight) depList.scrollTop = li.offsetTop + li.offsetHeight - depList.clientHeight + 4; }
      }
    }
    function openCombo() {
      if (combo.open) return;
      combo.open = true; combo.q = ""; combo.items = depItems();
      var cur = state.focus || ""; combo.idx = 0;
      combo.items.forEach(function (d, i) { if ((d.all ? "" : d.n) === cur) combo.idx = i; });
      drawCombo(); depInp.select();
    }
    function closeCombo() { combo.open = false; drawCombo(); depInp.value = state.focus || ""; }
    function pickDep(v) {
      closeCombo();
      if (!v) { if (state.focus) { state.focus = null; render(); } }
      else if (v !== state.focus) { state.focus = v; if (state.show === "touched") applyZoom(); render(); }
    }
    depInp.addEventListener("focus", openCombo); depInp.addEventListener("click", openCombo); depInp.addEventListener("blur", closeCombo);
    depInp.addEventListener("input", function () { combo.open = true; combo.q = depInp.value; combo.idx = 0; drawCombo(); });
    depInp.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (!combo.open) { openCombo(); return; }
        var n = combo.items.length; if (n) { combo.idx = (combo.idx + (e.key === "ArrowDown" ? 1 : n - 1)) % n; drawCombo(); }
      } else if (e.key === "Enter") { if (combo.open && combo.items[combo.idx]) { e.preventDefault(); pickDep(combo.items[combo.idx].all ? "" : combo.items[combo.idx].n); } }
      else if (e.key === "Escape") { if (combo.open) { e.preventDefault(); closeCombo(); } }
    });
    depList.addEventListener("mousedown", function (e) { e.preventDefault(); var li = e.target.closest('li[role="option"]'); if (li && li.dataset.v !== undefined) pickDep(li.dataset.v); });

    // ---- render
    function setPressed(id, v) { $$("#" + id + " button", rootEl).forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.v === String(v))); }); }
    function render(keepScroll) {
      var l = list(), V = state.view, files = V === "files";
      computeStats(); hideTip();
      stage.innerHTML = !l.length ? EMPTY : ({ table: viewTable, matrix: viewMatrix, tree: viewTree, bubble: viewBubble, graph: viewGraph, files: viewFiles })[V](l);
      if (V === "tree" && l.length) layoutTree();
      if (files && l.length) renderFiles(keepScroll === true);
      setPressed("dp-view", state.view); setPressed("dp-measure", state.measure); setPressed("dp-scope", state.scope); setPressed("dp-zoom", state.zoom); setPressed("dp-show", state.show);
      ["zoom", "show", "dep"].forEach(function (k) { $("#dp-" + k + "-ctl", rootEl).hidden = !files; });
      if (!combo.open) depInp.value = state.focus || "";
      depInp.placeholder = state.show === "touched" ? "Search dependencies" : "All dependencies";
      try { localStorage.setItem(STORE, JSON.stringify({ measure: state.measure, scope: state.scope })); } catch (e) {}
    }
    [["view", "dp-view"], ["measure", "dp-measure"], ["scope", "dp-scope"]].forEach(function (p) {
      $("#" + p[1], rootEl).addEventListener("click", function (e) {
        var b = e.target.closest("button"); if (!b) return;
        state[p[0]] = b.dataset.v; state.all = false; if (p[0] === "measure") tsort.key = null;
        render();
      });
    });
    $("#dp-zoom", rootEl).addEventListener("click", function (e) { var b = e.target.closest("button"); if (!b) return; state.zoom = +b.dataset.v; applyZoom(); render(); });
    $("#dp-show", rootEl).addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      state.show = b.dataset.v; if (state.show === "touched") computeStats();
      applyZoom(); render();
    });
    stage.addEventListener("click", function (e) {
      var sb = e.target.closest("[data-sort]"), row, n;
      if (sb) { nextSort(sb.dataset.sort); render(); return; }
      if (e.target.closest("[data-more]")) { state.all = !state.all; render(); return; }
      row = e.target.closest(".dp-row");
      if (row) { n = NODE[row.dataset.path]; state.sel = n.id; if (n.dir) toggle(n, !state.open[n.id]); else { focusRow = true; drawRows(); } }
    });

    // ---- tooltips: follow the pointer, use the page's shared tooltip element, and are not shown for touch
    var r2 = function (k, v) { return '<div class="dp-r"><span>' + k + "</span><span>" + v + "</span></div>"; };
    function depTip(d) {
      var mods = Object.keys(d.mods).sort(function (a, b) { return d.mods[b] - d.mods[a]; }).map(function (k) { return esc(k) + " " + d.mods[k]; }).join(" · ");
      var h = '<div class="tp-h">' + esc(d.n) + ' <span style="opacity:.75;font-weight:400">' + esc(d.v) + "</span></div>" +
        r2("Category", d.c + (d.c === "Other" ? " (inferred)" : "")) + r2("Scope", d.s + (d.group ? " · " + esc(d.group) : "")) + r2("Files importing", d.src + " source · " + d.tst + " test") +
        r2("Modules", mods || "none") + r2("Symbols used", d.sym);
      if (d.tr != null) h += r2("Pulls in", plural(d.tr, "package"));
      if (d.b !== undefined) h += r2("Breadth · spread · depth", pct(d.b) + " · " + pct(d.sp) + " · " + pct(d.dp));
      return h;
    }
    function tipFor(el) {
      var d, n, st, top, p, m;
      if (el.dataset.path) {
        n = NODE[el.dataset.path]; st = n.st;
        top = Object.keys(st.per).sort(function (a, b) { return st.per[b] - st.per[a] || (a < b ? -1 : 1); }).slice(0, 5);
        return '<div class="tp-h">' + esc(n.id) + (n.dir ? "/" : "") + "</div>" + r2(n.dir ? "Files" : "File", n.nf) + r2("Imports", st.imp) +
          top.map(function (k) { return r2(esc(k), st.per[k] + (n.dir ? " / " + n.nf : "")); }).join("");
      }
      if (el.dataset.cell) {
        p = el.dataset.cell.split("|"); m = MODS.filter(function (x) { return x.id === p[0]; })[0]; d = BYNAME[p[1]];
        return '<div class="tp-h">' + esc(p[1]) + " in " + esc(p[0]) + "</div>" + r2("Files importing", (d.mods[p[0]] || 0) + " of " + m.files + " (" + pct((d.mods[p[0]] || 0) / m.files) + "%)");
      }
      if (el.dataset.dep) { d = BYNAME[el.dataset.dep]; return d ? depTip(d) : null; }
      if (el.dataset.mod) {
        m = MODS.filter(function (x) { return x.id === el.dataset.mod; })[0];
        top = DEPS.filter(function (x) { return x.mods[m.id]; }).sort(function (a, b) { return b.mods[m.id] - a.mods[m.id]; }).slice(0, 5);
        return '<div class="tp-h">' + esc(m.id) + "</div>" + r2("Files", m.files) + top.map(function (x) { return r2(esc(x.n), x.mods[m.id]); }).join("");
      }
      return null;
    }
    var tipOwned = false;
    function hideTip() { if (tipOwned) { tip.hidden = true; tipOwned = false; } }
    function clearHl() { var s = $("svg.hl", stage); if (s) { s.classList.remove("hl"); $$(".on", s).forEach(function (p) { p.classList.remove("on"); }); } }
    function hl(svg, el) {
      var cell = el.dataset.cell ? el.dataset.cell.split("|") : null, m = el.dataset.mod || (cell && cell[0]), d = cell ? cell[1] : el.dataset.dep;
      svg.classList.add("hl");
      $$(".dp-ge", svg).forEach(function (p) { p.classList.toggle("on", cell ? (p.dataset.m === m && p.dataset.d === d) : (el.dataset.mod ? p.dataset.m === m : p.dataset.d === d)); });
    }
    stage.addEventListener("pointermove", function (e) {
      if (e.pointerType === "touch" || dragging) return;
      var el = e.target.closest("[data-cell],[data-dep],[data-mod],[data-path]"), h, w, ht, x, y, svg;
      if (!el) { hideTip(); clearHl(); return; }
      h = tipFor(el); if (!h) { hideTip(); return; }
      tip.className = ""; tip.innerHTML = h; tip.hidden = false; tipOwned = true;
      w = tip.offsetWidth; ht = tip.offsetHeight; x = e.clientX + 16; y = e.clientY + 16;
      if (x + w > window.innerWidth - 8) x = e.clientX - w - 16;
      if (y + ht > window.innerHeight - 8) y = window.innerHeight - ht - 8;
      tip.style.left = Math.max(8, x) + "px"; tip.style.top = Math.max(8, y) + "px";
      svg = e.target.closest("svg"); if (svg && state.view === "graph") hl(svg, el);
    });
    stage.addEventListener("pointerleave", function () { hideTip(); clearHl(); });

    applyZoom(); render();
  })();

  $("#menu-toggle").addEventListener("click", function () { var sb = $(".sidebar"); if (sb && sb.toggle) sb.toggle(); });

  // keep the sticky header height in sync so anchors land below it
  function syncHeader() { var h = $(".masthead"); if (h) root.style.setProperty("--header-h", (h.offsetHeight + 12) + "px"); }
  window.addEventListener("resize", syncHeader); syncHeader();
  applyTheme(); show();
})();
