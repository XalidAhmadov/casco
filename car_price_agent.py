#!/usr/bin/env python3
"""
CrashLogic / DentScan — Car Parts Price Agent
=============================================
Natural-language -> part price estimator for the Azerbaijani market.

The user types a request in plain (Azerbaijani/mixed) language, e.g.:
    "mercedes e class 2018 qabaq bumper və arxa bumper"
Gemini 2.5 Flash maps the request to canonical part codes and calls a
deterministic tool that looks the prices up in car_parts_prices.csv and
computes the total. All arithmetic happens in Python — the LLM never
invents prices or does the math.

Later, a car-part detection model can feed detected part codes straight
into `PriceDB.estimate(...)` — the same core the agent uses.

Run:
    pip install google-genai python-dotenv
    # .env faylına yaz:  GEMINI_API_KEY=...   (istəyə görə  CSV_PATH=...)
    python car_price_agent.py                 # chat
    python car_price_agent.py --test          # offline DB check (no API)
"""

import os
import re
import sys
import csv
import json
from collections import defaultdict

# Load variables from a local .env file (GEMINI_API_KEY, optional CSV_PATH, ...)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # pip install python-dotenv  (or export the vars manually)

CSV_PATH = os.environ.get("CSV_PATH", "car_parts_prices.csv")
MODEL_NAME = "gemini-2.5-flash"

# ─────────────────────────────────────────────────────────────────────────
#  Normalization helpers
# ─────────────────────────────────────────────────────────────────────────
def _alnum(s: str) -> str:
    """lowercase + strip everything non-alphanumeric (handles ə, ç, ş, etc.)"""
    return re.sub(r"[^a-z0-9]", "", s.lower())

BRAND_ALIASES = {
    "mercedes": "Mercedes-Benz", "mercedesbenz": "Mercedes-Benz",
    "benz": "Mercedes-Benz", "mers": "Mercedes-Benz", "mercedez": "Mercedes-Benz",
    "bmw": "BMW",
    "toyota": "Toyota", "tayota": "Toyota",
    "hyundai": "Hyundai", "hunday": "Hyundai", "hyunday": "Hyundai",
}

MODEL_ALIASES = {
    "eclass": "E-Class", "cclass": "C-Class", "sclass": "S-Class",
    "3series": "3 Series", "3seriya": "3 Series", "3ser": "3 Series", "seria3": "3 Series",
    "5series": "5 Series", "5seriya": "5 Series", "5ser": "5 Series", "seria5": "5 Series",
    "7series": "7 Series", "7seriya": "7 Series", "7ser": "7 Series", "seria7": "7 Series",
    "camry": "Camry", "kamri": "Camry", "kamry": "Camry",
    "corolla": "Corolla", "karolla": "Corolla",
    "prado": "Land Cruiser Prado", "landcruiserprado": "Land Cruiser Prado",
    "lcprado": "Land Cruiser Prado", "landprado": "Land Cruiser Prado",
    "accent": "Accent", "aksent": "Accent",
    "elantra": "Elantra", "elantara": "Elantra",
    "sonata": "Sonata", "sonota": "Sonata",
}

# Colloquial part terms -> canonical code (code-side safety net; Gemini is
# the primary resolver via the catalog injected into the system prompt).
PART_SYNONYMS = {
    "qabaqbumper": "front_bumper_cover", "onbumper": "front_bumper_cover",
    "onbamper": "front_bumper_cover", "qabaqbufer": "front_bumper_cover",
    "onbufer": "front_bumper_cover", "frontbumper": "front_bumper_cover",
    "arxabumper": "rear_bumper_cover", "arxabamper": "rear_bumper_cover",
    "arxabufer": "rear_bumper_cover", "rearbumper": "rear_bumper_cover",
    "kapot": "hood", "kaput": "hood", "hood": "hood",
    "solfara": "left_headlight", "solonfara": "left_headlight",
    "sagfara": "right_headlight", "sagonfara": "right_headlight",
    "solstop": "left_taillight", "sagstop": "right_taillight",
    "solduman": "left_fog_light", "sagduman": "right_fog_light",
    "barmaqliq": "front_grille", "radiatorbarmaqligi": "front_grille", "setka": "front_grille",
    "baqajqapagi": "trunk_lid", "baqaj": "trunk_lid",
    "tavan": "roof_panel",
    "onsuse": "front_windshield", "onsise": "front_windshield",
    "arxasuse": "rear_windshield",
    "yanetek": "rocker_panel", "astana": "rocker_panel",
    "yanacaqqapagi": "fuel_filler_door", "qapitutacagi": "door_handle",
}


