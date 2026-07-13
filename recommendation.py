#!/usr/bin/env python3
"""
CrashLogic / DentScan — Recommendation engine
=============================================
Turns per-part damage findings into an ACTION (repair vs replace) and a cost.

Input findings come from the two-stage CV pipeline:
    parts model    -> which part      (front_bumper_cover, hood, front_door ...)
    damage model   -> damage type     (scratch / dent / crack / glass_shatter /
                                        lamp_broken / tire_flat  — CarDD classes)
    fusion (IoU)   -> severity        (minor / moderate / severe, from mask area)

Decision logic (why this matters): a *scratch* or small *dent* is a paint/PDR
labor job — far cheaper than replacing the panel. Glass cracks, shattered glass,
broken lamps and bent rims need replacement. So the same detection can mean
50 AZN or 800 AZN depending on damage TYPE — which is exactly why the damage
type is worth detecting.

Replacement cost comes from the price CSV (via PriceDB). Repair/labor costs use
a small Baku labor table below (rough estimates — tune with real body-shop rates).
"""

import sys
from car_price_agent import PriceDB, CSV_PATH


# ── damage type normalization (CarDD names -> canonical) ─────────────────
def norm_damage(d: str) -> str:
    d = d.strip().lower().replace("-", " ").replace("_", " ")
    return {
        "scratch": "scratch", "dent": "dent", "crack": "crack",
        "glass shatter": "glass_shatter", "glassshatter": "glass_shatter",
        "lamp broken": "lamp_broken", "broken lamp": "lamp_broken",
        "tire flat": "tire_flat", "flat tire": "tire_flat",
    }.get(d, d.replace(" ", "_"))


# ── part -> physical kind (drives repairability) ─────────────────────────
GLASS = {"front_windshield", "rear_windshield", "front_left_door_window",
         "front_right_door_window", "rear_left_door_window", "rear_right_door_window",
         "rear_quarter_window", "mirror_glass"}
PLASTIC = {"front_bumper_cover", "rear_bumper_cover", "front_grille",
           "rear_spoiler", "mirror_cover", "fuel_filler_door"}


def classify_kind(code: str) -> str:
    if code in GLASS:
        return "glass"
    if any(k in code for k in ("headlight", "taillight", "fog_light")):
        return "lamp"
    if code.endswith("_wheel"):
        return "wheel"
    if code.endswith("_tire"):
        return "tire"
    if code in ("left_side_mirror_assembly", "right_side_mirror_assembly"):
        return "mirror"
    if code in PLASTIC:
        return "plastic_cover"
    if code == "door_handle":
        return "trim"
    return "metal_panel"


# ── labor / repair cost table (AZN, Baku) ────────────────────────────────
# Loaded from repair_prices.csv (same folder or REPAIR_CSV_PATH env var);
# falls back to the built-in defaults below if the CSV is missing.
_DEFAULT_LABOR = {
    "polish":         (20, 40, 70),
    "paint_panel":    (60, 120, 200),
    "pdr":            (30, 70, 120),
    "dent_paint":     (90, 160, 260),
    "plastic_repair": (50, 100, 160),
    "wheel_refinish": (40, 80, 120),
    "tire_patch":     (10, 20, 30),
    "glass_polish":   (25, 45, 80),
}

def _load_labor() -> dict:
    import os, csv as _csv
    path = os.environ.get("REPAIR_CSV_PATH",
                          os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "repair_prices.csv"))
    if not os.path.exists(path):
        return dict(_DEFAULT_LABOR)
    labor = {}
    with open(path, encoding="utf-8") as f:
        for r in _csv.DictReader(f):
            labor[r["action_code"]] = (int(r["price_min_azn"]),
                                       int(r["price_avg_azn"]),
                                       int(r["price_max_azn"]))
    # keep defaults for any action missing from the CSV
    for k, v in _DEFAULT_LABOR.items():
        labor.setdefault(k, v)
    return labor

