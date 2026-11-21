// Odwołania2JSON – podgląd: PDF (pdf.js) ↔ wyekstrahowane dane (JSON + evidence).
// Współrzędne evidence: punkty PDF, początek w lewym górnym rogu (pdfplumber), więc
// x_canvas = x0 * skala, y_canvas = top * skala – bez odwracania osi Y.

import * as pdfjsLib from "/static/vendor/pdfjs/pdf.min.mjs";

pdfjsLib.GlobalWorkerOptions.workerSrc = "/static/vendor/pdfjs/pdf.worker.min.mjs";
const PDF_OPTS = {
  cMapUrl: "/static/vendor/pdfjs/cmaps/",
  cMapPacked: true,
  standardFontDataUrl: "/static/vendor/pdfjs/standard_fonts/",
};

const CLASS_LABELS = {
  odwolanie: "Odwołanie",
  pelnomocnictwo: "Pełnomocnictwo",
  przelew: "Potwierdzenie przelewu",
};

// Opisy pól (ścieżka bez indeksów list). Klucz JSON pokazujemy zawsze w oryginale – zgodnie ze schematem UZP.
const FIELD_LABELS = {
  "OdwolanieKIO": "Odwołanie do KIO",
  "OdwolanieKIO.data": "data odwołania",
  "OdwolanieKIO.czynnosc_dzien": "dzień czynności zamawiającego",
  "OdwolanieKIO.czynnosc_powod_id": "powód (id ze słownika)",
  "OdwolanieKIO.czynnosc_opis": "opis czynności",
  "OdwolanieKIO.miejscowosc": "miejscowość",
  "Odwolujacy": "Odwołujący",
  "Zamawiajacy": "Zamawiający",
  "ZamowieniePubliczne": "Zamówienie publiczne",
  "ZamowieniePubliczne.numer_bzp": "numer ogłoszenia BZP",
  "ZamowieniePubliczne.numer_postepowania": "znak postępowania",
  "ZamowieniePubliczne.numer_ted": "numer ogłoszenia TED",
  "ZamowieniePubliczne.tytul": "nazwa zamówienia",
  "mocodawca": "Mocodawca",
  "pelnomocnicy": "Pełnomocnicy",
  "przelew_bankowy": "Przelew bankowy",
  "przelew_bankowy.data_operacji": "data operacji",
  "przelew_bankowy.kwota": "kwota (PLN)",
  "przelew_bankowy.na_rachunek": "rachunek odbiorcy",
  "przelew_bankowy.z_rachunku": "rachunek nadawcy",
  "przelew_bankowy.numer_transakcji": "numer transakcji",
  "przelew_bankowy.tytul": "tytuł przelewu",
};
const KEY_LABELS = {
  krs: "KRS", nip: "NIP", regon: "REGON", pesel: "PESEL", nazwa: "nazwa", mail: "e-mail",
  imie_nazwisko: "imię i nazwisko", "przez-pelnomocnika": "przez pełnomocnika (0/1)", pelnomocnik: "Pełnomocnik",
  prowadzacy_postepowanie: "prowadzący postępowanie", typ: "typ podmiotu", data: "dane", podpisujacy: "Podpisujący",
};

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

const state = {
  run: null, docIdx: 0, token: 0,
  pdf: null, ev: null, data: null, raw: "",
  zoom: null, scale: 1, pages: [],
  boxes: new Map(), rows: new Map(), selected: null,
  observer: null, lastWidth: 0,
};

// ------------------------------------------------------------------------------------------------ helpers

function classInfo(cls) {
  if (cls == null) return { label: "Nie rozpoznano", css: "cls-none" };
  if (CLASS_LABELS[cls]) return { label: CLASS_LABELS[cls], css: `cls-${cls}` };
  return { label: String(cls).replace(/_/g, " "), css: "cls-other" };
}

function badge(cls, small) {
  const info = classInfo(cls);
  const b = el("span", `badge ${info.css}${small ? " sm" : ""}`, info.label);
  b.title = cls == null ? "Nie rozpoznano typu dokumentu – wynik {}" : `Klasa dokumentu: ${cls}`;
  return b;
}