def normalize_brand(text: str) -> str | None:
    key = _alnum(text)
    if key in BRAND_ALIASES:
        return BRAND_ALIASES[key]
    for alias, canon in BRAND_ALIASES.items():
        if alias in key:
            return canon
    return None


def normalize_model(text: str, brand: str | None, known_models: set[str]) -> str | None:
    key = _alnum(text)
    if key in MODEL_ALIASES:
        return MODEL_ALIASES[key]
    # direct match against known canonical models
    for m in known_models:
        if _alnum(m) == key or _alnum(m) in key or key in _alnum(m):
            return m
    for alias, canon in MODEL_ALIASES.items():
        if alias in key and (brand is None or canon in known_models):
            return canon
    return None


# ─────────────────────────────────────────────────────────────────────────
#  Price database
# ─────────────────────────────────────────────────────────────────────────
class PriceDB:
    def __init__(self, path: str):
        self.rows = []
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                r["year_from"] = int(r["year_from"])
                r["year_to"] = int(r["year_to"])
                for k in ("price_min_azn", "price_avg_azn", "price_max_azn"):
                    r[k] = int(r[k])
                self.rows.append(r)

        self.parts = {}                      # code -> {en, az, category}
        self.models = defaultdict(set)       # brand -> {model}
        for r in self.rows:
            self.parts.setdefault(r["part_code"], {
                "en": r["part_name_en"], "az": r["part_name_az"], "category": r["category"],
            })
            self.models[r["brand"]].add(r["model"])

    # ----- part-code resolution (fallback for non-canonical input) --------
    def resolve_part_code(self, query: str) -> str | None:
        if query in self.parts:
            return query
        key = _alnum(query)
        # exact alnum against code
        for code in self.parts:
            if _alnum(code) == key:
                return code
        if key in PART_SYNONYMS:
            return PART_SYNONYMS[key]
        # token-subset match against az / en names
        qtok = set(re.split(r"\s+", query.lower().strip()))
        best, best_score = None, 0
        for code, meta in self.parts.items():
            for name in (meta["az"], meta["en"], code.replace("_", " ")):
                ntok = set(re.split(r"[\s_]+", name.lower()))
                score = len(qtok & ntok)
                if score > best_score:
                    best, best_score = code, score
        return best if best_score > 0 else None

    # ----- shared vehicle resolver ----------------------------------------
    def _resolve(self, brand, model, year):
        """Returns (brand, model, gen_rows, error). error is None on success."""
        b = normalize_brand(brand)
        if not b or b not in self.models:
            return None, None, None, {"found": False,
                    "reason": f"Marka tapılmadı: '{brand}'.",
                    "available_brands": sorted(self.models)}
        m = normalize_model(model, b, self.models[b])
        if not m:
            return None, None, None, {"found": False,
                    "reason": f"'{brand}' üçün model tapılmadı: '{model}'.",
                    "available_models": sorted(self.models[b])}
        gen_rows = [r for r in self.rows
                    if r["brand"] == b and r["model"] == m
                    and r["year_from"] <= year <= r["year_to"]]
        if not gen_rows:
            ranges = sorted({(r["year_from"], r["year_to"], r["generation"])
                             for r in self.rows if r["brand"] == b and r["model"] == m})
            return None, None, None, {"found": False,
                    "reason": f"{b} {m} üçün {year} ili heç bir nəsilə uyğun gəlmir.",
                    "available_year_ranges": [
                        {"from": f, "to": (t if t != 9999 else None), "generation": g}
                        for f, t, g in ranges]}
        return b, m, gen_rows, None

    def _vehicle_dict(self, b, m, gen_rows, year):
        r0 = gen_rows[0]
        yt = r0["year_to"]
        return {"brand": b, "model": m, "body_type": r0["body_type"],
                "generation": r0["generation"], "year": year,
                "year_range": f"{r0['year_from']}-{'indi' if yt == 9999 else yt}"}

    def vehicle_info(self, brand, model, year):
        """body_type, generation + the set of part codes valid for that gen (or None)."""
        b, m, gen_rows, err = self._resolve(brand, model, year)
        if err:
            return None
        info = self._vehicle_dict(b, m, gen_rows, year)
        info["available_codes"] = {r["part_code"] for r in gen_rows}
        return info

    # ----- the tool the agent calls (qty = 1 per listed code) -------------
    def estimate(self, brand: str, model: str, year: int, part_codes: list[str]) -> dict:
        b, m, gen_rows, err = self._resolve(brand, model, year)
        if err:
            return err
        by_code = {r["part_code"]: r for r in gen_rows}
        items, unmatched = [], []
        tot_min = tot_avg = tot_max = 0
        for pc in part_codes:
            code = pc if pc in by_code else self.resolve_part_code(pc)
            if not code or code not in by_code:
                unmatched.append(pc)
                continue
            r = by_code[code]
            items.append({"part_code": code, "part_az": r["part_name_az"],
                          "part_en": r["part_name_en"], "min": r["price_min_azn"],
                          "avg": r["price_avg_azn"], "max": r["price_max_azn"]})
            tot_min += r["price_min_azn"]; tot_avg += r["price_avg_azn"]; tot_max += r["price_max_azn"]
        return {"found": True, "vehicle": self._vehicle_dict(b, m, gen_rows, year),
                "items": items, "unmatched": unmatched,
                "totals": {"min": tot_min, "avg": tot_avg, "max": tot_max},
                "currency": "AZN", "price_type": "estimate"}

    # ----- quantity-aware estimate (used by the image / detection pipeline) 
    def estimate_items(self, brand, model, year, items):
        """items: iterable of (part_code, qty).  Prices multiplied by qty."""
        b, m, gen_rows, err = self._resolve(brand, model, year)
        if err:
            return err
        by_code = {r["part_code"]: r for r in gen_rows}
        lines, unmatched = [], []
        tot_min = tot_avg = tot_max = 0
        for pc, qty in items:
            code = pc if pc in by_code else self.resolve_part_code(pc)
            if not code or code not in by_code:
                unmatched.append(pc)
                continue
            r = by_code[code]
            lines.append({"part_code": code, "part_az": r["part_name_az"],
                          "part_en": r["part_name_en"], "qty": qty,
                          "unit_avg": r["price_avg_azn"],
                          "min": r["price_min_azn"] * qty,
                          "avg": r["price_avg_azn"] * qty,
                          "max": r["price_max_azn"] * qty})
            tot_min += r["price_min_azn"] * qty
            tot_avg += r["price_avg_azn"] * qty
            tot_max += r["price_max_azn"] * qty
        return {"found": True, "vehicle": self._vehicle_dict(b, m, gen_rows, year),
                "items": lines, "unmatched": unmatched,
                "totals": {"min": tot_min, "avg": tot_avg, "max": tot_max},
                "currency": "AZN", "price_type": "estimate"}

    # ----- catalog text injected into the system prompt -------------------
    def catalog_text(self) -> str:
        lines = ["VALID BRANDS & MODELS:"]
        for b in sorted(self.models):
            lines.append(f"  {b}: {', '.join(sorted(self.models[b]))}")
        lines.append("\nVALID PART CODES (code — Azərbaycanca (English) [category]):")
        for code in sorted(self.parts, key=lambda c: (self.parts[c]["category"], c)):
            meta = self.parts[code]
            lines.append(f"  {code} — {meta['az']} ({meta['en']}) [{meta['category']}]")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────