LABOR = _load_labor()

# Premium cars cost more to repair (paint match, sensors, shop rates).
LABOR_BRAND_FACTOR = {"Mercedes-Benz": 1.4, "BMW": 1.4, "Toyota": 1.1, "Hyundai": 1.0}


# ── the decision rules ───────────────────────────────────────────────────
def decide(kind: str, dtype: str, severity: str) -> tuple[str, str, str]:
    """Return (action_key, action_az, basis)  basis ∈ {'labor','replace'}."""
    # damage types that force replacement regardless of part
    if dtype == "glass_shatter":
        return "replace", "Əvəzləmə (şüşə)", "replace"
    if dtype == "lamp_broken":
        return "replace", "Əvəzləmə (fara/fənər)", "replace"
    if dtype == "tire_flat":
        return ("replace", "Şin əvəzləmə", "replace") if severity == "severe" \
            else ("tire_patch", "Şin təmiri (yamaq)", "labor")

    # part-kind driven
    if kind == "lamp":
        return "replace", "Əvəzləmə (fara/fənər)", "replace"
    if kind == "tire":
        return "replace", "Şin əvəzləmə", "replace"
    if kind == "glass":
        if dtype == "scratch":
            return "polish", "Cilalama", "labor"
        return "replace", "Əvəzləmə (şüşə)", "replace"        # crack on glass → replace
    if kind == "wheel":
        if dtype == "scratch":
            return "wheel_refinish", "Disk bərpası", "labor"
        return "replace", "Disk əvəzləmə", "replace"          # bent / cracked rim
    if kind == "mirror":
        if dtype == "scratch":
            return "paint_panel", "Rəng (güzgü qapağı)", "labor"
        if severity == "severe":
            return "replace", "Güzgü əvəzləmə", "replace"
        return "plastic_repair", "Güzgü təmiri", "labor"

    # generic panels (metal_panel / plastic_cover / trim)
    if dtype == "scratch":
        if severity == "minor":
            return "polish", "Cilalama", "labor"
        return "paint_panel", "Rəng (panel)", "labor"
    if dtype == "dent":
        if kind == "metal_panel":
            if severity == "minor":
                return "pdr", "PDR (rəngsiz düzəltmə)", "labor"
            if severity == "moderate":
                return "dent_paint", "Düzəltmə + rəng", "labor"
            return "replace", "Panel əvəzləmə", "replace"
        # plastic cover
        if severity == "severe":
            return "replace", "Əvəzləmə", "replace"
        return "plastic_repair", "Plastik təmir + rəng", "labor"
    if dtype == "crack":
        if kind == "plastic_cover":
            if severity == "severe":
                return "replace", "Əvəzləmə", "replace"
            return "plastic_repair", "Plastik qaynaq təmiri", "labor"
        return "replace", "Əvəzləmə", "replace"

    return "replace", "Əvəzləmə", "replace"