function toast(msg, isErr = false, ms = 5000) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast" + (isErr ? " err" : "");
  t.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.hidden = true), ms);
}

function busy(on, text) {
  $("#busy").hidden = !on;
  if (text) $("#busy-text").textContent = text;
}

async function api(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try { const j = await r.json(); if (j.detail) msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch {}
    throw new Error(msg);
  }
  return r;
}

const normPath = (p) => p.replace(/\[\d+\]/g, "");
function labelFor(path, key) {
  return FIELD_LABELS[normPath(path)] || KEY_LABELS[key] || null;
}
// Pola kwotowe w schemacie UZP są liczbami zmiennoprzecinkowymi (np. 200.0). JSON.parse gubi ".0",
// więc kwoty formatujemy zawsze z groszami, a w porównaniu z dokumentem pokazujemy literał zgodny z plikiem.
const isMoney = (path) => /(^|\.)kwota$/.test(normPath(path || ""));
function fmtNum(v, path) {
  if (typeof v !== "number") return String(v);
  if (isMoney(path) || !Number.isInteger(v)) return v.toLocaleString("pl-PL", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return String(v);
}
function jsonLit(v, path) {
  return typeof v === "number" && Number.isInteger(v) && isMoney(path) ? v.toFixed(1) : String(v);
}

// ------------------------------------------------------------------------------------------------ cases & runs

async function loadCases() {
  const sel = $("#case-select");
  try {
    const { sources } = await (await api("/api/cases")).json();
    for (const src of sources) {
      const og = document.createElement("optgroup");
      og.label = src.label;
      for (const c of src.cases) {
        const o = new Option(`${c.label || c.name} · ${c.pdfs} PDF`, `${src.id}|${c.name}`);
        og.appendChild(o);
      }
      sel.appendChild(og);
    }
    if (!sources.length) sel.options[0].textContent = "Brak spraw w input/";
  } catch (e) {
    sel.options[0].textContent = "Nie udało się wczytać spraw";
  }
}

async function loadHistory() {
  const sel = $("#history-select");
  sel.length = 1;
  try {
    const runs = await (await api("/api/runs")).json();
    for (const r of runs) {
      const d = new Date(r.created * 1000);
      const when = d.toLocaleString("pl-PL", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
      sel.appendChild(new Option(`${when} · ${r.label} (${r.docs})${r.status === "error" ? " ⚠" : ""}`, r.id));
    }
  } catch {}
}

async function runCase() {
  const v = $("#case-select").value;
  if (!v) return;
  const [source, ...rest] = v.split("|");
  const caseName = rest.join("|");
  busy(true, `Przetwarzanie sprawy ${caseName === "." ? source : caseName}…`);
  try {
    const meta = await (await api("/api/run/case", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source, case: caseName }),
    })).json();
    await showRun(meta, 0);
    loadHistory();
  } catch (e) {
    toast(`Błąd: ${e.message}`, true);
  } finally {
    busy(false);
  }
}

async function uploadFiles(fileList) {
  const files = [...fileList];
  if (!files.length) return;
  const fd = new FormData();
  for (const f of files) fd.append("files", f, f.name);
  busy(true, files.length === 1 ? `Przetwarzanie: ${files[0].name}` : `Przetwarzanie ${files.length} plików…`);
  try {
    const meta = await (await api("/api/run/upload", { method: "POST", body: fd })).json();
    await showRun(meta, 0);
    if (meta.skipped?.length) toast("Pominięto:\n" + meta.skipped.join("\n"), true, 8000);
    loadHistory();
  } catch (e) {
    toast(`Błąd: ${e.message}`, true);
  } finally {
    busy(false);
    $("#file-input").value = "";
  }
}

async function openRun(rid, idx = 0) {
  try {
    const meta = await (await api(`/api/runs/${encodeURIComponent(rid)}`)).json();
    await showRun(meta, idx);
  } catch (e) {
    toast(`Nie można otworzyć przebiegu: ${e.message}`, true);
  }
}

