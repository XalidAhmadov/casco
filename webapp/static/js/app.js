/* CrashLogic — app pages (upload / dashboard / chat) frontend logic */

// ── i18n ──────────────────────────────────────────────────────────────
const I18N = {
  az: {
    tagline: "zədə analizi və qiymət təxmini",
    nav_analyze: "Zədə analizi",
    nav_chat: "Qiymət çatı",

    page_title: "Zədə analizi",
    step1: "Şəkil yüklə",
    upload_h2: "Zədənin şəklini bura sürükləyin və ya seçin",
    upload_format: "PNG və ya JPG, 50 MB-a qədər",
    upload_btn: "Şəkil yüklə",
    upload_note: "Şəkillər yaxşı işıqlandırılmış və zədə aydın görünən olmalıdır.",
    brand: "Marka", model: "Model", year: "İl",
    analyze: "Analiz et", analyzing: "Analiz edilir…",

    page_title2: "Zədə icmalı",
    step2: "Zədə icmalı",
    results_empty: "Hələ analiz aparılmayıb. Şəkil yükləyin və avtomobili seçin.",
    go_upload: "Şəkil yüklə",
    damage_info: "Zədə məlumatı",
    photos_title: "Yüklənmiş şəkillər",
    findings_title: "Aşkarlanan zədələr",
    no_damage: "Şəkildə qiymətləndirilə bilən zədə tapılmadı.",
    uploaded_photos: "Yüklənmiş şəkillər",
    new_analysis: "Yeni analiz",
    tile_total: "Tövsiyə olunan cəm (orta)",
    tile_range: "Diapazon",
    tile_parts: "Zədəli hissə",
    tile_new: "Yeni analiz",
    parts_all: "Ümumi",
    orphans: "Hissəyə bağlanmayan zədələr",
    replace_was: "əvəzləmə olsaydı",
    price_missing: "qiymət bazada yoxdur",

    page_title3: "Qiymət çatı",
    chat_welcome: "Salam! Avtomobil hissələrinin qiymətini soruşa bilərsiniz.\nNümunə: mercedes e class 2018 qabaq bumper və arxa bumper",
    chat_placeholder: "Sualınızı yazın…",
    send: "Göndər",
    disclaimer: "ℹ️ Qiymətlər təxminidir (Bakı bazarı, analoq/işlənmiş hissələr).",

    sev: { minor: "yüngül", moderate: "orta", severe: "ağır" },
    dmg: {
      scratch: "cızıq", dent: "əzik", crack: "çat",
      glass_shatter: "şüşə qırılması", lamp_broken: "fara sınığı", tire_flat: "deşik şin",
    },
  },
  en: {
    tagline: "damage analysis & price estimation",
    nav_analyze: "Damage analysis",
    nav_chat: "Price chat",

    page_title: "Damage analysis",
    step1: "Upload photo",
    upload_h2: "Drag and drop damage photos here, or pick files",
    upload_format: "PNG or JPG up to 50 MB",
    upload_btn: "Upload photos",
    upload_note: "Photos should be taken under good lighting, with damage clearly visible.",
    brand: "Brand", model: "Model", year: "Year",
    analyze: "Analyze", analyzing: "Analyzing…",

    page_title2: "Damage survey",
    step2: "Damage survey",
    results_empty: "No analysis yet. Upload a photo and pick the vehicle.",
    go_upload: "Upload photo",
    damage_info: "Damage information",
    photos_title: "Uploaded photos",
    findings_title: "Detected damage",
    no_damage: "No assessable damage found in the image.",
    uploaded_photos: "Uploaded photos",
    new_analysis: "New analysis",
    tile_total: "Recommended total (avg)",
    tile_range: "Range",
    tile_parts: "Damaged parts",
    tile_new: "New analysis",
    parts_all: "Overview",
    orphans: "Damage not matched to a part",
    replace_was: "if replaced",
    price_missing: "price not in database",

    page_title3: "Price chat",
    chat_welcome: "Hi! Ask me about car part prices.\nExample: mercedes e class 2018 front bumper and rear bumper",
    chat_placeholder: "Type your question…",
    send: "Send",
    disclaimer: "ℹ️ Prices are estimates (Baku market, aftermarket/used parts).",

    sev: { minor: "minor", moderate: "moderate", severe: "severe" },
    dmg: {
      scratch: "scratch", dent: "dent", crack: "crack",
      glass_shatter: "glass shatter", lamp_broken: "broken lamp", tire_flat: "flat tire",
    },
  },
};

