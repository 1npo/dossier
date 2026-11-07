// Reads a JavaScript or TypeScript project with the TypeScript compiler API and prints one JSON object (plan 010, D9).
// It only parses and type-resolves: it never imports or runs repository code, and it reads tsconfig files as data.
// Input on stdin: {"root": ".", "files": ["src/a.ts", ...]}. Output paths are relative to root, with forward slashes.
import path from "node:path";
import ts from "typescript";

const CODE = /\.(ts|tsx|mts|cts|js|jsx|mjs|cjs)$/;
const NO_INPUT_CODES = new Set([18002, 18003]); // "files list is empty" is normal for a solution-style tsconfig
const ROUTERS = new Set(["createBrowserRouter", "createHashRouter", "createMemoryRouter", "useRoutes"]);
const HOOK = /^use[A-Z0-9]/;

const input = JSON.parse(await new Promise((resolve) => {
  let text = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (c) => { text += c; });
  process.stdin.on("end", () => resolve(text || "{}"));
}));
const root = path.resolve(input.root || ".");
const errors = [];
const posix = (p) => p.split(path.sep).join("/");
const rel = (abs) => posix(path.relative(root, abs));
const flat = (d) => ts.flattenDiagnosticMessageText(d.messageText, " ");

// ---- tsconfig choice -------------------------------------------------------------------------------------------------

function rawConfig(file) {
  const read = ts.readConfigFile(file, ts.sys.readFile);
  if (read.error) { errors.push(`${rel(file)}: ${flat(read.error)}`); return null; }
  return read.config || {};
}

function chooseConfig() {
  for (const name of ["tsconfig.json", "jsconfig.json"]) {
    const file = path.join(root, name);
    if (!ts.sys.fileExists(file)) continue;
    const raw = rawConfig(file);
    if (!raw) return { file: name, used: name, abs: file };
    const refs = (raw.references || []).map((r) => path.resolve(path.dirname(file), r.path || "")).map((p) => (p.endsWith(".json") ? p : path.join(p, "tsconfig.json")));
    if (refs.length && !(raw.compilerOptions || {}).paths) {
      const usable = refs.filter((r) => ts.sys.fileExists(r));
      const withPaths = usable.find((r) => ((rawConfig(r) || {}).compilerOptions || {}).paths);
      const pick = withPaths || usable[0];
      if (pick) return { file: name, used: rel(pick), abs: pick };
    }
    return { file: name, used: name, abs: file };
  }
  return null;
}

function compilerOptions(chosen) {
  let options = {};
  if (chosen) {
    const raw = rawConfig(chosen.abs);
    if (raw) {
      const parsed = ts.parseJsonConfigFileContent(raw, ts.sys, path.dirname(chosen.abs), undefined, chosen.abs);
      options = parsed.options;
      for (const d of parsed.errors) if (!NO_INPUT_CODES.has(d.code)) errors.push(`${rel(chosen.abs)}: ${flat(d)}`);
    }
  }
  const forced = { allowJs: true, noEmit: true, skipLibCheck: true, noLib: true, types: [] };
  const defaults = { jsx: ts.JsxEmit.Preserve, module: ts.ModuleKind.ESNext, moduleResolution: ts.ModuleResolutionKind.Bundler };
  const merged = { ...options, ...forced };
  for (const [k, v] of Object.entries(defaults)) if (merged[k] === undefined) merged[k] = v;
  if (merged.moduleResolution === ts.ModuleResolutionKind.Classic) merged.moduleResolution = ts.ModuleResolutionKind.Bundler;
  return merged;
}

// ---- helpers ---------------------------------------------------------------------------------------------------------

const chosen = chooseConfig();
const options = compilerOptions(chosen);
const wanted = (input.files || []).filter((f) => CODE.test(f));
const rootNames = wanted.map((f) => path.resolve(root, f));
const program = ts.createProgram(rootNames, options);
const checker = program.getTypeChecker();
const fileSet = new Set(wanted.map(posix));
const sources = rootNames.map((n) => program.getSourceFile(n)).filter(Boolean);

const line = (sf, pos) => sf.getLineAndCharacterOfPosition(pos).line + 1;
const startLine = (n) => line(n.getSourceFile(), n.getStart());
const endLine = (n) => line(n.getSourceFile(), n.getEnd());
const walk = (node, visit) => { ts.forEachChild(node, (c) => { if (visit(c) !== false) walk(c, visit); }); };
const hasMod = (n, kind) => (ts.canHaveModifiers(n) ? ts.getModifiers(n) || [] : []).some((m) => m.kind === kind);
const isStr = (n) => n && (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n));

function repoPath(abs) {
  const r = rel(abs);
  return r.startsWith("..") || r.includes("node_modules/") ? null : r;
}