async function showRun(meta, idx) {
  state.run = meta;
  const docs = meta.docs || [];
  if (meta.status === "error") {
    toast(`Pipeline zakończył się błędem (kod ${meta.returncode}).\n${(meta.log || "").slice(-600)}`, true, 12000);
  }
  if (!docs.length) {
    toast("Brak dokumentów PDF w tym przebiegu.", true);
    return;
  }
  $("#welcome").hidden = true;
  $("#workspace").hidden = false;
  $("#docbar").hidden = false;
  const recognized = docs.filter((d) => d.class).length;
  $("#run-info").textContent =
    `${docs.length} dok. · rozpoznano ${recognized} · ${meta.duration != null ? meta.duration.toLocaleString("pl-PL") + " s" : ""}`;
  $("#zip-link").href = `/api/runs/${meta.id}/zip`;

  const tabs = $("#doc-tabs");
  tabs.replaceChildren();
  docs.forEach((d, i) => {
    const t = el("button", "doc-tab");
    t.setAttribute("role", "tab");
    t.title = d.name;
    t.append(el("span", "doc-name ellipsis", d.name));
    const m = el("span", "doc-meta");
    m.append(badge(d.class, true));
    if (d.class) m.append(el("span", null, `${d.stats.filled}/${d.stats.total} pól`));
    else m.append(el("span", null, "→ {}"));
    t.append(m);
    t.addEventListener("click", () => selectDoc(i));
    tabs.append(t);
  });
  renderCaseReport(meta.id);
  await selectDoc(Math.min(Math.max(idx, 0), docs.length - 1));
}

// Kontrola formalna sprawy (config/case_rules.yaml): karta nad dokumentami, zielone/czerwone wiersze.
async function renderCaseReport(rid) {
  const box = $("#case-report");
  box.hidden = true;
  box.replaceChildren();
  let rep;
  try { rep = await (await api(`/api/runs/${rid}/case_report`)).json(); } catch { return; }
  if (!rep.rules || !rep.rules.length || state.run?.id !== rid) return;
  const head = el("button", "case-head");
  head.append(el("strong", null, "Kontrola formalna sprawy"),
    el("span", "muted", ` ${rep.passed}/${rep.evaluated} reguł spełnionych` + (rep.total > rep.evaluated ? ` · ${rep.total - rep.evaluated} nie dotyczy` : "")),
    el("span", "muted case-src", "config/case_rules.yaml"));
  head.addEventListener("click", () => box.classList.toggle("collapsed"));
  const list = el("div", "case-rules");
  for (const r of rep.rules) {
    const row = el("div", `case-rule ${r.status === "ok" ? "ok" : r.status === "fail" ? (r.severity === "info" ? "info" : "fail") : "na"}`);
    row.append(el("span", "case-dot"), el("span", "case-label", r.label + (r.severity === "info" ? " · informacyjnie" : "")),
      el("span", "case-msg muted", r.message || ""));
    row.title = `${r.label}\n${r.message || ""}`;
    list.append(row);
  }
  box.append(head, list);
  box.hidden = false;
}

// ------------------------------------------------------------------------------------------------ document