class RecommendationEngine:
    def __init__(self, db: PriceDB):
        self.db = db

    def recommend(self, brand, model, year, findings: list[dict]) -> dict:
        """findings: [{part_code, damage_type, severity?}, ...]"""
        codes = [f["part_code"] for f in findings]
        priced = self.db.estimate_items(brand, model, year, [(c, 1) for c in codes])
        if not priced.get("found"):
            return priced                                     # resolve error
        repl = {it["part_code"]: it for it in priced["items"]}

        lines = []
        rec_min = rec_avg = rec_max = 0
        repl_all_avg = 0
        for f in findings:
            code = f["part_code"]
            dtype = norm_damage(f.get("damage_type", ""))
            sev = (f.get("severity") or "moderate").lower()
            kind = classify_kind(code)
            action, action_az, basis = decide(kind, dtype, sev)

            r = repl.get(code)
            replace_cost = (r["avg"] if r else None)
            if replace_cost is not None:
                repl_all_avg += replace_cost

            if basis == "replace":
                if not r:                                     # part not in CSV
                    lines.append({"part_code": code, "damage": dtype, "severity": sev,
                                  "action": action_az, "basis": basis,
                                  "cost_avg": None, "note": "qiymət bazada yoxdur"})
                    continue
                cmin, cavg, cmax = r["min"], r["avg"], r["max"]
            else:
                factor = LABOR_BRAND_FACTOR.get(priced["vehicle"]["brand"], 1.0)
                lmin, lavg, lmax = LABOR[action]
                cmin = int(round(lmin * factor))
                cavg = int(round(lavg * factor))
                cmax = int(round(lmax * factor))

            rec_min += cmin; rec_avg += cavg; rec_max += cmax
            lines.append({
                "part_code": code,
                "part_az": (r["part_az"] if r else code),
                "damage": dtype, "severity": sev,
                "kind": kind, "action": action_az, "basis": basis,
                "cost_min": cmin, "cost_avg": cavg, "cost_max": cmax,
                "replace_cost_avg": replace_cost,
            })

        return {
            "found": True, "vehicle": priced["vehicle"],
            "lines": lines,
            "recommended_total": {"min": rec_min, "avg": rec_avg, "max": rec_max},
            "replace_all_total_avg": repl_all_avg,
            "savings_avg": repl_all_avg - rec_avg,
            "currency": "AZN", "price_type": "estimate",
        }


def format_report(res: dict) -> str:
    if not res.get("found"):
        return "❌ " + res.get("reason", "Tapılmadı.")
    v = res["vehicle"]
    out = [f"🚗 {v['brand']} {v['model']} — {v['generation']} ({v['year_range']}), {v['body_type']}", ""]
    for ln in res["lines"]:
        tag = "🔁" if ln["basis"] == "replace" else "🔧"
        cost = f"{ln.get('cost_avg')} AZN ({ln.get('cost_min')}–{ln.get('cost_max')})" \
            if ln.get("cost_avg") is not None else ln.get("note", "—")
        cmp = ""
        if ln["basis"] == "labor" and ln.get("replace_cost_avg"):
            cmp = f"   [əvəzləmə olsaydı ~{ln['replace_cost_avg']}]"
        out.append(f"  {tag} {ln.get('part_az', ln['part_code'])} — "
                   f"{ln['damage']}/{ln['severity']} → {ln['action']}: {cost}{cmp}")
    t = res["recommended_total"]
    out += ["", f"💰 TÖVSİYƏ OLUNAN CƏMİ (orta): {t['avg']} AZN  (diapazon {t['min']}–{t['max']})",
            f"   (hamısını əvəzləsək: ~{res['replace_all_total_avg']} AZN → "
            f"qənaət ~{res['savings_avg']} AZN)"]
    out.append("\nℹ️  Təmir/labor qiymətləri Bakı üçün təxmini; real servis dərəcələri ilə tənzimlənməlidir.")
    return "\n".join(out)


# ── offline demo (mock findings) ─────────────────────────────────────────
def _demo(db: PriceDB):
    eng = RecommendationEngine(db)
    print("Recommendation engine demo (mock findings)\n" + "-" * 48)

    findings = [
        {"part_code": "front_bumper_cover", "damage_type": "scratch", "severity": "minor"},
        {"part_code": "hood",               "damage_type": "dent",    "severity": "moderate"},
        {"part_code": "front_left_fender",  "damage_type": "dent",    "severity": "severe"},
        {"part_code": "front_windshield",   "damage_type": "crack",   "severity": "moderate"},
        {"part_code": "left_headlight",     "damage_type": "lamp_broken"},
    ]
    print("\nMercedes E-Class 2018:")
    print(format_report(eng.recommend("mercedes", "e class", 2018, findings)))


def main():
    import os
    if not os.path.exists(CSV_PATH):
        sys.exit(f"CSV tapılmadı: {CSV_PATH}")
    _demo(PriceDB(CSV_PATH))


if __name__ == "__main__":
    main()