function declFile(symbol) {
  if (!symbol) return null;
  let target = symbol;
  if (symbol.flags & ts.SymbolFlags.Alias) {
    try { target = checker.getAliasedSymbol(symbol); } catch { return null; }
  }
  const decl = target && target.declarations && target.declarations[0];
  return decl ? repoPath(decl.getSourceFile().fileName) : null;
}

function localExports(sf) {
  const names = new Map(); // local name -> exported name
  for (const st of sf.statements) {
    if (ts.isExportDeclaration(st) && !st.moduleSpecifier && st.exportClause && ts.isNamedExports(st.exportClause)) {
      for (const el of st.exportClause.elements) names.set((el.propertyName || el.name).text, el.name.text);
    } else if (ts.isExportAssignment(st) && ts.isIdentifier(st.expression)) names.set(st.expression.text, "default");
  }
  return names;
}

// ---- imports and exports ---------------------------------------------------------------------------------------------

function collectImports(sf, out) {
  const add = (spec, node, typeOnly, dynamic) => out.push({ path: rel(sf.fileName), specifier: spec.text, line: line(sf, spec.getStart()), type_only: typeOnly, dynamic });
  walk(sf, (n) => {
    if (ts.isImportDeclaration(n) && isStr(n.moduleSpecifier)) add(n.moduleSpecifier, n, !!(n.importClause && n.importClause.isTypeOnly), false);
    else if (ts.isExportDeclaration(n) && n.moduleSpecifier && isStr(n.moduleSpecifier)) add(n.moduleSpecifier, n, !!n.isTypeOnly, false);
    else if (ts.isImportEqualsDeclaration(n) && ts.isExternalModuleReference(n.moduleReference) && isStr(n.moduleReference.expression)) add(n.moduleReference.expression, n, !!n.isTypeOnly, false);
    else if (ts.isCallExpression(n) && n.arguments.length && isStr(n.arguments[0])) {
      if (n.expression.kind === ts.SyntaxKind.ImportKeyword) add(n.arguments[0], n, false, true);
      else if (ts.isIdentifier(n.expression) && n.expression.text === "require") add(n.arguments[0], n, false, false);
    }
  });
}

function collectExports(sf, out) {
  const p = rel(sf.fileName);
  const add = (name, node, local, isDefault) => out.push({ path: p, name, line: startLine(node), default: isDefault, ...(local && local !== name ? { local } : {}) });
  for (const st of sf.statements) {
    const exported = hasMod(st, ts.SyntaxKind.ExportKeyword);
    const dflt = hasMod(st, ts.SyntaxKind.DefaultKeyword);
    if (exported && ts.isVariableStatement(st)) {
      for (const d of st.declarationList.declarations) if (ts.isIdentifier(d.name)) add(d.name.text, d, null, false);
    } else if (exported && (ts.isFunctionDeclaration(st) || ts.isClassDeclaration(st) || ts.isInterfaceDeclaration(st) || ts.isTypeAliasDeclaration(st) || ts.isEnumDeclaration(st) || ts.isModuleDeclaration(st))) {
      add(dflt ? "default" : (st.name && st.name.text) || "default", st, dflt && st.name ? st.name.text : null, dflt);
    } else if (ts.isExportDeclaration(st) && !st.moduleSpecifier && st.exportClause && ts.isNamedExports(st.exportClause)) {
      for (const el of st.exportClause.elements) add(el.name.text, el, (el.propertyName || el.name).text, el.name.text === "default");
    } else if (ts.isExportAssignment(st) && !st.isExportEquals) {
      add("default", st, ts.isIdentifier(st.expression) ? st.expression.text : null, true);
    }
  }
}

// ---- types -----------------------------------------------------------------------------------------------------------

function memberFields(members, sf) {
  const fields = [];
  for (const m of members) {
    if ((ts.isPropertySignature(m) || ts.isPropertyDeclaration(m)) && m.name) {
      fields.push({ name: m.name.getText(sf), type: m.type ? m.type.getText(sf) : "", line: line(sf, m.getStart()), optional: !!m.questionToken });
    } else if (ts.isEnumMember(m)) {
      fields.push({ name: m.name.getText(sf), type: m.initializer ? m.initializer.getText(sf) : "", line: line(sf, m.getStart()), optional: false });
    }
  }
  return fields;
}