// backend action strings are Azerbaijani; map them for EN mode
const ACTION_EN = {
  "Cilalama": "Polish",
  "Rəng (panel)": "Repaint panel",
  "Rəng (güzgü qapağı)": "Repaint (mirror cover)",
  "PDR (rəngsiz düzəltmə)": "Paintless dent repair",
  "Düzəltmə + rəng": "Dent repair + repaint",
  "Plastik təmir + rəng": "Plastic repair + paint",
  "Plastik qaynaq təmiri": "Plastic weld repair",
  "Disk bərpası": "Rim refinish",
  "Disk əvəzləmə": "Wheel replacement",
  "Şin təmiri (yamaq)": "Tire patch",
  "Şin əvəzləmə": "Tire replacement",
  "Güzgü təmiri": "Mirror repair",
  "Güzgü əvəzləmə": "Mirror replacement",
  "Panel əvəzləmə": "Panel replacement",
  "Əvəzləmə": "Replacement",
  "Əvəzləmə (şüşə)": "Replacement (glass)",
  "Əvəzləmə (fara/fənər)": "Replacement (lamp)",
};

let lang = localStorage.getItem("cl_lang") || "az";
const t = (key) => I18N[lang][key] ?? key;

function applyI18n() {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => {
    el.placeholder = t(el.dataset.i18nPh);
  });
  document.querySelectorAll(".lang-toggle button").forEach((b) =>
    b.classList.toggle("active", b.dataset.lang === lang));
  if (typeof lastReport !== "undefined" && lastReport) renderReport(lastReport);
}

document.querySelectorAll(".lang-toggle button").forEach((b) =>
  b.addEventListener("click", () => {
    lang = b.dataset.lang;
    localStorage.setItem("cl_lang", lang);
    applyI18n();
  }));

// ── catalog / vehicle dropdowns (upload page) ──────────────────────────
const selBrand = document.getElementById("sel-brand");
const selModel = document.getElementById("sel-model");
const selYear = document.getElementById("sel-year");
let catalog = {};

if (selBrand) {
  const fillSelect = (sel, values) => {
    sel.innerHTML = "";
    values.forEach((v) => {
      const o = document.createElement("option");
      o.value = v; o.textContent = v;
      sel.appendChild(o);
    });
  };

  const refreshYears = () => {
    const gens = (catalog[selBrand.value] || {})[selModel.value] || [];
    const years = new Set();
    const now = new Date().getFullYear();
    gens.forEach((g) => {
      const to = g.year_to === 9999 ? now : g.year_to;
      for (let y = g.year_from; y <= to; y++) years.add(y);
    });
    fillSelect(selYear, [...years].sort((a, b) => b - a));
  };

  const refreshModels = () => {
    fillSelect(selModel, Object.keys(catalog[selBrand.value] || {}));
    refreshYears();
  };

  selBrand.addEventListener("change", refreshModels);
  selModel.addEventListener("change", refreshYears);

  fetch("/api/catalog")
    .then((r) => r.json())
    .then((c) => {
      catalog = c;
      fillSelect(selBrand, Object.keys(c));
      refreshModels();
    });
}

// ── image dropzone (upload page, keeps real File objects) ─────────────
const dropzone = document.getElementById("dropzone");
let imageFiles = [];

if (dropzone) {
  const input = document.getElementById("file-input");
  const btn = document.getElementById("upload-btn");
  const strip = document.getElementById("upload-strip");
  const btnAnalyze = document.getElementById("btn-analyze");
  const MAX_THUMBS = 8;

  const renderThumbs = () => {
    strip.innerHTML = "";
    imageFiles.slice(0, MAX_THUMBS).forEach((file) => {
      const cell = document.createElement("div");
      cell.className = "u-thumb";
      const img = document.createElement("img");
      img.alt = file.name;
      img.src = URL.createObjectURL(file);
      img.onload = () => URL.revokeObjectURL(img.src);
      cell.appendChild(img);
      strip.appendChild(cell);
    });
    if (btnAnalyze) btnAnalyze.disabled = imageFiles.length === 0;
  };

  const addFiles = (fileList) => {
    imageFiles.push(...[...fileList].filter((f) => f.type.startsWith("image/")));
    renderThumbs();
  };

  btn.addEventListener("click", () => input.click());
  input.addEventListener("change", () => {
    addFiles(input.files);
    input.value = "";
  });
  ["dragenter", "dragover"].forEach((ev) =>
    dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach((ev) =>
    dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove("dragover"); }));
  dropzone.addEventListener("drop", (e) => addFiles(e.dataTransfer.files));
}

