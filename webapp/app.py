#!/usr/bin/env python3
"""
CrashLogic / DentScan — FastAPI web app
=======================================
Exposes the two existing CLI entry points over HTTP:

    POST /api/analyze  — photo + brand/model/year → damage report (pipeline.py)
    POST /api/chat     — Azerbaijani price chat (car_price_agent.py + Gemini)
    GET  /api/catalog  — brands/models/generations for the dropdowns

Run from the repo root:
    uvicorn webapp.app:app --port 8000
"""

import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

# make the CSV resolvable no matter what the server's cwd is
os.environ.setdefault("CSV_PATH", str(ROOT / "car_parts_prices.csv"))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from car_price_agent import CSV_PATH, MODEL_NAME, PriceDB, build_system_prompt

WEBAPP = Path(__file__).resolve().parent
OUTPUTS = WEBAPP / "outputs"
OUTPUTS.mkdir(exist_ok=True)

PART_WEIGHTS = ROOT / "parts_best.pt"
DAMAGE_WEIGHTS = ROOT / "cardd_best.pt"

app = FastAPI(title="CrashLogic / DentScan")

db = PriceDB(CSV_PATH)


def _jsonable(o):
    """Reports may contain sets (e.g. vehicle_info available_codes)."""
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, set):
        return sorted(o)
    return o


# ── catalog ───────────────────────────────────────────────────────────────
@app.get("/api/catalog")
def catalog():
    out = {}
    seen = set()
    for r in db.rows:
        key = (r["brand"], r["model"], r["generation"])
        if key in seen:
            continue
        seen.add(key)
        out.setdefault(r["brand"], {}).setdefault(r["model"], []).append({
            "generation": r["generation"],
            "year_from": r["year_from"],
            "year_to": r["year_to"],
        })
    for models in out.values():
        for gens in models.values():
            gens.sort(key=lambda g: g["year_from"])
    return out


# ── damage analysis (lazy-loads the YOLO weights on first request) ───────
_pipeline = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        missing = [p.name for p in (PART_WEIGHTS, DAMAGE_WEIGHTS) if not p.exists()]
        if missing:
            raise HTTPException(503, f"Model çəkiləri tapılmadı: {', '.join(missing)}")
        from pipeline import DamagePipeline, SegModel
        _pipeline = DamagePipeline(db,
                                   SegModel(str(PART_WEIGHTS)),
                                   SegModel(str(DAMAGE_WEIGHTS)))
    return _pipeline


@app.post("/api/analyze")
async def analyze(image: UploadFile = File(...),
                  brand: str = Form(...),
                  model: str = Form(...),
                  year: int = Form(...)):
    pipe = get_pipeline()
    suffix = Path(image.filename or "upload.jpg").suffix.lower() or ".jpg"
    uid = uuid.uuid4().hex[:12]
    img_path = OUTPUTS / f"{uid}_src{suffix}"
    img_path.write_bytes(await image.read())
    ann_path = OUTPUTS / f"{uid}_annotated.jpg"
    try:
        res = pipe.analyze(str(img_path), brand, model, year,
                           annotate_path=str(ann_path))
    except Exception as e:
        raise HTTPException(500, f"Analiz xətası: {e}")
    res = _jsonable(res)
    res["annotated_url"] = f"/outputs/{ann_path.name}" if ann_path.exists() else None
    res["source_url"] = f"/outputs/{img_path.name}"
    return res


# ── price chat (Gemini, per-session history) ──────────────────────────────
class ChatReq(BaseModel):
    session_id: str
    message: str
    lang: str = "az"


_client = None
_sessions: dict = {}
MAX_SESSIONS = 200


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(503, "GEMINI_API_KEY qurulmayıb — çat agenti aktiv deyil. "
                                     "(.env faylına GEMINI_API_KEY=... əlavə edin)")
        from google import genai
        _client = genai.Client(api_key=api_key)
    return _client


def _new_chat():
    from google.genai import types

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

    config = types.GenerateContentConfig(
        system_instruction=build_system_prompt(db),
        tools=[estimate_parts],
        temperature=0,
    )
    return _get_client().chats.create(model=MODEL_NAME, config=config)


@app.post("/api/chat")
def chat(req: ChatReq):
    chat_obj = _sessions.get(req.session_id)
    if chat_obj is None:
        if len(_sessions) >= MAX_SESSIONS:
            _sessions.pop(next(iter(_sessions)))
        chat_obj = _new_chat()
        _sessions[req.session_id] = chat_obj
    msg = req.message
    if req.lang == "en":
        msg += "\n\n(Please answer in English.)"
    try:
        resp = chat_obj.send_message(msg)
    except Exception as e:
        raise HTTPException(502, f"Gemini xətası: {e}")
    return {"reply": resp.text or ""}


# ── static frontend ───────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=WEBAPP / "static"), name="static")
app.mount("/outputs", StaticFiles(directory=OUTPUTS), name="outputs")


@app.get("/")
def index():
    return FileResponse(WEBAPP / "static" / "index.html")
