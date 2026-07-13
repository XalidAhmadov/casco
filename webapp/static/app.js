/* CrashLogic — frontend logic (vanilla JS, no build step) */

// ── i18n ──────────────────────────────────────────────────────────────
const I18N = {
  az: {
    tagline: "zədə analizi və qiymət təxmini",
    tab_analyze: "Zədə analizi",
    tab_chat: "Qiymət çatı",
    upload_title: "Avtomobil məlumatları",
    drop_hint: "Şəkli bura atın və ya klikləyin",
    brand: "Marka",
    model: "Model",
    year: "İl",
    analyze: "Analiz et",
    analyzing: "Analiz edilir…",
    disclaimer: "ℹ️ Qiymətlər təxminidir (Bakı bazarı, analoq/işlənmiş hissələr).",
    results_empty: "Şəkil yükləyin, avtomobili seçin və analizə başlayın.",
    findings_title: "Aşkarlanan zədələr",
    no_damage: "Şəkildə qiymətləndirilə bilən zədə tapılmadı.",
    total_label: "Tövsiyə olunan cəmi (orta)",
    range: "Diapazon",
    replace_all: "Hamısını əvəzləsək",
    savings: "Qənaət",
    orphans: "Hissəyə bağlanmayan zədələr",
    replace_was: "əvəzləmə olsaydı",
    chat_welcome: "Salam! Avtomobil hissələrinin qiymətini soruşa bilərsiniz.\nNümunə: mercedes e class 2018 qabaq bumper və arxa bumper",
    chat_placeholder: "Sualınızı yazın…",
    send: "Göndər",
    price_missing: "qiymət bazada yoxdur",
    sev: { minor: "yüngül", moderate: "orta", severe: "ağır" },
    dmg: {
      scratch: "cızıq", dent: "əzik", crack: "çat",
      glass_shatter: "şüşə qırılması", lamp_broken: "fara sınığı", tire_flat: "deşik şin",
    },
  },
  en: {
    tagline: "damage analysis & price estimation",
    tab_analyze: "Damage analysis",
    tab_chat: "Price chat",
    upload_title: "Vehicle details",
    drop_hint: "Drop an image here or click",
    brand: "Brand",
    model: "Model",
    year: "Year",
    analyze: "Analyze",
    analyzing: "Analyzing…",
    disclaimer: "ℹ️ Prices are estimates (Baku market, aftermarket/used parts).",
    results_empty: "Upload a photo, pick the vehicle and start the analysis.",
    findings_title: "Detected damage",
    no_damage: "No assessable damage found in the image.",
    total_label: "Recommended total (avg)",
    range: "Range",
    replace_all: "If replacing everything",
    savings: "Savings",
    orphans: "Damage not matched to a part",
    replace_was: "if replaced",
    chat_welcome: "Hi! Ask me about car part prices.\nExample: mercedes e class 2018 front bumper and rear bumper",
    chat_placeholder: "Type your question…",
    send: "Send",
    price_missing: "price not in database",
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
  document.querySelectorAll(".lang").forEach((b) =>
    b.classList.toggle("active", b.dataset.lang === lang));
  if (lastReport) renderReport(lastReport);   // re-render results in new language
}

document.querySelectorAll(".lang").forEach((b) =>
  b.addEventListener("click", () => {
    lang = b.dataset.lang;
    localStorage.setItem("cl_lang", lang);
    applyI18n();
  }));

// ── tabs ──────────────────────────────────────────────────────────────
document.querySelectorAll(".tab").forEach((b) =>
  b.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === b));
    document.querySelectorAll(".panel").forEach((p) =>
      p.classList.toggle("active", p.id === "panel-" + b.dataset.tab));
  }));

// ── catalog / dropdowns ───────────────────────────────────────────────
let catalog = {};
const selBrand = document.getElementById("sel-brand");
const selModel = document.getElementById("sel-model");
const selYear = document.getElementById("sel-year");

function fillSelect(sel, values) {
  sel.innerHTML = "";
  values.forEach((v) => {
    const o = document.createElement("option");
    o.value = v; o.textContent = v;
    sel.appendChild(o);
  });
}

function refreshModels() {
  fillSelect(selModel, Object.keys(catalog[selBrand.value] || {}));
  refreshYears();
}

function refreshYears() {
  const gens = (catalog[selBrand.value] || {})[selModel.value] || [];
  const years = new Set();
  const now = new Date().getFullYear();
  gens.forEach((g) => {
    const to = g.year_to === 9999 ? now : g.year_to;
    for (let y = g.year_from; y <= to; y++) years.add(y);
  });
  fillSelect(selYear, [...years].sort((a, b) => b - a));
}

selBrand.addEventListener("change", refreshModels);
selModel.addEventListener("change", refreshYears);

fetch("/api/catalog")
  .then((r) => r.json())
  .then((c) => {
    catalog = c;
    fillSelect(selBrand, Object.keys(c));
    refreshModels();
  });

// ── image upload ──────────────────────────────────────────────────────
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const preview = document.getElementById("preview");
const dropHint = document.getElementById("drop-hint");
const btnAnalyze = document.getElementById("btn-analyze");
let imageFile = null;

