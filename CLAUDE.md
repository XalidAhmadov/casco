# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

CrashLogic / DentScan — a car-crash-damage estimator for the Azerbaijani (Baku) market. Two independent entry points share the same `PriceDB` core:

1. **Chat agent** (`car_price_agent.py`): natural-language (Azerbaijani) part-price lookup via Gemini 2.5 Flash function-calling. The LLM only extracts `brand/model/year/part_codes` and formats the reply — it never invents prices or does arithmetic; `PriceDB.estimate()` in Python is the sole source of numbers.
2. **CV pipeline** (`pipeline.py`): photo → two YOLO11-seg models → IoU fusion → repair/replace recommendation → priced report. No LLM involved.

## Commands

```bash
pip install -r requirements.txt

# Chat agent (needs GEMINI_API_KEY in .env)
python car_price_agent.py            # interactive chat
python car_price_agent.py --test     # offline DB test, no API key needed

# Recommendation engine demo (offline, mock findings)
python recommendation.py

# Fusion layer selftest (synthetic masks, no models needed)
python fusion.py

# Annotation overlay selftest (synthetic image, needs opencv-python)
python annotate.py

# Full pipeline
python pipeline.py --selftest        # offline, mock YOLO models
python pipeline.py --image crash.jpg --brand mercedes --model "e class" --year 2018 \
    --part-weights parts_best.pt --damage-weights cardd_best.pt \
    [--json] [--save-annotated [path]]

# Training / evaluation (Colab / GPU machine)
python train_and_eval.py --stage parts  --epochs 60
python train_and_eval.py --stage damage --data cardd.yaml --epochs 60

# Web app (FastAPI, serves both features at http://127.0.0.1:8000)
python -m uvicorn webapp.app:app --port 8000    # run from repo root
```

There is no test framework — each module's `if __name__ == "__main__"` block (or `--selftest`/`--test` flag) is its offline self-check. Run the relevant one after touching that module.

## Architecture

```
image ──► 1. PART model   (YOLO11-seg, carparts-seg)     ─┐
      ──► 2. DAMAGE model (YOLO11-seg, CarDD classes)     ├─► fusion.py (IoU)
                                                            ─┘      │
                                                                    ▼
                                         recommendation.py (repair vs replace)
                                           car_parts_prices.csv + repair_prices.csv
                                                                    │
                                                                    ▼
                                                    report + TOTAL (AZN)
```

- **`car_price_agent.py`** — defines `PriceDB`, the shared pricing core, loaded from `car_parts_prices.csv` (path overridable via `CSV_PATH` env var). Key methods: `estimate()` (qty=1 per part, used by the chat agent), `estimate_items()` (qty-aware, used by the CV pipeline), `resolve_part_code()` / `normalize_brand()` / `normalize_model()` (colloquial Azerbaijani input → canonical brand/model/part_code, used as a fallback safety net — Gemini is the primary resolver via the catalog text injected into the system prompt). `vehicle_info()` returns the valid part-code set for a given brand/model/year without pricing anything.
- **`fusion.py`** — combines part-model and damage-model detections purely via mask IoU. `PARTCLASS_TO_CODE` maps Ultralytics carparts-seg class names to canonical `part_code`s (unknown names fall through to `PriceDB.resolve_part_code` later). Severity is derived from `|damage ∩ part| / |part|`: <10% minor, <35% moderate, else severe. `fuse()` deduplicates by `(part_code, damage_type)` keeping the worst severity and returns `(findings, orphans)` — orphans are damages that didn't land ≥30% (`MIN_OVERLAP`) inside any part mask.
- **`recommendation.py`** — `RecommendationEngine.recommend()` turns `findings` (from fusion or manual input) into repair-vs-replace decisions via `decide()`: damage *type* (scratch/dent/crack/glass_shatter/lamp_broken/tire_flat) × part *kind* (`classify_kind()`: glass/lamp/wheel/tire/mirror/plastic_cover/metal_panel/trim) × severity → an action. Replace costs come from `PriceDB`; repair/labor costs come from `repair_prices.csv` (or `LABOR` defaults if the CSV is missing), scaled by `LABOR_BRAND_FACTOR` (premium brands cost more to repair).
- **`pipeline.py`** — wires `SegModel` (thin YOLO wrapper) → `fusion.fuse()` → `RecommendationEngine.recommend()` into `DamagePipeline.analyze()`, plus optional annotated-image output via `annotate.py`. This is the module to run end-to-end against real weights/photos.
- **`annotate.py`** — draws part masks (translucent, per-class color) and damage masks (bold red, labelled `damage_type->part_code (severity)`) onto the source photo using OpenCV. Colors are deterministic (MD5 hash of class name), labels are ASCII-only.
- **`webapp/`** — FastAPI web UI over both entry points (no changes to core modules). `webapp/app.py` exposes `GET /api/catalog` (dropdown data from `db.rows`), `POST /api/analyze` (multipart image + brand/model/year → `DamagePipeline.analyze()` report + annotated image served from `webapp/outputs/`), and `POST /api/chat` (per-session Gemini chat, in-memory sessions; returns a graceful 503 if `GEMINI_API_KEY` is missing). YOLO weights are lazy-loaded on the first analyze request. Frontend is vanilla HTML/CSS/JS in `webapp/static/` (dark theme, AZ/EN i18n dict in `app.js` — backend action strings are Azerbaijani, mapped to English client-side via `ACTION_EN`).
- **`train_and_eval.py`** — Colab/GPU training driver for both models. Stage `parts` fine-tunes COCO-pretrained `yolo11n-seg` on Ultralytics' `carparts-seg` dataset (auto-downloads); the untrained baseline scores ~0 because COCO has no part classes, which is expected/documented. Stage `damage` fine-tunes a CarDD checkpoint (downloaded from HF hub `harpreetsahota/car-dd-segmentation-yolov11` unless `--base-weights` given) on a CarDD-format dataset. Always evaluates baseline-before / best-after and appends both rows to `metrics_comparison.csv`.

## Data files

- **`car_parts_prices.csv`** — the price catalog: `brand, model, body_type, generation, year_from, year_to, category, part_code, part_name_en, part_name_az, price_min_azn, price_avg_azn, price_max_azn`. Adding a new brand/model/generation/part means adding rows here; `PriceDB` picks them up automatically (no code changes needed) as long as `part_code` stays consistent across call sites.
- **`repair_prices.csv`** — labor/repair action price table (`action_code, action_az, action_en, price_min/avg/max_azn`), keyed by the `action_code`s returned from `recommendation.decide()` (e.g. `polish`, `pdr`, `dent_paint`, `wheel_refinish`).
- **`parts_best.pt` / `cardd_best.pt`** — trained YOLO11-seg weights for the part and damage models respectively (outputs of `train_and_eval.py`).

## Conventions

- All user-facing chat/report text is in Azerbaijani; code identifiers, comments, and `part_code`/`action_code` values are English snake_case.
- `part_code` is the canonical join key across every module (CSV rows, fusion output, recommendation input/output) — never key on raw class names or free-text part descriptions.
- Money is always `(min, avg, max)` in AZN; never compute or print a single price without carrying the range, and never let an LLM compute totals — only `PriceDB`/`RecommendationEngine` arithmetic is trusted.