async function selectDoc(idx) {
  const meta = state.run;
  const d = meta.docs[idx];
  const token = ++state.token;
  state.docIdx = idx;
  history.replaceState(null, "", `#${meta.id}/${idx}`);
  [...$("#doc-tabs").children].forEach((t, i) => t.classList.toggle("active", i === idx));
  const base = `/api/runs/${meta.id}/docs/${idx}`;

  $("#pdf-name").textContent = d.name;
  $("#pdf-name").title = d.name;
  $("#pdf-open").href = `${base}/pdf`;
  $("#json-download").href = `${base}/json?download=1`;
  $("#json-download").toggleAttribute("hidden", !d.has_output);
  $("#class-badge").replaceWith(Object.assign(badge(d.class), { id: "class-badge" }));
  $("#field-stats").textContent = d.class
    ? `${d.stats.filled}/${d.stats.total} pól wypełnionych · ${d.stats.located} w PDF · ${d.stats.derived} wyliczonych`
    : "";
  clearSelection();

  const [ev, raw] = await Promise.all([
    api(`${base}/evidence`).then((r) => r.json()).catch(() => ({ fields: {} })),
    api(`${base}/json`).then((r) => r.text()).catch(() => null),
  ]);
  if (token !== state.token) return;
  state.ev = ev;
  state.raw = raw;
  try { state.data = raw == null ? null : JSON.parse(raw); } catch { state.data = null; }
  renderData(d);

  if (state.pdf) { state.pdf.destroy().catch(() => {}); state.pdf = null; }
  $("#pdf-pages-wrap").replaceChildren(el("div", "muted", "Wczytywanie PDF…"));
  try {
    const pdf = await pdfjsLib.getDocument({ url: `${base}/pdf`, ...PDF_OPTS }).promise;
    if (token !== state.token) { pdf.destroy(); return; }
    state.pdf = pdf;
    $("#pdf-pages").textContent = `· ${pdf.numPages} ${pdf.numPages === 1 ? "strona" : pdf.numPages < 5 ? "strony" : "stron"}`;
    const sizes = [];
    for (let i = 1; i <= pdf.numPages; i++) {
      const p = await pdf.getPage(i);
      const vp = p.getViewport({ scale: 1 });
      sizes.push([vp.width, vp.height]);
    }
    if (token !== state.token) return;
    state.pageSizes = sizes;
    state.zoom = null;
    layoutPages();
    $("#pdf-scroll").scrollTo(0, 0);
  } catch (e) {
    $("#pdf-pages-wrap").replaceChildren(el("div", "muted", `Nie można wyświetlić PDF: ${e.message}`));
  }
}

// ------------------------------------------------------------------------------------------------ PDF rendering

function fitScale() {
  const w = $("#pdf-scroll").clientWidth - 34;
  const maxW = Math.max(...state.pageSizes.map((s) => s[0]));
  return Math.max(0.3, Math.min(3, w / maxW));
}

function layoutPages() {
  if (!state.pdf) return;
  const scroller = $("#pdf-scroll");
  const ratio = scroller.scrollHeight ? scroller.scrollTop / scroller.scrollHeight : 0;
  state.scale = state.zoom ?? fitScale();
  state.lastWidth = scroller.clientWidth;
  state.observer?.disconnect();
  for (const p of state.pages) p.task?.cancel();
  state.pages = [];
  state.boxes = new Map();

  const wrap = $("#pdf-pages-wrap");
  wrap.replaceChildren();
  wrap.classList.toggle("show-all", $("#show-all").checked);
  const evSizes = state.ev?.page_sizes || [];

  state.observer = new IntersectionObserver((entries) => {
    for (const en of entries) if (en.isIntersecting) renderPage(state.pages[+en.target.dataset.i]);
  }, { root: scroller, rootMargin: "800px 0px" });

  state.pageSizes.forEach(([w, h], i) => {
    const div = el("div", "page");
    div.dataset.i = i;
    div.style.width = `${w * state.scale}px`;
    div.style.height = `${h * state.scale}px`;
    div.append(el("div", "page-loading", `strona ${i + 1}`));
    div.append(el("span", "page-no", `${i + 1}`));
    const overlay = el("div", "overlay");
    div.append(overlay);
    wrap.append(div);
    // skala evidence: szerokość strony w CSS px / szerokość strony wg pdfplumber
    const evW = evSizes[i]?.[0] || w;
    const page = { i, div, overlay, w, h, rendered: false, task: null, k: (w * state.scale) / evW };
    state.pages.push(page);
    state.observer.observe(div);
  });

  drawBoxes();
  scroller.scrollTop = ratio * scroller.scrollHeight;
  if (state.selected) applySelection(state.selected, { scrollPdf: false });
}

async function renderPage(page) {
  if (!page || page.rendered || !state.pdf) return;
  page.rendered = true;
  const token = state.token;
  try {
    const p = await state.pdf.getPage(page.i + 1);
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let vp = p.getViewport({ scale: state.scale * dpr });
    const maxPx = 14e6;
    if (vp.width * vp.height > maxPx) vp = p.getViewport({ scale: state.scale * dpr * Math.sqrt(maxPx / (vp.width * vp.height)) });
    const canvas = document.createElement("canvas");
    canvas.width = Math.floor(vp.width);
    canvas.height = Math.floor(vp.height);
    page.task = p.render({ canvasContext: canvas.getContext("2d"), viewport: vp });
    await page.task.promise;
    if (token !== state.token || !page.div.isConnected) return;
    page.div.querySelector(".page-loading")?.remove();
    page.div.prepend(canvas);
  } catch (e) {
    if (e?.name !== "RenderingCancelledException") {
      page.rendered = false;
      console.warn(e);
    }
  }
}

