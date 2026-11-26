"use strict";
const SOURCE_LABEL = {digital: "chữ số", ocr_layer: "lớp OCR ẩn", tesseract: "Tesseract", missing: "chưa OCR"};
const DEFAULT_SUGGEST = [
  {tag: "Hỏi đáp RAG & Tô vàng PDF", q: "Phạm vi điều chỉnh của nghị định về kiểm soát thủ tục hành chính là gì?"},
  {tag: "Trích xuất siêu dữ liệu", q: "Ai ký Nghị định 385/2026/NĐ-CP?"},
  {tag: "Tổng hợp nhiều văn bản", q: "Những văn bản nào nói về chuyển đổi số?"},
  {tag: "Tóm tắt có dẫn nguồn", q: "Tóm tắt công văn 10790/VPCP-CN"},
  {tag: "Tương tác & Thống kê kho", q: "Thống kê kho lưu trữ hiện có gì?"},
  {tag: "Kiểm tra Cổng từ chối (Câu bẫy)", q: "Thủ đô của nước Pháp là gì?", trap: true},
];
const $ = (id) => document.getElementById(id);
const store = {
  get(k, d) { try { const v = localStorage.getItem("tlvb." + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("tlvb." + k, JSON.stringify(v)); } catch { /* bỏ qua */ } },
};
const S = { docs: [], selected: new Set(), messages: [], viewer: null, busy: false, llm: null, user: null, sessionId: "nb_" + Math.random().toString(36).slice(2, 10) };

function authHeaders(extra = {}) {
  let tok = "";
  try { tok = localStorage.getItem("archive_token") || ""; } catch {}
  return tok ? { ...extra, Authorization: `Bearer ${tok}` } : { ...extra };
}

function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) e.append(c);
  return e;
}
async function api(path, opts = {}) {
  let r;
  const mergedOpts = { ...opts, headers: authHeaders(opts.headers || {}) };
  try {
    r = await fetch(path, mergedOpts);
  } catch {
    throw new Error("Không kết nối được tới máy chủ. Vui lòng kiểm tra kết nối hoặc thử lại.");
  }
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    let msg = body.detail || "";
    if (!msg) {
      if (r.status === 401) msg = "Vui lòng đăng nhập Quản trị viên để thực hiện thao tác này (401).";
      else if (r.status === 403) msg = "Tài khoản không đủ quyền thực hiện thao tác này (403).";
      else if (r.status === 429) msg = "Quá nhiều yêu cầu / giới hạn tốc độ OpenRouter (429), vui lòng thử lại sau ít giây.";
      else if (r.status === 503) msg = "Dịch vụ LLM tạm thời chưa sẵn sàng (503).";
      else msg = r.statusText || `Lỗi HTTP ${r.status}`;
    }
    const err = new Error(msg);
    err.status = r.status;
    throw err;
  }
  return r.json();
}

/* ---------- biểu tượng SVG (nét 1.8) ---------- */
const SVG_NS = "http://www.w3.org/2000/svg";
const ICONS = {
  file: ["M6 3h9l4 4v14H6z", "M14 3v5h5M9 13h7M9 17h5"],
  trash: ["M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"],
  pin: ["M12 17v5", "M9 3h6l-1 6 3 4H7l3-4z"],
  landmark: ["M3 21h18M5 21V10M19 21V10M9 21V10M15 21V10", "M2 10l10-6 10 6z"],
  sparkle: ["M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z", "M19 16l.7 1.8L21.5 18.5l-1.8.7L19 21l-.7-1.8-1.8-.7 1.8-.7z"],
  copy: ["M9 9h11v11H9z", "M5 15H4V4h11v1"],
  check: ["M5 12.5l4.5 4.5L19 7"],
  warn: ["M12 3l10 18H2z", "M12 10v5M12 18h.01"],
  zoomIn: ["M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z", "m20 20-4-4M11 8v6M8 11h6"],
  zoomOut: ["M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z", "m20 20-4-4M8 11h6"],
  expand: ["M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"],
  chevronLeft: ["M15 18l-6-6 6-6"],
  chevronRight: ["M9 18l6-6-6-6"],
  upload: ["M12 16V4M7 9l5-5 5 5", "M4 16v4h16v-4"],
  scissors: ["M6 6a3 3 0 1 0 0 .01M6 18a3 3 0 1 0 0 .01", "M8.1 8.1L20 20M8.1 15.9L20 4"],
};
function svgIcon(name, size = 15) {
  const s = document.createElementNS(SVG_NS, "svg");
  s.setAttribute("class", "ic");
  s.setAttribute("width", String(size)); s.setAttribute("height", String(size));
  s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("fill", "none");
  s.setAttribute("stroke", "currentColor"); s.setAttribute("stroke-width", "1.8");
  s.setAttribute("stroke-linecap", "round"); s.setAttribute("stroke-linejoin", "round");
  s.setAttribute("aria-hidden", "true");
  for (const d of ICONS[name] || []) {
    const p = document.createElementNS(SVG_NS, "path");
    p.setAttribute("d", d); s.append(p);
  }
  return s;
}

/* ---------- giao diện sáng/tối ---------- */
function applyTheme(t) { if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme; }
applyTheme(store.get("theme", null));
$("themeBtn").onclick = () => {
  const dark = document.documentElement.dataset.theme
    ? document.documentElement.dataset.theme === "dark"
    : matchMedia("(prefers-color-scheme: dark)").matches;
  const t = dark ? "light" : "dark"; applyTheme(t); store.set("theme", t);
};

/* ---------- quản lý 3 cột & thu phóng ---------- */
const COL1_DEFAULT = 310;
const COL3_DEFAULT = 480;
let col1W = Number(store.get("col1W", COL1_DEFAULT)) || COL1_DEFAULT;
let col3W = Number(store.get("col3W", COL3_DEFAULT)) || COL3_DEFAULT;
let currentZoom = 1.0;
let modalZoom = 1.0;

function applyColWidths() {
  const layout = $("layout");
  const rect = layout.getBoundingClientRect();
  const cs = getComputedStyle(layout);
  const avail = Math.max(0, rect.width - (parseFloat(cs.paddingLeft) || 0) - (parseFloat(cs.paddingRight) || 0));
  const c1Open = !layout.classList.contains("sources-closed") && innerWidth > 760;
  const c3Open = !layout.classList.contains("viewer-closed") && innerWidth > 1180;
  let w1 = Math.max(220, Math.min(520, col1W));
  let w3 = Math.max(300, Math.min(780, col3W));
  if (avail > 0) {
    const resizers = (c1Open ? 12 : 0) + (c3Open ? 12 : 0);
    const minChat = 340;
    if (c1Open && c3Open) {
      w3 = Math.min(w3, Math.max(300, avail - resizers - minChat - 220));
      w1 = Math.min(w1, Math.max(220, avail - resizers - minChat - w3));
    } else if (c1Open) {
      w1 = Math.min(w1, Math.max(220, avail - resizers - minChat));
    } else if (c3Open) {
      w3 = Math.min(w3, Math.max(300, avail - resizers - minChat));
    }
  }
  layout.style.setProperty("--col1-w", `${Math.round(w1)}px`);
  layout.style.setProperty("--col3-w", `${Math.round(w3)}px`);
}

