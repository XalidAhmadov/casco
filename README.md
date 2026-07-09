# CasCo 🚗💥

![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Models](https://img.shields.io/badge/models-YOLOv11--seg%20%C3%97%202-orange)
![Agent](https://img.shields.io/badge/agent-Gemini%202.5%20Flash-purple)

CrashLogic analyzes a photo of a damaged car and produces an **itemized repair-cost estimate calibrated to the Azerbaijani market**. Two computer-vision models work together — one identifies **which part** is damaged, the other classifies the **type of damage** (scratch / dent / crack / …). A fusion step maps each damage onto the part it sits on, and a recommendation engine decides **repair vs. replacement** and prices it from a local parts + labor database.

Built as a two-stage segmentation pipeline: **part segmentation + damage segmentation → fusion → repair/replace recommendation → cost.**

---

## Why two models

A single flat model that mixes part and damage into one label set (e.g. `bonnet-dent`, `bumper-damage`) is data-hungry, class-imbalanced, and usually collapses damage into just "dent" — losing `scratch` and `crack`. CrashLogic splits the problem into two **single-task** segmentation models, each trained on clean data:

- **Part model** → *which* panel is damaged (`front_bumper`, `hood`, `front_door`, …)
- **Damage model** → *what kind* of damage (`scratch`, `dent`, `crack`, `glass shatter`, `lamp broken`, `tire flat`)

Segmentation masks (not boxes) let the fusion step assign damage to the correct part precisely, and each model can be improved independently. This is both **more accurate** and the only way to get the damage **type**, which drives the repair-vs-replace decision.

---

## Current Status

| Component | Status | Notes |
| --- | --- | --- |
| Parts price database | ✅ Working | `car_parts_prices.csv` — 2107 rows: 12 models × generations × 44 parts, min/avg/max AZN |
| Repair / labor price table | ✅ Working | `repair_prices.csv` — Baku rates + premium-brand labor factor |
| Price lookup engine (`PriceDB`) | ✅ Working | year → generation resolution, fuzzy part-code matching |
| Text price agent (Gemini 2.5 Flash) | ✅ Working | natural-language part → price + total, function-calling |
| Damage-type model (scratch/dent/crack) | ✅ Working | CarDD YOLOv11-seg checkpoint (6 classes), fine-tune optional |
| Part segmentation model | 🔧 In progress | fine-tune COCO `yolo11n-seg` → carparts-seg |
| Mask fusion (damage → part) | ✅ Working | IoU overlap, severity from affected-area ratio |
| Recommendation engine (repair vs replace) | ✅ Working | per-damage decision + cost, savings vs full replacement |
| Full image pipeline | ✅ Working | image → 2 models → fusion → recommendation → JSON (wiring unit-tested) |
| Train & eval (baseline vs fine-tune) | ✅ Working | writes precision / recall / mAP comparison CSV |
| Streamlit web UI | 📋 Planned | image upload → annotated result + estimate table |
| FastAPI backend | 📋 Planned | `POST /analyze` incident endpoint |
| Live / mobile capture | 📋 Planned | phone photo → instant estimate |

> The deterministic components (price DB, fusion, recommendation, pipeline wiring) are covered by offline self-tests (`--selftest`). Training the **part** model is the remaining step before full end-to-end inference on real photos.

---

## Repository layout

```
crashlogic/
├── car_price_agent.py      # PriceDB + Gemini 2.5 Flash chat agent
├── pipeline.py             # full image → estimate pipeline (2 models)
├── fusion.py               # maps damage masks → part masks (IoU) + severity
├── recommendation.py       # repair vs replace decision + cost
├── detector.py             # single-model damage detector (simple bridge)
├── train_and_eval.py       # Colab training + baseline vs fine-tune metrics
├── car_parts_prices.csv    # part replacement prices (AZN)
├── repair_prices.csv       # labor / repair prices (AZN)
├── requirements.txt
└── .env.example
```

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/XalidAhmadov/casco.git
cd casco

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env          # Windows: copy .env.example .env
# Open .env and add your GEMINI_API_KEY
```

`requirements.txt`:

```
ultralytics
numpy
google-genai
python-dotenv
huggingface_hub
```

`.env`:

```
GEMINI_API_KEY=your_gemini_api_key_here
# optional, if the CSVs are not next to the scripts:
CSV_PATH=car_parts_prices.csv
REPAIR_CSV_PATH=repair_prices.csv
```

Before touching any API you can verify the whole non-model core offline:

```bash
python car_price_agent.py --test      # price DB + resolution
python fusion.py                      # mask fusion (synthetic masks)
python recommendation.py              # repair vs replace decisions
python pipeline.py --selftest         # full pipeline with mock models
```

---

## Usage

### 1. Text price agent — no image needed

Type a car + parts in plain (Azerbaijani/mixed) language; the agent maps them to part codes, looks up prices, and sums the total.

```bash
python car_price_agent.py
```

```
Siz > mercedes e class 2018 qabaq bumper və arxa bumper
Agent > E-Class (W213, 2016–2020):
          • Ön bamper örtüyü: 550 AZN
          • Arxa bamper örtüyü: 575 AZN
        CƏMİ (orta): 1125 AZN   (təxmini, analoq/işlənmiş Bakı bazarı)
```

### 2. Full image pipeline — 2 models

```bash
python pipeline.py \
  --image crash.jpg \
  --brand mercedes --model "e class" --year 2018 \
  --part-weights parts_best.pt \
  --damage-weights cardd_best.pt
```

Add `--json` for machine-readable output.

### Output — estimate contract

```json
{
  "vehicle": {
    "brand": "Mercedes-Benz", "model": "E-Class",
    "generation": "W213 (pre-facelift)", "year": 2018,
    "year_range": "2016-2020", "body_type": "Sedan"
  },
  "findings": [
    { "part_code": "front_bumper_cover", "damage_type": "scratch",
      "severity": "minor", "confidence": 0.81, "overlap": 1.0 },
    { "part_code": "hood", "damage_type": "dent",
      "severity": "severe", "confidence": 0.77 }
  ],
  "lines": [
    { "part_az": "Ön bamper örtüyü", "damage": "scratch", "severity": "minor",
      "action": "Cilalama", "basis": "labor", "cost_avg": 56 },
    { "part_az": "Kapot", "damage": "dent", "severity": "severe",
      "action": "Panel əvəzləmə", "basis": "replace", "cost_avg": 600 }
  ],
  "recommended_total": { "min": 798, "avg": 1456, "max": 2898 },
  "replace_all_total_avg": 1950,
  "savings_avg": 494,
  "currency": "AZN",
  "price_type": "estimate"
}
```

> **Note on prices:** all figures are `price_type: "estimate"` — anchored on real Baku listings, but the same part varies 5–20× between original / aftermarket / used, so numbers are meant to be tuned with real quotes, not treated as fixed retail.

---

## Training the models

Run in Google Colab (GPU runtime). Each stage evaluates the model **before and after** fine-tuning and writes `metrics_comparison.csv`.

```bash
!pip install -q ultralytics huggingface_hub roboflow

# Part model — carparts-seg auto-downloads via ultralytics
!python train_and_eval.py --stage parts --epochs 60

# Damage model — CarDD dataset (segmentation format), strong base checkpoint
!python train_and_eval.py --stage damage --data CarDD/data.yaml --epochs 60 \
    --base-weights cardd_base_best.pt

# Weights are copied to parts_best.pt and cardd_best.pt for pipeline.py
```

The **part** baseline scores ≈ 0 (COCO doesn't know "hood"/"bumper") — that is the honest "untrained" number, and the jump after fine-tuning is the headline metric. The **damage** model starts from a real CarDD checkpoint, so its baseline is already strong and fine-tuning is a refinement.

> If you're short on time, train **only the part model** and use the CarDD damage checkpoint as-is — the pipeline still runs end-to-end.

---

## Pipeline Architecture

```
                         image (damaged car)
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
         1. Part model                   2. Damage model
       YOLOv11-seg (carparts)          YOLOv11-seg (CarDD)
         → which part                  → scratch / dent / crack …
                 └───────────────┬───────────────┘
                                 ▼
                       Fusion (IoU overlap)
                    damage-on-part + severity
                                 │
                                 ▼
                    Recommendation engine
                     repair vs. replace
            parts price CSV + repair price CSV
                                 │
                                 ▼
              estimate report + TOTAL (AZN) / JSON
```

---

## Datasets

| Model | Base weights | Dataset |
| --- | --- | --- |
| Part segmentation | `yolo11n-seg` (COCO) | Ultralytics **carparts-seg** (auto-downloads) |
| Damage segmentation | CarDD YOLO-seg checkpoint | **CarDD** — 6 classes (dent, scratch, crack, glass shatter, lamp broken, tire flat), via Roboflow / Kaggle |

Price data is maintained in this repo as CSVs:

- `car_parts_prices.csv` — replacement prices for 44 parts across 12 models and their generations (Mercedes E/C/S, BMW 3/5/7, Toyota Camry/Corolla/Prado, Hyundai Accent/Elantra/Sonata), with `year_from`/`year_to` for lookup.
- `repair_prices.csv` — labor rates for polish, PDR, dent+paint, plastic repair, etc.

---

## Roadmap

- Streamlit UI: upload photo → annotated masks + estimate table
- FastAPI `POST /analyze`: image + vehicle → estimate JSON
- More brands / models and hatchback / wagon body types
- Per-supplier pricing (turbo.az, lalafo.az) and original-vs-aftermarket toggle
- Live / mobile capture for on-the-spot estimates

---

## Team

CrashLogic · Data & AI · 2026

- Ilaha Shafizada
- Nurana Aliyarli
- Ravan Khanbabayev
- Khalid Ahmadov

GitHub Organization · Project Board

---

## License

This project is licensed under the MIT License.