function drawBoxes() {
  const fields = state.ev?.fields || {};
  const tip = getTip();
  for (const [path, f] of Object.entries(fields)) {
    if (!f.boxes?.length || !f.page) continue;
    const page = state.pages[f.page - 1];
    if (!page) continue;
    const list = [];
    for (const b of f.boxes) {
      const pad = 1.5;
      const box = el("div", "box");
      box.style.left = `${b.x0 * page.k - pad}px`;
      box.style.top = `${b.top * page.k - pad}px`;
      box.style.width = `${(b.x1 - b.x0) * page.k + 2 * pad}px`;
      box.style.height = `${(b.bottom - b.top) * page.k + 2 * pad}px`;
      box.dataset.path = path;
      box.addEventListener("mouseenter", (e) => {
        hover(path, true);
        tip.innerHTML = `<b>${esc(path)}</b><br>${esc(fmtNum(f.value, path))}`;
        tip.hidden = false;
        moveTip(e);
      });
      box.addEventListener("mousemove", moveTip);
      box.addEventListener("mouseleave", () => { hover(path, false); tip.hidden = true; });
      box.addEventListener("click", () => select(path, { scrollTree: true, scrollPdf: false }));
      page.overlay.append(box);
      list.push(box);
    }
    state.boxes.set(path, list);
  }
}

function getTip() {
  let t = document.querySelector(".box-tip");
  if (!t) { t = el("div", "box-tip"); t.hidden = true; document.body.append(t); }
  return t;
}
function moveTip(e) {
  const t = getTip();
  const x = Math.min(e.clientX + 14, window.innerWidth - t.offsetWidth - 8);
  t.style.left = `${x}px`;
  t.style.top = `${e.clientY + 16}px`;
}

// ------------------------------------------------------------------------------------------------ data tree

function renderData(d) {
  const tree = $("#tree");
  tree.replaceChildren();
  state.rows = new Map();
  $("#json-view").innerHTML = highlightJson(state.raw ?? "");
  $("#legend").hidden = !d.class;

  if (state.data == null) {
    tree.append(foreignState("Brak wyniku", "Pipeline nie zapisał pliku JSON dla tego dokumentu. Szczegóły w logu przebiegu.", "!"));
    return;
  }
  if (isEmptyObject(state.data)) {
    tree.append(foreignState(
      null,
      "Dokument nie został rozpoznany jako odwołanie, pełnomocnictwo ani potwierdzenie przelewu. " +
      "Zgodnie ze specyfikacją UZP wynikowy plik JSON jest pusty.",
      "?",
    ));
    return;
  }
  for (const [k, v] of Object.entries(state.data)) tree.append(renderNode(k, v, k, 0));
}

function isEmptyObject(v) {
  return v && typeof v === "object" && !Array.isArray(v) && Object.keys(v).length === 0;
}

function foreignState(title, text, icon) {
  const box = el("div", "foreign");
  box.append(el("div", "icon", icon));
  const h = el("h2");
  if (title) h.textContent = title;
  else h.innerHTML = "Nie rozpoznano typu dokumentu → <code>{}</code>";
  box.append(h, el("p", null, text));
  if (!title) box.append(el("pre", null, "{}"));
  return box;
}

function countLeaves(v) {
  let total = 0, filled = 0;
  const walk = (x) => {
    if (x && typeof x === "object") Object.values(x).forEach(walk);
    else { total++; if (x != null) filled++; }
  };
  walk(v);
  return [filled, total];
}