#  System prompt
# ─────────────────────────────────────────────────────────────────────────
def build_system_prompt(db: PriceDB) -> str:
    return f"""Sən CrashLogic/DentScan layihəsi üçün avtomobil hissələri qiymət agentisən.
Azərbaycan bazarı üçün hissə qiymətlərini hesablayırsan. İstifadəçi ilə AZƏRBAYCAN DİLİNDƏ danış.

İŞ QAYDASI:
1. İstifadəçinin mesajından markanı, modeli, ili və istədiyi hissələri müəyyən et.
   Nümunə: "mercedes e class 2018 qabaq bumper və arxa bumper"
   → brand="Mercedes-Benz", model="E-Class", year=2018,
     part_codes=["front_bumper_cover", "rear_bumper_cover"]
2. Danışıq dilindəki adları part_code-a çevir. Bəzi uyğunluqlar:
   qabaq/ön bumper|bufer → front_bumper_cover ; arxa bumper|bufer → rear_bumper_cover
   kapot → hood ; sol fara → left_headlight ; sağ fara → right_headlight
   sol/sağ stop → left/right_taillight ; krlo|qanad → *_fender
   güzgü → *_side_mirror_assembly ; disk → *_wheel ; şin → *_tire ; şüşə → *_windshield/window
   "hər iki fara" → left_headlight VƏ right_headlight (ikisini də əlavə et).
3. Qiyməti HƏMİŞƏ `estimate_parts` alətindən al. ÖZÜN qiymət uydurMA və cəmi ÖZÜN hesablaMA —
   həmişə alətin qaytardığı rəqəmləri işlət.
4. Nəticəni səliqəli təqdim et: hər hissə üçün orta qiymət (lazım olsa min–max diapazon),
   sonra CƏMİ (orta). Rəqəmlərin təxmini olduğunu qeyd et (analoq/işlənmiş Bakı bazarı).
5. Marka/model/hissə tapılmasa, aləti izləyib istifadəçiyə nəyin mövcud olduğunu de.
   İl yoxdursa və ya aydın deyilsə, soruş.

{db.catalog_text()}
"""