function collectTypes(sf, out) {
  const p = rel(sf.fileName);
  const locals = localExports(sf);
  for (const st of sf.statements) {
    let kind = null;
    let members = [];
    let object = false;
    if (ts.isInterfaceDeclaration(st)) { kind = "interface"; members = st.members; object = true; }
    else if (ts.isTypeAliasDeclaration(st)) { kind = "type"; object = ts.isTypeLiteralNode(st.type); members = object ? st.type.members : []; }
    else if (ts.isEnumDeclaration(st)) { kind = "enum"; members = st.members; }
    else if (ts.isClassDeclaration(st) && st.name) { kind = "class"; members = st.members; }
    if (!kind) continue;
    const bases = (st.heritageClauses || []).flatMap((h) => h.types.map((t) => t.expression.getText(sf)));
    const decorators = (ts.canHaveDecorators(st) ? ts.getDecorators(st) || [] : []).map((d) => (ts.isCallExpression(d.expression) ? d.expression.expression : d.expression).getText(sf));
    const name = st.name ? st.name.text : "default";
    out.push({ path: p, name, kind, line: startLine(st), end_line: endLine(st), exported: hasMod(st, ts.SyntaxKind.ExportKeyword) || locals.has(name),
      object, bases, decorators, fields: memberFields(members, sf) });
  }
}

// ---- React components ------------------------------------------------------------------------------------------------

const FN_LIKE = (n) => n && (ts.isArrowFunction(n) || ts.isFunctionExpression(n));

function unwrap(expr) {
  let e = expr;
  for (;;) {
    if (!e) return null;
    if (ts.isParenthesizedExpression(e) || ts.isAsExpression(e) || ts.isSatisfiesExpression(e)) e = e.expression;
    else if (ts.isCallExpression(e) && /(^|\.)(memo|forwardRef)$/.test(e.expression.getText()) && e.arguments.length) e = e.arguments[0];
    else return e;
  }
}

function hasJsx(node) {
  let found = false;
  walk(node, (c) => {
    if (found) return false;
    if (ts.isJsxElement(c) || ts.isJsxSelfClosingElement(c) || ts.isJsxFragment(c)) { found = true; return false; }
    return true;
  });
  return found;
}

function describe(node, sf) {
  const renders = [];
  const seen = new Set();
  const hooks = [];
  const provides = [];
  const consumes = [];
  const push = (list, v) => { if (!list.includes(v)) list.push(v); };
  walk(node, (c) => {
    if (ts.isJsxOpeningElement(c) || ts.isJsxSelfClosingElement(c)) {
      const tag = c.tagName;
      if (ts.isPropertyAccessExpression(tag) && tag.name.text === "Provider") push(provides, tag.expression.getText(sf));
      else if (ts.isIdentifier(tag) && /^[A-Z]/.test(tag.text)) {
        const p = declFile(checker.getSymbolAtLocation(tag));
        const key = `${tag.text}|${p}`;
        if (!seen.has(key)) { seen.add(key); renders.push({ name: tag.text, path: p }); }
      }
    } else if (ts.isCallExpression(c)) {
      const callee = c.expression;
      const name = ts.isIdentifier(callee) ? callee.text : ts.isPropertyAccessExpression(callee) ? callee.name.text : "";
      if (HOOK.test(name)) push(hooks, name);
      if (name === "useContext" && c.arguments.length) push(consumes, c.arguments[0].getText(sf));
    }
  });
  return { renders, hooks, provides, consumes };
}

function collectComponents(sf, out) {
  const p = rel(sf.fileName);
  const locals = localExports(sf);
  const add = (name, node, body, exported) => out.push({ path: p, name, line: startLine(node), end_line: endLine(node), exported: exported || locals.has(name), ...describe(body, sf) });
  for (const st of sf.statements) {
    const exported = hasMod(st, ts.SyntaxKind.ExportKeyword);
    if (ts.isFunctionDeclaration(st) && st.name && st.body && /^[A-Z]/.test(st.name.text) && hasJsx(st.body)) add(st.name.text, st, st.body, exported);
    else if (ts.isClassDeclaration(st) && st.name && /^[A-Z]/.test(st.name.text)
      && (st.heritageClauses || []).some((h) => h.types.some((t) => /(^|\.)(Pure)?Component$/.test(t.expression.getText(sf))))) add(st.name.text, st, st, exported);
    else if (ts.isVariableStatement(st)) {
      for (const d of st.declarationList.declarations) {
        const fn = ts.isIdentifier(d.name) ? unwrap(d.initializer) : null;
        if (FN_LIKE(fn) && /^[A-Z]/.test(d.name.text) && hasJsx(fn)) add(d.name.text, d, fn, exported);
      }
    }
  }
}

// ---- routes ----------------------------------------------------------------------------------------------------------

function literalValue(node) {
  if (isStr(node)) return node.text;
  if (ts.isParenthesizedExpression(node) || ts.isAsExpression(node) || ts.isSatisfiesExpression(node)) return literalValue(node.expression);
  if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken) {
    const a = literalValue(node.left);
    const b = a === null ? null : literalValue(node.right);
    return b === null ? null : a + b;
  }
  if (ts.isTemplateExpression(node)) {
    let text = node.head.text;
    for (const span of node.templateSpans) {
      const v = literalValue(span.expression);
      if (v === null) return null;
      text += v + span.literal.text;
    }
    return text;
  }
  if (ts.isIdentifier(node) || ts.isPropertyAccessExpression(node)) {
    const t = checker.getTypeAtLocation(node);
    if (t && t.isStringLiteral()) return t.value;
  }
  return null;
}