function renderNode(key, value, path, depth) {
  if (value !== null && typeof value === "object") {
    const g = el("div", "group");
    const head = el("div", "group-head");
    head.append(el("span", "chev", "▼"));
    const label = labelFor(path, key);
    head.append(el("span", null, key));
    if (label && label.toLowerCase() !== key.toLowerCase()) head.append(el("span", "count", label));
    const [filled, total] = countLeaves(value);
    head.append(el("span", "count", Array.isArray(value) ? `· ${value.length} poz. · ${filled}/${total}` : `· ${filled}/${total}`));
    head.addEventListener("click", () => g.classList.toggle("collapsed"));
    const body = el("div", "group-body");
    if (Array.isArray(value)) {
      if (!value.length) body.append(el("div", "empty-list", "pusta lista"));
      value.forEach((item, i) => {
        const p = `${path}[${i}]`;
        if (item !== null && typeof item === "object" && !Array.isArray(item)) {
          if (value.length > 1 || depth > 0) body.append(el("div", "item-head", `${key} [${i + 1}]`));
          for (const [k, v] of Object.entries(item)) body.append(renderNode(k, v, `${p}.${k}`, depth + 1));
        } else {
          body.append(renderNode(`[${i}]`, item, p, depth + 1));
        }
      });
    } else {
      for (const [k, v] of Object.entries(value)) body.append(renderNode(k, v, `${path}.${k}`, depth + 1));
    }
    g.append(head, body);
    return g;
  }
  return renderLeaf(key, value, path);
}

function renderLeaf(key, value, path) {
  const f = state.ev?.fields?.[path];
  const row = el("div", "leaf");
  row.dataset.path = path;
  const k = el("div", "k", key);
  const label = labelFor(path, key);
  if (label && label !== key) k.append(el("small", null, label));
  const v = el("div", "v");
  let chip;
  if (value == null) {
    v.textContent = "brak";
    v.classList.add("null");
    chip = el("span", "chip null", "null");
    chip.title = "Pole nie zostało znalezione w dokumencie (null)";
    row.classList.add("missing");
  } else {
    v.textContent = fmtNum(value, path);
    if (typeof value === "number") v.classList.add("num");
    if (f?.boxes?.length) {
      row.classList.add("located");
      chip = el("span", "chip loc", `s. ${f.page}`);
      chip.title = "Zlokalizowane w PDF – kliknij, aby przewinąć do fragmentu";
    } else if (f?.source === "derived" || f == null) {
      row.classList.add("derived");
      chip = el("span", "chip der", "wyliczone");
      chip.title = "Wartość wyliczona (np. identyfikator ze słownika, flaga 0/1) – nie jest dosłownym cytatem z PDF";
    } else {
      row.classList.add("located");
      chip = el("span", "chip nobox", `s. ${f.page}`);
      chip.title = "Znaleziono w tekście strony, ale bez dokładnej ramki";
    }
  }
  const warns = (state.ev?.validation || []).filter((w) => w.path === path && !w.ok);
  if (warns.length) {
    row.classList.add("vwarn");
    const w = el("span", "vwarn-mark", "!");
    w.title = "Walidacja (tylko ostrzeżenie, wartość bez zmian): " + warns.map((x) => `${x.check}: ${x.message}`).join("; ");
    v.append(w);
  }
  row.append(k, v, chip);
  row.addEventListener("mouseenter", () => hover(path, true));
  row.addEventListener("mouseleave", () => hover(path, false));
  row.addEventListener("click", () => select(path, { scrollPdf: true }));
  state.rows.set(path, row);
  return row;
}

function highlightJson(text) {
  return esc(text).replace(
    /(&quot;(?:[^&]|&(?!quot;))*?&quot;)(\s*:)?|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g,
    (m, str, colon, lit, num) => {
      if (str) return colon ? `<span class="jk">${str}</span>${colon}` : `<span class="js">${str}</span>`;
      if (lit) return `<span class="jl">${lit}</span>`;
      return `<span class="jn">${num}</span>`;
    },
  );
}

// ------------------------------------------------------------------------------------------------ highlight & selection

function hover(path, on) {
  for (const b of state.boxes.get(path) || []) b.classList.toggle("hl", on);
  state.rows.get(path)?.classList.toggle("hover", on);
}