function toggleCol1(forceState) {
  const layout = $("layout");
  const isClosed = layout.classList.contains("sources-closed");
  const willClose = forceState !== undefined ? !forceState : !isClosed;
  layout.classList.toggle("sources-closed", willClose);
  $("btnToggleCol1").classList.toggle("active", !willClose);
  $("btnRestoreCol1").classList.toggle("hidden", !willClose);
  applyColWidths();
}

function firstDocId() {
  if (!S.docs.length) return null;
  return S.selected.size > 0 ? [...S.selected][0] : S.docs[0].doc_id;
}

function toggleCol3(forceState) {
  const layout = $("layout");
  const isClosed = layout.classList.contains("viewer-closed");
  const willClose = forceState !== undefined ? !forceState : !isClosed;
  layout.classList.toggle("viewer-closed", willClose);
  $("btnToggleCol3").classList.toggle("active", !willClose);
  applyColWidths();
  if (!willClose && !S.viewer && S.docs.length > 0) openSource(firstDocId());
}

function showViewer() {
  $("layout").classList.remove("viewer-closed");
  $("btnToggleCol3").classList.add("active");
  applyColWidths();
  if (innerWidth <= 760) setMobile("viewer");
}

function hideViewer() {
  $("layout").classList.add("viewer-closed");
  $("btnToggleCol3").classList.remove("active");
  S.viewer = null;
  applyColWidths();
  renderSources();
  if (innerWidth <= 760) setMobile("chat");
}

function setupResizer(handle, side) {
  if (!handle) return;
  let active = false;
  handle.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    active = true;
    handle.setPointerCapture(e.pointerId);
    handle.classList.add("dragging");
    $("layout").classList.add("is-resizing");
  });
  handle.addEventListener("pointermove", (e) => {
    if (!active) return;
    const layout = $("layout");
    const rect = layout.getBoundingClientRect();
    const cs = getComputedStyle(layout);
    const padL = parseFloat(cs.paddingLeft) || 0;
    const padR = parseFloat(cs.paddingRight) || 0;
    const avail = rect.width - padL - padR;
    if (side === "left") {
      const c3Open = !layout.classList.contains("viewer-closed") && innerWidth > 1180;
      const rightUsed = c3Open ? (col3W + 12) : 0;
      const maxW = Math.max(220, Math.min(520, avail - rightUsed - 340 - 12));
      col1W = Math.round(Math.max(220, Math.min(maxW, e.clientX - rect.left - padL - 6)));
    } else {
      const c1Open = !layout.classList.contains("sources-closed") && innerWidth > 760;
      const leftUsed = c1Open ? (col1W + 12) : 0;
      const maxW = Math.max(300, Math.min(780, avail - leftUsed - 340 - 12));
      col3W = Math.round(Math.max(300, Math.min(maxW, rect.right - padR - e.clientX - 6)));
    }
    applyColWidths();
  });
  const stop = (e) => {
    if (!active) return;
    active = false;
    if (handle.hasPointerCapture && handle.hasPointerCapture(e.pointerId)) {
      handle.releasePointerCapture(e.pointerId);
    }
    handle.classList.remove("dragging");
    $("layout").classList.remove("is-resizing");
    store.set("col1W", col1W);
    store.set("col3W", col3W);
  };
  handle.addEventListener("pointerup", stop);
  handle.addEventListener("pointercancel", stop);
  handle.addEventListener("dblclick", () => {
    if (side === "left") { col1W = COL1_DEFAULT; store.set("col1W", col1W); }
    else { col3W = COL3_DEFAULT; store.set("col3W", col3W); }
    applyColWidths();
  });
}
setupResizer($("resizerLeft"), "left");
setupResizer($("resizerRight"), "right");
window.addEventListener("resize", applyColWidths);
applyColWidths();

function setZoom(delta, reset = false) {
  if (reset) currentZoom = 1.0;
  else currentZoom = Math.min(2.5, Math.max(0.6, Math.round((currentZoom + delta) * 10) / 10));
  const img = $("pageImg");
  const zoomText = $("zoomVal");
  if (img) img.style.width = `${Math.round(currentZoom * 100)}%`;
  if (zoomText) zoomText.textContent = `${Math.round(currentZoom * 100)}%`;
}

/* ---------- modal xem ảnh trang ---------- */
function modalIsOpen() { return !$("imgModal").classList.contains("hidden"); }
function setModalZoom(delta, reset = false) {
  if (reset) modalZoom = 1.0;
  else modalZoom = Math.min(3, Math.max(0.5, Math.round((modalZoom + delta) * 10) / 10));
  $("modalImg").style.width = `${Math.round(modalZoom * 100)}%`;
  const z = $("modalZoomReset");
  if (z) z.title = `Đặt lại 100% (hiện ${Math.round(modalZoom * 100)}%)`;
}
function syncModal() {
  const img = $("pageImg");
  if (!img || !img.src) return;
  $("modalImg").src = img.src;
  const titleEl = $("vTitleText") || $("vTitle");
  $("modalTitle").textContent = ($("vTitle").title || titleEl.textContent || "Văn bản lưu trữ") + (S.viewer ? ` - Trang ${S.viewer.pageNo}` : "");
  const v = S.viewer;
  if (v) {
    $("modalPrev").disabled = v.pageNo <= 1;
    $("modalNext").disabled = v.pageNo >= v.doc.pages.length;
  }
}
function openFullscreenModal() {
  const img = $("pageImg");
  if (!img || !img.src) return;
  modalZoom = 1.0;
  $("modalImg").style.width = "100%";
  syncModal();
  $("imgModal").classList.remove("hidden");
}
async function modalGo(delta) {
  const v = S.viewer; if (!v) return;
  const next = v.pageNo + delta;
  if (next < 1 || next > v.doc.pages.length) return;
  await openSource(v.docId, next, 0, 0, "page", null, null);
  modalZoom = 1.0;
  $("modalImg").style.width = "100%";
  syncModal();
}
function closeImgModal(e) {
  const t = e && e.target;
  if (!t || t === $("imgModal") || (t.classList && t.classList.contains("img-modal-body")) || (t.closest && t.closest("#modalClose"))) {
    $("imgModal").classList.add("hidden");
  }
}
window.closeImgModal = closeImgModal;

$("btnToggleCol1").onclick = () => toggleCol1();
$("btnCollapseCol1").onclick = () => toggleCol1(false);
$("btnRestoreCol1").onclick = () => toggleCol1(true);
$("btnToggleCol2").onclick = () => {
  $("chatScroll").scrollTop = $("chatScroll").scrollHeight;
  $("q").focus();
};
$("btnToggleCol3").onclick = () => toggleCol3();
$("btnFullscreenPage").onclick = openFullscreenModal;