function setImage(file) {
  if (!file || !file.type.startsWith("image/")) return;
  imageFile = file;
  preview.src = URL.createObjectURL(file);
  preview.hidden = false;
  dropHint.hidden = true;
  btnAnalyze.disabled = false;
}

dropzone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => setImage(fileInput.files[0]));
["dragover", "dragenter"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("dragover"); }));
["dragleave", "drop"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove("dragover"); }));
dropzone.addEventListener("drop", (e) => setImage(e.dataTransfer.files[0]));

// ── analyze ───────────────────────────────────────────────────────────
const errBox = document.getElementById("analyze-error");
let lastReport = null;

btnAnalyze.addEventListener("click", async () => {
  if (!imageFile) return;
  errBox.hidden = true;
  btnAnalyze.disabled = true;
  btnAnalyze.querySelector(".spinner").hidden = false;
  btnAnalyze.querySelector("[data-i18n]").textContent = t("analyzing");

  const fd = new FormData();
  fd.append("image", imageFile);
  fd.append("brand", selBrand.value);
  fd.append("model", selModel.value);
  fd.append("year", selYear.value);

  try {
    const r = await fetch("/api/analyze", { method: "POST", body: fd });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || r.statusText);
    lastReport = data;
    renderReport(data);
  } catch (e) {
    errBox.textContent = "⚠ " + e.message;
    errBox.hidden = false;
  } finally {
    btnAnalyze.disabled = false;
    btnAnalyze.querySelector(".spinner").hidden = true;
    btnAnalyze.querySelector("[data-i18n]").textContent = t("analyze");
  }
});

const fmtDamage = (d) => I18N[lang].dmg[(d || "").toLowerCase()] || d;
const fmtPart = (line) =>
  lang === "az" ? (line.part_az || line.part_code)
                : (line.part_code || "").replace(/_/g, " ");
const fmtAction = (az) => (lang === "en" ? ACTION_EN[az] || az : az);

function renderReport(res) {
  document.getElementById("results-empty").hidden = true;
  document.getElementById("results").hidden = false;

  const v = res.vehicle || {};
  document.getElementById("vehicle-title").textContent =
    `🚗 ${v.brand || "?"} ${v.model || ""} — ${v.generation || ""} (${v.year_range || v.year || ""})`;

  const img = document.getElementById("annotated-img");
  img.src = res.annotated_url || res.source_url || "";

  const box = document.getElementById("findings");
  box.innerHTML = "";
  const lines = res.lines || [];
  document.getElementById("no-damage").hidden = lines.length > 0;
  document.getElementById("totals-card").hidden = lines.length === 0;

  lines.forEach((ln) => {
    const div = document.createElement("div");
    div.className = "finding";

    const main = document.createElement("div");
    main.className = "finding-main";
    const sev = (ln.severity || "moderate").toLowerCase();
    main.innerHTML = `
      <div class="finding-part">${fmtPart(ln)}</div>
      <div class="finding-sub">
        ${fmtDamage(ln.damage)}
        <span class="badge ${sev}">${I18N[lang].sev[sev] || sev}</span>
      </div>
      <span class="action-tag ${ln.basis === "replace" ? "replace" : "labor"}">
        ${ln.basis === "replace" ? "🔁" : "🔧"} ${fmtAction(ln.action)}
      </span>`;

    const cost = document.createElement("div");
    cost.className = "finding-cost";
    if (ln.cost_avg != null) {
      cost.innerHTML = `<span class="avg">${ln.cost_avg} AZN</span>
        <span class="rng">${ln.cost_min}–${ln.cost_max}</span>`;
      if (ln.basis !== "replace" && ln.replace_cost_avg) {
        cost.innerHTML += `<span class="was">${t("replace_was")}: ~${ln.replace_cost_avg}</span>`;
      }
    } else {
      cost.innerHTML = `<span class="rng">${t("price_missing")}</span>`;
    }

    div.append(main, cost);
    box.appendChild(div);
  });

  const orphans = res.orphans || [];
  const orphanEl = document.getElementById("orphans");
  orphanEl.hidden = orphans.length === 0;
  if (orphans.length) {
    orphanEl.textContent = `⚠ ${t("orphans")}: ` +
      orphans.map((o) => fmtDamage(o.damage_type)).join(", ");
  }

  const tot = res.recommended_total;
  if (tot) {
    document.getElementById("total-avg").textContent = tot.avg;
    document.getElementById("total-range").textContent = `${tot.min}–${tot.max}`;
    document.getElementById("replace-all").textContent = res.replace_all_total_avg ?? "—";
    document.getElementById("savings").textContent = res.savings_avg ?? "—";
  }
}

// ── chat ──────────────────────────────────────────────────────────────
const sessionId = (crypto.randomUUID && crypto.randomUUID()) || String(Math.random()).slice(2);
const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatText = document.getElementById("chat-text");

function addMsg(text, cls) {
  const div = document.createElement("div");
  div.className = "msg " + cls;
  div.textContent = text;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
  return div;
}

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

applyI18n();