function clearSelection() {
  if (state.selected) {
    for (const b of state.boxes.get(state.selected) || []) b.classList.remove("sel");
    state.rows.get(state.selected)?.classList.remove("sel");
  }
  state.selected = null;
  $("#detail").hidden = true;
}

function select(path, opts = {}) {
  if (state.selected === path && !opts.force) {
    // drugi klik: tylko ponowne przewinięcie
    applySelection(path, opts);
    return;
  }
  clearSelection();
  state.selected = path;
  applySelection(path, opts);
  showDetail(path);
}

function applySelection(path, { scrollPdf = false, scrollTree = false } = {}) {
  const boxes = state.boxes.get(path) || [];
  for (const b of boxes) {
    b.classList.remove("sel");
    void b.offsetWidth; // restart animacji pulsowania
    b.classList.add("sel");
  }
  const row = state.rows.get(path);
  row?.classList.add("sel");
  if (scrollTree && row) {
    row.closest(".group.collapsed")?.classList.remove("collapsed");
    row.scrollIntoView({ block: "center", behavior: "smooth" });
  }
  if (scrollPdf && boxes.length) {
    const f = state.ev.fields[path];
    const page = state.pages[f.page - 1];
    const b = f.boxes[0];
    const scroller = $("#pdf-scroll");
    const top = page.div.offsetTop + b.top * page.k - scroller.clientHeight / 3;
    const bx0 = page.div.offsetLeft + b.x0 * page.k, bx1 = page.div.offsetLeft + b.x1 * page.k;
    const visible = bx0 >= scroller.scrollLeft && bx1 <= scroller.scrollLeft + scroller.clientWidth;
    const left = visible ? scroller.scrollLeft : Math.max(0, bx0 - scroller.clientWidth / 4);
    scroller.scrollTo({ top: Math.max(0, top), left, behavior: "smooth" });
  }
}

function showDetail(path) {
  const f = state.ev?.fields?.[path];
  const row = state.rows.get(path);
  const det = $("#detail");
  det.replaceChildren();
  const head = el("div", "d-head");
  head.append(el("span", "d-path", path));
  const value = f ? f.value : null;
  let body;
  if (!f) {
    if (row?.classList.contains("missing")) {
      head.append(el("span", "chip null", "null"));
      body = el("div", "d-snippet", "Pole nie zostało znalezione w dokumencie – w pliku JSON ma wartość null.");
    } else {
      head.append(el("span", "chip der", "wyliczone"));
      body = el("div", "d-snippet", "Brak lokalizacji w PDF dla tej wartości.");
    }
  } else if (f.source === "derived") {
    head.append(el("span", "chip der", "wyliczone"));
    body = el("div", "d-snippet");
    body.innerHTML = `Wartość <b>${esc(fmtNum(value, path))}</b> została wyliczona (np. identyfikator ze słownika powodów, flaga 0/1) – nie jest dosłownym cytatem z dokumentu, więc nie ma ramki w PDF.`;
  } else {
    head.append(el("span", "chip loc", `strona ${f.page}`));
    body = el("div", "d-snippet");
    body.innerHTML = markSnippet(f.snippet || "", f.match || "");
    if (f.match && String(f.match) !== jsonLit(value, path)) {
      const norm = el("div", "muted");
      norm.style.marginTop = "5px";
      norm.innerHTML = `w dokumencie: „${esc(f.match)}” → w JSON: <b>${esc(jsonLit(value, path))}</b>`;
      body.append(norm);
    }
  }
  const close = el("button", "d-close", "×");
  close.title = "Zamknij (Esc)";
  close.addEventListener("click", clearSelection);
  head.append(close);
  det.append(head, body);
  det.hidden = false;
  requestAnimationFrame(() => row?.scrollIntoView({ block: "nearest" }));
}

function markSnippet(snippet, match) {
  const i = match ? snippet.toLowerCase().indexOf(match.toLowerCase()) : -1;
  if (i < 0) return esc(snippet);
  return `…${esc(snippet.slice(0, i))}<mark>${esc(snippet.slice(i, i + match.length))}</mark>${esc(snippet.slice(i + match.length))}…`;
}