$("imgModal").addEventListener("click", closeImgModal);
$("modalClose").addEventListener("click", closeImgModal);
$("modalPrev").addEventListener("click", () => modalGo(-1));
$("modalNext").addEventListener("click", () => modalGo(1));
$("modalZoomOut").addEventListener("click", () => setModalZoom(-0.2));
$("modalZoomReset").addEventListener("click", () => setModalZoom(0, true));
$("modalZoomIn").addEventListener("click", () => setModalZoom(0.2));

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    $("imgModal").classList.add("hidden");
    $("llmModal").classList.add("hidden");
  } else if (modalIsOpen() && e.key === "ArrowLeft") { e.preventDefault(); modalGo(-1); }
  else if (modalIsOpen() && e.key === "ArrowRight") { e.preventDefault(); modalGo(1); }
});

/* ---------- nguồn ---------- */
async function loadStatus() {
  const s = await api("/api/status");
  const src = Object.entries(s.by_source).map(([k, v]) => `${SOURCE_LABEL[k] || k} ${v}`).join(" · ");
  $("stat").textContent = `${s.n_docs} văn bản · ${s.n_pages} trang (${src})`;
}
async function loadDocs() {
  S.docs = await api("/api/docs");
  const saved = store.get("selected", null);
  const ids = new Set(S.docs.map(d => d.doc_id));
  S.selected = saved ? new Set(saved.filter(id => ids.has(id))) : new Set(ids);
  renderSources();
}
function docById(id) { return S.docs.find(d => d.doc_id === id); }
function renderSources() {
  const f = $("filter").value.trim().toLowerCase();
  const list = $("srcList"); list.replaceChildren();
  for (const d of S.docs) {
    const hay = [d.doc_id, d.label, d.doc_number, d.subject, d.doc_type].join(" ").toLowerCase();
    if (f && !hay.includes(f)) continue;
    const cb = el("input", {type: "checkbox", class: "src-check", "aria-label": "Dùng nguồn " + d.label});
    cb.checked = S.selected.has(d.doc_id);
    cb.onchange = () => { cb.checked ? S.selected.add(d.doc_id) : S.selected.delete(d.doc_id); saveSel(); };
    const badges = el("span", {class: "src-badges"},
      el("span", {class: "badge-pages"}, `${d.n_pages} tr.`),
      d.upload ? el("span", {class: "badge-upload"}, "Tải lên") : null,
      d.n_missing > 0 ? el("span", {class: "badge-miss"}, `${d.n_missing} chưa OCR`) : null);
    list.append(el("li", {class: "src-item" + (S.viewer?.docId === d.doc_id ? " active" : "")},
      cb,
      el("span", {class: "src-icon", "aria-hidden": "true"}, svgIcon("file", 16)),
      el("button", {class: "src-main", onclick: () => openSource(d.doc_id), title: "Xem nguồn"},
        el("div", {class: "src-head"},
          el("span", {class: "src-title", title: d.label}, d.label),
          badges),
        el("div", {class: "src-sub"}, d.subject || "(chưa trích được trích yếu)"),
        d.upload ? el("div", {class: "src-up"}, `Tải lên ${fmtTime(d.upload.uploaded_at)} · ${fmtSize(d.upload.size_bytes)}`) : null),
      d.upload ? el("button", {class: "icon-btn del", title: "Xóa tệp tải lên", "aria-label": "Xóa " + d.label,
        onclick: () => deleteUpload(d)}, svgIcon("trash", 15)) : null));
  }
  updateSelInfo();
}
function fmtTime(iso) {
  const d = new Date(iso); if (isNaN(d)) return "";
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())} ${p(d.getDate())}/${p(d.getMonth() + 1)}`;
}
function fmtSize(b) { return b == null ? "" : b < 1048576 ? `${Math.round(b / 1024)} KB` : `${(b / 1048576).toFixed(1)} MB`; }
async function deleteUpload(d) {
  if (!confirm(`Xóa tệp tải lên "${d.upload.original_name || d.label}" khỏi kho và khỏi đĩa?`)) return;
  try {
    await api(`/api/uploads/${encodeURIComponent(d.doc_id)}`, {method: "DELETE"});
    S.selected.delete(d.doc_id); docCache.delete(d.doc_id); saveSel();
    if (S.viewer?.docId === d.doc_id) $("vClose").click();
    await Promise.all([loadDocs(), loadStatus()]);
  } catch (e) { alert("Không xóa được: " + e.message); }
}
function saveSel() { store.set("selected", [...S.selected]); updateSelInfo(); }
function updateSelInfo() {
  const n = S.selected.size, total = S.docs.length;
  $("srcCount").textContent = `${n}/${total}`;
  const badge = $("col1Badge"); if (badge) badge.textContent = n;
  $("selInfo").textContent = n === total ? `Tất cả ${total} nguồn` : `${n} nguồn đang chọn`;
  $("selAll").checked = n === total && total > 0;
  $("selAll").indeterminate = n > 0 && n < total;
  if (!S.messages.length) renderChat();
}
$("selAll").onchange = (e) => {
  S.selected = e.target.checked ? new Set(S.docs.map(d => d.doc_id)) : new Set();
  saveSel(); renderSources();
};
$("filter").oninput = renderSources;
$("addBtn").onclick = () => $("upFile").click();

async function uploadPdfFile(file) {
  if (!file) return;
  const msg = $("upMsg"); msg.classList.remove("hidden"); msg.textContent = `Đang đọc ${file.name}…`;
  try {
    const d = await api("/api/upload", {method: "POST", body: file,
      headers: {"Content-Type": "application/pdf", "X-Filename": encodeURIComponent(file.name)}});
    S.selected.add(d.doc_id); saveSel();
    await Promise.all([loadDocs(), loadStatus()]);
    msg.textContent = d.n_missing ? `Đã thêm; ${d.n_missing}/${d.n_pages} trang là scan chưa OCR nên chưa tìm được.` : "Đã thêm vào nguồn.";
    openSource(d.doc_id);
  } catch (err) { msg.textContent = "Lỗi: " + err.message; }
}
$("upFile").onchange = async (e) => {
  const file = e.target.files[0]; e.target.value = "";
  await uploadPdfFile(file);
};
(function setupDrop() {
  const btn = $("addBtn");
  for (const ev of ["dragenter", "dragover"]) {
    btn.addEventListener(ev, (e) => { e.preventDefault(); btn.classList.add("dragover"); });
  }
  for (const ev of ["dragleave", "drop"]) {
    btn.addEventListener(ev, (e) => {
      e.preventDefault(); btn.classList.remove("dragover");
      if (ev !== "drop") return;
      const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (!file) return;
      if (!/\.pdf$/i.test(file.name) && file.type !== "application/pdf") {
        const msg = $("upMsg"); msg.classList.remove("hidden"); msg.textContent = "Chỉ hỗ trợ tệp PDF.";
        return;
      }
      uploadPdfFile(file);
    });
  }
})();

/* ---------- xem nguồn ---------- */
const docCache = new Map();
async function getDoc(id) {
  if (!docCache.has(id)) docCache.set(id, await api(`/api/docs/${encodeURIComponent(id)}`));
  return docCache.get(id);
}
$("vClose").onclick = hideViewer;
$("tabPage").onclick = () => {
  if (S.viewer) { S.viewer.tab = "page"; renderViewer(); }
  else if (S.docs.length) openSource(firstDocId(), 1, 0, 0, "page");
};
$("tabCard").onclick = () => {
  if (S.viewer) { S.viewer.tab = "card"; renderViewer(); }
  else if (S.docs.length) openSource(firstDocId(), 1, 0, 0, "card");
};

async function openSource(docId, pageNo = 1, start = 0, end = 0, tab = null, citedText = null, citeIndex = null) {
  if (String(docId || "").startsWith("GUIDE_")) return;
  const d = await getDoc(docId);
  S.viewer = {
    docId,
    doc: d,
    pageNo,
    start,
    end,
    tab: tab || (end > start || citedText ? "page" : (S.viewer?.tab || "card")),
    citedText: citedText || (end > start && S.viewer?.citedText ? S.viewer.citedText : null),
    citeIndex: citeIndex || (S.viewer?.citeIndex || null)
  };
  currentZoom = 1.0;
  showViewer();
  renderViewer();
  renderSources();
}

function renderViewer() {
  const v = S.viewer, d = v.doc;
  const fullTitle = d.label + (d.doc_number ? ` (${d.doc_number})` : "");
  const vTitleText = $("vTitleText");
  if (vTitleText) vTitleText.textContent = fullTitle;
  else $("vTitle").textContent = fullTitle;
  $("vTitle").title = fullTitle;
  $("tabPage").classList.toggle("on", v.tab === "page");
  $("tabCard").classList.toggle("on", v.tab === "card");
  const body = $("vBody"); body.replaceChildren();

  if (v.tab === "card") {
    body.append(renderSummaryBox(d));
    const guide = el("div", {class: "guide"}, el("h3", {}, "Trích yếu / tiêu đề"),
      el("div", {}, d.subject || "Chưa trích được trích yếu."));
    const tb = el("tbody");
    for (const f of d.fields) {
      const val = Array.isArray(f.value) ? f.value.join("; ") : f.value;
      tb.append(el("tr", {}, el("th", {}, f.label), el("td", {}, val,
        el("button", {class: "pg-link", onclick: () => openSource(d.doc_id, f.page_no, f.start, f.end, "page", val)}, `tr. ${f.page_no}`))));
    }
    const notes = [];
    if (d.flags.includes("issue_date_blank")) notes.push("PDF để trống ngày ban hành (thường nằm trên chữ ký số dạng ảnh).");
    if (d.flags.includes("doc_number_blank")) notes.push("PDF để trống phần số của số ký hiệu.");
    if (d.flags.includes("first_page_missing") || d.flags.includes("no_text")) notes.push("Trang đầu là scan chưa OCR nên thẻ có thể thiếu trường.");
    body.append(guide, el("table", {class: "fields"}, tb),
      el("p", {class: "small muted"}, "Thẻ do luật trích tự động (nhãn bạc, chưa người duyệt). " + notes.join(" ")));
    if (d.suggestions?.length) {
      body.append(el("div", {class: "small muted quick-label"}, "Hỏi nhanh về nguồn này:"),
        el("div", {class: "follow pills"}, d.suggestions.map(q => el("button", {onclick: () => { S.selected.add(d.doc_id); saveSel(); renderSources(); send(q); }}, q))));
    }
    return;
  }

  const page = d.pages.find(p => p.page_no === v.pageNo) || d.pages[0];

  // 1. Khung căn cứ trích dẫn
  if (v.citedText) {
    body.append(el("div", {class: "evidence-box"},
      el("div", {class: "ev-badge"},
        el("span", {class: "ev-label"}, svgIcon("pin", 14), "CĂN CỨ TRÍCH DẪN" + (v.citeIndex ? ` [${v.citeIndex}]` : "")),
        el("span", {class: "ev-page"}, `Trang ${page.page_no}/${d.pages.length}`)
      ),
      el("div", {class: "ev-text"}, `“${v.citedText}”`),
      el("div", {class: "ev-meta"},
        el("span", {class: "ev-doc"}, svgIcon("landmark", 14), d.label),
        d.doc_number ? el("span", {}, `№ ${d.doc_number}`) : null,
        el("span", {class: "ev-hint"}, svgIcon("sparkle", 14), "Vị trí trích dẫn đang được tô vàng trên bản scan dưới đây")
      )
    ));
  }

  // 2. Thanh công cụ trang & thu phóng
  const toolbar = el("div", {class: "viewer-toolbar"},
    el("div", {class: "page-nav"},
      el("button", {class: "sum-btn", onclick: () => openSource(d.doc_id, page.page_no - 1, 0, 0, "page", null, null), disabled: page.page_no <= 1, title: "Trang trước"},
        svgIcon("chevronLeft", 14), "Trước"),
      el("span", {class: "page-no"}, `Trang ${page.page_no}/${d.pages.length}`),
      el("button", {class: "sum-btn", onclick: () => openSource(d.doc_id, page.page_no + 1, 0, 0, "page", null, null), disabled: page.page_no >= d.pages.length, title: "Trang sau"},
        "Sau", svgIcon("chevronRight", 14)),
      el("span", {class: "small muted page-src"}, `(${SOURCE_LABEL[page.source] || page.source})`)
    ),
    el("div", {class: "zoom-btn-group"},
      el("button", {title: "Thu nhỏ", "aria-label": "Thu nhỏ", onclick: () => setZoom(-0.2)}, svgIcon("zoomOut", 15)),
      el("button", {title: "Đặt lại kích thước 100%", id: "zoomVal", onclick: () => setZoom(0, true)}, `${Math.round(currentZoom * 100)}%`),
      el("button", {title: "Phóng to", "aria-label": "Phóng to", onclick: () => setZoom(0.2)}, svgIcon("zoomIn", 15)),
      el("button", {title: "Xem toàn màn hình", class: "zoom-full", onclick: openFullscreenModal}, svgIcon("expand", 14), "Toàn cảnh")
    )
  );
  body.append(toolbar);

  if (page.source === "missing") {
    body.append(el("div", {class: "missing-note"}, svgIcon("warn", 15), "Trang scan chưa OCR: chưa có lớp chữ để nhận diện và trích dẫn."));
  }

  // 3. Khung ảnh có tô vàng
  const viewport = el("div", {class: "page-viewport"});
  const imgUrl = `/api/page/${encodeURIComponent(d.doc_id)}/${page.page_no}.png?start=${v.start}&end=${v.end}`;
  const img = el("img", {
    id: "pageImg",
    class: "page-img",
    alt: `${d.label}, trang ${page.page_no}`,
    src: imgUrl,
    loading: "eager",
    title: "Nhấp đúp chuột để xem toàn màn hình",
    ondblclick: openFullscreenModal
  });
  img.style.width = `${Math.round(currentZoom * 100)}%`;
  viewport.append(img);
  body.append(viewport);
}

/* ---------- tóm tắt văn bản ---------- */
const summaryCache = new Map();
function renderSummaryBox(d) {
  const box = el("div", {class: "guide summary-box"});
  const head = el("div", {class: "sum-head"}, el("h3", {}, "Tóm tắt có trích dẫn"));
  const content = el("div", {});
  const useLlm = () => $("llmToggle").checked;
  const btn = el("button", {class: "sum-btn", onclick: () => load(false)}, "Tạo tóm tắt");
  head.append(btn); box.append(head, content);

  function show(s) {
    btn.textContent = s.points.length ? "Tạo lại" : "Tạo tóm tắt";
    if (!s.points.length) {
      const hint = !useLlm()
        ? "Bấm “Tạo tóm tắt” để trích các câu tiêu biểu; bật “Trả lời bằng LLM” để LLM viết tóm tắt."
        : (S.llm?.provider === "openrouter"
            ? "Bấm “Tạo tóm tắt”: OpenRouter LLM đọc các đoạn tiêu biểu và tổng hợp (≈ 2–5 s)."
            : "Bấm “Tạo tóm tắt”: LLM cục bộ đọc các đoạn tiêu biểu (≈ 30–60 s).");
      content.replaceChildren(el("div", {class: "small muted"}, hint));
      return;
    }
    const ul = el("ul", {class: "sum-list"});
    for (const p of s.points) {
      const li = el("li", {}, p.text.trim(), " ");
      for (const n of p.sources) if (s.citations[n - 1]) li.append(citeChip(n, s.citations[n - 1]));
      ul.append(li);
    }
    const m = s.meta || {};
    const info = s.kind === "llm"
      ? `LLM ${(m.model || "").split("/").pop()} · ${m.seconds ?? "?"} s · từ ${m.n_passages} đoạn (trang ${(m.pages || []).join(", ")})`
        + (m.dropped?.length ? ` · đã cắt ${m.dropped.length} ý không khớp nguồn` : "")
      : `Trích nguyên văn từ ${m.n_passages} đoạn tiêu biểu (trang ${(m.pages || []).join(", ")})`
        + (m.fallback ? " · " + m.fallback : "");
    content.replaceChildren(ul, el("div", {class: "small muted"}, info));
  }
  async function load(cachedOnly) {
    const use_llm = useLlm();
    const key = `${d.doc_id}:${use_llm}:${S.llm?.provider || ""}:${S.llm?.model || ""}`;
    if (cachedOnly && summaryCache.has(key)) return show(summaryCache.get(key));
    if (!cachedOnly) {
      btn.disabled = true;
      const waitTxt = use_llm
        ? (S.llm?.provider === "openrouter" ? "OpenRouter đang tóm tắt (≈ 2–5 s)…" : "LLM đang tóm tắt (≈ 30–60 s)…")
        : "Đang chọn câu tiêu biểu…";
      content.replaceChildren(el("div", {class: "typing"}, el("i"), el("i"), el("i"),
        el("span", {class: "typing-text"}, waitTxt)));
    }
    try {
      const s = await api(`/api/docs/${encodeURIComponent(d.doc_id)}/summary?use_llm=${use_llm}&cached_only=${cachedOnly}&refresh=${cachedOnly ? "false" : "true"}`);
      if (s.points.length) summaryCache.set(key, s);
      show(s);
    } catch (e) { content.replaceChildren(el("div", {class: "warn"}, "Lỗi: " + e.message)); }
    btn.disabled = false;
    refreshLlm();
  }
  load(true);
  return box;
}

/* ---------- trò chuyện ---------- */
function renderChat() {
  const inner = $("chatInner"); inner.replaceChildren();
  $("chat").classList.toggle("has-msgs", S.messages.length > 0);
  if (!S.messages.length) {
    const n = S.selected.size;
    inner.append(
      el("div", {class: "empty empty-studio"},
        el("div", {class: "empty-icon"}, svgIcon("sparkle", 28)),
        el("h3", {class: "empty-title"}, "Hỏi về các văn bản trong kho"),
        el("p", {class: "empty-sub"}, `${n} nguồn đang chọn · mọi câu trả lời đều kèm số trích dẫn tới (văn bản, trang)`),
        n === 0 ? el("div", {class: "empty-warn"}, svgIcon("warn", 15), "Chưa chọn nguồn nào. Hãy tích chọn ít nhất một nguồn ở cột bên trái.") : null,
        el("div", {class: "suggest-grid"},
          DEFAULT_SUGGEST.map(item =>
            el("button", {class: "suggest-card", onclick: () => send(item.q)},
              el("span", {class: "suggest-tag" + (item.trap ? " trap" : "")}, item.tag),
              el("span", {class: "suggest-q"}, item.q)
            )
          )
        )
      )
    );
    return;
  }
  for (const m of S.messages) inner.append(m.role === "user" ? renderUser(m) : renderBot(m));
  requestAnimationFrame(() => { $("chatScroll").scrollTop = $("chatScroll").scrollHeight; });
}
function renderUser(m) { return el("div", {class: "msg user"}, el("div", {class: "bubble"}, m.text)); }

function inlineNodes(text, cites) {
  const out = [];
  for (const part of text.split(/(\[\d+\]|\*\*[^*]+\*\*|`[^`]+`)/)) {
    if (!part) continue;
    const mm = part.match(/^\[(\d+)\]$/);
    if (mm && cites[+mm[1] - 1]) out.push(citeChip(+mm[1], cites[+mm[1] - 1]));
    else if (/^\*\*[^*]+\*\*$/.test(part)) out.push(el("strong", {}, part.slice(2, -2)));
    else if (/^`[^`]+`$/.test(part)) out.push(el("code", {}, part.slice(1, -1)));
    else out.push(document.createTextNode(part));
  }
  return out;
}
function richText(text, cites) {
  const box = el("div", {}); let ul = null;
  for (const line of text.split("\n")) {
    if (!line.trim()) { ul = null; continue; }
    const hd = line.match(/^#{2,3}\s+(.*)$/);
    if (hd) { ul = null; box.append(el("h4", {}, inlineNodes(hd[1], cites))); continue; }
    const li = line.match(/^\s*[-•*]\s+(.*)$/);
    if (li) { if (!ul) { ul = el("ul"); box.append(ul); } ul.append(el("li", {}, inlineNodes(li[1], cites))); }
    else { ul = null; box.append(el("p", {}, inlineNodes(line, cites))); }
  }
  return box;
}
function citeChip(n, c) {
  const b = el("button", {
    class: "cite",
    "aria-label": `Nguồn [${n}]: ${c.label}, trang ${c.page_no}`,
    title: `Nhấp để mở xem trang ${c.page_no} của văn bản [${n}] (có tô sáng vàng)`,
    onclick: () => openSource(c.doc_id, c.page_no, c.start, c.end, "page", c.text, n)
  }, String(n));
  b.addEventListener("mouseenter", () => showTip(b, c));
  b.addEventListener("mouseleave", hideTip);
  b.addEventListener("focus", () => showTip(b, c));
  b.addEventListener("blur", hideTip);
  return b;
}
function showTip(anchor, c) {
  const tip = $("tip"); const snippet = c.text.length > 260 ? c.text.slice(0, 260) + "…" : c.text;
  tip.replaceChildren(el("b", {}, `${c.label} · trang ${c.page_no}`), el("div", {}, snippet));
  tip.classList.remove("hidden");
  const r = anchor.getBoundingClientRect(), w = Math.min(360, innerWidth - 16);
  tip.style.left = Math.max(8, Math.min(r.left - 20, innerWidth - w - 8)) + "px";
  const below = r.bottom + 8, h = tip.offsetHeight;
  tip.style.top = (below + h > innerHeight ? r.top - h - 8 : below) + "px";
}
function hideTip() { $("tip").classList.add("hidden"); }

function copyButton(text) {
  const btn = el("button", {class: "copy-btn", type: "button", title: "Sao chép câu trả lời", "aria-label": "Sao chép câu trả lời"});
  const reset = () => { btn.classList.remove("copied"); btn.replaceChildren(svgIcon("copy", 14), "Sao chép"); };
  reset();
  btn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(text);
      btn.classList.add("copied");
      btn.replaceChildren(svgIcon("check", 14), "Đã chép");
      setTimeout(reset, 1500);
    } catch { btn.replaceChildren(svgIcon("warn", 14), "Không chép được"); setTimeout(reset, 1500); }
  });
  return btn;
}

function renderBot(m) {
  if (m.pending) return el("div", {class: "msg bot"}, el("div", {class: "typing"}, el("i"), el("i"), el("i"),
    el("span", {class: "typing-text"}, m.useLlm
      ? (S.llm?.provider === "openrouter" ? "Đang tìm nguồn và gọi OpenRouter API…" : "Đang tìm nguồn và soạn câu trả lời (LLM cục bộ)…")
      : "Đang tìm trong nguồn…")));
  if (m.error) return el("div", {class: "msg bot refused"},
    el("div", {class: "bot-card"}, el("div", {class: "body"}, el("div", {class: "warn"}, "Lỗi: " + m.error))));
  const a = m.answer || {}, ok = a.status === "answered";
  const citations = Array.isArray(a.citations) ? a.citations : [];
  const warnings = Array.isArray(a.warnings) ? a.warnings : [];
  const retrieved = Array.isArray(a.retrieved) ? a.retrieved : [];
  const body = el("div", {class: "body"});
  if (!ok) body.append(el("div", {class: "refused-tag"}, "Không đủ căn cứ để trả lời"));
  body.append(richText(a.text || "", citations));
  if (!ok && a.reason) body.append(el("div", {class: "small muted"}, a.reason));
  const card = el("div", {class: "bot-card"},
    el("div", {class: "bot-head"}, el("span", {class: "bot-role"}, "Trợ lý lưu trữ"), copyButton(a.text || "")),
    body);
  const node = el("div", {class: "msg bot" + (ok ? "" : " refused")}, card);
  if (citations.length) {
    const seen = new Set(), pills = el("div", {class: "pills"});
    citations.forEach((c, i) => {
      const key = `${c.doc_id}|${c.page_no}`; if (seen.has(key)) return; seen.add(key);
      const isGuide = String(c.doc_id || "").startsWith("GUIDE_");
      pills.append(el("button", {
        class: "src-pill",
        onclick: isGuide ? null : () => openSource(c.doc_id, c.page_no, c.start, c.end, "page", c.text, i + 1),
        title: isGuide ? (c.label || "Tài liệu hướng dẫn") : `Nhấp để mở xem trang ${c.page_no} của ${c.label} (có tô vàng)`
      },
        el("span", {class: "n"}, String(i + 1)),
        el("span", {class: "t"}, svgIcon("file", 13), isGuide ? (c.label || c.doc_id) : `${c.label} · tr. ${c.page_no}`)
      ));
    });
    node.append(pills);
  }
  const foot = el("div", {class: "msg-foot"});
  if (ok) foot.append(el("span", {}, a.kind === "llm" ? "Diễn đạt bằng LLM, đã kiểm từng câu theo nguồn"
    : a.kind === "summary" ? (a.meta?.model && a.meta.model !== "extractive" && !a.meta.fallback
        ? "Tóm tắt bằng LLM, đã kiểm từng ý theo nguồn" : "Tóm tắt trích nguyên văn")
    : a.kind === "field" ? "Lấy từ thẻ thông tin"
    : a.kind === "list" ? "Danh sách văn bản liên quan"
    : a.kind === "conversation" ? "Hội thoại trợ lý"
    : a.kind === "archive_stats" ? "Thống kê kho trực tiếp"
    : a.kind === "procedure" ? "Quy trình nghiệp vụ lưu trữ"
    : a.kind === "archive_catalog" ? "Danh mục Phông lưu trữ"
    : a.kind === "dossier_detail" ? "Chi tiết Hồ sơ lưu trữ"
    : a.kind === "archive_lookup" ? "Tra cứu Phông – Hồ sơ"
    : "Trích nguyên văn"));
  if (foot.childNodes.length) node.append(foot);
  if (Array.isArray(a.suggestions) && a.suggestions.length) {
    node.append(el("div", {class: "follow pills"}, a.suggestions.map(q => el("button", {onclick: () => send(q)}, q))));
  }
  for (const w of warnings) node.append(el("div", {class: "warn"}, svgIcon("warn", 14), w));

  const metrics = el("div", {class: "more-metrics"});
  if (a.confidence != null) {
    const mtr = el("span", {class: "meter"}); const bar = el("i"); bar.style.width = `${Math.round(a.confidence * 100)}%`; mtr.append(bar);
    metrics.append(el("span", {title: "Tỉ lệ từ khóa câu hỏi có trong đoạn nguồn (âm tiết theo idf và cặp âm tiết)"}, "Độ phủ căn cứ ", mtr, ` ${a.confidence.toFixed(2)}`));
  }
  const g = a.meta?.gate;
  if (g?.dense != null) metrics.append(el("span", {title: "Cosine e5 giữa câu hỏi và đoạn gần nghĩa nhất"},
    `Độ gần nghĩa ${g.dense.toFixed(2)}` + (g.via === "nghĩa" ? " (đạt nhờ tìm theo nghĩa)" : "")));
  if (a.meta?.seconds != null) metrics.append(el("span", {}, `LLM ${a.meta.seconds} s · ${a.meta.new_tokens} token`));

  const hasMetrics = metrics.childNodes.length > 0;
  const hasRewrites = !!a.meta?.rewrites?.length;
  const hasDropped = !!a.meta?.dropped?.length;
  if (hasMetrics || retrieved.length || hasRewrites || hasDropped) {
    const det = el("details", {class: "more"}, el("summary", {}, "Chi tiết truy hồi"));
    if (hasMetrics) det.append(metrics);
    if (hasRewrites) det.append(el("div", {class: "more-note"}, "Câu hỏi được LLM viết lại để tìm rộng hơn: " + a.meta.rewrites.join(" · ")));
    if (retrieved.length) {
      const t = el("tbody");
      for (const r of retrieved.slice(0, 8)) t.append(el("tr", {},
        el("td", {}, `${docById(r.doc_id)?.label || r.doc_id} · tr. ${r.page_no}${r.section ? " · " + r.section : ""}`),
        el("td", {}, `RRF ${r.rrf.toFixed(4)}`), el("td", {}, `phủ ${r.coverage.toFixed(2)}`),
        el("td", {}, r.dense != null ? `nghĩa ${r.dense.toFixed(2)}` : "")));
      det.append(el("div", {class: "more-table-wrap"}, el("table", {}, t)));
    }
    if (hasDropped) {
      det.append(el("div", {class: "more-note"}, "Câu LLM bị cắt:"));
      for (const d of a.meta.dropped) det.append(el("div", {class: "dropped-row"}, svgIcon("scissors", 13), `“${d.text}” — ${d.reason}`));
    }
    node.append(det);
  }
  return node;
}

let pendingQuestionAfterConfig = null;
let pendingRetryPair = null;

async function send(text) {
  const q = (text ?? $("q").value).trim();
  if (!q || S.busy) return;
  const useLlm = $("llmToggle").checked;
  if (useLlm && S.llm && S.llm.provider === "openrouter" && !S.llm.has_api_key) {
    pendingQuestionAfterConfig = q;
    pendingRetryPair = null;
    openLlmModal("Vui lòng nhập OPENROUTER_API_KEY để sử dụng LLM qua OpenRouter (hoặc tắt công tắc LLM để trích xuất cục bộ).");
    return;
  }
  $("q").value = ""; autoGrow(); S.busy = true; updateSend();
  const userMsg = {role: "user", text: q};
  const pending = {role: "bot", pending: true, useLlm};
  S.messages.push(userMsg, pending); renderChat();
  if (innerWidth <= 760) setMobile("chat");
  try {
    const all = S.selected.size === S.docs.length;
    pending.answer = await api("/api/ask", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({question: q, doc_ids: all ? null : [...S.selected], use_llm: useLlm, session_id: S.sessionId})});
    const c = (pending.answer.citations || [])[0];
    if (pending.answer.status === "answered" && c && !String(c.doc_id || "").startsWith("GUIDE_") && innerWidth > 1180) {
      openSource(c.doc_id, c.page_no, c.start, c.end, "page", c.text, 1);
    }
  } catch (e) {
    pending.error = e.message;
    if (/OPENROUTER_API_KEY/i.test(e.message)) {
      pendingQuestionAfterConfig = q;
      pendingRetryPair = [userMsg, pending];
      openLlmModal(e.message);
    }
  }
  pending.pending = false; S.busy = false; updateSend(); renderChat(); refreshLlm();
}
function updateSend() { $("sendBtn").disabled = S.busy || !$("q").value.trim(); }
function autoGrow() {
  const t = $("q");
  t.style.height = "auto";
  const nextH = Math.min(t.scrollHeight, 160);
  t.style.height = nextH + "px";
  t.style.overflowY = t.scrollHeight > 160 ? "auto" : "hidden";
}
autoGrow();
$("q").addEventListener("input", () => { autoGrow(); updateSend(); });
$("q").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } });
$("sendBtn").onclick = () => send();
$("clearBtn").onclick = () => { S.messages = []; S.sessionId = "nb_" + Math.random().toString(36).slice(2, 10); renderChat(); };

/* ---------- LLM & OpenRouter Config ---------- */
function setLlmModalMsg(msg = "", isInfo = false) {
  const errEl = $("llmModalErr");
  if (!errEl) return;
  errEl.classList.remove("warn", "info", "hidden");
  if (!msg) {
    errEl.textContent = "";
    errEl.classList.add("hidden");
    return;
  }
  errEl.textContent = msg;
  errEl.classList.add(isInfo ? "info" : "warn");
}
function syncLlmAuthUI() {
  const isAdmin = S.user && S.user.role === "admin";
  const box = $("llmAuthBox");
  if (box) box.classList.toggle("hidden", !!isAdmin);
}
async function refreshAuth() {
  try {
    const me = await api("/api/auth/me");
    if (me && me.authenticated && me.user) {
      S.user = me.user;
    } else {
      S.user = null;
      try { localStorage.removeItem("archive_token"); } catch {}
    }
  } catch {
    S.user = null;
  }
  syncLlmAuthUI();
}
async function quickAdminLogin() {
  const pwEl = $("llmAdminPw");
  const pw = pwEl ? pwEl.value : "";
  if (!pw) {
    setLlmModalMsg("Vui lòng nhập mật khẩu Quản trị viên.");
    if (pwEl) pwEl.focus();
    return;
  }
  const btn = $("llmAdminLoginBtn");
  if (btn) btn.disabled = true;
  try {
    const res = await api("/api/auth/login", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({username: "admin", password: pw}),
    });
    if (res && res.token) {
      try { localStorage.setItem("archive_token", res.token); } catch {}
      S.user = res.user || {username: "admin", role: "admin"};
      if (pwEl) pwEl.value = "";
      syncLlmAuthUI();
      setLlmModalMsg("Đã đăng nhập Quản trị viên. Bạn có thể lưu cấu hình API.", true);
      docCache.clear();
      Promise.all([loadDocs(), loadStatus()]).catch(() => {});
    }
  } catch (e) {
    setLlmModalMsg(e.message || "Đăng nhập thất bại.");
  } finally {
    if (btn) btn.disabled = false;
  }
}
if ($("llmAdminLoginBtn")) $("llmAdminLoginBtn").onclick = quickAdminLogin;
if ($("llmAdminPw")) $("llmAdminPw").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); quickAdminLogin(); } });

function syncModalProviderUI() {
  const isOr = $("llmProviderSel").value === "openrouter";
  $("openrouterFields").classList.toggle("hidden", !isOr);
  $("llmClearKeyBtn").classList.toggle("hidden", !isOr);
}
function highlightPreset(val) {
  const cur = (val || "").trim();
  for (const btn of $("llmPresetList").querySelectorAll(".llm-preset")) {
    btn.classList.toggle("active", btn.dataset.model === cur);
  }
}
function openLlmModal(msg = "", isInfo = false) {
  const st = S.llm || {};
  $("llmProviderSel").value = st.provider || "openrouter";
  $("llmApiKeyInput").value = "";
  $("llmKeyStatus").textContent = st.has_api_key
    ? `Đã lưu khóa: ${st.api_key_masked || "••••"} (để trống nếu muốn giữ nguyên)`
    : "Chưa có khóa OpenRouter API. Dán khóa dạng sk-or-v1-... vào đây.";
  $("llmModelInput").value = st.openrouter_model || st.model || "google/gemini-2.0-flash-001";
  highlightPreset($("llmModelInput").value);
  syncModalProviderUI();
  syncLlmAuthUI();
  setLlmModalMsg(msg, isInfo);
  $("llmModal").classList.remove("hidden");
  if ($("llmProviderSel").value === "openrouter" && !st.has_api_key) $("llmApiKeyInput").focus();
}
function closeLlmModal() {
  $("llmModal").classList.add("hidden");
  pendingQuestionAfterConfig = null;
  pendingRetryPair = null;
}

async function refreshLlm() {
  try {
    S.llm = await api("/api/llm/status");
    const cfgBtn = $("btnLlmConfig");
    if (S.llm.provider === "openrouter") {
      const shortName = (S.llm.openrouter_model || S.llm.model || "").split("/").pop();
      $("llmToggle").disabled = false;
      $("llmInfo").textContent = S.llm.has_api_key
        ? `Trợ lý AI Đám mây · ${shortName}`
        : `OpenRouter · chưa cấu hình máy chủ`;
      if (cfgBtn) {
        cfgBtn.classList.add("hidden");
        cfgBtn.classList.remove("needs-key");
      }
    } else {
      const name = (S.llm.local_model || S.llm.model || "").split("/").pop();
      $("llmToggle").disabled = !S.llm.downloaded;
      if (!S.llm.downloaded) $("llmToggle").checked = false;
      $("llmInfo").textContent = !S.llm.downloaded ? `(chưa tải ${name})`
        : S.llm.loaded ? `${name} · ${S.llm.device === "cuda" ? "GPU" : "CPU"}` : `${name} · nạp ở lần hỏi đầu`;
      if (cfgBtn) {
        cfgBtn.classList.add("hidden");
        cfgBtn.classList.remove("needs-key");
      }
    }
  } catch { $("llmToggle").disabled = true; $("llmToggle").checked = false; $("llmInfo").textContent = "(LLM không dùng được)"; }
}
$("llmToggle").checked = store.get("useLlm_v2", true);
$("llmToggle").onchange = async (e) => {
  store.set("useLlm_v2", e.target.checked);
  if (e.target.checked && S.llm) {
    if (S.llm.provider === "openrouter" && !S.llm.has_api_key) {
      openLlmModal("Vui lòng nhập OPENROUTER_API_KEY để bật trả lời bằng OpenRouter.");
      return;
    }
    if (S.llm.provider === "local" && !S.llm.loaded) {
      $("llmInfo").textContent = "Đang nạp mô hình…";
      try { await api("/api/llm/load", {method: "POST"}); } catch (err) { $("llmInfo").textContent = "Lỗi: " + err.message; return; }
      refreshLlm();
    }
  }
};

$("btnLlmConfig").onclick = () => openLlmModal();
$("llmModalClose").onclick = closeLlmModal;
$("llmModal").addEventListener("click", (e) => { if (e.target === $("llmModal")) closeLlmModal(); });
$("llmProviderSel").onchange = syncModalProviderUI;
$("llmModelInput").addEventListener("input", () => highlightPreset($("llmModelInput").value));
$("llmPresetList").addEventListener("click", (e) => {
  const b = e.target.closest(".llm-preset");
  if (!b) return;
  $("llmModelInput").value = b.dataset.model;
  highlightPreset(b.dataset.model);
});
$("llmClearKeyBtn").onclick = async () => {
  try {
    S.llm = await api("/api/llm/config", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({api_key: ""})});
    summaryCache.clear();
    await refreshLlm();
    if (S.viewer?.tab === "card") renderViewer();
    openLlmModal("Đã xóa OPENROUTER_API_KEY khỏi cấu hình.", true);
  } catch (e) {
    if (e.status === 401 || e.status === 403) {
      $("llmAuthBox")?.classList.remove("hidden");
      $("llmAdminPw")?.focus();
    }
    setLlmModalMsg(e.message);
  }
};
$("llmSaveBtn").onclick = async () => {
  const provider = $("llmProviderSel").value;
  const rawKey = $("llmApiKeyInput").value.trim();
  const model = $("llmModelInput").value.trim();
  if (provider === "openrouter" && !rawKey && !S.llm?.has_api_key) {
    setLlmModalMsg("Vui lòng nhập khóa OPENROUTER_API_KEY (sk-or-v1-...) trước khi lưu.");
    $("llmApiKeyInput").focus();
    return;
  }
  const payload = {provider};
  if (provider === "openrouter") {
    if (rawKey) payload.api_key = rawKey;
    if (model) payload.model = model;
  }
  $("llmSaveBtn").disabled = true;
  try {
    S.llm = await api("/api/llm/config", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)});
    summaryCache.clear();
    await refreshLlm();
    if (S.viewer?.tab === "card") renderViewer();
    const qPending = pendingQuestionAfterConfig;
    const retryPair = pendingRetryPair;
    closeLlmModal();
    if (qPending && (S.llm.provider !== "openrouter" || S.llm.has_api_key)) {
      if (retryPair) {
        S.messages = S.messages.filter(m => m !== retryPair[0] && m !== retryPair[1]);
      }
      send(qPending);
    }
  } catch (e) {
    if (e.status === 401 || e.status === 403) {
      $("llmAuthBox")?.classList.remove("hidden");
      $("llmAdminPw")?.focus();
      setLlmModalMsg("Cần đăng nhập Quản trị viên (ô phía trên) trước khi lưu cấu hình API.");
    } else {
      setLlmModalMsg("Lỗi: " + e.message);
    }
  } finally {
    $("llmSaveBtn").disabled = false;
  }
};

/* ---------- màn hình hẹp ---------- */
function setMobile(which) {
  const layout = $("layout");
  layout.dataset.mobile = which;
  $("mtSources").classList.toggle("on", which === "sources");
  $("mtChat").classList.toggle("on", which === "chat");
  $("mtViewer").classList.toggle("on", which === "viewer");
  if (which === "sources") {
    layout.classList.remove("sources-closed");
    $("btnToggleCol1")?.classList.add("active");
    $("btnRestoreCol1")?.classList.add("hidden");
  }
  if (which === "viewer") {
    layout.classList.remove("viewer-closed");
    $("btnToggleCol3")?.classList.add("active");
    if (!S.viewer && S.docs.length > 0) openSource(firstDocId());
  }
}
$("mtSources").onclick = () => setMobile("sources");
$("mtChat").onclick = () => setMobile("chat");
$("mtViewer").onclick = () => setMobile("viewer");

renderChat();
refreshAuth()
  .then(() => Promise.all([loadStatus(), loadDocs(), refreshLlm()]))
  .catch(e => { $("stat").textContent = "Lỗi nạp: " + e.message; });