// ── analyze (upload page) ──────────────────────────────────────────────
const vehicleForm = document.getElementById("vehicle-form");

if (vehicleForm) {
  const btnAnalyze = document.getElementById("btn-analyze");
  const errBox = document.getElementById("analyze-error");

  vehicleForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!imageFiles.length) return;
    errBox.hidden = true;
    btnAnalyze.disabled = true;
    btnAnalyze.querySelector(".spinner").hidden = false;
    btnAnalyze.querySelector("[data-i18n]").textContent = t("analyzing");

    const fd = new FormData();
    imageFiles.forEach((f) => fd.append("images", f));
    fd.append("brand", selBrand.value);
    fd.append("model", selModel.value);
    fd.append("year", selYear.value);

    try {
      const r = await fetch("/api/analyze", { method: "POST", body: fd });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || r.statusText);
      sessionStorage.setItem("cl_report", JSON.stringify(data));
      window.location.href = "dashboard.html";
    } catch (err) {
      errBox.textContent = "⚠ " + err.message;
      errBox.hidden = false;
      btnAnalyze.disabled = false;
      btnAnalyze.querySelector(".spinner").hidden = true;
      btnAnalyze.querySelector("[data-i18n]").textContent = t("analyze");
    }
  });
}

// ── dashboard rendering ─────────────────────────────────────────────────
const reportEl = document.getElementById("report");
let lastReport = null;
let partFilter = null;

const fmtDamage = (d) => I18N[lang].dmg[(d || "").toLowerCase()] || d;
const fmtPart = (line) =>
  lang === "az" ? (line.part_az || line.part_code)
                : (line.part_code || "").replace(/_/g, " ");
const fmtAction = (az) => (lang === "en" ? ACTION_EN[az] || az : az);