// ------------------------------------------------------------------------------------------------ wiring

function setupEvents() {
  $("#file-input").addEventListener("change", (e) => uploadFiles(e.target.files));
  $("#drop-card").addEventListener("click", () => $("#file-input").click());
  $("#case-select").addEventListener("change", (e) => ($("#case-run").disabled = !e.target.value));
  $("#case-run").addEventListener("click", runCase);
  $("#history-select").addEventListener("change", (e) => {
    if (e.target.value) openRun(e.target.value, 0);
    e.target.value = "";
  });

  // przeciągnij i upuść w dowolnym miejscu okna
  let depth = 0;
  const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes("Files");
  window.addEventListener("dragenter", (e) => { if (hasFiles(e)) { depth++; $("#drop-overlay").hidden = false; } });
  window.addEventListener("dragleave", () => { if (--depth <= 0) { depth = 0; $("#drop-overlay").hidden = true; } });
  window.addEventListener("dragover", (e) => { if (hasFiles(e)) e.preventDefault(); });
  window.addEventListener("drop", (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    depth = 0;
    $("#drop-overlay").hidden = true;
    uploadFiles(e.dataTransfer.files);
  });

  // widoki prawego panelu
  document.querySelectorAll(".seg-btn").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll(".seg-btn").forEach((x) => x.classList.toggle("active", x === b));
    const json = b.dataset.view === "json";
    $("#tree").hidden = json;
    $("#json-view").hidden = !json;
  }));

  $("#show-all").addEventListener("change", (e) => $("#pdf-pages-wrap").classList.toggle("show-all", e.target.checked));
  $("#zoom-in").addEventListener("click", () => { state.zoom = state.scale * 1.2; layoutPages(); });
  $("#zoom-out").addEventListener("click", () => { state.zoom = Math.max(0.3, state.scale / 1.2); layoutPages(); });
  $("#zoom-fit").addEventListener("click", () => { state.zoom = null; layoutPages(); });

  let rt;
  new ResizeObserver(() => {
    if (state.zoom != null || !state.pdf) return;
    if (Math.abs($("#pdf-scroll").clientWidth - state.lastWidth) < 4) return;
    clearTimeout(rt);
    rt = setTimeout(layoutPages, 150);
  }).observe($("#pdf-scroll"));

  // zmiana szerokości paneli
  const gutter = $("#gutter");
  gutter.addEventListener("pointerdown", (e) => {
    const split = $("#workspace");
    const pane = document.querySelector(".pdf-pane");
    gutter.setPointerCapture(e.pointerId);
    gutter.classList.add("drag");
    const move = (ev) => {
      const r = split.getBoundingClientRect();
      const pct = Math.min(80, Math.max(25, ((ev.clientX - r.left) / r.width) * 100));
      pane.style.flexBasis = `${pct}%`;
    };
    const up = () => {
      gutter.classList.remove("drag");
      gutter.removeEventListener("pointermove", move);
      gutter.removeEventListener("pointerup", up);
    };
    gutter.addEventListener("pointermove", move);
    gutter.addEventListener("pointerup", up);
  });

  // klawiatura: Esc – odznacz, ↑/↓ – poprzednie/następne pole
  document.addEventListener("keydown", (e) => {
    if (e.target.matches("input, select, textarea")) return;
    if (e.key === "Escape") clearSelection();
    if ((e.key === "ArrowDown" || e.key === "ArrowUp") && state.rows.size && !$("#tree").hidden) {
      e.preventDefault();
      const paths = [...state.rows.keys()];
      const i = paths.indexOf(state.selected);
      const next = e.key === "ArrowDown" ? Math.min(paths.length - 1, i + 1) : Math.max(0, i < 0 ? 0 : i - 1);
      select(paths[next], { scrollPdf: true, scrollTree: true });
    }
  });
}

async function init() {
  setupEvents();
  await Promise.all([loadCases(), loadHistory()]);
  const m = location.hash.match(/^#([0-9]{8}-[0-9]{6}-[0-9a-f]{6})(?:\/(\d+))?/);
  if (m) openRun(m[1], +(m[2] || 0));
}

init();