# ─────────────────────────────────────────────────────────────────────────
#  Gemini agent (chat)
# ─────────────────────────────────────────────────────────────────────────
def run_chat(db: PriceDB):
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        sys.exit("google-genai qurulmayıb.  ->  pip install google-genai")

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        sys.exit(".env faylında GEMINI_API_KEY tapılmadı "
                 "(və ya python-dotenv qurulmayıb: pip install python-dotenv).")

    # Tool exposed to Gemini. Signature + docstring become the function schema.
    def estimate_parts(brand: str, model: str, year: int, part_codes: list[str]) -> dict:
        """Azərbaycan bazarı üçün verilmiş avtomobil hissələrinin təxmini qiymətlərini
        CSV bazasından tapır və cəmini hesablayır.

        Args:
            brand: Marka, məs. "Mercedes-Benz", "BMW", "Toyota", "Hyundai".
            model: Model, məs. "E-Class", "3 Series", "Camry", "Land Cruiser Prado".
            year: Buraxılış ili, məs. 2018.
            part_codes: Kanonik part_code-ların siyahısı,
                        məs. ["front_bumper_cover", "rear_bumper_cover"].
        Returns:
            Tapılan avtomobil, hər hissə üçün min/orta/max qiymət, tapılmayan hissələr,
            və cəmi (min/orta/max) — hamısı AZN. price_type "estimate"dir.
        """
        return db.estimate(brand, model, year, part_codes)

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=build_system_prompt(db),
        tools=[estimate_parts],
        temperature=0,
    )
    chat = client.chats.create(model=MODEL_NAME, config=config)

    print("CrashLogic qiymət agenti (Gemini 2.5 Flash). Çıxmaq üçün 'exit'.\n"
          "Nümunə: mercedes e class 2018 qabaq bumper və arxa bumper\n")
    while True:
        try:
            user = input("Siz > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if user.lower() in ("exit", "quit", "çıx", "cix"):
            break
        if not user:
            continue
        try:
            resp = chat.send_message(user)
            print(f"\nAgent > {resp.text}\n")
        except Exception as e:
            print(f"\n[xəta] {e}\n")


# ─────────────────────────────────────────────────────────────────────────
#  Offline self-test (no API needed)
# ─────────────────────────────────────────────────────────────────────────
def run_test(db: PriceDB):
    print("Offline DB testi (Gemini olmadan)\n" + "-" * 40)
    cases = [
        ("mercedes", "e class", 2018, ["front_bumper_cover", "rear_bumper_cover"]),
        ("BMW", "3 Series", 2020, ["left_headlight", "right_headlight", "hood"]),
        ("toyota", "prado", 2019, ["tailgate", "front_left_fender"]),
        ("hyundai", "elantra", 2022, ["ön bamper", "sol fara"]),   # colloquial input
    ]
    for brand, model, year, parts in cases:
        res = db.estimate(brand, model, year, parts)
        print(f"\nInput: {brand} {model} {year} {parts}")
        if not res["found"]:
            print("  ->", res["reason"])
            continue
        v = res["vehicle"]
        print(f"  {v['brand']} {v['model']} ({v['generation']}, {v['year_range']})")
        for it in res["items"]:
            print(f"    - {it['part_az']}: {it['avg']} AZN  ({it['min']}–{it['max']})")
        if res["unmatched"]:
            print("    tapılmadı:", res["unmatched"])
        print(f"    CƏMİ (orta): {res['totals']['avg']} AZN  "
              f"(diapazon {res['totals']['min']}–{res['totals']['max']})")


def main():
    if not os.path.exists(CSV_PATH):
        sys.exit(f"CSV tapılmadı: {CSV_PATH}\nCSV_PATH dəyişəni ilə yol göstərə bilərsiniz.")
    db = PriceDB(CSV_PATH)
    if "--test" in sys.argv:
        run_test(db)
    else:
        run_chat(db)


if __name__ == "__main__":
    main()