function renderReport(res) {
  document.getElementById("empty-state").hidden = true;
  reportEl.hidden = false;

  const v = res.vehicle || {};
  document.getElementById("vehicle-title").textContent =
    `🚗 ${v.brand || "?"} ${v.model || ""}`;
  document.getElementById("vehicle-sub").textContent =
    `${v.generation || ""} · ${v.year_range || v.year || ""} · ${v.body_type || ""}`;

  const lines = res.lines || [];
  const tot = res.recommended_total || { min: 0, avg: 0, max: 0 };
  const distinctParts = [...new Set(lines.map((l) => l.part_code))];

  // info tiles
  const tiles = document.getElementById("info-tiles");
  tiles.innerHTML = `
    <div class="tile primary">
      <div class="t-val">${tot.avg}<small> AZN</small></div>
      <div class="t-label">${t("tile_total")}</div>
    </div>
    <div class="tile">
      <div class="t-val">${tot.min}–${tot.max}</div>
      <div class="t-label">${t("tile_range")} (AZN)</div>
    </div>
    <div class="tile">
      <div class="t-val">${distinctParts.length}</div>
      <div class="t-label">${t("tile_parts")}</div>
    </div>
    <a class="tile map" href="upload.html">
      ${t("tile_new")}
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12"/></svg>
    </a>`;

  // parts nav (filter chips)
  const nav = document.getElementById("parts-nav");
  const partCounts = {};
  lines.forEach((l) => { partCounts[l.part_code] = (partCounts[l.part_code] || 0) + 1; });
  nav.innerHTML = "";
  const allLink = document.createElement("a");
  allLink.href = "#";
  allLink.className = partFilter === null ? "active" : "";
  allLink.textContent = t("parts_all");
  allLink.addEventListener("click", (e) => { e.preventDefault(); partFilter = null; renderReport(res); });
  nav.appendChild(allLink);
  distinctParts.forEach((code) => {
    const line = lines.find((l) => l.part_code === code);
    const a = document.createElement("a");
    a.href = "#";
    a.className = partFilter === code ? "active" : "";
    const label = document.createElement("span");
    label.textContent = fmtPart(line);
    const badge = document.createElement("span");
    badge.className = "badge-count";
    badge.textContent = partCounts[code];
    a.append(label, badge);
    a.addEventListener("click", (e) => { e.preventDefault(); partFilter = code; renderReport(res); });
    nav.appendChild(a);
  });

  // photo gallery (viewer) + right-panel thumbnails
  const photos = res.per_image && res.per_image.length
    ? res.per_image
    : (res.source_url || res.annotated_url) ? [{ annotated_url: res.annotated_url, source_url: res.source_url }] : [];

  const gallery = document.getElementById("gallery");
  gallery.innerHTML = "";
  photos.forEach((p) => {
    const src = p.annotated_url || p.source_url;
    if (!src) return;
    const img = document.createElement("img");
    img.src = src;
    gallery.appendChild(img);
  });

  const photoGrid = document.getElementById("photo-grid");
  const photoCount = document.getElementById("photo-count");
  photoGrid.innerHTML = "";
  photoCount.textContent = photos.length;
  photos.forEach((p) => {
    const cell = document.createElement("a");
    cell.className = "photo-cell";
    cell.href = p.annotated_url || p.source_url || "#";
    cell.target = "_blank";
    cell.style.background = "none";
    const img = document.createElement("img");
    img.src = p.source_url || p.annotated_url;
    img.style.width = "100%"; img.style.height = "100%"; img.style.objectFit = "cover";
    cell.appendChild(img);
    photoGrid.appendChild(cell);
  });

  // findings list
  const box = document.getElementById("findings-list");
  box.innerHTML = "";
  const visibleLines = partFilter ? lines.filter((l) => l.part_code === partFilter) : lines;
  document.getElementById("no-damage").hidden = lines.length > 0;

  visibleLines.forEach((ln) => {
    const row = document.createElement("div");
    row.className = "part-row";
    const sev = (ln.severity || "moderate").toLowerCase();
    const costHtml = ln.cost_avg != null
      ? `<div class="p-cost">${ln.cost_avg} AZN <small>${ln.cost_min}–${ln.cost_max}</small></div>
         ${ln.basis !== "replace" && ln.replace_cost_avg
            ? `<div class="p-sub">${t("replace_was")}: ~${ln.replace_cost_avg} AZN</div>` : ""}`
      : `<div class="p-cost">${t("price_missing")}</div>`;

    row.innerHTML = `
      <div class="part-info">
        <h4>${fmtPart(ln)}</h4>
        <div class="p-sub">${fmtDamage(ln.damage)} · <span class="badge ${sev}">${I18N[lang].sev[sev] || sev}</span></div>
        ${costHtml}
      </div>
      <div class="part-actions">
        <span class="action-tag ${ln.basis === "replace" ? "replace" : ""}">
          ${ln.basis === "replace" ? "🔁" : "🔧"} ${fmtAction(ln.action)}
        </span>
      </div>`;
    box.appendChild(row);
  });

  const orphans = res.orphans || [];
  const orphanEl = document.getElementById("orphans");
  orphanEl.hidden = orphans.length === 0;
  if (orphans.length) {
    orphanEl.textContent = `⚠ ${t("orphans")}: ` + orphans.map((o) => fmtDamage(o.damage_type)).join(", ");
  }
}

if (reportEl) {
  const raw = sessionStorage.getItem("cl_report");
  if (raw) {
    try {
      lastReport = JSON.parse(raw);
      renderReport(lastReport);
    } catch (e) { /* corrupt/empty — fall through to empty state */ }
  }
}

// ── chat ──────────────────────────────────────────────────────────────
const chatForm = document.getElementById("chat-form");

if (chatForm) {
  const sessionId = (crypto.randomUUID && crypto.randomUUID()) || String(Math.random()).slice(2);
  const chatLog = document.getElementById("chat-log");
  const chatText = document.getElementById("chat-text");

  const addMsg = (text, cls) => {
    const div = document.createElement("div");
    div.className = "msg " + cls;
    div.textContent = text;
    chatLog.appendChild(div);
    chatLog.scrollTop = chatLog.scrollHeight;
    return div;
  };

  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = chatText.value.trim();
    if (!msg) return;
    chatText.value = "";
    addMsg(msg, "user");
    const typing = addMsg("…", "agent typing");
    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: msg, lang }),
      });
      const data = await r.json();
      typing.remove();
      if (!r.ok) throw new Error(data.detail || r.statusText);
      addMsg(data.reply, "agent");
    } catch (err) {
      typing.remove();
      addMsg("⚠ " + err.message, "agent err");
    }
    chatLog.scrollTop = chatLog.scrollHeight;
  });
}

applyI18n();