function joinRoute(parent, child) {
  if (child === "" || child === undefined) return parent;
  if (child.startsWith("/") || !parent) return child;
  return parent.replace(/\/$/, "") + "/" + child;
}

function resolveFile(spec, from) {
  const r = ts.resolveModuleName(spec, from, options, ts.sys).resolvedModule;
  const p = r && repoPath(r.resolvedFileName);
  return p && fileSet.has(p) ? p : null;
}

function lazyTarget(obj, sf) {
  for (const prop of obj.properties) {
    if (ts.isPropertyAssignment(prop) && prop.name.getText(sf) === "lazy") {
      let found = null;
      walk(prop.initializer, (c) => {
        if (ts.isCallExpression(c) && c.expression.kind === ts.SyntaxKind.ImportKeyword && c.arguments.length && isStr(c.arguments[0])) found = resolveFile(c.arguments[0].text, sf.fileName);
      });
      return found;
    }
  }
  return null;
}

function emitRoute(out, sf, node, pathNode, parent, file, index) {
  let part = "";
  let resolved = true;
  let text = "";
  if (pathNode) {
    const v = literalValue(pathNode);
    text = pathNode.getText(sf);
    if (v === null) resolved = false; else part = v;
  } else if (!index) return { route: parent, resolved: true, skip: true };
  const route = resolved ? joinRoute(parent, part) : text;
  out.push({ path: rel(sf.fileName), line: startLine(node), end_line: endLine(node), route, resolved, file, framework: "react-router" });
  return { route, resolved };
}

function objectRoutes(array, parent, sf, out) {
  for (const el of array.elements) {
    if (!ts.isObjectLiteralExpression(el)) continue;
    let pathNode = null;
    let children = null;
    let index = false;
    for (const prop of el.properties) {
      if (!ts.isPropertyAssignment(prop)) continue;
      const key = prop.name.getText(sf);
      if (key === "path") pathNode = prop.initializer;
      else if (key === "children" && ts.isArrayLiteralExpression(prop.initializer)) children = prop.initializer;
      else if (key === "index") index = true;
    }
    const r = emitRoute(out, sf, el, pathNode, parent, lazyTarget(el, sf), index);
    if (children) objectRoutes(children, r.resolved ? r.route : parent, sf, out);
  }
}

function jsxRoutes(node, parent, sf, out) {
  const tag = ts.isJsxElement(node) ? node.openingElement : node;
  const isRoute = tag.tagName.getText(sf) === "Route";
  let next = parent;
  if (isRoute) {
    let pathNode = null;
    let index = false;
    for (const a of tag.attributes.properties) {
      if (!ts.isJsxAttribute(a)) continue;
      if (a.name.text === "path" && a.initializer) pathNode = ts.isJsxExpression(a.initializer) ? a.initializer.expression : a.initializer;
      if (a.name.text === "index") index = true;
    }
    const r = emitRoute(out, sf, node, pathNode, parent, null, index);
    if (r.resolved) next = r.route;
  }
  if (ts.isJsxElement(node)) for (const c of node.children) if (ts.isJsxElement(c) || ts.isJsxSelfClosingElement(c)) jsxRoutes(c, next, sf, out);
}

function collectRoutes(sf, out) {
  walk(sf, (n) => {
    if (ts.isCallExpression(n) && n.arguments.length && ts.isArrayLiteralExpression(n.arguments[0])) {
      const callee = ts.isIdentifier(n.expression) ? n.expression.text : ts.isPropertyAccessExpression(n.expression) ? n.expression.name.text : "";
      if (ROUTERS.has(callee)) { objectRoutes(n.arguments[0], "", sf, out); return false; }
    }
    if ((ts.isJsxElement(n) && n.openingElement.tagName.getText(sf) === "Route") || (ts.isJsxSelfClosingElement(n) && n.tagName.getText(sf) === "Route")) {
      jsxRoutes(n, "", sf, out);
      return false;
    }
    return true;
  });
}

// ---- main ------------------------------------------------------------------------------------------------------------

const result = { config: { file: chosen ? chosen.file : null, used: chosen ? chosen.used : null, paths: options.paths || {} },
  imports: [], exports: [], types: [], components: [], routes: [], errors };
for (const sf of sources) {
  collectImports(sf, result.imports);
  collectExports(sf, result.exports);
  collectTypes(sf, result.types);
  collectComponents(sf, result.components);
  collectRoutes(sf, result.routes);
}
console.log(JSON.stringify(result));
